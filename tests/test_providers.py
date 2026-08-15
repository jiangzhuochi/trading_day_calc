from pathlib import Path

import pytest

from trading_day_calc._providers import (
    FetchResponse,
    discover_notice_url,
    fetch_annual_schedule,
    parse_annual_notice,
)
from trading_day_calc.errors import CalendarDataError

FIXTURES = Path(__file__).parent / "fixtures"
SSE_URL = (
    "https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml"
)
SZSE_URL = "https://www.szse.cn/disclosure/notice/general/t20251222_618087.html"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_annual_notices_parse_to_the_same_schedule() -> None:
    sse = parse_annual_notice("SSE", 2026, SSE_URL, _fixture("sse_2026.html"))
    szse = parse_annual_notice("SZSE", 2026, SZSE_URL, _fixture("szse_2026.html"))

    assert sse.closed_weekdays == szse.closed_weekdays
    assert len(sse.closed_weekdays) == 19
    assert sse.closed_weekdays[0].isoformat() == "2026-01-01"
    assert sse.closed_weekdays[-1].isoformat() == "2026-10-07"


def test_notice_discovery_requires_one_official_match() -> None:
    listing = f'<a href="{SSE_URL}">2026 年部分节假日休市安排</a>'
    assert discover_notice_url("SSE", listing, 2026) == SSE_URL

    with pytest.raises(CalendarDataError):
        discover_notice_url("SSE", "<html>没有公告</html>", 2026)
    with pytest.raises(CalendarDataError):
        discover_notice_url(
            "SSE",
            listing + '<a href="/duplicate">2026年休市安排</a>',
            2026,
        )


def test_malformed_or_wrong_year_notice_is_rejected() -> None:
    with pytest.raises(CalendarDataError):
        parse_annual_notice("SSE", 2025, SSE_URL, _fixture("sse_2026.html"))
    with pytest.raises(CalendarDataError):
        parse_annual_notice(
            "SSE",
            2026,
            SSE_URL,
            "<h1>2026年休市安排</h1><p>1月1日休市，1月2日起照常开市</p>",
        )
    with pytest.raises(CalendarDataError):
        parse_annual_notice(
            "SSE", 2026, "https://example.com/notice", _fixture("sse_2026.html")
        )


def test_fetch_schedule_uses_discovered_notice() -> None:
    listing_url = "https://www.sse.com.cn/disclosure/dealinstruc/closed/list/"
    listing = f'<a href="{SSE_URL}">2026年部分节假日休市安排</a>'
    calls: list[str] = []

    def fake_fetcher(exchange: str, url: str, timeout: float) -> FetchResponse:
        assert exchange == "SSE"
        assert timeout == 3.0
        calls.append(url)
        if url == listing_url:
            return FetchResponse(url=url, text=listing)
        return FetchResponse(url=url, text=_fixture("sse_2026.html"))

    schedule = fetch_annual_schedule("SSE", 2026, fetcher=fake_fetcher, timeout=3.0)

    assert calls == [listing_url, SSE_URL]
    assert len(schedule.closed_weekdays) == 19
