"""
签到服务模块
"""
import os
import sys
# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import Dict, Optional
from datetime import datetime, timedelta, timezone
import aiosqlite
import random


def get_beijing_time() -> datetime:
    """获取北京时间（UTC+8）"""
    utc_now = datetime.now(timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    return utc_now.astimezone(beijing_tz)


class SigninService:
    """签到服务"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def signin(self, user_id: str, percentile: float) -> Dict:
        """用户签到"""
        today = get_beijing_time().strftime("%Y-%m-%d")
        
        async with aiosqlite.connect(self.db_path) as db:
            # 获取用户信息
            user = await self._get_user(db, user_id)
            
            # 检查是否已签到
            if user["last_signin_date"] == today:
                return {
                    "success": False,
                    "message": "今日已签到",
                    "balance": user["balance"],
                    "consecutive_days": user["consecutive_days"]
                }
            
            # 计算连续签到天数
            last_date = user["last_signin_date"]
            if last_date:
                try:
                    last = datetime.strptime(last_date, "%Y-%m-%d")
                    today_date = datetime.strptime(today, "%Y-%m-%d")
                    days_diff = (today_date - last).days
                    
                    if days_diff == 1:
                        consecutive = user["consecutive_days"] + 1
                    else:
                        consecutive = 1
                except:
                    consecutive = 1
            else:
                consecutive = 1
            
            # 计算签到奖励
            try:
                # 动态导入并刷新模块
                import importlib
                import config
                importlib.reload(config)
                from config import CONFIG
                base = getattr(CONFIG, 'BASE_SIGNIN_REWARD', 100)
            except Exception as e:
                # 如果导入失败，使用默认值
                base = 100
            bonus = int(base * (consecutive * 0.1))
            
            # 计算成就加成
            # 蓝色成就：每日签到额外增加星声
            signin_extra = 0
            cursor = await db.execute(
                "SELECT SUM(bonus_value) FROM achievement_bonuses WHERE user_id = ? AND bonus_type = 'signin_extra'",
                (user_id,)
            )
            bonus_result = await cursor.fetchone()
            if bonus_result and bonus_result[0]:
                signin_extra = int(bonus_result[0])
            
            # 彩色成就：每日签到额外获得好感值
            signin_favor_bonus = 0
            cursor = await db.execute(
                "SELECT SUM(bonus_value) FROM achievement_bonuses WHERE user_id = ? AND bonus_type = 'signin_favor_bonus'",
                (user_id,)
            )
            favor_result = await cursor.fetchone()
            if favor_result and favor_result[0]:
                signin_favor_bonus = int(favor_result[0])
            
            # 拜月结社福利
            yue_bonus_fixed = 0
            yue_bonus_percent = 0.0
            cursor = await db.execute(
                "SELECT society_name FROM user_society WHERE user_id = ?",
                (user_id,)
            )
            society_row = await cursor.fetchone()
            if society_row and society_row[0] == "拜月结社":
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM user_society WHERE society_name = '拜月结社'"
                )
                yue_count = await cursor.fetchone()
                yue_count = yue_count[0] if yue_count else 0
                yue_bonus_fixed = yue_count
                yue_bonus_percent = yue_count / 100.0
            
            # 低保加成（根据排名）
            low_income_rate = max(0.1, percentile)  # 最低10%加成
            total_before_yue = base + bonus + signin_extra
            yue_bonus = int(total_before_yue * yue_bonus_percent)
            total = total_before_yue + yue_bonus_fixed + yue_bonus
            
            # 更新用户数据（余额）
            new_balance = user["balance"] + total
            
            # 更新用户数据（好感值 - 彩色成就加成）
            if signin_favor_bonus > 0:
                await db.execute(
                    "UPDATE users SET favor_value = favor_value + ? WHERE user_id = ?",
                    (signin_favor_bonus, user_id)
                )
            
            await db.execute(
                "UPDATE users SET balance = ?, last_signin_date = ?, consecutive_days = ? WHERE user_id = ?",
                (new_balance, today, consecutive, user_id)
            )
            await db.commit()
            
            return {
                "success": True,
                "base": base,
                "bonus": bonus,
                "signin_extra": signin_extra,  # 蓝色成就加成
                "signin_favor_bonus": signin_favor_bonus,  # 彩色成就加成
                "yue_bonus_fixed": yue_bonus_fixed,  # 拜月结社固定加成
                "yue_bonus": yue_bonus,  # 拜月结社百分比加成
                "total": total,
                "balance": new_balance,
                "consecutive_days": consecutive
            }
    
    async def _get_user(self, db, user_id: str) -> Dict:
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
