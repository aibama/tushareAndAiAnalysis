"""
股票形态分析系统 - 形态分类模型
支持规则版和AI模型版
"""
from enum import IntEnum
import numpy as np
import pandas as pd
from typing import Literal, Optional, Tuple
from scipy.signal import argrelextrema
from dataclasses import dataclass

from .config import PATTERN_CONFIG, MODEL_CONFIG


class PatternType(IntEnum):
    """形态分类枚举"""
    SINGLE_UP = 1        # 单边上涨
    SINGLE_DOWN = 2      # 单边下跌
    ASC_TRIANGLE = 3     # 上升三角形
    DESC_TRIANGLE = 4    # 下降三角形
    SYM_TRIANGLE = 5     # 对称三角形
    CUP_HANDLE = 6      # 杯状带柄
    HEAD_SHOULDER_TOP = 7   # 头肩顶
    HEAD_SHOULDER_BOTTOM = 8 # 头肩底
    ROUND_TOP = 9        # 圆弧顶
    ROUND_BOTTOM = 10    # 圆弧底
    ASC_WEDGE = 12       # 上升楔形
    DESC_WEDGE = 13      # 下降楔形
    RECTANGLE = 14       # 矩形（箱体）
    OTHER = 11           # 其他形态


PATTERN_NAME_MAP = {
    PatternType.SINGLE_UP: "单边上涨",
    PatternType.SINGLE_DOWN: "单边下跌",
    PatternType.ASC_TRIANGLE: "上升三角形",
    PatternType.DESC_TRIANGLE: "下降三角形",
    PatternType.SYM_TRIANGLE: "对称三角形",
    PatternType.CUP_HANDLE: "杯状带柄",
    PatternType.HEAD_SHOULDER_TOP: "头肩顶",
    PatternType.HEAD_SHOULDER_BOTTOM: "头肩底",
    PatternType.ROUND_TOP: "圆弧顶",
    PatternType.ROUND_BOTTOM: "圆弧底",
    PatternType.ASC_WEDGE: "上升楔形",
    PatternType.DESC_WEDGE: "下降楔形",
    PatternType.RECTANGLE: "矩形（箱体）",
    PatternType.OTHER: "其他形态",
}


@dataclass
class PatternFeatures:
    """形态特征数据类"""
    trend_slope: float
    volatility: float
    price_range: float
    peak_count: int
    valley_count: int
    peak_ratio: float
    valley_ratio: float
    symmetry_score: float
    consolidation_ratio: float


