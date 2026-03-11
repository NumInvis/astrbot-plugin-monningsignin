"""银行服务模块"""
import os
import sys
# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import aiosqlite
from datetime import datetime
from config import CONFIG


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def format_num(n: int) -> str:
    return f"{n:,}"


class BankService:
    """银行服务类"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def has_vip_card(self, user_id: str) -> bool:
        """检查是否有贵宾卡"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?",
                (user_id, "莫塔里贵宾卡")
            )
            row = await cursor.fetchone()
            return row is not None and row[0] > 0
    
    async def update_bank_interest(self, user_id: str) -> tuple[int, float]:
        """更新银行利息"""
        has_vip = await self.has_vip_card(user_id)
        base_rate = CONFIG.BANK_VIP_RATE if has_vip else CONFIG.BANK_NORMAL_RATE
        
        # 应用紫色成就加成：银行存款利率永久性提升
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT SUM(bonus_value) FROM achievement_bonuses WHERE user_id = ? AND bonus_type = 'bank_rate_bonus'",
                (user_id,)
            )
            bonus_result = await cursor.fetchone()
            rate_bonus = bonus_result[0] if bonus_result and bonus_result[0] else 0
        
        rate = base_rate + rate_bonus
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT bank_balance, bank_last_date FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return 0, rate
            
            # 安全转换
            try:
                balance = int(row[0]) if row[0] else 0
            except (ValueError, TypeError):
                balance = 0
            
            last_date = row[1] if len(row) > 1 else None
            
            if balance <= 0:
                return balance, rate
            if last_date == today_str():
                return balance, rate
            
            # 计算复利
            try:
                d1 = datetime.strptime(last_date, "%Y-%m-%d")
                d2 = datetime.strptime(today_str(), "%Y-%m-%d")
                days = (d2 - d1).days
                if days > 0:
                    new_balance = int(balance * ((1 + rate) ** days))
                    await db.execute(
                        "UPDATE users SET bank_balance = ?, bank_last_date = ? WHERE user_id = ?",
                        (new_balance, today_str(), user_id)
                    )
                    await db.commit()
                    return new_balance, rate
            except:
                pass
            
            return balance, rate
    
    async def get_bank_info(self, user_id: str) -> dict:
        """获取银行信息"""
        bank, rate = await self.update_bank_interest(user_id)
        rate_pct = int(rate * 100)
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT balance FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            balance = int(row[0]) if row and row[0] else 0
        
        has_vip = await self.has_vip_card(user_id)
        
        return {
            "bank": bank,
            "balance": balance,
            "rate": rate,
            "rate_pct": rate_pct,
            "has_vip": has_vip
        }
    
    async def deposit(self, user_id: str, amount: int) -> dict:
        """存款"""
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
            
            if balance < amount:
                return {"success": False, "message": f"抽卡资源不足！当前：{format_num(balance)}星声"}
        
        # 更新利息并存款
        bank, rate = await self.update_bank_interest(user_id)
        new_bank = bank + amount
        new_cash = balance - amount
        rate_pct = int(rate * 100)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET balance = ?, bank_balance = ?, bank_last_date = ? WHERE user_id = ?",
                (new_cash, new_bank, today_str(), user_id)
            )
            await db.commit()
        
        has_vip = await self.has_vip_card(user_id)
        
        return {
            "success": True,
            "new_bank": new_bank,
            "new_cash": new_cash,
            "rate_pct": rate_pct,
            "has_vip": has_vip
        }
    
    async def withdraw(self, user_id: str, amount: int) -> dict:
        """取款"""
        # 更新利息
        bank, _ = await self.update_bank_interest(user_id)
        
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
            
            if bank < amount:
                return {"success": False, "message": f"存款不足！当前：{format_num(bank)}星声"}
        
        # 计算手续费
        has_vip = await self.has_vip_card(user_id)
        
        if has_vip:
            fee = 0
        else:
            fee = max(1, int(amount * CONFIG.BANK_WITHDRAW_FEE))
        
        actual = amount - fee
        new_bank = bank - amount
        new_cash = balance + actual
        
        # 更新余额
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET balance = ?, bank_balance = ? WHERE user_id = ?",
                (new_cash, new_bank, user_id)
            )
            await db.commit()
        
        return {
            "success": True,
            "amount": amount,
            "fee": fee,
            "actual": actual,
            "new_bank": new_bank,
            "new_cash": new_cash,
            "has_vip": has_vip
        }
