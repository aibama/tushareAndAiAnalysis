"""
遍历 stockinfobase，调用 Baostock 日线，写入 stocktradetodayinfo（语义对齐 akshare_api.sync_tradetoday_service）。
"""
from __future__ import annotations

import logging
import os
import random
import sys
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PatternAnalysis.akshare_api.stock_list_service import list_stockinfobase_with_stock_code
from PatternAnalysis.akshare_api.tradetoday_upsert import (
    has_tradetoday_data_any,
    has_tradetoday_data_in_range,
    upsert_tradetoday_rows,
)
from PatternAnalysis.config import BAOSTOCK_SYNC_CONFIG
from .hist_service import BaostockHistService
from .utils import AdjustType

logger = logging.getLogger(__name__)

DEFAULT_MAX_WORKERS = int(BAOSTOCK_SYNC_CONFIG.get("max_workers", 1))
DEFAULT_WINDOW_SECONDS = int(BAOSTOCK_SYNC_CONFIG.get("window_seconds", 600))
DEFAULT_REQUEST_LIMIT_PER_WINDOW = int(BAOSTOCK_SYNC_CONFIG.get("request_limit_per_window", 60))
DEFAULT_MIN_INTERVAL_SECONDS = float(BAOSTOCK_SYNC_CONFIG.get("request_min_interval_seconds", 0.5))
DEFAULT_MAX_INTERVAL_SECONDS = float(BAOSTOCK_SYNC_CONFIG.get("request_max_interval_seconds", 2.0))


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
                while self._req_times and now - self._req_times[0] >= self.window_seconds:
                    self._req_times.popleft()

                if len(self._req_times) >= self.request_limit_per_window:
                    sleep_for = max(sleep_for, self.window_seconds - (now - self._req_times[0]) + 0.01)

                sleep_for = max(sleep_for, self._next_allowed_ts - now)

                if sleep_for <= 0:
                    now2 = time.monotonic()
                    self._req_times.append(now2)
                    self._next_allowed_ts = now2 + random.uniform(
                        self.min_interval_seconds, self.max_interval_seconds
                    )
                    return
            time.sleep(sleep_for)


_baostock_limiter_lock = threading.Lock()
_baostock_shared_limiter: Optional[_SlidingWindowLimiter] = None


def _get_baostock_rate_limiter() -> _SlidingWindowLimiter:
    """进程内共享限流器，批量与 Swagger 单股接口共用。"""
    global _baostock_shared_limiter
    with _baostock_limiter_lock:
        if _baostock_shared_limiter is None:
            _baostock_shared_limiter = _SlidingWindowLimiter(
                window_seconds=DEFAULT_WINDOW_SECONDS,
                request_limit_per_window=DEFAULT_REQUEST_LIMIT_PER_WINDOW,
                min_interval_seconds=DEFAULT_MIN_INTERVAL_SECONDS,
                max_interval_seconds=DEFAULT_MAX_INTERVAL_SECONDS,
            )
        return _baostock_shared_limiter


def _sync_one_stock(
    ts_code: str,
    start_date: str,
    end_date: str,
    adjust: AdjustType,
    limiter: _SlidingWindowLimiter,
    dry_run: bool = False,
) -> Dict[str, Any]:
    if not ts_code:
        logger.warning(f"ts_code 为空，跳过")
        return {
            "ts_code": ts_code or "",
            "status": "error",
            "message": "ts_code 为空",
            "rows_saved": 0,
            "rows_fetched": 0,
        }
    try:
        # 检查是否已有数据（幂等跳过）
        if has_tradetoday_data_in_range(ts_code, start_date, end_date):
            logger.info(f"{ts_code}: 区间已有数据，跳过 (start={start_date}, end={end_date})")
            return {
                "ts_code": ts_code,
                "status": "skipped",
                "message": "区间数据已存在，跳过重复同步",
                "rows_saved": 0,
                "rows_fetched": 0,
            }

        # 限流等待
        logger.debug(f"{ts_code}: 等待限流...")
        limiter.acquire()
        logger.debug(f"{ts_code}: 限流通过，开始查询")

        # 查询数据
        hist = BaostockHistService()
        logger.info(f"{ts_code}: 调用 Baostock API 查询 (start={start_date}, end={end_date})...")
        records = hist.query_daily_records(ts_code, start_date, end_date, adjust)

        if not records:
            # API 返回空数据时，判断该股票是否有任何历史数据
            # - 如果有数据：可能是停牌/无交易，视为 "skipped"（已同步过）
            # - 如果无数据：可能是股票代码错误等异常，视为 "error"
            has_any = has_tradetoday_data_any(ts_code)
            if has_any:
                logger.info(f"{ts_code}: Baostock 返回空数据 (start={start_date}, end={end_date})，但该股票已有历史数据，视为停牌/无交易，跳过")
                return {
                    "ts_code": ts_code,
                    "status": "skipped",
                    "message": f"Baostock 返回空数据 (start={start_date}, end={end_date})，该股票已有历史数据，视为停牌",
                    "rows_saved": 0,
                    "rows_fetched": 0,
                }
            else:
                logger.warning(f"{ts_code}: Baostock 返回空数据 (start={start_date}, end={end_date})，该股票无任何历史数据")
                return {
                    "ts_code": ts_code,
                    "status": "error",
                    "message": f"Baostock 返回空数据 (start={start_date}, end={end_date})，该股票无任何历史数据",
                    "rows_saved": 0,
                    "rows_fetched": 0,
                }
        rows_fetched = len(records)
        logger.debug(f"{ts_code}: 获取到 {rows_fetched} 条数据")

        if dry_run:
            logger.info(f"{ts_code}: dry_run - 获取 {rows_fetched} 条，未写库")
            return {
                "ts_code": ts_code,
                "status": "success",
                "message": f"dry_run：已拉取 {rows_fetched} 条，未写库",
                "rows_saved": 0,
                "rows_fetched": rows_fetched,
            }

        # 写入数据库
        logger.debug(f"{ts_code}: 写入数据库...")
        n = upsert_tradetoday_rows(ts_code, records)
        logger.info(f"{ts_code}: 成功写入 {n} 条")

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


