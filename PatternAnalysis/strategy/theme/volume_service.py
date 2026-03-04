"""
成交量主题分析服务
计算个股的成交量相关指标，包括：
1. 历史最低价前后一个月的日均成交量
2. 最近一次涨停后累计成交量和日均成交量占涨停当日成交量的比值

核心概念：
- 最低价日均成交量：找到历史最低价日期，取该日期前一个月和后一个月（共两个月）的日均成交量
- 涨停后成交量比值：计算最近一次涨停后累计成交量，以及涨停后的日均成交量占涨停当日成交量的比值
"""
import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import math

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

# 导入配置
import sys
import os
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PatternAnalysis.config import DB_CONFIG, REDIS_CONFIG

logger = logging.getLogger(__name__)

# Redis键前缀
VOLUME_INFO_HASH_PREFIX = f"{REDIS_CONFIG.get('key_prefix', 'stock_rank:')}volume_info:"


# ============== 数据模型 ==============

@dataclass
class LowestPriceVolumeInfo:
    """历史最低价成交量信息"""
    ts_code: str
    lowest_price: Optional[float] = None  # 历史最低价
    lowest_price_date: Optional[str] = None  # 历史最低价日期
    # 前一个月
    pre_month_start: Optional[str] = None  # 前一个月开始日期
    pre_month_end: Optional[str] = None  # 前一个月结束日期
    pre_month_avg_volume: Optional[float] = None  # 前一个月日均成交量
    pre_month_trading_days: Optional[int] = None  # 前一个月交易天数
    # 后一个月
    post_month_start: Optional[str] = None  # 后一个月开始日期
    post_month_end: Optional[str] = None  # 后一个月结束日期
    post_month_avg_volume: Optional[float] = None  # 后一个月日均成交量
    post_month_trading_days: Optional[int] = None  # 后一个月交易天数
    # 两个月合计
    total_avg_volume: Optional[float] = None  # 两个月日均成交量
    total_trading_days: Optional[int] = None  # 两个月总交易天数


@dataclass
class LimitUpVolumeInfo:
    """涨停后成交量信息"""
    ts_code: str
    # 涨停信息
    limit_up_date: Optional[str] = None  # 最近涨停日期
    limit_up_price: Optional[float] = None  # 涨停价格
    limit_up_volume: Optional[float] = None  # 涨停当日成交量
    # 涨停后统计
    days_since_limit_up: Optional[int] = None  # 距今天数
    cumulative_volume: Optional[float] = None  # 涨停后累计成交量
    post_limit_avg_volume: Optional[float] = None  # 涨停后日均成交量
    volume_ratio: Optional[float] = None  # 涨停后日均成交量/涨停当日成交量


# ============== 数据库连接 ==============

def get_engine():
    """获取SQLAlchemy引擎"""
    connection_string = (
        f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        f"?charset={DB_CONFIG['charset']}"
    )
    return create_engine(
        connection_string,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600
    )


# ============== 功能1：历史最低价前后一个月日均成交量 ==============

