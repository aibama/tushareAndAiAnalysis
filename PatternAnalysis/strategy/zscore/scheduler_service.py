"""
Z-Score 定时计算任务

每日收盘后计算Z-Score数据
"""
import logging
import argparse
import sys
import os
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .zscore_service import (
    get_industry_daily_zscore,
    get_index_timeseries_zscore
)
from .data_service import get_latest_trade_date
from .config import ZSCORE_CONFIG

logger = logging.getLogger(__name__)


def calculate_all_zscore(trade_date: date = None, indicator: str = "price"):
    """
    计算所有Z-Score数据

    Args:
        trade_date: 交易日期
        indicator: 指标类型

    Returns:
        计算结果
    """
    if trade_date is None:
        trade_date = get_latest_trade_date()

    logger.info(f"开始计算 {trade_date} 的 Z-Score 数据，指标: {indicator}")

    results = {
        "trade_date": trade_date.strftime('%Y-%m-%d'),
        "indicator": indicator,
        "industry_count": 0,
        "index_series_length": 0,
        "errors": []
    }

    try:
        # 计算行业Z-Score
        industries = get_industry_daily_zscore(trade_date, indicator)
        results["industry_count"] = len(industries)
        logger.info(f"行业Z-Score计算完成，共 {len(industries)} 个行业")

    except Exception as e:
        logger.error(f"计算行业Z-Score失败: {e}")
        results["errors"].append(f"行业Z-Score: {str(e)}")

    try:
        # 计算指数时间序列
        window_days = ZSCORE_CONFIG.get("window_days", 60)
        index_series = get_index_timeseries_zscore(trade_date, window_days, indicator)
        results["index_series_length"] = len(index_series.get('series', []))
        logger.info(f"指数时间序列计算完成，共 {len(index_series.get('series', []))} 条数据")

    except Exception as e:
        logger.error(f"计算指数时间序列失败: {e}")
        results["errors"].append(f"指数时间序列: {str(e)}")

    # 汇总结果
    if results["errors"]:
        logger.warning(f"计算完成但有错误: {results['errors']}")
        return {
            "success": False,
            "message": f"计算完成但有 {len(results['errors'])} 个错误",
            "results": results
        }
    else:
        logger.info(f"Z-Score计算完成: {results}")
        return {
            "success": True,
            "message": "计算完成",
            "results": results
        }


def run_scheduler():
    """运行定时任务"""
    import time

    logger.info("Z-Score 定时计算任务已启动")

    while True:
        try:
            # 获取最新交易日期
            latest_date = get_latest_trade_date()

            # 检查是否需要计算（可以添加逻辑：只在交易日收盘后计算）
            result = calculate_all_zscore(latest_date)

            logger.info(f"定时任务执行结果: {result}")

        except Exception as e:
            logger.error(f"定时任务执行失败: {e}", exc_info=True)

        # 每小时检查一次
        time.sleep(3600)


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description='Z-Score 定时计算任务')

    parser.add_argument('--date', type=str, help='交易日期 (YYYY-MM-DD)')
    parser.add_argument('--indicator', type=str, default='price',
                       choices=['price', 'pe', 'pb'],
                       help='指标类型')
    parser.add_argument('--daemon', action='store_true',
                       help='以守护进程模式运行')

    args = parser.parse_args()

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    if args.daemon:
        # 守护进程模式
        run_scheduler()
    else:
        # 单次执行
        trade_date = None
        if args.date:
            from datetime import datetime
            trade_date = datetime.strptime(args.date, '%Y-%m-%d').date()

        result = calculate_all_zscore(trade_date, args.indicator)
        print(result)


if __name__ == "__main__":
    main()
