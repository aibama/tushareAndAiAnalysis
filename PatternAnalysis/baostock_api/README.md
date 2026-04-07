# PatternAnalysis/baostock_api

`/api/baostock/sync/tradetoday/all`（以及同类单股接口）用于把 **Baostock** 的 A 股日线历史写入 MySQL 表 `stocktradetodayinfo`。

本目录在设计上对齐了项目内 `akshare_api` 的接口语义，并提供“启动即执行”的分布式多节点实现（支持多实例同时部署）。

---

## 1. HTTP 接口（Swagger 可见）

### 1.1 批量同步

- `GET /api/baostock/sync/tradetoday/all`
- 参数：
  - `start_date`：开始日期（`yyyy-mm-dd` 或 `yyyymmdd`）
  - `end_date`：结束日期（`yyyy-mm-dd` 或 `yyyymmdd`）
  - `adjust`：复权（`""` 不复权，`qfq` 前复权，`hfq` 后复权）
  - `limit`：仅同步前 N 只股票（测试用，按 ts_code 顺序限制）

### 1.2 单股同步（用于调试）

- `GET /api/baostock/sync/tradetoday/one`
- 参数：
  - `ts_code`：股票 ts_code（例如 `600000.SH` / `000001.SZ`）
  - `start_date`、`end_date`、`adjust`
  - `dry_run`：`true` 时只拉取不落库

### 1.3 A 股交易日历（与 Java `ChinaStockTradingDayChecker` 对齐）

实现见 `china_stock_trading_day_checker.py`（周末休市 + 内置 2026 年法定节假日）。

- `GET /api/baostock/trading/latest` — 最近一个交易日、`today`、今日是否交易日  
- `GET /api/baostock/trading/is-trading-day?date=yyyy-MM-dd`  
- `GET /api/baostock/trading/previous?date=yyyy-MM-dd` — 从该日起向前最近交易日  
- `GET /api/baostock/trading/next?date=yyyy-MM-dd` — 从**下一天**起向后下一交易日  
- `GET /api/baostock/trading/need-update?level2_last_update_date=yyyy-MM-dd` — 是否与最近交易日对齐（Level2 补数判断）

---

## 2. 幂等与“不重复执行”的保证

在同步每只股票前，会执行区间幂等判断：

- 如果该 `ts_code` 在 `start_date ~ end_date` 区间内 **已经存在任意记录**，则本次直接返回 `skipped`，不会再请求 Baostock，也不会再写库。

因此：

- 项目重启后，重复调用同一批参数，已落库的数据不会再重复执行下载/入库。

> 说明：当前幂等是“区间内任意记录即跳过整只股票”。如果你希望“必须确保区间全量交易日都齐才算完成”，需要升级校验策略（可按交易日数量/最后交易日等方式实现）。

---

## 3. 降频与限流

为了降低上游拒绝连接概率，同步过程中使用进程内限流策略：

- 10 分钟滑动窗口：`request_limit_per_window` 限制总请求数
- 每次请求前随机间隔：`request_min_interval_seconds ~ request_max_interval_seconds`
- 多线程并发执行但统一走同一个限流器（进程内共享）

默认参数来自 `PatternAnalysis/config.py` 的 `BAOSTOCK_SYNC_CONFIG`（也可通过启动参数/环境变量覆盖你的配置方式）。

---

## 4. 分布式多节点启动执行（随项目启动运行）

批量 `/all` 的逻辑已经抽出为“可传入 `ts_codes` 列表”的函数，因此可以做多节点分片执行。

当 `run_server.py` 启动时，会后台触发：

- `PatternAnalysis/baostock_api/distributed_startup_runner.py`

### 4.0 启动同步的日期区间（配置 + 库内 MAX，2025-12 需求）

**不再**默认使用「最近 N 天回看」；改为：

1. **开始下界**  
   来自 `PatternAnalysis/config.py` → `BAOSTOCK_SYNC_CONFIG["sync_min_start_date"]`  
   例如当前库内业务最早日期为 `2023-01-03`，则配置为该字符串（`yyyy-mm-dd`）。

