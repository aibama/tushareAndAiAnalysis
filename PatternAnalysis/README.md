# 股票形态分析系统

基于K线形态的智能分类与涨跌幅分析系统，支持11种形态分类和增量数据处理。

## 功能特性

- **形态分类**: 支持单边上涨/下跌、三角形、杯柄、头肩、圆弧等11种形态识别
- **多周期分析**: 支持3个月、6个月、9个月、12个月及自定义时间周期
- **涨跌幅计算**: 自动计算当前周期和上一周期的涨跌幅
- **增量处理**: 新数据插入后自动增量补全和重算
- **Web界面**: 友好的可视化操作界面
- **API服务**: 提供RESTful API接口

## 目录结构

```
PatternAnalysis/
├── __init__.py           # 包初始化
├── config.py             # 配置文件
├── data_access.py       # 数据访问层
├── periods.py           # 时间周期计算
├── returns.py           # 涨跌幅计算
├── feature_engineering.py  # 技术指标与形态编码
├── pattern_model.py     # 形态分类模型
├── incremental_jobs.py  # 增量数据处理
├── api_service.py       # FastAPI接口
├── web/
│   └── index.html       # Web界面
├── models/              # AI模型存储目录
└── logs/                # 日志目录
```

## 安装依赖

```bash
pip install fastapi uvicorn pymysql pandas numpy scipy python-dateutil
pip install pandas numpy scipy python-dateutil
pip install setuptools
conda install -c conda-forge uvicorn
conda install -c conda-forge setuptools
conda install -c requests
conda install -c plombery

```

## 配置文件

在 `config.py` 中配置数据库连接:

```python
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "your_password",
    "database": "stock_data",
    "charset": "utf8"
}
```

## 启动服务

### 方式一: 使用Python启动

```bash
cd PatternAnalysis
python -m uvicorn api_service:app --host 0.0.0.0 --port 8000 --reload
```

### 方式二: 使用main.py启动

```bash
python main.py
```

### 方式三: 后台运行

```bash
nohup python -m uvicorn api_service:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
```

## API接口

### 1. 健康检查

```http
GET /health
```

响应:
```json
{
    "status": "healthy",
    "latest_trade_date": "2024-01-15",
    "timestamp": "2024-01-15T10:30:00"
}
```

### 2. 成交量主题分析 - 历史最低价成交量

```http
GET /api/volume/lowest-price/{ts_code}
```

参数:
- `ts_code`: 股票代码 (如 000001.SZ)
- `use_cache`: 是否使用缓存 (默认true)

响应:
```json
{
    "ts_code": "000001.SZ",
    "lowest_price": 8.50,
    "lowest_price_date": "2022-04-27",
    "pre_month_start": "2022-03-28",
    "pre_month_end": "2022-04-27",
    "pre_month_avg_volume": 1250000,
    "pre_month_trading_days": 22,
    "post_month_start": "2022-04-27",
    "post_month_end": "2022-05-26",
    "post_month_avg_volume": 1380000,
    "post_month_trading_days": 21,
    "total_avg_volume": 1315000,
    "total_trading_days": 43
}
```

**字段说明:**
- `lowest_price`: 历史最低价
- `lowest_price_date`: 历史最低价日期
- `pre_month_*`: 最低价前一个月的数据（约22个交易日）
- `post_month_*`: 最低价后一个月的数据（约22个交易日）
- `total_avg_volume`: 两个月日均成交量合计

### 3. 成交量主题分析 - 涨停后成交量

```http
GET /api/volume/limit-up/{ts_code}
```

参数:
- `ts_code`: 股票代码 (如 000001.SZ)
- `use_cache`: 是否使用缓存 (默认true)

响应:
```json
{
    "ts_code": "000001.SZ",
    "limit_up_date": "2024-01-15",
    "limit_up_price": 10.50,
    "limit_up_volume": 2500000,
    "days_since_limit_up": 20,
    "cumulative_volume": 35000000,
    "post_limit_avg_volume": 1750000,
    "volume_ratio": 0.70
}
```

**字段说明:**
- `limit_up_date`: 最近涨停日期
- `limit_up_price`: 涨停价格
- `limit_up_volume`: 涨停当日成交量
- `days_since_limit_up`: 距今天数（交易日）
- `cumulative_volume`: 涨停后累计成交量
- `post_limit_avg_volume`: 涨停后日均成交量
- `volume_ratio`: 涨停后日均成交量/涨停当日成交量比值

### 4. 触发全量成交量计算

```http
POST /api/volume/recalculate?num_threads=4
```

参数:
- `num_threads`: 并行计算的线程数 (默认4, 最大16)

响应:
```json
{
    "status": "completed",
    "total_stocks": 5000,
    "message": "全量计算完成，共处理 5000 只股票的历史最低价成交量和 5000 只股票的涨停后成交量"
}
```

### 5. 获取形态分类结果

```http
GET /api/patterns?period_type=3m
```

参数:
- `period_type`: 周期类型 (3m, 6m, 9m, 12m, custom)
- `start_date`: 自定义周期开始日期 (仅custom模式)
- `end_date`: 自定义周期结束日期 (仅custom模式)
- `use_cache`: 是否使用缓存 (默认true)

