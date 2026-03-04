"""
ATR稳定期检测服务

基于ATR（平均真实波幅）的自适应阈值算法，识别个股的中低波动稳定期，
并提供Redis存储和API查询功能。
"""
import logging
import json
from typing import List, Dict, Optional, Tuple
from datetime import date, datetime, timedelta
from dataclasses import dataclass, asdict
import pandas as pd
import numpy as np

from PatternAnalysis.config import REDIS_CONFIG, DB_CONFIG
from PatternAnalysis.data_access import get_engine
from PatternAnalysis.strategy.ATR.adaptive_threshold import (
    detect_stable_periods_adaptive,
    StablePeriod,
    analyze_stable_periods
)

logger = logging.getLogger(__name__)


# ============== 配置常量 ==============

# Redis Stream主题名称
STABLE_PERIOD_STREAM = f"{REDIS_CONFIG.get('key_prefix', 'stock_rank:')}atr_stable_period_stream"

# Redis Hash键前缀
STABLE_PERIOD_HASH_PREFIX = f"{REDIS_CONFIG.get('key_prefix', 'stock_rank:')}atr_stable_period:"

# 稳定期数据Hash键
STABLE_PERIOD_DATA_KEY = f"{REDIS_CONFIG.get('key_prefix', 'stock_rank:')}atr_stable_period_data"


# ============== Redis客户端 ==============

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


# ============== 市值计算相关 ==============

# Redis缓存键前缀
MARKET_CAP_CACHE_PREFIX = f"{REDIS_CONFIG.get('key_prefix', 'stock_rank:')}market_cap:"
MARKET_CAP_CACHE_TTL = 3600 * 4  # 4小时缓存


def _get_redis_client():
    """获取Redis客户端（用于市值缓存）"""
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
        # 使用线程池并行处理
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # 每批处理的股票数量
        BATCH_SIZE = 200
        # 并行线程数
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

                # 优化SQL：使用更简单的方式获取最新收盘价
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

        # 将未缓存的股票分成多批
        batches = [uncached_codes[i:i+BATCH_SIZE] for i in range(0, len(uncached_codes), BATCH_SIZE)]

        logger.info(f"开始并行计算市值，共 {len(uncached_codes)} 只股票，分 {len(batches)} 批，{MAX_WORKERS} 线程")

        # 使用线程池并行处理
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_batch, batch): batch for batch in batches}

            for future in as_completed(futures):
                try:
                    batch_result = future.result()
                    result.update(batch_result)

                    # 存入缓存
                    if client:
                        try:
                            pipe = client.pipeline()
                            for ts_code, market_cap in batch_result.items():
                                pipe.setex(
                                    f"{MARKET_CAP_CACHE_PREFIX}{ts_code}",
                                    MARKET_CAP_CACHE_TTL,
                                    str(market_cap)
                                )
                            pipe.execute()
                        except Exception as e:
                            logger.warning(f"批量设置市值缓存失败: {e}")
                except Exception as e:
                    logger.error(f"处理批次失败: {e}")

    return result


# market_factor与市值范围的映射（单位：元）
MARKET_FACTOR_RANGES = {
    "0Y-100Y": (0, 100 * 1e8),          # 一百亿以下
    "100Y-200Y": (100 * 1e8, 200 * 1e8),  # 一百亿至两百亿
    "200Y-400Y": (200 * 1e8, 400 * 1e8),  # 两百亿至四百亿
    "400Y-3000000Y": (400 * 1e8, 3000000 * 1e8),  # 四百亿以上
}