def sync_tradetoday_all_from_baostock(
    start_date: str,
    end_date: str,
    adjust: AdjustType = "",
    limit: Optional[int] = None,
    max_workers: Optional[int] = None,
) -> Dict[str, Any]:
    stocks = list_stockinfobase_with_stock_code()
    ts_codes = [str(s.get("ts_code") or "").strip() for s in stocks if s.get("ts_code")]
    if limit is not None and limit > 0:
        ts_codes = ts_codes[:limit]

    return sync_tradetoday_ts_codes_from_baostock(
        ts_codes=ts_codes,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
        max_workers=max_workers,
    )


def sync_tradetoday_ts_codes_from_baostock(
    ts_codes: List[str],
    start_date: str,
    end_date: str,
    adjust: AdjustType = "",
    max_workers: Optional[int] = None,
) -> Dict[str, Any]:
    import baostock as bs

    logger.info("=" * 60)
    logger.info("开始 Baostock 批量同步")
    logger.info(f"参数: start_date={start_date}, end_date={end_date}, adjust={adjust}, ts_codes_count={len(ts_codes)}")
    logger.info("=" * 60)

    workers = max_workers if max_workers is not None else DEFAULT_MAX_WORKERS
    workers = max(1, workers)
    logger.info(f"使用线程数: {workers}")

    limiter = _get_baostock_rate_limiter()
    logger.info(f"限流器: 每 {limiter.window_seconds}s 最多 {limiter.request_limit_per_window} 个请求")
    if not ts_codes:
        logger.warning("ts_codes 为空，跳过同步")
        return {
            "total": 0,
            "success_count": 0,
            "skipped_count": 0,
            "error_count": 0,
            "rows_saved_total": 0,
            "results": [],
            "message": "ts_codes 为空",
        }

    # 登录 Baostock
    logger.info("正在登录 Baostock...")
    lg = bs.login()
    logger.info(f"Baostock 登录结果: error_code={lg.error_code}, error_msg={lg.error_msg}")

    if lg.error_code != "0":
        logger.error(f"Baostock 登录失败: {lg.error_code} {lg.error_msg}")
        return {
            "total": 0,
            "success_count": 0,
            "skipped_count": 0,
            "error_count": 0,
            "rows_saved_total": 0,
            "results": [],
            "message": f"Baostock 登录失败: {lg.error_code} {lg.error_msg}",
        }

    logger.info("Baostock 登录成功")

    results: List[Dict[str, Any]] = []
    success_count = 0
    skipped_count = 0
    error_count = 0
    rows_saved_total = 0

    try:

        def _run() -> None:
            nonlocal success_count, skipped_count, error_count, rows_saved_total, results
            logger.info(f"开始并发同步，使用 {workers} 个线程...")

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

                # 使用 tqdm 风格输出进度（每10个股票或完成时打印）
                completed = 0
                total = len(ts_codes)
                for fut in as_completed(future_map):
                    ts_code = future_map[fut]
                    completed += 1

                    try:
                        r = fut.result()
                        results.append(r)

                        if r.get("status") == "success":
                            success_count += 1
                            rows_saved_total += int(r.get("rows_saved") or 0)
                            logger.info(f"[{completed}/{total}] 成功: {ts_code}, 获取 {r.get('rows_fetched')} 行, 保存 {r.get('rows_saved')} 行")
                        elif r.get("status") == "skipped":
                            skipped_count += 1
                            logger.info(f"[{completed}/{total}] 跳过: {ts_code}, 原因: {r.get('message', '')}")
                        else:
                            error_count += 1
                            logger.warning(f"[{completed}/{total}] 失败: {ts_code}, 错误: {r.get('message', '')}")
                    except Exception as e:
                        error_count += 1
                        logger.exception(f"[{completed}/{total}] 异常: {ts_code}, {e}")
                        results.append({
                            "ts_code": ts_code,
                            "status": "error",
                            "message": str(e),
                            "rows_saved": 0,
                            "rows_fetched": 0,
                        })

            logger.info("=" * 60)
            logger.info("并发同步完成")
            logger.info(f"成功: {success_count}, 跳过: {skipped_count}, 失败: {error_count}")
            logger.info(f"总获取行数: {rows_saved_total}")
            logger.info("=" * 60)

        _run()
    finally:
        logger.info("正在登出 Baostock...")
        bs.logout()
        logger.info("Baostock 已登出")

    return {
        "total": len(results),
        "success_count": success_count,
        "skipped_count": skipped_count,
        "error_count": error_count,
        "rows_saved_total": rows_saved_total,
        "results": results,
    }


def sync_tradetoday_one_from_baostock(
    ts_code: str,
    start_date: str,
    end_date: str,
    adjust: AdjustType = "",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """单只股票同步；供 Swagger GET /api/baostock/sync/tradetoday/one 调用。"""
    import baostock as bs

    limiter = _get_baostock_rate_limiter()
    lg = bs.login()
    if lg.error_code != "0":
        return {
            "ts_code": ts_code.strip(),
            "status": "error",
            "message": f"Baostock 登录失败: {lg.error_code} {lg.error_msg}",
            "rows_saved": 0,
            "rows_fetched": 0,
        }
    try:
        return _sync_one_stock(
            ts_code.strip(),
            start_date,
            end_date,
            adjust,
            limiter,
            dry_run=dry_run,
        )
    finally:
        bs.logout()
