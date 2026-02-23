"""
ATR Strategy Module

This module provides ATR-based adaptive threshold algorithms for detecting
stable market periods in trading data.

Submodules
----------
- adaptive_threshold : Core algorithm for detecting stable ATR periods

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

__all__ = [
    'detect_stable_periods_adaptive',
    'analyze_stable_periods',
    'quick_detect',
    'StablePeriod'
]

__version__ = '1.0.0'
