"""中国 A 股交易日历的核心查询接口。"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import date, datetime

from ._data import CalendarData, load_bundled_data
from .errors import CalendarCoverageError


@dataclass(frozen=True, slots=True)
class CalendarMetadata:
    """当前日历数据的来源与覆盖信息。"""

    coverage_start: date
    coverage_end: date
    generated_at: date
    session_count: int
    source_urls: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _CalendarState:
    data: CalendarData
    sessions: tuple[date, ...]
    session_set: frozenset[date]
    month_starts: tuple[date, ...]
    month_ends: tuple[date, ...]


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


def _build_state(data: CalendarData) -> _CalendarState:
    month_starts, month_ends = _month_boundaries(data.sessions)
    return _CalendarState(
        data=data,
        sessions=data.sessions,
        session_set=frozenset(data.sessions),
        month_starts=month_starts,
        month_ends=month_ends,
    )


class TradingCalendar:
    """中国 A 股统一交易日历。

    默认加载随包发布且已经过完整性校验的日历快照。所有返回的日期序列均为
    不可变元组，调用方不能意外修改日历内部状态。
    """

    def __init__(self) -> None:
        self._state = _build_state(load_bundled_data())

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
        )

    def _require_coverage(self, start: date, end: date) -> None:
        if start < self.coverage_start or end > self.coverage_end:
            raise CalendarCoverageError(
                f"请求范围 {start} 至 {end} 超出当前覆盖范围 "
                f"{self.coverage_start} 至 {self.coverage_end}"
            )

    def is_trading_day(self, day: date) -> bool:
        """判断指定日期是否为交易日。"""

        normalized = _validate_date(day, field="day")
        self._require_coverage(normalized, normalized)
        return normalized in self._state.session_set

    def trading_days(self, start: date, end: date) -> tuple[date, ...]:
        """返回闭区间内的全部交易日。"""

        normalized_start, normalized_end = _validate_range(start, end)
        self._require_coverage(normalized_start, normalized_end)
        sessions = self._state.sessions
        left = bisect_left(sessions, normalized_start)
        right = bisect_right(sessions, normalized_end)
        return sessions[left:right]

    def next_trading_day(self, day: date, steps: int = 1) -> date:
        """返回严格位于指定日期之后的第 ``steps`` 个交易日。"""

        normalized = _validate_date(day, field="day")
        normalized_steps = self._validate_steps(steps)
        self._require_coverage(normalized, normalized)
        index = bisect_right(self._state.sessions, normalized) + normalized_steps - 1
        if index >= len(self._state.sessions):
            raise CalendarCoverageError("当前覆盖范围内不存在所请求的后续交易日")
        return self._state.sessions[index]

    def previous_trading_day(self, day: date, steps: int = 1) -> date:
        """返回严格位于指定日期之前的第 ``steps`` 个交易日。"""

        normalized = _validate_date(day, field="day")
        normalized_steps = self._validate_steps(steps)
        self._require_coverage(normalized, normalized)
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

    def _boundaries_between(
        self, boundaries: tuple[date, ...], start: date, end: date
    ) -> tuple[date, ...]:
        normalized_start, normalized_end = _validate_range(start, end)
        self._require_coverage(normalized_start, normalized_end)
        left = bisect_left(boundaries, normalized_start)
        right = bisect_right(boundaries, normalized_end)
        return boundaries[left:right]

    @staticmethod
    def _validate_steps(steps: object) -> int:
        if not isinstance(steps, int) or isinstance(steps, bool) or steps < 1:
            raise ValueError("steps 必须是大于等于 1 的整数")
        return steps
