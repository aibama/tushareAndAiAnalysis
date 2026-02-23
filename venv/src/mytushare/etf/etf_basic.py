# ETF基础信息接口
# 接口：etf_basic
# 描述：获取国内ETF基础信息，包括了QDII。数据来源与沪深交易所公开披露信息。

import tushare as ts
import os
import sys
import logging
from datetime import datetime
from decimal import Decimal
from sqlalchemy.dialects.mysql import insert

# 设置路径
# etf_basic.py 位于 venv/src/mytushare/etf/etf_basic.py (5层目录)
_current_file = os.path.abspath(__file__)
# 手动构建正确的路径
_file_dir = os.path.dirname(_current_file)  # venv/src/mytushare/etf
_file_dir = os.path.dirname(_file_dir)       # venv/src/mytushare
_file_dir = os.path.dirname(_file_dir)       # venv/src
_file_dir = os.path.dirname(_file_dir)        # venv
_project_root = os.path.dirname(_file_dir)    # 项目根目录

# 构建需要的路径列表 (按优先级顺序)
# 注意：需要同时支持orm.etf(在项目根目录)和dbmanager(在venv/src/orm)
_paths_to_add = [
    _project_root,  # 项目根目录 - 用于orm.etf
    os.path.join(_project_root, 'venv', 'src', 'orm'),  # dbmanager模块路径
    os.path.join(_project_root, 'venv', 'src', 'mytushare'),  # mytushare模块
    os.path.join(_project_root, 'venv', 'src'),  # BaseFacility等模块路径
]

# 先移除已存在的这些路径
for _p in _paths_to_add:
    if _p in sys.path:
        sys.path.remove(_p)

# 反向添加，使得项目根目录最终在最前面
for _p in reversed(_paths_to_add):
    sys.path.insert(0, _p)

from BaseFacility.Logconfig.logconfig import logger
from orm.etf.fund_etf_info_model import FundEtfInfo

# 尝试导入commonapi中已配置的pro对象，避免重复设置token
# 先添加必要的路径
import sys
import os

# 获取项目根目录
_file = os.path.abspath(__file__)
_file_dir = os.path.dirname(_file)  # venv/src/mytushare/etf
_file_dir = os.path.dirname(_file_dir)  # venv/src/mytushare
_file_dir = os.path.dirname(_file_dir)  # venv/src
_file_dir = os.path.dirname(_file_dir)  # venv
_project_root = os.path.dirname(_file_dir)  # 项目根目录

# 添加项目根目录到sys.path
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# =====================================================
# Tushare配置 - 统一从PatternAnalysis/config.py读取
# =====================================================

# 从配置文件读取Tushare配置
_token = None
_http_url = None
try:
    # 添加项目根目录到sys.path
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)
    from PatternAnalysis.config import TUSHARE_CONFIG
    _token = TUSHARE_CONFIG.get('token')
    _http_url = TUSHARE_CONFIG.get('http_url', 'http://lianghua.9vvn.com')
    token_display = _token[:10] + "..." if _token else "None"
    logger.info(f"从PatternAnalysis.config读取Tushare配置: token={token_display}, url={_http_url}")
except ImportError:
    # 如果无法导入配置，尝试从commonapi导入
    logger.warning("无法导入PatternAnalysis.config，尝试从commonapi获取配置")
    try:
        from mytushare.commonapi import pro as commonapi_pro
        _token = commonapi_pro._DataApi__token
        _http_url = commonapi_pro._DataApi__http_url
        logger.info(f"从commonapi获取配置成功: token={_token[:10]}...")
    except ImportError as e:
        logger.error(f"无法获取Tushare配置: {e}")

# 使用有效的token配置
if _token:
    ts.set_token(_token)
    pro = ts.pro_api()
    pro._DataApi__token = _token
    if _http_url:
        pro._DataApi__http_url = _http_url
    logger.info("Token配置完成")
else:
    # 如果无法获取token
    logger.error("无法获取有效的Tushare Token，请检查配置！")
    raise ValueError("未配置有效的Tushare Token")


