#!/usr/bin/env python3
"""
Redis Stream 股票代码生产者 - 运维触发脚本

用于手动触发股票代码生产任务

使用方法:
    python trigger_production.py [--force] [--limit N] [--composition CODE1,CODE2]
    python trigger_production.py --add-stock STOCK_CODE [--composition CODE]
    python trigger_production.py --status
    python trigger_production.py --stream-info
"""

import argparse
import logging
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Redis Stream 股票代码生产者 - 运维触发脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 触发生产任务（按时间窗口）
  python trigger_production.py

  # 强制触发生产任务（忽略时间窗口）
  python trigger_production.py --force

  # 限制处理数量
  python trigger_production.py --force --limit 100

  # 只处理特定成分股
  python trigger_production.py --force --composition SZ50,HS300

  # 添加单个股票代码
  python trigger_production.py --add-stock 600309.SH --composition SZ50

  # 查看调度器状态
  python trigger_production.py --status

  # 查看 Stream 信息
  python trigger_production.py --stream-info
        """
    )
    
    parser.add_argument('--force', action='store_true',
                        help='强制执行，忽略时间窗口检查')
    parser.add_argument('--limit', type=int, default=None,
                        help='限制处理数量')
    parser.add_argument('--composition', type=str, default=None,
                        help='成分股筛选，多个用逗号分隔，如: SZ50,HS300')
    parser.add_argument('--add-stock', type=str, default=None,
                        help='添加单个股票代码到 Stream')
    parser.add_argument('--status', action='store_true',
                        help='查看调度器状态')
    parser.add_argument('--stream-info', action='store_true',
                        help='查看 Stream 信息')
    parser.add_argument('--stocks', action='store_true',
                        help='查看数据库中的股票列表')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='显示详细日志')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 导入模块
    from PatternAnalysis.emlevel2.stock_producer_service import (
        produce_stock_codes,
        add_single_stock_code,
        fetch_stocks_from_db,
        RedisStreamProducer
    )
    from PatternAnalysis.emlevel2.scheduler_service import (
        get_scheduler,
        trigger_production
    )
    from PatternAnalysis.emlevel2.config import is_in_time_window, is_enabled
    
    try:
        # 查看调度器状态
        if args.status:
            print("\n" + "=" * 50)
            print("调度器状态")
            print("=" * 50)
            scheduler = get_scheduler()
            status = scheduler.get_status()
            print(f"运行状态: {'运行中' if status['running'] else '已停止'}")
            print(f"检查间隔: {status['interval_minutes']} 分钟")
            print(f"上次执行日期: {status['last_run_date']}")
            print(f"当前时间: {status['current_time']}")
            print(f"时间窗口内: {'是' if is_in_time_window() else '否'}")
            print(f"生产者启用: {'是' if is_enabled() else '否'}")
            return
        
        # 查看 Stream 信息
        if args.stream_info:
            print("\n" + "=" * 50)
            print("Stream 信息")
            print("=" * 50)
            producer = RedisStreamProducer()
            info = producer.get_stream_info()
            producer.close()
            if 'error' in info:
                print(f"错误: {info['error']}")
            else:
                print(f"Stream 键: {info.get('stream_key')}")
                print(f"消息数量: {info.get('length', 0)}")
            return
        
        # 查看股票列表
        if args.stocks:
            print("\n" + "=" * 50)
            print("数据库股票列表")
            print("=" * 50)
            
            composition_codes = None
            if args.composition:
                composition_codes = args.composition.split(',')
            
            stocks = fetch_stocks_from_db(limit=args.limit, composition_codes=composition_codes)
            print(f"股票数量: {len(stocks)}")
            
            # 显示前10条
            for i, stock in enumerate(stocks[:10]):
                print(f"  {i+1}. {stock['ts_code']} - {stock['composition_code']}")
            
            if len(stocks) > 10:
                print(f"  ... 共 {len(stocks)} 条")
            return
        
        # 添加单个股票代码
        if args.add_stock:
            print("\n" + "=" * 50)
            print(f"添加股票代码: {args.add_stock}")
            print("=" * 50)
            
            composition_code = None
            if args.composition:
                composition_code = args.composition
            
            result = add_single_stock_code(args.add_stock, composition_code)
            print(f"结果: {result}")
            return
        
        # 触发生产任务
        print("\n" + "=" * 50)
        print("触发股票代码生产任务")
        print("=" * 50)
        
        # 显示当前状态
        print(f"当前时间窗口内: {'是' if is_in_time_window() else '否'}")
        print(f"强制执行: {'是' if args.force else '否'}")
        
        composition_codes = None
        if args.composition:
            composition_codes = args.composition.split(',')
            print(f"成分股筛选: {composition_codes}")
        
        if args.limit:
            print(f"处理数量限制: {args.limit}")
        
        # 执行
        result = produce_stock_codes(
            force=args.force,
            limit=args.limit,
            composition_codes=composition_codes
        )
        
        print("\n执行结果:")
        print(f"  成功: {result.get('success')}")
        print(f"  消息: {result.get('message')}")
        print(f"  数量: {result.get('count', 0)}")
        
    except Exception as e:
        logger.error(f"执行失败: {e}")
        print(f"\n错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
