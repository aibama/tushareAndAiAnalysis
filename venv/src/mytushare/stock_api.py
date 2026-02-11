






class mytushare_api:
    def __init__(self,func):
        self.func=func

    def __call__(self, begin_date:str,end_date:str):
        self.func(Gfunc_timeGenerate(begin_date,end_date))