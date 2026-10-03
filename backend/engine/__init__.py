"""Pure scheduling and protection logic. No Django imports, so it is easy to test and reason about."""
from .fees import FeeParts, FeeSchedule, fee_for, group_fee_for
from .money import DEFAULT_FEE_KOBO, format_naira, naira, to_naira
from .priorities import MAX_PRIORITIES, set_priority
from .protection import (
    Decision,
    Forecast,
    ForecastEvent,
    PlanLike,
    compare_key,
    decide,
    forecast,
    validate_priorities,
)
from .schedule import (
    MAX_PLAN_MONTHS,
    Schedule,
    all_occurrences,
    day_key,
    end_after_months,
    end_of_local_day,
    end_of_month,
    months_later,
    next_occurrences,
    occurrences,
    start_of_local_day,
    start_of_month,
    validate_schedule,
)

__all__ = [
    "FeeParts", "FeeSchedule", "fee_for", "group_fee_for",
    "DEFAULT_FEE_KOBO", "format_naira", "naira", "to_naira",
    "MAX_PRIORITIES", "set_priority",
    "Decision", "Forecast", "ForecastEvent", "PlanLike", "compare_key", "decide", "forecast", "validate_priorities",
    "MAX_PLAN_MONTHS", "all_occurrences", "end_after_months", "end_of_local_day", "months_later", "start_of_local_day",
    "Schedule", "day_key", "end_of_month", "next_occurrences", "occurrences", "start_of_month", "validate_schedule",
]
