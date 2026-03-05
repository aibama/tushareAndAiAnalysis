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
    STABLE_PERIOD_STREAM,
    filter_stocks_by_market_factor,
    calculate_stocks_market_cap_by_codes,
    calculate_stock_market_cap,
    preheat_market_cap_cache
)

# 涨停跌停主题分析相关导入
from .strategy.theme.limit_service import (
    get_stock_limit_info,
    calculate_limit_prices_for_all_stocks,
    save_limit_info_to_redis,
    get_limit_info_from_redis,
    get_all_limit_stock_codes,
    LimitPriceInfo
)

# 成交量主题分析相关导入
from .strategy.theme.volume_service import (
    get_stock_lowest_price_volume,
    get_stock_limit_up_volume,
    calculate_lowest_price_volume_for_all_stocks,
    calculate_limit_up_volume_for_all_stocks,
    save_lowest_price_volume_to_redis,
    get_lowest_price_volume_from_redis,
    save_limit_up_volume_to_redis,
    get_limit_up_volume_from_redis,
    LowestPriceVolumeInfo,
    LimitUpVolumeInfo
)

# 申万行业分类相关导入
from orm.sw_query_service import SwIndustryQueryService, SwStockQueryService
import math


def get_stock_names_batch(ts_codes: List[str]) -> Dict[str, str]:
    """
    批量获取股票名称

    参数:
        ts_codes: 股票代码列表

    返回:
        Dict: 键为股票代码，值为股票名称
    """
    if not ts_codes:
        return {}

    from orm.database import query_df

    # 构建IN子句
    placeholders = ','.join([f"'{code}'" for code in ts_codes])

    # 首先尝试从 stockinfobase 表获取（通过ts_code关联）
    sql = f"""
        SELECT ts_code, name
        FROM stockinfobase
        WHERE ts_code IN ({placeholders})
    """

    result = {}

    try:
        df = query_df(sql)
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                if row['ts_code'] and row['name']:
                    result[row['ts_code']] = row['name']
    except Exception as e:
        print(f"从stockinfobase查询失败: {e}")

    # 如果还有未找到的，尝试从tushare获取
    missing_codes = [c for c in ts_codes if c not in result]
    if missing_codes:
        try:
            import tushare as ts
            from PatternAnalysis.config import TUSHARE_CONFIG
            pro = ts.pro_api(TUSHARE_CONFIG['token'])

            # 获取所有未找到的股票
            for code in missing_codes:
                # 转换代码格式: 000001.SZ -> 000001.SZ
                try:
                    df_tushare = pro.stock_basic(ts_code=code, fields='ts_code,name')
                    if df_tushare is not None and not df_tushare.empty:
                        name = df_tushare.iloc[0]['name']
                        if name:
                            result[code] = name
                except Exception:
                    pass
        except Exception as e:
            print(f"从tushare查询失败: {e}")

    return result


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

    # 启动时预热ATR稳定期缓存
    try:
        print("正在检查ATR稳定期缓存...")
        # 检查是否已有缓存数据
        existing_stocks = get_all_stocks_with_stable_periods()
        if not existing_stocks:
            print("未发现ATR稳定期缓存，开始预热计算...")
            # 在后台线程中运行，避免阻塞启动
            import threading
            def preheat_atr_cache():
                try:
                    detect_and_save_all_stocks(
                        window=20,
                        percentile_threshold=30,
                        min_stable_days=5,
                        lookback_period=241
                    )
                    print("ATR稳定期缓存预热完成")
                except Exception as e:
                    print(f"ATR稳定期缓存预热失败: {e}")

            preheat_thread = threading.Thread(target=preheat_atr_cache, daemon=True)
            preheat_thread.start()
        else:
            print(f"发现已有ATR稳定期缓存，共 {len(existing_stocks)} 只股票")
    except Exception as e:
        print(f"警告: ATR稳定期缓存检查失败 (服务仍可启动): {e}")


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
    stock_name: Optional[str] = None  # 股票名称
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


# ============== 涨停跌停主题分析相关模型 ==============

