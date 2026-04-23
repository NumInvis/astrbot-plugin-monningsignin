"""
成就配置文件
"""
import os
import sys
import aiosqlite

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# 默认成就配置（内置成就）
DEFAULT_ACHIEVEMENTS = {
    # 蓝色成就
    "first_signin": {"name": "初次签到", "desc": "完成第一次签到", "emoji": "🌱", "rarity": "blue"},
    "signin_7": {"name": "周常打卡", "desc": "连续签到7天", "emoji": "📅", "rarity": "blue"},
    "work_hard": {"name": "打工人", "desc": "累计工资收入超过10万", "emoji": "💼", "rarity": "blue"},
    "vip_member": {"name": "贵宾", "desc": "拥有莫塔里贵宾卡", "emoji": "🌟", "rarity": "blue"},
    "flower_blue": {"name": "这朵花送给你", "desc": "背包有99朵花", "emoji": "🌸", "rarity": "blue"},
    # 紫色成就
    "signin_30": {"name": "月度达人", "desc": "连续签到30天", "emoji": "📆", "rarity": "purple"},
    "rich_purple": {"name": "亿万富翁", "desc": "总资产达到1000万", "emoji": "💎", "rarity": "purple"},
    "stock_master": {"name": "股神", "desc": "股票盈利超过100万", "emoji": "📈", "rarity": "purple"},
    "top_yue": {"name": "第一月吹", "desc": "拜月结社资产第一", "emoji": "🌙", "rarity": "purple"},
    "top_fu": {"name": "第一卡吹", "desc": "负资产结社资产第一", "emoji": "💸", "rarity": "purple"},
    "top_qian": {"name": "第一千吹", "desc": "千衢结社资产第一", "emoji": "⚡", "rarity": "purple"},
    "top_nuo": {"name": "第一弗吹", "desc": "弗糯结社资产第一", "emoji": "🍚", "rarity": "purple"},
    # 金色成就
    "signin_100": {"name": "百日筑基", "desc": "连续签到100天", "emoji": "🏆", "rarity": "gold"},
    "truth_seeker": {"name": "真理追寻者", "desc": "购买真理碎片", "emoji": "🔮", "rarity": "gold"},
    "flower_gold": {"name": "for you, for one more day", "desc": "背包有9999朵花", "emoji": "🌺", "rarity": "gold"},
    "pioneer": {"name": "先行者", "desc": "参与过莫宁宁第宁赛季", "emoji": "✨", "rarity": "gold"},
    "highest_laurel": {"name": "最高桂冠", "desc": "占卜时获得66倍奖励", "emoji": "👑", "rarity": "gold"},
    # 蓝色成就
    "lottery_winner": {"name": "欧皇", "desc": "占卜获得66倍奖励", "emoji": "🍀", "rarity": "blue"},
    "sadness_is_water": {"name": "我的悲伤是水做的", "desc": "占卜倍率小于0.05", "emoji": "💧", "rarity": "blue"},
    # 彩色成就
    "rich_colorful": {"name": "兆亿富翁", "desc": "总资产达到1亿", "emoji": "👑", "rarity": "purple"},
    "cycle_breaker": {"name": "斩断循环", "desc": "第宁赛季资产排行榜第一名", "emoji": "⚔️", "rarity": "colorful"},
    "moning_master": {"name": "莫宁之主", "desc": "系统管理员", "emoji": "👑", "rarity": "colorful"},
}


class AchievementManager:
    """成就管理器，支持动态加载自定义成就"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._achievements = None

    async def init_table(self):
        """初始化自定义成就表"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS custom_achievements (
                    achievement_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    desc TEXT NOT NULL,
                    emoji TEXT DEFAULT '🏆',
                    rarity TEXT DEFAULT 'blue'
                )
            """)
            await db.commit()

    async def get_all_achievements(self) -> dict:
        """获取所有成就（内置 + 自定义）"""
        if self._achievements is None:
            # 从数据库加载自定义成就
            custom_achievements = await self._load_custom_achievements()
            # 合并内置成就和自定义成就
            self._achievements = {**DEFAULT_ACHIEVEMENTS, **custom_achievements}
        return self._achievements

    async def _load_custom_achievements(self) -> dict:
        """从数据库加载自定义成就"""
        custom = {}
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT achievement_id, name, desc, emoji, rarity FROM custom_achievements"
                )
                rows = await cursor.fetchall()
                for row in rows:
                    achievement_id, name, desc, emoji, rarity = row
                    custom[achievement_id] = {
                        "name": name,
                        "desc": desc,
                        "emoji": emoji or '🏆',
                        "rarity": rarity or 'blue'
                    }
        except Exception:
            # 表可能不存在，返回空字典
            pass
        return custom

    async def add_custom_achievement(self, achievement_id: str, name: str, desc: str, emoji: str = '🏆', rarity: str = 'blue') -> bool:
        """添加自定义成就"""
        # 检查ID是否已存在（在内置成就中）
        if achievement_id in DEFAULT_ACHIEVEMENTS:
            return False

        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    """INSERT OR REPLACE INTO custom_achievements
                        (achievement_id, name, desc, emoji, rarity)
                        VALUES (?, ?, ?, ?, ?)""",
                    (achievement_id, name, desc, emoji, rarity)
                )
                await db.commit()
                # 清除缓存，下次重新加载
                self._achievements = None
                return True
            except Exception:
                return False

    async def delete_custom_achievement(self, achievement_id: str) -> bool:
        """删除自定义成就"""
        if achievement_id in DEFAULT_ACHIEVEMENTS:
            return False  # 不能删除内置成就

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM custom_achievements WHERE achievement_id = ?",
                (achievement_id,)
            )
            await db.commit()
            if cursor.rowcount > 0:
                self._achievements = None
                return True
            return False

    def clear_cache(self):
        """清除成就缓存"""
        self._achievements = None


# 全局成就字典（保持向后兼容）
ACHIEVEMENTS = DEFAULT_ACHIEVEMENTS.copy()
