"""
查看剩余未修复的记录
"""
import sys
sys.path.insert(0, '.')

from orm.database import query_df

# 查看剩余未修复的l3记录
sql = """
    SELECT node_code, node_name, parent_code, l1_code, l1_name, l2_code, l2_name
    FROM sw_industry 
    WHERE level = 3 AND (l1_name = '' OR l1_name IS NULL)
    LIMIT 20
"""
df = query_df(sql)
print("剩余未修复的三级行业:")
print(df)
