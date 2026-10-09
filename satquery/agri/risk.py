"""The explainable crop & pest risk score: three indicators per pest, weighted, every step visible.

Factors, each scored 0..1 by rules kept as data (`config.py`):
  weather_pest     how many recent and forecast days were favourable for this pest (`rules.py`)
  ndvi_anomaly     how far vegetation (NDVI) is below the same dates in earlier years (`ndvi.py`);
                   supporting evidence of a change in vegetation, never pest detection
  report_pressure  field observations of this pest in the area, weighted by severity
                   (SAMPLE data in this prototype; `observations.py` for a real dataset)

Each pest or disease with a weather rule or field observations is scored on its own; the area's
figure is that of its highest pest (`driver_pest`), and every pest's breakdown is kept
(`pest_risks`). Score = sum(weight x factor score) / sum(weight), shown as 0-100 with each factor's
points, so the score is always the sum of its visible parts.

Missing data is never filled in. By default (`missing_inputs: lower_bound`) a missing factor adds no
points but keeps its weight, so losing data can never raise a score. Data completeness is the share
of the weight backed by REAL data: SAMPLE (synthetic) evidence is scored and labelled, but never
counted as data. `score_range` is the band the real evidence allows (real points alone, up to that
plus every unavailable or SAMPLE input at full weight), and the score is also given without the
SAMPLE evidence, so it is visible how far a level rests on it. Below a minimum completeness no level
is given. "Critical" also needs two independent, real indicators. Field evidence keeps "no
observations available" apart from "no pest observed" (`details.evidence_state`). Known pests with
neither a weather rule nor field evidence are listed as not assessed, with no score. The score is
UNCALIBRATED until validated against outcomes, whatever the thresholds' status.

This is decision support: indicators suggest a risk level; nothing here detects or confirms an
outbreak. Confidence is a rule-based label, not a calibrated probability.
"""

from datetime import date

from satquery.agri import weather as weather_data
from satquery.agri.areas import extent_km
from satquery.agri.config import PestRulesConfig, RiskModelConfig, thresholds_status
from satquery.agri.models import (DISCLAIMER, PLACEHOLDER_NOTE, SAMPLE_LABEL, FactorResult, MonitoredArea,
                                  NdviAnomaly, PestEvaluation, PestNotAssessed, PestReport, PestRiskAssessment,
                                  Provenance, RiskAssessment, RiskConfidence)
from satquery.agri.ndvi import NdviClient
from satquery.agri.observations import AreaObservation, AreaObservations

FACTOR_NAMES = {"weather_pest": "Pest-favourable weather",
                "ndvi_anomaly": "Vegetation condition vs earlier years (NDVI)",
                "report_pressure": "Pest/disease field observations"}
LEVEL_ORDER = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3, "INSUFFICIENT_DATA": 4}
CONFIDENCE_METHOD = ("Rule-based label, not a calibrated probability: data completeness (the share of the model's "
                     "weight backed by real data) sets it (high at or above the high cut, medium at or above the "
                     "medium cut); it is capped at medium when an input is SAMPLE data and at low while any threshold "
                     "is a PLACEHOLDER.")
NDVI_CAVEAT = ("An NDVI change is supporting evidence of a change in vegetation condition, not pest or disease "
               "detection: low NDVI has many causes.")


def observation_name(sample: bool) -> str:
    return FACTOR_NAMES["report_pressure"] + (" (SAMPLE)" if sample else "")


def _unavailable(factor_id: str, weight: float, reason: str, provenance: list[Provenance] | None = None,
                 name: str | None = None, **extra) -> FactorResult:
    return FactorResult(id=factor_id, name=name or FACTOR_NAMES[factor_id], status="unavailable", score=None,
                        weight=weight, availability=0.0, summary=f"Unavailable: {reason}", unavailable_reason=reason,
                        provenance=provenance or [], **extra)


# ----------------------------------------------------------------------------------- factors

