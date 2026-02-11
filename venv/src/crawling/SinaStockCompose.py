import requests
from selectolax.parser import HTMLParser
from sqlalchemy.sql.expression import table, column, select, update, insert
from orm.dbmanager import dborm as db;
from orm.dbmanager.stockbaseinfo_popyo import stockinfobase
import collections
import logging
import re
#科创50
kc50SinaUrl="http://vip.stock.finance.sina.com.cn/corp/go.php/vII_NewestComponent/indexid/000688.phtml"
#创业50
cy50SinaUrl="http://vip.stock.finance.sina.com.cn/corp/go.php/vII_NewestComponent/indexid/399673.phtml"
#中小100
zx100SinaUrl="http://vip.stock.finance.sina.com.cn/corp/go.php/vII_NewestComponent/indexid/399005.phtml"
#中证1000
zz1000SinaUrl="http://vip.stock.finance.sina.com.cn/corp/go.php/vII_NewestComponent/indexid/000852.phtml"
#中证1000 page2
zz1000SinaUrlPage2Prefex = "http://vip.stock.finance.sina.com.cn/corp/view/vII_NewestComponent.php?page="
zz1000SinaUrlPage2Patch = "&indexid=000852"

# zz1000SinaUrlPage2 = "http://vip.stock.finance.sina.com.cn/corp/view/vII_NewestComponent.php?page=2&indexid=000852"

urllist = [zz1000SinaUrl,zx100SinaUrl]
# zx100 have duplicatied value with zz1000
# urldict = {"kc50":kc50SinaUrl,"cy50":cy50SinaUrl,"zx100":zx100SinaUrl,"zz1000":zz1000SinaUrl}
urldict = {"kc50":kc50SinaUrl,"cy50":cy50SinaUrl,"zz1000":zz1000SinaUrl}

logger = logging.getLogger()

class SinaStockCompose:

    def __doc__(self):
        return "爬取新浪静态页面，新浪有中证1000成分股"

    # 爬取和保存新浪中证1000成分股
    # todo 日志标签 记录函数抛出的可能错误：
    #  response 没有记录
    #  解析错误
    #  orm api 有变化
    def crawStockComposition(self,target:str,url)->list():
        resutl_list = list()
        logger.info(self.__doc__())
        if(target!="zz1000"):
            response = requests.get(
                url)
            selector = "#NewStockTable > tbody > *  "
            p = re.compile(r'<div align=\"center\">(.*?)</div>')
            for node in HTMLParser(response.text).css(selector):
                result = p.search(node.html)
                resutl_list.append(result.group(1))
            conn = db.engine.connect()
            stmt = update(stockinfobase).where(stockinfobase.ts_code.in_(resutl_list)).values(composition=target)
            conn.execute(stmt)
        else:
            # 50 per page ,so remain 19page counting to 1000code together
            for i in range(1,20):
                if i==1:
                    response = requests.get(
                        url)
                else:
                    response = requests.get(
                        zz1000SinaUrlPage2Prefex+str(i)+zz1000SinaUrlPage2Patch)
                selector = "#NewStockTable > tbody > *  "
                p = re.compile(r'<div align=\"center\">(.*?)</div>')
                for node in HTMLParser(response.text).css(selector):
                    result = p.search(node.html)
                    resutl_list.append(result.group(1))
                conn = db.engine.connect()
                stmt = update(stockinfobase).where(stockinfobase.ts_code.in_(resutl_list)).values(composition=target)
                conn.execute(stmt)
        return resutl_list

    # 爬取和保存新浪中证1000成分股
    # use global variale
    def docrawStockComposition(self):
        for k, v in urldict.items():
            self.crawStockComposition(k, v)

if  __name__ == '__main__':
    ssc = SinaStockCompose()
    compaList1 = list()
    compaList2 = list()

    # compare zz1000 have same value with zx100
    # for x, y in zip(urllist, urllist[1:]):
    #     compaList1 = ssc.crawStockComposition(x)
    #     compaList2 = ssc.crawStockComposition(y)
    #     combine=compaList1+compaList2
    #     print("differ by ",x,"and",y)
    #     print([item for item, count in collections.Counter(combine).items() if count > 1])
        # print (x,y)

    # compaList1 = ssc.crawStockComposition("zx100",urldict["zx100"])
    # compaList2 = ssc.crawStockComposition("zz1000",urldict["zz1000"])
    # combine=compaList1+compaList2
    # print("differ by zx100 and zz1000")
    # print([item for item, count in collections.Counter(combine).items() if count > 1])

    for k, v in urldict.items():
        ssc.crawStockComposition(k,v)

    # ssc = SinaStockCompose()
    # ssc.urldict_do()