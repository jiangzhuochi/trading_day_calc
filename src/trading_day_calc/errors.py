"""交易日历的公共异常类型。"""


class TradingCalendarError(Exception):
    """交易日历的基础异常。"""


class CalendarDataError(TradingCalendarError):
    """日历数据格式错误或未通过完整性校验。"""


class CalendarCoverageError(TradingCalendarError):
    """请求日期超出当前可确认的日历覆盖范围。"""


class CalendarUpdateError(TradingCalendarError):
    """联网更新日历失败。"""
