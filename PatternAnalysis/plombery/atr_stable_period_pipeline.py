"""
ATR稳定期检测Plombery任务
用于定时调度稳定期检测任务
"""
import logging
from datetime import datetime
from typing import Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ATRStablePeriodPipeline:
    """ATR稳定期检测流水线任务"""
    
    def __init__(
        self,
        window: int = 20,
        percentile_threshold: float = 30,
        min_stable_days: int = 5,
        lookback_period: int = 241
    ):
        """
        初始化稳定期检测任务
        
        Args:
            window: CV计算窗口大小
            percentile_threshold: 百分位阈值
            min_stable_days: 最少连续稳定天数
            lookback_period: 历史数据回溯期
        """
        self.window = window
        self.percentile_threshold = percentile_threshold
        self.min_stable_days = min_stable_days
        self.lookback_period = lookback_period
        self.last_run_time: Optional[datetime] = None
        self.last_status: str = "pending"
        self.last_result_count: int = 0
    
    def run(self, force_recalculate: bool = False):
        """
        执行稳定期检测任务

        Args:
            force_recalculate: 是否强制重新计算所有数据

        Returns:
            dict: 执行结果
        """
        self.last_run_time = datetime.now()
        logger.info(
            f"开始执行ATR稳定期检测任务，window={self.window}, "
            f"percentile={self.percentile_threshold}%, min_days={self.min_stable_days}, "
            f"lookback={self.lookback_period}, force={force_recalculate}"
        )

        try:
            # 导入检测服务
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            from PatternAnalysis.strategy.ATR.atr_stable_period_service import (
                detect_and_save_all_stocks,
                get_all_stocks_with_stable_periods
            )

            # 检查是否需要重新计算
            existing_stocks = get_all_stocks_with_stable_periods()
            
            if not existing_stocks or force_recalculate:
                logger.info(f"需要计算稳定期，当前已有 {len(existing_stocks)} 只股票的数据")
            
            # 执行批量检测
            result = detect_and_save_all_stocks(
                window=self.window,
                percentile_threshold=self.percentile_threshold,
                min_stable_days=self.min_stable_days,
                lookback_period=self.lookback_period
            )

            self.last_result_count = result.get("total_periods", 0)
            self.last_status = "success"

            logger.info(
                f"ATR稳定期检测任务完成，成功处理 {result.get('success_count', 0)} 只股票，"
                f"共检测到 {self.last_result_count} 个稳定期"
            )

            return {
                "status": "success",
                "parameters": {
                    "window": self.window,
                    "percentile_threshold": self.percentile_threshold,
                    "min_stable_days": self.min_stable_days,
                    "lookback_period": self.lookback_period
                },
                "result_count": self.last_result_count,
                "run_time": self.last_run_time.isoformat(),
                "total_stocks": result.get("total_stocks", 0),
                "success_count": result.get("success_count", 0),
                "fail_count": result.get("fail_count", 0)
            }

        except Exception as e:
            self.last_status = "failed"
            logger.error(f"ATR稳定期检测任务失败: {e}")
            import traceback
            traceback.print_exc()

            return {
                "status": "failed",
                "error": str(e),
                "run_time": self.last_run_time.isoformat()
            }
    
    def get_status(self) -> dict:
        """获取任务状态"""
        return {
            "last_run_time": self.last_run_time.isoformat() if self.last_run_time else None,
            "last_status": self.last_status,
            "last_result_count": self.last_result_count,
            "parameters": {
                "window": self.window,
                "percentile_threshold": self.percentile_threshold,
                "min_stable_days": self.min_stable_days,
                "lookback_period": self.lookback_period
            }
        }


# Plombery任务定义（如果plombery已安装）
try:
    from plombery import Pipeline, Task, trigger
    
    class ATRStablePeriodPlomberyPipeline(Pipeline):
        """ATR稳定期检测的Plombery Pipeline"""
        
        id = "atr_stable_period_detection"
        description = "基于ATR自适应阈值识别个股中低波动稳定期"
        
        # 定时触发器：每天16:30执行（在MTR/ATR计算之后）
        @trigger(schedule="0 16 * * *")
        def daily_stable_period_task(self):
            """每日稳定期检测任务"""
            pipeline = ATRStablePeriodPipeline(
                window=20,
                percentile_threshold=30,
                min_stable_days=5,
                lookback_period=241
            )
            result = pipeline.run()
            
            return result
        
        @trigger(schedule="0 */6 * * *")
        def hourly_stable_period_task(self):
            """每6小时稳定期检测任务（用于增量更新）"""
            pipeline = ATRStablePeriodPipeline(
                window=20,
                percentile_threshold=30,
                min_stable_days=5,
                lookback_period=241
            )
            result = pipeline.run(force_recalculate=False)
            
            return result
    
    __all__ = ["ATRStablePeriodPipeline", "ATRStablePeriodPlomberyPipeline"]
    
except ImportError:
    logger.warning("Plombery未安装，将使用独立的任务调度器")
    __all__ = ["ATRStablePeriodPipeline"]


def main():
    """独立运行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="ATR稳定期检测任务")
    parser.add_argument("--window", type=int, default=20, help="CV计算窗口大小")
    parser.add_argument("--percentile", type=float, default=30, help="百分位阈值")
    parser.add_argument("--min-days", type=int, default=5, help="最少连续稳定天数")
    parser.add_argument("--lookback", type=int, default=241, help="历史数据回溯期")
    parser.add_argument("--force", action="store_true", help="强制重新计算所有数据")
    
    args = parser.parse_args()
    
    pipeline = ATRStablePeriodPipeline(
        window=args.window,
        percentile_threshold=args.percentile,
        min_stable_days=args.min_days,
        lookback_period=args.lookback
    )
    result = pipeline.run(force_recalculate=args.force)
    
    print(f"任务执行结果: {result}")
    return result


if __name__ == "__main__":
    main()