class LimitPriceInfoResponse(BaseModel):
    """涨停跌停信息响应"""
    ts_code: str
    limit_up_date: Optional[str] = None
    limit_up_price: Optional[float] = None
    limit_down_date: Optional[str] = None
    limit_down_price: Optional[float] = None
    latest_close: Optional[float] = None
    sm_pre_up: Optional[float] = None
    sm_pre_down: Optional[float] = None


class LimitStockListResponse(BaseModel):
    """涨停/跌停股票列表响应"""
    limit_type: str
    total: int
    ts_codes: List[str]


class CalculateAllResponse(BaseModel):
    """批量计算响应"""
    status: str
    total_stocks: int
    limit_up_count: int
    limit_down_count: int
    message: str


# ============== 成交量主题分析相关模型 ==============

class LowestPriceVolumeResponse(BaseModel):
    """历史最低价成交量响应"""
    ts_code: str
    lowest_price: Optional[float] = None
    lowest_price_date: Optional[str] = None
    pre_month_start: Optional[str] = None
    pre_month_end: Optional[str] = None
    pre_month_avg_volume: Optional[float] = None
    pre_month_trading_days: Optional[int] = None
    post_month_start: Optional[str] = None
    post_month_end: Optional[str] = None
    post_month_avg_volume: Optional[float] = None
    post_month_trading_days: Optional[int] = None
    total_avg_volume: Optional[float] = None
    total_trading_days: Optional[int] = None


class LimitUpVolumeResponse(BaseModel):
    """涨停后成交量响应"""
    ts_code: str
    limit_up_date: Optional[str] = None
    limit_up_price: Optional[float] = None
    limit_up_volume: Optional[float] = None
    days_since_limit_up: Optional[int] = None
    cumulative_volume: Optional[float] = None
    post_limit_avg_volume: Optional[float] = None
    volume_ratio: Optional[float] = None


class VolumeBatchCalculateResponse(BaseModel):
    """成交量批量计算响应"""
    status: str
    total_stocks: int
    message: str


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


@app.get("/api/rank/test-stock-names")
async def test_stock_names(
    ts_codes: str = Query(..., description="股票代码，逗号分隔，如 '000001.SZ,000002.SZ'")
):
    """测试股票名称查询"""
    code_list = [code.strip() for code in ts_codes.split(',')]
    stock_names = get_stock_names_batch(code_list)
    return {
        "requested_codes": code_list,
        "stock_names": stock_names,
        "count": len(stock_names)
    }

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


# ============== 板块过滤函数 ==============

def filter_stocks_by_sector(ts_codes: List[str], sector: Optional[str]) -> List[str]:
    """
    按板块筛选股票
    
    参数:
        ts_codes: 股票代码列表
        sector: 板块代码
            - SH: 沪市主板 (600, 601, 603, 605)
            - SZ: 深市主板 (000, 001, 002, 003, 004)
            - CY: 创业板 (300, 301)
            - KC: 科创板 (688)
            - None/空: 不限制，返回全部
    
    返回:
        筛选后的股票代码列表
    """
    if not ts_codes or not sector:
        return ts_codes
    
    sector = sector.upper()
    
    # 定义各板块的股票代码前缀
    sector_prefixes = {
        'SH': ('600', '601', '603', '605'),  # 沪市主板
        'SZ': ('000', '001', '002', '003', '004'),  # 深市主板
        'CY': ('300', '301'),  # 创业板
        'KC': ('688',)  # 科创板
    }
    
    prefixes = sector_prefixes.get(sector)
    if not prefixes:
        # 无效的板块代码，返回全部
        return ts_codes
    
    # 过滤
    filtered = []
    for code in ts_codes:
        # 提取数字部分（去掉.SZ/.SH后缀）
        prefix = code.split('.')[0] if '.' in code else code[:3]
        # 检查是否以指定前缀开头
        for p in prefixes:
            if prefix.startswith(p):
                filtered.append(code)
                break
    
    return filtered


