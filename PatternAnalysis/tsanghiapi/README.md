# (deprecated)Tsanghi API 股票日线数据接口

对接 Tsanghi API 获取股票历史日线数据，支持个股查询和批量同步功能。

## 需求设计

### 背景
需要对接 Tsanghi 股票历史数据日线接口，用于获取股票的 OHLCV 数据（开盘价、最高价、最低价、收盘价、成交量）。

### 数据源
- **API 地址**: `https://www.tsanghi.com/api/fin/stock/{exchange_code}/daily`
- **参数说明**:
  - `token`: API Token（必选）
  - `exchange_code`: 交易所代码（必选）
    - `XSHG` - 上海交易所
    - `XSHE` - 深圳交易所
    - `XNAS` - 纳斯达克
  - `ticker`: 股票代码（必选），如 `600519`
  - `start_date`: 起始日期（可选），格式 `yyyy-mm-dd`
  - `end_date`: 结束日期（可选），格式 `yyyy-mm-dd`

### 功能需求

#### 功能1：个股历史数据接口
- 根据交易所代码和股票代码获取历史日线数据
- 支持指定日期范围查询
- 支持获取个股的开始时间和结束时间

#### 功能2：批量同步
- 读取 `stockinfobase` 表中的股票信息
- 使用 `ts_code` 提取 ticker，处理多种格式：
  - `000001.SZ` → `000001`（去掉 .SZ/.SH 后缀）
  - `1.600519` → `600519`（去掉 1. 前缀）
  - `0.000001` → `000001`（去掉 0. 前缀）
  - 最终输出纯数字的6位股票代码
- 使用 `factory_code` 转换为交易所代码（`SZ`→`XSHE`, `SH`→`XSHG`）
- 成功或失败都记录到日志表 `alert_log`

### 技术设计

#### 配置文件
配置统一在 `PatternAnalysis/config.py` 中：

```python
# Tsanghi API配置
TSANGHI_API_CONFIG = {
    "token": "ab0e7c09434f4277bb65a016403db823",                      # API Token
    "base_url": "https://www.tsanghi.com/api/fin/stock",
    "request_timeout": 30,                 # 请求超时（秒）
    "retry_times": 3,                     # 重试次数
    "retry_interval": 5,                   # 重试间隔（秒）
    "max_workers": 10,                    # 最大并发线程数
    "rate_limit_per_minute": 60,          # 每分钟请求上限
    "lock_key_prefix": "tsanghi:sync:lock:",  # 分布式锁前缀
    "lock_timeout": 3600,                 # 锁超时时间（秒）
}

# 日志表配置
LOG_TABLE_CONFIG = {
    "log_code_stock_daily": "000003",
}

# 交易所代码映射
EXCHANGE_CODE_MAPPING = {
    "SZ": "XSHE",  # 深圳交易所
    "SH": "XSHG",  # 上海交易所
}
```

#### 数据库配置
复用项目的 `DB_CONFIG`，数据库使用 MySQL。

#### 并发与限流
- 使用 `ThreadPoolExecutor` 实现多线程并发
- 使用令牌桶算法实现每分钟请求限流
- 使用 Redis 分布式锁确保批量同步并发安全

## 项目结构

```
PatternAnalysis/tsanghiapi/
├── __init__.py              # 模块初始化
├── api_client.py             # API客户端（含限流器）
├── db_operations.py          # 数据库操作
├── daily_service.py         # 个股历史数据服务
├── sync_service.py           # 批量同步服务（含分布式锁）
├── distributed_lock.py      # Redis分布式锁
├── api_routes.py            # FastAPI路由
└── README.md               # 使用说明
```

## 使用说明

### 1. 配置

确保 `config.py` 中已配置以下内容：

```python
# Tsanghi API 配置
TSANGHI_API_CONFIG = {
    "token": "你的token",  # 替换为实际token
    ...
}

# 日志表配置（确保 alert_log 表存在）
LOG_TABLE_CONFIG = {
    "log_code_stock_daily": "000003",
}
```

### 2. 依赖安装

```bash
pip install requests redis pymysql
```

### 3. 确保日志表存在

日志表 `alert_log` 需要存在，表结构参考：

```sql
CREATE TABLE alert_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    log_code VARCHAR(20) NOT NULL COMMENT '日志代码',
    alert_message TEXT COMMENT '告警消息',
    query_expression TEXT COMMENT '查询表达式',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_log_code (log_code)
);
```

### 4. API 接口

