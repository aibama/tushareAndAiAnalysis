"""
申万行业分类数据同步服务
负责从Tushare获取数据并持久化到数据库
"""
import pandas as pd
from typing import List, Optional
from datetime import datetime
from .tushare_api import get_tushare_service
from .database import get_engine, execute_sql, query_df
from sqlalchemy import text
import warnings
warnings.filterwarnings('ignore')


class SwIndustrySyncService:
    """申万行业分类数据同步服务"""
    
    def __init__(self, src: str = 'SW2021'):
        """
        初始化同步服务
        
        参数:
            src: 申万版本, SW2014 或 SW2021
        """
        self.src = src
        self.tushare = get_tushare_service()
        self.engine = get_engine()
    
    def sync_all_industry(self) -> dict:
        """
        同步所有申万行业分类数据
        
        返回:
            dict: 同步结果统计
        """
        result = {
            'l1_count': 0,
            'l2_count': 0,
            'l3_count': 0,
            'total_count': 0,
            'errors': []
        }
        
        try:
            # 获取一级行业
            l1_df = self.tushare.get_sw_l1_industry(self.src)
            if l1_df is not None and not l1_df.empty:
                l1_count = self._sync_l1_industry(l1_df)
                result['l1_count'] = l1_count
            
            # 获取二级行业
            l2_df = self.tushare.get_sw_l2_industry(self.src)
            if l2_df is not None and not l2_df.empty:
                l2_count = self._sync_l2_industry(l2_df)
                result['l2_count'] = l2_count
            
            # 获取三级行业
            l3_df = self.tushare.get_sw_l3_industry(self.src)
            if l3_df is not None and not l3_df.empty:
                l3_count = self._sync_l3_industry(l3_df)
                result['l3_count'] = l3_count
            
            result['total_count'] = result['l1_count'] + result['l2_count'] + result['l3_count']
            
        except Exception as e:
            result['errors'].append(str(e))
            print(f"同步行业分类失败: {e}")
        
        return result
    
    def _sync_l1_industry(self, df: pd.DataFrame) -> int:
        """同步一级行业数据"""
        count = 0
        errors = 0
        for _, row in df.iterrows():
            try:
                node_code = row['index_code']
                node_name = row['industry_name']
                
                # 构建SQL - 使用ON DUPLICATE KEY UPDATE防止重复
                sql = """
                    INSERT INTO sw_industry 
                    (node_code, node_name, level, l1_code, l1_name, is_valid)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        node_name = VALUES(node_name),
                        l1_name = VALUES(l1_name),
                        update_time = NOW()
                """
                execute_sql(sql, (node_code, node_name, 1, node_code, node_name, 1))
                count += 1
            except Exception as e:
                errors += 1
                if errors <= 5:  # 只打印前5个错误
                    print(f"同步一级行业 {row.get('index_code')} 失败: {e}")
        
        if errors > 5:
            print(f"... 共 {errors} 个错误")
        return count
    
    def _sync_l2_industry(self, df: pd.DataFrame) -> int:
        """同步二级行业数据"""
        count = 0
        errors = 0
        for _, row in df.iterrows():
            try:
                node_code = row['index_code']
                node_name = row['industry_name']
                parent_code = row.get('parent_code') or row.get('src_code')
                
                # 获取父节点（一级行业）信息
                parent_info = self._get_industry_by_code(parent_code)
                l1_code = parent_info['l1_code'] if parent_info else parent_code
                l1_name = parent_info['l1_name'] if parent_info else ''
                
                # 构建SQL - 使用ON DUPLICATE KEY UPDATE防止重复
                sql = """
                    INSERT INTO sw_industry 
                    (node_code, node_name, level, parent_code, l1_code, l1_name, l2_code, l2_name, is_valid)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        node_name = VALUES(node_name),
                        parent_code = VALUES(parent_code),
                        l2_name = VALUES(l2_name),
                        update_time = NOW()
                """
                execute_sql(sql, (node_code, node_name, 2, parent_code, l1_code, l1_name, node_code, node_name, 1))
                count += 1
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"同步二级行业 {row.get('index_code')} 失败: {e}")
        
        if errors > 5:
            print(f"... 共 {errors} 个错误")
        return count
    
    def _sync_l3_industry(self, df: pd.DataFrame) -> int:
        """同步三级行业数据"""
        count = 0
        errors = 0
        for _, row in df.iterrows():
            try:
                node_code = row['index_code']
                node_name = row['industry_name']
                parent_code = row.get('parent_code') or row.get('src_code')
                
                # 获取父节点（二级行业）信息
                parent_info = self._get_industry_by_code(parent_code)
                if parent_info:
                    l1_code = parent_info['l1_code']
                    l1_name = parent_info['l1_name']
                    l2_code = parent_info['l2_code']
                    l2_name = parent_info['l2_name']
                else:
                    l1_code = ''
                    l1_name = ''
                    l2_code = parent_code
                    l2_name = ''
                
                # 构建SQL (注意: full_path是MySQL生成列，不能在INSERT中指定)
                # 使用ON DUPLICATE KEY UPDATE防止重复
                sql = """
                    INSERT INTO sw_industry 
                    (node_code, node_name, level, parent_code, 
                     l1_code, l1_name, l2_code, l2_name, l3_code, l3_name, is_valid)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        node_name = VALUES(node_name),
                        parent_code = VALUES(parent_code),
                        l3_name = VALUES(l3_name),
                        update_time = NOW()
                """
                execute_sql(sql, (node_code, node_name, 3, parent_code,
                                  l1_code, l1_name, l2_code, l2_name, node_code, node_name, 1))
                count += 1
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"同步三级行业 {row.get('index_code')} 失败: {e}")
        
        if errors > 5:
            print(f"... 共 {errors} 个错误")
        return count
    
    def _get_industry_by_code(self, code: str) -> Optional[dict]:
        """根据代码获取行业信息"""
        if not code:
            return None
        sql = "SELECT l1_code, l1_name, l2_code, l2_name FROM sw_industry WHERE node_code = %s"
        df = query_df(sql, {'code': code})
        if df is not None and not df.empty:
            return df.iloc[0].to_dict()
        return None
    
    def get_industry_by_level(self, level: int) -> pd.DataFrame:
        """
        根据层级获取行业列表
        
        参数:
            level: 层级 (1/2/3)
            
        返回:
            DataFrame: 行业列表
        """
        sql = "SELECT * FROM sw_industry WHERE level = %s AND is_valid = 1 ORDER BY node_code"
        return query_df(sql, {'level': level})
    
    def get_industry_tree(self) -> List[dict]:
        """
        获取行业树形结构
        
        返回:
            List[dict]: 树形结构的行业数据
        """
        # 获取所有有效行业
        sql = "SELECT * FROM sw_industry WHERE is_valid = 1 ORDER BY level, node_code"
        df = query_df(sql)
        
        if df is None or df.empty:
            return []
        
        # 构建树形结构
        l1_list = df[df['level'] == 1].to_dict('records')
        l2_list = df[df['level'] == 2].to_dict('records')
        l3_list = df[df['level'] == 3].to_dict('records')
        
        # 构建二级到三级的映射
        l2_l3_map = {}
        for l3 in l3_list:
            parent = l3.get('parent_code')
            if parent not in l2_l3_map:
                l2_l3_map[parent] = []
            l2_l3_map[parent].append(l3)
        
        # 构建一级到二级的映射
        l1_l2_map = {}
        for l2 in l2_list:
            parent = l2.get('parent_code')
            if parent not in l1_l2_map:
                l1_l2_map[parent] = []
            l2['children'] = l2_l3_map.get(l2['node_code'], [])
            l1_l2_map[parent].append(l2)
        
        # 构建最终树形结构
        tree = []
        for l1 in l1_list:
            l1['children'] = l1_l2_map.get(l1['node_code'], [])
            tree.append(l1)
        
        return tree


