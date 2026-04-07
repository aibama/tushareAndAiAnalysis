# (deprecated) AkShare 应用层

与 `zhituapi` 类似面向「数据拉取场景」，但数据源为 **AkShare**（Python 包内接口，直接方法调用）。**股票基础名单**从 MySQL `stockinfobase` 读取，并在应用层从 `ts_code` 解析 **`stock_code`（6 位数字股票代码）**；部分接口已注册到主服务 Swagger（`/docs`）。

**命名说明：** Tsanghi 等 HTTP 接口请求里同含义参数常叫 **`ticker`**；本包统一用 **`stock_code`（股票代码）**，避免与「交易所+代码」形态的 `ts_code` 混淆。

## 依赖

```bash
pip install akshare pandas pymysql
```

数据库连接复用 `PatternAnalysis/config.py` 中的 `DB_CONFIG`（与 tsanghiapi 相同约定）。

## 模块说明

| 模块 | 说明 |
|------|------|
| `hist_service.py` | A 股历史 K 线：`stock_zh_a_hist`（不复权 / 前复权 / 后复权） |
| `utils.py` | `stock_code_from_ts_code`（多格式 ts_code → 6 位数字）、`to_yyyymmdd` |
| `db_operations.py` | 读取 `stockinfobase` |
| `stock_list_service.py` | 为每条基础信息附加 `stock_code` 字段 |
| `tradetoday_upsert.py` | AkShare 日线字段映射并 upsert 到 `stocktradetodayinfo` |
| `sync_tradetoday_service.py` | 遍历 `stockinfobase` 并发拉取日线并落库 |
| `api_routes.py` | FastAPI 路由：`/api/akshare/...`（由 `api_service` 注册） |

并发线程数见 `PatternAnalysis/config.py` 中 **`AKSHARE_SYNC_CONFIG["max_workers"]`**（默认 5）。

## ts_code → stock_code（应用层规则）

| 示例 ts_code | stock_code |
|--------------|--------------|
| `000001.SZ` | `000001` |
| `600519.SH` | `600519` |
| `1.600519` | `600519` |
| `0.000001` | `000001` |

实现函数：`stock_code_from_ts_code`；`normalize_a_share_symbol` 与其行为一致。

## HTTP 接口（Swagger）

启动主服务后打开 **`http://localhost:8081/docs`**（端口以本地配置为准），标签 **「AkShare」**：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/akshare/stocks/from-db` | 读取 `stockinfobase` 全表，返回 `ts_code`、`name`、`factory_code`、`stock_code` |
| GET | `/api/akshare/stocks/from-db/{ts_code}` | 按 `ts_code` 查一条，不存在则 404 |
| GET | `/api/akshare/sync/tradetoday/all` | 全市场日线同步：参数 `start_date`、`end_date`、**`adjust`**（空/`qfq`/`hfq`），可选 `limit`，写入 **`stocktradetodayinfo`** |

**落库说明（`sync/tradetoday/all`）：**

- 仅 **日 K**（`period=daily`）；AkShare 返回列映射为表字段：`open/high/low/close/vol/amount/pct_chg/pre_close`，**`echange`** 使用行情中的 **换手率（%）**（与 K 线 README 中「换手率」字段一致）。
- 使用与 `stock_trade_sync_service` 相同的 **`INSERT ... ON DUPLICATE KEY UPDATE`**；请确保库中存在 **`(ts_code, trade_date)`** 的唯一约束（或等价主键），否则请自行建唯一索引后再同步。

**curl 示例：**

```bash
curl -s "http://localhost:8081/api/akshare/stocks/from-db"
curl -s "http://localhost:8081/api/akshare/stocks/from-db/000001.SZ"

# 全市场日线写入 stocktradetodayinfo（建议先用 limit 小范围试跑）
curl -s "http://localhost:8081/api/akshare/sync/tradetoday/all?start_date=2026-02-14&end_date=2026-03-30&limit=5"
# 前复权
curl -s "http://localhost:8081/api/akshare/sync/tradetoday/all?start_date=2026-02-14&end_date=2026-03-30&adjust=qfq&limit=5"
```

## 代码调用（不写 HTTP）

### 从库中拉列表并带 stock_code

```python
from PatternAnalysis.akshare import (
    list_stockinfobase_with_stock_code,
    get_stockinfobase_row_with_stock_code,
)

rows = list_stockinfobase_with_stock_code()
# [{"ts_code", "name", "factory_code", "stock_code"}, ...]

one = get_stockinfobase_row_with_stock_code("000001.SZ")
```

### 仅解析股票代码（不查库）

```python
from PatternAnalysis.akshare import stock_code_from_ts_code

assert stock_code_from_ts_code("1.600519") == "600519"
```

调用 Tsanghi HTTP 时，把这里的 `stock_code` 填入对方接口要求名为 `ticker` 的字段即可。

### 批量同步到 stocktradetodayinfo（代码调用）

```python
from PatternAnalysis.akshare import sync_tradetoday_all_from_akshare