def parse_date(date_str):
    """
    解析日期字符串为Date对象
    支持格式: YYYYMMDD, YYYY-MM-DD
    """
    if not date_str:
        return None
    try:
        date_str = str(date_str).replace('-', '')
        if len(date_str) == 8:
            return datetime.strptime(date_str, '%Y%m%d').date()
        return None
    except Exception:
        return None


def parse_mgt_fee(fee_str):
    """
    解析管理费率字符串为Decimal
    """
    import math
    if fee_str is None or fee_str == '' or (isinstance(fee_str, float) and math.isnan(fee_str)):
        return None
    try:
        val = Decimal(str(fee_str))
        # 检查是否是NaN
        if str(val) == 'NaN':
            return None
        return val
    except Exception:
        return None


def determine_etf_type(ts_code: str, exchange: str = None) -> str:
    """
    判断ETF类型（境内、QDII）
    QDII ETF通常以QDII或港股通、境外等标识
    """
    # QDII ETF的代码特征
    qdii_prefixes = ['511990', '513100', '513500', '513600', '513800', '513900',
                     '510900', '511010', '511030', '511130', '511210', '511220',
                     '511260', '511280', '511290', '511310', '511380', '511660']
    
    # 检查是否是QDII ETF
    for prefix in qdii_prefixes:
        if ts_code.startswith(prefix):
            return 'QDII'
    
    # 检查交易所代码
    if exchange and '.HK' in ts_code.upper():
        return 'QDII'
    
    return '境内'


def get_existing_ts_codes(list_status: str = None, exchange: str = None) -> set:
    """
    获取数据库中已存在的ETF代码
    
    Args:
        list_status: 存续状态过滤 (L上市 D退市 P待上市)
        exchange: 交易所代码过滤
    
    Returns:
        set: 已存在的ETF代码集合
    """
    try:
        query = FundEtfInfo.query
        if list_status:
            query = query.filter_by(list_status=list_status)
        if exchange:
            query = query.filter_by(exchange=exchange)
        result = query.with_entities(FundEtfInfo.ts_code).all()
        return {r[0] for r in result}
    except Exception as e:
        logger.warning(f"获取已有ETF代码失败: {e}")
        return set()


def convert_tushare_to_db_record(df):
    """
    将Tushare返回的etf_basic数据转换为数据库记录格式
    
    Tushare etf_basic字段:
    - ts_code: 基金代码
    - name: 基金简称
    - management: 基金管理人
    - custodian: 基金托管人
    - fund_type: 基金类型
    - issue_date: 发行日期
    - delist_date: 终止上市日期
    - list_date: 上市日期
    - market: 市场
    - exchange: 交易所
    - asset_type: 资产类型
    - type: 基金类型
    """
    if df is None or df.empty:
        return []

    import math

    def safe_get(val):
        """安全获取值，将NaN转换为None"""
        if val is None:
            return None
        if isinstance(val, float) and math.isnan(val):
            return None
        return val

    records = []
    for _, row in df.iterrows():
        ts_code = str(row.get('ts_code', ''))
        
        # 获取交易所信息
        exchange_value = row.get('exchange', '')
        if not exchange_value and '.' in ts_code:
            exchange_value = ts_code.split('.')[-1] if len(ts_code.split('.')) > 1 else ''
        
        # 判断ETF类型
        etf_type = determine_etf_type(ts_code, exchange_value)
        
        record = {
            'ts_code': ts_code,
            'csname': str(row.get('name', ''))[:50] if row.get('name') else '',
            'extname': str(row.get('name', ''))[:100] if row.get('name') else None,
            'cname': str(row.get('full_name', row.get('name', '')))[:200] if row.get('name') else '',
            'index_code': safe_get(row.get('index_code')),
            'index_name': safe_get(row.get('index_name')),
            'setup_date': parse_date(row.get('issue_date')),
            'list_date': parse_date(row.get('list_date')),
            'list_status': str(row.get('status', 'L'))[0] if row.get('status') else 'L',
            'exchange': exchange_value,
            'mgr_name': str(row.get('management', ''))[:100] if row.get('management') else None,
            'custod_name': str(row.get('custodian', ''))[:200] if row.get('custodian') else None,
            'mgt_fee': parse_mgt_fee(row.get('mgt_fee')),
            'etf_type': etf_type
        }
        records.append(record)
    
    return records


