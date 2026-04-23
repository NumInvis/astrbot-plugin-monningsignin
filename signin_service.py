"""
签到服务模块
"""
from typing import Dict
from datetime import datetime
import aiosqlite
from astrbot.api import logger

from utils import today_str
from config import CONFIG
from base_service import BaseService


class SigninService(BaseService):
    """签到服务"""

    async def signin(self, user_id: str, percentile: float) -> Dict:
        """用户签到（使用事务保证原子性）"""
        today = today_str()
        logger.info(f"【签到】用户 {user_id} 开始签到，今日日期: {today}")

        async with aiosqlite.connect(self.db_path) as db:
            try:
                # 获取用户信息
                user = await self._get_user(user_id)
                logger.info(f"【签到】用户 {user_id} 信息: balance={user['balance']}, last_signin_date={user['last_signin_date']}")

                # 检查是否已签到
                if user["last_signin_date"] == today:
                    logger.info(f"【签到】用户 {user_id} 今日已签到")
                    return {
                        "success": False,
                        "message": "今日已签到",
                        "balance": user["balance"],
                        "consecutive_days": user["consecutive_days"]
                    }

                # 计算连续签到天数
                consecutive = self._calculate_consecutive_days(user, today)
                logger.info(f"【签到】用户 {user_id} 连续签到天数: {consecutive}")

                # 计算签到奖励
                rewards = await self._calculate_rewards(db, user_id, consecutive, percentile)
                logger.info(f"【签到】用户 {user_id} 奖励计算: base={rewards['base']}, total={rewards['total']}")

                # 更新用户数据
                new_balance = user["balance"] + rewards["total"]
                logger.info(f"【签到】用户 {user_id} 更新余额: {user['balance']} -> {new_balance}")
                await db.execute(
                    """UPDATE users
                       SET balance = ?,
                           last_signin_date = ?,
                           consecutive_days = ?,
                           favor_value = favor_value + ?
                       WHERE user_id = ?""",
                    (new_balance, today, consecutive, rewards["signin_favor_bonus"], user_id)
                )
                await db.commit()
                logger.info(f"【签到】用户 {user_id} 签到成功，新余额: {new_balance}")

                return {
                    "success": True,
                    "base": rewards["base"],
                    "bonus": rewards["bonus"],
                    "signin_extra": rewards["signin_extra"],
                    "signin_favor_bonus": rewards["signin_favor_bonus"],
                    "yue_bonus_fixed": rewards["yue_bonus_fixed"],
                    "yue_bonus": rewards["yue_bonus"],
                    "total": rewards["total"],
                    "balance": new_balance,
                    "consecutive_days": consecutive
                }
            except Exception as e:
                logger.error(f"【签到】用户 {user_id} 签到失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return {"success": False, "message": "签到失败，请稍后重试"}

    def _calculate_consecutive_days(self, user: Dict, today: str) -> int:
        """计算连续签到天数"""
        last_date = user["last_signin_date"]
        if not last_date:
            return 1

        try:
            last = datetime.strptime(last_date, "%Y-%m-%d")
            today_date = datetime.strptime(today, "%Y-%m-%d")
            days_diff = (today_date - last).days

            if days_diff == 1:
                return user["consecutive_days"] + 1
            else:
                return 1
        except (ValueError, TypeError) as e:
            logger.warning(f"日期解析失败: {e}")
            return 1

    async def _calculate_rewards(self, db, user_id: str, consecutive: int,
                                  percentile: float) -> Dict:
        """计算签到奖励"""
        # 基础奖励
        base = CONFIG.BASE_SIGNIN_REWARD
        bonus = int(base * (consecutive * 0.1))

        # 成就加成
        signin_extra = await self._get_achievement_bonus(db, user_id, 'signin_extra')
        signin_favor_bonus = await self._get_achievement_bonus(db, user_id, 'signin_favor_bonus')

        # 拜月结社福利
        yue_bonus_fixed, yue_bonus_percent = await self._get_yue_bonus(db, user_id)

        # 计算总奖励
        total_before_yue = base + bonus + signin_extra
        yue_bonus = int(total_before_yue * yue_bonus_percent)
        total = total_before_yue + yue_bonus_fixed + yue_bonus

        return {
            "base": base,
            "bonus": bonus,
            "signin_extra": signin_extra,
            "signin_favor_bonus": signin_favor_bonus,
            "yue_bonus_fixed": yue_bonus_fixed,
            "yue_bonus": yue_bonus,
            "total": total
        }

    async def _get_achievement_bonus(self, db, user_id: str, bonus_type: str) -> int:
        """获取成就加成"""
        cursor = await db.execute(
            """SELECT COALESCE(SUM(bonus_value), 0) FROM achievement_bonuses
               WHERE user_id = ? AND bonus_type = ?""",
            (user_id, bonus_type)
        )
        result = await cursor.fetchone()
        return int(result[0]) if result else 0

    async def _get_yue_bonus(self, db, user_id: str) -> tuple:
        """获取拜月结社福利"""
        cursor = await db.execute(
            "SELECT society_name FROM user_society WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()

        if not row or row[0] != "拜月结社":
            return 0, 0.0

        # 计算拜月结社人数
        cursor = await db.execute(
            "SELECT COUNT(*) FROM user_society WHERE society_name = '拜月结社'"
        )
        yue_count = await cursor.fetchone()
        yue_count = yue_count[0] if yue_count else 0

        return yue_count, yue_count / 100.0


