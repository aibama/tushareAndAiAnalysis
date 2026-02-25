# ETF份额规模 ORM 模型
from sqlalchemy import Column, String, DateTime, Float, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class etf_share_size_info(Base):
    """ETF份额规模数据表"""
    __tablename__ = 'etf_share_size_info'
    
    id = Column(String(36), primary_key=True)  # UUID
    ts_code = Column(String(20), nullable=False, comment='ETF代码')
    trade_date = Column(String(8), nullable=False, comment='交易日期')
    etf_name = Column(String(100), comment='ETF名称')
    total_share = Column(Float, comment='总份额')
    total_size = Column(Float, comment='总规模')
    exchange = Column(String(10), comment='交易所')
    last_update_time = Column(DateTime, comment='最后更新时间')
    
    def __repr__(self):
        return f"<etf_share_size_info(ts_code='{self.ts_code}', trade_date='{self.trade_date}', total_size={self.total_size})>"


class etf_share_size_base(Base):
    """ETF份额规模基础表"""
    __tablename__ = 'etf_share_size_base'
    
    id = Column(String(36), primary_key=True)
    ts_code = Column(String(20), nullable=False)
    trade_date = Column(String(8), nullable=False)
    etf_name = Column(String(100))
    total_share = Column(Float)
    total_size = Column(Float)
    exchange = Column(String(10))
    last_update_time = Column(DateTime)
    
    def __repr__(self):
        return f"<etf_share_size_base(ts_code='{self.ts_code}', trade_date='{self.trade_date}')>"
