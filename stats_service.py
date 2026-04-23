"""
统计服务模块
统一管理玩家总数、总资产、经济总量等统计，避免重复造轮子
"""
from typing import List, Dict
import aiosqlite
from datetime import timedelta

from utils import get_beijing_time, today_str
from astrbot.api import logger
from base_service import BaseService


class StatsService(BaseService):
    """统计服务类

    集中管理所有经济统计数据，避免各服务重复查询
    """

    async def get_player_count(self) -> int:
        """获取玩家总数"""
        row = await self._fetchone("SELECT COUNT(*) FROM users")
        return row[0] if row else 0

    async def get_all_users_assets(self) -> List[Dict]:
        """获取所有用户资产详情（优化版本，使用JOIN避免N+1查询）

        Returns:
            [{"user_id": str, "cash": int, "bank": int, "stock": int, "total": int}, ...]
        """
        rows = await self._fetchall("""
            SELECT
                u.user_id,
                COALESCE(u.balance, 0) as cash,
                COALESCE(u.bank_balance, 0) as bank,
                COALESCE(SUM(sh.remaining * sp.current_price), 0) as stock_value
            FROM users u
            LEFT JOIN stock_holdings sh ON u.user_id = sh.user_id AND sh.remaining > 0
            LEFT JOIN stock_prices sp ON sh.stock_name = sp.stock_name AND sp.delisted = 0
            GROUP BY u.user_id
        """)

        result = []
        for row in rows:
            user_id = row[0]
            cash = int(row[1]) if row[1] else 0
            bank = int(row[2]) if row[2] else 0
            stock_value = int(row[3]) if row[3] else 0

            total = cash + bank + stock_value
            result.append({
                "user_id": user_id,
                "cash": cash,
                "bank": bank,
                "stock": stock_value,
                "total": total
            })

        return result

    async def get_total_wealth(self) -> int:
        """获取经济总量（所有用户总资产之和）"""
        row = await self._fetchone("""
            SELECT
                COALESCE(SUM(u.balance), 0) +
                COALESCE(SUM(u.bank_balance), 0) +
                COALESCE(SUM(sh.remaining * sp.current_price), 0) as total
            FROM users u
            LEFT JOIN stock_holdings sh ON u.user_id = sh.user_id AND sh.remaining > 0
            LEFT JOIN stock_prices sp ON sh.stock_name = sp.stock_name AND sp.delisted = 0
        """)
        return int(row[0]) if row and row[0] else 0

    async def get_average_wealth(self) -> float:
        """获取人均资产"""
        total = await self.get_total_wealth()
        count = await self.get_player_count()
        return total / count if count > 0 else 0.0

    async def get_median_wealth(self) -> int:
        """获取资产中位数"""
        rows = await self._fetchall("""
            SELECT total_wealth FROM (
                SELECT
                    u.user_id,
                    COALESCE(u.balance, 0) +
                    COALESCE(u.bank_balance, 0) +
                    COALESCE(SUM(sh.remaining * sp.current_price), 0) as total_wealth
                FROM users u
                LEFT JOIN stock_holdings sh ON u.user_id = sh.user_id AND sh.remaining > 0
                LEFT JOIN stock_prices sp ON sh.stock_name = sp.stock_name AND sp.delisted = 0
                GROUP BY u.user_id
            )
            ORDER BY total_wealth
        """)

        if not rows:
            return 0

        totals = [int(row[0]) for row in rows if row[0]]
        n = len(totals)

        if n % 2 == 1:
            return totals[n // 2]
        else:
            return (totals[n // 2 - 1] + totals[n // 2]) // 2

    async def get_top10_assets(self) -> List[Dict]:
        """获取资产排行榜前十名（使用SQL排序）"""
        rows = await self._fetchall("""
            SELECT
                u.user_id,
                COALESCE(u.balance, 0) as cash,
                COALESCE(u.bank_balance, 0) as bank,
                COALESCE(SUM(sh.remaining * sp.current_price), 0) as stock_value,
                COALESCE(u.balance, 0) + COALESCE(u.bank_balance, 0) +
                COALESCE(SUM(sh.remaining * sp.current_price), 0) as total
            FROM users u
            LEFT JOIN stock_holdings sh ON u.user_id = sh.user_id AND sh.remaining > 0
            LEFT JOIN stock_prices sp ON sh.stock_name = sp.stock_name AND sp.delisted = 0
            GROUP BY u.user_id
            ORDER BY total DESC
            LIMIT 10
        """)

        result = []
        for row in rows:
            result.append({
                "user_id": row[0],
                "cash": int(row[1]) if row[1] else 0,
                "bank": int(row[2]) if row[2] else 0,
                "stock": int(row[3]) if row[3] else 0,
                "total": int(row[4]) if row[4] else 0
            })

        return result

    async def get_economy_stats(self, days: int = 7) -> Dict:
        """获取经济统计数据

        Args:
            days: 统计最近几天的数据

        Returns:
            {
                "player_count": int,
                "total_wealth": int,
                "avg_wealth": float,
                "median_wealth": int,
                "tax_total": int,
                "daily_stats": [{"date": str, "tax": int}, ...]
            }
        """
        player_count = await self.get_player_count()
        total_wealth = await self.get_total_wealth()
        avg_wealth = self._calculate_avg(total_wealth, player_count)
        median_wealth = await self.get_median_wealth()

        # 获取税收统计
        start_date = (get_beijing_time() - timedelta(days=days)).strftime("%Y-%m-%d")
        tax_rows = await self._fetchall(
            "SELECT date, total_tax FROM tax_pool WHERE date >= ? ORDER BY date DESC",
            (start_date,)
        )

        tax_total = sum(int(row[1]) for row in tax_rows if row[1])
        daily_stats = [{"date": row[0], "tax": int(row[1]) if row[1] else 0} for row in tax_rows]

        return {
            "player_count": player_count,
            "total_wealth": total_wealth,
            "avg_wealth": avg_wealth,
            "median_wealth": median_wealth,
            "tax_total": tax_total,
            "daily_stats": daily_stats
        }

    def _calculate_avg(self, total: int, count: int) -> float:
        """计算平均值"""
        return total / count if count > 0 else 0.0
