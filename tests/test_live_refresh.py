from __future__ import annotations

import os
from pathlib import Path

import pytest

from trading_day_calc import TradingCalendar
from trading_day_calc._data import load_calendar_file

NETWORK_TEST_ENABLED = os.environ.get("TRADING_DAY_CALC_NETWORK_TEST") == "1"


@pytest.mark.network
@pytest.mark.skipif(
    not NETWORK_TEST_ENABLED,
    reason="设置 TRADING_DAY_CALC_NETWORK_TEST=1 后运行真实网站测试",
)
def test_live_2026_refresh_end_to_end(tmp_path: Path) -> None:
    cache_path = tmp_path / "calendar-v1.json"
    calendar = TradingCalendar(
        cache_path,
        auto_refresh=False,
        timeout=20.0,
    )

    metadata = calendar.refresh(through_year=2026, force=True)
    cached = load_calendar_file(cache_path)

    assert metadata.coverage_start.isoformat() == "1990-12-19"
    assert metadata.coverage_end.isoformat() == "2026-12-31"
    assert metadata.session_count == 8797
    assert cached.sessions == calendar.sessions
    assert cached.sources[-1].year == 2026
    assert cached.sources[-1].sse.startswith("https://www.sse.com.cn/")
    assert cached.sources[-1].szse.startswith("https://www.szse.cn/")
