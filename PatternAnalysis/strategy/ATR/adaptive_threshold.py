"""
ATR Adaptive Threshold Algorithm

This module implements an adaptive threshold algorithm for detecting stable periods
in ATR (Average True Range) time series data.

The algorithm uses coefficient of variation (CV) to measure ATR stability and
dynamically adjusts thresholds based on historical data percentiles.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict


@dataclass
class StablePeriod:
    """Represents a stable period detected by the algorithm."""
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    duration_days: int
    avg_atr: float
    atr_cv: float
    threshold_used: float
    stability_score: float
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return asdict(self)


def detect_stable_periods_adaptive(
    atr_series: pd.Series,
    window: int = 20,
    percentile_threshold: float = 30,
    min_stable_days: int = 5,
    lookback_period: int = 252,
    default_threshold: float = 0.03
) -> Tuple[List[StablePeriod], pd.Series]:
    """
    Detect stable periods in ATR time series using adaptive threshold algorithm.
    
    Parameters
    ----------
    atr_series : pd.Series
        ATR time series with datetime index
    window : int, default 20
        Rolling window size for calculating coefficient of variation (CV)
    percentile_threshold : float, default 30
        Percentile threshold (0-100) for determining stability.
        Values below this percentile are considered "stable".
    min_stable_days : int, default 5
        Minimum consecutive stable days to be considered a valid stable period
    lookback_period : int, default 252
        Number of historical days to use for threshold calculation
        (approximately 1 trading year)
    default_threshold : float, default 0.03
        Default CV threshold when insufficient historical data is available
    
    Returns
    -------
    Tuple[List[StablePeriod], pd.Series]
        - List of StablePeriod objects containing all detected stable periods
        - pd.Series with datetime index containing the dynamic threshold for each date
    
    Algorithm
    ---------
    1. Calculate Coefficient of Variation (CV):
       CV = rolling_std / rolling_mean
    
    2. Calculate dynamic threshold for each day:
       - For first 'lookback_period' days: use available historical CV data
       - For subsequent days: use rolling window of past 'lookback_period' CV values
       - Threshold = percentile_threshold of historical CV values
    
    3. Identify stable days:
       - Day is stable if CV < dynamic_threshold and CV is computable
    
    4. Group consecutive stable days into stable periods:
       - Only periods with >= min_stable_days are recorded
    
    Examples
    --------
    >>> import pandas as pd
    >>> import numpy as np
    >>> dates = pd.date_range('2024-01-01', '2024-12-31', freq='B')
    >>> np.random.seed(42)
    >>> atr = pd.Series(2.0 + np.random.normal(0, 0.1, len(dates)), index=dates)
    >>> periods, thresholds = detect_stable_periods_adaptive(atr)
    >>> print(f"Found {len(periods)} stable periods")
    """
    
    # Validate inputs
    if atr_series.empty:
        raise ValueError("atr_series cannot be empty")
    
    if window < 2:
        raise ValueError("window must be at least 2")
    
    if not 0 <= percentile_threshold <= 100:
        raise ValueError("percentile_threshold must be between 0 and 100")
    
    if min_stable_days < 1:
        raise ValueError("min_stable_days must be at least 1")
    
    if lookback_period < window:
        raise ValueError("lookback_period must be >= window")
    
    # Step 1: Calculate Coefficient of Variation (CV)
    rolling_mean = atr_series.rolling(window=window).mean()
    rolling_std = atr_series.rolling(window=window).std()
    
    # CV = std / mean (handle division by zero)
    cv_series = rolling_std / rolling_mean
    
    # Step 2: Calculate dynamic thresholds and stable flags
    dynamic_thresholds = []
    stable_flags = []
    
    cv_values = cv_series.values
    atr_index = atr_series.index
    
    n = len(atr_series)
    
    for i in range(n):
        # Calculate threshold based on available historical data
        if i < lookback_period:
            # Use available historical CV data up to current point
            available_cv = cv_series.dropna().iloc[:i+1] if i >= window - 1 else pd.Series([])
            if len(available_cv) > 0:
                threshold = np.percentile(available_cv, percentile_threshold)
            else:
                threshold = default_threshold
        else:
            # Use rolling window of past 'lookback_period' CV values
            history_cv = cv_series.iloc[i-lookback_period:i]
            history_cv = history_cv.dropna()
            if len(history_cv) > 0:
                threshold = np.percentile(history_cv, percentile_threshold)
            else:
                threshold = default_threshold
        
        dynamic_thresholds.append(threshold)
        
        # Determine if current day is stable
        if i >= window - 1:  # Ensure enough data to compute CV
            current_cv = cv_values[i]
            is_stable = not pd.isna(current_cv) and current_cv < threshold
        else:
            is_stable = False
        
        stable_flags.append(is_stable)
    
    # Create threshold series with proper index
    threshold_series = pd.Series(dynamic_thresholds, index=atr_index, name='threshold')
    stable_flag_series = pd.Series(stable_flags, index=atr_index, name='stable')
    
    # Step 3: Identify consecutive stable periods
    stable_periods: List[StablePeriod] = []
    current_start = None
    
    for i, (date, is_stable) in enumerate(zip(atr_index, stable_flags)):
        if is_stable and current_start is None:
            # Start a new stable period
            current_start = i
        elif not is_stable and current_start is not None:
            # Current stable period ends
            duration = i - current_start
            
            if duration >= min_stable_days:
                # Extract stable period data
                period_atr = atr_series.iloc[current_start:i]
                period_thresholds = threshold_series.iloc[current_start:i]
                
                # Calculate statistics
                avg_atr = period_atr.mean()
                atr_cv = period_atr.std() / avg_atr if avg_atr > 0 else 0
                threshold_used = period_thresholds.mean()
                stability_score = 1 - atr_cv if atr_cv < 1 else 0
                
                # Create StablePeriod object
                period = StablePeriod(
                    start_date=pd.Timestamp(atr_index[current_start]),
                    end_date=pd.Timestamp(atr_index[i - 1]),
                    duration_days=duration,
                    avg_atr=avg_atr,
                    atr_cv=atr_cv,
                    threshold_used=threshold_used,
                    stability_score=stability_score
                )
                stable_periods.append(period)
            
            # Reset for next period
            current_start = None
    
    # Handle case where series ends while still in stable period
    if current_start is not None:
        duration = n - current_start
        
        if duration >= min_stable_days:
            period_atr = atr_series.iloc[current_start:]
            period_thresholds = threshold_series.iloc[current_start:]
            
            avg_atr = period_atr.mean()
            atr_cv = period_atr.std() / avg_atr if avg_atr > 0 else 0
            threshold_used = period_thresholds.mean()
            stability_score = 1 - atr_cv if atr_cv < 1 else 0
            
            period = StablePeriod(
                start_date=pd.Timestamp(atr_index[current_start]),
                end_date=pd.Timestamp(atr_index[-1]),
                duration_days=duration,
                avg_atr=avg_atr,
                atr_cv=atr_cv,
                threshold_used=threshold_used,
                stability_score=stability_score
            )
            stable_periods.append(period)
    
    return stable_periods, threshold_series


def analyze_stable_periods(
    atr_series: pd.Series,
    window: int = 20,
    percentile_threshold: float = 30,
    min_stable_days: int = 5,
    lookback_period: int = 241,  # Using 241 as mentioned in requirements
    default_threshold: float = 0.03
) -> Dict:
    """
    Analyze ATR data and return comprehensive analysis results.
    
    Parameters
    ----------
    atr_series : pd.Series
        ATR time series with datetime index
    window : int, default 20
        Rolling window size for CV calculation
    percentile_threshold : float, default 30
        Percentile threshold for stability detection
    min_stable_days : int, default 5
        Minimum stable days for valid period
    lookback_period : int, default 241
        Historical lookback period (adjusted for available data)
    default_threshold : float, default 0.03
        Default CV threshold
    
    Returns
    -------
    Dict
        Comprehensive analysis results including:
        - stable_periods: List of StablePeriod objects
        - threshold_series: Dynamic threshold series
        - summary: Summary statistics
        - cv_series: Calculated CV series
    """
    # Run the main algorithm
    stable_periods, threshold_series = detect_stable_periods_adaptive(
        atr_series=atr_series,
        window=window,
        percentile_threshold=percentile_threshold,
        min_stable_days=min_stable_days,
        lookback_period=lookback_period,
        default_threshold=default_threshold
    )
    
    # Calculate additional CV series for analysis
    cv_series = (atr_series.rolling(window=window).std() / 
                 atr_series.rolling(window=window).mean())
    
    # Generate summary statistics
    total_days = len(atr_series)
    stable_days = sum(p.duration_days for p in stable_periods)
    
    summary = {
        'total_days': total_days,
        'num_stable_periods': len(stable_periods),
        'total_stable_days': stable_days,
        'stable_day_ratio': stable_days / total_days if total_days > 0 else 0,
        'avg_stable_period_length': (
            sum(p.duration_days for p in stable_periods) / len(stable_periods)
            if stable_periods else 0
        ),
        'avg_atr': atr_series.mean(),
        'atr_std': atr_series.std(),
        'avg_cv': cv_series.dropna().mean() if not cv_series.dropna().empty else 0,
        'avg_threshold': threshold_series.mean(),
        'parameter_settings': {
            'window': window,
            'percentile_threshold': percentile_threshold,
            'min_stable_days': min_stable_days,
            'lookback_period': lookback_period
        }
    }
    
    return {
        'stable_periods': stable_periods,
        'threshold_series': threshold_series,
        'cv_series': cv_series,
        'summary': summary
    }


# Convenience function for quick analysis
def quick_detect(
    atr_values: List[float],
    dates: Optional[List[pd.Timestamp]] = None,
    **kwargs
) -> Tuple[List[Dict], pd.Series]:
    """
    Quick detection function for simple use cases.
    
    Parameters
    ----------
    atr_values : List[float]
        List of ATR values
    dates : Optional[List[pd.Timestamp]], optional
        Optional list of dates. If None, creates auto-dates.
    **kwargs
        Additional arguments passed to detect_stable_periods_adaptive
    
    Returns
    -------
    Tuple[List[Dict], pd.Series]
        List of period dictionaries and threshold series
    """
    if dates is None:
        dates = pd.date_range(start='2020-01-01', periods=len(atr_values), freq='B')
    
    atr_series = pd.Series(atr_values, index=dates)
    stable_periods, threshold_series = detect_stable_periods_adaptive(atr_series, **kwargs)
    
    # Convert to dict format for convenience
    periods_as_dicts = [p.to_dict() for p in stable_periods]
    
    return periods_as_dicts, threshold_series
