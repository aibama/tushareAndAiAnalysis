"""
Z-Score API 路由

提供热度图所需的数据接口
"""
import logging
from datetime import date, datetime
from typing import Optional
from flask import Blueprint, request, jsonify
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .zscore_service import (
    get_industry_daily_zscore,
    get_industry_stocks_zscore,
    get_stock_timeseries_zscore,
    get_industry_timeseries_zscore,
    get_index_timeseries_zscore
)
from .data_service import get_latest_trade_date
from .config import ZSCORE_CONFIG, get_zscore_color

logger = logging.getLogger(__name__)

# 创建蓝图
zscore_bp = Blueprint('zscore', __name__, url_prefix='/api/v1/zscore')


def success_response(data, message="success"):
    """成功响应"""
    return jsonify({
        "code": 0,
        "message": message,
        "data": data,
        "timestamp": datetime.now().isoformat()
    })


def error_response(message, code=-1):
    """错误响应"""
    return jsonify({
        "code": code,
        "message": message,
        "data": None,
        "timestamp": datetime.now().isoformat()
    })


def parse_date(date_str: str) -> Optional[date]:
    """解析日期字符串"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return None


@zscore_bp.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return success_response({"status": "ok"})


@zscore_bp.route('/industry/daily', methods=['GET'])
def get_industry_daily():
    """
    获取行业列表及当日Z-Score

    Query Parameters:
        - date: 日期 (YYYY-MM-DD)，可选，默认最新交易日
        - indicator: 指标类型 (price/pe/pb)，默认 price

    Response:
        {
            "code": 0,
            "data": {
                "date": "2026-03-20",
                "industries": [
                    {
                        "industry_code": "801010",
                        "industry_name": "电子",
                        "stock_count": 85,
                        "zscore": 0.85,
                        "color": "#FFB3BA"
                    },
                    ...
                ]
            }
        }
    """
    try:
        # 获取参数
        date_str = request.args.get('date')
        indicator = request.args.get('indicator', 'price')

        # 解析日期
        trade_date = parse_date(date_str)
        if trade_date is None:
            trade_date = get_latest_trade_date()

        # 验证指标类型
        valid_indicators = list(ZSCORE_CONFIG.get("indicators", {}).keys())
        if indicator not in valid_indicators:
            return error_response(f"无效的指标类型: {indicator}，可选值: {valid_indicators}")

        # 获取数据
        industries = get_industry_daily_zscore(trade_date, indicator)

        # 添加颜色信息
        for item in industries:
            item['color'] = get_zscore_color(item.get('zscore'))

        return success_response({
            "date": trade_date.strftime('%Y-%m-%d'),
            "indicator": indicator,
            "industries": industries
        })

    except Exception as e:
        logger.error(f"获取行业Z-Score失败: {e}", exc_info=True)
        return error_response(f"获取数据失败: {str(e)}")


@zscore_bp.route('/industry/stocks', methods=['GET'])
def get_industry_stocks():
    """
    获取某行业下成分股及当日Z-Score

    Query Parameters:
        - date: 日期 (YYYY-MM-DD)，可选，默认最新交易日
        - indicator: 指标类型 (price/pe/pb)，默认 price
        - industry_code: 行业代码，必填

    Response:
        {
            "code": 0,
            "data": {
                "date": "2026-03-20",
                "industry_code": "801010",
                "industry_name": "电子",
                "stocks": [
                    {
                        "ts_code": "000001.SZ",
                        "stock_name": "平安银行",
                        "zscore": 1.23,
                        "indicator_value": 12.34,
                        "color": "#E63946"
                    },
                    ...
                ]
            }
        }
    """
    try:
        # 获取参数
        date_str = request.args.get('date')
        indicator = request.args.get('indicator', 'price')
        industry_code = request.args.get('industry_code')

        # 验证必填参数
        if not industry_code:
            return error_response("缺少必填参数: industry_code")

        # 解析日期
        trade_date = parse_date(date_str)
        if trade_date is None:
            trade_date = get_latest_trade_date()

        # 验证指标类型
        valid_indicators = list(ZSCORE_CONFIG.get("indicators", {}).keys())
        if indicator not in valid_indicators:
            return error_response(f"无效的指标类型: {indicator}")

        # 获取数据
        result = get_industry_stocks_zscore(industry_code, trade_date, indicator)

        if not result or not result.get('stocks'):
            return error_response(f"未找到行业 {industry_code} 的成分股数据")

        # 添加颜色信息
        for item in result['stocks']:
            item['color'] = get_zscore_color(item.get('zscore'))

        return success_response({
            "date": trade_date.strftime('%Y-%m-%d'),
            "indicator": indicator,
            "industry_code": industry_code,
            "industry_name": result.get('industry_name'),
            "stocks": result['stocks']
        })

    except Exception as e:
        logger.error(f"获取行业成分股Z-Score失败: {e}", exc_info=True)
        return error_response(f"获取数据失败: {str(e)}")


@zscore_bp.route('/timeseries', methods=['GET'])
def get_timeseries():
    """
    获取时间序列（行业或个股）

    Query Parameters:
        - date: 结束日期 (YYYY-MM-DD)，必填
        - indicator: 指标类型 (price/pe/pb)，默认 price
        - entity_type: 实体类型 (industry/stock)，必填
        - entity_code: 实体代码（行业代码或股票代码），必填
        - days: 回溯天数，默认 60

    Response:
        {
            "code": 0,
            "data": {
                "entity_type": "industry",
                "entity_code": "801010",
                "entity_name": "电子",
                "indicator": "price",
                "series": [
                    {"date": "2026-01-01", "zscore": 0.5},
                    ...
                ]
            }
        }
    """
    try:
        # 获取参数
        date_str = request.args.get('date')
        indicator = request.args.get('indicator', 'price')
        entity_type = request.args.get('entity_type')
        entity_code = request.args.get('entity_code')
        days = request.args.get('days', 60, type=int)

        # 验证必填参数
        if not date_str:
            return error_response("缺少必填参数: date")
        if not entity_type:
            return error_response("缺少必填参数: entity_type")
        if not entity_code:
            return error_response("缺少必填参数: entity_code")

        # 解析日期
        trade_date = parse_date(date_str)
        if trade_date is None:
            return error_response("无效的日期格式，应为 YYYY-MM-DD")

        # 验证实体类型
        if entity_type not in ['industry', 'stock']:
            return error_response("无效的 entity_type，应为 industry 或 stock")

        # 验证指标类型
        valid_indicators = list(ZSCORE_CONFIG.get("indicators", {}).keys())
        if indicator not in valid_indicators:
            return error_response(f"无效的指标类型: {indicator}")

        # 获取数据
        if entity_type == 'industry':
            result = get_industry_timeseries_zscore(entity_code, trade_date, days, indicator)
            entity_name = result.get('industry_name', entity_code)
        else:
            result = get_stock_timeseries_zscore(entity_code, trade_date, days, indicator)
            entity_name = result.get('stock_name', entity_code)

        if not result or not result.get('series'):
            return error_response(f"未找到实体 {entity_code} 的时间序列数据")

        return success_response({
            "entity_type": entity_type,
            "entity_code": entity_code,
            "entity_name": entity_name,
            "indicator": indicator,
            "days": days,
            "series": result['series']
        })

    except Exception as e:
        logger.error(f"获取时间序列失败: {e}", exc_info=True)
        return error_response(f"获取数据失败: {str(e)}")


@zscore_bp.route('/index/timeseries', methods=['GET'])
def get_index_timeseries():
    """
    获取中证1000指数整体Z-Score时间序列

    Query Parameters:
        - date: 结束日期 (YYYY-MM-DD)，可选，默认最新交易日
        - indicator: 指标类型 (price/pe/pb)，默认 price
        - days: 回溯天数，默认 60

    Response:
        {
            "code": 0,
            "data": {
                "index_code": "000852",
                "index_name": "中证1000",
                "indicator": "price",
                "series": [
                    {"date": "2026-01-01", "zscore": 0.5},
                    ...
                ]
            }
        }
    """
    try:
        # 获取参数
        date_str = request.args.get('date')
        indicator = request.args.get('indicator', 'price')
        days = request.args.get('days', 60, type=int)

        # 解析日期
        trade_date = parse_date(date_str)
        if trade_date is None:
            trade_date = get_latest_trade_date()

        # 验证指标类型
        valid_indicators = list(ZSCORE_CONFIG.get("indicators", {}).keys())
        if indicator not in valid_indicators:
            return error_response(f"无效的指标类型: {indicator}")

        # 获取数据
        result = get_index_timeseries_zscore(trade_date, days, indicator)

        if not result or not result.get('series'):
            return error_response("未找到指数时间序列数据")

        return success_response({
            "index_code": result.get('index_code'),
            "index_name": result.get('index_name'),
            "indicator": indicator,
            "days": days,
            "series": result['series']
        })

    except Exception as e:
        logger.error(f"获取指数时间序列失败: {e}", exc_info=True)
        return error_response(f"获取数据失败: {str(e)}")


@zscore_bp.route('/config', methods=['GET'])
def get_config():
    """获取配置信息"""
    return success_response({
        "indicators": ZSCORE_CONFIG.get("indicators", {}),
        "window_days": ZSCORE_CONFIG.get("window_days", 60),
        "index_codes": ZSCORE_CONFIG.get("index_codes", {})
    })


def register_routes(app):
    """注册路由到Flask应用"""
    app.register_blueprint(zscore_bp)
    logger.info("Z-Score API 路由已注册")


if __name__ == "__main__":
    # 测试
    from flask import Flask

    app = Flask(__name__)
    register_routes(app)

    app.run(host='0.0.0.0', port=5000, debug=True)
