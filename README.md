# 交易日计算库

本库用来做中国市场交易日的处理和相关计算。

建这个库，一个目的是平常可能会用到这些，临时写起来比较杂乱，故而在这里集中归类存放，另一个目的是作为写 Python 包的练习。

## 安装

非常简陋，自认为发布在 PypI 上还不够格，因此发布在 TestPyPI 上作为自用。
如果您想尝试，运行下面的命令。

```shell
pip install -i https://test.pypi.org/simple/ trading-day-calc --upgrade 
```

卸载

```
pip uninstall trading-day-calc --yes  
```

## 功能

```python
import datetime

from trading_day_calc import TRADE_DATE, filter_d, filter_mon

'1990-12-19 到 2021-12-31 之间的股票交易日历数据库'
# print(TRADE_DATE)


'对日期列表进行过滤，在 2021 年 7 月的交易日'
td_on_july = filter_d(
    lambda d:
    datetime.date(2021, 7, 1) <= d <= datetime.date(2021, 7, 31),
    TRADE_DATE
)
# print(td_on_july)

'提取出在周一的交易日'
td_on_monday = filter_mon(TRADE_DATE)
# print(td_on_monday)


'''所有导出的变量
__all__ = [
    'TRADE_DATE',
    'filter_d',
    'filter_mon',
    'filter_tues',
    'filter_wed',
    'filter_thur',
    'filter_fri',
]'''

```

## 待办

- 给定开始和结束日，返回之间的所有交易日，前闭后闭
- 给定开始和结束日，返回之间的所有在假日前一天、二天的交易日，前闭后闭。
- 给定开始和结束日，返回之间的所有在假日后一天、二天、三天的交易日，前闭后闭。例如假日是 1，2，3，6，7，13，14，20，21。开始日 2，结束日 20，则假日后一天的交易日返回 4，8，15；假日后二天的交易日返回5，9，16；假日后三天的交易日只返回 10，17。
- ...

## 原则

- 尽量使用标准库
- 使用类型标注

## 依赖

包依赖详见 `pyproject.toml`，交易日历数据来源详见 `script\get_source_data.py`。

## 注意

众所周知，经济类、金融类学生是野生编程的高发人群，他们通常使用 Python、R、MATLAB 等语言，尤其善于使用单 `.ipynb` 文件。他们的要求是能用就行，且用后即抛。他们发出的最多的抱怨不是代码不够优雅和漂亮，而是运行太慢。不少人工程思维较差，养成了代码混乱、无组织、无条理的坏习惯，本人也不例外。

因此您在浏览代码时，可能会产生一些不适症状，包括但不限于血压升高、恶心、烦躁等生理或心理的反应，还请您谅解，如果能发个 issue 提出批评就更好了。