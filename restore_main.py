#!/usr/bin/env python3
"""
恢复 main.py 的辅助脚本
将所有代码段合并到 main.py
"""

import os

# 代码段列表 - 按顺序合并
code_segments = []

# 第1段：文件头和导入
code_segments.append('''"""
莫宁宁的币 - 经济系统插件 v2.0.0
作者：莫宁
功能：签到、银行、商店、股票、工作、结社、成就、好感度等经济系统
"""
import os
import sys
import re
import random
import asyncio
import aiosqlite
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.provider import ProviderRequest, LLMResponse
from astrbot.api import logger

# 导入服务模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CONFIG
from achievements import ACHIEVEMENTS
from signin_service import SigninService
from bank_service import BankService
from shop_service import ShopService
from stock_service import StockService
from work_service import WorkService
from society_service import SocietyService
from achievement_service import AchievementService
from tax_service import TaxService
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
            # 用户基础表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    nickname TEXT,
                    balance INTEGER DEFAULT 1000,
                    bank_balance INTEGER DEFAULT 0,
                    last_sign_date TEXT,
                    sign_streak INTEGER DEFAULT 0,
                    total_sign_days INTEGER DEFAULT 0,
                    vip_expiry TEXT,
                    created_at TEXT,
                    favor_value INTEGER DEFAULT 0
                )
            """)
            
            # 添加 favor_value 列（如果不存在）
            try:
                await db.execute("ALTER TABLE users ADD COLUMN favor_value INTEGER DEFAULT 0")
            except aiosqlite.OperationalError:
                pass  # 列已存在
            
            # 签到记录表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_sign (
                    user_id TEXT PRIMARY KEY,
                    last_sign_date TEXT,
                    sign_streak INTEGER DEFAULT 0,
                    total_sign_days INTEGER DEFAULT 0
                )
            """)
            
            # 背包表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    user_id TEXT,
                    item_name TEXT,
                    quantity INTEGER DEFAULT 0,
                    purchase_price INTEGER,
                    purchase_date TEXT,
                    PRIMARY KEY (user_id, item_name)
                )
            """)
            
            # 购买记录表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS purchase_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    item_name TEXT,
                    quantity INTEGER,
                    total_price INTEGER,
                    purchase_date TEXT
                )
            """)
            
            # 占卜记录表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS lottery_log (
                    user_id TEXT,
                    date TEXT,
                    count INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, date)
                )
            """)
            
            # 股票持仓表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS stock_holdings (
                    user_id TEXT,
                    stock_name TEXT,
                    quantity INTEGER DEFAULT 0,
                    avg_price INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, stock_name)
                )
            """)
            
            # 工作表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_work (
                    user_id TEXT PRIMARY KEY,
                    work_name TEXT,
                    salary INTEGER,
                    work_date TEXT,
                    last_salary_date TEXT
                )
            """)
            
            # 结社表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_society (
                    user_id TEXT PRIMARY KEY,
                    society_name TEXT,
                    join_date TEXT,
                    last_switch_date TEXT
                )
            """)
            
            # 成就表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_achievements (
                    user_id TEXT,
                    achievement_id TEXT,
                    obtain_time TEXT,
                    PRIMARY KEY (user_id, achievement_id)
                )
            """)
            
            # 税收表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tax_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    tax_amount INTEGER,
                    tax_date TEXT
                )
            """)
            
            # 分红表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS dividend_records (
                    user_id TEXT PRIMARY KEY,
                    last_dividend_date TEXT,
                    total_dividend INTEGER DEFAULT 0
                )
            """)
            
            # 用户关系描述表（存储AI生成的关系描述）
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
            
            await db.commit()
        
        self._ready = True
        logger.info("[经济系统] 数据库初始化完成")


# ============== 主插件类 ==============
@register("astrbot_plugin_signin", "莫宁", "莫宁宁的币 - 经济系统插件", "2.0.0", "https://github.com/your-repo")
class EconomyPlugin(Star):
    """经济系统主插件类"""
    
    def __init__(self, context: Context):
        super().__init__(context)
        self.db_path = os.path.join(os.path.dirname(__file__), "data", "economy.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # 初始化服务
        self.db = DBManager(self.db_path)
        self.signin_service = SigninService(self.db_path)
        self.bank_service = BankService(self.db_path)
        self.shop_service = ShopService(self.db_path)
        self.stock_service = StockService(self.db_path)
        self.work_service = WorkService(self.db_path)
        self.society_service = SocietyService(self.db_path)
        self.achievement_service = AchievementService(self.db_path)
        self.tax_service = TaxService(self.db_path)
        self.charity_service = CharityService(self.db_path)
        self.announcement_service = AnnouncementService(self.db_path)
        
        # 初始化好感度系统和数据库管理器
        self.favor_system = FavorSystem(self.db_path)
        self.db_manager = DatabaseManager(self.db_path)
        
        self._initialized = False
        logger.info("【经济系统】插件加载中 v2.0.0")
    
    async def _ensure_db(self):
        """确保数据库初始化"""
        if not self._initialized:
            await self.db.init()
            # 初始化公告表
            await self.announcement_service.init_table()
            # 授予赛季成就
            await self.achievement_service.grant_season_achievements()
            self._initialized = True
    
    def _get_sender_name(self, event: AstrMessageEvent) -> str:
        """获取发送者昵称"""
        sender = event.get_sender()
        if sender:
            return getattr(sender, 'nickname', '未知用户')
        return '未知用户'
    
    async def _get_nickname(self, user_id: str) -> Optional[str]:
        """从数据库获取用户昵称"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT nickname FROM users WHERE user_id = ?",
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
                """INSERT INTO users (user_id, nickname) VALUES (?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET nickname = ?""",
                (user_id, nickname, nickname)
            )
            await db.commit()
    
    async def _get_user(self, user_id: str) -> Dict:
        """获取或创建用户"""
        async with aiosqlite.connect(self.db_path) as db:
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
                """SELECT COALESCE(SUM(sh.quantity * sp.current_price), 0)
                   FROM stock_holdings sh
                   JOIN stock_prices sp ON sh.stock_name = sp.stock_name
                   WHERE sh.user_id = ? AND sh.quantity > 0""",
                (user_id,)
            )
            row = await cursor.fetchone()
            stock = int(row[0]) if row and len(row) > 0 and row[0] else 0
        
        return cash + bank + stock, cash, bank, stock
    
    async def _get_all_assets(self) -> List[Tuple[str, int]]:
        """获取所有用户总资产（用于排行榜）"""
        assets = []
        async with aiosqlite.connect(self.db_path) as db:
            # 获取所有用户
            cursor = await db.execute("SELECT user_id FROM users")
            users = await cursor.fetchall()
            
            for (uid,) in users:
                # 计算总资产
                total, _, _, _ = await self._get_user_asset(uid)
                assets.append((uid, total))
        
        # 按资产排序
        assets.sort(key=lambda x: x[1], reverse=True)
        return assets
    
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
''')

print("脚本已创建。由于代码非常长，建议直接上传完整文件到 /tmp/main.py")
print("然后运行: cp /tmp/main.py /root/ai/astrbot/data/plugins/astrbot_plugin_signin/main.py")
