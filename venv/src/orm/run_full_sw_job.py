# 申万行业分类全量数据获取测试脚本
# 使用Tushare接口获取申万行业分类和成分股数据
# 支持重启运行 - 自动过滤已存在的数据

import sys
import os

# 设置路径 - 硬编码项目根目录
# venv/src/orm/run_full_sw_job.py -> c:/03_code/pythonCode/easymoneycrawling
_project_root = 'c:/03_code/pythonCode/easymoneycrawling'

# 添加项目根目录
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 添加PatternAnalysis模块路径
_pattern_analysis_path = _project_root + '/PatternAnalysis'
if _pattern_analysis_path not in sys.path:
    sys.path.insert(0, _pattern_analysis_path)

# 添加venv/src路径
_venv_src_path = _project_root + '/venv/src'
if _venv_src_path not in sys.path:
    sys.path.insert(0, _venv_src_path)

from orm.sw_sync_service import SwIndustrySyncService, SwMemberSyncService
from orm.sw_query_service import SwIndustryQueryService, SwStockQueryService
from orm.database import table_exists


def init_database():
    """
    初始化数据库表
    
    Returns:
        bool: 是否成功
    """
    tables = ['sw_industry', 'stock_sw_relation']
    all_exists = True
    
    for table in tables:
        exists = table_exists(table)
        if not exists:
            print(f"表 {table} 不存在，请先执行SQL脚本创建表")
            print(f"SQL文件: {os.path.join(_base_dir, 'sw_schema.sql')}")
            all_exists = False
    
    return all_exists


def get_existing_industry_count():
    """
    获取已存在的行业数量
    
    Returns:
        dict: 各层级行业数量
    """
    query_service = SwIndustryQueryService()
    
    l1_count = len(query_service.get_l1_industry())
    l2_count = len(query_service.get_l2_industry())
    l3_count = len(query_service.get_l3_industry())
    
    return {
        'l1': l1_count,
        'l2': l2_count,
        'l3': l3_count,
        'total': l1_count + l2_count + l3_count
    }


def sync_sw_industry(src: str = 'SW2021', force: bool = False):
    """
    同步申万行业分类数据
    
    Args:
        src: 申万版本，SW2014 或 SW2021
        force: 是否强制同步（忽略已有数据）
        
    Returns:
        dict: 同步结果
    """
    # 检查现有数据
    if not force:
        existing = get_existing_industry_count()
        if existing['total'] > 0:
            print(f"数据库已有行业数据: L1={existing['l1']}, L2={existing['l2']}, L3={existing['l3']}")
            print("使用 --force 参数强制重新同步")
            return {'skipped': True, 'reason': '已有数据', 'existing': existing}
    
    print(f"\n开始同步申万行业分类数据 (版本: {src})...")
    service = SwIndustrySyncService(src=src)
    result = service.sync_all_industry()
    
    return result


def sync_sw_members(src: str = 'SW2021', force: bool = False):
    """
    同步申万行业成分股数据
    
    Args:
        src: 申万版本，SW2014 或 SW2021
        force: 是否强制同步
        
    Returns:
        dict: 同步结果
    """
    # 检查现有数据
    if not force:
        query_service = SwStockQueryService()
        # 检查是否有成分股数据
        try:
            # 随机检查一个三级行业
            l3_df = query_service.get_industry_list(level=3)
            if not l3_df.empty:
                sample_code = l3_df.iloc[0]['node_code']
                stocks_df = query_service.get_industry_stocks(sample_code, is_latest=True)
                if not stocks_df.empty:
                    print(f"数据库已有成分股数据")
                    return {'skipped': True, 'reason': '已有数据'}
        except:
            pass
    
    print(f"\n开始同步申万行业成分股数据 (版本: {src})...")
    service = SwMemberSyncService(src=src)
    result = service.sync_all_members()
    
    return result


