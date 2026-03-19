"""
Redis Stream 股票代码生产者服务

从 stock_composition_relation 表读取数据，并将股票代码添加到 Redis Stream
"""
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PatternAnalysis.config import REDIS_CONFIG
from .config import REDIS_STREAM_PRODUCER_CONFIG, get_stream_key

logger = logging.getLogger(__name__)


class RedisStreamProducer:
    """Redis Stream 生产者"""
    
    def __init__(self):
        self._redis_client = None
        self.stream_key = get_stream_key()
        self.batch_size = REDIS_STREAM_PRODUCER_CONFIG.get("batch_size", 100)
        self.max_messages_per_day = REDIS_STREAM_PRODUCER_CONFIG.get("max_messages_per_day", 10000)
        self.message_field = REDIS_STREAM_PRODUCER_CONFIG.get("message_fields", {}).get("stock_code", "stockCode")
    
    @property
    def redis_client(self):
        """获取 Redis 客户端（延迟初始化）"""
        if self._redis_client is None:
            import redis
            self._redis_client = redis.Redis(
                host=REDIS_CONFIG["host"],
                port=REDIS_CONFIG["port"],
                db=REDIS_CONFIG.get("db", 0),
                password=REDIS_CONFIG.get("password"),
                decode_responses=True
            )
        return self._redis_client
    
    def add_message(self, stock_code: str, composition_code: str = None, 
                   in_date: str = None, out_date: str = None) -> Optional[str]:
        """
        添加单条消息到 Stream
        
        Args:
            stock_code: 股票代码
            composition_code: 成分股归属（如 SZ50, HS300, ZZ500, ZZ1000）
            in_date: 纳入日期
            out_date: 调出日期
        
        Returns:
            消息ID，如果失败返回 None
        """
        try:
            message = {
                self.message_field: stock_code,
            }
            if composition_code:
                message["composition_code"] = composition_code
            if in_date:
                message["in_date"] = in_date
            if out_date:
                message["out_date"] = out_date
            
            message_id = self.redis_client.xadd(self.stream_key, message)
            logger.info(f"消息已添加: {stock_code}, message_id: {message_id}")
            return message_id
        except Exception as e:
            logger.error(f"添加消息失败: {e}")
            return None
    
    def add_messages_batch(self, stocks: List[Dict[str, Any]]) -> int:
        """
        批量添加消息到 Stream
        
        Args:
            stocks: 股票列表，每项包含 ts_code, composition_code, in_date, out_date
        
        Returns:
            成功添加的消息数量
        """
        success_count = 0
        for stock in stocks:
            message_id = self.add_message(
                stock_code=stock.get("ts_code"),
                composition_code=stock.get("composition_code"),
                in_date=stock.get("in_date"),
                out_date=stock.get("out_date")
            )
            if message_id:
                success_count += 1
        
        return success_count
    
    def get_stream_info(self) -> Dict[str, Any]:
        """获取 Stream 信息"""
        try:
            info = self.redis_client.xinfo_stream(self.stream_key)
            return {
                "length": info.get("length", 0),
                "first_entry": info.get("first-entry"),
                "last_entry": info.get("last-entry"),
                "stream_key": self.stream_key
            }
        except Exception as e:
            logger.warning(f"获取 Stream 信息失败: {e}")
            return {"error": str(e)}
    
    def close(self):
        """关闭 Redis 连接"""
        if self._redis_client:
            self._redis_client.close()
            self._redis_client = None


def fetch_stocks_from_db(limit: int = None, composition_codes: List[str] = None) -> List[Dict[str, Any]]:
    """
    从数据库获取股票代码列表
    
    Args:
        limit: 限制返回数量
        composition_codes: 筛选成分股归属（如 ["SZ50", "HS300"]）
    
    Returns:
        股票列表
    """
    import pymysql
    from datetime import datetime
    
    db_config = {
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "123456",
        "database": "stockdata",
        "charset": "utf8mb4",
    }
    
    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 构建查询条件
            sql = """
                SELECT ts_code, composition_code, in_date, out_date, is_latest
                FROM stock_composition_relation
                WHERE is_latest = 1
            """
            params = []
            
            if composition_codes:
                placeholders = ",".join(["%s"] * len(composition_codes))
                sql += f" AND composition_code IN ({placeholders})"
                params.extend(composition_codes)
            
            sql += " ORDER BY id"
            
            if limit:
                sql += " LIMIT %s"
                params.append(limit)
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            # 转换日期格式
            stocks = []
            for row in rows:
                stock = {
                    "ts_code": row["ts_code"],
                    "composition_code": row["composition_code"],
                    "in_date": row["in_date"].strftime("%Y-%m-%d") if row["in_date"] else None,
                    "out_date": row["out_date"].strftime("%Y-%m-%d") if row["out_date"] else None,
                    "is_latest": row["is_latest"]
                }
                stocks.append(stock)
            
            return stocks
    finally:
        conn.close()


def produce_stock_codes(force: bool = False, limit: int = None, 
                        composition_codes: List[str] = None) -> Dict[str, Any]:
    """
    生产股票代码消息
    
    Args:
        force: 是否强制执行（忽略时间窗口检查）
        limit: 限制处理数量
        composition_codes: 筛选成分股归属
    
    Returns:
        执行结果
    """
    from .config import is_in_time_window, is_enabled
    
    # 检查是否启用
    if not is_enabled():
        return {
            "success": False,
            "message": "生产者未启用",
            "count": 0
        }
    
    # 检查时间窗口
    if not force and not is_in_time_window():
        return {
            "success": False,
            "message": f"当前时间不在允许的时间窗口内（16:30-22:00），当前时间: {datetime.now().strftime('%H:%M')}",
            "count": 0
        }
    
    # 获取股票列表
    stocks = fetch_stocks_from_db(limit=limit, composition_codes=composition_codes)
    
    if not stocks:
        return {
            "success": False,
            "message": "没有找到需要处理的股票数据",
            "count": 0
        }
    
    # 添加到 Stream
    producer = RedisStreamProducer()
    try:
        # 批量添加
        success_count = 0
        for stock in stocks:
            message_id = producer.add_message(
                stock_code=stock["ts_code"],
                composition_code=stock.get("composition_code"),
                in_date=stock.get("in_date"),
                out_date=stock.get("out_date")
            )
            if message_id:
                success_count += 1
        
        return {
            "success": True,
            "message": f"成功添加 {success_count}/{len(stocks)} 条消息到 Stream",
            "count": success_count,
            "total": len(stocks)
        }
    finally:
        producer.close()


def add_single_stock_code(stock_code: str, composition_code: str = None) -> Dict[str, Any]:
    """
    添加单个股票代码到 Stream
    
    Args:
        stock_code: 股票代码
        composition_code: 成分股归属
    
    Returns:
        执行结果
    """
    producer = RedisStreamProducer()
    try:
        message_id = producer.add_message(
            stock_code=stock_code,
            composition_code=composition_code
        )
        
        if message_id:
            return {
                "success": True,
                "message": f"消息已添加: {message_id}",
                "message_id": message_id,
                "stock_code": stock_code
            }
        else:
            return {
                "success": False,
                "message": "添加消息失败",
                "stock_code": stock_code
            }
    finally:
        producer.close()


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    # 测试添加单条消息
    result = add_single_stock_code("600309.SH", "SZ50")
    print(f"添加单条消息结果: {result}")
    
    # 测试获取 Stream 信息
    producer = RedisStreamProducer()
    info = producer.get_stream_info()
    print(f"Stream 信息: {info}")
    producer.close()
