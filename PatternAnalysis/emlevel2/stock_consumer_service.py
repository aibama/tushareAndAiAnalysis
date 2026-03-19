"""
Redis Stream 消费者服务

从 Redis Stream 消费股票代码消息，按批次处理
"""
import logging
import time
import threading
from typing import Callable, Optional, List, Dict, Any
import socket
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PatternAnalysis.config import REDIS_CONFIG
from .config import REDIS_STREAM_PRODUCER_CONFIG, get_stream_key

logger = logging.getLogger(__name__)


class RedisStreamConsumer:
    """Redis Stream 消费者"""

    def __init__(self, group_name: str = None, consumer_name: str = None,
                 batch_size: int = None, message_handler: Callable = None):
        """
        初始化消费者

        Args:
            group_name: 消费者组名称
            consumer_name: 消费者名称（默认使用 hostname-pid）
            batch_size: 每批处理数量
            message_handler: 消息处理函数，接收 (message_id, message_dict) 参数
        """
        self._redis_client = None

        config = REDIS_STREAM_PRODUCER_CONFIG
        self.stream_key = get_stream_key()
        self.group_name = group_name or config.get("group_name", "stock-group")
        self.consumer_name = consumer_name or self._generate_consumer_name()
        self.batch_size = batch_size or config.get("batch_size", 100)
        self.message_handler = message_handler

        # 运行时状态
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def _generate_consumer_name(self) -> str:
        """生成消费者名称"""
        hostname = socket.gethostname().replace("-", "-")
        pid = os.getpid()
        return f"consumer-{hostname}-{pid}"

    @property
    def redis_client(self):
        """获取 Redis 客户端"""
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

    def create_group_if_not_exists(self):
        """创建消费者组（如果不存在）"""
        try:
            # 尝试创建消费者组
            # 使用 "0" 表示从头开始读取
            self.redis_client.xgroup_create(
                self.stream_key,
                self.group_name,
                id="0",
                mkstream=True
            )
            logger.info(f"创建消费者组: {self.group_name}")
        except Exception as e:
            if "BUSYGROUP" in str(e):
                logger.debug(f"消费者组 {self.group_name} 已存在")
            else:
                logger.warning(f"创建消费者组失败: {e}")

    def consume(self, block_ms: int = 5000) -> List[tuple]:
        """
        消费消息（主动拉取新消息）

        Args:
            block_ms: 阻塞等待毫秒数

        Returns:
            消息列表 [(message_id, message_dict), ...]
        """
        # 使用 XREADGROUP 读取新消息
        # ">" 表示只读取新消息（不包括 pending）
        messages = self.redis_client.xreadgroup(
            groupname=self.group_name,
            consumername=self.consumer_name,
            streams={self.stream_key: ">"},
            count=self.batch_size,
            block=block_ms
        )

        if not messages:
            return []

        result = []
        for stream_name, stream_messages in messages:
            for msg_id, msg_data in stream_messages:
                result.append((msg_id, msg_data))

        return result

    def consume_pending(self) -> List[tuple]:
        """
        消费 pending 消息（之前拉取但未 ACK 的）

        Returns:
            消息列表 [(message_id, message_dict), ...]
        """
        # 使用 XREADGROUP 读取 pending 消息
        # "0" 表示读取 pending 列表中的消息
        messages = self.redis_client.xreadgroup(
            groupname=self.group_name,
            consumername=self.consumer_name,
            streams={self.stream_key: "0"},
            count=self.batch_size
        )

        if not messages:
            return []

        result = []
        for stream_name, stream_messages in messages:
            for msg_id, msg_data in stream_messages:
                result.append((msg_id, msg_data))

        return result

    def ack_message(self, message_id: str) -> bool:
        """确认消息已处理"""
        try:
            result = self.redis_client.xack(self.stream_key, self.group_name, message_id)
            return result > 0
        except Exception as e:
            logger.error(f"ACK 消息失败: {message_id}, error: {e}")
            return False

    def process_loop(self, block_ms: int = 5000):
        """
        处理循环：先处理 pending，再拉取新消息

        Args:
            block_ms: 阻塞等待毫秒数
        """
        processed_count = 0

        # 1. 先尝试处理 pending 消息（之前拉取但未 ACK 的）
        pending_messages = self.consume_pending()
        if pending_messages:
            logger.info(f"处理 {len(pending_messages)} 条 pending 消息")
            for msg_id, msg_data in pending_messages:
                self._process_single_message(msg_id, msg_data)
                processed_count += 1

        # 2. 如果没有 pending，拉取新消息
        if not pending_messages:
            new_messages = self.consume(block_ms=block_ms)
            if new_messages:
                logger.info(f"拉取到 {len(new_messages)} 条新消息")
                for msg_id, msg_data in new_messages:
                    self._process_single_message(msg_id, msg_data)
                    processed_count += 1

        return processed_count

    def _process_single_message(self, msg_id: str, msg_data: dict):
        """处理单条消息"""
        try:
            if self.message_handler:
                # 调用自定义处理函数
                self.message_handler(msg_id, msg_data)
            else:
                # 默认处理：打印消息
                logger.info(f"处理消息: {msg_id}, data: {msg_data}")

            # 确认消息
            self.ack_message(msg_id)
            logger.debug(f"消息已 ACK: {msg_id}")

        except Exception as e:
            logger.error(f"处理消息失败: {msg_id}, error: {e}")
            # 不 ACK，消息会重新变为 pending

    def start_consuming(self, interval_seconds: float = 1.0):
        """启动持续消费"""
        if self._running:
            logger.warning("消费者已在运行中")
            return

        self._running = True
        self._thread = threading.Thread(target=self._consume_loop,
                                        args=(interval_seconds,),
                                        daemon=True,
                                        name="RedisStreamConsumer")
        self._thread.start()
        logger.info(f"消费者已启动: {self.consumer_name}, group: {self.group_name}")

    def stop_consuming(self):
        """停止消费"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("消费者已停止")

    def _consume_loop(self, interval_seconds: float):
        """消费主循环"""
        while self._running:
            try:
                count = self.process_loop(block_ms=5000)

                if count == 0:
                    # 没有消息，稍作等待
                    time.sleep(interval_seconds)
                else:
                    logger.info(f"本轮处理了 {count} 条消息")

            except Exception as e:
                logger.error(f"消费循环出错: {e}")
                time.sleep(5)  # 出错后等待一段时间

    def get_pending_info(self) -> Dict[str, Any]:
        """获取 pending 消息信息"""
        try:
            pending = self.redis_client.xpending(
                self.stream_key,
                self.group_name,
                start="-",
                end="+",
                count=10
            )
            return {
                "pending_count": len(pending),
                "pending": pending
            }
        except Exception as e:
            return {"error": str(e)}

    def close(self):
        """关闭连接"""
        if self._redis_client:
            self._redis_client.close()
            self._redis_client = None


def default_message_handler(msg_id: str, msg_data: dict):
    """默认消息处理函数"""
    stock_code = msg_data.get("stockCode", msg_data.get("stock_code", "unknown"))
    logger.info(f"处理股票代码: {stock_code}")

    # 在这里添加你的业务逻辑
    # 例如：调用 API、分析数据等

    # 模拟处理时间
    time.sleep(0.1)


def start_consumer(message_handler: Callable = None, batch_size: int = 100):
    """
    启动消费者

    Args:
        message_handler: 消息处理函数
        batch_size: 批次大小
    """
    consumer = RedisStreamConsumer(
        batch_size=batch_size,
        message_handler=message_handler or default_message_handler
    )

    # 创建消费者组
    consumer.create_group_if_not_exists()

    # 启动消费
    consumer.start_consuming()

    return consumer


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("启动 Redis Stream 消费者...")
    consumer = start_consumer()

    try:
        while True:
            time.sleep(60)
            # 打印状态
            pending_info = consumer.get_pending_info()
            print(f"Pending 信息: {pending_info}")
    except KeyboardInterrupt:
        print("停止消费者...")
        consumer.stop_consuming()
        consumer.close()
