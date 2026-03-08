
两个接口：
/api/volume/recalculate
/api/limit/recalculate
以及各自对用的其他两个接口，是否没有用redis缓存起来；如果没有，则加上redis/stream的缓存；这是一个改善点（称作A)
因为我先触发上面两个接口，然后用/api/atr/stable-periods/{ts_code}这个接口，是能查到  "limit_info"和
  "volume_info"的信息的；系统重启了，就没法查到了（没有触发上面两个接口）；所以/api/atr/stable-periods/{ts_code}的"limit_info"和
  "volume_info"的信息也先走缓存，后走实时计算；


  两个接口：
/api/volume/recalculate
/api/limit/recalculate;
项目启动时，异步触发这两个接口（不要阻塞项目启动）

上面已完成：
但是还有个需要优化的：

2026-03-07 21:48:04,088 - PatternAnalysis.api_service - INFO - 按稳定期时间段筛选: begin_date=2025-01-01, end_date=2026-02-01
2026-03-07 21:48:07,253 - PatternAnalysis.api_service - INFO - 按稳定期时间段筛选后股票数量: 5377
2026-03-07 21:48:07,257 - PatternAnalysis.strategy.ATR.atr_stable_period_service - INFO - 开始并行计算市值，共 42 只股票，分 1 批，10 线程
INFO:     127.0.0.1:63123 - "GET /api/atr/stable-periods/index?begin_date=2025-01-01&end_date=2026-02-01&page=1&page_size=50 HTTP/1.1" 200 OK


1、项目启动的启动时候，异步进行市值计算（preheat_market_cap_cache）的预热，不影响项目启动
2、atr_stable_period_service.py确保是先走的缓存拿市值，不存在的时候，再多线程计算