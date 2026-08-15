"""交易日历数据的读取与完整性校验。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from importlib import resources
from pathlib import Path
from urllib.parse import urlsplit

from .errors import CalendarDataError

SCHEMA_VERSION = 1
MARKET = "CN_A_SHARE"


@dataclass(frozen=True, slots=True)
class SourceRecord:
    """一个年度对应的沪深交易所官方来源。"""

    year: int
    sse: str
    szse: str


@dataclass(frozen=True, slots=True)
class CalendarData:
    """经过校验、可供计算使用的不可变日历数据。"""

    coverage_start: date
    coverage_end: date
    generated_at: date
    sessions: tuple[date, ...]
    sources: tuple[SourceRecord, ...]


def _fail(origin: str, message: str) -> CalendarDataError:
    return CalendarDataError(f"{origin}: {message}")


def _as_mapping(value: object, *, origin: str, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise _fail(origin, f"{field} 必须是字符串键对象")
    return value


def _as_list(value: object, *, origin: str, field: str) -> list[object]:
    if not isinstance(value, list):
        raise _fail(origin, f"{field} 必须是数组")
    return value


def _as_string(value: object, *, origin: str, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise _fail(origin, f"{field} 必须是非空字符串")
    return value


def _as_integer(value: object, *, origin: str, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise _fail(origin, f"{field} 必须是整数")
    return value


def _as_date(value: object, *, origin: str, field: str) -> date:
    text = _as_string(value, origin=origin, field=field)
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise _fail(origin, f"{field} 不是有效的 ISO 日期") from exc


def _validate_source_url(url: str, *, origin: str, field: str) -> None:
    parsed = urlsplit(url)
    expected_host = "www.sse.com.cn" if field == "sse" else "www.szse.cn"
    if parsed.scheme != "https" or parsed.hostname != expected_host:
        raise _fail(origin, f"{field} 必须指向 {expected_host} 的 HTTPS 地址")


def _parse_sources(value: object, *, origin: str) -> tuple[SourceRecord, ...]:
    records: list[SourceRecord] = []
    for index, item in enumerate(_as_list(value, origin=origin, field="sources")):
        field = f"sources[{index}]"
        mapping = _as_mapping(item, origin=origin, field=field)
        year = _as_integer(mapping.get("year"), origin=origin, field=f"{field}.year")
        sse = _as_string(mapping.get("sse"), origin=origin, field=f"{field}.sse")
        szse = _as_string(mapping.get("szse"), origin=origin, field=f"{field}.szse")
        _validate_source_url(sse, origin=origin, field="sse")
        _validate_source_url(szse, origin=origin, field="szse")
        records.append(SourceRecord(year=year, sse=sse, szse=szse))

    years = [record.year for record in records]
    if not records:
        raise _fail(origin, "sources 不能为空")
    if years != sorted(set(years)):
        raise _fail(origin, "sources 年份必须严格递增且不重复")
    return tuple(records)


def parse_calendar_data(text: str, *, origin: str = "日历数据") -> CalendarData:
    """解析并严格校验一份日历 JSON。"""

    try:
        decoded: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise _fail(origin, "不是有效的 JSON") from exc

    payload = _as_mapping(decoded, origin=origin, field="根节点")
    version = _as_integer(
        payload.get("schema_version"), origin=origin, field="schema_version"
    )
    if version != SCHEMA_VERSION:
        raise _fail(origin, f"不支持 schema_version={version}")
    market = _as_string(payload.get("market"), origin=origin, field="market")
    if market != MARKET:
        raise _fail(origin, f"不支持 market={market}")

    coverage_start = _as_date(
        payload.get("coverage_start"), origin=origin, field="coverage_start"
    )
    coverage_end = _as_date(
        payload.get("coverage_end"), origin=origin, field="coverage_end"
    )
    generated_at = _as_date(
        payload.get("generated_at"), origin=origin, field="generated_at"
    )
    if coverage_start > coverage_end:
        raise _fail(origin, "coverage_start 不能晚于 coverage_end")

    raw_sessions = _as_list(payload.get("sessions"), origin=origin, field="sessions")
    sessions = tuple(
        _as_date(item, origin=origin, field=f"sessions[{index}]")
        for index, item in enumerate(raw_sessions)
    )
    if not sessions:
        raise _fail(origin, "sessions 不能为空")
    if any(current >= following for current, following in zip(sessions, sessions[1:])):
        raise _fail(origin, "sessions 必须严格递增且不重复")
    if any(item.weekday() >= 5 for item in sessions):
        raise _fail(origin, "sessions 不能包含周六或周日")
    if (
        sessions[0] != coverage_start
        or not coverage_start <= sessions[-1] <= coverage_end
    ):
        raise _fail(origin, "sessions 与覆盖范围不一致")

    expected_count = _as_integer(
        payload.get("session_count"), origin=origin, field="session_count"
    )
    if expected_count != len(sessions):
        raise _fail(origin, "session_count 与 sessions 长度不一致")

    return CalendarData(
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        generated_at=generated_at,
        sessions=sessions,
        sources=_parse_sources(payload.get("sources"), origin=origin),
    )


def load_calendar_file(path: Path) -> CalendarData:
    """从指定 UTF-8 JSON 文件加载日历。"""

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CalendarDataError(f"无法读取日历文件 {path}: {exc}") from exc
    return parse_calendar_data(text, origin=str(path))


def load_bundled_data() -> CalendarData:
    """加载随 Python 包发布的内置日历。"""

    resource = resources.files("trading_day_calc").joinpath("calendar.json")
    try:
        text = resource.read_text(encoding="utf-8")
    except OSError as exc:
        raise CalendarDataError(f"无法读取包内 calendar.json: {exc}") from exc
    return parse_calendar_data(text, origin="包内 calendar.json")
