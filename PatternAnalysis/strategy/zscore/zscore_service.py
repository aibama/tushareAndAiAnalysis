"""
Z-Score 计算服务

实现个股Z-Score和行业综合Z-Score的计算
"""
import logging
from typing import List, Dict, Optional, Tuple
from datetime import date, timedelta
import pandas as pd
import numpy as np
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .config import ZSCORE_CONFIG
from .data_service import (
    get_zz1000_stocks,
    get_stock_daily,
    get_sw_industries,
    get_stock_industry_relation,
    get_industry_stocks,
    get_trade_dates,
    get_latest_trade_date,
    get_stock_mv
)

logger = logging.getLogger(__name__)


def calculate_stock_zscore(
    ts_code: str,
    df_daily: pd.DataFrame,
    window_days: int = 60,
    indicator: str = "price"
) -> Optional[float]:
    """
    计算单只股票的Z-Score

    Args:
        ts_code: 股票代码
        df_daily: 日线数据DataFrame
        window_days: 滚动窗口天数
        indicator: 指标类型

    Returns:
        Z-Score值
    """
    # 筛选该股票的数据
    df = df_daily[df_daily['ts_code'] == ts_code].copy()

    if df.empty:
        return None

    # 按日期排序
    df = df.sort_values('trade_date')

    # 获取指标值
    if indicator == "price":
        values = df['close'].values
    else:
        # 其他指标暂时使用close
        values = df['close'].values

    if len(values) < 2:
        return None

    # 取最近window_days个交易日的数据
    values = values[-window_days:]

    # 计算均值和标准差
    mean_val = np.mean(values)
    std_val = np.std(values, ddof=0)  # 总体标准差

    # 如果标准差为0，返回0
    if std_val == 0 or math.isnan(std_val):
        return 0.0

    # 计算Z-Score
    current_value = values[-1]
    zscore = (current_value - mean_val) / std_val

    # 处理异常值
    if math.isnan(zscore) or math.isinf(zscore):
        return 0.0

    return round(zscore, 4)


def calculate_industry_zscore(
    industry_code: str,
    df_daily: pd.DataFrame,
    df_mv: pd.DataFrame,
    window_days: int = 60,
    indicator: str = "price"
) -> Optional[float]:
    """
    计算行业综合Z-Score（按市值加权）

    Args:
        industry_code: 行业代码
        df_daily: 日线数据DataFrame
        df_mv: 市值数据DataFrame (ts_code, mv)
        window_days: 滚动窗口天数
        indicator: 指标类型

    Returns:
        行业Z-Score
    """
    # 获取该行业的成分股
    industry_stocks = get_industry_stocks(industry_code)
    ts_codes = [s['ts_code'] for s in industry_stocks]

    if not ts_codes:
        return None

    # 计算每只股票的Z-Score
    zscores = []
    weights = []

    for ts_code in ts_codes:
        zscore = calculate_stock_zscore(ts_code, df_daily, window_days, indicator)

        if zscore is not None:
            # 获取市值作为权重
            mv_row = df_mv[df_mv['ts_code'] == ts_code]
            if not mv_row.empty:
                mv = mv_row.iloc[0].get('mv', 0)
                if mv and mv > 0:
                    zscores.append(zscore)
                    weights.append(mv)

    if not zscores:
        return None

    # 市值加权平均
    zscores = np.array(zscores)
    weights = np.array(weights)

    # 加权平均
    weighted_zscore = np.sum(zscores * weights) / np.sum(weights)

    if math.isnan(weighted_zscore) or math.isinf(weighted_zscore):
        return 0.0

    return round(weighted_zscore, 4)


