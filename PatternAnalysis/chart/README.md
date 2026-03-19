# K线图数据服务

提供日K线图所需的数据接口，基于 `stocktradetodayinfo` 表结构。

## 数据表结构

```sql
CREATE TABLE `stocktradetodayinfo` (
  `id` decimal(16,2) DEFAULT NULL,
  `ts_code` varchar(255) NOT NULL,
  `amount` decimal(16,3) DEFAULT NULL,    -- 成交额（元）
  `echange` float DEFAULT NULL,           -- 换手率
  `close` float DEFAULT NULL,              -- 收盘价
  `high` float DEFAULT NULL,               -- 最高价
  `low` float DEFAULT NULL,                -- 最低价
  `open` float DEFAULT NULL,               -- 开盘价
  `pct_chg` float DEFAULT NULL,           -- 涨跌幅（%）
  `pre_close` float DEFAULT NULL,          -- 前收盘价
  `trade_date` datetime(6) DEFAULT NULL,   -- 交易日期
  `vol` decimal(16,2) DEFAULT NULL,       -- 成交量（手）
  `trade_date_tmp` datetime(6) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
```

## API接口

### 1. 获取K线数据

```
GET /api/chart/kline/{ts_code}
```

**参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| ts_code | string | 是 | 股票代码，如 `000001.SZ` |
| start_date | string | 是 | 开始日期，格式：`YYYY-MM-DD` |
| end_date | string | 是 | 结束日期，格式：`YYYY-MM-DD` |
| kline_type | string | 否 | K线类型：`daily`(日K)、`weekly`(周K)、`monthly`(月K)，默认 `daily` |

**响应示例：**

```json
{
  "ts_code": "000001.SZ",
  "kline_type": "daily",
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "total": 20,
  "data": [
    {
      "trade_date": "2024-01-02",
      "open": 10.50,
      "high": 10.80,
      "low": 10.40,
      "close": 10.75,
      "volume": 1250000,
      "amount": 13250000.0,
      "pct_chg": 2.38,
      "pre_close": 10.50
    }
  ]
}
```

### 2. 获取Chart.js格式数据

```
GET /api/chart/kline/{ts_code}/chartjs
```

**参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| ts_code | string | 是 | 股票代码 |
| days | int | 否 | 获取最近多少天的数据，默认30天 |

**响应示例：**

```json
{
  "ts_code": "000001.SZ",
  "count": 30,
  "labels": ["2024-01-02", "2024-01-03", ...],
  "ohlc": [
    [10.50, 10.80, 10.40, 10.75],  // [开盘, 最高, 最低, 收盘]
    ...
  ],
  "volume": [1250000, 1380000, ...]
}
```

## 前端使用示例

### 使用ECharts渲染K线图

```javascript
// 获取K线数据
const response = await fetch('/api/chart/kline/000001.SZ?start_date=2024-01-01&end_date=2024-03-01&kline_type=daily');
const data = await response.json();

// ECharts配置
const option = {
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'cross' }
  },
  xAxis: {
    data: data.data.map(item => item.trade_date)
  },
  yAxis: {},
  series: [
    {
      type: 'candlestick',
      data: data.data.map(item => [item.open, item.close, item.low, item.high])
    }
  ]
};
```

### 使用Chart.js渲染K线图

```javascript
// 获取Chart.js格式数据
const response = await fetch('/api/chart/kline/000001.SZ/chartjs?days=60');
const data = await response.json();

// Chart.js配置
new Chart(ctx, {
  type: 'bar',
  data: {
    labels: data.labels,
    datasets: [{
      label: '成交量',
      data: data.volume,
      backgroundColor: data.ohlc.map(o => o[3] >= o[0] ? '#ff0000' : '#00ff00')
    }]
  }
});
```

## 服务层使用

```python
from PatternAnalysis.chart.kline_service import (
    get_kline,
    get_daily_kline,
    get_weekly_kline,
    get_monthly_kline,
    get_kline_for_chartjs
)

# 获取日K线数据
kline_data = get_kline(
    ts_code='000001.SZ',
    start_date=date(2024, 1, 1),
    end_date=date(2024, 3, 1),
    kline_type='daily'
)

# 获取适合Chart.js的数据格式
chartjs_data = get_kline_for_chartjs('000001.SZ', days=30)
```

## 依赖

- Python 3.8+
- pandas
- numpy
- sqlalchemy
- pymysql

数据来源于 `stocktradetodayinfo` 表，需要确保数据库连接配置正确。
