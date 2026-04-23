"""
Base Service Module
Provides common database operations for all services to avoid code duplication
"""
import aiosqlite
from typing import Tuple, Optional, Dict, Any, List
from utils import get_beijing_time


class BaseService:
    """Service base class providing common database operations"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    # ========== 通用数据库查询方法 ==========

    async def _execute(self, query: str, params: tuple = ()) -> int:
        """执行无返回SQL，返回影响行数"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(query, params)
            await db.commit()
            return cursor.rowcount

    async def _fetchone(self, query: str, params: tuple = ()) -> Optional[tuple]:
        """获取单条记录"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(query, params)
            return await cursor.fetchone()

    async def _fetchall(self, query: str, params: tuple = ()) -> List[tuple]:
        """获取所有记录"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(query, params)
            return await cursor.fetchall()

    async def _executemany(self, query: str, params_list: List[tuple]) -> int:
        """批量执行SQL"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.executemany(query, params_list)
            await db.commit()
            return cursor.rowcount

    # ========== 用户相关通用方法 ==========

    async def _user_exists(self, user_id: str) -> bool:
        """检查用户是否存在"""
        row = await self._fetchone(
            "SELECT 1 FROM users WHERE user_id = ?", (user_id,)
        )
        return row is not None

    async def _get_user(self, user_id: str) -> Dict[str, Any]:
        """获取用户数据，不存在则自动创建"""
        row = await self._fetchone(
            "SELECT user_id, balance, bank_balance, last_signin_date, "
            "consecutive_days, bank_last_date, favor_value "
            "FROM users WHERE user_id = ?",
            (user_id,)
        )
        if row:
            return {
                "user_id": row[0],
                "balance": int(row[1]) if row[1] else 0,
                "bank_balance": int(row[2]) if row[2] else 0,
                "last_signin_date": row[3],
                "consecutive_days": int(row[4]) if row[4] else 0,
                "bank_last_date": row[5],
                "favor_value": int(row[6]) if row[6] else 0,
            }
        # 创建新用户
        await self._execute(
            "INSERT INTO users (user_id) VALUES (?)", (user_id,)
        )
        return {
            "user_id": user_id,
            "balance": 0,
            "bank_balance": 0,
            "last_signin_date": None,
            "consecutive_days": 0,
            "bank_last_date": None,
            "favor_value": 0,
        }

    async def _get_user_balance(self, user_id: str) -> int:
        """获取用户现金余额"""
        row = await self._fetchone(
            "SELECT balance FROM users WHERE user_id = ?", (user_id,)
        )
        return int(row[0]) if row and row[0] else 0

    async def _get_user_bank(self, user_id: str) -> int:
        """获取用户银行存款"""
        row = await self._fetchone(
            "SELECT bank_balance FROM users WHERE user_id = ?", (user_id,)
        )
        return int(row[0]) if row and row[0] else 0

    async def _update_balance(self, user_id: str, delta: int) -> int:
        """原子更新用户余额（delta可为负数），返回新余额"""
        await self._execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (delta, user_id)
        )
        return await self._get_user_balance(user_id)

    async def _update_bank(self, user_id: str, delta: int) -> int:
        """原子更新用户银行存款，返回新余额"""
        await self._execute(
            "UPDATE users SET bank_balance = bank_balance + ? WHERE user_id = ?",
            (delta, user_id)
        )
        return await self._get_user_bank(user_id)

    async def _get_user_asset(self, user_id: str) -> Tuple[int, int, int, int]:
        """
        Get user assets (total, cash, bank, stock)
        Returns: (total, cash, bank, stock)
        """
        row = await self._fetchone(
            "SELECT balance, bank_balance FROM users WHERE user_id = ?",
            (user_id,)
        )
        if not row:
            return (0, 0, 0, 0)

        cash = int(row[0]) if row[0] else 0
        bank = int(row[1]) if row[1] else 0

        stock_row = await self._fetchone(
            """SELECT COALESCE(SUM(sh.remaining * sp.current_price), 0)
               FROM stock_holdings sh
               JOIN stock_prices sp ON sh.stock_name = sp.stock_name
               WHERE sh.user_id = ? AND sh.remaining > 0 AND sp.delisted = 0""",
            (user_id,)
        )
        stock = int(stock_row[0]) if stock_row and stock_row[0] else 0

        return (cash + bank + stock, cash, bank, stock)

    async def _get_rich_average_asset(self, percentile: float = 0.2) -> int:
        """
        Get average asset of top X% richest users
        Args: percentile: Top percentage (default 0.2 for top 20%)
        Returns: Average asset of rich users
        """
        rows = await self._fetchall(
            """SELECT u.user_id,
                COALESCE(u.balance, 0) + COALESCE(u.bank_balance, 0) +
                COALESCE(SUM(sh.remaining * sp.current_price), 0) as total
               FROM users u
               LEFT JOIN stock_holdings sh ON u.user_id = sh.user_id AND sh.remaining > 0
               LEFT JOIN stock_prices sp ON sh.stock_name = sp.stock_name AND sp.delisted = 0
               GROUP BY u.user_id
               ORDER BY total DESC"""
        )
        if not rows:
            return 0

        top_count = max(1, int(len(rows) * percentile))
        top_users = rows[:top_count]

        total = sum(row[1] for row in top_users)
        return total // top_count if top_count > 0 else 0
