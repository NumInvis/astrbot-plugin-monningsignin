"""
数据库管理模块
负责数据库初始化和表创建
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import aiosqlite
from astrbot.api import logger


class DatabaseManager:
    """数据库管理类"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def init_database(self):
        """初始化数据库，创建所有必需的表"""
        async with aiosqlite.connect(self.db_path) as db:
            # 用户表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    balance INTEGER DEFAULT 0,
                    bank_balance INTEGER DEFAULT 0,
                    last_signin_date TEXT,
                    consecutive_days INTEGER DEFAULT 0,
                    bank_last_date TEXT,
                    favor_value INTEGER DEFAULT 0
                )
            """)
            
            # 背包表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    quantity INTEGER DEFAULT 0,
                    UNIQUE(user_id, item_name)
                )
            """)
            
            # 购买记录表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS purchase_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    purchase_date TEXT NOT NULL,
                    count INTEGER DEFAULT 0,
                    UNIQUE(user_id, item_name, purchase_date)
                )
            """)
            
            # 占卜记录表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS lottery_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    count INTEGER DEFAULT 0,
                    UNIQUE(user_id, date)
                )
            """)
            
            # 股票表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS stock_prices (
                    stock_name TEXT PRIMARY KEY,
                    current_price REAL DEFAULT 0,
                    previous_price REAL DEFAULT 0,
                    base_price REAL DEFAULT 0,
                    total_shares INTEGER DEFAULT 0,
                    circulating_shares INTEGER DEFAULT 0,
                    emoji TEXT,
                    desc TEXT,
                    owner_id TEXT,
                    delisted INTEGER DEFAULT 0,
                    last_update TEXT
                )
            """)
            
            # 股票持仓表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS stock_holdings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    stock_name TEXT NOT NULL,
                    quantity REAL DEFAULT 0,
                    buy_price REAL DEFAULT 0,
                    buy_time TEXT,
                    remaining REAL DEFAULT 0,
                    last_dividend_date TEXT,
                    UNIQUE(user_id, stock_name)
                )
            """)
            
            # 结社表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_society (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL UNIQUE,
                    society_name TEXT,
                    join_time TEXT,
                    last_change_time TEXT
                )
            """)
            
            # 工作表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL UNIQUE,
                    job_name TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    last_salary_date TEXT
                )
            """)
            
            # 塔罗牌表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_daily_tarot (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    card_name TEXT NOT NULL,
                    effect_type TEXT,
                    effect_value INTEGER DEFAULT 0,
                    UNIQUE(user_id, date)
                )
            """)

            # 用户工作表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_work (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL UNIQUE,
                    work_name TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    last_claim_time TEXT NOT NULL,
                    total_earned INTEGER DEFAULT 0
                )
            """)

            # 用户关系描述表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_relationship (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL UNIQUE,
                    relationship_desc TEXT,
                    update_time TEXT,
                    next_update_time TEXT
                )
            """)

            # 用户信息表（用于存储昵称等）
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL UNIQUE,
                    nickname TEXT
                )
            """)

            # 股票价格历史表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS stock_price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_name TEXT,
                    price REAL,
                    timestamp TEXT,
                    FOREIGN KEY (stock_name) REFERENCES stock_prices(stock_name)
                )
            """)

            # 股票交易记录表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS stock_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    stock_name TEXT NOT NULL,
                    transaction_type TEXT NOT NULL,
                    quantity REAL DEFAULT 0,
                    price REAL DEFAULT 0,
                    sell_price REAL DEFAULT 0,
                    sell_time TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 税收池表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tax_pool (
                    date TEXT PRIMARY KEY,
                    total_tax INTEGER DEFAULT 0,
                    bonus_pool INTEGER DEFAULT 0,
                    bonus_claimed INTEGER DEFAULT 0,
                    top10_list TEXT,
                    median_wealth INTEGER DEFAULT 0,
                    player_count INTEGER DEFAULT 0,
                    details TEXT
                )
            """)

            # 用户税收记录表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_tax_record (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    base_tax INTEGER DEFAULT 0,
                    extra_tax INTEGER DEFAULT 0,
                    total_tax INTEGER DEFAULT 0,
                    wealth_before INTEGER DEFAULT 0,
                    UNIQUE(user_id, date)
                )
            """)

            await db.commit()
            logger.info("【数据库】基础表初始化完成")
