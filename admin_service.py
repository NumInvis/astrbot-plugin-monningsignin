"""
管理员服务模块
"""
import os
import sys
# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import List, Dict
import aiosqlite
from config import CONFIG
from achievements import ACHIEVEMENTS
from utils import get_beijing_time, mask_id


class AdminService:
    """管理员服务"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def get_all_achievements(self) -> Dict[str, List[str]]:
        """获取所有用户的成就"""
        async with aiosqlite.connect(self.db_path) as db:
            # 获取所有用户
            cursor = await db.execute("SELECT user_id FROM users")
            users = await cursor.fetchall()
            
            # 统计每个用户的成就
            user_achievements = {}
            for (uid,) in users:
                cursor = await db.execute(
                    "SELECT achievement_id FROM user_achievements WHERE user_id = ?",
                    (uid,)
                )
                achievements = [row[0] for row in await cursor.fetchall()]
                user_achievements[uid] = achievements
            
            return user_achievements
    
    async def give_maintenance_compensation(self, amount: int) -> int:
        """给所有人发放维护补偿"""
        async with aiosqlite.connect(self.db_path) as db:
            # 获取所有用户
            cursor = await db.execute("SELECT user_id FROM users")
            users = await cursor.fetchall()
            
            # 给每个用户发补偿
            for (uid,) in users:
                await db.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                    (amount, uid)
                )
            
            await db.commit()
            
            return len(users)
    
    async def grant_achievement(self, user_id: str, achievement_id: str) -> bool:
        """给指定用户授予成就（含加成）"""
        from achievement_service import AchievementService
        achievement_service = AchievementService(self.db_path)
        return await achievement_service.grant_achievement(user_id, achievement_id)
    
    async def grant_achievement_to_all(self, achievement_id: str) -> int:
        """给所有用户授予成就（含加成）"""
        from achievement_service import AchievementService
        achievement_service = AchievementService(self.db_path)
        return await achievement_service.grant_achievement_to_all(achievement_id)
    
    async def start_new_season(self) -> None:
        """开启新赛季"""
        async with aiosqlite.connect(self.db_path) as db:
            # 清空现金和银行（保留连续签到数据）
            await db.execute(
                "UPDATE users SET balance = 0, bank_balance = 0, bank_last_date = NULL"
            )

            # 清空工作
            await db.execute("DELETE FROM user_work")

            # 清空背包
            await db.execute("DELETE FROM inventory")

            # 清空购买日志
            await db.execute("DELETE FROM purchase_log")

            # 清空占卜日志
            await db.execute("DELETE FROM lottery_log")

            # 清空塔罗牌记录
            await db.execute("DELETE FROM user_daily_tarot")

            # 清空股票持仓
            await db.execute("DELETE FROM stock_holdings")

            # 重置股票价格
            await db.execute(
                """UPDATE stock_prices
                   SET current_price = base_price, delisted = 0, last_update = ?
                   WHERE owner_id IS NULL""",
                (get_beijing_time().strftime("%Y-%m-%d"),)
            )

            # 清空结社
            await db.execute("DELETE FROM user_society")

            await db.commit()

    async def give_subsidy(self, user_id: str, amount: int) -> dict:
        """给指定用户发放补贴

        Returns:
            dict: {'success': bool, 'message': str, 'new_balance': int}
        """
        async with aiosqlite.connect(self.db_path) as db:
            # 检查用户是否存在
            cursor = await db.execute(
                "SELECT 1 FROM users WHERE user_id = ?",
                (user_id,)
            )
            if not await cursor.fetchone():
                return {'success': False, 'message': '用户不存在', 'new_balance': 0}

            # 发放补贴
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id)
            )

            # 获取新余额
            cursor = await db.execute(
                "SELECT balance FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            new_balance = int(row[0]) if row and row[0] else 0

            await db.commit()

            return {'success': True, 'message': '补贴发放成功', 'new_balance': new_balance}

    async def deduct_asset(self, user_id: str, amount: int) -> dict:
        """扣除用户资产

        Returns:
            dict: {'success': bool, 'message': str, 'new_balance': int}
        """
        async with aiosqlite.connect(self.db_path) as db:
            # 获取用户当前余额
            cursor = await db.execute(
                "SELECT balance FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()

            if not row:
                return {'success': False, 'message': '用户不存在', 'new_balance': 0}

            current_balance = int(row[0]) if row[0] else 0

            if current_balance < amount:
                return {
                    'success': False,
                    'message': f'用户余额不足！当前余额：{current_balance}',
                    'new_balance': current_balance
                }

            # 扣除资产
            await db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (amount, user_id)
            )

            # 获取新余额
            cursor = await db.execute(
                "SELECT balance FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            new_balance = int(row[0]) if row and row[0] else 0

            await db.commit()

            return {'success': True, 'message': '资产扣除成功', 'new_balance': new_balance}

    async def reset_signin(self, user_id: str = None) -> dict:
        """重置用户签到状态

        Args:
            user_id: 用户ID，如果为None则重置所有人

        Returns:
            dict: {'success': bool, 'signin_count': int, 'tarot_count': int, 'message': str}
        """
        from utils import today_str, get_beijing_time

        today = today_str()
        yesterday = (get_beijing_time() - __import__('datetime').timedelta(days=1)).strftime("%Y-%m-%d")

        async with aiosqlite.connect(self.db_path) as db:
            if user_id is None:
                # 重置所有人的今日签到状态
                cursor = await db.execute(
                    "UPDATE users SET last_signin_date = ? WHERE last_signin_date = ?",
                    (yesterday, today)
                )
                signin_count = cursor.rowcount

                # 删除今日所有塔罗牌记录
                cursor = await db.execute(
                    "DELETE FROM user_daily_tarot WHERE date = ?",
                    (today,)
                )
                tarot_count = cursor.rowcount

                await db.commit()

                return {
                    'success': True,
                    'signin_count': signin_count,
                    'tarot_count': tarot_count,
                    'message': f'已重置 {signin_count} 个用户的签到状态，清除 {tarot_count} 条塔罗牌记录'
                }
            else:
                # 重置特定用户
                cursor = await db.execute(
                    "UPDATE users SET last_signin_date = ? WHERE user_id = ? AND last_signin_date = ?",
                    (yesterday, user_id, today)
                )

                if cursor.rowcount > 0:
                    await db.execute(
                        "DELETE FROM user_daily_tarot WHERE user_id = ? AND date = ?",
                        (user_id, today)
                    )
                    await db.commit()
                    return {
                        'success': True,
                        'signin_count': 1,
                        'tarot_count': 1,
                        'message': f'已重置用户 {user_id} 的签到状态'
                    }
                else:
                    return {
                        'success': False,
                        'signin_count': 0,
                        'tarot_count': 0,
                        'message': f'用户 {user_id} 今日未签到，无需重置'
                    }