def get_industry_daily_zscore(
    trade_date: date = None,
    indicator: str = "price"
) -> List[Dict]:
    """
    获取所有申万一级行业当日的Z-Score

    Args:
        trade_date: 交易日期，默认最新
        indicator: 指标类型

    Returns:
        行业Z-Score列表
    """
    if trade_date is None:
        trade_date = get_latest_trade_date()

    window_days = ZSCORE_CONFIG.get("window_days", 60)

    # 计算开始日期（回溯window_days天）
    start_date = trade_date - timedelta(days=window_days * 2)  # 多取一些天数以确保有足够数据

    # 获取中证1000成分股
    stocks = get_zz1000_stocks()
    ts_codes = [s['ts_code'] for s in stocks]

    if not ts_codes:
        logger.warning("没有找到中证1000成分股")
        return []

    # 获取日线数据
    df_daily = get_stock_daily(ts_codes, start_date, trade_date)

    if df_daily.empty:
        logger.warning(f"没有找到日期范围 {start_date} 到 {trade_date} 的日线数据")
        return []

    # 获取市值数据（使用真实的市值计算服务）
    mv_data = get_stock_mv(ts_codes, trade_date)
    df_mv_data = [{"ts_code": code, "mv": mv} for code, mv in mv_data.items()]
    df_mv = pd.DataFrame(df_mv_data)

    # 获取申万一级行业
    industries = get_sw_industries(level=1)

    # 获取股票-行业映射
    stock_industry_map = get_stock_industry_relation(ts_codes)

    # 计算每个行业的Z-Score
    results = []

    for industry in industries:
        industry_code = industry['node_code']
        industry_name = industry['node_name']

        # 获取该行业的成分股
        industry_stocks = get_industry_stocks(industry_code)
        industry_ts_codes = [s['ts_code'] for s in industry_stocks]

        # 过滤出属于中证1000的股票
        valid_ts_codes = [c for c in industry_ts_codes if c in ts_codes]

        if not valid_ts_codes:
            continue

        # 筛选该行业的日线数据
        df_industry_daily = df_daily[df_daily['ts_code'].isin(valid_ts_codes)]

        if df_industry_daily.empty:
            continue

        # 计算行业Z-Score
        industry_zscore = calculate_industry_zscore(
            industry_code,
            df_industry_daily,
            df_mv[df_mv['ts_code'].isin(valid_ts_codes)],
            window_days,
            indicator
        )

        if industry_zscore is not None:
            results.append({
                "industry_code": industry_code,
                "industry_name": industry_name,
                "stock_count": len(valid_ts_codes),
                "zscore": industry_zscore
            })

    return results


def get_industry_stocks_zscore(
    industry_code: str,
    trade_date: date = None,
    indicator: str = "price"
) -> List[Dict]:
    """
    获取某行业下所有成分股的Z-Score

    Args:
        industry_code: 行业代码
        trade_date: 交易日期，默认最新
        indicator: 指标类型

    Returns:
        成分股Z-Score列表
    """
    if trade_date is None:
        trade_date = get_latest_trade_date()

    window_days = ZSCORE_CONFIG.get("window_days", 60)

    # 计算开始日期
    start_date = trade_date - timedelta(days=window_days * 2)

    # 获取该行业的成分股
    industry_stocks = get_industry_stocks(industry_code)
    ts_codes = [s['ts_code'] for s in industry_stocks]

    if not ts_codes:
        return []

    # 获取股票名称映射
    stock_names = {s['ts_code']: s['stock_name'] for s in industry_stocks}

    # 获取日线数据
    df_daily = get_stock_daily(ts_codes, start_date, trade_date)

    if df_daily.empty:
        return []

    # 获取市值数据（使用真实的市值计算服务）
    mv_data = get_stock_mv(ts_codes, trade_date)
    df_mv_data = [{"ts_code": code, "mv": mv} for code, mv in mv_data.items()]
    df_mv = pd.DataFrame(df_mv_data)

    # 获取行业名称
    industries = get_sw_industries(level=1)
    industry_name = next((i['node_name'] for i in industries if i['node_code'] == industry_code), "")

    # 计算每只股票的Z-Score
    results = []

    for ts_code in ts_codes:
        zscore = calculate_stock_zscore(ts_code, df_daily, window_days, indicator)

        if zscore is not None:
            # 获取当前价格
            df_stock = df_daily[df_daily['ts_code'] == ts_code]
            if not df_stock.empty:
                current_price = df_stock.iloc[-1]['close']
            else:
                current_price = 0

            # 获取市值
            stock_mv = mv_data.get(ts_code, 10000000000)

            results.append({
                "ts_code": ts_code,
                "stock_name": stock_names.get(ts_code, ts_code),
                "zscore": zscore,
                "indicator_value": current_price,
                "mv": stock_mv
            })

    # 按Z-Score降序排序
    results.sort(key=lambda x: x['zscore'], reverse=True)

    return {
        "industry_code": industry_code,
        "industry_name": industry_name,
        "stocks": results
    }


