"""
定时调度服务

负责每天 16:30 - 22:00 定时触发股票代码生产任务
"""
import logging
import threading
import time
from datetime import datetime, time as dt_time
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class StockProducerScheduler:
    """
    股票代码生产者定时调度器
    
    调度策略：
    - 每天 16:30 - 22:00 期间，每隔一定时间间隔执行一次
    - 检查当前时间是否在时间窗口内
    """
    
    def __init__(self, interval_minutes: int = 30):
        """
        初始化调度器
        
        Args:
            interval_minutes: 检查间隔（分钟），默认 30 分钟
        """
        self.interval_minutes = interval_minutes
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable] = None
        self._last_run_date: Optional[str] = None
        
    def start(self, callback: Callable):
        """
        启动调度器
        
        Args:
            callback: 回调函数，每次触发时执行
        """
        if self._running:
            logger.warning("调度器已在运行中")
            return
        
        self._callback = callback
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="StockProducerScheduler")
        self._thread.start()
        logger.info(f"股票代码生产者调度器已启动，检查间隔: {self.interval_minutes} 分钟")
    
    def stop(self):
        """停止调度器"""
        if not self._running:
            return
        
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("股票代码生产者调度器已停止")
    
    def _run_loop(self):
        """调度主循环"""
        while self._running:
            try:
                self._check_and_run()
            except Exception as e:
                logger.error(f"调度器执行出错: {e}")
            
            # 等待下一个检查周期
            time.sleep(self.interval_minutes * 60)
    
    def _check_and_run(self):
        """检查时间窗口并执行任务"""
        from .config import is_in_time_window, is_enabled
        
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        
        # 检查是否启用
        if not is_enabled():
            logger.debug("生产者未启用，跳过本次检查")
            return
        
        # 检查是否在时间窗口内
        if not is_in_time_window():
            in_window = False
            # 计算下一次执行时间
            config = self._get_time_config()
            start_hour = config.get("start_hour", 16)
            start_minute = config.get("start_minute", 30)
            
            if now.hour < start_hour or (now.hour == start_hour and now.minute < start_minute):
                # 当前在开始时间之前，等待下次
                next_run = now.replace(hour=start_hour, minute=start_minute, second=0)
                if now.hour >= 22:
                    # 过了22点，今天不再执行
                    self._last_run_date = today_str
                    logger.debug(f"当前时间 {now.strftime('%H:%M')} 不在时间窗口内，今天已跳过")
                else:
                    logger.debug(f"当前时间 {now.strftime('%H:%M')} 不在时间窗口内，下次执行: {next_run.strftime('%H:%M')}")
            else:
                # 当前在结束时间之后
                self._last_run_date = today_str
                logger.debug(f"当前时间 {now.strftime('%H:%M')} 不在时间窗口内（已过22:00）")
            return
        
        # 检查今天是否已执行
        if self._last_run_date == today_str:
            logger.debug(f"今天 ({today_str}) 已执行过，跳过")
            return
        
        # 执行回调函数
        if self._callback:
            logger.info(f"时间窗口内，开始执行股票代码生产任务...")
            try:
                result = self._callback()
                self._last_run_date = today_str
                logger.info(f"股票代码生产任务执行完成: {result}")
            except Exception as e:
                logger.error(f"股票代码生产任务执行失败: {e}")
    
    def _get_time_config(self):
        """获取时间窗口配置"""
        from .config import REDIS_STREAM_PRODUCER_CONFIG
        return REDIS_STREAM_PRODUCER_CONFIG.get("time_window", {})
    
    def trigger_now(self) -> dict:
        """
        手动触发立即执行
        
        Returns:
            执行结果
        """
        from .stock_producer_service import produce_stock_codes
        
        if self._callback:
            logger.info("手动触发股票代码生产任务...")
            try:
                result = self._callback()
                self._last_run_date = datetime.now().strftime("%Y-%m-%d")
                return result
            except Exception as e:
                logger.error(f"手动触发失败: {e}")
                return {"success": False, "message": str(e)}
        else:
            return {"success": False, "message": "调度器未启动"}
    
    def get_status(self) -> dict:
        """获取调度器状态"""
        return {
            "running": self._running,
            "interval_minutes": self.interval_minutes,
            "last_run_date": self._last_run_date,
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }


# 全局调度器实例
_scheduler: Optional[StockProducerScheduler] = None


def get_scheduler() -> StockProducerScheduler:
    """获取全局调度器实例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = StockProducerScheduler(interval_minutes=30)
    return _scheduler


def start_scheduler(callback: Callable = None):
    """
    启动全局调度器
    
    Args:
        callback: 回调函数
    """
    from .stock_producer_service import produce_stock_codes
    
    if callback is None:
        callback = lambda: produce_stock_codes(force=True)
    
    scheduler = get_scheduler()
    scheduler.start(callback)


def stop_scheduler():
    """停止全局调度器"""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
        _scheduler = None


def trigger_production() -> dict:
    """
    触发股票代码生产（供外部调用）
    
    Returns:
        执行结果
    """
    from .stock_producer_service import produce_stock_codes
    
    # 尝试使用调度器触发
    scheduler = get_scheduler()
    if scheduler._running:
        return scheduler.trigger_now()
    
    # 直接执行
    return produce_stock_codes(force=True)


if __name__ == "__main__":
    # 测试调度器
    logging.basicConfig(level=logging.INFO)
    
    # 启动调度器
    start_scheduler()
    
    # 保持运行
    try:
        while True:
            time.sleep(60)
            status = get_scheduler().get_status()
            print(f"调度器状态: {status}")
    except KeyboardInterrupt:
        print("停止调度器...")
        stop_scheduler()
