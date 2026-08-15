"""用户日历缓存的选择、校验与原子写入。"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from ._data import (
    CalendarData,
    calendar_data_to_json,
    load_bundled_data,
    load_calendar_file,
)
from .errors import CalendarDataError, CalendarUpdateError

LOGGER = logging.getLogger(__name__)
CACHE_FILE_NAME = "calendar-v1.json"


def default_cache_path() -> Path:
    """返回当前平台的默认用户缓存文件。"""

    local_app_data = os.environ.get("LOCALAPPDATA")
    if os.name == "nt" and local_app_data:
        root = Path(local_app_data)
    else:
        xdg_cache = os.environ.get("XDG_CACHE_HOME")
        root = Path(xdg_cache) if xdg_cache else Path.home() / ".cache"
    return root / "trading_day_calc" / CACHE_FILE_NAME


def _is_compatible_cache(candidate: CalendarData, bundled: CalendarData) -> bool:
    if candidate.coverage_start != bundled.coverage_start:
        return False
    if candidate.coverage_end < bundled.coverage_end:
        return False

    # 已发布年份不可被用户缓存改写；快照生成当年仍允许官方后续公告纠正。
    protected_year = bundled.generated_at.year
    bundled_history = tuple(
        session for session in bundled.sessions if session.year < protected_year
    )
    candidate_history = tuple(
        session for session in candidate.sessions if session.year < protected_year
    )
    return candidate_history == bundled_history


def load_best_available(cache_path: Path) -> CalendarData:
    """优先加载有效且不早于内置快照的用户缓存。"""

    bundled = load_bundled_data()
    if not cache_path.exists():
        return bundled
    try:
        cached = load_calendar_file(cache_path)
    except CalendarDataError as exc:
        LOGGER.warning("忽略损坏的交易日历缓存 %s: %s", cache_path, exc)
        return bundled
    if not _is_compatible_cache(cached, bundled):
        LOGGER.warning("忽略过期或与内置历史不一致的交易日历缓存 %s", cache_path)
        return bundled
    return cached


def write_cache_atomically(cache_path: Path, data: CalendarData) -> None:
    """校验序列化结果后，在同目录原子替换缓存。"""

    text = calendar_data_to_json(data)
    temporary_path: Path | None = None
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{cache_path.name}.",
            suffix=".tmp",
            dir=cache_path.parent,
            delete=False,
        ) as temporary:
            temporary.write(text)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        load_calendar_file(temporary_path)
        os.replace(temporary_path, cache_path)
        temporary_path = None
    except (OSError, CalendarDataError) as exc:
        raise CalendarUpdateError(f"无法安全写入日历缓存 {cache_path}: {exc}") from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                LOGGER.warning("无法清理临时日历文件 %s", temporary_path)
