#!/usr/bin/env python
# coding: utf-8

# In[11]:


import requests
import lxml.html
from selectolax.parser import HTMLParser
import re
# In[12]:
from orm.dbmanager import dborm as db;
from sqlalchemy.sql import text
from orm.dbmanager.stockbaseinfo_popyo import stockinfobase
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import table, column, select, update, insert
from orm.dbmanager import stockinfobase_table

response = requests.get('http://vip.stock.finance.sina.com.cn/corp/go.php/vII_NewestComponent/indexid/000852.phtml')


selector = "#NewStockTable > tbody > *  "
# selector = "#NewStockTable > tbody > * > td.head > *  "
p = re.compile(r'<div align=\"center\">(.*?)</div>')
resutl_list = list()
for node in HTMLParser(response.text).css(selector):
    result = p.search(node.html)
    resutl_list.append(result.group(1))

# 成功
# conn = db.engine.connect()
# stmt = update(stockinfobase).where(stockinfobase.ts_code=="000002").values(composition = "zz100")
# conn.execute(stmt)

# conn = db.engine.connect()
update(stockinfobase).where(stockinfobase.ts_code=="000002").values(composition = "zz100")
# conn.execute(stmt)

# result = session.query(stockinfobase).filter(stockinfobase.ts_code.in_(resutl_list))
# for row in result:d
#     row.composition="zz100"

#session.update(stockinfobase).where(stockinfobase.ts_code=="000001").values(composition = "zz100")
#AttributeError: type object 'stockinfobase' has no attribute 'update'
#stockinfobase.update().where(stockinfobase.ts_code=="000001").values(composition = "zz100")
# stmt = text(r'update table stockinfobase set composition = "zz100" where substring (ts_code,1,6) in (:value1)')
# db.DBSession.execute(stmt,value1 = resutl_list)
# db.DBSession.commit()
print(resutl_list)
# In[4]:






