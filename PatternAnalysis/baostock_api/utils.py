"""
Baostock 代码与复权参数工具。
"""
from __future__ import annotations

from typing import Literal

from PatternAnalysis.akshare_api.utils import stock_code_from_ts_code, to_yyyymmdd

AdjustType = Literal["", "qfq", "hfq"]


def ts_code_to_baostock_code(ts_code: str) -> str:
    """
    将 ts_code 转为 Baostock 证券代码，如 sh.600000、sz.000001。
    """
    if not ts_code or not str(ts_code).strip():
        return ""
    s = str(ts_code).strip()
    code = stock_code_from_ts_code(s)
    if not code:
        return ""
    upper = s.upper()
    if upper.endswith(".SH") or upper.endswith(".SSE"):
        return f"sh.{code}"
    if upper.endswith(".BJ"):
        return f"bj.{code}"
    if upper.endswith(".SZ") or upper.endswith(".SZSE"):
        return f"sz.{code}"
    if code.startswith("6"):
        return f"sh.{code}"
    return f"sz.{code}"


def adjust_to_baostock_flag(adjust: AdjustType) -> str:
    """AkShare 风格 adjust -> Baostock adjustflag：1后复权 2前复权 3不复权。"""
    if adjust == "hfq":
        return "1"
    if adjust == "qfq":
        return "2"
    return "3"


def to_baostock_date(date_str: str) -> str:
    """yyyy-mm-dd 或 yyyymmdd -> yyyy-mm-dd。"""
    d8 = to_yyyymmdd(date_str)
    if not d8:
        return ""
    return f"{d8[:4]}-{d8[4:6]}-{d8[6:8]}"
