"""
Base Service Module
Provides common database operations for all services to avoid code duplication
"""
import aiosqlite
from typing import Tuple, Optional, Dict, Any
from utils import get_beijing_time


class BaseService:
    """Service base class providing common database operations"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def _get_user_asset(self, user_id: str) -> Tuple[int, int, int, int]:
        """
        Get user assets (total, cash, bank, stock)

        Returns:
            Tuple[int, int, int, int]: (total, cash, bank, stock)
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT balance, bank_balance FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()

            if not row:
                return (0, 0, 0, 0)

            cash = int(row[0]) if row[0] else 0
            bank = int(row[1]) if row[1] else 0

            cursor = await db.execute(
                """SELECT COALESCE(SUM(sh.remaining * sp.current_price), 0)
                   FROM stock_holdings sh
                   JOIN stock_prices sp ON sh.stock_name = sp.stock_name
                   WHERE sh.user_id = ? AND sh.remaining > 0 AND sp.delisted = 0""",
                (user_id,)
            )
            stock_row = await cursor.fetchone()
            stock = int(stock_row[0]) if stock_row and stock_row[0] else 0

        return (cash + bank + stock, cash, bank, stock)

    async def _get_rich_average_asset(self, percentile: float = 0.2) -> int:
        """
        Get average asset of top X% richest users

        Args:
            percentile: Top percentage (default 0.2 for top 20%)

        Returns:
            int: Average asset of rich users
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT u.user_id,
                    COALESCE(u.balance, 0) + COALESCE(u.bank_balance, 0) +
                    COALESCE(SUM(sh.remaining * sp.current_price), 0) as total
                   FROM users u
                   LEFT JOIN stock_holdings sh ON u.user_id = sh.user_id AND sh.remaining > 0
                   LEFT JOIN stock_prices sp ON sh.stock_name = sp.stock_name AND sp.delisted = 0
                   GROUP BY u.user_id
                   ORDER BY total DESC"""
            )
            rows = await cursor.fetchall()

            if not rows:
                return 0

            top_count = max(1, int(len(rows) * percentile))
            top_users = rows[:top_count]

            total = sum(row[1] for row in top_users)
            return total // top_count if top_count > 0 else 0
