"""
Tsanghi API 路由
提供 HTTP 接口访问股票日线数据
支持分布式锁保护批量操作
"""
from fastapi import APIRouter, Query, Path, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import logging
import sys
import os

# 添加项目根目录到sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PatternAnalysis.tsanghiapi.daily_service import DailyDataService
from PatternAnalysis.tsanghiapi.sync_service import (
    SyncService,
    sync_single_stock,
    sync_all_stocks,
    sync_all_stocks_with_lock,
)
from PatternAnalysis.tsanghiapi.db_operations import (
    get_stock_info_by_ts_code,
)
from PatternAnalysis.tsanghiapi.distributed_lock import RedisLock, SYNC_LOCK_KEY

logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/api/tsanghi", tags=["Tsanghi股票日线数据"])


# ==================== 响应模型 ====================

class DateRangeResponse(BaseModel):
    """日期范围响应"""
    exchange_code: str
    ticker: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    message: str = ""


class DailyDataItem(BaseModel):
    """日线数据项"""
    ticker: str
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class DailyDataListResponse(BaseModel):
    """日线数据列表响应"""
    exchange_code: str
    ticker: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    count: int = 0
    data: List[DailyDataItem] = []


class SyncResponse(BaseModel):
    """同步响应"""
    ts_code: str
    status: str
    message: str
    data_count: Optional[int] = None


class BatchSyncResponse(BaseModel):
    """批量同步响应"""
    total: int
    success_count: int
    error_count: int
    results: List[SyncResponse]


class LockedSyncResponse(BaseModel):
    """带锁的同步响应"""
    success: bool
    message: str
    total: Optional[int] = None
    success_count: Optional[int] = None
    error_count: Optional[int] = None


class LockStatusResponse(BaseModel):
    """锁状态响应"""
    locked: bool
    message: str


# ==================== 功能1：个股日期范围和历史数据 ====================

@router.get("/stock/{exchange_code}/{ticker}/date-range",
            response_model=DateRangeResponse,
            summary="获取个股开始时间和结束时间")
def get_stock_date_range(
    exchange_code: str = Path(..., description="交易所代码: XSHG, XSHE, XNAS"),
    ticker: str = Path(..., description="股票代码: 如 600519")
):
    """
    获取个股的开始时间和结束时间

    - **exchange_code**: 交易所代码 (XSHG, XSHE, XNAS)
    - **ticker**: 股票代码
    """
    service = DailyDataService()
    try:
        result = service.get_stock_date_range(exchange_code, ticker)

        if result is None:
            raise HTTPException(status_code=404, detail=f"无法获取 {exchange_code}/{ticker} 的数据")

        return DateRangeResponse(
            exchange_code=exchange_code,
            ticker=ticker,
            start_date=result.get("start_date"),
            end_date=result.get("end_date"),
            message="成功"
        )
    finally:
        service.close()


@router.get("/stock/{exchange_code}/{ticker}/daily",
            response_model=DailyDataListResponse,
            summary="获取个股历史数据")
def get_stock_daily(
    exchange_code: str = Path(..., description="交易所代码: XSHG, XSHE, XNAS"),
    ticker: str = Path(..., description="股票代码: 如 600519"),
    start_date: Optional[str] = Query(None, description="起始日期: yyyy-mm-dd"),
    end_date: Optional[str] = Query(None, description="结束日期: yyyy-mm-dd")
):
    """
    获取个股的历史数据

    - **exchange_code**: 交易所代码 (XSHG, XSHE, XNAS)
    - **ticker**: 股票代码
    - **start_date**: 起始日期 (yyyy-mm-dd)，默认最近一年
    - **end_date**: 结束日期 (yyyy-mm-dd)，默认最新日期
    """
    service = DailyDataService()
    try:
        data = service.get_stock_history_by_range(exchange_code, ticker, start_date, end_date)

        if data is None:
            raise HTTPException(status_code=404, detail=f"无法获取 {exchange_code}/{ticker} 的数据")

        items = [DailyDataItem(**item) for item in data]

        return DailyDataListResponse(
            exchange_code=exchange_code,
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            count=len(items),
            data=items
        )
    finally:
        service.close()


# ==================== 功能2：基于 stockinfobase 的批量同步 ====================

@router.get("/sync/stock/{ts_code}",
            response_model=SyncResponse,
            summary="同步单只股票日线数据")
def sync_single_stock_api(
    ts_code: str = Path(..., description="股票代码: 如 000001.SZ")
):
    """
    根据 stockinfobase 的 ts_code 同步单只股票日线数据

    - ts_code 格式: 000001.SZ
    - 自动转换: .SZ -> XSHE, .SH -> XSHG
    - 成功/失败都会记录到日志表
    """
    # 1. 验证 ts_code 格式
    stock_info = get_stock_info_by_ts_code(ts_code)

    if not stock_info:
        raise HTTPException(status_code=404, detail=f"股票代码不存在: {ts_code}")

    # 2. 同步
    service = SyncService()
    try:
        result = service.sync_single_stock(ts_code)

        return SyncResponse(
            ts_code=ts_code,
            status=result.get("status", "error"),
            message=result.get("message", ""),
            data_count=len(result.get("data", [])) if result.get("data") else None
        )
    finally:
        service.close()


