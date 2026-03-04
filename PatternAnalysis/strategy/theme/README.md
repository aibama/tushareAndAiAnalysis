# Theme Strategy - 主题分析

提供个股的涨停/跌停信息、成交量分析等功能的计算和Redis存储。

## 核心概念

### 涨停跌停分析

- **STOCK_MAX_LASTEST_PRICE (SMLP)**: 最近一次涨停的价格
- **SM_PRE**: 最近收盘价与SMLP的比值 = 最近收盘价 / SMLP
  - SM_PRE > 1: 当前收盘价高于上次涨停价
  - SM_PRE < 1: 当前收盘价低于上次涨停价
- 跌停逻辑类似

### 成交量分析

#### 1. 历史最低价成交量
- **lowest_price**: 历史最低价
- **lowest_price_date**: 历史最低价日期
- **pre_month_avg_volume**: 最低价前一个月日均成交量
- **post_month_avg_volume**: 最低价后一个月日均成交量
- **total_avg_volume**: 两个月日均成交量合计

#### 2. 涨停后成交量
- **limit_up_date**: 最近涨停日期
- **cumulative_volume**: 涨停后累计成交量
- **post_limit_avg_volume**: 涨停后日均成交量
- **volume_ratio**: 涨停后日均成交量 / 涨停当日成交量比值

## 数据模型

### LimitPriceInfo

| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | str | 股票代码 |
| limit_up_date | str | 最近涨停日期 |
| limit_up_price | float | 涨停价格 (SMLP) |
| limit_down_date | str | 最近跌停日期 |
| limit_down_price | float | 跌停价格 |
| latest_close | float | 最近收盘价 |
| sm_pre_up | float | 收盘价/涨停价比 (SM_PRE_UP) |
| sm_pre_down | float | 收盘价/跌停价比 (SM_PRE_DOWN) |

## 安装依赖

```bash
pip install redis pandas sqlalchemy pymysql
```

## 使用示例

### 1. 获取单只股票信息

```python
from PatternAnalysis.strategy.theme import get_stock_limit_info

# 获取单只股票的涨停跌停信息
info = get_stock_limit_info("000001.SZ")

print(f"股票代码: {info.ts_code}")
print(f"最近涨停日期: {info.limit_up_date}")
print(f"涨停价格(SMLP): {info.limit_up_price}")
print(f"最近跌停日期: {info.limit_down_date}")
print(f"跌停价格: {info.limit_down_price}")
print(f"最近收盘价: {info.latest_close}")
print(f"收盘/涨停价比(SM_PRE_UP): {info.sm_pre_up}")
print(f"收盘/跌停价比(SM_PRE_DOWN): {info.sm_pre_down}")
```

### 2. 批量计算所有股票

```python
from PatternAnalysis.strategy.theme import calculate_limit_prices_for_all_stocks

# 使用4线程批量计算（默认4线程）
results = calculate_limit_prices_for_all_stocks(num_threads=4)

print(f"共计算 {len(results)} 只股票")
```

### 3. Redis存储操作

```python
from PatternAnalysis.strategy.theme import (
    save_limit_info_to_redis,
    get_limit_info_from_redis,
    get_all_limit_stock_codes
)

# 保存到Redis
info = get_stock_limit_info("000001.SZ", use_cache=False)
save_limit_info_to_redis(info)

# 从Redis读取
cached = get_limit_info_from_redis("000001.SZ")

# 获取有涨停记录的股票列表
up_codes = get_all_limit_stock_codes("up")

# 获取有跌停记录的股票列表
down_codes = get_all_limit_stock_codes("down")
```

## Redis存储结构

### Hash存储
- Key: `stock_rank:limit_info:{ts_code}`
- 存储每个股票的详细涨停跌停信息

### Stream存储 (Redis 5.0+)
- 涨停事件: `stock_rank:limit_up_stream`
- 跌停事件: `stock_rank:limit_down_stream`

### 索引
- 涨停股票索引: `stock_rank:limit_up_index`
- 跌停股票索引: `stock_rank:limit_down_index`

### Redis版本兼容

代码自动检测Redis版本：
- **Redis 5.0+**: 使用Stream进行事件追踪
- **Redis < 5.0**: 使用List模拟Stream（兼容模式）

## 配置

在 `PatternAnalysis/config.py` 中配置数据库和Redis连接：

```python
# 数据库配置
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "database": "stockdata",
    "charset": "utf8"
}

# Redis配置
REDIS_CONFIG = {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "password": "dzs940611",
    "key_prefix": "stock_rank:",
    "cache_ttl": 3600
}
```

## 运行测试

```bash
python PatternAnalysis/strategy/theme/test_limit.py
```

测试将执行：
1. 单只股票计算测试
2. Redis存储测试
3. 多线程批量计算测试
4. 获取涨停/跌停股票列表测试

## 成交量分析使用示例

### 1. 获取历史最低价成交量

```python
from PatternAnalysis.strategy.theme import get_stock_lowest_price_volume

# 获取单只股票的历史最低价成交量信息
info = get_stock_lowest_price_volume("000001.SZ")

print(f"历史最低价: {info.lowest_price}")
print(f"历史最低价日期: {info.lowest_price_date}")
print(f"前一个月日均成交量: {info.pre_month_avg_volume}")
print(f"后一个月日均成交量: {info.post_month_avg_volume}")
print(f"两个月日均成交量: {info.total_avg_volume}")
```

### 2. 获取涨停后成交量

```python
from PatternAnalysis.strategy.theme import get_stock_limit_up_volume

# 获取单只股票的涨停后成交量信息
info = get_stock_limit_up_volume("000001.SZ")

print(f"涨停日期: {info.limit_up_date}")
print(f"涨停当日成交量: {info.limit_up_volume}")
print(f"涨停后累计成交量: {info.cumulative_volume}")
print(f"涨停后日均成交量: {info.post_limit_avg_volume}")
print(f"成交量比值: {info.volume_ratio}")
```

### 3. 批量计算

```python
from PatternAnalysis.strategy.theme import (
    calculate_lowest_price_volume_for_all_stocks,
    calculate_limit_up_volume_for_all_stocks
)

# 计算所有股票的历史最低价成交量
results1 = calculate_lowest_price_volume_for_all_stocks(num_threads=4)

# 计算所有股票的涨停后成交量
results2 = calculate_limit_up_volume_for_all_stocks(num_threads=4)
```

### 4. Redis操作

```python
from PatternAnalysis.strategy.theme import (
    save_lowest_price_volume_to_redis,
    get_lowest_price_volume_from_redis,
    save_limit_up_volume_to_redis,
    get_limit_up_volume_from_redis
)

# 保存到Redis
info1 = get_stock_lowest_price_volume("000001.SZ", use_cache=False)
save_lowest_price_volume_to_redis(info1)

info2 = get_stock_limit_up_volume("000001.SZ", use_cache=False)
save_limit_up_volume_to_redis(info2)

# 从Redis读取
cached1 = get_lowest_price_volume_from_redis("000001.SZ")
cached2 = get_limit_up_volume_from_redis("000001.SZ")
```

## Redis存储结构

### Hash存储
- Key: `stock_rank:volume_info:lowest:{ts_code}` - 历史最低价成交量信息
- Key: `stock_rank:volume_info:limit_up:{ts_code}` - 涨停后成交量信息
