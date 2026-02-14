#!/usr/bin/env python
"""
股票形态分析系统 - 增量任务运行脚本
"""
import sys
import os

# 确保当前目录在Python路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "incremental"
    
    from PatternAnalysis.incremental_jobs import run_incremental_job, run_full_recalculation, init_tables
    
    if mode == "init":
        print("初始化数据库表...")
        init_tables()
        print("完成")
    elif mode == "incremental":
        print("执行增量计算任务...")
        run_incremental_job()
        print("完成")
    elif mode == "full":
        print("执行全量重算任务...")
        run_full_recalculation()
        print("完成")
    else:
        print(f"未知模式: {mode}")
        print("可用模式: init, incremental, full")
        sys.exit(1)