def weather_factor(pests: list[PestEvaluation], weather: weather_data.HourlyWeather | None, error: str | None,
                   model: RiskModelConfig, area: MonitoredArea, today: date) -> FactorResult:
    """Pest-favourable weather for the given pests (one pest for a per-pest score), driven by the
    most favourable of them."""
    weight = model.weights["weather_pest"]
    if weather is None:
        reason = error or "no weather data"
        return _unavailable("weather_pest", weight, reason,
                            [Provenance(source=weather_data.SOURCE, state="UNAVAILABLE", note=reason)])
    evaluated = [p for p in pests if p.index is not None]
    thresholds = "PLACEHOLDER" if any(p.thresholds == "PLACEHOLDER" for p in pests) else "VERIFIED"
    if not evaluated:
        return _unavailable("weather_pest", weight, "no day had enough hourly weather data to judge the pest rules",
                            [weather.provenance()], thresholds=thresholds)
    driver = max(evaluated, key=lambda p: (p.index, p.longest_run))
    judged = [(p.known_past + p.known_forecast) / (p.past_days + p.forecast_days) for p in pests]
    availability = round(sum(judged) / len(judged), 3)
    reasons = [p.explanation for p in sorted(evaluated, key=lambda p: -p.index)]
    width, height = extent_km(area)
    if max(width, height) > model.weather_point_span_km:
        reasons.append(f"Weather is for one point inside the area, which spans about {width:.0f} x {height:.0f} km; "
                       "conditions can differ across it.")
    if weather.stale:
        reasons.append(f"Weather is a STALE cached copy ({weather.stale_reason or 'not refreshed'}).")
    days = driver.favourable_past + driver.favourable_forecast
    calculation = weather_calculation(driver, model.calibration.status)
    if calculation["saturated"]:
        reasons.append(f"{driver.name}: the index is capped at 1.0. {days} favourable days exceed the "
                       f"{driver.full_score_days} that give the full score (full_score_days, a {driver.thresholds} "
                       f"parameter), so {driver.full_score_days} to {calculation['window_days']} favourable days all "
                       "score the same.")
    if driver.favourable_forecast:
        reasons.append(f"{driver.favourable_forecast} of the {days} favourable days are forecast days, counted like past "
                       "days (an uncalibrated choice; a forecast is less certain than the model's past analyses).")
    return FactorResult(
        id="weather_pest", name=FACTOR_NAMES["weather_pest"], weight=weight, score=driver.index,
        status="ok" if availability == 1 else "partial", availability=availability,
        summary=f"{driver.name}: favourable weather on {days} day(s) of the "
                f"{driver.past_days}+{driver.forecast_days}-day window (index {driver.index:.2f})",
        reasons=reasons, thresholds=thresholds, provenance=[weather.provenance()],
        details={"driver": driver.pest_id, "pests": [p.model_dump(exclude={"days"}) for p in pests],
                 "calculation": calculation, "weather_summary": weather_data.summarise(weather, today),
                 "point": {"latitude": weather.latitude, "longitude": weather.longitude}})


def weather_calculation(p: PestEvaluation, calibration: str) -> dict:
    """The weather index of one pest, step by step, so it can be checked by hand."""
    favourable = p.favourable_past + p.favourable_forecast
    return {"formula": "index = min(1, favourable days / full_score_days)",
            "favourable_past_days": p.favourable_past, "favourable_forecast_days": p.favourable_forecast,
            "judged_days": p.known_past + p.known_forecast, "window_days": p.past_days + p.forecast_days,
            "full_score_days": p.full_score_days, "uncapped_ratio": round(favourable / p.full_score_days, 3),
            "index": p.index, "saturated": favourable > p.full_score_days,
            "forecast_share": round(p.favourable_forecast / favourable, 3) if favourable else None,
            "thresholds": p.thresholds, "calibration": calibration}


