"""
涨停跌停主题分析服务
计算个股的涨停/跌停信息，并通过Redis Stream进行存储

核心概念：
- STOCK_MAX_LASTEST_PRICE (SMLP): 最近一次涨停的价格
- SM_PRE: 最近收盘价与SMLP的比值 = 最近收盘价 / SMLP
- 跌停逻辑类似
"""
import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import math

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

# 导入配置 - PatternAnalysis的父目录是easymoneycrawling，再往上是pythonCode
import sys
import os
# 项目根目录是 easymoneycrawling 的父目录 pythonCode
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PatternAnalysis.config import DB_CONFIG, REDIS_CONFIG

logger = logging.getLogger(__name__)

# ============== Redis配置 ==============
# Redis Stream主题名称
LIMIT_UP_STREAM = f"{REDIS_CONFIG.get('key_prefix', 'stock_rank:')}limit_up_stream"
LIMIT_DOWN_STREAM = f"{REDIS_CONFIG.get('key_prefix', 'stock_rank:')}limit_down_stream"

# Redis Hash键前缀
LIMIT_INFO_HASH_PREFIX = f"{REDIS_CONFIG.get('key_prefix', 'stock_rank:')}limit_info:"

# 涨停/跌停索引键
LIMIT_UP_INDEX_KEY = f"{REDIS_CONFIG.get('key_prefix', 'stock_rank:')}limit_up_index"
LIMIT_DOWN_INDEX_KEY = f"{REDIS_CONFIG.get('key_prefix', 'stock_rank:')}limit_down_index"


# ============== 数据模型 ==============

@dataclass
class LimitPriceInfo:
    """涨停/跌停信息"""
    ts_code: str
    # 涨停信息
    limit_up_date: Optional[str] = None  # 最近涨停日期
    limit_up_price: Optional[float] = None  # 涨停价格 (SMLP)
    # 跌停信息
    limit_down_date: Optional[str] = None  # 最近跌停日期
    limit_down_price: Optional[float] = None  # 跌停价格
    # 收盘价信息
    latest_close: Optional[float] = None  # 最近收盘价
    # 比率
    sm_pre_up: Optional[float] = None  # 收盘价/涨停价比 (SM_PRE_UP)
    sm_pre_down: Optional[float] = None  # 收盘价/跌停价比 (SM_PRE_DOWN)


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


def get_redis_client():
    """获取Redis客户端"""
    try:
        import redis
        return redis.Redis(
            host=REDIS_CONFIG["host"],
            port=REDIS_CONFIG["port"],
            db=REDIS_CONFIG.get("db", 0),
            password=REDIS_CONFIG.get("password"),
            decode_responses=True
        )
    except Exception as e:
        logger.error(f"Redis连接失败: {e}")
        return None


# ============== Redis Stream支持检查 ==============

def get_redis_version(client) -> Optional[str]:
    """获取Redis服务器版本"""
    try:
        info = client.info()
        return info.get('redis_version')
    except:
        return None


def is_redis_stream_supported(client) -> bool:
    """检查Redis是否支持Stream（Redis 5.0+）"""
    version = get_redis_version(client)
    if version:
        try:
            major = int(version.split('.')[0])
            return major >= 5
        except:
            return False
    return False


# ============== 涨停跌停计算 ==============

def is_limit_up(pre_close: float, close: float, pct_chg: float = None) -> bool:
    """
    判断是否涨停
    A股涨跌停规则：
    - 普通股票：涨跌幅限制为10%
    - ST股票：涨跌幅限制为5%
    - 科创板/创业板：涨跌幅限制为20%
    """
    if pre_close is None or close is None:
        return False

    if pct_chg is not None:
        # 如果有涨跌幅数据，直接判断
        return pct_chg >= 9.9  # 约等于涨停

    # 否则通过价格计算
    change_ratio = (close - pre_close) / pre_close
    return change_ratio >= 0.099  # 约10%


def is_limit_down(pre_close: float, close: float, pct_chg: float = None) -> bool:
    """
    判断是否跌停
    """
    if pre_close is None or close is None:
        return False

    if pct_chg is not None:
        return pct_chg <= -9.9

    change_ratio = (close - pre_close) / pre_close
    return change_ratio <= -0.099


