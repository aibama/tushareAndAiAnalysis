from sqlalchemy import *

from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class stockinfobase(Base):
    __tablename__ = 'stockinfobase';
    # id = Column(Integer, primary_key=True);
    tsCode = Column('ts_code',primary_key=True);
    symbol = Column('symbol');
    name = Column('name');
    area = Column('area');
    industry = Column('industry');
    list_date = Column('list_date');
    composition = Column('composition');
    lastUpdateTime = Column('last_update_time',default=datetime.now());
    def __init__(self,dict):
        self.tsCode=dict.get("ts_code");
        self.symbol = dict.get("symbol");
        self.name = dict.get("name");
        self.industry = dict.get("industry");
        self.area = dict.get("area");
        self.listDate = dict.get("list_date");
        self.composition = dict.get("composition");
        self.lastUpdateTime = dict.get("last_update_time")
