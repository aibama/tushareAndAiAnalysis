"""
股票形态分析系统 - 涨跌幅计算
计算指定周期内的涨跌幅
"""
import pandas as pd
import numpy as np
from typing import Optional, Union, Tuple
from datetime import date
from .config import DRAWDOWN_REBOUND_CONFIG


def calc_period_return(df: pd.DataFrame) -> Optional[float]:
    """
    计算指定周期内的涨跌幅
    
    Args:
        df: 必须按 trade_date 升序排列的DataFrame，且包含 'close' 列
    
    Returns:
        涨跌幅（如 0.15 表示 15%），数据不足返回 None
    """
    if df is None or df.empty:
        return None
    
    if 'close' not in df.columns:
        return None
    
    # 去除NaN值
    closes = df['close'].dropna()
    
    if len(closes) < 2:
        return None
    
    first = closes.iloc[0]
    last = closes.iloc[-1]
    
    if first is None or last is None or first == 0 or np.isnan(first) or np.isnan(last):
        return None
    
    return float(last / first - 1.0)


def calc_period_return_pct(df: pd.DataFrame, decimals: int = 4) -> Optional[str]:
    """
    计算指定周期内的涨跌幅（百分比格式）
    
    Args:
        df: K线数据DataFrame
        decimals: 小数位数
    
    Returns:
        百分比字符串（如 "15.23%"），失败返回 None
    """
    ret = calc_period_return(df)
    if ret is None:
        return None
    return f"{ret * 100:.{decimals}2f}%"


def calc_max_drawdown(df: pd.DataFrame, window: int = None) -> Optional[float]:
    """
    计算最大回撤（使用滚动窗口）
    
    算法：
    1. 确定计算的时间窗口
    2. 计算滚动最高点：对于每个交易日，计算从窗口起始日到当前日的最高收盘价
    3. 计算回撤：(滚动最高点 - 当前收盘价) / 滚动最高点
    4. 最大回撤：在窗口内取所有回撤值的最大值
    
    Args:
        df: K线数据DataFrame，需包含 'close' 列
        window: 计算窗口大小（交易日），默认使用配置文件中的值
    
    Returns:
        最大回撤比例（负数），失败返回 None
    """
    if window is None:
        window = DRAWDOWN_REBOUND_CONFIG["window"]
    if df is None or df.empty or 'close' not in df.columns:
        return None
    
    closes = df['close'].dropna()
    if len(closes) < 2:
        return None
    
    # 计算滚动最高点（窗口内从起始到当前的最大值）
    rolling_max = closes.rolling(window, min_periods=1).max()
    
    # 计算每日回撤：(滚动最高点 - 当前收盘价) / 滚动最高点
    drawdown = (rolling_max - closes) / rolling_max
    
    # 计算窗口内的最大回撤
    max_dd = drawdown.rolling(window, min_periods=1).max()
    
    # 返回整体最大回撤
    result = max_dd.min()
    
    return float(result) if not pd.isna(result) else None


def calc_max_rebound(df: pd.DataFrame, window: int = None) -> Optional[float]:
    """
    计算最大反弹（使用滚动窗口）
    
    算法：
    1. 确定计算的时间窗口
    2. 计算滚动最低点：对于每个交易日，计算从窗口起始日到当前日的最低收盘价
    3. 计算反弹：(当前收盘价 - 滚动最低点) / 滚动最低点
    4. 最大反弹：在窗口内取所有反弹值的最大值
    
    Args:
        df: K线数据DataFrame，需包含 'close' 列
        window: 计算窗口大小（交易日），默认使用配置文件中的值
    
    Returns:
        最大反弹比例（正数），失败返回 None
    """
    if window is None:
        window = DRAWDOWN_REBOUND_CONFIG["window"]
    if df is None or df.empty or 'close' not in df.columns:
        return None
    
    closes = df['close'].dropna()
    if len(closes) < 2:
        return None
    
    # 计算滚动最低点（窗口内从起始到当前的最小值）
    rolling_min = closes.rolling(window, min_periods=1).min()
    
    # 计算每日反弹：(当前收盘价 - 滚动最低点) / 滚动最低点
    rebound = (closes - rolling_min) / rolling_min
    
    # 计算窗口内的最大反弹
    max_rb = rebound.rolling(window, min_periods=1).max()
    
    # 返回整体最大反弹
    result = max_rb.max()
    
    return float(result) if not pd.isna(result) else None


def calc_max_gain(df: pd.DataFrame) -> Optional[float]:
    """
    计算最大涨幅（从最低点到最高点）
    
    Args:
        df: K线数据DataFrame，需包含 'close' 列
    
    Returns:
        最大涨幅比例，失败返回 None
    """
    if df is None or df.empty or 'close' not in df.columns:
        return None
    
    closes = df['close'].dropna()
    if len(closes) < 2:
        return None
    
    min_price = closes.min()
    max_price = closes.max()
    
    if min_price == 0:
        return None
    
    return float((max_price - min_price) / min_price)


