"""
Z-Score 数据服务

提供中证1000成分股、日线行情、行业等数据查询
"""
import logging
from typing import List, Dict, Optional
from datetime import date, timedelta
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PatternAnalysis.config import DB_CONFIG, PG_CONFIG

logger = logging.getLogger(__name__)


def get_mysql_connection():
    """获取MySQL连接"""
    import pymysql
    return pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset=DB_CONFIG.get("charset", "utf8mb4")
    )


def get_pg_connection():
    """获取PostgreSQL连接"""
    import psycopg2
    return psycopg2.connect(
        host=PG_CONFIG["host"],
        port=PG_CONFIG["port"],
        user=PG_CONFIG["user"],
        password=PG_CONFIG["password"],
        database=PG_CONFIG["database"]
    )


def get_zz1000_stocks(trade_date: date = None) -> List[Dict]:
    """
    获取中证1000成分股列表

    Args:
        trade_date: 交易日期，默认最新

    Returns:
        成分股列表 [{"ts_code": "000001.SZ", "stock_name": "xxx"}, ...]
    """
    conn = get_mysql_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 查询中证1000成分股（ZZ1000）
            sql = """
                SELECT DISTINCT ts_code
                FROM stock_composition_relation
                WHERE composition_code = 'ZZ1000'
                  AND is_latest = 1
            """
            cursor.execute(sql)
            rows = cursor.fetchall()

            # 获取股票名称
            ts_codes = [r['ts_code'] for r in rows]
            if not ts_codes:
                return []

            placeholders = ",".join(["%s"] * len(ts_codes))
            name_sql = f"""
                SELECT ts_code, name
                FROM stockinfobase
                WHERE ts_code IN ({placeholders})
            """
            cursor.execute(name_sql, ts_codes)
            name_rows = {r['ts_code']: r['name'] for r in cursor.fetchall()}

            result = []
            for r in rows:
                ts_code = r['ts_code']
                result.append({
                    "ts_code": ts_code,
                    "stock_name": name_rows.get(ts_code, ts_code)
                })

            return result
    finally:
        conn.close()


