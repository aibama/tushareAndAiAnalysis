"""
Tsanghi API 客户端
用于获取股票历史日线数据
支持多线程并发和限流控制
"""
import requests
import random
import time
import logging
import threading
from typing import List, Optional, Dict, Any
from collections import deque
import sys
import os

# 添加项目根目录到sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PatternAnalysis.config import TSANGHI_API_CONFIG, REDIS_CONFIG

logger = logging.getLogger(__name__)

# 从配置中获取参数
API_TOKEN = TSANGHI_API_CONFIG["token"]
API_BASE_URL = TSANGHI_API_CONFIG["base_url"]
REQUEST_TIMEOUT = TSANGHI_API_CONFIG.get("request_timeout", 30)
RETRY_TIMES = TSANGHI_API_CONFIG.get("retry_times", 3)
RETRY_INTERVAL = TSANGHI_API_CONFIG.get("retry_interval", 5)
MAX_WORKERS = TSANGHI_API_CONFIG.get("max_workers", 10)
RATE_LIMIT_PER_MINUTE = TSANGHI_API_CONFIG.get("rate_limit_per_minute", 60)


class RateLimiter:
    """令牌桶限流器"""

    def __init__(self, max_per_minute: int):
        """
        初始化限流器

        Args:
            max_per_minute: 每分钟最大请求数
        """
        self.max_per_minute = max_per_minute
        self.interval = 60.0 / max_per_minute  # 每个请求之间的最小间隔
        self.last_request_time = 0
        self.lock = threading.Lock()

    def acquire(self):
        """获取令牌（阻塞等待）"""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time

            if elapsed < self.interval:
                # 需要等待
                sleep_time = self.interval - elapsed
                time.sleep(sleep_time)
                now = time.time()

            self.last_request_time = now


# 全局限流器（所有线程共享）
_global_rate_limiter = RateLimiter(RATE_LIMIT_PER_MINUTE)


class TsanghiApiClient:
    """Tsanghi API 客户端"""

    def __init__(self, token: str = None, use_rate_limit: bool = True):
        self.token = token or API_TOKEN
        self.base_url = API_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.random = random.Random()
        self.use_rate_limit = use_rate_limit

    def _make_request(self, url: str, max_retries: int = None) -> Optional[Any]:
        """发起GET请求，带重试机制和限流"""
        max_retries = max_retries or RETRY_TIMES

        # 限流
        if self.use_rate_limit:
            _global_rate_limiter.acquire()

        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                logger.warning(f"请求失败 (尝试 {attempt + 1}/{max_retries}): {url}, 错误: {e}")
                if attempt < max_retries - 1:
                    time.sleep(RETRY_INTERVAL)
                else:
                    logger.error(f"请求最终失败: {url}")
                    return None
        return None

    def _build_url(self, exchange_code: str, ticker: str,
                  start_date: str = None, end_date: str = None) -> str:
        """构建请求URL"""
        url = f"{self.base_url}/{exchange_code}/daily?token={self.token}&ticker={ticker}"

        if start_date:
            url += f"&start_date={start_date}"
        if end_date:
            url += f"&end_date={end_date}"

        return url

    def get_daily_data(self, exchange_code: str, ticker: str,
                       start_date: str = None, end_date: str = None) -> Optional[List[Dict[str, Any]]]:
        """
        获取股票日线数据

        Args:
            exchange_code: 交易所代码 (XSHG, XSHE, XNAS)
            ticker: 股票代码 (如 600519)
            start_date: 起始日期 (yyyy-mm-dd)
            end_date: 结束日期 (yyyy-mm-dd)

        Returns:
            日线数据列表，失败返回None
        """
        url = self._build_url(exchange_code, ticker, start_date, end_date)
        logger.info(f"请求日线数据: {url}")

        result = self._make_request(url)

        if result is None:
            return None

        # 检查API返回状态
        if result.get("code") == 200:
            data = result.get("data", [])
            logger.info(f"成功获取 {len(data)} 条日线数据: {exchange_code}/{ticker}")
            return data
        else:
            logger.error(f"API返回错误: code={result.get('code')}, msg={result.get('msg')}")
            return None

    def get_stock_date_range(self, exchange_code: str, ticker: str) -> Optional[Dict[str, str]]:
        """
        获取个股的开始时间和结束时间

        Args:
            exchange_code: 交易所代码
            ticker: 股票代码

        Returns:
            {'start_date': 'yyyy-mm-dd', 'end_date': 'yyyy-mm-dd'} 或 None
        """
        data = self.get_daily_data(exchange_code, ticker)

        if data is None or len(data) == 0:
            return None

        # 数据按日期降序排列
        dates = [item.get("date") for item in data if item.get("date")]

        if not dates:
            return None

        return {
            "start_date": min(dates),
            "end_date": max(dates)
        }

    def close(self):
        """关闭会话"""
        self.session.close()


# 便捷函数
def get_daily_data(exchange_code: str, ticker: str,
                   start_date: str = None, end_date: str = None) -> Optional[List[Dict[str, Any]]]:
    """获取股票日线数据（便捷函数）"""
    client = TsanghiApiClient()
    try:
        return client.get_daily_data(exchange_code, ticker, start_date, end_date)
    finally:
        client.close()


def get_stock_date_range(exchange_code: str, ticker: str) -> Optional[Dict[str, str]]:
    """获取个股日期范围（便捷函数）"""
    client = TsanghiApiClient()
    try:
        return client.get_stock_date_range(exchange_code, ticker)
    finally:
        client.close()


# 多线程并发控制
_thread_pool = None
_thread_pool_lock = threading.Lock()


def get_thread_pool():
    """获取线程池（单例）"""
    global _thread_pool

    if _thread_pool is None:
        with _thread_pool_lock:
            if _thread_pool is None:
                from concurrent.futures import ThreadPoolExecutor
                _thread_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    return _thread_pool
