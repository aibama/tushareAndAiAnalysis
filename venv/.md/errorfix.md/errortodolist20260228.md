接口报错：
2026-02-28 08:25:03,623 - PatternAnalysis.strategy.ATR.atr_stable_period_service - ERROR - 从Redis获取稳定期数据失败: WRONGTYPE Operation against a key holding the wrong kind of value
2026-02-28 08:25:20,488 - PatternAnalysis.strategy.ATR.atr_stable_period_service - WARNING - 股票 index 数据不足，无法计算ATR       
2026-02-28 08:25:20,489 - PatternAnalysis.strategy.ATR.atr_stable_period_service - WARNING - 股票 index 数据不足，无法检测稳定期    
INFO:     127.0.0.1:55132 - "GET /api/atr/stable-periods/index?market_factor=0Y-100Y&page=1&page_size=50 HTTP/1.1" 400 Bad Request 
但是个股接口：
curl -X 'GET' \
  'http://localhost:8081/api/atr/stable-periods/600486.SH?window=20&percentile_threshold=30&min_stable_days=5&lookback_period=241&use_cache=true' \
  -H 'accept: application/json'
会返回数据：
{
  "ts_code": "600486.SH",
  "status": "computed",
  "num_stable_periods": 16,
  "total_stable_days": 201,
  "max_stable_days": 59,
  "min_stable_days": 5,
  "stable_periods": [
    {
      "start_date": "2023-05-08",
      "end_date": "2023-05-22",
      "duration_days": 11,
      "avg_atr": 2.3527,
      "atr_cv": 0.0545,
      "stability_score": 0.9455
    },
    {
      "start_date": "2023-07-06",
      "end_date": "2023-07-13",
      "duration_days": 6,
      "avg_atr": 2.0789,
      "atr_cv": 0.0324,
      "stability_score": 0.9676
    },
    {
      "start_date": "2026-01-09",
      "end_date": "2026-01-29",
      "duration_days": 15,
      "avg_atr": 2.5156,
      "atr_cv": 0.0563,
      "stability_score": 0.9437
    }
  ],
  "summary": {
    "status": "success",
    "ts_code": "600486.SH",
    "total_data_points": 708,
    "num_stable_periods": 16,
    "total_stable_days": 201,
    "parameters": {
      "window": 20,
      "percentile_threshold": 30,
      "min_stable_days": 5,
      "lookback_period": 241,
      "default_threshold": 0.03
    },
    "atr_range": {
      "min": 1.1545,
      "max": 3.3991,
      "mean": 1.9582
    }
  }
}