# 注意：固定路径的index路由必须放在{ts_code}参数路由之前，否则/index会被匹配为ts_code参数
@app.get("/api/atr/stable-periods/index")
async def get_stable_periods_index(
    market_factor: Optional[str] = Query(
        None,
        description="市值因子筛选: 0Y-100Y(一 hundred亿以下), 100Y-200Y, 200Y-400Y, 400Y-3000000Y"
    ),
    full_path: Optional[str] = Query(
        None,
        description="申万行业分类路径筛选，如 '801010.801020.801030'"
    ),
    sector: Optional[str] = Query(
        None,
        description="板块筛选: SH(沪市主板), SZ(深市主板), CY(创业板), KC(科创板)"
    ),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(50, ge=1, le=500, description="每页数量")
):
    """
    获取所有已计算稳定期的股票列表，支持市值和行业筛选

    **参数说明：**
    - market_factor: 市值因子筛选
        - 0Y-100Y: 一百亿以下
        - 100Y-200Y: 一百亿至两百亿
        - 200Y-400Y: 两百亿至四百亿
        - 400Y-3000000Y: 四百亿以上
    - full_path: 申万行业分类路径筛选（支持三级路径，如 '801010.801020.801030'）
    - page: 页码（默认1）
    - page_size: 每页数量（默认50，最大500）

    **返回示例：**
    ```json
    {
        "total": 1000,
        "page": 1,
        "page_size": 50,
        "total_pages": 20,
        "stocks": [
            {
                "ts_code": "000001.SZ",
                "market_cap": 15000000000,
                "sw_industry": {
                    "l1_name": "银行",
                    "l2_name": "股份制银行",
                    "l3_name": "股份制银行"
                }
            }
        ]
    }
    ```
    """
    # 1. 获取所有有稳定期数据的股票列表
    stocks = get_all_stocks_with_stable_periods()

    # 2. 如果提供了full_path参数，通过申万概念分类筛选
    if full_path:
        logger.info(f"按申万行业筛选: full_path={full_path}")
        
        # 查询符合条件的股票
        from orm.sw_query_service import SwStockQueryService
        from orm.database import query_df

        # 前端传入逻辑:
        # - level=1: 传入l1_code (如 801030.SI)
        # - level=2: 传入l2_code (如 220800)
        # - level=3: 传入l3_code (如 850333.SI)
        
        input_val = full_path.strip()
        df_sw = None
        
        # 根据是否包含.SI后缀来判断传入的是哪个层级
        # l1_code 和 l3_code 有.SI后缀，l2_code 没有.SI后缀
        if input_val.endswith('.SI'):
            # 可能是 l1_code 或 l3_code (都有.SI)
            # 优先匹配 node_code，因为最精确
            sql = """
                SELECT DISTINCT r.ts_code
                FROM stock_sw_relation r
                JOIN sw_industry s ON r.sw_node_code = s.node_code
                WHERE r.is_latest = 1 AND s.node_code = %s
            """
            params = {'node_code': input_val}
            df_sw = query_df(sql, params)
            
            # 如果没匹配到，尝试 l1_code
            if df_sw is None or df_sw.empty:
                sql = """
                    SELECT DISTINCT r.ts_code
                    FROM stock_sw_relation r
                    JOIN sw_industry s ON r.sw_node_code = s.node_code
                    WHERE r.is_latest = 1 AND s.l1_code = %s
                """
                params = {'l1_code': input_val}
                df_sw = query_df(sql, params)
            
            # 如果还没匹配到，尝试 l3_code
            if df_sw is None or df_sw.empty:
                sql = """
                    SELECT DISTINCT r.ts_code
                    FROM stock_sw_relation r
                    JOIN sw_industry s ON r.sw_node_code = s.node_code
                    WHERE r.is_latest = 1 AND s.l3_code = %s
                """
                params = {'l3_code': input_val}
                df_sw = query_df(sql, params)
        else:
            # 没有.SI后缀，可能是 l2_code (如 220800)
            sql = """
                SELECT DISTINCT r.ts_code
                FROM stock_sw_relation r
                JOIN sw_industry s ON r.sw_node_code = s.node_code
                WHERE r.is_latest = 1 AND s.l2_code = %s
            """
            params = {'l2_code': input_val}
            df_sw = query_df(sql, params)
            
            # 如果没匹配到，尝试带.SI后缀的版本(l1_code或l3_code)
            if df_sw is None or df_sw.empty:
                input_with_suffix = input_val + '.SI'
                sql = """
                    SELECT DISTINCT r.ts_code
                    FROM stock_sw_relation r
                    JOIN sw_industry s ON r.sw_node_code = s.node_code
                    WHERE r.is_latest = 1 AND s.l1_code = %s
                """
                params = {'l1_code': input_with_suffix}
                df_sw = query_df(sql, params)
                
                if df_sw is None or df_sw.empty:
                    sql = """
                        SELECT DISTINCT r.ts_code
                        FROM stock_sw_relation r
                        JOIN sw_industry s ON r.sw_node_code = s.node_code
                        WHERE r.is_latest = 1 AND s.l3_code = %s
                    """
                    params = {'l3_code': input_with_suffix}
                    df_sw = query_df(sql, params)

        if df_sw is not None and not df_sw.empty:
            sw_stocks = set(df_sw['ts_code'].tolist())
            # 取交集
            stocks = list(set(stocks) & sw_stocks)
            logger.info(f"申万行业筛选后股票数量: {len(stocks)}")

        df_sw = query_df(sql, params)
        if df_sw is not None and not df_sw.empty:
            sw_stocks = set(df_sw['ts_code'].tolist())
            # 取交集
            stocks = list(set(stocks) & sw_stocks)
            logger.info(f"申万行业筛选后股票数量: {len(stocks)}")

    # 3. 如果提供了market_factor参数，通过市值筛选
    if market_factor:
        logger.info(f"按市值筛选: market_factor={market_factor}")
        stocks = filter_stocks_by_market_factor(stocks, market_factor)

    # 4. 如果提供了sector参数，通过板块筛选
    if sector:
        logger.info(f"按板块筛选: sector={sector}")
        stocks = filter_stocks_by_sector(stocks, sector)

    # 5. 计算总数和分页
    total_stocks = len(stocks)
    total_pages = (total_stocks + page_size - 1) // page_size
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_stocks)

    # 5. 获取当前页的股票数据
    page_stocks = stocks[start_idx:end_idx]

    # 6. 批量获取市值、申万行业信息和股票名称（优化版）
    # 6.1 批量获取市值
    market_caps = calculate_stocks_market_cap_by_codes(page_stocks)

    # 6.2 批量获取申万行业信息
    from orm.sw_query_service import SwStockQueryService
    sw_industries = SwStockQueryService.get_stocks_industry_batch(page_stocks)

    # 6.3 批量获取股票名称
    stock_names = get_stock_names_batch(page_stocks)

    # 6.4 组装结果
    result_stocks = []
    for ts_code in page_stocks:
        item = {"ts_code": ts_code}

        # 获取股票名称
        stock_name = stock_names.get(ts_code)
        if stock_name:
            item["stock_name"] = stock_name

        # 获取市值
        market_cap = market_caps.get(ts_code)
        if market_cap:
            item["market_cap"] = market_cap
            # 转换为亿元
            item["market_cap_yi"] = round(market_cap / 1e8, 2)

        # 获取申万行业信息
        sw_info = sw_industries.get(ts_code)
        if sw_info:
            item["sw_industry"] = sw_info

        result_stocks.append(item)

    return {
        "total": total_stocks,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "stocks": result_stocks
    }


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


