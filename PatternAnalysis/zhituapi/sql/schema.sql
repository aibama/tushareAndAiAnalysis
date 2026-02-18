-- 股票基本信息表
CREATE TABLE IF NOT EXISTS stockinfobase (
    ts_code VARCHAR(50) NOT NULL COMMENT '股票代码',
    symbol VARCHAR(50) COMMENT '股票符号',
    name VARCHAR(100) COMMENT '股票名称',
    area VARCHAR(50) COMMENT '地区',
    industry VARCHAR(100) COMMENT '行业',
    list_date VARCHAR(20) COMMENT '上市日期',
    composition VARCHAR(255) COMMENT '成分股信息',
    factory_code VARCHAR(20) COMMENT '交易所,股票对应的交易所',
    line_code VARCHAR(20) COMMENT '股票对应的,代码风险板块，KC科创,SH上海，SZ深圳,CY创业',
    last_update_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    PRIMARY KEY (ts_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票基本信息表';

-- 股票交易信息表
CREATE TABLE IF NOT EXISTS stock_trade_info (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增主键ID，用于内部关联',
    market_code VARCHAR(10) NOT NULL COMMENT '市场代码，例如: SH（上交所）、SZ（深交所）、BJ（北交所）',
    stock_symbol VARCHAR(20) NOT NULL COMMENT '股票交易代码,用于交易的，如000001',
    stock_code VARCHAR(20) NOT NULL COMMENT '股票程序代码,用于程序数据交换的，如000001.SZ',
    stock_name VARCHAR(100) NOT NULL COMMENT '股票简称',
    listing_date DATE DEFAULT NULL COMMENT '上市日期',
    prev_close_price DECIMAL(10,2) NOT NULL DEFAULT '0.00' COMMENT '前收盘价',
    up_limit_price DECIMAL(10,2) DEFAULT NULL COMMENT '当日涨停价',
    down_limit_price DECIMAL(10,2) DEFAULT NULL COMMENT '当日跌停价',
    float_shares BIGINT DEFAULT '0' COMMENT '流通股本（单位：股）',
    total_shares BIGINT DEFAULT '0' COMMENT '总股本（单位：股）',
    price_tick DECIMAL(5,2) DEFAULT '0.01' COMMENT '最小价格变动单位',
    is_suspended TINYINT NOT NULL DEFAULT '0' COMMENT '是否停牌: 0-正常交易，1-停牌',
    status TINYINT NOT NULL DEFAULT '1' COMMENT '记录状态: 0-无效/退市，1-有效',
    data_source VARCHAR(50) DEFAULT NULL COMMENT '数据来源标识',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录最后更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_market_symbol (market_code, stock_symbol),
    KEY idx_symbol (stock_symbol),
    KEY idx_name (stock_name),
    KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='股票基础信息表';
