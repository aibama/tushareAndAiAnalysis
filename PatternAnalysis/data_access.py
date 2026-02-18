"""
股票形态分析系统 - 数据访问层
从 stocktradetodayinfo 拉取K线数据
"""
import pymysql
import pandas as pd
from sqlalchemy import create_engine, text, bindparam
from sqlalchemy.pool import QueuePool
from typing import Optional, List, Tuple
from datetime import date, datetime
from .config import DB_CONFIG
import threading

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


def get_latest_trade_date() -> Optional[date]:
    """获取最新交易日期"""
    engine = get_engine()
    sql = "SELECT MAX(trade_date) AS max_dt FROM stocktradetodayinfo"
    
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(sql), conn)
        
        if df.empty or df['max_dt'].iloc[0] is None:
            return None
        
        max_dt = df['max_dt'].iloc[0]
        if isinstance(max_dt, datetime):
            return max_dt.date()
        elif isinstance(max_dt, str):
            return datetime.strptime(max_dt.split()[0], '%Y-%m-%d').date()
        return max_dt
    except Exception as e:
        print(f"获取最新交易日期失败: {e}")
        return None


def get_all_ts_codes() -> List[str]:
    """获取所有股票代码"""
    engine = get_engine()
    sql = "SELECT DISTINCT ts_code FROM stocktradetodayinfo"
    
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(sql), conn)
        return df['ts_code'].tolist()
    except Exception as e:
        print(f"获取股票代码列表失败: {e}")
        return []