@app.post("/api/market-cap/preheat")
async def preheat_market_cap():
    """
    预热市值缓存

    批量计算所有股票的市值并存入Redis缓存，提高后续查询性能。
    这是一个耗时操作，首次调用或缓存过期后需要运行。
    """
    import asyncio

    def run_preheat():
        return preheat_market_cap_cache()

    # 在线程池中运行（避免阻塞）
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(executor, run_preheat)

    return {
        "status": "completed",
        "message": f"市值缓存预热完成，共缓存 {result} 只股票的市值",
        "cached_count": result
    }


# ============== 涨停跌停主题分析API ==============

@app.get("/api/limit/{ts_code}", response_model=LimitPriceInfoResponse)
async def get_stock_limit_info_endpoint(
    ts_code: str = Path(..., description="股票代码，如 '000001.SZ'"),
    use_cache: bool = Query(True, description="是否使用Redis缓存数据")
):
    """
    获取个股的涨停跌停信息

    返回个股的涨停/跌停信息，包括：
    - 最近涨停日期和涨停价格 (SMLP)
    - 最近跌停日期和跌停价格
    - 最近收盘价
    - 收盘价/涨停价比 (SM_PRE_UP)
    - 收盘价/跌停价比 (SM_PRE_DOWN)

    **核心概念：**
    - SMLP (STOCK_MAX_LASTEST_PRICE): 最近一次涨停的价格
    - SM_PRE: 最近收盘价与SMLP的比值 = 最近收盘价 / SMLP
      - SM_PRE > 1: 当前收盘价高于上次涨停价
      - SM_PRE < 1: 当前收盘价低于上次涨停价
    - 跌停逻辑类似

    **返回示例：**
    ```json
    {
        "ts_code": "000001.SZ",
        "limit_up_date": "2024-01-15",
        "limit_up_price": 10.50,
        "limit_down_date": null,
        "limit_down_price": null,
        "latest_close": 11.20,
        "sm_pre_up": 1.0667,
        "sm_pre_down": null
    }
    ```
    """
    # 优先从Redis获取
    if use_cache:
        cached = get_limit_info_from_redis(ts_code)
        if cached:
            return LimitPriceInfoResponse(
                ts_code=cached.ts_code,
                limit_up_date=cached.limit_up_date,
                limit_up_price=cached.limit_up_price,
                limit_down_date=cached.limit_down_date,
                limit_down_price=cached.limit_down_price,
                latest_close=cached.latest_close,
                sm_pre_up=cached.sm_pre_up,
                sm_pre_down=cached.sm_pre_down
            )

    # 从数据库计算
    info = get_stock_limit_info(ts_code, use_cache=False)

    if info is None:
        raise HTTPException(
            status_code=404,
            detail=f"未找到股票 {ts_code} 的数据"
        )

    # 如果启用缓存，保存到Redis
    if use_cache:
        save_limit_info_to_redis(info)

    return LimitPriceInfoResponse(
        ts_code=info.ts_code,
        limit_up_date=info.limit_up_date,
        limit_up_price=info.limit_up_price,
        limit_down_date=info.limit_down_date,
        limit_down_price=info.limit_down_price,
        latest_close=info.latest_close,
        sm_pre_up=info.sm_pre_up,
        sm_pre_down=info.sm_pre_down
    )


