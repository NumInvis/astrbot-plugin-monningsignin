"""
塔罗牌服务模块
"""
import random
import aiosqlite
from config import CONFIG
from utils import today_str, format_num
from base_service import BaseService


class TarotService(BaseService):
    """塔罗牌服务类"""

    def __init__(self, db_path: str):
        super().__init__(db_path)

    async def draw_tarot(self, user_id: str) -> dict:
        """
        抽取今日塔罗牌

        Returns:
            dict: {
                'success': bool,
                'already_drawn': bool,
                'card_name': str,
                'desc': str,
                'effect': dict,
                'effect_result': str,
                'message': str
            }
        """
        today = today_str()

        async with aiosqlite.connect(self.db_path) as db:
            # 检查今日是否已抽取
            cursor = await db.execute(
                "SELECT card_name FROM user_daily_tarot WHERE user_id = ? AND date = ?",
                (user_id, today)
            )
            row = await cursor.fetchone()

            if row:
                card_name = row[0]
                desc = CONFIG.TAROT_DESC.get(card_name, "")
                effect = CONFIG.TAROT_EFFECTS.get(card_name, {})

                return {
                    'success': True,
                    'already_drawn': True,
                    'card_name': card_name,
                    'desc': desc,
                    'effect': effect,
                    'effect_result': '',
                    'message': f"今日已抽取【{card_name}】"
                }

            # 随机抽取一张塔罗牌
            card_name = random.choice(CONFIG.TAROT_CARDS)
            desc = CONFIG.TAROT_DESC.get(card_name, "")
            effect = CONFIG.TAROT_EFFECTS.get(card_name, {})
            effect_type = effect.get('type', '')
            effect_value = effect.get('value', 0)

            # 保存记录
            await db.execute(
                """INSERT INTO user_daily_tarot (user_id, date, card_name, effect_type, effect_value)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, today, card_name, effect_type, str(effect_value))
            )
            await db.commit()

            # 应用效果
            effect_result = await self._apply_effect(user_id, effect)

            return {
                'success': True,
                'already_drawn': False,
                'card_name': card_name,
                'desc': desc,
                'effect': effect,
                'effect_result': effect_result,
                'message': f"抽取到【{card_name}】"
            }

    async def get_tarot_effect(self, user_id: str) -> dict:
        """
        获取今日塔罗牌效果

        Returns:
            dict: {
                'success': bool,
                'has_tarot': bool,
                'card_name': str,
                'desc': str,
                'effect_type': str,
                'effect_value': str,
                'effect_desc': str,
                'message': str
            }
        """
        today = today_str()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT card_name, effect_type, effect_value FROM user_daily_tarot WHERE user_id = ? AND date = ?",
                (user_id, today)
            )
            row = await cursor.fetchone()

            if not row:
                return {
                    'success': True,
                    'has_tarot': False,
                    'card_name': '',
                    'desc': '',
                    'effect_type': '',
                    'effect_value': '',
                    'effect_desc': '',
                    'message': '今日尚未抽取塔罗牌'
                }

            card_name, effect_type, effect_value = row
            desc = CONFIG.TAROT_DESC.get(card_name, "")
            effect_info = CONFIG.TAROT_EFFECTS.get(card_name, {})

            return {
                'success': True,
                'has_tarot': True,
                'card_name': card_name,
                'desc': desc,
                'effect_type': effect_type,
                'effect_value': effect_value,
                'effect_desc': effect_info.get('desc', ''),
                'message': f"今日塔罗牌：{card_name}"
            }

    async def _apply_effect(self, user_id: str, effect: dict) -> str:
        """
        应用塔罗牌效果

        Returns:
            str: 效果描述
        """
        effect_type = effect.get('type', '')
        effect_value = effect.get('value', 0)

        if effect_type == 'balance_reward':
            # 获得星声
            if isinstance(effect_value, list) and len(effect_value) == 2:
                amount = random.randint(effect_value[0], effect_value[1])
            else:
                amount = effect_value

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                    (amount, user_id)
                )
                await db.commit()
            return f"获得 {format_num(amount)} 星声"

        elif effect_type == 'balance_penalty':
            # 失去星声（按总资产比例）
            if isinstance(effect_value, list) and len(effect_value) == 2:
                rate = random.uniform(effect_value[0], effect_value[1])
            else:
                rate = effect_value

            # 获取用户总资产
            total = await self._get_user_total_asset(user_id)
            loss = int(total * rate)

            async with aiosqlite.connect(self.db_path) as db:
                # 优先从现金扣除
                cursor = await db.execute(
                    "SELECT balance FROM users WHERE user_id = ?",
                    (user_id,)
                )
                row = await cursor.fetchone()
                cash = int(row[0]) if row and row[0] else 0

                if cash >= loss:
                    await db.execute(
                        "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                        (loss, user_id)
                    )
                else:
                    # 现金不够，扣完现金再扣银行
                    remaining = loss - cash
                    await db.execute(
                        "UPDATE users SET balance = 0, bank_balance = bank_balance - ? WHERE user_id = ?",
                        (remaining, user_id)
                    )
                await db.commit()
            return f"失去 {format_num(loss)} 星声"

        elif effect_type == 'favor_value_reward':
            # 获得好感值
            if isinstance(effect_value, list) and len(effect_value) == 2:
                amount = random.randint(effect_value[0], effect_value[1])
            else:
                amount = effect_value

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE users SET favor_value = COALESCE(favor_value, 0) + ? WHERE user_id = ?",
                    (amount, user_id)
                )
                await db.commit()
            return f"获得 {amount} 点好感值"

        elif effect_type == 'favor_value_penalty':
            # 扣除好感值
            if isinstance(effect_value, list) and len(effect_value) == 2:
                amount = random.randint(effect_value[0], effect_value[1])
            else:
                amount = effect_value

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE users SET favor_value = MAX(0, COALESCE(favor_value, 0) - ?) WHERE user_id = ?",
                    (amount, user_id)
                )
                await db.commit()
            return f"扣除 {amount} 点好感值"

        elif effect_type == 'lottery_extra':
            # 增加占卜次数
            return f"占卜次数增加 {effect_value} 次"

        elif effect_type == 'lose_salary':
            # 失去工资
            if isinstance(effect_value, list) and len(effect_value) == 2:
                hours = random.randint(effect_value[0], effect_value[1])
            else:
                hours = effect_value
            return f"失去 {hours} 小时的当前工作工资"

        # 股票相关效果
        elif effect_type == 'stock_price_up':
            return "随机持仓股票上涨"
        elif effect_type == 'stock_price_down':
            return "随机持仓股票下跌"

        return ""

    async def _get_user_total_asset(self, user_id: str) -> int:
        """获取用户总资产（使用BaseService方法）"""
        total, _, _, _ = await self._get_user_asset(user_id)
        return total
