"""
Z-Score 热度图配置
"""
from typing import Dict, Any

# Z-Score 计算配置
ZSCORE_CONFIG: Dict[str, Any] = {
    # 滚动窗口天数
    "window_days": 60,

    # 指标类型
    "indicators": {
        "price": {
            "name": "股价",
            "db_field": "close",
            "description": "基于收盘价计算的Z-Score"
        },
        "pe": {
            "name": "市盈率",
            "db_field": "pe",
            "description": "基于市盈率计算的Z-Score"
        },
        "pb": {
            "name": "市净率",
            "db_field": "pb",
            "description": "基于市净率计算的Z-Score"
        }
    },

    # 默认指标
    "default_indicator": "price",

    # 指数代码配置
    "index_codes": {
        "zz1000": "000852",  # 中证1000
        "sz50": "000016",    # 上证50
        "hs300": "000300",   # 沪深300
        "zz500": "000905",   # 中证500
    },

    # 申万一级行业代码范围
    "sw_industry_level": 1,

    # 缓存配置
    "cache": {
        "enabled": True,
        "ttl": 3600,  # 1小时
        "prefix": "zscore:"
    },

    # API配置
    "api": {
        "prefix": "/api/v1/zscore",
        "title": "Z-Score 热度图服务",
        "version": "1.0.0"
    }
}


# 颜色映射配置
ZSCORE_COLORS = {
    ">= 2": "#B22234",    # 深红
    ">= 1": "#E63946",     # 红
    ">= 0": "#FFB3BA",    # 浅红
    ">= -1": "#B0E0E6",   # 浅绿
    ">= -2": "#2E8B57",   # 绿
    "< -2": "#006400",     # 深绿
    "null": "#CCCCCC"      # 灰
}


def get_zscore_color(zscore: float) -> str:
    """根据Z-Score值返回对应的颜色"""
    import math

    if zscore is None or (isinstance(zscore, float) and math.isnan(zscore)):
        return ZSCORE_COLORS["null"]

    if zscore >= 2:
        return ZSCORE_COLORS[">= 2"]
    elif zscore >= 1:
        return ZSCORE_COLORS[">= 1"]
    elif zscore >= 0:
        return ZSCORE_COLORS[">= 0"]
    elif zscore >= -1:
        return ZSCORE_COLORS[">= -1"]
    elif zscore >= -2:
        return ZSCORE_COLORS[">= -2"]
    else:
        return ZSCORE_COLORS["< -2"]


def get_indicator_field(indicator: str = "price") -> str:
    """获取指标对应的数据库字段"""
    return ZSCORE_CONFIG["indicators"].get(indicator, {}).get("db_field", "close")
