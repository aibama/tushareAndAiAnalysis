"""
AkShare 应用层：在包内封装常用接口，通过 Python 方法调用；部分能力同时注册为 FastAPI 路由。

当前提供：
- A 股历史行情 stock_zh_a_hist（日线/周线/月线，不复权/前复权/后复权）
- 从 stockinfobase 读取股票并解析 stock_code（6 位数字；Tsanghi HTTP 中同义字段常称 ticker）
"""

from .hist_service import (
    StockZhAHistService,
    get_stock_zh_a_hist,
    get_stock_zh_a_hist_dataframe,
)
from .stock_list_service import (
    get_stockinfobase_row_with_stock_code,
    list_stockinfobase_with_stock_code,
)
from .sync_tradetoday_service import sync_tradetoday_all_from_akshare
from .utils import normalize_a_share_symbol, stock_code_from_ts_code, to_yyyymmdd

__all__ = [
    "StockZhAHistService",
    "get_stock_zh_a_hist",
    "get_stock_zh_a_hist_dataframe",
    "list_stockinfobase_with_stock_code",
    "get_stockinfobase_row_with_stock_code",
    "sync_tradetoday_all_from_akshare",
    "normalize_a_share_symbol",
    "stock_code_from_ts_code",
    "to_yyyymmdd",
]