def calculate_lowest_price_volume(ts_code: str, engine=None) -> LowestPriceVolumeInfo:
    """
    计算历史最低价前后一个月的日均成交量
    
    算法说明：
    1. 找到股票的历史最低价日期
    2. 获取该日期前一个月和后一个月（共两个月）的交易数据
    3. 计算这两个月的日均成交量
    
    返回：
        LowestPriceVolumeInfo对象
    """
    need_dispose = False
    if engine is None:
        engine = get_engine()
        need_dispose = True
    
    try:
        # 查询股票的所有交易数据（按日期排序）
        sql = """
            SELECT
                trade_date,
                low,
                vol
            FROM stocktradetodayinfo
            WHERE ts_code = :ts_code
              AND low > 0
              AND vol > 0
            ORDER BY trade_date ASC
        """
        
        df = pd.read_sql(text(sql), engine, params={"ts_code": ts_code})
        
        if df.empty:
            return LowestPriceVolumeInfo(ts_code=ts_code)
        
        # 转换日期格式
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        
        # 找到历史最低价
        min_idx = df['low'].idxmin()
        lowest_price = float(df.loc[min_idx, 'low'])
        lowest_price_date = df.loc[min_idx, 'trade_date']
        
        result = LowestPriceVolumeInfo(
            ts_code=ts_code,
            lowest_price=lowest_price,
            lowest_price_date=lowest_price_date.strftime('%Y-%m-%d')
        )
        
        # 计算前一个月和后一个月的日期范围
        # 一个月按约22个交易日计算
        trading_days_per_month = 22
        
        # 获取前后各22个交易日的数据
        # 前一个月：从最低价日期往前找22个交易日
        pre_month_start_idx = max(0, min_idx - trading_days_per_month + 1)
        pre_month_end_idx = min_idx
        
        # 后一个月：从最低价日期往后找22个交易日
        post_month_start_idx = min_idx
        post_month_end_idx = min(len(df) - 1, min_idx + trading_days_per_month - 1)
        
        # 计算前一个月数据
        if pre_month_end_idx >= pre_month_start_idx:
            pre_df = df.iloc[pre_month_start_idx:pre_month_end_idx + 1]
            if not pre_df.empty:
                result.pre_month_start = pre_df['trade_date'].iloc[0].strftime('%Y-%m-%d')
                result.pre_month_end = pre_df['trade_date'].iloc[-1].strftime('%Y-%m-%d')
                result.pre_month_avg_volume = float(pre_df['vol'].mean())
                result.pre_month_trading_days = len(pre_df)
        
        # 计算后一个月数据
        if post_month_end_idx >= post_month_start_idx:
            post_df = df.iloc[post_month_start_idx:post_month_end_idx + 1]
            if not post_df.empty:
                result.post_month_start = post_df['trade_date'].iloc[0].strftime('%Y-%m-%d')
                result.post_month_end = post_df['trade_date'].iloc[-1].strftime('%Y-%m-%d')
                result.post_month_avg_volume = float(post_df['vol'].mean())
                result.post_month_trading_days = len(post_df)
        
        # 计算两个月合计的日均成交量
        if result.pre_month_trading_days and result.post_month_trading_days:
            result.total_trading_days = result.pre_month_trading_days + result.post_month_trading_days
            
            # 合并两个月的成交量数据计算总日均
            if pre_month_end_idx >= pre_month_start_idx and post_month_end_idx >= post_month_start_idx:
                combined_vol = list(pre_df['vol'].values) + list(post_df['vol'].values)
                result.total_avg_volume = float(sum(combined_vol) / len(combined_vol))
        
        return result
        
    except Exception as e:
        logger.error(f"计算股票 {ts_code} 历史最低价成交量失败: {e}")
        return LowestPriceVolumeInfo(ts_code=ts_code)
    finally:
        if need_dispose:
            engine.dispose()


def calculate_lowest_price_volume_for_all_stocks(num_threads: int = 4) -> List[LowestPriceVolumeInfo]:
    """
    多线程计算所有股票的历史最低价成交量信息
    
    Args:
        num_threads: 线程数
    
    Returns:
        List[LowestPriceVolumeInfo]: 所有股票的历史最低价成交量信息列表
    """
    logger.info(f"开始计算所有股票的历史最低价成交量信息，使用 {num_threads} 个线程...")
    
    # 获取所有股票代码
    engine = get_engine()
    try:
        sql = "SELECT DISTINCT ts_code FROM stocktradetodayinfo WHERE vol > 0 AND low > 0"
        df = pd.read_sql(text(sql), engine)
        ts_codes = df['ts_code'].tolist()
    finally:
        engine.dispose()
    
    if not ts_codes:
        logger.warning("未找到任何股票数据")
        return []
    
    total_stocks = len(ts_codes)
    logger.info(f"共有 {total_stocks} 只股票需要计算")
    
    # 分批处理
    chunk_size = math.ceil(total_stocks / num_threads)
    code_chunks = [ts_codes[i:i + chunk_size] for i in range(0, total_stocks, chunk_size)]
    
    all_results = []
    
    def process_chunk(chunk_codes: List[str], thread_id: int) -> List[LowestPriceVolumeInfo]:
        thread_engine = get_engine()
        results = []
        try:
            for code in chunk_codes:
                info = calculate_lowest_price_volume(code, thread_engine)
                if info:
                    results.append(info)
        finally:
            thread_engine.dispose()
        return results
    
    # 使用线程池并行计算
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = {
            executor.submit(process_chunk, chunk, i): i
            for i, chunk in enumerate(code_chunks)
        }
        
        completed = 0
        for future in as_completed(futures):
            try:
                chunk_results = future.result()
                all_results.extend(chunk_results)
                completed += 1
                logger.info(f"进度: {completed}/{num_threads} 批次完成")
            except Exception as e:
                logger.error(f"线程执行失败: {e}")
    
    logger.info(f"计算完成，共处理 {len(all_results)} 只股票")
    return all_results