def run_full_sw_job(src: str = 'SW2021', force: bool = False):
    """
    运行申万行业全量数据同步任务
    
    Args:
        src: 申万版本，SW2014 或 SW2021
        force: 是否强制同步
    """
    print("=" * 60)
    print("申万行业分类全量数据同步任务")
    print(f"版本: {src}")
    print(f"强制同步: {force}")
    print("=" * 60)
    
    # 1. 初始化数据库
    print("\n【步骤1】检查数据库表...")
    if not init_database():
        return
    
    # 2. 同步行业分类
    print("\n【步骤2】同步申万行业分类...")
    industry_result = sync_sw_industry(src=src, force=force)
    
    if industry_result.get('skipped'):
        print(f"跳过同步: {industry_result['reason']}")
    else:
        print(f"行业分类同步完成:")
        print(f"  - 一级行业: {industry_result.get('l1_count', 0)}")
        print(f"  - 二级行业: {industry_result.get('l2_count', 0)}")
        print(f"  - 三级行业: {industry_result.get('l3_count', 0)}")
        print(f"  - 总计: {industry_result.get('total_count', 0)}")
        if industry_result.get('errors'):
            print(f"  - 错误: {len(industry_result['errors'])}")
    
    # 3. 同步成分股
    print("\n【步骤3】同步申万行业成分股...")
    member_result = sync_sw_members(src=src, force=force)
    
    if member_result.get('skipped'):
        print(f"跳过同步: {member_result['reason']}")
    else:
        print(f"成分股同步完成:")
        print(f"  - 行业数量: {member_result.get('industry_count', 0)}")
        print(f"  - 股票数量: {member_result.get('stock_count', 0)}")
        if member_result.get('errors'):
            print(f"  - 错误: {len(member_result['errors'])}")
    
    # 4. 显示统计
    print("\n【步骤4】数据统计...")
    existing = get_existing_industry_count()
    print(f"当前行业数据:")
    print(f"  - 一级行业: {existing['l1']}")
    print(f"  - 二级行业: {existing['l2']}")
    print(f"  - 三级行业: {existing['l3']}")
    print(f"  - 总计: {existing['total']}")
    
    # 总结
    print("\n" + "=" * 60)
    print("任务完成!")
    print(f"版本: {src}")
    print("=" * 60)


def query_industry_tree():
    """查询并显示行业树形结构"""
    print("\n查询申万行业树形结构...")
    
    query_service = SwIndustryQueryService()
    tree = query_service.get_industry_tree()
    
    print(f"\n一级行业数量: {len(tree)}")
    
    for l1 in tree[:5]:  # 只显示前5个
        print(f"\n{l1['node_code']} - {l1['node_name']}")
        
        if 'children' in l1 and l1['children']:
            l2_children = l1['children']
            print(f"  包含 {len(l2_children)} 个二级行业")
            
            for l2 in l2_children[:3]:  # 每个一级显示前3个二级
                print(f"    ├─ {l2['node_code']} - {l2['node_name']}")
                
                if 'children' in l2 and l2['children']:
                    l3_children = l2['children']
                    print(f"    │   包含 {len(l3_children)} 个三级行业")
                    
                    for l3 in l3_children[:2]:  # 每个二级显示前2个三级
                        print(f"    │   ├─ {l3['node_code']} - {l3['node_name']}")


def query_stock_industry(ts_code: str):
    """
    查询股票所属行业
    
    Args:
        ts_code: 股票代码
    """
    print(f"\n查询股票 {ts_code} 所属行业...")
    
    query_service = SwStockQueryService()
    industries = query_service.get_stock_industry(ts_code)
    
    if industries:
        print(f"找到 {len(industries)} 个所属行业:")
        for ind in industries:
            print(f"  - {ind['l1_name']}/{ind['l2_name']}/{ind['l3_name']}")
    else:
        print("未找到所属行业信息")


def query_industry_stocks(node_code: str):
    """
    查询行业成分股
    
    Args:
        node_code: 行业节点代码
    """
    print(f"\n查询行业 {node_code} 成分股...")
    
    query_service = SwStockQueryService()
    stocks = query_service.get_industry_stocks(node_code, is_latest=True)
    
    if stocks is not None and not stocks.empty:
        print(f"找到 {len(stocks)} 只成分股:")
        for _, row in stocks.head(10).iterrows():
            print(f"  - {row['ts_code']}")
    else:
        print("未找到成分股信息")


# 使用示例
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='申万行业分类全量数据同步脚本')
    parser.add_argument('--src', type=str, default='SW2021', 
                        choices=['SW2014', 'SW2021'],
                        help='申万版本: SW2014 或 SW2021')
    parser.add_argument('--force', action='store_true', 
                        help='强制同步（忽略已有数据）')
    parser.add_argument('--query-tree', action='store_true',
                        help='查询并显示行业树形结构')
    parser.add_argument('--query-stock', type=str, 
                        help='查询股票所属行业，传入股票代码')
    parser.add_argument('--query-members', type=str,
                        help='查询行业成分股，传入行业代码')
    
    args = parser.parse_args()
    
    if args.query_tree:
        # 查询行业树
        query_industry_tree()
    elif args.query_stock:
        # 查询股票所属行业
        query_stock_industry(args.query_stock)
    elif args.query_members:
        # 查询行业成分股
        query_industry_stocks(args.query_members)
    else:
        # 运行全量同步
        run_full_sw_job(src=args.src, force=args.force)
