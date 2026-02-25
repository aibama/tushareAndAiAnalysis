# ETF基金基本信息 ORM 模型
# 表名: fund_etf_info
# 描述: 国内ETF基础信息，包括QDII

from sqlalchemy import Column, String, Date, DECIMAL, Integer
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class FundEtfInfo(Base):
    """ETF基金基本信息表"""
    __tablename__ = 'fund_etf_info'

    # 主键和基本字段
    ts_code = Column(String(20), primary_key=True, comment='基金交易代码')
    csname = Column(String(50), nullable=False, comment='ETF中文简称')
    extname = Column(String(100), default=None, comment='ETF扩位简称(对应交易所简称)')
    cname = Column(String(200), nullable=False, comment='基金中文全称')
    
    # 指数信息
    index_code = Column(String(20), default=None, comment='ETF基准指数代码')
    index_name = Column(String(200), default=None, comment='ETF基准指数中文全称')
    
    # 日期信息
    setup_date = Column(Date, default=None, comment='设立日期(格式:YYYYMMDD)')
    list_date = Column(Date, default=None, comment='上市日期(格式:YYYYMMDD)')
    
    # 状态和交易所
    list_status = Column(String(1), default=None, comment='存续状态(L上市 D退市 P待上市)')
    exchange = Column(String(10), default=None, comment='交易所(上交所SH 深交所SZ)')
    
    # 管理人和托管人
    mgr_name = Column(String(100), default=None, comment='基金管理人简称')
    custod_name = Column(String(200), default=None, comment='基金托管人名称')
    
    # 费用信息
    mgt_fee = Column(DECIMAL(5, 4), default=None, comment='基金管理人收取的管理费率')
    
    # ETF类型
    etf_type = Column(String(20), default=None, comment='基金投资通道类型(境内、QDII)')

    def __repr__(self):
        return f"<FundEtfInfo(ts_code='{self.ts_code}', csname='{self.csname}', exchange='{self.exchange}')>"
