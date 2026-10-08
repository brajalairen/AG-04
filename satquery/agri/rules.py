"""Pest-favourable weather: each pest rule (data, in `pest_rules.json`) is checked day by day.

A day is favourable when every condition of the rule holds on that day's hourly values. A day with
too few hourly values for any condition is UNKNOWN: it counts neither for nor against, and lowers
the evaluation's completeness instead. The rule's index is the number of favourable days in the
window (recent past + forecast) over the days that count as full pressure, capped at 1.
"""

from datetime import date, timedelta

from satquery.agri.config import Condition, PestRule
from satquery.agri.models import DayCheck, PestEvaluation
from satquery.agri.weather import HourlyWeather


def _aggregate(condition: Condition, values: list[float]) -> float:
    if condition.aggregate == "mean":
        return sum(values) / len(values)
    if condition.aggregate == "min":
        return min(values)
    if condition.aggregate == "max":
        return max(values)
    if condition.aggregate == "sum":
        return sum(values)
    if condition.aggregate == "hours_at_or_above":
        return float(sum(1 for v in values if v >= condition.threshold))
    low, high = condition.between  # hours_between
    return float(sum(1 for v in values if low <= v <= high))


def _holds(condition: Condition, value: float) -> bool:
    if condition.aggregate in ("hours_at_or_above", "hours_between"):
        return value >= condition.at_least
    if condition.between is not None:
        low, high = condition.between
        if not low <= value <= high:
            return False
    if condition.at_least is not None and value < condition.at_least:
        return False
    return condition.at_most is None or value <= condition.at_most


def check_day(rule: PestRule, hours: dict[str, list] | None, day: str, period: str, min_hours: int) -> DayCheck:
    values, unmet = {}, []
    for condition in rule.conditions:
        present = [v for v in (hours or {}).get(condition.variable, []) if v is not None]
        if len(present) < min_hours:
            return DayCheck(date=day, period=period, favourable=None, values=values,
                            unmet=[f"not enough hourly data ({len(present)} of {min_hours} needed hours)"])
        value = _aggregate(condition, present)
        values[condition.label] = round(value, 2)
        if not _holds(condition, value):
            unmet.append(condition.label)
    return DayCheck(date=day, period=period, favourable=not unmet, values=values, unmet=unmet)


def _longest_run(checks: list[DayCheck]) -> int:
    best = run = 0
    for check in checks:
        run = run + 1 if check.favourable else 0
        best = max(best, run)
    return best


def evaluate(rule: PestRule, weather: HourlyWeather, today: date, min_hours: int = 20) -> PestEvaluation:
    """The rule over the last `past_days` days (before today) and the next `forecast_days` (from today)."""
    by_day = weather.by_day()
    past = [(today - timedelta(days=n)).isoformat() for n in range(rule.past_days, 0, -1)]
    future = [(today + timedelta(days=n)).isoformat() for n in range(rule.forecast_days)]
    checks = [check_day(rule, by_day.get(d), d, "past", min_hours) for d in past]
    checks += [check_day(rule, by_day.get(d), d, "forecast", min_hours) for d in future]

    def favourable(period):
        return sum(1 for c in checks if c.period == period and c.favourable)

    def known(period):
        return sum(1 for c in checks if c.period == period and c.favourable is not None)

    favourable_past, favourable_forecast = favourable("past"), favourable("forecast")
    known_past, known_forecast = known("past"), known("forecast")
    judged = known_past + known_forecast
    status = "unavailable" if judged == 0 else "ok" if judged == len(checks) else "partial"
    index = None if judged == 0 else min(1.0, (favourable_past + favourable_forecast) / rule.full_score_days)
    placeholder = " [PLACEHOLDER thresholds, not yet verified]" if rule.status == "PLACEHOLDER" else ""
    if judged == 0:
        explanation = f"{rule.name}: not evaluated, no day had enough hourly weather data.{placeholder}"
    else:
        explanation = (f"{rule.name}: favourable conditions on {favourable_past} of the last {rule.past_days} days"
                       + (f" and {favourable_forecast} of the next {rule.forecast_days} forecast days"
                          if rule.forecast_days else "")
                       + f" ({'; '.join(c.label for c in rule.conditions)})."
                       + (f" {len(checks) - judged} day(s) could not be judged (missing hourly data)."
                          if judged < len(checks) else "") + placeholder)
    return PestEvaluation(pest_id=rule.id, name=rule.name, crop=rule.crop, status=status,
                          index=round(index, 3) if index is not None else None,
                          favourable_past=favourable_past, known_past=known_past, past_days=rule.past_days,
                          favourable_forecast=favourable_forecast, known_forecast=known_forecast,
                          forecast_days=rule.forecast_days, longest_run=_longest_run(checks),
                          full_score_days=rule.full_score_days, conditions=[c.label for c in rule.conditions],
                          thresholds=rule.status, sources=[s.model_dump() for s in rule.sources],
                          explanation=explanation, days=checks)
