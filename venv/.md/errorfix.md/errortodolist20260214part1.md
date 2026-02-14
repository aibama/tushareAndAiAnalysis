执行run_incremen.py报错：2026-02-14 09:26:02,115 - PatternAnalysis.incremental_jobs - INFO - 需要处理的股票数量: 5503
2026-02-14 09:26:02,121 - PatternAnalysis.incremental_jobs - ERROR - 获取最后处理日期失败: List argument must consist only of dictionaries ；
另外程序获取时间区间内的数据，好像有问题，控制台输出：2026-02-14 09:43:34,611 - PatternAnalysis.incremental_jobs - WARNING - 股票 000166.SZ 在当前周期没有数据
2026-02-14 09:43:34,640 - PatternAnalysis.incremental_jobs - INFO - 股票 000166.SZ 周期 3m 分类完成: 其他形态
其实数据库是有数据的，两个日期中间还有很多数据：
INSERT INTO `stockdata`.`stocktradetodayinfo` (`id`, `ts_code`, `amount`, `echange`, `close`, `high`, `low`, `open`, `pct_chg`, `pre_close`, `trade_date`, `vol`, `trade_date_tmp`) VALUES (NULL, '000166.SZ', 811928.261, 0.03, 5.13, 5.19, 5.1, 5.1, 0.5882, 5.1, '2026-01-26 00:00:00.000000', 1580010.24, NULL);
INSERT INTO `stockdata`.`stocktradetodayinfo` (`id`, `ts_code`, `amount`, `echange`, `close`, `high`, `low`, `open`, `pct_chg`, `pre_close`, `trade_date`, `vol`, `trade_date_tmp`) VALUES (NULL, '000166.SZ', 753439.142, 0.06, 5.52, 5.55, 5.48, 5.5, 1.0989, 5.46, '2025-10-27 00:00:00.000000', 1366910.20, NULL);
