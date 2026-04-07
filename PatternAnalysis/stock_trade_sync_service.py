"""
股票交易数据同步服务

从 PostgreSQL stock_minute_trades 表读取数据，汇总后写入 MySQL stocktradetodayinfo 表
"""
import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PatternAnalysis.config import DB_CONFIG, PG_CONFIG

logger = logging.getLogger(__name__)


def get_pg_connection():
    """获取 PostgreSQL 连接"""
    import psycopg2
    return psycopg2.connect(
        host=PG_CONFIG["host"],
        port=PG_CONFIG["port"],
        user=PG_CONFIG["user"],
        password=PG_CONFIG["password"],
        database=PG_CONFIG["database"]
    )


def get_mysql_connection():
    """获取 MySQL 连接"""
    import pymysql
    return pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset=DB_CONFIG.get("charset", "utf8")
    )


def fetch_daily_trade_data(target_date: date = None) -> List[Dict[str, Any]]:
    """
    从 PostgreSQL 获取指定日期的交易数据

    Args:
        target_date: 目标日期，默认今天

    Returns:
        每日汇总数据列表
    """
    if target_date is None:
        target_date = date.today()

    date_str = target_date.strftime("%Y-%m-%d")

    conn = get_pg_connection()
    try:
        with conn.cursor() as cursor:
            # 查询每日汇总数据
            sql = """
                SELECT
                    stock_code,
                    MAX(price) as high,
                    MIN(price) as low,
                    -- 开盘价：09:25:00 的价格
                    MAX(CASE WHEN time::time = '09:25:00' THEN price END) as open,
                    -- 收盘价：15:00:00 的价格
                    MAX(CASE WHEN time::time = '15:00:00' THEN price END) as close,
                    -- 成交量总和
                    SUM(volume) as vol,
                    -- 成交额总和
                    SUM(volume * price) as amount
                FROM stock_minute_trades
                WHERE time::date = %s
                GROUP BY stock_code
            """
            cursor.execute(sql, (date_str,))
            rows = cursor.fetchall()

            results = []
            for row in rows:
                stock_code, high, low, open_price, close_price, vol, amount = row

                # 跳过没有收盘价的股票
                if close_price is None:
                    logger.warning(f"股票 {stock_code} 没有 15:00 的收盘价，跳过")
                    continue

                results.append({
                    "ts_code": stock_code,
                    "high": float(high) if high else 0,
                    "low": float(low) if low else 0,
                    "open": float(open_price) if open_price else 0,
                    "close": float(close_price) if close_price else 0,
                    "vol": int(vol) if vol else 0,
                    "amount": float(amount) if amount else 0,
                    "trade_date": target_date
                })

            logger.info(f"从 PostgreSQL 获取到 {len(results)} 条交易数据")
            return results

    finally:
        conn.close()


def get_pre_close(stock_code: str, target_date: date = None) -> Optional[float]:
    """
    获取股票的前收盘价

    Args:
        stock_code: 股票代码
        target_date: 目标日期

    Returns:
        前收盘价
    """
    if target_date is None:
        target_date = date.today()

    # 查找前一天的数据
    from datetime import timedelta
    pre_date = target_date - timedelta(days=1)

    conn = get_pg_connection()
    try:
        with conn.cursor() as cursor:
            # 获取前一天 15:00 的收盘价作为前收盘价
            sql = """
                SELECT price FROM stock_minute_trades
                WHERE stock_code = %s AND time::date = %s AND time::time = '15:00:00'
                LIMIT 1
            """
            cursor.execute(sql, (stock_code, pre_date.strftime("%Y-%m-%d")))
            row = cursor.fetchone()
            return float(row[0]) if row else None
    finally:
        conn.close()


def insert_or_update_trade_info(trade_data: Dict[str, Any]) -> bool:
    """
    插入或更新 MySQL stocktradetodayinfo 表

    Args:
        trade_data: 交易数据

    Returns:
        是否成功
    """
    # 获取前收盘价
    pre_close = get_pre_close(trade_data["ts_code"], trade_data["trade_date"])

    # 计算涨跌幅
    pct_chg = 0
    if pre_close and pre_close > 0:
        pct_chg = (trade_data["close"] - pre_close) / pre_close * 100

    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            # 生成 ID（使用时间戳+随机数）
            import time
            import random
            ts = int(time.time() * 1000)
            record_id = float(f"{ts}{random.randint(10, 99)}")

            sql = """
                INSERT INTO stocktradetodayinfo
                (id, ts_code, amount, echange, close, high, low, open, pct_chg, pre_close, trade_date, vol, trade_date_tmp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    amount = VALUES(amount),
                    echange = VALUES(echange),
                    close = VALUES(close),
                    high = VALUES(high),
                    low = VALUES(low),
                    open = VALUES(open),
                    pct_chg = VALUES(pct_chg),
                    pre_close = VALUES(pre_close),
                    trade_date = VALUES(trade_date),
                    vol = VALUES(vol),
                    trade_date_tmp = VALUES(trade_date_tmp)
            """
            trade_datetime = datetime.combine(trade_data["trade_date"], datetime.min.time())

            cursor.execute(sql, (
                record_id,
                trade_data["ts_code"],
                trade_data["amount"],
                0,  # echange
                trade_data["close"],
                trade_data["high"],
                trade_data["low"],
                trade_data["open"],
                pct_chg,
                pre_close or 0,
                trade_datetime,
                trade_data["vol"],
                trade_datetime
            ))

            conn.commit()
            return True

    except Exception as e:
        logger.error(f"插入数据失败: {e}, data: {trade_data}")
        conn.rollback()
        return False
    finally:
        conn.close()


def sync_daily_trade_data(target_date: date = None) -> Dict[str, Any]:
    """
    同步指定日期的交易数据

    Args:
        target_date: 目标日期，默认今天

    Returns:
        同步结果
    """
    if target_date is None:
        target_date = date.today()

    logger.info(f"开始同步 {target_date} 的交易数据...")

    # 1. 从 PostgreSQL 获取数据
    trade_data_list = fetch_daily_trade_data(target_date)

    if not trade_data_list:
        return {
            "success": False,
            "message": f"没有找到 {target_date} 的交易数据",
            "count": 0
        }

    # 2. 逐条插入 MySQL
    success_count = 0
    fail_count = 0

    for trade_data in trade_data_list:
        if insert_or_update_trade_info(trade_data):
            success_count += 1
        else:
            fail_count += 1

    logger.info(f"同步完成: 成功 {success_count}, 失败 {fail_count}")

    return {
        "success": True,
        "message": f"同步完成: 成功 {success_count}, 失败 {fail_count}",
        "total": len(trade_data_list),
        "success_count": success_count,
        "fail_count": fail_count,
        "date": target_date.strftime("%Y-%m-%d")
    }


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    # 测试同步今天的数据
    result = sync_daily_trade_data()
    print(f"同步结果: {result}")
