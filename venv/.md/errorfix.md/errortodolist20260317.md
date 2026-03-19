你作为python后端开发专家，阅览和理解项目所有的相关代码和文档，
需求：遇到股票代码.SH结尾的，改成1.股票代码，
例如：601919.SH改成1.601919
即股票代码转换: 601919.SH -> 1.601919;
下面是运行时的日志输出：
2026-03-14T16:42:04.872+08:00 ERROR 35028 --- [mybatisdemo] [e-node1-thread3] c.e.e.api.StockMinusTradeDataApiImp      : get ut:bd1d9ddb04089700cf9c27f6f7426281
2026-03-14T16:42:04.872+08:00  INFO 35028 --- [mybatisdemo] [e-node1-thread3] c.e.e.api.StockMinusTradeDataApiImp      : 获取到新UT: bd1d9ddb04089700cf9c27f6f7426281
2026-03-14T16:42:04.873+08:00  INFO 35028 --- [mybatisdemo] [e-node1-thread3] c.e.e.api.StockMinusTradeDataApiImp      : Redis更新成功: key=601919.SH, UT=bd1d9ddb04089700cf9c27f6f7426281
2026-03-14T16:42:04.873+08:00  INFO 35028 --- [mybatisdemo] [e-node1-thread3] c.e.e.api.StockMinusTradeDataApiImp      : 使用有效UT建立SSE连接: UT=bd1d9ddb04089700cf9c27f6f7426281
2026-03-14T16:42:04.873+08:00  INFO 35028 --- [mybatisdemo] [e-node1-thread3] c.e.e.api.StockMinusTradeDataApiImp      : 股票代码转换: 601919.SH -> 0.601919