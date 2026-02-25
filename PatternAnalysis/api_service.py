"""
股票形态分析系统 - FastAPI服务
提供形态分类API接口
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Query, Path, HTTPException
from pydantic import BaseModel, Field
from typing import Union
from typing import List, Dict, Optional, Union, Tuple
from datetime import date, datetime
from enum import IntEnum

# 配置日志
logger = logging.getLogger(__name__)

# Thread pool for blocking operations
executor = ThreadPoolExecutor(max_workers=10)

from .config import API_CONFIG
from .data_access import (
    get_latest_trade_date,
    get_all_ts_codes,
    get_stock_ohlc_in_range,
    StockDataAccess
)
import pandas as pd
from .periods import (
    get_period_windows,
    get_custom_windows,
    get_period_months,
    validate_period_type,
    PeriodCalculator
)
from .returns import calc_max_drawdown, calc_max_rebound, ReturnCalculator
from .cache import (
    get_cached_rank,
    set_cached_rank,
    get_cached_rank_info,
    clear_rank_cache,
    RankCacheManager
)
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
from .strategy.ATR.atr_stable_period_service import (
    detect_stable_periods_for_stock,
    get_stable_periods_from_redis,
    format_stable_periods_for_api,
    detect_and_save_all_stocks,
    get_all_stocks_with_stable_periods,
    STABLE_PERIOD_STREAM
)

# 申万行业分类相关导入
from orm.sw_query_service import SwIndustryQueryService
import math


def _clean_nan_values(obj):
    """
    递归清理字典/列表中的NaN值，将其转换为None以便JSON序列化
    """
    if isinstance(obj, dict):
        return {k: _clean_nan_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_clean_nan_values(item) for item in obj]
    elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    else:
        return obj


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


class StockRankItem(BaseModel):
    """股票排名单项"""
    rank: int
    ts_code: str
    return_rate: float  # 区间涨跌幅（时间序列收益率）
    max_drawdown_rebound: Optional[float] = None  # 时间序列收益率 = (末日收盘价 - 首日收盘价) / 首日收盘价
    price_range_return_rate: Optional[float] = None  # 区间最高收益 = (区间最高价 - 区间最低价) / 区间最低价（现货卖空概念）


class PaginationParams(BaseModel):
    """分页参数"""
    page: int = Field(default=1, ge=1, description="页码，从1开始")
    page_size: int = Field(default=50, ge=1, le=500, description="每页数量")


class PaginatedStockRankResponse(BaseModel):
    """股票排名分页响应"""
    direction: str
    start_date: str
    end_date: str
    total_stocks: int
    page: int
    page_size: int
    total_pages: int
    rankings: List[StockRankItem]


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


def get_cache_manager() -> RankCacheManager:
    """获取缓存管理器"""
    return RankCacheManager()


# ============== API端点 ==============

@app.get("/api/rank/cache/status")
async def get_cache_status():
    """获取排名缓存状态"""
    manager = RankCacheManager()
    return manager.get_status()


@app.delete("/api/rank/cache")
async def clear_cache():
    """清除排名缓存"""
    manager = RankCacheManager()
    result = manager.clear()
    return result

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


# ============== ATR稳定期相关API ==============

class StablePeriodParams(BaseModel):
    """稳定期检测参数"""
    window: int = Field(default=20, ge=2, le=100, description="CV计算窗口大小（天数）")
    percentile_threshold: float = Field(default=30, ge=0, le=100, description="百分位阈值（30%分位数=低波动期）")
    min_stable_days: int = Field(default=5, ge=1, le=50, description="最少连续稳定天数")
    lookback_period: int = Field(default=241, ge=20, le=500, description="历史数据回溯期（交易日）")


class StablePeriodItem(BaseModel):
    """单个稳定期信息"""
    start_date: str
    end_date: str
    duration_days: int
    avg_atr: float
    atr_cv: float
    stability_score: float


class StablePeriodResponse(BaseModel):
    """稳定期查询响应"""
    ts_code: str
    status: str
    num_stable_periods: int
    total_stable_days: int
    max_stable_days: int = Field(description="stable_periods中最大的duration_days")
    min_stable_days: int = Field(description="查询参数min_stable_days的值，表示返回稳定期的最小天数阈值")
    stable_periods: List[StablePeriodItem]
    summary: Optional[Dict] = None


@app.get("/api/atr/stable-periods/{ts_code}", response_model=StablePeriodResponse)
async def get_stock_stable_periods(
    ts_code: str = Path(..., description="股票代码，如 '000001.SZ'"),
    window: int = Query(20, ge=2, le=100, description="CV计算窗口大小（天数）"),
    percentile_threshold: float = Query(30, ge=0, le=100, description="百分位阈值（30%分位数=低波动期）"),
    min_stable_days: int = Query(5, ge=1, le=50, description="最少连续稳定天数"),
    lookback_period: int = Query(241, ge=20, le=500, description="历史数据回溯期（交易日）"),
    use_cache: bool = Query(True, description="是否使用Redis缓存数据")
):
    """
    获取个股的中低波动稳定期信息
    
    基于ATR（平均真实波幅）的自适应阈值算法，识别个股的低波动稳定期。
    
    **算法说明：**
    - 使用变异系数（CV = 标准差/均值）衡量ATR的波动稳定性
    - 动态阈值：根据历史CV数据的百分位数自适应调整
    - 稳定期判定：CV < 动态阈值 且 连续稳定天数 >= min_stable_days
    
    **参数说明：**
    - window: 计算CV的滚动窗口大小，建议值20天
    - percentile_threshold: 百分位阈值，建议值30%（表示低于历史30%的CV值）
    - min_stable_days: 最少连续稳定天数阈值，只有连续稳定天数 >= min_stable_days 的才会被识别为稳定期
    - lookback_period: 历史数据回溯期，建议值241天（一年交易日）
    
    **min_stable_days 逻辑说明：**
    - 该参数用于过滤稳定期，只有duration_days >= min_stable_days的稳定期才会返回
    - 返回响应中的min_stable_days字段即为查询时使用的参数值
    - max_stable_days是stable_periods列表中最大的duration_days
    
    **返回示例：**
    ```json
    {
        "ts_code": "000001.SZ",
        "status": "success",
        "num_stable_periods": 2,
        "total_stable_days": 45,
        "max_stable_days": 26,
        "min_stable_days": 5,
        "stable_periods": [
            {
                "start_date": "2024-01-15",
                "end_date": "2024-02-10",
                "duration_days": 26,
                "avg_atr": 1.85,
                "atr_cv": 0.045,
                "stability_score": 0.955
            }
        ]
    }
    ```
    """
    # 尝试从缓存获取
    if use_cache:
        cached_data = get_stable_periods_from_redis(ts_code)
        if cached_data and cached_data.get("records"):
            records_data = cached_data["records"]
            summary = cached_data.get("summary", {})
            
            stable_periods = [
                StablePeriodItem(
                    start_date=r["start_date"],
                    end_date=r["end_date"],
                    duration_days=r["duration_days"],
                    avg_atr=r["avg_atr"],
                    atr_cv=r["atr_cv"],
                    stability_score=r["stability_score"]
                )
                for r in records_data
            ]
            
            # 计算max_stable_days
            max_stable_days = max((r.duration_days for r in stable_periods), default=0)
            
            return StablePeriodResponse(
                ts_code=ts_code,
                status="cached",
                num_stable_periods=len(stable_periods),
                total_stable_days=sum(r.duration_days for r in stable_periods),
                max_stable_days=max_stable_days,
                min_stable_days=min_stable_days,
                stable_periods=stable_periods,
                summary=summary
            )
    
    # 实时计算
    records, summary = detect_stable_periods_for_stock(
        ts_code=ts_code,
        window=window,
        percentile_threshold=percentile_threshold,
        min_stable_days=min_stable_days,
        lookback_period=lookback_period
    )
    
    if summary.get("status") == "insufficient_data":
        raise HTTPException(
            status_code=400,
            detail=f"数据不足: 需要至少 {summary.get('required', 241)} 个数据点，当前只有 {summary.get('data_points', 0)} 个"
        )
    
    # 格式化结果
    stable_periods = [
        StablePeriodItem(
            start_date=r.start_date,
            end_date=r.end_date,
            duration_days=r.duration_days,
            avg_atr=r.avg_atr,
            atr_cv=r.atr_cv,
            stability_score=r.stability_score
        )
        for r in records
    ]
    
    # 计算max_stable_days
    max_stable_days = max((r.duration_days for r in stable_periods), default=0)
    
    return StablePeriodResponse(
        ts_code=ts_code,
        status="computed",
        num_stable_periods=len(stable_periods),
        total_stable_days=sum(r.duration_days for r in stable_periods),
        max_stable_days=max_stable_days,
        min_stable_days=min_stable_days,
        stable_periods=stable_periods,
        summary=summary
    )


@app.get("/api/atr/stable-periods/index")
async def get_stable_periods_index():
    """
    获取所有已计算稳定期的股票列表
    
    返回所有已有中低波动稳定期数据的股票代码。
    """
    stocks = get_all_stocks_with_stable_periods()
    return {
        "total": len(stocks),
        "stocks": stocks
    }


@app.post("/api/atr/stable-periods/recalculate")
async def recalculate_stable_periods(
    window: int = Query(20, ge=2, le=100),
    percentile_threshold: float = Query(30, ge=0, le=100),
    min_stable_days: int = Query(5, ge=1, le=50),
    lookback_period: int = Query(241, ge=20, le=500)
):
    """
    触发全量重新计算所有股票的稳定期
    
    这是一个耗时操作，会在后台批量处理所有股票。
    """
    import asyncio
    
    def run_detection():
        return detect_and_save_all_stocks(
            window=window,
            percentile_threshold=percentile_threshold,
            min_stable_days=min_stable_days,
            lookback_period=lookback_period
        )
    
    # 在线程池中运行（避免阻塞）
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(executor, run_detection)
    
    return {
        "status": "started",
        "message": f"全量计算已启动，共 {result.get('total_stocks', 0)} 只股票",
        "result": result
    }


def _compute_drawdown_rebound(args):
    """计算回撤或反弹（异步操作）"""
    ts_code, start_date, end_date, direction = args
    try:
        df = get_stock_ohlc_in_range(ts_code, start_date, end_date)
        if df.empty or len(df) < 2:
            return None, None
        
        # Calculate max drawdown or rebound
        if direction == "up":
            max_drawdown = calc_max_drawdown(df)
            metric = abs(max_drawdown) if max_drawdown else 0
        else:
            max_rebound = calc_max_rebound(df)
            metric = max_rebound if max_rebound else 0
        
        return ts_code, round(metric * 100, 2)
    except Exception as e:
        logger.error(f"计算股票 {ts_code} 回撤/反弹失败: {e}")
        return ts_code, None


def _async_refresh_drawdown_rebound(ts_codes: List[str], start_date: date, end_date: date, direction: str):
    """异步刷新回撤/反弹数据到缓存"""
    logger.info(f"开始异步计算回撤/反弹，共 {len(ts_codes)} 只股票")
    
    args_list = [(code, start_date, end_date, direction) for code in ts_codes]
    
    with ThreadPoolExecutor(max_workers=5) as exec:
        futures = [exec.submit(_compute_drawdown_rebound, args) for args in args_list]
        
        updated = 0
        for future in futures:
            ts_code, metric = future.result()
            if metric is not None:
                # 更新缓存
                updated += 1
        
    logger.info(f"异步计算完成，更新 {updated} 只股票的 回撤/反弹 数据")


@app.post("/api/rank", response_model=PaginatedStockRankResponse)
async def get_stock_rank(
    direction: str = Query(
        ...,
        pattern="^(up|down)$",
        description="Ranking direction: up(gainers) or down(losers)"
    ),
    start_date: date = Query(
        ...,
        description="Start date"
    ),
    end_date: date = Query(
        ...,
        description="End date"
    ),
    limit: int = Query(
        default=150,
        ge=1,
        le=500,
        description="Number of results (default: 150)"
    ),
    use_cache: bool = Query(
        default=True,
        description="Whether to use cached data"
    ),
    pagination: Optional[PaginationParams] = None
):
    """
    Get stock ranking (gainers/losers) with pagination

    策略：
    1. 快速返回涨跌幅排名
    2. 回撤/反弹数据异步计算并更新缓存

    Args:
        Query params: direction, start_date, end_date, limit, use_cache
        Body: pagination (page, page_size)
    """
    import time
    
    start_time = time.time()
    
    # 处理分页参数
    page = pagination.page if pagination else 1
    pagination_page_size = pagination.page_size if pagination else None
    
    # 如果有pagination，使用pagination的page_size；否则使用limit
    # pagination用于分页展示，但总数不能超过limit
    effective_page_size = pagination_page_size if pagination_page_size else limit
    page_size = min(effective_page_size, limit)
    
    logger.info(f"开始计算股票排名: direction={direction}, start={start_date}, end={end_date}, page={page}, page_size={page_size}, limit={limit}")
    
    if start_date >= end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be less than end_date"
        )
    
    # 尝试从缓存获取完整数据
    if use_cache:
        logger.info("尝试从缓存获取完整数据...")
        cached_data = get_cached_rank(direction, start_date, end_date)
        if cached_data:
            # 检查是否所有记录都有回撤/反弹数据
            all_have_metric = all(item.get("max_drawdown_rebound") is not None for item in cached_data)
            if all_have_metric:
                logger.info(f"缓存命中且数据完整，获取到 {len(cached_data)} 条记录")
                
                # 计算分页
                # 使用page_size进行分页，确保总数不超过limit
                actual_page_size = min(page_size, limit)
                actual_total_count = len(cached_data)
                effective_total = min(actual_total_count, limit)  # 有效记录数不超过limit
                
                # total_stocks设置为limit参数值（而非实际股票数量）
                total_stocks = limit
                total_pages = (effective_total + actual_page_size - 1) // actual_page_size
                start_idx = (page - 1) * actual_page_size
                end_idx = min(start_idx + actual_page_size, effective_total)
                
                # 获取当前页数据
                page_data = cached_data[start_idx:end_idx]
                rankings = [
                    StockRankItem(
                        rank=start_idx + i + 1,
                        ts_code=item["ts_code"],
                        return_rate=item["return_rate"],
                        max_drawdown_rebound=item.get("max_drawdown_rebound"),
                        price_range_return_rate=item.get("price_range_return_rate")
                    )
                    for i, item in enumerate(page_data)
                ]
                
                elapsed = time.time() - start_time
                logger.info(f"缓存查询完成，耗时: {elapsed:.2f}秒")
                return PaginatedStockRankResponse(
                    direction=direction,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                    total_stocks=total_stocks,
                    page=page,
                    page_size=page_size,
                    total_pages=total_pages,
                    rankings=rankings
                )
            else:
                logger.info("缓存存在但数据不完整，需要补充回撤/反弹数据")
    
    # 快速获取股票列表
    logger.info("正在获取股票列表...")
    ts_codes = get_all_ts_codes()
    logger.info(f"获取到 {len(ts_codes)} 只股票")
    
    # 阶段1：使用SQL批量计算涨跌幅（极速）
    logger.info("阶段1：使用SQL批量计算涨跌幅...")
    phase1_start = time.time()
    
    access = StockDataAccess()
    results_df = access.get_stock_returns_in_range(start_date, end_date, direction)
    
    # 转换为列表格式
    raw_results = []
    for _, row in results_df.iterrows():
        raw_results.append({
            "ts_code": row["ts_code"],
            "return_rate": float(row["return_rate"]),
            "max_drawdown_rebound": float(row["max_drawdown_rebound"]) if pd.notna(row.get("max_drawdown_rebound")) else None,
            "price_range_return_rate": float(row["price_range_return_rate"]) if pd.notna(row.get("price_range_return_rate")) else None
        })
    
    phase1_elapsed = time.time() - phase1_start
    logger.info(f"阶段1完成：通过SQL计算了 {len(raw_results)} 只股票的涨跌幅，耗时: {phase1_elapsed:.2f}秒")
    
    # 排序
    if direction == "up":
        raw_results.sort(key=lambda x: x["return_rate"], reverse=True)
    else:
        raw_results.sort(key=lambda x: x["return_rate"])
    
    # 缓存初步结果（无回撤/反弹）
    if use_cache:
        logger.info("缓存初步结果（无回撤/反弹）...")
        set_cached_rank(direction, start_date, end_date, raw_results)
    
    # 阶段2：异步计算回撤/反弹（后台执行）
    logger.info("阶段2：启动异步计算回撤/反弹...")
    phase2_start = time.time()
    
    # 需要计算回撤/反弹的股票列表
    pending_codes = [r["ts_code"] for r in raw_results]
    
    # 在后台线程中计算
    def async_compute(pending_codes: List[str], direction: str, start_date: date, end_date: date, use_cache: bool):
        """异步计算回撤/反弹并更新缓存"""
        try:
            logger.info(f"异步任务开始: 计算 {len(pending_codes)} 只股票的回撤/反弹")
            start = time.time()
            
            # 重新获取缓存数据
            if use_cache:
                cached = get_cached_rank(direction, start_date, end_date)
                if cached:
                    raw_results_async = cached
                else:
                    raw_results_async = raw_results
            else:
                raw_results_async = raw_results
            
            with ThreadPoolExecutor(max_workers=5) as exec:
                futures = [
                    exec.submit(_compute_drawdown_rebound, (code, start_date, end_date, direction))
                    for code in pending_codes
                ]
                
                updated_count = 0
                for future in futures:
                    ts_code, metric = future.result()
                    if metric is not None:
                        # 更新缓存中的记录
                        for item in raw_results_async:
                            if item["ts_code"] == ts_code:
                                item["max_drawdown_rebound"] = metric
                                updated_count += 1
                                break
                
                # 重新缓存完整数据
                if use_cache:
                    set_cached_rank(direction, start_date, end_date, raw_results_async)
                
                elapsed = time.time() - start
                logger.info(f"异步计算完成：更新了 {updated_count} 只股票的回撤/反弹数据，耗时: {elapsed:.2f}秒")
        except Exception as e:
            logger.error(f"异步计算回撤/反弹失败: {e}")
    
    # ============================================================
    # 阶段2：异步计算回撤/反弹（已注释，不再使用）
    # 由于max_drawdown_rebound现在直接通过SQL计算，此异步逻辑已屏蔽
    # ============================================================
    # loop = asyncio.get_running_loop()
    # loop.create_task(asyncio.to_thread(async_compute, pending_codes, direction, start_date, end_date, use_cache))
    logger.info("阶段2已屏蔽：max_drawdown_rebound现在直接通过SQL计算")
    
    # 计算分页
    actual_page_size = min(page_size, limit)
    actual_total_count = len(raw_results)
    effective_total = min(actual_total_count, limit)  # 有效记录数不超过limit
    total_pages = (effective_total + actual_page_size - 1) // actual_page_size
    start_idx = (page - 1) * actual_page_size
    end_idx = min(start_idx + actual_page_size, effective_total)
    
    # total_stocks设置为limit参数值（而非实际股票数量）
    total_stocks = limit
    
    # 获取当前页数据
    page_data = raw_results[start_idx:end_idx]
    rankings = [
        StockRankItem(
            rank=start_idx + i + 1,
            ts_code=item["ts_code"],
            return_rate=item["return_rate"],
            max_drawdown_rebound=item.get("max_drawdown_rebound"),
            price_range_return_rate=item.get("price_range_return_rate")
        )
        for i, item in enumerate(page_data)
    ]
    
    elapsed = time.time() - start_time
    logger.info(f"初步结果返回，涨跌幅排名计算耗时: {elapsed:.2f}秒，回撤/反弹数据正在后台计算中")
    
    return PaginatedStockRankResponse(
        direction=direction,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        total_stocks=total_stocks,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        rankings=rankings
    )


# ============== 申万行业分类API ==============

@app.get("/api/sw/industry-tree")
async def get_sw_industry_tree(
    src: str = Query("SW2021", description="申万版本: SW2014 或 SW2021")
):
    """
    获取申万行业分类树形结构
    
    返回申万行业的三级分类树形数据，可用于前端生成目录树。
    树形结构为: 一级行业 -> 二级行业 -> 三级行业
    
    **返回示例：**
    ```json
    [
        {
            "node_code": "801010",
            "node_name": "农林牧渔",
            "level": 1,
            "children": [
                {
                    "node_code": "801020",
                    "node_name": "农林牧渔基础化工",
                    "level": 2,
                    "children": [
                        {
                            "node_code": "801030",
                            "node_name": "农药",
                            "level": 3,
                            "children": []
                        }
                    ]
                }
            ]
        }
    ]
    ```
    """
    try:
        tree = SwIndustryQueryService.get_industry_tree(src=src)
        # 清理NaN值以确保JSON序列化正常
        tree = _clean_nan_values(tree)
        return {
            "status": "success",
            "src": src,
            "total_l1": sum(1 for item in tree if item.get('level') == 1),
            "tree": tree
        }
    except Exception as e:
        logger.error(f"获取申万行业树失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取申万行业树失败: {str(e)}")


@app.get("/api/sw/industry-list")
async def get_sw_industry_list(
    level: int = Query(None, ge=1, le=3, description="行业层级: 1=一级, 2=二级, 3=三级, 不传则返回全部"),
    src: str = Query("SW2021", description="申万版本: SW2014 或 SW2021")
):
    """
    获取申万行业分类列表
    
    返回指定层级的行业列表，可用于下拉选择等场景。
    """
    try:
        df = SwIndustryQueryService.get_industry_list(level=level, src=src)
        if df is None or df.empty:
            return {
                "status": "success",
                "level": level,
                "src": src,
                "total": 0,
                "list": []
            }
        
        # 转换为字典列表，排除pandas相关的列
        df = df.fillna("")
        records = df.to_dict('records')
        # 清理NaN值以确保JSON序列化正常
        records = _clean_nan_values(records)
        
        return {
            "status": "success",
            "level": level,
            "src": src,
            "total": len(records),
            "list": records
        }
    except Exception as e:
        logger.error(f"获取申万行业列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取申万行业列表失败: {str(e)}")


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
