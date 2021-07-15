import datetime
from collections.abc import Iterable
from typing import Callable, List

import trading_day_calc
from trading_day_calc import *

# Type aliases
DateType = datetime.date
FilterFunc = Callable[[DateType], bool]

td = trading_day_calc.TRADE_DATE


def test_version():
    assert trading_day_calc.__version__ == '0.1.3'


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

    year2021 = filter_between(start=datetime.date(2021, 4, 1),
                              end=datetime.date(2021, 7, 31))

    assert [] == get_first_day_per_month([])
    assert [datetime.date(2021, 4, 1),
            datetime.date(2021, 5, 6),
            datetime.date(2021, 6, 1),
            datetime.date(2021, 7, 1)] == get_first_day_per_month(year2021)

    assert [] == get_last_day_per_month([])
    assert [datetime.date(2021, 4, 30),
            datetime.date(2021, 5, 31),
            datetime.date(2021, 6, 30),
            datetime.date(2021, 7, 30)] == get_last_day_per_month(year2021)
