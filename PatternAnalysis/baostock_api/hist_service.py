"""
Baostock 沪深 A 股日 K，输出与 akshare hist_service 一致的英文键 dict 列表（供 tradetoday_upsert 复用）。
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from .utils import AdjustType, adjust_to_baostock_flag, to_baostock_date, ts_code_to_baostock_code

logger = logging.getLogger(__name__)

_BS_QUERY_LOCK = threading.Lock()

_FIELDS = "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST"


def _f(x: Any) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip()
    if not s or s in (".", "nan", "None"):
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _row_to_hist_rec(row: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """单条 Baostock 行 -> ak_hist_record_to_trade_row 可消费的 dict。"""
    ts_status = (row.get("tradestatus") or "").strip()
    if ts_status and ts_status != "1":
        return None

    trade_date = (row.get("date") or "").strip()
    if not trade_date:
        return None

    close = _f(row.get("close"))
    preclose = _f(row.get("preclose"))
    vol_shares = _f(row.get("volume"))
    vol_lots = (vol_shares / 100.0) if vol_shares is not None else None
    chg_amt: Optional[float] = None
    if close is not None and preclose is not None:
        chg_amt = close - preclose

    return {
        "date": trade_date,
        "open": _f(row.get("open")),
        "high": _f(row.get("high")),
        "low": _f(row.get("low")),
        "close": close,
        "volume": vol_lots,
        "amount": _f(row.get("amount")),
        "pct_change": _f(row.get("pctChg")),
        "change_amount": chg_amt,
        "turnover_pct": _f(row.get("turn")),
    }


class BaostockHistService:
    """封装 bs.query_history_k_data_plus（日线）。"""

    def query_daily_records(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
        adjust: AdjustType = "",
    ) -> List[Dict[str, Any]]:
        import baostock as bs

        bs_code = ts_code_to_baostock_code(ts_code)
        if not bs_code:
            logger.warning("无法解析 Baostock 代码: %r", ts_code)
            return []

        sd = to_baostock_date(start_date)
        ed = to_baostock_date(end_date)
        if not sd or not ed:
            logger.warning("日期无效: start=%r end=%r", start_date, end_date)
            return []
        if sd > ed:
            sd, ed = ed, sd

        flag = adjust_to_baostock_flag(adjust)
        out: List[Dict[str, Any]] = []

        with _BS_QUERY_LOCK:
            rs = bs.query_history_k_data_plus(
                bs_code,
                _FIELDS,
                start_date=sd,
                end_date=ed,
                frequency="d",
                adjustflag=flag,
            )

            if rs.error_code != "0":
                logger.error(
                    "Baostock query 失败: code=%s err=%s msg=%s",
                    bs_code,
                    rs.error_code,
                    rs.error_msg,
                )
                return []

            fields = list(rs.fields)
            while rs.error_code == "0" and rs.next():
                vals = rs.get_row_data()
                row = dict(zip(fields, vals))
                rec = _row_to_hist_rec(row)
                if rec:
                    out.append(rec)

        return out


def get_baostock_daily_records(
    ts_code: str,
    start_date: str,
    end_date: str,
    adjust: AdjustType = "",
) -> List[Dict[str, Any]]:
    return BaostockHistService().query_daily_records(ts_code, start_date, end_date, adjust)
