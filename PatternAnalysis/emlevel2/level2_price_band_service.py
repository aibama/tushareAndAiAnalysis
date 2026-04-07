"""
Level2 价格区间统计服务

统计个股在最近交易日收盘价 ±30% 价格区间内每分钟的历史成交情况：
- 各个价位的成交笔数
- 大单的成交量
- 大单的笔数

使用 PostgreSQL 的时间窗口和分区技术优化查询性能
"""
import logging
from typing import List, Dict, Optional, Any
from datetime import date, datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PatternAnalysis.config import DB_CONFIG, PG_CONFIG
from .config import LEVEL2_PRICE_BAND_CONFIG

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


def get_latest_close_price(ts_code: str) -> Optional[float]:
    """
    获取个股最近一个交易日的收盘价

    Args:
        ts_code: 股票代码

    Returns:
        收盘价，如果没有数据返回 None
    """
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT close
                FROM stocktradetodayinfo
                WHERE ts_code = %s
                ORDER BY trade_date DESC
                LIMIT 1
            """
            cursor.execute(sql, (ts_code,))
            row = cursor.fetchone()
            return float(row[0]) if row and row[0] else None
    finally:
        conn.close()


def get_stock_id(ts_code: str) -> Optional[int]:
    """
    获取股票在 PostgreSQL 中的 stock_id

    Args:
        ts_code: 股票代码

    Returns:
        stock_id，如果没有数据返回 None
    """
    # stock_minute_trades 表使用 stock_code 字段
    # 这里的 ts_code 格式是 000001.SZ，需要转换为 000001
    stock_symbol = ts_code.split('.')[0] if '.' in ts_code else ts_code
    return stock_symbol


def get_price_band_statistics(
    ts_code: str,
    price_range_percent: int = None,
    large_order_threshold: int = None,
    days_back: int = 30
) -> Dict[str, Any]:
    """
    获取个股价格区间内的历史成交统计

    Args:
        ts_code: 股票代码
        price_range_percent: 价格区间百分比（默认 30%）
        large_order_threshold: 大单阈值（默认 10000 股）
        days_back: 回溯天数（默认 30 天）

    Returns:
        统计结果字典
    """
    # 使用配置默认值
    if price_range_percent is None:
        price_range_percent = LEVEL2_PRICE_BAND_CONFIG.get("price_range_percent", 30)
    if large_order_threshold is None:
        large_order_threshold = LEVEL2_PRICE_BAND_CONFIG.get("large_order_threshold", 10000)

    # 1. 获取最近收盘价
    close_price = get_latest_close_price(ts_code)
    if close_price is None:
        return {
            "success": False,
            "message": f"未找到股票 {ts_code} 的收盘价数据",
            "ts_code": ts_code
        }

    # 2. 计算价格区间
    min_price = close_price * (100 - price_range_percent) / 100
    max_price = close_price * (100 + price_range_percent) / 100

    # 3. 计算日期范围
    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)

    # 4. 从 PostgreSQL 查询统计数据
    stats = query_price_band_from_pg(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        min_price=min_price,
        max_price=max_price,
        large_order_threshold=large_order_threshold
    )

    if stats is None:
        return {
            "success": False,
            "message": f"查询失败，股票 {ts_code} 可能没有 Level2 数据",
            "ts_code": ts_code,
            "close_price": close_price,
            "price_range": {
                "min": round(min_price, 2),
                "max": round(max_price, 2)
            }
        }

    # 5. 整理结果
    result = {
        "success": True,
        "ts_code": ts_code,
        "close_price": close_price,
        "price_range": {
            "min": round(min_price, 2),
            "max": round(max_price, 2),
            "percent": price_range_percent
        },
        "query_range": {
            "start_date": start_date.strftime('%Y-%m-%d'),
            "end_date": end_date.strftime('%Y-%m-%d'),
            "days": days_back
        },
        "large_order_threshold": large_order_threshold,
        "total_trades": stats.get("total_trades", 0),
        "total_volume": stats.get("total_volume", 0),
        "large_order_trades": stats.get("large_order_trades", 0),
        "large_order_volume": stats.get("large_order_volume", 0),
        "price_band_stats": stats.get("price_band_stats", [])
    }

    return result


def query_price_band_from_pg(
    ts_code: str,
    start_date: date,
    end_date: date,
    min_price: float,
    max_price: float,
    large_order_threshold: int
) -> Optional[Dict[str, Any]]:
    """
    从 PostgreSQL 查询价格区间统计数据

    使用 PostgreSQL 的时间分区和索引优化查询性能

    Args:
        ts_code: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        min_price: 最低价格
        max_price: 最高价格
        large_order_threshold: 大单阈值

    Returns:
        统计数据字典
    """
    conn = get_pg_connection()
    try:
        # 股票代码处理（去掉 .SH/.SZ 后缀）
        stock_symbol = ts_code.split('.')[0] if '.' in ts_code else ts_code

        # SQL 查询：按价格区间和分钟统计
        # 使用 PostgreSQL 的 date_trunc 函数进行时间窗口聚合
        sql = """
            SELECT
                date_trunc('minute', time) as trade_minute,
                -- 价格区间（向下取整到 0.01）
                floor(price * 100) / 100 as price_band,

                -- 统计指标
                COUNT(*) as trade_count,
                SUM(volume) as total_volume,

                -- 大单统计
                SUM(CASE WHEN volume >= %s THEN 1 ELSE 0 END) as large_order_count,
                SUM(CASE WHEN volume >= %s THEN volume ELSE 0 END) as large_order_volume

            FROM stock_minute_trades
            WHERE stock_code = %s
              AND time >= %s
              AND time < %s + INTERVAL '1 day'
              AND price >= %s
              AND price <= %s

            GROUP BY trade_minute, price_band
            ORDER BY trade_minute DESC, price_band DESC
        """

        params = (
            large_order_threshold,
            large_order_threshold,
            stock_symbol,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d'),
            min_price,
            max_price
        )

        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()

        if not rows:
            return None

        # 整理数据
        total_trades = 0
        total_volume = 0
        large_order_trades = 0
        large_order_volume = 0
        price_band_stats = []

        # 按分钟分组
        minute_data = {}
        for row in rows:
            trade_minute, price_band, trade_count, total_vol, large_count, large_vol = row

            minute_key = trade_minute.strftime('%Y-%m-%d %H:%M:%S') if trade_minute else None
            if not minute_key:
                continue

            if minute_key not in minute_data:
                minute_data[minute_key] = {
                    "minute": minute_key,
                    "price_bands": [],
                    "trade_count": 0,
                    "total_volume": 0,
                    "large_order_count": 0,
                    "large_order_volume": 0
                }

            minute_data[minute_key]["price_bands"].append({
                "price": float(price_band) if price_band else 0,
                "trade_count": int(trade_count) if trade_count else 0,
                "total_volume": int(total_vol) if total_vol else 0,
                "large_order_count": int(large_count) if large_count else 0,
                "large_order_volume": int(large_vol) if large_vol else 0
            })

            # 累计分钟统计
            minute_data[minute_key]["trade_count"] += int(trade_count) if trade_count else 0
            minute_data[minute_key]["total_volume"] += int(total_vol) if total_vol else 0
            minute_data[minute_key]["large_order_count"] += int(large_count) if large_count else 0
            minute_data[minute_key]["large_order_volume"] += int(large_vol) if large_vol else 0

            # 累计总统计
            total_trades += int(trade_count) if trade_count else 0
            total_volume += int(total_vol) if total_vol else 0
            large_order_trades += int(large_count) if large_count else 0
            large_order_volume += int(large_vol) if large_vol else 0

        # 转换为列表
        for minute_key in sorted(minute_data.keys(), reverse=True):
            price_band_stats.append(minute_data[minute_key])

        return {
            "total_trades": total_trades,
            "total_volume": total_volume,
            "large_order_trades": large_order_trades,
            "large_order_volume": large_order_volume,
            "price_band_stats": price_band_stats[:100]  # 限制返回最近 100 分钟
        }

    except Exception as e:
        logger.error(f"查询 PostgreSQL 失败: {e}")
        return None
    finally:
        conn.close()


def get_stock_list_by_keyword(keyword: str, limit: int = 10) -> List[Dict]:
    """
    根据关键字搜索股票（用于 API 的自动补全）

    Args:
        keyword: 关键字
        limit: 返回数量

    Returns:
        股票列表
    """
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT ts_code, name
                FROM stockinfobase
                WHERE ts_code LIKE %s OR name LIKE %s
                LIMIT %s
            """
            like_keyword = f"%{keyword}%"
            cursor.execute(sql, (like_keyword, like_keyword, limit))
            rows = cursor.fetchall()

            return [{"ts_code": r[0], "name": r[1]} for r in rows]
    finally:
        conn.close()


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)

    # 测试获取价格区间统计
    print("=== 测试价格区间统计 ===")
    result = get_price_band_statistics("000001.SZ")
    print(f"结果: {result}")
