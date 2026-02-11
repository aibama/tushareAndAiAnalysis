from sqlalchemy import Column, String, Integer, Date

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String,  create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

import logging

mysqlurl = 'mysql+pymysql://root:123456@localhost:3306/stockdata';

'''
# create an engine
engine = create_engine('mysql://localhost:3306/stockdata?serverTimezone=UTC')

# create a configured "Session" class
Session = sessionmaker(bind=engine)

# create a Session
session = Session()
'''

DBSession = scoped_session(sessionmaker())
engine = None
logger = logging.getLogger()
def init_sqlalchemy(dbname='sqlite:///sqlalchemy.db'):
    global engine
    engine = create_engine(dbname, echo=False)
    DBSession.remove()
    DBSession.configure(bind=engine, autoflush=False, expire_on_commit=False)
    logger.info("init_sqlalchemy successed!")
Session = sessionmaker(bind=engine)
session = Session()
init_sqlalchemy(mysqlurl)