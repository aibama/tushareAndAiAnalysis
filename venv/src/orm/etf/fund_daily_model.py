# ETF日线行情 ORM 模型
from sqlalchemy import Column, String, DateTime, Float, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class etf_daily_info(Base):
    """ETF日线行情数据表"""
    __tablename__ = 'etf_daily_info'
    
    id = Column(String(36), primary_key=True)  # UUID
    ts_code = Column(String(20), nullable=False, comment='ETF代码')
    trade_date = Column(String(8), nullable=False, comment='交易日期')
    open = Column(Float, comment='开盘价')
    high = Column(Float, comment='最高价')
    low = Column(Float, comment='最低价')
    close = Column(Float, comment='收盘价')
    pre_close = Column(Float, comment='前收盘价')
    change = Column(Float, comment='涨跌额')
    pct_chg = Column(Float, comment='涨跌幅')
    vol = Column(Float, comment='成交量')
    amount = Column(Float, comment='成交额')
    last_update_time = Column(DateTime, comment='最后更新时间')
    
    def __repr__(self):
        return f"<etf_daily_info(ts_code='{self.ts_code}', trade_date='{self.trade_date}', close={self.close})>"


class etf_daily_base(Base):
    """ETF日线基础信息表"""
    __tablename__ = 'etf_daily_base'
    
    id = Column(String(36), primary_key=True)
    ts_code = Column(String(20), nullable=False, comment='ETF代码')
    trade_date = Column(String(8), nullable=False, comment='交易日期')
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    pre_close = Column(Float)
    change = Column(Float)
    pct_chg = Column(Float)
    vol = Column(Float)
    amount = Column(Float)
    last_update_time = Column(DateTime)
    
    def __repr__(self):
        return f"<etf_daily_base(ts_code='{self.ts_code}', trade_date='{self.trade_date}')>"