class SwMemberSyncService:
    """申万行业成分股同步服务"""
    
    def __init__(self, src: str = 'SW2021'):
        """
        初始化同步服务
        
        参数:
            src: 申万版本, SW2014 或 SW2021
        """
        self.src = src
        self.tushare = get_tushare_service()
        self.engine = get_engine()
    
    def sync_all_members(self) -> dict:
        """
        同步所有三级行业的成分股
        
        返回:
            dict: 同步结果统计
        """
        result = {
            'industry_count': 0,
            'stock_count': 0,
            'errors': []
        }
        
        try:
            # 先获取所有三级行业
            industry_service = SwIndustrySyncService(self.src)
            l3_df = industry_service.get_industry_by_level(3)
            
            if l3_df is None or l3_df.empty:
                result['errors'].append('未找到三级行业数据')
                return result
            
            l3_codes = l3_df['node_code'].tolist()
            result['industry_count'] = len(l3_codes)
            
            # 获取每个三级行业的成分股
            for l3_code in l3_codes:
                try:
                    count = self.sync_l3_members(l3_code)
                    result['stock_count'] += count
                except Exception as e:
                    result['errors'].append(f"同步 {l3_code} 失败: {str(e)}")
            
        except Exception as e:
            result['errors'].append(str(e))
            print(f"同步成分股失败: {e}")
        
        return result
    
    def sync_l3_members(self, l3_code: str) -> int:
        """
        同步指定三级行业的成分股
        
        参数:
            l3_code: 三级行业代码
            
        返回:
            int: 同步的股票数量
        """
        # 从Tushare获取成分股数据
        df = self.tushare.get_index_member_all(l3_code)
        
        if df is None or df.empty:
            return 0
        
        count = 0
        # 获取当前行业下的现有关系
        existing_relations = self._get_existing_relations(l3_code)
        
        for _, row in df.iterrows():
            try:
                ts_code = row['ts_code']
                in_date_str = str(row.get('in_date', ''))
                
                # 解析日期
                in_date = None
                if in_date_str and in_date_str.isdigit():
                    try:
                        in_date = datetime.strptime(in_date_str, '%Y%m%d').date()
                    except:
                        pass
                
                if in_date is None:
                    in_date = datetime.now().date()
                
                # 检查是否已存在
                key = f"{ts_code}_{l3_code}_{in_date}"
                if key in existing_relations:
                    continue
                
                # 获取行业节点代码
                sw_node_code = l3_code
                
                # 插入新关系
                sql = """
                    INSERT INTO stock_sw_relation 
                    (ts_code, sw_node_code, in_date, is_latest, create_time)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE
                        in_date = VALUES(in_date),
                        is_latest = 1
                """
                execute_sql(sql, (ts_code, sw_node_code, in_date, 1))
                count += 1
                
            except Exception as e:
                print(f"同步成分股 {row.get('ts_code')} 失败: {e}")
        
        # 更新该行业下所有股票的最新状态
        self._update_latest_status(l3_code)
        
        return count
    
    def _get_existing_relations(self, l3_code: str) -> set:
        """获取现有的成分股关系"""
        sql = """
            SELECT CONCAT(ts_code, '_', sw_node_code, '_', in_date) as rel_key 
            FROM stock_sw_relation 
            WHERE sw_node_code = %s
        """
        df = query_df(sql, {'l3_code': l3_code})
        if df is not None and not df.empty:
            return set(df['rel_key'].tolist())
        return set()
    
    def _update_latest_status(self, l3_code: str):
        """更新指定行业的最新成分股状态"""
        # 先将所有的is_latest设为0
        sql1 = "UPDATE stock_sw_relation SET is_latest = 0 WHERE sw_node_code = %s"
        execute_sql(sql1, (l3_code,))
        
        # 再将每个股票最新入会的记录设为1
        sql2 = """
            UPDATE stock_sw_relation r
            INNER JOIN (
                SELECT ts_code, MAX(in_date) as max_in_date
                FROM stock_sw_relation
                WHERE sw_node_code = %s AND (out_date IS NULL OR out_date >= CURDATE())
                GROUP BY ts_code
            ) latest ON r.ts_code = latest.ts_code AND r.in_date = latest.max_in_date
            SET r.is_latest = 1
            WHERE r.sw_node_code = %s
        """
        execute_sql(sql2, (l3_code, l3_code))
    
    def get_stock_industry(self, ts_code: str) -> pd.DataFrame:
        """
        获取股票当前所属的申万行业
        
        参数:
            ts_code: 股票代码
            
        返回:
            DataFrame: 行业信息
        """
        sql = """
            SELECT r.*, s.node_name as industry_name, s.level as industry_level,
                   s.l1_code, s.l1_name, s.l2_code, s.l2_name, s.l3_code, s.l3_name
            FROM stock_sw_relation r
            JOIN sw_industry s ON r.sw_node_code = s.node_code
            WHERE r.ts_code = %s AND r.is_latest = 1
        """
        return query_df(sql, {'ts_code': ts_code})
    
    def get_industry_stocks(self, node_code: str, is_latest: bool = True) -> pd.DataFrame:
        """
        获取指定行业的成分股
        
        参数:
            node_code: 行业节点代码
            is_latest: 是否只查询最新成分
            
        返回:
            DataFrame: 成分股列表
        """
        if is_latest:
            sql = """
                SELECT r.*, s.name as stock_name
                FROM stock_sw_relation r
                LEFT JOIN (
                    SELECT ts_code, name FROM stock_basics 
                    UNION ALL 
                    SELECT ts_code, name FROM stock_company
                ) s ON r.ts_code = s.ts_code
                WHERE r.sw_node_code = %s AND r.is_latest = 1
                ORDER BY r.in_date
            """
        else:
            sql = """
                SELECT r.*, s.name as stock_name
                FROM stock_sw_relation r
                LEFT JOIN (
                    SELECT ts_code, name FROM stock_basics 
                    UNION ALL 
                    SELECT ts_code, name FROM stock_company
                ) s ON r.ts_code = s.ts_code
                WHERE r.sw_node_code = %s
                ORDER BY r.in_date
            """
        return query_df(sql, {'node_code': node_code})


# 创建全局同步服务实例
_industry_sync_service = None
_member_sync_service = None


def get_industry_sync_service(src: str = 'SW2021') -> SwIndustrySyncService:
    """获取行业同步服务实例"""
    global _industry_sync_service
    if _industry_sync_service is None or _industry_sync_service.src != src:
        _industry_sync_service = SwIndustrySyncService(src)
    return _industry_sync_service


def get_member_sync_service(src: str = 'SW2021') -> SwMemberSyncService:
    """获取成分股同步服务实例"""
    global _member_sync_service
    if _member_sync_service is None or _member_sync_service.src != src:
        _member_sync_service = SwMemberSyncService(src)
    return _member_sync_service
