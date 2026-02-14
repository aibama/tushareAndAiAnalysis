"""
股票形态分析系统
提供K线形态分类、技术指标计算、涨跌幅分析等功能
"""

__version__ = "1.0.0"
__author__ = "EasyMoneyCrawling"

from .config import DB_CONFIG, MODEL_CONFIG, PERIOD_CONFIG, TECHNICAL_INDICATORS, PATTERN_CONFIG, API_CONFIG
from .data_access import StockDataAccess, get_latest_trade_date, get_all_ts_codes
from .periods import PeriodCalculator, get_period_windows
from .returns import ReturnCalculator, calc_period_return
from .pattern_model import PatternType, PATTERN_NAME_MAP, PatternClassifier
from .feature_engineering import FeatureEngineer
from .api_service import app, create_app

__all__ = [
    # 配置
    "DB_CONFIG",
    "MODEL_CONFIG", 
    "PERIOD_CONFIG",
    "TECHNICAL_INDICATORS",
    "PATTERN_CONFIG",
    "API_CONFIG",
    
    # 数据访问
    "StockDataAccess",
    "get_latest_trade_date",
    "get_all_ts_codes",
    
    # 周期计算
    "PeriodCalculator",
    "get_period_windows",
    
    # 涨跌幅计算
    "ReturnCalculator",
    "calc_period_return",
    
    # 形态分类
    "PatternType",
    "PATTERN_NAME_MAP", 
    "PatternClassifier",
    
    # 特征工程
    "FeatureEngineer",
    
    # API
    "app",
    "create_app",
]
