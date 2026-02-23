"""
MTR/ATR计算Plombery任务
用于定时调度MTR/ATR计算任务
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


class MTRATRPipeline:
    """MTR/ATR计算流水线任务"""
    
    def __init__(self, atr_period: int = 14):
        """
        初始化MTR/ATR计算任务
        
        Args:
            atr_period: ATR计算周期，默认14天
        """
        self.atr_period = atr_period
        self.last_run_time: Optional[datetime] = None
        self.last_status: str = "pending"
        self.last_result_count: int = 0
    
    def run(
        self,
        force_recalculate: bool = False,
        start_date: str = None,
        end_date: str = None,
        fill_gaps: bool = False
    ):
        """
        执行MTR/ATR计算任务

        Args:
            force_recalculate: 是否强制重新计算所有数据
            start_date: 开始日期 (YYYY-MM-DD格式)，用于补数据
            end_date: 结束日期 (YYYY-MM-DD格式)，用于补数据
            fill_gaps: 是否填充数据缺口

        Returns:
            dict: 执行结果
        """
        self.last_run_time = datetime.now()
        logger.info(
            f"开始执行MTR/ATR计算任务，ATR周期={self.atr_period}, "
            f"强制重算={force_recalculate}, start_date={start_date}, "
            f"end_date={end_date}, fill_gaps={fill_gaps}"
        )

        try:
            # 导入计算服务
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from orm.etf.stock_statistics_service import (
                run_incremental_mtr_atr_calculation,
                MTRATRStatusManager
            )

            # 检查配置参数是否变化
            status_manager = MTRATRStatusManager()
            needs_recalculation = status_manager.is_recalculation_needed(self.atr_period) or force_recalculate

            if needs_recalculation:
                logger.info("ATR周期参数变化或强制重算，将重新计算所有股票的MTR/ATR")
            else:
                logger.info("ATR周期参数未变化，将执行增量计算")

            # 执行计算（支持时间范围和补数据）
            result = run_incremental_mtr_atr_calculation(
                atr_period=self.atr_period,
                start_date=start_date,
                end_date=end_date,
                fill_gaps=fill_gaps,
                force_recalculate=force_recalculate
            )

            self.last_result_count = result.get("result_count", 0)
            self.last_status = "success"

            logger.info(f"MTR/ATR计算任务完成，成功计算 {self.last_result_count} 条记录")

            return {
                "status": "success",
                "atr_period": self.atr_period,
                "result_count": self.last_result_count,
                "run_time": self.last_run_time.isoformat(),
                "needs_recalculation": needs_recalculation,
                "start_date": start_date,
                "end_date": end_date,
                "fill_gaps": fill_gaps
            }

        except Exception as e:
            self.last_status = "failed"
            logger.error(f"MTR/ATR计算任务失败: {e}")
            import traceback
            traceback.print_exc()

            return {
                "status": "failed",
                "error": str(e),
                "atr_period": self.atr_period,
                "run_time": self.last_run_time.isoformat()
            }
    
    def get_status(self) -> dict:
        """获取任务状态"""
        return {
            "last_run_time": self.last_run_time.isoformat() if self.last_run_time else None,
            "last_status": self.last_status,
            "last_result_count": self.last_result_count,
            "atr_period": self.atr_period
        }


# Plombery任务定义（如果plombery已安装）
try:
    from plombery import Pipeline, Task, trigger
    
    class MTRATRPlomberyPipeline(Pipeline):
        """MTR/ATR计算的Plombery Pipeline"""
        
        id = "mtr_atr_calculation"
        description = "计算个股的MTR（真实波幅）和ATR（平均真实波幅）"
        
        # 定时触发器：每天16:00执行
        @trigger(schedule="0 16 * * *")
        def daily_mtr_atr_task(self):
            """每日MTR/ATR计算任务"""
            pipeline = MTRATRPipeline(atr_period=14)
            result = pipeline.run()
            
            return result
        
        @trigger(schedule="0 */4 * * *")
        def hourly_mtr_atr_task(self):
            """每4小时MTR/ATR计算任务（用于增量更新）"""
            pipeline = MTRATRPipeline(atr_period=14)
            result = pipeline.run()
            
            return result
    
    __all__ = ["MTRATRPipeline", "MTRATRPlomberyPipeline"]
    
except ImportError:
    logger.warning("Plombery未安装，将使用独立的任务调度器")
    __all__ = ["MTRATRPipeline"]


def main():
    """独立运行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MTR/ATR计算任务")
    parser.add_argument("--period", type=int, default=14, help="ATR计算周期，默认14天")
    parser.add_argument("--force", action="store_true", help="强制重新计算所有数据")
    
    args = parser.parse_args()
    
    pipeline = MTRATRPipeline(atr_period=args.period)
    result = pipeline.run(force_recalculate=args.force)
    
    print(f"任务执行结果: {result}")
    return result


if __name__ == "__main__":
    main()
