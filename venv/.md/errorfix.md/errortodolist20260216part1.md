/api/rank 接口报错了，Internal Server Error 。日志是：2026-02-16 08:15:08,629 - PatternAnalysis.api_service - INFO - 开始计算股票排名: direction=up, start=2025-01-20, end=2026-01-10
2026-02-16 08:15:08,630 - PatternAnalysis.api_service - INFO - 尝试从缓存获取完整数据...
2026-02-16 08:15:09,308 - PatternAnalysis.api_service - INFO - 正在获取股票列表...
2026-02-16 08:15:10,131 - PatternAnalysis.api_service - INFO - 获取到 5503 只股票
2026-02-16 08:15:10,132 - PatternAnalysis.api_service - INFO - 阶段1：使用SQL批量计算涨跌幅...
2026-02-16 08:15:35,166 - PatternAnalysis.api_service - INFO - 阶段1完成：通过SQL计算了 4447 只股票的涨跌幅，耗时: 25.03秒
2026-02-16 08:15:35,167 - PatternAnalysis.api_service - INFO - 缓存初步结果（无回撤/反弹）...
2026-02-16 08:15:35,171 - PatternAnalysis.api_service - INFO - 阶段2：启动异步计算回撤/反弹...
INFO:     127.0.0.1:60807 - "GET /api/rank?direction=up&start_date=2025-01-20&end_date=2026-01-10&limit=10&use_cache=true HTTP/1.1" 500 Internal Server Error
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  File "C:\Users\dzs52\AppData\Roaming\Python\Python314\site-packages\uvicorn\protocols\http\h11_impl.py", line 410, in run_asgi
    result = await app(  # type: ignore[func-returns-value]
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        self.scope, self.receive, self.send
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "C:\Users\dzs52\AppData\Roaming\Python\Python314\site-packages\uvicorn\middleware\proxy_headers.py", line 60, in __call__
    return await self.app(scope, receive, send)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\dzs52\AppData\Roaming\Python\Python314\site-packages\fastapi\applications.py", line 1134, in __call__
    await super().__call__(scope, receive, send)
  File "C:\Users\dzs52\AppData\Roaming\Python\Python314\site-packages\starlette\applications.py", line 107, in __call__
    await self.middleware_stack(scope, receive, send)
  File "C:\Users\dzs52\AppData\Roaming\Python\Python314\site-packages\starlette\middleware\errors.py", line 186, in __call__
    raise exc
  File "C:\Users\dzs52\AppData\Roaming\Python\Python314\site-packages\starlette\middleware\errors.py", line 164, in __call__
    await self.app(scope, receive, _send)
  File "C:\Users\dzs52\AppData\Roaming\Python\Python314\site-packages\starlette\middleware\exceptions.py", line 63, in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
  File "C:\Users\dzs52\AppData\Roaming\Python\Python314\site-packages\starlette\_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "C:\Users\dzs52\AppData\Roaming\Python\Python314\site-packages\starlette\_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "C:\Users\dzs52\AppData\Roaming\Python\Python314\site-packages\fastapi\middleware\asyncexitstack.py", line 18, in __call__
    await self.app(scope, receive, send)
  File "C:\Users\dzs52\AppData\Roaming\Python\Python314\site-packages\starlette\routing.py", line 716, in __call__
    await self.middleware_stack(scope, receive, send)
  File "C:\Users\dzs52\AppData\Roaming\Python\Python314\site-packages\starlette\routing.py", line 736, in app
    await route.handle(scope, receive, send)
  File "C:\Users\dzs52\AppData\Roaming\Python\Python314\site-packages\starlette\routing.py", line 290, in handle
    await self.app(scope, receive, send)
  File "C:\Users\dzs52\AppData\Roaming\Python\Python314\site-packages\fastapi\routing.py", line 119, in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
  File "C:\Users\dzs52\AppData\Roaming\Python\Python314\site-packages\starlette\_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "C:\Users\dzs52\AppData\Roaming\Python\Python314\site-packages\starlette\_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "C:\Users\dzs52\AppData\Roaming\Python\Python314\site-packages\fastapi\routing.py", line 105, in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
  File "C:\Users\dzs52\AppData\Roaming\Python\Python314\site-packages\fastapi\routing.py", line 424, in app
    raw_response = await run_endpoint_function(
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    ...<3 lines>...
    )
    ^
  File "C:\Users\dzs52\AppData\Roaming\Python\Python314\site-packages\fastapi\routing.py", line 312, in run_endpoint_function
    return await dependant.call(**values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\03_code\pythonCode\easymoneycrawling\PatternAnalysis\api_service.py", line 675, in get_stock_rank
    StockRankItem(
    ~~~~~~~~~~~~~^
        rank=i + 1,
        ^^^^^^^^^^^
    ...<2 lines>...
        max_drawdown_rebound=item.get("max_drawdown_rebound")  # 可能为None
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "C:\Users\dzs52\AppData\Roaming\Python\Python314\site-packages\pydantic\main.py", line 250, in __init__
    validated_self = self.__pydantic_validator__.validate_python(data, self_instance=self)
pydantic_core._pydantic_core.ValidationError: 1 validation error for StockRankItem
max_drawdown_rebound
  Input should be a valid number [type=float_type, input_value=None, input_type=NoneType]
    For further information visit https://errors.pydantic.dev/2.12/v/float_type
2026-02-16 08:15:35,186 - PatternAnalysis.api_service - INFO - 异步任务开始: 计算 4447 只股票的回撤/反弹