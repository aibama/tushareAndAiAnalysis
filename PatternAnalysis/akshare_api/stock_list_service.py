"""
从 stockinfobase 组装带股票代码字段的股票列表（应用层薄封装）。
"""
from typing import Any, Dict, List, Optional

from .db_operations import get_all_stockinfobase, get_stockinfobase_by_ts_code
from .utils import stock_code_from_ts_code


def _row_with_stock_code(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    ts = out.get("ts_code") or ""
    out["stock_code"] = stock_code_from_ts_code(str(ts))
    return out


def list_stockinfobase_with_stock_code() -> List[Dict[str, Any]]:
    """
    读取 stockinfobase 全表，为每条记录增加 stock_code 字段。

    Returns:
        ``[{"ts_code","name","factory_code","stock_code"}, ...]``
    """
    rows = get_all_stockinfobase()
    return [_row_with_stock_code(r) for r in rows]


def get_stockinfobase_row_with_stock_code(ts_code: str) -> Optional[Dict[str, Any]]:
    """单条查询并附带 stock_code；不存在则返回 None。"""
    row = get_stockinfobase_by_ts_code(ts_code)
    if not row:
        return None
    return _row_with_stock_code(row)
