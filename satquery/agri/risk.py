"""The explainable crop & pest risk score: three indicators, weighted, every step visible.

Factors, each scored 0..1 by rules kept as data (`config.py`):
  weather_pest     the strongest pest-favourable-weather index (`rules.py`)
  ndvi_anomaly     how far vegetation (NDVI) is below the same dates in earlier years (`ndvi.py`)
  report_pressure  recent pest reports in the area, weighted by severity (SAMPLE data in this prototype)

Score = sum(weight x factor score) / sum(weight) over the AVAILABLE factors, shown as 0-100 with
each factor's points, so the score is always the sum of its visible parts. A missing factor is
never filled in: it is named, the remaining factors carry the score, and data completeness (the
share of the model's weight backed by data) lowers the confidence. Below a minimum completeness no
level is given at all. "Critical" also needs two independent indicators to agree.

This is decision support: indicators suggest a risk level; nothing here detects or confirms an
outbreak. Confidence is a rule-based label, not a calibrated probability.
"""

from datetime import date

from satquery.agri import weather as weather_data
from satquery.agri.areas import extent_km
from satquery.agri.config import PestRulesConfig, RiskModelConfig, thresholds_status
from satquery.agri.models import (DISCLAIMER, PLACEHOLDER_NOTE, SAMPLE_LABEL, FactorResult, MonitoredArea,
                                  NdviAnomaly, PestEvaluation, PestReport, Provenance, RiskAssessment, RiskConfidence)
from satquery.agri.ndvi import NdviClient

FACTOR_NAMES = {"weather_pest": "Pest-favourable weather",
                "ndvi_anomaly": "Vegetation condition vs earlier years (NDVI)",
                "report_pressure": "Recent pest reports (SAMPLE)"}
LEVEL_ORDER = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3, "INSUFFICIENT_DATA": 4}
CONFIDENCE_METHOD = ("Rule-based label, not a calibrated probability: data completeness sets it (high at or above "
                     "the high cut, medium at or above the medium cut); it is capped at medium when an input is SAMPLE "
                     "data and at low while any threshold is a PLACEHOLDER.")


def _unavailable(factor_id: str, weight: float, reason: str, provenance: list[Provenance] | None = None,
                 **extra) -> FactorResult:
    return FactorResult(id=factor_id, name=FACTOR_NAMES[factor_id], status="unavailable", score=None, weight=weight,
                        availability=0.0, summary=f"Unavailable: {reason}", unavailable_reason=reason,
                        provenance=provenance or [], **extra)


# ----------------------------------------------------------------------------------- factors

def weather_factor(pests: list[PestEvaluation], weather: weather_data.HourlyWeather | None, error: str | None,
                   model: RiskModelConfig, area: MonitoredArea, today: date) -> FactorResult:
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
        reasons.append("Weather is a STALE cached copy: the provider could not be reached.")
    days = driver.favourable_past + driver.favourable_forecast
    return FactorResult(
        id="weather_pest", name=FACTOR_NAMES["weather_pest"], weight=weight, score=driver.index,
        status="ok" if availability == 1 else "partial", availability=availability,
        summary=f"{driver.name}: favourable weather on {days} day(s) of the "
                f"{driver.past_days}+{driver.forecast_days}-day window (index {driver.index:.2f})",
        reasons=reasons, thresholds=thresholds, provenance=[weather.provenance()],
        details={"driver": driver.pest_id, "pests": [p.model_dump(exclude={"days"}) for p in pests],
                 "weather_summary": weather_data.summarise(weather, today),
                 "point": {"latitude": weather.latitude, "longitude": weather.longitude}})


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
    availability = round(anomaly.baseline_years_used / cfg.baseline_years, 3)
    return FactorResult(id="ndvi_anomaly", name=FACTOR_NAMES["ndvi_anomaly"], weight=weight, score=round(score, 3),
                        status="ok" if availability == 1 else "partial", availability=availability,
                        summary=f"NDVI {current.mean:.2f} vs {anomaly.baseline_mean:.2f} baseline ({change:+.0%})",
                        reasons=reasons, provenance=provenance, details=details, thresholds=model.status)


def report_factor(reports: list[PestReport] | None, provenance: Provenance | None, model: RiskModelConfig,
                  today: date) -> FactorResult:
    weight, cfg = model.weights["report_pressure"], model.reports
    if reports is None:
        return _unavailable("report_pressure", weight, "no pest-report source is connected", thresholds=model.status)
    weighted = sum(cfg.severity_weights[r.severity] for r in reports)
    score = min(1.0, weighted / cfg.weighted_count_for_full_score)
    by_pest, by_severity = {}, {"low": 0, "moderate": 0, "high": 0}
    for report in reports:
        by_pest[report.pest] = by_pest.get(report.pest, 0) + 1
        by_severity[report.severity] += 1
    if reports:
        pests = ", ".join(f"{name.replace('_', ' ')} x{count}" for name, count in sorted(by_pest.items()))
        reason = (f"{len(reports)} SAMPLE pest report(s) in the last {cfg.lookback_days} days inside the area "
                  f"({pests}; {by_severity['high']} high severity).")
    else:
        reason = f"No SAMPLE pest reports in the last {cfg.lookback_days} days inside the area."
    sample = any(r.synthetic for r in reports) or (provenance is not None and provenance.state == "SAMPLE")
    reasons = [reason + (f" {SAMPLE_LABEL}: synthetic reports, not real observations." if sample else "")]
    return FactorResult(id="report_pressure", name=FACTOR_NAMES["report_pressure"], weight=weight,
                        score=round(score, 3), status="ok", availability=1.0, sample_data=sample,
                        summary=f"{len(reports)} SAMPLE report(s), {by_severity['high']} high severity "
                                f"(weighted {weighted:g} of {cfg.weighted_count_for_full_score:g} for full pressure)",
                        reasons=reasons, provenance=[provenance] if provenance else [], thresholds=model.status,
                        details={"count": len(reports), "weighted": weighted, "by_pest": by_pest,
                                 "by_severity": by_severity, "lookback_days": cfg.lookback_days,
                                 "reports": [r.model_dump() for r in reports]})


