#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
from sqlalchemy import create_engine
from pandas_profiling import ProfileReport
from pandasgui import show
import dtale
import numpy as np


# In[2]:


engine = create_engine('mysql+pymysql://root:123456@localhost:3306/stockdata')
#转成十进制显示，不成功
#pd.set_option('display.float_format', '{:.2g}'.format)
#pd.Series(data=[0.00000001])
pd.set_option('display.float_format', lambda x: '%.3f' % x)


# # 看市场的水位，通过时间区间的涨跌幅度，观察时间区间的强势、收益情况
# # 逻辑是全量交易数据，200w，先设置显示的行数
# # 设置开始和结束时间，算涨跌幅，对比响应的指数
# 

# In[3]:



sql_trade_daily = "SELECT * FROM stockdata.stocktradedailyinfo;"
df_read1 = pd.read_sql_query(sql_trade_daily, engine)
sql_stock_info = "select ts_code,name from stockinfobase"
df_read2 = pd.read_sql_query(sql_stock_info, engine)


# In[ ]:





# In[4]:


df_read1.dtypes


# In[5]:


df_read1.set_index("trade_date",inplace=True) 


# In[6]:


#df_read1[20].shift(periods=1,freq=30)


# In[7]:


df_read1.index


# In[8]:


def pairStockCloseMinus(x):
    if(len(x.close)<2):
        return pd.Series([x.ts_code,None])
    else:
        return pd.Series([x.ts_code[0], (x.close[1] - x.close[0]) / x.close[0]])


# In[9]:


cut = df_read1.query("trade_date==20211109 or trade_date==20211111").groupby(["ts_code"]).apply(pairStockCloseMinus)


# In[10]:


cut


# In[11]:


cut.columns


# In[ ]:


#cut.columns=["stock_code","interval_ATR%"]


# In[ ]:


cut['stock_code'] = cut['stock_code'].str[:6]


# In[12]:


cut.reset_index(drop=True, inplace=True)


# In[ ]:


#cut.columns=["stock_code","interval_ATR%"]


# In[13]:


cut.columns=["ts_code","interval_ATR%"]


# In[14]:


cut['ts_code'] = cut['ts_code'].str[:6]


# In[15]:


cut.columns


# In[16]:


cut


# In[19]:


df_read2


# In[20]:


type(cut)


# In[21]:


cut.dtypes


# In[22]:


df_read2.dtypes


# In[23]:


cut.index


# In[24]:


df_read2.index


# In[18]:


cut.merge(df_read2,on="ts_code",how="inner")


# In[ ]:





# In[ ]:


cut = df_read1.query("trade_date==20211109 or trade_date==20211111").groupby(["ts_code"]).apply(pairStockCloseMinus)


# In[ ]:





# In[ ]:


cut


# In[ ]:





# In[ ]:


dtale.show(cut)


# In[ ]:





# In[ ]:


type(cut)


# In[ ]:





# def applyfunc(y):
#     for x in y.tolist():
#         print(x.name+":   "+x)
# rand = np.random.RandomState(1)
# df = pd.DataFrame({'A': ['foo', 'bar'] * 3,
#                    'B': rand.randn(6),
#                    'C': rand.randint(0, 20, 6)})
# gb = df.groupby(['A'])
# df

# df_read1.query("trade_date==20211109 or trade_date==20211111")

# In[ ]:


df_read1.query("trade_date==20211109 or trade_date==20211111").groupby(["ts_code"]).apply(lambda x:print(x.ts_code[0],(x.close[1]-x.close[0])/x.close[0]))


# In[ ]:





# 

# In[ ]:


close1=df_read1["2022-01-05"].groupby(["ts_code"]).get_group("600203.SH")['close']


# In[ ]:





# In[ ]:


df_read1["2021-21-11"]


# In[ ]:





# In[ ]:


close2=df_read1["2022-01-07"][['ts_code','close']]
print(close2.to_string())


# In[ ]:





# In[ ]:


dd11=df_read1["2022-01-05":"2022-01-08"].groupby(["ts_code"])['close'].apply(applyfunc)


# In[ ]:





# In[ ]:


df_read1


# In[ ]:





# In[ ]:


df_read1["2022-01-04":"2022-01-05"].groupby(['ts_code'])["close"].transform(lambda x: x-x)


# In[ ]:





# In[ ]:





# In[ ]:


# >>> df = pd.DataFrame({'A': a, 'B': b}, index=[0])
# >>> df
#    A  B
# 0  2  3

# >>> df = pd.DataFrame({'A': [a], 'B': [b]})
# >>> df
#    A  B
# 0  2  3


# In[ ]:


df_test = pd.DataFrame(
    {
        "group": [11,22],
        #"date1": pd.to_datetime("2020-01-02","2020-01-03")
        "date1": pd.Series(["2020-01-02","2020-01-03"],dtype='datetime64[ns]')

    }
)
df_test


# In[ ]:


df_test[[(df_test['date1']==pd.to_datetime("2020-01-02"))]]


# In[ ]:





# In[ ]:


df_test['date1']==pd.to_datetime("2020-01-02")


# In[ ]:




