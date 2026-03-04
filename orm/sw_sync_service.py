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
    
    def fix_industry_links(self) -> dict:
        """
        修复行业关联关系
        用于修复因parent_code映射错误导致的l1_code/l1_name不正确的问题
        
        返回:
            dict: 修复结果统计
        """
        result = {
            'l2_fixed': 0,
            'l3_fixed': 0,
            'errors': []
        }
        
        # 获取一级行业映射
        l1_mapping = self._build_l1_mapping()
        
        # 构建内部编码前缀到l1_code/l1_name的映射
        # 例如: 110000 -> (801010.SI, 农林牧渔), 110100 -> (801010.SI, 农林牧渔)
        internal_to_l1 = {}
        for parent_code, (l1_code, l1_name) in l1_mapping.items():
            # 获取parent_code的前3位作为一级行业前缀
            if len(parent_code) >= 3:
                prefix = parent_code[:3]
                internal_to_l1[prefix] = (l1_code, l1_name)
        
        try:
            # 修复二级行业
            for parent_code, (l1_code, l1_name) in l1_mapping.items():
                sql = """
                    UPDATE sw_industry 
                    SET l1_code = %s, l1_name = %s 
                    WHERE level = 2 AND parent_code = %s
                """
                cursor = execute_sql(sql, (l1_code, l1_name, parent_code))
                if cursor:
                    result['l2_fixed'] += cursor.rowcount if hasattr(cursor, 'rowcount') else 0
            
            # 修复三级行业 - 使用前缀匹配
            for internal_prefix, (l1_code, l1_name) in internal_to_l1.items():
                # 查找所有parent_code以前缀开头的三级行业
                sql = """
                    UPDATE sw_industry 
                    SET l1_code = %s, l1_name = %s
                    WHERE level = 3 AND parent_code LIKE %s AND (l1_code != %s OR l1_name = '' OR l1_name IS NULL)
                """
                cursor = execute_sql(sql, (l1_code, l1_name, f"{internal_prefix}%", l1_code))
                if cursor:
                    result['l3_fixed'] += cursor.rowcount if hasattr(cursor, 'rowcount') else 0
            
            # 第二步：修复l2_code和l2_name
            # 构建l2的内部编码到l2_code/l2_name的映射
            sql = "SELECT node_code, l2_code, l2_name FROM sw_industry WHERE level = 2"
            df = query_df(sql)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    node_code = row['node_code']
                    l2_code = row['l2_code']
                    l2_name = row['l2_name']
                    if node_code and l2_code:
                        # 查找parent_code匹配的三级行业并更新l2信息
                        sql = """
                            UPDATE sw_industry 
                            SET l2_code = %s, l2_name = %s
                            WHERE level = 3 AND parent_code = %s
                        """
                        # 这里需要用parent_code来匹配，但我们需要知道每个l3的parent_code对应的l2 node_code
                        pass
                        
        except Exception as e:
            result['errors'].append(str(e))
            print(f"修复行业关联失败: {e}")
        
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
    
    def _build_l1_mapping(self) -> dict:
        """
        构建一级行业映射表
        用于将Tushare返回的内部parent_code映射到实际的l1_code和l1_name
        
        返回:
            dict: {parent_code: (l1_code, l1_name)}
        """
        # 直接使用预设的映射表
        # 这些是通过分析Tushare返回数据得出的parent_code到l1_code的映射
        # parent_code是Tushare API返回的内部编码，l1_code是对应的一级行业node_code
        mapping = {
            # 主要一级行业
            '110000': ('801010.SI', '农林牧渔'),
            '220000': ('801030.SI', '基础化工'),
            '230000': ('801040.SI', '钢铁'),
            '240000': ('801050.SI', '有色金属'),
            '270000': ('801080.SI', '电子'),
            '280000': ('801880.SI', '汽车'),
            '330000': ('801110.SI', '家用电器'),
            '340000': ('801120.SI', '食品饮料'),
            '350000': ('801130.SI', '纺织服饰'),
            '360000': ('801140.SI', '轻工制造'),
            '370000': ('801150.SI', '医药生物'),
            '410000': ('801160.SI', '公用事业'),
            '420000': ('801170.SI', '交通运输'),
            '430000': ('801180.SI', '房地产'),
            '450000': ('801200.SI', '商贸零售'),
            '460000': ('801210.SI', '社会服务'),
            '480000': ('801780.SI', '银行'),
            '490000': ('801790.SI', '非银金融'),
            '510000': ('801230.SI', '综合'),
            '610000': ('801710.SI', '建筑材料'),
            '620000': ('801720.SI', '建筑装饰'),
            '630000': ('801730.SI', '电力设备'),
            '640000': ('801890.SI', '机械设备'),
            '650000': ('801740.SI', '国防军工'),
            '710000': ('801750.SI', '计算机'),
            '720000': ('801760.SI', '传媒'),
            '730000': ('801770.SI', '通信'),
            '740000': ('801950.SI', '煤炭'),
            '750000': ('801960.SI', '石油石化'),
            '760000': ('801970.SI', '环保'),
            '770000': ('801980.SI', '美容护理'),
            
            # 交通运输的子分类
            '421000': ('801170.SI', '交通运输'),
            '421100': ('801170.SI', '交通运输'),
            
            # 社会服务的子分类
            '461000': ('801210.SI', '社会服务'),
            '461100': ('801210.SI', '社会服务'),
            
            # 传媒的子分类
            '721000': ('801760.SI', '传媒'),
        }
        
        return mapping
    
    def _sync_l2_industry(self, df: pd.DataFrame) -> int:
        """同步二级行业数据"""
        count = 0
        errors = 0
        
        # 构建一级行业映射: parent_code -> (l1_code, l1_name)
        # Tushare返回的parent_code是内部编码(如110000)，需要映射到实际的node_code(如801010.SI)
        l1_mapping = self._build_l1_mapping()
        
        for _, row in df.iterrows():
            try:
                node_code = row['index_code']
                node_name = row['industry_name']
                parent_code = row.get('parent_code') or row.get('src_code')
                
                # 使用一级行业映射获取父节点信息
                if parent_code in l1_mapping:
                    l1_code, l1_name = l1_mapping[parent_code]
                else:
                    # 备用方案：尝试直接查找
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
