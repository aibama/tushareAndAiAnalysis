# Z-Score 热度图服务

中证1000 Z-Score 行业钻取热度图后端服务

## 功能说明

提供基于 Z-Score 的热度图数据接口，支持：
- 行业层级 Z-Score（一级视图）
- 个股层级 Z-Score（二级视图）
- 时间序列分析

## Z-Score 计算逻辑

### 个股 Z-Score

对于每个交易日 t 和每只股票 i：
1. 取过去60个交易日的指标序列
2. 计算均值 μ 和标准差 σ
3. Z-Score = (当前值 - μ) / σ

### 行业综合 Z-Score

行业内所有成分股 Z-Score 的市值加权平均：
```
Z_行业 = Σ(市值_i × Z_i) / Σ(市值_i)
```

## 目录结构

```
zscore/
├── __init__.py           # 包初始化
├── config.py             # 配置文件
├── data_service.py       # 数据获取服务
├── zscore_service.py     # Z-Score计算服务
├── api_routes.py         # API路由
├── scheduler_service.py  # 定时任务
└── README.md             # 说明文档
```

## 快速开始

### 1. 安装依赖

```bash
pip install pymysql psycopg2-binary pandas numpy flask
```

### 2. 配置数据库

确保 MySQL 和 PostgreSQL 配置正确（在 `PatternAnalysis/config.py` 中配置）

### 3. 启动 API 服务

```python
from flask import Flask
from PatternAnalysis.strategy.zscore import register_routes

app = Flask(__name__)
register_routes(app)

app.run(host='0.0.0.0', port=8081)
```

或使用命令行：

```bash
python -m PatternAnalysis.strategy.zscore.api_routes
```

## API 接口

### 1. 获取行业列表及当日 Z-Score

```
GET /api/v1/zscore/industry/daily
```

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| date | string | 否 | 日期 (YYYY-MM-DD)，默认最新交易日 |
| indicator | string | 否 | 指标类型 (price/pe/pb)，默认 price |

**响应示例：**
```json
{
  "code": 0,
  "data": {
    "date": "2026-03-20",
    "indicator": "price",
    "industries": [
      {
        "industry_code": "801010",
        "industry_name": "电子",
        "stock_count": 85,
        "zscore": 0.85,
        "color": "#FFB3BA"
      }
    ]
  }
}
```

### 2. 获取行业成分股 Z-Score

```
GET /api/v1/zscore/industry/stocks
```

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| date | string | 否 | 日期 (YYYY-MM-DD) |
| indicator | string | 否 | 指标类型 |
| industry_code | string | 是 | 行业代码 |

### 3. 获取时间序列

```
GET /api/v1/zscore/timeseries
```

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| date | string | 是 | 结束日期 (YYYY-MM-DD) |
| indicator | string | 否 | 指标类型 |
| entity_type | string | 是 | 实体类型 (industry/stock) |
| entity_code | string | 是 | 实体代码 |
| days | int | 否 | 回溯天数，默认60 |

### 4. 获取指数时间序列

```
GET /api/v1/zscore/index/timeseries
```

## 颜色规范

| Z-Score 区间 | 颜色 |
|-------------|------|
| ≥ 2 | #B22234 (深红) |
| [1, 2) | #E63946 (红) |
| [0, 1) | #FFB3BA (浅红) |
| [-1, 0) | #B0E0E6 (浅绿) |
| [-2, -1) | #2E8B57 (绿) |
| < -2 | #006400 (深绿) |
| null | #CCCCCC (灰) |

## 定时任务

### 命令行执行

```bash
# 计算当天数据
python -m PatternAnalysis.strategy.zscore.scheduler_service --date 2026-03-20

# 守护进程模式
python -m PatternAnalysis.strategy.zscore.scheduler_service --daemon
```

### 集成到现有服务

```python
from PatternAnalysis.strategy.zscore.scheduler_service import calculate_all_zscore
from datetime import date

# 计算指定日期
result = calculate_all_zscore(date(2026, 3, 20))
```

## 数据来源

- **成分股**: stockdata.stock_composition_relation (ZZ1000)
- **日线数据**: stockdata.stocktradetodayinfo
- **行业信息**: stockdata.sw_industry, stockdata.stock_sw_relation
- **市值数据**: 使用共享市值计算服务（pre_close × total_shares），带 Redis 缓存

## 注意事项

1. 首次运行需要确保数据库中有中证1000成分股数据
2. 日线数据需要至少60个交易日才能计算有效的Z-Score
3. 市值数据通过 Redis 缓存获取（stock_rank:market_cap:{ts_code}），计算失败时使用默认值（100亿）
4. 建议在每日收盘后执行定时任务
