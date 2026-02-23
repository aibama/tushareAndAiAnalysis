# ETF全量数据获取测试脚本
# 使用fund_etf_info表中的ETF列表，获取完整的日线、份额、复权因子数据
# 支持重启运行 - 自动过滤已存在的数据

import sys
import os
from datetime import datetime, timedelta

# 设置路径
_base_dir = os.path.dirname(os.path.abspath(__file__))
# 添加项目根目录到sys.path (需要上4级: etf -> mytushare -> src -> venv -> 项目根目录)
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_base_dir))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 添加mytushare模块路径
_mytushare_path = os.path.join(_project_root, 'venv', 'src', 'mytushare')
if _mytushare_path not in sys.path:
    sys.path.insert(0, _mytushare_path)

# 添加orm模块路径 (dbmanager在venv/src/orm/dbmanager)
_orm_path = os.path.join(_project_root, 'venv', 'src', 'orm')
if _orm_path not in sys.path:
    sys.path.insert(0, _orm_path)

from mytushare.etf.etf_basic import fetch_etf_basic, FundEtfInfo
from mytushare.etf.fund_daily import ETFDailyAPI
from mytushare.etf.etf_share_size import ETFShareSizeAPI
from mytushare.etf.fund_adj import FundAdjAPI

# 导入数据库模块
from dbmanager import dborm as db


def get_all_listed_etfs():
    """
    获取所有已上市的ETF列表（从fund_etf_info表）
    
    Returns:
        list: ETF代码列表，如 ['510330.SH', '510310.SH', ...]
    """
    try:
        # 从数据库获取所有上市的ETF
        etfs = db.DBSession.query(FundEtfInfo.ts_code).filter(
            FundEtfInfo.list_status == 'L'
        ).all()
        return [e[0] for e in etfs]
    except Exception as e:
        print(f"获取ETF列表失败: {e}")
        return []


def get_etf_list_from_tushare():
    """
    从Tushare获取ETF列表（用于首次运行）
    
    Returns:
        list: ETF代码列表
    """
    print("从Tushare获取ETF基础信息...")
    df = fetch_etf_basic(
        list_status='L',
        fields='ts_code',
        filter_existing=False  # 首次运行不过滤
    )
    if df is not None and not df.empty:
        return df['ts_code'].tolist()
    return []


