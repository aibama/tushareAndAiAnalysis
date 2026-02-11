#!/usr/bin/env python
# coding: utf-8
# %%

# %%


import pandas as pd
from sqlalchemy import create_engine
from pandas_profiling import ProfileReport
from pandasgui import show
import dtale
import numpy as np


# %%


engine = create_engine('mysql+pymysql://root:123456@localhost:3306/stockdata')
#转成十进制显示，不成功
#pd.set_option('display.float_format', '{:.2g}'.format)
#pd.Series(data=[0.00000001])
pd.set_option('display.float_format', lambda x: '%.3f' % x)


# # 看市场的水位，通过时间区间的涨跌幅度，观察时间区间的强势、收益情况
# # 逻辑是全量交易数据，200w，先设置显示的行数
# # 设置开始和结束时间，算涨跌幅，对比响应的指数
# 

# %%



sql_trade_daily = "SELECT * FROM stockdata.stocktradedailyinfo;"
df_read1 = pd.read_sql_query(sql_trade_daily, engine)


# %%





# %%


df_read1.dtypes


# %%


df_read1.set_index("trade_date",inplace=True) 


# %%


#df_read1[20].shift(periods=1,freq=30)


# %%


df_read1.index


# %%





# %%





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

# %%
def pairStockCloseMinus(x):
    if(len(x.close)<2):
        print(x.ts_code[0] + "None")
    print(x.ts_code[0], (x.close[1] - x.close[0]) / x.close[0])
    return 

df_read1.query("trade_date==20211109 or trade_date==20211111").groupby(["ts_code"]).apply(pairStockCloseMinus)


# %%


stock_secion_df=df_read1.query("trade_date==20211109 or trade_date==20211111").groupby(["ts_code"]).apply(pairStockCloseMinus)
show(stock_secion_df)


# %%
def pairStockCloseMinus(x,y):
    if(len(x.close)<2):
        print(x.ts_code[0] + "None"+y)
    print(x.ts_code[0], (x.close[1] - x.close[0]) / x.close[0])



# %%
stock_secion_df=df_read1.query("trade_date==20211109 or trade_date==20211111").groupby(["ts_code"]).apply(pairStockCloseMinus)

# %%
print(stock_secion_df.shape)

# %%

# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%


df_read1["2021-21-11"]


# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%


close2=df_read1["2022-01-07"][['ts_code','close']]
print(close2.to_string())


# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%


dd11=df_read1["2022-01-05":"2022-01-08"].groupby(["ts_code"])['close'].apply(applyfunc)


# %%





# %%


df_read1


# %%





# %%





# %%


dd11


# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%


df_read1["2022-01-04":"2022-01-05"].groupby(['ts_code'])["close"].transform(lambda x: x-x)


# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%





# %%


# >>> df = pd.DataFrame({'A': a, 'B': b}, index=[0])
# >>> df
#    A  B
# 0  2  3

# >>> df = pd.DataFrame({'A': [a], 'B': [b]})
# >>> df
#    A  B
# 0  2  3


# %%


df_test = pd.DataFrame(
    {
        "group": [11,22],
        #"date1": pd.to_datetime("2020-01-02","2020-01-03")
        "date1": pd.Series(["2020-01-02","2020-01-03"],dtype='datetime64[ns]')

    }
)
df_test


# %%


df_test[[(df_test['date1']==pd.to_datetime("2020-01-02"))]]


# %%





# %%


df_test['date1']==pd.to_datetime("2020-01-02")


# %%




