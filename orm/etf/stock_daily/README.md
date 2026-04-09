# 涨跌停状态同步服务

## 需求说明

### 背景
计算 `stocktradetodayinfo` 表中每只股票的涨跌停状态，并写入数据库。

### 数据库变更
```sql
ALTER TABLE `stocktradetodayinfo`
ADD COLUMN `limit_status` VARCHAR(20) DEFAULT 'NORMAL' COMMENT '涨跌停状态: UP_MAX=涨停，DOWN_MAX=跌停，NORMAL=正常';
```

---

## 功能说明

### 1. 核心逻辑

根据 A 股交易规则，计算涨跌停价格：

| 板块类型 | 涨停/跌停比例 | 代码前缀 |
|---------|-------------|---------|
| 主板普通股 | ±10% | 600/000/002/003 |
| 科创板 | ±20% | 688 |
| 创业板 | ±20% | 300/301 |
| 北交所 | ±30% | 8 |

**计算公式：**
- 涨停价 = round(前收盘价 × (1 + 涨停比例), 2)
- 跌停价 = round(前收盘价 × (1 - 涨停比例), 2)

**判断规则：**
- 收盘价 ≥ 涨停价 → 涨停 (UP_MAX)
- 收盘价 ≤ 跌停价 → 跌停 (DOWN_MAX)
- 其他 → 正常 (NORMAL)

### 2. 服务文件

| 文件 | 说明 |
|-----|------|
| `limit_status_service.py` | 核心服务：涨跌停计算逻辑 |
| `distributed_startup_runner.py` | 启动运行器：带分布式锁（30分钟） |
| `api_routes.py` | API 路由：注册到 Swagger |

---

## 使用说明

### 1. 随系统启动（推荐）

服务会自动随 `run_server.py` 启动，后台执行涨跌停状态同步。

**环境变量控制：**
| 环境变量 | 默认值 | 说明 |
|---------|-------|------|
| `LIMIT_STATUS_SYNC_ON_STARTUP_ENABLED` | `true` | 是否启用启动同步 |
| `LIMIT_STATUS_SYNC_LOCK_PREFIX` | `limit_status:sync:lock:` | Redis 锁前缀 |

### 2. API 接口

#### 同步所有股票
```bash
GET /api/limit-status/sync/all?trade_date=2026-04-08
```
- `trade_date`：可选，指定交易日期，默认最新

#### 同步指定股票
```bash
GET /api/limit-status/sync/stock/600000.SH?trade_date=2026-04-08
```
- `ts_code`：股票代码
- `trade_date`：可选，默认最新

#### 查询涨跌停状态
```bash
GET /api/limit-status/query/600000.SH?trade_date=2026-04-08
```
- `ts_code`：股票代码
- `trade_date`：可选，默认最新

### 3. 代码调用

```python
from orm.etf.stock_daily.limit_status_service import (
    calculate_limit_status_for_all,
    calculate_limit_status_for_stock,
)

# 同步所有股票
result = calculate_limit_status_for_all(trade_date="2026-04-08")

# 同步指定股票
result = calculate_limit_status_for_stock(
    ts_code="600000.SH",
    trade_date="2026-04-08"
)
```

---

## 注意事项

1. **分布式锁**：启动时使用 Redis 分布式锁，默认30分钟超时，避免多节点重复执行

2. **前收盘价为0**：当前收盘价为0或空时，返回 NORMAL

3. **精度处理**：使用 `Decimal` 进行精确计算，避免浮点数误差

4. **ST股处理**：当前版本未区分ST股，统一按主板10%处理，如需ST股5%判断需额外字段支持

5. **执行时间**：建议在每日收盘后执行（15:00后），可配合定时任务

6. **增量更新**：服务会跳过已计算的数据（limit_status 非空），只计算未标记的记录

---

## 配置参考

Redis 锁配置（默认）：
- 锁前缀：`limit_status:sync:lock:`
- 超时时间：1800秒（30分钟）

数据库连接复用 `PatternAnalysis/config.py` 中的 `DB_CONFIG`