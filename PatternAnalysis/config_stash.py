"""
Stash 配置管理模块
用于从 Stash 加密获取敏感配置
"""
from stash import Client

# Stash 配置
STASH_CONFIG = {
    "url": "http://192.168.1.104:8080",
    "zk_key": "deng@@13414979009"
}

_stash_client = None


def get_stash_client():
    """获取 Stash 客户端单例"""
    global _stash_client
    if _stash_client is None:
        _stash_client = Client(STASH_CONFIG["url"], zk_key=STASH_CONFIG["zk_key"])
    return _stash_client


def get_config(key: str, default=None, value_type=None):
    """
    从 Stash 获取配置

    Args:
        key: 配置 key
        default: 默认值（当 Stash 不可用时使用）
        value_type: 值类型（int, str, bool 等），用于自动转换

    Returns:
        配置值，如果获取失败则返回默认值
    """
    try:
        client = get_stash_client()
        value = client.get(key)
        if value is not None:
            # 类型转换
            if value_type == int:
                return int(value)
            elif value_type == bool:
                return str(value).lower() in ("true", "1", "yes", "y")
            return value
        return default
    except (ValueError, TypeError) as e:
        # 类型转换失败时使用默认值
        print(f"从 stash 获取配置类型转换失败: {key}, {e}")
        return default
    except Exception as e:
        print(f"从 stash 获取配置失败: {key}, {e}")
        return default


def get_config_int(key: str, default: int = 0) -> int:
    """获取整数配置"""
    return get_config(key, default, value_type=int)


def get_config_bool(key: str, default: bool = False) -> bool:
    """获取布尔配置"""
    return get_config(key, default, value_type=bool)


def init_stash_config():
    """
    初始化 stash 配置（仅首次需要）
    将当前 config.py 中的敏感配置写入 stash
    """
    client = get_stash_client()

    # 数据库配置
    db_config_map = {
        "app/config/db/host": "localhost",
        "app/config/db/port": "3306",
        "app/config/db/user": "root",
        "app/config/db/password": "123456",
        "app/config/db/database": "stockdata",
    }

    # Redis 配置
    redis_config_map = {
        "app/config/redis/host": "localhost",
        "app/config/redis/port": "6379",
        "app/config/redis/db": "0",
        "app/config/redis/password": "dzs940611",
    }

    # PostgreSQL 配置
    pg_config_map = {
        "app/config/pg/host": "localhost",
        "app/config/pg/port": "5432",
        "app/config/pg/user": "postgres",
        "app/config/pg/password": "940611",
        "app/config/pg/database": "stock_data",
    }

    # API Token 配置
    api_config_map = {
        "app/config/zhitu/token": "3738FCAC-163E-42A4-82CB-34423318394F",
        "app/config/tsanghi/token": "ab0e7c09434f4277bb65a016403db823",
    }

    # 合并所有配置
    all_configs = {**db_config_map, **redis_config_map, **pg_config_map, **api_config_map}

    for key, value in all_configs.items():
        client.set(key, value)
        print(f"已设置 stash 配置: {key}")


if __name__ == "__main__":
    # 测试：初始化配置到 stash
    init_stash_config()