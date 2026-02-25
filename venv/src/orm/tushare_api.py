"""
Tushare API 服务封装
提供申万行业分类数据接口
参考 venv/src/mytushare/etf/ 下的配置方式
"""
import tushare as ts
import pandas as pd
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

# 全局变量存储token和http_url
_token = None
_http_url = None
_pro = None

def _init_tushare():
    """初始化Tushare配置"""
    global _token, _http_url, _pro
    
    if _pro is not None:
        return _pro
    
    # 尝试从配置文件读取
    try:
        from PatternAnalysis.config import TUSHARE_CONFIG
        _token = TUSHARE_CONFIG.get('token')
        _http_url = TUSHARE_CONFIG.get('http_url', 'http://lianghua.nanyangqiankun.top')
        token_display = _token[:10] + "..." if _token else "None"
        logger.info(f"从PatternAnalysis.config读取Tushare配置: token={token_display}, url={_http_url}")
    except ImportError:
        logger.warning("无法导入PatternAnalysis.config，使用默认配置")
        _token = None
        _http_url = 'http://lianghua.nanyangqiankun.top'
    
    # 设置token
    if _token:
        ts.set_token(_token)
        _pro = ts.pro_api()
        # 设置token到DataApi
        _pro._DataApi__token = _token
        # 设置自定义http_url
        if _http_url:
            _pro._DataApi__http_url = _http_url
        logger.info("Tushare Token配置完成")
    else:
        logger.warning("未配置Tushare Token")
        _pro = ts.pro_api()
    
    return _pro


class TushareApiService:
    """Tushare API 服务类"""
    
    _instance = None
    _pro = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_pro()
        return cls._instance
    
    def _init_pro(self):
        """初始化tushare pro接口"""
        self._pro = _init_tushare()
    
    @property
    def pro(self):
        """获取pro接口"""
        return self._pro
    
    def get_index_classify(self, level: str = 'L1', src: str = 'SW2021') -> pd.DataFrame:
        """
        获取申万行业分类
        
        参数:
            level: 层级, L1/L2/L3
            src: 版本, SW2014 或 SW2021
            
        返回:
            DataFrame: 申万行业分类数据
        """
        df = self.pro.index_classify(level=level, src=src)
        return df
    
    def get_sw_l1_industry(self, src: str = 'SW2021') -> pd.DataFrame:
        """获取申万一级行业列表"""
        return self.get_index_classify(level='L1', src=src)
    
    def get_sw_l2_industry(self, src: str = 'SW2021') -> pd.DataFrame:
        """获取申万二级行业列表"""
        return self.get_index_classify(level='L2', src=src)
    
    def get_sw_l3_industry(self, src: str = 'SW2021') -> pd.DataFrame:
        """获取申万三级行业列表"""
        return self.get_index_classify(level='L3', src=src)
    
    def get_all_sw_industry(self, src: str = 'SW2021') -> pd.DataFrame:
        """获取所有申万行业列表（一二三級）"""
        l1_df = self.get_sw_l1_industry(src)
        l2_df = self.get_sw_l2_industry(src)
        l3_df = self.get_sw_l3_industry(src)
        
        # 添加层级标识
        l1_df['src_level'] = 1
        l2_df['src_level'] = 2
        l3_df['src_level'] = 3
        
        # 合并所有数据
        all_df = pd.concat([l1_df, l2_df, l3_df], ignore_index=True)
        return all_df
    
    def get_index_member_all(self, l3_code: str = None) -> pd.DataFrame:
        """
        按三级分类提取申万行业成分
        
        参数:
            l3_code: 三级行业代码，如 '850531.SI'
            
        返回:
            DataFrame: 行业成分股数据
        """
        df = self.pro.index_member_all(l3_code=l3_code)
        return df
    
    def get_all_l3_members(self, l3_codes: List[str] = None) -> pd.DataFrame:
        """
        获取多个三级行业的成分股
        
        参数:
            l3_codes: 三级行业代码列表
            
        返回:
            DataFrame: 所有成分股数据
        """
        if l3_codes is None:
            # 先获取所有三级行业代码
            l3_df = self.get_sw_l3_industry()
            l3_codes = l3_df['index_code'].tolist()
        
        all_members = []
        for l3_code in l3_codes:
            try:
                df = self.get_index_member_all(l3_code)
                if df is not None and not df.empty:
                    all_members.append(df)
            except Exception as e:
                print(f"获取行业 {l3_code} 成分股失败: {e}")
        
        if all_members:
            return pd.concat(all_members, ignore_index=True)
        return pd.DataFrame()


# 创建全局实例
_tushare_service = None

def get_tushare_service() -> TushareApiService:
    """获取Tushare服务实例"""
    global _tushare_service
    if _tushare_service is None:
        _tushare_service = TushareApiService()
    return _tushare_service