响应:
```json
{
    "period_type": "3m",
    "period_months": 3,
    "current_period": {
        "start": "2023-10-15",
        "end": "2024-01-15"
    },
    "previous_period": {
        "start": "2023-07-15",
        "end": "2023-10-15"
    },
    "total_stocks": 1000,
    "pattern_groups": [
        {
            "pattern_type": 1,
            "pattern_name": "单边上涨",
            "stocks": [
                {
                    "ts_code": "000001.SZ",
                    "pattern_type": 1,
                    "pattern_name": "单边上涨",
                    "curr_return": 0.15,
                    "prev_return": 0.08
                }
            ]
        }
    ]
}
```

### 3. 获取单个股票形态

```http
GET /api/patterns/000001.SZ?period_type=3m
```

### 4. 获取形态汇总

```http
GET /api/patterns/summary/3m
```

### 5. 触发增量计算

```http
POST /api/jobs/incremental
```

### 6. 触发全量重算

```http
POST /api/jobs/full
```

### 7. 股票排名（涨跌幅）

```http
GET /api/rank?direction=up&start_date=2025-01-20&end_date=2026-01-10&limit=150
```

参数:
- `direction`: 排名方向 (up=涨, down=跌)
- `start_date`: 开始日期
- `end_date`: 结束日期
- `limit`: 返回结果数量限制 (默认150, 最大500)
- `use_cache`: 是否使用缓存 (默认true)

请求体 (分页参数，可选):
```json
{
    "page": 1,
    "page_size": 50
}
```

响应:
```json
{
    "direction": "up",
    "start_date": "2025-01-20",
    "end_date": "2026-01-10",
    "total_stocks": 150,
    "page": 1,
    "page_size": 50,
    "total_pages": 3,
    "rankings": [
        {
            "rank": 1,
            "ts_code": "688585.SH",
            "return_rate": 2091.63,
            "max_drawdown_rebound": 2091.63,
            "price_range_return_rate": 3500.25
        }
    ]
}
```

**字段说明:**
- `return_rate`: 区间涨跌幅（排名依据）
- `max_drawdown_rebound`: 时间序列收益率 = (末日收盘价 - 首日收盘价) / 首日收盘价
- `price_range_return_rate`: 区间最高收益 = (区间最高价 - 区间最低价) / 区间最低价（现货卖空概念）

## Web界面

打开浏览器访问: http://localhost:8000/web/index.html

或直接打开 `PatternAnalysis/web/index.html` 文件。

## 形态分类说明

| 编号 | 形态名称 | 说明 |
|------|----------|------|
| 1 | 单边上涨 | 价格持续上涨，波动较小 |
| 2 | 单边下跌 | 价格持续下跌，波动较小 |
| 3 | 上升三角形 | 高点走平，低点上升 |
| 4 | 下降三角形 | 高点下降，低点走平 |
| 5 | 对称三角形 | 高点和低点都向中间收敛 |
| 6 | 杯状带柄 | 形似茶杯，右侧有短暂回调 |
| 7 | 头肩顶 | 中间高，两侧低 |
| 8 | 头肩底 | 中间低，两侧高 |
| 9 | 圆弧顶 | 价格弧形下跌 |
| 10 | 圆弧底 | 价格弧形上涨 |
| 11 | 其他形态 | 无法归类的形态 |

## 增量数据处理

### 自动增量处理

系统会在以下情况自动触发增量处理:
1. 新日线数据插入后
2. 定时任务执行

### 手动触发

```bash
# 增量处理
python incremental_jobs.py --mode incremental

# 全量重算
python incremental_jobs.py --mode full

# 初始化表
python incremental_jobs.py --mode init
```

## 涨跌幅计算

### /api/rank 返回字段说明

| 字段 | 说明 | 计算公式 |
|------|------|----------|
| return_rate | 区间涨跌幅（时间序列收益率） | (末日收盘价 - 首日收盘价) / 首日收盘价 × 100% |
| max_drawdown_rebound | 时间序列收益率 | 同return_rate，冗余字段 |
| price_range_return_rate | 区间最高收益（现货卖空概念） | (区间最高价 - 区间最低价) / 区间最低价 × 100% |

### 形态分析涨跌幅计算

- **当前周期涨幅**: 当前周期最后交易日收盘价 / 当前周期首日收盘价 - 1
- **上一周期涨幅**: 上一周期最后交易日收盘价 / 上一周期首日收盘价 - 1

## 技术指标

系统内置计算以下技术指标:
- 移动平均线 (MA5, MA10, MA20, MA60)
- 指数移动平均线 (EMA12, EMA26)
- MACD指标
- 布林带
- RSI指标
- ATR指标
- 波动率

## GPU支持

系统支持在6GB显存的显卡上运行:
- 批大小: 32
- 序列长度: 120
- 支持1D CNN和小型Transformer模型

## 注意事项

1. 确保数据库中有足够的交易数据（建议至少30个交易日）
2. 自定义日期范围需要提供完整的起止日期
3. 首次运行会自动初始化数据库表
4. 建议定期执行增量任务以保持数据最新

## 许可证

MIT License

## 系统启动
## F5 文件run_server.py

## 接口文档查看
## http://localhost:8081/docs#/