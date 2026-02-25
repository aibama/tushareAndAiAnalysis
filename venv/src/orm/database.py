"""
申万行业分类数据库访问层
提供数据库连接和基础操作
"""
import pymysql
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from typing import Optional
import threading

# 数据库配置
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "database": "stockdata",
    "charset": "utf8mb4",
}

# 全局引擎和锁
_engine = None
_engine_lock = threading.Lock()


def get_engine():
    """获取SQLAlchemy引擎（使用连接池）"""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                connection_string = (
                    f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
                    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
                    f"?charset={DB_CONFIG['charset']}"
                )
                _engine = create_engine(
                    connection_string,
                    poolclass=QueuePool,
                    pool_size=5,
                    max_overflow=10,
                    pool_pre_ping=True,
                    pool_recycle=3600
                )
    return _engine


def get_connection():
    """获取数据库连接（pymysql原生连接，用于非pandas操作）"""
    return pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset=DB_CONFIG["charset"],
        cursorclass=pymysql.cursors.DictCursor
    )


def execute_sql(sql: str, params: tuple = None) -> int:
    """执行SQL语句，返回影响的行数"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if params:
                # 如果是字典，转换为元组
                if isinstance(params, dict):
                    param_values = tuple(params.values())
                    cursor.execute(sql, param_values)
                else:
                    cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            conn.commit()
            return cursor.rowcount
    finally:
        conn.close()


def execute_many(sql: str, params_list: list) -> int:
    """批量执行SQL语句"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(sql), params_list)
        conn.commit()
        return result.rowcount


def query_df(sql: str, params: dict = None) -> pd.DataFrame:
    """查询数据，返回DataFrame"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 将字典参数转换为元组（如果是字典）
            if params:
                # 提取所有值作为元组
                param_values = tuple(params.values())
                cursor.execute(sql, param_values)
            else:
                cursor.execute(sql)
            
            # 检查是否有结果集
            if cursor.description is None:
                return pd.DataFrame()
            
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return pd.DataFrame(rows, columns=columns)
    finally:
        conn.close()


def table_exists(table_name: str) -> bool:
    """检查表是否存在"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT COUNT(*) as count 
                FROM information_schema.tables 
                WHERE table_schema = %s AND table_name = %s
            """
            cursor.execute(sql, (DB_CONFIG['database'], table_name))
            result = cursor.fetchone()
            return result['count'] > 0 if result else False
    finally:
        conn.close()
