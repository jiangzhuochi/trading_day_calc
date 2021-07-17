import datetime
import time
from typing import Callable

import pytest
import trading_day_calc
from trading_day_calc import *

# Type aliases
DateType = dt = datetime.date
FilterFunc = Callable[[DateType], bool]

td = trading_day_calc.TRADE_DATE


@pytest.mark.benchmark(group="us-group")
def test_bench_filter_mon(benchmark):
    ret = benchmark.pedantic(filter_mon, args=(td,), rounds=100, iterations=10)
    for d in ret:
        assert d.weekday() == 0


@pytest.mark.benchmark(group="us-group")
def test_bench_filter_between(benchmark):
    assert td == benchmark.pedantic(
        filter_between,
        rounds=100, iterations=10
    )


@pytest.mark.benchmark(group="ms-group")
def test_bench_get_first_day_per_month(benchmark):
    assert benchmark.pedantic(
        get_first_day_per_month,
        rounds=30, iterations=10
    )


@pytest.mark.benchmark(group="ms-group")
def test_bench_get_1d_before_holiday(benchmark):
    assert benchmark.pedantic(
        get_1d_before_holiday,
        rounds=30, iterations=10
    )
