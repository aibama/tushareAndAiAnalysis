"""
Tsanghi API 模块
用于获取股票历史日线数据

配置统一在 PatternAnalysis/config.py 中的 TSANGHI_API_CONFIG

主要配置项:
- token: API Token
- base_url: API 基础地址
- max_workers: 最大并发线程数
- rate_limit_per_minute: 每分钟请求上限
- lock_key_prefix: 分布式锁 key 前缀
- lock_timeout: 分布式锁超时时间

使用示例:
    # 获取单只股票数据
    from PatternAnalysis.tsanghiapi.api_client import get_daily_data
    data = get_daily_data("XSHG", "600519")

    # 同步所有股票（带分布式锁）
    from PatternAnalysis.tsanghiapi.sync_service import sync_all_stocks_with_lock
    result = sync_all_stocks_with_lock(limit=100)
"""
from PatternAnalysis.tsanghiapi.api_client import (
    TsanghiApiClient,
    get_daily_data,
    get_stock_date_range,
    get_thread_pool,
)
from PatternAnalysis.tsanghiapi.daily_service import (
    DailyDataService,
    get_stock_date_range,
    get_stock_full_history,
    get_stock_history_by_range,
)
from PatternAnalysis.tsanghiapi.sync_service import (
    SyncService,
    sync_single_stock,
    sync_all_stocks,
    sync_all_stocks_with_lock,
)
from PatternAnalysis.tsanghiapi.distributed_lock import (
    RedisLock,
    acquire_lock,
    with_lock,
    SYNC_LOCK_KEY,
)
