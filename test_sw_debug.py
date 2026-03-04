"""
调试申万行业分类映射
"""
import sys
sys.path.insert(0, '.')

from orm.sw_sync_service import SwIndustrySyncService

def debug_mapping():
    """调试映射构建"""
    service = SwIndustrySyncService()
    
    # 构建映射
    mapping = service._build_l1_mapping()
    print(f"映射数量: {len(mapping)}")
    print("\n映射内容:")
    for k, v in list(mapping.items())[:5]:
        print(f"  {k} -> {v}")
    
    # 检查数据库中实际的parent_code
    from orm.database import query_df
    sql = "SELECT DISTINCT parent_code FROM sw_industry WHERE level = 2 LIMIT 10"
    df = query_df(sql)
    print("\n数据库中实际的parent_code:")
    print(df)
    
    # 检查一级行业
    sql = "SELECT node_code, l1_code, l1_name FROM sw_industry WHERE level = 1 LIMIT 10"
    df = query_df(sql)
    print("\n一级行业数据:")
    print(df)

if __name__ == '__main__':
    debug_mapping()
