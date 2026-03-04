"""
申万行业分类查询API服务
提供股票-申万行业关系查询功能
"""
import pandas as pd
from typing import List, Optional, Dict
from .database import query_df, execute_sql
from .sw_sync_service import get_industry_sync_service, get_member_sync_service


class SwIndustryQueryService:
    """申万行业分类查询服务"""
    
    @staticmethod
    def get_industry_tree(src: str = 'SW2021') -> List[Dict]:
        """
        获取申万行业树形结构
        
        参数:
            src: 申万版本
            
        Returns:
            List[Dict]: 树形结构
        """
        service = get_industry_sync_service(src)
        return service.get_industry_tree()
    
    @staticmethod
    def get_industry_list(level: Optional[int] = None, src: str = 'SW2021') -> pd.DataFrame:
        """
        获取申万行业列表
        
        参数:
            level: 层级 (1/2/3), None表示全部
            src: 申万版本
            
        Returns:
            DataFrame: 行业列表
        """
        if level is not None:
            sql = "SELECT * FROM sw_industry WHERE level = %s AND is_valid = 1 ORDER BY node_code"
            df = query_df(sql, {'level': level})
        else:
            sql = "SELECT * FROM sw_industry WHERE is_valid = 1 ORDER BY level, node_code"
            df = query_df(sql)
        
        return df
    
    @staticmethod
    def get_industry_by_code(node_code: str) -> Optional[Dict]:
        """
        根据代码获取行业信息
        
        参数:
            node_code: 行业代码
            
        Returns:
            Dict: 行业信息
        """
        sql = "SELECT * FROM sw_industry WHERE node_code = %s AND is_valid = 1"
        df = query_df(sql, {'node_code': node_code})
        
        if df is not None and not df.empty:
            return df.iloc[0].to_dict()
        return None
    
    @staticmethod
    def get_l1_industry(src: str = 'SW2021') -> pd.DataFrame:
        """获取一级行业列表"""
        return SwIndustryQueryService.get_industry_list(level=1, src=src)
    
    @staticmethod
    def get_l2_industry(src: str = 'SW2021') -> pd.DataFrame:
        """获取二级行业列表"""
        return SwIndustryQueryService.get_industry_list(level=2, src=src)
    
    @staticmethod
    def get_l3_industry(src: str = 'SW2021') -> pd.DataFrame:
        """获取三级行业列表"""
        return SwIndustryQueryService.get_industry_list(level=3, src=src)
    
    @staticmethod
    def search_industry(keyword: str) -> pd.DataFrame:
        """
        搜索行业
        
        参数:
            keyword: 关键词
            
        Returns:
            DataFrame: 匹配的行业列表
        """
        sql = """
            SELECT * FROM sw_industry 
            WHERE is_valid = 1 
            AND (node_name LIKE %s OR node_code LIKE %s OR l1_name LIKE %s OR l2_name LIKE %s OR l3_name LIKE %s)
            ORDER BY level, node_code
        """
        pattern = f"%{keyword}%"
        df = query_df(sql, {
            'pattern': pattern, 
            'pattern': pattern, 
            'pattern': pattern, 
            'pattern': pattern, 
            'pattern': pattern
        })
        return df


