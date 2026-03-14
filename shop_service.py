"""商店服务模块"""
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


def today_str() -> str:
    """获取今天的日期字符串（北京时间）"""
    return get_beijing_time().strftime("%Y-%m-%d")


def now_str() -> str:
    """获取当前时间的字符串（北京时间）"""
    return get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")


def format_num(n: int) -> str:
    return f"{n:,}"


class ShopService:
    """商店服务类"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def get_shop_items(self) -> dict:
        """获取商店物品列表"""
        return CONFIG.SHOP_ITEMS
    
    async def buy_item(self, user_id: str, item_name: str, count: int = 1) -> dict:
        """购买物品"""
        if item_name not in CONFIG.SHOP_ITEMS:
            return {"success": False, "message": f"商品不存在！可用：{', '.join(CONFIG.SHOP_ITEMS.keys())}"}
        
        item = CONFIG.SHOP_ITEMS[item_name]
        total_price = item['price'] * count
        today = today_str()
        
        async with aiosqlite.connect(self.db_path) as db:
            # 检查限购
            if item['daily_limit'] > 0:
                cursor = await db.execute(
                    "SELECT count FROM purchase_log WHERE user_id = ? AND item_name = ? AND purchase_date = ?",
                    (user_id, item_name, today)
                )
                row = await cursor.fetchone()
                bought_today = int(row[0]) if row else 0

                if bought_today + count > item['daily_limit']:
                    return {
                        "success": False,
                        "message": f"今日购买已达上限！\n今日已买：{bought_today}次\n限购：{item['daily_limit']}次/天"
                    }
            
            # 检查余额
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
            
            if balance < total_price:
                return {"success": False, "message": f"星声不足！需要{format_num(total_price)}，当前{format_num(balance)}"}
            
            # 扣款并添加物品
            new_balance = balance - total_price
            await db.execute(
                "UPDATE users SET balance = ? WHERE user_id = ?",
                (new_balance, user_id)
            )
            await db.execute(
                """INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, ?)
                   ON CONFLICT(user_id, item_name) DO UPDATE SET quantity = quantity + ?""",
                (user_id, item_name, count, count)
            )
            
            if item['daily_limit'] > 0:
                await db.execute(
                    """INSERT INTO purchase_log (user_id, item_name, purchase_date, count) VALUES (?, ?, ?, ?)
                       ON CONFLICT(user_id, item_name, purchase_date) DO UPDATE SET count = count + ?""",
                    (user_id, item_name, today, count, count)
                )
            
            await db.commit()
        
        return {
            "success": True,
            "item_name": item_name,
            "count": count,
            "total_price": total_price,
            "new_balance": new_balance
        }
    
    async def get_inventory(self, user_id: str) -> dict:
        """获取背包物品"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT item_name, quantity FROM inventory WHERE user_id = ? AND quantity > 0",
                (user_id,)
            )
            items = await cursor.fetchall()
            
            # 查询今日占卜次数
            cursor = await db.execute(
                "SELECT count FROM lottery_log WHERE user_id = ? AND date = ?",
                (user_id, today_str())
            )
            row = await cursor.fetchone()
            used_count = int(row[0]) if row else 0
            remaining = CONFIG.LOTTERY_LIMIT - used_count
        
        # 检查花朵成就
        flower_count = 0
        inventory_items = []
        for name, qty in items:
            inventory_items.append((name, qty))
            if name == "花花":
                flower_count = int(qty)
        
        return {
            "items": inventory_items,
            "flower_count": flower_count,
            "used_lottery_count": used_count,
            "remaining_lottery_count": remaining
        }
    
    async def do_lottery(self, user_id: str, bet: int, is_allin: bool = False) -> dict:
        """执行占卜"""
        async with aiosqlite.connect(self.db_path) as db:
            # 检查今日占卜次数
            cursor = await db.execute(
                "SELECT count FROM lottery_log WHERE user_id = ? AND date = ?",
                (user_id, today_str())
            )
            row = await cursor.fetchone()
            used_today = int(row[0]) if row else 0

            if used_today >= CONFIG.LOTTERY_LIMIT:
                return {
                    "success": False,
                    "message": f"今日占卜次数已用完！（{used_today}/{CONFIG.LOTTERY_LIMIT}次）"
                }

            # 检查占卜券
            cursor = await db.execute(
                "SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?",
                (user_id, "占卜券")
            )
            row = await cursor.fetchone()

            if not row or int(row[0]) <= 0:
                return {
                    "success": False,
                    "message": "你没有占卜券！去 /商店 购买"
                }

            ticket_count = int(row[0])

            # 检查余额
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
            
            if balance < bet:
                return {
                    "success": False,
                    "message": f"抽卡资源不足！需要{format_num(bet)}星声"
                }

            # 占卜逻辑 - 按照要求的概率分布
            # 概率分布：
            # 1%  桂冠       5.0x ~ 66.0x  (r == 1)
            # 5%  幸运       2.0x ~ 5.0x   (r <= 6)
            # 24% 成功占卜   1.1x ~ 2.0x   (r <= 30)
            # 35% 平平无奇   0.9x ~ 1.1x   (r <= 65)
            # 25% 失败       0.5x ~ 0.9x   (r <= 90)
            # 10% 水逆       0.01x ~ 0.5x  (r > 90)
            r = random.randint(1, 100)

            if r == 1:
                # 1% 桂冠: 5.0x ~ 66.0x
                multiplier = random.uniform(5.0, 66.0)
                result_type = "桂冠"
                result_emoji = "👑"
            elif r <= 6:
                # 5% 幸运: 2.0x ~ 5.0x
                multiplier = random.uniform(2.0, 5.0)
                result_type = "幸运"
                result_emoji = "🍀"
            elif r <= 30:
                # 24% 成功占卜: 1.1x ~ 2.0x
                multiplier = random.uniform(1.1, 2.0)
                result_type = "成功占卜"
                result_emoji = "✨"
            elif r <= 65:
                # 35% 平平无奇: 0.9x ~ 1.1x
                multiplier = random.uniform(0.9, 1.1)
                result_type = "平平无奇"
                result_emoji = "😐"
            elif r <= 90:
                # 25% 失败: 0.5x ~ 0.9x
                multiplier = random.uniform(0.5, 0.9)
                result_type = "失败"
                result_emoji = "💔"
            else:
                # 10% 水逆: 0.01x ~ 0.5x
                multiplier = random.uniform(0.01, 0.5)
                result_type = "水逆"
                result_emoji = "💀"

            final = int(bet * multiplier)
            if final < 1:
                final = 1

            profit = final - bet
            new_cash = balance + profit

            # 更新余额
            await db.execute(
                "UPDATE users SET balance = ? WHERE user_id = ?",
                (new_cash, user_id)
            )

            # 消耗占卜券
            await db.execute(
                "UPDATE inventory SET quantity = quantity - 1 WHERE user_id = ? AND item_name = ?",
                (user_id, "占卜券")
            )

            # 记录占卜次数
            await db.execute(
                """INSERT INTO lottery_log (user_id, date, count) VALUES (?, ?, 1)
                   ON CONFLICT(user_id, date) DO UPDATE SET count = count + 1""",
                (user_id, today_str())
            )

            await db.commit()

            new_used_count = used_today + 1
        
        return {
            "success": True,
            "result_type": result_type,
            "result_emoji": result_emoji,
            "multiplier": multiplier,
            "bet": bet,
            "final": final,
            "profit": profit,
            "new_cash": new_cash,
            "ticket_count": ticket_count - 1,
            "used_count": new_used_count,
            "remaining_count": CONFIG.LOTTERY_LIMIT - new_used_count,
            "is_allin": is_allin
        }
    
    async def get_lottery_probability(self, user_id: str) -> dict:
        """获取占卜概率分布"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT count FROM lottery_log WHERE user_id = ? AND date = ?",
                (user_id, today_str())
            )
            row = await cursor.fetchone()
            used_today = int(row[0]) if row else 0
            remaining = CONFIG.LOTTERY_LIMIT - used_today
        
        # 实际概率分布
        prob_dist = [
            ("5.0x ~ 66.0x", "1%", "桂冠", "👑"),
            ("2.0x ~ 5.0x", "5%", "幸运", "🍀"),
            ("1.1x ~ 2.0x", "24%", "成功占卜", "✨"),
            ("0.9x ~ 1.1x", "35%", "平平无奇", "😐"),
            ("0.5x ~ 0.9x", "25%", "失败", "💔"),
            ("0.01x ~ 0.5x", "10%", "水逆", "💀"),
        ]
        
        return {
            "remaining": remaining,
            "limit": CONFIG.LOTTERY_LIMIT,
            "prob_dist": prob_dist
        }
