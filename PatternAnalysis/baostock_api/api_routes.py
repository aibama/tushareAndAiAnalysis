"""
Baostock 相关 HTTP 接口（与 akshare_api 对齐）。
"""
from datetime import datetime
from typing import List, Optional, cast
import pymysql

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from PatternAnalysis.config import DB_CONFIG
from PatternAnalysis.baostock_api.china_stock_trading_day_checker import (
    get_latest_trading_day_date_str,
    get_next_trading_day,
    get_previous_trading_day_str,
    get_today_date_str,
    is_trading_day_str,
    need_to_update_data,
)
from PatternAnalysis.baostock_api.sync_tradetoday_service import (
    sync_tradetoday_all_from_baostock,
    sync_tradetoday_one_from_baostock,
)
from PatternAnalysis.baostock_api.utils import AdjustType

router = APIRouter(prefix="/api/baostock", tags=["Baostock"])


# 数据库连接
def _get_db_connection():
    return pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset=DB_CONFIG["charset"],
        cursorclass=pymysql.cursors.DictCursor,
    )


# 统计响应模型
class TradeDateCountItem(BaseModel):
    trade_date: str
    count: int


class TradeDateCountResponse(BaseModel):
    total_trade_dates: int
    total_records: int
    data: List[TradeDateCountItem]


class LatestTradingDayResponse(BaseModel):
    """与 Java getLatestTradingDayDateStr / 今日是否交易日 对齐。"""

    latest_trading_day: str
    today: str
    is_today_trading_day: bool


class TradingDayCheckResponse(BaseModel):
    date: str
    is_trading_day: bool


class NeedUpdateResponse(BaseModel):
    need_update: bool
    latest_trading_day: str


class NextTradingDayResponse(BaseModel):
    ref_date: str
    next_trading_day: str


class PreviousTradingDayResponse(BaseModel):
    ref_date: str
    previous_trading_day: str


@router.get(
    "/trading/latest",
    response_model=LatestTradingDayResponse,
    summary="获取最近一个交易日（A 股日历：周末+内置节假日）",
    description="""
若**今天**为交易日则 `latest_trading_day` 为今天，否则为向前追溯的上一交易日。
节假日数据与 `china_stock_trading_day_checker` 中 2026 年集合一致，可按年扩展。
""",
)
def get_latest_trading_day_api():
    today_s = get_today_date_str()
    latest = get_latest_trading_day_date_str()
    is_td = is_trading_day_str(today_s)
    return LatestTradingDayResponse(
        latest_trading_day=latest,
        today=today_s,
        is_today_trading_day=is_td,
    )


@router.get(
    "/trading/is-trading-day",
    response_model=TradingDayCheckResponse,
    summary="判断某日是否为交易日",
)
def is_trading_day_api(
    date: str = Query(..., description="yyyy-MM-dd"),
):
    d = (date or "").strip()
    if len(d) < 10:
        raise HTTPException(status_code=400, detail="date 请使用 yyyy-MM-dd")
    return TradingDayCheckResponse(date=d[:10], is_trading_day=is_trading_day_str(d[:10]))


@router.get(
    "/trading/previous",
    response_model=PreviousTradingDayResponse,
    summary="从指定日起向前最近交易日（含当日若当日为交易日）",
    description="日期字符串解析失败时与 Java 一致返回 **今天** 的日期（未必为交易日）。",
)
def previous_trading_day_api(
    date: str = Query(..., description="起始日 yyyy-MM-dd"),
):
    d = (date or "").strip()
    ref = d[:10] if len(d) >= 10 else d
    prev = get_previous_trading_day_str(ref)
    return PreviousTradingDayResponse(ref_date=ref, previous_trading_day=prev.isoformat())


@router.get(
    "/trading/next",
    response_model=NextTradingDayResponse,
    summary="从指定日的下一天起向后下一个交易日",
)
def next_trading_day_api(
    date: str = Query(..., description="参考日 yyyy-MM-dd"),
):
    d = (date or "").strip()
    if len(d) < 10:
        raise HTTPException(status_code=400, detail="date 请使用 yyyy-MM-dd")
    try:
        ref = datetime.strptime(d[:10], "%Y-%m-%d").date()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"日期解析失败: {e}") from e
    nxt = get_next_trading_day(ref)
    return NextTradingDayResponse(ref_date=d[:10], next_trading_day=nxt.isoformat())


@router.get(
    "/trading/need-update",
    response_model=NeedUpdateResponse,
    summary="Level2 等场景：最后更新日是否需补数",
    description="与 Java needToUpdateData 一致：空/解析失败/不等于最近交易日 → 需要更新。",
)
def need_update_api(
    level2_last_update_date: Optional[str] = Query(
        None,
        description="最后更新日期 yyyy-MM-dd；空表示需要更新",
    ),
):
    latest = get_latest_trading_day_date_str()
    return NeedUpdateResponse(
        need_update=need_to_update_data(level2_last_update_date),
        latest_trading_day=latest,
    )


