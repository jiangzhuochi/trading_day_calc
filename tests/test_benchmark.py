from collections.abc import Callable
from datetime import date
from typing import Protocol, TypeVar

import pytest

from trading_day_calc import TradingCalendar

ResultT = TypeVar("ResultT")


class BenchmarkFixture(Protocol):
    def __call__(
        self, function: Callable[..., ResultT], *args: object, **kwargs: object
    ) -> ResultT: ...


@pytest.fixture(scope="module")
def calendar() -> TradingCalendar:
    return TradingCalendar()


@pytest.mark.benchmark(group="core-query")
def test_bench_trading_days(
    benchmark: BenchmarkFixture, calendar: TradingCalendar
) -> None:
    result = benchmark(
        calendar.trading_days,
        date(1990, 12, 19),
        date(2026, 12, 31),
    )
    assert len(result) == 8_797


@pytest.mark.benchmark(group="core-query")
def test_bench_month_starts(
    benchmark: BenchmarkFixture, calendar: TradingCalendar
) -> None:
    result = benchmark(
        calendar.month_starts,
        date(1990, 12, 19),
        date(2026, 12, 31),
    )
    assert len(result) == 433


@pytest.mark.benchmark(group="constant-query")
def test_bench_is_trading_day(
    benchmark: BenchmarkFixture, calendar: TradingCalendar
) -> None:
    result = benchmark(calendar.is_trading_day, date(2026, 8, 14))
    assert result is True


@pytest.mark.benchmark(group="core-query")
def test_bench_closed_periods(
    benchmark: BenchmarkFixture, calendar: TradingCalendar
) -> None:
    result = benchmark(
        calendar.closed_periods,
        date(1990, 12, 19),
        date(2026, 12, 31),
    )
    assert len(result) > 100
