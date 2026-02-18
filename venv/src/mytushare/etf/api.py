# ETF接口主入口文件
# 整合三个ETF相关接口：
# 1. fund_daily - ETF日线行情
# 2. etf_share_size - ETF份额规模
# 3. fund_adj - 基金复权因子

from .fund_daily import ETFDailyAPI, fetch_fund_daily, fetch_fund_daily_by_dates
from .etf_share_size import ETFShareSizeAPI, fetch_etf_share_size, fetch_etf_share_size_by_dates
from .fund_adj import FundAdjAPI, fetch_fund_adj, fetch_fund_adj_by_dates

__all__ = [
    'ETFDailyAPI',
    'ETFShareSizeAPI', 
    'FundAdjAPI',
    'fetch_fund_daily',
    'fetch_fund_daily_by_dates',
    'fetch_etf_share_size',
    'fetch_etf_share_size_by_dates',
    'fetch_fund_adj',
    'fetch_fund_adj_by_dates'
]


def run_etf_incremental_job(ts_code: str, start_date: str, end_date: str = None):
    """
    运行ETF增量更新任务
    
    Args:
        ts_code: ETF代码
        start_date: 开始日期
        end_date: 结束日期
    """
    print(f"开始更新 {ts_code} 的数据...")
    print(f"日期范围: {start_date} - {end_date}")
    
    # 1. 更新日线行情
    print("\n=== 更新ETF日线行情 ===")
    daily_api = ETFDailyAPI(ts_code=ts_code)
    daily_api.get_daily_incremental(start_date=start_date, end_date=end_date)
    
    # 2. 更新份额规模
    print("\n=== 更新ETF份额规模 ===")
    share_api = ETFShareSizeAPI(ts_code=ts_code)
    share_api.get_share_size_incremental(start_date=start_date, end_date=end_date)
    
    print(f"\n{ts_code} 数据更新完成!")


def run_etf_full_job(ts_code: str, start_date: str, end_date: str = None):
    """
    运行ETF全量更新任务（不过滤已存在数据）
    
    Args:
        ts_code: ETF代码
        start_date: 开始日期
        end_date: 结束日期
    """
    print(f"开始全量更新 {ts_code} 的数据...")
    
    # 1. 更新日线行情
    print("\n=== 更新ETF日线行情 ===")
    daily_api = ETFDailyAPI(ts_code=ts_code)
    df = daily_api.get_daily(start_date=start_date, end_date=end_date, filter_existing=False)
    print(df)
    
    # 2. 更新份额规模
    print("\n=== 更新ETF份额规模 ===")
    share_api = ETFShareSizeAPI(ts_code=ts_code)
    df = share_api.get_share_size(start_date=start_date, end_date=end_date, filter_existing=False)
    print(df)
    
    print(f"\n{ts_code} 全量更新完成!")


if __name__ == '__main__':
    # 使用示例
    print("=" * 50)
    print("ETF接口使用示例")
    print("=" * 50)
    
    # 示例1：使用API类
    print("\n【示例1】使用API类获取数据")
    api = ETFDailyAPI(ts_code='510330.SH')
    df = api.get_daily(start_date='20250101', end_date='20250618')
    print(df.head())
    
    # 示例2：增量更新
    print("\n【示例2】增量更新（过滤已存在数据）")
    run_etf_incremental_job(ts_code='510330.SH', start_date='20250601', end_date='20250618')
    
    # 示例3：获取指定日期所有ETF份额规模
    print("\n【示例3】获取指定日期所有ETF份额规模")
    share_api = ETFShareSizeAPI()
    df = share_api.get_all_etf_on_date(trade_date='20251224', exchange='SSE')
    print(df.head())
    
    # 示例4：获取复权因子
    print("\n【示例4】获取基金复权因子")
    adj_api = FundAdjAPI(ts_code='513100.SH')
    df = adj_api.get_adj(start_date='20190101', end_date='20190926')
    print(df.head())