# ============== 功能2：涨停后成交量统计 ==============

def calculate_limit_up_volume(ts_code: str, engine=None) -> LimitUpVolumeInfo:
    """
    计算最近一次涨停后累计成交量和日均成交量占涨停当日成交量的比值
    
    算法说明：
    1. 找到最近一次涨停的日期和当日成交量
    2. 计算从涨停日到最新交易日的后续累计成交量
    3. 计算涨停后的日均成交量
    4. 计算涨停后日均成交量 / 涨停当日成交量的比值
    
    返回：
        LimitUpVolumeInfo对象
    """
    need_dispose = False
    if engine is None:
        engine = get_engine()
        need_dispose = True
    
    try:
        # 查询股票的所有交易数据（按日期倒序）
        sql = """
            SELECT
                trade_date,
                pre_close,
                close,
                pct_chg,
                vol
            FROM stocktradetodayinfo
            WHERE ts_code = :ts_code
              AND close > 0
              AND pre_close > 0
            ORDER BY trade_date DESC
            LIMIT 500  # 最多查询近500个交易日
        """
        
        df = pd.read_sql(text(sql), engine, params={"ts_code": ts_code})
        
        if df.empty:
            return LimitUpVolumeInfo(ts_code=ts_code)
        
        # 转换日期格式
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        
        # 初始化结果
        result = LimitUpVolumeInfo(ts_code=ts_code)
        
        # 查找最近一次涨停
        limit_up_idx = None
        for idx, row in df.iterrows():
            pct_chg = row['pct_chg']
            if pct_chg is not None and pct_chg >= 9.9:  # 约等于涨停
                limit_up_idx = idx
                result.limit_up_date = row['trade_date'].strftime('%Y-%m-%d')
                result.limit_up_price = float(row['close'])
                result.limit_up_volume = float(row['vol'])
                break
        
        # 如果没有找到涨停，返回空结果
        if limit_up_idx is None:
            return result
        
        # 计算涨停后（不包含涨停日）到最新交易日的统计数据
        # limit_up_idx 是从0开始的（倒序），所以后面的行就是涨停后的数据
        post_limit_df = df.iloc[limit_up_idx + 1:]
        
        if not post_limit_df.empty:
            # 计算距今天数（交易日）
            result.days_since_limit_up = len(post_limit_df)
            
            # 计算累计成交量
            result.cumulative_volume = float(post_limit_df['vol'].sum())
            
            # 计算日均成交量
            result.post_limit_avg_volume = float(post_limit_df['vol'].mean())
            
            # 计算比值：涨停后日均成交量 / 涨停当日成交量
            if result.limit_up_volume and result.limit_up_volume > 0:
                result.volume_ratio = round(result.post_limit_avg_volume / result.limit_up_volume, 4)
        
        return result
        
    except Exception as e:
        logger.error(f"计算股票 {ts_code} 涨停后成交量失败: {e}")
        return LimitUpVolumeInfo(ts_code=ts_code)
    finally:
        if need_dispose:
            engine.dispose()


