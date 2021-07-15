import datetime
from collections.abc import Iterable
from typing import Callable, List

import trading_day_calc
from trading_day_calc import *

# Type aliases
DateType = datetime.date
FilterFunc = Callable[[DateType], bool]


def test_version():
    assert trading_day_calc.__version__ == '0.1.2'


td = trading_day_calc.TRADE_DATE


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
