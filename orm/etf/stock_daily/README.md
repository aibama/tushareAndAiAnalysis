# 股票日交易数据同步服务

## 需求说明

### 数据源（PostgreSQL）
- **数据库**: stock_data
- **表**: stock_minute_trades

```sql
CREATE TABLE IF NOT EXISTS public.stock_minute_trades
(
    id integer NOT NULL DEFAULT nextval('stock_minute_trades_id_seq'::regclass),
    "time" timestamp without time zone NOT NULL,
    stock_id integer,
    price numeric(10,2),
    volume integer,
    direction character varying(10),
    pre_price numeric(10,2),
    stock_code character varying(12),
    CONSTRAINT stock_minute_trades_pkey PRIMARY KEY (id),
    CONSTRAINT stock_minute_trades_stock_id_time_key UNIQUE (stock_id, "time")
)
```

### 目标表（MySQL）
- **数据库**: stockdata
- **表**: stocktradetodayinfo

```sql
CREATE TABLE `stocktradetodayinfo` (
  `id` decimal(16,2) DEFAULT NULL,
  `ts_code` varchar(255) NOT NULL,
  `amount` decimal(16,3) DEFAULT NULL,
  `echange` float DEFAULT NULL,
  `close` float DEFAULT NULL,
  `high` float DEFAULT NULL,
  `low` float DEFAULT NULL,
  `open` float DEFAULT NULL,
  `pct_chg` float DEFAULT NULL,
  `pre_close` float DEFAULT NULL,
  `trade_date` datetime(6) DEFAULT NULL,
  `vol` decimal(16,2) DEFAULT NULL,
  `trade_date_tmp` datetime(6) DEFAULT NULL,
  KEY `idx_stocktradedailyinfo_trade_date` (`trade_date`),
  KEY `idx_ts_code_date` (`ts_code`,`trade_date` DESC),
  KEY `idx_trade_date_ts_code` (`trade_date`,`ts_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
```

### 数据映射关系

| MySQL 字段 | 数据来源 |
|-----------|---------|
| ts_code | stock_minute_trades.stock_code |
| close | stock_minute_trades 中 time 为当天 15:00:00 的 price |
| high | stock_minute_trades 个股当日最高 price |
| low | stock_minute_trades 个股当日最低 price |
| open | stock_minute_trades 中 time 为当天 09:25:00 的 price |
| vol | stock_minute_trades 当日 volume 总和 |
| amount | stock_minute_trades 当日 volume * price 总和 |
| pct_chg | (close - pre_close) / pre_close * 100 |
| pre_close | 前一天 15:00:00 的 price |
| trade_date | 当天日期 |

## 开发内容

### 1. 配置文件
- **文件**: PatternAnalysis/config.py
- **内容**: 添加 PostgreSQL 数据库连接配置

```python
PG_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "postgres",
    "password": "940611",
    "database": "stock_data"
}
```

### 2. 同步服务
- **文件**: PatternAnalysis/stock_trade_sync_service.py
- **功能**:
  - 从 PostgreSQL 读取指定日期的分时交易数据
  - 按股票代码汇总计算各项指标
  - 获取前收盘价并计算涨跌幅
  - 写入 MySQL stocktradetodayinfo 表（支持 upsert）

## 使用方式

### 方式一：命令行运行

```bash
# 使用 conda 环境运行
conda run -n py_newest_stock python -m PatternAnalysis.stock_trade_sync_service

# 或直接指定 Python 路径
/c/Users/dzs52/miniconda3/envs/py_newest_stock/python.exe -m PatternAnalysis.stock_trade_sync_service
```

### 方式二：代码调用

```python
from datetime import date, timedelta
from PatternAnalysis.stock_trade_sync_service import sync_daily_trade_data

# 同步今天的数据
result = sync_daily_trade_data()

# 同步指定日期的数据
result = sync_daily_trade_data(date(2026, 3, 18))

# 同步昨天的数据
result = sync_daily_trade_data(date.today() - timedelta(days=1))

print(result)
# 输出: {'success': True, 'message': '同步完成: 成功 100, 失败 0', 'total': 100, ...}
```

### 方式三：集成到定时任务

```python
# 在现有的调度服务中添加
from PatternAnalysis.stock_trade_sync_service import sync_daily_trade_data

def daily_sync_job():
    """每日 15:00 后执行的同步任务"""
    return sync_daily_trade_data()
```

## 注意事项

### 1. 环境依赖
- 需要安装 `psycopg2-binary` 包：
  ```bash
  pip install psycopg2-binary
  ```

### 2. 前收盘价说明
- 如果前一天没有 15:00 的收盘价记录，`pre_close` 和 `pct_chg` 将为 0
- 这不影响其他字段的正常同步

### 3. 数据完整性
- 只有当天 15:00 收盘价存在的股票才会被同步
- 缺少开盘价（09:25:00）的股票，`open` 字段将为 0

### 4. MySQL 主键策略
- 使用时间戳+随机数生成唯一 ID
- 支持 ON DUPLICATE KEY UPDATE，可重复执行同步

### 5. 执行时间建议
- 建议在每天 15:00 之后执行，确保当天数据完整
- 可配合 cron 或调度器实现自动化

### 6. 错误处理
- 单条数据插入失败不会中断整体流程
- 失败的数据会在日志中记录


日志表使用示例：
{
  "log_code": "LOGIN_FAIL",
  "log_message": "用户 1001 登录失败，密码错误 3 次",
  "attr1": "1001",
  "attr2": "3"
}

{
  "log_code": "LOGIN_FAIL",
  "alert_message": "用户登录失败次数过多",
  "query_expression": "attr1 = {ts_code}"
} 
这里 alert_message 作为标题或概要，log_message 作为详情。