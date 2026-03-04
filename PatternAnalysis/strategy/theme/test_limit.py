"""
测试涨停跌停服务
"""
import sys
import os

# 项目根目录是 easymoneycrawling 的父目录 pythonCode
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PatternAnalysis.strategy.theme.limit_service import (
    get_stock_limit_info,
    calculate_limit_prices_for_all_stocks,
    save_limit_info_to_redis,
    get_limit_info_from_redis,
    get_all_limit_stock_codes,
    LimitPriceInfo
)


def test_single_stock():
    """测试单只股票"""
    print("=" * 50)
    print("测试1: 单只股票计算")
    print("=" * 50)

    test_code = "000001.SZ"
    info = get_stock_limit_info(test_code, use_cache=False)

    if info:
        print(f"\n股票 {info.ts_code}:")
        print(f"  最近涨停日期: {info.limit_up_date}")
        print(f"  涨停价格(SMLP): {info.limit_up_price}")
        print(f"  最近跌停日期: {info.limit_down_date}")
        print(f"  跌停价格: {info.limit_down_price}")
        print(f"  最近收盘价: {info.latest_close}")
        print(f"  收盘/涨停价比(SM_PRE_UP): {info.sm_pre_up}")
        print(f"  收盘/跌停价比(SM_PRE_DOWN): {info.sm_pre_down}")
        return True
    else:
        print(f"未找到股票 {test_code} 的数据")
        return False


def test_save_to_redis():
    """测试Redis存储"""
    print("\n" + "=" * 50)
    print("测试2: Redis存储")
    print("=" * 50)

    # 先计算
    info = get_stock_limit_info("000001.SZ", use_cache=False)
    if not info:
        print("计算失败")
        return False

    # 保存到Redis
    success = save_limit_info_to_redis(info)
    print(f"保存结果: {'成功' if success else '失败'}")

    if success:
        # 从Redis读取
        cached = get_limit_info_from_redis("000001.SZ")
        if cached:
            print("从Redis读取成功:")
            print(f"  涨停日期: {cached.limit_up_date}, 涨停价: {cached.limit_up_price}")
            print(f"  跌停日期: {cached.limit_down_date}, 跌停价: {cached.limit_down_price}")
            return True
        else:
            print("从Redis读取失败")
            return False
    return False


def test_multi_thread():
    """测试多线程批量计算"""
    print("\n" + "=" * 50)
    print("测试3: 多线程批量计算")
    print("=" * 50)

    import time
    start_time = time.time()

    # 使用4线程计算
    results = calculate_limit_prices_for_all_stocks(num_threads=4)

    elapsed = time.time() - start_time
    print(f"计算完成，共处理 {len(results)} 只股票，耗时: {elapsed:.2f}秒")

    # 统计有涨停/跌停的股票数量
    limit_up_count = sum(1 for r in results if r.limit_up_date)
    limit_down_count = sum(1 for r in results if r.limit_down_date)

    print(f"有涨停记录的股票: {limit_up_count}")
    print(f"有跌停记录的股票: {limit_down_count}")

    # 保存前10只到Redis作为示例
    print("\n保存前10只股票到Redis...")
    for i, info in enumerate(results[:10]):
        save_limit_info_to_redis(info)
    print("完成")

    return True


def test_get_all_codes():
    """测试获取所有有涨停/跌停记录的股票"""
    print("\n" + "=" * 50)
    print("测试4: 获取有涨停/跌停记录的股票")
    print("=" * 50)

    up_codes = get_all_limit_stock_codes("up")
    down_codes = get_all_limit_stock_codes("down")

    print(f"有涨停记录的股票数量: {len(up_codes)}")
    print(f"有跌停记录的股票数量: {len(down_codes)}")

    if up_codes:
        print(f"涨停股票示例: {up_codes[:5]}")

    return True


if __name__ == "__main__":
    test_single_stock()
    test_save_to_redis()
    test_multi_thread()
    test_get_all_codes()
    print("\n所有测试完成!")
