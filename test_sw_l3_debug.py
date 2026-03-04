"""
调试三级行业数据
"""
import sys
sys.path.insert(0, '.')

from orm.database import query_df

# 查看三级行业的parent_code
sql = "SELECT DISTINCT parent_code FROM sw_industry WHERE level = 3 LIMIT 20"
df = query_df(sql)
print("三级行业的parent_code:")
print(df)

# 查看二级行业的node_code
sql = "SELECT node_code, parent_code FROM sw_industry WHERE level = 2 LIMIT 10"
df = query_df(sql)
print("\n二级行业的node_code和parent_code:")
print(df)

# 查看一级行业的node_code
sql = "SELECT node_code, l1_code FROM sw_industry WHERE level = 1 LIMIT 10"
df = query_df(sql)
print("\n一级行业的node_code:")
print(df)
