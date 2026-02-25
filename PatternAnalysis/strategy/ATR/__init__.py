"""
ATR Strategy Module

This module provides ATR-based adaptive threshold algorithms for detecting
stable market periods in trading data.

Submodules
----------
- adaptive_threshold : Core algorithm for detecting stable ATR periods
- atr_stable_period_service : Service for detecting and storing stable periods in Redis

Quick Start
-----------
>>> from PatternAnalysis.strategy.ATR import detect_stable_periods_adaptive
>>> import pandas as pd
>>> import numpy as np
>>> 
>>> # Prepare ATR data
>>> dates = pd.date_range('2024-01-01', '2024-12-31', freq='B')
>>> atr = pd.Series(2.0 + np.random.normal(0, 0.1, len(dates)), index=dates)
>>> 
>>> # Detect stable periods
>>> periods, thresholds = detect_stable_periods_adaptive(atr)
>>> 
>>> # Print results
>>> for p in periods:
...     print(f"Stable period: {p.start_date.date()} to {p.end_date.date()}, {p.duration_days} days")
"""

from .adaptive_threshold import (
    detect_stable_periods_adaptive,
    analyze_stable_periods,
    quick_detect,
    StablePeriod
)

# Service exports
from .atr_stable_period_service import (
    detect_stable_periods_for_stock,
    get_stable_periods_from_redis,
    format_stable_periods_for_api,
    detect_and_save_all_stocks,
    get_all_stocks_with_stable_periods,
    StablePeriodRecord,
    STABLE_PERIOD_STREAM
)

__all__ = [
    # Core algorithm
    'detect_stable_periods_adaptive',
    'analyze_stable_periods',
    'quick_detect',
    'StablePeriod',
    # Service
    'detect_stable_periods_for_stock',
    'get_stable_periods_from_redis',
    'format_stable_periods_for_api',
    'detect_and_save_all_stocks',
    'get_all_stocks_with_stable_periods',
    'StablePeriodRecord',
    'STABLE_PERIOD_STREAM'
]

__version__ = '1.0.0'
