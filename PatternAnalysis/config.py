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
    "port": 8000,
    "debug": False,
    "title": "股票形态分析服务",
    "version": "1.0.0"
}

# 日志配置
LOG_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": os.path.join(os.path.dirname(__file__), "logs", "pattern_analysis.log")
}
