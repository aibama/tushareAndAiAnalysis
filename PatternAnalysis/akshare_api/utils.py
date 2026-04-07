"""
AkShare 应用层通用工具：从 ts_code 提取股票代码（6 位数字）、日期格式规范化。

说明：Tsanghi 等 HTTP 接口的请求字段名常写作 ``ticker``，与本包返回的
``stock_code`` 在含义上同为「去掉市场后缀后的纯数字代码」，仅命名习惯不同。
"""
import re
from typing import Optional


def stock_code_from_ts_code(ts_code: Optional[str]) -> str:
    """
    从 ts_code 提取 6 位数字股票代码（供 AkShare ``symbol`` 等使用）。

    规则：
    - 000001.SZ / 600519.SH → 去掉 .SZ/.SH，取点前段
    - 1.600519 → 600519（点前为 1 时取点右段）
    - 0.000001 → 000001（点前为 0 时取点右段）
    - 其余以连续数字为准，不足 6 位左侧补 0，超过 6 位取末 6 位
    """
    if not ts_code or not str(ts_code).strip():
        return ""
    s = str(ts_code).strip()
    code_part = s
    if "." in s:
        left, right = s.split(".", 1)
        left_st = left.strip()
        right_st = right.strip()
        ru = right_st.upper()
        if ru in ("SZ", "SH"):
            code_part = left_st
        elif left_st in ("0", "1") and right_st.isdigit():
            code_part = right_st
        else:
            code_part = left_st
    if code_part.startswith("1.") or code_part.startswith("0."):
        code_part = code_part[2:]
    digits_only = re.sub(r"\D", "", code_part)
    if digits_only:
        core = digits_only[-6:] if len(digits_only) >= 6 else digits_only
        return core.zfill(6)
    if code_part.isdigit():
        return code_part.zfill(6)
    return code_part


def normalize_a_share_symbol(symbol: str) -> str:
    """
    将常见 ts 风格代码转为 AkShare A 股 6 位代码。
    与 ``stock_code_from_ts_code`` 行为一致。
    """
    return stock_code_from_ts_code(symbol)


def to_yyyymmdd(date_str: Optional[str]) -> Optional[str]:
    """
    统一为 AkShare stock_zh_a_hist 所需的 yyyymmdd 字符串。

    支持: 20170301、2017-03-01、2017/03/01
    """
    if date_str is None:
        return None
    s = date_str.strip()
    if not s:
        return None
    digits = re.sub(r"\D", "", s)
    if len(digits) == 8:
        return digits
    return None