def preheat_market_cap_cache(ts_codes: List[str] = None, batch_size: int = 500) -> int:
    """
    预热市值缓存（批量计算并存入Redis）

    可以在服务启动时或定时任务中调用，提前将所有股票的市值存入缓存

    Args:
        ts_codes: 股票代码列表，None表示获取所有股票
        batch_size: 每批处理的股票数量

    Returns:
        成功缓存的股票数量
    """
    from PatternAnalysis.data_access import get_all_ts_codes

    if ts_codes is None:
        ts_codes = get_all_ts_codes()

    logger.info(f"开始预热市值缓存，共 {len(ts_codes)} 只股票")

    # 批量计算并缓存
    cached_count = 0
    for i in range(0, len(ts_codes), batch_size):
        batch = ts_codes[i:i + batch_size]
        result = calculate_stocks_market_cap_by_codes(batch)
        cached_count += len(result)

        if (i + batch_size) % 1000 == 0:
            logger.info(f"市值缓存预热进度: {min(i + batch_size, len(ts_codes))}/{len(ts_codes)}")

    logger.info(f"市值缓存预热完成，共缓存 {cached_count} 只股票的市值")
    return cached_count


def filter_stocks_by_market_factor(ts_codes: List[str], market_factor: str) -> List[str]:
    """
    根据市值范围筛选股票

    Args:
        ts_codes: 股票代码列表
        market_factor: 市值因子，如 "0Y-100Y", "100Y-200Y" 等

    Returns:
        符合条件的股票代码列表
    """
    if market_factor not in MARKET_FACTOR_RANGES:
        logger.warning(f"未知的市值因子: {market_factor}")
        return ts_codes

    min_cap, max_cap = MARKET_FACTOR_RANGES[market_factor]

    # 批量计算市值（带缓存）
    market_caps = calculate_stocks_market_cap_by_codes(ts_codes)

    # 筛选符合条件的股票
    result = []
    for ts_code, cap in market_caps.items():
        if min_cap <= cap < max_cap:
            result.append(ts_code)

    logger.info(f"市值因子 {market_factor} 筛选: 原始 {len(ts_codes)} 只，筛选后 {len(result)} 只")
    return result


# ============== 数据模型 ==============

@dataclass
class StablePeriodRecord:
    """稳定期记录数据结构"""
    ts_code: str
    start_date: str
    end_date: str
    duration_days: int
    avg_atr: float
    atr_cv: float
    threshold_used: float
    stability_score: float
    detected_at: str
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_stable_period(cls, ts_code: str, period: StablePeriod) -> 'StablePeriodRecord':
        """从StablePeriod创建记录"""
        return cls(
            ts_code=ts_code,
            start_date=period.start_date.strftime('%Y-%m-%d') if hasattr(period.start_date, 'strftime') else str(period.start_date),
            end_date=period.end_date.strftime('%Y-%m-%d') if hasattr(period.end_date, 'strftime') else str(period.end_date),
            duration_days=period.duration_days,
            avg_atr=round(period.avg_atr, 4),
            atr_cv=round(period.atr_cv, 4),
            threshold_used=round(period.threshold_used, 4),
            stability_score=round(period.stability_score, 4),
            detected_at=datetime.now().isoformat()
        )


# ============== ATR数据获取 ==============

def get_atr_time_series(ts_code: str, start_date: date = None, end_date: date = None) -> pd.Series:
    """
    获取个股的历史ATR时间序列
    
    Args:
        ts_code: 股票代码（如 '000001.SZ'）
        start_date: 开始日期，默认3年前
        end_date: 结束日期，默认今天
    
    Returns:
        pd.Series: ATR时间序列，索引为交易日期
    """
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=365 * 3)  # 默认3年数据
    
    # 从数据库获取K线数据
    from PatternAnalysis.data_access import get_stock_ohlc_in_range
    
    df = get_stock_ohlc_in_range(ts_code, start_date, end_date)
    
    if df.empty or len(df) < 20:
        logger.warning(f"股票 {ts_code} 数据不足，无法计算ATR")
        return pd.Series(dtype=float)
    
    # 计算True Range (TR)
    df = df.sort_values('trade_date').reset_index(drop=True)
    
    # 计算TR: max(H-L, |H-PC|, |L-PC|)
    prev_close = df['close'].shift(1)
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - prev_close).abs()
    tr3 = (df['low'] - prev_close).abs()
    df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # 处理第一行（没有前一天收盘价）
    df.loc[df.index[0], 'tr'] = df.loc[df.index[0], 'high'] - df.loc[df.index[0], 'low']
    
    # 计算ATR (14天周期)
    atr_period = 14
    atr_values = []
    
    for i in range(len(df)):
        if i < atr_period - 1:
            atr_values.append(None)
        elif i == atr_period - 1:
            # 初始ATR = 前atr_period个TR的简单算术平均
            atr_values.append(df['tr'].iloc[:atr_period].mean())
        else:
            # ATR = [前一日ATR × 13 + 当日TR] / 14
            prev_atr = atr_values[-1]
            current_tr = df['tr'].iloc[i]
            current_atr = (prev_atr * (atr_period - 1) + current_tr) / atr_period
            atr_values.append(current_atr)
    
    df['atr'] = atr_values
    
    # 创建ATR序列（去除None值）
    atr_series = df.dropna(subset=['atr']).set_index('trade_date')['atr']
    
    return atr_series