def get_stock_daily(
    ts_codes: List[str],
    start_date: date,
    end_date: date,
    fields: List[str] = None
) -> pd.DataFrame:
    """
    获取股票日线数据

    Args:
        ts_codes: 股票代码列表
        start_date: 开始日期
        end_date: 结束日期
        fields: 返回字段，默认 ['ts_code', 'trade_date', 'close', 'open', 'high', 'low', 'vol']

    Returns:
        DataFrame
    """
    if not ts_codes:
        return pd.DataFrame()

    if fields is None:
        fields = ['ts_code', 'trade_date', 'close', 'open', 'high', 'low', 'vol', 'amount', 'pre_close']

    conn = get_mysql_connection()
    try:
        # 构建字段列表
        field_str = ", ".join([f"`{f}`" if f != 'trade_date' else f"DATE(trade_date) as trade_date" for f in fields])

        placeholders = ",".join(["%s"] * len(ts_codes))

        sql = f"""
            SELECT {field_str}
            FROM stocktradetodayinfo
            WHERE ts_code IN ({placeholders})
              AND DATE(trade_date) >= %s
              AND DATE(trade_date) <= %s
            ORDER BY ts_code, trade_date
        """

        params = ts_codes + [start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')]

        df = pd.read_sql(sql, conn, params=params)
        return df
    finally:
        conn.close()


def get_sw_industries(level: int = 1) -> List[Dict]:
    """
    获取申万行业列表

    Args:
        level: 行业级别（1=一级行业）

    Returns:
        行业列表
    """
    conn = get_mysql_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = """
                SELECT node_code, node_name, level
                FROM sw_industry
                WHERE level = %s
                ORDER BY node_code
            """
            cursor.execute(sql, (level,))
            rows = cursor.fetchall()
            return rows
    finally:
        conn.close()


def get_stock_industry_relation(ts_codes: List[str], trade_date: date = None) -> Dict[str, Dict]:
    """
    获取股票对应的申万行业（一级）

    Args:
        ts_codes: 股票代码列表
        trade_date: 交易日期

    Returns:
        {ts_code: {"industry_code": "801010", "industry_name": "电子"}, ...}
    """
    if not ts_codes:
        return {}

    conn = get_mysql_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            placeholders = ",".join(["%s"] * len(ts_codes))

            sql = f"""
                SELECT r.ts_code, s.node_code as industry_code, s.node_name as industry_name
                FROM stock_sw_relation r
                JOIN sw_industry s ON r.sw_node_code = s.node_code
                WHERE r.ts_code IN ({placeholders})
                  AND r.is_latest = 1
                  AND s.level = 1
            """

            cursor.execute(sql, ts_codes)
            rows = cursor.fetchall()

            result = {}
            for r in rows:
                result[r['ts_code']] = {
                    "industry_code": r['industry_code'],
                    "industry_name": r['industry_name']
                }

            return result
    finally:
        conn.close()


def get_industry_stocks(industry_code: str, trade_date: date = None) -> List[Dict]:
    """
    获取某行业下的所有成分股

    Args:
        industry_code: 申万行业代码
        trade_date: 交易日期

    Returns:
        成分股列表
    """
    conn = get_mysql_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = """
                SELECT r.ts_code, s.stock_name
                FROM stock_sw_relation r
                JOIN sw_industry s ON r.sw_node_code = s.node_code
                JOIN stockinfobase b ON r.ts_code = b.ts_code
                WHERE s.node_code = %s
                  AND r.is_latest = 1
                  AND s.level = 1
                ORDER BY b.list_date
            """
            cursor.execute(sql, (industry_code,))
            rows = cursor.fetchall()
            return rows
    finally:
        conn.close()


def get_latest_trade_date() -> date:
    """
    获取最新的交易日期

    Returns:
        最新交易日期
    """
    conn = get_mysql_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = """
                SELECT MAX(DATE(trade_date)) as latest_date
                FROM stocktradetodayinfo
                WHERE vol > 0
            """
            cursor.execute(sql)
            row = cursor.fetchone()
            if row and row['latest_date']:
                return row['latest_date']
            # 如果没有数据，返回昨天
            return date.today() - timedelta(days=1)
    finally:
        conn.close()


def get_trade_dates(start_date: date, end_date: date) -> List[date]:
    """
    获取交易日列表

    Args:
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        交易日列表
    """
    conn = get_mysql_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = """
                SELECT DISTINCT DATE(trade_date) as trade_date
                FROM stocktradetodayinfo
                WHERE DATE(trade_date) >= %s
                  AND DATE(trade_date) <= %s
                  AND vol > 0
                ORDER BY trade_date
            """
            cursor.execute(sql, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
            rows = cursor.fetchall()
            return [r['trade_date'] for r in rows]
    finally:
        conn.close()


def get_stock_mv(ts_codes: List[str], trade_date: date = None) -> Dict[str, float]:
    """
    获取股票总市值（使用共享的市值计算服务）

    Args:
        ts_codes: 股票代码列表
        trade_date: 交易日期（可选，用于未来扩展）

    Returns:
        {ts_code: mv, ...}
    """
    if not ts_codes:
        return {}

    # 使用共享的市值计算服务
    from .market_cap_service import calculate_stocks_market_cap_by_codes

    try:
        result = calculate_stocks_market_cap_by_codes(ts_codes)

        # 对于计算失败的股票，使用默认值
        default_mv = 10000000000  # 100亿
        for code in ts_codes:
            if code not in result:
                result[code] = default_mv
                logger.debug(f"股票 {code} 市值计算失败，使用默认值")

        return result
    except Exception as e:
        logger.warning(f"批量获取市值失败: {e}")
        # 返回默认市值
        return {code: 10000000000 for code in ts_codes}


if __name__ == "__main__":
    # 测试代码
    import pymysql

    logging.basicConfig(level=logging.INFO)

    # 测试获取中证1000成分股
    stocks = get_zz1000_stocks()
    print(f"中证1000成分股数量: {len(stocks)}")
    if stocks:
        print(f"前5只: {stocks[:5]}")

    # 测试获取最新交易日期
    latest_date = get_latest_trade_date()
    print(f"最新交易日期: {latest_date}")

    # 测试获取申万一级行业
    industries = get_sw_industries(level=1)
    print(f"申万一级行业数量: {len(industries)}")
    if industries:
        print(f"前5个: {industries[:5]}")