# ------------------------------------------------------------------------------- combination

def _level(score: float | None, completeness: float, available: list[FactorResult],
           model: RiskModelConfig) -> tuple[str, str | None]:
    if score is None or completeness < model.min_completeness_for_level:
        return "INSUFFICIENT_DATA", (f"Only {completeness:.0%} of the model's inputs are available "
                                     f"(minimum {model.min_completeness_for_level:.0%}), so no risk level is given.")
    cuts, rule = model.levels, model.critical_corroboration
    if score >= cuts.critical:
        strong = [f for f in available if f.score >= rule.factor_score_at_least]
        if len(strong) >= rule.min_factors and completeness >= rule.min_completeness:
            return "CRITICAL", (f"Critical: the score is in the critical band and {len(strong)} independent indicators "
                                f"agree ({', '.join(f.name for f in strong)}).")
        return "HIGH", (f"The score reaches the critical band, but Critical needs at least {rule.min_factors} "
                        f"independent indicators at {rule.factor_score_at_least:.0%} or more and "
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
    notes = [f"Data completeness {completeness:.0%}: the share of the model's weight backed by available inputs."]
    if sample:
        if level == "high":
            level = "medium"
        notes.append("Report pressure uses SAMPLE (synthetic) reports, so confidence is at most medium.")
    if thresholds == "PLACEHOLDER":
        level = "low"
        notes.append("Thresholds are PLACEHOLDERS awaiting agronomic verification, so confidence is low.")
    return RiskConfidence(level=level, data_completeness=round(completeness, 3), method=CONFIDENCE_METHOD, notes=notes)


def combine(area: MonitoredArea, factors: list[FactorResult], pests: list[PestEvaluation], rules: PestRulesConfig,
            model: RiskModelConfig, as_of: str, district_context: dict | None = None) -> RiskAssessment:
    total_weight = sum(f.weight for f in factors)
    completeness = sum(f.weight * f.availability for f in factors) / total_weight if total_weight else 0.0
    available = [f for f in factors if f.score is not None and f.availability > 0]
    available_weight = sum(f.weight for f in available)
    score = sum(f.weight * f.score for f in available) / available_weight if available_weight else None
    score = round(score, 6) if score is not None else None  # 0.35 must not become 0.34999999999999997
    scored = [f.model_copy(update={"points": round(100 * f.weight * f.score / available_weight, 1)})
              if f in available else f for f in factors]
    level, level_note = _level(score, completeness, available, model)
    thresholds = thresholds_status(rules, model)
    sample = any(f.sample_data for f in factors)

    contributing = sorted((f for f in scored if f.points), key=lambda f: -f.points)
    unavailable = [f for f in scored if f.score is None]
    reasons = [level_note] if level_note else []
    for factor in contributing + [f for f in scored if f.points == 0]:
        reasons.extend(factor.reasons)
    for factor in unavailable:
        reasons.append(f"{factor.name} is unavailable: {factor.unavailable_reason}. It is left out of the score, not "
                       "estimated.")
    if sample:
        reasons.append(f"Includes {SAMPLE_LABEL}: the report figures are synthetic.")
    if thresholds == "PLACEHOLDER":
        reasons.append(PLACEHOLDER_NOTE)

    if level == "INSUFFICIENT_DATA":
        missing = "; ".join(f"{f.name.lower()} unavailable" for f in unavailable) or "too little data"
        headline = f"Not enough data to estimate risk for {area.name} ({missing})."
    else:
        drivers = " and ".join(f.name.lower() for f in contributing[:2])
        headline = (f"Indicators suggest {level} risk ({100 * score:.0f}/100) for {area.name}"
                    + (f", mainly from {drivers}" if drivers else "") + ".")

    provenance, seen = [], set()
    for factor in scored:
        for item in factor.provenance:
            key = (item.source, item.state, item.covers, item.retrieved_at)
            if key not in seen:
                seen.add(key)
                provenance.append(item)
    return RiskAssessment(area_id=area.id, area_name=area.name, area_kind=area.kind, as_of=as_of,
                          score=None if level == "INSUFFICIENT_DATA" else round(100 * score, 1), level=level,
                          headline=headline, reasons=reasons, top_factors=[f.id for f in contributing],
                          factors=scored, pests=pests, confidence=_confidence(completeness, thresholds, sample, model),
                          provenance=provenance, thresholds_status=thresholds, includes_sample_data=sample,
                          disclaimer=DISCLAIMER, district_context=district_context)


def rank(assessments: list[RiskAssessment]) -> list[RiskAssessment]:
    """Most urgent first: by level, then score, then name. Areas without enough data to estimate are
    listed last and get no rank number, so "#2 of 6" counts only areas that have an estimate."""
    ordered = sorted(assessments, key=lambda a: (LEVEL_ORDER[a.level], -(a.score or 0.0), a.area_name))
    estimated = sum(1 for a in ordered if a.level != "INSUFFICIENT_DATA")
    return [a.model_copy(update={"rank": i + 1 if a.level != "INSUFFICIENT_DATA" else None, "rank_of": estimated})
            for i, a in enumerate(ordered)]
