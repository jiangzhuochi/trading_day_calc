import json
from pathlib import Path
from typing import cast

import pytest

from trading_day_calc.__main__ import main


def test_status_command_prints_human_readable_metadata(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cache_path = tmp_path / "calendar.json"

    exit_code = main(["status", "--cache", str(cache_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "覆盖范围：1990-12-19 至 2026-12-31" in captured.out
    assert "交易日数：8797" in captured.out
    assert "自动刷新：关闭" in captured.out
    assert captured.err == ""


def test_status_command_can_print_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["status", "--cache", str(tmp_path / "calendar.json"), "--json"])

    captured = capsys.readouterr()
    decoded = json.loads(captured.out)
    assert isinstance(decoded, dict)
    payload = cast(dict[str, object], decoded)
    assert exit_code == 0
    assert payload["coverage_end"] == "2026-12-31"
    assert payload["session_count"] == 8_797
    assert payload["auto_refresh"] is False


def test_refresh_with_covered_year_does_not_require_network(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(
        [
            "refresh",
            "--cache",
            str(tmp_path / "calendar.json"),
            "--through-year",
            "2026",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "覆盖范围：1990-12-19 至 2026-12-31" in captured.out
    assert captured.err == ""


def test_cli_reports_calendar_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(
        [
            "refresh",
            "--cache",
            str(tmp_path / "calendar.json"),
            "--through-year",
            "2021",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "交易日历操作失败" in captured.err
