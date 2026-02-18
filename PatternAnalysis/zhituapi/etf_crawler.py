"""
Tushare ETF数据爬虫主程序

功能：
1. 获取ETF日线行情数据（fund_daily）
2. 获取ETF份额规模数据（etf_share_size）
3. 获取基金复权因子数据（fund_adj）
4. 支持增量更新和全量更新
"""

import sys
import os
import time
import logging
from datetime import datetime

# 添加项目根目录到sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 添加venv路径用于导入Tushare ETF模块
_venv_etf_path = os.path.join(_project_root, 'venv', 'src', 'mytushare')
if _venv_etf_path not in sys.path:
    sys.path.insert(0, _venv_etf_path)

from venv.src.mytushare.etf import ETFDailyAPI, ETFShareSizeAPI, FundAdjAPI
from PatternAnalysis.config import DB_CONFIG

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def crawl_etf_daily(ts_code: str, start_date: str, end_date: str = None, 
                   incremental: bool = False):
    """
    步骤1: 获取ETF日线行情数据
    
    Args:
        ts_code: ETF代码，如 '510330.SH'
        start_date: 开始日期，格式 YYYYMMDD
        end_date: 结束日期，格式 YYYYMMDD
        incremental: 是否增量更新（逐日获取）
    
    Returns:
        bool: 是否成功
    """
    logger.info("=" * 50)
    logger.info(f"[步骤1] 开始获取ETF日线行情: {ts_code}")
    logger.info(f"  日期范围: {start_date} ~ {end_date or '至今'}")
    logger.info(f"  更新模式: {'增量' if incremental else '全量'}")
    logger.info("=" * 50)

    api = ETFDailyAPI(ts_code=ts_code)

    try:
        if incremental:
            count = api.get_daily_incremental(start_date=start_date, end_date=end_date)
            logger.info(f"增量更新完成: 新增 {count} 条记录")
        else:
            df = api.get_daily(start_date=start_date, end_date=end_date, 
                              filter_existing=not incremental)
            if df is not None and not df.empty:
                logger.info(f"成功获取 {len(df)} 条日线数据")
            else:
                logger.warning("未获取到任何数据")
        
        logger.info(f"[步骤1] ETF日线行情获取完成: {ts_code}")
        return True

    except Exception as e:
        logger.error(f"[步骤1] 获取ETF日线行情失败: {e}")
        return False


def crawl_etf_share_size(ts_code: str = None, start_date: str = None, 
                        end_date: str = None, incremental: bool = False,
                        trade_date: str = None):
    """
    步骤2: 获取ETF份额规模数据
    
    Args:
        ts_code: ETF代码，如 '510330.SH'，None表示获取所有ETF
        start_date: 开始日期
        end_date: 结束日期
        incremental: 是否增量更新
        trade_date: 指定日期（获取当日所有ETF）
    
    Returns:
        bool: 是否成功
    """
    target = ts_code or "所有ETF"
    logger.info("=" * 50)
    logger.info(f"[步骤2] 开始获取ETF份额规模: {target}")
    if trade_date:
        logger.info(f"  指定日期: {trade_date}")
    else:
        logger.info(f"  日期范围: {start_date} ~ {end_date or '至今'}")
    logger.info(f"  更新模式: {'增量' if incremental else '全量'}")
    logger.info("=" * 50)

    api = ETFShareSizeAPI(ts_code=ts_code)

    try:
        if trade_date:
            # 获取指定日期的所有ETF
            df = api.get_all_etf_on_date(trade_date=trade_date)
            if df is not None and not df.empty:
                logger.info(f"成功获取 {len(df)} 条份额规模数据")
            else:
                logger.warning("未获取到任何数据")
        elif incremental:
            count = api.get_share_size_incremental(start_date=start_date, end_date=end_date)
            logger.info(f"增量更新完成: 新增 {count} 条记录")
        else:
            df = api.get_share_size(start_date=start_date, end_date=end_date,
                                   filter_existing=not incremental)
            if df is not None and not df.empty:
                logger.info(f"成功获取 {len(df)} 条份额规模数据")
            else:
                logger.warning("未获取到任何数据")
        
        logger.info(f"[步骤2] ETF份额规模获取完成: {target}")
        return True

    except Exception as e:
        logger.error(f"[步骤2] 获取ETF份额规模失败: {e}")
        return False


def crawl_fund_adj(ts_code: str, start_date: str, end_date: str = None,
                  incremental: bool = False):
    """
    步骤3: 获取基金复权因子数据
    
    Args:
        ts_code: 基金代码，如 '513100.SH'
        start_date: 开始日期
        end_date: 结束日期
        incremental: 是否增量更新
    
    Returns:
        bool: 是否成功
    """
    logger.info("=" * 50)
    logger.info(f"[步骤3] 开始获取基金复权因子: {ts_code}")
    logger.info(f"  日期范围: {start_date} ~ {end_date or '至今'}")
    logger.info(f"  更新模式: {'增量' if incremental else '全量'}")
    logger.info("=" * 50)

    api = FundAdjAPI(ts_code=ts_code)

    try:
        if incremental:
            count = api.get_adj_incremental(start_date=start_date, end_date=end_date)
            logger.info(f"增量更新完成: 新增 {count} 条记录")
        else:
            df = api.get_adj(start_date=start_date, end_date=end_date,
                            filter_existing=not incremental)
            if df is not None and not df.empty:
                logger.info(f"成功获取 {len(df)} 条复权因子数据")
            else:
                logger.warning("未获取到任何数据")
        
        logger.info(f"[步骤3] 基金复权因子获取完成: {ts_code}")
        return True

    except Exception as e:
        logger.error(f"[步骤3] 获取基金复权因子失败: {e}")
        return False


def crawl_all_etf_data(ts_code: str, start_date: str, end_date: str = None,
                       incremental: bool = False):
    """
    获取ETF所有相关数据（日线、份额规模、复权因子）
    
    Args:
        ts_code: ETF代码
        start_date: 开始日期
        end_date: 结束日期
        incremental: 是否增量更新
    """
    logger.info("=" * 60)
    logger.info(f"开始获取ETF完整数据: {ts_code}")
    logger.info(f"  日期范围: {start_date} ~ {end_date or '至今'}")
    logger.info(f"  更新模式: {'增量' if incremental else '全量'}")
    logger.info("=" * 60)
    
    start_time = time.time()
    
    results = {
        'daily': False,
        'share_size': False,
        'adj': False
    }
    
    # 步骤1: 获取日线行情
    results['daily'] = crawl_etf_daily(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        incremental=incremental
    )
    
    # 步骤2: 获取份额规模
    results['share_size'] = crawl_etf_share_size(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        incremental=incremental
    )
    
    # 步骤3: 获取复权因子
    results['adj'] = crawl_fund_adj(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        incremental=incremental
    )
    
    elapsed_time = time.time() - start_time
    
    logger.info("=" * 60)
    logger.info(f"ETF数据获取完成: {ts_code}")
    logger.info(f"  日线行情: {'成功' if results['daily'] else '失败'}")
    logger.info(f"  份额规模: {'成功' if results['share_size'] else '失败'}")
    logger.info(f"  复权因子: {'成功' if results['adj'] else '失败'}")
    logger.info(f"  耗时: {elapsed_time:.2f} 秒")
    logger.info("=" * 60)
    
    return all(results.values())


def crawl_multiple_etfs(ts_codes: list, start_date: str, end_date: str = None,
                        incremental: bool = False):
    """
    批量获取多个ETF的数据
    
    Args:
        ts_codes: ETF代码列表
        start_date: 开始日期
        end_date: 结束日期
        incremental: 是否增量更新
    """
    logger.info("=" * 60)
    logger.info(f"开始批量获取ETF数据")
    logger.info(f"  ETF数量: {len(ts_codes)}")
    logger.info(f"  日期范围: {start_date} ~ {end_date or '至今'}")
    logger.info(f"  更新模式: {'增量' if incremental else '全量'}")
    logger.info("=" * 60)
    
    start_time = time.time()
    
    success_count = 0
    fail_count = 0
    
    for i, ts_code in enumerate(ts_codes):
        logger.info(f"[{i + 1}/{len(ts_codes)}] 处理ETF: {ts_code}")
        
        try:
            success = crawl_all_etf_data(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                incremental=incremental
            )
            
            if success:
                success_count += 1
            else:
                fail_count += 1
                
        except Exception as e:
            logger.error(f"处理ETF {ts_code} 时出错: {e}")
            fail_count += 1
        
        # 每个ETF之间添加短暂间隔，避免请求过快
        if i < len(ts_codes) - 1:
            interval = 1
            logger.debug(f"等待 {interval} 秒后继续...")
            time.sleep(interval)
    
    elapsed_time = time.time() - start_time
    
    logger.info("=" * 60)
    logger.info("批量ETF数据获取完成")
    logger.info(f"  成功: {success_count} 个")
    logger.info(f"  失败: {fail_count} 个")
    logger.info(f"  总耗时: {elapsed_time:.2f} 秒")
    logger.info("=" * 60)
    
    return success_count, fail_count


def main():
    """主函数：执行ETF数据爬取流程"""
    print("=" * 60)
    print("Tushare ETF数据爬虫启动")
    print("=" * 60)
    print(f"数据库: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    
    # 示例：获取单个ETF的完整数据
    # 可以根据需要修改为批量模式
    
    # 单ETF模式
    ts_code = '510330.SH'
    start_date = '20250101'
    end_date = '20251231'
    incremental = True
    
    logger.info(f"\n执行模式: 单ETF [{ts_code}]")
    
    try:
        crawl_all_etf_data(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            incremental=incremental
        )
        
        print("=" * 60)
        print("ETF数据爬虫执行完成")
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"ETF数据爬虫执行失败: {e}")
        raise


if __name__ == "__main__":
    main()