def calculate_limit_up_volume_for_all_stocks(num_threads: int = 4) -> List[LimitUpVolumeInfo]:
    """
    多线程计算所有股票的涨停后成交量信息
    
    Args:
        num_threads: 线程数
    
    Returns:
        List[LimitUpVolumeInfo]: 所有股票的涨停后成交量信息列表
    """
    logger.info(f"开始计算所有股票的涨停后成交量信息，使用 {num_threads} 个线程...")
    
    # 获取所有股票代码
    engine = get_engine()
    try:
        sql = "SELECT DISTINCT ts_code FROM stocktradetodayinfo WHERE close > 0 AND pre_close > 0"
        df = pd.read_sql(text(sql), engine)
        ts_codes = df['ts_code'].tolist()
    finally:
        engine.dispose()
    
    if not ts_codes:
        logger.warning("未找到任何股票数据")
        return []
    
    total_stocks = len(ts_codes)
    logger.info(f"共有 {total_stocks} 只股票需要计算")
    
    # 分批处理
    chunk_size = math.ceil(total_stocks / num_threads)
    code_chunks = [ts_codes[i:i + chunk_size] for i in range(0, total_stocks, chunk_size)]
    
    all_results = []
    
    def process_chunk(chunk_codes: List[str], thread_id: int) -> List[LimitUpVolumeInfo]:
        thread_engine = get_engine()
        results = []
        try:
            for code in chunk_codes:
                info = calculate_limit_up_volume(code, thread_engine)
                if info:
                    results.append(info)
        finally:
            thread_engine.dispose()
        return results
    
    # 使用线程池并行计算
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = {
            executor.submit(process_chunk, chunk, i): i
            for i, chunk in enumerate(code_chunks)
        }
        
        completed = 0
        for future in as_completed(futures):
            try:
                chunk_results = future.result()
                all_results.extend(chunk_results)
                completed += 1
                logger.info(f"进度: {completed}/{num_threads} 批次完成")
            except Exception as e:
                logger.error(f"线程执行失败: {e}")
    
    logger.info(f"计算完成，共处理 {len(all_results)} 只股票")
    return all_results


# ============== Redis存储 ==============

def save_lowest_price_volume_to_redis(info: LowestPriceVolumeInfo) -> bool:
    """
    将历史最低价成交量信息保存到Redis
    """
    try:
        import redis
        client = redis.Redis(
            host=REDIS_CONFIG["host"],
            port=REDIS_CONFIG["port"],
            db=REDIS_CONFIG.get("db", 0),
            password=REDIS_CONFIG.get("password"),
            decode_responses=True
        )
        
        hash_key = f"{VOLUME_INFO_HASH_PREFIX}lowest:{info.ts_code}"
        info_dict = {
            "ts_code": info.ts_code,
            "lowest_price": str(info.lowest_price) if info.lowest_price else "",
            "lowest_price_date": info.lowest_price_date or "",
            "pre_month_start": info.pre_month_start or "",
            "pre_month_end": info.pre_month_end or "",
            "pre_month_avg_volume": str(info.pre_month_avg_volume) if info.pre_month_avg_volume else "",
            "pre_month_trading_days": str(info.pre_month_trading_days) if info.pre_month_trading_days else "",
            "post_month_start": info.post_month_start or "",
            "post_month_end": info.post_month_end or "",
            "post_month_avg_volume": str(info.post_month_avg_volume) if info.post_month_avg_volume else "",
            "post_month_trading_days": str(info.post_month_trading_days) if info.post_month_trading_days else "",
            "total_avg_volume": str(info.total_avg_volume) if info.total_avg_volume else "",
            "total_trading_days": str(info.total_trading_days) if info.total_trading_days else ""
        }
        
        client.hset(hash_key, mapping=info_dict)
        return True
    except Exception as e:
        logger.error(f"保存历史最低价成交量信息到Redis失败: {e}")
        return False


