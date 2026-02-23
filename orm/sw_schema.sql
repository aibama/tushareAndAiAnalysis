-- 申万行业分类标准数据表结构定义
-- 数据库: stockdata

-- 申万行业分类标准树
CREATE TABLE IF NOT EXISTS `sw_industry` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT COMMENT '代理主键',
  `node_code` varchar(20) NOT NULL COMMENT '节点唯一编码（如: 801020.SI）',
  `node_name` varchar(100) NOT NULL COMMENT '节点名称',
  `level` tinyint NOT NULL COMMENT '层级: 1-一级行业, 2-二级行业, 3-三级行业',
  `parent_code` varchar(20) DEFAULT NULL COMMENT '父节点编码（一级行业的父节点为NULL）',
  `full_path` varchar(200) DEFAULT NULL COMMENT '层级路径（推导字段，便于查询）',
  `l1_code` varchar(10) DEFAULT NULL COMMENT '一级行业代码（冗余，便于筛选）',
  `l1_name` varchar(50) DEFAULT NULL COMMENT '一级行业名称',
  `l2_code` varchar(10) DEFAULT NULL COMMENT '二级行业代码',
  `l2_name` varchar(50) DEFAULT NULL COMMENT '二级行业名称',
  `l3_code` varchar(10) DEFAULT NULL COMMENT '三级行业代码',
  `l3_name` varchar(50) DEFAULT NULL COMMENT '三级行业名称',
  `is_valid` tinyint DEFAULT '1' COMMENT '是否有效（分类可能被修订）',
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_node_code` (`node_code`),
  KEY `idx_level` (`level`),
  KEY `idx_parent` (`parent_code`),
  KEY `idx_l1` (`l1_code`),
  KEY `idx_l3` (`l3_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='申万行业分类标准树';

-- 股票-申万行业成分历史关系表
CREATE TABLE IF NOT EXISTS `stock_sw_relation` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `ts_code` varchar(20) NOT NULL COMMENT '股票代码',
  `sw_node_code` varchar(20) NOT NULL COMMENT '申万行业节点编码（关联sw_industry.node_code）',
  `in_date` date NOT NULL COMMENT '纳入日期',
  `out_date` date DEFAULT NULL COMMENT '剔除日期（NULL表示当前仍在成分内）',
  `is_latest` tinyint DEFAULT '0' COMMENT '是否最新成分关系（1是，0否）',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_stock_node_date` (`ts_code`, `sw_node_code`, `in_date`),
  KEY `idx_ts_code_latest` (`ts_code`, `is_latest`),
  KEY `idx_node_latest` (`sw_node_code`, `is_latest`),
  KEY `idx_in_date` (`in_date`),
  KEY `idx_out_date` (`out_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票-申万行业成分历史关系表';

-- 创建视图：股票当前所属申万行业（方便查询）
CREATE OR REPLACE VIEW `v_stock_sw_current` AS
SELECT 
    r.ts_code,
    s.node_code as sw_code,
    s.node_name as sw_name,
    s.level as sw_level,
    s.l1_code,
    s.l1_name,
    s.l2_code,
    s.l2_name,
    s.l3_code,
    s.l3_name,
    r.in_date,
    r.out_date
FROM stock_sw_relation r
JOIN sw_industry s ON r.sw_node_code = s.node_code
WHERE r.is_latest = 1;

-- 创建视图：申万行业当前成分股（方便查询）
CREATE OR REPLACE VIEW `v_sw_industry_stocks` AS
SELECT 
    s.node_code as sw_code,
    s.node_name as sw_name,
    s.level as sw_level,
    r.ts_code,
    r.in_date,
    r.out_date
FROM stock_sw_relation r
JOIN sw_industry s ON r.sw_node_code = s.node_code
WHERE r.is_latest = 1;
