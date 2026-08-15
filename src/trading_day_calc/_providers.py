"""沪深交易所年度休市公告的发现、抓取与解析。"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from html.parser import HTMLParser
from typing import Literal, Protocol
from urllib.parse import urljoin, urlsplit
from urllib.request import OpenerDirector, ProxyHandler, Request, build_opener

from .errors import CalendarCoverageError, CalendarDataError, CalendarUpdateError

Exchange = Literal["SSE", "SZSE"]

LISTING_URLS: dict[Exchange, str] = {
    "SSE": "https://www.sse.com.cn/disclosure/dealinstruc/closed/list/",
    "SZSE": "https://www.szse.cn/disclosure/notice/general/index.html",
}
ALLOWED_HOSTS: dict[Exchange, str] = {
    "SSE": "www.sse.com.cn",
    "SZSE": "www.szse.cn",
}
MAX_RESPONSE_BYTES = 2 * 1024 * 1024

# 交易所官网可直接公开访问。显式使用空代理处理器，避免继承环境变量或
# Windows 系统代理；某些代理会在 TLS 握手阶段提前断开连接。
_DIRECT_OPENER: OpenerDirector = build_opener(ProxyHandler({}))

_DATE_TOKEN = (
    r"(?:\d{4}\s*年\s*)?\d{1,2}\s*月\s*\d{1,2}\s*日"
    r"(?:\s*[（(]\s*星期[^）)]*[）)])?"
)
_CLOSED_RANGE_PATTERN = re.compile(
    rf"(?P<start>{_DATE_TOKEN})(?:\s*至\s*(?P<end>{_DATE_TOKEN}))?\s*休市"
)
_DATE_PATTERN = re.compile(
    r"(?:(?P<year>\d{4})\s*年\s*)?"
    r"(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})\s*日"
)


@dataclass(frozen=True, slots=True)
class FetchResponse:
    """一次受限制 HTTP 抓取的结果。"""

    url: str
    text: str


@dataclass(frozen=True, slots=True)
class HolidaySchedule:
    """某交易所某年度公告解析出的工作日休市集合。"""

    exchange: Exchange
    year: int
    source_url: str
    closed_weekdays: tuple[date, ...]


class Fetcher(Protocol):
    """可替换的网页抓取接口，便于离线测试。"""

    def __call__(
        self, exchange: Exchange, url: str, timeout: float
    ) -> FetchResponse: ...


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.lower() in {"script", "style"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


class _AnchorExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a" or self._href is not None:
            return
        href = next((value for name, value in attrs if name.lower() == "href"), None)
        if href:
            self._href = href
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._parts)))
            self._href = None
            self._parts = []


def _validate_official_url(exchange: Exchange, url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOSTS[exchange]:
        raise CalendarDataError(
            f"{exchange} 来源必须是 {ALLOWED_HOSTS[exchange]} 的 HTTPS 地址"
        )


def fetch_official_page(exchange: Exchange, url: str, timeout: float) -> FetchResponse:
    """使用标准库抓取受信任交易所页面，并限制响应体大小。"""

    _validate_official_url(exchange, url)
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "trading-day-calc/1.0 (+https://github.com/jiangzhuochi/trading_day_calc)",
        },
    )
    try:
        with _DIRECT_OPENER.open(request, timeout=timeout) as response:  # noqa: S310
            final_url = response.geturl()
            _validate_official_url(exchange, final_url)
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise CalendarUpdateError(f"{exchange} 页面超过 2 MiB 限制")
            charset = response.headers.get_content_charset() or "utf-8"
    except CalendarDataError:
        raise
    except OSError as exc:
        raise CalendarUpdateError(f"抓取 {exchange} 页面失败: {exc}") from exc

    try:
        return FetchResponse(url=final_url, text=body.decode(charset))
    except (LookupError, UnicodeDecodeError) as exc:
        raise CalendarUpdateError(f"无法按 {charset} 解码 {exchange} 页面") from exc


def _normalized_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    text = unicodedata.normalize("NFKC", " ".join(parser.parts))
    text = re.sub(r"(?<=\d)\s+(?=\d)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def discover_notice_url(exchange: Exchange, listing_html: str, year: int) -> str:
    """从交易所公告列表中发现指定年度的休市通知地址。"""

    parser = _AnchorExtractor()
    parser.feed(listing_html)
    expected = f"{year}年"
    candidates: list[str] = []
    for href, anchor_text in parser.anchors:
        normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", anchor_text))
        if expected in normalized and "休市安排" in normalized:
            url = urljoin(LISTING_URLS[exchange], href)
            _validate_official_url(exchange, url)
            candidates.append(url)
    if not candidates:
        raise CalendarCoverageError(f"{exchange} 尚未公布 {year} 年休市通知")
    if len(candidates) != 1:
        raise CalendarDataError(
            f"{exchange} 公告列表应唯一匹配 {year} 年休市通知，实际为 {len(candidates)} 条"
        )
    return candidates[0]


def _parse_date_token(token: str, *, default_year: int) -> date:
    match = _DATE_PATTERN.search(token)
    if match is None:
        raise CalendarDataError(f"无法解析公告日期: {token}")
    year_text = match.group("year")
    year = int(year_text) if year_text is not None else default_year
    try:
        return date(year, int(match.group("month")), int(match.group("day")))
    except ValueError as exc:
        raise CalendarDataError(f"公告包含无效日期: {token}") from exc


def parse_annual_notice(
    exchange: Exchange, year: int, source_url: str, html: str
) -> HolidaySchedule:
    """解析年度休市通知，并只保留目标年度的工作日休市日期。"""

    _validate_official_url(exchange, source_url)
    text = _normalized_text(html)
    compact_text = re.sub(r"\s+", "", text)
    if f"{year}年" not in compact_text or "休市安排" not in compact_text:
        raise CalendarDataError(f"{exchange} 页面不是 {year} 年休市安排")
    if "照常开市" not in compact_text:
        raise CalendarDataError(f"{exchange} 页面缺少完整的开市恢复信息")

    closed: set[date] = set()
    matched_ranges = 0
    for match in _CLOSED_RANGE_PATTERN.finditer(text):
        start = _parse_date_token(match.group("start"), default_year=year)
        end_text = match.group("end")
        end = (
            _parse_date_token(end_text, default_year=start.year)
            if end_text is not None
            else start
        )
        if end < start or (end - start).days > 20:
            raise CalendarDataError(
                f"{exchange} 公告包含异常休市区间: {start} 至 {end}"
            )
        matched_ranges += 1
        current = start
        while current <= end:
            if current.year == year and current.weekday() < 5:
                closed.add(current)
            current += timedelta(days=1)

    if matched_ranges < 5 or not 5 <= len(closed) <= 40:
        raise CalendarDataError(
            f"{exchange} {year} 年公告解析不完整: "
            f"{matched_ranges} 个区间、{len(closed)} 个工作日休市"
        )
    return HolidaySchedule(
        exchange=exchange,
        year=year,
        source_url=source_url,
        closed_weekdays=tuple(sorted(closed)),
    )


def fetch_annual_schedule(
    exchange: Exchange,
    year: int,
    *,
    fetcher: Fetcher = fetch_official_page,
    timeout: float = 10.0,
) -> HolidaySchedule:
    """发现并抓取一个交易所指定年度的完整休市安排。"""

    listing_url = LISTING_URLS[exchange]
    listing = fetcher(exchange, listing_url, timeout)
    notice_url = discover_notice_url(exchange, listing.text, year)
    notice = fetcher(exchange, notice_url, timeout)
    return parse_annual_notice(exchange, year, notice.url, notice.text)
