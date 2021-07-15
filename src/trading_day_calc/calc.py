import datetime
import pkgutil
from collections.abc import Iterable
from itertools import groupby
from typing import Callable, List, Optional

__all__ = [
    'TRADE_DATE',
    'filter_d',
    'filter_mon',
    'filter_tues',
    'filter_wed',
    'filter_thur',
    'filter_fri',
    'filter_between',
    'get_first_day_per_month',
    'get_last_day_per_month'
]

# Type aliases
DateType = datetime.date
FilterFunc = Callable[[DateType], bool]


def _get_trade_date() -> List[DateType]:
    data_bytes = pkgutil.get_data(__package__, 'trade_date.txt')
    if data_bytes is not None:
        trade_date_str = data_bytes.decode()
    else:
        raise Exception("Not found trade_date.txt")
    scope = {}
    exec(trade_date_str, scope)
    return scope['TRADE_DATE']


TRADE_DATE: List[DateType] = _get_trade_date()


def filter_d(f: FilterFunc, ds: Iterable[DateType]) -> List[DateType]:
    return [d for d in ds if f(d)]


def filter_mon(ds: Iterable[DateType]) -> List[DateType]:
    return filter_d(lambda d: d.weekday() == 0, ds)


def filter_tues(ds: Iterable[DateType]) -> List[DateType]:
    return filter_d(lambda d: d.weekday() == 1, ds)


def filter_wed(ds: Iterable[DateType]) -> List[DateType]:
    return filter_d(lambda d: d.weekday() == 2, ds)


def filter_thur(ds: Iterable[DateType]) -> List[DateType]:
    return filter_d(lambda d: d.weekday() == 3, ds)


def filter_fri(ds: Iterable[DateType]) -> List[DateType]:
    return filter_d(lambda d: d.weekday() == 4, ds)


def filter_between(ds: Optional[List[DateType]] = None, *,
                   start: Optional[DateType] = None,
                   end: Optional[DateType] = None) -> List[DateType]:

    ds = TRADE_DATE if ds is None else ds
    # 若传入一个空列表，则返回一个空列表
    if len(ds) == 0:
        return []
    s: DateType = ds[0] if start is None else start
    e: DateType = ds[-1] if end is None else end

    return filter_d(lambda d: s <= d <= e, ds)


def _get_nth_day_per_month(*, ds: Optional[List[DateType]],
                           start: Optional[DateType],
                           end: Optional[DateType],
                           nth: int = 0) -> List[DateType]:

    ungrouped = filter_between(ds=ds, start=start, end=end)
    if len(ungrouped) == 0:
        return []

    groups = []
    for _, g in groupby(ungrouped, key=lambda d: d.strftime('%Y%m')):
        groups.append(list(g)[nth])

    return groups


def get_first_day_per_month(ds: Optional[List[DateType]] = None, *,
                            start: Optional[DateType] = None,
                            end: Optional[DateType] = None) -> List[DateType]:
    return _get_nth_day_per_month(ds=ds, start=start, end=end, nth=0)


def get_last_day_per_month(ds: Optional[List[DateType]] = None, *,
                           start: Optional[DateType] = None,
                           end: Optional[DateType] = None) -> List[DateType]:
    return _get_nth_day_per_month(ds=ds, start=start, end=end, nth=-1)
