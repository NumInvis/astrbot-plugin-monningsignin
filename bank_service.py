"""银行服务模块"""
import aiosqlite
from datetime import datetime
from astrbot.api import logger

from config import CONFIG
from utils import today_str, format_num


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
            "SELECT COALESCE(SUM(bonus_value), 0) FROM achievement_bonuses WHERE user_id = ? AND bonus_type = 'bank_rate_bonus'",
            (user_id,)
        )
        rate_bonus = await cursor.fetchone()
        rate_bonus = rate_bonus[0] if rate_bonus else 0

        # 负资产结社福利
        fu_bonus = await self._get_fu_bonus(db, user_id)

        return base_rate + rate_bonus + fu_bonus

    async def _get_fu_bonus(self, db, user_id: str) -> float:
        """获取负资产结社福利加成"""
        cursor = await db.execute(
            "SELECT society_name FROM user_society WHERE user_id = ?",
            (user_id,)
        )
        society_row = await cursor.fetchone()
        if not society_row or society_row[0] != "负资产结社":
            return 0.0

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
        return max(0, 25 - ratio) / 100.0

    async def _calc_interest(self, db, user_id: str, bank: int, rate: float) -> int:
        """计算银行利息（内部方法）"""
        if bank <= 0:
            return bank

        cursor = await db.execute(
            "SELECT bank_last_date FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        last_date = row[0] if row and row[0] else today_str()

        if last_date == today_str():
            return bank

        # 计算复利
        try:
            d1 = datetime.strptime(last_date, "%Y-%m-%d")
            d2 = datetime.strptime(today_str(), "%Y-%m-%d")
            days = (d2 - d1).days
            if days > 0:
                # 限制最大天数防止溢出
                days = min(days, 365)
                new_balance = int(bank * ((1 + rate) ** days))
                await db.execute(
                    "UPDATE users SET bank_balance = ?, bank_last_date = ? WHERE user_id = ?",
                    (new_balance, today_str(), user_id)
                )
                await db.commit()
                return new_balance
        except Exception as e:
            logger.warning(f"日期解析失败: {e}")

        return bank

    async def update_bank_interest(self, user_id: str) -> tuple:
        """更新银行利息"""
        async with aiosqlite.connect(self.db_path) as db:
            rate = await self._get_rate(db, user_id)

            cursor = await db.execute(
                "SELECT bank_balance, bank_last_date FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()

            if not row:
                return 0, rate

            balance = int(row[0]) if row[0] else 0
            last_date = row[1]

            if balance <= 0:
                return balance, rate
            if last_date == today_str():
                return balance, rate

            # 计算复利
            new_balance = await self._calc_interest(db, user_id, balance, rate)
            return new_balance, rate

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
        async with aiosqlite.connect(self.db_path) as db:
            try:
                # 检查余额
                cursor = await db.execute(
                    "SELECT balance, bank_balance FROM users WHERE user_id = ?",
                    (user_id,)
                )
                row = await cursor.fetchone()
                if not row:
                    return {"success": False, "message": "用户不存在"}

                balance = int(row[0]) if row[0] else 0
                bank = int(row[1]) if row[1] else 0

                if balance < amount:
                    return {"success": False, "message": f"抽卡资源不足！当前：{format_num(balance)}星声"}

                # 计算利息
                rate = await self._get_rate(db, user_id)
                bank = await self._calc_interest(db, user_id, bank, rate)

                # 执行存款
                new_bank = bank + amount
                new_cash = balance - amount
                rate_pct = int(rate * 100)

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
            except Exception as e:
                logger.error(f"存款失败: {e}")
                return {"success": False, "message": "存款失败，请稍后重试"}

    async def withdraw(self, user_id: str, amount: int) -> dict:
        """取款"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                # 更新利息并获取当前余额
                rate = await self._get_rate(db, user_id)
                cursor = await db.execute(
                    "SELECT balance, bank_balance FROM users WHERE user_id = ?",
                    (user_id,)
                )
                row = await cursor.fetchone()
                if not row:
                    return {"success": False, "message": "用户不存在"}

                balance = int(row[0]) if row[0] else 0
                bank = int(row[1]) if row[1] else 0

                # 计算利息
                bank = await self._calc_interest(db, user_id, bank, rate)

                # 检查存款余额
                if bank < amount:
                    return {"success": False, "message": f"银行存款不足！当前存款：{format_num(bank)} 星声，需要：{format_num(amount)} 星声。请先使用 /存款 命令将现金存入银行。"}

                # 计算手续费
                has_vip = await self.has_vip_card(user_id)
                fee = 0 if has_vip else max(1, int(amount * CONFIG.BANK_WITHDRAW_FEE))

                actual = amount - fee
                new_bank = bank - amount
                new_cash = balance + actual

                # 更新余额
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
            except Exception as e:
                logger.error(f"取款失败: {e}")
                return {"success": False, "message": "取款失败，请稍后重试"}

    async def transfer(self, from_user: str, to_user: str, amount: int) -> dict:
        """转账 - 从现金余额扣除"""
        if from_user == to_user:
            return {"success": False, "message": "不能给自己转账"}

        async with aiosqlite.connect(self.db_path) as db:
            try:
                # 查询转出方现金余额
                cursor = await db.execute(
                    "SELECT balance FROM users WHERE user_id = ?",
                    (from_user,)
                )
                row = await cursor.fetchone()
                if not row:
                    return {"success": False, "message": "转出方用户不存在"}

                balance = int(row[0]) if row[0] else 0

                if balance < amount:
                    return {"success": False, "message": f"现金余额不足！当前：{format_num(balance)} 星声"}

                # 扣除转出方现金余额
                await db.execute(
                    "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                    (amount, from_user)
                )

                # 检查接收方是否存在
                cursor = await db.execute(
                    "SELECT 1 FROM users WHERE user_id = ?",
                    (to_user,)
                )
                if not await cursor.fetchone():
                    return {"success": False, "message": "接收方用户不存在"}

                # 增加接收方现金余额
                await db.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                    (amount, to_user)
                )
                await db.commit()

                return {
                    "success": True,
                    "amount": amount,
                    "message": f"成功转账 {format_num(amount)} 星声"
                }
            except Exception as e:
                logger.error(f"转账失败: {e}")
                return {"success": False, "message": "转账失败，请稍后重试"}
