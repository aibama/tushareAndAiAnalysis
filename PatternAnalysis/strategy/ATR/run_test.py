#!/usr/bin/env python
"""
Quick test runner for ATR Adaptive Threshold Algorithm
"""

import sys
sys.path.insert(0, '.')

from PatternAnalysis.strategy.ATR.adaptive_threshold import (
    detect_stable_periods_adaptive,
    StablePeriod,
    analyze_stable_periods
)
import pandas as pd
import numpy as np

def main():
    # Quick test
    dates = pd.date_range('2024-01-01', periods=300, freq='B')
    np.random.seed(42)
    atr = pd.Series(2.0 + np.random.normal(0, 0.1, 300), index=dates)
    
    print("=" * 60)
    print("ATR Adaptive Threshold Algorithm - Quick Test")
    print("=" * 60)
    
    # Test basic detection
    periods, thresholds = detect_stable_periods_adaptive(atr, lookback_period=241)
    print(f"\nBasic detection result:")
    print(f"  - Found {len(periods)} stable periods")
    
    for i, p in enumerate(periods[:5], 1):
        print(f"  - Period {i}: {p.start_date.date()} to {p.end_date.date()}, {p.duration_days} days")
    
    # Test comprehensive analysis
    print("\n" + "-" * 60)
    results = analyze_stable_periods(atr, lookback_period=241)
    print(f"\nComprehensive analysis result:")
    summary = results['summary']
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"  - {key}: {value:.4f}")
        else:
            print(f"  - {key}: {value}")
    
    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)

if __name__ == '__main__':
    main()
