# 基金复权因子接口
# 接口：fund_adj
# 描述：获取基金复权因子，用于计算基金复权行情

import tushare as ts
import os
import sys
import logging
from datetime import datetime
from uuid import uuid4
import math
from sqlalchemy.dialects.mysql import insert


def to_none(value):
    """将NaN转换为None，其他值原样返回"""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return value

# 设置路径
_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # venv/src
# 添加项目根目录 (用于orm.etf模块)
_project_root = os.path.dirname(_base_dir)  # 项目根目录
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
# 添加venv/src (包含BaseFacility等模块)
if _base_dir not in sys.path:
    sys.path.insert(0, _base_dir)
# 添加venv/src/orm路径 (用于dbmanager模块)
_orm_path = os.path.join(_base_dir, 'orm')
if _orm_path not in sys.path:
    sys.path.insert(0, _orm_path)

from BaseFacility.Logconfig.logconfig import logger
from orm.etf.fund_adj_model import fund_adj_base, fund_adj_info

# =====================================================
# Tushare配置 - 统一从PatternAnalysis/config.py读取
# =====================================================

# 从配置文件读取Tushare配置
_token = None
_http_url = None
try:
    from PatternAnalysis.config import TUSHARE_CONFIG
    _token = TUSHARE_CONFIG.get('token')
    _http_url = TUSHARE_CONFIG.get('http_url', 'http://lianghua.9vvn.com')
    token_display = _token[:10] + "..." if _token else "None"
    logger.info(f"从PatternAnalysis.config读取Tushare配置: token={token_display}, url={_http_url}")
except ImportError:
    # 如果无法导入配置，尝试使用默认token
    logger.warning("无法导入PatternAnalysis.config，使用默认配置")
    _token = "27d26a829762ddae3467ca0950f08ae324e08452087f0642b0a859c3de92"
    _http_url = 'http://lianghua.9vvn.com'

# 使用有效的token配置
if _token:
    ts.set_token(_token)
    pro = ts.pro_api()
    pro._DataApi__token = _token
    if _http_url:
        pro._DataApi__http_url = _http_url
    logger.info("Token配置完成")
else:
    logger.error("无法获取有效的Tushare Token，请检查配置！")
    raise ValueError("未配置有效的Tushare Token")


def get_existing_dates(ts_code: str) -> set:
    """获取数据库中已有的交易日期"""
    try:
        from dbmanager import dborm as db
        result = db.DBSession.query(fund_adj_info.trade_date).filter(
            fund_adj_info.ts_code == ts_code
        ).all()
        return {r[0] for r in result}
    except Exception as e:
        logger.warning(f"获取已有日期失败: {e}")
        return set()


def save_fund_adj_data(df, ts_code: str):
    """保存基金复权因子数据到数据库"""
    if df.empty:
        logger.info(f"没有数据需要保存 for {ts_code}")
        return
    
    try:
        from dbmanager import dborm as db

        # 生成UUID作为主键
        records = []
        for x in df.to_dict('records'):
            record = {
                'id': str(uuid4()),
                'ts_code': x.get('ts_code'),
                'trade_date': x.get('trade_date'),
                'adj_factor': to_none(x.get('adj_factor')),
                'last_update_time': datetime.now()
            }
            records.append(record)
        stmt = insert(fund_adj_info).values(records)
        stmt = stmt.on_duplicate_key_update(
            adj_factor=stmt.inserted.adj_factor,
            last_update_time=stmt.inserted.last_update_time
        )
        db.DBSession.execute(stmt)
        db.DBSession.commit()
        logger.info(f"成功保存 {len(df)} 条 {ts_code} 复权因子数据")
    except Exception as e:
        logger.error(f"保存数据失败: {e}")
        from dbmanager import dborm as db
        db.DBSession.rollback()


