from __future__ import annotations

from pathlib import Path
from types import TracebackType

import pytest

import trading_day_calc._providers as providers
from trading_day_calc._providers import (
    FetchResponse,
    discover_notice_url,
    fetch_annual_schedule,
    fetch_official_page,
    parse_annual_notice,
)
from trading_day_calc.errors import CalendarCoverageError, CalendarDataError

FIXTURES = Path(__file__).parent / "fixtures"
SSE_URL = (
    "https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml"
)
SZSE_URL = "https://www.szse.cn/disclosure/notice/general/t20251222_618087.html"


class _FakeHeaders:
    def get_content_charset(self) -> str:
        return "utf-8"


class _FakeResponse:
    def __init__(self, url: str, body: bytes) -> None:
        self._url = url
        self._body = body
        self.headers = _FakeHeaders()

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exception_type, exception, traceback

    def geturl(self) -> str:
        return self._url

    def read(self, size: int) -> bytes:
        assert size > len(self._body)
        return self._body


class _FakeOpener:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    def open(self, request: object, timeout: float) -> _FakeResponse:
        assert request is not None
        assert timeout == 2.0
        return self._response


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_official_fetcher_limits_and_decodes_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = "官方页面".encode()
    monkeypatch.setattr(
        providers,
        "_DIRECT_OPENER",
        _FakeOpener(_FakeResponse(SSE_URL, body)),
    )

    response = fetch_official_page("SSE", SSE_URL, 2.0)

    assert response == FetchResponse(url=SSE_URL, text="官方页面")


def test_annual_notices_parse_to_the_same_schedule() -> None:
    sse = parse_annual_notice("SSE", 2026, SSE_URL, _fixture("sse_2026.html"))
    szse = parse_annual_notice("SZSE", 2026, SZSE_URL, _fixture("szse_2026.html"))

    assert sse.closed_weekdays == szse.closed_weekdays
    assert len(sse.closed_weekdays) == 19
    assert sse.closed_weekdays[0].isoformat() == "2026-01-01"
    assert sse.closed_weekdays[-1].isoformat() == "2026-10-07"


def test_notice_discovery_selects_one_annual_notice() -> None:
    listing = f'<a href="{SSE_URL}">2026 年部分节假日休市安排</a>'
    single_holiday_url = (
        "https://www.sse.com.cn/disclosure/announcement/general/holiday.shtml"
    )
    listing_with_single_holiday = (
        f'<a href="{single_holiday_url}">关于2026年端午节休市安排的公告</a>' + listing
    )
    assert discover_notice_url("SSE", listing_with_single_holiday, 2026) == SSE_URL

    with pytest.raises(CalendarCoverageError):
        discover_notice_url("SSE", "<html>没有公告</html>", 2026)
    with pytest.raises(CalendarDataError):
        discover_notice_url(
            "SSE",
            listing + '<a href="/duplicate">2026年部分节假日休市安排</a>',
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


def test_fetch_schedule_traverses_szse_static_pages() -> None:
    listing_url = "https://www.szse.cn/disclosure/notice/general/index.html"
    annual_url = "https://www.szse.cn/disclosure/notice/general/annual.html"
    listing = '<script>createPageHTML(5, 0, "index", "html");</script>'
    annual_listing = f"""
        <script>
        var curHref = '{annual_url}';
        //var curTitle = '被注释的标题';
        var curTitle = '关于20 26年部分节假日休市安排的通知';
        </script>
    """
    calls: list[str] = []

    def fake_fetcher(exchange: str, url: str, timeout: float) -> FetchResponse:
        assert exchange == "SZSE"
        assert timeout == 3.0
        calls.append(url)
        if url == annual_url:
            return FetchResponse(url=SZSE_URL, text=_fixture("szse_2026.html"))
        if url.endswith("index_3.html"):
            return FetchResponse(url=url, text=annual_listing)
        return FetchResponse(url=url, text=listing if url == listing_url else "")

    schedule = fetch_annual_schedule("SZSE", 2026, fetcher=fake_fetcher, timeout=3.0)

    assert calls == [
        listing_url,
        "https://www.szse.cn/disclosure/notice/general/index_1.html",
        "https://www.szse.cn/disclosure/notice/general/index_2.html",
        "https://www.szse.cn/disclosure/notice/general/index_3.html",
        annual_url,
    ]
    assert len(schedule.closed_weekdays) == 19


def test_listing_pagination_rejects_abnormal_page_count() -> None:
    listing = '<script>createPageHTML(51, 0, "index", "html");</script>'

    def fake_fetcher(exchange: str, url: str, timeout: float) -> FetchResponse:
        del exchange, timeout
        return FetchResponse(url=url, text=listing)

    with pytest.raises(CalendarDataError, match="页数异常"):
        fetch_annual_schedule("SZSE", 2026, fetcher=fake_fetcher)