def ndvi_factor(anomaly: NdviAnomaly | None, error: str | None, model: RiskModelConfig) -> FactorResult:
    weight, cfg = model.weights["ndvi_anomaly"], model.ndvi
    if anomaly is None:
        return _unavailable("ndvi_anomaly", weight, error or "no imagery provider configured", thresholds=model.status)
    provenance = NdviClient.provenance(anomaly)
    details = {"anomaly": anomaly.model_dump()}
    if not anomaly.current.usable:
        return _unavailable("ndvi_anomaly", weight, f"current NDVI unavailable ({anomaly.current.reason})", provenance,
                            details=details, thresholds=model.status)
    if anomaly.relative_change is None:
        missing = "; ".join(f"{w.label}: {w.reason}" for w in anomaly.baseline if not w.usable)
        return _unavailable("ndvi_anomaly", weight,
                            f"baseline unavailable: {anomaly.baseline_years_used} of {cfg.baseline_years} earlier years "
                            f"observed clearly, {cfg.min_baseline_years} needed ({missing})", provenance,
                            details=details, thresholds=model.status)
    change, current = anomaly.relative_change, anomaly.current
    drop = max(0.0, -change)
    low = cfg.ignore_relative_drop_below
    score = 0.0 if drop <= low else min(1.0, (drop - low) / (cfg.relative_drop_for_full_score - low))
    years = ", ".join(w.label for w in anomaly.baseline if w.usable)
    direction = "below" if change < 0 else "above"
    reasons = [f"NDVI over the observed land in the last {cfg.window_days} days is {current.mean:.2f}, "
               f"{abs(change):.0%} {direction} the {anomaly.baseline_mean:.2f} average for the same dates in {years}.",
               f"{current.observed_fraction:.0%} of the area had at least one clear Sentinel-2 view in the window."]
    low_b, high_b = anomaly.baseline_range
    reasons.append(f"That is {'within' if anomaly.within_baseline_range else 'outside'} the range of those years "
                   f"({low_b:.2f}-{high_b:.2f}).")
    reasons.append("NDVI covers all clear land in the area (crops, trees, grass), not cropland alone; a change can "
                   "also come from sowing or harvest timing.")
    reasons.append(NDVI_CAVEAT)
    availability = round(anomaly.baseline_years_used / cfg.baseline_years, 3)
    return FactorResult(id="ndvi_anomaly", name=FACTOR_NAMES["ndvi_anomaly"], weight=weight, score=round(score, 3),
                        status="ok" if availability == 1 else "partial", availability=availability,
                        summary=f"NDVI {current.mean:.2f} vs {anomaly.baseline_mean:.2f} baseline ({change:+.0%})",
                        reasons=reasons, provenance=provenance, details=details, thresholds=model.status)


EVIDENCE_STATES = {
    "NO_SOURCE": "no observations available: no pest-observation source is connected",
    "NOT_COVERED": "no observations available: the source does not survey this area",
    "NOT_SURVEYED": "no observations available: the source does not survey this pest",
    "COVERAGE_UNKNOWN": "no observations available: no records, and the source does not state what it surveys",
    "HISTORICAL_ONLY": "no current observations: only HISTORICAL records, older than the look-back window",
    "NONE_OBSERVED": "no pest observed by REAL surveillance that covers this area and pest",
    "SAMPLE_NONE": "no pest in the SAMPLE simulation (not an observation of absence)",
    "OBSERVED": "pest/disease observed",
}


