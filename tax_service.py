"""
税收服务模块
"""
import os
import sys
# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import List, Tuple, Optional
from datetime import datetime
import aiosqlite
from config import CONFIG

def mask_id(uid: str) -> str:
    if len(uid) <= 4:
        return uid
    return uid[:3] + "***" + uid[-2:]


class TaxService:
    """税收服务"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def collect_tax(self) -> Optional[Tuple]:
        """收取每日税收"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM tax_pool WHERE date = ?", (today,)
            )
            if await cursor.fetchone():
                return None
            
            # 计算贫富差距
            all_assets = await self._get_all_assets(db)
            wealth_list = [w for _, w in all_assets if w > 0]
            
            if len(wealth_list) >= 5:
                wealth_list.sort(reverse=True)
                rich_avg = sum(wealth_list[:max(1, len(wealth_list)//5)]) // max(1, len(wealth_list)//5)
                poor_avg = sum(wealth_list[-max(1, len(wealth_list)//5):]) // max(1, len(wealth_list)//5)
                poor_avg = max(1, poor_avg)
                wealth_ratio = rich_avg / poor_avg
            else:
                wealth_ratio, rich_avg, poor_avg = 1.0, 0, 0
            
            extra_rate = wealth_ratio / CONFIG.WEALTH_GAP_DIVISOR if wealth_ratio > 1 else 0
            
            # 获取前10名
            sorted_assets = sorted(all_assets, key=lambda x: x[1], reverse=True)[:10]
            
            if not sorted_assets or sorted_assets[0][1] <= 0:
                await db.execute(
                    """INSERT INTO tax_pool (date, total_tax, bonus_pool, top10_list, wealth_gap_ratio)
                        VALUES (?, 0, 0, ?, ?)""",
                    (today, "无人上榜", wealth_ratio)
                )
                await db.commit()
                return (0, 0, [], 0, wealth_ratio)
            
            total_tax = 0
            details = []
            
            for i, (uid, total_wealth) in enumerate(sorted_assets):
                if i >= len(CONFIG.TAX_RATES):
                    break
                if total_wealth <= 0:
                    continue
                
                rate = min(CONFIG.TAX_RATES[i] + extra_rate, CONFIG.MAX_TAX_RATE)
                tax = int(total_wealth * rate)
                
                if tax <= 0:
                    continue
                
                # 扣税
                user = await self._get_user(db, uid)
                cash, bank = user["balance"], user["bank_balance"]
                
                if cash >= tax:
                    new_cash, new_bank = cash - tax, bank
                else:
                    new_cash = 0
                    new_bank = max(0, bank - (tax - cash))
                
                await db.execute(
                    "UPDATE users SET balance = ?, bank_balance = ? WHERE user_id = ?",
                    (new_cash, new_bank, uid)
                )
                
                total_tax += tax
                details.append(f"第{i+1}名({mask_id(uid)}):-{tax}")
            
            bonus_pool = int(total_tax * 0.5)
            
            await db.execute(
                """INSERT INTO tax_pool 
                    (date, total_tax, bonus_pool, claimed, top10_list, wealth_gap_ratio, extra_tax_rate)
                    VALUES (?, ?, ?, 0, ?, ?, ?)""",
                (today, total_tax, bonus_pool, " | ".join(details), wealth_ratio, extra_rate)
            )
            await db.commit()
            
            return (total_tax, bonus_pool, details, extra_rate, wealth_ratio)
    
    async def claim_tax_bonus(self, user_id: str) -> Tuple[int, int]:
        """领取税收分红"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT bonus_pool, claimed FROM tax_pool WHERE date = ?",
                (today,)
            )
            row = await cursor.fetchone()
            
            if not row or row[0] <= 0:
                return 0, 0
            
            bonus_pool, claimed = row
            remaining = bonus_pool - claimed
            
            if remaining <= 0:
                return 0, 0
            
            share = min(remaining, bonus_pool // 50)
            if share <= 0:
                share = remaining
            
            await db.execute(
                "UPDATE tax_pool SET claimed = claimed + ? WHERE date = ?",
                (share, today)
            )
            await db.commit()
            
            return share, remaining - share
    
    async def _get_all_assets(self, db) -> List[Tuple[str, int]]:
        """获取所有用户资产"""
        cursor = await db.execute("SELECT user_id FROM users")
        users = await cursor.fetchall()
        
        result = []
        for (uid,) in users:
            total = await self._get_user_total_asset(db, uid)
            result.append((uid, total))
        
        return result
    
    async def _get_user_total_asset(self, db, user_id: str) -> int:
        """获取用户总资产"""
        # 获取现金和银行存款
        cursor = await db.execute(
            "SELECT balance, bank_balance FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            return 0
        
        # 安全转换数值字段
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
        
        return cash + bank + stock
    
    async def _get_user(self, db, user_id: str) -> dict:
        """获取用户信息"""
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        
        if row:
            # 安全转换数值字段
            try:
                balance = int(row[1]) if len(row) > 1 and row[1] else 0
            except (ValueError, TypeError):
                balance = 0
            try:
                bank_balance = int(row[2]) if len(row) > 2 and row[2] else 0
            except (ValueError, TypeError):
                bank_balance = 0
            try:
                last_signin_date = row[3] if len(row) > 3 else None
            except:
                last_signin_date = None
            try:
                consecutive = int(row[4]) if len(row) > 4 and row[4] else 0
            except (ValueError, TypeError):
                consecutive = 0
            return {
                "user_id": row[0],
                "balance": balance,
                "bank_balance": bank_balance,
                "last_signin_date": last_signin_date,
                "consecutive_days": consecutive
            }
        
        # 如果用户不存在，创建用户
        await db.execute(
            "INSERT INTO users (user_id) VALUES (?)", (user_id,)
        )
        await db.commit()
        
        return {
            "user_id": user_id,
            "balance": 0,
            "bank_balance": 0,
            "last_signin_date": None,
            "consecutive_days": 0
        }