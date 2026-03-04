这两个接口：
/api/atr/stable-periods/index
/api/rank?direction=up&start_date=2025-01-20&end_date=2026-01-10&limit=150&use_cache=true
从之前的关联stock_trade_info这个表变成：
通过ts_code关联，获取stockinfobase的name作为股票名称；