启动服务后，访问 `http://localhost:8081/docs` 查看完整 API 文档。

#### 功能1：个股历史数据

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/tsanghi/stock/{exchange_code}/{ticker}/date-range` | GET | 获取个股开始/结束时间 |
| `/api/tsanghi/stock/{exchange_code}/{ticker}/daily` | GET | 获取个股历史数据 |

**示例**:
```bash
# 获取贵州茅台日期范围
curl "http://localhost:8081/api/tsanghi/stock/XSHG/600519/date-range"

# 获取贵州茅台历史数据
curl "http://localhost:8081/api/tsanghi/stock/XSHG/600519/daily?start_date=2024-01-01&end_date=2024-12-31"
```

#### 功能2：批量同步

| 接口路径 | 方法 | 说明 |
|----------|------|------|
| `/api/tsanghi/sync/stock/{ts_code}` | GET | 同步单只股票 |
| `/api/tsanghi/sync/all` | GET | 同步所有股票（多线程并发） |
| `/api/tsanghi/sync/all/locked` | GET | 同步所有股票（带分布式锁，推荐） |
| `/api/tsanghi/sync/lock/status` | GET | 查询锁状态 |
| `/api/tsanghi/sync/lock/release` | POST | 强制释放锁 |

**参数说明**:
- `limit`: 限制同步数量，用于测试
- `start_date`: 起始日期 (yyyy-mm-dd)，用于增量同步
- `end_date`: 结束日期 (yyyy-mm-dd)，用于增量同步

**使用场景**:
- **全量同步**: 不传 start_date 和 end_date
- **增量同步**: 传入 start_date 和 end_date，如 `start_date=2026-02-14&end_date=2026-03-30`

**示例**:
```bash
# 同步单只股票（ts_code格式：000001.SZ）
curl "http://localhost:8081/api/tsanghi/sync/stock/000001.SZ"

# 同步所有股票（限制100只用于测试）
curl "http://localhost:8081/api/tsanghi/sync/all?limit=100"

# 增量同步（2026-02-14至2026-03-30）- 多线程并发
curl "http://localhost:8081/api/tsanghi/sync/all?start_date=2026-02-14&end_date=2026-03-30"

# 带锁的同步（适合定时任务，推荐）
curl "http://localhost:8081/api/tsanghi/sync/all/locked?limit=100"

# 带锁的增量同步（推荐用于定时任务）
curl "http://localhost:8081/api/tsanghi/sync/all/locked?start_date=2026-02-14&end_date=2026-03-30"

# 查询锁状态
curl "http://localhost:8081/api/tsanghi/sync/lock/status"
```

### 5. 代码调用

```python
# 获取个股历史数据
from PatternAnalysis.tsanghiapi.api_client import get_daily_data
data = get_daily_data("XSHG", "600519", "2024-01-01", "2024-12-31")

# 获取个股日期范围
from PatternAnalysis.tsanghiapi.daily_service import get_stock_date_range
date_range = get_stock_date_range("XSHG", "600519")

# 同步单只股票（默认全量）
from PatternAnalysis.tsanghiapi.sync_service import sync_single_stock
result = sync_single_stock("000001.SZ")

# 同步单只股票（增量）
from PatternAnalysis.tsanghiapi.sync_service import sync_single_stock
result = sync_single_stock("000001.SZ", "2026-02-14", "2026-03-30")

# 带锁的批量同步（默认全量）
from PatternAnalysis.tsanghiapi.sync_service import sync_all_stocks_with_lock
result = sync_all_stocks_with_lock(limit=100)

# 带锁的批量同步（增量）
from PatternAnalysis.tsanghiapi.sync_service import sync_all_stocks_with_lock
result = sync_all_stocks_with_lock(limit=None, start_date="2026-02-14", end_date="2026-03-30")
```

### 6. 定时任务配置

推荐使用带锁的接口进行定时同步，避免重复执行：

```bash
# crontab 示例：每天凌晨2点执行
0 2 * * * curl -s "http://localhost:8081/api/tsanghi/sync/all/locked"
```

## 注意事项

1. **API Token**: 需要替换为实际的 Tsanghi API Token，目前使用 `demo` 可能有访问限制
2. **限流配置**: 根据 API 实际限制调整 `rate_limit_per_minute`
3. **并发数**: 根据服务器性能调整 `max_workers`
4. **分布式锁**: 确保 Redis 服务正常运行
5. **日志表**: 确保 `alert_log` 表存在，否则日志记录会失败
