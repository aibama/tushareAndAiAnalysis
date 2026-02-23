-- ETF数据库表结构
-- 注意：表结构由SQLAlchemy ORM自动生成

-- ETF日线行情表
CREATE TABLE IF NOT EXISTS `etf_daily_info` (
    `id` VARCHAR(36) NOT NULL,
    `ts_code` VARCHAR(20) NOT NULL COMMENT 'ETF代码',
    `trade_date` VARCHAR(8) NOT NULL COMMENT '交易日期',
    `open` FLOAT COMMENT '开盘价',
    `high` FLOAT COMMENT '最高价',
    `low` FLOAT COMMENT '最低价',
    `close` FLOAT COMMENT '收盘价',
    `pre_close` FLOAT COMMENT '前收盘价',
    `change` FLOAT COMMENT '涨跌额',
    `pct_chg` FLOAT COMMENT '涨跌幅',
    `vol` FLOAT COMMENT '成交量',
    `amount` FLOAT COMMENT '成交额',
    `last_update_time` DATETIME COMMENT '最后更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_etf_daily` (`ts_code`, `trade_date`),
    INDEX `idx_ts_code` (`ts_code`),
    INDEX `idx_trade_date` (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ETF日线行情';

-- ETF份额规模表
CREATE TABLE IF NOT EXISTS `etf_share_size_info` (
    `id` VARCHAR(36) NOT NULL,
    `ts_code` VARCHAR(20) NOT NULL COMMENT 'ETF代码',
    `trade_date` VARCHAR(8) NOT NULL COMMENT '交易日期',
    `etf_name` VARCHAR(100) COMMENT 'ETF名称',
    `total_share` FLOAT COMMENT '总份额',
    `total_size` FLOAT COMMENT '总规模',
    `exchange` VARCHAR(10) COMMENT '交易所',
    `last_update_time` DATETIME COMMENT '最后更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_etf_share` (`ts_code`, `trade_date`),
    INDEX `idx_ts_code` (`ts_code`),
    INDEX `idx_trade_date` (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ETF份额规模';

-- 基金复权因子表
CREATE TABLE IF NOT EXISTS `fund_adj_info` (
    `id` VARCHAR(36) NOT NULL,
    `ts_code` VARCHAR(20) NOT NULL COMMENT '基金代码',
    `trade_date` VARCHAR(8) NOT NULL COMMENT '交易日期',
    `adj_factor` FLOAT COMMENT '复权因子',
    `last_update_time` DATETIME COMMENT '最后更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_fund_adj` (`ts_code`, `trade_date`),
    INDEX `idx_ts_code` (`ts_code`),
    INDEX `idx_trade_date` (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='基金复权因子';

-- ETF基金基本信息表
CREATE TABLE IF NOT EXISTS `fund_etf_info` (
    `ts_code` VARCHAR(20) NOT NULL COMMENT '基金交易代码',
    `csname` VARCHAR(50) NOT NULL COMMENT 'ETF中文简称',
    `extname` VARCHAR(100) DEFAULT NULL COMMENT 'ETF扩位简称(对应交易所简称)',
    `cname` VARCHAR(200) NOT NULL COMMENT '基金中文全称',
    `index_code` VARCHAR(20) DEFAULT NULL COMMENT 'ETF基准指数代码',
    `index_name` VARCHAR(200) DEFAULT NULL COMMENT 'ETF基准指数中文全称',
    `setup_date` DATE DEFAULT NULL COMMENT '设立日期(格式:YYYYMMDD)',
    `list_date` DATE DEFAULT NULL COMMENT '上市日期(格式:YYYYMMDD)',
    `list_status` CHAR(1) DEFAULT NULL COMMENT '存续状态(L上市 D退市 P待上市)',
    `exchange` VARCHAR(10) DEFAULT NULL COMMENT '交易所(上交所SH 深交所SZ)',
    `mgr_name` VARCHAR(100) DEFAULT NULL COMMENT '基金管理人简称',
    `custod_name` VARCHAR(200) DEFAULT NULL COMMENT '基金托管人名称',
    `mgt_fee` DECIMAL(5,4) DEFAULT NULL COMMENT '基金管理人收取的费用',
    `etf_type` VARCHAR(20) DEFAULT NULL COMMENT '基金投资通道类型(境内、QDII)',
    PRIMARY KEY (`ts_code`),
    KEY `idx_list_status` (`list_status`),
    KEY `idx_exchange` (`exchange`),
    KEY `idx_list_date` (`list_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ETF基金基本信息表';
