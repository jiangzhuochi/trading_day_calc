import hashlib
import logging
from datetime import date
from pathlib import Path

import pytest

from trading_day_calc import (
    CalendarCoverageError,
    CalendarDataError,
    CalendarUpdateError,
    TradingCalendar,
)
from trading_day_calc._cache import load_best_available, write_cache_atomically
from trading_day_calc._data import load_bundled_data
from trading_day_calc._providers import Exchange, FetchResponse

SSE_LISTING = "https://www.sse.com.cn/disclosure/dealinstruc/closed/list/"
SZSE_LISTING = "https://www.szse.cn/disclosure/notice/general/index.html"
SSE_NOTICE = "https://www.sse.com.cn/disclosure/announcement/general/c/2027.shtml"
SZSE_NOTICE = "https://www.szse.cn/disclosure/notice/general/2027.html"


def _notice(year: int, *, first_closed_day: int = 1) -> str:
    return f"""
    <h1>关于{year}年部分节假日休市安排的通知</h1>
    <p>元旦：1月{first_closed_day}日至1月3日休市，1月4日起照常开市。</p>
    <p>春节：2月8日至2月12日休市，2月15日起照常开市。</p>
    <p>清明节：4月5日休市，4月6日起照常开市。</p>
    <p>劳动节：5月3日至5月5日休市，5月6日起照常开市。</p>
    <p>端午节：6月14日休市，6月15日起照常开市。</p>
    <p>国庆节：10月1日至10月7日休市，10月8日起照常开市。</p>
    """


class FakeFetcher:
    def __init__(self, *, mismatch: bool = False, fail_once: bool = False) -> None:
        self.mismatch = mismatch
        self.fail_once = fail_once
        self.calls: list[tuple[Exchange, str]] = []

    def __call__(self, exchange: Exchange, url: str, timeout: float) -> FetchResponse:
        assert timeout == 3.0
        self.calls.append((exchange, url))
        if self.fail_once:
            self.fail_once = False
            raise CalendarUpdateError("模拟临时网络失败")
        if url == SSE_LISTING:
            return FetchResponse(
                url=url,
                text=f'<a href="{SSE_NOTICE}">2027年部分节假日休市安排</a>',
            )
        if url == SZSE_LISTING:
            return FetchResponse(
                url=url,
                text=f'<a href="{SZSE_NOTICE}">2027年部分节假日休市安排</a>',
            )
        first_day = 2 if self.mismatch and exchange == "SZSE" else 1
        return FetchResponse(url=url, text=_notice(2027, first_closed_day=first_day))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_future_query_refreshes_once_and_reuses_persistent_cache(
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "calendar.json"
    fetcher = FakeFetcher()
    calendar = TradingCalendar(
        cache_path, auto_refresh=True, timeout=3.0, _fetcher=fetcher
    )

    assert calendar.is_trading_day(date(2027, 1, 4))
    assert calendar.coverage_end.isoformat() == "2027-12-31"
    assert cache_path.exists()
    assert len(fetcher.calls) == 4

    offline_fetcher = FakeFetcher()
    cached_calendar = TradingCalendar(
        cache_path, auto_refresh=True, timeout=3.0, _fetcher=offline_fetcher
    )
    assert cached_calendar.is_trading_day(date(2027, 1, 4))
    assert offline_fetcher.calls == []


def test_disabled_auto_refresh_fails_without_network(tmp_path: Path) -> None:
    fetcher = FakeFetcher()
    calendar = TradingCalendar(
        tmp_path / "calendar.json",
        auto_refresh=False,
        timeout=3.0,
        _fetcher=fetcher,
    )

    with pytest.raises(CalendarCoverageError):
        calendar.is_trading_day(date(2027, 1, 4))
    assert fetcher.calls == []


def test_transient_update_error_is_retried_once(tmp_path: Path) -> None:
    fetcher = FakeFetcher(fail_once=True)
    calendar = TradingCalendar(
        tmp_path / "calendar.json", timeout=3.0, _fetcher=fetcher
    )

    calendar.refresh(through_year=2027)

    assert len(fetcher.calls) == 5


def test_source_mismatch_does_not_replace_existing_cache(tmp_path: Path) -> None:
    cache_path = tmp_path / "calendar.json"
    calendar = TradingCalendar(cache_path, timeout=3.0, _fetcher=FakeFetcher())
    calendar.refresh(through_year=2027)
    original_hash = _sha256(cache_path)

    mismatched = TradingCalendar(
        cache_path, timeout=3.0, _fetcher=FakeFetcher(mismatch=True)
    )
    with pytest.raises(CalendarDataError):
        mismatched.refresh(through_year=2027, force=True)

    assert _sha256(cache_path) == original_hash


def test_corrupt_cache_is_ignored_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cache_path = tmp_path / "calendar.json"
    cache_path.write_text("not-json", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        data = load_best_available(cache_path)

    assert data.coverage_end.isoformat() == "2026-12-31"
    assert "忽略损坏" in caplog.text


def test_atomic_write_failure_preserves_existing_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "calendar.json"
    cache_path.write_text("existing-cache", encoding="utf-8")

    def fail_replace(_source: object, _destination: object) -> None:
        raise OSError("模拟原子替换失败")

    monkeypatch.setattr("trading_day_calc._cache.os.replace", fail_replace)

    with pytest.raises(CalendarUpdateError):
        write_cache_atomically(cache_path, load_bundled_data())

    assert cache_path.read_text(encoding="utf-8") == "existing-cache"
    assert list(tmp_path.glob("*.tmp")) == []


@pytest.mark.parametrize(
    ("kwargs", "error_type"),
    [
        ({"timeout": 0}, ValueError),
        ({"timeout": True}, ValueError),
        ({"auto_refresh": 1}, TypeError),
    ],
)
def test_invalid_calendar_options_are_rejected(
    tmp_path: Path,
    kwargs: dict[str, object],
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type):
        TradingCalendar(tmp_path / "calendar.json", **kwargs)  # type: ignore[arg-type]