def calc_volatility(df: pd.DataFrame, window: int = 20) -> Optional[float]:
    """
    计算波动率（标准差）
    
    Args:
        df: K线数据DataFrame，需包含 'close' 列
        window: 计算窗口
    
    Returns:
        波动率，失败返回 None
    """
    if df is None or df.empty or 'close' not in df.columns:
        return None
    
    closes = df['close'].dropna()
    if len(closes) < window:
        return None
    
    returns = closes.pct_change().dropna()
    volatility = returns.std()
    
    return float(volatility)


def calc_sharpe_ratio(
    df: pd.DataFrame, 
    risk_free_rate: float = 0.03,
    trading_days: int = 252
) -> Optional[float]:
    """
    计算夏普比率
    
    Args:
        df: K线数据DataFrame
        risk_free_rate: 无风险利率（年化）
        trading_days: 年交易日数
    
    Returns:
        夏普比率，失败返回 None
    """
    if df is None or df.empty:
        return None
    
    closes = df['close'].dropna()
    if len(closes) < 2:
        return None
    
    returns = closes.pct_change().dropna()
    
    if len(returns) == 0 or returns.std() == 0:
        return None
    
    # 年化收益和波动率
    annual_return = returns.mean() * trading_days
    annual_volatility = returns.std() * np.sqrt(trading_days)
    
    sharpe = (annual_return - risk_free_rate) / annual_volatility
    
    return float(sharpe)


def calc_period_stats(df: pd.DataFrame) -> dict:
    """
    计算周期统计信息
    
    Args:
        df: K线数据DataFrame
    
    Returns:
        包含各项统计指标的字典
    """
    if df is None or df.empty:
        return {}
    
    closes = df['close'].dropna()
    if len(closes) < 2:
        return {}
    
    stats = {
        "start_close": float(closes.iloc[0]),
        "end_close": float(closes.iloc[-1]),
        "period_return": calc_period_return(df),
        "max_close": float(closes.max()),
        "min_close": float(closes.min()),
        "max_drawdown": calc_max_drawdown(df),
        "max_gain": calc_max_gain(df),
        "volatility": calc_volatility(df),
        "trading_days": len(closes)
    }
    
    return stats


def compare_periods(
    df_curr: pd.DataFrame, 
    df_prev: pd.DataFrame
) -> dict:
    """
    比较当前周期和上一周期
    
    Args:
        df_curr: 当前周期数据
        df_prev: 上一周期数据
    
    Returns:
        包含比较结果的字典
    """
    curr_stats = calc_period_stats(df_curr) if df_curr is not None and not df_curr.empty else {}
    prev_stats = calc_period_stats(df_prev) if df_prev is not None and not df_prev.empty else {}
    
    return {
        "current_period": curr_stats,
        "previous_period": prev_stats,
        "return_comparison": {
            "curr_return": curr_stats.get("period_return"),
            "prev_return": prev_stats.get("period_return"),
            "return_diff": (
                curr_stats.get("period_return") - prev_stats.get("period_return")
                if curr_stats.get("period_return") and prev_stats.get("period_return") 
                else None
            )
        }
    }


class ReturnCalculator:
    """涨跌幅计算器类"""
    
    def __init__(self, risk_free_rate: float = 0.03, trading_days: int = 252):
        self.risk_free_rate = risk_free_rate
        self.trading_days = trading_days
    
    def calc_return(self, df: pd.DataFrame) -> Optional[float]:
        """计算周期涨跌幅"""
        return calc_period_return(df)
    
    def calc_return_pct(self, df: pd.DataFrame, decimals: int = 2) -> Optional[str]:
        """计算周期涨跌幅（百分比）"""
        ret = calc_period_return(df)
        if ret is None:
            return None
        return f"{ret * 100:.{decimals}2f}%"
    
    def calc_max_drawdown(self, df: pd.DataFrame) -> Optional[float]:
        """计算最大回撤"""
        return calc_max_drawdown(df)
    
    def calc_max_rebound(self, df: pd.DataFrame) -> Optional[float]:
        """计算最大反弹"""
        return calc_max_rebound(df)
    
    def calc_full_stats(self, df: pd.DataFrame) -> dict:
        """计算完整统计信息"""
        return calc_period_stats(df)
    
    def compare_two_periods(
        self, 
        df_curr: pd.DataFrame, 
        df_prev: pd.DataFrame
    ) -> dict:
        """比较两个周期"""
        return compare_periods(df_curr, df_prev)
