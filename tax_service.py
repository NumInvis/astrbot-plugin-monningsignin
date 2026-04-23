"""
税收服务模块 V2
实现新的收税逻辑：
1. 基础税收（前十名递减：20%, 18%...2%）
2. 额外平衡税收（高于中位数者：总资产/(中位数*888)%，最高80%）
3. 税收奖池（50%进入奖池，签到时分配）
"""
import os
import sys
# 确保插件目录在Python路径中
plugin_dir = os.path.dirname(os.path.abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

from typing import List, Tuple, Optional, Dict
import aiosqlite
from config import CONFIG
from utils import get_beijing_time, mask_id
from astrbot.api import logger
from stats_service import StatsService
from base_service import BaseService


class TaxService(BaseService):
    """税收服务 V2"""

    def __init__(self, db_path: str, stats_service=None):
        super().__init__(db_path)
        self.stats_service = stats_service
    
    async def init_table(self):
        """初始化税收相关表"""
        async with aiosqlite.connect(self.db_path) as db:
            # 税收池表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tax_pool (
                    date TEXT PRIMARY KEY,
                    total_tax INTEGER DEFAULT 0,
                    bonus_pool INTEGER DEFAULT 0,
                    bonus_claimed INTEGER DEFAULT 0,
                    top10_list TEXT,
                    median_wealth INTEGER DEFAULT 0,
                    player_count INTEGER DEFAULT 0,
                    details TEXT
                )
            """)
            # 用户税收记录表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_tax_record (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    base_tax INTEGER DEFAULT 0,
                    extra_tax INTEGER DEFAULT 0,
                    total_tax INTEGER DEFAULT 0,
                    wealth_before INTEGER DEFAULT 0,
                    UNIQUE(user_id, date)
                )
            """)
            await db.commit()
    
    async def collect_tax(self) -> Optional[Dict]:
        """收取每日税收
        
        Returns:
            {
                "total_tax": int,
                "bonus_pool": int,
                "player_count": int,
                "median_wealth": int,
                "top10_details": List[Dict],
                "extra_tax_details": List[Dict]
            }
        """
        today = get_beijing_time().strftime("%Y-%m-%d")
        
        async with aiosqlite.connect(self.db_path) as db:
            # 检查今日是否已收税
            cursor = await db.execute(
                "SELECT 1 FROM tax_pool WHERE date = ?", (today,)
            )
            if await cursor.fetchone():
                logger.info(f"今日({today})已收税，跳过")
                return None
            
            # 获取所有用户资产（使用统计服务，避免重复代码）
            all_assets = await self.stats_service.get_all_users_assets()
            player_count = len(all_assets)
            
            if player_count == 0:
                await db.execute(
                    """INSERT INTO tax_pool 
                        (date, total_tax, bonus_pool, player_count, median_wealth, top10_list, details)
                        VALUES (?, 0, 0, 0, 0, '无玩家', '无数据')""",
                    (today,)
                )
                await db.commit()
                return {
                    "total_tax": 0,
                    "bonus_pool": 0,
                    "player_count": 0,
                    "median_wealth": 0,
                    "top10_details": [],
                    "extra_tax_details": []
                }
            
            # 计算中位数
            sorted_totals = sorted([a["total"] for a in all_assets])
            median_wealth = self._calculate_median(sorted_totals)
            
            # 按资产排序
            all_assets.sort(key=lambda x: x["total"], reverse=True)
            
            total_tax = 0
            bonus_pool = 0
            top10_details = []
            extra_tax_details = []
            
            # 基础税率（前十名递减，从配置读取）
            base_rates = CONFIG.TOP10_TAX_RATES
            
            for idx, user_asset in enumerate(all_assets):
                user_id = user_asset["user_id"]
                total_wealth = user_asset["total"]
                cash = user_asset["cash"]
                bank = user_asset["bank"]
                
                if total_wealth <= 0:
                    continue
                
                base_tax = 0
                extra_tax = 0
                
                # 1. 基础税收（前十名）
                if idx < 10:
                    base_rate = base_rates[idx]
                    base_tax = int(total_wealth * base_rate)
                    top10_details.append({
                        "rank": idx + 1,
                        "user_id": user_id,
                        "wealth": total_wealth,
                        "rate": base_rate,
                        "tax": base_tax
                    })
                
                # 2. 额外平衡税收（高于中位数）
                if total_wealth > median_wealth and median_wealth > 0:
                    extra_rate = total_wealth / (median_wealth * CONFIG.EXTRA_TAX_MEDIAN_MULTIPLIER)
                    extra_rate = min(extra_rate, CONFIG.EXTRA_TAX_MAX_RATE)  # 最高80%
                    extra_tax = int(total_wealth * extra_rate)
                    extra_tax_details.append({
                        "user_id": user_id,
                        "wealth": total_wealth,
                        "median": median_wealth,
                        "rate": extra_rate,
                        "tax": extra_tax
                    })
                
                # 总税收
                user_total_tax = base_tax + extra_tax
                
                if user_total_tax > 0:
                    # 扣税（先扣现金，现金不够扣银行存款）
                    new_cash, new_bank = self._deduct_tax(cash, bank, user_total_tax)
                    
                    await db.execute(
                        "UPDATE users SET balance = ?, bank_balance = ? WHERE user_id = ?",
                        (new_cash, new_bank, user_id)
                    )
                    
                    # 记录税收详情
                    await db.execute(
                        """INSERT INTO user_tax_record 
                            (user_id, date, base_tax, extra_tax, total_tax, wealth_before)
                            VALUES (?, ?, ?, ?, ?, ?)""",
                        (user_id, today, base_tax, extra_tax, user_total_tax, total_wealth)
                    )
                    
                    total_tax += user_total_tax
            
            # 50%进入奖池
            bonus_pool = int(total_tax * 0.5)
            
            # 生成详情文本
            top10_text = " | ".join([
                f"第{d['rank']}名({mask_id(d['user_id'])}):-{d['tax']}"
                for d in top10_details
            ]) if top10_details else "无"
            
            details_text = f"总税收:{total_tax} | 奖池:{bonus_pool} | 中位数:{median_wealth}"
            
            await db.execute(
                """INSERT INTO tax_pool 
                    (date, total_tax, bonus_pool, bonus_claimed, player_count, median_wealth, top10_list, details)
                    VALUES (?, ?, ?, 0, ?, ?, ?, ?)""",
                (today, total_tax, bonus_pool, player_count, median_wealth, top10_text, details_text)
            )
            await db.commit()
            
            logger.info(f"收税完成：总税收={total_tax}, 奖池={bonus_pool}, 玩家数={player_count}")
            
            return {
                "total_tax": total_tax,
                "bonus_pool": bonus_pool,
                "player_count": player_count,
                "median_wealth": median_wealth,
                "top10_details": top10_details,
                "extra_tax_details": extra_tax_details
            }
    
    async def claim_tax_bonus(self, user_id: str) -> Tuple[int, int]:
        """领取税收奖池分红，直接更新用户余额

        Returns:
            (领取金额, 剩余奖池)
        """
        today = get_beijing_time().strftime("%Y-%m-%d")

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT bonus_pool, bonus_claimed FROM tax_pool WHERE date = ?",
                (today,)
            )
            row = await cursor.fetchone()

            if not row or row[0] <= 0:
                return 0, 0

            bonus_pool, claimed = row
            remaining = bonus_pool - claimed

            if remaining <= 0:
                return 0, 0

            # 获取玩家总数
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            player_count = (await cursor.fetchone())[0]

            if player_count <= 0:
                return 0, remaining

            # 每人分得：奖池 / 玩家数
            share = bonus_pool // player_count

            if share <= 0:
                share = min(1, remaining)  # 至少1星声

            share = min(share, remaining)  # 不能超过剩余

            # 更新已领取金额
            await db.execute(
                "UPDATE tax_pool SET bonus_claimed = bonus_claimed + ? WHERE date = ?",
                (share, today)
            )

            # 直接更新用户余额
            if share > 0:
                await db.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                    (share, user_id)
                )

            await db.commit()

            return share, remaining - share
    
    async def force_collect_tax(self) -> Optional[Dict]:
        """强制收税（管理员用）"""
        today = get_beijing_time().strftime("%Y-%m-%d")
        
        async with aiosqlite.connect(self.db_path) as db:
            # 删除今日税收记录
            await db.execute("DELETE FROM tax_pool WHERE date = ?", (today,))
            await db.execute("DELETE FROM user_tax_record WHERE date = ?", (today,))
            await db.commit()
            
            # 重新收税
            return await self.collect_tax()
    
    async def get_tax_stats(self, days: int = 7) -> Dict:
        """获取税收统计"""
        async with aiosqlite.connect(self.db_path) as db:
            start_date = (get_beijing_time() - __import__('datetime').timedelta(days=days)).strftime("%Y-%m-%d")
            cursor = await db.execute(
                """SELECT date, total_tax, bonus_pool, bonus_claimed, player_count, median_wealth
                   FROM tax_pool WHERE date >= ? ORDER BY date DESC""",
                (start_date,)
            )
            rows = await cursor.fetchall()
            
            total_tax = sum(int(row[1]) for row in rows if row[1])
            total_bonus = sum(int(row[2]) for row in rows if row[2])
            
            daily_stats = [{
                "date": row[0],
                "total_tax": int(row[1]) if row[1] else 0,
                "bonus_pool": int(row[2]) if row[2] else 0,
                "claimed": int(row[3]) if row[3] else 0,
                "player_count": int(row[4]) if row[4] else 0,
                "median_wealth": int(row[5]) if row[5] else 0
            } for row in rows]
            
            return {
                "total_tax": total_tax,
                "total_bonus": total_bonus,
                "daily_stats": daily_stats
            }
    
    async def _get_all_assets(self, db) -> List[Dict]:
        """获取所有用户资产"""
        cursor = await db.execute("SELECT user_id, balance, bank_balance FROM users")
        rows = await cursor.fetchall()
        
        result = []
        for row in rows:
            user_id = row[0]
            cash = int(row[1]) if row[1] else 0
            bank = int(row[2]) if row[2] else 0
            
            # 计算股票市值
            cursor = await db.execute(
                """SELECT COALESCE(SUM(sh.remaining * sp.current_price), 0)
                   FROM stock_holdings sh
                   JOIN stock_prices sp ON sh.stock_name = sp.stock_name
                   WHERE sh.user_id = ? AND sh.remaining > 0 AND sp.delisted = 0""",
                (user_id,)
            )
            stock_row = await cursor.fetchone()
            stock = int(stock_row[0]) if stock_row and stock_row[0] else 0
            
            result.append({
                "user_id": user_id,
                "cash": cash,
                "bank": bank,
                "stock": stock,
                "total": cash + bank + stock
            })
        
        return result
    
    def _calculate_median(self, sorted_list: List[int]) -> int:
        """计算中位数"""
        if not sorted_list:
            return 0
        n = len(sorted_list)
        if n % 2 == 1:
            return sorted_list[n // 2]
        else:
            return (sorted_list[n // 2 - 1] + sorted_list[n // 2]) // 2
    
    def _deduct_tax(self, cash: int, bank: int, tax: int) -> Tuple[int, int]:
        """扣税（先扣现金，再扣银行）"""
        if cash >= tax:
            return cash - tax, bank
        else:
            remaining = tax - cash
            return 0, max(0, bank - remaining)
