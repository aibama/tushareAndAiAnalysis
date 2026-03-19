"""
K线图数据服务

提供日K线图所需的数据接口，基于stocktradetodayinfo表结构。
支持多种K线类型（日K、周K、月K）和时间范围查询。
"""
import logging
from typing import List, Dict, Optional
from datetime import date, datetime, timedelta
from dataclasses import dataclass

import pandas as pd
import numpy as np

from PatternAnalysis.config import DB_CONFIG
from PatternAnalysis.data_access import get_engine

logger = logging.getLogger(__name__)


# ============== 数据模型 ==============

@dataclass
class KLineItem:
    """K线数据项"""
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    pct_chg: Optional[float] = None
    pre_close: Optional[float] = None


@dataclass
class KLineResponse:
    """K线图响应数据"""
    ts_code: str
    kline_type: str  # 'daily', 'weekly', 'monthly'
    start_date: str
    end_date: str
    data: List[Dict]
    total: int


# ============== K线数据获取 ==============

def get_daily_kline(
    ts_code: str,
    start_date: date,
    end_date: date
) -> List[Dict]:
    """
    获取日K线数据

    Args:
        ts_code: 股票代码（如 '000001.SZ'）
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        K线数据列表
    """
    engine = get_engine()
    
    sql = """
        SELECT 
            DATE(trade_date) as trade_date,
            open, high, low, close, 
            vol as volume, amount,
            pct_chg, pre_close
        FROM stocktradetodayinfo
        WHERE ts_code = :ts_code 
          AND DATE(trade_date) >= :start_date 
          AND DATE(trade_date) <= :end_date
        ORDER BY trade_date ASC
    """
    
    try:
        from sqlalchemy import text
        
        start_str = start_date.strftime('%Y-%m-%d') if isinstance(start_date, date) else str(start_date)
        end_str = end_date.strftime('%Y-%m-%d') if isinstance(end_date, date) else str(end_date)
        
        with engine.connect() as conn:
            df = pd.read_sql(
                text(sql),
                conn,
                params={
                    "ts_code": ts_code,
                    "start_date": start_str,
                    "end_date": end_str
                }
            )
        
        if df.empty:
            return []
        
        # 转换数据类型
        df['trade_date'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y-%m-%d')
        df['open'] = pd.to_numeric(df['open'], errors='coerce').fillna(0)
        df['high'] = pd.to_numeric(df['high'], errors='coerce').fillna(0)
        df['low'] = pd.to_numeric(df['low'], errors='coerce').fillna(0)
        df['close'] = pd.to_numeric(df['close'], errors='coerce').fillna(0)
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
        df['pct_chg'] = pd.to_numeric(df['pct_chg'], errors='coerce')
        df['pre_close'] = pd.to_numeric(df['pre_close'], errors='coerce')
        
        # 转换为字典列表
        return df.to_dict('records')
        
    except Exception as e:
        logger.error(f"获取日K线数据失败: {e}")
        return []


def get_weekly_kline(
    ts_code: str,
    start_date: date,
    end_date: date
) -> List[Dict]:
    """
    获取周K线数据

    Args:
        ts_code: 股票代码
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        周K线数据列表
    """
    engine = get_engine()
    
    # 周K线：取每周第一天开盘、每周最高价、每周最低价、每周最后一天收盘
    sql = """
        SELECT 
            DATE(MIN(trade_date)) as trade_date,
            FIRST_VALUE(open) OVER (PARTITION BY YEAR(trade_date), WEEK(trade_date) ORDER BY trade_date) as open,
            MAX(high) as high,
            MIN(low) as low,
            LAST_VALUE(close) OVER (PARTITION BY YEAR(trade_date), WEEK(trade_date) ORDER BY trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) as close,
            SUM(vol) as volume,
            SUM(amount) as amount
        FROM stocktradetodayinfo
        WHERE ts_code = :ts_code 
          AND DATE(trade_date) >= :start_date 
          AND DATE(trade_date) <= :end_date
        GROUP BY YEAR(trade_date), WEEK(trade_date)
        ORDER BY trade_date ASC
    """
    
    try:
        from sqlalchemy import text
        
        start_str = start_date.strftime('%Y-%m-%d') if isinstance(start_date, date) else str(start_date)
        end_str = end_date.strftime('%Y-%m-%d') if isinstance(end_date, date) else str(end_date)
        
        with engine.connect() as conn:
            df = pd.read_sql(
                text(sql),
                conn,
                params={
                    "ts_code": ts_code,
                    "start_date": start_str,
                    "end_date": end_str
                }
            )
        
        if df.empty:
            return []
        
        # 转换数据类型
        df['trade_date'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y-%m-%d')
        df['open'] = pd.to_numeric(df['open'], errors='coerce').fillna(0)
        df['high'] = pd.to_numeric(df['high'], errors='coerce').fillna(0)
        df['low'] = pd.to_numeric(df['low'], errors='coerce').fillna(0)
        df['close'] = pd.to_numeric(df['close'], errors='coerce').fillna(0)
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
        
        return df.to_dict('records')
        
    except Exception as e:
        logger.error(f"获取周K线数据失败: {e}")
        # 降级方案：使用日K线数据手动合成周K
        return convert_daily_to_weekly(ts_code, start_date, end_date)


def get_monthly_kline(
    ts_code: str,
    start_date: date,
    end_date: date
) -> List[Dict]:
    """
    获取月K线数据

    Args:
        ts_code: 股票代码
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        月K线数据列表
    """
    engine = get_engine()
    
    # 月K线：取每月第一天开盘、每月最高价、每月最低价、每月最后一天收盘
    sql = """
        SELECT 
            DATE(MIN(trade_date)) as trade_date,
            FIRST_VALUE(open) OVER (PARTITION BY YEAR(trade_date), MONTH(trade_date) ORDER BY trade_date) as open,
            MAX(high) as high,
            MIN(low) as low,
            LAST_VALUE(close) OVER (PARTITION BY YEAR(trade_date), MONTH(trade_date) ORDER BY trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) as close,
            SUM(vol) as volume,
            SUM(amount) as amount
        FROM stocktradetodayinfo
        WHERE ts_code = :ts_code 
          AND DATE(trade_date) >= :start_date 
          AND DATE(trade_date) <= :end_date
        GROUP BY YEAR(trade_date), MONTH(trade_date)
        ORDER BY trade_date ASC
    """
    
    try:
        from sqlalchemy import text
        
        start_str = start_date.strftime('%Y-%m-%d') if isinstance(start_date, date) else str(start_date)
        end_str = end_date.strftime('%Y-%m-%d') if isinstance(end_date, date) else str(end_date)
        
        with engine.connect() as conn:
            df = pd.read_sql(
                text(sql),
                conn,
                params={
                    "ts_code": ts_code,
                    "start_date": start_str,
                    "end_date": end_str
                }
            )
        
        if df.empty:
            return []
        
        # 转换数据类型
        df['trade_date'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y-%m-%d')
        df['open'] = pd.to_numeric(df['open'], errors='coerce').fillna(0)
        df['high'] = pd.to_numeric(df['high'], errors='coerce').fillna(0)
        df['low'] = pd.to_numeric(df['low'], errors='coerce').fillna(0)
        df['close'] = pd.to_numeric(df['close'], errors='coerce').fillna(0)
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
        
        return df.to_dict('records')
        
    except Exception as e:
        logger.error(f"获取月K线数据失败: {e}")
        # 降级方案：使用日K线数据手动合成月K
        return convert_daily_to_monthly(ts_code, start_date, end_date)


def convert_daily_to_weekly(
    ts_code: str,
    start_date: date,
    end_date: date
) -> List[Dict]:
    """
    将日K线数据转换为周K线数据（降级方案）
    """
    daily_data = get_daily_kline(ts_code, start_date, end_date)
    
    if not daily_data:
        return []
    
    # 按周分组
    df = pd.DataFrame(daily_data)
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df['year_week'] = df['trade_date'].dt.isocalendar().year.astype(str) + '_' + df['trade_date'].dt.isocalendar().week.astype(str).str.zfill(2)
    
    weekly_data = []
    for year_week, group in df.groupby('year_week'):
        if group.empty:
            continue
        
        # 周开盘：第一天开盘价
        open_price = group.iloc[0]['open']
        # 周收盘：最后一天收盘价
        close_price = group.iloc[-1]['close']
        # 周最高：最高价的最大值
        high_price = group['high'].max()
        # 周最低：最低价的最小值
        low_price = group['low'].min()
        # 周成交量：总成交量
        volume = group['volume'].sum()
        # 周成交额：总成交额
        amount = group['amount'].sum()
        
        weekly_data.append({
            'trade_date': group.iloc[0]['trade_date'].strftime('%Y-%m-%d'),
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close_price, 2),
            'volume': int(volume),
            'amount': round(amount, 2)
        })
    
    return weekly_data


def convert_daily_to_monthly(
    ts_code: str,
    start_date: date,
    end_date: date
) -> List[Dict]:
    """
    将日K线数据转换为月K线数据（降级方案）
    """
    daily_data = get_daily_kline(ts_code, start_date, end_date)
    
    if not daily_data:
        return []
    
    # 按月分组
    df = pd.DataFrame(daily_data)
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df['year_month'] = df['trade_date'].dt.to_period('M').astype(str)
    
    monthly_data = []
    for year_month, group in df.groupby('year_month'):
        if group.empty:
            continue
        
        # 月开盘：第一天开盘价
        open_price = group.iloc[0]['open']
        # 月收盘：最后一天收盘价
        close_price = group.iloc[-1]['close']
        # 月最高：最高价的最大值
        high_price = group['high'].max()
        # 月最低：最低价的最小值
        low_price = group['low'].min()
        # 月成交量：总成交量
        volume = group['volume'].sum()
        # 月成交额：总成交额
        amount = group['amount'].sum()
        
        monthly_data.append({
            'trade_date': group.iloc[0]['trade_date'].strftime('%Y-%m-%d'),
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close_price, 2),
            'volume': int(volume),
            'amount': round(amount, 2)
        })
    
    return monthly_data


def get_kline(
    ts_code: str,
    start_date: date,
    end_date: date,
    kline_type: str = 'daily'
) -> KLineResponse:
    """
    获取K线数据（统一入口）

    Args:
        ts_code: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        kline_type: K线类型 ('daily', 'weekly', 'monthly')

    Returns:
        KLineResponse对象
    """
    kline_type = kline_type.lower()
    
    if kline_type == 'weekly':
        data = get_weekly_kline(ts_code, start_date, end_date)
    elif kline_type == 'monthly':
        data = get_monthly_kline(ts_code, start_date, end_date)
    else:
        # 默认日K
        data = get_daily_kline(ts_code, start_date, end_date)
        kline_type = 'daily'
    
    return KLineResponse(
        ts_code=ts_code,
        kline_type=kline_type,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        data=data,
        total=len(data)
    )


def get_kline_for_chartjs(ts_code: str, days: int = 30) -> Dict:
    """
    获取适合Chart.js渲染的K线数据格式

    Args:
        ts_code: 股票代码
        days: 获取最近多少天的数据

    Returns:
        适合前端Chart.js使用的字典格式
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    # 获取日K数据
    daily_data = get_daily_kline(ts_code, start_date, end_date)
    
    if not daily_data:
        return {
            'labels': [],
            'datasets': []
        }
    
    # 转换为Chart.js格式
    labels = [item['trade_date'] for item in daily_data]
    
    # 准备数据
    ohlc_data = []
    volume_data = []
    
    for item in daily_data:
        # OHLC格式: [开盘, 最高, 最低, 收盘]
        ohlc_data.append([
            round(item['open'], 2),
            round(item['high'], 2),
            round(item['low'], 2),
            round(item['close'], 2)
        ])
        volume_data.append(int(item['volume']))
    
    return {
        'labels': labels,
        'ohlc': ohlc_data,
        'volume': volume_data,
        'ts_code': ts_code,
        'count': len(daily_data)
    }


# ============== 批量获取 ==============

def get_stocks_kline_batch(
    ts_codes: List[str],
    start_date: date,
    end_date: date,
    kline_type: str = 'daily'
) -> Dict[str, List[Dict]]:
    """
    批量获取多只股票的K线数据

    Args:
        ts_codes: 股票代码列表
        start_date: 开始日期
        end_date: 结束日期
        kline_type: K线类型

    Returns:
        字典，键为股票代码，值为K线数据列表
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    result = {}
    
    def fetch_kline(code: str):
        return code, get_kline(code, start_date, end_date, kline_type)
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_kline, code): code for code in ts_codes}
        
        for future in as_completed(futures):
            try:
                code, kline_data = future.result()
                result[code] = kline_data
            except Exception as e:
                logger.error(f"批量获取K线数据失败: {e}")
    
    return result


# ============== 主函数 ==============

if __name__ == "__main__":
    # 测试用
    test_ts_code = "000001.SZ"
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    print(f"获取股票 {test_ts_code} 最近30天日K线数据...")
    daily = get_daily_kline(test_ts_code, start_date, end_date)
    print(f"日K数据: {len(daily)} 条")
    
    print(f"\n获取股票 {test_ts_code} 周K线数据...")
    weekly = get_weekly_kline(test_ts_code, start_date, end_date)
    print(f"周K数据: {len(weekly)} 条")
    
    print(f"\n获取股票 {test_ts_code} 月K线数据...")
    monthly = get_monthly_kline(test_ts_code, start_date, end_date)
    print(f"月K数据: {len(monthly)} 条")
    
    print(f"\n获取Chart.js格式数据...")
    chartjs_data = get_kline_for_chartjs(test_ts_code, 30)
    print(f"Chart.js数据: {chartjs_data['count']} 条")
