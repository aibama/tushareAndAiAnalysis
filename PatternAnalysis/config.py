"""
股票形态分析系统 - 配置文件
"""
import os

# 数据库配置
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "database": "stockdata",
    "charset": "utf8",
    # MySQL连接池配置
    "pool_size": 5,
    "max_overflow": 10,
    "pool_recycle": 3600,
    "wait_timeout": 600
}

# 模型配置
MODEL_CONFIG = {
    # 序列长度配置
    "sequence_length": 120,
    "feature_length": 100,
    
    # 训练配置（针对6GB显卡优化）
    "batch_size": 32,
    "learning_rate": 0.001,
    "epochs": 100,
    
    # 模型路径
    "model_path": os.path.join(os.path.dirname(__file__), "models"),
    "model_file": "pattern_classifier.pth"
}

# 时间周期配置
PERIOD_CONFIG = {
    "available_periods": ["3m", "6m", "9m", "12m"],
    "default_period": "3m",
    "min_days_required": 30  # 最少需要30个交易日
}

# 技术指标配置
TECHNICAL_INDICATORS = {
    "ma_periods": [5, 10, 20, 60],
    "macd_params": {"fast": 12, "slow": 26, "signal": 9},
    "bollinger_params": {"window": 20, "num_std": 2},
    "rsi_period": 14,
    "atr_period": 14
}

# 回撤反弹配置
DRAWDOWN_REBOUND_CONFIG = {
    "window": 252,  # 滚动窗口大小（交易日），默认252（一年）
    "min_periods": 1  # 最少需要的交易日数量
}

# 形态分类配置
PATTERN_CONFIG = {
    "single_up_threshold": 0.15,  # 单边上涨斜率阈值
    "single_down_threshold": -0.15,  # 单边下跌斜率阈值
    "triangle_angle_threshold": 0.3,  # 三角形收敛角度阈值
    "cup_handle_ratio": 0.3,  # 杯柄形态比例阈值
}

# API服务配置
API_CONFIG = {
    "host": "0.0.0.0",
    "port": 8081,
    "debug": False,
    "title": "股票形态分析服务",
    "version": "1.0.0"
}

# Redis配置
REDIS_CONFIG = {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "password": "dzs940611",
    "key_prefix": "stock_rank:",
    "cache_ttl": 3600  # 缓存1小时
}

# 日志配置
LOG_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": os.path.join(os.path.dirname(__file__), "logs", "pattern_analysis.log")
}

# PostgreSQL 配置（stock_data 数据库）
PG_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "postgres",
    "password": "940611",
    "database": "stock_data"
}
ZHITU_API_CONFIG = {
    "token": "3738FCAC-163E-42A4-82CB-34423318394F",
    "base_url": "https://api.zhituapi.com",
    "request_interval_min": 5000,  # 最小间隔5秒
    "request_interval_max": 10000,  # 最大间隔10秒
    "data_source": "zhituapi"
}

# Tsanghi API配置（股票日线数据）
TSANGHI_API_CONFIG = {
    "token": "ab0e7c09434f4277bb65a016403db823",  # TODO: 替换为实际token
    "base_url": "https://www.tsanghi.com/api/fin/stock",
    "request_timeout": 30,  # 请求超时时间（秒）
    "retry_times": 3,  # 重试次数
    "retry_interval": 5,  # 重试间隔（秒）

    # 并发配置
    "max_workers": 3,  # 最大并发线程数

    # 限流配置（每分钟请求上限）
    "rate_limit_per_minute": 60,  # 每分钟请求上限

    # 分布式锁配置
    "lock_key_prefix": "tsanghi:sync:lock:",  # 分布式锁key前缀
    "lock_timeout": 3600,  # 锁超时时间（秒），默认1小时
}

# 日志表配置（用于记录数据同步状态）
LOG_TABLE_CONFIG = {
    "log_code_stock_daily": "000003",  # stock_daily_data_fill_tsanghiapi
}

# 交易所代码映射
EXCHANGE_CODE_MAPPING = {
    "SZ": "XSHE",  # 深圳交易所
    "SH": "XSHG",  # 上海交易所
}

# AkShare 批量写入 stocktradetodayinfo 时的并发数（避免过快请求东方财富接口）
AKSHARE_SYNC_CONFIG = {
    "max_workers": 3,  # 保守并发，降低被上游拒绝连接概率
    "window_seconds": 600,  # 10分钟时间窗
    "request_limit_per_window": 200,  # 时间窗内最大请求数
    "request_min_interval_seconds": 1.4,  # 相邻请求最小随机间隔
    "request_max_interval_seconds": 3.6,  # 相邻请求最大随机间隔
}

# Baostock 批量写入 stocktradetodayinfo（与 AKSHARE_SYNC_CONFIG 语义对齐；默认单线程 + 串行 query 锁）
BAOSTOCK_SYNC_CONFIG = {
    "max_workers": 1,
    "window_seconds": 600,
    "request_limit_per_window": 60,
    "request_min_interval_seconds": 1.4,
    "request_max_interval_seconds": 10.0,
    # run_server 启动分布式同步时：全量/补数下界（与库内最早业务约定一致，如当前库最小为 2023-01-03）
    "sync_min_start_date": "2023-01-03",
}

# AkShare 代理配置
AKSHARE_PROXY_CONFIG = {
    "enabled": True,  # 是否启用代理
    "host": "101.201.173.125",  # 代理主机
    "port": 50,  # 代理端口
    "user": "",  # 代理用户名（可选）
}
