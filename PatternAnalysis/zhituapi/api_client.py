"""
智途API客户端
使用requests库调用接口
"""
import requests
import random
import time
import sys
import os
from typing import List, Optional, Dict, Any
import logging

# 添加项目根目录到sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PatternAnalysis.config import ZHITU_API_CONFIG

logger = logging.getLogger(__name__)

# 从配置中获取参数
API_TOKEN = ZHITU_API_CONFIG["token"]
API_BASE_URL = ZHITU_API_CONFIG["base_url"]
REQUEST_INTERVAL_MIN = ZHITU_API_CONFIG["request_interval_min"]
REQUEST_INTERVAL_MAX = ZHITU_API_CONFIG["request_interval_max"]


class ZhituApiClient:
    """智途API客户端"""

    def __init__(self):
        self.token = API_TOKEN
        self.base_url = API_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.random = random.Random()

    def _make_request(self, url: str) -> Optional[Any]:
        """发起GET请求"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"请求失败: {url}, 错误: {e}")
            return None

    def get_stock_list(self) -> List[Dict]:
        """
        接口一：获取股票列表
        GET https://api.zhituapi.com/hs/list/all?token=xxx
        """
        url = f"{self.base_url}/hs/list/all?token={self.token}"
        logger.info(f"获取股票列表: {url}")

        result = self._make_request(url)
        if result is None:
            return []

        if isinstance(result, list):
            logger.info(f"获取到 {len(result)} 只股票")
            return result
        else:
            logger.warning(f"股票列表返回格式异常: {result}")
            return []

    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        """
        接口二：获取单只股票详细信息
        GET http://api.zhituapi.com/hs/instrument/{stock_code}?token=xxx
        """
        url = f"{self.base_url}/hs/instrument/{stock_code}?token={self.token}"
        logger.info(f"获取股票信息: {stock_code}")

        return self._make_request(url)

    def get_random_interval(self) -> float:
        """获取随机延时时间（秒）5-10秒"""
        return self.random.randint(REQUEST_INTERVAL_MIN, REQUEST_INTERVAL_MAX) / 1000.0

    def sleep_with_interval(self, is_last: bool = False):
        """延时等待"""
        if not is_last:
            interval = self.get_random_interval()
            logger.debug(f"等待 {interval:.2f} 秒后继续...")
            time.sleep(interval)

    def close(self):
        """关闭会话"""
        self.session.close()


def get_stock_list() -> List[Dict]:
    """便捷函数：获取股票列表"""
    client = ZhituApiClient()
    try:
        return client.get_stock_list()
    finally:
        client.close()


def get_stock_info(stock_code: str) -> Optional[Dict]:
    """便捷函数：获取单只股票信息"""
    client = ZhituApiClient()
    try:
        return client.get_stock_info(stock_code)
    finally:
        client.close()
