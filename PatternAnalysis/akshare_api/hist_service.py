"""
A 股历史行情（AkShare stock_zh_a_hist）应用层封装。

对应 AkShare 接口：不复权 adjust=""，亦可传 qfq / hfq。
输出可返回规范化字典列表，便于与 Tsanghi 等模块对齐；也可直接返回 DataFrame。
"""
from __future__ import annotations

import inspect
import logging
import random
import sys
import time
from http.client import RemoteDisconnected
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

import pandas as pd
from requests import exceptions as req_exc
from urllib3.exceptions import ProtocolError

from .utils import normalize_a_share_symbol, to_yyyymmdd

logger = logging.getLogger(__name__)

# 当 sys.path 含有 …/PatternAnalysis 时，裸 import akshare 会加载本包而非 PyPI akshare，导致 hist_func 指向本地 get_stock_zh_a_hist 并无限递归。
_LOCAL_AKSHARE_PKG_ROOT = Path(__file__).resolve().parent
_pypi_akshare = None
_MAX_RETRIES = 3
_RETRY_BASE_DELAY_SEC = 0.8


def _akshare_sys_modules_is_local_shadow(mod: Any) -> bool:
    path = getattr(mod, "__file__", None)
    if not path:
        return False
    try:
        return Path(path).resolve().parent == _LOCAL_AKSHARE_PKG_ROOT
    except OSError:
        return False


def _import_pypi_akshare():
    """导入 site-packages 中的 akshare 库。"""
    global _pypi_akshare
    if _pypi_akshare is not None:
        return _pypi_akshare

    # 清除缓存，确保重新导入
    for name in list(sys.modules):
        if name == "akshare" or name.startswith("akshare."):
            del sys.modules[name]

    # 安装代理补丁
    from PatternAnalysis.config import AKSHARE_PROXY_CONFIG
    from . import akshare_proxy_patch

    if AKSHARE_PROXY_CONFIG.get("enabled", False):
        host = AKSHARE_PROXY_CONFIG.get("host", "")
        port = AKSHARE_PROXY_CONFIG.get("port", 0)
        user = AKSHARE_PROXY_CONFIG.get("user", "")
        if host and port:
            logger.info(f"安装 akshare 代理补丁: {host}:{port}")
            akshare_proxy_patch.install_patch(host, user, port)

    import akshare as ak
    _pypi_akshare = ak
    return ak


def _is_retryable_network_error(err: Exception) -> bool:
    """识别可重试的网络瞬时错误（连接中断/超时/远端断开）。"""
    if isinstance(
        err,
        (
            req_exc.Timeout,
            req_exc.ConnectionError,
            req_exc.ChunkedEncodingError,
            req_exc.SSLError,
            ProtocolError,
            RemoteDisconnected,
            TimeoutError,
            ConnectionResetError,
            BrokenPipeError,
        ),
    ):
        return True
    msg = str(err).lower()
    return "remote end closed connection without response" in msg or "connection aborted" in msg


PeriodType = Literal["daily", "weekly", "monthly"]
AdjustType = Literal["", "qfq", "hfq"]

# AkShare 文档中的中文列名 -> 应用层英文字段名
_ZH_TO_EN: Dict[str, str] = {
    "日期": "date",
    "股票代码": "symbol",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
    "振幅": "amplitude_pct",
    "涨跌幅": "pct_change",
    "涨跌额": "change_amount",
    "换手率": "turnover_pct",
}


def _df_row_to_record(row: pd.Series) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for col, val in row.items():
        key = _ZH_TO_EN.get(str(col), str(col))
        if pd.isna(val):
            out[key] = None
        elif key == "date":
            if hasattr(val, "strftime"):
                out[key] = val.strftime("%Y-%m-%d")
            elif isinstance(val, str):
                out[key] = val.replace("/", "-")[:10]
            else:
                out[key] = str(pd.Timestamp(val).date())
        else:
            out[key] = val.item() if hasattr(val, "item") else val
    return out


def _dataframe_to_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    if df is None or df.empty:
        return []
    records: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        records.append(_df_row_to_record(row))
    return records


