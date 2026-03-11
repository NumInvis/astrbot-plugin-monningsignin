"""
管理员服务模块
"""
import os
import sys
# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import List, Dict
from datetime import datetime
import aiosqlite
from config import CONFIG
from achievements import ACHIEVEMENTS

def mask_id(uid: str) -> str:
    if len(uid) <= 4:
        return uid
    return uid[:3] + "***" + uid[-2:]


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
        """给指定用户授予成就"""
        async with aiosqlite.connect(self.db_path) as db:
            # 检查是否已获得
            cursor = await db.execute(
                "SELECT 1 FROM user_achievements WHERE user_id = ? AND achievement_id = ?",
                (user_id, achievement_id)
            )
            if await cursor.fetchone():
                return False
            
            # 授予成就
            await db.execute(
                "INSERT INTO user_achievements (user_id, achievement_id, obtain_time) VALUES (?, ?, ?)",
                (user_id, achievement_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            await db.commit()
            return True
    
    async def grant_achievement_to_all(self, achievement_id: str) -> int:
        """给所有用户授予成就"""
        async with aiosqlite.connect(self.db_path) as db:
            # 获取所有用户
            cursor = await db.execute("SELECT user_id FROM users")
            users = await cursor.fetchall()
            
            success_count = 0
            for (uid,) in users:
                # 检查是否已获得
                cursor = await db.execute(
                    "SELECT 1 FROM user_achievements WHERE user_id = ? AND achievement_id = ?",
                    (uid, achievement_id)
                )
                if not await cursor.fetchone():
                    # 授予成就
                    await db.execute(
                        "INSERT INTO user_achievements (user_id, achievement_id, obtain_time) VALUES (?, ?, ?)",
                        (uid, achievement_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    )
                    success_count += 1
            
            await db.commit()
            return success_count
    
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
                (datetime.now().strftime("%Y-%m-%d"),)
            )
            
            # 清空结社
            await db.execute("DELETE FROM user_society")
            
            await db.commit()