def observation_factor(pest_id: str | None, evidence: AreaObservations | None, model: RiskModelConfig) -> FactorResult:
    """Field evidence for one pest (or all pests when `pest_id` is None). A record inside the area
    counts fully, a district-level record by `district_match_weight`; a record with no readable
    severity is listed but adds nothing.

    "No observations available" and "no pest observed" are kept apart (`details.evidence_state`):
    no records is zero evidence (NONE_OBSERVED) only where a REAL source states that it surveys the
    area and the pest. Otherwise the factor is unavailable and adds nothing; records older than the
    window are HISTORICAL context, never current evidence."""
    weight, cfg = model.weights["report_pressure"], model.reports
    if evidence is None:
        return _unavailable("report_pressure", weight, "no pest-observation source is connected",
                            thresholds=model.status, details={"evidence_state": "NO_SOURCE",
                                                              "evidence": EVIDENCE_STATES["NO_SOURCE"]})
    sample, name = evidence.sample, observation_name(evidence.sample)
    label = "SAMPLE" if sample else "REAL"
    what = "pest/disease" if pest_id is None else pest_id.replace("_", " ")
    items = evidence.items if pest_id is None else evidence.for_pest(pest_id)
    historical = evidence.historical if pest_id is None else evidence.historical_for(pest_id)
    latest = max((o.observed_on for o in historical), default=None)

    def unavailable(state: str, reason: str) -> FactorResult:
        return _unavailable("report_pressure", weight, reason, [evidence.provenance], name=name, sample_data=sample,
                            thresholds=model.status,
                            details={"evidence_state": state, "evidence": EVIDENCE_STATES[state],
                                     "coverage": evidence.coverage, "historical_count": len(historical),
                                     "latest_historical": latest})

    if evidence.coverage == "not_covered":
        return unavailable("NOT_COVERED", evidence.coverage_note.rstrip("."))
    if not items and pest_id is not None and evidence.surveys(pest_id) is False:
        return unavailable("NOT_SURVEYED", f"the observation source does not survey {what}")
    if not items and evidence.coverage == "unknown":
        if historical:
            return unavailable("HISTORICAL_ONLY",
                               f"only HISTORICAL {what} records for this area (latest {latest}), older than the "
                               f"{evidence.lookback_days}-day window: context, not current evidence")
        return unavailable("COVERAGE_UNKNOWN",
                           f"no {what} records for this area in the last {evidence.lookback_days} days, and the source "
                           "does not state its surveillance coverage, so no records is not evidence of no pests")
    state = "OBSERVED" if items else "SAMPLE_NONE" if sample else "NONE_OBSERVED"

    def strength(item: AreaObservation) -> float:
        return cfg.severity_weights[item.severity] * (1.0 if item.match == "inside_area" else cfg.district_match_weight)

    scored = [i for i in items if i.severity is not None]
    weighted = round(sum(strength(i) for i in scored), 3)
    score = min(1.0, weighted / cfg.weighted_count_for_full_score)
    by_pest, by_severity = {}, {"low": 0, "moderate": 0, "high": 0}
    for item in items:
        by_pest[item.observation.pest] = by_pest.get(item.observation.pest, 0) + 1
    for item in scored:
        by_severity[item.severity] += 1
    district_level = sum(1 for i in items if i.match == "same_district")
    if items:
        pests = ", ".join(f"{p.replace('_', ' ')} x{n}" for p, n in sorted(by_pest.items()))
        reasons = [f"{len(items)} {label} {what} observation(s) in the last {evidence.lookback_days} days in the area "
                   f"({pests}; {by_severity['high']} high severity)."]
    elif sample:
        reasons = [f"No SAMPLE {what} observations in the last {evidence.lookback_days} days in the area: the "
                   "simulation produced none, which is not an observation of absence."]
    else:
        reasons = [f"No REAL {what} observations in the last {evidence.lookback_days} days in the area: none observed "
                   f"by a source that surveys it ({evidence.coverage_note.rstrip('.')})."]
    if district_level:
        reasons.append(f"{district_level} of them are district-level records (not located inside the zone), weighted "
                       f"{cfg.district_match_weight:g}.")
    if len(scored) < len(items):
        reasons.append(f"{len(items) - len(scored)} record(s) have no severity the engine can read: "
                       + "; ".join(sorted({i.severity_basis for i in items if i.severity is None})) + ".")
    if historical:
        reasons.append(f"{len(historical)} HISTORICAL {what} record(s) (latest {latest}) are older than the "
                       f"{evidence.lookback_days}-day window: context only, not current evidence.")
    if sample:
        reasons[0] += f" {SAMPLE_LABEL}: synthetic, not real field observations."
    placeholder_etl = any("PLACEHOLDER" in i.severity_basis for i in scored)  # read with an unverified ETL
    return FactorResult(id="report_pressure", name=name, weight=weight, score=round(score, 3), status="ok",
                        availability=1.0, sample_data=sample,
                        summary=f"{len(items)} {label} observation(s), {by_severity['high']} high severity "
                                f"(weighted {weighted:g} of {cfg.weighted_count_for_full_score:g} for full pressure)",
                        reasons=reasons, provenance=[evidence.provenance],
                        thresholds="PLACEHOLDER" if placeholder_etl or model.status == "PLACEHOLDER" else "VERIFIED",
                        details={"evidence_state": state, "evidence": EVIDENCE_STATES[state], "count": len(items),
                                 "weighted": weighted, "by_pest": by_pest, "by_severity": by_severity,
                                 "lookback_days": evidence.lookback_days, "coverage": evidence.coverage,
                                 "historical_count": len(historical), "latest_historical": latest,
                                 "reports": [i.flat() for i in items]})


