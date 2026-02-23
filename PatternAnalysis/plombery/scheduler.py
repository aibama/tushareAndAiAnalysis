"""
独立任务调度器
当plombery不可用时，使用此调度器进行任务调度
"""
import sys
import os

# 添加项目根目录到Python路径，确保模块导入正常工作
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Callable, Optional, Dict
from croniter import croniter

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Task:
    """任务定义"""
    
    def __init__(
        self,
        task_id: str,
        func: Callable,
        schedule: str,
        description: str = "",
        **kwargs
    ):
        """
        初始化任务
        
        Args:
            task_id: 任务ID
            func: 任务函数
            schedule: Cron表达式
            description: 任务描述
            **kwargs: 传递给任务函数的额外参数
        """
        self.task_id = task_id
        self.func = func
        self.schedule = schedule
        self.description = description
        self.kwargs = kwargs
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        self.is_running = False
    
    def calculate_next_run(self, base_time: datetime = None):
        """计算下次运行时间"""
        if base_time is None:
            base_time = datetime.now()
        
        cron = croniter(self.schedule, base_time)
        self.next_run = cron.get_next(datetime)
        return self.next_run


class Scheduler:
    """独立任务调度器"""
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.running = False
        self.thread: Optional[threading.Thread] = None
    
    def add_task(self, task: Task):
        """添加任务"""
        task.calculate_next_run()
        self.tasks[task.task_id] = task
        logger.info(f"任务已添加: {task.task_id} (ID: {task.task_id}, 下次运行: {task.next_run})")
    
    def remove_task(self, task_id: str):
        """移除任务"""
        if task_id in self.tasks:
            del self.tasks[task_id]
            logger.info(f"任务已移除: {task_id}")
    
    def _run_task(self, task: Task):
        """运行任务"""
        if task.is_running:
            logger.warning(f"任务 {task.task_id} 正在运行，跳过本次执行")
            return
        
        task.is_running = True
        task.last_run = datetime.now()
        
        try:
            logger.info(f"开始执行任务: {task.task_id}")
            result = task.func(**task.kwargs)
            logger.info(f"任务 {task.task_id} 执行完成，结果: {result}")
        except Exception as e:
            logger.error(f"任务 {task.task_id} 执行失败: {e}")
        finally:
            task.is_running = False
            task.calculate_next_run()
    
    def _scheduler_loop(self):
        """调度器主循环"""
        while self.running:
            now = datetime.now()
            
            for task_id, task in list(self.tasks.items()):
                if task.next_run and now >= task.next_run and not task.is_running:
                    logger.info(f"触发任务: {task_id}")
                    threading.Thread(
                        target=self._run_task,
                        args=(task,),
                        name=f"Task-{task_id}"
                    ).start()
            
            # 休眠1秒后继续检查
            time.sleep(1)
    
    def start(self):
        """启动调度器"""
        if self.running:
            logger.warning("调度器已在运行")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._scheduler_loop, name="Scheduler")
        self.thread.daemon = True
        self.thread.start()
        logger.info("任务调度器已启动")
    
    def stop(self):
        """停止调度器"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("任务调度器已停止")
    
    def get_status(self) -> Dict:
        """获取调度器状态"""
        return {
            "running": self.running,
            "task_count": len(self.tasks),
            "tasks": {
                task_id: {
                    "description": task.description,
                    "schedule": task.schedule,
                    "last_run": task.last_run.isoformat() if task.last_run else None,
                    "next_run": task.next_run.isoformat() if task.next_run else None,
                    "is_running": task.is_running
                }
                for task_id, task in self.tasks.items()
            }
        }


# 默认调度器实例
default_scheduler = Scheduler()


def start_scheduler():
    """启动默认调度器"""
    default_scheduler.start()


def stop_scheduler():
    """停止默认调度器"""
    default_scheduler.stop()


def add_scheduled_task(task_id: str, func: Callable, schedule: str, description: str = "", **kwargs):
    """添加定时任务"""
    task = Task(task_id, func, schedule, description, **kwargs)
    default_scheduler.add_task(task)


def setup_default_tasks():
    """设置默认任务"""
    try:
        from .mtr_atr_pipeline import MTRATRPipeline
    except ImportError:
        from mtr_atr_pipeline import MTRATRPipeline
    
    # 每日16:00执行MTR/ATR计算
    add_scheduled_task(
        task_id="daily_mtr_atr",
        func=MTRATRPipeline,
        schedule="0 16 * * *",
        description="每日MTR/ATR计算任务",
        atr_period=14
    )
    
    # 每4小时执行增量更新
    add_scheduled_task(
        task_id="hourly_mtr_atr",
        func=MTRATRPipeline,
        schedule="0 */4 * * *",
        description="每4小时MTR/ATR增量更新",
        atr_period=14
    )


if __name__ == "__main__":
    # 设置默认任务
    setup_default_tasks()
    
    # 启动调度器
    start_scheduler()
    
    # 保持运行
    try:
        while True:
            time.sleep(60)
            status = default_scheduler.get_status()
            print(f"调度器状态: {status['running']}, 任务数: {status['task_count']}")
    except KeyboardInterrupt:
        stop_scheduler()