# ============== 稳定期检测核心逻辑 ==============

def detect_stable_periods_for_stock(
    ts_code: str,
    window: int = 20,
    percentile_threshold: float = 30,
    min_stable_days: int = 5,
    lookback_period: int = 241,
    default_threshold: float = 0.03,
    start_date: date = None,
    end_date: date = None
) -> Tuple[List[StablePeriodRecord], Dict]:
    """
    检测个股的中低波动稳定期
    
    Args:
        ts_code: 股票代码
        window: CV计算窗口
        percentile_threshold: 百分位阈值
        min_stable_days: 最少稳定天数
        lookback_period: 回溯期
        default_threshold: 默认阈值
        start_date: 数据开始日期
        end_date: 数据结束日期
    
    Returns:
        Tuple[稳定期记录列表, 详细信息字典]
    """
    # 获取ATR时间序列
    atr_series = get_atr_time_series(ts_code, start_date, end_date)
    
    if atr_series.empty or len(atr_series) < window + lookback_period:
        logger.warning(f"股票 {ts_code} 数据不足，无法检测稳定期")
        return [], {
            "status": "insufficient_data",
            "ts_code": ts_code,
            "data_points": len(atr_series) if not atr_series.empty else 0,
            "required": window + lookback_period
        }
    
    # 使用自适应阈值算法检测稳定期
    stable_periods, threshold_series = detect_stable_periods_adaptive(
        atr_series=atr_series,
        window=window,
        percentile_threshold=percentile_threshold,
        min_stable_days=min_stable_days,
        lookback_period=lookback_period,
        default_threshold=default_threshold
    )
    
    # 转换为记录格式
    records = [StablePeriodRecord.from_stable_period(ts_code, p) for p in stable_periods]
    
    # 生成汇总信息
    summary = {
        "status": "success",
        "ts_code": ts_code,
        "total_data_points": len(atr_series),
        "num_stable_periods": len(records),
        "total_stable_days": sum(r.duration_days for r in records),
        "parameters": {
            "window": window,
            "percentile_threshold": percentile_threshold,
            "min_stable_days": min_stable_days,
            "lookback_period": lookback_period,
            "default_threshold": default_threshold
        },
        "atr_range": {
            "min": round(atr_series.min(), 4),
            "max": round(atr_series.max(), 4),
            "mean": round(atr_series.mean(), 4)
        }
    }
    
    return records, summary


# ============== Redis存储 ==============

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
            pass
    return False


