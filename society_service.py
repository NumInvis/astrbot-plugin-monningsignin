"""结社服务模块"""
import os
import sys
# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import aiosqlite
from datetime import datetime, timedelta, timezone
from config import CONFIG


def format_num(n: int) -> str:
    return f"{n:,}"


def mask_user_id(uid: str) -> str:
    if len(uid) <= 4:
        return uid
    return uid[:3] + "***" + uid[-2:]


def get_beijing_time() -> datetime:
    """获取北京时间（UTC+8）"""
    utc_now = datetime.now(timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    return utc_now.astimezone(beijing_tz)


def now_str() -> str:
    """获取当前时间的字符串（北京时间）"""
    return get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")


class SocietyService:
    """结社服务类"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def get_society_stats(self) -> dict:
        """获取结社统计信息"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM user_society WHERE society_name IS NOT NULL")
            total = (await cursor.fetchone())[0]
            
            stats = {}
            for name in CONFIG.SOCIETIES.keys():
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM user_society WHERE society_name = ?",
                    (name,)
                )
                count = (await cursor.fetchone())[0]
                percentage = (count / total * 100) if total > 0 else 0
                stats[name] = {"count": count, "percentage": percentage}
        
        return {
            "total": total,
            "stats": stats
        }
    
    async def join_society(self, user_id: str, society_name: str) -> dict:
        """加入结社"""
        if society_name not in CONFIG.SOCIETIES:
            return {"success": False, "message": f"结社不存在！可选：{', '.join(CONFIG.SOCIETIES.keys())}"}
        
        config = CONFIG.SOCIETIES[society_name]
        now = get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")
        
        async with aiosqlite.connect(self.db_path) as db:
            # 检查冷却
            cursor = await db.execute(
                "SELECT last_change_time FROM user_society WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            
            if row and row[0]:
                last_change = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                last_change = last_change.replace(tzinfo=timezone(timedelta(hours=8)))
                if (get_beijing_time() - last_change).total_seconds() < CONFIG.SOCIETY_COOLDOWN * 3600:
                    remaining = int((CONFIG.SOCIETY_COOLDOWN * 3600 - (get_beijing_time() - last_change).total_seconds()) / 60)
                    return {"success": False, "message": f"⏳ 冷却中！还需 {remaining} 分钟才能更换结社"}
            
            await db.execute(
                """INSERT INTO user_society (user_id, society_name, join_time, last_change_time)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET 
                   society_name = ?, join_time = ?, last_change_time = ?""",
                (user_id, society_name, now, now, society_name, now, now)
            )
            await db.commit()
        
        return {
            "success": True,
            "society_name": society_name,
            "emoji": config['emoji'],
            "desc": config['desc']
        }
    
    async def get_my_society(self, user_id: str) -> dict:
        """获取我的结社信息"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT us.society_name, us.join_time,
                          (SELECT COUNT(*) FROM user_society WHERE society_name = us.society_name) as member_count
                   FROM user_society us WHERE us.user_id = ?""",
                (user_id,)
            )
            row = await cursor.fetchone()
        
        if not row or not row[0]:
            return {"success": False, "message": "💼 你还没有加入任何结社\n发送 /结社 查看可加入的结社"}
        
        society_name, join_time, member_count = row
        config = CONFIG.SOCIETIES.get(society_name, {})
        
        # 获取本结社资产第一的人
        top_user = await self._get_society_top_user(society_name)
        top_info = {}
        if top_user:
            top_uid, top_asset, top_name = top_user
            is_me = top_uid == user_id
            
            # 根据结社名称设置第一的称号
            if society_name == "拜月结社":
                top_title = "第一月吹"
            elif society_name == "负资产结社":
                top_title = "第一卡吹"
            elif society_name == "千衢结社":
                top_title = "第一千吹"
            elif society_name == "弗糯结社":
                top_title = "第一弗吹"
            else:
                top_title = "结社第一"
            
            top_info = {
                "uid": top_uid,
                "name": top_name,
                "asset": top_asset,
                "is_me": is_me,
                "title": top_title
            }
            
            # 如果是自己，检查并授予成就
            if top_uid == user_id:
                await self._check_society_top_achievement(user_id, society_name)
        
        # 获取结社福利信息
        benefits = await self._get_society_benefits(society_name)
        
        return {
            "success": True,
            "society_name": society_name,
            "emoji": config.get('emoji', '🔮'),
            "desc": config.get('desc', ''),
            "member_count": member_count,
            "join_time": join_time,
            "top_user": top_info,
            "cooldown": CONFIG.SOCIETY_COOLDOWN,
            "benefits": benefits
        }
    
    async def _get_society_benefits(self, society_name: str) -> dict:
        """获取结社福利"""
        benefits = {}
        
        async with aiosqlite.connect(self.db_path) as db:
            if society_name == "拜月结社":
                # 签到额外奖励增加x星声+x%星声，x为结社人数
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM user_society WHERE society_name = '拜月结社'"
                )
                member_count = await cursor.fetchone()
                member_count = member_count[0] if member_count else 0
                benefits = {
                    "type": "签到奖励",
                    "detail": f"额外增加{member_count}星声+{member_count}%星声"
                }
            
            elif society_name == "负资产结社":
                # 银行利率增加25-x%，x为负资产结社人数占比
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM user_society"
                )
                total_members = await cursor.fetchone()
                total_members = total_members[0] if total_members else 1
                
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM user_society WHERE society_name = '负资产结社'"
                )
                member_count = await cursor.fetchone()
                member_count = member_count[0] if member_count else 0
                
                ratio = (member_count / total_members) * 100
                interest_increase = max(0, 25 - ratio)
                benefits = {
                    "type": "银行利率",
                    "detail": f"增加{interest_increase:.1f}%"
                }
            
            elif society_name == "千衢结社":
                # 每小时的工资增加千衢结社人数*0.01%*富人阶级（前20%）玩家的平均资产
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM user_society WHERE society_name = '千衢结社'"
                )
                member_count = await cursor.fetchone()
                member_count = member_count[0] if member_count else 0
                
                # 获取富人阶级平均资产
                rich_avg = await self._get_rich_average_asset(db)
                wage_increase = member_count * 0.0001 * rich_avg
                benefits = {
                    "type": "工资增加",
                    "detail": f"每小时增加约{int(wage_increase)}星声"
                }
            
            elif society_name == "弗糯结社":
                # 股票交易无手续费，每日分红增加0.1%*弗糯结社人数
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM user_society WHERE society_name = '弗糯结社'"
                )
                member_count = await cursor.fetchone()
                member_count = member_count[0] if member_count else 0
                dividend_increase = member_count * 0.1
                benefits = {
                    "type": "股票福利",
                    "detail": f"交易无手续费，分红增加{dividend_increase}%"
                }
        
        return benefits
    
    async def _get_rich_average_asset(self, db) -> int:
        """获取富人阶级（前20%）玩家的平均资产"""
        # 获取所有用户资产
        cursor = await db.execute("SELECT user_id FROM users")
        users = await cursor.fetchall()
        
        if not users:
            return 0
        
        asset_list = []
        for (uid,) in users:
            asset = await self._get_user_asset(uid)
            total = asset[0]  # 总资产
            asset_list.append(total)
        
        if not asset_list:
            return 0
        
        # 排序并取前20%
        asset_list.sort(reverse=True)
        top_20_percent = int(len(asset_list) * 0.2)
        if top_20_percent == 0:
            top_20_percent = 1
        
        top_assets = asset_list[:top_20_percent]
        avg_asset = sum(top_assets) // len(top_assets)
        
        return avg_asset
    
    async def _get_society_top_user(self, society_name: str):
        """获取结社资产第一的用户"""
        async with aiosqlite.connect(self.db_path) as db:
            # 获取结社所有成员
            cursor = await db.execute(
                "SELECT user_id FROM user_society WHERE society_name = ?",
                (society_name,)
            )
            members = await cursor.fetchall()

            if not members:
                return None

            # 计算每个成员的资产
            top_user = None
            top_asset = -1

            for (uid,) in members:
                asset = await self._get_user_asset(uid)
                total = asset[0]  # 总资产
                if total > top_asset:
                    top_asset = total
                    top_user = uid

            if top_user:
                # 获取昵称
                cursor = await db.execute(
                    "SELECT nickname FROM user_info WHERE user_id = ?",
                    (top_user,)
                )
                row = await cursor.fetchone()
                nickname = row[0] if row and row[0] else mask_user_id(top_user)
                return (top_user, top_asset, nickname)

            return None
    
    async def _get_user_asset(self, user_id: str) -> tuple:
        """获取用户资产"""
        async with aiosqlite.connect(self.db_path) as db:
            # 获取现金和银行存款
            cursor = await db.execute(
                "SELECT balance, bank_balance FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return (0, 0, 0, 0)
            
            # 安全转换
            try:
                cash = int(row[0]) if row[0] else 0
            except (ValueError, TypeError):
                cash = 0
            try:
                bank = int(row[1]) if row[1] else 0
            except (ValueError, TypeError):
                bank = 0
            
            # 计算股票市值
            cursor = await db.execute(
                """SELECT COALESCE(SUM(sh.remaining * sp.current_price), 0)
                   FROM stock_holdings sh
                   JOIN stock_prices sp ON sh.stock_name = sp.stock_name
                   WHERE sh.user_id = ? AND sh.remaining > 0 AND sp.delisted = 0""",
                (user_id,)
            )
            row = await cursor.fetchone()
            stock = int(row[0]) if row and row[0] else 0
        
        return cash + bank + stock, cash, bank, stock
    
    async def get_society_benefit_detail(self, society_name: str) -> dict:
        """获取结社福利详情（用于看板展示）"""
        async with aiosqlite.connect(self.db_path) as db:
            if society_name == "拜月结社":
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM user_society WHERE society_name = '拜月结社'"
                )
                member_count = await cursor.fetchone()
                member_count = member_count[0] if member_count else 0
                return {
                    "type": "签到奖励",
                    "detail": f"额外增加{member_count}星声+{member_count}%星声",
                    "current": member_count
                }
            
            elif society_name == "负资产结社":
                cursor = await db.execute("SELECT COUNT(*) FROM user_society")
                total_members = await cursor.fetchone()
                total_members = total_members[0] if total_members else 1
                
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM user_society WHERE society_name = '负资产结社'"
                )
                member_count = await cursor.fetchone()
                member_count = member_count[0] if member_count else 0
                
                ratio = (member_count / total_members) * 100
                interest_increase = max(0, 25 - ratio)
                return {
                    "type": "银行利率",
                    "detail": f"增加{interest_increase:.1f}%",
                    "current": interest_increase
                }
            
            elif society_name == "千衢结社":
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM user_society WHERE society_name = '千衢结社'"
                )
                member_count = await cursor.fetchone()
                member_count = member_count[0] if member_count else 0
                
                rich_avg = await self._get_rich_average_asset(db)
                wage_increase = member_count * 0.0001 * rich_avg
                return {
                    "type": "工资增加",
                    "detail": f"每小时增加约{int(wage_increase)}星声",
                    "current": int(wage_increase)
                }
            
            elif society_name == "弗糯结社":
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM user_society WHERE society_name = '弗糯结社'"
                )
                member_count = await cursor.fetchone()
                member_count = member_count[0] if member_count else 0
                dividend_increase = member_count * 0.1
                return {
                    "type": "股票福利",
                    "detail": f"交易无手续费，分红增加{dividend_increase}%",
                    "current": dividend_increase
                }
        
        return {}
    
    async def _check_society_top_achievement(self, user_id: str, society_name: str):
        """检查并授予结社第一成就"""
        achievement_map = {
            "拜月结社": "top_yue",
            "负资产结社": "top_fu",
            "千衢结社": "top_qian",
            "弗糯结社": "top_nuo"
        }

        achievement_id = achievement_map.get(society_name)
        if not achievement_id:
            return

        async with aiosqlite.connect(self.db_path) as db:
            # 检查是否已获得
            cursor = await db.execute(
                "SELECT 1 FROM user_achievements WHERE user_id = ? AND achievement_id = ?",
                (user_id, achievement_id)
            )
            if await cursor.fetchone():
                return

            # 授予成就
            await db.execute(
                "INSERT INTO user_achievements (user_id, achievement_id, obtain_time) VALUES (?, ?, ?)",
                (user_id, achievement_id, now_str())
            )
            await db.commit()
