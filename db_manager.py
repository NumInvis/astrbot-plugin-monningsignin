"""
数据库管理器模块
"""
import os
import sys
import aiosqlite

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CONFIG


def today_str() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")


def now_str() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class DatabaseManager:
    """数据库管理器类"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def init_database(self):
        """初始化数据库"""
        async with aiosqlite.connect(self.db_path) as db:
            # 用户表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    balance INTEGER DEFAULT 0,
                    bank_balance INTEGER DEFAULT 0,
                    last_signin_date TEXT,
                    consecutive_days INTEGER DEFAULT 0,
                    favor_value INTEGER DEFAULT 0
                )
            """)
            
            # 背包表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    user_id TEXT,
                    item_name TEXT,
                    count INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, item_name)
                )
            """)
            
            # 股票持仓表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS stock_holdings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    stock_name TEXT,
                    quantity REAL DEFAULT 0,
                    buy_price REAL DEFAULT 0,
                    buy_time TEXT,
                    remaining REAL DEFAULT 0,
                    last_dividend_date TEXT
                )
            """)
            
            # 股票价格表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS stock_prices (
                    stock_name TEXT PRIMARY KEY,
                    current_price REAL DEFAULT 100,
                    base_price REAL DEFAULT 100,
                    emoji TEXT,
                    desc TEXT,
                    last_update TEXT
                )
            """)
            
            # 成就表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_achievements (
                    user_id TEXT,
                    achievement_id TEXT,
                    obtain_time TEXT,
                    PRIMARY KEY (user_id, achievement_id)
                )
            """)
            
            # 工作表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_jobs (
                    user_id TEXT PRIMARY KEY,
                    job_name TEXT,
                    start_date TEXT,
                    last_salary_date TEXT
                )
            """)
            
            # 购买日志表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS purchase_log (
                    user_id TEXT,
                    item_name TEXT,
                    purchase_date TEXT,
                    count INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, item_name, purchase_date)
                )
            """)
            
            # 成就加成表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS achievement_bonuses (
                    user_id TEXT,
                    achievement_id TEXT,
                    bonus_type TEXT,
                    bonus_value REAL,
                    PRIMARY KEY (user_id, achievement_id, bonus_type)
                )
            """)
            
            # 初始化默认股票
            default_stocks = [
                ("菲比教会", 10, "🕊️", "菲比啾比，菲比啾比！"),
                ("莫宁时代", 50, "🏢", "我将，诘问群星！"),
                ("今州科技", 200, "🔬", "今州地大物博"),
                ("深空联合", 1000, "🚀", "我们是薪火的传承者")
            ]
            
            for name, price, emoji, desc in default_stocks:
                await db.execute(
                    """INSERT OR IGNORE INTO stock_prices 
                        (stock_name, current_price, base_price, emoji, desc, last_update)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                    (name, price, price, emoji, desc, today_str())
                )
            
            await db.commit()
    
    async def get_user(self, user_id: str) -> dict:
        """获取用户信息"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                return {
                    "user_id": row[0],
                    "balance": int(row[1]) if row[1] else 0,
                    "bank_balance": int(row[2]) if row[2] else 0,
                    "last_signin_date": row[3],
                    "consecutive_days": int(row[4]) if row[4] else 0,
                    "favor_value": int(row[5]) if len(row) > 5 and row[5] else 0
                }
            else:
                # 创建新用户
                await db.execute(
                    "INSERT INTO users (user_id, balance, bank_balance, consecutive_days, favor_value) VALUES (?, 0, 0, 0, 0)",
                    (user_id,)
                )
                await db.commit()
                return {
                    "user_id": user_id,
                    "balance": 0,
                    "bank_balance": 0,
                    "last_signin_date": None,
                    "consecutive_days": 0,
                    "favor_value": 0
                }
    
    async def update_user_balance(self, user_id: str, amount: int) -> bool:
        """更新用户余额"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id)
            )
            await db.commit()
            return True
    
    async def update_user_bank_balance(self, user_id: str, amount: int) -> bool:
        """更新用户银行余额"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET bank_balance = bank_balance + ? WHERE user_id = ?",
                (amount, user_id)
            )
            await db.commit()
            return True
    
    async def get_inventory(self, user_id: str) -> dict:
        """获取用户背包"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT item_name, count FROM inventory WHERE user_id = ?",
                (user_id,)
            )
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}
    
    async def add_item(self, user_id: str, item_name: str, count: int) -> bool:
        """添加物品到背包"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO inventory (user_id, item_name, count) 
                    VALUES (?, ?, COALESCE((SELECT count FROM inventory WHERE user_id = ? AND item_name = ?), 0) + ?)""",
                (user_id, item_name, user_id, item_name, count)
            )
            await db.commit()
            return True
    
    async def remove_item(self, user_id: str, item_name: str, count: int) -> bool:
        """从背包移除物品"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT count FROM inventory WHERE user_id = ? AND item_name = ?",
                (user_id, item_name)
            )
            row = await cursor.fetchone()
            
            if not row or row[0] < count:
                return False
            
            new_count = row[0] - count
            if new_count > 0:
                await db.execute(
                    "UPDATE inventory SET count = ? WHERE user_id = ? AND item_name = ?",
                    (new_count, user_id, item_name)
                )
            else:
                await db.execute(
                    "DELETE FROM inventory WHERE user_id = ? AND item_name = ?",
                    (user_id, item_name)
                )
            
            await db.commit()
            return True
    
    async def get_stock_holdings(self, user_id: str) -> dict:
        """获取用户股票持仓"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT stock_name, quantity, buy_price FROM stock_holdings WHERE user_id = ?",
                (user_id,)
            )
            rows = await cursor.fetchall()
            return {row[0]: {"quantity": row[1], "buy_price": row[2]} for row in rows}

    async def update_stock_holding(self, user_id: str, stock_name: str, quantity: float, buy_price: float) -> bool:
        """更新股票持仓"""
        async with aiosqlite.connect(self.db_path) as db:
            if quantity > 0:
                await db.execute(
                    """INSERT OR REPLACE INTO stock_holdings (user_id, stock_name, quantity, buy_price, remaining)
                        VALUES (?, ?, ?, ?, ?)""",
                    (user_id, stock_name, quantity, buy_price, quantity)
                )
            else:
                await db.execute(
                    "DELETE FROM stock_holdings WHERE user_id = ? AND stock_name = ?",
                    (user_id, stock_name)
                )
            await db.commit()
            return True
    
    async def get_all_users(self) -> list:
        """获取所有用户"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT user_id FROM users")
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
