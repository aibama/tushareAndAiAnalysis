#!/usr/bin/env python
"""
测试修复后的代码
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PatternAnalysis.data_access import get_stock_ohlc_in_range, get_latest_trade_date
from PatternAnalysis.periods import get_period_windows
from datetime import date

if __name__ == "__main__":
    # 测试获取最新交易日期
    print("1. 测试获取最新交易日期...")
    latest = get_latest_trade_date()
    print(f"最新交易日期: {latest}")
    
    # 测试获取特定股票数据
    print("\n2. 测试获取股票 000166.SZ 的数据...")
    test_code = "000166.SZ"
    
    # 计算3个月周期
    if latest:
        (curr_start, curr_end), (prev_start, prev_end) = get_period_windows(latest, 3)
        print(f"当前周期: {curr_start} 到 {curr_end}")
        print(f"上一周期: {prev_start} 到 {prev_end}")
        
        # 测试查询当前周期数据
        print(f"\n3. 查询股票 {test_code} 在当前周期的数据...")
        df = get_stock_ohlc_in_range(test_code, curr_start, curr_end)
        print(f"查询到 {len(df)} 条记录")
        if not df.empty:
            print(f"日期范围: {df['trade_date'].min()} 到 {df['trade_date'].max()}")
            print(f"前5条数据:")
            print(df.head())
        else:
            print("未查询到数据，尝试查询该股票的所有数据...")
            # 查询该股票的所有数据
            from PatternAnalysis.data_access import get_engine
            from sqlalchemy import text
            engine = get_engine()
            sql = """
                SELECT MIN(DATE(trade_date)) as min_date, MAX(DATE(trade_date)) as max_date, COUNT(*) as cnt
                FROM stocktradetodayinfo
                WHERE ts_code = :ts_code
            """
            with engine.connect() as conn:
                result = conn.execute(text(sql), {"ts_code": test_code})
                row = result.fetchone()
                if row:
                    print(f"股票 {test_code} 在数据库中的实际日期范围: {row[0]} 到 {row[1]}, 共 {row[2]} 条记录")
        
        # 测试查询上一周期数据
        print(f"\n4. 查询股票 {test_code} 在上一周期的数据...")
        df_prev = get_stock_ohlc_in_range(test_code, prev_start, prev_end)
        print(f"查询到 {len(df_prev)} 条记录")
    else:
        print("无法获取最新交易日期，跳过测试")
