# ETF日线行情接口
# 接口：fund_daily
# 描述：获取ETF基金日线行情数据

import tushare as ts
import os
import sys
import logging
from datetime import datetime
from sqlalchemy.dialects.mysql import insert

# 设置路径
_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(_base_dir)

from BaseFacility.Logconfig.logconfig import logger
from orm.etf.fund_daily_model import etf_daily_base, etf_daily_info

# Tushare token设置
ts.set_token("27d26a829762ddae3467ca0950f08ae324e08452087f0642b0a859c3de92")
pro = ts.pro_api()
pro._DataApi__token = "27d26a829762ddae3467ca0950f08ae324e08452087f0642b0a859c3de92"
pro._DataApi__http_url = 'http://lianghua.9vvn.com'


def get_existing_dates(ts_code: str) -> set:
    """获取数据库中已有的交易日期"""
    try:
        result = etf_daily_info.query.filter_by(ts_code=ts_code).with_entities(
            etf_daily_info.trade_date
        ).all()
        return {r[0] for r in result}
    except Exception as e:
        logger.warning(f"获取已有日期失败: {e}")
        return set()


def save_fund_daily_data(df, ts_code: str):
    """保存ETF日线数据到数据库"""
    if df.empty:
        logger.info(f"没有数据需要保存 for {ts_code}")
        return
    
    tmp = []
    for x in df.to_dict('records'):
        record = etf_daily_info(
            ts_code=ts_code,
            trade_date=x.get('trade_date'),
            open=x.get('open'),
            high=x.get('high'),
            low=x.get('low'),
            close=x.get('close'),
            pre_close=x.get('pre_close'),
            change=x.get('change'),
            pct_chg=x.get('pct_chg'),
            vol=x.get('vol'),
            amount=x.get('amount'),
            last_update_time=datetime.now()
        )
        tmp.append(record)
    
    try:
        # 使用upsert方式插入，避免重复
        stmt = insert(etf_daily_info).values([{
            'ts_code': x.get('ts_code'),
            'trade_date': x.get('trade_date'),
            'open': x.get('open'),
            'high': x.get('high'),
            'low': x.get('low'),
            'close': x.get('close'),
            'pre_close': x.get('pre_close'),
            'change': x.get('change'),
            'pct_chg': x.get('pct_chg'),
            'vol': x.get('vol'),
            'amount': x.get('amount'),
            'last_update_time': datetime.now()
        } for x in df.to_dict('records')])
        stmt = stmt.on_duplicate_key_update(
            open=stmt.inserted.open,
            high=stmt.inserted.high,
            low=stmt.inserted.low,
            close=stmt.inserted.close,
            pre_close=stmt.inserted.pre_close,
            change=stmt.inserted.change,
            pct_chg=stmt.inserted.pct_chg,
            vol=stmt.inserted.vol,
            amount=stmt.inserted.amount,
            last_update_time=stmt.inserted.last_update_time
        )
        from orm.dbmanager import dborm as db
        db.DBSession.execute(stmt)
        db.DBSession.commit()
        logger.info(f"成功保存 {len(df)} 条 {ts_code} 日线数据")
    except Exception as e:
        logger.error(f"保存数据失败: {e}")
        from orm.dbmanager import dborm as db
        db.DBSession.rollback()


def fetch_fund_daily(ts_code: str, start_date: str, end_date: str = None, 
                     fields: str = None, filter_existing: bool = True):
    """
    获取ETF日线行情数据
    
    Args:
        ts_code: ETF代码，如 '510330.SH'
        start_date: 开始日期，格式 YYYYMMDD
        end_date: 结束日期，格式 YYYYMMDD，默认为None表示到当前
        fields: 输出字段，默认为None表示全部字段
        filter_existing: 是否过滤已存在的数据，默认为True
    
    Returns:
        DataFrame: ETF日线数据
    """
    try:
        # 构建查询参数
        params = {
            'ts_code': ts_code,
            'start_date': start_date,
            'end_date': end_date
        }
        if fields:
            params['fields'] = fields
        
        # 获取数据
        df = pro.fund_daily(**params)
        
        if df is None or df.empty:
            logger.info(f"没有获取到数据 for {ts_code}")
            return df
        
        # 如果需要过滤已存在的数据
        if filter_existing:
            existing_dates = get_existing_dates(ts_code)
            if existing_dates:
                df = df[~df['trade_date'].astype(str).isin(existing_dates)]
                logger.info(f"过滤后剩余 {len(df)} 条数据需要保存")
        
        # 保存到数据库
        if not df.empty:
            save_fund_daily_data(df, ts_code)
        
        return df
        
    except Exception as e:
        logger.error(f"获取ETF日线数据失败: {e}")
        raise


