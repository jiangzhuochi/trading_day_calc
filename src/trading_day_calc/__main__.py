"""``python -m trading_day_calc`` 命令入口。"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .calendar import CalendarMetadata, TradingCalendar
from .errors import TradingCalendarError


def _metadata_payload(metadata: CalendarMetadata) -> dict[str, object]:
    return {
        "coverage_start": metadata.coverage_start.isoformat(),
        "coverage_end": metadata.coverage_end.isoformat(),
        "generated_at": metadata.generated_at.isoformat(),
        "session_count": metadata.session_count,
        "source_urls": list(metadata.source_urls),
        "cache_path": str(metadata.cache_path),
        "auto_refresh": metadata.auto_refresh,
    }


def _print_metadata(metadata: CalendarMetadata, *, as_json: bool) -> None:
    payload = _metadata_payload(metadata)
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(f"覆盖范围：{payload['coverage_start']} 至 {payload['coverage_end']}")
    print(f"交易日数：{payload['session_count']}")
    print(f"数据生成日：{payload['generated_at']}")
    print(f"缓存文件：{payload['cache_path']}")
    print(f"自动刷新：{'开启' if metadata.auto_refresh else '关闭'}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="中国 A 股交易日历")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="查看本地日历状态")
    status.add_argument("--cache", type=Path, help="指定缓存文件")
    status.add_argument("--json", action="store_true", help="输出 JSON")

    refresh = subparsers.add_parser("refresh", help="联网刷新年度日历")
    refresh.add_argument("--cache", type=Path, help="指定缓存文件")
    refresh.add_argument("--through-year", type=int, help="刷新至指定年份")
    refresh.add_argument("--force", action="store_true", help="强制重查目标年份")
    refresh.add_argument("--json", action="store_true", help="输出 JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """执行命令并返回进程退出码。"""

    args = _build_parser().parse_args(argv)
    try:
        if args.command == "status":
            calendar = TradingCalendar(args.cache, auto_refresh=False)
            _print_metadata(calendar.metadata, as_json=args.json)
            return 0
        calendar = TradingCalendar(args.cache)
        metadata = calendar.refresh(
            through_year=args.through_year,
            force=args.force,
        )
        _print_metadata(metadata, as_json=args.json)
        return 0
    except TradingCalendarError as exc:
        print(f"交易日历操作失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