def extract_features(df: pd.DataFrame) -> PatternFeatures:
    """提取形态特征"""
    if df is None or df.empty or len(df) < 10:
        return None
    
    closes = df['close'].values.astype(float)
    highs = df['high'].values.astype(float)
    lows = df['low'].values.astype(float)
    
    # 基本统计
    mean_close = np.mean(closes)
    std_close = np.std(closes)
    
    # 趋势斜率
    x = np.arange(len(closes))
    slope, _ = np.linalg.lstsq(np.vstack([x, np.ones(len(x))]).T, closes, rcond=None)[0]
    trend_slope = slope / (mean_close + 1e-8)
    
    # 波动率
    volatility = std_close / (mean_close + 1e-8)
    
    # 价格振幅
    price_range = (closes.max() - closes.min()) / (mean_close + 1e-8)
    
    # 局部极值
    window = max(3, len(closes) // 20)
    peak_indices = argrelextrema(closes, np.greater, order=window)[0]
    valley_indices = argrelextrema(closes, np.less, order=window)[0]
    
    peak_count = len(peak_indices)
    valley_count = len(valley_indices)
    
    peak_ratio = (closes[peak_indices].max() / (mean_close + 1e-8)) if len(peak_indices) > 0 else 0
    valley_ratio = (closes[valley_indices].min() / (mean_close + 1e-8)) if len(valley_indices) > 0 else 0
    
    # 对称性评分
    first_half = closes[:len(closes)//2]
    second_half = closes[len(closes)//2:]
    symmetry_score = 1 - abs(np.mean(first_half) - np.mean(second_half)) / (mean_close + 1e-8)
    
    # 整理度（价格波动相对于趋势的比例）
    detrended = closes - (slope * x + closes[0])
    consolidation_ratio = 1 - (np.std(detrended) / (std_close + 1e-8))
    
    return PatternFeatures(
        trend_slope=trend_slope,
        volatility=volatility,
        price_range=price_range,
        peak_count=peak_count,
        valley_count=valley_count,
        peak_ratio=peak_ratio,
        valley_ratio=valley_ratio,
        symmetry_score=symmetry_score,
        consolidation_ratio=consolidation_ratio
    )


def detect_single_trend(df: pd.DataFrame, features: PatternFeatures) -> Optional[PatternType]:
    """检测单边趋势（优化版，更容易识别明显的单边上涨/下跌）"""
    if features is None or df is None or df.empty:
        return None
    
    closes = df['close'].values.astype(float)
    highs = df['high'].values.astype(float)
    lows = df['low'].values.astype(float)
    n = len(closes)
    
    # 计算整体涨跌幅
    total_return = (closes[-1] - closes[0]) / closes[0]
    
    # 计算最大回撤（从最高点到最低点的跌幅）
    max_price = closes.max()
    min_price = closes.min()
    max_drawdown = (max_price - min_price) / max_price if max_price > 0 else 0
    
    # 计算上涨趋势的持续性（上涨天数占比）
    up_days = np.sum(np.diff(closes) > 0)
    up_ratio = up_days / (n - 1) if n > 1 else 0
    
    # 计算趋势的线性度（R²值）
    x = np.arange(n)
    slope, intercept = np.polyfit(x, closes, 1)
    y_pred = slope * x + intercept
    ss_res = np.sum((closes - y_pred) ** 2)
    ss_tot = np.sum((closes - np.mean(closes)) ** 2)
    r_squared = 1 - (ss_res / (ss_tot + 1e-8))
    
    # 计算斜率（归一化）
    normalized_slope = slope / (np.mean(closes) + 1e-8)
    
    # 计算最近一段时间的趋势强度（避免早期波动影响判断）
    recent_ratio = 0.3  # 最近30%的数据
    recent_start = int(n * (1 - recent_ratio))
    recent_closes = closes[recent_start:]
    recent_return = (recent_closes[-1] - recent_closes[0]) / recent_closes[0] if len(recent_closes) > 1 else 0
    
    # 单边上涨判断条件（大幅降低阈值，更容易识别）
    # 策略1：明显上涨（涨幅>8%，斜率>2%，回撤<50%）
    condition1 = (
        total_return > 0.08 and  # 整体涨幅>8%（降低阈值）
        normalized_slope > 0.02 and  # 趋势斜率>2%（降低阈值）
        max_drawdown < 0.50 and  # 最大回撤<50%
        up_ratio > 0.45  # 上涨天数>45%
    )
    
    # 策略2：涨幅较大（>15%），即使波动稍大也认为是单边上涨
    condition2 = (
        total_return > 0.15 and  # 整体涨幅>15%
        normalized_slope > 0.015 and  # 趋势斜率>1.5%
        up_ratio > 0.40  # 上涨天数>40%
    )
    
    # 策略3：最近强势上涨（最近30%数据涨幅>10%），整体趋势向上
    condition3 = (
        recent_return > 0.10 and  # 最近涨幅>10%
        total_return > 0.05 and  # 整体涨幅>5%
        normalized_slope > 0.01 and  # 趋势斜率>1%
        up_ratio > 0.45  # 上涨天数>45%
    )
    
    # 策略4：极强上涨（涨幅>25%），即使回撤较大也认为是单边上涨
    condition4 = (
        total_return > 0.25 and  # 整体涨幅>25%
        normalized_slope > 0.01 and  # 趋势斜率>1%
        up_ratio > 0.35  # 上涨天数>35%
    )
    
    if condition1 or condition2 or condition3 or condition4:
        return PatternType.SINGLE_UP
    
    # 单边下跌判断条件（同样降低阈值）
    # 策略1：明显下跌
    down_condition1 = (
        total_return < -0.08 and  # 整体跌幅>8%
        normalized_slope < -0.02 and  # 趋势斜率<-2%
        max_drawdown < 0.50 and  # 最大回撤<50%
        up_ratio < 0.45  # 上涨天数<45%
    )
    
    # 策略2：跌幅较大
    down_condition2 = (
        total_return < -0.15 and  # 整体跌幅>15%
        normalized_slope < -0.015 and  # 趋势斜率<-1.5%
        up_ratio < 0.40  # 上涨天数<40%
    )
    
    if down_condition1 or down_condition2:
        return PatternType.SINGLE_DOWN
    
    return None


def detect_triangle(
    df: pd.DataFrame, 
    features: PatternFeatures
) -> Optional[PatternType]:
    """检测三角形形态（更严格地排除单边趋势）"""
    if features is None or df is None or df.empty:
        return None
    
    closes = df['close'].values.astype(float)
    highs = df['high'].values.astype(float)
    lows = df['low'].values.astype(float)
    n = len(closes)
    
    # 先检查是否是明显的单边趋势，如果是则不是三角形
    total_return = (closes[-1] - closes[0]) / closes[0]
    x = np.arange(n)
    slope, _ = np.polyfit(x, closes, 1)
    normalized_slope = slope / (np.mean(closes) + 1e-8)
    
    # 更严格地排除单边趋势：如果整体涨跌幅>8%且斜率明显，不是三角形
    if abs(total_return) > 0.08 and abs(normalized_slope) > 0.015:
        # 明显的单边趋势，不是三角形
        return None
    
    # 计算上涨天数占比，如果>55%或<45%，可能是单边趋势
    up_days = np.sum(np.diff(closes) > 0)
    up_ratio = up_days / (n - 1) if n > 1 else 0.5
    if up_ratio > 0.55 or up_ratio < 0.45:
        # 偏向单边，不太可能是三角形
        return None
    
    # 拟合高低点趋势线
    x = np.arange(len(highs))
    
    # 高点趋势
    high_fit = np.polyfit(x, highs, 1)
    high_slope = high_fit[0] / (np.mean(highs) + 1e-8)
    
    # 低点趋势
    low_fit = np.polyfit(x, lows, 1)
    low_slope = low_fit[0] / (np.mean(lows) + 1e-8)
    
    # 计算高低点收敛程度（三角形的重要特征）
    # 如果高低点差距在缩小，可能是三角形
    first_third_high = np.mean(highs[:int(len(highs)/3)])
    last_third_high = np.mean(highs[-int(len(highs)/3):])
    first_third_low = np.mean(lows[:int(len(lows)/3)])
    last_third_low = np.mean(lows[-int(len(lows)/3):])
    
    early_range = first_third_high - first_third_low
    late_range = last_third_high - last_third_low
    convergence_ratio = (early_range - late_range) / (early_range + 1e-8)
    
    # 三角形需要明显的收敛（收敛度>20%）
    if convergence_ratio < 0.20:
        return None
    
    # 判断三角形类型
    if (abs(high_slope) < 0.03 and low_slope > 0.02 and convergence_ratio > 0.20):
        # 高点走平，低点上升，有明显收敛 - 上升三角形
        return PatternType.ASC_TRIANGLE
    
    if (high_slope < -0.02 and abs(low_slope) < 0.03 and convergence_ratio > 0.20):
        # 高点下降，低点走平，有明显收敛 - 下降三角形
        return PatternType.DESC_TRIANGLE
    
    if (abs(high_slope) < 0.03 and abs(low_slope) < 0.03 and convergence_ratio > 0.20):
        # 两者都走平，有明显收敛 - 对称三角形
        return PatternType.SYM_TRIANGLE
    
    return None


def detect_cup_handle(df: pd.DataFrame, features: PatternFeatures) -> Optional[PatternType]:
    """检测杯柄形态"""
    if features is None or df is None or df.empty:
        return None
    
    closes = df['close'].values.astype(float)
    n = len(closes)
    
    if n < 40:  # 需要足够的数据
        return None
    
    # 找到最高点位置
    max_idx = np.argmax(closes)
    
    if max_idx < int(n * 0.3) or max_idx > int(n * 0.6):
        return None  # 杯顶位置应该在前期
    
    # 检查杯子部分（左侧下跌+右侧上涨）
    cup_start = 0
    cup_end = int(max(n * 0.7, max_idx + n // 10))
    
    cup_closes = closes[cup_start:cup_end]
    cup_max = cup_closes.max()
    cup_min = cup_closes.min()
    
    # 杯子深度
    cup_depth = (cup_max - cup_min) / (cup_max + 1e-8)
    
    if cup_depth < 0.15 or cup_depth > 0.5:
        return None
    
    # 杯柄部分（杯右侧的短暂回调）
    handle_start = int(cup_end)
    handle_end = min(n, handle_start + n // 8)
    
    if handle_end - handle_start < 5:
        return None
    
    handle_data = closes[handle_start:handle_end]
    handle_range = (handle_data.max() - handle_data.min()) / (cup_max + 1e-8)
    
    if handle_range < 0.02 or handle_range > 0.1:
        return None
    
    return PatternType.CUP_HANDLE


def detect_head_shoulder(
    df: pd.DataFrame, 
    features: PatternFeatures
) -> Optional[PatternType]:
    """检测头肩形态"""
    if features is None or df is None or df.empty:
        return None
    
    closes = df['close'].values.astype(float)
    n = len(closes)
    
    if n < 30:
        return None
    
    # 找局部极值
    window = max(3, n // 15)
    peak_indices = argrelextrema(closes, np.greater, order=window)[0]
    valley_indices = argrelextrema(closes, np.less, order=window)[0]
    
    if len(peak_indices) < 3 or len(valley_indices) < 2:
        return None
    
    # 头肩顶：左肩 -> 头 -> 右肩，中间有谷
    peaks = closes[peak_indices]
    peak_times = peak_indices
    
    if len(peaks) >= 3:
        # 检查是否有中间最高的三个峰
        sorted_peak_idx = np.argsort(peaks)[::-1][:3]
        
        if (peak_times[sorted_peak_idx[0]] > peak_times[sorted_peak_idx[1]] and
            peak_times[sorted_peak_idx[1]] > peak_times[sorted_peak_idx[2]]):
            # 中间的峰最高，是头肩顶
            return PatternType.HEAD_SHOULDER_TOP
    
    # 头肩底：左肩 -> 头 -> 右肩，中间有峰
    valleys = closes[valley_indices]
    valley_times = valley_indices
    
    if len(valleys) >= 3:
        sorted_valley_idx = np.argsort(valleys)[:3]
        
        if (valley_times[sorted_valley_idx[0]] > valley_times[sorted_valley_idx[1]] and
            valley_times[sorted_valley_idx[1]] > valley_times[sorted_valley_idx[2]]):
            # 中间的谷最低，是头肩底
            return PatternType.HEAD_SHOULDER_BOTTOM
    
    return None


def detect_round_pattern(
    df: pd.DataFrame, 
    features: PatternFeatures
) -> Optional[PatternType]:
    """检测圆弧形态"""
    if features is None or df is None or df.empty:
        return None
    
    closes = df['close'].values.astype(float)
    n = len(closes)
    
    if n < 30:
        return None
    
    # 圆弧形态应该有较低的波动率和逐渐变化的趋势
    if features.volatility > 0.2:
        return None
    
    # 拟合二次曲线检测弧形
    x = np.arange(n)
    coeffs = np.polyfit(x, closes, 2)
    
    # 二次项系数
    quad_coeff = coeffs[0]
    normalized_quad = quad_coeff / (np.mean(closes) + 1e-8) * n * n
    
    if normalized_quad < -0.001:
        # 向下开口的抛物线 - 圆弧顶
        if features.symmetry_score > 0.8:
            return PatternType.ROUND_TOP
    
    if normalized_quad > 0.001:
        # 向上开口的抛物线 - 圆弧底
        if features.symmetry_score > 0.8:
            return PatternType.ROUND_BOTTOM
    
    return None


def detect_wedge(df: pd.DataFrame, features: PatternFeatures) -> Optional[PatternType]:
    """检测楔形形态（上升楔形、下降楔形）"""
    if features is None or df is None or df.empty:
        return None
    
    closes = df['close'].values.astype(float)
    highs = df['high'].values.astype(float)
    lows = df['low'].values.astype(float)
    n = len(closes)
    
    if n < 20:
        return None
    
    # 拟合高低点趋势线
    x = np.arange(n)
    
    # 高点趋势
    high_fit = np.polyfit(x, highs, 1)
    high_slope = high_fit[0] / (np.mean(highs) + 1e-8)
    
    # 低点趋势
    low_fit = np.polyfit(x, lows, 1)
    low_slope = low_fit[0] / (np.mean(lows) + 1e-8)
    
    # 计算高低点收敛程度（楔形的重要特征：两条线都向同一方向倾斜但收敛）
    first_third_high = np.mean(highs[:int(n/3)])
    last_third_high = np.mean(highs[-int(n/3):])
    first_third_low = np.mean(lows[:int(n/3)])
    last_third_low = np.mean(lows[-int(n/3):])
    
    early_range = first_third_high - first_third_low
    late_range = last_third_high - last_third_low
    convergence_ratio = (early_range - late_range) / (early_range + 1e-8)
    
    # 楔形需要明显的收敛（收敛度>15%）
    if convergence_ratio < 0.15:
        return None
    
    # 上升楔形：两条线都向上倾斜，但高点斜率小于低点斜率（收敛）
    # 通常出现在上升趋势的末期，是看跌信号
    if (high_slope > 0.01 and low_slope > 0.01 and  # 都向上倾斜
        high_slope < low_slope and  # 高点斜率小于低点斜率（收敛）
        convergence_ratio > 0.15):
        return PatternType.ASC_WEDGE
    
    # 下降楔形：两条线都向下倾斜，但低点斜率大于高点斜率（收敛）
    # 通常出现在下降趋势的末期，是看涨信号
    if (high_slope < -0.01 and low_slope < -0.01 and  # 都向下倾斜
        abs(low_slope) < abs(high_slope) and  # 低点斜率绝对值小于高点斜率（收敛）
        convergence_ratio > 0.15):
        return PatternType.DESC_WEDGE
    
    return None


def detect_rectangle(df: pd.DataFrame, features: PatternFeatures) -> Optional[PatternType]:
    """检测矩形（箱体）形态"""
    if features is None or df is None or df.empty:
        return None
    
    closes = df['close'].values.astype(float)
    highs = df['high'].values.astype(float)
    lows = df['low'].values.astype(float)
    n = len(closes)
    
    if n < 20:
        return None
    
    # 矩形特征：价格在上下边界之间震荡，没有明显趋势
    # 1. 计算价格区间
    price_range = highs.max() - lows.min()
    mean_price = np.mean(closes)
    
    # 2. 计算上下边界（使用分位数）
    upper_bound = np.percentile(highs, 90)  # 90%分位数作为上边界
    lower_bound = np.percentile(lows, 10)    # 10%分位数作为下边界
    
    # 3. 计算价格在边界内的比例
    in_range_ratio = np.sum((closes >= lower_bound) & (closes <= upper_bound)) / n
    
    # 4. 计算趋势斜率（矩形应该斜率很小）
    x = np.arange(n)
    slope, _ = np.polyfit(x, closes, 1)
    normalized_slope = abs(slope / (mean_price + 1e-8))
    
    # 5. 计算波动率（矩形应该有稳定的波动）
    volatility = np.std(closes) / (mean_price + 1e-8)
    
    # 6. 计算高低点的变化趋势（应该都接近水平）
    high_fit = np.polyfit(x, highs, 1)
    low_fit = np.polyfit(x, lows, 1)
    high_slope = abs(high_fit[0] / (np.mean(highs) + 1e-8))
    low_slope = abs(low_fit[0] / (np.mean(lows) + 1e-8))
    
    # 矩形判断条件：
    # - 价格主要在上下边界内（>70%）
    # - 整体趋势斜率很小（<1%）
    # - 高低点趋势线都接近水平（斜率<1.5%）
    # - 波动率适中（0.05-0.25）
    # - 价格区间相对稳定
    if (in_range_ratio > 0.70 and  # 价格主要在边界内
        normalized_slope < 0.01 and  # 整体趋势斜率很小
        high_slope < 0.015 and  # 高点趋势接近水平
        low_slope < 0.015 and  # 低点趋势接近水平
        0.05 < volatility < 0.25):  # 波动率适中
        return PatternType.RECTANGLE
    
    return None


def simple_rule_pattern(df: pd.DataFrame) -> PatternType:
    """
    极简规则版形态分类
    
    Args:
        df: K线数据DataFrame，需包含 'close', 'high', 'low' 列
    
    Returns:
        PatternType: 分类结果
    """
    if df is None or df.empty:
        return PatternType.OTHER
    
    if len(df) < 20:
        return PatternType.OTHER
    
    # 提取特征
    features = extract_features(df)
    
    if features is None:
        return PatternType.OTHER
    
    # 1. 优先检测单边趋势（最重要，避免误判）
    single_trend = detect_single_trend(df, features)
    if single_trend:
        return single_trend
    
    # 2. 检测矩形（箱体）- 在三角形之前检测，因为矩形也可能有收敛特征
    rectangle = detect_rectangle(df, features)
    if rectangle:
        return rectangle
    
    # 3. 检测楔形 - 在三角形之前检测
    wedge = detect_wedge(df, features)
    if wedge:
        return wedge
    
    # 4. 检测三角形（需要排除明显的单边趋势）
    triangle = detect_triangle(df, features)
    if triangle:
        return triangle
    
    # 5. 检测杯柄
    cup_handle = detect_cup_handle(df, features)
    if cup_handle:
        return cup_handle
    
    # 6. 检测头肩
    head_shoulder = detect_head_shoulder(df, features)
    if head_shoulder:
        return head_shoulder
    
    # 7. 检测圆弧
    round_pattern = detect_round_pattern(df, features)
    if round_pattern:
        return round_pattern
    
    # 8. 其他形态
    return PatternType.OTHER


def classify_pattern(
    df: pd.DataFrame, 
    mode: Literal["rule", "ai"] = "rule"
) -> PatternType:
    """
    对给定周期的一只股票K线进行形态分类
    
    Args:
        df: K线数据DataFrame
        mode: 模式，"rule" 使用规则版，"ai" 使用AI模型
    
    Returns:
        PatternType: 分类结果
    """
    if mode == "rule":
        return simple_rule_pattern(df)
    else:
        # TODO: 加载AI模型进行推理
        # 暂时返回规则版结果作为占位
        return simple_rule_pattern(df)


def batch_classify(
    df_dict: dict,
    mode: Literal["rule", "ai"] = "rule"
) -> dict:
    """
    批量分类多只股票
    
    Args:
        df_dict: {ts_code: df} 字典
        mode: 分类模式
    
    Returns:
        {ts_code: (PatternType, features)} 字典
    """
    results = {}
    
    for ts_code, df in df_dict.items():
        pattern = classify_pattern(df, mode)
        features = extract_features(df)
        results[ts_code] = (pattern, features)
    
    return results


class PatternClassifier:
    """形态分类器类"""
    
    def __init__(self, mode: Literal["rule", "ai"] = "rule"):
        self.mode = mode
        self.pattern_type = PatternType
    
    def classify(self, df: pd.DataFrame) -> PatternType:
        """分类单只股票"""
        return classify_pattern(df, self.mode)
    
    def batch_classify(self, df_dict: dict) -> dict:
        """批量分类"""
        return batch_classify(df_dict, self.mode)
    
    def get_pattern_name(self, pattern: PatternType) -> str:
        """获取形态名称"""
        return PATTERN_NAME_MAP.get(pattern, "未知形态")
    
    def get_all_patterns(self) -> list:
        """获取所有形态类型"""
        return list(PatternType)
