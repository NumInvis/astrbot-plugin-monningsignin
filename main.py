"""
莫宁宁的币 - 专业级经济系统插件 v2.0.0
重构版本：模块化、高性能、易维护
"""
import os
import sys
# 确保插件目录在Python路径中
plugin_dir = os.path.dirname(os.path.abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

import random
import json
import re
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

import aiosqlite
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp

from config import CONFIG
from config_manager import ConfigManager
from achievements import AchievementManager, ACHIEVEMENTS
from help_texts import get_signin_help, get_admin_help
from tarot_service import TarotService

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
from favor_system import FavorSystem
from announcement_service import AnnouncementService
from stats_service import StatsService
from db_manager import DatabaseManager
from db_migrate_complete import check_and_migrate
from fix_tarot_table import check_and_fix_tarot
from utils import today_str, mask_id, format_num, get_beijing_time

# ============== 命令处理器导入 ==============
from handlers import basic
from handlers import admin
from handlers import bank
from handlers import shop
from handlers import stock
from handlers import work
from handlers import society
from handlers import favor
from handlers import tarot
from handlers import achievement
from handlers import announcement


@register("astrbot_plugin_monningsignin", "NumInvis", "莫宁宁的币", "2.0.0")
class EconomyPlugin(Star):
    """经济系统主插件"""

    def __init__(self, context: Context):
        super().__init__(context)
        
        # 初始化数据目录 - 使用 AstrBot 标准插件数据目录
        # 兼容旧版：优先检测本地 data/ 目录已有的数据库
        local_data_dir = os.path.join(os.path.dirname(__file__), "data")
        std_data_dir = os.path.join(os.path.dirname(__file__), "data")
        
        # 尝试获取 AstrBot 标准数据目录（3.0+）
        try:
            if hasattr(context, 'get_plugin_data_dir'):
                std_data_dir = context.get_plugin_data_dir()
        except Exception:
            pass
        
        # 检查哪个目录存在数据库文件，优先保留已有数据
        if os.path.exists(os.path.join(local_data_dir, "signin.db")):
            data_dir = local_data_dir
        elif os.path.exists(os.path.join(std_data_dir, "signin.db")):
            data_dir = std_data_dir
        else:
            # 默认使用标准数据目录，回退到本地目录
            data_dir = std_data_dir if std_data_dir != local_data_dir else local_data_dir
            os.makedirs(data_dir, exist_ok=True)
        
        self.db_path = os.path.join(data_dir, "signin.db")
        
        # 初始化服务
        self.signin_service = SigninService(self.db_path)
        self.bank_service = BankService(self.db_path)
        self.shop_service = ShopService(self.db_path)
        self.stock_service = StockService(self.db_path)
        self.work_service = WorkService(self.db_path)
        self.society_service = SocietyService(self.db_path)
        self.achievement_service = AchievementService(self.db_path)
        self.favor_system = FavorSystem(self.db_path)
        self.admin_service = AdminService(self.db_path)
        self.stats_service = StatsService(self.db_path)
        self.tax_service = TaxService(self.db_path, self.stats_service)
        self.announcement_service = AnnouncementService(self.db_path)
        self.tarot_service = TarotService(self.db_path)
        self.config_manager = ConfigManager(self.db_path)
        self.achievement_manager = AchievementManager(self.db_path)
        self.db_manager = DatabaseManager(self.db_path)
        
        # 初始化标志
        self._initialized = False
        self._init_lock = asyncio.Lock()
        
        logger.info("【经济系统】插件 v2.0.0 加载中...")

    async def _ensure_db(self):
        """确保数据库已初始化（带异步锁防止并发）"""
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return

            # 执行数据库迁移（修复缺失的列）
            await check_and_migrate(self.db_path)

            # 修复塔罗牌表结构
            await check_and_fix_tarot(self.db_path)

            # 初始化基础数据库表
            await self.db_manager.init_database()
            
            # 初始化成就表
            await self.achievement_service.init_table()
            
            # 授予赛季成就
            await self.achievement_service.grant_season_achievements()
            
            # 初始化公告表
            await self.announcement_service.init_table()
            
            # 初始化税收表
            await self.tax_service.init_table()
            
            # 初始化自定义成就表
            await self.achievement_manager.init_table()
            
            self._initialized = True
            logger.info("【经济系统】数据库初始化完成")

            # 启动股票后台任务（价格更新、情绪更新）
            self.stock_service.start_background_tasks()

            # 启动定时收税任务
            asyncio.create_task(self._daily_tax_scheduler())

            # 启动定时股票分红任务
            asyncio.create_task(self._daily_dividend_scheduler())

    async def _daily_tax_scheduler(self):
        """每日0点自动收税调度器"""
        last_tax_date = None

        while True:
            try:
                now = get_beijing_time()
                today_str = now.strftime("%Y-%m-%d")

                # 检查是否是0点且今日未收税
                if now.hour == 0 and now.minute == 0 and last_tax_date != today_str:
                    logger.info(f"【税收系统】到达0点，开始执行收税...")

                    result = await self.tax_service.collect_tax()
                    if result:
                        logger.info(f"【税收系统】自动收税完成：总税收={result['total_tax']}, 奖池={result['bonus_pool']}")
                    else:
                        logger.info("【税收系统】今日已收税，跳过")

                    last_tax_date = today_str

                # 每分钟检查一次
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"【税收系统】自动收税失败：{e}")
                await asyncio.sleep(60)

    async def _daily_dividend_scheduler(self):
        """每日0点自动股票分红调度器"""
        last_dividend_date = None

        while True:
            try:
                now = get_beijing_time()
                today_str = now.strftime("%Y-%m-%d")

                # 检查是否是0点且今日未分红
                if now.hour == 0 and now.minute == 0 and last_dividend_date != today_str:
                    logger.info(f"【股票分红】到达0点，开始执行分红...")

                    # 获取所有股票列表
                    stocks = await self.stock_service.get_stock_market()
                    total_dividend = 0

                    for stock in stocks:
                        stock_name = stock['name']
                        result = await self.stock_service.pay_dividend(stock_name)
                        if result['success']:
                            total_dividend += result['total_dividend']
                            logger.info(f"【股票分红】{stock_name}: 发放 {result['total_dividend']} 星声，利率 {result['dividend_rate']:.2f}%")

                    logger.info(f"【股票分红】完成，总发放：{total_dividend} 星声")
                    last_dividend_date = today_str

                # 每分钟检查一次
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"【股票分红】自动分红失败：{e}")
                await asyncio.sleep(60)

    # ============== 辅助方法 ==============
    
    def _get_sender_name(self, event: AstrMessageEvent) -> str:
        """获取发送者名称"""
        try:
            sender = event.message_obj.sender
            if hasattr(sender, 'nickname') and sender.nickname:
                return sender.nickname
            if hasattr(sender, 'card') and sender.card:
                return sender.card
            if hasattr(sender, 'user_id'):
                return str(sender.user_id)
        except Exception:
            pass
        
        try:
            name = event.get_sender_name()
            if name:
                return name
        except Exception:
            pass
        
        return "未知用户"
    
    def _extract_target_user(self, event: AstrMessageEvent) -> Optional[str]:
        """从消息中提取目标用户ID（支持@或QQ号）"""
        message_str = event.message_str
        message_obj = event.message_obj
        
        # 方法1：从消息链中查找At组件
        for comp in message_obj.message:
            if isinstance(comp, Comp.At):
                return str(comp.qq)
        
        # 方法2：从文本中提取@用户名或QQ号
        at_match = re.search(r'@(\d{5,})', message_str)
        if at_match:
            return at_match.group(1)
        
        # 方法3：尝试从参数中提取纯数字QQ号
        parts = message_str.split()
        for part in parts[1:]:
            if part.isdigit() and len(part) >= 5:
                return part
        
        return None
    
    async def _get_user(self, user_id: str) -> Dict:
        """获取或创建用户"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                user_data = self._parse_user_row(row)
                logger.info(f"【_get_user】用户 {user_id} 已存在，balance={user_data['balance']}, last_signin_date={user_data['last_signin_date']}")
                return user_data
            else:
                # 创建新用户
                logger.info(f"【_get_user】用户 {user_id} 不存在，创建新用户")
                await db.execute(
                    "INSERT INTO users (user_id) VALUES (?)", (user_id,)
                )
                await db.commit()
                logger.info(f"【_get_user】用户 {user_id} 创建成功")
                
                return {
                    "user_id": user_id,
                    "balance": 0,
                    "bank_balance": 0,
                    "last_signin_date": None,
                    "consecutive_days": 0,
                    "favor_value": 0
                }
    
    def _parse_user_row(self, row) -> Dict:
        """解析用户数据行"""
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
        except Exception:
            last_signin_date = None
        try:
            consecutive = int(row[4]) if len(row) > 4 and row[4] else 0
        except (ValueError, TypeError):
            consecutive = 0
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
    
    async def _get_user_asset(self, user_id: str) -> Tuple[int, int, int, int]:
        """获取用户资产 (总, 现金, 银行, 股票)"""
        user = await self._get_user(user_id)
        cash = user["balance"]
        bank = user["bank_balance"]
        
        # 获取股票持仓
        stocks = await self.stock_service.get_stock_holdings(user_id)
        stock_value = 0
        for name, holding in stocks.items():
            price = await self.stock_service.get_stock_price(name)
            stock_value += int(holding["quantity"] * price)
        
        total = cash + bank + stock_value
        return total, cash, bank, stock_value
    
    # ============== 基础功能命令 ==============

    @filter.command("签到")
    async def cmd_signin(self, event: AstrMessageEvent):
        async for result in basic.cmd_signin(self, event):
            yield result

    @filter.command("资产排行榜")
    async def cmd_asset_ranking(self, event: AstrMessageEvent):
        async for result in basic.cmd_asset_ranking(self, event):
            yield result

    @filter.command("经济")
    async def cmd_economy_stats(self, event: AstrMessageEvent):
        async for result in basic.cmd_economy_stats(self, event):
            yield result

    @filter.command("收税")
    async def cmd_collect_tax(self, event: AstrMessageEvent):
        async for result in admin.cmd_collect_tax(self, event):
            yield result

    @filter.command("昨日税收")
    async def cmd_yesterday_tax(self, event: AstrMessageEvent):
        async for result in admin.cmd_yesterday_tax(self, event):
            yield result

    @filter.command("发放补贴")
    async def cmd_give_subsidy(self, event: AstrMessageEvent):
        async for result in admin.cmd_give_subsidy(self, event):
            yield result

    @filter.command("扣除资产")
    async def cmd_deduct_asset(self, event: AstrMessageEvent):
        async for result in admin.cmd_deduct_asset(self, event):
            yield result

    @filter.command("赛季")
    async def cmd_season_info(self, event: AstrMessageEvent):
        async for result in admin.cmd_season_info(self, event):
            yield result

    @filter.command("新赛季")
    async def cmd_new_season(self, event: AstrMessageEvent):
        async for result in admin.cmd_new_season(self, event):
            yield result

    @filter.command("银行")
    async def cmd_bank(self, event: AstrMessageEvent):
        async for result in bank.cmd_bank(self, event):
            yield result

    @filter.command("存款")
    async def cmd_deposit(self, event: AstrMessageEvent):
        async for result in bank.cmd_deposit(self, event):
            yield result

    @filter.command("取款")
    async def cmd_withdraw(self, event: AstrMessageEvent):
        async for result in bank.cmd_withdraw(self, event):
            yield result

    @filter.command("转账")
    async def cmd_transfer(self, event: AstrMessageEvent):
        async for result in bank.cmd_transfer(self, event):
            yield result

    @filter.command("商店")
    @filter.command("购买")
    async def cmd_shop(self, event: AstrMessageEvent):
        async for result in shop.cmd_shop(self, event):
            yield result

    @filter.command("背包")
    async def cmd_inventory(self, event: AstrMessageEvent):
        async for result in shop.cmd_inventory(self, event):
            yield result

    @filter.command("占卜")
    async def cmd_lottery(self, event: AstrMessageEvent):
        async for result in shop.cmd_lottery(self, event):
            yield result

    @filter.command("Allin")
    async def cmd_allin(self, event: AstrMessageEvent):
        async for result in shop.cmd_allin(self, event):
            yield result

    @filter.command("占卜概率")
    async def cmd_lottery_prob(self, event: AstrMessageEvent):
        async for result in shop.cmd_lottery_prob(self, event):
            yield result

    @filter.command("成就")
    async def cmd_achievements(self, event: AstrMessageEvent):
        async for result in achievement.cmd_achievements(self, event):
            yield result

    @filter.command("所有人成就")
    async def cmd_all_achievements(self, event: AstrMessageEvent):
        async for result in admin.cmd_all_achievements(self, event):
            yield result

    @filter.command("授予成就")
    async def cmd_grant_achievement(self, event: AstrMessageEvent):
        async for result in admin.cmd_grant_achievement(self, event):
            yield result

    @filter.command("成就i")
    async def cmd_achievements_info(self, event: AstrMessageEvent):
        async for result in admin.cmd_achievements_info(self, event):
            yield result

    @filter.command("创建成就")
    async def cmd_create_achievement(self, event: AstrMessageEvent):
        async for result in admin.cmd_create_achievement(self, event):
            yield result

    @filter.command("重置签到")
    async def cmd_reset_signin(self, event: AstrMessageEvent):
        async for result in admin.cmd_reset_signin(self, event):
            yield result

    @filter.command("签到帮助")
    async def cmd_signin_help(self, event: AstrMessageEvent):
        async for result in basic.cmd_signin_help(self, event):
            yield result

    @filter.command("高级签到帮助")
    async def cmd_admin_help(self, event: AstrMessageEvent):
        async for result in admin.cmd_admin_help(self, event):
            yield result

    @filter.command("好感度")
    async def cmd_favor(self, event: AstrMessageEvent):
        async for result in favor.cmd_favor(self, event):
            yield result

    @filter.command("送礼物")
    @filter.command("赠送")
    async def cmd_gift(self, event: AstrMessageEvent):
        async for result in favor.cmd_gift(self, event):
            yield result

    @filter.command("好感度排行")
    async def cmd_favor_ranking(self, event: AstrMessageEvent):
        async for result in favor.cmd_favor_ranking(self, event):
            yield result

    @filter.command("公告")
    async def cmd_announcement(self, event: AstrMessageEvent):
        async for result in announcement.cmd_announcement(self, event):
            yield result

    @filter.command("发布公告")
    async def cmd_publish_announcement(self, event: AstrMessageEvent):
        async for result in admin.cmd_publish_announcement(self, event):
            yield result

    @filter.command("股市")
    async def cmd_stock_market(self, event: AstrMessageEvent):
        async for result in stock.cmd_stock_market(self, event):
            yield result

    @filter.command("持仓")
    async def cmd_portfolio(self, event: AstrMessageEvent):
        async for result in stock.cmd_portfolio(self, event):
            yield result

    @filter.command("买入")
    async def cmd_buy_stock(self, event: AstrMessageEvent):
        async for result in stock.cmd_buy_stock(self, event):
            yield result

    @filter.command("卖出")
    async def cmd_sell_stock(self, event: AstrMessageEvent):
        async for result in stock.cmd_sell_stock(self, event):
            yield result

    @filter.command("创立公司")
    async def cmd_create_company(self, event: AstrMessageEvent):
        async for result in stock.cmd_create_company(self, event):
            yield result

    @filter.command("k线")
    async def cmd_kline(self, event: AstrMessageEvent):
        async for result in stock.cmd_kline(self, event):
            yield result

    @filter.command("结社")
    async def cmd_society(self, event: AstrMessageEvent):
        async for result in society.cmd_society(self, event):
            yield result

    @filter.command("结社信息")
    async def cmd_society_info(self, event: AstrMessageEvent):
        async for result in society.cmd_society_info(self, event):
            yield result

    @filter.command("加入结社")
    async def cmd_join_society(self, event: AstrMessageEvent):
        async for result in society.cmd_join_society(self, event):
            yield result

    @filter.command("离开结社")
    async def cmd_leave_society(self, event: AstrMessageEvent):
        async for result in society.cmd_leave_society(self, event):
            yield result

    @filter.command("我的结社")
    async def cmd_my_society(self, event: AstrMessageEvent):
        async for result in society.cmd_my_society(self, event):
            yield result

    @filter.command("找工作")
    async def cmd_find_work(self, event: AstrMessageEvent):
        async for result in work.cmd_find_work(self, event):
            yield result

    @filter.command("应聘")
    async def cmd_apply_work(self, event: AstrMessageEvent):
        async for result in work.cmd_apply_work(self, event):
            yield result

    @filter.command("工作状态")
    async def cmd_work_status(self, event: AstrMessageEvent):
        async for result in work.cmd_work_status(self, event):
            yield result

    @filter.command("领工资")
    async def cmd_claim_salary(self, event: AstrMessageEvent):
        async for result in work.cmd_claim_salary(self, event):
            yield result

    @filter.command("塔罗牌")
    async def cmd_tarot(self, event: AstrMessageEvent):
        async for result in tarot.cmd_tarot(self, event):
            yield result

    @filter.command("资产")
    async def cmd_asset(self, event: AstrMessageEvent):
        async for result in basic.cmd_asset(self, event):
            yield result

    @filter.command("余额")
    async def cmd_balance(self, event: AstrMessageEvent):
        async for result in basic.cmd_balance(self, event):
            yield result

