"""
涨跌停状态同步服务 - 随系统启动的分布式执行器

功能：
1. 多节点启动时使用分布式锁避免重复执行
2. 锁超时时间30分钟
3. 启动后后台运行，不阻塞 FastAPI 启动
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Optional

from .limit_status_service import calculate_limit_status_for_all

logger = logging.getLogger(__name__)

# 锁配置
LOCK_KEY = "limit_status:sync:all"
LOCK_TIMEOUT_SECONDS = 1800  # 30分钟

# 环境变量控制
ENV_ENABLED = "LIMIT_STATUS_SYNC_ON_STARTUP_ENABLED"
ENV_LOCK_PREFIX = "LIMIT_STATUS_SYNC_LOCK_PREFIX"

_runner_lock = threading.Lock()
_started_once = False


def _env_str(name: str, default: str) -> str:
    v = os.getenv(name, "")
    return v if v else default


def _env_bool(name: str, default: bool = True) -> bool:
    v = _env_str(name, "").lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "y", "t")


def run_limit_status_sync_on_startup() -> None:
    """
    供 run_server.py 在启动时后台调用
    使用分布式锁确保多节点不重复执行
    """
    global _started_once
    with _runner_lock:
        if _started_once:
            logger.info("涨跌停同步已执行过，跳过")
            return
        _started_once = True

    # 检查是否启用
    if not _env_bool(ENV_ENABLED, True):
        logger.info(f"{ENV_ENABLED}=false，跳过涨跌停启动同步")
        return

    # 获取锁前缀
    lock_prefix = _env_str(ENV_LOCK_PREFIX, "limit_status:sync:lock:")

    # 使用分布式锁
    from PatternAnalysis.tsanghiapi.distributed_lock import RedisLock

    lock_key = f"{lock_prefix}{LOCK_KEY}"
    lock = RedisLock(LOCK_KEY, timeout=LOCK_TIMEOUT_SECONDS, prefix=lock_prefix)

    try:
        acquired = lock.acquire(blocking=False)
        if not acquired:
            logger.info(f"未获取分布式锁 {lock.lock_key}（说明该节点/任务已在运行），跳过")
            return
        logger.info(f"获取分布式锁成功: {lock.lock_key}")
    except Exception as e:
        logger.warning(f"获取分布式锁失败（可能是 Redis 未启动）: {e}，跳过启动同步")
        return

    # 后台执行同步
    def _do_sync():
        try:
            logger.info("开始执行涨跌停状态同步...")
            result = calculate_limit_status_for_all()
            logger.info(f"涨跌停状态同步完成: {result}")
        except Exception as e:
            logger.exception(f"涨跌停状态同步失败: {e}")
        finally:
            # 释放锁
            try:
                lock.release()
                logger.info(f"释放分布式锁: {lock.lock_key}")
            except Exception as e:
                logger.warning(f"释放分布式锁失败: {e}")

    # 后台线程执行
    thread = threading.Thread(target=_do_sync, daemon=True)
    thread.start()
    logger.info("涨跌停状态同步已启动（后台运行）")


def trigger_limit_status_sync(trade_date: Optional[str] = None) -> dict:
    """
    手动触发涨跌停状态同步（带锁）

    Args:
        trade_date: 交易日期，默认最新

    Returns:
        执行结果
    """
    import time
    from PatternAnalysis.tsanghiapi.distributed_lock import RedisLock

    lock_prefix = _env_str(ENV_LOCK_PREFIX, "limit_status:sync:lock:")
    lock_key = f"{lock_prefix}{LOCK_KEY}_manual"
    lock = RedisLock(LOCK_KEY, timeout=300, prefix=lock_prefix)  # 手动触发锁5分钟

    try:
        acquired = lock.acquire(blocking=False)
        if not acquired:
            return {"success": False, "message": "已有同步任务在运行中，请稍后再试"}
    except Exception as e:
        return {"success": False, "message": f"获取锁失败: {e}"}

    try:
        result = calculate_limit_status_for_all(trade_date=trade_date)
        return result
    finally:
        try:
            lock.release()
        except Exception:
            pass