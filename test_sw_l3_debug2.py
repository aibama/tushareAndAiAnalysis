"""
调试三级行业修复
"""
import sys
sys.path.insert(0, '.')

from orm.database import query_df

# 获取一级行业映射
l1_mapping = {
    '110000': ('801010.SI', '农林牧渔'),
    '220000': ('801030.SI', '基础化工'),
    '230000': ('801040.SI', '钢铁'),
}

# 构建l2_internal_to_node映射
l2_internal_to_node = {}

for parent_code, (l1_code, l1_name) in l1_mapping.items():
    sql = "SELECT node_code FROM sw_industry WHERE level = 2 AND parent_code = %s LIMIT 1"
    df = query_df(sql, {'parent_code': parent_code})
    print(f"查询 parent_code={parent_code}: {df}")
    if df is not None and not df.empty:
        l2_internal_to_node[parent_code] = df.iloc[0]['node_code']

print(f"\nl2_internal_to_node: {l2_internal_to_node}")

# 测试查询三级行业
for l2_parent_code, l2_node_code in l2_internal_to_node.items():
    sql = "SELECT l1_code, l1_name, l2_code, l2_name FROM sw_industry WHERE node_code = %s"
    df = query_df(sql, {'node_code': l2_node_code})
    print(f"\n查询 l2_node_code={l2_node_code}:")
    print(df)
    
    if df is not None and not df.empty:
        l1_code = df.iloc[0]['l1_code']
        l1_name = df.iloc[0]['l1_name']
        l2_code = df.iloc[0]['l2_code']
        l2_name = df.iloc[0]['l2_name']
        
        # 检查有多少三级行业需要更新
        sql = "SELECT COUNT(*) as cnt FROM sw_industry WHERE level = 3 AND parent_code = %s"
        cnt_df = query_df(sql, {'parent_code': l2_parent_code})
        print(f"  需要更新的三级行业数量 (parent_code={l2_parent_code}): {cnt_df.iloc[0]['cnt']}")