@router.get("/sync/all",
            response_model=BatchSyncResponse,
            summary="同步所有股票日线数据（多线程并发）",
            description="""
### 功能说明
遍历 stockinfobase 表，同步所有股票的日线数据。

### 处理逻辑
1. 从 stockinfobase 获取所有股票 ts_code 和 factory_code
2. 自动转换 ts_code 为 ticker（去掉 .SZ/.SH 后缀，或 1./0. 前缀）
3. 自动转换 factory_code 为 exchange_code（SZ→XSHE, SH→XSHG）
4. 调用 Tsanghi API 获取日线数据
5. 成功/失败都记录到 alert_log 日志表

### 参数说明
- limit: 限制同步数量，用于测试
- start_date: 起始日期 (yyyy-mm-dd)，用于增量同步
- end_date: 结束日期 (yyyy-mm-dd)，用于增量同步

### 使用场景
- 全量同步：不传 start_date 和 end_date
- 增量同步：传入 start_date 和 end_date，如 2026-02-14 至 2026-03-30
""")
def sync_all_stocks_api(
    limit: Optional[int] = Query(None, description="限制同步数量，用于测试"),
    start_date: Optional[str] = Query(None, description="起始日期: yyyy-mm-dd"),
    end_date: Optional[str] = Query(None, description="结束日期: yyyy-mm-dd")
):
    """
    同步 stockinfobase 中所有股票的日线数据

    - 遍历 stockinfobase 表
    - 自动转换 ts_code 和 factory_code
    - 成功/失败都会记录到日志表
    - 使用多线程并发执行
    - 支持指定日期范围（增量同步）
    """
    service = SyncService()
    try:
        results = service.sync_all_stocks(limit, start_date, end_date)

        sync_responses = [
            SyncResponse(
                ts_code=r.get("ts_code", ""),
                status=r.get("status", "error"),
                message=r.get("message", ""),
                data_count=len(r.get("data", [])) if r.get("data") else None
            )
            for r in results
        ]

        return BatchSyncResponse(
            total=len(results),
            success_count=service.success_count,
            error_count=service.error_count,
            results=sync_responses
        )
    finally:
        service.close()


@router.get("/sync/all/locked",
            response_model=LockedSyncResponse,
            summary="同步所有股票日线数据（带分布式锁）",
            description="""
### 功能说明
带分布式锁的批量同步，确保同一时间只有一个客户端可以执行。

### 处理逻辑
1. 使用 Redis 分布式锁确保并发安全
2. 遍历 stockinfobase 表获取所有股票
3. 自动转换 ts_code 和 factory_code
4. 调用 Tsanghi API 获取日线数据
5. 成功/失败都记录到 alert_log 日志表

### 参数说明
- limit: 限制同步数量，用于测试
- start_date: 起始日期 (yyyy-mm-dd)，用于增量同步
- end_date: 结束日期 (yyyy-mm-dd)，用于增量同步

### 使用场景
- 推荐用于定时任务，避免重复执行
- 支持增量同步，如 2026-02-14 至 2026-03-30

### 锁机制
- 锁 key: tsanghi:sync:lock:batch_sync_all
- 锁超时: 3600 秒（1小时）
- 阻塞超时: 30 秒
""")
def sync_all_stocks_locked_api(
    limit: Optional[int] = Query(None, description="限制同步数量，用于测试"),
    start_date: Optional[str] = Query(None, description="起始日期: yyyy-mm-dd"),
    end_date: Optional[str] = Query(None, description="结束日期: yyyy-mm-dd")
):
    """
    带分布式锁的批量同步

    - 确保同一时间只有一个客户端可以执行批量同步
    - 使用 Redis 分布式锁实现
    - 适合定时任务调用，避免重复执行
    - 支持指定日期范围（增量同步）
    """
    result = sync_all_stocks_with_lock(limit, start_date, end_date)

    if result.get("success"):
        data = result.get("data", {})
        return LockedSyncResponse(
            success=True,
            message=result.get("message", ""),
            total=data.get("total"),
            success_count=data.get("success_count"),
            error_count=data.get("error_count")
        )
    else:
        return LockedSyncResponse(
            success=False,
            message=result.get("message", "同步失败"),
            total=0,
            success_count=0,
            error_count=0
        )


@router.get("/sync/lock/status",
            response_model=LockStatusResponse,
            summary="查询分布式锁状态")
def get_lock_status():
    """
    查询批量同步的分布式锁状态

    - 用于判断当前是否有批量同步任务正在执行
    """
    lock = RedisLock(SYNC_LOCK_KEY)

    try:
        # 尝试非阻塞获取锁
        acquired = lock.acquire(blocking=False)

        if acquired:
            # 成功获取，说明锁是空闲的
            lock.release()
            return LockStatusResponse(
                locked=False,
                message="锁可用，可以开始同步"
            )
        else:
            # 无法获取，说明有任务正在执行
            return LockStatusResponse(
                locked=True,
                message="锁已被占用，有其他同步任务正在执行"
            )

    except Exception as e:
        logger.error(f"查询锁状态失败: {e}")
        return LockStatusResponse(
            locked=False,
            message=f"查询失败: {str(e)}"
        )


@router.post("/sync/lock/release",
            response_model=LockStatusResponse,
            summary="强制释放分布式锁")
def release_lock():
    """
    强制释放分布式锁

    - 谨慎使用，可能导致正在执行的任务数据不一致
    - 仅在确认没有任务在执行时使用
    """
    lock = RedisLock(SYNC_LOCK_KEY)

    try:
        # 尝试释放锁（不检查持有者）
        lock.release()
        return LockStatusResponse(
            locked=False,
            message="锁已释放"
        )
    except Exception as e:
        logger.error(f"释放锁失败: {e}")
        return LockStatusResponse(
            locked=True,
            message=f"释放失败: {str(e)}"
        )
