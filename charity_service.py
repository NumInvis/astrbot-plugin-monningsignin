"""慈善服务模块"""
import os
import sys
# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import aiosqlite
from config import CONFIG


def format_num(n: int) -> str:
    return f"{n:,}"


class CharityService:
    """慈善服务类"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def donate(self, user_id: str, amount: int) -> dict:
        """慈善捐款"""
        if amount <= 0:
            return {"success": False, "message": "捐款金额必须大于0"}
        
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
                return {"success": False, "message": f"余额不足！当前：{format_num(balance)}星声"}
        
        # 计算管理费和实际捐款
        fee = max(1, int(amount * CONFIG.CHARITY_FEE_RATE))
        actual_donation = amount - fee
        
        async with aiosqlite.connect(self.db_path) as db:
            # 扣款
            await db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (amount, user_id)
            )
            # 给慈善对象
            await db.execute(
                """INSERT INTO users (user_id, balance) VALUES (?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?""",
                (CONFIG.CHARITY_RECIPIENT, actual_donation, actual_donation)
            )
            await db.commit()
        
        new_balance = balance - amount
        
        return {
            "success": True,
            "amount": amount,
            "fee": fee,
            "actual_donation": actual_donation,
            "new_balance": new_balance
        }
