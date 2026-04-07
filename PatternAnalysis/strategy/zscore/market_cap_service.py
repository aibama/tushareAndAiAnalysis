"""
市值计算服务

提供股票市值计算和缓存功能，供 Z-Score、ATR 等模块使用。

计算逻辑: 市值 = pre_close × total_shares
- pre_close: 来自 stocktradetodayinfo 表（最近交易日收盘价）
- total_shares: 来自 stock_trade_info 表（总股本）
"""
import logging
from typing import List, Dict, Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PatternAnalysis.config import REDIS_CONFIG
from PatternAnalysis.data_access import get_engine

logger = logging.getLogger(__name__)


# ============== 配置常量 ==============

# Redis缓存键前缀
MARKET_CAP_CACHE_PREFIX = f"{REDIS_CONFIG.get('key_prefix', 'stock_rank:')}market_cap:"
MARKET_CAP_CACHE_TTL = 3600 * 4  # 4小时缓存


# ============== Redis客户端 ==============

def _get_redis_client():
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


# ============== 缓存操作 ==============

def get_cached_market_cap(ts_code: str) -> Optional[float]:
    """
    从Redis缓存获取股票市值

    Args:
        ts_code: 股票代码

    Returns:
        缓存的市值，如果没有缓存返回None
    """
    client = _get_redis_client()
    if client is None:
        return None

    try:
        cache_key = f"{MARKET_CAP_CACHE_PREFIX}{ts_code}"
        cached = client.get(cache_key)
        if cached:
            return float(cached)
    except Exception as e:
        logger.warning(f"获取市值缓存失败: {e}")

    return None


def set_cached_market_cap(ts_code: str, market_cap: float) -> bool:
    """
    将股票市值存入Redis缓存

    Args:
        ts_code: 股票代码
        market_cap: 市值

    Returns:
        是否缓存成功
    """
    client = _get_redis_client()
    if client is None:
        return False

    try:
        cache_key = f"{MARKET_CAP_CACHE_PREFIX}{ts_code}"
        client.setex(cache_key, MARKET_CAP_CACHE_TTL, str(market_cap))
        return True
    except Exception as e:
        logger.warning(f"设置市值缓存失败: {e}")
        return False


# ============== 市值计算 ==============

def calculate_stock_market_cap(ts_code: str) -> Optional[float]:
    """
    计算股票总市值（带缓存）

    市值 = pre_close * total_shares
    - pre_close: 最近一个交易日的收盘价（来自stocktradetodayinfo表）
    - total_shares: 总股本（来自stock_trade_info表）

    Args:
        ts_code: 股票代码

    Returns:
        总市值（元），如果计算失败返回None
    """
    # 先尝试从缓存获取
    cached_cap = get_cached_market_cap(ts_code)
    if cached_cap is not None:
        return cached_cap

    # 缓存未命中，从数据库计算
    engine = get_engine()
    if engine is None:
        return None

    try:
        from sqlalchemy import text

        # 获取最近一个交易日的pre_close
        sql_price = """
            SELECT pre_close
            FROM stocktradetodayinfo
            WHERE ts_code = :ts_code
            ORDER BY trade_date DESC
            LIMIT 1
        """

        # 获取总股本
        sql_shares = """
            SELECT total_shares
            FROM stock_trade_info
            WHERE stock_code = :ts_code
            LIMIT 1
        """

        with engine.connect() as conn:
            # 获取收盘价
            df_price = pd.read_sql(text(sql_price), conn, params={"ts_code": ts_code})
            if df_price.empty or df_price['pre_close'].iloc[0] is None:
                logger.warning(f"股票 {ts_code} 无收盘价数据")
                return None

            pre_close = float(df_price['pre_close'].iloc[0])

            # 获取总股本
            df_shares = pd.read_sql(text(sql_shares), conn, params={"ts_code": ts_code})
            if df_shares.empty or df_shares['total_shares'].iloc[0] is None:
                logger.warning(f"股票 {ts_code} 无总股本数据")
                return None

            total_shares = float(df_shares['total_shares'].iloc[0])

            # 计算市值
            market_cap = pre_close * total_shares

            # 存入缓存
            set_cached_market_cap(ts_code, market_cap)

            return market_cap

    except Exception as e:
        logger.error(f"计算股票 {ts_code} 市值失败: {e}")
        return None


