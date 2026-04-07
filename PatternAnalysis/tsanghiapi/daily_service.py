"""
Tsanghi API 股票日线数据服务
功能1：获取个股的开始时间和结束时间的历史数据接口
"""
import logging
from typing import Optional, Dict, List, Any
import sys
import os

# 添加项目根目录到sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PatternAnalysis.tsanghiapi.api_client import TsanghiApiClient

logger = logging.getLogger(__name__)


class DailyDataService:
    """股票日线数据服务"""

    def __init__(self):
        self.client = TsanghiApiClient()

    def get_stock_date_range(self, exchange_code: str, ticker: str) -> Optional[Dict[str, str]]:
        """
        获取个股的开始时间和结束时间

        Args:
            exchange_code: 交易所代码 (XSHG, XSHE, XNAS)
            ticker: 股票代码 (如 600519)

        Returns:
            {'start_date': 'yyyy-mm-dd', 'end_date': 'yyyy-mm-dd'} 或 None
        """
        logger.info(f"获取个股日期范围: {exchange_code}/{ticker}")
        return self.client.get_stock_date_range(exchange_code, ticker)

    def get_stock_full_history(self, exchange_code: str, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """
        获取个股的全部历史数据（从开始到结束）

        Args:
            exchange_code: 交易所代码
            ticker: 股票代码

        Returns:
            日线数据列表
        """
        logger.info(f"获取个股全部历史数据: {exchange_code}/{ticker}")

        # 先获取日期范围
        date_range = self.client.get_stock_date_range(exchange_code, ticker)

        if date_range is None:
            logger.warning(f"无法获取 {exchange_code}/{ticker} 的日期范围")
            return None

        start_date = date_range.get("start_date")
        end_date = date_range.get("end_date")

        logger.info(f"日期范围: {start_date} ~ {end_date}")

        # 获取完整历史数据
        return self.client.get_daily_data(exchange_code, ticker, start_date, end_date)

    def get_stock_history_by_range(self, exchange_code: str, ticker: str,
                                   start_date: str, end_date: str) -> Optional[List[Dict[str, Any]]]:
        """
        根据指定日期范围获取历史数据

        Args:
            exchange_code: 交易所代码
            ticker: 股票代码
            start_date: 起始日期 (yyyy-mm-dd)
            end_date: 结束日期 (yyyy-mm-dd)

        Returns:
            日线数据列表
        """
        logger.info(f"获取指定范围历史数据: {exchange_code}/{ticker}, {start_date} ~ {end_date}")
        return self.client.get_daily_data(exchange_code, ticker, start_date, end_date)

    def close(self):
        """关闭服务"""
        self.client.close()


# 便捷函数
def get_stock_date_range(exchange_code: str, ticker: str) -> Optional[Dict[str, str]]:
    """获取个股日期范围（便捷函数）"""
    service = DailyDataService()
    try:
        return service.get_stock_date_range(exchange_code, ticker)
    finally:
        service.close()


def get_stock_full_history(exchange_code: str, ticker: str) -> Optional[List[Dict[str, Any]]]:
    """获取个股全部历史数据（便捷函数）"""
    service = DailyDataService()
    try:
        return service.get_stock_full_history(exchange_code, ticker)
    finally:
        service.close()


def get_stock_history_by_range(exchange_code: str, ticker: str,
                               start_date: str, end_date: str) -> Optional[List[Dict[str, Any]]]:
    """获取指定范围历史数据（便捷函数）"""
    service = DailyDataService()
    try:
        return service.get_stock_history_by_range(exchange_code, ticker, start_date, end_date)
    finally:
        service.close()