def fetch_fund_adj(ts_code: str, start_date: str = None, end_date: str = None,
                   filter_existing: bool = True):
    """
    获取基金复权因子
    
    Args:
        ts_code: 基金代码，如 '513100.SH'
        start_date: 开始日期，格式 YYYYMMDD
        end_date: 结束日期，格式 YYYYMMDD
        filter_existing: 是否过滤已存在的数据，默认为True
    
    Returns:
        DataFrame: 复权因子数据
    """
    try:
        # 构建查询参数
        params = {'ts_code': ts_code}
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        
        # 获取数据
        df = pro.fund_adj(**params)
        
        if df is None or df.empty:
            logger.info(f"没有获取到复权因子数据 for {ts_code}")
            return df
        
        # 如果需要过滤已存在的数据
        if filter_existing:
            existing_dates = get_existing_dates(ts_code)
            if existing_dates:
                df = df[~df['trade_date'].astype(str).isin(existing_dates)]
                logger.info(f"过滤后剩余 {len(df)} 条数据需要保存")
        
        # 保存到数据库
        if not df.empty:
            save_fund_adj_data(df, ts_code)
        
        return df
        
    except Exception as e:
        logger.error(f"获取基金复权因子数据失败: {e}")
        raise


def fetch_fund_adj_by_dates(ts_code: str, start_date: str, end_date: str = None):
    """
    按日期获取基金复权因子（逐日获取，支持增量更新）
    
    Args:
        ts_code: 基金代码，如 '513100.SH'
        start_date: 开始日期，格式 YYYYMMDD
        end_date: 结束日期，格式 YYYYMMDD
    """
    try:
        # 获取已有日期
        existing_dates = get_existing_dates(ts_code)
        logger.info(f"已存在 {len(existing_dates)} 条 {ts_code} 的复权因子数据")
        
        # 获取交易日历
        if end_date:
            date_range = f"{start_date}:{end_date}"
        else:
            date_range = start_date
            
        trade_cal = pro.query('trade_cal', start_date=start_date, end_date=end_date)
        trade_dates = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()
        
        logger.info(f"交易日历中有 {len(trade_dates)} 个交易日")
        
        # 逐日获取数据
        total_saved = 0
        for trade_date in trade_dates:
            if trade_date in existing_dates:
                logger.debug(f"跳过已存在的日期: {trade_date}")
                continue
            
            try:
                df = pro.fund_adj(ts_code=ts_code, trade_date=trade_date)
                
                if df is not None and not df.empty:
                    save_fund_adj_data(df, ts_code)
                    total_saved += len(df)
                
            except Exception as e:
                logger.warning(f"获取 {trade_date} 数据失败: {e}")
                continue
        
        logger.info(f"共保存 {total_saved} 条 {ts_code} 复权因子数据")
        return total_saved
        
    except Exception as e:
        logger.error(f"按日期获取基金复权因子数据失败: {e}")
        raise


class FundAdjAPI:
    """基金复权因子API类"""
    
    def __init__(self, ts_code: str = None):
        """
        初始化基金复权因子API
        
        Args:
            ts_code: 基金代码，如 '513100.SH'
        """
        self.ts_code = ts_code
    
    def get_adj(self, start_date: str = None, end_date: str = None,
                filter_existing: bool = True):
        """
        获取基金复权因子
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            filter_existing: 是否过滤已存在数据
            
        Returns:
            DataFrame
        """
        if not self.ts_code:
            raise ValueError("请设置ts_code")
        return fetch_fund_adj(
            ts_code=self.ts_code,
            start_date=start_date,
            end_date=end_date,
            filter_existing=filter_existing
        )
    
    def get_adj_incremental(self, start_date: str, end_date: str = None):
        """
        增量获取基金复权因子（逐日获取）
        """
        if not self.ts_code:
            raise ValueError("请设置ts_code")
        return fetch_fund_adj_by_dates(
            ts_code=self.ts_code,
            start_date=start_date,
            end_date=end_date
        )


if __name__ == '__main__':
    # 测试代码
    api = FundAdjAPI(ts_code='513100.SH')
    
    # 获取2019年以来的复权因子
    print("获取基金复权因子数据...")
    df = api.get_adj(start_date='20190101', end_date='20190926')
    print(df)
    
    print("\n增量获取数据...")
    count = api.get_adj_incremental(start_date='20190901', end_date='20190926')
    print(f"新增 {count} 条记录")
