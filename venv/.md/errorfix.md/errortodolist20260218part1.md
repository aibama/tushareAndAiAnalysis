/api/rank 需要修复和完善如下：
1、返回字段的逻辑错误，total_stocks按参入的参数limit设置；
{
  "direction": "up",
  "start_date": "2025-01-20",
  "end_date": "2026-01-10",
  "total_stocks": 4447,
  "page": 1,
  "page_size": 50,
  "total_pages": 89,
  "rankings": [
    {
      "rank": 1,
      "ts_code": "688585.SH",
      "return_rate": 2091.63,
      "max_drawdown_rebound": null
    },
    {
      "rank": 2,
      "ts_code": "605255.SH",
      "return_rate": 1565.55,
      "max_drawdown_rebound": null
    }
	]
}
2、屏蔽阶段2：启动异步计算回撤/反弹...的所有逻辑代码（注释掉）

3、get_stock_returns_in_range的sql逻辑变成如下：
-- 计算时间序列收益率
CREATE TEMPORARY TABLE time_series AS
SELECT 
    ts_code,
    MAX(CASE WHEN rn_asc = 1 THEN close END) AS first_close,
    MAX(CASE WHEN rn_desc = 1 THEN close END) AS last_close
FROM (
    SELECT 
        ts_code,
        close,
        ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date) AS rn_asc,
        ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) AS rn_desc
    FROM stocktradetodayinfo
    WHERE trade_date >= '2025-01-20'
      AND trade_date <= '2026-01-10'
      AND close > 0
) ranked
WHERE rn_asc = 1 OR rn_desc = 1
GROUP BY ts_code;

-- 计算价格区间收益率
CREATE TEMPORARY TABLE price_range AS
SELECT 
    ts_code,
    MIN(close) AS min_close,
    MAX(close) AS max_close
FROM stocktradetodayinfo
WHERE trade_date >= '2025-01-20'
  AND trade_date <= '2026-01-10'
  AND close > 0
GROUP BY ts_code;

-- 合并结果
SELECT 
    t.ts_code,
    ROUND((t.last_close - t.first_close) / t.first_close * 100, 2) AS max_drawdown_rebound,
    ROUND((p.max_close - p.min_close) / p.min_close * 100, 2) AS price_range_return_rate
FROM time_series t
JOIN price_range p ON t.ts_code = p.ts_code
WHERE t.first_close > 0
  AND p.min_close > 0;
  
同时代码里面，和readme记录
max_drawdown_rebound  既是时间序列收益率
price_range_return_rate 计算区间最高收益（现货卖空的概念)
