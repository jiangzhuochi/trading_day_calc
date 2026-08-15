"""双交易所校验和年度日历合并。"""

from __future__ import annotations

from datetime import date, timedelta

from ._data import CalendarData, SourceRecord
from ._providers import (
    Exchange,
    Fetcher,
    HolidaySchedule,
    fetch_annual_schedule,
    fetch_official_page,
)
from .errors import CalendarDataError, CalendarUpdateError


def _fetch_with_retry(
    exchange: Exchange, year: int, *, fetcher: Fetcher, timeout: float
) -> HolidaySchedule:
    last_error: CalendarUpdateError | None = None
    for _attempt in range(2):
        try:
            return fetch_annual_schedule(
                exchange, year, fetcher=fetcher, timeout=timeout
            )
        except CalendarUpdateError as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def fetch_verified_year(
    year: int,
    *,
    fetcher: Fetcher = fetch_official_page,
    timeout: float = 10.0,
) -> tuple[tuple[date, ...], SourceRecord]:
    """抓取两所年度公告，仅在休市集合一致时生成交易日。"""

    sse = _fetch_with_retry("SSE", year, fetcher=fetcher, timeout=timeout)
    szse = _fetch_with_retry("SZSE", year, fetcher=fetcher, timeout=timeout)
    if sse.closed_weekdays != szse.closed_weekdays:
        raise CalendarDataError(f"沪深交易所 {year} 年休市安排不一致，拒绝更新")

    closed = frozenset(sse.closed_weekdays)
    current = date(year, 1, 1)
    end = date(year, 12, 31)
    sessions: list[date] = []
    while current <= end:
        if current.weekday() < 5 and current not in closed:
            sessions.append(current)
        current += timedelta(days=1)
    if not 200 <= len(sessions) <= 260:
        raise CalendarDataError(
            f"{year} 年生成了异常的 {len(sessions)} 个交易日，拒绝更新"
        )
    return tuple(sessions), SourceRecord(
        year=year, sse=sse.source_url, szse=szse.source_url
    )


def merge_year(
    data: CalendarData,
    year: int,
    sessions: tuple[date, ...],
    source: SourceRecord,
    *,
    generated_at: date,
) -> CalendarData:
    """在不可变日历数据中新增或替换一个完整年度。"""

    if source.year != year or any(session.year != year for session in sessions):
        raise CalendarDataError("年度交易日与来源年份不一致")
    merged_sessions = tuple(
        sorted(
            [session for session in data.sessions if session.year != year]
            + list(sessions)
        )
    )
    merged_sources = tuple(
        sorted(
            [record for record in data.sources if record.year != year] + [source],
            key=lambda record: record.year,
        )
    )
    coverage_end = max(data.coverage_end, date(year, 12, 31))
    return CalendarData(
        coverage_start=data.coverage_start,
        coverage_end=coverage_end,
        generated_at=generated_at,
        sessions=merged_sessions,
        sources=merged_sources,
    )
