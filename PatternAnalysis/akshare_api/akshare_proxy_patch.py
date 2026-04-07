"""
Akshare 代理补丁模块
用于在使用 akshare 时通过代理发送请求
"""
import logging
import sys

import requests

logger = logging.getLogger(__name__)


def _get_akshare_module():
    """获取已加载的 PyPI akshare 模块；尚未 import 时返回 None。"""
    return sys.modules.get("akshare")

# 代理配置
_proxy_host = None
_proxy_port = None
_proxy_auth = None
_installed = False
_original_session_class = None


def install_patch(proxy_host: str, proxy_user: str = "", proxy_port: int = 0):
    """
    安装代理补丁，修改 akshare 的请求行为

    Args:
        proxy_host: 代理主机地址
        proxy_user: 代理用户名（可选）
        proxy_port: 代理端口
    """
    global _proxy_host, _proxy_port, _proxy_auth, _installed, _original_session_class

    if not proxy_host or not proxy_port:
        logger.warning("代理配置不完整，跳过安装补丁")
        return
    if not (1 <= int(proxy_port) <= 65535):
        logger.warning("代理端口不合法(%s)，跳过安装补丁", proxy_port)
        return

    _proxy_host = proxy_host
    _proxy_port = proxy_port

    # 构建代理认证信息
    if proxy_user:
        _proxy_auth = (proxy_user, "")
    else:
        _proxy_auth = None

    # 构建代理 URL
    if proxy_user:
        proxy_url = f"http://{proxy_user}:@{proxy_host}:{proxy_port}"
    else:
        proxy_url = f"http://{proxy_host}:{proxy_port}"

    logger.info(f"安装 akshare 代理补丁: {proxy_url}")

    # 保存原始的 requests.Session 类
    _original_session = requests.Session
    _original_session_class = _original_session

    class ProxiedSession(_original_session):
        """带代理的 Session 类"""

        def __init__(self):
            super().__init__()
            self.proxies = {
                "http": proxy_url,
                "https": proxy_url,
            }

    # 替换 akshare 内部使用的 session 创建逻辑
    # akshare 使用 requests.Session() 创建 session，我们替换全局的 Session
    requests.Session = ProxiedSession

    # 若 akshare 已在本次进程内加载过，替换其全局 Session；否则等后续 import 时会使用已补丁的 Session
    ak_mod = _get_akshare_module()
    if ak_mod is not None and getattr(ak_mod, "_sess", None) is not None:
        ak_mod._sess = ProxiedSession()

    # 尝试替换 akshare 的全局 session
    _patch_akshare_global_session(ProxiedSession)

    _installed = True
    logger.info("akshare 代理补丁安装成功")


def _patch_akshare_global_session(session_class):
    """修补 akshare 全局 session"""
    try:
        ak_mod = _get_akshare_module()
        if ak_mod is not None and hasattr(ak_mod, "_sess"):
            ak_mod._sess = session_class()
    except Exception as e:
        logger.debug(f"修补 akshare 全局 session 失败: {e}")


def uninstall_patch():
    """卸载代理补丁"""
    global _installed, _original_session_class

    if _installed and _original_session_class is not None:
        # 恢复原始的 Session 类
        requests.Session = _original_session_class
        _installed = False
        logger.info("akshare 代理补丁已卸载")


def is_installed() -> bool:
    """检查代理补丁是否已安装"""
    return _installed
