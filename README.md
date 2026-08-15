# trading-day-calc

`trading-day-calc` 是一个轻量、零运行时依赖的中国 A 股交易日历库。它提供沪深交易所统一交易日查询、月度边界、休市区间和官方日历刷新能力。

当前内置快照覆盖 **1990-12-19 至 2026-12-31**，包含 **8,797** 个交易日。导入包和读取覆盖范围内的数据不会访问网络。

## 安装

需要 Python 3.10 或更高版本。项目尚未声明已发布到 PyPI，建议从源码安装：

```shell
python -m pip install .
```

## 快速开始

```python
from datetime import date

from trading_day_calc import TradingCalendar

calendar = TradingCalendar()

calendar.is_trading_day(date(2026, 1, 5))
calendar.trading_days(date(2026, 1, 1), date(2026, 1, 10))
calendar.next_trading_day(date(2026, 1, 1))
calendar.previous_trading_day(date(2026, 1, 5))

calendar.month_starts(date(2026, 1, 1), date(2026, 3, 31))
calendar.month_ends(date(2026, 1, 1), date(2026, 3, 31))

for period in calendar.closed_periods(
    date(2026, 1, 1),
    date(2026, 3, 31),
):
    print(period.start, period.end, period.kind)
```

查询区间的起止日期均包含在内。所有日期参数只接受 `datetime.date`，不接受 `datetime.datetime`；所有日期序列均以不可变 `tuple` 返回。

## API 语义

| 接口 | 语义 |
| --- | --- |
| `sessions` | 当前覆盖范围内的全部交易日 |
| `is_trading_day(day)` | 判断指定日期是否为交易日 |
| `trading_days(start, end)` | 返回闭区间内的交易日 |
| `next_trading_day(day, steps=1)` | 返回严格晚于 `day` 的第 N 个交易日 |
| `previous_trading_day(day, steps=1)` | 返回严格早于 `day` 的第 N 个交易日 |
| `month_starts(start, end)` | 返回区间内各自然月真正的首个交易日 |
| `month_ends(start, end)` | 返回区间内各自然月真正的末个交易日 |
| `closed_periods(start, end)` | 返回与区间相交的交易所休市段；默认排除普通周末 |
| `refresh(through_year=None, force=False)` | 从沪深交易所官网核验并更新日历 |

`ClosedPeriod.kind` 有三种取值：

- `weekend`：只包含周六、周日；
- `exchange_holiday`：只包含工作日休市；
- `mixed`：同时包含周末和工作日休市。

设置 `include_weekends=True` 可让 `closed_periods` 返回全部非交易区间。返回的是完整休市段，可能向查询边界外延伸，以保留准确的前后交易日信息。

## 数据与更新

内置快照启动快、可复现。2022—2026 年数据记录了上海证券交易所和深圳证券交易所的年度休市公告 URL；更早数据沿用原项目历史快照。具体结构、校验规则和维护流程见 [数据契约](docs/data-contract.md)。

查询超出当前末日时，实例默认尝试按年联网刷新：

```python
calendar = TradingCalendar(auto_refresh=True, timeout=10)
calendar.refresh(through_year=2027)
```

更新遵循“失败时保留旧状态”的原则：沪深两份结果必须完全一致，下载、解析、交叉核验和序列化校验全部成功后，才会原子替换用户缓存。网络或数据异常不会把不完整结果当成真实市场状态。

默认缓存位置：

- Windows：`%LOCALAPPDATA%\trading_day_calc\calendar-v1.json`
- Linux/macOS：`$XDG_CACHE_HOME/trading_day_calc/calendar-v1.json`，未设置时使用 `~/.cache`

也可以用 `TradingCalendar(cache_path=...)` 指定路径，或设置 `auto_refresh=False` 禁止隐式联网。

## 命令行

```shell
python -m trading_day_calc status
python -m trading_day_calc status --json
python -m trading_day_calc refresh --through-year 2027
python -m trading_day_calc refresh --through-year 2026 --force --json
```

`status` 只读取本地数据。`refresh` 联网更新，失败时退出码为 1，并把中文错误写到标准错误。

## 异常

所有库异常都继承 `TradingCalendarError`：

| 异常 | 含义 |
| --- | --- |
| `CalendarCoverageError` | 请求超出可确认范围，或范围内没有所需前后交易日 |
| `CalendarDataError` | 日历文件格式错误或完整性校验失败 |
| `CalendarUpdateError` | 下载、解析、沪深交叉核验或缓存写入失败 |

参数类型错误使用 `TypeError`，范围和数值错误使用 `ValueError`。

## 从 0.2.x 迁移

1.0 精简了公共接口，不保留旧名称：

| 旧接口 | 1.0 写法 |
| --- | --- |
| `TRADE_DATE` | `calendar.sessions` |
| `filter_between(start, end)` | `calendar.trading_days(start, end)` |
| `get_first_day_per_month(...)` | `calendar.month_starts(start, end)` |
| `get_last_day_per_month(...)` | `calendar.month_ends(start, end)` |
| `get_1d_before_holiday(...)` / `get_1d_after_holiday(...)` | 遍历 `calendar.closed_periods(...)`，读取 `previous_trading_day` / `next_trading_day` |
| `filter_mon` 等星期过滤器 | 对 `calendar.trading_days(...)` 使用列表推导式和 `date.weekday()` |

## 性能

基准环境为 Windows、Python 3.11.9。当前实现预计算集合和边界索引，再使用哈希查找或二分查找：

| 查询 | 当前中位数 | 0.2.x 参考值 | 约提升 |
| --- | ---: | ---: | ---: |
| 单日判断 | 0.42 μs | — | — |
| 区间交易日 | 1.2 μs | 658 μs | 548 倍 |
| 月首交易日 | 1.1 μs | 20.2 ms | 18,000 倍 |
| 休市区间 | 1.1 μs | 2.24 ms | 2,000 倍* |

\* 新版休市接口返回结构化完整区间，和旧版前后日期函数并非完全相同语义，数字仅用于量级参考。性能会随硬件和 Python 版本变化。

## 开发与验证

```shell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\ruff format .
.venv\Scripts\pyright
.venv\Scripts\ruff check .
.venv\Scripts\python -m pytest -m "not benchmark" --cov=trading_day_calc
.venv\Scripts\python -m pytest -m benchmark --benchmark-only
.venv\Scripts\python -m build --no-isolation
```

项目要求分支覆盖率不低于 95%。联网测试带有 `network` 标记，默认测试套件使用固定的官方公告样本，不依赖交易所网站的实时可用性。
