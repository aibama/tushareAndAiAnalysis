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
conda install -c conda-forge uvicorn
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

### 2. 获取形态分类结果

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
