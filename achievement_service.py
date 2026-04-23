"""成就服务模块"""
import os
import sys
# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import aiosqlite
from astrbot.api import logger
from achievements import ACHIEVEMENTS, AchievementManager
from config import CONFIG
from utils import today_str, now_str


class AchievementService:
    """成就服务类"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.achievement_manager = AchievementManager(db_path)
    
    async def init_table(self):
        """初始化成就相关表"""
        async with aiosqlite.connect(self.db_path) as db:
            # 用户成就表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_achievements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    achievement_id TEXT NOT NULL,
                    obtain_time TEXT NOT NULL,
                    UNIQUE(user_id, achievement_id)
                )
            """)
            # 成就加成表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS achievement_bonuses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    achievement_id TEXT NOT NULL,
                    bonus_type TEXT NOT NULL,
                    bonus_value INTEGER DEFAULT 0,
                    UNIQUE(user_id, achievement_id, bonus_type)
                )
            """)
            await db.commit()
    
    async def get_user_achievements(self, user_id: str) -> dict:
        """获取用户成就"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT achievement_id, obtain_time FROM user_achievements WHERE user_id = ?",
                (user_id,)
            )
            obtained = {row[0]: row[1] for row in await cursor.fetchall()}

        # 获取所有成就（包括自定义成就）
        all_achievements = await self.achievement_manager.get_all_achievements()

        obtained_count = len(obtained)
        hidden_count = len(all_achievements) - obtained_count

        return {
            "obtained": obtained,
            "obtained_count": obtained_count,
            "hidden_count": hidden_count,
            "total_count": len(all_achievements)
        }
    
    async def check_achievements(self, user_id: str, event_type: str, data: dict = None) -> list:
        """检查并授予成就，返回新获得的成就"""
        # 防御性编程：确保data不为None
        if data is None:
            data = {}

        new_achievements = []

        try:
            # 获取所有成就（包括自定义成就）
            all_achievements = await self.achievement_manager.get_all_achievements()

            async with aiosqlite.connect(self.db_path) as db:
                # 检查是否已获得
                async def has_achievement(aid: str) -> bool:
                    cursor = await db.execute(
                        "SELECT 1 FROM user_achievements WHERE user_id = ? AND achievement_id = ?",
                        (user_id, aid)
                    )
                    return await cursor.fetchone() is not None

                # 检查连续签到成就
                if event_type == "signin":
                    consecutive = data.get("consecutive", 0)
                    if consecutive >= 7 and not await has_achievement("signin_7"):
                        await db.execute(
                            "INSERT INTO user_achievements (user_id, achievement_id, obtain_time) VALUES (?, ?, ?)",
                            (user_id, "signin_7", now_str())
                        )
                        if "signin_7" in all_achievements:
                            new_achievements.append(all_achievements["signin_7"])
                    if consecutive >= 30 and not await has_achievement("signin_30"):
                        await db.execute(
                            "INSERT INTO user_achievements (user_id, achievement_id, obtain_time) VALUES (?, ?, ?)",
                            (user_id, "signin_30", now_str())
                        )
                        if "signin_30" in all_achievements:
                            new_achievements.append(all_achievements["signin_30"])
                    if consecutive >= 100 and not await has_achievement("signin_100"):
                        await db.execute(
                            "INSERT INTO user_achievements (user_id, achievement_id, obtain_time) VALUES (?, ?, ?)",
                            (user_id, "signin_100", now_str())
                        )
                        if "signin_100" in all_achievements:
                            new_achievements.append(all_achievements["signin_100"])
                    if not await has_achievement("first_signin"):
                        await db.execute(
                            "INSERT INTO user_achievements (user_id, achievement_id, obtain_time) VALUES (?, ?, ?)",
                            (user_id, "first_signin", now_str())
                        )
                        if "first_signin" in all_achievements:
                            new_achievements.append(all_achievements["first_signin"])

                # 检查财富成就
                if event_type == "asset_check":
                    total = data.get("total", 0)
                    if total >= 10000000 and not await has_achievement("rich_purple"):
                        await db.execute(
                            "INSERT INTO user_achievements (user_id, achievement_id, obtain_time) VALUES (?, ?, ?)",
                            (user_id, "rich_purple", now_str())
                        )
                        if "rich_purple" in all_achievements:
                            new_achievements.append(all_achievements["rich_purple"])
                    if total >= 100000000 and not await has_achievement("rich_colorful"):
                        await db.execute(
                            "INSERT INTO user_achievements (user_id, achievement_id, obtain_time) VALUES (?, ?, ?)",
                            (user_id, "rich_colorful", now_str())
                        )
                        if "rich_colorful" in all_achievements:
                            new_achievements.append(all_achievements["rich_colorful"])

                # 检查占卜成就
                if event_type == "lottery":
                    multiplier = data.get("multiplier", 0)
                    # 欧皇：占卜倍率>=66
                    if multiplier >= 66 and not await has_achievement("lottery_winner"):
                        await db.execute(
                            "INSERT INTO user_achievements (user_id, achievement_id, obtain_time) VALUES (?, ?, ?)",
                            (user_id, "lottery_winner", now_str())
                        )
                        if "lottery_winner" in all_achievements:
                            new_achievements.append(all_achievements["lottery_winner"])
                    # 我的悲伤是水做的：占卜倍率<0.05
                    if multiplier < 0.05 and not await has_achievement("sadness_is_water"):
                        await db.execute(
                            "INSERT INTO user_achievements (user_id, achievement_id, obtain_time) VALUES (?, ?, ?)",
                            (user_id, "sadness_is_water", now_str())
                        )
                        if "sadness_is_water" in all_achievements:
                            new_achievements.append(all_achievements["sadness_is_water"])

                # 检查贵宾卡成就
                if event_type == "buy" and data.get("item") == "莫塔里贵宾卡":
                    if not await has_achievement("vip_member"):
                        await db.execute(
                            "INSERT INTO user_achievements (user_id, achievement_id, obtain_time) VALUES (?, ?, ?)",
                            (user_id, "vip_member", now_str())
                        )
                        if "vip_member" in all_achievements:
                            new_achievements.append(all_achievements["vip_member"])

                # 检查真理碎片成就
                if event_type == "buy" and data.get("item") == "真理碎片":
                    if not await has_achievement("truth_seeker"):
                        await db.execute(
                            "INSERT INTO user_achievements (user_id, achievement_id, obtain_time) VALUES (?, ?, ?)",
                            (user_id, "truth_seeker", now_str())
                        )
                        if "truth_seeker" in all_achievements:
                            new_achievements.append(all_achievements["truth_seeker"])

                # 检查花朵成就
                if event_type == "flower_check":
                    count = data.get("count", 0)
                    if count >= 99 and not await has_achievement("flower_blue"):
                        await db.execute(
                            "INSERT INTO user_achievements (user_id, achievement_id, obtain_time) VALUES (?, ?, ?)",
                            (user_id, "flower_blue", now_str())
                        )
                        if "flower_blue" in all_achievements:
                            new_achievements.append(all_achievements["flower_blue"])
                    if count >= 9999 and not await has_achievement("flower_gold"):
                        await db.execute(
                            "INSERT INTO user_achievements (user_id, achievement_id, obtain_time) VALUES (?, ?, ?)",
                            (user_id, "flower_gold", now_str())
                        )
                        if "flower_gold" in all_achievements:
                            new_achievements.append(all_achievements["flower_gold"])

                await db.commit()
        except Exception as e:
            logger.error(f"检查成就失败: {e}")

        return new_achievements
    
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
                (user_id, achievement_id, now_str())
            )

            # 获取所有成就（包括自定义成就）
            all_achievements = await self.achievement_manager.get_all_achievements()

            # 添加成就加成
            if achievement_id in all_achievements:
                achievement = all_achievements[achievement_id]
                rarity = achievement.get("rarity", "blue")

                # 从配置文件读取加成配置
                bonus_config = CONFIG.ACHIEVEMENT_BONUSES.get(rarity, {})
                bonus_type = bonus_config.get("type", "signin_extra")
                bonus_value = bonus_config.get("value", 1)

                # 根据加成类型添加到数据库
                await db.execute(
                    "INSERT OR IGNORE INTO achievement_bonuses (user_id, achievement_id, bonus_type, bonus_value) VALUES (?, ?, ?, ?)",
                    (user_id, achievement_id, bonus_type, bonus_value)
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

            # 获取所有成就（包括自定义成就）
            all_achievements = await self.achievement_manager.get_all_achievements()

            # 从配置文件读取加成配置
            bonus_config = {}
            bonus_type = "signin_extra"
            bonus_value = 1

            if achievement_id in all_achievements:
                achievement = all_achievements[achievement_id]
                rarity = achievement.get("rarity", "blue")
                bonus_config = CONFIG.ACHIEVEMENT_BONUSES.get(rarity, {})
                bonus_type = bonus_config.get("type", "signin_extra")
                bonus_value = bonus_config.get("value", 1)

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
                        (uid, achievement_id, now_str())
                    )

                    # 添加成就加成
                    if achievement_id in all_achievements:
                        await db.execute(
                            "INSERT OR IGNORE INTO achievement_bonuses (user_id, achievement_id, bonus_type, bonus_value) VALUES (?, ?, ?, ?)",
                            (uid, achievement_id, bonus_type, bonus_value)
                        )

                    success_count += 1

            await db.commit()
            return success_count
    
    async def get_all_achievements(self) -> dict:
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
    
    async def grant_season_achievements(self):
        """授予赛季成就"""
        from config import CONFIG
        
        # 给指定用户授予"斩断循环"成就
        for uid in CONFIG.CYCLE_BREAKER_USERS:
            await self.grant_achievement(uid, "cycle_breaker")
        
        # 给系统管理员授予"莫宁之主"成就
        for uid in CONFIG.ADMIN_IDS:
            await self.grant_achievement(uid, "moning_master")
        
        # 给所有已有数据的用户授予"先行者"成就
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT user_id FROM users")
            users = await cursor.fetchall()
            for (uid,) in users:
                await self.grant_achievement(uid, "pioneer")
