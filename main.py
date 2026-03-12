"""
莫宁宁的币 - 专业级经济系统插件 v2.0.0
重构版本：模块化、高性能、易维护
"""
import os
import sys
import random
import math
import json
import re
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

import aiosqlite
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.provider import ProviderRequest, LLMResponse
from astrbot.api import logger

# ============== 配置管理 ==============
import os
import sys
# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import CONFIG
from achievements import ACHIEVEMENTS

# ============== 服务类导入 ==============
from admin_service import AdminService
from tax_service import TaxService
from signin_service import SigninService
from bank_service import BankService
from shop_service import ShopService
from work_service import WorkService
from stock_service import StockService
from society_service import SocietyService
from achievement_service import AchievementService
from charity_service import CharityService
from favor_system import FavorSystem
from db_manager import DatabaseManager
from announcement_service import AnnouncementService
from utils import today_str, now_str, mask_id, format_num

# ============== 数据库管理器 ==============
class DBManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ready = False
    
    async def init(self):
        if self._ready:
            return
        
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            # 用户表 - 使用CREATE TABLE IF NOT EXISTS确保表存在但不删除
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    balance INTEGER DEFAULT 0,
                    bank_balance INTEGER DEFAULT 0,
                    last_signin_date TEXT,
                    consecutive_days INTEGER DEFAULT 0,
                    bank_last_date TEXT,
                    favor_value INTEGER DEFAULT 0
                )
            """)
            
            # 添加 favor_value 列（如果不存在）- 兼容性迁移
            try:
                await db.execute("ALTER TABLE users ADD COLUMN favor_value INTEGER DEFAULT 0")
            except aiosqlite.OperationalError:
                pass  # 列已存在
            
            # 添加 bank_last_date 列（如果不存在）- 兼容性迁移
            try:
                await db.execute("ALTER TABLE users ADD COLUMN bank_last_date TEXT")
            except aiosqlite.OperationalError:
                pass  # 列已存在
            
            # 用户信息表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_info (
                    user_id TEXT PRIMARY KEY,
                    nickname TEXT,
                    last_update TEXT
                )
            """)
            
            # 税收池表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tax_pool (
                    date TEXT PRIMARY KEY,
                    total_tax INTEGER DEFAULT 0,
                    bonus_pool INTEGER DEFAULT 0,
                    claimed INTEGER DEFAULT 0,
                    top10_list TEXT,
                    wealth_gap_ratio REAL DEFAULT 0,
                    extra_tax_rate REAL DEFAULT 0
                )
            """)
            
            # 经济历史表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS economy_history (
                    date TEXT PRIMARY KEY,
                    total_assets INTEGER DEFAULT 0,
                    user_count INTEGER DEFAULT 0,
                    avg_assets INTEGER DEFAULT 0,
                    wealth_gap_ratio REAL DEFAULT 0,
                    gini_coefficient REAL DEFAULT 0
                )
            """)
            
            # 库存表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    user_id TEXT,
                    item_name TEXT,
                    quantity INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, item_name)
                )
            """)
            
            # 购买日志
            await db.execute("""
                CREATE TABLE IF NOT EXISTS purchase_log (
                    user_id TEXT,
                    item_name TEXT,
                    purchase_date TEXT,
                    count INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, item_name, purchase_date)
                )
            """)
            
            # 占卜日志
            await db.execute("""
                CREATE TABLE IF NOT EXISTS lottery_log (
                    user_id TEXT,
                    date TEXT,
                    count INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, date)
                )
            """)
            
            # 签到记录表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_sign (
                    user_id TEXT PRIMARY KEY,
                    last_sign_date TEXT,
                    continuous_days INTEGER DEFAULT 0,
                    total_days INTEGER DEFAULT 0
                )
            """)
            
            # 塔罗牌记录
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_daily_tarot (
                    user_id TEXT,
                    date TEXT,
                    tarot_card TEXT,
                    draw_time TEXT,
                    PRIMARY KEY (user_id, date)
                )
            """)
            
            # 额外占卜次数表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_lottery_extra (
                    user_id TEXT,
                    date TEXT,
                    extra_count INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, date)
                )
            """)
            
            # 工作表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_work (
                    user_id TEXT PRIMARY KEY,
                    work_name TEXT,
                    start_time TEXT,
                    last_claim_time TEXT,
                    total_earned INTEGER DEFAULT 0
                )
            """)
            
            # 结社表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_society (
                    user_id TEXT PRIMARY KEY,
                    society_name TEXT,
                    join_time TEXT,
                    last_change_time TEXT
                )
            """)
            
            # 股票表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS stock_prices (
                    stock_name TEXT PRIMARY KEY,
                    current_price REAL DEFAULT 0,
                    base_price REAL DEFAULT 0,
                    owner_id TEXT,
                    delisted INTEGER DEFAULT 0,
                    emoji TEXT,
                    desc TEXT,
                    last_update TEXT
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS stock_holdings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    stock_name TEXT,
                    quantity REAL DEFAULT 0,
                    buy_price REAL DEFAULT 0,
                    buy_time TEXT,
                    remaining REAL DEFAULT 0,
                    last_dividend_date TEXT
                )
            """)
            
            # 成就表 - 使用CREATE TABLE IF NOT EXISTS确保表存在但不删除
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_achievements (
                    user_id TEXT,
                    achievement_id TEXT,
                    obtain_time TEXT,
                    PRIMARY KEY (user_id, achievement_id)
                )
            """)
            
            # 初始化默认股票
            default_stocks = [
                ("菲比教会", 10, "🕊️", "菲比啾比，菲比啾比！"),
                ("莫宁时代", 50, "🎁", "我将，诘问群星！"),
                ("今州科技", 200, "🎁", "今州地大物博"),
                ("深空联合", 1000, "🎁", "我们是薪火的传承者")
            ]
            
            for name, price, emoji, desc in default_stocks:
                await db.execute(
                    """INSERT OR IGNORE INTO stock_prices 
                        (stock_name, current_price, base_price, emoji, desc, last_update)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                    (name, price, price, emoji, desc, today_str())
                )
            
            # 创建成就加成表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS achievement_bonuses (
                    user_id TEXT,
                    achievement_id TEXT,
                    bonus_type TEXT,
                    bonus_value REAL,
                    PRIMARY KEY (user_id, achievement_id, bonus_type)
                )
            """)
            
            # 创建用户关系描述表（存储AI生成的关系描述）
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_relationship (
                    user_id TEXT PRIMARY KEY,
                    relationship_desc TEXT,
                    update_time TEXT,
                    next_update_time TEXT
                )
            """)
            
            # 检查并添加 next_update_time 列（兼容性迁移）
            try:
                await db.execute("SELECT next_update_time FROM user_relationship LIMIT 1")
            except aiosqlite.OperationalError:
                # 列不存在，添加它
                await db.execute("ALTER TABLE user_relationship ADD COLUMN next_update_time TEXT")
                logger.info("[数据库迁移] 已添加 next_update_time 列到 user_relationship 表")
            
            # 创建常用索引
            await db.execute("CREATE INDEX IF NOT EXISTS idx_inventory_user ON inventory(user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_lottery_user_date ON lottery_log(user_id, date)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_stock_holdings_user ON stock_holdings(user_id, stock_name)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_achievements_user ON user_achievements(user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_purchase_user ON purchase_log(user_id)")
            
            # v1.0.1.1 新增索引
            await db.execute("CREATE INDEX IF NOT EXISTS idx_stock_holdings_stock ON stock_holdings(stock_name)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_user_society_name ON user_society(society_name)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_stock_price_history ON stock_price_history(stock_name, timestamp)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_tax_pool_date ON tax_pool(date)")
            
            await db.commit()
        
        self._ready = True

# ============== 主插件类 ==============
@register("astrbot_plugin_signin", "NumInvis", "莫宁宁的币", "2.0.0")
class EconomyPlugin(Star):
    """经济系统主插件"""
    
    def __init__(self, context: Context):
        super().__init__(context)
        self.db_path = os.path.join(os.path.dirname(__file__), "data", "signin.db")
        self.db = DBManager(self.db_path)
        
        # 初始化服务
        self.admin_service = AdminService(self.db_path)
        self.tax_service = TaxService(self.db_path)
        self.signin_service = SigninService(self.db_path)
        self.bank_service = BankService(self.db_path)
        self.shop_service = ShopService(self.db_path)
        self.work_service = WorkService(self.db_path)
        self.stock_service = StockService(self.db_path)
        self.society_service = SocietyService(self.db_path)
        self.achievement_service = AchievementService(self.db_path)
        self.charity_service = CharityService(self.db_path)
        
        # 初始化好感度系统和数据库管理器
        self.favor_system = FavorSystem(self.db_path)
        self.db_manager = DatabaseManager(self.db_path)
        
        # 初始化公告服务
        self.announcement_service = AnnouncementService(self.db_path)
        
        self._initialized = False
        logger.info("【经济系统】插件加载中 v2.0.0")
    
    async def _ensure_db(self):
        """确保数据库初始化"""
        if not self._initialized:
            await self.db.init()
            # 授予赛季成就
            await self.achievement_service.grant_season_achievements()
            # 初始化公告表
            await self.announcement_service.init_table()
            self._initialized = True
    
    # ============== 用户基础功能 ==============
    async def _get_user(self, user_id: str) -> Dict:
        """获取或创建用户"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                # 安全转换数值字段
                # 列顺序: user_id(0), balance(1), bank_balance(2), last_signin_date(3), 
                #         consecutive_days(4), bank_last_date(5), favor_value(6)
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
                # favor_value 现在是第7列 (index 6)
                try:
                    favor_value = int(row[6]) if len(row) > 6 and row[6] else 0
                except (ValueError, TypeError):
                    favor_value = 0
                return {
                    "user_id": row[0],
                    "balance": balance,
                    "bank_balance": bank_balance,
                    "last_signin_date": last_signin_date,
                    "consecutive_days": consecutive,
                    "favor_value": favor_value
                }
            else:
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
                    "consecutive_days": 0,
                    "favor_value": 0
                }
    
    async def _get_user_asset(self, user_id: str) -> Tuple[int, int, int, int]:
        """获取用户资产 (总, 现金, 银行, 股票)"""
        user = await self._get_user(user_id)
        cash = user["balance"]
        bank = user["bank_balance"]
        
        # 计算股票市值
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT COALESCE(SUM(sh.remaining * sp.current_price), 0)
                   FROM stock_holdings sh
                   JOIN stock_prices sp ON sh.stock_name = sp.stock_name
                   WHERE sh.user_id = ? AND sh.remaining > 0 AND sp.delisted = 0""",
                (user_id,)
            )
            row = await cursor.fetchone()
            stock = int(row[0]) if row and len(row) > 0 and row[0] else 0
        
        return cash + bank + stock, cash, bank, stock
    
    async def _get_all_assets(self) -> List[Tuple[str, int]]:
        """获取所有用户资产"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT user_id FROM users")
            users = await cursor.fetchall()
        
        result = []
        for (uid,) in users:
            total, _, _, _ = await self._get_user_asset(uid)
            result.append((uid, total))
        
        return result
    
    async def _get_rank(self, user_id: str) -> Tuple[int, float]:
        """获取排名和百分位"""
        all_assets = await self._get_all_assets()
        if not all_assets:
            return 1, 0.0
        
        sorted_assets = sorted(all_assets, key=lambda x: x[1], reverse=True)
        total = len(sorted_assets)
        
        user_total, _, _, _ = await self._get_user_asset(user_id)
        
        rank = 1
        for i, (uid, asset) in enumerate(sorted_assets, 1):
            if uid == user_id:
                rank = i
                break
        
        percentile = (rank - 1) / total if total > 0 else 0
        return rank, percentile
    
    async def _get_nickname(self, user_id: str) -> Optional[str]:
        """获取用户昵称"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT nickname FROM user_info WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else None
    
    async def _update_nickname(self, user_id: str, nickname: str):
        """更新昵称"""
        if not nickname or nickname == user_id:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO user_info (user_id, nickname, last_update)
                   VALUES (?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET nickname = ?, last_update = ?""",
                (user_id, nickname, today_str(), nickname, today_str())
            )
            await db.commit()
    
    def _get_sender_name(self, event: AstrMessageEvent) -> str:
        """获取发送者名称"""
        try:
            if hasattr(event, 'get_sender_name'):
                name = event.get_sender_name()
                if name and name != str(event.get_sender_id()):
                    return name
        except:
            pass
        
        try:
            if hasattr(event, 'message_obj') and event.message_obj:
                sender = event.message_obj.sender
                if sender:
                    nick = sender.get('nickname')
                    if nick:
                        return nick
                    card = sender.get('card')
                    if card:
                        return card
        except:
            pass
        
        return mask_id(str(event.get_sender_id()))
    
    def _parse_target(self, event: AstrMessageEvent) -> Optional[str]:
        """解析@目标"""
        msg = event.message_str
        match = re.search(r'\[CQ:at,qq=(\d+)\]', msg)
        if match:
            return match.group(1)
        
        parts = msg.split()
        if len(parts) >= 2:
            potential = parts[1].replace("@", "").strip()
            if potential.isdigit():
                return potential
        
        return None
    
    # ============== 税收系统 ==============
    async def _collect_tax(self) -> Optional[Tuple]:
        """收取每日税收"""
        return await self.tax_service.collect_tax()
    
    async def _claim_tax_bonus(self, user_id: str) -> Tuple[int, int]:
        """领取税收分红"""
        return await self.tax_service.claim_tax_bonus(user_id)
    
    # ============== 命令处理 ==============
    @filter.command("签到")
    async def cmd_signin(self, event: AstrMessageEvent):
        """签到命令"""
        await self._ensure_db()
        
        # 收税
        tax_result = await self._collect_tax()
        
        user_id = str(event.get_sender_id())
        nickname = self._get_sender_name(event)
        await self._update_nickname(user_id, nickname)
        
        today = today_str()
        
        rank, percentile = await self._get_rank(user_id)
        
        # 使用SigninService执行签到
        signin_result = await self.signin_service.signin(user_id, percentile)
        
        # 检查是否已签到
        if not signin_result["success"]:
            yield event.plain_result(
                f"⛔ {signin_result['message']}\n"
                f"💰 当前余额：{format_num(signin_result['balance'])} 星声\n"
                f"📅 连续签到：{signin_result['consecutive_days']} 天"
            )
            return
        
        # 税收分红
        tax_bonus, remaining_pool = await self._claim_tax_bonus(user_id)
        total = signin_result["total"] + tax_bonus
        new_balance = signin_result["balance"] + tax_bonus
        
        # 更新余额以包含税收分红
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET balance = ? WHERE user_id = ?",
                (new_balance, user_id)
            )
            await db.commit()
        
        # 检查成就
        new_achievements = await self.achievement_service.check_achievements(user_id, "signin", {"consecutive": signin_result["consecutive_days"]})
        
        # 显示新成就通知
        achievement_msg = ""
        if new_achievements:
            achievement_msg = "\n" + "\n".join([
                f"🎁 【新成就】{a['emoji']} {a['name']}\n   📝 {a['desc']}"
                for a in new_achievements
            ])
        
        # 抽塔罗牌
        tarot_msg = ""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT tarot_card FROM user_daily_tarot WHERE user_id = ? AND date = ?",
                (user_id, today)
            )
            if not await cursor.fetchone():
                card = random.choice(CONFIG.TAROT_CARDS)
                desc = CONFIG.TAROT_DESC.get(card, "今日运势平稳")
                effect = CONFIG.TAROT_EFFECTS.get(card, {})
                
                # 处理塔罗牌效果
                effect_msg = ""
                if effect:
                    effect_type = effect.get("type")
                    effect_value = effect.get("value")
                    effect_desc = effect.get("desc")
                    
                    # 获得星声
                    if effect_type == "balance_reward":
                        if isinstance(effect_value, list):
                            min_val, max_val = effect_value
                            reward = random.randint(min_val, max_val)
                        else:
                            reward = effect_value
                        await db.execute(
                            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                            (reward, user_id)
                        )
                        effect_msg = f"\n🎁 效果：{effect_desc}\n实际获得 {reward} 星声"
                    
                    # 失去星声（按总资产比例）
                    elif effect_type == "balance_penalty":
                        # 获取用户总资产
                        cursor = await db.execute(
                            "SELECT balance + bank_balance + COALESCE((SELECT SUM(quantity * buy_price) FROM stock_holdings WHERE user_id = ?), 0) as total_assets FROM users WHERE user_id = ?",
                            (user_id, user_id)
                        )
                        row = await cursor.fetchone()
                        total_assets = row[0] if row and row[0] else 0
                        
                        if isinstance(effect_value, list):
                            min_val, max_val = effect_value
                            penalty_rate = random.uniform(min_val, max_val)
                        else:
                            penalty_rate = effect_value
                        
                        # 按比例计算扣除金额
                        penalty = int(total_assets * penalty_rate)
                        
                        await db.execute(
                            "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                            (penalty, user_id)
                        )
                        effect_msg = f"\n🎁 效果：{effect_desc}\n总资产 {format_num(total_assets)}，实际失去 {format_num(penalty)} 星声（{penalty_rate*100:.1f}%）"
                    
                    # 获得好感值
                    elif effect_type == "favor_value_reward":
                        if isinstance(effect_value, list):
                            min_val, max_val = effect_value
                            favor_reward = random.randint(min_val, max_val)
                        else:
                            favor_reward = effect_value
                        await db.execute(
                            "UPDATE users SET favor_value = COALESCE(favor_value, 0) + ? WHERE user_id = ?",
                            (favor_reward, user_id)
                        )
                        effect_msg = f"\n🎁 效果：{effect_desc}\n实际获得 {favor_reward} 点好感值"

                    # 扣除好感值
                    elif effect_type == "favor_value_penalty":
                        if isinstance(effect_value, list):
                            min_val, max_val = effect_value
                            favor_penalty = random.randint(min_val, max_val)
                        else:
                            favor_penalty = effect_value
                        await db.execute(
                            "UPDATE users SET favor_value = COALESCE(favor_value, 0) - ? WHERE user_id = ?",
                            (favor_penalty, user_id)
                        )
                        effect_msg = f"\n🎁 效果：{effect_desc}\n实际扣除 {favor_penalty} 点好感值"
                    
                    # 持仓股票立即上涨（随机一只）
                    elif effect_type == "stock_price_up":
                        if isinstance(effect_value, list):
                            min_val, max_val = effect_value
                            increase_rate = random.uniform(min_val, max_val)
                        else:
                            increase_rate = effect_value
                        # 获取用户持仓股票
                        cursor = await db.execute(
                            "SELECT stock_name, quantity FROM stock_holdings WHERE user_id = ? AND quantity > 0",
                            (user_id,)
                        )
                        holdings = await cursor.fetchall()
                        if holdings:
                            # 随机选择一只持仓股票
                            selected_stock = random.choice(holdings)
                            stock_name, quantity = selected_stock
                            # 获取当前股价
                            cursor = await db.execute(
                                "SELECT current_price FROM stock_prices WHERE stock_name = ?",
                                (stock_name,)
                            )
                            row = await cursor.fetchone()
                            if row:
                                current_price = row[0]
                                new_price = current_price * (1 + increase_rate)
                                await db.execute(
                                    "UPDATE stock_prices SET current_price = ? WHERE stock_name = ?",
                                    (new_price, stock_name)
                                )
                                effect_msg = f"\n🎁 效果：{effect_desc}\n【{stock_name}】上涨 {increase_rate*100:.1f}%"
                        else:
                            effect_msg = f"\n🎁 效果：{effect_desc}\n但你没有持仓股票"

                    # 持仓股票立即下跌（随机一只）
                    elif effect_type == "stock_price_down":
                        if isinstance(effect_value, list):
                            min_val, max_val = effect_value
                            decrease_rate = random.uniform(min_val, max_val)
                        else:
                            decrease_rate = effect_value
                        # 获取用户持仓股票
                        cursor = await db.execute(
                            "SELECT stock_name, quantity FROM stock_holdings WHERE user_id = ? AND quantity > 0",
                            (user_id,)
                        )
                        holdings = await cursor.fetchall()
                        if holdings:
                            # 随机选择一只持仓股票
                            selected_stock = random.choice(holdings)
                            stock_name, quantity = selected_stock
                            # 获取当前股价
                            cursor = await db.execute(
                                "SELECT current_price FROM stock_prices WHERE stock_name = ?",
                                (stock_name,)
                            )
                            row = await cursor.fetchone()
                            if row:
                                current_price = row[0]
                                new_price = max(1, current_price * (1 - decrease_rate))
                                await db.execute(
                                    "UPDATE stock_prices SET current_price = ? WHERE stock_name = ?",
                                    (new_price, stock_name)
                                )
                                effect_msg = f"\n🎁 效果：{effect_desc}\n【{stock_name}】下跌 {decrease_rate*100:.1f}%"
                        else:
                            effect_msg = f"\n🎁 效果：{effect_desc}\n但你没有持仓股票"
                    
                    # 失去工作
                    elif effect_type == "lose_job":
                        # 检查用户是否有工作
                        try:
                            cursor = await db.execute(
                                "SELECT work_name FROM user_work WHERE user_id = ?",
                                (user_id,)
                            )
                            row = await cursor.fetchone()
                            if row:
                                work_name = row[0]
                                await db.execute(
                                    "DELETE FROM user_work WHERE user_id = ?",
                                    (user_id,)
                                )
                                effect_msg = f"\n🎁 效果：{effect_desc}\n你失去了工作：{work_name}"
                            else:
                                effect_msg = f"\n🎁 效果：{effect_desc}\n但你现在是无业游民"
                        except:
                            effect_msg = f"\n🎁 效果：{effect_desc}\n但你现在是无业游民"
                    
                    # 占卜次数增加
                    elif effect_type == "lottery_extra":
                        # 记录额外的占卜次数到用户数据
                        await db.execute(
                            "INSERT OR REPLACE INTO user_lottery_extra (user_id, extra_count, date) VALUES (?, COALESCE((SELECT extra_count FROM user_lottery_extra WHERE user_id = ? AND date = ?), 0) + ?, ?)",
                            (user_id, user_id, today, effect_value, today)
                        )
                        effect_msg = f"\n🎁 效果：{effect_desc}"
                    
                    # 其他效果
                    else:
                        effect_msg = f"\n🎁 效果：{effect_desc}"
                
                await db.execute(
                    "INSERT INTO user_daily_tarot (user_id, date, tarot_card, draw_time) VALUES (?, ?, ?, ?)",
                    (user_id, today, card, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                )
                await db.commit()
                
                tarot_msg = f"\n═══════════════════\n🔮 今日塔罗：【{card}】\n{desc}{effect_msg}"
        
        # 构建消息
        wealth_icon = "🎁" if percentile < 0.1 else "🎁" if percentile < 0.5 else "🎁"
        
        lines = [
            f"⛔ 签到成功！{wealth_icon} 财富排名：第{rank}名（前{int(percentile*100)}%）",
            f"�� 基础：{signin_result['base']}星声（低保加成{int(percentile*100)}%）",
            f"🔥 连续加成：{signin_result['bonus']}星声（{signin_result['consecutive_days']}天×{1 + (percentile * 0.5):.1f}倍）"
        ]
        
        # 显示成就加成
        # 蓝色成就：每日签到额外星声
        if signin_result.get('signin_extra', 0) > 0:
            lines.append(f"🔵 蓝色成就加成：+{signin_result['signin_extra']}星声")
        
        # 彩色成就：每日签到额外好感值
        if signin_result.get('signin_favor_bonus', 0) > 0:
            lines.append(f"�� 彩色成就加成：+{signin_result['signin_favor_bonus']}好感值")
        
        lines.append(f"🏆 赛季：S{CONFIG.CURRENT_SEASON}")
        
        if tax_bonus > 0:
            lines.append(f"🏛️ 富豪税分红：+{tax_bonus}星声（奖池剩余{remaining_pool}）")
        
        if tax_result and len(tax_result) >= 5:
            _, _, _, extra_rate, ratio = tax_result
            if ratio > 1:
                lines.append(f"⚖️ 贫富差距指数：{ratio:.1f}（调节税+{extra_rate*100:.1f}%）")
        
        lines.extend([
            "═══════════════════",
            f"💰 共计：{total}星声",
            f"�� 余额：{format_num(new_balance)}星声"
        ])
        
        if tarot_msg:
            lines.append(tarot_msg)
        
        yield event.plain_result("\n".join(lines))
    
    @filter.command("签到帮助")
    async def cmd_signin_help(self, event: AstrMessageEvent):
        """经济系统帮助"""
        help_text = """📋 指令列表

💰 基础：/签到 /余额 /转账 @用户 金额 /资产排行榜 /经济 /税收
🏦 银行：/银行 /存款 金额 /取款 金额
🛍️ 商店：/商店 /购买 商品 数量 /背包 /使用 物品 /占卜概率 /Allin
💼 工作：/找工作 /应聘 工作名 /工作状态 /领工资
📈 股票：/股市 /买入 股票 数量 /卖出 股票 数量 /持仓 /创立公司 名称 价格 描述 /宣告破产 公司 /研发 公司 金额 /股东 股票 /k线 股票
🏛️ 结社：/结社 /加入结社 名称 /我的结社
💖 好感：/好感度 /好感度排行
🏆 成就：/成就 /塔罗牌
🔧 管理：/高级签到帮助"""
        yield event.plain_result(help_text)
    
    @filter.command("高级签到帮助")
    async def cmd_advanced_signin_help(self, event: AstrMessageEvent):
        """管理员帮助"""
        user_id = str(event.get_sender_id())
        
        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("? 权限不足！此命令仅管理员可用")
            return
        
        help_text = """🔧 管理员指令

系统：/admin reset 用户 /admin add 用户 金额 /admin remove 用户 金额 /admin clear
统计：/admin stats /admin users /admin logs
经济：/admin tax 税率 /admin bank 利率 /admin shop 商品 价格 数量
股票：/admin stock add 名称 价格 描述 /admin stock remove 名称 /admin stock price 名称 价格
商店：/admin shop add 商品名 价格 限购 好感值 描述 /admin shop remove 商品名 /admin shop edit 商品名 属性 值
好感：/admin favor add 用户 数量 /admin favor remove 用户 数量 /admin favor reset 用户
成就：/所有人成就 /授予成就 用户ID/所有人 成就ID /重置签到 用户ID/所有人
赛季：/新赛季 密码"""
        yield event.plain_result(help_text)
    
    @filter.command("新赛季")
    async def cmd_new_season(self, event: AstrMessageEvent):
        """开启新赛季"""
        user_id = str(event.get_sender_id())
        
        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("? 权限不足！此命令仅管理员可用")
            return
        
        # 获取密码
        args = event.message_str.split()
        if len(args) < 2:
            yield event.plain_result("? 请输入密码：/新赛季 <密码>")
            return
        
        password = args[1]
        if password != CONFIG.SEASON_PASSWORD:
            yield event.plain_result("? 密码错误！")
            return
        
        await self._ensure_db()
        
        # 开始新赛季
        new_season = CONFIG.CURRENT_SEASON + 1
        
        async with aiosqlite.connect(self.db_path) as db:
            # 清空抽卡资源
            await db.execute("DELETE FROM user_daily_tarot")
            
            # 清空银行存款
            await db.execute("UPDATE users SET bank_balance = 0")
            
            # 清空股票持仓
            await db.execute("DELETE FROM stock_holdings")
            
            # 清空工作状态
            await db.execute("DELETE FROM user_work")
            
            # 清空背包
            await db.execute("DELETE FROM inventory")
            
            # 获取所有用户
            cursor = await db.execute("SELECT user_id FROM users")
            users = await cursor.fetchall()
            
            # 给所有用户发放赛季成就
            for (uid,) in users:
                achievement_id = f"season_{new_season-1}_pioneer"
                await self.achievement_service._grant_achievement(db, uid, achievement_id)
            
            await db.commit()
        
        # 更新配置文件中的赛季数
        config_content = ""
        with open("config.py", "r", encoding="utf-8") as f:
            config_content = f.read()
        
        # 替换赛季数
        import re
        config_content = re.sub(r"CURRENT_SEASON = \d+", f"CURRENT_SEASON = {new_season}", config_content)
        
        with open("config.py", "w", encoding="utf-8") as f:
            f.write(config_content)
        
        yield event.plain_result(f"? 新赛季开启成功！现在是 S{new_season} 赛季\n\n" +
                               "🏆 赛季重置内容：\n" +
                               "- 清空所有用户的抽卡资源\n" +
                               "- 清空所有用户的银行存款\n" +
                               "- 清空所有用户的股票持仓\n" +
                               "- 清空所有用户的工作状态\n" +
                               "- 清空所有用户的背包物品\n\n" +
                               "🎁 发放成就：\n" +
                               f"- 给所有用户发放金色成就 \"S{new_season-1}先行者\"\n\n" +
                               "📌 保留内容：\n" +
                               "- 连续签到天数\n" +
                               "- 所有成就记录")
    
    @filter.command("admin")
    async def cmd_admin(self, event: AstrMessageEvent):
        """管理员命令"""
        user_id = str(event.get_sender_id())
        
        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("? 权限不足！此命令仅管理员可用")
            return
        
        args = event.message_str.split()
        if len(args) < 2:
            yield event.plain_result("⚠️ 用法：/admin <子命令> [参数]")
            return
        
        subcommand = args[1]
        
        # 处理商店相关命令
        if subcommand == "shop":
            if len(args) < 3:
                yield event.plain_result("? 用法：/admin shop <add/remove/edit> [参数]")
                return
            
            shop_cmd = args[2]
            
            # 上架新商品
            if shop_cmd == "add":
                if len(args) < 7:
                    yield event.plain_result("? 用法：/admin shop add <商品名> <价格> <每日限购> <好感值> <描述>")
                    return
                
                item_name = args[3]
                try:
                    price = int(args[4])
                    daily_limit = int(args[5])
                    favor_value = int(args[6])
                except:
                    yield event.plain_result("? 价格、每日限购和好感值必须是整数！")
                    return
                
                desc = " ".join(args[7:])
                
                # 更新配置文件
                config_content = ""
                with open("config.py", "r", encoding="utf-8") as f:
                    config_content = f.read()
                
                # 添加新商品到SHOP_ITEMS
                import re
                shop_items_match = re.search(r"SHOP_ITEMS = \{([\s\S]*?)\}", config_content)
                if shop_items_match:
                    shop_items_content = shop_items_match.group(1)
                    new_item = f'        "{item_name}": {{"price": {price}, "daily_limit": {daily_limit}, "desc": "增加莫宁宁{favor_value}点好感值"}}'
                    
                    if shop_items_content.strip():
                        new_shop_items = shop_items_content.strip() + ",\n" + new_item
                    else:
                        new_shop_items = new_item
                    
                    new_config = config_content.replace(shop_items_match.group(1), new_shop_items)
                    
                    with open("config.py", "w", encoding="utf-8") as f:
                        f.write(new_config)
                    
                    # 更新favor_items字典（需要重启插件生效）
                    yield event.plain_result(f"? 商品上架成功！\n商品：{item_name}\n价格：{price}星声\n每日限购：{daily_limit}个\n好感值：{favor_value}点\n描述：{desc}")
                else:
                    yield event.plain_result("? 配置文件格式错误，无法添加商品")
            
            # 下架商品
            elif shop_cmd == "remove":
                if len(args) < 4:
                    yield event.plain_result("? 用法：/admin shop remove <商品名>")
                    return
                
                item_name = args[3]
                
                # 更新配置文件
                config_content = ""
                with open("config.py", "r", encoding="utf-8") as f:
                    config_content = f.read()
                
                # 从SHOP_ITEMS中移除商品
                import re
                pattern = r'\s*"' + re.escape(item_name) + r'":\s*\{[^\}]*\},?\s*'
                new_config = re.sub(pattern, '', config_content)
                
                with open("config.py", "w", encoding="utf-8") as f:
                    f.write(new_config)
                
                # 更新favor_items字典（需要重启插件生效）
                yield event.plain_result(f"? 商品下架成功！\n商品：{item_name}")
            
            # 修改商品属性
            elif shop_cmd == "edit":
                if len(args) < 5:
                    yield event.plain_result("? 用法：/admin shop edit <商品名> <属性> <值>")
                    return
                
                item_name = args[3]
                attribute = args[4]
                value = args[5]
                
                # 验证属性
                valid_attributes = ["price", "daily_limit"]
                if attribute not in valid_attributes:
                    yield event.plain_result(f"? 无效的属性！有效属性：{', '.join(valid_attributes)}")
                    return
                
                # 验证值
                try:
                    if attribute in ["price", "daily_limit"]:
                        int(value)
                except:
                    yield event.plain_result("? 值必须是整数！")
                    return
                
                # 更新配置文件
                config_content = ""
                with open("config.py", "r", encoding="utf-8") as f:
                    config_content = f.read()
                
                # 修改商品属性
                import re
                pattern = r'("' + re.escape(item_name) + r'":\s*\{[^\}]*"' + attribute + r'")\s*:\s*[^,}]+'
                replacement = r'\1: ' + value
                new_config = re.sub(pattern, replacement, config_content)
                
                with open("config.py", "w", encoding="utf-8") as f:
                    f.write(new_config)
                
                yield event.plain_result(f"? 商品属性修改成功！\n商品：{item_name}\n属性：{attribute}\n新值：{value}")
            
            else:
                yield event.plain_result("? 无效的商店命令！可用命令：add, remove, edit")
        
        else:
            yield event.plain_result("? 无效的管理员命令！")

    @filter.command("余额")
    async def cmd_balance(self, event: AstrMessageEvent):
        """查看余额"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        nickname = self._get_sender_name(event)
        await self._update_nickname(user_id, nickname)

        today = today_str()
        total, cash, bank, stock = await self._get_user_asset(user_id)
        user = await self._get_user(user_id)

        status = "? 今日已签到" if user["last_signin_date"] == today else "? 今日未签到"

        # 获取好感度和好感值
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COALESCE(favor_value, 0) FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            favor_value = int(row[0]) if row else 0

            # 计算好感度
            cursor = await db.execute(
                "SELECT SUM(COALESCE(favor_value, 0)) FROM users WHERE favor_value > 0"
            )
            total_favor_row = await cursor.fetchone()
            total_favor = int(total_favor_row[0]) if total_favor_row and total_favor_row[0] else 1
            favor_level = int((favor_value / total_favor) * 520) if total_favor > 0 else 0

        favor_info = f"\n💖 好感值：{favor_value}  好感度：{favor_level}"

        msg = (
            f"👤 [{nickname}] 的资产\n"
            f"💵 抽卡资源：{format_num(cash)} 星声\n"
            f"🏦 存款：{format_num(bank)} 星声\n"
            f"📈 股票：{format_num(stock)} 星声\n"
            f"💰 总资产：{format_num(total)} 星声\n"
            f"📅 连续签到：{user['consecutive_days']}天\n"
            f"📋 状态：{status}{favor_info}"
        )

        # 检查财富成就
        await self.achievement_service.check_achievements(user_id, "asset_check", {"total": total})

        yield event.plain_result(msg)
    
    @filter.command("转账")
    async def cmd_transfer(self, event: AstrMessageEvent):
        """转账命令"""
        await self._ensure_db()
        
        sender_id = str(event.get_sender_id())
        parts = event.message_str.split()
        
        if len(parts) < 3:
            yield event.plain_result("💡 用法：/转账 @用户 金额")
            return
        
        try:
            amount = int(parts[-1])
            if amount <= 0:
                raise ValueError()
        except:
            yield event.plain_result("? 金额必须是正整数！")
            return
        
        target_id = self._parse_target(event)
        if not target_id:
            yield event.plain_result("? 请@要转账的用户！")
            return
        
        if sender_id == target_id:
            yield event.plain_result("? 不能给自己转账！")
            return
        
        sender = await self._get_user(sender_id)
        if sender["balance"] < amount:
            yield event.plain_result(f"? 余额不足！当前：{format_num(sender['balance'])}星声")
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (amount, sender_id)
            )
            await db.execute(
                """INSERT INTO users (user_id, balance) VALUES (?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?""",
                (target_id, amount, amount)
            )
            await db.commit()
        
        yield event.plain_result(
            f"⛔ 转账成功！\n"
            f"🎁 转出：{format_num(amount)}星声\n"
            f"👤 给：{mask_id(target_id)}\n"
            f"🎁 您剩余：{format_num(sender['balance'] - amount)}星声"
        )
    
    @filter.command("资产排行榜")
    async def cmd_ranking(self, event: AstrMessageEvent):
        """资产排行榜"""
        await self._ensure_db()
        await self._collect_tax()
        
        user_id = str(event.get_sender_id())
        
        # 获取昵称映射
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT user_id, nickname FROM user_info WHERE nickname IS NOT NULL")
            name_map = {str(row[0]): row[1] for row in await cursor.fetchall()}
        
        # 获取所有资产
        all_assets = await self._get_all_assets()
        sorted_assets = sorted(all_assets, key=lambda x: x[1], reverse=True)
        
        if not sorted_assets:
            yield event.plain_result("🎁 暂无资产数据")
            return
        
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        lines = ["🏆 资产排行榜 Top 10", "═══════════════════"]

        for i, (uid, total) in enumerate(sorted_assets[:10]):
            medal = medals[i] if i < len(medals) else f"{i+1}."
            name = name_map.get(uid, mask_id(uid))
            is_self = uid == user_id
            name_display = f"{name} (你)" if is_self else name

            # 获取详细资产
            _, cash, bank, stock = await self._get_user_asset(uid)

            lines.append(f"{medal} {name_display}")
            lines.append(f"   💰 总资产：{format_num(total)} 星声")
            lines.append(f"   💵 {format_num(cash)} | 🏦 {format_num(bank)} | 📈 {format_num(stock)}")
            if i < 9:
                lines.append("")
        
        # 找到自己的排名
        my_rank = None
        for idx, (uid, _) in enumerate(sorted_assets, 1):
            if uid == user_id:
                my_rank = idx
                break
        
        if my_rank:
            my_total, my_cash, my_bank, my_stock = await self._get_user_asset(user_id)
            lines.extend([
                "═══════════════════",
                f"💡 我的排名：第 {my_rank} 名",
                f"💰 总资产：{format_num(my_total)} 星声",
                f"💵 {format_num(my_cash)} | 🏦 {format_num(my_bank)} | 📈 {format_num(my_stock)}"
            ])
        
        # 添加税收信息
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT total_tax, bonus_pool, wealth_gap_ratio FROM tax_pool WHERE date = ?",
                (today_str(),)
            )
            row = await cursor.fetchone()
            if row:
                lines.append(f"\n⚖️ 贫富差距r={row[2]:.1f} | 🏛️ 税:{format_num(row[0])} | 奖池:{format_num(row[1])}")
        
        yield event.plain_result("\n".join(lines))
    
    @filter.command("经济")
    async def cmd_economy(self, event: AstrMessageEvent):
        """宏观经济数据"""
        await self._ensure_db()
        
        # 记录经济数据
        all_assets = await self._get_all_assets()
        total_assets = sum(w for _, w in all_assets)
        user_count = len(all_assets)
        avg_assets = total_assets // user_count if user_count > 0 else 0
        
        # 计算基尼系数
        wealth_list = [w for _, w in all_assets if w >= 0]
        if len(wealth_list) >= 2:
            wealth_list.sort()
            n = len(wealth_list)
            total_wealth = sum(wealth_list)
            if total_wealth > 0:
                cumsum = sum((i + 1) * w for i, w in enumerate(wealth_list))
                gini = (2.0 * cumsum) / (n * total_wealth) - (n + 1.0) / n
                gini = max(0.0, min(1.0, gini))
            else:
                gini = 0.0
        else:
            gini = 0.0
        
        # 保存数据
        async with aiosqlite.connect(self.db_path) as db:
            # 确保经济历史表有赛季字段
            await db.execute("""
                CREATE TABLE IF NOT EXISTS economy_history (
                    date TEXT PRIMARY KEY,
                    season INTEGER,
                    total_assets INTEGER,
                    user_count INTEGER,
                    avg_assets INTEGER,
                    gini_coefficient REAL,
                    wealth_gap_ratio REAL
                )
            """)
            
            # 尝试添加赛季列（如果不存在）
            try:
                await db.execute("ALTER TABLE economy_history ADD COLUMN season INTEGER DEFAULT 1")
            except:
                pass
            
            await db.execute(
                """INSERT OR REPLACE INTO economy_history 
                    (date, season, total_assets, user_count, avg_assets, gini_coefficient)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                (today_str(), CONFIG.CURRENT_SEASON, total_assets, user_count, avg_assets, gini)
            )
            await db.commit()
            
            # 获取历史数据
            cursor = await db.execute(
                """SELECT date, total_assets, user_count, avg_assets, wealth_gap_ratio
                   FROM economy_history ORDER BY date DESC LIMIT 7"""
            )
            history = await cursor.fetchall()
        
        if not history:
            yield event.plain_result("🎁 暂无经济数据")
            return
        
        latest = history[0]
        lines = [
            f"📊 索拉里斯宏观经济报告（S{CONFIG.CURRENT_SEASON}赛季）",
            "═══════════════════",
            f"💰 总资产：{format_num(int(latest[1]))} 星声",
            f"👥 玩家数：{int(latest[2])} 人",
            f"💵 人均资产：{format_num(int(latest[3]))} 星声",
            f"📉 基尼系数：{gini:.3f}",
            "",
            "�� 近7天详细数据：",
            "日期　　| 总资产　　　　| 玩家数 | 人均",
            "────────┼───────────────┼────────┼──────────"
        ]
        
        for row in history[:7]:
            date_short = row[0][-5:] if len(row[0]) >= 5 else row[0]
            lines.append(f"{date_short}　│ {format_num(int(row[1])):>13} │ {int(row[2]):>6} │ {format_num(int(row[3])):>9}")
        
        yield event.plain_result("\n".join(lines))
    
    @filter.command("税收")
    async def cmd_tax(self, event: AstrMessageEvent):
        """税收报告"""
        await self._ensure_db()
        
        today = today_str()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT total_tax, bonus_pool, claimed, top10_list, 
                          wealth_gap_ratio, extra_tax_rate
                   FROM tax_pool WHERE date = ?""",
                (today,)
            )
            row = await cursor.fetchone()
        
        if not row:
            yield event.plain_result("📭 今日尚未收税")
            return
        
        total, bonus, claimed, top10, gap_ratio, extra_rate = row
        remaining = bonus - claimed
        
        msg = (
            f"🏛️ 富豪税与贫富差距报告\n"
            f"═══════════════════\n"
            f"💰 总收税：{format_num(total)}星声\n"
            f"🎁 今日奖池：{format_num(bonus)}星声\n"
            f"⛔ 已领取：{format_num(claimed)}星声\n"
            f"📦 剩余：{format_num(remaining)}星声\n"
        )
        
        if gap_ratio and gap_ratio > 1:
            msg += f"⚖️ 贫富差距指数 r={gap_ratio:.2f}\n"
            msg += f"📊 调节税率：+{extra_rate*100:.1f}%\n"
        
        # 显示税率信息
        msg += f"\n🏛️ 税率设置：\n"
        for i, rate in enumerate(CONFIG.TAX_RATES, 1):
            msg += f"第{i}名：{rate*100:.1f}%\n"
        msg += f"贫富差距除数：{CONFIG.WEALTH_GAP_DIVISOR}\n"
        
        msg += f"\n═══════════════════\n被税名单：{top10 or '无'}"
        
        yield event.plain_result(msg)
    
    # ============== 好感度系统 ==============
    @filter.command("好感度")
    async def cmd_favor(self, event: AstrMessageEvent):
        """查看好感度"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        nickname = self._get_sender_name(event)
        
        # 确保 favor_system 已初始化
        if not self.favor_system:
            yield event.plain_result("? 系统初始化中，请稍后再试")
            return
        
        favor_info = await self.favor_system.get_user_favor_info(user_id)
        if not favor_info:
            yield event.plain_result("? 获取好感度信息失败")
            return
        
        # 获取关系描述和CD信息
        rel_info = await self.favor_system.get_relationship_desc(user_id)
        if not rel_info:
            rel_info = {'desc': None, 'can_update': True, 'next_update_time': None}
        
        # 构建显示消息
        lines = [
            f"🎁 {nickname} 的好感度信息",
            f"💕 好感度：{favor_info['favor_level']:.2f}/520"
        ]
        
        # 显示AI生成的关系描述
        if rel_info.get('desc'):
            lines.append(f"💭 我们的关系：{rel_info['desc']}")
            if rel_info.get('can_update'):
                lines.append("🔄 关系描述可更新")
            else:
                # 计算剩余时间
                from datetime import datetime
                try:
                    next_update = datetime.strptime(rel_info['next_update_time'], "%Y-%m-%d %H:%M:%S")
                    remaining = next_update - datetime.now()
                    remaining_minutes = int(remaining.total_seconds() / 60)
                    lines.append(f"? 关系更新CD：{remaining_minutes}分钟后可更新")
                except:
                    lines.append("? 关系更新CD中")
        else:
            lines.append("💭 我们的关系：还没有足够的互动记录...")
        
        lines.append("\n💡 提示：与我互动可以增加好感度哦～")
        
        yield event.plain_result("\n".join(lines))
    
    @filter.command("好感度排行")
    async def cmd_favor_ranking(self, event: AstrMessageEvent):
        """查看好感度排行榜"""
        await self._ensure_db()
        
        # 确保 favor_system 已初始化
        if not self.favor_system:
            yield event.plain_result("? 系统初始化中，请稍后再试")
            return
        
        ranking = await self.favor_system.get_favor_ranking()
        
        if not ranking:
            yield event.plain_result("🎁 暂无好感度数据")
            return
        
        lines = ["💕 好感度排行榜 Top 10", "═══════════════════"]
        medals = ["🎁", "🎁", "🎁", "4🎁", "5🎁", "6🎁", "7🎁", "8🎁", "9🎁", "🎁"]
        
        # 获取所有用户的关系描述
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT user_id, relationship_desc FROM user_relationship")
            relationship_map = {row[0]: row[1] for row in await cursor.fetchall()}
        
        for i, user_info in enumerate(ranking[:10], 1):
            medal = medals[i-1] if i-1 < len(medals) else f"{i}."
            name = await self._get_nickname(user_info['user_id']) or mask_id(user_info['user_id'])
            ai_rel = relationship_map.get(user_info['user_id'])
            
            lines.append(f"{medal} {name}")
            lines.append(f"   💕 好感度：{user_info.get('favor_level', 0)}")
            if ai_rel:
                lines.append(f"   🎁 {ai_rel}")
            if i < 10:
                lines.append("")
        
        # 找到自己的排名
        user_id = str(event.get_sender_id())
        my_rank = None
        my_info = None
        for idx, user_info in enumerate(ranking, 1):
            if user_info.get('user_id') == user_id:
                my_rank = idx
                my_info = user_info
                break
        
        if my_rank and my_info:
            # 获取自己的关系描述
            my_rel_info = await self.favor_system.get_relationship_desc(user_id)
            if not my_rel_info:
                my_rel_info = {'desc': None}
            
            if my_rel_info.get('desc'):
                my_ai_rel = my_rel_info['desc']
            else:
                my_ai_rel = "还没有足够的互动记录..."
            
            lines.extend([
                "═══════════════════",
                f"💡 我的排名：第 {my_rank} 名",
                f"🎁 我的好感度：{my_info.get('favor_level', 0)}",
                f"💭 我们的关系：{my_ai_rel}"
            ])
        
        yield event.plain_result("\n".join(lines))
    
    @filter.command("成就")
    async def cmd_achievements(self, event: AstrMessageEvent):
        """查看个人成就"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        nickname = self._get_sender_name(event)
        
        achievements = await self.achievement_service.get_user_achievements(user_id)
        obtained = achievements.get("obtained", {})
        obtained_count = achievements.get("obtained_count", 0)
        total_count = achievements.get("total_count", 0)
        
        lines = [f"🏆 {nickname} 的成就", "═══════════════════"]
        
        if obtained:
            # 按稀有度排序
            rarity_order = {"colorful": 0, "gold": 1, "purple": 2, "blue": 3}
            sorted_achievements = []
            
            for aid, obtain_time in obtained.items():
                if aid in ACHIEVEMENTS:
                    achievement = ACHIEVEMENTS[aid]
                    # 使用元组 (稀有度顺序, 成就名称) 作为排序键，避免比较字典
                    sort_key = (rarity_order.get(achievement.get("rarity", "blue"), 3), achievement.get("name", ""))
                    sorted_achievements.append((sort_key, achievement, obtain_time))
            
            sorted_achievements.sort(key=lambda x: x[0])
            
            for _, achievement, obtain_time in sorted_achievements:
                lines.append(f"{achievement['emoji']} {achievement['name']}")
                lines.append(f"   📝 {achievement['desc']}")
                # 显示成就加成
                rarity = achievement.get("rarity", "blue")
                try:
                    bonus_config = CONFIG.ACHIEVEMENT_BONUSES.get(rarity, {})
                    bonus_desc = bonus_config.get("desc", "无加成")
                except:
                    # 如果CONFIG没有ACHIEVEMENT_BONUSES，使用默认值
                    bonus_desc = {
                        "blue": "每日签到额外增加1个星声",
                        "purple": "银行存款利率永久性提升0.1%",
                        "gold": "创立公司时额外赠送1000股",
                        "colorful": "每日签到额外获得1点好感值"
                    }.get(rarity, "无加成")
                lines.append(f"   ? 加成：{bonus_desc}")
                lines.append(f"   🎁 {obtain_time}")
                lines.append("")
        else:
            lines.append("🎁 暂未获得任何成就")
        
        lines.extend([
            "═══════════════════",
            f"🎁 已获得：{obtained_count}/{total_count}",
            "🎁 完成各种任务可以获得成就，成就永久保存"
        ])
        
        yield event.plain_result("\n".join(lines))
    
    @filter.command("所有人成就")
    async def cmd_all_achievements(self, event: AstrMessageEvent):
        """管理员查看所有用户的成就"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        
        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("? 权限不足！此命令仅管理员可用")
            return
        
        # 获取所有用户的成就
        all_achievements = await self.achievement_service.get_all_achievements()
        
        if not all_achievements:
            yield event.plain_result("📭 暂无成就数据")
            return
        
        lines = ["🏆 所有人成就统计", "═══════════════════"]
        
        # 统计每个用户的成就
        for uid, achievements in all_achievements.items():
            name = await self._get_nickname(uid) or mask_id(uid)
            lines.append(f"\n📦 {name}")
            lines.append(f"   成就数量：{len(achievements)}")
            
            if achievements:
                # 按稀有度分类
                rarity_emojis = {"blue": "🎁", "purple": "🎁", "gold": "🎁", "colorful": "🎁"}
                rarity_counts = {"blue": 0, "purple": 0, "gold": 0, "colorful": 0}
                
                for aid in achievements:
                    if aid in ACHIEVEMENTS:
                        rarity = ACHIEVEMENTS[aid].get("rarity", "blue")
                        rarity_counts[rarity] += 1
                
                rarity_str = " | ".join([f"{rarity_emojis[r]} {count}" for r, count in rarity_counts.items() if count > 0])
                lines.append(f"   {rarity_str}")
        
        # 统计总成就数
        total_achievements = sum(len(achievements) for achievements in all_achievements.values())
        lines.extend([
            "",
            "═══════════════════",
            f"📊 总计：{len(all_achievements)} 个用户，{total_achievements} 个成就"
        ])
        
        yield event.plain_result("\n".join(lines))
    
    @filter.command("授予成就")
    async def cmd_grant_achievement(self, event: AstrMessageEvent):
        """管理员授予用户特定成就"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        
        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("? 权限不足！此命令仅管理员可用")
            return
        
        # 解析参数: /授予成就 <用户ID/所有人> <成就ID>
        parts = event.message_str.split()
        if len(parts) < 3:
            yield event.plain_result("? 用法：/授予成就 <用户ID/所有人> <成就ID>")
            return
        
        target = parts[1]
        achievement_id = parts[2]
        
        # 检查成就是否存在
        if achievement_id not in ACHIEVEMENTS:
            yield event.plain_result(f"? 成就 {achievement_id} 不存在！")
            return
        
        achievement = ACHIEVEMENTS[achievement_id]
        
        if target == "所有人":
            # 给所有用户授予成就
            count = await self.achievement_service.grant_achievement_to_all(achievement_id)
            yield event.plain_result(
                f"⛔ 成功给 {count} 个用户授予成就！\n"
                f"🏆 {achievement['emoji']} {achievement['name']}\n"
                f"📝 {achievement['desc']}"
            )
        else:
            # 给特定用户授予成就
            success = await self.achievement_service.grant_achievement(target, achievement_id)
            
            if success:
                yield event.plain_result(
                    f"⛔ 成功给用户 {target} 授予成就！\n"
                    f"🏆 {achievement['emoji']} {achievement['name']}\n"
                    f"📝 {achievement['desc']}"
                )
            else:
                yield event.plain_result(f"🎁 用户 {target} 已经拥有该成就。")
    
    @filter.command("重置签到")
    async def cmd_reset_signin(self, event: AstrMessageEvent):
        """管理员重置用户签到状态（保留连续天数，允许重新签到和抽塔罗牌）"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        
        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("? 权限不足！此命令仅管理员可用")
            return
        
        # 解析参数: /重置签到 <用户ID/所有人>
        parts = event.message_str.split()
        if len(parts) < 2:
            yield event.plain_result("? 用法：/重置签到 <用户ID/所有人>")
            return
        
        target = parts[1]
        today = today_str()
        
        if target == "所有人":
            # 重置所有人的今日签到状态
            async with aiosqlite.connect(self.db_path) as db:
                # 将所有今日签到的用户的last_signin_date设为昨天，允许重新签到
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                cursor = await db.execute(
                    "UPDATE users SET last_signin_date = ? WHERE last_signin_date = ?",
                    (yesterday, today)
                )
                signin_count = cursor.rowcount
                
                # 删除今日所有塔罗牌记录
                cursor = await db.execute(
                    "DELETE FROM user_daily_tarot WHERE date = ?",
                    (today,)
                )
                tarot_count = cursor.rowcount
                
                await db.commit()
            
            yield event.plain_result(
                f"⛔ 已重置所有人的今日签到状态！\n"
                f"🎁 重置签到记录：{signin_count} 人\n"
                f"🎁 重置塔罗牌记录：{tarot_count} 人\n"
                f"📅 连续签到天数保持不变\n"
                f"🎁 所有人可以重新签到并抽取塔罗牌"
            )
        else:
            # 重置特定用户的今日签到状态
            target_user = target
            async with aiosqlite.connect(self.db_path) as db:
                # 将用户的last_signin_date设为昨天，允许重新签到
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                await db.execute(
                    "UPDATE users SET last_signin_date = ? WHERE user_id = ? AND last_signin_date = ?",
                    (yesterday, target_user, today)
                )
                
                # 删除今日塔罗牌记录
                await db.execute(
                    "DELETE FROM user_daily_tarot WHERE user_id = ? AND date = ?",
                    (target_user, today)
                )
                
                await db.commit()
            
            yield event.plain_result(
                f"⛔ 已重置用户 {target_user} 的今日签到状态！\n"
                f"📅 连续签到天数保持不变\n"
                f"🎁 用户可以重新签到并抽取塔罗牌"
            )
    
    @filter.command("塔罗牌")
    async def cmd_view_tarot(self, event: AstrMessageEvent):
        """查看今天获得的塔罗牌"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        today = today_str()
        
        async with aiosqlite.connect(self.db_path) as db:
            # 查询今日塔罗牌
            cursor = await db.execute(
                "SELECT tarot_card, draw_time FROM user_daily_tarot WHERE user_id = ? AND date = ?",
                (user_id, today)
            )
            row = await cursor.fetchone()
        
        if not row:
            yield event.plain_result(
                "🎁 你今天还没有抽取塔罗牌！\n"
                "🎁 请先签到或抽取塔罗牌"
            )
            return
        
        card, draw_time = row
        desc = CONFIG.TAROT_DESC.get(card, "今日运势平稳")
        effect = CONFIG.TAROT_EFFECTS.get(card, {})
        effect_desc = effect.get("desc", "无特殊效果")
        
        yield event.plain_result(
            f"🔮 今日塔罗牌：【{card}】\n"
            f"═══════════════════\n"
            f"🎁 {desc}\n"
            f"🎁 效果：{effect_desc}\n"
            f"🎁 抽取时间：{draw_time}"
        )
    
    # ============== 消息事件处理 ==============
    async def on_message(self, event: AstrMessageEvent):
        """处理消息事件
        
        注意：情感分析现在完全由LLM通过prompt自主决定
        不再使用硬编码的关键词匹配
        """
        await self._ensure_db()
        
        # 情感分析和奖惩现在完全由AI通过prompt自主决定
        # 无需在此处进行任何处理
        pass
    
    def _get_user_sync(self, user_id: str) -> dict:
        """同步获取用户信息"""
        import sqlite3
        db_path = os.path.join(os.path.dirname(__file__), "data", "signin.db")
        with sqlite3.connect(db_path) as db:
            cursor = db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            )
            row = cursor.fetchone()
            
            if row:
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
                try:
                    favor_value = int(row[5]) if len(row) > 5 and row[5] else 0
                except (ValueError, TypeError):
                    favor_value = 0
                return {
                    "user_id": row[0],
                    "balance": balance,
                    "bank_balance": bank_balance,
                    "last_signin_date": last_signin_date,
                    "consecutive_days": consecutive,
                    "favor_value": favor_value
                }
            else:
                return {
                    "user_id": user_id,
                    "balance": 0,
                    "bank_balance": 0,
                    "last_signin_date": None,
                    "consecutive_days": 0,
                    "favor_value": 0
                }
    
    # ============== LLM 干涉功能 ==============
    @filter.on_llm_request()
    async def intercept_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        """拦截LLM请求，注入好感度信息"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        
        # 使用FavorSystem获取好感度信息
        favor_info = await self.favor_system.get_llm_favor_info(user_id)
        
        # 尝试注入到system_prompt（优先）
        if hasattr(req, 'system_prompt') and req.system_prompt is not None:
            req.system_prompt += favor_info
        elif hasattr(req, 'prompt') and req.prompt is not None:
            # 如果没有system_prompt，则注入到prompt开头
            req.prompt = favor_info + "\n" + req.prompt
        
        return
    
    @filter.on_llm_response(priority=200)
    async def on_llm_response(self, event: AstrMessageEvent, resp: LLMResponse) -> None:
        """处理LLM响应，检查是否包含奖惩指令"""
        logger.info("[on_llm_response] 方法被调用!")
        try:
            await self._ensure_db()
            
            user_id = str(event.get_sender_id())
            
            # 获取AI的回复内容
            response_text = ""
            if hasattr(resp, 'completion_text') and resp.completion_text:
                response_text = resp.completion_text
            elif hasattr(resp, 'text') and resp.text:
                response_text = resp.text
            elif hasattr(resp, 'content') and resp.content:
                response_text = resp.content
            
            logger.info(f"[on_llm_response] 收到AI回复，用户 {user_id}，内容长度 {len(response_text)}")
            
            if not response_text:
                logger.info("[on_llm_response] 回复内容为空，跳过处理")
                return
            
            # 检查是否包含扣除星声指令 [扣除星声:数量]
            penalty_match = re.search(r'\[扣除星声:(\d+)\]', response_text)
            logger.info(f"[on_llm_response] 扣除星声匹配结果: {penalty_match is not None}")
            if penalty_match:
                penalty_amount = int(penalty_match.group(1))
                logger.info(f"[on_llm_response] 提取到扣除金额: {penalty_amount}")
                # 获取用户资产
                user_assets = await self.favor_system.get_user_assets(user_id)
                user_total = user_assets['total']
                max_penalty = int(user_total * 0.05)  # 5%资产
                logger.info(f"[on_llm_response] 用户总资产: {user_total}, 扣除上限: {max_penalty}")
                
                # 限制扣除金额
                actual_penalty = min(penalty_amount, max_penalty)
                logger.info(f"[on_llm_response] 实际扣除金额: {actual_penalty}")
                
                if actual_penalty > 0:
                    # 执行扣除
                    async with aiosqlite.connect(self.db_path) as db:
                        await db.execute(
                            "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                            (actual_penalty, user_id)
                        )
                        await db.commit()
                    
                    logger.info(f"[好感度系统] AI扣除用户 {user_id} {actual_penalty} 星声")
                else:
                    logger.info(f"[on_llm_response] 实际扣除金额为0，跳过执行")
            
            # 检查是否包含奖励星声指令 [奖励星声:数量]
            reward_match = re.search(r'\[奖励星声:(\d+)\]', response_text)
            logger.info(f"[on_llm_response] 奖励星声匹配结果: {reward_match is not None}")
            if reward_match:
                reward_amount = int(reward_match.group(1))
                logger.info(f"[on_llm_response] 提取到奖励金额: {reward_amount}")
                # 获取经济总量
                total_economy = await self.favor_system.get_total_economy()
                max_reward = max(10, int(total_economy * 0.0001))  # max(10, 0.01%经济总量)
                logger.info(f"[on_llm_response] 经济总量: {total_economy}, 奖励上限: {max_reward}")
                
                # 限制奖励金额
                actual_reward = min(reward_amount, max_reward)
                logger.info(f"[on_llm_response] 实际奖励金额: {actual_reward}")
                
                if actual_reward > 0:
                    # 执行奖励
                    async with aiosqlite.connect(self.db_path) as db:
                        await db.execute(
                            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                            (actual_reward, user_id)
                        )
                        await db.commit()
                    
                    logger.info(f"[好感度系统] AI奖励用户 {user_id} {actual_reward} 星声")
                else:
                    logger.info(f"[on_llm_response] 实际奖励金额为0，跳过执行")
            
            # 检查是否包含好感值变化指令 [好感值变化:+数量] 或 [好感值变化:-数量]
            favor_match = re.search(r'\[好感值变化:([+-]?\d+(?:\.\d+)?)\]', response_text)
            if favor_match:
                favor_change = float(favor_match.group(1))
                # 限制变化范围在-10到+10之间
                favor_change = max(-10, min(10, favor_change))
                # 四舍五入到整数
                favor_change = round(favor_change)
                
                if favor_change != 0:
                    # 执行好感值变化
                    async with aiosqlite.connect(self.db_path) as db:
                        await db.execute(
                            "UPDATE users SET favor_value = COALESCE(favor_value, 0) + ? WHERE user_id = ?",
                            (favor_change, user_id)
                        )
                        await db.commit()
                    
                    action = "增加" if favor_change > 0 else "减少"
                    logger.info(f"[好感度系统] AI{action}用户 {user_id} {abs(favor_change)} 点好感值")
            
            # 检查是否包含关系更新指令 [关系:描述]
            rel_match = re.search(r'\[关系:([^\]]+)\]', response_text)
            logger.info(f"[on_llm_response] 关系匹配结果: {rel_match is not None}")
            if rel_match:
                new_relationship = rel_match.group(1).strip()
                logger.info(f"[on_llm_response] 提取到关系描述: {new_relationship}")
                if new_relationship and len(new_relationship) <= 100:
                    # 更新关系描述（带CD检查）
                    result = await self.favor_system.update_relationship_desc(user_id, new_relationship)
                    logger.info(f"[on_llm_response] 更新关系结果: {result}")
                    if result['success']:
                        logger.info(f"[好感度系统] AI更新用户 {user_id} 的关系描述: {new_relationship}")
                    else:
                        logger.info(f"[好感度系统] AI尝试更新用户 {user_id} 的关系描述失败: {result['message']}")
        except Exception as e:
            logger.error(f"[on_llm_response] 处理异常: {e}")
    
    # ============== 银行系统 ==============
    @filter.command("银行")
    async def cmd_bank(self, event: AstrMessageEvent):
        """银行信息"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        bank_info = await self.bank_service.get_bank_info(user_id)
        
        vip_status = "🎁 贵宾卡生效中（利率1.5%，取款免手续费）\n" if bank_info["has_vip"] else ""
        
        msg = (
            f"🏦 我的银行\n"
            f"{vip_status}"
            f"🏦 存款：{format_num(bank_info['bank'])}星声（日息{bank_info['rate_pct']}%）\n"
            f"💵 抽卡资源：{format_num(bank_info['balance'])}星声\n"
            f"💡 提示：每天首次查询/存取时自动结算利息"
        )
        
        yield event.plain_result(msg)
    
    @filter.command("存款")
    async def cmd_deposit(self, event: AstrMessageEvent):
        """存款"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        parts = event.message_str.split()
        
        try:
            amount = int(parts[-1])
            if amount <= 0:
                raise ValueError()
        except:
            yield event.plain_result("? 用法：/存款 100")
            return
        
        result = await self.bank_service.deposit(user_id, amount)
        if not result["success"]:
            yield event.plain_result(result["message"])
            return
        
        vip_str = "（贵宾卡生效）" if result["has_vip"] else ""
        
        yield event.plain_result(
            f"⛔ 存款成功！\n"
            f"🎁 银行存款：{format_num(result['new_bank'])}星声\n"
            f"📦 剩余抽卡资源：{format_num(result['new_cash'])}星声\n"
            f"📈 日息{result['rate_pct']}%{vip_str}"
        )
    
    @filter.command("取款")
    async def cmd_withdraw(self, event: AstrMessageEvent):
        """取款"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        parts = event.message_str.split()
        
        try:
            amount = int(parts[-1])
            if amount <= 0:
                raise ValueError()
        except:
            yield event.plain_result("? 用法：/取款 100")
            return
        
        result = await self.bank_service.withdraw(user_id, amount)
        if not result["success"]:
            yield event.plain_result(result["message"])
            return
        
        fee_str = "0（贵宾卡免手续费）" if result["has_vip"] else f"{result['fee']}（0.1%）"
        
        yield event.plain_result(
            f"⛔ 取款成功！\n"
            f"�� 取出：{format_num(result['amount'])}星声\n"
            f"🎁 手续费：{fee_str}\n"
            f"💵 到账抽卡资源：{format_num(result['actual'])}星声\n"
            f"💵 现在抽卡资源：{format_num(result['new_cash'])}星声\n"
            f"📦 剩余存款：{format_num(result['new_bank'])}星声"
        )
    
    # ============== 商店系统 ==============
    @filter.command("商店")
    async def cmd_shop(self, event: AstrMessageEvent):
        """商店"""
        await self._ensure_db()
        
        items = await self.shop_service.get_shop_items()
        lines = ["🛍️ 莫塔里银行商店", "═══════════════════"]
        
        for name, info in items.items():
            limit = f"（每日限购{info['daily_limit']}次）" if info['daily_limit'] > 0 else "（永久有效）"
            lines.append(f"📦 {name}")
            lines.append(f"💰 价格：{format_num(info['price'])}星声{limit}")
            lines.append(f"📝 {info['desc']}")
            lines.append("")
        
        lines.append(f"⚠️ 注意：每日最多占卜{CONFIG.LOTTERY_LIMIT}次")
        lines.append("💡 用法：/购买 商品名 数量")
        
        yield event.plain_result("\n".join(lines))
    
    @filter.command("购买")
    async def cmd_buy(self, event: AstrMessageEvent):
        """购买物品"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        parts = event.message_str.split()
        
        if len(parts) < 2:
            yield event.plain_result("? 用法：/购买 商品名 数量")
            return
        
        item_name = parts[1]
        try:
            count = int(parts[2]) if len(parts) >= 3 else 1
            if count <= 0:
                raise ValueError()
        except:
            count = 1
        
        result = await self.shop_service.buy_item(user_id, item_name, count)
        if not result["success"]:
            yield event.plain_result(result["message"])
            return
        
        # 检查成就
        await self.achievement_service.check_achievements(user_id, "buy", {"item": item_name})
        
        yield event.plain_result(
            f"⛔ 购买成功！\n"
            f"🎁 {result['item_name']} x{result['count']}\n"
            f"🎁 花费：{format_num(result['total_price'])}星声\n"
            f"📦 剩余星声：{format_num(result['new_balance'])}星声"
        )
    
    @filter.command("背包")
    async def cmd_bag(self, event: AstrMessageEvent):
        """查看背包"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        inventory = await self.shop_service.get_inventory(user_id)
        
        # 检查花朵成就
        if inventory["flower_count"] >= 99:
            await self.achievement_service.check_achievements(user_id, "flower_check", {"count": inventory["flower_count"]})

        if not inventory["items"]:
            msg = "🎁 背包空空如也\n"
        else:
            msg = "🎁 我的背包\n═══════════════════\n"
            for name, qty in inventory["items"]:
                msg += f"📦 {name} x{qty}\n"

        msg += f"\n🎁 今日剩余占卜次数：{inventory['remaining_lottery_count']}/{CONFIG.LOTTERY_LIMIT}次\n"
        msg += "🎁 使用：/使用 占卜券 金额"

        yield event.plain_result(msg)
    
    @filter.command("使用")
    async def cmd_use(self, event: AstrMessageEvent):
        """使用物品"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        parts = event.message_str.split()

        if len(parts) < 3:
            yield event.plain_result("? 用法：/使用 物品名称 数量")
            return

        item_name = parts[1]

        try:
            quantity = int(parts[2])
            if quantity <= 0:
                raise ValueError()
        except:
            yield event.plain_result("? 请输入有效的数量！")
            return

        # 获取好感值商品配置
        favor_items = self.favor_system.get_favor_items()

        # 处理好感值商品
        if item_name in favor_items:
            # 检查背包中是否有足够的物品
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?",
                    (user_id, item_name)
                )
                row = await cursor.fetchone()
                
                if not row or row[0] < quantity:
                    yield event.plain_result(f"? 你没有足够的{item_name}！")
                    return
                
                # 扣除物品
                await db.execute(
                    "UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND item_name = ?",
                    (quantity, user_id, item_name)
                )
                
                # 增加好感值
                favor_increase = favor_items[item_name] * quantity
                await db.execute(
                    "UPDATE users SET favor_value = favor_value + ? WHERE user_id = ?",
                    (favor_increase, user_id)
                )
                
                # 音乐会门票特殊效果：3%概率获得金色成就
                achievement_msg = ""
                if item_name == "音乐会门票":
                    if random.random() < 0.03:  # 3%概率
                        # 授予金色成就：形同陌路
                        achievement_id = "golden_stranger"
                        await self.achievement_service._grant_achievement(db, user_id, achievement_id)
                        achievement_msg = "\n🎁 恭喜获得金色成就：形同陌路"
                
                await db.commit()
            
            yield event.plain_result(f"? 使用成功！\n使用了 {quantity} 个{item_name}\n增加了 {favor_increase} 点好感值{achievement_msg}")
        
        # 处理占卜券
        elif item_name == "占卜券":
            if len(parts) < 3:
                yield event.plain_result("? 用法：/使用 占卜券 <星声数量>")
                return
            try:
                bet = int(parts[2])
                if bet <= 0:
                    raise ValueError()
            except ValueError:
                yield event.plain_result("? 请输入有效的星声数量！")
                return

            # 执行占卜
            result = await self.shop_service.do_lottery(user_id, bet, is_allin=False)
            if not result["success"]:
                yield event.plain_result(result["message"])
                return
            
            # 检查成就
            await self.achievement_service.check_achievements(user_id, "lottery", {"multiplier": result["multiplier"]})

            # 构建结果消息
            multiplier_str = f"{result['multiplier']:.1f}x" if isinstance(result['multiplier'], float) else f"{result['multiplier']}x"
            if result["profit"] >= 0:
                result_str = f"盈利：+{format_num(result['profit'])}星声 🎁"
            else:
                result_str = f"亏损：{format_num(result['profit'])}星声 🎁"

            allin_tag = "🎁 【ALL IN】 " if result["is_allin"] else ""

            msg = (
                f"{allin_tag}{result['result_emoji']} 占卜结果：{result['result_type']}！\n"
                f"🎁 倍数：{multiplier_str}\n"
                f"🎁 投入：{format_num(result['bet'])}星声 → 获得：{format_num(result['final'])}星声\n"
                f"🎁 {result_str}\n"
                f"🎁 当前抽卡资源：{format_num(result['new_cash'])}星声\n"
                f"📦 剩余占卜券：{result['ticket_count']}张\n"
                f"🎁 今日占卜：{result['used_count']}/{CONFIG.LOTTERY_LIMIT}次"
            )

            yield event.plain_result(msg)
        
        else:
            yield event.plain_result(f"? 无法使用该物品！")
    
    @filter.command("赠送")
    async def cmd_gift(self, event: AstrMessageEvent):
        """快捷购买并直接使用好感值商品"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        parts = event.message_str.split()
        
        if len(parts) < 2:
            yield event.plain_result("? 用法：/赠送 商品名 [数量]")
            return
        
        item_name = parts[1]
        try:
            quantity = int(parts[2]) if len(parts) >= 3 else 1
            if quantity <= 0:
                raise ValueError()
        except:
            quantity = 1
        
        # 获取好感值商品列表
        favor_items = self.favor_system.get_favor_items()
        
        # 检查是否是好感值商品
        if item_name not in favor_items:
            yield event.plain_result(f"? {item_name} 不是好感值商品，无法使用/赠送命令！")
            return
        
        # 检查商品是否在商店中
        if item_name not in CONFIG.SHOP_ITEMS:
            yield event.plain_result(f"? 商店中没有 {item_name}！")
            return
        
        # 获取商品价格
        item_info = CONFIG.SHOP_ITEMS[item_name]
        price = item_info["price"]
        daily_limit = item_info.get("daily_limit", 0)
        total_price = price * quantity
        
        # 检查用户余额
        user = await self._get_user(user_id)
        if user["balance"] < total_price:
            yield event.plain_result(f"? 余额不足！需要 {format_num(total_price)} 星声，当前余额 {format_num(user['balance'])} 星声")
            return
        
        # 检查每日限购
        if daily_limit > 0:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT COALESCE(SUM(count), 0) FROM purchase_log WHERE user_id = ? AND item_name = ? AND purchase_date = ?",
                    (user_id, item_name, today_str())
                )
                row = await cursor.fetchone()
                purchased_today = row[0] if row else 0
                
                if purchased_today + quantity > daily_limit:
                    remaining = daily_limit - purchased_today
                    yield event.plain_result(f"? 今日购买次数已达上限！还可购买 {remaining} 个")
                    return
        
        # 扣除星声
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (total_price, user_id)
            )
            
            # 记录购买日志
            await db.execute(
                "INSERT OR REPLACE INTO purchase_log (user_id, item_name, purchase_date, count) VALUES (?, ?, ?, COALESCE((SELECT count FROM purchase_log WHERE user_id = ? AND item_name = ? AND purchase_date = ?), 0) + ?)",
                (user_id, item_name, today_str(), user_id, item_name, today_str(), quantity)
            )
            
            # 直接使用：增加好感值
            favor_increase = favor_items[item_name] * quantity
            await db.execute(
                "UPDATE users SET favor_value = favor_value + ? WHERE user_id = ?",
                (favor_increase, user_id)
            )
            
            # 音乐会门票特殊效果：3%概率获得金色成就
            achievement_msg = ""
            if item_name == "音乐会门票":
                if random.random() < 0.03:  # 3%概率
                    # 授予金色成就：形同陌路
                    achievement_id = "golden_stranger"
                    await self.achievement_service._grant_achievement(db, user_id, achievement_id)
                    achievement_msg = "\n🎁 恭喜获得金色成就：形同陌路"
            
            await db.commit()
        
        yield event.plain_result(
            f"⛔ 赠送成功！\n"
            f"🎁 购买了 {quantity} 个{item_name}\n"
            f"🎁 花费：{format_num(total_price)}星声\n"
            f"🎁 增加了 {favor_increase} 点好感值{achievement_msg}"
        )
    
    @filter.command("Allin")
    async def cmd_allin(self, event: AstrMessageEvent):
        """全部身家梭哈占卜"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())

        # 获取全部身家
        user = await self._get_user(user_id)
        bet = user["balance"]

        if bet <= 0:
            yield event.plain_result("? 你没有星声可以Allin！")
            return

        # 检查是否有占卜券，如果没有则自动购买
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?",
                (user_id, "占卜券")
            )
            row = await cursor.fetchone()
            
            ticket_price = 10  # 占卜券价格
            
            if not row or int(row[0]) <= 0:
                # 没有占卜券，尝试自动购买
                if bet < ticket_price:
                    yield event.plain_result(f"? 你没有占卜券，且星声不足以购买（需要{ticket_price}星声）！")
                    return
                
                # 扣除星声并添加占卜券
                await db.execute(
                    "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                    (ticket_price, user_id)
                )
                await db.execute(
                    """INSERT INTO inventory (user_id, item_name, quantity) 
                        VALUES (?, ?, 1)
                        ON CONFLICT(user_id, item_name) 
                        DO UPDATE SET quantity = quantity + 1""",
                    (user_id, "占卜券")
                )
                await db.commit()
                
                # 更新下注金额（扣除购买占卜券的费用）
                bet -= ticket_price
                
                if bet <= 0:
                    yield event.plain_result("? 购买占卜券后没有剩余星声可以Allin！")
                    return

        # 执行占卜
        result = await self.shop_service.do_lottery(user_id, bet, is_allin=True)
        if not result["success"]:
            yield event.plain_result(result["message"])
            return
        
        # 检查成就
        await self.achievement_service.check_achievements(user_id, "lottery", {"multiplier": result["multiplier"]})

        # 构建结果消息
        multiplier_str = f"{result['multiplier']:.1f}x" if isinstance(result['multiplier'], float) else f"{result['multiplier']}x"
        if result["profit"] >= 0:
            result_str = f"盈利：+{format_num(result['profit'])}星声 🎁"
        else:
            result_str = f"亏损：{format_num(result['profit'])}星声 🎁"

        allin_tag = "🎁 【ALL IN】 " if result["is_allin"] else ""

        msg = (
            f"{allin_tag}{result['result_emoji']} 占卜结果：{result['result_type']}！\n"
            f"🎁 倍数：{multiplier_str}\n"
            f"🎁 投入：{format_num(result['bet'])}星声 → 获得：{format_num(result['final'])}星声\n"
            f"🎁 {result_str}\n"
            f"🎁 当前抽卡资源：{format_num(result['new_cash'])}星声\n"
            f"📦 剩余占卜券：{result['ticket_count']}张\n"
            f"🎁 今日占卜：{result['used_count']}/{CONFIG.LOTTERY_LIMIT}次"
        )

        yield event.plain_result(msg)
    
    @filter.command("占卜概率")
    async def cmd_lottery_prob(self, event: AstrMessageEvent):
        """查看占卜概率分布"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        prob_info = await self.shop_service.get_lottery_probability(user_id)

        lines = [
            "🎁 占卜概率分布",
            "═══════════════════",
            f"🎁 今日剩余：{prob_info['remaining']}/{prob_info['limit']} 次",
            "",
            "倍数范围　　　│ 概率　 │ 结果　　　│",
            "──────────────┼───────┼───────────│"
        ]

        for range_str, prob, result, emoji in prob_info['prob_dist']:
            lines.append(f"{range_str:<13}│ {prob:<6} │ {emoji} {result}")

        lines.extend([
            "",
            "💡 提示：",
            "? 最高可获得 66 倍奖励（1%概率）",
            "? 获得 5 倍以上可解锁「欧皇」成就",
            "? 使用：/使用 占卜券 金额",
            "? Allin：/Allin"
        ])

        yield event.plain_result("\n".join(lines))
    
    # ============== 工作系统 ==============
    @filter.command("找工作")
    async def cmd_work_list(self, event: AstrMessageEvent):
        """工作列表"""
        await self._ensure_db()
        
        works = await self.work_service.get_works()
        lines = ["🎁 人才市场 - 选择你的职业", "═══════════════════"]
        
        for name, config in works.items():
            lines.append(f"{config['emoji']} {name}")
            lines.append(f"   🎁 入职费：{format_num(config['price'])}星声")
            lines.append(f"   🎁 时薪：{format_num(config['min'])}~{format_num(config['max'])}星声/小时")
            lines.append(f"   🎁 {config['desc']}")
            lines.append("")
        
        lines.append("💡 用法：/应聘 职业名")
        
        yield event.plain_result("\n".join(lines))
    
    @filter.command("应聘")
    async def cmd_apply_work(self, event: AstrMessageEvent):
        """应聘工作"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        parts = event.message_str.split()
        
        if len(parts) < 2:
            yield event.plain_result("? 用法：/应聘 职业名")
            return
        
        work_name = parts[1]
        
        result = await self.work_service.apply_work(user_id, work_name)
        if not result["success"]:
            yield event.plain_result(result["message"])
            return
        
        yield event.plain_result(
            f"⛔ 成功入职：{result['emoji']}{result['work_name']}！\n"
            f"🎁 花费：{format_num(result['price'])}星声\n"
            f"🎁 开始时间：{result['start_time']}"
        )
    
    @filter.command("工作状态")
    async def cmd_work_status(self, event: AstrMessageEvent):
        """工作状态"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        result = await self.work_service.get_work_status(user_id)
        
        if not result["success"]:
            yield event.plain_result(result["message"])
            return
        
        msg = (
            f"🎁 当前工作：{result['emoji']}{result['work_name']}\n"
            f"🎁 {result['desc']}\n"
            f"🎁 已工作：{result['hours_passed']}小时\n"
            f"🎁 预计可领：约{format_num(result['pending'])}星声\n"
            f"🎁 累计收入：{format_num(result['total_earned'])}星声\n"
        )
        
        if result["hours_passed"] > 0:
            msg += f"\n🎁 发送 /领工资 领取{result['hours_passed']}小时工资"
        else:
            msg += f"\n? 还需工作{60 - datetime.now().minute}分钟可领工资"
        
        yield event.plain_result(msg)
    
    @filter.command("领工资")
    async def cmd_claim_salary(self, event: AstrMessageEvent):
        """领取工资"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        result = await self.work_service.claim_salary(user_id)
        
        if not result["success"]:
            yield event.plain_result(result["message"])
            return
        
        yield event.plain_result(
            f"🎁 工资到账！\n"
            f"🎁 职业：{result['emoji']}{result['work_name']}\n"
            f"🎁 工作时间：{result['hours']}小时\n"
            f" 获得工资：{format_num(result['total_earnings'])}星声\n"
            f" 当前余额：{format_num(result['new_balance'])}星声"
        )
    
    # ============== 股票系统 ==============
    @filter.command("股市")
    async def cmd_stock_market(self, event: AstrMessageEvent):
        """股市行情"""
        await self._ensure_db()
        
        # 获取市场情绪
        sentiment = await self.stock_service.get_market_sentiment()
        
        stocks = await self.stock_service.get_stock_market()
        
        lines = [
            "🎁 索拉里斯证券交易所",
            "═══════════════════",
            f"🎁 市场情绪：{sentiment}",
            "? 价格每10分钟刷新",
            "🎁 指令：/买入 股票名 数量 | /卖出 股票名 数量 | /持仓 | /股东 股票名",
            "═══════════════════"
        ]
        
        for stock in stocks:
            lines.append(f"{stock['emoji']} {stock['name']}")
            lines.append(f"    当前价：{stock['price']:.2f}（较开盘{stock['arrow']}{stock['change_pct']:+.2f}%）")
            lines.append(f"    市值：{format_num(stock['market_cap'])} 星声{stock['owner_str']}")
            lines.append(f"   🎁 {stock['desc']}")
            lines.append("")
        
        yield event.plain_result("\n".join(lines))
    
    @filter.command("买入")
    async def cmd_buy_stock(self, event: AstrMessageEvent):
        """买入股票"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        parts = event.message_str.split()
        
        if len(parts) < 3:
            yield event.plain_result("? 用法：/买入 股票名 数量")
            return
        
        stock_name = parts[1]
        try:
            quantity = float(parts[2])
            if quantity <= 0:
                raise ValueError()
        except:
            yield event.plain_result("? 数量格式错误")
            return
        
        result = await self.stock_service.buy_stock(user_id, stock_name, quantity)
        if not result["success"]:
            yield event.plain_result(result["message"])
            return
        
        yield event.plain_result(
            f"⛔ 买入成功！\n"
            f"🎁 {result['stock_name']}\n"
            f"🎁 买入价：{result['price']:.2f}\n"
            f" 数量：{result['quantity']}\n"
            f" 花费：{format_num(result['total_cost'])}星声"
        )
    
    @filter.command("卖出")
    async def cmd_sell_stock(self, event: AstrMessageEvent):
        """卖出股票"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        parts = event.message_str.split()
        
        if len(parts) < 3:
            yield event.plain_result("? 用法：/卖出 股票名 数量")
            return
        
        stock_name = parts[1]
        try:
            want_sell = float(parts[2])
            if want_sell <= 0:
                raise ValueError()
        except:
            yield event.plain_result("? 数量格式错误")
            return
        
        result = await self.stock_service.sell_stock(user_id, stock_name, want_sell)
        if not result["success"]:
            yield event.plain_result(result["message"])
            return
        
        yield event.plain_result(
            f"⛔ 卖出成功！\n"
            f"🎁 {result['stock_name']}\n"
            f"🎁 卖出价：{result['price']:.2f}\n"
            f"🎁 数量：{result['quantity']}\n"
            f"🎁 成交额：{format_num(result['sell_amount'])}星声\n"
            f"🎁 手续费：{format_num(result['fee'])}\n"
            f" 净收入：{format_num(result['net_amount'])}星声"
        )
    
    @filter.command("持仓")
    async def cmd_portfolio(self, event: AstrMessageEvent):
        """查看持仓"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        result = await self.stock_service.get_portfolio(user_id)
        
        if not result["success"]:
            yield event.plain_result(result["message"])
            return
        
        lines = ["🎁 我的持仓", "═══════════════════"]
        
        for item in result["portfolio"]:
            lines.append(f"{item['emoji']} {item['stock_name']}")
            lines.append(f"   🎁 持有：{item['quantity']:.2f} | 成本：{item['avg_cost']:.2f}")
            lines.append(f"   🎁 现价：{item['current_price']:.2f} | 市值：{format_num(item['market_value'])}")
            lines.append(f"   {item['arrow']} 盈亏：{item['profit']:+,} ({item['profit_pct']:+.2f}%)")
            lines.append("")
        
        lines.extend([
            "═══════════════════",
            f"🎁 总市值：{format_num(result['total_value'])}",
            f"🎁 总成本：{format_num(result['total_cost'])}",
            f" 总盈亏：{result['total_profit']:+,} ({result['total_profit_pct']:+.2f}%)"
        ])
        
        yield event.plain_result("\n".join(lines))
    
    @filter.command("创立公司")
    async def cmd_create_company(self, event: AstrMessageEvent):
        """创立上市公司"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        parts = event.message_str.split()
        
        if len(parts) < 4:
            yield event.plain_result("💡 用法：/创立公司 公司名 初始股价 简介\n例：/创立公司 莫宁科技 100 探索未知的科技公司")
            return
        
        company_name = parts[1]
        try:
            init_price = float(parts[2])
            if init_price < 1 or init_price > 10000:
                raise ValueError()
        except:
            yield event.plain_result("? 初始股价需在1-10000之间")
            return
        
        desc = " ".join(parts[3:]) if len(parts) > 3 else "玩家创立的企业"
        
        result = await self.stock_service.create_company(user_id, company_name, init_price, desc)
        if not result["success"]:
            yield event.plain_result(result["message"])
            return
        
        yield event.plain_result(
            f"🎁 公司创立成功！\n"
            f"🎁 {result['company_name']}\n"
            f"🎁 初始股价：{result['init_price']:.2f}星声\n"
            f" {result['desc']}\n"
            f"🎁 启动资金：{format_num(result['required'])}星声\n"
            f" 您获得10万股创始股份"
        )
    
    @filter.command("宣告破产")
    async def cmd_bankrupt(self, event: AstrMessageEvent):
        """宣告公司破产"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        parts = event.message_str.split()
        
        if len(parts) < 2:
            yield event.plain_result("💡 用法：/宣告破产 公司名")
            return
        
        company_name = parts[1]
        
        result = await self.stock_service.bankrupt(user_id, company_name)
        if not result["success"]:
            yield event.plain_result(result["message"])
            return
        
        yield event.plain_result(
            f"🎁 {result['company_name']} 已宣告破产退市\n"
            f"所有股东持仓将保留但无法交易"
        )
    
    @filter.command("研发")
    async def cmd_research(self, event: AstrMessageEvent):
        """公司研发（提升股价）"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        parts = event.message_str.split()
        
        if len(parts) < 3:
            yield event.plain_result("💡 用法：/研发 公司名 投入金额")
            return
        
        company_name = parts[1]
        try:
            amount = int(parts[2])
            if amount < 10000:
                raise ValueError()
        except:
            yield event.plain_result("? 研发资金至少10000星声")
            return
        
        result = await self.stock_service.research(user_id, company_name, amount)
        if not result["success"]:
            yield event.plain_result(result["message"])
            return
        
        yield event.plain_result(
            f" 研发成功！\n"
            f"🎁 {result['company_name']}\n"
            f"🎁 投入：{format_num(result['amount'])}星声\n"
            f" 股价提升：+{result['boost']*100:.2f}%\n"
            f" 新股价：{result['new_price']:.2f}星声"
        )
    
    @filter.command("股东")
    async def cmd_shareholders(self, event: AstrMessageEvent):
        """查看股东列表"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        parts = event.message_str.split()
        
        if len(parts) < 2:
            yield event.plain_result("💡 用法：/股东 股票名")
            return
        
        stock_name = parts[1]
        
        result = await self.stock_service.get_shareholders(stock_name)
        if not result["success"]:
            yield event.plain_result(result["message"])
            return
        
        lines = [f"🎁 {result['stock_name']} 股东列表", "═══════════════════"]
        
        if result["controlling_shareholder"]:
            lines.append(f"🎁 控股股东：{result['controlling_shareholder']['name']}")
            lines.append("")
        
        lines.append(f"🎁 总股数：{result['total_shares']:.2f}")
        lines.append("")
        lines.append("股东列表：")
        lines.append("─────────────────────")
        
        for shareholder in result["shareholders"]:
            lines.append(f"{shareholder['name']}: {shareholder['shares']:.2f}股 ({shareholder['ratio']:.2f}%)")
        
        yield event.plain_result("\n".join(lines))
    
    @filter.command("k线")
    async def cmd_stock_kline(self, event: AstrMessageEvent):
        """查看股票价格走势（带图表）"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        parts = event.message_str.split()

        if len(parts) < 2:
            yield event.plain_result("💡 用法：/k线 股票名")
            return

        stock_name = parts[1]

        result = await self.stock_service.get_stock_kline(stock_name)
        if not result["success"]:
            yield event.plain_result(result["message"])
            return

        price_data = result.get("price_data", [])
        if not price_data:
            yield event.plain_result(f"📈 {result['stock_name']} 最近24小时价格走势\n═══════════════════\n📊 暂无价格数据")
            return

        lines = [f"📈 {result['stock_name']} 最近24小时价格走势", "═══════════════════"]

        # 生成文本图表
        prices = [d['price'] for d in price_data]
        min_price = min(prices)
        max_price = max(prices)
        price_range = max_price - min_price if max_price != min_price else 1

        # 图表高度为10行
        chart_height = 10
        chart_width = min(len(price_data), 30)  # 最多显示30个数据点

        lines.append("")
        lines.append("价格/时间 →")

        # 生成图表每一行
        for row in range(chart_height, -1, -1):
            price_level = min_price + (price_range * row / chart_height)

            # 价格标签
            if row == chart_height:
                label = f"{max_price:>8.2f} ┤"
            elif row == 0:
                label = f"{min_price:>8.2f} ┤"
            else:
                label = "         │"

            # 绘制价格点
            line = label
            for i in range(chart_width):
                if i < len(price_data):
                    price = price_data[i]['price']
                    # 计算该价格应该在哪个高度
                    price_row = int((price - min_price) / price_range * chart_height) if price_range > 0 else chart_height // 2
                    if price_row == row:
                        line += "●"
                    elif price_row > row:
                        line += "│"
                    else:
                        line += " "
                else:
                    line += " "

            lines.append(line)

        # 底部横线
        lines.append("         └" + "─" * chart_width)

        # 时间标签（只显示首尾）
        if len(price_data) > 0:
            first_time = price_data[0]['timestamp'].split()[1] if ' ' in price_data[0]['timestamp'] else price_data[0]['timestamp']
            last_time = price_data[-1]['timestamp'].split()[1] if ' ' in price_data[-1]['timestamp'] else price_data[-1]['timestamp']
            time_label = f"         {first_time:<{chart_width-5}}{last_time}"
            lines.append(time_label)

        lines.append("")
        lines.append(f"📊 数据点: {len(price_data)}个 | 最高: {max_price:.2f} | 最低: {min_price:.2f}")

        yield event.plain_result("\n".join(lines))
    
    # ============== 结社系统 ==============
    @filter.command("结社")
    async def cmd_society(self, event: AstrMessageEvent):
        """结社看板"""
        await self._ensure_db()
        
        stats = await self.society_service.get_society_stats()
        
        lines = [" 索拉里斯秘密结社", "═══════════════════"]
        
        if stats["total"] == 0:
            lines.append("目前还没有人加入任何结社")
        else:
            lines.append(f"🎁 总成员：{stats['total']} 人")
            lines.append("")
            
            for name, config in CONFIG.SOCIETIES.items():
                data = stats["stats"].get(name, {"count": 0, "percentage": 0})
                lines.append(f"{config['emoji']} {name}")
                lines.append(f"   🎁 人数：{data['count']} 人 ({data['percentage']:.1f}%)")
                lines.append(f"   🎁 {config['desc']}")
                lines.append("")
        
        lines.append("💡 用法：/加入结社 结社名")
        
        yield event.plain_result("\n".join(lines))
    
    @filter.command("加入结社")
    async def cmd_join_society(self, event: AstrMessageEvent):
        """加入结社"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        parts = event.message_str.split()
        
        if len(parts) < 2:
            yield event.plain_result("💡 用法：/加入结社 结社名")
            return
        
        society_name = parts[1]
        
        result = await self.society_service.join_society(user_id, society_name)
        if not result["success"]:
            yield event.plain_result(result["message"])
            return
        
        yield event.plain_result(
            f"⛔ 成功加入 {result['emoji']}{result['society_name']}！\n"
            f"🎁 {result['desc']}"
        )
    
    @filter.command("我的结社")
    async def cmd_my_society(self, event: AstrMessageEvent):
        """查看我的结社信息"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        result = await self.society_service.get_my_society(user_id)

        if not result["success"]:
            yield event.plain_result(result["message"])
            return

        lines = [
            f"{result['emoji']} {result['society_name']}",
            "═══════════════════",
            f"🎁 {result['desc']}",
            f"🎁 成员：{result['member_count']}人",
            f"🎁 加入时间：{result['join_time']}"
        ]

        # 显示结社福利
        if result.get("benefits"):
            lines.append("")
            lines.append("🎁 结社福利：")
            lines.append(f"   {result['benefits']['type']}：{result['benefits']['detail']}")

        # 显示结社第一
        if result.get("top_user") and result["top_user"]:
            lines.append("")
            top_user = result["top_user"]
            if top_user["is_me"]:
                lines.append(f"🎁 {top_user['title']}：{top_user['name']}（你）")
            else:
                lines.append(f"🎁 {top_user['title']}：{top_user['name']}")
            lines.append(f"   资产：{format_num(top_user['asset'])}星声")

        lines.append("")
        lines.append(f"? 更换冷却：{result['cooldown']}小时")

        yield event.plain_result("\n".join(lines))

    # ============== 公告功能 ==============
    @filter.command("发布公告")
    async def cmd_publish_announcement(self, event: AstrMessageEvent):
        """发布公告到所有群 - /发布公告 <内容>"""
        user_id = str(event.get_sender_id())
        
        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("⚠️ 权限不足！此命令仅管理员可用")
            return
        
        await self._ensure_db()
        
        sender_name = self._get_sender_name(event)
        
        # 获取公告内容 - 使用 message_str 获取完整消息
        msg_text = event.message_str
        args = msg_text.split(maxsplit=1)
        if len(args) < 2:
            yield event.plain_result("📢 请输入公告内容：/发布公告 <内容>")
            return
        
        content = args[1].strip()
        if not content:
            yield event.plain_result("📢 公告内容不能为空！")
            return
        
        # 发布公告到数据库
        title = "系统公告"
        result = await self.announcement_service.publish_announcement(
            title=title,
            content=content,
            author_id=user_id,
            author_name=sender_name
        )
        
        if not result["success"]:
            yield event.plain_result(f"📢 发布公告失败：{result.get('message', '未知错误')}")
            return
        
        # 广播到所有群
        broadcast_result = await self._broadcast_announcement(event, content)
        
        yield event.plain_result(
            f"📢 公告发布成功！\n"
            f"内容：{content[:50]}{'...' if len(content) > 50 else ''}\n"
            f"广播结果：成功 {broadcast_result['success']} 个群，失败 {broadcast_result['failed']} 个群"
        )
    
    async def _broadcast_announcement(self, event, content: str) -> dict:
        """广播公告到白名单群"""
        success_count = 0
        failed_count = 0
        
        # 获取白名单（使用 getattr 提供默认值，兼容旧配置）
        whitelist = getattr(CONFIG, 'ANNOUNCEMENT_WHITELIST', ["1047215229", "468563035", "1078585038"])
        if not whitelist:
            logger.warning("公告白名单为空，无法广播")
            return {"success": 0, "failed": 0, "skipped": 0}
        
        try:
            # 使用 context 获取平台管理器
            if hasattr(self, 'context') and self.context:
                try:
                    # 获取所有平台实例
                    platform_insts = self.context.platform_manager.platform_insts
                    
                    for platform in platform_insts:
                        try:
                            # 获取平台适配器
                            adapter = platform
                            if hasattr(adapter, 'bot'):
                                bot = adapter.bot
                                
                                # 只发送到白名单中的群
                                for group_id_str in whitelist:
                                    try:
                                        group_id = int(group_id_str)
                                        # 构造公告消息
                                        announcement_msg = f"📢【系统公告】📢\n═══════════════════\n{content}\n═══════════════════\n⏰ 发布时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"
                                        
                                        # 发送群消息
                                        await bot.api.call_action(
                                            "send_group_msg",
                                            group_id=group_id,
                                            message=[{"type": "text", "data": {"text": announcement_msg}}]
                                        )
                                        success_count += 1
                                        logger.info(f"公告已发送到群 {group_id}")
                                    except Exception as e:
                                        logger.warning(f"广播到群 {group_id_str} 失败: {e}")
                                        failed_count += 1
                        except Exception as e:
                            logger.warning(f"获取平台适配器失败: {e}")
                            continue
                except Exception as e:
                    logger.warning(f"获取平台实例失败: {e}")
                    failed_count = len(whitelist)
            else:
                # 尝试使用 event.bot
                if hasattr(event, 'bot') and event.bot:
                    try:
                        # 只发送到白名单中的群
                        for group_id_str in whitelist:
                            try:
                                group_id = int(group_id_str)
                                announcement_msg = f"📢【系统公告】📢\n═══════════════════\n{content}\n═══════════════════\n⏰ 发布时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"
                                
                                await event.bot.api.call_action(
                                    "send_group_msg",
                                    group_id=group_id,
                                    message=[{"type": "text", "data": {"text": announcement_msg}}]
                                )
                                success_count += 1
                                logger.info(f"公告已发送到群 {group_id}")
                            except Exception as e:
                                logger.warning(f"广播到群 {group_id_str} 失败: {e}")
                                failed_count += 1
                    except Exception as e:
                        logger.warning(f"使用 event.bot 广播失败: {e}")
                        failed_count = len(whitelist)
                else:
                    logger.warning("无法获取 bot 实例，无法广播公告")
                    failed_count = len(whitelist)
        except Exception as e:
            logger.error(f"广播公告时出错: {e}")
            failed_count = len(whitelist)
        
        return {"success": success_count, "failed": failed_count}
    
    @filter.command("公告")
    async def cmd_announcement(self, event: AstrMessageEvent):
        """查看最新公告 - /公告"""
        await self._ensure_db()
        
        # 获取最新公告
        announcement = await self.announcement_service.get_latest_announcement()
        
        if not announcement:
            yield event.plain_result("📢 暂无公告")
            return
        
        lines = [
            f"📢【{announcement['title']}】📢",
            "═══════════════════",
            f"{announcement['content']}",
            "═══════════════════",
            f"👤 发布者：{announcement['author_name']}",
            f"⏰ 发布时间：{announcement['publish_time']}"
        ]
        
        yield event.plain_result("\n".join(lines))
    
    @filter.command("公告列表")
    async def cmd_announcement_list(self, event: AstrMessageEvent):
        """查看历史公告列表 - /公告列表"""
        await self._ensure_db()
        
        # 获取最近10条公告
        announcements = await self.announcement_service.get_announcements(limit=10)
        
        if not announcements:
            yield event.plain_result("📢 暂无公告")
            return
        
        lines = ["📋【历史公告列表】📋", "═══════════════════"]
        
        for i, ann in enumerate(announcements, 1):
            content_preview = ann['content'][:30] + "..." if len(ann['content']) > 30 else ann['content']
            lines.append(f"{i}. {ann['title']}")
            lines.append(f"   内容：{content_preview}")
            lines.append(f"   时间：{ann['publish_time']}")
            lines.append("")

        lines.append(f"📊 共 {len(announcements)} 条公告")
        lines.append("💡 使用 /公告 查看最新公告")
        
        yield event.plain_result("\n".join(lines))
    
    @filter.command("公告白名单")
    async def cmd_announcement_whitelist(self, event: AstrMessageEvent):
        """管理公告推送白名单 - /公告白名单 <add/remove/list> [群号]"""
        user_id = str(event.get_sender_id())
        
        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("⚠️ 权限不足！此命令仅管理员可用")
            return
        
        # 获取命令参数
        msg_text = event.message_str
        args = msg_text.split()
        
        # 获取白名单（使用 getattr 提供默认值，兼容旧配置）
        whitelist = getattr(CONFIG, 'ANNOUNCEMENT_WHITELIST', ["1047215229", "468563035", "1078585038"])
        
        if len(args) < 2:
            # 显示当前白名单
            if not whitelist:
                yield event.plain_result("📋 当前公告白名单为空\n💡 用法：/公告白名单 add 群号\n   /公告白名单 remove 群号\n   /公告白名单 list")
                return
            
            lines = ["📋【公告推送白名单】", "═══════════════════"]
            for i, group_id in enumerate(whitelist, 1):
                lines.append(f"{i}. {group_id}")
            lines.append("═══════════════════")
            lines.append(f"📊 共 {len(whitelist)} 个群")
            lines.append("💡 用法：/公告白名单 add 群号")
            lines.append("   /公告白名单 remove 群号")
            lines.append("   /公告白名单 list")
            yield event.plain_result("\n".join(lines))
            return
        
        action = args[1].lower()
        
        if action == "list":
            # 列出白名单
            if not whitelist:
                yield event.plain_result("📋 当前公告白名单为空")
                return
            
            lines = ["📋【公告推送白名单】", "═══════════════════"]
            for i, group_id in enumerate(whitelist, 1):
                lines.append(f"{i}. {group_id}")
            lines.append("═══════════════════")
            lines.append(f"📊 共 {len(whitelist)} 个群")
            yield event.plain_result("\n".join(lines))
        
        elif action == "add":
            # 添加群到白名单
            if len(args) < 3:
                yield event.plain_result("📢 用法：/公告白名单 add 群号")
                return
            
            group_id = args[2].strip()
            if not group_id.isdigit():
                yield event.plain_result("❌ 群号必须是数字！")
                return
            
            if group_id in whitelist:
                yield event.plain_result(f"📢 群 {group_id} 已在白名单中")
                return
            
            whitelist.append(group_id)
            yield event.plain_result(f"✅ 已添加群 {group_id} 到白名单\n📊 当前白名单共 {len(whitelist)} 个群")
        
        elif action == "remove":
            # 从白名单移除群
            if len(args) < 3:
                yield event.plain_result("📢 用法：/公告白名单 remove 群号")
                return
            
            group_id = args[2].strip()
            if group_id not in whitelist:
                yield event.plain_result(f"📢 群 {group_id} 不在白名单中")
                return
            
            whitelist.remove(group_id)
            yield event.plain_result(f"✅ 已从白名单移除群 {group_id}\n📊 当前白名单共 {len(whitelist)} 个群")
        
        else:
            yield event.plain_result("❌ 未知操作！\n💡 用法：/公告白名单 add 群号\n   /公告白名单 remove 群号\n   /公告白名单 list")