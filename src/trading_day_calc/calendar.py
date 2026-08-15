"""中国 A 股交易日历的核心查询接口。"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Literal

from ._cache import default_cache_path, load_best_available, write_cache_atomically
from ._data import CalendarData
from ._providers import Fetcher, fetch_official_page
from ._updater import fetch_verified_year, merge_year
from .errors import CalendarCoverageError

ClosedPeriodKind = Literal["weekend", "exchange_holiday", "mixed"]


@dataclass(frozen=True, slots=True)
class CalendarMetadata:
    """当前日历数据的来源与覆盖信息。"""

    coverage_start: date
    coverage_end: date
    generated_at: date
    session_count: int
    source_urls: tuple[str, ...]
    cache_path: Path
    auto_refresh: bool


@dataclass(frozen=True, slots=True)
class ClosedPeriod:
    """一段连续休市区间及其前后交易日。"""

    start: date
    end: date
    previous_trading_day: date
    next_trading_day: date
    kind: ClosedPeriodKind


@dataclass(frozen=True, slots=True)
class _CalendarState:
    data: CalendarData
    sessions: tuple[date, ...]
    session_set: frozenset[date]
    month_starts: tuple[date, ...]
    month_ends: tuple[date, ...]
    closed_periods: tuple[ClosedPeriod, ...]
    holiday_periods: tuple[ClosedPeriod, ...]
    closed_starts: tuple[date, ...]
    closed_ends: tuple[date, ...]
    holiday_starts: tuple[date, ...]
    holiday_ends: tuple[date, ...]


def _validate_date(value: object, *, field: str) -> date:
    if isinstance(value, datetime) or not isinstance(value, date):
        raise TypeError(f"{field} 必须是 datetime.date，不能是 datetime.datetime")
    return value


def _validate_range(start: date, end: date) -> tuple[date, date]:
    normalized_start = _validate_date(start, field="start")
    normalized_end = _validate_date(end, field="end")
    if normalized_start > normalized_end:
        raise ValueError("start 不能晚于 end")
    return normalized_start, normalized_end


def _validate_bool(value: object, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{field} 必须是 bool")
    return value


def _validate_timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError("timeout 必须是大于 0 的秒数")
    return float(value)


def _validate_year(value: object) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 1990 <= value <= 9999
    ):
        raise ValueError("through_year 必须是 1990 至 9999 的整数")
    return value


def _month_boundaries(
    sessions: tuple[date, ...],
) -> tuple[tuple[date, ...], tuple[date, ...]]:
    starts = [sessions[0]]
    ends: list[date] = []
    previous_session = sessions[0]
    for session in sessions[1:]:
        if (session.year, session.month) != (
            previous_session.year,
            previous_session.month,
        ):
            ends.append(previous_session)
            starts.append(session)
        previous_session = session
    ends.append(previous_session)
    return tuple(starts), tuple(ends)


def _build_closed_periods(sessions: tuple[date, ...]) -> tuple[ClosedPeriod, ...]:
    periods: list[ClosedPeriod] = []
    one_day = timedelta(days=1)
    for previous_session, next_session in zip(sessions, sessions[1:], strict=False):
        if next_session - previous_session == one_day:
            continue
        start = previous_session + one_day
        end = next_session - one_day
        has_weekday = False
        has_weekend = False
        current = start
        while current <= end:
            if current.weekday() < 5:
                has_weekday = True
            else:
                has_weekend = True
            current += one_day
        kind: ClosedPeriodKind
        if has_weekday and has_weekend:
            kind = "mixed"
        elif has_weekday:
            kind = "exchange_holiday"
        else:
            kind = "weekend"
        periods.append(
            ClosedPeriod(
                start=start,
                end=end,
                previous_trading_day=previous_session,
                next_trading_day=next_session,
                kind=kind,
            )
        )
    return tuple(periods)


def _build_state(data: CalendarData) -> _CalendarState:
    month_starts, month_ends = _month_boundaries(data.sessions)
    closed_periods = _build_closed_periods(data.sessions)
    holiday_periods = tuple(
        period for period in closed_periods if period.kind != "weekend"
    )
    return _CalendarState(
        data=data,
        sessions=data.sessions,
        session_set=frozenset(data.sessions),
        month_starts=month_starts,
        month_ends=month_ends,
        closed_periods=closed_periods,
        holiday_periods=holiday_periods,
        closed_starts=tuple(period.start for period in closed_periods),
        closed_ends=tuple(period.end for period in closed_periods),
        holiday_starts=tuple(period.start for period in holiday_periods),
        holiday_ends=tuple(period.end for period in holiday_periods),
    )


class TradingCalendar:
    """中国 A 股统一交易日历。

    默认加载随包发布且已经过完整性校验的日历快照。所有返回的日期序列均为
    不可变元组，调用方不能意外修改日历内部状态。
    """

    def __init__(
        self,
        cache_path: str | Path | None = None,
        *,
        auto_refresh: bool = True,
        timeout: float = 10.0,
        _fetcher: Fetcher = fetch_official_page,
    ) -> None:
        self._cache_path = (
            Path(cache_path) if cache_path is not None else default_cache_path()
        )
        self._auto_refresh = _validate_bool(auto_refresh, field="auto_refresh")
        self._timeout = _validate_timeout(timeout)
        self._fetcher = _fetcher
        self._refresh_lock = RLock()
        self._state = _build_state(load_best_available(self._cache_path))

    @property
    def sessions(self) -> tuple[date, ...]:
        """返回覆盖范围内的全部交易日。"""

        return self._state.sessions

    @property
    def coverage_start(self) -> date:
        """返回当前数据覆盖的首日。"""

        return self._state.data.coverage_start

    @property
    def coverage_end(self) -> date:
        """返回当前数据覆盖的末日，包括末日可能为非交易日的情况。"""

        return self._state.data.coverage_end

    @property
    def metadata(self) -> CalendarMetadata:
        """返回当前数据的只读元信息。"""

        data = self._state.data
        source_urls = tuple(
            url for source in data.sources for url in (source.sse, source.szse)
        )
        return CalendarMetadata(
            coverage_start=data.coverage_start,
            coverage_end=data.coverage_end,
            generated_at=data.generated_at,
            session_count=len(data.sessions),
            source_urls=source_urls,
            cache_path=self._cache_path,
            auto_refresh=self._auto_refresh,
        )

    def _ensure_coverage(self, start: date, end: date) -> None:
        if start < self.coverage_start:
            raise CalendarCoverageError(
                f"请求范围 {start} 至 {end} 超出当前覆盖范围 "
                f"{self.coverage_start} 至 {self.coverage_end}"
            )
        if end <= self.coverage_end:
            return
        if self._auto_refresh:
            self.refresh(through_year=end.year)
        if end > self.coverage_end:
            raise CalendarCoverageError(
                f"请求范围 {start} 至 {end} 超出当前覆盖范围 "
                f"{self.coverage_start} 至 {self.coverage_end}"
            )

    def is_trading_day(self, day: date) -> bool:
        """判断指定日期是否为交易日。"""

        normalized = _validate_date(day, field="day")
        self._ensure_coverage(normalized, normalized)
        return normalized in self._state.session_set

    def trading_days(self, start: date, end: date) -> tuple[date, ...]:
        """返回闭区间内的全部交易日。"""

        normalized_start, normalized_end = _validate_range(start, end)
        self._ensure_coverage(normalized_start, normalized_end)
        sessions = self._state.sessions
        left = bisect_left(sessions, normalized_start)
        right = bisect_right(sessions, normalized_end)
        return sessions[left:right]

    def next_trading_day(self, day: date, steps: int = 1) -> date:
        """返回严格位于指定日期之后的第 ``steps`` 个交易日。"""

        normalized = _validate_date(day, field="day")
        normalized_steps = self._validate_steps(steps)
        self._ensure_coverage(normalized, normalized)
        index = bisect_right(self._state.sessions, normalized) + normalized_steps - 1
        if index >= len(self._state.sessions):
            raise CalendarCoverageError("当前覆盖范围内不存在所请求的后续交易日")
        return self._state.sessions[index]

    def previous_trading_day(self, day: date, steps: int = 1) -> date:
        """返回严格位于指定日期之前的第 ``steps`` 个交易日。"""

        normalized = _validate_date(day, field="day")
        normalized_steps = self._validate_steps(steps)
        self._ensure_coverage(normalized, normalized)
        index = bisect_left(self._state.sessions, normalized) - normalized_steps
        if index < 0:
            raise CalendarCoverageError("当前覆盖范围内不存在所请求的前序交易日")
        return self._state.sessions[index]

    def month_starts(self, start: date, end: date) -> tuple[date, ...]:
        """返回区间内真正的月度首个交易日。"""

        return self._boundaries_between(self._state.month_starts, start, end)

    def month_ends(self, start: date, end: date) -> tuple[date, ...]:
        """返回区间内真正的月度最后一个交易日。"""

        return self._boundaries_between(self._state.month_ends, start, end)

    def closed_periods(
        self, start: date, end: date, *, include_weekends: bool = False
    ) -> tuple[ClosedPeriod, ...]:
        """返回与查询范围相交的完整休市区间。

        默认排除只包含周六、周日的普通周末。设为 ``include_weekends=True``
        后返回全部休市间隔。返回完整区间而不是裁剪后的片段，以保留准确的
        前后交易日信息。
        """

        normalized_start, normalized_end = _validate_range(start, end)
        self._ensure_coverage(normalized_start, normalized_end)
        normalized_include_weekends = _validate_bool(
            include_weekends, field="include_weekends"
        )
        state = self._state
        if normalized_include_weekends:
            periods = state.closed_periods
            starts = state.closed_starts
            ends = state.closed_ends
        else:
            periods = state.holiday_periods
            starts = state.holiday_starts
            ends = state.holiday_ends
        left = bisect_left(ends, normalized_start)
        right = bisect_right(starts, normalized_end)
        return periods[left:right]

    def _boundaries_between(
        self, boundaries: tuple[date, ...], start: date, end: date
    ) -> tuple[date, ...]:
        normalized_start, normalized_end = _validate_range(start, end)
        self._ensure_coverage(normalized_start, normalized_end)
        left = bisect_left(boundaries, normalized_start)
        right = bisect_right(boundaries, normalized_end)
        return boundaries[left:right]

    @staticmethod
    def _validate_steps(steps: object) -> int:
        if not isinstance(steps, int) or isinstance(steps, bool) or steps < 1:
            raise ValueError("steps 必须是大于等于 1 的整数")
        return steps

    def refresh(
        self, through_year: int | None = None, *, force: bool = False
    ) -> CalendarMetadata:
        """联网刷新日历，并在全部年度成功后原子写入缓存。

        ``through_year`` 默认为当前公历年份。普通刷新只扩展覆盖范围；设置
        ``force=True`` 时可重新核验并替换一个已覆盖年度。
        """

        normalized_force = _validate_bool(force, field="force")
        target_year = _validate_year(
            date.today().year if through_year is None else through_year
        )

        with self._refresh_lock:
            current_data = self._state.data
            earliest_refresh_year = min(source.year for source in current_data.sources)
            if target_year < earliest_refresh_year:
                raise CalendarCoverageError(
                    f"官方联网刷新仅支持 {earliest_refresh_year} 年及以后"
                )
            current_year = current_data.coverage_end.year
            if normalized_force:
                years = (target_year,)
            elif target_year > current_year:
                years = tuple(range(current_year + 1, target_year + 1))
            else:
                return self.metadata

            updated = current_data
            generated_at = date.today()
            for year in years:
                sessions, source = fetch_verified_year(
                    year, fetcher=self._fetcher, timeout=self._timeout
                )
                updated = merge_year(
                    updated,
                    year,
                    sessions,
                    source,
                    generated_at=generated_at,
                )
            write_cache_atomically(self._cache_path, updated)
            self._state = _build_state(updated)
            return self.metadata
