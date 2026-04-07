"""
单只股票 Baostock 日线同步测试（可写库）。

等价 HTTP（启动 FastAPI 后在 Swagger ``/docs`` 中也可调用）::

    GET /api/baostock/sync/tradetoday/one?ts_code=600000.SH&start_date=2024-07-01&end_date=2024-12-31&dry_run=false

用法（在项目根目录 easymoneycrawling 下）::

    python -m PatternAnalysis.baostock_api.test_sync_one_stock --ts-code 600000.SH --start-date 2024-07-01 --end-date 2024-12-31

仅拉取不落库::

    python -m PatternAnalysis.baostock_api.test_sync_one_stock --ts-code 000001.SZ --start-date 2024-01-01 --end-date 2024-01-31 --dry-run
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def main() -> int:
    p = argparse.ArgumentParser(description="Baostock 单股日线同步测试")
    p.add_argument("--ts-code", required=True, help="如 600000.SH、000001.SZ")
    p.add_argument("--start-date", required=True)
    p.add_argument("--end-date", required=True)
    p.add_argument("--adjust", default="", choices=["", "qfq", "hfq"])
    p.add_argument("--dry-run", action="store_true", help="只拉取并打印条数，不写 MySQL")
    args = p.parse_args()

    import baostock as bs

    from PatternAnalysis.akshare_api.tradetoday_upsert import (
        has_tradetoday_data_in_range,
        upsert_tradetoday_rows,
    )
    from PatternAnalysis.baostock_api.hist_service import BaostockHistService
    from PatternAnalysis.baostock_api.utils import AdjustType, ts_code_to_baostock_code

    ts_code = args.ts_code.strip()
    adjust: AdjustType = args.adjust  # type: ignore[assignment]

    if has_tradetoday_data_in_range(ts_code, args.start_date, args.end_date):
        print("幂等：区间内已有数据，跳过同步（与全量接口一致）")
        return 0

    lg = bs.login()
    if lg.error_code != "0":
        print(f"登录失败: {lg.error_code} {lg.error_msg}")
        return 1
    try:
        print(f"Baostock 代码: {ts_code_to_baostock_code(ts_code)}")
        svc = BaostockHistService()
        records = svc.query_daily_records(ts_code, args.start_date, args.end_date, adjust)
        print(f"拉取条数: {len(records)}")
        if records:
            print(f"样例首条键: {list(records[0].keys())}")
        if args.dry_run:
            return 0
        n = upsert_tradetoday_rows(ts_code, records)
        print(f"写入/更新行数: {n}")
    finally:
        bs.logout()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
