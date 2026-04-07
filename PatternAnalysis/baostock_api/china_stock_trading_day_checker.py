"""
国内交易所（A 股）交易日判断工具（与 Java ChinaStockTradingDayChecker 对齐）。

规则：周六周日休市 + 法定节假日休市。

当前内置 2026 年法定节假日集合；其它年份仅按周末判断（与提供的 Java 静态实现一致）。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional, Set

# yyyy-MM-dd，与 Java HOLIDAYS 一致
HOLIDAYS_2026: Set[str] = {
    "2026-01-01",
    "2026-01-02",
    "2026-01-03",
    "2026-02-15",
    "2026-02-16",
    "2026-02-17",
    "2026-02-18",
    "2026-02-19",
    "2026-02-20",
    "2026-02-21",
    "2026-02-22",
    "2026-02-23",
    "2026-04-04",
    "2026-04-05",
    "2026-04-06",
    "2026-05-01",
    "2026-05-02",
    "2026-05-03",
    "2026-05-04",
    "2026-05-05",
    "2026-06-19",
    "2026-06-20",
    "2026-06-21",
    "2026-09-25",
    "2026-09-26",
    "2026-09-27",
    "2026-10-01",
    "2026-10-02",
    "2026-10-03",
    "2026-10-04",
    "2026-10-05",
    "2026-10-06",
    "2026-10-07",
}


def _date_str(d: date) -> str:
    return d.isoformat()


def is_trading_day(d: date) -> bool:
    """指定日期是否为交易日。"""
    if d.weekday() >= 5:
        return False
    return _date_str(d) not in HOLIDAYS_2026


def is_trading_day_str(date_str: str) -> bool:
    """日期字符串 yyyy-MM-dd 是否为交易日；解析失败返回 False。"""
    try:
        return is_trading_day(datetime.strptime(date_str[:10], "%Y-%m-%d").date())
    except (ValueError, TypeError):
        return False


def get_previous_trading_day(d: date) -> date:
    """从指定日期起向前追溯的最近一个交易日（含当日若当日为交易日）。"""
    cur = d
    while not is_trading_day(cur):
        cur -= timedelta(days=1)
    return cur


def get_previous_trading_day_str(date_str: str) -> date:
    """从日期字符串起向前追溯最近交易日；解析失败时返回 date.today()（与 Java 一致）。"""
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        return get_previous_trading_day(d)
    except (ValueError, TypeError):
        return date.today()


def get_next_trading_day(d: date) -> date:
    """从下一天起向后追溯的下一个交易日。"""
    cur = d + timedelta(days=1)
    while not is_trading_day(cur):
        cur += timedelta(days=1)
    return cur


def get_today_date_str() -> str:
    return _date_str(date.today())


def get_today() -> date:
    return date.today()


def get_latest_trading_day_date_str() -> str:
    """
    最近一个交易日：若今天为交易日则返回今天，否则返回上一个交易日（yyyy-MM-dd）。
    """
    today = get_today()
    if is_trading_day(today):
        return _date_str(today)
    return _date_str(get_previous_trading_day(today))


def get_latest_trading_day_date() -> date:
    """同 get_latest_trading_day_date_str，返回 date。"""
    return datetime.strptime(get_latest_trading_day_date_str(), "%Y-%m-%d").date()


def need_to_update_data(level2_last_update_date: Optional[str]) -> bool:
    """
    根据 Level2 最后更新日期判断是否需要更新数据。
    等于最近一个交易日则无需更新；为空、解析失败或其它情况需要更新。
    """
    if level2_last_update_date is None or not str(level2_last_update_date).strip():
        return True
    latest = get_latest_trading_day_date_str()
    try:
        last_update = datetime.strptime(str(level2_last_update_date).strip()[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return True
    if _date_str(last_update) == latest:
        return False
    return True
