# Redis Stream Producer Service

## 概述

本模块实现了 Redis Stream 生产者功能，用于从 `stock_composition_relation` 表读取股票代码数据并添加到 Redis Stream，供消费者处理。

## 配置项

在 `config.py` 中添加以下配置：

```python
# Redis Stream 生产者配置
REDIS_STREAM_PRODUCER_CONFIG = {
    "stream_key": "stock-stream",           # Stream 键名称
    "group_name": "stock-group",           # 消费者组名称
    "enabled": True,                        # 是否启用生产者
    "time_window": {
        "start_hour": 0,                   # 开始时间（小时）
        "start_minute": 2,                 # 开始时间（分钟）
        "end_hour": 22,                     # 结束时间（小时）
        "end_minute": 0                     # 结束时间（分钟）
    },
    "batch_size": 100,                      # 每批处理数量
    "max_messages_per_day": 10000           # 每天最大消息数
}
```

## 主要功能

1. **定时生产消息**：每天 16:30 - 22:00 自动从数据库读取股票代码并添加到 Stream
2. **手动触发**：提供 API 接口手动触发消息生产
3. **运维脚本**：提供命令行脚本用于运维触发
