"""Stock Pattern Analysis System - Redis Cache Management"""
import json
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from .config import REDIS_CONFIG

_redis_client = None

def get_redis_client():
    global _redis_client
    if _redis_client is None:
        try:
            import redis
            _redis_client = redis.Redis(
                host=REDIS_CONFIG["host"],
                port=REDIS_CONFIG["port"],
                db=REDIS_CONFIG.get("db", 0),
                password=REDIS_CONFIG.get("password"),
                decode_responses=True
            )
        except Exception as e:
            print(f"Redis connection failed: {e}")
            return None
    return _redis_client

def _make_cache_key(prefix: str, **kwargs) -> str:
    sorted_items = sorted(kwargs.items())
    key_str = prefix + "_" + "_".join(f"{k}={v}" for k, v in sorted_items)
    return f"{REDIS_CONFIG['key_prefix']}{key_str}"

def _serialize(obj: Any) -> str:
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return json.dumps(obj, ensure_ascii=False)

def _deserialize(data: str) -> Any:
    return json.loads(data)

def get_cached_rank(direction: str, start_date: date, end_date: date) -> Optional[List[Dict]]:
    client = get_redis_client()
    if client is None:
        return None
    cache_key = _make_cache_key("rank", direction=direction, start=start_date, end=end_date)
    try:
        data = client.get(cache_key)
        if data:
            return _deserialize(data)
    except Exception as e:
        print(f"Read cache failed: {e}")
    return None

def set_cached_rank(direction: str, start_date: date, end_date: date, data: List[Dict], ttl: int = None):
    client = get_redis_client()
    if client is None:
        return
    cache_key = _make_cache_key("rank", direction=direction, start=start_date, end=end_date)
    ttl = ttl or REDIS_CONFIG["cache_ttl"]
    try:
        serialized = _serialize(data)
        client.setex(cache_key, ttl, serialized)
    except Exception as e:
        print(f"Write cache failed: {e}")

def get_cached_rank_info() -> Dict[str, Any]:
    client = get_redis_client()
    if client is None:
        return {"status": "disconnected", "keys": []}
    try:
        pattern = f"{REDIS_CONFIG['key_prefix']}rank_*"
        keys = list(client.scan_iter(pattern))
        info = {"status": "connected", "keys": keys, "key_count": len(keys)}
        ttls = {}
        for key in keys:
            try:
                ttl = client.ttl(key)
                ttls[key] = ttl if ttl > 0 else "persistent"
            except:
                ttls[key] = "unknown"
        info["ttls"] = ttls
        return info
    except Exception as e:
        return {"status": "error", "message": str(e), "keys": []}

def clear_rank_cache() -> int:
    client = get_redis_client()
    if client is None:
        return 0
    try:
        pattern = f"{REDIS_CONFIG['key_prefix']}rank_*"
        keys = list(client.scan_iter(pattern))
        if keys:
            client.delete(*keys)
        return len(keys)
    except Exception as e:
        print(f"Clear cache failed: {e}")
        return 0

class RankCacheManager:
    def __init__(self):
        self.config = REDIS_CONFIG
    
    def get_status(self) -> Dict[str, Any]:
        return get_cached_rank_info()
    
    def clear(self) -> Dict[str, Any]:
        count = clear_rank_cache()
        return {"cleared": count, "status": "success"}
    
    def precompute_rank(self, direction: str, start_date: date, end_date: date) -> bool:
        return True
