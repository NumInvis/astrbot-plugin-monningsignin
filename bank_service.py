"""银行服务模块"""
import os
import sys
# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import aiosqlite
from datetime import datetime, timedelta, timezone
from config import CONFIG
from astrbot.api import logger


def get_beijing_time() -> datetime:
    """获取北京时间（UTC+8）"""
    utc_now = datetime.now(timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    return utc_now.astimezone(beijing_tz)


def today_str() -> str:
    """获取今天的日期字符串（北京时间）"""
    return get_beijing_time().strftime("%Y-%m-%d")


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

    async def _get_rate(self, db, user_id: str) -> float:
        """获取用户银行存款利率（内部方法）"""
        has_vip = await self.has_vip_card(user_id)
        base_rate = CONFIG.BANK_VIP_RATE if has_vip else CONFIG.BANK_NORMAL_RATE

        # 应用紫色成就加成
        cursor = await db.execute(
            "SELECT SUM(bonus_value) FROM achievement_bonuses WHERE user_id = ? AND bonus_type = 'bank_rate_bonus'",
            (user_id,)
        )
        bonus_result = await cursor.fetchone()
        rate_bonus = bonus_result[0] if bonus_result and bonus_result[0] else 0

        # 负资产结社福利
        fu_bonus = 0.0
        cursor = await db.execute(
            "SELECT society_name FROM user_society WHERE user_id = ?",
            (user_id,)
        )
        society_row = await cursor.fetchone()
        if society_row and society_row[0] == "负资产结社":
            # 计算负资产结社福利：银行利率增加25-x%，x为负资产结社人数占比
            cursor = await db.execute("SELECT COUNT(*) FROM user_society")
            total_members = await cursor.fetchone()
            total_members = total_members[0] if total_members else 1
            
            cursor = await db.execute(
                "SELECT COUNT(*) FROM user_society WHERE society_name = '负资产结社'"
            )
            member_count = await cursor.fetchone()
            member_count = member_count[0] if member_count else 0
            
            ratio = (member_count / total_members) * 100
            fu_bonus = max(0, 25 - ratio) / 100.0  # 转换为小数

        return base_rate + rate_bonus + fu_bonus

    async def _calc_interest(self, db, user_id: str, bank: int, rate: float) -> tuple[int, float]:
        """计算银行利息（内部方法）"""
        if bank <= 0:
            return bank, rate

        cursor = await db.execute(
            "SELECT bank_last_date FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        last_date = row[0] if row and row[0] else today_str()

        if last_date == today_str():
            return bank, rate

        # 计算复利
        try:
            d1 = datetime.strptime(last_date, "%Y-%m-%d")
            d2 = datetime.strptime(today_str(), "%Y-%m-%d")
            days = (d2 - d1).days
            if days > 0:
                new_balance = int(bank * ((1 + rate) ** days))
                await db.execute(
                    "UPDATE users SET bank_balance = ?, bank_last_date = ? WHERE user_id = ?",
                    (new_balance, today_str(), user_id)
                )
                return new_balance, rate
        except Exception as e:
            logger.warning(f"日期解析失败: {e}")

        return bank, rate
    
    async def update_bank_interest(self, user_id: str) -> tuple[int, float]:
        """更新银行利息"""
        has_vip = await self.has_vip_card(user_id)
        base_rate = CONFIG.BANK_VIP_RATE if has_vip else CONFIG.BANK_NORMAL_RATE
        
        async with aiosqlite.connect(self.db_path) as db:
            # 应用紫色成就加成：银行存款利率永久性提升
            cursor = await db.execute(
                "SELECT SUM(bonus_value) FROM achievement_bonuses WHERE user_id = ? AND bonus_type = 'bank_rate_bonus'",
                (user_id,)
            )
            bonus_result = await cursor.fetchone()
            rate_bonus = bonus_result[0] if bonus_result and bonus_result[0] else 0
            
            # 负资产结社福利
            fu_bonus = 0.0
            cursor = await db.execute(
                "SELECT society_name FROM user_society WHERE user_id = ?",
                (user_id,)
            )
            society_row = await cursor.fetchone()
            if society_row and society_row[0] == "负资产结社":
                cursor = await db.execute("SELECT COUNT(*) FROM user_society")
                total_members = await cursor.fetchone()
                total_members = total_members[0] if total_members else 1
                
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM user_society WHERE society_name = '负资产结社'"
                )
                member_count = await cursor.fetchone()
                member_count = member_count[0] if member_count else 0
                
                ratio = (member_count / total_members) * 100
                fu_bonus = max(0, 25 - ratio) / 100.0
        
        rate = base_rate + rate_bonus + fu_bonus
        
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
            except Exception as e:
                logger.warning(f"日期解析失败: {e}")
            
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
        # 使用事务原子操作检查余额并存款
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                # 检查余额
                cursor = await db.execute(
                    "SELECT balance, bank_balance FROM users WHERE user_id = ?",
                    (user_id,)
                )
                row = await cursor.fetchone()
                if not row:
                    await db.execute("ROLLBACK")
                    return {"success": False, "message": "用户不存在"}
                
                try:
                    balance = int(row[0]) if row[0] else 0
                    bank = int(row[1]) if row[1] else 0
                except (ValueError, TypeError):
                    balance = 0
                    bank = 0
                
                if balance < amount:
                    await db.execute("ROLLBACK")
                    return {"success": False, "message": f"抽卡资源不足！当前：{format_num(balance)}星声"}
                
                # 计算利息
                rate = await self._get_rate(db, user_id)
                bank, _ = await self._calc_interest(db, user_id, bank, rate)
                
                # 执行存款
                new_bank = bank + amount
                new_cash = balance - amount
                rate_pct = int(rate * 100)
                
                await db.execute(
                    "UPDATE users SET balance = ?, bank_balance = ?, bank_last_date = ? WHERE user_id = ?",
                    (new_cash, new_bank, today_str(), user_id)
                )
                await db.execute("COMMIT")
            except Exception as e:
                await db.execute("ROLLBACK")
                logger.error(f"存款失败: {e}")
                return {"success": False, "message": "存款失败，请稍后重试"}
        
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
        # 使用事务原子操作
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                # 更新利息并获取当前余额
                rate = await self._get_rate(db, user_id)
                cursor = await db.execute(
                    "SELECT balance, bank_balance FROM users WHERE user_id = ?",
                    (user_id,)
                )
                row = await cursor.fetchone()
                if not row:
                    await db.execute("ROLLBACK")
                    return {"success": False, "message": "用户不存在"}

                try:
                    balance = int(row[0]) if row[0] else 0
                    bank = int(row[1]) if row[1] else 0
                except (ValueError, TypeError):
                    balance = 0
                    bank = 0

                # 计算利息
                bank, _ = await self._calc_interest(db, user_id, bank, rate)

                # 检查存款余额
                if bank < amount:
                    await db.execute("ROLLBACK")
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
                await db.execute(
                    "UPDATE users SET balance = ?, bank_balance = ? WHERE user_id = ?",
                    (new_cash, new_bank, user_id)
                )
                await db.execute("COMMIT")

                return {
                    "success": True,
                    "amount": amount,
                    "fee": fee,
                    "actual": actual,
                    "new_bank": new_bank,
                    "new_cash": new_cash,
                    "has_vip": has_vip
                }
            except Exception as e:
                await db.execute("ROLLBACK")
                logger.error(f"取款失败: {e}")
                return {"success": False, "message": "取款失败，请稍后重试"}
