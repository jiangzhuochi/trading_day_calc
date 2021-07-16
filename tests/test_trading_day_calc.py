import datetime
from typing import Callable

import trading_day_calc
from trading_day_calc import *

# Type aliases
DateType = dt = datetime.date
FilterFunc = Callable[[DateType], bool]

td = trading_day_calc.TRADE_DATE


def test_version():
    assert trading_day_calc.__version__ == '0.1.4'


def test_trade_date():
    assert len(td) == 7586


def test_filter_mon_to_fri():
    cases = [filter_mon(td), filter_tues(td),
             filter_wed(td), filter_thur(td),
             filter_fri(td)]
    for i, case in enumerate(cases):
        assert len(case)
        for d in case:
            assert d.weekday() == i


def test_filter_between():
    assert [] == filter_between([])
    assert [td[0]] == filter_between([td[0]])
    assert td == filter_between()

    daytop100 = td[100]
    daybottom20 = td[-20]
    assert td[100:] == filter_between(td[50:], start=daytop100)
    assert td[:-19] == filter_between(end=daybottom20)
    assert td[100:-19] == filter_between(start=daytop100, end=daybottom20)


def test_filter_first_last_day_per_month():
    year2021 = filter_between(
        start=dt(2021, 4, 1),
        end=dt(2021, 7, 31)
    )
    assert [] == get_first_day_per_month([])
    assert [dt(2021, 4, 1),
            dt(2021, 5, 6),
            dt(2021, 6, 1),
            dt(2021, 7, 1)] == get_first_day_per_month(year2021)
    assert [] == get_last_day_per_month([])
    assert [dt(2021, 4, 30),
            dt(2021, 5, 31),
            dt(2021, 6, 30),
            dt(2021, 7, 30)] == get_last_day_per_month(year2021)


def test_get_1d_before_or_after_holiday():
    year2021_july = filter_between(
        start=dt(2021, 7, 1),
        end=dt(2021, 7, 31)
    )
    year2021_october = filter_between(
        start=dt(2021, 10, 1),
        end=dt(2021, 10, 31)
    )
    assert [dt(2021, 7, 5),
            dt(2021, 7, 12),
            dt(2021, 7, 19),
            dt(2021, 7, 26)] == get_1d_after_holiday(year2021_july)

    assert [dt(2021, 7, 2),
            dt(2021, 7, 9),
            dt(2021, 7, 16),
            dt(2021, 7, 23),
            dt(2021, 7, 30)] == get_1d_before_holiday(year2021_july)

    assert [dt(2021, 10, 8),
            dt(2021, 10, 11),
            dt(2021, 10, 18),
            dt(2021, 10, 25)] == get_1d_after_holiday(year2021_october)

    assert [dt(2021, 10, 8),
            dt(2021, 10, 15),
            dt(2021, 10, 22),
            dt(2021, 10, 29)] == get_1d_before_holiday(year2021_october)