2. **结束上界（日历「最近一个交易日」）**  
   由 `PatternAnalysis/baostock_api/china_stock_trading_day_checker.py` 的 `get_latest_trading_day_date()`：  
   **今天为交易日则取今天，否则向前取上一交易日**；节假日集合当前内置 **2026** 年（与 Java 版一致），其它年份仅按**周末**判断休市。

3. **是否拉取、拉哪一段**（基于 `stocktradetodayinfo` 全表）  
   - 查询 `MAX(trade_date)`（与 `PatternAnalysis.data_access.get_latest_trade_date()` 一致）。  
   - 若 **无数据**：同步区间为 `[sync_min_start_date, 日历最近交易日]`（全量/首次）。  
   - 若 `MAX(trade_date) >= 日历最近交易日`：**认为已跟上**，本次启动**不进行** Baostock 同步。  
   - 若 `MAX(trade_date) < 日历最近交易日`：**增量**区间为  
     `[max(sync_min_start_date, MAX(trade_date) + 1 天), 日历最近交易日]`。

4. **运维覆盖（可选）**  
   若环境变量**同时**设置 `BAOSTOCK_SYNC_START_DATE` 与 `BAOSTOCK_SYNC_END_DATE`，则**优先**使用该区间，忽略上述自动逻辑。  
   只设置其中一个会被忽略并打日志警告。

相关实现文件：

- `PatternAnalysis/baostock_api/china_stock_trading_day_checker.py` — A 股交易日判断（与 Java 对齐）  
- `PatternAnalysis/baostock_api/startup_sync_dates.py` — 区间计算  
- `PatternAnalysis/baostock_api/distributed_startup_runner.py` — 启动入口（调用上述区间后再分片、加锁、同步）

### 4.1 分片与不重叠机制（重点）

多节点分片使用确定性策略：

1. 从 `stockinfobase` 读取全部 `ts_code`
2. 对 `ts_code` 做**确定性排序**（`sorted({ts_code})`）
3. 按排序后的稳定顺序切分：`i % node_count == node_id`

由于增加了“排序”，不同节点/不同启动时间拿到的 `ts_code` 序列将保持一致，从而满足：

- 各节点负责互不重叠的 ts_code 子集
- 节点间不会互相干扰（理论上不重叠；即使发生异常/重试也会被幂等跳过）

### 4.2 Redis 分布式锁

每个节点分片还会在启动时尝试获取 Redis 锁，避免“同一 node_id 的重复触发”。

- 默认：锁粒度按 `node_id`（允许不同 node_id 并行）
- 可选：开启全局锁（所有节点互斥）

---

## 5. 启动环境变量（建议）

你可以为每台节点设置不同的 `BAOSTOCK_SYNC_NODE_ID` / `BAOSTOCK_SYNC_NODE_COUNT`：

- `BAOSTOCK_SYNC_ON_STARTUP_ENABLED`：是否启动自动同步（默认 `true`）
- `BAOSTOCK_SYNC_ADJUST`：`"" | qfq | hfq`（默认 `""`）
- `BAOSTOCK_SYNC_START_DATE` + `BAOSTOCK_SYNC_END_DATE`：**同时设置**时覆盖自动区间（运维调试用）；见上文 4.0
- `BAOSTOCK_SYNC_NODE_ID`：当前节点编号（默认 `0`）
- `BAOSTOCK_SYNC_NODE_COUNT`：总节点数（默认 `1`）
- `BAOSTOCK_SYNC_LIMIT_PER_NODE`：每个节点最多处理多少只股票（默认 `0` 表示不限制）
- `BAOSTOCK_SYNC_USE_GLOBAL_LOCK`：是否全局互斥（默认 `false`）
- `BAOSTOCK_SYNC_LOCK_TIMEOUT_SECONDS`：锁超时（默认 21600 秒）
- `BAOSTOCK_SYNC_MAX_WORKERS`：每个节点内部线程数（默认使用项目默认）

当节点数为 2，且 `stockinfobase` 大约有 1 万只股票时，每个节点大约会负责 5 千只左右的 ts_code 子集（误差来自股票数量不能被节点数整除）。