class SwStockQueryService:
    """股票-申万行业关系查询服务"""
    
    @staticmethod
    def get_stock_industry(ts_code: str) -> List[Dict]:
        """
        获取股票当前所属的申万行业

        参数:
            ts_code: 股票代码

        Returns:
            List[Dict]: 行业信息列表（可能有多条，比如同时属于多个三级行业）
        """
        sql = """
            SELECT
                r.ts_code,
                r.sw_node_code,
                r.in_date,
                r.out_date,
                r.is_latest,
                s.node_name as industry_name,
                s.level as industry_level,
                s.l1_code,
                s.l1_name,
                s.l2_code,
                s.l2_name,
                s.l3_code,
                s.l3_name
            FROM stock_sw_relation r
            JOIN sw_industry s ON r.sw_node_code = s.node_code
            WHERE r.ts_code = %s AND r.is_latest = 1
            ORDER BY s.level
        """
        df = query_df(sql, {'ts_code': ts_code})

        if df is not None and not df.empty:
            return df.to_dict('records')
        return []

    @staticmethod
    def get_stocks_industry_batch(ts_codes: List[str]) -> Dict[str, Dict]:
        """
        批量获取多个股票当前所属的申万行业（优化版）

        参数:
            ts_codes: 股票代码列表

        Returns:
            Dict: 键为股票代码，值为行业信息字典（取最新的一条）
        """
        if not ts_codes:
            return {}

        # 构建IN子句
        placeholders = ','.join([f"'{code}'" for code in ts_codes])

        sql = f"""
            SELECT
                r.ts_code,
                r.sw_node_code,
                r.in_date,
                r.out_date,
                r.is_latest,
                s.node_name as industry_name,
                s.level as industry_level,
                s.l1_code,
                s.l1_name,
                s.l2_code,
                s.l2_name,
                s.l3_code,
                s.l3_name
            FROM stock_sw_relation r
            JOIN sw_industry s ON r.sw_node_code = s.node_code
            WHERE r.ts_code IN ({placeholders}) AND r.is_latest = 1
            ORDER BY r.ts_code, s.level
        """

        df = query_df(sql)

        if df is None or df.empty:
            return {}

        # 转换为字典，每只股票只取一条（取最新的一条）
        result = {}
        for _, row in df.iterrows():
            ts_code = row['ts_code']
            if ts_code not in result:
                result[ts_code] = {
                    "l1_name": row.get('l1_name'),
                    "l2_name": row.get('l2_name'),
                    "l3_name": row.get('l3_name'),
                    "l1_code": row.get('l1_code'),
                    "l2_code": row.get('l2_code'),
                    "l3_code": row.get('l3_code')
                }

        return result
    
    @staticmethod
    def get_stock_industry_history(ts_code: str) -> pd.DataFrame:
        """
        获取股票所属行业历史变动
        
        参数:
            ts_code: 股票代码
            
        Returns:
            DataFrame: 历史关系列表
        """
        sql = """
            SELECT 
                r.ts_code,
                r.sw_node_code,
                r.in_date,
                r.out_date,
                r.is_latest,
                s.node_name as industry_name,
                s.level as industry_level,
                s.l1_code,
                s.l1_name,
                s.l2_code,
                s.l2_name,
                s.l3_code,
                s.l3_name
            FROM stock_sw_relation r
            JOIN sw_industry s ON r.sw_node_code = s.node_code
            WHERE r.ts_code = %s
            ORDER BY r.in_date DESC, s.level
        """
        return query_df(sql, {'ts_code': ts_code})
    
    @staticmethod
    def get_industry_stocks(node_code: str, level: Optional[int] = None, is_latest: bool = True) -> pd.DataFrame:
        """
        获取指定行业的成分股
        
        参数:
            node_code: 行业节点代码
            level: 行业层级，用于查询某层级的所有下级行业成分股
            is_latest: 是否只查询最新成分
            
        Returns:
            DataFrame: 成分股列表
        """
        # 如果指定了层级，需要先获取该层级下的所有行业代码
        if level is not None:
            if level == 1:
                # 一级行业：查询该一级行业下所有三级行业的成分股
                sql = """
                    SELECT DISTINCT r.*
                    FROM stock_sw_relation r
                    JOIN sw_industry s ON r.sw_node_code = s.node_code
                    WHERE s.l1_code = %s AND r.is_latest = 1
                    ORDER BY r.ts_code
                """
            elif level == 2:
                # 二级行业：查询该二级行业下所有三级行业的成分股
                sql = """
                    SELECT DISTINCT r.*
                    FROM stock_sw_relation r
                    JOIN sw_industry s ON r.sw_node_code = s.node_code
                    WHERE s.l2_code = %s AND r.is_latest = 1
                    ORDER BY r.ts_code
                """
            else:
                sql = """
                    SELECT r.*
                    FROM stock_sw_relation r
                    WHERE r.sw_node_code = %s AND r.is_latest = 1
                    ORDER BY r.ts_code
                """
            return query_df(sql, {'node_code': node_code})
        else:
            # 直接查询指定节点
            if is_latest:
                sql = """
                    SELECT r.*
                    FROM stock_sw_relation r
                    WHERE r.sw_node_code = %s AND r.is_latest = 1
                    ORDER BY r.ts_code
                """
            else:
                sql = """
                    SELECT r.*
                    FROM stock_sw_relation r
                    WHERE r.sw_node_code = %s
                    ORDER BY r.ts_code, r.in_date
                """
            return query_df(sql, {'node_code': node_code})
    
    @staticmethod
    def get_industry_stock_count(node_code: str, level: Optional[int] = None) -> int:
        """
        获取行业成分股数量
        
        参数:
            node_code: 行业节点代码
            level: 行业层级
            
        Returns:
            int: 成分股数量
        """
        df = SwStockQueryService.get_industry_stocks(node_code, level, is_latest=True)
        return len(df) if df is not None else 0
    
    @staticmethod
    def get_l1_industry_with_stocks(src: str = 'SW2021') -> pd.DataFrame:
        """
        获取一级行业及其成分股数量
        
        参数:
            src: 申万版本
            
        Returns:
            DataFrame: 一级行业列表及成分股数量
        """
        sql = """
            SELECT 
                s.node_code,
                s.node_name,
                COUNT(r.ts_code) as stock_count
            FROM sw_industry s
            LEFT JOIN stock_sw_relation r ON s.node_code = r.sw_node_code AND r.is_latest = 1
            WHERE s.level = 1 AND s.is_valid = 1
            GROUP BY s.node_code, s.node_name
            ORDER BY s.node_code
        """
        return query_df(sql)
    
    @staticmethod
    def get_l2_industry_with_stocks(l1_code: str = None, src: str = 'SW2021') -> pd.DataFrame:
        """
        获取二级行业及其成分股数量
        
        参数:
            l1_code: 一级行业代码，None表示全部
            src: 申万版本
            
        Returns:
            DataFrame: 二级行业列表及成分股数量
        """
        if l1_code:
            sql = """
                SELECT 
                    s.node_code,
                    s.node_name,
                    s.parent_code,
                    COUNT(r.ts_code) as stock_count
                FROM sw_industry s
                LEFT JOIN stock_sw_relation r ON s.node_code = r.sw_node_code AND r.is_latest = 1
                WHERE s.level = 2 AND s.is_valid = 1 AND s.l1_code = %s
                GROUP BY s.node_code, s.node_name, s.parent_code
                ORDER BY s.node_code
            """
            return query_df(sql, {'l1_code': l1_code})
        else:
            sql = """
                SELECT 
                    s.node_code,
                    s.node_name,
                    s.parent_code,
                    s.l1_code,
                    COUNT(r.ts_code) as stock_count
                FROM sw_industry s
                LEFT JOIN stock_sw_relation r ON s.node_code = r.sw_node_code AND r.is_latest = 1
                WHERE s.level = 2 AND s.is_valid = 1
                GROUP BY s.node_code, s.node_name, s.parent_code, s.l1_code
                ORDER BY s.node_code
            """
            return query_df(sql)
    
    @staticmethod
    def get_l3_industry_with_stocks(l2_code: str = None, src: str = 'SW2021') -> pd.DataFrame:
        """
        获取三级行业及其成分股数量
        
        参数:
            l2_code: 二级行业代码，None表示全部
            src: 申万版本
            
        Returns:
            DataFrame: 三级行业列表及成分股数量
        """
        if l2_code:
            sql = """
                SELECT 
                    s.node_code,
                    s.node_name,
                    s.parent_code,
                    COUNT(r.ts_code) as stock_count
                FROM sw_industry s
                LEFT JOIN stock_sw_relation r ON s.node_code = r.sw_node_code AND r.is_latest = 1
                WHERE s.level = 3 AND s.is_valid = 1 AND s.l2_code = %s
                GROUP BY s.node_code, s.node_name, s.parent_code
                ORDER BY s.node_code
            """
            return query_df(sql, {'l2_code': l2_code})
        else:
            sql = """
                SELECT 
                    s.node_code,
                    s.node_name,
                    s.parent_code,
                    s.l1_code,
                    s.l1_name,
                    s.l2_code,
                    s.l2_name,
                    COUNT(r.ts_code) as stock_count
                FROM sw_industry s
                LEFT JOIN stock_sw_relation r ON s.node_code = r.sw_node_code AND r.is_latest = 1
                WHERE s.level = 3 AND s.is_valid = 1
                GROUP BY s.node_code, s.node_name, s.parent_code, s.l1_code, s.l1_name, s.l2_code, s.l2_name
                ORDER BY s.node_code
            """
            return query_df(sql)


# 创建全局查询服务实例
_industry_query_service = None
_stock_query_service = None


def get_industry_query_service() -> SwIndustryQueryService:
    """获取行业查询服务实例"""
    global _industry_query_service
    if _industry_query_service is None:
        _industry_query_service = SwIndustryQueryService()
    return _industry_query_service


def get_stock_query_service() -> SwStockQueryService:
    """获取股票查询服务实例"""
    global _stock_query_service
    if _stock_query_service is None:
        _stock_query_service = SwStockQueryService()
    return _stock_query_service