@app.get("/api/limit/list/{limit_type}", response_model=LimitStockListResponse)
async def get_limit_stock_list(
    limit_type: str = Path(
        ...,
        pattern="^(up|down)$",
        description="类型: up(涨停) 或 down(跌停)"
    )
):
    """
    获取所有有涨停/跌停记录的股票代码列表

    从Redis中获取所有曾经涨停或跌停的股票代码列表。

    **返回示例：**
    ```json
    {
        "limit_type": "up",
        "total": 150,
        "ts_codes": ["000001.SZ", "000002.SZ", "600000.SH"]
    }
    ```
    """
    ts_codes = get_all_limit_stock_codes(limit_type)

    return LimitStockListResponse(
        limit_type=limit_type,
        total=len(ts_codes),
        ts_codes=ts_codes
    )


@app.post("/api/limit/recalculate")
async def recalculate_all_stocks_limit(
    num_threads: int = Query(4, ge=1, le=16, description="计算线程数")
):
    """
    触发全量重新计算所有股票的涨停跌停信息

    这是一个耗时操作，会在后台批量处理所有股票。

    **参数说明：**
    - num_threads: 并行计算的线程数，建议值为4-8

    **返回示例：**
    ```json
    {
        "status": "started",
        "total_stocks": 5000,
        "limit_up_count": 3200,
        "limit_down_count": 1800,
        "message": "全量计算已启动"
    }
    ```
    """
    import asyncio

    def run_calculation():
        results = calculate_limit_prices_for_all_stocks(num_threads=num_threads)

        # 统计有涨停/跌停的股票数量
        limit_up_count = sum(1 for r in results if r.limit_up_date)
        limit_down_count = sum(1 for r in results if r.limit_down_date)

        return {
            "total_stocks": len(results),
            "limit_up_count": limit_up_count,
            "limit_down_count": limit_down_count
        }

    # 在线程池中运行（避免阻塞）
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(executor, run_calculation)

    return {
        "status": "completed",
        "total_stocks": result["total_stocks"],
        "limit_up_count": result["limit_up_count"],
        "limit_down_count": result["limit_down_count"],
        "message": f"全量计算完成，共处理 {result['total_stocks']} 只股票"
    }


