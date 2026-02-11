import json
import urllib3

from crawling.entity.FavoriteCodeRank import FavoriteCodeRank
from orm.dbmanager import dborm as db;
import logging

#
# def convert_headers(raw_header):
#     header = dict()
#     for line in raw_header.split("\n"):
#         a,b = line.split(":",1)
#         header[a.strip()] = b.strip()
#     return header



header = {"authority":"emappdata.eastmoney.com",
"sec-ch-ua":"\" Not A;Brand\";v=\"99\", \"Chromium\";v=\"99\", \"Google Chrome\";v=\"99\"",
"sec-ch-ua-mobile":"?1",
"user-agent":"Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.74 Mobile Safari/537.36",
"sec-ch-ua-platform":"\"Android\"",
"content-type":"application/json",
"accept":"*/*",
"origin":"https://vipmoney.eastmoney.com",
"sec-fetch-site":"same-site",
"sec-fetch-mode":"cors",
"sec-fetch-dest":"empty",
"referer":"https://vipmoney.eastmoney.com/",
"accept-language":"zh-CN,zh;q=0.9"
        }

body = {"appId":"appId01","globalId":"786e4c21-70dc-435a-93bb-38","marketType":"","pageNo":1,"pageSize":100}

body_encode = json.dumps(body).encode('utf-8')

class emFavoriteCodeRank:
    def getSaveFavoriteCodeRank(self):
        http = urllib3.PoolManager()
        r = http.request(
            'POST',
            'https://emappdata.eastmoney.com/stockrank/getAllCurrentList',
            body=body_encode,
            headers=header
        )
        r = json.loads(r.data.decode('utf-8'))
        stockrank = FavoriteCodeRank(r['data'])
        db.DBSession.add(stockrank)
        db.DBSession.commit()

if  __name__ == '__main__':
    http = urllib3.PoolManager()
    r = http.request(
        'POST',
        'https://emappdata.eastmoney.com/stockrank/getAllCurrentList',
        body=body_encode,
        headers=header
    )
    #print(json.loads(r.data.decode('utf-8')))
    r = json.loads(r.data.decode('utf-8'))
    stockrank = FavoriteCodeRank(r['data'])
    db.DBSession.add(stockrank)
    db.DBSession.commit()
    print(stockrank)