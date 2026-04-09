"""
涨跌停状态 API 路由
"""
from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, Query, Path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/limit-status", tags=["涨跌停状态"])


@router.get(
    "/sync/all",
    summary="同步所有股票的涨跌停状态",
    description="计算 stocktradetodayinfo 中所有股票的涨跌停状态并更新到数据库",
)
def sync_all_limit_status(trade_date: Optional[str] = Query(None, description="交易日期，默认为最新日期")):
    """
    同步所有股票的涨跌停状态
    """
    from .limit_status_service import calculate_limit_status_for_all

    try:
        result = calculate_limit_status_for_all(trade_date=trade_date)
        return result
    except Exception as e:
        logger.exception(f"同步涨跌停状态失败: {e}")
        return {"success": False, "message": str(e)}


@router.get(
    "/sync/stock/{ts_code}",
    summary="同步指定股票的涨跌停状态",
    description="计算指定股票在指定日期的涨跌停状态",
)
def sync_stock_limit_status(
    ts_code: str = Path(..., description="股票代码，如 600000.SH"),
    trade_date: Optional[str] = Query(None, description="交易日期，默认为最新日期"),
):
    """
    同步指定股票的涨跌停状态
    """
    from .limit_status_service import calculate_limit_status_for_stock

    try:
        result = calculate_limit_status_for_stock(ts_code=ts_code, trade_date=trade_date)
        return result
    except Exception as e:
        logger.exception(f"同步涨跌停状态失败: {e}")
        return {"success": False, "message": str(e)}


@router.get(
    "/query/{ts_code}",
    summary="查询指定股票的涨跌停状态",
    description="查询指定股票在指定日期的涨跌停状态",
)
def query_stock_limit_status(
    ts_code: str = Path(..., description="股票代码，如 600000.SH"),
    trade_date: Optional[str] = Query(None, description="交易日期，默认为最新日期"),
):
    """
    查询指定股票的涨跌停状态
    """
    import pymysql
    from datetime import datetime
    from PatternAnalysis.config import DB_CONFIG

    conn = pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset=DB_CONFIG["charset"],
        cursorclass=pymysql.cursors.DictCursor,
    )

    try:
        with conn.cursor() as cursor:
            if trade_date is None:
                cursor.execute(
                    "SELECT MAX(trade_date) as max_date FROM stocktradetodayinfo WHERE ts_code = %s",
                    (ts_code,)
                )
                result = cursor.fetchone()
                if result and result.get('max_date'):
                    trade_date = result['max_date']
                    if isinstance(trade_date, datetime):
                        trade_date = trade_date.strftime('%Y-%m-%d')

            cursor.execute(
                """SELECT ts_code, trade_date, pre_close, close, limit_status
                   FROM stocktradetodayinfo
                   WHERE ts_code = %s AND trade_date = %s""",
                (ts_code, trade_date)
            )
            row = cursor.fetchone()

            if not row:
                return {"success": False, "message": f"未找到 {ts_code} 在 {trade_date} 的数据"}

            return {
                "success": True,
                "ts_code": row['ts_code'],
                "trade_date": row['trade_date'],
                "pre_close": row['pre_close'],
                "close": row['close'],
                "limit_status": row.get('limit_status', 'NORMAL')
            }
    except Exception as e:
        logger.exception(f"查询涨跌停状态失败: {e}")
        return {"success": False, "message": str(e)}
    finally:
        conn.close()