@app.get("/api/limit/summary")
async def get_limit_summary():
    """
    获取涨停跌停汇总统计

    返回当前系统中涨停/跌停股票的统计信息。

    **返回示例：**
    ```json
    {
        "limit_up_count": 3200,
        "limit_down_count": 1800,
        "total_analyzed": 5000
    }
    ```
    """
    # 获取涨停和跌停的股票列表
    up_codes = get_all_limit_stock_codes("up")
    down_codes = get_all_limit_stock_codes("down")

    # 获取去重后的总数
    all_codes = set(up_codes) | set(down_codes)

    return {
        "limit_up_count": len(up_codes),
        "limit_down_count": len(down_codes),
        "total_analyzed": len(all_codes)
    }


# ============== 成交量主题分析API ==============

@app.get("/api/volume/lowest-price/{ts_code}", response_model=LowestPriceVolumeResponse)
async def get_stock_lowest_price_volume_endpoint(
    ts_code: str = Path(..., description="股票代码，如 '000001.SZ'"),
    use_cache: bool = Query(True, description="是否使用Redis缓存数据")
):
    """
    获取个股的历史最低价成交量信息

    计算历史最低价前后一个月的日均成交量：
    - 找到股票的历史最低价日期
    - 获取该日期前一个月（约22个交易日）和后一个月的交易数据
    - 计算这两个月的日均成交量

    **返回示例：**
    ```json
    {
        "ts_code": "000001.SZ",
        "lowest_price": 8.50,
        "lowest_price_date": "2022-04-27",
        "pre_month_start": "2022-03-28",
        "pre_month_end": "2022-04-27",
        "pre_month_avg_volume": 1250000,
        "pre_month_trading_days": 22,
        "post_month_start": "2022-04-27",
        "post_month_end": "2022-05-26",
        "post_month_avg_volume": 1380000,
        "post_month_trading_days": 21,
        "total_avg_volume": 1315000,
        "total_trading_days": 43
    }
    ```
    """
    # 优先从Redis获取
    if use_cache:
        cached = get_lowest_price_volume_from_redis(ts_code)
        if cached:
            return LowestPriceVolumeResponse(
                ts_code=cached.ts_code,
                lowest_price=cached.lowest_price,
                lowest_price_date=cached.lowest_price_date,
                pre_month_start=cached.pre_month_start,
                pre_month_end=cached.pre_month_end,
                pre_month_avg_volume=cached.pre_month_avg_volume,
                pre_month_trading_days=cached.pre_month_trading_days,
                post_month_start=cached.post_month_start,
                post_month_end=cached.post_month_end,
                post_month_avg_volume=cached.post_month_avg_volume,
                post_month_trading_days=cached.post_month_trading_days,
                total_avg_volume=cached.total_avg_volume,
                total_trading_days=cached.total_trading_days
            )

    # 从数据库计算
    info = get_stock_lowest_price_volume(ts_code, use_cache=False)

    if info is None or (info.lowest_price is None and info.lowest_price_date is None):
        raise HTTPException(
            status_code=404,
            detail=f"未找到股票 {ts_code} 的数据"
        )

    # 如果启用缓存，保存到Redis
    if use_cache:
        save_lowest_price_volume_to_redis(info)

    return LowestPriceVolumeResponse(
        ts_code=info.ts_code,
        lowest_price=info.lowest_price,
        lowest_price_date=info.lowest_price_date,
        pre_month_start=info.pre_month_start,
        pre_month_end=info.pre_month_end,
        pre_month_avg_volume=info.pre_month_avg_volume,
        pre_month_trading_days=info.pre_month_trading_days,
        post_month_start=info.post_month_start,
        post_month_end=info.post_month_end,
        post_month_avg_volume=info.post_month_avg_volume,
        post_month_trading_days=info.post_month_trading_days,
        total_avg_volume=info.total_avg_volume,
        total_trading_days=info.total_trading_days
    )