def run_full_etf_job(start_date: str = None, end_date: str = None, 
                     filter_existing: bool = True):
    """
    运行ETF全量数据获取任务
    
    Args:
        start_date: 开始日期，格式 YYYYMMDD，默认为2020年1月1日
        end_date: 结束日期，格式 YYYYMMDD，默认为今天
        filter_existing: 是否过滤已存在的数据，默认为True（可重启）
    """
    # 设置默认日期
    if not end_date:
        end_date = datetime.now().strftime('%Y%m%d')
    if not start_date:
        start_date = '20200101'
    
    print("=" * 60)
    print("ETF全量数据获取任务")
    print(f"日期范围: {start_date} - {end_date}")
    print(f"过滤已存在: {filter_existing}")
    print("=" * 60)
    
    # 1. 首先获取ETF列表
    print("\n【步骤1】获取ETF列表...")
    etf_list = get_all_listed_etfs()
    
    if not etf_list:
        print("数据库中没有ETF，从Tushare获取...")
        etf_list = get_etf_list_from_tushare()
    
    if not etf_list:
        print("无法获取ETF列表，任务终止")
        return
    
    print(f"共获取 {len(etf_list)} 个ETF")
    
    # 2. 获取ETF日线行情
    print("\n【步骤2】获取ETF日线行情...")
    print("-" * 40)
    daily_success = 0
    daily_failed = 0
    
    for i, ts_code in enumerate(etf_list):
        try:
            print(f"[{i+1}/{len(etf_list)}] 获取 {ts_code} 日线数据...", end=" ")
            api = ETFDailyAPI(ts_code=ts_code)
            df = api.get_daily(
                start_date=start_date,
                end_date=end_date,
                filter_existing=filter_existing
            )
            if df is not None and not df.empty:
                print(f"成功获取 {len(df)} 条")
                daily_success += 1
            else:
                print("无新数据")
        except Exception as e:
            print(f"失败: {e}")
            daily_failed += 1
    
    print(f"\n日线数据: 成功 {daily_success} 个, 失败 {daily_failed} 个")
    
    # 3. 获取ETF份额规模
    print("\n【步骤3】获取ETF份额规模...")
    print("-" * 40)
    share_success = 0
    share_failed = 0
    
    for i, ts_code in enumerate(etf_list):
        try:
            print(f"[{i+1}/{len(etf_list)}] 获取 {ts_code} 份额规模...", end=" ")
            api = ETFShareSizeAPI(ts_code=ts_code)
            df = api.get_share_size(
                start_date=start_date,
                end_date=end_date,
                filter_existing=filter_existing
            )
            if df is not None and not df.empty:
                print(f"成功获取 {len(df)} 条")
                share_success += 1
            else:
                print("无新数据")
        except Exception as e:
            print(f"失败: {e}")
            share_failed += 1
    
    print(f"\n份额规模: 成功 {share_success} 个, 失败 {share_failed} 个")
    
    # 4. 获取基金复权因子
    print("\n【步骤4】获取基金复权因子...")
    print("-" * 40)
    adj_success = 0
    adj_failed = 0
    
    for i, ts_code in enumerate(etf_list):
        try:
            print(f"[{i+1}/{len(etf_list)}] 获取 {ts_code} 复权因子...", end=" ")
            api = FundAdjAPI(ts_code=ts_code)
            df = api.get_adj(
                start_date=start_date,
                end_date=end_date,
                filter_existing=filter_existing
            )
            if df is not None and not df.empty:
                print(f"成功获取 {len(df)} 条")
                adj_success += 1
            else:
                print("无新数据")
        except Exception as e:
            print(f"失败: {e}")
            adj_failed += 1
    
    print(f"\n复权因子: 成功 {adj_success} 个, 失败 {adj_failed} 个")
    
    # 总结
    print("\n" + "=" * 60)
    print("任务完成!")
    print(f"日期范围: {start_date} - {end_date}")
    print(f"ETF数量: {len(etf_list)}")
    print(f"日线数据: 成功 {daily_success}, 失败 {daily_failed}")
    print(f"份额规模: 成功 {share_success}, 失败 {share_failed}")
    print(f"复权因子: 成功 {adj_success}, 失败 {adj_failed}")
    print("=" * 60)


def run_incremental_job(days: int = 30):
    """
    运行增量更新任务（最近N天的数据）
    
    Args:
        days: 回溯天数，默认为30天
    """
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
    
    print(f"运行增量更新任务: 最近 {days} 天")
    run_full_etf_job(start_date=start_date, end_date=end_date, filter_existing=True)


# 使用示例
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='ETF全量数据获取脚本')
    parser.add_argument('--start-date', type=str, default='20200101', 
                        help='开始日期，格式 YYYYMMDD')
    parser.add_argument('--end-date', type=str, default=None, 
                        help='结束日期，格式 YYYYMMDD，默认为今天')
    parser.add_argument('--no-filter', action='store_true', 
                        help='不过滤已存在的数据（首次运行使用）')
    parser.add_argument('--incremental', action='store_true',
                        help='增量模式（最近30天）')
    parser.add_argument('--days', type=int, default=30,
                        help='增量模式回溯天数')
    
    args = parser.parse_args()
    
    if args.incremental:
        # 增量模式
        run_incremental_job(days=args.days)
    else:
        # 全量模式
        run_full_etf_job(
            start_date=args.start_date,
            end_date=args.end_date,
            filter_existing=not args.no_filter
        )