def calculate_stocks_market_cap_by_codes(ts_codes: List[str]) -> Dict[str, float]:
    """
    批量计算股票市值（带缓存优化 + 多线程并行）

    优化策略：
    1. 先从Redis缓存获取
    2. 对于缓存未命中的股票，使用多线程并行查询数据库
    3. 将新查询的结果存入缓存

    Args:
        ts_codes: 股票代码列表

    Returns:
        字典，键为股票代码，值为市值
    """
    if not ts_codes:
        return {}

    result = {}
    uncached_codes = []

    # 1. 先从缓存获取
    client = _get_redis_client()
    if client:
        try:
            cache_keys = [f"{MARKET_CAP_CACHE_PREFIX}{code}" for code in ts_codes]
            cached_values = client.mget(cache_keys)

            for i, ts_code in enumerate(ts_codes):
                if cached_values[i] is not None:
                    result[ts_code] = float(cached_values[i])
                else:
                    uncached_codes.append(ts_code)
        except Exception as e:
            logger.warning(f"批量获取市值缓存失败: {e}")
            uncached_codes = list(ts_codes)
    else:
        uncached_codes = list(ts_codes)

    # 2. 如果有未缓存的股票，使用多线程并行查询
    if uncached_codes:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        BATCH_SIZE = 200
        MAX_WORKERS = 10

        def process_batch(batch_codes: List[str]) -> Dict[str, float]:
            """处理一批股票的市值计算"""
            batch_result = {}
            engine = get_engine()
            if engine is None:
                return batch_result

            try:
                from sqlalchemy import text

                placeholders = ','.join([f"'{code}'" for code in batch_codes])

                sql_price = f"""
                    SELECT t.ts_code, t.pre_close
                    FROM stocktradetodayinfo t
                    INNER JOIN (
                        SELECT ts_code, MAX(trade_date) as max_date
                        FROM stocktradetodayinfo
                        WHERE ts_code IN ({placeholders})
                        GROUP BY ts_code
                    ) latest ON t.ts_code = latest.ts_code AND t.trade_date = latest.max_date
                """

                sql_shares = f"""
                    SELECT stock_code as ts_code, total_shares
                    FROM stock_trade_info
                    WHERE stock_code IN ({placeholders})
                """

                with engine.connect() as conn:
                    df_price = pd.read_sql(text(sql_price), conn)
                    df_shares = pd.read_sql(text(sql_shares), conn)

                if not df_price.empty and not df_shares.empty:
                    df_price = df_price.set_index('ts_code')
                    df_shares = df_shares.set_index('ts_code')

                    for ts_code in batch_codes:
                        if ts_code in df_price.index and ts_code in df_shares.index:
                            pre_close = df_price.loc[ts_code, 'pre_close']
                            total_shares = df_shares.loc[ts_code, 'total_shares']
                            if pd.notna(pre_close) and pd.notna(total_shares):
                                batch_result[ts_code] = float(pre_close) * float(total_shares)

            except Exception as e:
                logger.error(f"批量计算股票市值失败: {e}")

            return batch_result

        # 分批处理
        batches = [uncached_codes[i:i+BATCH_SIZE] for i in range(0, len(uncached_codes), BATCH_SIZE)]

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_batch, batch): batch for batch in batches}

            for future in as_completed(futures):
                try:
                    batch_result = future.result()
                    result.update(batch_result)

                    # 批量存入缓存
                    if client:
                        pipe = client.pipeline()
                        for ts_code, cap in batch_result.items():
                            cache_key = f"{MARKET_CAP_CACHE_PREFIX}{ts_code}"
                            pipe.setex(cache_key, MARKET_CAP_CACHE_TTL, str(cap))
                        pipe.execute()
                except Exception as e:
                    logger.error(f"批量存入缓存失败: {e}")

    return result


def preheat_market_cap_cache(ts_codes: List[str], batch_size: int = 500) -> int:
    """
    预热市值缓存

    Args:
        ts_codes: 股票代码列表
        batch_size: 每批处理数量

    Returns:
        预热成功的股票数量
    """
    if not ts_codes:
        return 0

    logger.info(f"开始预热市值缓存，股票数量: {len(ts_codes)}")

    result = calculate_stocks_market_cap_by_codes(ts_codes)

    success_count = len(result)
    logger.info(f"市值缓存预热完成，成功: {success_count}/{len(ts_codes)}")

    return success_count


# ============== 导入pandas ==============

import pandas as pd


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)

    # 测试单只股票
    print("=== 测试单只股票市值 ===")
    cap = calculate_stock_market_cap("000001.SZ")
    print(f"000001.SZ 市值: {cap}")

    # 测试批量
    print("\n=== 测试批量市值 ===")
    codes = ["000001.SZ", "000002.SZ", "600000.SH"]
    caps = calculate_stocks_market_cap_by_codes(codes)
    print(f"批量结果: {caps}")

    # 测试缓存
    print("\n=== 测试缓存 ===")
    cached = get_cached_market_cap("000001.SZ")
    print(f"缓存结果: {cached}")
