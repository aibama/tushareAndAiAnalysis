# ETF接口模块

本模块提供Tushare ETF相关数据接口，包括：
- ETF日线行情
- ETF份额规模
- 基金复权因子

## 目录结构

```
etf/
├── __init__.py      # 模块初始化
├── api.py           # 主入口文件
├── fund_daily.py    # ETF日线行情接口
├── etf_share_size.py  # ETF份额规模接口
└── fund_adj.py      # 基金复权因子接口
```

## 快速开始

### 1. ETF日线行情接口 (fund_daily)

```python
from venv.src.mytushare.etf import ETFDailyAPI

# 初始化API
api = ETFDailyAPI(ts_code='510330.SH')

# 获取日线数据（自动过滤已存在数据）
df = api.get_daily(
    start_date='20250101',
    end_date='20250618',
    fields='trade_date,open,high,low,close,vol,amount'
)

# 增量获取（逐日获取，更细粒度）
count = api.get_daily_incremental(
    start_date='20250101',
    end_date='20250618'
)
```

### 2. ETF份额规模接口 (etf_share_size)

```python
from venv.src.mytushare.etf import ETFShareSizeAPI

# 初始化API
api = ETFShareSizeAPI(ts_code='510330.SH')

# 获取份额规模数据
df = api.get_share_size(
    start_date='20250101',
    end_date='20251224'
)

# 获取指定日期所有ETF份额规模
df = api.get_all_etf_on_date(trade_date='20251224', exchange='SSE')

# 增量获取
count = api.get_share_size_incremental(start_date='20250601', end_date='20250618')
```

### 3. 基金复权因子接口 (fund_adj)

```python
from venv.src.mytushare.etf import FundAdjAPI

# 初始化API
api = FundAdjAPI(ts_code='513100.SH')

# 获取复权因子
df = api.get_adj(
    start_date='20190101',
    end_date='20190926'
)

# 增量获取
count = api.get_adj_incremental(start_date='20190901', end_date='20190926')
```

## 增量更新说明

所有接口都支持增量更新，在接口重启运行时会自动过滤已存在的数据：

1. **filter_existing参数**：默认为True，会过滤数据库中已存在的日期
2. **逐日获取模式**：使用`*_incremental()`方法可以逐日获取数据，更细粒度控制

### 使用场景

- **首次运行**：设置`filter_existing=False`获取全部历史数据
- **日常更新**：使用默认的`filter_existing=True`过滤已存在数据
- **断点续传**：使用`*_incremental()`方法逐日获取

## 数据表结构

### etf_daily_info (ETF日线行情)

| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | String | ETF代码 |
| trade_date | String | 交易日期 |
| open | Float | 开盘价 |
| high | Float | 最高价 |
| low | Float | 最低价 |
| close | Float | 收盘价 |
| pre_close | Float | 前收盘价 |
| change | Float | 涨跌额 |
| pct_chg | Float | 涨跌幅 |
| vol | Float | 成交量 |
| amount | Float | 成交额 |
| last_update_time | DateTime | 更新时间 |

### etf_share_size_info (ETF份额规模)

| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | String | ETF代码 |
| trade_date | String | 交易日期 |
| etf_name | String | ETF名称 |
| total_share | Float | 总份额 |
| total_size | Float | 总规模 |
| exchange | String | 交易所 |
| last_update_time | DateTime | 更新时间 |

### fund_adj_info (基金复权因子)

| 字段 | 类型 | 说明 |
|------|------|------|
| ts_code | String | 基金代码 |
| trade_date | String | 交易日期 |
| adj_factor | Float | 复权因子 |
| last_update_time | DateTime | 更新时间 |

## 常用ETF代码示例

| ETF名称 | 代码 | 交易所 |
|--------|------|--------|
| 沪深300ETF华夏 | 510330.SH | 上交所 |
| 沪深300ETF易方达 | 510310.SH | 上交所 |
| 黄金ETF | 518880.SH | 上交所 |
| 纳指ETF | 513100.SH | 上交所 |
| 创业板ETF | 159915.SZ | 深交所 |