def save_etf_basic_data(df):
    """
    保存ETF基础信息到数据库（Upsert模式）
    """
    if df is None or df.empty:
        logger.info("没有数据需要保存")
        return

    # 导入pandas和numpy并处理NaN值 - 将NaN替换为None以兼容MySQL
    import pandas as pd
    import numpy as np
    df = df.replace({pd.NA: None, np.nan: None, float('nan'): None})

    records = convert_tushare_to_db_record(df)
    if not records:
        logger.info("转换后没有有效数据")
        return
    
    try:
        # 使用upsert方式插入，避免重复
        stmt = insert(FundEtfInfo).values(records)
        stmt = stmt.on_duplicate_key_update(
            csname=stmt.inserted.csname,
            extname=stmt.inserted.extname,
            cname=stmt.inserted.cname,
            index_code=stmt.inserted.index_code,
            index_name=stmt.inserted.index_name,
            setup_date=stmt.inserted.setup_date,
            list_date=stmt.inserted.list_date,
            list_status=stmt.inserted.list_status,
            exchange=stmt.inserted.exchange,
            mgr_name=stmt.inserted.mgr_name,
            custod_name=stmt.inserted.custod_name,
            mgt_fee=stmt.inserted.mgt_fee,
            etf_type=stmt.inserted.etf_type
        )
        # 导入dbmanager - 由于已添加venv/src/orm到sys.path，可以直接导入
        from dbmanager import dborm as db
        db.DBSession.execute(stmt)
        db.DBSession.commit()
        logger.info(f"成功保存 {len(records)} 条ETF基础信息")
    except Exception as e:
        logger.error(f"保存ETF基础信息失败: {e}")
        from dbmanager import dborm as db
        db.DBSession.rollback()
        raise


def fetch_etf_basic(list_status: str = 'L', exchange: str = None, 
                    fields: str = None, save_to_db: bool = True,
                    filter_existing: bool = True):
    """
    获取ETF基础信息
    
    Args:
        list_status: 存续状态 (L上市 D退市 P待上市) 默认为'L'
        exchange: 交易所代码 (SSE上交所 SZSE深交所) 默认为None获取全部
        fields: 输出字段，默认为None表示全部字段
        save_to_db: 是否保存到数据库，默认为True
        filter_existing: 是否过滤已存在的数据，默认为True（自动过滤已存在的ETF代码）
    
    Returns:
        DataFrame: ETF基础信息数据
    
    Tushare etf_basic 接口参数:
    - exchange: 交易所 SSE/SZSE
    - list_status: 上市状态 L/D/P
    - fields: 输出字段
    
    Tushare etf_basic 接口返回字段:
    - ts_code: 基金代码
    - name: 基金简称
    - management: 基金管理人
    - custodian: 基金托管人
    - fund_type: 基金类型
    - issue_date: 发行日期
    - delist_date: 终止上市日期
    - list_date: 上市日期
    - market: 市场
    - exchange: 交易所
    """
    try:
        # 构建查询参数
        params = {
            'list_status': list_status
        }
        
        if exchange:
            params['exchange'] = exchange
        
        # 指定需要的字段，避免获取过多不必要的数据
        if fields:
            params['fields'] = fields
        
        logger.info(f"开始获取ETF基础信息，参数: {params}")
        
        # 调用Tushare接口
        df = pro.etf_basic(**params)
        
        if df is None or df.empty:
            logger.info("没有获取到ETF基础信息数据")
            return df
        
        logger.info(f"成功获取 {len(df)} 条ETF基础信息")
        
        # 如果需要过滤已存在的数据（按ETF代码过滤）
        if filter_existing:
            existing_ts_codes = get_existing_ts_codes(list_status=list_status, exchange=exchange)
            if existing_ts_codes:
                df = df[~df['ts_code'].isin(existing_ts_codes)]
                logger.info(f"过滤后剩余 {len(df)} 条ETF需要保存")
        
        # 保存到数据库
        if save_to_db and not df.empty:
            save_etf_basic_data(df)
        
        return df
        
    except Exception as e:
        logger.error(f"获取ETF基础信息失败: {e}")
        raise


