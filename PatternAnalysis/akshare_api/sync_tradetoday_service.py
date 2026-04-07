"""
遍历 stockinfobase，调用 AkShare 日线，写入 stocktradetodayinfo。
"""
from __future__ import annotations

import logging
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import deque
from typing import Any, Dict, List, Optional

import sys
import os

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PatternAnalysis.config import AKSHARE_SYNC_CONFIG
from PatternAnalysis.akshare_api.hist_service import StockZhAHistService, AdjustType
from PatternAnalysis.akshare_api.stock_list_service import list_stockinfobase_with_stock_code
from PatternAnalysis.akshare_api.tradetoday_upsert import (
    has_tradetoday_data_in_range,
    upsert_tradetoday_rows,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_WORKERS = int(AKSHARE_SYNC_CONFIG.get("max_workers", 2))
DEFAULT_WINDOW_SECONDS = int(AKSHARE_SYNC_CONFIG.get("window_seconds", 600))
DEFAULT_REQUEST_LIMIT_PER_WINDOW = int(AKSHARE_SYNC_CONFIG.get("request_limit_per_window", 80))
DEFAULT_MIN_INTERVAL_SECONDS = float(AKSHARE_SYNC_CONFIG.get("request_min_interval_seconds", 0.4))
DEFAULT_MAX_INTERVAL_SECONDS = float(AKSHARE_SYNC_CONFIG.get("request_max_interval_seconds", 1.6))


class _SlidingWindowLimiter:
    """线程安全滑动窗口限流器：限制窗口总次数 + 请求间随机间隔。"""

    def __init__(
        self,
        window_seconds: int,
        request_limit_per_window: int,
        min_interval_seconds: float,
        max_interval_seconds: float,
    ) -> None:
        self.window_seconds = max(1, int(window_seconds))
        self.request_limit_per_window = max(1, int(request_limit_per_window))
        self.min_interval_seconds = max(0.0, float(min_interval_seconds))
        self.max_interval_seconds = max(self.min_interval_seconds, float(max_interval_seconds))
        self._lock = threading.Lock()
        self._req_times: deque[float] = deque()
        self._next_allowed_ts: float = 0.0

    def acquire(self) -> None:
        while True:
            sleep_for = 0.0
            with self._lock:
                now = time.monotonic()
                # 清理窗口外请求
                while self._req_times and now - self._req_times[0] >= self.window_seconds:
                    self._req_times.popleft()

                # 10分钟窗口上限
                if len(self._req_times) >= self.request_limit_per_window:
                    sleep_for = max(sleep_for, self.window_seconds - (now - self._req_times[0]) + 0.01)

                # 请求间随机间隔
                sleep_for = max(sleep_for, self._next_allowed_ts - now)

                if sleep_for <= 0:
                    now2 = time.monotonic()
                    self._req_times.append(now2)
                    self._next_allowed_ts = now2 + random.uniform(
                        self.min_interval_seconds, self.max_interval_seconds
                    )
                    return
            time.sleep(sleep_for)


_akshare_limiter_lock = threading.Lock()
_akshare_shared_limiter: Optional[_SlidingWindowLimiter] = None


def _get_akshare_rate_limiter() -> _SlidingWindowLimiter:
    """进程内共享限流器，批量同步与 Swagger 单股接口共用。"""
    global _akshare_shared_limiter
    with _akshare_limiter_lock:
        if _akshare_shared_limiter is None:
            _akshare_shared_limiter = _SlidingWindowLimiter(
                window_seconds=DEFAULT_WINDOW_SECONDS,
                request_limit_per_window=DEFAULT_REQUEST_LIMIT_PER_WINDOW,
                min_interval_seconds=DEFAULT_MIN_INTERVAL_SECONDS,
                max_interval_seconds=DEFAULT_MAX_INTERVAL_SECONDS,
            )
        return _akshare_shared_limiter


def _sync_one_stock(
    ts_code: str,
    start_date: str,
    end_date: str,
    adjust: AdjustType,
    limiter: _SlidingWindowLimiter,
    dry_run: bool = False,
) -> Dict[str, Any]:
    if not ts_code:
        return {
            "ts_code": ts_code or "",
            "status": "error",
            "message": "ts_code 为空",
            "rows_saved": 0,
            "rows_fetched": 0,
        }
    try:
        if has_tradetoday_data_in_range(ts_code, start_date, end_date):
            return {
                "ts_code": ts_code,
                "status": "skipped",
                "message": "区间数据已存在，跳过重复同步",
                "rows_saved": 0,
                "rows_fetched": 0,
            }

        limiter.acquire()
        hist = StockZhAHistService()
        records = hist.get_hist(
            symbol=ts_code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
            as_dataframe=False,
        )
        if not isinstance(records, list) or len(records) == 0:
            return {
                "ts_code": ts_code,
                "status": "error",
                "message": "AkShare 返回空数据",
                "rows_saved": 0,
                "rows_fetched": 0,
            }
        rows_fetched = len(records)
        if dry_run:
            return {
                "ts_code": ts_code,
                "status": "success",
                "message": f"dry_run：已拉取 {rows_fetched} 条，未写库",
                "rows_saved": 0,
                "rows_fetched": rows_fetched,
            }
        n = upsert_tradetoday_rows(ts_code, records)
        return {
            "ts_code": ts_code,
            "status": "success",
            "message": f"写入 {n} 条",
            "rows_saved": n,
            "rows_fetched": rows_fetched,
        }
    except Exception as e:
        logger.exception("同步失败 ts_code=%s: %s", ts_code, e)
        return {
            "ts_code": ts_code,
            "status": "error",
            "message": str(e),
            "rows_saved": 0,
            "rows_fetched": 0,
        }


def sync_tradetoday_all_from_akshare(
    start_date: str,
    end_date: str,
    adjust: AdjustType = "",
    limit: Optional[int] = None,
    max_workers: Optional[int] = None,
) -> Dict[str, Any]:
    """
    从 stockinfobase 取全部股票，按日期区间拉取 AkShare 日线并写入 stocktradetodayinfo。

    Args:
        start_date: yyyy-mm-dd 或 yyyymmdd
        end_date: 同上
        adjust: 不复权 ``""``，前复权 ``qfq``，后复权 ``hfq``
        limit: 仅处理前 N 条（测试用）
        max_workers: 线程数，默认读取 AKSHARE_SYNC_CONFIG
    """
    workers = max_workers if max_workers is not None else DEFAULT_MAX_WORKERS
    workers = max(1, workers)
    limiter = _get_akshare_rate_limiter()

    stocks = list_stockinfobase_with_stock_code()
    if not stocks:
        return {
            "total": 0,
            "success_count": 0,
            "skipped_count": 0,
            "error_count": 0,
            "rows_saved_total": 0,
            "results": [],
            "message": "stockinfobase 无数据",
        }

    ts_codes = [str(s.get("ts_code") or "").strip() for s in stocks if s.get("ts_code")]
    if limit is not None and limit > 0:
        ts_codes = ts_codes[:limit]

    results: List[Dict[str, Any]] = []
    success_count = 0
    skipped_count = 0
    error_count = 0
    rows_saved_total = 0

    def _run():
        nonlocal success_count, skipped_count, error_count, rows_saved_total, results
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {
                executor.submit(
                    _sync_one_stock,
                    ts_code,
                    start_date,
                    end_date,
                    adjust,
                    limiter,
                    False,
                ): ts_code
                for ts_code in ts_codes
            }

            for fut in as_completed(future_map):
                r = fut.result()
                results.append(r)
                if r.get("status") == "success":
                    success_count += 1
                    rows_saved_total += int(r.get("rows_saved") or 0)
                elif r.get("status") == "skipped":
                    skipped_count += 1
                else:
                    error_count += 1

    _run()

    return {
        "total": len(results),
        "success_count": success_count,
        "skipped_count": skipped_count,
        "error_count": error_count,
        "rows_saved_total": rows_saved_total,
        "results": results,
    }


def sync_tradetoday_one_from_akshare(
    ts_code: str,
    start_date: str,
    end_date: str,
    adjust: AdjustType = "",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """单只股票同步（与批量共用限流器）；供 Swagger /api/akshare/sync/tradetoday/one 调用。"""
    limiter = _get_akshare_rate_limiter()
    return _sync_one_stock(
        ts_code.strip(),
        start_date,
        end_date,
        adjust,
        limiter,
        dry_run=dry_run,
    )
