# 基金复权因子 ORM 模型
from sqlalchemy import Column, String, DateTime, Float, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class fund_adj_info(Base):
    """基金复权因子数据表"""
    __tablename__ = 'fund_adj_info'
    
    id = Column(String(36), primary_key=True)  # UUID
    ts_code = Column(String(20), nullable=False, comment='基金代码')
    trade_date = Column(String(8), nullable=False, comment='交易日期')
    adj_factor = Column(Float, comment='复权因子')
    last_update_time = Column(DateTime, comment='最后更新时间')
    
    def __repr__(self):
        return f"<fund_adj_info(ts_code='{self.ts_code}', trade_date='{self.trade_date}', adj_factor={self.adj_factor})>"


class fund_adj_base(Base):
    """基金复权因子基础表"""
    __tablename__ = 'fund_adj_base'
    
    id = Column(String(36), primary_key=True)
    ts_code = Column(String(20), nullable=False)
    trade_date = Column(String(8), nullable=False)
    adj_factor = Column(Float)
    last_update_time = Column(DateTime)
    
    def __repr__(self):
        return f"<fund_adj_base(ts_code='{self.ts_code}', trade_date='{self.trade_date}')>"
