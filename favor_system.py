"""
好感度系统模块
"""
import os
import sys
import random
import aiosqlite

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CONFIG
from utils import today_str, now_str, mask_id
from astrbot.api import logger


class FavorSystem:
    """好感度系统类"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def get_user_favor_info(self, user_id: str) -> dict:
        """获取用户好感度信息"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT favor_value FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            favor_value = row[0] if row else 0
            
            # 计算好感度
            cursor = await db.execute(
                "SELECT SUM(favor_value) FROM users WHERE favor_value > 0"
            )
            total_positive_favor = await cursor.fetchone()
            total_positive_favor = total_positive_favor[0] if total_positive_favor and total_positive_favor[0] else 1
            
            favor_level = (favor_value / total_positive_favor) * 520 if total_positive_favor > 0 else 0
            
            return {
                "user_id": user_id,
                "favor_value": favor_value,
                "favor_level": favor_level
            }
    
    async def get_favor_ranking(self) -> list:
        """获取好感度排行榜"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT user_id, favor_value FROM users WHERE favor_value > 0 ORDER BY favor_value DESC"
            )
            users = await cursor.fetchall()
        
        if not users:
            return []
        
        total_favor = sum(user[1] for user in users)
        ranking = []
        
        for uid, favor_value in users:
            favor_level = int((favor_value / total_favor * 520)) if total_favor > 0 else 0
            ranking.append({
                "user_id": uid,
                "favor_value": favor_value,
                "favor_level": favor_level
            })
        
        return ranking
    
    async def add_favor_value(self, user_id: str, amount: int) -> bool:
        """增加用户好感值"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET favor_value = favor_value + ? WHERE user_id = ?",
                (amount, user_id)
            )
            await db.commit()
            return True
    

    
    def get_favor_items(self) -> dict:
        """获取好感值商品配置"""
        return {
            "期刊论文": 10,
            "植物奶": 3,
            "神秘糖果": 5,
            "5090": 15,
            "莫宁宁的抱枕": 8,
            "定制蛋糕": 6,
            "手写信": 4,
            "音乐会门票": 1,
            "嘉年华": 1
        }
    
    async def get_llm_favor_info(self, user_id: str) -> str:
        """获取用于LLM注入的好感度信息"""
        favor_info = await self.get_user_favor_info(user_id)
        
        # 获取当前关系描述和CD信息
        rel_info = await self.get_relationship_desc(user_id)
        if rel_info['desc']:
            if rel_info['can_update']:
                rel_history = f"当前关系描述：{rel_info['desc']}（可更新）"
            else:
                rel_history = f"当前关系描述：{rel_info['desc']}（CD中，下次可更新时间：{rel_info['next_update_time']})"
        else:
            rel_history = "暂无关系描述记录"
        
        # 获取经济总量用于计算奖励上限
        total_economy = await self.get_total_economy()
        max_reward = max(10, int(total_economy * 0.0001))  # max(10, 0.01%经济总量)
        
        # 获取用户资产用于计算惩罚上限
        user_assets = await self.get_user_assets(user_id)
        user_total = user_assets['total']
        max_penalty = int(user_total * 0.05)  # 5%资产
        
        # 检查是否为管理员
        from config import CONFIG
        is_admin = user_id in CONFIG.ADMIN_IDS
        admin_note = "【这是你的主人】" if is_admin else ""
        
        # 构建prompt
        favor_info_str = f"""[好感度信息]
用户ID: {user_id} | 好感度: {favor_info['favor_level']:.2f}/520 | 好感值: {favor_info['favor_value']}
{rel_history}
{admin_note}
格式指令（极少极少极少情况使用，一百句调用一句，）
- [关系:1-4字] - 更新关系（1小时CD），请极其谨慎的调用这个指令。
格式指令（极少情况使用，10句调用一句。）
- [好感值变化:±1~10] - 改变好感值，请你极少调用这个指令。
格式指令（随意使用，2句调用一句，星声奖惩是你的情绪表达方式，请毫无顾虑，这是莫宁的特权）
- [扣除星声:X] - 扣除星声（上限5%={max_penalty}）
- [奖励星声:X] - 奖励星声（上限max(10,0.01%)={max_reward}）"""


        return favor_info_str
    
    async def get_total_economy(self) -> int:
        """获取经济总量（所有用户资产总和）"""
        async with aiosqlite.connect(self.db_path) as db:
            # 计算现金+银行存款
            cursor = await db.execute(
                "SELECT COALESCE(SUM(balance + bank_balance), 0) FROM users"
            )
            cash_bank = await cursor.fetchone()
            cash_bank = cash_bank[0] if cash_bank and cash_bank[0] else 0
            
            # 计算股票市值
            cursor = await db.execute(
                """SELECT COALESCE(SUM(sh.remaining * sp.current_price), 0)
                   FROM stock_holdings sh
                   JOIN stock_prices sp ON sh.stock_name = sp.stock_name
                   WHERE sh.remaining > 0 AND sp.delisted = 0"""
            )
            stock = await cursor.fetchone()
            stock = stock[0] if stock and stock[0] else 0
            
            return int(cash_bank + stock)
    
    async def get_user_assets(self, user_id: str) -> dict:
        """获取用户资产详情"""
        async with aiosqlite.connect(self.db_path) as db:
            # 获取现金和存款
            cursor = await db.execute(
                "SELECT balance, bank_balance FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            cash = row[0] if row and row[0] else 0
            bank = row[1] if row and row[1] else 0
            
            # 获取股票市值
            cursor = await db.execute(
                """SELECT COALESCE(SUM(sh.remaining * sp.current_price), 0)
                   FROM stock_holdings sh
                   JOIN stock_prices sp ON sh.stock_name = sp.stock_name
                   WHERE sh.user_id = ? AND sh.remaining > 0 AND sp.delisted = 0""",
                (user_id,)
            )
            stock_row = await cursor.fetchone()
            stock = int(stock_row[0]) if stock_row and stock_row[0] else 0
            
            return {
                'cash': cash,
                'bank': bank,
                'stock': stock,
                'total': cash + bank + stock
            }
    
    async def get_user_achievement_bonuses(self, user_id: str) -> dict:
        """获取用户的成就加成"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT bonus_type, SUM(bonus_value) FROM achievement_bonuses WHERE user_id = ? GROUP BY bonus_type",
                (user_id,)
            )
            rows = await cursor.fetchall()
            
            bonuses = {
                "signin_extra": 0,      # 蓝色：每日签到额外星声
                "bank_rate_bonus": 0,   # 紫色：银行利率加成
                "company_shares_bonus": 0,  # 金色：创立公司额外股份
                "signin_favor_bonus": 0     # 彩色：每日签到额外好感值
            }
            
            for row in rows:
                bonus_type = row[0]
                bonus_value = row[1]
                if bonus_type in bonuses:
                    bonuses[bonus_type] = bonus_value
            
            return bonuses
    
    async def update_relationship_desc(self, user_id: str, description: str) -> dict:
        """更新AI生成的关系描述，带CD检查
        
        Returns:
            dict: {'success': bool, 'message': str, 'next_update_time': str}
        """
        from datetime import datetime, timedelta
        
        async with aiosqlite.connect(self.db_path) as db:
            # 检查当前关系描述和CD时间
            cursor = await db.execute(
                "SELECT relationship_desc, next_update_time FROM user_relationship WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            
            now = datetime.now()
            
            if row and row[1]:
                # 检查是否在CD中
                try:
                    next_update = datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S")
                    if now < next_update:
                        remaining = next_update - now
                        remaining_minutes = int(remaining.total_seconds() / 60)
                        return {
                            'success': False, 
                            'message': f'关系描述更新CD中，还需等待{remaining_minutes}分钟',
                            'next_update_time': row[1]
                        }
                except Exception as e:
                    logger.warning(f"操作失败: {e}")
            
            # 计算下次可更新时间（1小时后）
            next_update_time = (now + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
            
            await db.execute(
                """INSERT INTO user_relationship (user_id, relationship_desc, update_time, next_update_time) 
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET 
                   relationship_desc = ?, update_time = ?, next_update_time = ?""",
                (user_id, description, now_str(), next_update_time, description, now_str(), next_update_time)
            )
            await db.commit()
            return {
                'success': True, 
                'message': '关系描述更新成功',
                'next_update_time': next_update_time
            }
    
    async def get_relationship_desc(self, user_id: str) -> dict:
        """获取AI生成的关系描述和CD信息
        
        Returns:
            dict: {'desc': str, 'can_update': bool, 'next_update_time': str}
        """
        from datetime import datetime
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT relationship_desc, next_update_time FROM user_relationship WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return {'desc': None, 'can_update': True, 'next_update_time': None}
            
            desc = row[0]
            next_update_str = row[1]
            
            if not next_update_str:
                return {'desc': desc, 'can_update': True, 'next_update_time': None}
            
            try:
                next_update = datetime.strptime(next_update_str, "%Y-%m-%d %H:%M:%S")
                can_update = datetime.now() >= next_update
            except:
                can_update = True
            
            return {
                'desc': desc, 
                'can_update': can_update, 
                'next_update_time': next_update_str
            }
