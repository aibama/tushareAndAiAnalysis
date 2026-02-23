#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试MTR/ATR计算功能"""

import sys
sys.path.insert(0, '.')

import pymysql
import json

# 直接使用pymysql测试
conn = pymysql.connect(
    host='localhost',
    port=3306,
    user='root',
    password='123456',
    database='stockdata',
    charset='utf8',
    cursorclass=pymysql.cursors.DictCursor
)

cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) as cnt FROM stocktradetodayinfo')
row = cursor.fetchone()
print(f'表记录数: {row["cnt"]}')

cursor.execute('SELECT COUNT(DISTINCT ts_code) as distinct_cnt FROM stocktradetodayinfo WHERE ts_code IS NOT NULL AND ts_code != ""')
row = cursor.fetchone()
print(f'去重股票数: {row["distinct_cnt"]}')

cursor.execute('SELECT ts_code, COUNT(*) as cnt FROM stocktradetodayinfo WHERE ts_code IS NOT NULL AND ts_code != "" GROUP BY ts_code LIMIT 5')
rows = cursor.fetchall()
print('前5个股票:')
for row in rows:
    print(f'  {row["ts_code"]}: {row["cnt"]} 条记录')

cursor.close()
conn.close()

print('\n=== 测试StockStatisticsService ===')
from orm.etf.stock_statistics_service import StockStatisticsService

service = StockStatisticsService()
summary = service.get_stock_data_summary()
print(f'总股票数: {summary["total_stocks"]}')

if summary['stocks']:
    print('前3个股票:')
    for stock in summary['stocks'][:3]:
        print(f'  {stock["ts_code"]}: {stock["record_count"]} 条记录, 从 {stock["start_date"]} 到 {stock["end_date"]}')

# 测试MTR/ATR计算
if summary['stocks']:
    test_ts_code = summary['stocks'][0]['ts_code']
    print(f'\n测试股票 {test_ts_code} 的MTR/ATR:')
    mtr, atr = service.calculate_mtr_atr(test_ts_code)
    print(f'  MTR: {mtr}')
    print(f'  ATR: {atr}')

service.close()

print('\n测试完成!')
