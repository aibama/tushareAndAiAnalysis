"""
智途API股票数据爬虫模块 + Tushare ETF数据爬虫模块

股票数据：
使用requests库调用智途API，获取股票数据并存入MySQL数据库。
配置在 PatternAnalysis/config.py 中的 ZHITU_API_CONFIG

ETF数据：
使用Tushare接口获取ETF相关数据（日线行情、份额规模、复权因子）。
"""

from .api_client import ZhituApiClient, get_stock_list, get_stock_info
from .db_operations import (
    save_stock_list_to_db,
    get_all_ts_codes,
    save_stock_info_to_db,
    batch_save_stock_info
)
from .crawler import crawl_stock_list, crawl_stock_details, main
from .etf_crawler import (
    crawl_etf_daily,
    crawl_etf_share_size,
    crawl_fund_adj,
    crawl_all_etf_data,
    crawl_multiple_etfs
)

__version__ = "1.1.0"
__all__ = [
    # 智途API
    "ZhituApiClient",
    "get_stock_list",
    "get_stock_info",
    "save_stock_list_to_db",
    "get_all_ts_codes",
    "save_stock_info_to_db",
    "batch_save_stock_info",
    "crawl_stock_list",
    "crawl_stock_details",
    "main",
    # Tushare ETF
    "crawl_etf_daily",
    "crawl_etf_share_size",
    "crawl_fund_adj",
    "crawl_all_etf_data",
    "crawl_multiple_etfs",
]
