from datetime import date, datetime

import pytest

import trading_day_calc
from trading_day_calc import CalendarCoverageError, TradingCalendar


@pytest.fixture(scope="module")
def calendar() -> TradingCalendar:
    return TradingCalendar()


def test_version_and_metadata(calendar: TradingCalendar) -> None:
    assert trading_day_calc.__version__ == "1.0.0"
    assert calendar.coverage_start == date(1990, 12, 19)
    assert calendar.coverage_end == date(2026, 12, 31)
    assert calendar.metadata.session_count == 8_797
    assert len(calendar.metadata.source_urls) == 10
    assert isinstance(calendar.sessions, tuple)


def test_trading_day_judgement(calendar: TradingCalendar) -> None:
    assert calendar.is_trading_day(date(2021, 7, 2))
    assert not calendar.is_trading_day(date(2021, 7, 3))
    assert not calendar.is_trading_day(date(2025, 10, 1))
    assert calendar.is_trading_day(date(2025, 10, 9))


def test_trading_days_uses_inclusive_bounds(calendar: TradingCalendar) -> None:
    assert calendar.trading_days(date(2021, 7, 1), date(2021, 7, 5)) == (
        date(2021, 7, 1),
        date(2021, 7, 2),
        date(2021, 7, 5),
    )
    assert calendar.trading_days(date(2021, 7, 3), date(2021, 7, 4)) == ()


def test_next_and_previous_trading_day(calendar: TradingCalendar) -> None:
    assert calendar.next_trading_day(date(2025, 9, 30)) == date(2025, 10, 9)
    assert calendar.next_trading_day(date(2025, 9, 30), 2) == date(2025, 10, 10)
    assert calendar.previous_trading_day(date(2025, 10, 9)) == date(2025, 9, 30)
    assert calendar.previous_trading_day(date(2025, 10, 9), 2) == date(2025, 9, 29)


def test_month_boundaries_are_actual_calendar_boundaries(
    calendar: TradingCalendar,
) -> None:
    assert calendar.month_starts(date(2021, 4, 1), date(2021, 7, 31)) == (
        date(2021, 4, 1),
        date(2021, 5, 6),
        date(2021, 6, 1),
        date(2021, 7, 1),
    )
    assert calendar.month_ends(date(2021, 4, 1), date(2021, 7, 31)) == (
        date(2021, 4, 30),
        date(2021, 5, 31),
        date(2021, 6, 30),
        date(2021, 7, 30),
    )
    assert calendar.month_starts(date(2021, 4, 2), date(2021, 5, 31)) == (
        date(2021, 5, 6),
    )
    assert calendar.month_ends(date(2021, 4, 1), date(2021, 5, 28)) == (
        date(2021, 4, 30),
    )


@pytest.mark.parametrize("steps", [0, -1, True, 1.5])
def test_invalid_steps_are_rejected(calendar: TradingCalendar, steps: object) -> None:
    with pytest.raises(ValueError):
        calendar.next_trading_day(date(2021, 7, 1), steps)  # type: ignore[arg-type]


def test_invalid_ranges_and_types_are_rejected(calendar: TradingCalendar) -> None:
    with pytest.raises(ValueError):
        calendar.trading_days(date(2021, 7, 2), date(2021, 7, 1))
    with pytest.raises(TypeError):
        calendar.is_trading_day(datetime(2021, 7, 1))


def test_coverage_errors_are_explicit(calendar: TradingCalendar) -> None:
    with pytest.raises(CalendarCoverageError):
        calendar.is_trading_day(date(1990, 12, 18))
    with pytest.raises(CalendarCoverageError):
        calendar.trading_days(date(2026, 12, 31), date(2027, 1, 1))
    with pytest.raises(CalendarCoverageError):
        calendar.next_trading_day(date(2026, 12, 31))
    with pytest.raises(CalendarCoverageError):
        calendar.previous_trading_day(date(1990, 12, 19))