def fetch_fund_daily_by_dates(ts_code: str, start_date: str, end_date: str = None,
                              fields: str = None):
    """
    按日期获取ETF日线数据（逐日获取，支持增量更新）
    
    Args:
        ts_code: ETF代码，如 '510330.SH'
        start_date: 开始日期，格式 YYYYMMDD
        end_date: 结束日期，格式 YYYYMMDD
        fields: 输出字段
    """
    try:
        # 获取已有日期
        existing_dates = get_existing_dates(ts_code)
        logger.info(f"已存在 {len(existing_dates)} 条 {ts_code} 的日线数据")
        
        # 获取交易日历
        if end_date:
            date_range = f"{start_date}:{end_date}"
        else:
            date_range = start_date
            
        trade_cal = pro.query('trade_cal', start_date=start_date, end_date=end_date)
        trade_dates = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()
        
        logger.info(f"交易日历中有 {len(trade_dates)} 个交易日")
        
        # 逐日获取数据
        total_saved = 0
        for trade_date in trade_dates:
            if trade_date in existing_dates:
                logger.debug(f"跳过已存在的日期: {trade_date}")
                continue
            
            try:
                params = {'ts_code': ts_code, 'trade_date': trade_date}
                if fields:
                    params['fields'] = fields
                
                df = pro.fund_daily(**params)
                
                if df is not None and not df.empty:
                    save_fund_daily_data(df, ts_code)
                    total_saved += len(df)
                
            except Exception as e:
                logger.warning(f"获取 {trade_date} 数据失败: {e}")
                continue
        
        logger.info(f"共保存 {total_saved} 条 {ts_code} 日线数据")
        return total_saved
        
    except Exception as e:
        logger.error(f"按日期获取ETF日线数据失败: {e}")
        raise


class ETFDailyAPI:
    """ETF日线行情API类"""
    
    def __init__(self, ts_code: str = None):
        """
        初始化ETF日线API
        
        Args:
            ts_code: ETF代码，如 '510330.SH'
        """
        self.ts_code = ts_code
    
    def get_daily(self, start_date: str, end_date: str = None, 
                  fields: str = None, filter_existing: bool = True):
        """
        获取ETF日线行情
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            fields: 输出字段
            filter_existing: 是否过滤已存在数据
            
        Returns:
            DataFrame
        """
        if not self.ts_code:
            raise ValueError("请设置ts_code")
        return fetch_fund_daily(
            ts_code=self.ts_code,
            start_date=start_date,
            end_date=end_date,
            fields=fields,
            filter_existing=filter_existing
        )
    
    def get_daily_incremental(self, start_date: str, end_date: str = None,
                               fields: str = None):
        """
        增量获取ETF日线行情（逐日获取）
        """
        if not self.ts_code:
            raise ValueError("请设置ts_code")
        return fetch_fund_daily_by_dates(
            ts_code=self.ts_code,
            start_date=start_date,
            end_date=end_date,
            fields=fields
        )


if __name__ == '__main__':
    # 测试代码
    api = ETFDailyAPI(ts_code='510330.SH')
    
    # 获取2025年以来的数据
    print("获取ETF日线行情数据...")
    df = api.get_daily(start_date='20250101', end_date='20250618', 
                       fields='trade_date,open,high,low,close,vol,amount')
    print(df)
    
    print("\n增量获取数据...")
    count = api.get_daily_incremental(start_date='20250601', end_date='20250618')
    print(f"新增 {count} 条记录")