# 统计每个交易日的记录数
@router.get(
    "/statistics/trade-date-count",
    response_model=TradeDateCountResponse,
    summary="统计 stocktradetodayinfo 每个 trade_date 的记录数",
    description="""
查询 MySQL 表 stocktradetodayinfo，按 trade_date 分组统计记录数。
返回：总交易日数、总记录数、各交易日的记录数列表。
""",
)
def get_trade_date_count(
    limit: Optional[int] = Query(
        None, description="限制返回的交易日数量（按日期倒序）"
    ),
):
    sql = """
        SELECT trade_date, COUNT(*) as count
        FROM stocktradetodayinfo
        GROUP BY trade_date
        ORDER BY trade_date DESC
    """
    if limit:
        sql += f" LIMIT {int(limit)}"

    conn = _get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            results = cursor.fetchall()

        # 统计
        data = [
            TradeDateCountItem(
                trade_date=str(r["trade_date"]),
                count=int(r["count"]),
            )
            for r in results
        ]
        total_records = sum(item.count for item in data)

        return TradeDateCountResponse(
            total_trade_dates=len(data),
            total_records=total_records,
            data=data,
        )
    finally:
        conn.close()


class TradetodaySyncItem(BaseModel):
    ts_code: str
    status: str
    message: str = ""
    rows_saved: int = 0


class TradetodaySyncBatchResponse(BaseModel):
    total: int
    success_count: int
    skipped_count: int = 0
    error_count: int
    rows_saved_total: int
    results: List[TradetodaySyncItem]
    message: Optional[str] = None


class TradetodaySyncOneResponse(BaseModel):
    ts_code: str
    status: str
    message: str = ""
    rows_saved: int = 0
    rows_fetched: int = 0


@router.get(
    "/sync/tradetoday/one",
    response_model=TradetodaySyncOneResponse,
    summary="Baostock 单股日线同步（测试/补数）",
    description="""
指定 **ts_code**，用 Baostock ``query_history_k_data_plus`` 拉取日 K，写入 **stocktradetodayinfo**。

- **dry_run=true**：只拉取统计条数，**不写库**
- 与批量接口共用进程内**滑动窗口限流**；区间内已有数据时 **skipped**（幂等）
- 每次调用会 **login/logout** 各一次（与批量任务内长登录不同，适合单点调试）
""",
)
def sync_tradetoday_one_api(
    ts_code: str = Query(..., description="如 600000.SH、000001.SZ"),
    start_date: str = Query(..., description="开始日期 yyyy-mm-dd 或 yyyymmdd"),
    end_date: str = Query(..., description="结束日期 yyyy-mm-dd 或 yyyymmdd"),
    adjust: str = Query(
        "",
        description="复权：不传或空=不复权；qfq=前复权；hfq=后复权",
    ),
    dry_run: bool = Query(False, description="为 true 时仅拉取不落库"),
):
    if adjust not in ("", "qfq", "hfq"):
        raise HTTPException(
            status_code=400,
            detail="adjust 必须为 ''（不复权）、qfq（前复权）或 hfq（后复权）",
        )
    data = sync_tradetoday_one_from_baostock(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        adjust=cast(AdjustType, adjust),
        dry_run=dry_run,
    )
    return TradetodaySyncOneResponse(
        ts_code=data.get("ts_code", ""),
        status=data.get("status", "error"),
        message=data.get("message", "") or "",
        rows_saved=int(data.get("rows_saved") or 0),
        rows_fetched=int(data.get("rows_fetched") or 0),
    )


@router.get(
    "/sync/tradetoday/all",
    response_model=TradetodaySyncBatchResponse,
    summary="Baostock 日线批量写入 stocktradetodayinfo",
    description="""
遍历 **stockinfobase** 全部 `ts_code`，用 Baostock ``query_history_k_data_plus`` 拉取 **日 K**（``frequency=d``），
按 `start_date`～`end_date` 写入 MySQL **stocktradetodayinfo**（字段映射与 AkShare 路径一致）。

- **adjust**：不复权传空 `adjust=`；前复权 `qfq`；后复权 `hfq`
- **limit**：仅同步前 N 只股票
- 内置：滑动窗口限流、随机间隔、区间内已落表则 **skipped**（幂等）
- 单股调试请用 **GET /api/baostock/sync/tradetoday/one**
- 表需具备 ``ts_code`` + ``trade_date`` 唯一约束以支持 upsert
""",
)
def sync_tradetoday_all_api(
    start_date: str = Query(..., description="开始日期 yyyy-mm-dd 或 yyyymmdd"),
    end_date: str = Query(..., description="结束日期 yyyy-mm-dd 或 yyyymmdd"),
    adjust: str = Query(
        "",
        description="复权：不传或空=不复权；qfq=前复权；hfq=后复权",
    ),
    limit: Optional[int] = Query(
        None, description="仅处理前 N 条 stockinfobase 记录（测试用）"
    ),
):
    if adjust not in ("", "qfq", "hfq"):
        raise HTTPException(
            status_code=400,
            detail="adjust 必须为 ''（不复权）、qfq（前复权）或 hfq（后复权）",
        )
    data = sync_tradetoday_all_from_baostock(
        start_date=start_date,
        end_date=end_date,
        adjust=cast(AdjustType, adjust),
        limit=limit,
    )
    return TradetodaySyncBatchResponse(
        total=data["total"],
        success_count=data["success_count"],
        skipped_count=int(data.get("skipped_count") or 0),
        error_count=data["error_count"],
        rows_saved_total=data["rows_saved_total"],
        results=[
            TradetodaySyncItem(
                ts_code=r.get("ts_code", ""),
                status=r.get("status", "error"),
                message=r.get("message", "") or "",
                rows_saved=int(r.get("rows_saved") or 0),
            )
            for r in data["results"]
        ],
        message=data.get("message"),
    )
