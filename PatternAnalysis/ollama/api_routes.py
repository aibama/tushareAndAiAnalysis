"""
从 MySQL stocktradetodayinfo 按区间导出 OHLCV，供 Ollama 等下游使用。
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from PatternAnalysis.data_access import get_stock_ohlc_in_range

router = APIRouter(prefix="/api/ollama", tags=["Ollama"])


class OhlcBarItem(BaseModel):
    date: str = Field(..., description="交易日 yyyy-mm-dd")
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = Field(None, description="成交量（与表字段 vol 一致，单位与入库来源一致）")


class StockOhlcvJsonResponse(BaseModel):
    """同时返回结构化 bars 与整段 JSON 数组字符串（json_string）。"""

    ts_code: str
    start_date: str
    end_date: str
    bars: List[OhlcBarItem]
    json_string: str = Field(..., description="与 bars 等价的 JSON 数组字符串")


def _parse_date(s: str) -> date:
    s = (s or "").strip()
    if not s:
        raise ValueError("空日期")
    if "-" in s:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    digits = "".join(c for c in s if c.isdigit())
    if len(digits) == 8:
        return datetime.strptime(digits, "%Y%m%d").date()
    raise ValueError(f"无法解析日期: {s!r}")


def _clean_float(x: Any) -> Optional[float]:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


@router.get(
    "/stock/ohlcv",
    response_model=StockOhlcvJsonResponse,
    summary="按区间导出股票 OHLCV（stocktradetodayinfo）",
    description="""
从 MySQL 表 **stocktradetodayinfo** 读取指定股票的日线 OHLCV。

**参数二选一（互斥）**：

1. **区间**：`start_date` + `end_date`（均必填）
2. **最近天数**：`last_days`（正整数，以今天为结束日向前推算自然日区间）

- `ts_code`：与表中一致，如 `000001.SZ`、`600000.SH`
""",
)
def get_stock_ohlcv_json(
    ts_code: str = Query(..., description="股票 ts_code，如 600000.SH"),
    start_date: Optional[str] = Query(None, description="开始日期 yyyy-mm-dd 或 yyyymmdd（与 last_days 互斥）"),
    end_date: Optional[str] = Query(None, description="结束日期 yyyy-mm-dd 或 yyyymmdd（与 last_days 互斥）"),
    last_days: Optional[int] = Query(
        None,
        ge=1,
        le=3650,
        description="最近自然日天数（与 start_date/end_date 互斥），结束日为今天",
    ),
):
    ts_code = ts_code.strip()
    if not ts_code:
        raise HTTPException(status_code=400, detail="ts_code 不能为空")

    use_range = start_date is not None or end_date is not None
    use_last = last_days is not None

    if use_range and use_last:
        raise HTTPException(
            status_code=400,
            detail="start_date/end_date 与 last_days 互斥，请只传其中一种",
        )
    if use_range and (not start_date or not end_date):
        raise HTTPException(
            status_code=400,
            detail="使用区间时请同时提供 start_date 与 end_date",
        )
    if not use_range and not use_last:
        raise HTTPException(
            status_code=400,
            detail="请提供 start_date+end_date，或提供 last_days",
        )

    try:
        if use_last:
            end = date.today()
            start = end - timedelta(days=int(last_days) - 1)
        else:
            start = _parse_date(start_date or "")
            end = _parse_date(end_date or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if start > end:
        start, end = end, start

    df = get_stock_ohlc_in_range(ts_code, start, end, include_tmp=False)
    if df is None or df.empty:
        bars: List[OhlcBarItem] = []
        payload = []
    else:
        rows: List[dict] = []
        for _, row in df.iterrows():
            td = row.get("trade_date")
            if hasattr(td, "strftime"):
                d_str = td.strftime("%Y-%m-%d") if hasattr(td, "strftime") else str(td)[:10]
            else:
                d_str = str(td)[:10]
            vol = row.get("vol")
            item = {
                "date": d_str,
                "open": _clean_float(row.get("open")),
                "high": _clean_float(row.get("high")),
                "low": _clean_float(row.get("low")),
                "close": _clean_float(row.get("close")),
                "volume": _clean_float(vol),
            }
            rows.append(item)
        bars = [OhlcBarItem(**r) for r in rows]
        payload = rows

    json_str = json.dumps(payload, ensure_ascii=False)
    return StockOhlcvJsonResponse(
        ts_code=ts_code,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        bars=bars,
        json_string=json_str,
    )