@app.get("/api/volume/limit-up/{ts_code}", response_model=LimitUpVolumeResponse)
async def get_stock_limit_up_volume_endpoint(
    ts_code: str = Path(..., description="股票代码，如 '000001.SZ'"),
    use_cache: bool = Query(True, description="是否使用Redis缓存数据")
):
    """
    获取个股的涨停后成交量信息

    计算最近一次涨停后累计成交量和日均成交量占涨停当日成交量的比值：
    - 找到最近一次涨停的日期和当日成交量
    - 计算从涨停日到最新交易日的后续累计成交量
    - 计算涨停后的日均成交量
    - 计算涨停后日均成交量 / 涨停当日成交量的比值

    **返回示例：**
    ```json
    {
        "ts_code": "000001.SZ",
        "limit_up_date": "2024-01-15",
        "limit_up_price": 10.50,
        "limit_up_volume": 2500000,
        "days_since_limit_up": 20,
        "cumulative_volume": 35000000,
        "post_limit_avg_volume": 1750000,
        "volume_ratio": 0.70
    }
    ```
    """
    # 优先从Redis获取
    if use_cache:
        cached = get_limit_up_volume_from_redis(ts_code)
        if cached:
            return LimitUpVolumeResponse(
                ts_code=cached.ts_code,
                limit_up_date=cached.limit_up_date,
                limit_up_price=cached.limit_up_price,
                limit_up_volume=cached.limit_up_volume,
                days_since_limit_up=cached.days_since_limit_up,
                cumulative_volume=cached.cumulative_volume,
                post_limit_avg_volume=cached.post_limit_avg_volume,
                volume_ratio=cached.volume_ratio
            )

    # 从数据库计算
    info = get_stock_limit_up_volume(ts_code, use_cache=False)

    if info is None or info.limit_up_date is None:
        raise HTTPException(
            status_code=404,
            detail=f"未找到股票 {ts_code} 的涨停数据"
        )

    # 如果启用缓存，保存到Redis
    if use_cache:
        save_limit_up_volume_to_redis(info)

    return LimitUpVolumeResponse(
        ts_code=info.ts_code,
        limit_up_date=info.limit_up_date,
        limit_up_price=info.limit_up_price,
        limit_up_volume=info.limit_up_volume,
        days_since_limit_up=info.days_since_limit_up,
        cumulative_volume=info.cumulative_volume,
        post_limit_avg_volume=info.post_limit_avg_volume,
        volume_ratio=info.volume_ratio
    )