def fetch_all_etf_basic(save_to_db: bool = True, filter_existing: bool = True):
    """
    获取所有ETF基础信息（包含所有状态）
    
    Args:
        save_to_db: 是否保存到数据库
        filter_existing: 是否过滤已存在的数据，默认为True
    
    Returns:
        DataFrame: 所有ETF基础信息
    """
    # 获取所有上市状态的ETF
    all_dfs = []
    
    for status in ['L', 'P', 'D']:
        df = fetch_etf_basic(
            list_status=status, 
            exchange=None, 
            save_to_db=save_to_db,
            filter_existing=filter_existing
        )
        if df is not None and not df.empty:
            all_dfs.append(df)
    
    if all_dfs:
        import pandas as pd
        return pd.concat(all_dfs, ignore_index=True)
    
    return None


class ETFBasicAPI:
    """ETF基础信息API类"""
    
    def __init__(self):
        """初始化ETF基础信息API"""
        pass
    
    def get_etf_basic(self, list_status: str = 'L', exchange: str = None,
                      fields: str = None, save_to_db: bool = True,
                      filter_existing: bool = True):
        """
        获取ETF基础信息
        
        Args:
            list_status: 存续状态 (L上市 D退市 P待上市)
            exchange: 交易所代码 (SSE上交所 SZSE深交所)
            fields: 输出字段
            save_to_db: 是否保存到数据库
            filter_existing: 是否过滤已存在的数据，默认为True
        
        Returns:
            DataFrame: ETF基础信息
        """
        return fetch_etf_basic(
            list_status=list_status,
            exchange=exchange,
            fields=fields,
            save_to_db=save_to_db,
            filter_existing=filter_existing
        )
    
    def get_listed_etf(self, exchange: str = None, fields: str = None,
                      filter_existing: bool = True):
        """
        获取上市ETF列表
        
        Args:
            exchange: 交易所代码
            fields: 输出字段
            filter_existing: 是否过滤已存在的数据，默认为True
        
        Returns:
            DataFrame: 上市ETF列表
        """
        return fetch_etf_basic(
            list_status='L',
            exchange=exchange,
            fields=fields,
            save_to_db=True,
            filter_existing=filter_existing
        )
    
    def get_all_etf(self, save_to_db: bool = True, filter_existing: bool = True):
        """
        获取所有ETF（包含所有状态）
        
        Args:
            save_to_db: 是否保存到数据库
            filter_existing: 是否过滤已存在的数据，默认为True
        
        Returns:
            DataFrame: 所有ETF信息
        """
        return fetch_all_etf_basic(save_to_db=save_to_db, filter_existing=filter_existing)


# 使用示例
if __name__ == '__main__':
    # 测试代码
    print("=== 测试获取ETF基础信息 ===")
    
    # 创建API实例
    api = ETFBasicAPI()
    
    # 获取当前所有上市的ETF列表
    print("\n1. 获取上市ETF列表...")
    df = api.get_listed_etf(
        fields='ts_code,name,management,custodian,list_date,exchange'
    )
    print(df)
    
    # 获取所有ETF（包含退市和待上市）
    print("\n2. 获取所有ETF...")
    all_etf = api.get_all_etf(save_to_db=True)
    print(f"共获取 {len(all_etf)} 条ETF记录")
    
    # 直接调用函数方式
    print("\n3. 直接调用函数方式...")
    df2 = fetch_etf_basic(
        list_status='L', 
        fields='ts_code,extname,index_code,index_name,exchange,mgr_name'
    )
    print(df2)
