#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试导入 - 检查依赖是否安装正确
"""
import sys
import os

# 添加父目录到Python路径
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

def test_imports():
    """测试所有导入"""
    modules = [
        ("sys", "sys"),
        ("os", "os"),
        ("uvicorn", "uvicorn"),
        ("fastapi", "fastapi"),
        ("pydantic", "pydantic"),
        ("pymysql", "pymysql"),
        ("pandas", "pandas"),
        ("numpy", "numpy"),
        ("scipy", "scipy"),
        ("dateutil", "dateutil"),
    ]
    
    all_ok = True
    for module_name, import_name in modules:
        try:
            __import__(import_name)
            print(f"[OK] {module_name}")
        except ImportError as e:
            print(f"[FAIL] {module_name} - {e}")
            all_ok = False
    
    # 测试PatternAnalysis模块
    print("\n测试PatternAnalysis模块:")
    try:
        from PatternAnalysis.config import API_CONFIG
        print("[OK] PatternAnalysis.config")
    except ImportError as e:
        print(f"[FAIL] PatternAnalysis.config - {e}")
        all_ok = False
    
    try:
        from PatternAnalysis.pattern_model import PatternType
        print("[OK] PatternAnalysis.pattern_model")
    except ImportError as e:
        print(f"[FAIL] PatternAnalysis.pattern_model - {e}")
        all_ok = False
    
    try:
        from PatternAnalysis.api_service import app
        print("[OK] PatternAnalysis.api_service")
    except ImportError as e:
        print(f"[FAIL] PatternAnalysis.api_service - {e}")
        all_ok = False
    
    if all_ok:
        print("\n[SUCCESS] 所有导入测试通过!")
    else:
        print("\n[ERROR] 部分导入失败，请安装缺失的依赖")
        sys.exit(1)

if __name__ == "__main__":
    test_imports()