out = sync_tradetoday_all_from_akshare(
    start_date="2026-02-14",
    end_date="2026-03-30",
    adjust="",       # 不复权；前复权 "qfq"；后复权 "hfq"
    limit=10,       # 仅测前 10 只；全市场则 limit=None
)
# out["rows_saved_total"], out["success_count"], out["results"]
```

### 历史行情（不复权示例）

对应 AkShare：`ak.stock_zh_a_hist(symbol=..., period="daily", start_date="20170301", end_date="20240528", adjust="")`

应用层支持 `start_date` / `end_date` 使用 **`yyyy-mm-dd`** 或 **`yyyymmdd`**，由 `to_yyyymmdd` 统一转换。

```python
from PatternAnalysis.akshare import get_stock_zh_a_hist, get_stock_zh_a_hist_dataframe

rows = get_stock_zh_a_hist(
    symbol="000001",
    period="daily",
    start_date="2017-03-01",
    end_date="2024-05-28",
    adjust="",
)
# rows[0] 示例键: date, symbol, open, close, high, low, volume, amount,
#               amplitude_pct, pct_change, change_amount, turnover_pct
# volume 单位：手；amount：元；振幅/涨跌幅/换手率：%

df = get_stock_zh_a_hist_dataframe(
    symbol="000001.SZ",
    start_date="20170301",
    end_date="20240528",
    adjust="",
)
```

### 参数要点（历史行情）

- **symbol**：6 位股票代码；也可传 `000001.SZ` / `600519.SH`，内部用 `stock_code_from_ts_code` 规整。
- **period**：`daily` | `weekly` | `monthly`
- **adjust**：不复权 `""`；前复权 `qfq`；后复权 `hfq`
- **timeout**：若当前安装的 `akshare` 中 `stock_zh_a_hist` 支持该参数则传入，否则自动忽略并打 debug 日志

### 类方式（历史行情）

```python
from PatternAnalysis.akshare import StockZhAHistService

svc = StockZhAHistService()
df = svc.get_hist_dataframe("600519", start_date="2021-03-01", end_date="2021-06-16")
records = svc.get_hist("600519", start_date="2021-03-01", end_date="2021-06-16")
```

## 与 zhituapi 的对比

| 项目 | zhituapi | akshare（本目录） |
|------|----------|-------------------|
| 数据源 | 智途 HTTP API | AkShare 库内函数 |
| 调用方式 | `ZhituApiClient` / 爬虫脚本 | `get_stock_zh_a_hist` 等函数；名单可走 `list_stockinfobase_with_stock_code` |
| 配置 | `ZHITU_API_CONFIG` 等 | `DB_CONFIG` + 行情一般无需 token |
| HTTP | 无（本仓库主服务中为形态分析 API） | 主服务额外注册 `/api/akshare/*` |


section3:
已按你要求把 /api/akshare/sync/tradetoday/all 做成“降频 + 限流 + 幂等跳过”的可运行方案，并已落代码。

已实现的方案
降低线程请求数

在 PatternAnalysis/config.py 把 AKSHARE_SYNC_CONFIG.max_workers 默认降为 2。
sync 服务仍支持传参覆盖，但默认更保守。
10分钟窗口请求上限

在 PatternAnalysis/akshare_api/sync_tradetoday_service.py 新增线程安全滑动窗口限流器 _SlidingWindowLimiter。
按配置限制 window_seconds=600 内最多 request_limit_per_window=80 次请求。
超限自动等待到可用窗口再继续，不会硬打上游。
各请求随机间隔

同一限流器内增加随机间隔控制：request_min_interval_seconds=0.4 到 request_max_interval_seconds=1.6。
每次真正发起抓取前会 acquire()，自动打散请求节奏。
重启后同参数不重复执行（基于已落表数据）

在 PatternAnalysis/akshare_api/tradetoday_upsert.py 新增 has_tradetoday_data_in_range(ts_code, start_date, end_date)。
在 PatternAnalysis/akshare_api/sync_tradetoday_service.py 的 _sync_one_stock 里先查：
如果该 ts_code 在区间内已有数据，直接返回 status=skipped，不再请求 AkShare。
这样服务重启后，针对相同区间请求，已落表的股票会被跳过，不重复执行。
接口返回增加跳过统计

在 PatternAnalysis/akshare_api/api_routes.py 的 TradetodaySyncBatchResponse 增加 skipped_count。
返回结果现在会区分 success / skipped / error。
配置项（已加到 AKSHARE_SYNC_CONFIG）
max_workers
window_seconds
request_limit_per_window
request_min_interval_seconds
request_max_interval_seconds
你可以按上游稳定性继续调小，例如：

max_workers=1
request_limit_per_window=40
间隔改成 0.8~2.5s
说明（重要）
你这次“同参数不重复执行”是按落表幂等跳过实现的：
只要某 ts_code 在该区间内已经有任意记录，就会跳过该股票，避免重复请求上游。
这符合你“已落表数据不重复执行”的目标；如果你后续希望“必须覆盖区间每个交易日才算完成”，我可以再给你升级成“按交易日完整度校验后再决定是否跳过”的严格版。