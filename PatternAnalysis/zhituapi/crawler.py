"""
智途API爬虫主程序

功能：
1. 调用接口一获取股票列表，存入stockinfobase表
2. 调用接口二获取股票详细信息，存入stock_trade_info表（每5-10秒随机间隔）
"""
import time
import logging
import sys
import os

# 添加项目根目录到sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PatternAnalysis.zhituapi.api_client import ZhituApiClient
from PatternAnalysis.zhituapi.db_operations import (
    save_stock_list_to_db,
    get_all_ts_codes,
    save_stock_info_to_db
)
from PatternAnalysis.config import DB_CONFIG

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def crawl_stock_list():
    """步骤1: 获取股票列表并存入stockinfobase表"""
    logger.info("=" * 50)
    logger.info("[步骤1] 开始获取股票列表...")
    logger.info("=" * 50)

    api_client = ZhituApiClient()

    try:
        stock_list = api_client.get_stock_list()

        if not stock_list:
            logger.warning("未获取到任何股票数据")
            return False

        saved_count = save_stock_list_to_db(stock_list)

        if saved_count > 0:
            logger.info(f"步骤1完成: 成功保存 {saved_count} 只股票到stockinfobase表")
            return True
        else:
            logger.error("步骤1失败: 保存股票基本信息失败")
            return False

    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        return False


def crawl_stock_details():
    """步骤2: 获取股票详细信息并存入stock_trade_info表（每5-10秒调用一次）"""
    logger.info("=" * 50)
    logger.info("[步骤2] 开始获取股票详细信息...")
    logger.info("=" * 50)

    stock_codes = get_all_ts_codes()

    if not stock_codes:
        logger.warning("数据库中没有股票数据，请先执行步骤1")
        return False

    logger.info(f"找到 {len(stock_codes)} 只股票需要获取详细信息")

    api_client = ZhituApiClient()

    success_count = 0
    fail_count = 0
    start_time = time.time()

    try:
        for i, stock_code in enumerate(stock_codes):
            is_last = (i == len(stock_codes) - 1)

            logger.info(f"获取股票信息 [{i + 1}/{len(stock_codes)}]: {stock_code}")

            stock_info = api_client.get_stock_info(stock_code)

            if stock_info:
                result = save_stock_info_to_db(stock_info)
                if result > 0:
                    logger.info(f"  -> 成功")
                    success_count += 1
                else:
                    logger.warning(f"  -> 保存失败")
                    fail_count += 1
            else:
                logger.warning(f"  -> 未获取到数据")
                fail_count += 1

            # 每5-10秒随机延时（最后一次不需要延时）
            if not is_last:
                interval = api_client.get_random_interval()
                logger.debug(f"  等待 {interval:.2f} 秒后继续...")
                time.sleep(interval)

    except KeyboardInterrupt:
        logger.warning("用户中断爬取")
    except Exception as e:
        logger.error(f"爬取过程出错: {e}")
    finally:
        api_client.close()

    elapsed_time = time.time() - start_time
    logger.info("=" * 50)
    logger.info("股票详细信息获取完成:")
    logger.info(f"  成功: {success_count} 只")
    logger.info(f"  失败: {fail_count} 只")
    logger.info(f"  耗时: {elapsed_time:.2f} 秒")
    logger.info("=" * 50)

    return True


def main():
    """主函数：执行完整的爬取流程"""
    print("=" * 50)
    print("智途API股票数据爬虫启动")
    print("=" * 50)
    print(f"数据库: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")

    try:
        # step1_success = crawl_stock_list()

        # if not step1_success:
        #     logger.error("步骤1失败，退出程序")
        #     return

        crawl_stock_details()

        print("=" * 50)
        print("爬虫执行完成")
        print("=" * 50)

    except Exception as e:
        logger.error(f"爬虫执行失败: {e}")
        raise


if __name__ == "__main__":
    main()
