"""
Tsanghi API 分布式锁模块
基于 Redis 实现分布式锁，确保批量操作的并发安全
"""
import time
import uuid
import logging
from typing import Optional
import sys
import os

# 添加项目根目录到sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PatternAnalysis.config import REDIS_CONFIG, TSANGHI_API_CONFIG

logger = logging.getLogger(__name__)

# 分布式锁名称
SYNC_LOCK_KEY = "batch_sync_all"


class RedisLock:
    """基于 Redis 的分布式锁"""

    def __init__(self, lock_key: str, timeout: int = None, prefix: str = None):
        """
        初始化分布式锁

        Args:
            lock_key: 锁的 key
            timeout: 锁超时时间（秒），默认使用配置
            prefix: 锁 key 前缀，默认使用 Tsanghi 配置
        """
        # 默认使用 Tsanghi 的前缀，保持向后兼容
        default_prefix = TSANGHI_API_CONFIG.get('lock_key_prefix', 'tsanghi:sync:lock:')
        self.lock_key = f"{prefix or default_prefix}{lock_key}"
        self.timeout = timeout or TSANGHI_API_CONFIG.get("lock_timeout", 3600)
        self.lock_value = str(uuid.uuid4())  # 锁的值，用于区分不同客户端
        self.redis_client = None

    def _get_redis(self):
        """获取 Redis 客户端"""
        if self.redis_client is None:
            try:
                import redis
                self.redis_client = redis.Redis(
                    host=REDIS_CONFIG["host"],
                    port=REDIS_CONFIG["port"],
                    db=REDIS_CONFIG.get("db", 0),
                    password=REDIS_CONFIG.get("password"),
                    decode_responses=True
                )
            except Exception as e:
                logger.error(f"Redis 连接失败: {e}")
                raise
        return self.redis_client

    def acquire(self, blocking: bool = True, blocking_timeout: int = 30) -> bool:
        """
        获取锁

        Args:
            blocking: 是否阻塞等待
            blocking_timeout: 阻塞超时时间（秒）

        Returns:
            是否成功获取锁
        """
        redis_client = self._get_redis()
        end_time = time.time() + blocking_timeout

        while True:
            # 尝试设置锁（NX: 不存在则设置，PX: 毫秒过期）
            result = redis_client.set(
                self.lock_key,
                self.lock_value,
                nx=True,
                ex=self.timeout
            )

            if result:
                logger.info(f"成功获取锁: {self.lock_key}")
                return True

            if not blocking:
                logger.warning(f"无法获取锁（非阻塞）: {self.lock_key}")
                return False

            # 检查是否超时
            if time.time() >= end_time:
                logger.warning(f"获取锁超时: {self.lock_key}")
                return False

            # 等待后重试
            time.sleep(0.5)

    def release(self) -> bool:
        """
        释放锁（仅释放自己持有的锁）

        Returns:
            是否成功释放
        """
        if not self.redis_client:
            return False

        try:
            # 使用 Lua 脚本确保原子性：仅当锁值匹配时删除
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            result = self.redis_client.eval(lua_script, 1, self.lock_key, self.lock_value)

            if result:
                logger.info(f"成功释放锁: {self.lock_key}")
                return True
            else:
                logger.warning(f"锁已被其他客户端持有或已过期: {self.lock_key}")
                return False
        except Exception as e:
            logger.error(f"释放锁失败: {e}")
            return False

    def __enter__(self):
        """上下文管理器入口"""
        if not self.acquire():
            raise RuntimeError(f"无法获取锁: {self.lock_key}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.release()
        return False


def acquire_lock(lock_key: str, timeout: int = None) -> Optional[RedisLock]:
    """
    获取分布式锁的便捷函数

    Args:
        lock_key: 锁的 key
        timeout: 锁超时时间

    Returns:
        锁对象，获取失败返回 None
    """
    lock = RedisLock(lock_key, timeout)
    if lock.acquire(blocking=True, blocking_timeout=30):
        return lock
    return None


def with_lock(lock_key: str, timeout: int = None):
    """
    分布式锁装饰器

    Args:
        lock_key: 锁的 key
        timeout: 锁超时时间

    Usage:
        @with_lock("my_lock_key")
        def my_function():
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            lock = RedisLock(lock_key, timeout)
            try:
                if lock.acquire(blocking=True, blocking_timeout=30):
                    return func(*args, **kwargs)
                else:
                    raise RuntimeError(f"无法获取锁: {lock_key}")
            finally:
                lock.release()
        return wrapper
    return decorator
