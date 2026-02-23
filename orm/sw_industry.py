"""
申万行业分类 ORM 模型
表名: sw_industry
描述: 申万行业分类标准树
"""

from sqlalchemy import Column, String, Integer, SmallInteger, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class SwIndustry(Base):
    """申万行业分类标准树"""
    __tablename__ = 'sw_industry'

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment='代理主键')
    
    # 行业节点信息
    node_code = Column(String(20), nullable=False, unique=True, comment='节点唯一编码（如: 801020.SI）')
    node_name = Column(String(100), nullable=False, comment='节点名称')
    level = Column(SmallInteger, nullable=False, comment='层级: 1-一级行业, 2-二级行业, 3-三级行业')
    parent_code = Column(String(20), default=None, comment='父节点编码（一级行业的父节点为NULL）')
    
    # 层级路径（推导字段）
    full_path = Column(String(200), comment='层级路径（推导字段，便于查询）')
    
    # 层级信息（冗余字段，便于筛选）
    l1_code = Column(String(10), comment='一级行业代码')
    l1_name = Column(String(50), comment='一级行业名称')
    l2_code = Column(String(10), comment='二级行业代码')
    l2_name = Column(String(50), comment='二级行业名称')
    l3_code = Column(String(10), comment='三级行业代码')
    l3_name = Column(String(50), comment='三级行业名称')
    
    # 状态信息
    is_valid = Column(SmallInteger, default=1, comment='是否有效（分类可能被修订）')
    
    # 时间戳
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 索引
    __table_args__ = (
        UniqueConstraint('node_code', name='uk_node_code'),
        Index('idx_level', 'level'),
        Index('idx_parent', 'parent_code'),
        Index('idx_l1', 'l1_code'),
        Index('idx_l3', 'l3_code'),
    )

    def __repr__(self):
        return f"<SwIndustry(node_code='{self.node_code}', node_name='{self.node_name}', level={self.level})>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'node_code': self.node_code,
            'node_name': self.node_name,
            'level': self.level,
            'parent_code': self.parent_code,
            'full_path': self.full_path,
            'l1_code': self.l1_code,
            'l1_name': self.l1_name,
            'l2_code': self.l2_code,
            'l2_name': self.l2_name,
            'l3_code': self.l3_code,
            'l3_name': self.l3_name,
            'is_valid': self.is_valid,
            'update_time': self.update_time.strftime('%Y-%m-%d %H:%M:%S') if self.update_time else None
        }