def calculate_limit_for_stock(ts_code: str, engine) -> Optional[LimitPriceInfo]:
    """
    计算单个股票的涨停/跌停信息

    返回：
        LimitPriceInfo对象，包含：
        - limit_up_date: 最近涨停日期
        - limit_up_price: 最近涨停价格 (SMLP)
        - limit_down_date: 最近跌停日期
        - limit_down_price: 最近跌停价格
        - latest_close: 最近收盘价
        - sm_pre_up: 收盘价/涨停价比 (SM_PRE)
        - sm_pre_down: 收盘价/跌停价比
    """
    try:
        # 查询股票的所有交易数据（按日期倒序）
        sql = """
            SELECT
                trade_date,
                pre_close,
                close,
                pct_chg
            FROM stocktradetodayinfo
            WHERE ts_code = :ts_code
              AND close > 0
              AND pre_close > 0
            ORDER BY trade_date DESC
            LIMIT 1000  -- 最多查询近1000个交易日
        """

        df = pd.read_sql(text(sql), engine, params={"ts_code": ts_code})

        if df.empty:
            return None

        # 转换日期格式
        df['trade_date'] = pd.to_datetime(df['trade_date'])

        # 初始化结果
        result = LimitPriceInfo(ts_code=ts_code)

        # 获取最近收盘价
        result.latest_close = float(df.iloc[0]['close']) if len(df) > 0 else None

        # 查找最近一次涨停
        for _, row in df.iterrows():
            if is_limit_up(row['pre_close'], row['close'], row['pct_chg']):
                result.limit_up_date = row['trade_date'].strftime('%Y-%m-%d')
                result.limit_up_price = float(row['close'])
                break

        # 查找最近一次跌停
        for _, row in df.iterrows():
            if is_limit_down(row['pre_close'], row['close'], row['pct_chg']):
                result.limit_down_date = row['trade_date'].strftime('%Y-%m-%d')
                result.limit_down_price = float(row['close'])
                break

        # 计算比率
        if result.limit_up_price and result.limit_up_price > 0 and result.latest_close:
            result.sm_pre_up = round(result.latest_close / result.limit_up_price, 4)

        if result.limit_down_price and result.limit_down_price > 0 and result.latest_close:
            result.sm_pre_down = round(result.latest_close / result.limit_down_price, 4)

        return result

    except Exception as e:
        logger.error(f"计算股票 {ts_code} 涨停跌停信息失败: {e}")
        return None


def calculate_limit_prices_for_all_stocks(num_threads: int = 4) -> List[LimitPriceInfo]:
    """
    多线程计算所有股票的涨停跌停信息

    Args:
        num_threads: 线程数

    Returns:
        List[LimitPriceInfo]: 所有股票的涨停跌停信息列表
    """
    logger.info(f"开始计算所有股票的涨停跌停信息，使用 {num_threads} 个线程...")

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

    # 为每个线程创建独立引擎
    def process_chunk(chunk_codes: List[str], thread_id: int) -> List[LimitPriceInfo]:
        thread_engine = get_engine()
        results = []
        try:
            for code in chunk_codes:
                info = calculate_limit_for_stock(code, thread_engine)
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

def save_limit_info_to_redis(info: LimitPriceInfo) -> bool:
    """
    将个股的涨停跌停信息保存到Redis

    使用Hash存储具体数据，使用Stream记录事件
    """
    client = get_redis_client()
    if client is None:
        logger.error("Redis客户端不可用")
        return False

    try:
        # 1. 保存到Hash
        hash_key = f"{LIMIT_INFO_HASH_PREFIX}{info.ts_code}"
        info_dict = asdict(info)

        # 处理None值，转为字符串存储
        for key, value in info_dict.items():
            if value is None:
                info_dict[key] = ""

        client.hset(hash_key, mapping=info_dict)

        # 2. 更新索引
        if info.limit_up_date:
            client.sadd(LIMIT_UP_INDEX_KEY, info.ts_code)
            # 添加到Stream（如果支持）
            if is_redis_stream_supported(client):
                stream_data = {
                    "ts_code": info.ts_code,
                    "limit_up_date": info.limit_up_date,
                    "limit_up_price": str(info.limit_up_price) if info.limit_up_price else "",
                    "latest_close": str(info.latest_close) if info.latest_close else "",
                    "sm_pre_up": str(info.sm_pre_up) if info.sm_pre_up else "",
                    "timestamp": datetime.now().isoformat()
                }
                client.xadd(LIMIT_UP_STREAM, stream_data)

        if info.limit_down_date:
            client.sadd(LIMIT_DOWN_INDEX_KEY, info.ts_code)
            if is_redis_stream_supported(client):
                stream_data = {
                    "ts_code": info.ts_code,
                    "limit_down_date": info.limit_down_date,
                    "limit_down_price": str(info.limit_down_price) if info.limit_down_price else "",
                    "latest_close": str(info.latest_close) if info.latest_close else "",
                    "sm_pre_down": str(info.sm_pre_down) if info.sm_pre_down else "",
                    "timestamp": datetime.now().isoformat()
                }
                client.xadd(LIMIT_DOWN_STREAM, stream_data)

        return True

    except Exception as e:
        logger.error(f"保存涨停跌停信息到Redis失败: {e}")
        return False


