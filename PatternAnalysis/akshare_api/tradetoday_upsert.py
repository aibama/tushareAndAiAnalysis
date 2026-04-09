"""
将日线数据 upsert 到 MySQL stocktradetodayinfo（与 stock_trade_sync_service 字段约定一致）。

依赖表上存在可用于 ON DUPLICATE KEY UPDATE 的唯一约束（通常为 ts_code + trade_date）。
"""
from __future__ import annotations

import logging
import random
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from .db_operations import get_connection
from .utils import to_yyyymmdd

logger = logging.getLogger(__name__)

UPSERT_SQL = """
INSERT INTO stocktradetodayinfo
(id, ts_code, amount, echange, close, high, low, open, pct_chg, pre_close, trade_date, vol, trade_date_tmp)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    amount = VALUES(amount),
    echange = VALUES(echange),
    close = VALUES(close),
    high = VALUES(high),
    low = VALUES(low),
    open = VALUES(open),
    pct_chg = VALUES(pct_chg),
    pre_close = VALUES(pre_close),
    trade_date = VALUES(trade_date),
    vol = VALUES(vol),
    trade_date_tmp = VALUES(trade_date_tmp)
"""


def _gen_row_id() -> float:
    """生成唯一且可写入 MySQL decimal(16,2) 的 id（整数部分最多 14 位）。"""
    ms = int(time.time() * 1000)
    base = ms % 1_000_000_000_000  # 取低 12 位毫秒特征，避免与 random 拼接后超过 14 位整数
    suffix = random.randint(0, 99)
    return float(base * 100 + suffix)


def _parse_trade_date(d: Any) -> Optional[datetime]:
    if d is None:
        return None
    if isinstance(d, datetime):
        return datetime.combine(d.date(), datetime.min.time())
    if isinstance(d, date):
        return datetime.combine(d, datetime.min.time())
    s = str(d).strip().replace("/", "-")[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        logger.warning("无法解析交易日期: %r", d)
        return None


def _f(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def has_tradetoday_data_in_range(ts_code: str, start_date: str, end_date: str) -> bool:
    """
    判断指定股票在日期区间是否已落表。

    说明：
    - 只要该区间内已有任意记录，即判定为"已同步过"，用于避免同参数重复执行。
    """
    sd = to_yyyymmdd(start_date)
    ed = to_yyyymmdd(end_date)
    if not ts_code or not sd or not ed:
        logger.warning(f"幂等检查参数无效: ts_code={ts_code}, start_date={start_date}, end_date={end_date}")
        return False
    if sd > ed:
        sd, ed = ed, sd
        logger.debug(f"日期范围颠倒，已自动调整: start={sd}, end={ed}")

    sql = """
    SELECT 1
    FROM stocktradetodayinfo
    WHERE ts_code = %s
      AND trade_date >= %s
      AND trade_date < %s
    LIMIT 1
    """
    sd_dt = datetime.strptime(sd, "%Y%m%d")
    ed_dt_next = datetime.strptime(ed, "%Y%m%d") + timedelta(days=1)
    logger.debug(f"幂等检查: ts_code={ts_code}, trade_date >= {sd_dt}, trade_date < {ed_dt_next}")
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (ts_code, sd_dt, ed_dt_next))
            result = cursor.fetchone() is not None
            if result:
                logger.info(f"幂等检查命中: ts_code={ts_code} 在 {sd}~{ed} 区间已有数据，跳过 API 调用")
            return result


def has_tradetoday_data_any(ts_code: str) -> bool:
    """
    判断指定股票是否有任何历史数据（任意日期）。

    用于：当 API 返回空数据时，判断该股票是否曾经有数据。
    - 如果有数据，说明是停牌等正常情况，返回 "skipped"
    - 如果无数据，说明是真正的异常，返回 "error"
    """
    if not ts_code:
        return False
    sql = "SELECT 1 FROM stocktradetodayinfo WHERE ts_code = %s LIMIT 1"
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (ts_code,))
            return cursor.fetchone() is not None


def ak_hist_record_to_trade_row(ts_code: str, rec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    将 hist_service 返回的英文键记录转为 stocktradetodayinfo 一行（不含 id）。

    AkShare: volume 手, amount 元, pct_change 涨跌幅%, turnover_pct 换手率%,
    change_amount 涨跌额（用于推算 pre_close）。
    """
    trade_dt = _parse_trade_date(rec.get("date"))
    if not trade_dt:
        return None

    close = _f(rec.get("close"))
    open_ = _f(rec.get("open"))
    high = _f(rec.get("high"))
    low = _f(rec.get("low"))
    vol = _f(rec.get("volume"))
    amount = _f(rec.get("amount"))
    pct_chg = _f(rec.get("pct_change"))
    chg_amt = _f(rec.get("change_amount"))
    turnover = _f(rec.get("turnover_pct"))

    pre_close: Optional[float] = None
    if close is not None and chg_amt is not None:
        pre_close = close - chg_amt
    elif close is not None and pct_chg is not None and abs(pct_chg + 100.0) > 1e-6:
        pre_close = close / (1.0 + pct_chg / 100.0)

    return {
        "ts_code": ts_code,
        "trade_date": trade_dt,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "pre_close": pre_close,
        "pct_chg": pct_chg,
        "echange": turnover,
        "vol": vol,
        "amount": amount,
    }


def upsert_tradetoday_rows(ts_code: str, hist_records: List[Dict[str, Any]]) -> int:
    """把单只股票的多日行情写入 stocktradetodayinfo，返回成功写入/更新的条数。"""
    if not hist_records:
        return 0

    rows: List[Dict[str, Any]] = []
    for rec in hist_records:
        row = ak_hist_record_to_trade_row(ts_code, rec)
        if row:
            rows.append(row)

    if not rows:
        return 0

    saved = 0
    with get_connection() as conn:
        with conn.cursor() as cursor:
            for row in rows:
                tid = _gen_row_id()
                td = row["trade_date"]
                cursor.execute(
                    UPSERT_SQL,
                    (
                        tid,
                        row["ts_code"],
                        row["amount"],
                        row["echange"],
                        row["close"],
                        row["high"],
                        row["low"],
                        row["open"],
                        row["pct_chg"],
                        row["pre_close"],
                        td,
                        row["vol"],
                        td,
                    ),
                )
                saved += 1
        conn.commit()
    return saved
