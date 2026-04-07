"""
run_server 启动 Baostock 同步时的日期区间计算。

- 开始下界：配置文件 BAOSTOCK_SYNC_CONFIG["sync_min_start_date"]
- 结束上界：A 股日历「最近交易日」（周末 + 内置法定节假日），见 china_stock_trading_day_checker
- 增量：若 stocktradetodayinfo 全局 MAX(trade_date) 小于上述最近交易日，则拉取 (max+1)～最近交易日
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from typing import Optional, Tuple

from PatternAnalysis.config import BAOSTOCK_SYNC_CONFIG
from PatternAnalysis.data_access import get_latest_trade_date
from PatternAnalysis.baostock_api.china_stock_trading_day_checker import (
    get_latest_trading_day_date,
)

logger = logging.getLogger(__name__)


def _parse_cfg_date(s: str) -> date:
    s = (s or "").strip()
    if not s:
        raise ValueError("sync_min_start_date 为空")
    if "-" in s:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    digits = "".join(c for c in s if c.isdigit())
    if len(digits) != 8:
        raise ValueError(f"无法解析日期: {s!r}")
    return datetime.strptime(digits, "%Y%m%d").date()


def _parse_env_date_yyyy_mm_dd(d: str) -> Optional[str]:
    s = (d or "").strip()
    if not s:
        return None
    if "-" in s:
        return s[:10]
    digits = "".join(c for c in s if c.isdigit())
    if len(digits) != 8:
        return None
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"


def resolve_startup_sync_date_range() -> Optional[Tuple[str, str]]:
    """
    计算启动同步用的 [start_date, end_date]（yyyy-mm-dd 字符串）。

    若环境变量同时设置了 BAOSTOCK_SYNC_START_DATE 与 BAOSTOCK_SYNC_END_DATE，则优先使用该区间（运维覆盖）。

    否则：
    - end = 日历「最近交易日」（china_stock_trading_day_checker.get_latest_trading_day_date）
    - 若表无数据：start = 配置 sync_min_start_date
    - 若表 max_date >= end：无需同步，返回 None
    - 否则：start = max(sync_min_start_date, max_date + 1 天)

    若 start > end 返回 None。
    """
    env_start = _parse_env_date_yyyy_mm_dd(os.getenv("BAOSTOCK_SYNC_START_DATE", ""))
    env_end = _parse_env_date_yyyy_mm_dd(os.getenv("BAOSTOCK_SYNC_END_DATE", ""))
    if env_start and env_end:
        logger.info("使用环境变量覆盖同步区间: %s ~ %s", env_start, env_end)
        return env_start, env_end
    if env_start or env_end:
        logger.warning(
            "仅设置了 BAOSTOCK_SYNC_START_DATE 或 BAOSTOCK_SYNC_END_DATE 之一，将忽略并改用配置+库内 MAX 逻辑"
        )

    min_start = _parse_cfg_date(str(BAOSTOCK_SYNC_CONFIG.get("sync_min_start_date", "2023-01-03")))
    end_d = get_latest_trading_day_date()
    end_s = end_d.strftime("%Y-%m-%d")

    raw_max = get_latest_trade_date()
    if raw_max is None:
        start_s = min_start.strftime("%Y-%m-%d")
        logger.info("stocktradetodayinfo 无数据，全量区间: %s ~ %s", start_s, end_s)
        return start_s, end_s

    max_d = raw_max
    if isinstance(max_d, datetime):
        max_d = max_d.date()

    if max_d >= end_d:
        logger.info(
            "库内 MAX(trade_date)=%s 已不早于日历最近交易日 %s，跳过启动增量同步",
            max_d,
            end_d,
        )
        return None

    inc_start = max_d + timedelta(days=1)
    actual_start = max(min_start, inc_start)
    start_s = actual_start.strftime("%Y-%m-%d")
    logger.info(
        "启动增量同步: MAX(trade_date)=%s < 日历最近交易日=%s → 区间 %s ~ %s",
        max_d,
        end_d,
        start_s,
        end_s,
    )
    if actual_start > end_d:
        logger.info("计算得 start > end，跳过")
        return None
    return start_s, end_s
