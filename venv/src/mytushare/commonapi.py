import json

import tushare as ts

import os
import sys
# 使用绝对路径确保调试时能找到模块
_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(_base_dir)

# 添加项目根目录到sys.path，以便导入PatternAnalysis.config
_project_root = os.path.dirname(_base_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
from BaseFacility.Logconfig.logconfig import *;
from orm.dbmanager import stocktradebaseinfo_popyo as st;
from orm.dbmanager import dborm as db;
from orm.dbmanager.stockbaseinfo_popyo import *;
from sqlalchemy.dialects.mysql import insert;
from chinese_calendar import is_workday, is_holiday;
from datetime import datetime;

# 从配置文件读取Tushare配置
try:
    from PatternAnalysis.config import TUSHARE_CONFIG
    _token = TUSHARE_CONFIG.get('token')
    _http_url = TUSHARE_CONFIG.get('http_url', 'http://lianghua.9vvn.com')
except ImportError:
    # 如果无法导入配置，使用备用配置
    _token = "18bee8fb83e34ae5596920c58b6c799b30a99f1a0b3a2031168331f3f83d"
    _http_url = 'http://lianghua.9vvn.com'

ts.set_token(_token)
pro = ts.pro_api()
pro._DataApi__token = _token
pro._DataApi__http_url = _http_url
logger = logging.getLogger(__name__)

def Gfunc_timeGenerate(begin,end):
    dates = pro.query('trade_cal', start_date=begin, end_date=end)
    datelist = dates["cal_date"].values.tolist()
    return datelist

# @StockTimeExecutor_api not in user condition
# deprecated
class StockTimeExecutor_api:
    def __init__(self,func):
        self.func=func

    def __call__(self, begin_date:str,end_date:str):
        self.func(Gfunc_timeGenerate(begin_date,end_date))

#  trade time sequence function executor
def DoStockTimeExecute(begin_date:str,end_date:str):
    def StockFuncExecute(func):
        # 调用tushar的接口，返回交易日的日期列表
        dates = pro.query('trade_cal', start_date=begin_date, end_date=end_date)
        datelist = dates["cal_date"].values.tolist()
        def function_wrapper():
            for date in datelist:
                func(date)
        return function_wrapper
    return StockFuncExecute

# 获取tushare的股票交易信息：股票代码、收盘价格、成交量、最高、最低，就是日数据，缺市值，ATR，macd等指标
def GetStockTrade(date):
    tmp = [];
    df = pro.daily(trade_date=date);

    for x in df.to_dict('records'):
        tmp.append(st.stocktradebaseinfo(x));
    db.DBSession.bulk_save_objects(tmp);
    logging.debug("save %s successed：" %date)
    # db.DBSession.bulk_insert_mappings(st.stocktradebaseinfo, [st.stocktradebaseinfo(i) for i in df.to_dict('records')]);
    db.DBSession.commit();
    #print(df);



# 获取tushare的股票基本信息：股票代码、股票名字、地区、上市时间
def GetStockBaseInfo():
    tmp = [];
    df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,list_date');
    df["ts_code"] = df["ts_code"].apply(lambda x: x[0:6])
    df["last_update_time"] = datetime.now()
    for x in df.to_dict('records'):
        tmp.append(x);
    stmt = insert(stockinfobase).values(tmp)
    stmt = stmt.on_duplicate_key_update(
        tsCode=stmt.inserted.ts_code,
        name=stmt.inserted.name,
        area=stmt.inserted.area,
        industry=stmt.inserted.industry,
        list_date=stmt.inserted.list_date,
        last_update_time=stmt.inserted.last_update_time
    )
    db.DBSession.execute(stmt)
    db.DBSession.commit();

# class tushare_api:
#     def stocktradedailyinfo(self):

# 获取tushare的股票基本信息：股票代码、股票名字、地区、上市时间
def GetStockBaseInfoTest():
    json_str = '{"ts_code": "689009", "symbol": "689009", "name": "九号公司-WD", "area": "北京", "industry": "摩托车", "list_date": "20201029", "last_update_time": "2025-03-11 23:34:42.725829"}'
    dt = json.loads(json_str)
    stmt = insert(stockinfobase(dt))
    stmt = stmt.on_duplicate_key_update(
        TS_CODE=stmt.inserted.tsCode,
        NAME=stmt.inserted.name,
        AREA=stmt.inserted.area,
        INDUSTRY=stmt.inserted.industry,
        LIST_DATE=stmt.inserted.listDate,
        last_update_time=stmt.inserted.lastUpdateTime
    )
    db.DBSession.execute(stmt)
    db.DBSession.commit();

def createWorkDate(begin_date,end_date):
    datetag = begin_date
    while (datetag != end_date):
        if (is_workday(datetag)):
            yield datetag.strftime("%Y%m%d");
        datetag += datetime.timedelta(days=1);


if  __name__ == '__main__':
    # # not include 2020,12,30
    # begind = datetime.date(2022,1,4);
    # endd = datetime.date(2022,1,5);
    while(1):
        logger.info("开始tushare接口获取股票数据");
        logger.info("请选择下面选项，输入数字");
        logger.info("1、股票基本信息，代码、行业、发行日期、地区");
        logger.info("2、股票沪深创的日线数据，代码、成交量、最高价、最低价");
        use_choice = input("请输入数字")
        if('1'==use_choice):
            GetStockBaseInfo()
            logger.info("获取股票基本信息，代码、行业、发行日期、地区结束");
        if('2'==use_choice):
            dayrange = DoStockTimeExecute("20250121", "20260126")
            run_stocktrade = dayrange(GetStockTrade)
            run_stocktrade()
        if ('3' == use_choice):
            GetStockBaseInfoTest()
    # begin = "20220105"
    # end = "20220213"
    # dates = pro.query('trade_cal', start_date=begin, end_date=end)
    # datelist = dates["    cal_date"].values.tolist()
    # for dy in datelist:
    #     # date_time_obj = datetime.datetime.strptime(dy, '%Y%m%d')
    #     GetStockTrade(dy);
    #endd = datetime.date(2021,12,9);
    # for n in createWorkDate(begind,endd):
    #
    #GetStockBaseInfo();