def report_factor(reports: list[PestReport] | None, provenance: Provenance | None, model: RiskModelConfig,
                  today: date) -> FactorResult:
    """All-pest field evidence from a plain list of reports located in the area (the Phase 2 form)."""
    if reports is None:
        return observation_factor(None, None, model)
    sample = any(r.synthetic for r in reports) or (provenance is not None and provenance.state == "SAMPLE")
    items = [AreaObservation(observation=r, match="inside_area", severity=r.severity,
                             severity_basis="severity recorded by the source") for r in reports]
    evidence = AreaObservations(items=items, provenance=provenance or Provenance(source="reports", state="SAMPLE"),
                                sample=sample, coverage="covered", coverage_note="reports given for this area",
                                lookback_days=model.reports.lookback_days)
    return observation_factor(None, evidence, model)


# ------------------------------------------------------------------------------- combination

def _score(factors: list[FactorResult], model: RiskModelConfig):
    """(score 0..1 or None, real-evidence band (low, high) or None, completeness, factors with points,
    available factors).

    The band is what REAL evidence allows: low counts only real inputs, high adds the full weight of
    every input that is unavailable or SAMPLE, as if it were fully adverse. Its width is the share of
    the model not backed by real data, the same share data completeness leaves out."""
    total = sum(f.weight for f in factors)
    completeness = sum(f.weight * f.availability for f in factors if not f.sample_data) / total if total else 0.0
    available = [f for f in factors if f.score is not None and f.availability > 0]
    renormalise = model.missing_inputs == "renormalise"
    denominator = sum(f.weight for f in available) if renormalise else total
    if not available or not denominator:
        return None, None, completeness, factors, available
    score = round(sum(f.weight * f.score for f in available) / denominator, 6)  # 0.35 must not become 0.3499...
    band = None
    if not renormalise:
        real = [f for f in available if not f.sample_data]
        unbacked = sum(f.weight for f in factors if f not in real)
        if unbacked:
            low = round(sum(f.weight * f.score for f in real) / total, 6)
            band = (low, round(low + unbacked / total, 6))
    scored = [f.model_copy(update={"points": round(100 * f.weight * f.score / denominator, 1)})
              if f in available else f for f in factors]
    return score, band, completeness, scored, available


def _band(band: tuple[float, float] | None) -> tuple[float, float] | None:
    return (round(100 * band[0], 1), round(100 * band[1], 1)) if band else None


def _level(score: float | None, completeness: float, available: list[FactorResult],
           model: RiskModelConfig) -> tuple[str, str | None]:
    if score is None or completeness < model.min_completeness_for_level:
        return "INSUFFICIENT_DATA", (f"Only {completeness:.0%} of the model's inputs are backed by real data "
                                     f"(minimum {model.min_completeness_for_level:.0%}), so no risk level is given.")
    cuts, rule = model.levels, model.critical_corroboration
    if score >= cuts.critical:
        strong = [f for f in available if f.score >= rule.factor_score_at_least and not f.sample_data]
        if len(strong) >= rule.min_factors and completeness >= rule.min_completeness:
            return "CRITICAL", (f"Critical: the score is in the critical band and {len(strong)} independent indicators "
                                f"agree ({', '.join(f.name for f in strong)}).")
        return "HIGH", (f"The score reaches the critical band, but Critical needs at least {rule.min_factors} "
                        f"independent real indicators at {rule.factor_score_at_least:.0%} or more and "
                        f"{rule.min_completeness:.0%} data completeness; shown as High.")
    if score >= cuts.high:
        return "HIGH", None
    if score >= cuts.moderate:
        return "MODERATE", None
    return "LOW", None


