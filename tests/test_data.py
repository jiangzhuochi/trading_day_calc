import hashlib
import json
from collections.abc import Callable
from datetime import date
from importlib import resources
from pathlib import Path
from typing import cast

import pytest

from trading_day_calc._data import (
    calendar_data_to_json,
    load_bundled_data,
    load_calendar_file,
    parse_calendar_data,
)
from trading_day_calc.errors import CalendarDataError

LEGACY_SESSION_COUNT = 7_586
LEGACY_SESSION_SHA256 = (
    "6cf4443577a41897d0799e2b8e23746a7f5e671147164601528c4ff50f52364a"
)


def _bundled_payload() -> dict[str, object]:
    text = (
        resources.files("trading_day_calc")
        .joinpath("calendar.json")
        .read_text(encoding="utf-8")
    )
    value = json.loads(text)
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _invalid_schema(payload: dict[str, object]) -> None:
    payload["schema_version"] = 999


def _invalid_market(payload: dict[str, object]) -> None:
    payload["market"] = "UNKNOWN"


def _invalid_count(payload: dict[str, object]) -> None:
    payload["session_count"] = 1


def _invalid_coverage(payload: dict[str, object]) -> None:
    payload["coverage_start"] = "2026-01-01"


def _duplicate_sessions(payload: dict[str, object]) -> None:
    payload["sessions"] = ["2021-01-04", "2021-01-04"]


def _weekend_session(payload: dict[str, object]) -> None:
    payload["sessions"] = ["2021-01-09"]


def _missing_sources(payload: dict[str, object]) -> None:
    payload["sources"] = []


def _invalid_sessions_type(payload: dict[str, object]) -> None:
    payload["sessions"] = "not-a-list"


def _empty_market(payload: dict[str, object]) -> None:
    payload["market"] = ""


def _boolean_count(payload: dict[str, object]) -> None:
    payload["session_count"] = True


def _invalid_date(payload: dict[str, object]) -> None:
    payload["generated_at"] = "2026-13-01"


def _reversed_coverage(payload: dict[str, object]) -> None:
    payload["coverage_start"] = "2027-01-01"
    payload["coverage_end"] = "2026-12-31"


def _empty_sessions(payload: dict[str, object]) -> None:
    payload["sessions"] = []
    payload["session_count"] = 0


def _invalid_source_url(payload: dict[str, object]) -> None:
    sources = cast(list[object], payload["sources"])
    first = cast(dict[str, object], sources[0])
    first["sse"] = "http://www.sse.com.cn/notice"


def _unordered_sources(payload: dict[str, object]) -> None:
    sources = cast(list[object], payload["sources"])
    payload["sources"] = [sources[1], sources[0], *sources[2:]]


INVALID_MUTATIONS: tuple[Callable[[dict[str, object]], None], ...] = (
    _invalid_schema,
    _invalid_market,
    _invalid_count,
    _invalid_coverage,
    _duplicate_sessions,
    _weekend_session,
    _missing_sources,
    _invalid_sessions_type,
    _empty_market,
    _boolean_count,
    _invalid_date,
    _reversed_coverage,
    _empty_sessions,
    _invalid_source_url,
    _unordered_sources,
)


def test_bundled_data_preserves_legacy_sessions_and_extends_to_2026() -> None:
    data = load_bundled_data()

    legacy_payload = "\n".join(
        item.isoformat() for item in data.sessions[:LEGACY_SESSION_COUNT]
    ).encode()
    assert hashlib.sha256(legacy_payload).hexdigest() == LEGACY_SESSION_SHA256
    assert data.coverage_start == date(1990, 12, 19)
    assert data.coverage_end == date(2026, 12, 31)
    assert data.sessions[-1] == date(2026, 12, 31)
    assert len(data.sessions) == 8_797
    assert [
        sum(item.year == year for item in data.sessions) for year in range(2022, 2027)
    ] == [
        242,
        242,
        242,
        243,
        242,
    ]
    assert [source.year for source in data.sources] == [2022, 2023, 2024, 2025, 2026]


@pytest.mark.parametrize(
    "mutate",
    INVALID_MUTATIONS,
)
def test_invalid_calendar_data_is_rejected(
    mutate: Callable[[dict[str, object]], None],
) -> None:
    payload = _bundled_payload()
    mutate(payload)

    with pytest.raises(CalendarDataError):
        parse_calendar_data(json.dumps(payload))


def test_calendar_json_round_trip_and_missing_file_error(tmp_path: Path) -> None:
    bundled = load_bundled_data()

    assert parse_calendar_data(calendar_data_to_json(bundled)) == bundled
    with pytest.raises(CalendarDataError):
        load_calendar_file(tmp_path / "missing.json")
