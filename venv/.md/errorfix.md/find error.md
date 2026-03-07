已修复股票名称显示问题。问题是数据库 stock_trade_info 表中没有新股票（如科创板688xxx）的数据。


I've switched to using FastAPI's default Swagger UI (which loads from CDN). The server is now running and serving Swagger UI from https://cdn.jsdelivr.net.

Please try accessing http://localhost:8081/docs with a hard browser refresh (Ctrl+F5).

If this also fails, the issue might be:
1. Network firewall blocking the CDN (jsdelivr.net)
2. Browser-specific caching issue

If the CDN version works, we can keep it. If not, we'll need to investigate further.