def save_stable_periods_to_redis(
    ts_code: str,
    records: List[StablePeriodRecord],
    summary: Dict
) -> bool:
    """
    将稳定期数据保存到Redis
    
    支持两种模式：
    - Redis 5.0+: 使用Stream进行事件追踪
    - Redis < 5.0: 使用List模拟Stream
    
    Args:
        ts_code: 股票代码
        records: 稳定期记录列表
        summary: 汇总信息
    
    Returns:
        bool: 是否保存成功
    """
    client = get_redis_client()
    if client is None:
        logger.error("Redis客户端不可用")
        return False
    
    try:
        # 检查Redis版本
        stream_supported = is_redis_stream_supported(client)
        
        # 1. 保存到Hash结构（存储每个股票的稳定期数据）- 两种版本都支持
        hash_key = f"{STABLE_PERIOD_HASH_PREFIX}{ts_code}"
        
        # 将记录转换为JSON
        data = {
            "records": [r.to_dict() for r in records],
            "summary": summary,
            "updated_at": datetime.now().isoformat()
        }
        
        client.hset(hash_key, "data", json.dumps(data, ensure_ascii=False))
        client.hset(hash_key, "updated_at", datetime.now().isoformat())
        
        # 2. 事件追踪 - 根据Redis版本选择不同方式
        stream_data = {
            "ts_code": ts_code,
            "num_periods": len(records),
            "total_stable_days": sum(r.duration_days for r in records),
            "updated_at": datetime.now().isoformat()
        }
        
        if stream_supported:
            # Redis 5.0+: 使用Stream
            try:
                client.xadd(STABLE_PERIOD_STREAM, stream_data)
            except Exception as e:
                logger.warning(f"Stream添加失败，回退到List: {e}")
                # 回退到List
                list_key = f"{STABLE_PERIOD_STREAM}_list"
                client.lpush(list_key, json.dumps(stream_data, ensure_ascii=False))
                # 限制列表长度，保留最近1000条
                client.ltrim(list_key, 0, 999)
        else:
            # Redis < 5.0: 使用List模拟
            list_key = f"{STABLE_PERIOD_STREAM}_list"
            client.lpush(list_key, json.dumps(stream_data, ensure_ascii=False))
            # 限制列表长度，保留最近1000条
            client.ltrim(list_key, 0, 999)
        
        # 3. 更新股票索引（记录哪些股票有稳定期数据）
        client.sadd(f"{STABLE_PERIOD_HASH_PREFIX}index", ts_code)
        
        logger.info(f"股票 {ts_code} 稳定期数据已保存到Redis，共 {len(records)} 个稳定期 (Stream支持: {stream_supported})")
        return True
        
    except Exception as e:
        logger.error(f"保存稳定期数据到Redis失败: {e}")
        return False


def get_stable_periods_from_redis(ts_code: str) -> Optional[Dict]:
    """
    从Redis获取个股的稳定期数据
    
    Args:
        ts_code: 股票代码
    
    Returns:
        稳定期数据字典，如果不存在则返回None
    """
    client = get_redis_client()
    if client is None:
        return None
    
    try:
        hash_key = f"{STABLE_PERIOD_HASH_PREFIX}{ts_code}"
        
        # 检查key是否存在以及其类型
        key_type = client.type(hash_key)
        
        if key_type == 'none':
            # key不存在
            return None
        elif key_type == 'hash':
            # 正常情况：key是Hash类型
            data_str = client.hget(hash_key, "data")
            if data_str:
                return json.loads(data_str)
            return None
        else:
            # key类型不正确
            logger.warning(f"Redis key {hash_key} 类型错误 (当前类型: {key_type})，尝试修复...")
            # 删除错误的key
            client.delete(hash_key)
            logger.info(f"已删除错误的Redis key {hash_key}")
            return None
        
    except Exception as e:
        logger.error(f"从Redis获取稳定期数据失败: {e}")
        return None