def get_lowest_price_volume_from_redis(ts_code: str) -> Optional[LowestPriceVolumeInfo]:
    """
    从Redis获取历史最低价成交量信息
    """
    try:
        import redis
        client = redis.Redis(
            host=REDIS_CONFIG["host"],
            port=REDIS_CONFIG["port"],
            db=REDIS_CONFIG.get("db", 0),
            password=REDIS_CONFIG.get("password"),
            decode_responses=True
        )
        
        hash_key = f"{VOLUME_INFO_HASH_PREFIX}lowest:{ts_code}"
        data = client.hgetall(hash_key)
        
        if not data:
            return None
        
        return LowestPriceVolumeInfo(
            ts_code=ts_code,
            lowest_price=float(data['lowest_price']) if data.get('lowest_price') else None,
            lowest_price_date=data.get('lowest_price_date') or None,
            pre_month_start=data.get('pre_month_start') or None,
            pre_month_end=data.get('pre_month_end') or None,
            pre_month_avg_volume=float(data['pre_month_avg_volume']) if data.get('pre_month_avg_volume') else None,
            pre_month_trading_days=int(data['pre_month_trading_days']) if data.get('pre_month_trading_days') else None,
            post_month_start=data.get('post_month_start') or None,
            post_month_end=data.get('post_month_end') or None,
            post_month_avg_volume=float(data['post_month_avg_volume']) if data.get('post_month_avg_volume') else None,
            post_month_trading_days=int(data['post_month_trading_days']) if data.get('post_month_trading_days') else None,
            total_avg_volume=float(data['total_avg_volume']) if data.get('total_avg_volume') else None,
            total_trading_days=int(data['total_trading_days']) if data.get('total_trading_days') else None
        )
    except Exception as e:
        logger.error(f"从Redis获取历史最低价成交量信息失败: {e}")
        return None


def save_limit_up_volume_to_redis(info: LimitUpVolumeInfo) -> bool:
    """
    将涨停后成交量信息保存到Redis
    """
    try:
        import redis
        client = redis.Redis(
            host=REDIS_CONFIG["host"],
            port=REDIS_CONFIG["port"],
            db=REDIS_CONFIG.get("db", 0),
            password=REDIS_CONFIG.get("password"),
            decode_responses=True
        )
        
        hash_key = f"{VOLUME_INFO_HASH_PREFIX}limit_up:{info.ts_code}"
        info_dict = {
            "ts_code": info.ts_code,
            "limit_up_date": info.limit_up_date or "",
            "limit_up_price": str(info.limit_up_price) if info.limit_up_price else "",
            "limit_up_volume": str(info.limit_up_volume) if info.limit_up_volume else "",
            "days_since_limit_up": str(info.days_since_limit_up) if info.days_since_limit_up else "",
            "cumulative_volume": str(info.cumulative_volume) if info.cumulative_volume else "",
            "post_limit_avg_volume": str(info.post_limit_avg_volume) if info.post_limit_avg_volume else "",
            "volume_ratio": str(info.volume_ratio) if info.volume_ratio else ""
        }
        
        client.hset(hash_key, mapping=info_dict)
        return True
    except Exception as e:
        logger.error(f"保存涨停后成交量信息到Redis失败: {e}")
        return False


def get_limit_up_volume_from_redis(ts_code: str) -> Optional[LimitUpVolumeInfo]:
    """
    从Redis获取涨停后成交量信息
    """
    try:
        import redis
        client = redis.Redis(
            host=REDIS_CONFIG["host"],
            port=REDIS_CONFIG["port"],
            db=REDIS_CONFIG.get("db", 0),
            password=REDIS_CONFIG.get("password"),
            decode_responses=True
        )
        
        hash_key = f"{VOLUME_INFO_HASH_PREFIX}limit_up:{ts_code}"
        data = client.hgetall(hash_key)
        
        if not data:
            return None
        
        return LimitUpVolumeInfo(
            ts_code=ts_code,
            limit_up_date=data.get('limit_up_date') or None,
            limit_up_price=float(data['limit_up_price']) if data.get('limit_up_price') else None,
            limit_up_volume=float(data['limit_up_volume']) if data.get('limit_up_volume') else None,
            days_since_limit_up=int(data['days_since_limit_up']) if data.get('days_since_limit_up') else None,
            cumulative_volume=float(data['cumulative_volume']) if data.get('cumulative_volume') else None,
            post_limit_avg_volume=float(data['post_limit_avg_volume']) if data.get('post_limit_avg_volume') else None,
            volume_ratio=float(data['volume_ratio']) if data.get('volume_ratio') else None
        )
    except Exception as e:
        logger.error(f"从Redis获取涨停后成交量信息失败: {e}")
        return None


