# ATR Adaptive Threshold Algorithm

基于ATR（平均真实波幅）的自适应阈值算法，用于识别市场中低波动稳定期。

## 目录

- [算法概述](#算法概述)
- [安装](#安装)
- [快速开始](#快速开始)
- [核心函数](#核心函数)
- [算法详解](#算法详解)
- [参数说明](#参数说明)
- [返回值结构](#返回值结构)
- [完整示例](#完整示例)
- [测试运行](#测试运行)
- [算法原理](#算法原理)
- [参数调优建议](#参数调优建议)

---

## 算法概述

本算法通过分析ATR时间序列的变异系数（CV），动态识别市场的低波动稳定期。

**核心特点：**
- 自适应阈值：根据历史数据动态调整，非固定阈值
- 百分位逻辑：使用30%分位数识别"低波动"时期
- 避免未来数据泄露：只使用历史数据计算
- 渐进式计算：数据不足时使用保守估计

---

## 安装

确保Python环境已安装以下依赖：

```bash
pip install pandas numpy
```

导入模块：

```python
from PatternAnalysis.strategy.ATR import (
    detect_stable_periods_adaptive,
    analyze_stable_periods,
    StablePeriod
)
```

---

## 快速开始

```python
import pandas as pd
import numpy as np
from PatternAnalysis.strategy.ATR import detect_stable_periods_adaptive

# 准备ATR数据
dates = pd.date_range('2024-01-01', periods=300, freq='B')
np.random.seed(42)
atr_values = 2.0 + np.random.normal(0, 0.1, 300)  # 模拟ATR数据
atr_series = pd.Series(atr_values, index=dates)

# 运行检测
stable_periods, threshold_series = detect_stable_periods_adaptive(
    atr_series=atr_series,
    window=20,
    percentile_threshold=30,
    min_stable_days=5,
    lookback_period=241
)

# 查看结果
print(f"检测到 {len(stable_periods)} 个稳定期")
for period in stable_periods:
    print(f"  {period.start_date.date()} ~ {period.end_date.date()}: {period.duration_days}天")
```

---

## 核心函数

### 1. detect_stable_periods_adaptive

主检测函数，识别ATR序列中的稳定期。

```python
stable_periods, threshold_series = detect_stable_periods_adaptive(
    atr_series,
    window=20,
    percentile_threshold=30,
    min_stable_days=5,
    lookback_period=241,
    default_threshold=0.03
)
```

### 2. analyze_stable_periods

综合分析函数，返回更详细的统计信息。

```python
results = analyze_stable_periods(
    atr_series,
    window=20,
    percentile_threshold=30,
    min_stable_days=5,
    lookback_period=241
)

# 返回结果包含：
# - stable_periods: 稳定期列表
# - threshold_series: 动态阈值序列
# - cv_series: CV序列
# - summary: 汇总统计
```

### 3. StablePeriod

稳定期数据结构，包含以下属性：

| 属性 | 类型 | 说明 |
|------|------|------|
| `start_date` | pd.Timestamp | 稳定期开始日期 |
| `end_date` | pd.Timestamp | 稳定期结束日期 |
| `duration_days` | int | 持续天数 |
| `avg_atr` | float | 期间平均ATR |
| `atr_cv` | float | 期间变异系数 |
| `threshold_used` | float | 使用的阈值 |
| `stability_score` | float | 稳定性评分 (0-1) |

---

## 算法详解

### 步骤1：计算变异系数（CV）

```
rolling_mean = ATR.rolling(window).mean()
rolling_std = ATR.rolling(window).std()
CV = rolling_std / rolling_mean
```

CV值越小，表示ATR波动越稳定。

### 步骤2：动态阈值计算

对于每个时间点：
- **数据不足期（< lookback_period天）**：使用已有的历史CV数据计算百分位数
- **正常期（≥ lookback_period天）**：使用过去252/241天的滚动窗口CV数据

```python
threshold = np.percentile(history_cv, percentile_threshold)
```

### 步骤3：稳定期识别

当 `CV < 动态阈值` 时，标记为稳定日。连续稳定日（≥ min_stable_days）构成一个稳定期。

---

## 参数说明

| 参数 | 默认值 | 范围 | 说明 |
|------|--------|------|------|
| `atr_series` | 必填 | - | ATR时间序列（带DatetimeIndex的pandas Series） |
| `window` | 20 | ≥2 | 计算CV的滚动窗口大小（天数） |
| `percentile_threshold` | 30 | 0-100 | 百分位阈值（30%分位数=低波动期） |
| `min_stable_days` | 5 | ≥1 | 最少连续稳定天数 |
| `lookback_period` | 241 | ≥window | 历史数据回溯期（交易日） |
| `default_threshold` | 0.03 | >0 | 数据不足时的默认阈值 |

---

## 返回值结构

### stable_periods（稳定期列表）

```python
[
    {
        'start_date': Timestamp('2024-01-15 00:00:00'),
        'end_date': Timestamp('2024-02-10 00:00:00'),
        'duration_days': 26,
        'avg_atr': 1.85,
        'atr_cv': 0.045,        # 4.5%波动率
        'threshold_used': 0.052, # 阈值5.2%
        'stability_score': 0.955 # 稳定性评分
    },
    # ... 更多稳定期
]
```

### threshold_series（动态阈值序列）

```python
Date
2024-01-02    0.051
2024-01-03    0.050
2024-01-04    0.052
2024-01-05    0.049
...
Name: threshold, dtype: float64
```

---

## 完整示例

### 示例1：基础使用

```python
import pandas as pd
import numpy as np
from PatternAnalysis.strategy.ATR import detect_stable_periods_adaptive

# 生成测试数据
dates = pd.date_range('2024-01-01', periods=500, freq='B')
np.random.seed(42)
base_atr = 2.0
atr = pd.Series(base_atr + np.random.normal(0, 0.1, 500), index=dates)

# 检测稳定期
periods, thresholds = detect_stable_periods_adaptive(
    atr_series=atr,
    window=20,
    percentile_threshold=30,
    min_stable_days=5,
    lookback_period=241
)

# 分析结果
print(f"检测到 {len(periods)} 个稳定期")
for i, p in enumerate(periods, 1):
    print(f"\n稳定期 {i}:")
    print(f"  时间段: {p.start_date.date()} ~ {p.end_date.date()}")
    print(f"  持续天数: {p.duration_days} 天")
    print(f"  平均ATR: {p.avg_atr:.3f}")
    print(f"  波动率(CV): {p.atr_cv*100:.2f}%")
    print(f"  稳定性评分: {p.stability_score:.3f}")
```

### 示例2：综合分析

```python
from PatternAnalysis.strategy.ATR import analyze_stable_periods

# 运行综合分析
results = analyze_stable_periods(
    atr_series=atr,
    window=20,
    percentile_threshold=30,
    min_stable_days=5,
    lookback_period=241
)

# 打印汇总统计
summary = results['summary']
print("=" * 50)
print("ATR分析汇总")
print("=" * 50)
print(f"总交易日: {summary['total_days']}")
print(f"稳定期数量: {summary['num_stable_periods']}")
print(f"稳定日总数: {summary['total_stable_days']}")
print(f"稳定日占比: {summary['stable_day_ratio']*100:.2f}%")
print(f"平均ATR: {summary['avg_atr']:.4f}")
print(f"平均CV: {summary['avg_cv']*100:.4f}%")
print(f"平均阈值: {summary['avg_threshold']*100:.4f}%")
```

### 示例3：可视化

```python
import matplotlib.pyplot as plt

# 假设已获取结果
# periods, thresholds = detect_stable_periods_adaptive(atr)

fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

# 图1: ATR与稳定期
axes[0].plot(atr.index, atr.values, label='ATR', alpha=0.7)
for p in periods:
    axes[0].axvspan(p.start_date, p.end_date, alpha=0.2, color='green')
axes[0].set_ylabel('ATR值')
axes[0].set_title('ATR与稳定期')
axes[0].legend()

# 图2: 动态阈值
axes[1].plot(thresholds.index, thresholds.values, label='阈值', color='orange')
axes[1].set_ylabel('CV阈值')
axes[1].set_title('动态阈值')
axes[1].legend()

# 图3: CV与阈值对比
cv = atr.rolling(20).std() / atr.rolling(20).mean()
axes[2].plot(cv.index, cv.values, label='CV', alpha=0.7)
axes[2].plot(thresholds.index, thresholds.values, label='阈值', color='orange')
axes[2].set_ylabel('CV')
axes[2].set_xlabel('日期')
axes[2].set_title('CV vs 阈值')
axes[2].legend()

plt.tight_layout()
plt.show()
```

---

## 测试运行

运行测试脚本：

```bash
python "PatternAnalysis/strategy/ATR/run_test.py"
```

运行完整测试套件：

```python
from PatternAnalysis.strategy.ATR.test_adaptive_threshold import *

# 运行所有测试
run_basic_test()
run_comprehensive_analysis()
test_parameter_sensitivity()
test_edge_cases()
```

---

## 算法原理

### 变异系数（CV）说明

CV = 标准差 / 均值

- CV < 0.05：非常稳定
- 0.05 ≤ CV < 0.10：一般稳定
- CV ≥ 0.10：波动较大

### 百分位阈值逻辑

使用30%分位数意味着：
- 如果当天CV值低于历史30%的CV值，标记为"低波动"
- 这保证了在任何市场环境中，约30%的时间会被识别为"稳定"

### 自适应机制

```
低波动市场 → 历史CV普遍较低 → 阈值自动降低（更严格）
高波动市场 → 历史CV普遍较高 → 阈值自动升高（更宽松）
```

---

## 参数调优建议

### 不同市场环境的建议参数

| 市场环境 | percentile_threshold | min_stable_days | lookback_period |
|----------|---------------------|------------------|------------------|
| 正常市场 | 30 | 5 | 241 |
| 高波动市场 | 40 | 7 | 252 |
| 低波动市场 | 25 | 3 | 200 |
| 保守策略 | 20 | 10 | 252 |

### 敏感性分析

```python
from PatternAnalysis.strategy.ATR import detect_stable_periods_adaptive

atr_series = ...

# 测试不同百分位阈值
for threshold in [20, 30, 40, 50]:
    periods, _ = detect_stable_periods_adaptive(
        atr_series, percentile_threshold=threshold
    )
    total_days = sum(p.duration_days for p in periods)
    print(f"阈值{threshold}%: {len(periods)}个稳定期, 共{total_days}天")
```

---

## 文件结构

```
PatternAnalysis/strategy/ATR/
├── __init__.py              # 包初始化，导出主要接口
├── adaptive_threshold.py    # 核心算法实现
├── README.md                # 本文档
├── run_test.py              # 快速测试脚本
└── test_adaptive_threshold.py # 完整测试套件
```

---

## 依赖

- Python 3.8+
- pandas >= 1.3.0
- numpy >= 1.20.0

---

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0.0 | 2026-02-18 | 初始版本 |

---

## License

MIT License