def _confidence(completeness: float, thresholds: str, sample: bool, model: RiskModelConfig) -> RiskConfidence:
    cfg = model.confidence
    level = ("high" if completeness >= cfg.high_min_completeness
             else "medium" if completeness >= cfg.medium_min_completeness else "low")
    notes = [f"Data completeness {completeness:.0%}: the share of the model's weight backed by real (non-SAMPLE) data."]
    if sample:
        if level == "high":
            level = "medium"
        notes.append("Field observations are SAMPLE (synthetic): they are not counted as data and cap confidence at "
                     "medium.")
    if thresholds == "PLACEHOLDER":
        level = "low"
        notes.append("Thresholds are PLACEHOLDERS awaiting agronomic verification, so confidence is low.")
    if model.calibration.status == "UNCALIBRATED":
        notes.append("The score is UNCALIBRATED: " + model.calibration.note)
    return RiskConfidence(level=level, data_completeness=round(completeness, 3), method=CONFIDENCE_METHOD, notes=notes)


def _points(value: float | None) -> str:
    return f"{100 * value:.0f}/100" if value is not None else "no score"


def combine(area: MonitoredArea, factors: list[FactorResult], pests: list[PestEvaluation], rules: PestRulesConfig,
            model: RiskModelConfig, as_of: str, district_context: dict | None = None,
            pest_risks: list[PestRiskAssessment] | None = None, driver: PestRiskAssessment | None = None,
            not_assessed: list[PestNotAssessed] | None = None) -> RiskAssessment:
    """The area's assessment from one set of factors (the driving pest's when `driver` is given)."""
    score, band, completeness, scored, available = _score(factors, model)
    level, level_note = _level(score, completeness, available, model)
    thresholds = "PLACEHOLDER" if (thresholds_status(rules, model) == "PLACEHOLDER"
                                   or any(f.thresholds == "PLACEHOLDER" for f in factors)) else "VERIFIED"
    sample = any(f.sample_data for f in factors) or any(p.includes_sample_data for p in pest_risks or [])

    without_score = without_level = None
    if any(f.sample_data for f in factors):
        real_only = [_unavailable(f.id, f.weight, "SAMPLE evidence left out") if f.sample_data else f for f in factors]
        without_score, _, _, _, real_available = _score(real_only, model)
        without_level, _ = _level(without_score, completeness, real_available, model)

    contributing = sorted((f for f in scored if f.points), key=lambda f: -f.points)
    unavailable = [f for f in scored if f.score is None]
    reasons = [level_note] if level_note else []
    if pest_risks and len(pest_risks) > 1:
        reasons.append("Per pest/disease: " + "; ".join(
            f"{p.name} {p.level} ({p.score:.0f}/100)" if p.score is not None else f"{p.name} {p.level}"
            for p in pest_risks) + f". The area takes the highest, {driver.name}.")
    if without_level is not None and level != "INSUFFICIENT_DATA":
        if without_level != level:
            reasons.append(f"Without the SAMPLE field observations this area would be {without_level} "
                           f"({_points(without_score)}): the {level} level depends on synthetic data.")
        else:
            reasons.append(f"Without the SAMPLE field observations the level would still be {without_level} "
                           f"({_points(without_score)}).")
    if band is not None and level != "INSUFFICIENT_DATA":
        low, high = band
        high_level, _ = _level(high, completeness, [f for f in available if not f.sample_data], model)
        gaps = [f.name.lower() if f.sample_data and f.score is not None else f"{f.name.lower()} (unavailable)"
                for f in scored if f.score is None or f.sample_data]
        inputs = "inputs were" if len(gaps) > 1 else "input were"
        reasons.append(f"Not backed by real data: {' and '.join(gaps)}. Real evidence alone gives {_points(low)}; "
                       f"if the missing {inputs} fully adverse the score could reach {_points(high)}"
                       + (f" ({high_level})." if high_level != level else ".")
                       + " Missing data never raises the score.")
    for factor in contributing + [f for f in scored if f.points == 0]:
        reasons.extend(factor.reasons)
    for factor in unavailable:
        reasons.append(f"{factor.name} is unavailable: {factor.unavailable_reason}. It adds no points and is not "
                       "estimated.")
    if not_assessed:
        reasons.append("Not assessed, so no score is given (no weather rule and no field evidence): "
                       + ", ".join(p.name.lower() for p in not_assessed) + ".")
    if sample:
        reasons.append(f"Includes {SAMPLE_LABEL}: the field-observation figures are synthetic.")
    if thresholds == "VERIFIED" and model.calibration.status == "UNCALIBRATED":
        reasons.append("The score is UNCALIBRATED: " + model.calibration.note)
    if thresholds == "PLACEHOLDER":
        reasons.append(PLACEHOLDER_NOTE)

    if level == "INSUFFICIENT_DATA":
        missing = "; ".join(f"{f.name.lower()} unavailable" for f in unavailable) or "too little real data"
        headline = f"Not enough data to estimate risk for {area.name} ({missing})."
    else:
        drivers = " and ".join(f.name.lower() for f in contributing[:2])
        led = f", led by {driver.name.lower()}" if driver and pest_risks and len(pest_risks) > 1 else ""
        headline = (f"Indicators suggest {level} risk ({100 * score:.0f}/100) for {area.name}{led}"
                    + (f", mainly from {drivers}" if drivers else "") + ".")

    provenance, seen = [], set()
    for factor in scored:
        for item in factor.provenance:
            key = (item.source, item.state, item.covers, item.retrieved_at)
            if key not in seen:
                seen.add(key)
                provenance.append(item)
    estimated = level != "INSUFFICIENT_DATA"
    return RiskAssessment(area_id=area.id, area_name=area.name, area_kind=area.kind, as_of=as_of,
                          score=round(100 * score, 1) if estimated else None, level=level,
                          headline=headline, reasons=reasons, top_factors=[f.id for f in contributing],
                          factors=scored, pests=pests, confidence=_confidence(completeness, thresholds, sample, model),
                          provenance=provenance, thresholds_status=thresholds, includes_sample_data=sample,
                          disclaimer=DISCLAIMER, district_context=district_context, pest_risks=pest_risks or [],
                          driver_pest=driver.pest_id if driver else None,
                          score_range=_band(band) if estimated else None,
                          score_without_sample=(round(100 * without_score, 1)
                                                if estimated and without_score is not None else None),
                          level_without_sample=without_level if estimated else None,
                          pests_not_assessed=not_assessed or [], calibration=model.calibration.status)


