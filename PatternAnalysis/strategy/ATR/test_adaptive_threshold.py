"""
Test module for ATR Adaptive Threshold Algorithm

This module provides tests and examples for the ATR adaptive threshold
detection algorithm.

Usage:
    python -c "from PatternAnalysis.strategy.ATR import test_adaptive_threshold; test_adaptive_threshold.run_all()"
"""

import pandas as pd
import numpy as np


def generate_test_data(
    n_days: int = 500,
    seed: int = 42
) -> pd.Series:
    """
    Generate realistic test ATR data with known stable periods.
    
    Parameters
    ----------
    n_days : int
        Number of business days to generate
    seed : int
        Random seed for reproducibility
    
    Returns
    -------
    pd.Series
        ATR series with datetime index
    """
    np.random.seed(seed)
    
    # Create dates
    dates = pd.date_range('2023-01-01', periods=n_days, freq='B')
    
    # Base ATR with occasional regime changes
    base_atr = 2.0
    atr_values = np.full(n_days, base_atr)
    
    # Add regime changes at specific periods
    # Period 1: Low volatility (days 50-100)
    atr_values[50:100] = 1.5 + np.random.normal(0, 0.05, 50)
    
    # Period 2: Normal volatility (days 150-250)
    atr_values[150:250] = 2.2 + np.random.normal(0, 0.15, 100)
    
    # Period 3: Low volatility (days 300-350)
    atr_values[300:350] = 1.8 + np.random.normal(0, 0.03, 50)
    
    # Period 4: High volatility spike (days 380-400)
    atr_values[380:400] = 3.0 + np.random.normal(0, 0.3, 20)
    
    # Add some noise
    noise = np.random.normal(0, 0.1, n_days)
    atr_values = atr_values + noise
    
    # Ensure ATR is positive
    atr_values = np.maximum(atr_values, 0.1)
    
    return pd.Series(atr_values, index=dates)


def run_basic_test():
    """Run basic functionality test."""
    from .adaptive_threshold import detect_stable_periods_adaptive, StablePeriod
    
    print("=" * 60)
    print("ATR Adaptive Threshold Algorithm - Basic Test")
    print("=" * 60)
    
    # Generate test data
    atr_series = generate_test_data(n_days=500, seed=42)
    print(f"\nGenerated {len(atr_series)} days of ATR data")
    print(f"ATR range: {atr_series.min():.3f} - {atr_series.max():.3f}")
    print(f"Mean ATR: {atr_series.mean():.3f}")
    
    # Run detection with default parameters
    print("\n--- Running detection with default parameters ---")
    stable_periods, threshold_series = detect_stable_periods_adaptive(
        atr_series=atr_series,
        window=20,
        percentile_threshold=30,
        min_stable_days=5,
        lookback_period=241  # As mentioned in requirements
    )
    
    print(f"\nDetection Results:")
    print(f"  - Found {len(stable_periods)} stable periods")
    print(f"  - Total stable days: {sum(p.duration_days for p in stable_periods)}")
    
    # Print each stable period
    print("\n--- Stable Periods Detail ---")
    for i, period in enumerate(stable_periods, 1):
        print(f"\nPeriod {i}:")
        print(f"  Start Date: {period.start_date.date()}")
        print(f"  End Date: {period.end_date.date()}")
        print(f"  Duration: {period.duration_days} days")
        print(f"  Average ATR: {period.avg_atr:.3f}")
        print(f"  ATR CV: {period.atr_cv:.4f} ({period.atr_cv*100:.2f}%)")
        print(f"  Threshold Used: {period.threshold_used:.4f}")
        print(f"  Stability Score: {period.stability_score:.3f}")
    
    # Show threshold series summary
    print(f"\n--- Threshold Series Summary ---")
    print(f"  Min Threshold: {threshold_series.min():.4f}")
    print(f"  Max Threshold: {threshold_series.max():.4f}")
    print(f"  Mean Threshold: {threshold_series.mean():.4f}")
    
    return stable_periods, threshold_series


def run_comprehensive_analysis():
    """Run comprehensive analysis with all parameters."""
    from .adaptive_threshold import analyze_stable_periods
    
    print("\n" + "=" * 60)
    print("Comprehensive Analysis Test")
    print("=" * 60)
    
    atr_series = generate_test_data(n_days=500, seed=42)
    
    # Run comprehensive analysis
    results = analyze_stable_periods(
        atr_series=atr_series,
        window=20,
        percentile_threshold=30,
        min_stable_days=5,
        lookback_period=241
    )
    
    print(f"\nSummary Statistics:")
    summary = results['summary']
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")
    
    return results


