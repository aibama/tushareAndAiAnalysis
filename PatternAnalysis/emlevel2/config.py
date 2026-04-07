"""
Redis Stream 生产者配置
"""
from typing import Dict, Any

# Level2 价格区间统计配置
LEVEL2_PRICE_BAND_CONFIG: Dict[str, Any] = {
    # 价格区间范围（百分比）
    "price_range_percent": 30,

    # 大单定义（每笔成交量达到此值视为大单）
    "large_order_threshold": 10000,  # 10000 股

    # 大单分级
    "large_order_levels": {
        "L1": 10000,      # 1万+
        "L2": 50000,      # 5万+
        "L3": 100000,     # 10万+
        "L4": 500000,     # 50万+
    },

    # PostgreSQL 表名
    "minute_trades_table": "stock_minute_trades",

    # 性能优化：分页大小
    "query_batch_size": 50000,

    # 缓存配置
    "cache": {
        "enabled": True,
        "ttl": 3600,  # 1小时
        "prefix": "level2:price_band:"
    }
}

# Redis Stream 生产者配置
REDIS_STREAM_PRODUCER_CONFIG: Dict[str, Any] = {
    # Stream 配置
    "stream_key": "stock-stream",           # Stream 键名称（与消费者一致）
    "group_name": "stock-group",            # 消费者组名称（与消费者一致）
    
    # 启用开关
    "enabled": False,                         # 是否启用生产者
    
    # 时间窗口配置（每天 16:30 - 22:00 产生数据）
    "time_window": {
        "start_hour": 0,                    # 开始时间（小时）
        "start_minute": 2,                   # 开始时间（分钟）
        "end_hour": 23,                       # 结束时间（小时）
        "end_minute": 59                       # 结束时间（分钟）
    },
    
    # 批处理配置
    "batch_size": 100,                       # 每批处理数量
    "max_messages_per_day": 10000,            # 每天最大消息数
    
    # 消息格式配置
    "message_fields": {
        "stock_code": "stockCode",            # 股票代码字段名
    }
}


def get_stream_key() -> str:
    """获取 Stream 键名称"""
    return REDIS_STREAM_PRODUCER_CONFIG.get("stream_key", "stock-stream")


def is_in_time_window() -> bool:
    """
    判断当前时间是否在允许的时间窗口内
    每天 16:30 - 22:00 允许产生数据
    """
    from datetime import datetime
    
    config = REDIS_STREAM_PRODUCER_CONFIG.get("time_window", {})
    now = datetime.now()
    current_minutes = now.hour * 60 + now.minute
    
    start_minutes = config.get("start_hour", 16) * 60 + config.get("start_minute", 30)
    end_minutes = config.get("end_hour", 22) * 60 + config.get("end_minute", 0)
    
    return start_minutes <= current_minutes < end_minutes


def is_enabled() -> bool:
    """检查生产者是否启用"""
    return REDIS_STREAM_PRODUCER_CONFIG.get("enabled", True)
