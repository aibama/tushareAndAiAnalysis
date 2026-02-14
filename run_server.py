#!/usr/bin/env python
"""
股票形态分析系统 - 启动脚本
"""
import sys
import os

# 确保当前目录在Python路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import uvicorn
    from PatternAnalysis.config import API_CONFIG
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装所有依赖")
    sys.exit(1)

if __name__ == "__main__":
    print("=" * 60)
    print("  股票形态分析系统")
    print("=" * 60)
    print(f"启动服务: http://{API_CONFIG['host']}:{API_CONFIG['port']}")
    print()
    
    uvicorn.run(
        "PatternAnalysis.api_service:app",
        host=API_CONFIG["host"],
        port=API_CONFIG["port"],
        reload=API_CONFIG.get("debug", False)
    )