def get_stock_ohlc_in_range(
    ts_code: str, 
    start: date, 
    end: date,
    include_tmp: bool = False
) -> pd.DataFrame:
    """
    获取指定股票的OHLC数据
    """
    engine = get_engine()
    
    # 确保日期是date类型
    if isinstance(start, datetime):
        start = start.date()
    if isinstance(end, datetime):
        end = end.date()
    
    if include_tmp:
        sql = """
            SELECT trade_date, ts_code, open, high, low, close, vol, amount, pct_chg, pre_close
            FROM stocktradetodayinfo
            WHERE ts_code = :ts_code 
              AND DATE(trade_date) >= :start_date 
              AND DATE(trade_date) <= :end_date
            ORDER BY trade_date ASC
        """
    else:
        sql = """
            SELECT trade_date, open, high, low, close, vol, amount
            FROM stocktradetodayinfo
            WHERE ts_code = :ts_code 
              AND DATE(trade_date) >= :start_date 
              AND DATE(trade_date) <= :end_date
            ORDER BY trade_date ASC
        """
    
    try:
        # 使用 pandas 的 read_sql，它更兼容不同版本的 SQLAlchemy
        # 将日期转换为字符串格式以确保兼容性
        start_str = start.strftime('%Y-%m-%d') if isinstance(start, date) else str(start)
        end_str = end.strftime('%Y-%m-%d') if isinstance(end, date) else str(end)
        
        # 使用 pandas read_sql，它自动处理参数绑定
        df = pd.read_sql(
            text(sql),
            engine,
            params={
                "ts_code": ts_code, 
                "start_date": start_str, 
                "end_date": end_str
            }
        )
        
        if not df.empty:
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df['open'] = pd.to_numeric(df['open'], errors='coerce')
            df['high'] = pd.to_numeric(df['high'], errors='coerce')
            df['low'] = pd.to_numeric(df['low'], errors='coerce')
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df['vol'] = pd.to_numeric(df['vol'], errors='coerce')
            if 'amount' in df.columns:
                df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        
        return df
    except Exception as e:
        print(f"获取股票 {ts_code} 数据失败: {e}")
        print(f"查询日期范围: {start} 到 {end}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


def get_updated_ts_codes(since: datetime) -> List[str]:
    """获取指定时间后有更新的股票代码"""
    engine = get_engine()
    sql = "SELECT DISTINCT ts_code FROM stocktradetodayinfo WHERE DATE(trade_date) >= :since_date"
    
    # 确保是date类型
    since_date = since.date() if isinstance(since, datetime) else since
    
    try:
        # 使用 pandas read_sql
        since_str = since_date.strftime('%Y-%m-%d') if isinstance(since_date, date) else str(since_date)
        df = pd.read_sql(text(sql), engine, params={"since_date": since_str})
        return df['ts_code'].tolist()
    except Exception as e:
        print(f"获取更新的股票代码失败: {e}")
        return []


def get_trade_dates_range(start: date, end: date) -> List[date]:
    """获取指定日期范围内的交易日列表"""
    engine = get_engine()
    sql = """
        SELECT DISTINCT DATE(trade_date) as trade_date
        FROM stocktradetodayinfo
        WHERE DATE(trade_date) >= :start_date AND DATE(trade_date) <= :end_date
        ORDER BY trade_date ASC
    """
    
    # 确保是date类型
    if isinstance(start, datetime):
        start = start.date()
    if isinstance(end, datetime):
        end = end.date()
    
    start_str = start.strftime('%Y-%m-%d') if isinstance(start, date) else str(start)
    end_str = end.strftime('%Y-%m-%d') if isinstance(end, date) else str(end)
    
    try:
        # 使用 pandas read_sql
        df = pd.read_sql(text(sql), engine, params={"start_date": start_str, "end_date": end_str})
        if df.empty:
            return []
        
        dates = []
        for d in df['trade_date']:
            if isinstance(d, datetime):
                dates.append(d.date())
            elif isinstance(d, date):
                dates.append(d)
            elif isinstance(d, str):
                dates.append(datetime.strptime(d.split()[0], '%Y-%m-%d').date())
            else:
                dates.append(d)
        return dates
    except Exception as e:
        print(f"获取交易日列表失败: {e}")
        return []


def close_all_connections():
    """关闭所有连接"""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


class StockDataAccess:
    """股票数据访问类"""
    
    def __init__(self):
        self.config = DB_CONFIG
    
    def get_connection(self):
        return get_connection()
    
    def get_engine(self):
        return get_engine()
    
    def get_latest_trade_date(self) -> Optional[date]:
        return get_latest_trade_date()
    
    def get_all_ts_codes(self) -> List[str]:
        return get_all_ts_codes()
    
    def get_stock_ohlc(self, ts_code: str, start: date, end: date) -> pd.DataFrame:
        return get_stock_ohlc_in_range(ts_code, start, end)
    
    def get_period_data(self, ts_code: str, period_months: int) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        from .periods import get_period_windows
        
        latest_dt = get_latest_trade_date()
        if latest_dt is None:
            return None, None
        
        (curr_start, curr_end), (prev_start, prev_end) = get_period_windows(latest_dt, period_months)
        
        df_curr = get_stock_ohlc_in_range(ts_code, curr_start, curr_end)
        df_prev = get_stock_ohlc_in_range(ts_code, prev_start, prev_end)
        
        return df_curr, df_prev
    
    def get_stock_returns_in_range(self, start: datetime, end: datetime, direction: str = "up") -> pd.DataFrame:
        """
        批量获取指定日期范围内所有股票的涨跌幅

        计算字段说明：
        - max_drawdown_rebound: 时间序列收益率 = (末日收盘价 - 首日收盘价) / 首日收盘价 * 100
        - price_range_return_rate: 区间最高收益 = (区间最高价 - 区间最低价) / 区间最低价 * 100（现货卖空概念）

        使用MySQL 8.0窗口函数优化：
        - 使用 ROW_NUMBER() 窗口函数标记首日和末日
        - 无需多次JOIN表，大幅提升查询性能

        Args:
            start: 开始日期时间
            end: 结束日期时间
            direction: up=只统计正值, down=只统计负值, all或None=统计全部

        Returns:
            包含ts_code、return_rate、max_drawdown_rebound、price_range_return_rate的DataFrame
        """
        engine = get_engine()

        # 确保日期是datetime类型
        if isinstance(start, date) and not isinstance(start, datetime):
            start = datetime.combine(start, datetime.min.time())
        if isinstance(end, date) and not isinstance(end, datetime):
            end = datetime.combine(end, datetime.min.time())

        # 日期字符串格式化
        start_str = start.strftime('%Y-%m-%d') if isinstance(start, (date, datetime)) else str(start)
        end_str = end.strftime('%Y-%m-%d') if isinstance(end, (date, datetime)) else str(end)

        # 根据direction参数构建过滤条件
        if direction == "up":
            direction_filter = "return_rate > 0"
        elif direction == "down":
            direction_filter = "return_rate < 0"
        else:
            direction_filter = "1=1"  # direction为all或None时不过滤

        # 使用临时表计算时间序列收益率和区间最高收益
        create_sql = """
            CREATE TEMPORARY TABLE calc_result AS
            SELECT
                t.ts_code,
                ROUND((t.last_close - t.first_close) / t.first_close * 100, 2) AS return_rate,
                ROUND((p.max_close - p.min_close) / p.min_close * 100, 2) AS price_range_return_rate
            FROM (
                -- 计算首日和末日收盘价
                SELECT
                    ts_code,
                    MAX(CASE WHEN rn_asc = 1 THEN close END) AS first_close,
                    MAX(CASE WHEN rn_desc = 1 THEN close END) AS last_close
                FROM (
                    SELECT
                        ts_code,
                        close,
                        ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date) AS rn_asc,
                        ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) AS rn_desc
                    FROM stocktradetodayinfo
                    WHERE trade_date >= :start_date
                      AND trade_date <= :end_date
                      AND close > 0
                ) ranked
                WHERE rn_asc = 1 OR rn_desc = 1
                GROUP BY ts_code
            ) t
            JOIN (
                -- 计算价格区间（区间最高收益，现货卖空概念）
                SELECT
                    ts_code,
                    MIN(close) AS min_close,
                    MAX(close) AS max_close
                FROM stocktradetodayinfo
                WHERE trade_date >= :start_date
                  AND trade_date <= :end_date
                  AND close > 0
                GROUP BY ts_code
            ) p ON t.ts_code = p.ts_code
            WHERE t.first_close > 0
              AND p.min_close > 0;
        """

        # 根据direction过滤的查询语句
        result_sql = f"""
            SELECT
                ts_code,
                return_rate AS max_drawdown_rebound,
                price_range_return_rate
            FROM calc_result
            WHERE {direction_filter}
        """

        try:
            # 执行SQL
            with engine.connect() as conn:
                from sqlalchemy import text
                # 创建临时表
                conn.execute(text(create_sql), {"start_date": start_str, "end_date": end_str})
                conn.commit()

                # 查询结果
                df = pd.read_sql(text(result_sql), conn)

            if df.empty:
                return pd.DataFrame(columns=["ts_code", "return_rate", "max_drawdown_rebound", "price_range_return_rate"])

            # 重命名列：return_rate = max_drawdown_rebound（时间序列收益率）
            df["return_rate"] = df["max_drawdown_rebound"]

            return df[["ts_code", "return_rate", "max_drawdown_rebound", "price_range_return_rate"]]
        except Exception as e:
            print(f"批量获取股票涨跌幅失败: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame(columns=["ts_code", "return_rate", "max_drawdown_rebound", "price_range_return_rate"])
