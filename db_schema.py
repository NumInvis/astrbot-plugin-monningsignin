"""
数据库表结构定义
集中管理所有数据库表结构，避免重复定义
"""

# users 表结构
USERS_TABLE_SCHEMA = """
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        nickname TEXT,
        balance INTEGER DEFAULT 0,
        bank_balance INTEGER DEFAULT 0,
        last_signin_date TEXT,
        consecutive_days INTEGER DEFAULT 0,
        bank_last_date TEXT,
        favor_value INTEGER DEFAULT 0
    )
"""

# 其他表结构定义
OTHER_TABLES = {
    "user_sign": """
        CREATE TABLE IF NOT EXISTS user_sign (
            user_id TEXT PRIMARY KEY,
            last_sign_date TEXT,
            sign_streak INTEGER DEFAULT 0,
            total_sign_days INTEGER DEFAULT 0
        )
    """,
    "inventory": """
        CREATE TABLE IF NOT EXISTS inventory (
            user_id TEXT,
            item_name TEXT,
            quantity INTEGER DEFAULT 0,
            purchase_price INTEGER,
            purchase_date TEXT,
            PRIMARY KEY (user_id, item_name)
        )
    """,
    "purchase_log": """
        CREATE TABLE IF NOT EXISTS purchase_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            item_name TEXT,
            quantity INTEGER,
            total_price INTEGER,
            purchase_date TEXT
        )
    """,
    "lottery_log": """
        CREATE TABLE IF NOT EXISTS lottery_log (
            user_id TEXT,
            date TEXT,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, date)
        )
    """,
    "stock_holdings": """
        CREATE TABLE IF NOT EXISTS stock_holdings (
            user_id TEXT,
            stock_name TEXT,
            quantity INTEGER DEFAULT 0,
            avg_price INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, stock_name)
        )
    """,
    "user_work": """
        CREATE TABLE IF NOT EXISTS user_work (
            user_id TEXT PRIMARY KEY,
            work_name TEXT,
            salary INTEGER,
            work_date TEXT,
            last_salary_date TEXT
        )
    """,
    "user_society": """
        CREATE TABLE IF NOT EXISTS user_society (
            user_id TEXT PRIMARY KEY,
            society_name TEXT,
            join_date TEXT,
            last_switch_date TEXT
        )
    """,
    "user_achievements": """
        CREATE TABLE IF NOT EXISTS user_achievements (
            user_id TEXT,
            achievement_id TEXT,
            obtain_time TEXT,
            PRIMARY KEY (user_id, achievement_id)
        )
    """,
    "tax_records": """
        CREATE TABLE IF NOT EXISTS tax_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            tax_amount INTEGER,
            tax_date TEXT
        )
    """,
    "dividend_records": """
        CREATE TABLE IF NOT EXISTS dividend_records (
            user_id TEXT PRIMARY KEY,
            last_dividend_date TEXT,
            total_dividend INTEGER DEFAULT 0
        )
    """,
    "user_relationship": """
        CREATE TABLE IF NOT EXISTS user_relationship (
            user_id TEXT PRIMARY KEY,
            relationship_desc TEXT,
            update_time TEXT,
            next_update_time TEXT
        )
    """
}

# 数据库索引
DB_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_inventory_user ON inventory(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_lottery_user_date ON lottery_log(user_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_stock_holdings_user ON stock_holdings(user_id, stock_name)",
    "CREATE INDEX IF NOT EXISTS idx_achievements_user ON user_achievements(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_purchase_user ON purchase_log(user_id)"
]

# 兼容性迁移语句
MIGRATIONS = [
    # 添加 favor_value 列（如果不存在）
    ("ALTER TABLE users ADD COLUMN favor_value INTEGER DEFAULT 0", "favor_value"),
    # 添加 bank_last_date 列（如果不存在）
    ("ALTER TABLE users ADD COLUMN bank_last_date TEXT", "bank_last_date"),
    # 添加 next_update_time 列到 user_relationship（如果不存在）
    ("ALTER TABLE user_relationship ADD COLUMN next_update_time TEXT", "next_update_time")
]
