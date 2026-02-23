"""
股票-申万行业关系 ORM 模型
表名: stock_sw_relation
描述: 股票-申万行业成分历史关系表
"""

from sqlalchemy import Column, String, Integer, SmallInteger, Date, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class StockSwRelation(Base):
    """股票-申万行业成分历史关系表"""
    __tablename__ = 'stock_sw_relation'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 股票和行业信息
    ts_code = Column(String(20), nullable=False, comment='股票代码')
    sw_node_code = Column(String(20), nullable=False, comment='申万行业节点编码（关联sw_industry.node_code）')
    
    # 日期信息
    in_date = Column(Date, nullable=False, comment='纳入日期')
    out_date = Column(Date, default=None, comment='剔除日期（NULL表示当前仍在成分内）')
    
    # 状态信息
    is_latest = Column(SmallInteger, default=0, comment='是否最新成分关系（1是，0否）')
    
    # 创建时间
    create_time = Column(DateTime, default=datetime.now, comment='创建时间')

    # 索引
    __table_args__ = (
        UniqueConstraint('ts_code', 'sw_node_code', 'in_date', name='uk_stock_node_date'),
        Index('idx_ts_code_latest', 'ts_code', 'is_latest'),
        Index('idx_node_latest', 'sw_node_code', 'is_latest'),
        Index('idx_in_date', 'in_date'),
        Index('idx_out_date', 'out_date'),
    )

    def __repr__(self):
        return f"<StockSwRelation(ts_code='{self.ts_code}', sw_node_code='{self.sw_node_code}', in_date='{self.in_date}')>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'ts_code': self.ts_code,
            'sw_node_code': self.sw_node_code,
            'in_date': self.in_date.strftime('%Y-%m-%d') if self.in_date else None,
            'out_date': self.out_date.strftime('%Y-%m-%d') if self.out_date else None,
            'is_latest': self.is_latest,
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None
        }
