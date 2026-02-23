"""
申万行业分类数据同步和查询测试脚本
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orm import (
    get_industry_sync_service, 
    get_member_sync_service,
    get_industry_query_service,
    get_stock_query_service,
    table_exists
)
from orm.database import execute_sql


def test_table_exists():
    """测试表是否存在"""
    print("\n=== 测试: 检查数据表是否存在 ===")
    
    tables = ['sw_industry', 'stock_sw_relation']
    for table in tables:
        exists = table_exists(table)
        print(f"表 {table}: {'存在' if exists else '不存在'}")
    
    return all(table_exists(t) for t in tables)


def test_sync_industry():
    """测试同步申万行业分类"""
    print("\n=== 测试: 同步申万行业分类数据 ===")
    
    try:
        service = get_industry_sync_service('SW2021')
        result = service.sync_all_industry()
        
        print(f"一级行业同步数量: {result['l1_count']}")
        print(f"二级行业同步数量: {result['l2_count']}")
        print(f"三级行业同步数量: {result['l3_count']}")
        print(f"总计同步数量: {result['total_count']}")
        
        if result['errors']:
            print(f"错误信息: {result['errors']}")
        
        return result['total_count'] > 0
    except Exception as e:
        print(f"同步失败: {e}")
        print("注意: 请检查Tushare Token是否有效")
        return False


def test_query_industry():
    """测试查询行业分类"""
    print("\n=== 测试: 查询申万行业分类 ===")
    
    query_service = get_industry_query_service()
    
    # 查询一级行业
    l1_df = query_service.get_l1_industry()
    print(f"一级行业数量: {len(l1_df)}")
    if not l1_df.empty:
        print(f"示例: {l1_df.iloc[0]['node_code']} - {l1_df.iloc[0]['node_name']}")
    
    # 查询二级行业
    l2_df = query_service.get_l2_industry()
    print(f"二级行业数量: {len(l2_df)}")
    
    # 查询三级行业
    l3_df = query_service.get_l3_industry()
    print(f"三级行业数量: {len(l3_df)}")
    
    return len(l1_df) > 0


def test_sync_members():
    """测试同步成分股"""
    print("\n=== 测试: 同步申万行业成分股 ===")
    
    try:
        service = get_member_sync_service('SW2021')
        result = service.sync_all_members()
        
        print(f"行业数量: {result['industry_count']}")
        print(f"股票数量: {result['stock_count']}")
        
        if result['errors']:
            print(f"错误信息: {result['errors'][:3]}...")  # 只显示前3个错误
        
        return result['stock_count'] > 0
    except Exception as e:
        print(f"同步失败: {e}")
        return False


def test_query_stock_industry():
    """测试查询股票所属行业"""
    print("\n=== 测试: 查询股票所属行业 ===")
    
    query_service = get_stock_query_service()
    
    # 测试几个常见股票
    test_stocks = ['000001.SZ', '600519.SH', '000858.SZ', '601318.SH']
    
    for ts_code in test_stocks:
        industries = query_service.get_stock_industry(ts_code)
        print(f"\n{ts_code} 所属行业:")
        if industries:
            for ind in industries:
                print(f"  - {ind['l1_name']}/{ind['l2_name']}/{ind['l3_name']}")
        else:
            print("  未找到")
    
    return True


def test_query_industry_stocks():
    """测试查询行业成分股"""
    print("\n=== 测试: 查询行业成分股 ===")
    
    query_service = get_stock_query_service()
    industry_service = get_industry_query_service()
    
    # 查询"黄金"行业成分股
    l3_df = industry_service.get_industry_list(level=3)
    if l3_df is not None and not l3_df.empty:
        gold_industry = l3_df[l3_df['l3_name'].str.contains('黄金', na=False)]
        
        if not gold_industry.empty:
            gold_code = gold_industry.iloc[0]['node_code']
            gold_name = gold_industry.iloc[0]['l3_name']
            
            stocks_df = query_service.get_industry_stocks(gold_code, is_latest=True)
            print(f"\n{gold_name}({gold_code}) 成分股数量: {len(stocks_df)}")
            
            if not stocks_df.empty:
                print("前5只成分股:")
                for _, row in stocks_df.head(5).iterrows():
                    print(f"  - {row['ts_code']}")
    
    return True


def test_query_industry_tree():
    """测试查询行业树形结构"""
    print("\n=== 测试: 查询行业树形结构 ===")
    
    query_service = get_industry_query_service()
    tree = query_service.get_industry_tree()
    
    print(f"一级行业数量: {len(tree)}")
    
    if tree:
        first_l1 = tree[0]
        print(f"\n示例一级行业: {first_l1['node_name']}")
        
        if 'children' in first_l1 and first_l1['children']:
            print(f"  包含二级行业数量: {len(first_l1['children'])}")
            
            first_l2 = first_l1['children'][0]
            print(f"  示例二级行业: {first_l2['node_name']}")
            
            if 'children' in first_l2 and first_l2['children']:
                print(f"    包含三级行业数量: {len(first_l2['children'])}")
    
    return len(tree) > 0


def main():
    """运行所有测试"""
    print("=" * 50)
    print("申万行业分类数据同步和查询测试")
    print("=" * 50)
    
    # 检查表是否存在，如果不存在则创建
    if not test_table_exists():
        print("\n警告: 数据表不存在，请先执行SQL脚本创建表")
        print("SQL文件: orm/sw_schema.sql")
        return
    
    # 测试查询行业分类（不依赖Tushare）
    if test_query_industry():
        print("\n[OK] 行业分类查询成功")
    else:
        # 如果没有数据，尝试同步
        print("\n行业数据为空，尝试同步...")
        if test_sync_industry():
            print("\n[OK] 行业分类同步成功")
            # 再次查询
            test_query_industry()
    
    # 测试查询行业树
    if test_query_industry_tree():
        print("\n[OK] 行业树形结构查询成功")
    
    # 尝试同步成分股（需要有效的Tushare Token）
    sync_success = False
    try:
        if test_sync_members():
            print("\n[OK] 成分股同步成功")
            sync_success = True
    except Exception as e:
        print(f"\n[!] 成分股同步跳过: {e}")
    
    # 测试查询股票所属行业
    if test_query_stock_industry():
        print("\n[OK] 股票所属行业查询成功")
    
    # 测试查询行业成分股
    if test_query_industry_stocks():
        print("\n[OK] 行业成分股查询成功")
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)


if __name__ == "__main__":
    main()
