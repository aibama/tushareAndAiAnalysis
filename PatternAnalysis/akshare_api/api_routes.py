"""
AkShare 相关 HTTP 接口（Swagger /docs）
"""
from typing import List, Optional, cast

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from PatternAnalysis.akshare_api.stock_list_service import (
    get_stockinfobase_row_with_stock_code,
    list_stockinfobase_with_stock_code,
)
from PatternAnalysis.akshare_api.hist_service import AdjustType
from PatternAnalysis.akshare_api.sync_tradetoday_service import (
    sync_tradetoday_all_from_akshare,
    sync_tradetoday_one_from_akshare,
)

router = APIRouter(prefix="/api/akshare", tags=["AkShare"])


class StockInfoFromDb(BaseModel):
    ts_code: str
    name: Optional[str] = None
    factory_code: Optional[str] = None
    stock_code: str = Field(
        "",
        description="从 ts_code 解析的 6 位数字股票代码（AkShare 的 symbol 等）；"
        "Tsanghi HTTP 请求里同含义的字段常命名为 ticker",
    )


class StockInfoFromDbListResponse(BaseModel):
    count: int
    items: List[StockInfoFromDb]


@router.get(
    "/stocks/from-db",
    response_model=StockInfoFromDbListResponse,
    summary="从 stockinfobase 读取股票列表并解析股票代码",
    description="""
从 MySQL `stockinfobase` 读取 `ts_code`, `name`, `factory_code`，
并按规则解析 **stock_code**（6 位数字）：

- `000001.SZ` → `000001`
- `600519.SH` → `600519`
- `1.600519` → `600519`
- `0.000001` → `000001`

说明：Tsanghi 等 HTTP 接口中同含义参数常叫 `ticker`，此处 API 返回字段名为 `stock_code`。
""",
)
def list_stocks_from_stockinfobase():
    raw = list_stockinfobase_with_stock_code()
    items = [
        StockInfoFromDb(
            ts_code=str(r.get("ts_code") or ""),
            name=r.get("name"),
            factory_code=r.get("factory_code"),
            stock_code=r.get("stock_code") or "",
        )
        for r in raw
    ]
    return StockInfoFromDbListResponse(count=len(items), items=items)


@router.get(
    "/stocks/from-db/{ts_code}",
    response_model=StockInfoFromDb,
    summary="按 ts_code 查询 stockinfobase 并解析股票代码",
)
def get_stock_from_stockinfobase(
    ts_code: str = Path(..., description="如 000001.SZ 或数据库中的 ts_code"),
):
    row = get_stockinfobase_row_with_stock_code(ts_code)
    if not row:
        raise HTTPException(status_code=404, detail=f"stockinfobase 中不存在: {ts_code}")
    return StockInfoFromDb(
        ts_code=str(row.get("ts_code") or ""),
        name=row.get("name"),
        factory_code=row.get("factory_code"),
        stock_code=row.get("stock_code") or "",
    )


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
    summary="AkShare 单股日线同步（测试/补数）",
    description="""
指定 **ts_code**，用 AkShare 日 K 拉取 `start_date`～`end_date` 并写入 **stocktradetodayinfo**。

- **dry_run=true**：只拉取统计条数，**不写库**
- 与批量接口共用进程内**滑动窗口限流**；区间内已有数据时 **skipped**（幂等）
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
    data = sync_tradetoday_one_from_akshare(
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
    summary="AkShare 日线批量写入 stocktradetodayinfo",
    description="""
遍历 **stockinfobase** 全部 `ts_code`，用 `stock_zh_a_hist` 拉取 **日 K**（`period=daily`），
按 `start_date`～`end_date` 写入 MySQL **stocktradetodayinfo**。

- **adjust**：不复权传空字符串 `adjust=`；前复权 `qfq`；后复权 `hfq`（与 AkShare 一致）
- **limit**：仅同步前 N 只股票，便于联调
- 内置：滑动窗口限流、随机间隔；区间内已落表则 **skipped**（幂等）
- 单股调试请用 **GET /api/akshare/sync/tradetoday/one**
- 表需具备与 ``stock_trade_sync_service`` 相同的 upsert 语义（通常要求 ``ts_code`` + ``trade_date`` 上有唯一索引）
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
    data = sync_tradetoday_all_from_akshare(
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
