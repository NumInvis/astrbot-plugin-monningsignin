"""工作服务模块"""
import os
import sys
# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import aiosqlite
import random
from datetime import datetime
from config import CONFIG


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
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
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
            now = datetime.now()
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
            now = datetime.now()
            hours = int((now - last_time).total_seconds() // 3600)
        except:
            hours = 0
        
        if hours <= 0:
            return {"success": False, "message": "工作未满1小时，暂无工资可领"}
        
        # 计算工资
        total_earnings = 0
        min_pay = int(config.get('min', 0))
        max_pay = int(config.get('max', 0))
        for _ in range(hours):
            hourly = random.randint(min_pay, max_pay)
            total_earnings += hourly
        
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (total_earnings, user_id)
            )
            await db.execute(
                """UPDATE user_work 
                   SET last_claim_time = ?, total_earned = total_earned + ?
                   WHERE user_id = ?""",
                (now_str, total_earnings, user_id)
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
            "new_balance": new_balance
        }
