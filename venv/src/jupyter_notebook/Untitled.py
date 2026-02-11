#!/usr/bin/env python
# coding: utf-8

# In[6]:


import pandas as pd
from sqlalchemy import create_engine
from pandas_profiling import ProfileReport


# In[7]:


engine = create_engine('mysql+pymysql://root:123456@localhost:3306/stockdata')
#转成十进制显示，不成功
#pd.set_option('display.float_format', '{:.2g}'.format)
#pd.Series(data=[0.00000001])
pd.set_option('display.float_format', lambda x: '%.3f' % x)


# In[8]:


sql_query = 'select compositiontype,security_name_abbr,secucode from stockcomposition order by compositiontype;'
# 使用pandas的read_sql_query函数执行SQL语句，并存入DataFrame
df_read = pd.read_sql_query(sql_query, engine)
print(df_read)


# In[9]:


sql_query = 'select ts_code,full_value,limit_value from stockvaluebase order by full_value desc ;'
df_read_marketvalue = pd.read_sql_query(sql_query, engine)
sql_query = 'select substring(ts_code,1,6) as ts_code,name from stockinfobase;'
df_read_info = pd.read_sql_query(sql_query, engine)


# In[10]:


print(df_read_marketvalue)
print(df_read_info)


# In[16]:


df_differ = df_read_info.loc[~df_read_info.ts_code.isin(df_read_marketvalue.ts_code)]


# pandas.set_option('display.max_rows', df_differ.shape[0]+1)
# 设置显示的最大行数

# In[18]:


pd.set_option('display.max_rows', df_differ.shape[0]+1)
df_differ


# In[ ]:





# In[11]:


result0=pd.merge(df_read_marketvalue,df_read_info,on=['ts_code'])


# In[12]:


print(result0)


# 上面是按市值、或者流动市值排序的表

# In[27]:


query_code_gainian = "select f12 as ts_code,f14,gainianpojo_f12 as f12 from gainianeachpojo "
query_gainian = "select f12,f14 from gainianpojo"
result1 = pd.read_sql_query(query_code_gainian, engine)
result2 = pd.read_sql_query(query_gainian, engine)

result = pd.merge(result1,result2,on=['f12'])
print(result)


# In[28]:


result['f14_y'] = result.groupby(['ts_code'])['f14_y'].transform(lambda x: '，'.join(x))

pandas的操作很多时候要注意带原有的引用，
result['f14_y'] = result.groupby(['code_f12'])['f14_y'].transform(lambda x: '，'.join(x))
像这里的result['f14_y'] = 左操作
result.drop_duplicates(subset=None, keep="first", inplace=True)
以及
# In[29]:


result.drop('f12',axis=1,inplace=True)
result.drop_duplicates(subset=None, keep="first", inplace=True)
print(result)


# result['f12'] = result.groupby(['code_f12'])['f12'].transform(lambda x: '，'.join(x))
# result['f14_y'] = result.groupby(['code_f12'])['f14_y'].transform(lambda x: '，'.join(x))

# 准备拼接基础表A、基础表B

# In[30]:


print(list(result))


# In[31]:


target_df = pd.merge(result0,result[["ts_code","f14_y"]],on=['ts_code'])


# target_df.loc(target_df['ts_code']=='600308')
# 这里会报错TypeError: unhashable type: 'Series'
# loc是内置函数？
# target_df.loc[target_df['ts_code']=='600308']

# target_df.loc[target_df['ts_code']=='600308']
# 通过指定列值，获取行值

# In[15]:


profile = ProfileReport(target_df, title="Pandas Profiling Report",explorative=True)


# In[16]:


profile


# In[17]:


profile.to_widgets()


# In[19]:


target_df.loc[target_df['ts_code']=='000858'] 


# In[ ]:




