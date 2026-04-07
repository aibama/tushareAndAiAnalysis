"""
Tsanghi API 批量同步服务
功能2：根据 stockinfobase 表批量同步股票日线数据
支持多线程并发和分布式锁
"""
import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import sys
import os

# 添加项目根目录到sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PatternAnalysis.config import TSANGHI_API_CONFIG
from PatternAnalysis.tsanghiapi.api_client import TsanghiApiClient
from PatternAnalysis.tsanghiapi.db_operations import (
    get_all_stock_info,
    get_exchange_code_from_factory_code,
    get_ticker_from_ts_code,
    log_stock_daily_sync_status,
    get_stock_info_by_ts_code,
)
from PatternAnalysis.tsanghiapi.distributed_lock import RedisLock

logger = logging.getLogger(__name__)

# 从配置获取并发数
MAX_WORKERS = TSANGHI_API_CONFIG.get("max_workers", 10)

# 分布式锁名称
SYNC_LOCK_KEY = "batch_sync_all"


class SyncService:
    """批量同步服务（支持多线程并发）"""

    def __init__(self):
        self.client = TsanghiApiClient()
        self.success_count = 0
        self.error_count = 0
        self.count_lock = threading.Lock()

    def sync_single_stock(self, ts_code: str, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """
        同步单个股票的日线数据

        Args:
            ts_code: 股票代码 (如 000001.SZ)
            start_date: 起始日期 (yyyy-mm-dd)，默认 None 表示获取全部历史
            end_date: 结束日期 (yyyy-mm-dd)，默认 None 表示获取到最新

        Returns:
            {'status': 'success'/'error', 'data': ..., 'message': ...}
        """
        try:
            # 1. 从 ts_code 提取 ticker
            ticker = get_ticker_from_ts_code(ts_code)
            if not ticker:
                msg = f"无法从 ts_code 提取 ticker: {ts_code}"
                logger.error(msg)
                log_stock_daily_sync_status(ts_code, "error", msg)
                with self.count_lock:
                    self.error_count += 1
                return {"status": "error", "ts_code": ts_code, "message": msg}

            # 2. 获取 factory_code 并转换为 exchange_code
            stock_info = get_stock_info_by_ts_code(ts_code)

            if not stock_info:
                msg = f"无法获取股票信息: {ts_code}"
                logger.error(msg)
                log_stock_daily_sync_status(ts_code, "error", msg)
                with self.count_lock:
                    self.error_count += 1
                return {"status": "error", "ts_code": ts_code, "message": msg}

            factory_code = stock_info.get("factory_code", "SZ")
            exchange_code = get_exchange_code_from_factory_code(factory_code)

            # 记录日期范围日志
            date_range_str = ""
            if start_date or end_date:
                date_range_str = f", 日期范围: {start_date or '起始'} ~ {end_date or '最新'}"

            logger.info(f"同步股票: ts_code={ts_code}, ticker={ticker}, exchange_code={exchange_code}{date_range_str}")

            # 3. 调用 API 获取数据
            data = self.client.get_daily_data(exchange_code, ticker, start_date, end_date)

            if data is None or len(data) == 0:
                msg = f"API返回空数据: {exchange_code}/{ticker}"
                logger.warning(msg)
                log_stock_daily_sync_status(ts_code, "error", msg)
                with self.count_lock:
                    self.error_count += 1
                return {"status": "error", "ts_code": ts_code, "message": msg}

            # 4. 记录成功日志
            msg = f"成功获取 {len(data)} 条数据"
            log_stock_daily_sync_status(ts_code, "success", msg)
            with self.count_lock:
                self.success_count += 1

            logger.info(f"同步成功: ts_code={ts_code}, 记录数={len(data)}")

            return {
                "status": "success",
                "ts_code": ts_code,
                "data": data,
                "message": msg
            }

        except Exception as e:
            msg = f"同步异常: {e}"
            logger.error(f"同步股票 {ts_code} 时发生异常: {e}")
            log_stock_daily_sync_status(ts_code, "error", msg)
            with self.count_lock:
                self.error_count += 1
            return {"status": "error", "ts_code": ts_code, "message": msg}

    def sync_all_stocks(self, limit: int = None, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        """
        同步所有股票的日线数据（多线程并发）

        Args:
            limit: 限制同步数量（用于测试）
            start_date: 起始日期 (yyyy-mm-dd)，默认 None 表示获取全部历史
            end_date: 结束日期 (yyyy-mm-dd)，默认 None 表示获取到最新

        Returns:
            同步结果列表
        """
        # 记录日期范围
        date_range_str = ""
        if start_date or end_date:
            date_range_str = f", 日期范围: {start_date or '起始'} ~ {end_date or '最新'}"

        logger.info(f"开始批量同步所有股票日线数据（并发数：{MAX_WORKERS}）{date_range_str}...")

        # 1. 获取所有股票信息
        stocks = get_all_stock_info()

        if not stocks:
            logger.warning("stockinfobase 表中没有股票数据")
            return []

        logger.info(f"共获取 {len(stocks)} 只股票")

        # 2. 准备任务
        ts_codes = [stock.get("ts_code") for stock in stocks if stock.get("ts_code")]

        if limit:
            ts_codes = ts_codes[:limit]

        # 3. 多线程并发执行
        results = []
        self.success_count = 0
        self.error_count = 0

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # 提交所有任务
            future_to_ts_code = {
                executor.submit(self.sync_single_stock, ts_code, start_date, end_date): ts_code
                for ts_code in ts_codes
            }

            # 收集结果
            for future in as_completed(future_to_ts_code):
                ts_code = future_to_ts_code[future]
                try:
                    result = future.result()
                    results.append(result)

                    # 实时输出进度
                    total = len(ts_codes)
                    done = len(results)
                    if done % 100 == 0 or done == total:
                        logger.info(f"进度: {done}/{total}, 成功: {self.success_count}, 失败: {self.error_count}")

                except Exception as e:
                    logger.error(f"处理股票 {ts_code} 时发生异常: {e}")
                    results.append({
                        "status": "error",
                        "ts_code": ts_code,
                        "message": str(e)
                    })

        # 4. 输出统计
        logger.info(f"批量同步完成: 成功={self.success_count}, 失败={self.error_count}")

        return results

    def close(self):
        """关闭服务"""
        self.client.close()


# 便捷函数
def sync_single_stock(ts_code: str, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    """同步单个股票（便捷函数）"""
    service = SyncService()
    try:
        return service.sync_single_stock(ts_code, start_date, end_date)
    finally:
        service.close()


def sync_all_stocks(limit: int = None, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
    """同步所有股票（便捷函数）"""
    service = SyncService()
    try:
        return service.sync_all_stocks(limit, start_date, end_date)
    finally:
        service.close()


# 带分布式锁的同步函数
def sync_all_stocks_with_lock(limit: int = None, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    """
    带分布式锁的批量同步（确保并发安全）

    Args:
        limit: 限制同步数量
        start_date: 起始日期 (yyyy-mm-dd)
        end_date: 结束日期 (yyyy-mm-dd)

    Returns:
        {'success': bool, 'message': str, 'data': {...}}
    """
    lock = RedisLock(SYNC_LOCK_KEY)

    try:
        # 尝试获取锁
        if not lock.acquire(blocking=True, blocking_timeout=30):
            return {
                "success": False,
                "message": "无法获取分布式锁，可能有其他进程正在执行同步",
                "data": None
            }

        logger.info("获取分布式锁成功，开始执行同步...")

        # 执行同步
        results = sync_all_stocks(limit, start_date, end_date)

        return {
            "success": True,
            "message": f"同步完成: 成功={sum(1 for r in results if r.get('status') == 'success')}, 失败={sum(1 for r in results if r.get('status') == 'error')}",
            "data": {
                "total": len(results),
                "success_count": sum(1 for r in results if r.get('status') == 'success'),
                "error_count": sum(1 for r in results if r.get('status') == 'error'),
            }
        }

    except Exception as e:
        logger.error(f"同步过程发生异常: {e}")
        return {
            "success": False,
            "message": f"同步异常: {str(e)}",
            "data": None
        }

    finally:
        lock.release()
        logger.info("分布式锁已释放")
