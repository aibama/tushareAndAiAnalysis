这两个接口：
/api/atr/stable-periods/index
/api/rank?direction=up&start_date=2025-01-20&end_date=2026-01-10&limit=150&use_cache=true
从之前的关联stock_trade_info这个表变成：
通过ts_code关联，获取stockinfobase的name作为股票名称；

这两个接口：
/api/atr/stable-periods/index
/api/rank?direction=up&start_date=2025-01-20&end_date=2026-01-10&limit=150&use_cache=true
都会前端增加参数sector=？前端的编码如下：
☑全部  不传
口沪板  SH
口深板  SZ
口创业板 CY
☐科创板 KC
后端的过滤逻辑：
板块/市场	交易代码前缀
SH沪市主板	600、601、603、605
SZ深市主板	000、001、002、003、004
CY创业板	300、301
KC科创板	688

deprecated
你是python后端专家，先阅览理解项目原有代码和目录；做以下功能：/api/atr/stable-periods/index新增两个参数：
begin_date：开始时间
end_date：结束时间
对存在对应时间段内的股票进行过滤（可以一部分时间在这内，只要有相交，或者包含，或者被包含都算）；