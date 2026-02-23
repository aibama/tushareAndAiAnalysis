#!/usr/bin/env python
"""
ATR计算测试脚本
支持立即执行ATR计算，支持指定时间范围补充数据
"""
import sys
import os
from datetime import datetime, timedelta

# 确保当前目录在Python路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orm.etf.stock_statistics_service import (
    run_incremental_mtr_atr_calculation,
    StockStatisticsService
)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="ATR计算测试脚本")
    parser.add_argument("--period", type=int, default=14, help="ATR计算周期，默认14天")
    parser.add_argument("--start", type=str, default=None, help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None, help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--fill", action="store_true", help="填充数据缺口（补充缺失的历史和最新数据）")
    parser.add_argument("--force", action="store_true", help="强制重新计算所有数据")
    parser.add_argument("--status", action="store_true", help="显示当前数据状态")
    parser.add_argument("--verbose", action="store_true", help="详细输出")

    args = parser.parse_args()

    if args.status:
        show_data_status()
        return

    # 如果指定了start和end日期，用于补数据
    if args.start and args.end:
        print(f"补数据模式: {args.start} 到 {args.end}")
        result = run_incremental_mtr_atr_calculation(
            atr_period=args.period,
            start_date=args.start,
            end_date=args.end,
            fill_gaps=False,
            force_recalculate=args.force
        )
    elif args.fill:
        print(f"填充数据缺口模式，ATR周期={args.period}")
        result = run_incremental_mtr_atr_calculation(
            atr_period=args.period,
            start_date=None,
            end_date=None,
            fill_gaps=True,
            force_recalculate=args.force
        )
    else:
        # 立即执行增量计算
        print(f"立即执行ATR计算，ATR周期={args.period}")
        result = run_incremental_mtr_atr_calculation(
            atr_period=args.period,
            force_recalculate=args.force
        )

    print(f"\n执行结果: {result}")
    return result


def show_data_status():
    """显示当前数据状态"""
    print("=" * 60)
    print("当前ATR数据状态")
    print("=" * 60)

    service = StockStatisticsService()

    # 获取数据统计
    summary = service.get_stock_data_summary()
    print(f"\n总股票数: {summary['total_stocks']}")

    if summary['stocks']:
        # 计算数据范围
        valid_stocks = [s for s in summary['stocks'] if s['start_date'] != 'N/A']
        if valid_stocks:
            min_date = min(s['start_date'] for s in valid_stocks)
            max_date = max(s['end_date'] for s in valid_stocks)
            print(f"数据范围: {min_date} 到 {max_date}")

        # 显示前10个股票
        print("\n前10个股票:")
        for stock in summary['stocks'][:10]:
            print(f"  {stock['ts_code']}: {stock['record_count']}条, {stock['start_date']} 到 {stock['end_date']}")

    # 检查ATR状态
    from orm.etf.stock_statistics_service import MTRATRStatusManager
    status_manager = MTRATRStatusManager()
    last_period = status_manager.get_last_atr_period()
    print(f"\nATR周期配置: {last_period}")

    service.close()
    status_manager.close()


def fill_gaps_demo():
    """
    演示如何补充数据

    场景：
    - 当前数据: 2025-01-21 到 2026-01-26
    - 现在是: 2026-02-19
    - 需要补充: 2025-01-21之前 和 2026-01-26到2026-02-19
    """
    print("=" * 60)
    print("数据补充演示")
    print("=" * 60)

    # 假设当前数据范围
    current_start = "2025-01-21"
    current_end = "2026-01-26"
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')

    print(f"假设当前数据范围: {current_start} 到 {current_end}")
    print(f"现在日期: {today}")

    # 补充之前的数据
    print(f"\n补充 {current_start} 之前的数据...")
    result1 = run_incremental_mtr_atr_calculation(
        atr_period=14,
        start_date="2024-01-01",  # 假设从2024-01-01开始有数据
        end_date=current_start,
        fill_gaps=False
    )

    # 补充之后的数据
    print(f"\n补充 {current_end} 到 {today} 的数据...")
    result2 = run_incremental_mtr_atr_calculation(
        atr_period=14,
        start_date=current_end,
        end_date=today,
        fill_gaps=False
    )

    print(f"\n补充之前数据结果: {result1}")
    print(f"补充之后数据结果: {result2}")


if __name__ == "__main__":
    # 如果没有参数，显示帮助和演示
    if len(sys.argv) == 1:
        print("ATR计算测试脚本")
        print("=" * 60)
        print("用法:")
        print("  python run_atr_test.py                    # 立即执行增量计算")
        print("  python run_atr_test.py --status           # 显示当前数据状态")
        print("  python run_atr_test.py --fill            # 填充数据缺口")
        print("  python run_atr_test.py --start 2024-01-01 --end 2025-01-20  # 补之前的数据")
        print("  python run_atr_test.py --start 2026-01-27 --end 2026-02-19  # 补之后的数据")
        print("  python run_atr_test.py --force            # 强制重新计算所有数据")
        print()
        print("示例：补充所有缺失数据")
        print("  python run_atr_test.py --fill")
        print()
        show_data_status()
    else:
        main()
