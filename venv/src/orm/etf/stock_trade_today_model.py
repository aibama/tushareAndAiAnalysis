# 个股日线行情 ORM 模型
from sqlalchemy import Column, String, DateTime, Float, Numeric
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class stock_trade_today_info(Base):
    """个股日线行情数据表"""
    __tablename__ = 'stocktradetodayinfo'
    
    id = Column(String(36), primary_key=True)
    ts_code = Column(String(255), nullable=False, comment='股票代码')
    amount = Column(Numeric(16, 3), comment='成交额')
    echange = Column(Float, comment='涨跌额')
    close = Column(Float, comment='收盘价')
    high = Column(Float, comment='最高价')
    low = Column(Float, comment='最低价')
    open = Column(Float, comment='开盘价')
    pct_chg = Column(Float, comment='涨跌幅')
    pre_close = Column(Float, comment='前收盘价')
    trade_date = Column(DateTime(6), comment='交易日期')
    vol = Column(Numeric(16, 2), comment='成交量')
    trade_date_tmp = Column(DateTime(6), comment='临时交易日期')
    
    def __repr__(self):
        return f"<stock_trade_today_info(ts_code='{self.ts_code}', trade_date='{self.trade_date}', close={self.close})>"


class stock_trade_today_base(Base):
    """个股日线基础信息表"""
    __tablename__ = 'stocktradetodayinfo_base'
    
    id = Column(String(36), primary_key=True)
    ts_code = Column(String(255), nullable=False)
    amount = Column(Numeric(16, 3))
    echange = Column(Float)
    close = Column(Float)
    high = Column(Float)
    low = Column(Float)
    open = Column(Float)
    pct_chg = Column(Float)
    pre_close = Column(Float)
    trade_date = Column(DateTime(6))
    vol = Column(Numeric(16, 2))
    
    def __repr__(self):
        return f"<stock_trade_today_base(ts_code='{self.ts_code}', trade_date='{self.trade_date}')>"
