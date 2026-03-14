"""工作服务模块"""
import os
import sys
# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import aiosqlite
import random
from datetime import datetime, timedelta, timezone
from config import CONFIG


def get_beijing_time() -> datetime:
    """获取北京时间（UTC+8）"""
    utc_now = datetime.now(timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    return utc_now.astimezone(beijing_tz)


def format_num(n: int) -> str:
    return f"{n:,}"


class WorkService:
    """工作服务类"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def get_works(self) -> dict:
        """获取工作列表"""
        return CONFIG.WORKS
    
    async def apply_work(self, user_id: str, work_name: str) -> dict:
        """应聘工作"""
        if work_name not in CONFIG.WORKS:
            return {"success": False, "message": f"职业不存在！可选：{', '.join(CONFIG.WORKS.keys())}"}
        
        config = CONFIG.WORKS[work_name]
        price = config['price']
        
        # 检查余额
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT balance FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return {"success": False, "message": "用户不存在"}
            
            try:
                balance = int(row[0]) if row[0] else 0
            except (ValueError, TypeError):
                balance = 0
            
            if balance < price:
                return {"success": False, "message": f"星声不足！需要{format_num(price)}星声"}
        
        now = get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (price, user_id)
            )
            await db.execute(
                """INSERT INTO user_work (user_id, work_name, start_time, last_claim_time, total_earned)
                   VALUES (?, ?, ?, ?, 0)
                   ON CONFLICT(user_id) DO UPDATE SET 
                   work_name = ?, start_time = ?, last_claim_time = ?, total_earned = 0""",
                (user_id, work_name, now, now, work_name, now, now)
            )
            await db.commit()
        
        return {
            "success": True,
            "work_name": work_name,
            "emoji": config['emoji'],
            "price": price,
            "start_time": now
        }
    
    async def get_work_status(self, user_id: str) -> dict:
        """获取工作状态"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT work_name, start_time, last_claim_time, total_earned FROM user_work WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
        
        if not row:
            return {"success": False, "message": "你目前无业游民中...\n发送 /找工作 查看可应聘职位"}
        
        work_name, start_str, last_claim_str, total_earned = row
        config = CONFIG.WORKS.get(work_name, {})
        
        try:
            last_time = datetime.strptime(last_claim_str, "%Y-%m-%d %H:%M:%S")
            last_time = last_time.replace(tzinfo=timezone(timedelta(hours=8)))
            now = get_beijing_time()
            hours_passed = int((now - last_time).total_seconds() // 3600)
        except:
            hours_passed = 0
        
        if hours_passed < 0:
            hours_passed = 0
        
        avg_hourly = (int(config.get('min', 0)) + int(config.get('max', 0))) // 2
        pending = hours_passed * avg_hourly
        
        return {
            "success": True,
            "work_name": work_name,
            "emoji": config.get('emoji', '💼'),
            "desc": config.get('desc', ''),
            "hours_passed": hours_passed,
            "pending": pending,
            "total_earned": total_earned or 0,
            "last_claim_time": last_claim_str
        }
    
    async def _get_rich_average_asset(self, db) -> int:
        """获取富人阶级（前20%）玩家的平均资产"""
        cursor = await db.execute("SELECT user_id FROM users")
        users = await cursor.fetchall()
        
        if not users:
            return 0
        
        asset_list = []
        for (uid,) in users:
            # 获取用户资产
            cursor = await db.execute(
                "SELECT balance, bank_balance FROM users WHERE user_id = ?",
                (uid,)
            )
            row = await cursor.fetchone()
            if not row:
                continue
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
                (uid,)
            )
            stock_row = await cursor.fetchone()
            stock = int(stock_row[0]) if stock_row and stock_row[0] else 0
            
            total = cash + bank + stock
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
    
    async def claim_salary(self, user_id: str) -> dict:
        """领取工资"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT work_name, last_claim_time FROM user_work WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
        
        if not row:
            return {"success": False, "message": "你还没有工作！发送 /找工作 查看职位"}
        
        work_name, last_claim_str = row
        config = CONFIG.WORKS.get(work_name, {})
        
        try:
            last_time = datetime.strptime(last_claim_str, "%Y-%m-%d %H:%M:%S")
            last_time = last_time.replace(tzinfo=timezone(timedelta(hours=8)))
            now = get_beijing_time()
            hours = int((now - last_time).total_seconds() // 3600)
        except:
            hours = 0
        
        if hours <= 0:
            return {"success": False, "message": "工作未满1小时，暂无工资可领"}
        
        # 计算基础工资
        total_earnings = 0
        min_pay = int(config.get('min', 0))
        max_pay = int(config.get('max', 0))
        for _ in range(hours):
            hourly = random.randint(min_pay, max_pay)
            total_earnings += hourly
        
        # 千衢结社福利
        qian_bonus = 0
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT society_name FROM user_society WHERE user_id = ?",
                (user_id,)
            )
            society_row = await cursor.fetchone()
            if society_row and society_row[0] == "千衢结社":
                # 计算千衢结社福利
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM user_society WHERE society_name = '千衢结社'"
                )
                qian_count = await cursor.fetchone()
                qian_count = qian_count[0] if qian_count else 0
                
                # 获取富人阶级平均资产
                rich_avg = await self._get_rich_average_asset(db)
                qian_bonus = int(qian_count * 0.0001 * rich_avg * hours)
        
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        final_earnings = total_earnings + qian_bonus
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (final_earnings, user_id)
            )
            await db.execute(
                """UPDATE user_work 
                   SET last_claim_time = ?, total_earned = total_earned + ?
                   WHERE user_id = ?""",
                (now_str, final_earnings, user_id)
            )
            await db.commit()
            
            # 获取新余额
            cursor = await db.execute(
                "SELECT balance FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            new_balance = int(row[0]) if row and row[0] else 0
        
        return {
            "success": True,
            "work_name": work_name,
            "emoji": config.get('emoji', '💼'),
            "hours": hours,
            "total_earnings": total_earnings,
            "qian_bonus": qian_bonus,
            "final_earnings": final_earnings,
            "new_balance": new_balance
        }
