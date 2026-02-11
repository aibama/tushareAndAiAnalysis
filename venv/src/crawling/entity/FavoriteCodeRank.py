import datetime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import *
Base = declarative_base()

class FavoriteCodeRank(Base):
    __tablename__ = 'EMFavoriteCodeRank'
    rankdate=Column('rankdate',primary_key=True)
    favoriteCodeRankJson=Column('favoriteCodeRankJson')
    def __init__(self,data):
        self.rankdate = datetime.datetime.now().strftime("%Y-%m-%d")
        str_bank = ""
        self.favoriteCodeRankJson = str_bank.join(i['sc']+"," for i in data)
        # self.favoriteCodeRankJson = data

    def __str__(self):
        template = 'date: {0.rankdate} \n {0.favoriteCodeRankJson}'
        # return "date:",self.rankdate,self.favoriteCodeRankJson
        return template.format(self)