# ------------------------------------------------------------------------------------ per pest

def pest_risk(pest_id: str, name: str, crop: str, factors: list[FactorResult], has_weather_rule: bool,
              observation_count: int, model: RiskModelConfig) -> PestRiskAssessment:
    score, band, completeness, scored, available = _score(factors, model)
    level, _ = _level(score, completeness, available, model)
    estimated = level != "INSUFFICIENT_DATA"
    parts = ", ".join(f"{f.name.lower()} {f.points:g}" if f.points is not None else f"{f.name.lower()} n/a"
                      for f in scored)
    summary = f"{name}: {level}" + (f" ({100 * score:.0f}/100)" if estimated else "") + f"; points: {parts}."
    return PestRiskAssessment(pest_id=pest_id, name=name, crop=crop, level=level,
                              score=round(100 * score, 1) if estimated else None,
                              score_range=_band(band) if estimated else None,
                              factors=scored, data_completeness=round(completeness, 3),
                              includes_sample_data=any(f.sample_data for f in factors),
                              has_weather_rule=has_weather_rule, observation_count=observation_count, summary=summary)


def assess_area(area: MonitoredArea, *, rules: PestRulesConfig, model: RiskModelConfig, as_of: str, today: date,
                pests: list[PestEvaluation], weather: weather_data.HourlyWeather | None, weather_error: str | None,
                ndvi: FactorResult, evidence: AreaObservations | None, names: dict[str, str] | None = None,
                district_context: dict | None = None) -> RiskAssessment:
    """Score every pest with a weather rule or field observations in the window, then the area.

    `pests` are the weather evaluations (empty without weather); `ndvi` is the area's NDVI factor,
    shared by every pest; `names` gives display names for observed pests without a weather rule."""
    by_rule = {rule.id: rule for rule in rules.pests}
    evaluated = {p.pest_id: p for p in pests}
    observed = sorted({i.observation.pest for i in evidence.items}) if evidence else []
    risks = []
    for pest_id in list(by_rule) + [p for p in observed if p not in by_rule]:
        rule = by_rule.get(pest_id)
        name = rule.name if rule else (names or {}).get(pest_id, pest_id.replace("_", " ").capitalize())
        if rule is None:
            weather_f = _unavailable("weather_pest", model.weights["weather_pest"],
                                     f"no weather rule is configured for {name.lower()}")
        elif pest_id in evaluated:
            weather_f = weather_factor([evaluated[pest_id]], weather, None, model, area, today)
        else:
            weather_f = weather_factor([], None, weather_error, model, area, today)
        observation_f = observation_factor(pest_id, evidence, model)
        records = evidence.for_pest(pest_id) if evidence else []
        crop = rule.crop if rule else records[0].observation.crop
        risks.append(pest_risk(pest_id, name, crop, [weather_f, ndvi, observation_f], rule is not None, len(records),
                               model))
    order = sorted(risks, key=lambda p: (LEVEL_ORDER[p.level], -(p.score or 0.0), p.name))
    driver = order[0]
    assessed = {p.pest_id for p in risks}
    not_assessed = [PestNotAssessed(pest_id=pest_id, name=name, reason=_not_assessed_reason(pest_id, evidence))
                    for pest_id, name in (names or {}).items() if pest_id not in assessed]
    return combine(area, [f.model_copy(update={"points": None}) for f in driver.factors], pests, rules, model, as_of,
                   district_context=district_context, pest_risks=order, driver=driver, not_assessed=not_assessed)