# ============== 对外API ==============

def get_stock_lowest_price_volume(ts_code: str, use_cache: bool = True) -> LowestPriceVolumeInfo:
    """
    获取个股的历史最低价成交量信息
    
    Args:
        ts_code: 股票代码
        use_cache: 是否使用缓存
    
    Returns:
        LowestPriceVolumeInfo对象
    """
    # 尝试从缓存获取
    if use_cache:
        cached = get_lowest_price_volume_from_redis(ts_code)
        if cached:
            return cached
    
    # 计算
    info = calculate_lowest_price_volume(ts_code)
    if info and use_cache:
        save_lowest_price_volume_to_redis(info)
    return info


def get_stock_limit_up_volume(ts_code: str, use_cache: bool = True) -> LimitUpVolumeInfo:
    """
    获取个股的涨停后成交量信息
    
    Args:
        ts_code: 股票代码
        use_cache: 是否使用缓存
    
    Returns:
        LimitUpVolumeInfo对象
    """
    # 尝试从缓存获取
    if use_cache:
        cached = get_limit_up_volume_from_redis(ts_code)
        if cached:
            return cached
    
    # 计算
    info = calculate_limit_up_volume(ts_code)
    if info and use_cache:
        save_limit_up_volume_to_redis(info)
    return info


# ============== 测试 ==============

if __name__ == "__main__":
    # 测试功能1：历史最低价成交量
    print("=" * 50)
    print("测试功能1：历史最低价成交量")
    print("=" * 50)
    
    test_code = "000001.SZ"
    info1 = get_stock_lowest_price_volume(test_code, use_cache=False)
    
    print(f"\n股票 {info1.ts_code}:")
    print(f"  历史最低价: {info1.lowest_price}")
    print(f"  历史最低价日期: {info1.lowest_price_date}")
    print(f"  前一个月: {info1.pre_month_start} ~ {info1.pre_month_end}")
    print(f"    日均成交量: {info1.pre_month_avg_volume:,.0f}" if info1.pre_month_avg_volume else "    日均成交量: N/A")
    print(f"    交易天数: {info1.pre_month_trading_days}")
    print(f"  后一个月: {info1.post_month_start} ~ {info1.post_month_end}")
    print(f"    日均成交量: {info1.post_month_avg_volume:,.0f}" if info1.post_month_avg_volume else "    日均成交量: N/A")
    print(f"    交易天数: {info1.post_month_trading_days}")
    print(f"  两个月日均成交量: {info1.total_avg_volume:,.0f}" if info1.total_avg_volume else "  两个月日均成交量: N/A")
    print(f"  两个月总交易天数: {info1.total_trading_days}")
    
    # 保存到Redis
    save_lowest_price_volume_to_redis(info1)
    print("\n已保存到Redis")
    
    # 测试功能2：涨停后成交量
    print("\n" + "=" * 50)
    print("测试功能2：涨停后成交量")
    print("=" * 50)
    
    info2 = get_stock_limit_up_volume(test_code, use_cache=False)
    
    print(f"\n股票 {info2.ts_code}:")
    print(f"  最近涨停日期: {info2.limit_up_date}")
    print(f"  涨停价格: {info2.limit_up_price}")
    print(f"  涨停当日成交量: {info2.limit_up_volume:,.0f}" if info2.limit_up_volume else "  涨停当日成交量: N/A")
    print(f"  距今天数: {info2.days_since_limit_up}")
    print(f"  涨停后累计成交量: {info2.cumulative_volume:,.0f}" if info2.cumulative_volume else "  涨停后累计成交量: N/A")
    print(f"  涨停后日均成交量: {info2.post_limit_avg_volume:,.0f}" if info2.post_limit_avg_volume else "  涨停后日均成交量: N/A")
    print(f"  成交量比值: {info2.volume_ratio}" if info2.volume_ratio else "  成交量比值: N/A")
    
    # 保存到Redis
    save_limit_up_volume_to_redis(info2)
    print("\n已保存到Redis")
