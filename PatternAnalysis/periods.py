"""
股票形态分析系统 - 时间周期计算
支持3/6/9/12个月及自定义时间周期
"""
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Tuple, Optional, Union
from .config import PERIOD_CONFIG


def get_period_windows(
    end_date: date, 
    months: int
) -> Tuple[Tuple[date, date], Tuple[date, date]]:
    """
    获取当前周期和上一周期的时间窗口
    
    Args:
        end_date: 最新交易日（日期对象）
        months: 周期月数，如 3/6/9/12
    
    Returns:
        ((curr_start, curr_end), (prev_start, prev_end))
        - curr_start: 当前周期开始日期
        - curr_end: 当前周期结束日期
        - prev_start: 上一周期开始日期
        - prev_end: 上一周期结束日期
    """
    # 确保end_date是date类型
    if isinstance(end_date, datetime):
        end_date = end_date.date()
    
    # 当前周期
    curr_end = end_date
    curr_start = end_date - relativedelta(months=months) + timedelta(days=1)
    
    # 上一周期：紧邻当前周期前的一个周期
    prev_end = curr_start - timedelta(days=1)
    prev_start = prev_end - relativedelta(months=months) + timedelta(days=1)
    
    return (curr_start, curr_end), (prev_start, prev_end)


def get_custom_windows(
    start_date: date, 
    end_date: date
) -> Tuple[Tuple[date, date], Tuple[date, date]]:
    """
    获取自定义周期的时间窗口
    
    Args:
        start_date: 自定义周期开始日期
        end_date: 自定义周期结束日期
    
    Returns:
        ((curr_start, curr_end), (prev_start, prev_end))
    """
    # 当前周期
    curr_start = start_date
    curr_end = end_date
    
    # 上一周期：向前平移相同天数
    delta_days = (curr_end - curr_start).days + 1
    prev_end = curr_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=delta_days - 1)
    
    return (curr_start, curr_end), (prev_start, prev_end)


def get_period_months(period_type: str) -> Optional[int]:
    """
    根据周期类型获取月数
    
    Args:
        period_type: 周期类型字符串，如 "3m", "6m", "9m", "12m"
    
    Returns:
        月数，如 3, 6, 9, 12，无效返回None
    """
    if period_type in PERIOD_CONFIG["available_periods"]:
        return int(period_type.replace("m", ""))
    return None


def validate_period_type(period_type: str, allow_custom: bool = True) -> bool:
    """
    验证周期类型是否有效
    
    Args:
        period_type: 周期类型
        allow_custom: 是否允许自定义周期
    
    Returns:
        有效返回True，否则返回False
    """
    if period_type in PERIOD_CONFIG["available_periods"]:
        return True
    if allow_custom and period_type == "custom":
        return True
    return False


def get_trading_days_count(
    start: date, 
    end: date,
    trading_days: list
) -> int:
    """
    计算指定范围内的交易日数量
    
    Args:
        start: 开始日期
        end: 结束日期
        trading_days: 交易日列表
    
    Returns:
        交易日数量
    """
    return sum(1 for d in trading_days if start <= d <= end)


def adjust_start_for_min_days(
    start: date, 
    end: date,
    min_days: int,
    trading_days: list
) -> date:
    """
    根据最小天数要求调整开始日期
    
    Args:
        start: 原始开始日期
        end: 结束日期
        min_days: 最少需要的交易日天数
        trading_days: 交易日列表
    
    Returns:
        调整后的开始日期
    """
    current_count = get_trading_days_count(start, end, trading_days)
    
    if current_count >= min_days:
        return start
    
    # 向前延伸以满足最小天数要求
    needed_days = min_days - current_count
    extended_start = start
    
    for d in reversed(trading_days):
        if d < start:
            extended_start = d
            needed_days -= 1
            if needed_days <= 0:
                break
    
    return extended_start


class PeriodCalculator:
    """时间周期计算器类"""
    
    def __init__(self):
        self.available_periods = PERIOD_CONFIG["available_periods"]
        self.min_days = PERIOD_CONFIG["min_days_required"]
    
    def calculate_windows(
        self,
        end_date: date,
        period_type: str,
        custom_start: Optional[date] = None,
        custom_end: Optional[date] = None
    ) -> Tuple[Tuple[date, date], Tuple[date, date]]:
        """
        计算时间窗口
        
        Args:
            end_date: 结束日期
            period_type: 周期类型
            custom_start: 自定义开始日期
            custom_end: 自定义结束日期
        
        Returns:
            ((curr_start, curr_end), (prev_start, prev_end))
        """
        if period_type in self.available_periods:
            months = int(period_type.replace("m", ""))
            return get_period_windows(end_date, months)
        elif period_type == "custom" and custom_start and custom_end:
            return get_custom_windows(custom_start, custom_end)
        else:
            raise ValueError(f"无效的周期类型: {period_type}")
    
    def get_period_info(
        self,
        end_date: date,
        period_type: str,
        custom_start: Optional[date] = None,
        custom_end: Optional[date] = None
    ) -> dict:
        """
        获取周期信息
        
        Returns:
            包含周期信息的字典
        """
        (curr_start, curr_end), (prev_start, prev_end) = self.calculate_windows(
            end_date, period_type, custom_start, custom_end
        )
        
        return {
            "period_type": period_type,
            "current_period": {
                "start": curr_start,
                "end": curr_end,
                "months": int(period_type.replace("m", "")) if period_type != "custom" else None,
                "days": (curr_end - curr_start).days + 1
            },
            "previous_period": {
                "start": prev_start,
                "end": prev_end,
                "months": int(period_type.replace("m", "")) if period_type != "custom" else None,
                "days": (prev_end - prev_start).days + 1
            }
        }


def parse_date(date_str: str) -> Optional[date]:
    """
    解析日期字符串
    
    Args:
        date_str: 日期字符串，格式如 "2024-01-01"
    
    Returns:
        date对象，解析失败返回None
    """
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"]:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def format_date(d: date) -> str:
    """
    格式化日期为字符串
    
    Args:
        d: date对象
    
    Returns:
        格式化后的日期字符串
    """
    return d.strftime("%Y-%m-%d")
