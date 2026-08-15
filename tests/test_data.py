import hashlib
import json
from collections.abc import Callable
from datetime import date
from importlib import resources

import pytest

from trading_day_calc._data import load_bundled_data, parse_calendar_data
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
    return value


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
    [
        lambda payload: payload.update(schema_version=999),
        lambda payload: payload.update(market="UNKNOWN"),
        lambda payload: payload.update(session_count=1),
        lambda payload: payload.update(coverage_start="2026-01-01"),
        lambda payload: payload.update(sessions=["2021-01-04", "2021-01-04"]),
        lambda payload: payload.update(sessions=["2021-01-09"]),
        lambda payload: payload.update(sources=[]),
    ],
)
def test_invalid_calendar_data_is_rejected(
    mutate: Callable[[dict[str, object]], None],
) -> None:
    payload = _bundled_payload()
    mutate(payload)

    with pytest.raises(CalendarDataError):
        parse_calendar_data(json.dumps(payload))