def get_all_stocks_with_stable_periods() -> List[str]:
    """获取所有有稳定期数据的股票代码"""
    client = get_redis_client()
    if client is None:
        return []
    
    try:
        index_key = f"{STABLE_PERIOD_HASH_PREFIX}index"
        
        # 检查key是否存在以及其类型
        key_type = client.type(index_key)
        
        if key_type == 'none':
            # key不存在，返回空列表
            logger.warning(f"Redis key {index_key} 不存在，需要先运行稳定期计算任务")
            return []
        elif key_type == 'set':
            # 正常情况：key是Set类型
            return list(client.smembers(index_key))
        else:
            # key类型不正确，尝试修复
            logger.warning(f"Redis key {index_key} 类型错误 (当前类型: {key_type})，尝试修复...")
            
            # 获取当前值
            current_value = client.get(index_key)
            if current_value:
                # 如果是字符串类型，可能之前存储了错误的数据
                logger.error(f"Redis key {index_key} 存储了错误的数据: {current_value[:100]}...")
            
            # 删除错误的key
            client.delete(index_key)
            logger.info(f"已删除错误的Redis key {index_key}，请重新运行稳定期计算任务")
            return []
            
    except Exception as e:
        logger.error(f"获取股票索引失败: {e}")
        return []


# ============== 批量处理 ==============

def detect_and_save_all_stocks(
    window: int = 20,
    percentile_threshold: float = 30,
    min_stable_days: int = 5,
    lookback_period: int = 241,
    batch_size: int = 50
) -> Dict:
    """
    批量检测并保存所有股票的稳定期
    
    Args:
        window: CV计算窗口
        percentile_threshold: 百分位阈值
        min_stable_days: 最少稳定天数
        lookback_period: 回溯期
        batch_size: 每批处理的股票数量
    
    Returns:
        处理结果汇总
    """
    from PatternAnalysis.data_access import get_all_ts_codes
    
    ts_codes = get_all_ts_codes()
    logger.info(f"开始批量检测稳定期，共 {len(ts_codes)} 只股票")
    
    success_count = 0
    fail_count = 0
    total_periods = 0
    errors = []
    
    for i, ts_code in enumerate(ts_codes):
        try:
            records, summary = detect_stable_periods_for_stock(
                ts_code=ts_code,
                window=window,
                percentile_threshold=percentile_threshold,
                min_stable_days=min_stable_days,
                lookback_period=lookback_period
            )
            
            if summary["status"] == "success" and records:
                save_stable_periods_to_redis(ts_code, records, summary)
                success_count += 1
                total_periods += len(records)
            else:
                fail_count += 1
                
        except Exception as e:
            logger.error(f"处理股票 {ts_code} 失败: {e}")
            fail_count += 1
            errors.append({"ts_code": ts_code, "error": str(e)})
        
        # 定期打印进度
        if (i + 1) % batch_size == 0:
            logger.info(f"进度: {i + 1}/{len(ts_codes)}, 成功: {success_count}, 失败: {fail_count}")
    
    result = {
        "status": "completed",
        "total_stocks": len(ts_codes),
        "success_count": success_count,
        "fail_count": fail_count,
        "total_periods": total_periods,
        "errors": errors[:10]  # 最多返回10个错误
    }
    
    logger.info(f"批量检测完成: {result}")
    return result


# ============== API数据转换 ==============

def format_stable_periods_for_api(records: List[StablePeriodRecord]) -> List[Dict]:
    """
    格式化稳定期数据用于API响应
    
    Returns:
        [
            {
                "start_date": "2024-01-15",
                "end_date": "2024-02-10",
                "duration_days": 26,
                "avg_atr": 1.85,
                "atr_cv": 0.045,
                "stability_score": 0.955
            },
            ...
        ]
    """
    return [
        {
            "start_date": r.start_date,
            "end_date": r.end_date,
            "duration_days": r.duration_days,
            "avg_atr": r.avg_atr,
            "atr_cv": r.atr_cv,
            "stability_score": r.stability_score
        }
        for r in records
    ]


# ============== 主函数 ==============

if __name__ == "__main__":
    # 测试用
    test_ts_code = "000001.SZ"
    print(f"检测股票 {test_ts_code} 的稳定期...")
    
    records, summary = detect_stable_periods_for_stock(test_ts_code)
    
    print(f"状态: {summary['status']}")
    print(f"稳定期数量: {len(records)}")
    
    if records:
        save_stable_periods_to_redis(test_ts_code, records, summary)
        print("数据已保存到Redis")
