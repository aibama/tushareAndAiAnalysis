"""
AkShare 应用层：读取 MySQL stockinfobase（与 tsanghiapi 同库同表字段约定）。
"""
import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import pymysql
import os
import sys

_project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PatternAnalysis.config import DB_CONFIG

logger = logging.getLogger(__name__)


@contextmanager
def get_connection():
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
        yield conn
    finally:
        conn.close()


def get_all_stockinfobase() -> List[Dict[str, Any]]:
    """读取 stockinfobase 全部股票的 ts_code、name、factory_code。"""
    sql = "SELECT ts_code, name, factory_code FROM stockinfobase"
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
                return list(rows) if rows else []
    except Exception as e:
        logger.error("读取 stockinfobase 失败: %s", e)
        raise


def get_stockinfobase_by_ts_code(ts_code: str) -> Optional[Dict[str, Any]]:
    """按 ts_code 查询一条股票基础信息。"""
    sql = "SELECT ts_code, name, factory_code FROM stockinfobase WHERE ts_code = %s"
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (ts_code,))
                return cursor.fetchone()
    except Exception as e:
        logger.error("按 ts_code 查询 stockinfobase 失败: %s", e)
        raise
