



from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String
meta = MetaData()

# deprecated
stockinfobase_table = Table(
   'stockinfobase',
   meta,
   Column('ts_code', String, primary_key = True),
   Column('symbol', String),
   Column('name', String),
   Column('area', String),
   Column('industry', String),
   Column('list_date', String),
   Column('composition', String),
)