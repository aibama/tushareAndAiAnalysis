"""
Z-Score 热度图服务

提供中证1000指数成分股的Z-Score计算和API接口
"""

from .config import ZSCORE_CONFIG, ZSCORE_COLORS, get_zscore_color, get_indicator_field
from .data_service import (
    get_zz1000_stocks,
    get_stock_daily,
    get_sw_industries,
    get_stock_industry_relation,
    get_industry_stocks,
    get_trade_dates,
    get_latest_trade_date,
    get_stock_mv
)
from .zscore_service import (
    get_industry_daily_zscore,
    get_industry_stocks_zscore,
    get_stock_timeseries_zscore,
    get_industry_timeseries_zscore,
    get_index_timeseries_zscore
)
from .market_cap_service import (
    get_cached_market_cap,
    set_cached_market_cap,
    calculate_stock_market_cap,
    calculate_stocks_market_cap_by_codes,
    preheat_market_cap_cache
)
from .api_routes import zscore_bp, register_routes

__all__ = [
    "ZSCORE_CONFIG",
    "ZSCORE_COLORS",
    "get_zscore_color",
    "get_indicator_field",
    "zscore_bp",
    "register_routes",
    "get_zz1000_stocks",
    "get_stock_daily",
    "get_sw_industries",
    "get_stock_industry_relation",
    "get_industry_stocks",
    "get_trade_dates",
    "get_latest_trade_date",
    "get_stock_mv",
    "get_industry_daily_zscore",
    "get_industry_stocks_zscore",
    "get_stock_timeseries_zscore",
    "get_industry_timeseries_zscore",
    "get_index_timeseries_zscore",
    "get_cached_market_cap",
    "set_cached_market_cap",
    "calculate_stock_market_cap",
    "calculate_stocks_market_cap_by_codes",
    "preheat_market_cap_cache"
]
