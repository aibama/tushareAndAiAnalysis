"""
测试申万行业分类关联修复
"""
import sys
sys.path.insert(0, '.')

from orm.sw_sync_service import SwIndustrySyncService

def test_fix():
    """测试修复功能"""
    service = SwIndustrySyncService()
    
    # 先查看当前的数据情况
    print("=== 查看当前数据 ===")
    from orm.database import query_df
    
    # 查看一级行业
    l1_df = query_df("SELECT node_code, node_name, l1_code, l1_name FROM sw_industry WHERE level = 1 LIMIT 5")
    print("\n一级行业:")
    print(l1_df)
    
    # 查看二级行业 (有问题数据的例子)
    l2_df = query_df("SELECT node_code, node_name, parent_code, l1_code, l1_name FROM sw_industry WHERE level = 2 LIMIT 10")
    print("\n二级行业 (修复前):")
    print(l2_df)
    
    # 查看l1_name为空的记录数
    empty_l1_name = query_df("SELECT COUNT(*) as cnt FROM sw_industry WHERE level = 2 AND (l1_name = '' OR l1_name IS NULL)")
    print(f"\n二级行业中l1_name为空的记录数: {empty_l1_name.iloc[0]['cnt'] if not empty_l1_name.empty else 0}")
    
    empty_l1_name_l3 = query_df("SELECT COUNT(*) as cnt FROM sw_industry WHERE level = 3 AND (l1_name = '' OR l1_name IS NULL)")
    print(f"三级行业中l1_name为空的记录数: {empty_l1_name_l3.iloc[0]['cnt'] if not empty_l1_name_l3.empty else 0}")
    
    # 执行修复
    print("\n=== 执行修复 ===")
    result = service.fix_industry_links()
    print(f"修复结果: {result}")
    
    # 再次查看修复后的数据
    print("\n=== 修复后数据 ===")
    l2_df_fixed = query_df("SELECT node_code, node_name, parent_code, l1_code, l1_name FROM sw_industry WHERE level = 2 LIMIT 10")
    print("\n二级行业 (修复后):")
    print(l2_df_fixed)
    
    # 验证修复结果
    empty_l1_name_after = query_df("SELECT COUNT(*) as cnt FROM sw_industry WHERE level = 2 AND (l1_name = '' OR l1_name IS NULL)")
    print(f"\n修复后二级行业中l1_name为空的记录数: {empty_l1_name_after.iloc[0]['cnt'] if not empty_l1_name_after.empty else 0}")
    
    empty_l1_name_l3_after = query_df("SELECT COUNT(*) as cnt FROM sw_industry WHERE level = 3 AND (l1_name = '' OR l1_name IS NULL)")
    print(f"修复后三级行业中l1_name为空的记录数: {empty_l1_name_l3_after.iloc[0]['cnt'] if not empty_l1_name_l3_after.empty else 0}")

if __name__ == '__main__':
    test_fix()
