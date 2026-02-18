"""
数据库操作模块
"""
import pymysql
from typing import List, Dict, Optional, Any
from datetime import datetime
from contextlib import contextmanager
import logging
import sys
import os

# 添加项目根目录到sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PatternAnalysis.config import DB_CONFIG
from PatternAnalysis.config import ZHITU_API_CONFIG

logger = logging.getLogger(__name__)

DATA_SOURCE = ZHITU_API_CONFIG["data_source"]


@contextmanager
def get_connection():
    """获取数据库连接"""
    conn = pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset=DB_CONFIG["charset"],
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        yield conn
    finally:
        conn.close()


def save_stock_list_to_db(stock_list: List[Dict]) -> int:
    """
    保存股票列表到stockinfobase表
    dm -> ts_code, mc -> name, jys -> factory_code
    """
    if not stock_list:
        return 0

    sql = """
        INSERT INTO stockinfobase (ts_code, name, factory_code, last_update_time)
        VALUES (%s, %s, %s, NOW())
        ON DUPLICATE KEY UPDATE
            name = VALUES(name),
            factory_code = VALUES(factory_code),
            last_update_time = NOW()
    """

    success_count = 0
    fail_count = 0

    with get_connection() as conn:
        with conn.cursor() as cursor:
            try:
                conn.autocommit(False)
                for stock in stock_list:
                    try:
                        ts_code = stock.get("dm")
                        name = stock.get("mc")
                        factory_code = stock.get("jys")

                        if ts_code:
                            cursor.execute(sql, (ts_code, name, factory_code))
                            success_count += 1
                        else:
                            logger.warning(f"股票数据缺少dm字段: {stock}")
                            fail_count += 1
                    except Exception as e:
                        logger.error(f"插入股票失败: {stock}, 错误: {e}")
                        fail_count += 1

                conn.commit()
                logger.info(f"保存股票列表完成: 成功{success_count}条, 失败{fail_count}条")

            except Exception as e:
                conn.rollback()
                logger.error(f"保存股票列表事务失败: {e}")
                return -1

    return success_count


def get_all_ts_codes() -> List[str]:
    """
    获取不在stock_trade_info表中的股票代码（从stockinfobase获取）
    用于增量获取，只获取尚未处理过的股票
    """
    # 使用CONVERT函数强制统一字符集，避免排序规则冲突
    sql = """
        SELECT b.ts_code 
        FROM stockinfobase b
        WHERE NOT EXISTS (
            SELECT 1 FROM stock_trade_info t 
            WHERE CONVERT(t.stock_code USING utf8mb4) = CONVERT(b.ts_code USING utf8mb4)
        )
    """

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            results = cursor.fetchall()
            ts_codes = [row["ts_code"] for row in results if row.get("ts_code")]
            logger.info(f"找到 {len(ts_codes)} 只股票需要获取详细信息（排除已处理的）")
            return ts_codes


def save_stock_info_to_db(stock_info: Dict) -> int:
    """
    保存股票详细信息到stock_trade_info表
    """
    if not stock_info:
        return 0

    sql = """
        INSERT INTO stock_trade_info (
            market_code, stock_symbol, stock_code, stock_name, listing_date,
            prev_close_price, up_limit_price, down_limit_price,
            float_shares, total_shares, price_tick, is_suspended,
            data_source, updated_at
        ) VALUES (
            %s, %s, %s, %s, STR_TO_DATE(%s, '%%Y%%m%%d'),
            %s, %s, %s, %s, %s, %s, %s, %s, NOW()
        )
        ON DUPLICATE KEY UPDATE
            stock_name = VALUES(stock_name),
            prev_close_price = VALUES(prev_close_price),
            up_limit_price = VALUES(up_limit_price),
            down_limit_price = VALUES(down_limit_price),
            float_shares = VALUES(float_shares),
            total_shares = VALUES(total_shares),
            price_tick = VALUES(price_tick),
            is_suspended = VALUES(is_suspended),
            updated_at = NOW()
    """

    try:
        # ei -> market_code
        market_code = stock_info.get("ei")

        # ii -> stock_symbol (股票交易代码，如000001)
        stock_symbol = stock_info.get("ii")

        # ii + "." + ei -> stock_code (股票程序代码，如600519.SH)
        ii_code = stock_info.get("ii")
        stock_code_full = f"{ii_code}.{market_code}" if ii_code and market_code else None

        # name -> stock_name
        stock_name = stock_info.get("name")

        # od -> listing_date
        listing_date = stock_info.get("od")

        # pc -> prev_close_price
        prev_close_price = stock_info.get("pc")
        if prev_close_price is not None:
            prev_close_price = round(float(prev_close_price), 2)

        # up -> up_limit_price
        up_limit_price = stock_info.get("up")
        if up_limit_price is not None:
            up_limit_price = round(float(up_limit_price), 2)

        # dp -> down_limit_price
        down_limit_price = stock_info.get("dp")
        if down_limit_price is not None:
            down_limit_price = round(float(down_limit_price), 2)

        # fv -> float_shares
        float_shares = stock_info.get("fv")
        if float_shares is not None:
            float_shares = round(float(float_shares))

        # tv -> total_shares
        total_shares = stock_info.get("tv")
        if total_shares is not None:
            total_shares = round(float(total_shares))

        # pk -> price_tick
        price_tick = stock_info.get("pk")
        if price_tick is not None:
            price_tick = round(float(price_tick), 2)

        # is -> is_suspended (is <= 0 时为0正常)
        is_suspended_value = stock_info.get("is")
        is_suspended = 0 if (is_suspended_value is None or is_suspended_value <= 0) else 1

        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (
                    market_code, stock_symbol, stock_code_full, stock_name, listing_date,
                    prev_close_price, up_limit_price, down_limit_price,
                    float_shares, total_shares, price_tick, is_suspended,
                    DATA_SOURCE
                ))
                conn.commit()

                logger.debug(f"保存股票信息成功: {stock_code_full}")
                return 1

    except Exception as e:
        logger.error(f"保存股票信息失败: {stock_info.get('ii')}, 错误: {e}")
        return 0


