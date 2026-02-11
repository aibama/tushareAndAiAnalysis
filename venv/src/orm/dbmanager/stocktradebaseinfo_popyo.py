from sqlalchemy import *
from sqlalchemy.orm import *

import uuid
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()


class GUID(TypeDecorator):
    impl = String(32)

    def process_bind_param(self, value, dialect):
        if value is not None:
            return "%.32x" % value
        else:
            return None

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            return uuid.UUID(value)

class stocktradebaseinfo(Base):
    __tablename__ = 'stocktradedailyinfo';

    id = Column(Integer, primary_key=True);
    ts_code = Column(String);
    trade_date = Column('trade_date',Date);
    open = Column(String);
    high = Column(String);
    low = Column(String);
    close = Column(String);
    pre_close = Column(String);
    change = Column('echange');
    pct_chg = Column(String);
    vol = Column('vol');
    amount = Column('amount');

    def __init__(self,ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount):
        self.ts_code=ts_code;
        self.trade_date=trade_date;
        self.open=open;
        self.high=high;
        self.low=low;
        self.close=close;
        self.pre_close=pre_close;
        self.change=change;
        self.pct_chg=pct_chg;
        self.vol=vol;
        self.amount=amount;

    def __init__(self,dict):
        self.ts_code=dict.get("ts_code");
        self.trade_date = dict.get("trade_date");
        self.open = dict.get("open");
        self.high = dict.get("high");
        self.low = dict.get("low");
        self.close = dict.get("close");
        self.pre_close = dict.get("pre_close");
        self.change = dict.get("change");
        self.pct_chg = dict.get("pct_chg");
        self.vol = dict.get("vol");
        self.amount = dict.get("amount");

