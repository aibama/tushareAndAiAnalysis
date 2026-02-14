#!/usr/bin/env python
"""
股票形态分析系统 - 主入口脚本
提供便捷的启动方式
"""

import sys
import os

# 添加父目录到Python路径
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

try:
    import uvicorn
    from PatternAnalysis.config import API_CONFIG
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装所有依赖: pip install fastapi uvicorn pymysql pandas numpy scipy python-dateutil pydantic")
    sys.exit(1)


def main():
    """主函数"""
    print("=" * 60)
    print("  股票形态分析系统")
    print("  Pattern Analysis Service")
    print("=" * 60)
    print()
    print(f"启动服务: http://{API_CONFIG['host']}:{API_CONFIG['port']}")
    print(f"API文档: http://{API_CONFIG['host']}:{API_CONFIG['port']}/docs")
    print(f"Web界面: http://{API_CONFIG['host']}:{API_CONFIG['port']}/web/index.html")
    print()
    print("按 Ctrl+C 停止服务")
    print("=" * 60)
    print()
    
    # 启动服务
    try:
        uvicorn.run(
            "PatternAnalysis.api_service:app",
            host=API_CONFIG["host"],
            port=API_CONFIG["port"],
            reload=API_CONFIG.get("debug", False),
            log_level="info"
        )
    except OSError as e:
        print(f"启动失败: {e}")
        print("可能端口已被占用，请检查或修改config.py中的端口设置")
        sys.exit(1)


if __name__ == "__main__":
    main()