def batch_save_stock_info(stock_info_list: List[Dict]) -> tuple:
    """批量保存股票详细信息"""
    if not stock_info_list:
        return (0, 0)

    sql = """
        INSERT INTO stock_trade_info (
            market_code, stock_symbol, stock_code, stock_name, listing_date,
            prev_close_price, up_limit_price, down_limit_price,
            float_shares, total_shares, price_tick, is_suspended,
            data_source, updated_at
        ) VALUES (
            %s, %s, %s, %s, STR_TO_DATE(%s, '%%Y%%m%%d'),
            %s, %s, %s, %s, %s, %s, %s, %s, NOW()
        )
        ON DUPLICATE KEY UPDATE
            stock_name = VALUES(stock_name),
            prev_close_price = VALUES(prev_close_price),
            up_limit_price = VALUES(up_limit_price),
            down_limit_price = VALUES(down_limit_price),
            float_shares = VALUES(float_shares),
            total_shares = VALUES(total_shares),
            price_tick = VALUES(price_tick),
            is_suspended = VALUES(is_suspended),
            updated_at = NOW()
    """

    success_count = 0
    fail_count = 0

    with get_connection() as conn:
        with conn.cursor() as cursor:
            try:
                conn.autocommit(False)

                for stock_info in stock_info_list:
                    try:
                        market_code = stock_info.get("ei")
                        # ii -> stock_symbol (股票交易代码，如000001)
                        stock_symbol = stock_info.get("ii")
                        # ii + "." + ei -> stock_code (股票程序代码，如600519.SH)
                        ii_code = stock_info.get("ii")
                        stock_code_full = f"{ii_code}.{market_code}" if ii_code and market_code else None
                        stock_name = stock_info.get("name")
                        listing_date = stock_info.get("od")

                        prev_close_price = stock_info.get("pc")
                        if prev_close_price is not None:
                            prev_close_price = round(float(prev_close_price), 2)

                        up_limit_price = stock_info.get("up")
                        if up_limit_price is not None:
                            up_limit_price = round(float(up_limit_price), 2)

                        down_limit_price = stock_info.get("dp")
                        if down_limit_price is not None:
                            down_limit_price = round(float(down_limit_price), 2)

                        float_shares = stock_info.get("fv")
                        if float_shares is not None:
                            float_shares = round(float(float_shares))

                        total_shares = stock_info.get("tv")
                        if total_shares is not None:
                            total_shares = round(float(total_shares))

                        price_tick = stock_info.get("pk")
                        if price_tick is not None:
                            price_tick = round(float(price_tick), 2)

                        is_suspended_value = stock_info.get("is")
                        is_suspended = 0 if (is_suspended_value is None or is_suspended_value <= 0) else 1

                        cursor.execute(sql, (
                            market_code, stock_symbol, stock_code_full, stock_name, listing_date,
                            prev_close_price, up_limit_price, down_limit_price,
                            float_shares, total_shares, price_tick, is_suspended,
                            DATA_SOURCE
                        ))
                        success_count += 1

                    except Exception as e:
                        logger.error(f"批量插入股票信息失败: {stock_info.get('ii')}, 错误: {e}")
                        fail_count += 1

                conn.commit()
                logger.info(f"批量保存完成: 成功{success_count}条, 失败{fail_count}条")

            except Exception as e:
                conn.rollback()
                logger.error(f"批量保存事务失败: {e}")
                return (-1, len(stock_info_list))

    return (success_count, fail_count)
