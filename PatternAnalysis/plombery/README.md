# Plombery Tasks - MTR/ATR计算任务

## 概述

本目录包含用于定时调度MTR/ATR计算的任务模块。

## 文件结构

```
PatternAnalysis/plombery/
├── __init__.py          # 包初始化文件
├── mtr_atr_pipeline.py  # MTR/ATR计算流水线任务
├── scheduler.py         # 独立任务调度器（plombery不可用时使用）
├── config.yaml          # 任务配置文件
└── README.md            # 本文档
```

## 功能说明

### 1. MTR/ATR计算任务

#### MTRATRPlomberyPipeline (Plombery可用时)
当plombery框架安装后，可以使用Plombery Pipeline进行任务调度：
- `daily_mtr_atr_task`: 每天16:00执行全量计算
- `hourly_mtr_atr_task`: 每4小时执行增量更新

#### MTRATRPipeline (通用)
通用的MTR/ATR计算流水线，支持：
- 全量计算（重新计算所有股票的MTR/ATR）
- 增量计算（只计算新增交易日的数据）
- 参数变更检测（ATR周期变化时自动重新计算）

#### Scheduler (Plombery不可用时)
独立的任务调度器，支持Cron表达式配置的任务调度。

## 使用方法

### 方法1: 直接运行计算任务

```bash
# 运行MTR/ATR计算
python -m PatternAnalysis.plombery.mtr_atr_pipeline --period 14

# 强制重新计算所有数据
python -m PatternAnalysis.plombery.mtr_atr_pipeline --period 14 --force
```

### 方法2: 启动独立调度器

```bash
# 启动调度器（会按照config.yaml中的配置执行任务）
python -m PatternAnalysis.plombery.scheduler
```

### 方法3: 使用Plombery框架（需要安装）

```bash
# 安装plombery（需要Rust编译器）
pip install plombery

# 启动plombery服务
plombery run
```

## 配置说明

### config.yaml 配置

```yaml
mtr_atr_task:
  atr_period: 14  # ATR计算周期
  
  schedules:
    - name: "daily"
      cron: "0 16 * * *"  # 每天16:00
      enabled: true
    
    - name: "hourly"
      cron: "0 */4 * * *"  # 每4小时
      enabled: true

redis_stream:
  stream_name: "stock_rank:mtr_atr_stream"
  max_length: 10000
```

## Redis Stream

计算结果会保存到Redis Stream，Stream名称为 `stock_rank:mtr_atr_stream`。

消息格式：
```json
{
  "ts_code": "000001.SZ",
  "mtr": 1.2345,
  "atr": 1.5678,
  "atr_period": "14",
  "calculated_at": "2024-01-01T16:00:00"
}
```

## ATR计算公式

### 真实波幅 (TR)
```
TR = MAX( 当日最高价 - 当日最低价, |当日最高价 - 前一日收盘价|, |当日最低价 - 前一日收盘价| )
```

### 平均真实波幅 (ATR)
```
初始ATR = (TR1 + TR2 + ... + TR14) / 14

后续ATR = [前一日ATR × 13 + 当日TR] / 14
```