def get_limit_info_from_redis(ts_code: str) -> Optional[LimitPriceInfo]:
    """
    从Redis获取个股的涨停跌停信息
    """
    client = get_redis_client()
    if client is None:
        return None

    try:
        hash_key = f"{LIMIT_INFO_HASH_PREFIX}{ts_code}"
        data = client.hgetall(hash_key)

        if not data:
            return None

        # 构建LimitPriceInfo对象
        info = LimitPriceInfo(
            ts_code=ts_code,
            limit_up_date=data.get('limit_up_date') or None,
            limit_up_price=float(data['limit_up_price']) if data.get('limit_up_price') else None,
            limit_down_date=data.get('limit_down_date') or None,
            limit_down_price=float(data['limit_down_price']) if data.get('limit_down_price') else None,
            latest_close=float(data['latest_close']) if data.get('latest_close') else None,
            sm_pre_up=float(data['sm_pre_up']) if data.get('sm_pre_up') else None,
            sm_pre_down=float(data['sm_pre_down']) if data.get('sm_pre_down') else None
        )

        return info

    except Exception as e:
        logger.error(f"从Redis获取涨停跌停信息失败: {e}")
        return None


def get_all_limit_stock_codes(limit_type: str = "up") -> List[str]:
    """
    获取所有有涨停/跌停记录的股票代码

    Args:
        limit_type: "up" 表示涨停，"down" 表示跌停

    Returns:
        股票代码列表
    """
    client = get_redis_client()
    if client is None:
        return []

    try:
        index_key = LIMIT_UP_INDEX_KEY if limit_type == "up" else LIMIT_DOWN_INDEX_KEY
        return list(client.smembers(index_key))
    except Exception as e:
        logger.error(f"获取{limit_type}股票代码列表失败: {e}")
        return []


def get_stock_limit_info(ts_code: str, use_cache: bool = True) -> Optional[LimitPriceInfo]:
    """
    获取个股的涨停跌停信息

    优先从Redis获取，如果不存在则计算

    Args:
        ts_code: 股票代码
        use_cache: 是否使用缓存

    Returns:
        LimitPriceInfo对象
    """
    # 尝试从缓存获取
    if use_cache:
        cached = get_limit_info_from_redis(ts_code)
        if cached:
            return cached

    # 计算
    engine = get_engine()
    try:
        info = calculate_limit_for_stock(ts_code, engine)
        if info and use_cache:
            save_limit_info_to_redis(info)
        return info
    finally:
        engine.dispose()


# ============== 测试 ==============

if __name__ == "__main__":
    # 测试计算
    print("测试计算股票涨停跌停信息...")

    # 测试单只股票
    test_code = "000001.SZ"
    info = get_stock_limit_info(test_code, use_cache=False)
    if info:
        print(f"\n股票 {info.ts_code}:")
        print(f"  最近涨停日期: {info.limit_up_date}")
        print(f"  涨停价格(SMLP): {info.limit_up_price}")
        print(f"  最近跌停日期: {info.limit_down_date}")
        print(f"  跌停价格: {info.limit_down_price}")
        print(f"  最近收盘价: {info.latest_close}")
        print(f"  收盘/涨停价比(SM_PRE_UP): {info.sm_pre_up}")
        print(f"  收盘/跌停价比(SM_PRE_DOWN): {info.sm_pre_down}")

        # 保存到Redis
        save_limit_info_to_redis(info)
        print("\n已保存到Redis")

        # 从Redis读取
        cached = get_limit_info_from_redis(test_code)
        if cached:
            print("从Redis读取成功")
    else:
        print(f"未找到股票 {test_code} 的数据")
