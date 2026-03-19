"""
Redis Stream 生产者模块

提供股票代码生产功能，用于向 Redis Stream 添加股票代码数据
"""

from .config import (
    REDIS_STREAM_PRODUCER_CONFIG,
    get_stream_key,
    is_in_time_window,
    is_enabled
)

from .stock_producer_service import (
    RedisStreamProducer,
    produce_stock_codes,
    add_single_stock_code,
    fetch_stocks_from_db
)

from .scheduler_service import (
    StockProducerScheduler,
    get_scheduler,
    start_scheduler,
    stop_scheduler,
    trigger_production
)

__all__ = [
    # 配置
    'REDIS_STREAM_PRODUCER_CONFIG',
    'get_stream_key',
    'is_in_time_window',
    'is_enabled',
    
    # 生产者服务
    'RedisStreamProducer',
    'produce_stock_codes',
    'add_single_stock_code',
    'fetch_stocks_from_db',
    
    # 调度器
    'StockProducerScheduler',
    'get_scheduler',
    'start_scheduler',
    'stop_scheduler',
    'trigger_production'
]
