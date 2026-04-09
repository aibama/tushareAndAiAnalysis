#!/usr/bin/env python
"""
股票形态分析系统 - 启动脚本
"""
import sys
import os
import threading
import logging

# 确保当前目录在Python路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import uvicorn
    from PatternAnalysis.config import API_CONFIG
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装所有依赖")
    sys.exit(1)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    print("=" * 60)
    print("股票形态分析系统启动中...")
    print("=" * 60)

    # 启动时后台自动执行 Baostock 同步（分布式多节点支持）
    def _auto_baostock_sync():
        try:
            from PatternAnalysis.baostock_api.distributed_startup_runner import (
                run_baostock_tradetoday_distributed_on_startup,
            )

            run_baostock_tradetoday_distributed_on_startup()
        except Exception as e:
            logger.exception("启动 Baostock 自动同步失败: %s", e)

    t = threading.Thread(target=_auto_baostock_sync, daemon=True)
    t.start()

    # 启动时后台自动执行涨跌停状态同步（分布式多节点支持）
    def _auto_limit_status_sync():
        try:
            from orm.etf.stock_daily.distributed_startup_runner import (
                run_limit_status_sync_on_startup,
            )

            run_limit_status_sync_on_startup()
        except Exception as e:
            logger.exception("启动涨跌停状态自动同步失败: %s", e)

    t2 = threading.Thread(target=_auto_limit_status_sync, daemon=True)
    t2.start()

    uvicorn.run(
        "PatternAnalysis.api_service:app",
        host=API_CONFIG.get("host", "0.0.0.0"),
        port=API_CONFIG.get("port", 8081),
        reload=API_CONFIG.get("debug", False)
    )