class StockZhAHistService:
    """封装 ak.stock_zh_a_hist，负责参数规范化与结果转换。"""

    def get_hist_dataframe(
        self,
        symbol: str,
        period: PeriodType = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: AdjustType = "",
        timeout: Optional[float] = None,
    ) -> pd.DataFrame:
        ak = _import_pypi_akshare()

        sym = normalize_a_share_symbol(symbol)
        if not sym:
            logger.warning("normalize_a_share_symbol 得到空代码: %r", symbol)
            return pd.DataFrame()

        sd = to_yyyymmdd(start_date) if start_date else None
        ed = to_yyyymmdd(end_date) if end_date else None

        kwargs: Dict[str, Any] = {
            "symbol": sym,
            "period": period,
            "adjust": adjust,
        }
        if sd is not None:
            kwargs["start_date"] = sd
        if ed is not None:
            kwargs["end_date"] = ed

        # 兼容新旧版本 akshare：新版本使用 get_stock_zh_a_hist，旧版本使用 stock_zh_a_hist
        if hasattr(ak, 'stock_zh_a_hist'):
            hist_func = ak.stock_zh_a_hist
        elif hasattr(ak, 'get_stock_zh_a_hist'):
            hist_func = ak.get_stock_zh_a_hist
        else:
            raise AttributeError("akshare 库中未找到股票历史行情函数 (stock_zh_a_hist 或 get_stock_zh_a_hist)")

        sig = inspect.signature(hist_func)
        if timeout is not None and "timeout" in sig.parameters:
            kwargs["timeout"] = timeout
        elif timeout is not None:
            logger.debug("当前 akshare 版本不支持 timeout 参数，已忽略")

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                df = hist_func(**kwargs)
                break
            except Exception as e:
                if _is_retryable_network_error(e) and attempt < _MAX_RETRIES:
                    sleep_sec = _RETRY_BASE_DELAY_SEC * (2 ** (attempt - 1)) + random.uniform(0, 0.3)
                    logger.warning(
                        "akshare 历史行情网络异常，准备重试: symbol=%s, attempt=%s/%s, wait=%.2fs, err=%s",
                        sym,
                        attempt,
                        _MAX_RETRIES,
                        sleep_sec,
                        e,
                    )
                    time.sleep(sleep_sec)
                    continue
                logger.error("akshare 股票历史行情调用失败: symbol=%s, kwargs=%s, err=%s", sym, kwargs, e)
                raise

        if df is None:
            return pd.DataFrame()
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame(df)

    def get_hist(
        self,
        symbol: str,
        period: PeriodType = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: AdjustType = "",
        timeout: Optional[float] = None,
        as_dataframe: bool = False,
    ) -> Union[List[Dict[str, Any]], pd.DataFrame]:
        """
        获取 A 股历史 K 线。

        Args:
            symbol: 6 位代码，或带后缀如 000001.SZ
            period: daily / weekly / monthly
            start_date: yyyy-mm-dd 或 yyyymmdd，不传则由 AkShare 默认行为决定
            end_date: 同上
            adjust: 不复权 ""；前复权 qfq；后复权 hfq
            timeout: 请求超时（秒），仅当当前 akshare 支持时传入
            as_dataframe: True 时返回 DataFrame，否则返回规范化 dict 列表

        Returns:
            默认 List[dict]，字段名为英文（volume 单位为手，amount 为元，*_pct 为 %）
        """
        df = self.get_hist_dataframe(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
            timeout=timeout,
        )
        if as_dataframe:
            return df
        return _dataframe_to_records(df)


def get_stock_zh_a_hist(
    symbol: str,
    period: PeriodType = "daily",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    adjust: AdjustType = "",
    timeout: Optional[float] = None,
    as_dataframe: bool = False,
) -> Union[List[Dict[str, Any]], pd.DataFrame]:
    """便捷函数：与 StockZhAHistService.get_hist 一致。"""
    svc = StockZhAHistService()
    return svc.get_hist(
        symbol=symbol,
        period=period,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
        timeout=timeout,
        as_dataframe=as_dataframe,
    )


def get_stock_zh_a_hist_dataframe(
    symbol: str,
    period: PeriodType = "daily",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    adjust: AdjustType = "",
    timeout: Optional[float] = None,
) -> pd.DataFrame:
    """便捷函数：直接返回 pandas DataFrame（与 AkShare 列名一致，多为中文）。"""
    return StockZhAHistService().get_hist_dataframe(
        symbol=symbol,
        period=period,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
        timeout=timeout,
    )
