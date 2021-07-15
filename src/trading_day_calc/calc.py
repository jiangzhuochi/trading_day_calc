import datetime
import pkgutil
from collections.abc import Iterable
from typing import Callable, List

__all__ = [
    'TRADE_DATE',
    'filter_d',
    'filter_mon',
    'filter_tues',
    'filter_wed',
    'filter_thur',
    'filter_fri',
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


def filter_mon(ds: Iterable[DateType]):
    return filter_d(lambda d: d.weekday() == 0, ds)


def filter_tues(ds: Iterable[DateType]):
    return filter_d(lambda d: d.weekday() == 1, ds)


def filter_wed(ds: Iterable[DateType]):
    return filter_d(lambda d: d.weekday() == 2, ds)


def filter_thur(ds: Iterable[DateType]):
    return filter_d(lambda d: d.weekday() == 3, ds)


def filter_fri(ds: Iterable[DateType]):
    return filter_d(lambda d: d.weekday() == 4, ds)
