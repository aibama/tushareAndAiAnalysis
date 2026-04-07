"""
Baostock 应用层：日线同步至 stocktradetodayinfo，接口语义对齐 akshare_api。
"""

from .hist_service import BaostockHistService, get_baostock_daily_records
from .sync_tradetoday_service import (
    sync_tradetoday_all_from_baostock,
    sync_tradetoday_ts_codes_from_baostock,
    sync_tradetoday_one_from_baostock,
)
from .utils import adjust_to_baostock_flag, ts_code_to_baostock_code

__all__ = [
    "BaostockHistService",
    "get_baostock_daily_records",
    "sync_tradetoday_all_from_baostock",
    "sync_tradetoday_ts_codes_from_baostock",
    "sync_tradetoday_one_from_baostock",
    "adjust_to_baostock_flag",
    "ts_code_to_baostock_code",
]
