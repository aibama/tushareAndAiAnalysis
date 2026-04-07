"""
Tsanghi API 数据库操作模块
用于操作 stockinfobase 表和日志表
复用项目的数据库配置
"""
import pymysql
import logging
from typing import List, Dict, Optional, Any
from contextlib import contextmanager
import sys
import os

# 添加项目根目录到sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 复用项目的数据库配置
from PatternAnalysis.config import DB_CONFIG, LOG_TABLE_CONFIG, EXCHANGE_CODE_MAPPING

logger = logging.getLogger(__name__)


@contextmanager
def get_connection():
    """获取数据库连接（复用项目配置）"""
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


def get_stock_info_by_ts_code(ts_code: str) -> Optional[Dict[str, Any]]:
    """
    根据 ts_code 获取股票信息

    Args:
        ts_code: 股票代码 (如 000001.SZ)

    Returns:
        股票信息字典，包含 ts_code, factory_code 等
    """
    sql = "SELECT ts_code, name, factory_code FROM stockinfobase WHERE ts_code = %s"

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (ts_code,))
            result = cursor.fetchone()
            return result


def get_all_stock_info() -> List[Dict[str, Any]]:
    """
    获取所有股票信息

    Returns:
        股票信息列表
    """
    sql = "SELECT ts_code, name, factory_code FROM stockinfobase"

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            results = cursor.fetchall()
            return results or []


def get_exchange_code_from_factory_code(factory_code: str) -> str:
    """
    根据 factory_code 获取交易所代码

    Args:
        factory_code: 交易所代码 (SZ -> XSHE, SH -> XSHG)

    Returns:
        交易所API代码
    """
    # factory_code 可能是 "深市" / "沪市" / "SZ" / "SH" 等
    # 需要映射为 API 需要的格式
    mapping = EXCHANGE_CODE_MAPPING

    # 尝试直接映射
    if factory_code in mapping:
        return mapping[factory_code]

    # 尝试模糊匹配
    factory_code_upper = factory_code.upper() if factory_code else ""
    if "深" in factory_code or "SZ" in factory_code_upper:
        return mapping.get("SZ", "XSHE")
    if "沪" in factory_code or "SH" in factory_code_upper:
        return mapping.get("SH", "XSHG")

    # 默认返回深交所
    return mapping.get("SZ", "XSHE")


def get_ticker_from_ts_code(ts_code: str) -> str:
    """
    从 ts_code 提取 ticker（处理多种格式）

    处理规则：
    - 000001.SZ -> 000001
    - 600519.SH -> 600519
    - 1.600519 -> 600519 (去掉前缀1.)
    - 0.000001 -> 000001 (去掉前缀0.)
    - 最终输出纯数字的6位股票代码

    Args:
        ts_code: 股票代码 (如 000001.SZ, 1.600519, 0.000001)

    Returns:
        股票代码 (如 000001, 600519)
    """
    if not ts_code:
        return ""

    # 去掉 .SZ 或 .SH 后缀
    if "." in ts_code:
        code_part = ts_code.split(".")[0]
    else:
        code_part = ts_code

    # 去掉 1. 或 0. 前缀（如 1.600519 -> 600519, 0.000001 -> 000001）
    if code_part.startswith("1.") or code_part.startswith("0."):
        code_part = code_part[2:]

    # 去除可能存在的其他前缀（如有）
    # 确保返回6位数字，不足6位前面补0
    if code_part.isdigit():
        return code_part.zfill(6)

    return code_part


def log_stock_daily_sync_status(ts_code: str, status: str, message: str = "") -> bool:
    """
    记录股票日线数据同步状态到日志表

    Args:
        ts_code: 股票代码
        status: 状态 (success/error)
        message: 消息

    Returns:
        是否成功
    """
    log_code = LOG_TABLE_CONFIG.get("log_code_stock_daily", "000003")

    sql = """
        INSERT INTO alert_log (log_code, alert_message, query_expression, created_at, updated_at)
        VALUES (%s, %s, %s, NOW(), NOW())
    """

    # 构建 alert_message: "stock_daily_data_fill_tsanghiapi - {status}"
    alert_msg = f"stock_daily_data_fill_tsanghiapi - {status}"
    if message:
        alert_msg += f": {message}"

    # 构建 query_expression: "attri1 = {ts_code}"
    query_expr = f"attri1 = {ts_code}"

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (log_code, alert_msg, query_expr))
            conn.commit()
            logger.info(f"日志记录成功: ts_code={ts_code}, status={status}")
            return True
    except Exception as e:
        logger.error(f"日志记录失败: ts_code={ts_code}, error={e}")
        return False


def batch_log_stock_daily_sync(results: List[Dict[str, Any]]) -> int:
    """
    批量记录股票日线数据同步状态

    Args:
        results: 同步结果列表，每项包含 ts_code, status, message

    Returns:
        成功记录数
    """
    success_count = 0

    for item in results:
        ts_code = item.get("ts_code")
        status = item.get("status")
        message = item.get("message", "")

        if ts_code and status:
            if log_stock_daily_sync_status(ts_code, status, message):
                success_count += 1

    return success_count
