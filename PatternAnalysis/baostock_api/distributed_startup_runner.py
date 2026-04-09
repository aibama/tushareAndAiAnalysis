"""
Baostock /api/baostock/sync/tradetoday/all 的逻辑抽离后的"启动分布式执行器"。

目标：
1) 多节点（多个进程/机器）同时启动时，按 node_id/node_count 分片执行；
2) 使用 Redis 分布式锁避免同一 node_id 的重复触发；
3) 启动后后台运行，不阻塞 FastAPI/uvicorn 启动。
"""
from __future__ import annotations

import logging
import os
import threading
from typing import List

from PatternAnalysis.akshare_api.stock_list_service import (
    list_stockinfobase_with_stock_code,
)
from PatternAnalysis.baostock_api.sync_tradetoday_service import (
    sync_tradetoday_ts_codes_from_baostock,
)
from PatternAnalysis.tsanghiapi.distributed_lock import RedisLock
from PatternAnalysis.baostock_api.startup_sync_dates import resolve_startup_sync_date_range
from PatternAnalysis.config import BAOSTOCK_SYNC_CONFIG

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name, "")
    if not v:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    v = os.getenv(name, "")
    return v if v else default


_runner_lock = threading.Lock()
_started_once = False


def run_baostock_tradetoday_distributed_on_startup() -> None:
    """
    供 run_server.py 在启动时后台调用。
    同步区间见 `startup_sync_dates.resolve_startup_sync_date_range`；分片/锁等仍由环境变量控制。
    """
    global _started_once
    with _runner_lock:
        if _started_once:
            return
        _started_once = True

    # 读取配置中的 enabled，fallback 到环境变量
    config_enabled = BAOSTOCK_SYNC_CONFIG.get("enabled")
    if config_enabled is not None:
        enabled = config_enabled
    else:
        # 兼容旧环境变量逻辑
        enabled = _env_str("BAOSTOCK_SYNC_ON_STARTUP_ENABLED", "true").lower() in (
            "1",
            "true",
            "yes",
            "y",
            "t",
        )
    if not enabled:
        logger.info("BAOSTOCK_SYNC_CONFIG.enabled=false，跳过启动自动同步")
        return

    adjust = _env_str("BAOSTOCK_SYNC_ADJUST", "")
    if adjust not in ("", "qfq", "hfq"):
        logger.warning("BAOSTOCK_SYNC_ADJUST 非法: %r，回退到 ''", adjust)
        adjust = ""

    # 日期：sync_min_start_date + stocktradetodayinfo MAX(trade_date) + china_stock_trading_day_checker 日历最近交易日；
    # 可用环境变量 BAOSTOCK_SYNC_START_DATE + BAOSTOCK_SYNC_END_DATE 同时指定以覆盖（见 README）
    range_pair = resolve_startup_sync_date_range()
    if range_pair is None:
        logger.info("无需启动 Baostock 同步（已最新或无有效区间）")
        return
    start_date, end_date = range_pair

    node_id = _env_int("BAOSTOCK_SYNC_NODE_ID", 0)
    node_count = _env_int("BAOSTOCK_SYNC_NODE_COUNT", 1)
    node_count = max(1, node_count)
    node_id = max(0, node_id)
    if node_id >= node_count:
        logger.warning("BAOSTOCK_SYNC_NODE_ID(%s) >= NODE_COUNT(%s)，将 node_id 回退到 0", node_id, node_count)
        node_id = 0

    limit_per_node = _env_int("BAOSTOCK_SYNC_LIMIT_PER_NODE", 0)
    max_workers = _env_int("BAOSTOCK_SYNC_MAX_WORKERS", 0) or None

    use_global_lock = _env_str("BAOSTOCK_SYNC_USE_GLOBAL_LOCK", "false").lower() in (
        "1",
        "true",
        "yes",
        "y",
        "t",
    )

    logger.debug("开始获取 stockinfobase 列表...")

    # 取 stockinfobase 全量 ts_code，并按 node_id/node_count 切分
    stocks = list_stockinfobase_with_stock_code()
    logger.debug(f"获取到 {len(stocks)} 只股票")

    # 注意：stockinfobase 查询未必有 ORDER BY，不同节点/不同启动时间可能返回顺序不同。
    # 为保证"跨节点不重叠"，这里对 ts_code 做确定性排序后再按 i%node_count 分片。
    all_ts_codes: List[str] = [str(s.get("ts_code") or "").strip() for s in stocks if s.get("ts_code")]
    all_ts_codes = sorted({c for c in all_ts_codes if c})
    logger.debug(f"去重后 {len(all_ts_codes)} 只股票")

    if not all_ts_codes:
        logger.warning("stockinfobase 为空，跳过 baostock 同步")
        return

    # 为保证幂等判断一致，分片基于稳定的 enumerate 顺序（已在上面完成排序）
    partitioned_ts_codes = [
        c for i, c in enumerate(all_ts_codes) if (i % node_count) == node_id
    ]
    logger.debug(f"本节点分片 {len(partitioned_ts_codes)} 只股票 (node_id={node_id})")

    if limit_per_node and limit_per_node > 0:
        partitioned_ts_codes = partitioned_ts_codes[:limit_per_node]

    if not partitioned_ts_codes:
        logger.info("本节点分片为空（node_id=%s），跳过", node_id)
        return

    logger.debug("开始获取分布式锁...")

    lock_timeout_sec = _env_int("BAOSTOCK_SYNC_LOCK_TIMEOUT_SECONDS", 21600)  # 默认 6 小时
    # 锁 key：默认"每节点一把锁"，允许不同 node_id 并行；若用 global lock 则所有节点互斥
    if use_global_lock:
        lock_key = f"baostock:sync:tradetoday:{start_date}:{end_date}:{adjust}"
    else:
        lock_key = f"baostock:sync:tradetoday:{start_date}:{end_date}:{adjust}:node{node_id}"

    lock = None
    try:
        # 使用独立的 Baostock 锁前缀，避免与 Tsanghi 冲突
        lock = RedisLock(lock_key, timeout=lock_timeout_sec, prefix="baostock:sync:lock:")
        acquired = lock.acquire(blocking=False)
        if not acquired:
            logger.info("未获取分布式锁 %s（说明该节点/任务已在运行），跳过", lock.lock_key)
            return
        logger.debug("分布式锁获取成功: %s", lock.lock_key)
    except Exception as e:
        logger.warning(f"获取分布式锁失败（可能是 Redis 未启动）: {e}，跳过启动同步")
        return

    try:
        logger.info(
            "启动 Baostock 分布式同步: start=%s end=%s adjust=%s node_id=%s node_count=%s ts_codes=%s",
            start_date,
            end_date,
            adjust,
            node_id,
            node_count,
            len(partitioned_ts_codes),
        )
        sync_tradetoday_ts_codes_from_baostock(
            ts_codes=partitioned_ts_codes,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
            max_workers=max_workers,
        )
    finally:
        # 注意：即使 sync 抛异常也要释放锁，避免卡死
        try:
            lock.release()
        except Exception:
            logger.exception("释放锁失败: %s", lock.lock_key)