def get_stock_timeseries_zscore(
    ts_code: str,
    trade_date: date = None,
    days: int = 60,
    indicator: str = "price"
) -> List[Dict]:
    """
    获取个股Z-Score时间序列

    Args:
        ts_code: 股票代码
        trade_date: 结束日期，默认最新
        days: 回溯天数
        indicator: 指标类型

    Returns:
        Z-Score时间序列
    """
    if trade_date is None:
        trade_date = get_latest_trade_date()

    # 计算开始日期
    start_date = trade_date - timedelta(days=days * 2)

    # 获取日线数据
    df_daily = get_stock_daily([ts_code], start_date, trade_date)

    if df_daily.empty:
        return []

    # 获取股票名称
    from .data_service import get_mysql_connection
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT name FROM stockinfobase WHERE ts_code = %s", (ts_code,))
            row = cursor.fetchone()
            stock_name = row[0] if row else ts_code
    finally:
        conn.close()

    # 获取该股票所有交易日
    trade_dates = get_trade_dates(start_date, trade_date)

    if len(trade_dates) < days:
        days = len(trade_dates)

    results = []

    for i in range(days):
        # 从后往前推
        end_idx = len(trade_dates) - days + i + 1
        if end_idx < days:
            continue

        current_date = trade_dates[end_idx - 1]
        window_start_idx = max(0, end_idx - days)

        # 筛选窗口期数据
        df_window = df_daily[
            (df_daily['trade_date'] >= trade_dates[window_start_idx]) &
            (df_daily['trade_date'] <= current_date)
        ]

        if df_window.empty:
            continue

        zscore = calculate_stock_zscore(ts_code, df_window, days, indicator)

        if zscore is not None:
            results.append({
                "date": current_date.strftime('%Y-%m-%d') if isinstance(current_date, date) else str(current_date),
                "zscore": zscore
            })

    return {
        "ts_code": ts_code,
        "stock_name": stock_name,
        "indicator": indicator,
        "series": results
    }


def get_industry_timeseries_zscore(
    industry_code: str,
    trade_date: date = None,
    days: int = 60,
    indicator: str = "price"
) -> List[Dict]:
    """
    获取行业Z-Score时间序列

    Args:
        industry_code: 行业代码
        trade_date: 结束日期，默认最新
        days: 回溯天数
        indicator: 指标类型

    Returns:
        Z-Score时间序列
    """
    if trade_date is None:
        trade_date = get_latest_trade_date()

    # 计算开始日期
    start_date = trade_date - timedelta(days=days * 2)

    # 获取该行业的成分股
    industry_stocks = get_industry_stocks(industry_code)
    ts_codes = [s['ts_code'] for s in industry_stocks]

    if not ts_codes:
        return []

    # 获取日线数据
    df_daily = get_stock_daily(ts_codes, start_date, trade_date)

    if df_daily.empty:
        return []

    # 获取市值数据（使用真实的市值计算服务）
    mv_data = get_stock_mv(ts_codes, trade_date)
    df_mv_data = [{"ts_code": code, "mv": mv} for code, mv in mv_data.items()]
    df_mv = pd.DataFrame(df_mv_data)

    # 获取行业名称
    industries = get_sw_industries(level=1)
    industry_name = next((i['node_name'] for i in industries if i['node_code'] == industry_code), "")

    # 获取所有交易日
    trade_dates = get_trade_dates(start_date, trade_date)

    if len(trade_dates) < days:
        days = len(trade_dates)

    results = []

    for i in range(days):
        # 从后往前推
        end_idx = len(trade_dates) - days + i + 1
        if end_idx < days:
            continue

        current_date = trade_dates[end_idx - 1]
        window_start_idx = max(0, end_idx - days)

        # 筛选窗口期数据
        df_window = df_daily[
            (df_daily['trade_date'] >= trade_dates[window_start_idx]) &
            (df_daily['trade_date'] <= current_date)
        ]

        if df_window.empty:
            continue

        # 筛选该行业的成分股数据
        df_industry_window = df_window[df_window['ts_code'].isin(ts_codes)]

        if df_industry_window.empty:
            continue

        zscore = calculate_industry_zscore(
            industry_code,
            df_industry_window,
            df_mv[df_mv['ts_code'].isin(ts_codes)],
            days,
            indicator
        )

        if zscore is not None:
            results.append({
                "date": current_date.strftime('%Y-%m-%d') if isinstance(current_date, date) else str(current_date),
                "zscore": zscore
            })

    return {
        "industry_code": industry_code,
        "industry_name": industry_name,
        "indicator": indicator,
        "series": results
    }


