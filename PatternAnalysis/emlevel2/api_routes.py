"""
Redis Stream 生产者 API 路由

提供 Flask 接口用于手动触发和查询状态
"""
import logging
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

# 创建 Blueprint
producer_bp = Blueprint('producer', __name__, url_prefix='/api/producer')


@producer_bp.route('/trigger', methods=['POST'])
def trigger_production():
    """
    手动触发股票代码生产
    
    请求参数:
        - force: 是否强制执行（忽略时间窗口检查），默认为 false
        - limit: 限制处理数量，可选
        - composition_codes: 成分股筛选，多个用逗号分隔，可选
    
    返回:
        JSON 格式的执行结果
    """
    from .stock_producer_service import produce_stock_codes
    
    force = request.json.get('force', False) if request.is_json else request.args.get('force', 'false').lower() == 'true'
    limit = request.json.get('limit') if request.is_json else request.args.get('limit', type=int)
    
    composition_codes = None
    if request.is_json and request.json.get('composition_codes'):
        composition_codes = request.json.get('composition_codes')
    elif request.args.get('composition_codes'):
        composition_codes = request.args.get('composition_codes').split(',')
    
    logger.info(f"手动触发请求: force={force}, limit={limit}, composition_codes={composition_codes}")
    
    try:
        result = produce_stock_codes(
            force=force,
            limit=limit,
            composition_codes=composition_codes
        )
        return jsonify(result)
    except Exception as e:
        logger.error(f"触发失败: {e}")
        return jsonify({
            "success": False,
            "message": str(e),
            "count": 0
        }), 500


@producer_bp.route('/add_stock', methods=['POST'])
def add_stock():
    """
    添加单个股票代码到 Stream
    
    请求参数:
        - stock_code: 股票代码（必填）
        - composition_code: 成分股归属（可选）
    
    返回:
        JSON 格式的执行结果
    """
    from .stock_producer_service import add_single_stock_code
    
    stock_code = None
    composition_code = None
    
    if request.is_json:
        stock_code = request.json.get('stock_code')
        composition_code = request.json.get('composition_code')
    else:
        stock_code = request.args.get('stock_code')
        composition_code = request.args.get('composition_code')
    
    if not stock_code:
        return jsonify({
            "success": False,
            "message": "缺少 stock_code 参数"
        }), 400
    
    logger.info(f"添加股票代码: {stock_code}, composition: {composition_code}")
    
    try:
        result = add_single_stock_code(stock_code, composition_code)
        return jsonify(result)
    except Exception as e:
        logger.error(f"添加失败: {e}")
        return jsonify({
            "success": False,
            "message": str(e),
            "stock_code": stock_code
        }), 500


@producer_bp.route('/stream/info', methods=['GET'])
def get_stream_info():
    """
    获取 Stream 信息
    
    返回:
        JSON 格式的 Stream 信息
    """
    from .stock_producer_service import RedisStreamProducer
    
    try:
        producer = RedisStreamProducer()
        info = producer.get_stream_info()
        producer.close()
        return jsonify({
            "success": True,
            "data": info
        })
    except Exception as e:
        logger.error(f"获取 Stream 信息失败: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@producer_bp.route('/scheduler/status', methods=['GET'])
def get_scheduler_status():
    """
    获取调度器状态
    
    返回:
        JSON 格式的调度器状态
    """
    from .scheduler_service import get_scheduler
    
    try:
        scheduler = get_scheduler()
        status = scheduler.get_status()
        return jsonify({
            "success": True,
            "data": status
        })
    except Exception as e:
        logger.error(f"获取调度器状态失败: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@producer_bp.route('/scheduler/start', methods=['POST'])
def start_scheduler():
    """
    启动调度器
    
    返回:
        JSON 格式的执行结果
    """
    from .scheduler_service import start_scheduler
    
    try:
        start_scheduler()
        return jsonify({
            "success": True,
            "message": "调度器已启动"
        })
    except Exception as e:
        logger.error(f"启动调度器失败: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@producer_bp.route('/scheduler/stop', methods=['POST'])
def stop_scheduler():
    """
    停止调度器
    
    返回:
        JSON 格式的执行结果
    """
    from .scheduler_service import stop_scheduler
    
    try:
        stop_scheduler()
        return jsonify({
            "success": True,
            "message": "调度器已停止"
        })
    except Exception as e:
        logger.error(f"停止调度器失败: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@producer_bp.route('/stocks', methods=['GET'])
def get_stocks_from_db():
    """
    从数据库获取股票列表
    
    查询参数:
        - limit: 限制返回数量
        - composition_codes: 成分股筛选，多个用逗号分隔
    
    返回:
        JSON 格式的股票列表
    """
    from .stock_producer_service import fetch_stocks_from_db
    
    limit = request.args.get('limit', type=int)
    composition_codes = None
    if request.args.get('composition_codes'):
        composition_codes = request.args.get('composition_codes').split(',')
    
    try:
        stocks = fetch_stocks_from_db(limit=limit, composition_codes=composition_codes)
        return jsonify({
            "success": True,
            "count": len(stocks),
            "data": stocks
        })
    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        return jsonify({
            "success": False,
            "message": str(e),
            "count": 0
        }), 500


def register_routes(app):
    """注册路由到 Flask 应用"""
    app.register_blueprint(producer_bp)
    logger.info("Redis Stream 生产者 API 路由已注册")
