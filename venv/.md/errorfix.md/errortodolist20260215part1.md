get_stock_returns_in_range实现起来，还是很慢的，而且数据量太大了，所以将这个逻辑改成用以下sql实现，如果下面逻辑有问题，也一并修改，
总之将子查询转换为JOIN操作，提高性能。
def get_stock_returns_in_range(self, start: datetime, end: datetime, direction: str = "up") -> pd.DataFrame:
    """
    MySQL 5.7兼容版本：简化聚合方法
    """
    engine = get_engine()
    
    # 确保日期是datetime类型
    if isinstance(start, date) and not isinstance(start, datetime):
        start = datetime.combine(start, datetime.min.time())
    if isinstance(end, date) and not isinstance(end, datetime):
        end = datetime.combine(end, datetime.min.time())
    
    # 简化版本：分别获取最小和最大日期的收盘价
    sql = """
        SELECT 
            s1.ts_code,
            ROUND((s2.close - s1.close) / s1.close * 100, 2) AS return_rate
        FROM (
            -- 获取每只股票最早交易日的收盘价
            SELECT 
                ts_code, 
                close
            FROM stocktradetodayinfo
            WHERE (ts_code, trade_date) IN (
                SELECT ts_code, MIN(trade_date)
                FROM stocktradetodayinfo
                WHERE trade_date BETWEEN :start_date AND :end_date
                GROUP BY ts_code
            )
        ) s1
        JOIN (
            -- 获取每只股票最晚交易日的收盘价
            SELECT 
                ts_code, 
                close
            FROM stocktradetodayinfo
            WHERE (ts_code, trade_date) IN (
                SELECT ts_code, MAX(trade_date)
                FROM stocktradetodayinfo
                WHERE trade_date BETWEEN :start_date AND :end_date
                GROUP BY ts_code
            )
        ) s2 ON s1.ts_code = s2.ts_code
        WHERE s1.close > 0
    """
    
    try:
        df = pd.read_sql(
            text(sql),
            engine,
            params={"start_date": start, "end_date": end}
        )
        
        if df.empty:
            return pd.DataFrame(columns=["ts_code", "return_rate", "max_drawdown_rebound"])
        
        # 根据方向过滤
        if direction == "up":
            df = df[df["return_rate"] > 0]
        elif direction == "down":
            df = df[df["return_rate"] < 0]
        
        # 添加空的max_drawdown_rebound列
        df["max_drawdown_rebound"] = None
        
        return df[["ts_code", "return_rate", "max_drawdown_rebound"]]
    except Exception as e:
        print(f"批量获取股票涨跌幅失败: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame(columns=["ts_code", "return_rate", "max_drawdown_rebound"])