"""
涨跌停判断服务 - 计算 stocktradetodayinfo 中每只股票的涨跌停状态
"""
from __future__ import annotations

import logging
import os
import sys
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional

# 复用项目配置
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PatternAnalysis.config import DB_CONFIG
from PatternAnalysis.tsanghiapi.distributed_lock import RedisLock

logger = logging.getLogger(__name__)

# Redis 锁配置
LOCK_KEY_PREFIX = "limit_status:sync:lock:"
LOCK_TIMEOUT_SECONDS = 1800  # 30分钟


def get_limit_rate(ts_code: str) -> float:
    """
    根据 ts_code 获取涨跌停比例

    Args:
        ts_code: 股票代码，如 '600000.SH'

    Returns:
        涨跌停比例（浮点数，如 0.10 表示 10%）
    """
    # 去掉后缀，只保留数字部分
    code_prefix = ts_code.split('.')[0] if '.' in ts_code else ts_code

    if code_prefix.startswith(('688', '300', '301')):
        return 0.20  # 科创板、创业板
    elif code_prefix.startswith('8'):
        return 0.30  # 北交所
    else:
        # 主板普通股 (600/000/002/003 开头)
        return 0.10


def round_half_up(value: float, places: int = 2) -> float:
    """
    四舍五入保留指定位数小数

    Args:
        value: 待四舍五入的值
        places: 保留小数位数，默认2位

    Returns:
        四舍五入后的浮点数
    """
    if value is None:
        return 0.0
    d = Decimal(str(value))
    return float(d.quantize(Decimal(f'0.{"0" * places}'), rounding=ROUND_HALF_UP))


def get_limit_status(row: Dict[str, Any]) -> str:
    """
    根据单条股票交易数据判断涨跌停状态

    Args:
        row: 包含 ts_code, pre_close, close 字段的字典

    Returns:
        'UP_MAX' - 涨停
        'DOWN_MAX' - 跌停
        'NORMAL' - 正常
    """
    ts_code = row.get('ts_code', '')
    pre_close = row.get('pre_close')
    close = row.get('close')

    # 处理空值
    if pre_close is None or close is None or pre_close == 0:
        return 'NORMAL'

    # 转换为 Decimal 进行精确计算
    pre_close_dec = Decimal(str(pre_close))
    close_dec = Decimal(str(close))
    rate = Decimal(str(get_limit_rate(ts_code)))

    # 计算涨跌停价（精确到分）
    limit_up = (pre_close_dec * (1 + rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    limit_down = (pre_close_dec * (1 - rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # 精度容差
    eps = Decimal('1e-8')

    if close_dec >= limit_up - eps:
        return 'UP_MAX'
    elif close_dec <= limit_down + eps:
        return 'DOWN_MAX'
    else:
        return 'NORMAL'


def calculate_limit_status_for_all(trade_date: Optional[str] = None) -> Dict[str, Any]:
    """
    计算所有股票的涨跌停状态并更新到数据库

    Args:
        trade_date: 交易日期，默认最新日期

    Returns:
        包含执行结果的字典
    """
    import pymysql
    from datetime import datetime

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
            # 如果未指定日期，获取最新交易日期
            if trade_date is None:
                cursor.execute("SELECT MAX(trade_date) as max_date FROM stocktradetodayinfo")
                result = cursor.fetchone()
                if result and result.get('max_date'):
                    trade_date = result['max_date']
                    if isinstance(trade_date, datetime):
                        trade_date = trade_date.strftime('%Y-%m-%d')
                else:
                    return {"success": False, "message": "stocktradetodayinfo 表为空"}

            logger.info(f"开始计算涨跌停状态，日期: {trade_date}")

            # 查询需要计算的数据（排除已计算的）
            sql = """
                SELECT id, ts_code, pre_close, close, limit_status
                FROM stocktradetodayinfo
                WHERE trade_date = %s
                  AND (limit_status IS NULL OR limit_status = '' OR limit_status = '正常')
            """
            cursor.execute(sql, (trade_date,))
            rows = cursor.fetchall()

            if not rows:
                return {"success": True, "message": f"{trade_date} 无需计算的记录", "updated": 0}

            # 逐条计算并更新
            updated = 0
            for row in rows:
                limit_status = get_limit_status(row)
                cursor.execute(
                    "UPDATE stocktradetodayinfo SET limit_status = %s WHERE id = %s",
                    (limit_status, row['id'])
                )
                updated += 1

            conn.commit()
            logger.info(f"涨跌停状态计算完成，共更新 {updated} 条记录")

            return {
                "success": True,
                "message": f"计算完成，更新 {updated} 条",
                "trade_date": trade_date,
                "updated": updated
            }

    except Exception as e:
        conn.rollback()
        logger.exception(f"计算涨跌停状态失败: {e}")
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def calculate_limit_status_for_stock(ts_code: str, trade_date: Optional[str] = None) -> Dict[str, Any]:
    """
    计算指定股票的涨跌停状态

    Args:
        ts_code: 股票代码
        trade_date: 交易日期，默认最新日期

    Returns:
        涨跌停状态
    """
    import pymysql
    from datetime import datetime

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
                "SELECT ts_code, pre_close, close FROM stocktradetodayinfo WHERE ts_code = %s AND trade_date = %s",
                (ts_code, trade_date)
            )
            row = cursor.fetchone()

            if not row:
                return {"success": False, "message": f"未找到 {ts_code} 在 {trade_date} 的数据"}

            limit_status = get_limit_status(row)

            # 更新数据库
            cursor.execute(
                "UPDATE stocktradetodayinfo SET limit_status = %s WHERE ts_code = %s AND trade_date = %s",
                (limit_status, ts_code, trade_date)
            )
            conn.commit()

            return {
                "success": True,
                "ts_code": ts_code,
                "trade_date": trade_date,
                "limit_status": limit_status,
                "pre_close": row.get('pre_close'),
                "close": row.get('close')
            }

    except Exception as e:
        logger.exception(f"计算涨跌停状态失败: {e}")
        return {"success": False, "message": str(e)}
    finally:
        conn.close()