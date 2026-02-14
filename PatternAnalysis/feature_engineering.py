"""
股票形态分析系统 - 特征工程
技术指标计算与形态编码
"""
import numpy as np
import pandas as pd
from typing import Optional, Tuple, List, Dict
from datetime import date
from .config import TECHNICAL_INDICATORS


def calculate_ma(df: pd.DataFrame, periods: List[int] = None) -> pd.DataFrame:
    """
    计算移动平均线
    
    Args:
        df: K线数据DataFrame，需包含 'close' 列
        periods: 周期列表
    
    Returns:
        包含各周期MA的DataFrame
    """
    if df is None or df.empty or 'close' not in df.columns:
        return df.copy() if df is not None else pd.DataFrame()
    
    periods = periods or TECHNICAL_INDICATORS["ma_periods"]
    result = df.copy()
    
    for period in periods:
        result[f'ma_{period}'] = df['close'].rolling(window=period).mean()
    
    return result


def calculate_ema(df: pd.DataFrame, periods: List[int] = None) -> pd.DataFrame:
    """
    计算指数移动平均线
    
    Args:
        df: K线数据DataFrame
        periods: 周期列表
    
    Returns:
        包含各周期EMA的DataFrame
    """
    if df is None or df.empty or 'close' not in df.columns:
        return df.copy() if df is not None else pd.DataFrame()
    
    periods = periods or [12, 26]
    result = df.copy()
    
    for period in periods:
        result[f'ema_{period}'] = df['close'].ewm(span=period, adjust=False).mean()
    
    return result


def calculate_macd(
    df: pd.DataFrame, 
    fast: int = None, 
    slow: int = None, 
    signal: int = None
) -> pd.DataFrame:
    """
    计算MACD指标
    
    Args:
        df: K线数据DataFrame
        fast: 快线周期
        slow: 慢线周期
        signal: 信号线周期
    
    Returns:
        包含MACD指标的DataFrame
    """
    params = TECHNICAL_INDICATORS["macd_params"]
    fast = fast or params["fast"]
    slow = slow or params["slow"]
    signal = signal or params["signal"]
    
    if df is None or df.empty or 'close' not in df.columns:
        return df.copy() if df is not None else pd.DataFrame()
    
    result = df.copy()
    
    # 计算EMA
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    
    # DIF (MACD快线)
    result['dif'] = ema_fast - ema_slow
    
    # DEA (MACD慢线/信号线)
    result['dea'] = result['dif'].ewm(span=signal, adjust=False).mean()
    
    # MACD柱状图
    result['macd_hist'] = (result['dif'] - result['dea']) * 2
    
    return result


def calculate_bollinger_bands(
    df: pd.DataFrame, 
    window: int = None, 
    num_std: float = None
) -> pd.DataFrame:
    """
    计算布林带
    
    Args:
        df: K线数据DataFrame
        window: 窗口大小
        num_std: 标准差倍数
    
    Returns:
        包含布林带的DataFrame
    """
    params = TECHNICAL_INDICATORS["bollinger_params"]
    window = window or params["window"]
    num_std = num_std or params["num_std"]
    
    if df is None or df.empty or 'close' not in df.columns:
        return df.copy() if df is not None else pd.DataFrame()
    
    result = df.copy()
    
    rolling_mean = df['close'].rolling(window=window).mean()
    rolling_std = df['close'].rolling(window=window).std()
    
    result['bb_middle'] = rolling_mean
    result['bb_upper'] = rolling_mean + (rolling_std * num_std)
    result['bb_lower'] = rolling_mean - (rolling_std * num_std)
    result['bb_width'] = (result['bb_upper'] - result['bb_lower']) / rolling_mean
    result['bb_position'] = (df['close'] - result['bb_lower']) / (
        result['bb_upper'] - result['bb_lower']
    )
    
    return result


def calculate_rsi(df: pd.DataFrame, period: int = None) -> pd.DataFrame:
    """
    计算RSI指标
    
    Args:
        df: K线数据DataFrame
        period: RSI周期
    
    Returns:
        包含RSI的DataFrame
    """
    period = period or TECHNICAL_INDICATORS["rsi_period"]
    
    if df is None or df.empty or 'close' not in df.columns:
        return df.copy() if df is not None else pd.DataFrame()
    
    result = df.copy()
    
    # 计算价格变化
    delta = df['close'].diff()
    
    # 上涨和下跌
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    
    # 计算平均收益和损失
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    # RS和RSI
    rs = avg_gain / avg_loss
    result['rsi'] = 100 - (100 / (1 + rs))
    
    return result


def calculate_atr(df: pd.DataFrame, period: int = None) -> pd.DataFrame:
    """
    计算ATR指标（真实波幅平均值）
    
    Args:
        df: K线数据DataFrame，需包含 'high', 'low', 'close' 列
        period: ATR周期
    
    Returns:
        包含ATR的DataFrame
    """
    period = period or TECHNICAL_INDICATORS["atr_period"]
    
    if df is None or df.empty:
        return df.copy() if df is not None else pd.DataFrame()
    
    result = df.copy()
    
    # 计算真实波幅
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    
    # 计算ATR
    result['atr'] = tr.rolling(window=period).mean()
    result['tr'] = tr
    
    return result