@app.post("/api/volume/recalculate")
async def recalculate_all_stocks_volume(
    num_threads: int = Query(4, ge=1, le=16, description="计算线程数")
):
    """
    触发全量重新计算所有股票的成交量信息

    这是一个耗时操作，会在后台批量处理所有股票。
    同时计算：
    1. 历史最低价前后一个月的日均成交量
    2. 最近一次涨停后累计成交量和日均成交量占比

    **参数说明：**
    - num_threads: 并行计算的线程数，建议值为4-8

    **返回示例：**
    ```json
    {
        "status": "started",
        "total_stocks": 5000,
        "message": "全量计算已启动"
    }
    ```
    """
    import asyncio

    def run_calculation():
        # 计算历史最低价成交量
        results1 = calculate_lowest_price_volume_for_all_stocks(num_threads=num_threads)
        # 计算涨停后成交量
        results2 = calculate_limit_up_volume_for_all_stocks(num_threads=num_threads)

        return {
            "lowest_price_volume_count": len(results1),
            "limit_up_volume_count": len(results2)
        }

    # 在线程池中运行（避免阻塞）
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(executor, run_calculation)

    return {
        "status": "completed",
        "total_stocks": result["lowest_price_volume_count"],
        "message": f"全量计算完成，共处理 {result['lowest_price_volume_count']} 只股票的历史最低价成交量和 {result['limit_up_volume_count']} 只股票的涨停后成交量"
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
    sector: Optional[str] = Query(
        None,
        description="板块筛选: SH(沪市主板), SZ(深市主板), CY(创业板), KC(科创板)"
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
            # 如果提供了sector参数，按板块筛选
            if sector:
                logger.info(f"按板块筛选: sector={sector}")
                cached_data = [r for r in cached_data if filter_stocks_by_sector([r["ts_code"]], sector)]
                logger.info(f"板块筛选后剩余 {len(cached_data)} 只股票")
            
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

                # 批量获取股票名称
                page_ts_codes = [item["ts_code"] for item in page_data]
                stock_names = get_stock_names_batch(page_ts_codes)

                rankings = [
                    StockRankItem(
                        rank=start_idx + i + 1,
                        ts_code=item["ts_code"],
                        stock_name=stock_names.get(item["ts_code"]),
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
    
    # 阶段1：使用SQL批量计算涨跌幅（多线程版本）
    logger.info("阶段1：使用SQL批量计算涨跌幅（多线程版本）...")
    phase1_start = time.time()

    access = StockDataAccess()
    # 使用4个线程并行计算，可以根据服务器配置调整
    results_df = access.get_stock_returns_in_range(start_date, end_date, direction, num_threads=4)
    
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
    
    # 如果提供了sector参数，按板块筛选
    if sector:
        logger.info(f"按板块筛选: sector={sector}")
        raw_results = [r for r in raw_results if filter_stocks_by_sector([r["ts_code"]], sector)]
        logger.info(f"板块筛选后剩余 {len(raw_results)} 只股票")
    
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

    # 批量获取股票名称
    page_ts_codes = [item["ts_code"] for item in page_data]
    stock_names = get_stock_names_batch(page_ts_codes)

    rankings = [
        StockRankItem(
            rank=start_idx + i + 1,
            ts_code=item["ts_code"],
            stock_name=stock_names.get(item["ts_code"]),
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


@app.get("/api/sw/industry-stocks")
async def get_industry_stocks(
    node_code: str = Query(..., description="申万行业节点代码，如 '801010'(一级), '801020'(二级), '801030'(三级)"),
    level: int = Query(None, ge=1, le=3, description="行业层级: 1=一级, 2=二级, 3=三级。不传则按node_code精确匹配"),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(50, ge=1, le=500, description="每页数量")
):
    """
    根据申万行业节点代码获取对应的股票代码列表

    支持按一级、二级、三级行业节点查询：
    - 传入一级节点代码(如801010)，返回该一级行业下所有股票
    - 传入二级节点代码(如801020)，返回该二级行业下所有股票
    - 传入三级节点代码(如801030)，返回该三级行业下所有股票

    **参数说明：**
    - node_code: 行业节点代码
    - level: 行业层级（可选，不传则按node_code精确匹配）
    - page: 页码（默认1）
    - page_size: 每页数量（默认50，最大500）

    **返回示例：**
    ```json
    {
        "status": "success",
        "node_code": "801010",
        "level": 1,
        "total": 100,
        "page": 1,
        "page_size": 50,
        "total_pages": 2,
        "stocks": [
            {
                "ts_code": "000001.SZ",
                "stock_name": "平安银行"
            }
        ]
    }
    ```
    """
    try:
        # 获取行业股票
        df = SwStockQueryService.get_industry_stocks(node_code, level=level, is_latest=True)

        if df is None or df.empty:
            return {
                "status": "success",
                "node_code": node_code,
                "level": level,
                "total": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0,
                "stocks": []
            }

        # 获取股票代码列表
        ts_codes = df['ts_code'].unique().tolist()

        # 计算总数和分页
        total_stocks = len(ts_codes)
        total_pages = (total_stocks + page_size - 1) // page_size
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total_stocks)

        # 获取当前页的股票代码
        page_ts_codes = ts_codes[start_idx:end_idx]

        # 批量获取股票名称
        stock_names = get_stock_names_batch(page_ts_codes)

        # 组装结果
        stocks = []
        for ts_code in page_ts_codes:
            stock_info = {"ts_code": ts_code}
            stock_name = stock_names.get(ts_code)
            if stock_name:
                stock_info["stock_name"] = stock_name
            stocks.append(stock_info)

        return {
            "status": "success",
            "node_code": node_code,
            "level": level,
            "total": total_stocks,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "stocks": stocks
        }
    except Exception as e:
        logger.error(f"获取行业股票列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取行业股票列表失败: {str(e)}")


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
