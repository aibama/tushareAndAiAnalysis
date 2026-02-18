# 智途API股票数据爬虫

使用 `requests` 库调用智途API，获取股票数据并存入MySQL数据库。

## 配置说明

配置统一在 `PatternAnalysis/config.py` 中的 `ZHITU_API_CONFIG`：

```python
ZHITU_API_CONFIG = {
    "token": "你的API令牌",
    8657CA7B-E544-4C2A-9540-1F9E28C77ABF
    F65AE572-E30A-45C5-8AB2-88E70493EEA8
    3738FCAC-163E-42A4-82CB-34423318394F
    "base_url": "https://api.zhituapi.com",
    "request_interval_min": 5000,  # 最小间隔5秒
    "request_interval_max": 10000,  # 最大间隔10秒
    "data_source": "zhituapi"
}
```

数据库使用 `PatternAnalysis/config.py` 中的 `DB_CONFIG`。

## 项目结构

```
PatternAnalysis/zhituapi/
├── __init__.py              # 模块初始化
├── api_client.py             # API客户端
├── db_operations.py          # 数据库操作
├── crawler.py               # 主程序入口
├── sql/
│   └── schema.sql          # 数据库表结构
└── README.md               # 使用说明
```

## 使用方法

### 1. 创建数据库表

```bash
mysql -u root -p < PatternAnalysis/zhituapi/sql/schema.sql
```

### 2. 安装依赖

```bash
pip install requests pymysql
```

### 3. 运行爬虫

```bash
python PatternAnalysis/zhituapi/crawler.py
```

### 4. 在代码中调用

```python
from PatternAnalysis.zhituapi import (
    crawl_stock_list,
    crawl_stock_details
)

crawl_stock_list()   # 步骤1: 获取股票列表
crawl_stock_details()  # 步骤2: 获取详细信息（5-10秒/只）
```

## 功能说明

### 接口一：获取股票列表
- **URL**: `https://api.zhituapi.com/hs/list/all?token=xxx`
- **存储**: `stockinfobase` 表
  - `dm` → `ts_code`
  - `mc` → `name`
  - `jys` → `factory_code`

### 接口二：获取股票详细信息
- **URL**: `http://api.zhituapi.com/hs/instrument/{stock_code}?token=xxx`
- **调用频率**: 每5-10秒随机间隔
- **存储**: `stock_trade_info` 表

| 接口字段 | 表字段 |
|---------|--------|
| `ei` | `market_code` |
| `ii` | `stock_code` |
| `ii`去掉后缀 | `stock_symbol` |
| `name` | `stock_name` |
| `od` | `listing_date` |
| `pc` | `prev_close_price` |
| `up` | `up_limit_price` |
| `dp` | `down_limit_price` |
| `fv` | `float_shares` |
| `tv` | `total_shares` |
| `pk` | `price_tick` |
| `is` | `is_suspended` |
