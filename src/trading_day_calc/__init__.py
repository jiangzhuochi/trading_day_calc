"""中国 A 股交易日历。"""

from .calendar import CalendarMetadata, ClosedPeriod, ClosedPeriodKind, TradingCalendar
from .errors import (
    CalendarCoverageError,
    CalendarDataError,
    CalendarUpdateError,
    TradingCalendarError,
)

__version__ = "1.0.0"

__all__ = [
    "CalendarCoverageError",
    "CalendarDataError",
    "CalendarMetadata",
    "CalendarUpdateError",
    "ClosedPeriod",
    "ClosedPeriodKind",
    "TradingCalendar",
    "TradingCalendarError",
    "__version__",
]
