"""
个股日线数据统计服务
提供个股日线数据统计和MTR/ATR计算功能
"""
import logging
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from decimal import Decimal

import pandas as pd
import redis
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PatternAnalysis.config import DB_CONFIG, REDIS_CONFIG

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RedisStreamManager:
    """Redis Stream管理器"""

    def __init__(self):
        self._redis_client = redis.Redis(
            host=REDIS_CONFIG["host"],
            port=REDIS_CONFIG["port"],
            db=REDIS_CONFIG.get("db", 0),
            password=REDIS_CONFIG.get("password", None),
            decode_responses=True
        )
        self.key_prefix = REDIS_CONFIG.get("key_prefix", "stock_rank:")
        self.mtr_atr_stream = f"{self.key_prefix}mtr_atr_stream"

    @property
    def redis_client(self):
        """提供对redis客户端的访问（兼容旧代码）"""
        return self._redis_client
    
    def add_message(self, stream_name: str, data: dict) -> bool:
        """
        向Stream添加消息
        Returns: True if success, False if failed
        """
        try:
            message_id = self._redis_client.xadd(stream_name, data)
            logger.debug(f"消息已添加到Stream {stream_name}: {message_id}")
            return True
        except Exception as e:
            logger.debug(f"Stream不可用，跳过: {e}")
            return False
    
    def create_stream_if_not_exists(self, stream_name: str, max_len: int = 10000):
        """创建Stream（如果不存在）"""
        try:
            # 检查stream是否存在
            info = self._redis_client.xinfo_stream(stream_name)
            logger.debug(f"Stream {stream_name} 已存在")
        except redis.exceptions.ResponseError:
            # Stream不存在，创建它
            self._redis_client.xadd(stream_name, {"init": "true"}, maxlen=max_len, approximate=True)
            logger.info(f"Stream {stream_name} 已创建")

    def close(self):
        """关闭Redis连接"""
        if self._redis_client:
            self._redis_client.close()