def get_index_timeseries_zscore(
    trade_date: date = None,
    days: int = 60,
    indicator: str = "price"
) -> List[Dict]:
    """
    获取中证1000指数整体Z-Score时间序列

    Args:
        trade_date: 结束日期，默认最新
        days: 回溯天数
        indicator: 指标类型

    Returns:
        Z-Score时间序列
    """
    # 使用全部成分股的加权平均作为指数Z-Score
    if trade_date is None:
        trade_date = get_latest_trade_date()

    # 计算开始日期
    start_date = trade_date - timedelta(days=days * 2)

    # 获取中证1000成分股
    stocks = get_zz1000_stocks()
    ts_codes = [s['ts_code'] for s in stocks]

    if not ts_codes:
        return []

    # 获取日线数据
    df_daily = get_stock_daily(ts_codes, start_date, trade_date)

    if df_daily.empty:
        return []

    # 获取市值数据（使用真实的市值计算服务）
    mv_data = get_stock_mv(ts_codes, trade_date)
    df_mv_data = [{"ts_code": code, "mv": mv} for code, mv in mv_data.items()]
    df_mv = pd.DataFrame(df_mv_data)

    # 获取所有交易日
    trade_dates = get_trade_dates(start_date, trade_date)

    if len(trade_dates) < days:
        days = len(trade_dates)

    results = []

    for i in range(days):
        # 从后往前推
        end_idx = len(trade_dates) - days + i + 1
        if end_idx < days:
            continue

        current_date = trade_dates[end_idx - 1]
        window_start_idx = max(0, end_idx - days)

        # 筛选窗口期数据
        df_window = df_daily[
            (df_daily['trade_date'] >= trade_dates[window_start_idx]) &
            (df_daily['trade_date'] <= current_date)
        ]

        if df_window.empty:
            continue

        # 计算指数整体Z-Score（所有成分股市值加权）
        zscore = calculate_industry_zscore(
            "ZZ1000",  # 使用一个虚拟的行业代码
            df_window,
            df_mv,
            days,
            indicator
        )

        if zscore is not None:
            results.append({
                "date": current_date.strftime('%Y-%m-%d') if isinstance(current_date, date) else str(current_date),
                "zscore": zscore
            })

    return {
        "index_code": "000852",
        "index_name": "中证1000",
        "indicator": indicator,
        "series": results
    }


if __name__ == "__main__":
    # 测试代码
    import logging
    from datetime import date

    logging.basicConfig(level=logging.INFO)

    # 测试获取行业Z-Score
    print("=== 测试行业Z-Score ===")
    results = get_industry_daily_zscore(trade_date=date(2026, 3, 19), indicator="price")
    print(f"行业数量: {len(results)}")
    if results:
        print(f"前5个: {results[:5]}")

    # 测试获取行业成分股Z-Score
    print("\n=== 测试行业成分股Z-Score ===")
    industry_result = get_industry_stocks_zscore("801010", trade_date=date(2026, 3, 19))
    print(f"行业: {industry_result.get('industry_name')}")
    print(f"成分股数量: {len(industry_result.get('stocks', []))}")
    if industry_result.get('stocks'):
        print(f"前5只: {industry_result['stocks'][:5]}")
