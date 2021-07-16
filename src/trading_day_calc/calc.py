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
    'get_last_day_per_month',
    'get_1d_after_holiday',
    'get_1d_before_holiday',
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


def _get_nd_before_or_after_holiday(*, ds: Optional[List[DateType]],
                                    start: Optional[DateType],
                                    end: Optional[DateType],
                                    nth: int = 0) -> List[DateType]:

    ungrouped = filter_between(ds=ds, start=start, end=end)
    if len(ungrouped) == 0:
        return []

    s: DateType = ungrouped[0]
    e: DateType = ungrouped[-1]

    # 时间列表的开始日的前一交易日，结束日的后一交易日也加进去
    i = TRADE_DATE.index(s)
    if i > 0:
        before_s = [TRADE_DATE[i-1]]
    else:
        before_s = []

    i = TRADE_DATE.index(e)
    if i < len(TRADE_DATE) - 1:
        after_e = [TRADE_DATE[i+1]]
    else:
        after_e = []

    if before_s and after_e:
        ungrouped_before_s = before_s + ungrouped
        ungrouped_after_e = ungrouped + after_e
    elif before_s:
        ungrouped_before_s = before_s + ungrouped[:-1]
        ungrouped_after_e = ungrouped
    elif after_e:
        ungrouped_before_s = ungrouped
        ungrouped_after_e = ungrouped[1:] + after_e
    else:
        ungrouped_before_s = ungrouped[:-1]
        ungrouped_after_e = ungrouped[1:]

    diff = list(map(
        lambda d1, d2: (d2-d1).days,
        ungrouped_before_s,
        ungrouped_after_e
    ))
    # 这个列表存放的数字，对应于 ungrouped_after_e 列表下标，是假期后的第一个交易日
    subscripts = [i for i, j in enumerate(diff) if j > 1]

    # 全部的切片组
    slices: List[slice] = []
    for i in range(len(subscripts)):
        if i == 0:
            slices.append(slice(0, subscripts[0]))
        if i < len(subscripts) - 1:
            slices.append(slice(subscripts[i], subscripts[i+1]))
        else:
            # 原本的 ungrouped 不含 after_e，因此这里的切片也不包含它
            slices.append(slice(subscripts[i], len(ungrouped_after_e)-1))

    groups = []
    # nth 不小于 0 是假期后，nth=0 为假期后第一个交易日，nth=1 为假期后第二个交易日
    # nth=-1 为假期前第一个交易日
    # 当提取假期后交易日时，去掉第一组
    # 原因是第一组的第一天可能 不是 假期后的第一天
    # 同理，当计算假期前交易日时，去掉最后一组
    slice_group = slices[1:] if nth >= 0 else slices[:-1]
    for sli in slice_group:
        try:
            groups.append(ungrouped_after_e[sli][nth])
        except IndexError:
            pass

    # print('\n\n', diff)
    # print('\n\n', slice_group)
    # print('\n\n', ungrouped_after_e)
    # print('\n\n', groups)

    return groups


def get_1d_after_holiday(ds: Optional[List[DateType]] = None, *,
                         start: Optional[DateType] = None,
                         end: Optional[DateType] = None) -> List[DateType]:
    return _get_nd_before_or_after_holiday(ds=ds, start=start, end=end, nth=0)


def get_1d_before_holiday(ds: Optional[List[DateType]] = None, *,
                          start: Optional[DateType] = None,
                          end: Optional[DateType] = None) -> List[DateType]:
    return _get_nd_before_or_after_holiday(ds=ds, start=start, end=end, nth=-1)