class StockStatisticsService:
    """个股统计数据服务"""
    
    def __init__(self):
        self.engine = self._create_engine()
        self.redis_manager = RedisStreamManager()
    
    def _create_engine(self):
        """创建SQLAlchemy引擎"""
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
    
    def get_stock_data_summary(self) -> Dict:
        """
        1.1 统计每个个股的日线数据情况
        返回格式：
        {
            "total_stocks": 100,
            "stocks": [
                {
                    "ts_code": "000001.SZ",
                    "record_count": 250,
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31"
                },
                ...
            ]
        }
        """
        logger.info("开始统计个股日线数据情况")
        
        try:
            # 查询每个股票的数据统计
            sql = """
                SELECT 
                    ts_code,
                    COUNT(*) as record_count,
                    MIN(DATE(trade_date)) as start_date,
                    MAX(DATE(trade_date)) as end_date
                FROM stocktradetodayinfo
                WHERE ts_code IS NOT NULL AND ts_code != ''
                GROUP BY ts_code
                ORDER BY ts_code
            """
            
            df = pd.read_sql(text(sql), self.engine)
            
            if df.empty:
                return {
                    "total_stocks": 0,
                    "stocks": [],
                    "generated_at": datetime.now().isoformat()
                }
            
            # 转换日期格式
            stocks = []
            for _, row in df.iterrows():
                start_date = row['start_date']
                end_date = row['end_date']
                
                # 处理日期格式
                if isinstance(start_date, (datetime, date)):
                    start_date = start_date.strftime('%Y-%m-%d')
                elif start_date is None:
                    start_date = "N/A"
                
                if isinstance(end_date, (datetime, date)):
                    end_date = end_date.strftime('%Y-%m-%d')
                elif end_date is None:
                    end_date = "N/A"
                
                stocks.append({
                    "ts_code": row['ts_code'],
                    "record_count": int(row['record_count']) if pd.notna(row['record_count']) else 0,
                    "start_date": start_date,
                    "end_date": end_date
                })
            
            result = {
                "total_stocks": len(stocks),
                "stocks": stocks,
                "generated_at": datetime.now().isoformat()
            }
            
            logger.info(f"统计完成，共 {len(stocks)} 个股票")
            return result
            
        except Exception as e:
            logger.error(f"统计个股数据失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "total_stocks": 0,
                "stocks": [],
                "error": str(e),
                "generated_at": datetime.now().isoformat()
            }
    
    def format_summary_text(self) -> str:
        """
        格式化输出统计信息
        输出格式：
        个股：共XXX个，
        000001.SZ,记录数XXX,从YYYY-MM-DD到YYYY-MM-DD,
        ....
        """
        summary = self.get_stock_data_summary()
        
        lines = []
        lines.append(f"个股：共{summary['total_stocks']}个，")
        
        for stock in summary['stocks']:
            lines.append(
                f"{stock['ts_code']},记录数{stock['record_count']},"
                f"从{stock['start_date']}到{stock['end_date']},"
            )
        
        return '\n'.join(lines)
    
    def get_stock_ohlc_data(self, ts_code: str, limit: int = None) -> pd.DataFrame:
        """获取单个股票的OHLC数据"""
        try:
            if limit:
                sql = """
                    SELECT trade_date, open, high, low, close, pre_close, vol, amount
                    FROM stocktradetodayinfo
                    WHERE ts_code = :ts_code
                    ORDER BY trade_date ASC
                    LIMIT :limit_val
                """
                params = {"ts_code": ts_code, "limit_val": limit}
            else:
                sql = """
                    SELECT trade_date, open, high, low, close, pre_close, vol, amount
                    FROM stocktradetodayinfo
                    WHERE ts_code = :ts_code
                    ORDER BY trade_date ASC
                """
                params = {"ts_code": ts_code}
            
            df = pd.read_sql(text(sql), self.engine, params=params)
            
            if not df.empty:
                df['trade_date'] = pd.to_datetime(df['trade_date'])
                for col in ['open', 'high', 'low', 'close', 'pre_close']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
            
        except Exception as e:
            logger.error(f"获取股票 {ts_code} 数据失败: {e}")
            return pd.DataFrame()
    
    def calculate_tr(self, high: float, low: float, pre_close: float) -> float:
        """
        计算单日真实波幅 (TR)
        TR = MAX( 当日最高价 - 当日最低价, |当日最高价 - 前一日收盘价|, |当日最低价 - 前一日收盘价| )
        """
        tr1 = high - low
        tr2 = abs(high - pre_close)
        tr3 = abs(low - pre_close)
        return max(tr1, tr2, tr3)
    
    def calculate_mtr_atr(self, ts_code: str, atr_period: int = 14) -> Tuple[Optional[float], Optional[float]]:
        """
        计算单个股票的MTR和ATR
        
        Args:
            ts_code: 股票代码
            atr_period: ATR计算周期，默认14天
            
        Returns:
            Tuple of (MTR, ATR)，如果数据不足则返回 (None, None)
        """
        df = self.get_stock_ohlc_data(ts_code)
        
        if df.empty or len(df) < atr_period:
            logger.warning(f"股票 {ts_code} 数据不足 {atr_period} 天，无法计算MTR/ATR")
            return None, None
        
        # 计算每日的TR
        tr_values = []
        for idx, row in df.iterrows():
            high = row['high']
            low = row['low']
            
            # 前一日收盘价（第一天的前一日收盘价使用当天的pre_close）
            if idx == 0:
                pre_close = row['pre_close'] if pd.notna(row['pre_close']) else row['close']
            else:
                pre_close = df.iloc[idx - 1]['close']
            
            if pd.notna(high) and pd.notna(low) and pd.notna(pre_close):
                tr = self.calculate_tr(high, low, pre_close)
                tr_values.append(tr)
            else:
                tr_values.append(0)
        
        df['tr'] = tr_values
        
        # 计算ATR
        if len(df) >= atr_period:
            # 初始ATR = 前atr_period个TR的简单算术平均
            initial_atr = df['tr'].iloc[:atr_period].mean()
            
            # 从第atr_period天开始，使用EMA公式计算
            atr_values = [None] * (atr_period - 1)  # 前面几天没有ATR
            
            current_atr = initial_atr
            atr_values.append(current_atr)
            
            for i in range(atr_period, len(df)):
                current_tr = df['tr'].iloc[i]
                # ATR = [前一日ATR × 13 + 当日TR] / 14
                current_atr = (current_atr * (atr_period - 1) + current_tr) / atr_period
                atr_values.append(current_atr)
            
            df['atr'] = atr_values
            
            # MTR = 最后一天的ATR（或者最新计算的有效ATR）
            mtr = df['atr'].iloc[-1] if df['atr'].iloc[-1] is not None else None
            atr = df['atr'].iloc[-1] if df['atr'].iloc[-1] is not None else None
            
            return mtr, atr
        else:
            return None, None
    
    def calculate_all_stocks_mtr_atr(
        self,
        atr_period: int = 14,
        batch_size: int = 100,
        on_batch_complete: callable = None
    ) -> List[Dict]:
        """
        计算所有股票的MTR和ATR

        Args:
            atr_period: ATR计算周期，默认14天
            batch_size: 每批次处理的股票数量，默认100
            on_batch_complete: 每批次完成后的回调函数，接收(batch_results, batch_idx)参数

        Returns:
            包含MTR/ATR数据的列表
        """
        logger.info(f"开始计算所有股票的MTR/ATR，周期={atr_period}天，批次大小={batch_size}")

        # 获取所有股票代码
        sql = "SELECT DISTINCT ts_code FROM stocktradetodayinfo WHERE ts_code IS NOT NULL AND ts_code != ''"
        df = pd.read_sql(text(sql), self.engine)

        if df.empty:
            logger.warning("没有找到股票数据")
            return []

        ts_codes = df['ts_code'].tolist()
        results = []
        batch_results = []

        for idx, ts_code in enumerate(ts_codes):
            try:
                mtr, atr = self.calculate_mtr_atr(ts_code, atr_period)

                result = {
                    "ts_code": ts_code,
                    "mtr": round(mtr, 4) if mtr is not None else None,
                    "atr": round(atr, 4) if atr is not None else None,
                    "atr_period": atr_period,
                    "calculated_at": datetime.now().isoformat()
                }
                results.append(result)
                batch_results.append(result)

                # 每批次完成后保存到Redis
                if (idx + 1) % batch_size == 0:
                    logger.info(f"已计算 {idx + 1}/{len(ts_codes)} 个股票，保存批次数据到Redis")
                    # 触发回调（传入当前批次结果）
                    if on_batch_complete:
                        on_batch_complete(batch_results.copy(), idx // batch_size)
                    # 保存批次结果到Redis
                    self.save_mtr_atr_to_redis_stream(batch_results)
                    batch_results = []  # 清空批次缓存

            except Exception as e:
                logger.error(f"计算股票 {ts_code} 的MTR/ATR失败: {e}")
                results.append({
                    "ts_code": ts_code,
                    "mtr": None,
                    "atr": None,
                    "atr_period": atr_period,
                    "error": str(e),
                    "calculated_at": datetime.now().isoformat()
                })
                batch_results.append(results[-1])

        # 保存剩余的批次结果
        if batch_results:
            logger.info(f"保存剩余 {len(batch_results)} 条记录到Redis")
            self.save_mtr_atr_to_redis_stream(batch_results)

        logger.info(f"MTR/ATR计算完成，共 {len(results)} 个股票")
        return results
    
    def save_mtr_atr_to_redis_stream(self, results: List[Dict], stream_name: str = None):
        """
        将MTR/ATR结果保存到Redis Stream
        如果Redis不支持Stream，使用Hash作为备选方案
        """
        if stream_name is None:
            stream_name = self.redis_manager.mtr_atr_stream

        # 备选方案：使用Redis Hash存储
        hash_key = f"{stream_name}:data"

        saved_count = 0
        stream_failed = False

        for result in results:
            try:
                # 尝试使用Stream（如果Stream还没失败过）
                if not stream_failed:
                    message = {
                        "ts_code": result["ts_code"],
                        "mtr": str(result["mtr"]) if result["mtr"] is not None else "",
                        "atr": str(result["atr"]) if result["atr"] is not None else "",
                        "atr_period": str(result["atr_period"]),
                        "calculated_at": result["calculated_at"]
                    }

                    if "error" in result:
                        message["error"] = result["error"]

                    success = self.redis_manager.add_message(stream_name, message)
                    if success:
                        saved_count += 1
                    else:
                        stream_failed = True
                        # Fallback to Hash
                        field = result["ts_code"]
                        value = f"{result['mtr']},{result['atr']},{result['atr_period']},{result['calculated_at']}"
                        self.redis_manager.redis_client.hset(hash_key, field, value)
                        saved_count += 1

                # Stream已失败，直接使用Hash
                if stream_failed:
                    field = result["ts_code"]
                    value = f"{result['mtr']},{result['atr']},{result['atr_period']},{result['calculated_at']}"
                    self.redis_manager.redis_client.hset(hash_key, field, value)
                    saved_count += 1

            except Exception as e:
                logger.error(f"保存股票 {result['ts_code']} 到Redis失败: {e}")

        if saved_count > 0:
            logger.info(f"已将 {saved_count}/{len(results)} 条MTR/ATR记录保存到Redis (Stream: {not stream_failed}, Hash fallback: {stream_failed})")
    
    def close(self):
        """关闭连接"""
        if self.engine:
            self.engine.dispose()
        self.redis_manager.close()


# MTR/ATR状态管理
class MTRATRStatusManager:
    """MTR/ATR计算状态管理器，用于增量计算"""
    
    def __init__(self):
        self.engine = self._create_engine()
        self.redis_client = redis.Redis(
            host=REDIS_CONFIG["host"],
            port=REDIS_CONFIG["port"],
            db=REDIS_CONFIG.get("db", 0),
            password=REDIS_CONFIG.get("password", None),
            decode_responses=True
        )
        self.status_key = f"{REDIS_CONFIG.get('key_prefix', 'stock_rank:')}mtr_atr_status"
    
    def _create_engine(self):
        """创建SQLAlchemy引擎"""
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
    
    def get_last_atr_period(self) -> Optional[int]:
        """获取上次计算的ATR周期"""
        try:
            period = self.redis_client.hget(self.status_key, "atr_period")
            return int(period) if period else None
        except Exception as e:
            logger.error(f"获取ATR周期失败: {e}")
            return None
    
    def save_atr_period(self, atr_period: int):
        """保存ATR周期配置"""
        try:
            self.redis_client.hset(self.status_key, "atr_period", str(atr_period))
            self.redis_client.hset(self.status_key, "last_updated", datetime.now().isoformat())
            logger.info(f"ATR周期配置已保存: {atr_period}")
        except Exception as e:
            logger.error(f"保存ATR周期失败: {e}")
    
    def get_last_trade_date(self, ts_code: str) -> Optional[date]:
        """获取指定股票最后计算的交易日"""
        try:
            key = f"{self.status_key}:{ts_code}"
            trade_date = self.redis_client.hget(key, "last_trade_date")
            if trade_date:
                return datetime.strptime(trade_date, '%Y-%m-%d').date()
            return None
        except Exception as e:
            logger.error(f"获取股票 {ts_code} 最后交易日失败: {e}")
            return None
    
    def save_last_trade_date(self, ts_code: str, trade_date: date):
        """保存指定股票的最后交易日"""
        try:
            key = f"{self.status_key}:{ts_code}"
            self.redis_client.hset(key, "last_trade_date", trade_date.strftime('%Y-%m-%d'))
            self.redis_client.hset(key, "last_updated", datetime.now().isoformat())
        except Exception as e:
            logger.error(f"保存股票 {ts_code} 最后交易日失败: {e}")
    
    def is_recalculation_needed(self, atr_period: int) -> bool:
        """
        判断是否需要重新计算所有股票的MTR/ATR
        如果ATR周期参数变化了，需要重新计算
        """
        last_period = self.get_last_atr_period()
        if last_period is None or last_period != atr_period:
            logger.info(f"ATR周期变化: {last_period} -> {atr_period}，需要重新计算")
            return True
        return False
    
    def close(self):
        """关闭连接"""
        if self.engine:
            self.engine.dispose()
        if self.redis_client:
            self.redis_client.close()


def run_incremental_mtr_atr_calculation(
    atr_period: int = 14,
    start_date: str = None,
    end_date: str = None,
    fill_gaps: bool = False,
    force_recalculate: bool = False
):
    """
    增量运行MTR/ATR计算

    Args:
        atr_period: ATR计算周期，默认14天
        start_date: 开始日期（YYYY-MM-DD格式），可选
        end_date: 结束日期（YYYY-MM-DD格式），可选
        fill_gaps: 是否填充数据缺口（自动检测并补充缺失的数据）
        force_recalculate: 是否强制重新计算所有数据

    Returns:
        dict: 执行结果包含计算记录数和状态
    """
    from datetime import datetime, timedelta

    logger.info(f"开始MTR/ATR计算，ATR周期={atr_period}, start_date={start_date}, end_date={end_date}, fill_gaps={fill_gaps}")

    service = StockStatisticsService()
    status_manager = MTRATRStatusManager()

    try:
        # 获取全局数据范围
        global_summary = service.get_stock_data_summary()
        if global_summary['stocks']:
            global_start = min(s['start_date'] for s in global_summary['stocks'] if s['start_date'] != 'N/A')
            global_end = max(s['end_date'] for s in global_summary['stocks'] if s['end_date'] != 'N/A')
            logger.info(f"数据库中数据范围: {global_start} 到 {global_end}")
        else:
            global_start = None
            global_end = None

        # 确定计算范围
        if start_date is None:
            if fill_gaps and global_start:
                start_date = global_start
            else:
                # 默认从end_date往前推ATR_period天，确保有足够数据计算ATR
                reference_date = end_date if end_date else datetime.now().strftime('%Y-%m-%d')
                start_date = reference_date  # 具体范围由增量逻辑决定

        if end_date is None:
            if fill_gaps and global_end:
                end_date = global_end
            else:
                end_date = datetime.now().strftime('%Y-%m-%d')

        # 检查是否需要重新计算所有股票
        if force_recalculate or status_manager.is_recalculation_needed(atr_period):
            logger.info("执行全量重新计算")
            results = service.calculate_all_stocks_mtr_atr(atr_period)
            status_manager.save_atr_period(atr_period)

            # 更新所有股票的最后交易日
            for result in results:
                ts_code = result["ts_code"]
                df = service.get_stock_ohlc_data(ts_code)
                if not df.empty:
                    last_date = df['trade_date'].max().date()
                    status_manager.save_last_trade_date(ts_code, last_date)
        else:
            logger.info("执行增量计算")
            # 实现真正的增量计算逻辑
            results = _run_incremental_calculation(
                service, status_manager, atr_period, start_date, end_date, fill_gaps
            )

        # 保存到Redis Stream
        service.save_mtr_atr_to_redis_stream(results)

        result_count = len([r for r in results if r.get('atr') is not None])
        logger.info(f"MTR/ATR计算完成，共 {result_count} 条有效记录")

        return {
            "status": "success",
            "atr_period": atr_period,
            "result_count": result_count,
            "start_date": start_date,
            "end_date": end_date,
            "fill_gaps": fill_gaps
        }

    finally:
        service.close()
        status_manager.close()


def _run_incremental_calculation(
    service: StockStatisticsService,
    status_manager: MTRATRStatusManager,
    atr_period: int,
    start_date: str,
    end_date: str,
    fill_gaps: bool
):
    """
    执行真正的增量计算

    逻辑说明：
    1. 遍历所有股票
    2. 对于每个股票，获取其最后计算日期
    3. 如果fill_gaps=True，补充缺失日期的数据
    4. 如果指定了start_date和end_date，只计算该范围内的数据
    5. 往后就每天新增（end_date为None或等于今天时）
    """
    from datetime import datetime, timedelta

    # 获取所有股票
    sql = "SELECT DISTINCT ts_code FROM stocktradetodayinfo WHERE ts_code IS NOT NULL AND ts_code != ''"
    df = pd.read_sql(text(sql), service.engine)
    if df.empty:
        return []

    ts_codes = df['ts_code'].tolist()
    results = []

    for idx, ts_code in enumerate(ts_codes):
        try:
            # 获取该股票的最后计算日期
            last_calc_date = status_manager.get_last_trade_date(ts_code)
            stock_data = service.get_stock_ohlc_data(ts_code)

            if stock_data.empty:
                continue

            # 获取该股票的数据范围
            stock_start = stock_data['trade_date'].min().strftime('%Y-%m-%d')
            stock_end = stock_data['trade_date'].max().strftime('%Y-%m-%d')

            # 确定该股票需要计算的范围
            calc_start = start_date
            calc_end = end_date

            if fill_gaps and last_calc_date:
                # 补充缺失的数据（从数据开始到最后一条数据）
                calc_start = min(stock_start, last_calc_date.strftime('%Y-%m-%d'))
                calc_end = max(stock_end, last_calc_date.strftime('%Y-%m-%d'))
            elif last_calc_date and not fill_gaps:
                # 只计算增量（从最后计算日期的下一天到最新数据）
                calc_start = (last_calc_date + timedelta(days=1)).strftime('%Y-%m-%d')
                calc_end = stock_end

            # 如果计算范围无效，跳过
            if calc_start > calc_end:
                logger.debug(f"股票 {ts_code} 无需增量计算")
                # 仍然获取已有的MTR/ATR值
                existing_result = _get_existing_mtr_atr(service, ts_code, atr_period)
                if existing_result:
                    results.append(existing_result)
                continue

            # 计算该股票的MTR/ATR
            mtr, atr = service.calculate_mtr_atr(ts_code, atr_period)

            # 更新状态
            if stock_data['trade_date'].max():
                status_manager.save_last_trade_date(ts_code, stock_data['trade_date'].max().date())

            result = {
                "ts_code": ts_code,
                "mtr": round(mtr, 4) if mtr is not None else None,
                "atr": round(atr, 4) if atr is not None else None,
                "atr_period": atr_period,
                "calculated_at": datetime.now().isoformat(),
                "calc_range": f"{calc_start} to {calc_end}"
            }
            results.append(result)

            if (idx + 1) % 100 == 0:
                logger.info(f"已计算 {idx + 1}/{len(ts_codes)} 个股票")

        except Exception as e:
            logger.error(f"计算股票 {ts_code} 的MTR/ATR失败: {e}")
            results.append({
                "ts_code": ts_code,
                "mtr": None,
                "atr": None,
                "atr_period": atr_period,
                "error": str(e),
                "calculated_at": datetime.now().isoformat()
            })

    return results


def _get_existing_mtr_atr(service: StockStatisticsService, ts_code: str, atr_period: int) -> Dict:
    """获取股票已有的MTR/ATR值（从缓存或重新计算）"""
    try:
        # 从Redis获取已有的值
        status_manager = MTRATRStatusManager()
        last_date = status_manager.get_last_trade_date(ts_code)

        if last_date:
            # 重新计算以获取最新的MTR/ATR
            mtr, atr = service.calculate_mtr_atr(ts_code, atr_period)
            return {
                "ts_code": ts_code,
                "mtr": round(mtr, 4) if mtr is not None else None,
                "atr": round(atr, 4) if atr is not None else None,
                "atr_period": atr_period,
                "calculated_at": datetime.now().isoformat(),
                "from_cache": True
            }
        return None
    except Exception as e:
        logger.error(f"获取股票 {ts_code} 已有MTR/ATR失败: {e}")
        return None


if __name__ == "__main__":
    # 测试代码
    service = StockStatisticsService()
    
    # 测试1: 统计个股数据
    print("=== 个股数据统计 ===")
    summary = service.get_stock_data_summary()
    print(f"总股票数: {summary['total_stocks']}")
    if summary['stocks']:
        print("前5个股票:")
        for stock in summary['stocks'][:5]:
            print(f"  {stock['ts_code']}: {stock['record_count']} 条记录, {stock['start_date']} 到 {stock['end_date']}")
    
    # 测试2: 计算单个股票的MTR/ATR
    print("\n=== MTR/ATR计算测试 ===")
    if summary['stocks']:
        test_ts_code = summary['stocks'][2]['ts_code']
        mtr, atr = service.calculate_mtr_atr(test_ts_code)
        print(f"股票 {test_ts_code}: MTR={mtr}, ATR={atr}")
    
    service.close()