def test_parameter_sensitivity():
    """Test how different parameters affect results."""
    from .adaptive_threshold import detect_stable_periods_adaptive
    
    print("\n" + "=" * 60)
    print("Parameter Sensitivity Test")
    print("=" * 60)
    
    atr_series = generate_test_data(n_days=500, seed=42)
    
    # Test different percentile thresholds
    thresholds = [20, 30, 40, 50]
    print("\n--- Effect of Percentile Threshold ---")
    for pt in thresholds:
        periods, _ = detect_stable_periods_adaptive(
            atr_series=atr_series,
            percentile_threshold=pt,
            lookback_period=241
        )
        total_days = sum(p.duration_days for p in periods)
        print(f"  Percentile {pt}%: {len(periods)} periods, {total_days} stable days")
    
    # Test different min_stable_days
    print("\n--- Effect of Minimum Stable Days ---")
    for min_days in [3, 5, 10, 15]:
        periods, _ = detect_stable_periods_adaptive(
            atr_series=atr_series,
            min_stable_days=min_days,
            lookback_period=241
        )
        total_days = sum(p.duration_days for p in periods)
        print(f"  Min {min_days} days: {len(periods)} periods, {total_days} stable days")


def test_edge_cases():
    """Test edge cases."""
    from .adaptive_threshold import detect_stable_periods_adaptive
    
    print("\n" + "=" * 60)
    print("Edge Cases Test")
    print("=" * 60)
    
    # Test 1: Empty series
    print("\nTest 1: Empty series")
    try:
        empty_series = pd.Series([], index=[])
        detect_stable_periods_adaptive(empty_series)
        print("  ERROR: Should have raised ValueError")
    except ValueError as e:
        print(f"  OK: Correctly raised ValueError: {e}")
    
    # Test 2: Very short series
    print("\nTest 2: Very short series (10 days)")
    short_dates = pd.date_range('2024-01-01', periods=10, freq='B')
    short_atr = pd.Series([2.0] * 10, index=short_dates)
    periods, thresholds = detect_stable_periods_adaptive(short_atr)
    print(f"  Result: {len(periods)} stable periods (expected 0 due to insufficient data)")
    
    # Test 3: Constant ATR (should be very stable)
    print("\nTest 3: Constant ATR values")
    const_dates = pd.date_range('2024-01-01', periods=100, freq='B')
    const_atr = pd.Series([2.0] * 100, index=const_dates)
    periods, _ = detect_stable_periods_adaptive(const_atr, min_stable_days=5)
    print(f"  Result: {len(periods)} stable periods")
    if periods:
        print(f"  First period: {periods[0].start_date.date()} to {periods[0].end_date.date()}")


def run_visualization_example():
    """Example showing how to visualize results."""
    print("\n" + "=" * 60)
    print("Visualization Example Code")
    print("=" * 60)
    
    # This is example code - visualization requires matplotlib
    example_code = '''
import matplotlib.pyplot as plt

# Generate data and run detection
atr_series = generate_test_data()
stable_periods, thresholds = detect_stable_periods_adaptive(atr_series)

# Create visualization
fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

# Plot 1: ATR with stable periods
axes[0].plot(atr_series.index, atr_series.values, label='ATR', alpha=0.7)
for period in stable_periods:
    axes[0].axvspan(period.start_date, period.end_date, 
                    alpha=0.2, color='green')
axes[0].set_ylabel('ATR Value')
axes[0].set_title('ATR with Stable Periods Highlighted')
axes[0].legend()

# Plot 2: Dynamic Threshold
axes[1].plot(thresholds.index, thresholds.values, label='Threshold', 
             color='orange', linewidth=1.5)
axes[1].set_ylabel('CV Threshold')
axes[1].set_title('Dynamic Threshold Over Time')
axes[1].legend()

# Plot 3: CV series
cv = atr_series.rolling(20).std() / atr_series.rolling(20).mean()
axes[2].plot(cv.index, cv.values, label='CV', alpha=0.7)
axes[2].plot(thresholds.index, thresholds.values, label='Threshold', 
             color='orange', linewidth=1.5)
axes[2].set_ylabel('Coefficient of Variation')
axes[2].set_xlabel('Date')
axes[2].set_title('CV vs Threshold')
axes[2].legend()

plt.tight_layout()
plt.show()
'''
    print(example_code)


def run_all():
    """Run all tests."""
    print("ATR Adaptive Threshold Algorithm - Test Suite")
    print("=" * 60)
    
    # Run all tests
    run_basic_test()
    run_comprehensive_analysis()
    test_parameter_sensitivity()
    test_edge_cases()
    run_visualization_example()
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == '__main__':
    # When run as script, add parent to path
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    from .adaptive_threshold import (
        detect_stable_periods_adaptive,
        analyze_stable_periods,
        StablePeriod
    )
    
    run_all()
