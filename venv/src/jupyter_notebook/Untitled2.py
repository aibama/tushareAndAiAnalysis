#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
from sqlalchemy import create_engine
from pandas_profiling import ProfileReport
from pandasgui import show
import dtale


# In[2]:


engine = create_engine('mysql+pymysql://root:123456@localhost:3306/stockdata')
#转成十进制显示，不成功
#pd.set_option('display.float_format', '{:.2g}'.format)
#pd.Series(data=[0.00000001])
pd.set_option('display.float_format', lambda x: '%.3f' % x)


# In[3]:


sql_gainian_eachstock = "select f12,f14,gainianpojo_f12 from gainianeachpojo"
df_read = pd.read_sql_query(sql_gainian_eachstock, engine)
sql_stock_value = "select ts_code,full_value,limit_value from stockvaluebase"
df_read1 = pd.read_sql_query(sql_stock_value, engine)


# In[ ]:





# In[4]:


#module 'pandas.core' has no attribute 'index'


# In[5]:


dtale.show(df_read1)


# In[6]:





# In[ ]:





# In[ ]:




