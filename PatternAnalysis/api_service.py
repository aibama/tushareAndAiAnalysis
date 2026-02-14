"""
股票形态分析系统 - FastAPI服务
提供形态分类API接口
"""
from fastapi import FastAPI, Query, Path, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Union
from datetime import date, datetime
from enum import IntEnum

from .config import API_CONFIG
from .data_access import (
    get_latest_trade_date,
    get_all_ts_codes,
    get_stock_ohlc_in_range,
    StockDataAccess
)
from .periods import (
    get_period_windows,
    get_custom_windows,
    get_period_months,
    validate_period_type,
    PeriodCalculator
)
from .returns import calc_period_return, ReturnCalculator
from .pattern_model import (
    classify_pattern,
    PatternType,
    PATTERN_NAME_MAP,
    PatternClassifier
)
from .incremental_jobs import (
    init_tables,
    get_cached_results,
    IncrementalJobManager
)


# 创建FastAPI应用
app = FastAPI(
    title=API_CONFIG["title"],
    version=API_CONFIG["version"],
    description="提供股票形态分类、涨跌幅计算等API接口"
)


# 初始化增量表
@app.on_event("startup")
async def startup_event():
    """启动时初始化"""
    try:
        init_tables()
    except Exception as e:
        print(f"警告: 数据库初始化失败 (服务仍可启动): {e}")


# ============== 数据模型 ==============

class StockPatternItem(BaseModel):
    """单个股票的形态分类结果"""
    ts_code: str
    pattern_type: int
    pattern_name: str
    curr_return: Optional[float] = None
    prev_return: Optional[float] = None


class PatternGroup(BaseModel):
    """按形态分组的股票列表"""
    pattern_type: int
    pattern_name: str
    stocks: List[StockPatternItem]


class PatternResponse(BaseModel):
    """形态分类响应"""
    period_type: str
    period_months: Optional[int] = None
    current_period: Dict[str, str]
    previous_period: Dict[str, str]
    total_stocks: int
    pattern_groups: List[PatternGroup]


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    latest_trade_date: Optional[str]
    timestamp: datetime


# ============== 依赖注入 ==============

def get_data_access() -> StockDataAccess:
    """获取数据访问实例"""
    return StockDataAccess()


def get_period_calculator() -> PeriodCalculator:
    """获取周期计算器"""
    return PeriodCalculator()


def get_return_calculator() -> ReturnCalculator:
    """获取涨跌幅计算器"""
    return ReturnCalculator()


def get_pattern_classifier() -> PatternClassifier:
    """获取形态分类器"""
    return PatternClassifier(mode="rule")


# ============== API端点 ==============

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    latest_dt = get_latest_trade_date()
    return HealthResponse(
        status="healthy",
        latest_trade_date=latest_dt.isoformat() if latest_dt else None,
        timestamp=datetime.now()
    )


@app.get("/api/patterns", response_model=PatternResponse)
async def get_patterns(
    period_type: str = Query(
        ..., 
        pattern="^(3m|6m|9m|12m|custom)$",
        description="周期类型: 3m(3个月), 6m(6个月), 9m(9个月), 12m(12个月), custom(自定义)"
    ),
    start_date: Optional[date] = Query(
        None, 
        description="自定义周期的开始日期"
    ),
    end_date: Optional[date] = Query(
        None, 
        description="自定义周期的结束日期"
    ),
    use_cache: bool = Query(
        True, 
        description="是否使用缓存结果"
    )
):
    """
    获取所有股票的形态分类结果
    
    支持以下周期类型：
    - 3m: 最近3个月
    - 6m: 最近6个月
    - 9m: 最近9个月
    - 12m: 最近12个月
    - custom: 自定义周期（需指定start_date和end_date）
    """
    # 验证周期类型
    if period_type == "custom":
        if not start_date or not end_date:
            raise HTTPException(
                status_code=400,
                detail="自定义周期必须提供 start_date 和 end_date"
            )
        if start_date >= end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date 必须小于 end_date"
            )
    elif not validate_period_type(period_type):
        raise HTTPException(
            status_code=400,
            detail=f"无效的周期类型: {period_type}"
        )
    
    # 获取最新交易日
    latest_dt = get_latest_trade_date()
    if latest_dt is None:
        raise HTTPException(
            status_code=500,
            detail="数据库中尚无交易数据"
        )
    
    # 计算时间窗口
    period_calc = PeriodCalculator()
    
    if period_type == "custom":
        (curr_start, curr_end), (prev_start, prev_end) = get_custom_windows(start_date, end_date)
        period_months = None
    else:
        months = get_period_months(period_type)
        (curr_start, curr_end), (prev_start, prev_end) = get_period_windows(latest_dt, months)
        period_months = months
    
    # 尝试使用缓存
    if use_cache:
        cached_data = get_cached_results(period_type)
        if cached_data:
            # 按形态分组
            pattern_groups_dict: Dict[int, List[dict]] = {}
            for item in cached_data:
                pt = item['pattern_type']
                if pt not in pattern_groups_dict:
                    pattern_groups_dict[pt] = []
                pattern_groups_dict[pt].append({
                    "ts_code": item['ts_code'],
                    "pattern_type": item['pattern_type'],
                    "pattern_name": item['pattern_name'],
                    "curr_return": item.get('curr_return'),
                    "prev_return": item.get('prev_return')
                })
            
            pattern_groups = [
                PatternGroup(
                    pattern_type=pt,
                    pattern_name=PATTERN_NAME_MAP.get(PatternType(pt), "未知形态"),
                    stocks=[StockPatternItem(**s) for s in stocks]
                )
                for pt, stocks in sorted(pattern_groups_dict.items())
            ]
            
            return PatternResponse(
                period_type=period_type,
                period_months=period_months,
                current_period={
                    "start": curr_start.isoformat(),
                    "end": curr_end.isoformat()
                },
                previous_period={
                    "start": prev_start.isoformat(),
                    "end": prev_end.isoformat()
                },
                total_stocks=len(cached_data),
                pattern_groups=pattern_groups
            )
    
    # 实时计算
    ts_codes = get_all_ts_codes()
    pattern_groups_dict: Dict[int, List[StockPatternItem]] = {t.value: [] for t in PatternType}
    
    for code in ts_codes:
        # 获取当前周期数据
        df_curr = get_stock_ohlc_in_range(code, curr_start, curr_end)
        
        if df_curr.empty:
            continue
        
        # 分类
        pattern = classify_pattern(df_curr, mode="rule")
        
        # 计算涨跌幅
        df_prev = get_stock_ohlc_in_range(code, prev_start, prev_end)
        curr_ret = calc_period_return(df_curr)
        prev_ret = calc_period_return(df_prev) if not df_prev.empty else None
        
        item = StockPatternItem(
            ts_code=code,
            pattern_type=int(pattern.value),
            pattern_name=PATTERN_NAME_MAP[pattern],
            curr_return=curr_ret,
            prev_return=prev_ret
        )
        
        pattern_groups_dict[int(pattern.value)].append(item)
    
    # 构建响应
    pattern_groups = [
        PatternGroup(
            pattern_type=pt,
            pattern_name=PATTERN_NAME_MAP.get(PatternType(pt), "未知形态"),
            stocks=stocks
        )
        for pt, stocks in pattern_groups_dict.items()
        if len(stocks) > 0
    ]
    
    # 按形态类型排序
    pattern_groups.sort(key=lambda x: x.pattern_type)
    
    total_stocks = sum(len(g.stocks) for g in pattern_groups)
    
    return PatternResponse(
        period_type=period_type,
        period_months=period_months,
        current_period={
            "start": curr_start.isoformat(),
            "end": curr_end.isoformat()
        },
        previous_period={
            "start": prev_start.isoformat(),
            "end": prev_end.isoformat()
        },
        total_stocks=total_stocks,
        pattern_groups=pattern_groups
    )


@app.get("/api/patterns/{ts_code}")
async def get_single_stock_pattern(
    ts_code: str,
    period_type: str = Query(
        ..., 
        pattern="^(3m|6m|9m|12m|custom)$"
    ),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
):
    """
    获取单个股票的形态分类结果
    
    Args:
        ts_code: 股票代码（如 '000001.SZ'）
        period_type: 周期类型
        start_date: 自定义周期开始日期
        end_date: 自定义周期结束日期
    """
    # 获取最新交易日
    latest_dt = get_latest_trade_date()
    if latest_dt is None:
        raise HTTPException(status_code=500, detail="数据库中尚无交易数据")
    
    # 计算时间窗口
    if period_type == "custom":
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="自定义周期需要提供 start_date 和 end_date")
        (curr_start, curr_end), (prev_start, prev_end) = get_custom_windows(start_date, end_date)
    else:
        months = get_period_months(period_type)
        (curr_start, curr_end), (prev_start, prev_end) = get_period_windows(latest_dt, months)
    
    # 获取数据
    df_curr = get_stock_ohlc_in_range(ts_code, curr_start, curr_end)
    
    if df_curr.empty:
        raise HTTPException(status_code=404, detail=f"股票 {ts_code} 在指定周期内没有数据")
    
    # 分类
    pattern = classify_pattern(df_curr, mode="rule")
    
    # 计算涨跌幅
    df_prev = get_stock_ohlc_in_range(ts_code, prev_start, prev_end)
    curr_ret = calc_period_return(df_curr)
    prev_ret = calc_period_return(df_prev) if not df_prev.empty else None
    
    return {
        "ts_code": ts_code,
        "period_type": period_type,
        "pattern_type": int(pattern.value),
        "pattern_name": PATTERN_NAME_MAP[pattern],
        "current_period": {
            "start": curr_start.isoformat(),
            "end": curr_end.isoformat(),
            "return": curr_ret
        },
        "previous_period": {
            "start": prev_start.isoformat(),
            "end": prev_end.isoformat(),
            "return": prev_ret
        }
    }


@app.get("/api/patterns/summary/{period_type}")
async def get_pattern_summary(
    period_type: str = Path(..., pattern="^(3m|6m|9m|12m|custom)$"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
):
    """
    获取形态分类汇总统计
    """
    # 复用主接口获取数据
    response = await get_patterns(period_type, start_date, end_date, use_cache=False)
    
    # 汇总统计
    summary = {
        "period_type": response.period_type,
        "total_stocks": response.total_stocks,
        "pattern_summary": {}
    }
    
    for group in response.pattern_groups:
        summary["pattern_summary"][group.pattern_name] = {
            "pattern_type": group.pattern_type,
            "count": len(group.stocks),
            "percentage": f"{len(group.stocks) / response.total_stocks * 100:.2f}%" if response.total_stocks > 0 else "0%"
        }
    
    return summary


@app.post("/api/jobs/incremental")
async def trigger_incremental_job():
    """触发增量计算任务"""
    manager = IncrementalJobManager()
    manager.run_incremental()
    return {"status": "started", "message": "增量计算任务已启动"}


@app.post("/api/jobs/full")
async def trigger_full_recalculation():
    """触发全量重算任务"""
    manager = IncrementalJobManager()
    manager.run_full_recalculation()
    return {"status": "started", "message": "全量重算任务已启动"}


# ============== 启动服务 ==============

def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "PatternAnalysis.api_service:app",
        host=API_CONFIG["host"],
        port=API_CONFIG["port"],
        reload=API_CONFIG.get("debug", False)
    )
