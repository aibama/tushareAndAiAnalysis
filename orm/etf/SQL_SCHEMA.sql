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
