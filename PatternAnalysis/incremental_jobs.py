"""
股票形态分析系统 - 增量数据处理
在新日线数据插入后，对受影响个股的形态分类任务做增量补全和重算
"""
import logging
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from pathlib import Path

import pandas as pd
import pymysql
from sqlalchemy import text

from .config import DB_CONFIG, PERIOD_CONFIG
from .data_access import (
    get_connection,
    get_engine,
    get_latest_trade_date,
    get_all_ts_codes,
    get_stock_ohlc_in_range,
    get_updated_ts_codes,
    close_all_connections
)
from .periods import get_period_windows, get_period_months
from .returns import calc_period_return
from .pattern_model import PatternType, classify_pattern, PATTERN_NAME_MAP


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# 状态表SQL
CREATE_STATUS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pattern_analysis_status (
  ts_code VARCHAR(255) NOT NULL,
  period_type VARCHAR(16) NOT NULL,
  last_trade_date DATE NOT NULL,
  last_update_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (ts_code, period_type),
  INDEX idx_last_update (last_update_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
"""

# 结果表SQL
CREATE_RESULT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pattern_analysis_result (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  ts_code VARCHAR(255) NOT NULL,
  period_type VARCHAR(16) NOT NULL,
  pattern_type INT NOT NULL,
  pattern_name VARCHAR(50) NOT NULL,
  curr_return FLOAT,
  prev_return FLOAT,
  curr_start DATE NOT NULL,
  curr_end DATE NOT NULL,
  prev_start DATE NOT NULL,
  prev_end DATE NOT NULL,
  calculation_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  INDEX idx_ts_code (ts_code),
  INDEX idx_period_type (period_type),
  INDEX idx_pattern_type (pattern_type),
  INDEX idx_calculation_time (calculation_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
"""


def init_tables():
    """初始化状态表和结果表"""
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(CREATE_STATUS_TABLE_SQL)
            cursor.execute(CREATE_RESULT_TABLE_SQL)
        conn.commit()
        conn.close()
        logger.info("增量数据处理表初始化完成")
    except Exception as e:
        logger.error(f"初始化表失败: {e}")
        raise


def get_last_processed_date(ts_code: str, period_type: str) -> Optional[date]:
    """获取股票在指定周期下的最后处理日期"""
    engine = get_engine()
    sql = """
        SELECT last_trade_date 
        FROM pattern_analysis_status 
        WHERE ts_code = :ts_code AND period_type = :period_type
    """
    
    try:
        # 使用 pandas read_sql，更兼容
        import pandas as pd
        df = pd.read_sql(text(sql), engine, params={"ts_code": ts_code, "period_type": period_type})
        
        if df.empty:
            return None
        
        last_date = df['last_trade_date'].iloc[0]
        # 确保返回date类型
        if isinstance(last_date, datetime):
            return last_date.date()
        elif isinstance(last_date, date):
            return last_date
        elif isinstance(last_date, str):
            return datetime.strptime(last_date.split()[0], '%Y-%m-%d').date()
        elif pd.isna(last_date):
            return None
        return last_date
    except Exception as e:
        logger.error(f"获取最后处理日期失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def update_status(ts_code: str, period_type: str, last_trade_date: date):
    """更新状态表"""
    conn = get_connection()
    sql = """
        INSERT INTO pattern_analysis_status (ts_code, period_type, last_trade_date, last_update_time)
        VALUES (%s, %s, %s, NOW())
        ON DUPLICATE KEY UPDATE last_trade_date = %s, last_update_time = NOW()
    """
    
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, [ts_code, period_type, last_trade_date, last_trade_date])
        conn.commit()
    finally:
        conn.close()


def save_result(
    ts_code: str,
    period_type: str,
    pattern: PatternType,
    curr_return: Optional[float],
    prev_return: Optional[float],
    curr_start: date,
    curr_end: date,
    prev_start: date,
    prev_end: date
):
    """保存分类结果"""
    conn = get_connection()
    sql = """
        INSERT INTO pattern_analysis_result 
        (ts_code, period_type, pattern_type, pattern_name, curr_return, prev_return,
         curr_start, curr_end, prev_start, prev_end)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, [
                ts_code, period_type, int(pattern.value), 
                PATTERN_NAME_MAP[pattern],
                curr_return, prev_return,
                curr_start, curr_end, prev_start, prev_end
            ])
        conn.commit()
    finally:
        conn.close()


def classify_single_stock(
    ts_code: str,
    period_type: str,
    latest_date: date
) -> Tuple[PatternType, Optional[float], Optional[float], dict]:
    """对单只股票进行形态分类"""
    months = get_period_months(period_type)
    if months is None:
        months = 3
    
    (curr_start, curr_end), (prev_start, prev_end) = get_period_windows(latest_date, months)
    
    # 调试日志：输出查询日期范围
    logger.debug(f"股票 {ts_code} 查询日期范围: 当前周期 [{curr_start} 到 {curr_end}], 上一周期 [{prev_start} 到 {prev_end}]")
    
    # 获取数据
    df_curr = get_stock_ohlc_in_range(ts_code, curr_start, curr_end)
    df_prev = get_stock_ohlc_in_range(ts_code, prev_start, prev_end)
    
    if df_curr.empty:
        # 尝试查询该股票在数据库中的实际日期范围
        logger.warning(f"股票 {ts_code} 在当前周期 [{curr_start} 到 {curr_end}] 没有数据")
        # 查询该股票的实际数据范围用于调试
        try:
            engine = get_engine()
            debug_sql = """
                SELECT MIN(DATE(trade_date)) as min_date, MAX(DATE(trade_date)) as max_date, COUNT(*) as cnt
                FROM stocktradetodayinfo
                WHERE ts_code = :ts_code
            """
            with engine.connect() as conn:
                from sqlalchemy import text
                result = conn.execute(text(debug_sql), {"ts_code": ts_code})
                row = result.fetchone()
                if row:
                    logger.debug(f"股票 {ts_code} 在数据库中的实际日期范围: {row[0]} 到 {row[1]}, 共 {row[2]} 条记录")
        except Exception as e:
            logger.debug(f"查询股票 {ts_code} 实际日期范围失败: {e}")
        
        return PatternType.OTHER, None, None, {
            "curr_start": curr_start, "curr_end": curr_end,
            "prev_start": prev_start, "prev_end": prev_end
        }
    
    # 分类
    pattern = classify_pattern(df_curr, mode="rule")
    
    # 计算涨跌幅
    curr_return = calc_period_return(df_curr)
    prev_return = calc_period_return(df_prev) if not df_prev.empty else None
    
    return pattern, curr_return, prev_return, {
        "curr_start": curr_start, "curr_end": curr_end,
        "prev_start": prev_start, "prev_end": prev_end
    }


def process_stock_incremental(
    ts_code: str,
    period_types: List[str] = None,
    latest_date: date = None
):
    """增量处理单只股票的形态分类"""
    if latest_date is None:
        latest_date = get_latest_trade_date()
    
    if latest_date is None:
        logger.error("无法获取最新交易日期")
        return
    
    period_types = period_types or PERIOD_CONFIG["available_periods"]
    
    for period_type in period_types:
        # 检查是否需要更新
        last_processed = get_last_processed_date(ts_code, period_type)
        
        if last_processed and last_processed >= latest_date:
            logger.debug(f"股票 {ts_code} 在周期 {period_type} 已是最新的")
            continue
        
        # 执行分类
        pattern, curr_ret, prev_ret, period_info = classify_single_stock(
            ts_code, period_type, latest_date
        )
        
        # 保存结果
        save_result(
            ts_code=ts_code,
            period_type=period_type,
            pattern=pattern,
            curr_return=curr_ret,
            prev_return=prev_ret,
            curr_start=period_info["curr_start"],
            curr_end=period_info["curr_end"],
            prev_start=period_info["prev_start"],
            prev_end=period_info["prev_end"]
        )
        
        # 更新状态
        update_status(ts_code, period_type, latest_date)
        
        logger.info(f"股票 {ts_code} 周期 {period_type} 分类完成: {PATTERN_NAME_MAP[pattern]}")


def run_incremental_job(since: datetime = None, period_types: List[str] = None):
    """运行增量处理任务"""
    logger.info("开始执行增量处理任务")
    
    # 初始化表
    init_tables()
    
    # 获取需要处理的股票列表
    if since:
        ts_codes = get_updated_ts_codes(since)
    else:
        ts_codes = get_all_ts_codes()
    
    logger.info(f"需要处理的股票数量: {len(ts_codes)}")
    
    # 获取最新交易日期
    latest_date = get_latest_trade_date()
    if latest_date is None:
        logger.error("数据库中没有交易数据")
        return
    
    # 批量处理
    total = len(ts_codes)
    for idx, ts_code in enumerate(ts_codes):
        try:
            process_stock_incremental(ts_code, period_types, latest_date)
            logger.info(f"进度: {idx + 1}/{total}")
        except Exception as e:
            logger.error(f"处理股票 {ts_code} 时出错: {e}")
    
    # 关闭连接池
    close_all_connections()
    logger.info("增量处理任务完成")


def run_full_recalculation(period_types: List[str] = None):
    """运行全量重算任务"""
    logger.info("开始执行全量重算任务")
    
    # 初始化表
    init_tables()
    
    ts_codes = get_all_ts_codes()
    logger.info(f"需要重算的股票数量: {len(ts_codes)}")
    
    latest_date = get_latest_trade_date()
    if latest_date is None:
        logger.error("数据库中没有交易数据")
        return
    
    period_types = period_types or PERIOD_CONFIG["available_periods"]
    
    total = len(ts_codes)
    for idx, ts_code in enumerate(ts_codes):
        try:
            # 重置状态，强制重新计算
            update_status(ts_code, period_types[0], date(2000, 1, 1))
            process_stock_incremental(ts_code, period_types, latest_date)
            logger.info(f"进度: {idx + 1}/{total}")
        except Exception as e:
            logger.error(f"重算股票 {ts_code} 时出错: {e}")
    
    # 关闭连接池
    close_all_connections()
    logger.info("全量重算任务完成")


def get_cached_results(
    period_type: str,
    pattern_type: PatternType = None,
    limit: int = 1000
) -> List[dict]:
    """获取缓存的分类结果"""
    engine = get_engine()
    
    if pattern_type:
        sql = """
            SELECT ts_code, pattern_type, pattern_name, curr_return, prev_return,
                   curr_start, curr_end, prev_start, prev_end, calculation_time
            FROM pattern_analysis_result
            WHERE period_type = :period_type AND pattern_type = :pattern_type
            ORDER BY calculation_time DESC
            LIMIT :limit_val
        """
        params = {
            "period_type": period_type, 
            "pattern_type": int(pattern_type.value), 
            "limit_val": limit
        }
    else:
        sql = """
            SELECT ts_code, pattern_type, pattern_name, curr_return, prev_return,
                   curr_start, curr_end, prev_start, prev_end, calculation_time
            FROM pattern_analysis_result
            WHERE period_type = :period_type
            ORDER BY calculation_time DESC
            LIMIT :limit_val
        """
        params = {"period_type": period_type, "limit_val": limit}
    
    try:
        # 使用 pandas read_sql，更兼容
        df = pd.read_sql(text(sql), engine, params=params)
        return df.to_dict('records') if not df.empty else []
    except Exception as e:
        logger.error(f"获取缓存结果失败: {e}")
        import traceback
        traceback.print_exc()
        return []


class IncrementalJobManager:
    """增量任务管理器"""
    
    def __init__(self):
        self.periods = PERIOD_CONFIG["available_periods"]
    
    def run_incremental(self, since: datetime = None):
        """运行增量任务"""
        run_incremental_job(since, self.periods)
    
    def run_full_recalculation(self):
        """运行全量重算"""
        run_full_recalculation(self.periods)
    
    def process_stock(self, ts_code: str):
        """处理单只股票"""
        process_stock_incremental(ts_code, self.periods)
    
    def get_results(self, period_type: str, pattern_type: PatternType = None):
        """获取缓存结果"""
        return get_cached_results(period_type, pattern_type)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="股票形态分析增量处理")
    parser.add_argument("--mode", choices=["incremental", "full", "init"], default="incremental")
    parser.add_argument("--since", type=str, help="增量起始时间，如 '2024-01-01'")
    
    args = parser.parse_args()
    
    if args.mode == "init":
        init_tables()
    elif args.mode == "incremental":
        since = None
        if args.since:
            since = datetime.strptime(args.since, "%Y-%m-%d")
        run_incremental_job(since)
    elif args.mode == "full":
        run_full_recalculation()