def calculate_volatility(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """
    计算波动率
    
    Args:
        df: K线数据DataFrame
        window: 窗口大小
    
    Returns:
        包含波动率的DataFrame
    """
    if df is None or df.empty or 'close' not in df.columns:
        return df.copy() if df is not None else pd.DataFrame()
    
    result = df.copy()
    
    returns = df['close'].pct_change()
    result['volatility'] = returns.rolling(window=window).std() * np.sqrt(252)
    
    return result


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算所有技术指标
    
    Args:
        df: K线数据DataFrame
    
    Returns:
        包含所有技术指标的DataFrame
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    result = df.copy()
    
    # 依次计算各指标
    result = calculate_ma(result)
    result = calculate_ema(result)
    result = calculate_macd(result)
    result = calculate_bollinger_bands(result)
    result = calculate_rsi(result)
    result = calculate_atr(result)
    result = calculate_volatility(result)
    
    return result


def extract_local_extrema(
    closes: np.ndarray, 
    window: int = 5
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    提取局部极值点（峰谷）
    
    Args:
        closes: 收盘价序列
        window: 局部极值检测窗口
    
    Returns:
        (peaks_idx, valleys_idx, peaks, valleys)
    """
    from scipy.signal import argrelextrema
    
    # 找局部极大值（峰）
    peak_indices = argrelextrema(closes, np.greater, order=window)[0]
    peaks = closes[peak_indices]
    
    # 找局部极小值（谷）
    valley_indices = argrelextrema(closes, np.less, order=window)[0]
    valleys = closes[valley_indices]
    
    return peak_indices, valley_indices, peaks, valleys


def calculate_trend_slope(closes: np.ndarray) -> float:
    """
    计算价格趋势斜率
    
    Args:
        closes: 收盘价序列
    
    Returns:
        线性回归斜率
    """
    if len(closes) < 2:
        return 0.0
    
    x = np.arange(len(closes))
    A = np.vstack([x, np.ones(len(x))]).T
    slope, _ = np.linalg.lstsq(A, closes, rcond=None)[0]
    
    # 归一化斜率
    normalized_slope = slope / np.mean(closes)
    
    return float(normalized_slope)


def encode_pattern_features(df: pd.DataFrame) -> np.ndarray:
    """
    将K线数据编码为模型输入特征
    
    Args:
        df: K线数据DataFrame
    
    Returns:
        特征向量
    """
    if df is None or df.empty or len(df) < 20:
        return np.zeros(100)  # 返回零向量
    
    # 计算技术指标
    df_indicators = calculate_all_indicators(df)
    
    # 提取价格序列
    closes = df['close'].values.astype(float)
    highs = df['high'].values.astype(float)
    lows = df['low'].values.astype(float)
    volumes = df['vol'].values.astype(float) if 'vol' in df.columns else np.zeros(len(closes))
    
    # 标准化价格序列
    closes_norm = (closes - closes.min()) / (closes.max() - closes.min() + 1e-8)
    
    # 提取局部极值
    peak_idx, valley_idx, peaks, valleys = extract_local_extrema(closes, window=5)
    
    # 趋势特征
    trend_slope = calculate_trend_slope(closes)
    
    # 波动特征
    volatility = np.std(closes) / (np.mean(closes) + 1e-8)
    price_range = (closes.max() - closes.min()) / (np.mean(closes) + 1e-8)
    
    # 技术指标特征
    latest_ma = []
    for period in [5, 10, 20, 60]:
        if f'ma_{period}' in df_indicators.columns:
            latest_ma.append(df_indicators[f'ma_{period}'].iloc[-1])
        else:
            latest_ma.append(0)
    
    latest_rsi = df_indicators['rsi'].iloc[-1] if 'rsi' in df_indicators.columns else 50
    latest_macd = df_indicators['macd_hist'].iloc[-1] if 'macd_hist' in df_indicators.columns else 0
    
    # 构建特征向量 (100维)
    features = np.zeros(100)
    
    # 价格序列 (0-59)
    seq_length = min(60, len(closes_norm))
    features[:seq_length] = closes_norm[-seq_length:]
    
    # 局部极值 (60-69)
    if len(peak_idx) > 0:
        features[60] = len(peak_idx) / 10  # 峰数量
        features[61] = peaks.max() / (closes.max() + 1e-8) if len(peaks) > 0 else 0
    if len(valley_idx) > 0:
        features[62] = len(valley_idx) / 10  # 谷数量
        features[63] = valleys.min() / (closes.min() + 1e-8) if len(valleys) > 0 else 0
    
    # 趋势和波动 (64-73)
    features[64] = trend_slope * 100  # 趋势斜率
    features[65] = volatility  # 波动率
    features[66] = price_range  # 价格振幅
    
    # 技术指标 (74-89)
    features[74:78] = np.array(latest_ma) / (closes[-1] + 1e-8)
    features[78] = latest_rsi / 100  # RSI
    features[79] = (latest_macd / (closes[-1] + 1e-8)) * 10  # MACD柱状图
    
    # 成交量特征 (90-99)
    if len(volumes) > 0:
        vol_norm = (volumes - volumes.min()) / (volumes.max() - volumes.min() + 1e-8)
        vol_length = min(10, len(vol_norm))
        features[90:90+vol_length] = vol_norm[-vol_length:]
    
    return features.astype(np.float32)


class FeatureEngineer:
    """特征工程类"""
    
    def __init__(self):
        self.indicators_config = TECHNICAL_INDICATORS
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算所有技术指标"""
        return calculate_all_indicators(df)
    
    def encode_features(self, df: pd.DataFrame) -> np.ndarray:
        """编码特征向量"""
        return encode_pattern_features(df)
    
    def get_local_extrema(
        self, 
        df: pd.DataFrame, 
        window: int = 5
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """获取局部极值"""
        closes = df['close'].values.astype(float)
        return extract_local_extrema(closes, window)
    
    def get_trend_slope(self, df: pd.DataFrame) -> float:
        """获取趋势斜率"""
        closes = df['close'].values.astype(float)
        return calculate_trend_slope(closes)