def _not_assessed_reason(pest_id: str, evidence: AreaObservations | None) -> str:
    if evidence is None:
        return "no weather rule is configured, and no pest-observation source is connected"
    if evidence.surveys(pest_id) is False:
        return ("no weather rule is configured, and the SAMPLE generator does not simulate it" if evidence.sample
                else "no weather rule is configured, and the observation source does not survey it")
    historical = evidence.historical_for(pest_id)
    if historical:
        latest = max(o.observed_on for o in historical)
        return f"no weather rule is configured; only HISTORICAL observations (latest {latest}), not current evidence"
    return f"no weather rule is configured, and no observations in the last {evidence.lookback_days} days"


def rank(assessments: list[RiskAssessment]) -> list[RiskAssessment]:
    """Most urgent first: by level, then score, then data completeness (at equal scores the area
    backed by more real data comes first, so missing data never lifts an area), then name. Areas
    without enough data to estimate are listed last and get no rank number, so "#2 of 6" counts only
    areas that have an estimate."""
    ordered = sorted(assessments, key=lambda a: (LEVEL_ORDER[a.level], -(a.score or 0.0),
                                                 -a.confidence.data_completeness, a.area_name))
    estimated = sum(1 for a in ordered if a.level != "INSUFFICIENT_DATA")
    return [a.model_copy(update={"rank": i + 1 if a.level != "INSUFFICIENT_DATA" else None, "rank_of": estimated})
            for i, a in enumerate(ordered)]
