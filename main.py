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


@register("astrbot_plugin_monningsignin", "NumInvis", "莫宁宁的币", "2.0.0")
class EconomyPlugin(Star):
    """经济系统主插件"""

    def __init__(self, context: Context):
        super().__init__(context)
        
        # 初始化数据目录 - 使用AstrBot标准数据目录
        # 优先使用已有的数据库路径
        plugin_data_dir = "/root/ai/astrbot/data/plugin_data/astrbot_plugin_monningsignin"
        local_data_dir = os.path.join(os.path.dirname(__file__), "data")
        
        # 检查哪个目录存在数据库文件
        if os.path.exists(os.path.join(plugin_data_dir, "signin.db")):
            data_dir = plugin_data_dir
        elif os.path.exists(os.path.join(local_data_dir, "signin.db")):
            data_dir = local_data_dir
        else:
            # 默认使用AstrBot标准数据目录
            data_dir = plugin_data_dir
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
        """每日签到 - 自动结算利息、领取工资、抽取塔罗牌、领取分红"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        nickname = self._get_sender_name(event)

        # ========== 签到前自动结算 ==========

        # 1. 自动结算银行利息
        bank_info = await self.bank_service.get_bank_info(user_id)
        bank_before = bank_info["bank"]

        # 2. 自动领取工资
        salary_result = await self.work_service.claim_salary(user_id)

        # 3. 自动抽取塔罗牌
        tarot_result = await self.tarot_service.draw_tarot(user_id)

        # 获取用户排名百分比（用于低保加成）
        total, cash, bank, stock = await self._get_user_asset(user_id)
        all_users = await self.stats_service.get_all_users_assets()
        if len(all_users) > 1:
            rank = sum(1 for u in all_users if u["total"] > total) + 1
            percentile = rank / len(all_users)
        else:
            percentile = 0.5

        # 执行签到
        result = await self.signin_service.signin(user_id, percentile)

        if result["success"]:
            # 检查成就
            new_achievements = await self.achievement_service.check_achievements(
                user_id, "signin", {"consecutive": result["consecutive_days"]}
            )

            # 获取更新后的银行余额（用于计算利息）
            bank_info_after = await self.bank_service.get_bank_info(user_id)
            bank_after = bank_info_after["bank"]
            bank_interest = bank_after - bank_before

            # 构建回复消息
            lines = [
                f"🌟 {nickname} 签到成功！",
                f"📅 连续签到：{result['consecutive_days']} 天",
                f"💰 基础奖励：{format_num(result['base'])} 星声"
            ]

            if result['bonus'] > 0:
                lines.append(f"🎁 连续加成：+{format_num(result['bonus'])} 星声")
            if result['signin_extra'] > 0:
                lines.append(f"🔵 成就加成：+{format_num(result['signin_extra'])} 星声")
            if result['yue_bonus'] > 0 or result['yue_bonus_fixed'] > 0:
                lines.append(f"🌙 拜月加成：+{format_num(result['yue_bonus'] + result['yue_bonus_fixed'])} 星声")
            if result['signin_favor_bonus'] > 0:
                lines.append(f"💕 好感加成：+{result['signin_favor_bonus']} 好感值")

            lines.extend([
                f"💎 总计获得：{format_num(result['total'])} 星声",
                f"💳 当前余额：{format_num(result['balance'])} 星声"
            ])

            # 显示银行利息结算
            if bank_interest > 0:
                lines.append(f"🏦 银行利息：+{format_num(bank_interest)} 星声（利率{bank_info_after['rate_pct']}%）")

            # 显示工资领取
            if salary_result.get("success"):
                lines.append(f"💼 工资收入：+{format_num(salary_result['final_earnings'])} 星声（工作{salary_result['hours']}小时）")
                if salary_result.get('qian_bonus', 0) > 0:
                    lines.append(f"⚡ 千衢结社加成：+{format_num(salary_result['qian_bonus'])} 星声")

            # 显示塔罗牌抽取结果
            if tarot_result.get("success"):
                if tarot_result.get("already_drawn"):
                    lines.append(f"🎴 今日塔罗：{tarot_result['card_name']}（已抽取）")
                else:
                    lines.append(f"🎴 塔罗牌：{tarot_result['card_name']}")
                    # 显示塔罗牌台词
                    if tarot_result.get("desc"):
                        lines.append(f"   📜 {tarot_result['desc']}")
                    # 显示效果
                    if tarot_result.get("effect_result"):
                        lines.append(f"   ✨ {tarot_result['effect_result']}")

            # 领取税收奖池分红（tax_service已直接更新余额）
            tax_bonus, remaining_pool = await self.tax_service.claim_tax_bonus(user_id)
            if tax_bonus > 0:
                lines.append(f"🎁 税收分红：+{format_num(tax_bonus)} 星声（奖池剩余{format_num(remaining_pool)}）")

            # 显示新成就
            if new_achievements:
                lines.append("\n🏆 【新成就】")
                for a in new_achievements:
                    lines.append(f"{a['emoji']} {a['name']}\n   📝 {a['desc']}")

            # 重新查询实际余额（包含所有收入）
            total, cash, bank, stock = await self._get_user_asset(user_id)
            lines.append(f"\n💳 实际余额：{format_num(cash)} 星声")
            lines.append(f"🏦 银行存款：{format_num(bank)} 星声")
            lines.append(f"📈 总资产：{format_num(total)} 星声")

            yield event.plain_result("\n".join(lines))
        else:
            yield event.plain_result(f"❌ {result['message']}")

    @filter.command("资产排行榜")
    async def cmd_asset_ranking(self, event: AstrMessageEvent):
        """查看资产排行榜前十名"""
        await self._ensure_db()

        top10 = await self.stats_service.get_top10_assets()
        
        if not top10:
            yield event.plain_result("📊 暂无资产数据")
            return

        lines = ["🏆 资产排行榜 TOP10", "═══════════════════"]
        
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        
        for idx, user in enumerate(top10):
            medal = medals[idx] if idx < len(medals) else f"{idx+1}."
            user_id = user["user_id"]
            total = user["total"]
            cash = user["cash"]
            bank = user["bank"]
            stock = user["stock"]
            
            lines.append(f"{medal} {mask_id(user_id)}")
            lines.append(f"   💎 总资产：{format_num(total)} 星声")
            lines.append(f"   💳 {format_num(cash)} | 🏦 {format_num(bank)} | 📈 {format_num(stock)}")
            lines.append("")

        # 添加统计信息
        total_wealth = await self.stats_service.get_total_wealth()
        player_count = await self.stats_service.get_player_count()
        avg_wealth = await self.stats_service.get_average_wealth()
        
        lines.extend([
            "═══════════════════",
            f"📊 服务器统计：",
            f"   玩家总数：{player_count} 人",
            f"   经济总量：{format_num(total_wealth)} 星声",
            f"   人均资产：{format_num(int(avg_wealth))} 星声"
        ])

        yield event.plain_result("\n".join(lines))

    @filter.command("经济")
    async def cmd_economy_stats(self, event: AstrMessageEvent):
        """查看经济统计（最近7天）"""
        await self._ensure_db()

        stats = await self.stats_service.get_economy_stats(days=7)
        tax_stats = await self.tax_service.get_tax_stats(days=7)

        lines = ["📈 经济统计（最近7天）", "═══════════════════"]
        
        lines.extend([
            f"👥 玩家总数：{stats['player_count']} 人",
            f"💰 经济总量：{format_num(stats['total_wealth'])} 星声",
            f"📊 人均资产：{format_num(int(stats['avg_wealth']))} 星声",
            f"📈 资产中位数：{format_num(stats['median_wealth'])} 星声",
            "",
            f"💸 税收总额：{format_num(tax_stats['total_tax'])} 星声",
            f"🎁 奖池总额：{format_num(tax_stats['total_bonus'])} 星声"
        ])

        # 显示每日税收详情
        if tax_stats['daily_stats']:
            lines.extend(["", "📅 每日税收详情："])
            for day in tax_stats['daily_stats'][:7]:
                lines.append(f"   {day['date']}: {format_num(day['total_tax'])} 星声")

        yield event.plain_result("\n".join(lines))

    @filter.command("收税")
    async def cmd_collect_tax(self, event: AstrMessageEvent):
        """管理员强制收税"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())

        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
            return

        result = await self.tax_service.force_collect_tax()

        if result is None:
            yield event.plain_result("⚠️ 今日已收税，如需重新收税请先删除记录")
            return

        lines = [
            "✅ 强制收税完成！",
            "═══════════════════",
            f"💰 总税收：{format_num(result['total_tax'])} 星声",
            f"🎁 奖池：{format_num(result['bonus_pool'])} 星声",
            f"👥 玩家数：{result['player_count']} 人",
            f"📈 资产中位数：{format_num(result['median_wealth'])} 星声",
            ""
        ]

        # 显示前十名税收详情
        if result['top10_details']:
            lines.append("🏆 前十名税收详情：")
            for detail in result['top10_details']:
                lines.append(
                    f"   第{detail['rank']}名 {mask_id(detail['user_id'])}: "
                    f"-{format_num(detail['tax'])} 星声 ({int(detail['rate']*100)}%)"
                )

        # 显示额外税收详情
        extra_count = len(result['extra_tax_details'])
        if extra_count > 0:
            lines.append(f"\n⚖️ 额外平衡税收：{extra_count} 人")

        yield event.plain_result("\n".join(lines))

    @filter.command("昨日税收")
    async def cmd_yesterday_tax(self, event: AstrMessageEvent):
        """查看昨日税收"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())

        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
            return

        yesterday = (get_beijing_time() - timedelta(days=1)).strftime("%Y-%m-%d")

        # 使用tax_service获取税收统计
        stats = await self.tax_service.get_tax_stats(days=2)
        daily_stats = stats.get('daily_stats', [])

        # 查找昨日数据
        yesterday_stats = None
        for day in daily_stats:
            if day['date'] == yesterday:
                yesterday_stats = day
                break

        if not yesterday_stats:
            yield event.plain_result("📊 昨日无税收记录")
            return

        lines = [
            f"📊 昨日税收 ({yesterday})",
            "═══════════════════",
            f"💰 总税收：{format_num(yesterday_stats['total_tax'])} 星声",
            f"🎁 奖池：{format_num(yesterday_stats['bonus_pool'])} 星声",
            f"👥 玩家数：{yesterday_stats['player_count']} 人",
            f"📈 资产中位数：{format_num(yesterday_stats['median_wealth'])} 星声"
        ]

        yield event.plain_result("\n".join(lines))

    @filter.command("发放补贴")
    async def cmd_give_subsidy(self, event: AstrMessageEvent):
        """发放补贴给指定用户"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())

        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
            return

        args = event.message_str.split()
        if len(args) < 3:
            yield event.plain_result("❌ 用法：/发放补贴 @用户/QQ号 [金额]")
            return

        # 提取目标用户
        target_user = self._extract_target_user(event)
        if not target_user:
            yield event.plain_result("❌ 请指定目标用户（@用户或输入QQ号）")
            return

        # 提取金额
        try:
            amount = int(args[-1])
        except ValueError:
            yield event.plain_result("❌ 请输入有效的金额")
            return

        if amount <= 0:
            yield event.plain_result("❌ 金额必须大于0")
            return

        # 使用admin_service发放补贴
        result = await self.admin_service.give_subsidy(target_user, amount)

        if result['success']:
            yield event.plain_result(
                f"✅ 补贴发放成功！\n"
                f"👤 用户：{mask_id(target_user)}\n"
                f"💰 金额：{format_num(amount)} 星声\n"
                f"💳 新余额：{format_num(result['new_balance'])} 星声"
            )
        else:
            yield event.plain_result(f"❌ {result['message']}")

    @filter.command("扣除资产")
    async def cmd_deduct_asset(self, event: AstrMessageEvent):
        """扣除用户资产"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())

        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
            return

        args = event.message_str.split()
        if len(args) < 3:
            yield event.plain_result("❌ 用法：/扣除资产 @用户/QQ号 [金额]")
            return

        # 提取目标用户
        target_user = self._extract_target_user(event)
        if not target_user:
            yield event.plain_result("❌ 请指定目标用户（@用户或输入QQ号）")
            return

        # 提取金额
        try:
            amount = int(args[-1])
        except ValueError:
            yield event.plain_result("❌ 请输入有效的金额")
            return

        if amount <= 0:
            yield event.plain_result("❌ 金额必须大于0")
            return

        # 使用admin_service扣除资产
        result = await self.admin_service.deduct_asset(target_user, amount)

        if result['success']:
            yield event.plain_result(
                f"✅ 资产扣除成功！\n"
                f"👤 用户：{mask_id(target_user)}\n"
                f"💰 扣除金额：{format_num(amount)} 星声\n"
                f"💳 新余额：{format_num(result['new_balance'])} 星声"
            )
        else:
            yield event.plain_result(f"❌ {result['message']}")

    @filter.command("赛季")
    async def cmd_season_info(self, event: AstrMessageEvent):
        """查看当前赛季信息"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())

        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
            return

        season = await self.config_manager.get_season()

        lines = [
            "🎮 当前赛季信息",
            "═══════════════════",
            f"📅 当前赛季：第 {season} 赛季",
            "",
            "💡 使用 /新赛季 开启新赛季",
            "⚠️ 开启新赛季将重置所有用户数据！"
        ]

        yield event.plain_result("\n".join(lines))

    @filter.command("新赛季")
    async def cmd_new_season(self, event: AstrMessageEvent):
        """开启新赛季"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())

        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
            return

        # 获取当前赛季
        current_season = await self.config_manager.get_season()
        new_season = current_season + 1

        # 开启新赛季
        await self.admin_service.start_new_season()
        await self.config_manager.set_season(new_season)

        yield event.plain_result(
            f"🎉 新赛季开启成功！\n"
            f"═══════════════════\n"
            f"📅 当前赛季：第 {new_season} 赛季\n"
            f"✅ 所有用户数据已重置"
        )

    @filter.command("银行")
    async def cmd_bank(self, event: AstrMessageEvent):
        """银行存取款"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        args = event.message_str.split()

        if len(args) >= 2:
            action = args[1]
            if action in ["存", "存款"]:
                # 存款
                amount = int(args[2]) if len(args) >= 3 else 0
                if amount <= 0:
                    yield event.plain_result("❌ 请输入有效金额")
                    return

                result = await self.bank_service.deposit(user_id, amount)
                if result["success"]:
                    yield event.plain_result(
                        f"✅ 存款成功！\n"
                        f"💰 存入：{format_num(amount)} 星声\n"
                        f"🏦 银行存款：{format_num(result['new_bank'])} 星声\n"
                        f"💳 现金余额：{format_num(result['new_cash'])} 星声\n"
                        f"📈 利率：{result['rate_pct']}%{' (贵宾卡)' if result['has_vip'] else ''}"
                    )
                else:
                    yield event.plain_result(f"❌ {result['message']}")
                return

            elif action in ["取", "取款"]:
                # 取款
                amount = int(args[2]) if len(args) >= 3 else 0
                if amount <= 0:
                    yield event.plain_result("❌ 请输入有效金额")
                    return

                result = await self.bank_service.withdraw(user_id, amount)
                if result["success"]:
                    fee_info = " (免手续费)" if result['is_nuo_member'] else f" (手续费 {format_num(result['fee'])} 星声)"
                    yield event.plain_result(
                        f"✅ 取款成功！\n"
                        f"💰 取出：{format_num(result['amount'])} 星声\n"
                        f"💵 实际到账：{format_num(result['net_amount'])} 星声{fee_info}\n"
                        f"🏦 银行存款：{format_num(result['new_bank'])} 星声\n"
                        f"💳 现金余额：{format_num(result['new_cash'])} 星声"
                    )
                else:
                    yield event.plain_result(f"❌ {result['message']}")
                return

        # 查询银行信息
        bank_info = await self.bank_service.get_bank_info(user_id)
        rate_info = f"{bank_info['rate_pct']}%"
        if bank_info['has_vip']:
            rate_info += " (贵宾卡特权)"

        yield event.plain_result(
            f"🏦 银行信息\n"
            f"═══════════════════\n"
            f"💰 银行存款：{format_num(bank_info['bank'])} 星声\n"
            f"💳 现金余额：{format_num(bank_info['balance'])} 星声\n"
            f"📈 日利率：{rate_info}\n"
            f"\n💡 使用 /存款 [金额] 或 /取款 [金额]"
        )

    @filter.command("存款")
    async def cmd_deposit(self, event: AstrMessageEvent):
        """银行存款"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        args = event.message_str.split()

        if len(args) < 2:
            yield event.plain_result("❌ 用法：/存款 [金额]\n💡 示例：/存款 1000")
            return

        try:
            amount = int(args[1])
        except ValueError:
            yield event.plain_result("❌ 请输入有效的数字金额")
            return

        if amount <= 0:
            yield event.plain_result("❌ 请输入大于0的金额")
            return

        result = await self.bank_service.deposit(user_id, amount)
        if result["success"]:
            yield event.plain_result(
                f"✅ 存款成功！\n"
                f"💰 存入：{format_num(amount)} 星声\n"
                f"🏦 银行存款：{format_num(result['new_bank'])} 星声\n"
                f"💳 现金余额：{format_num(result['new_cash'])} 星声\n"
                f"📈 利率：{result['rate_pct']}%{' (贵宾卡)' if result['has_vip'] else ''}"
            )
        else:
            yield event.plain_result(f"❌ {result['message']}")

    @filter.command("取款")
    async def cmd_withdraw(self, event: AstrMessageEvent):
        """银行取款"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        args = event.message_str.split()

        if len(args) < 2:
            yield event.plain_result("❌ 用法：/取款 [金额]\n💡 示例：/取款 1000")
            return

        try:
            amount = int(args[1])
        except ValueError:
            yield event.plain_result("❌ 请输入有效的数字金额")
            return

        if amount <= 0:
            yield event.plain_result("❌ 请输入大于0的金额")
            return

        result = await self.bank_service.withdraw(user_id, amount)
        if result["success"]:
            fee_info = " (免手续费)" if result['has_vip'] else f" (手续费 {format_num(result['fee'])} 星声)"
            yield event.plain_result(
                f"✅ 取款成功！\n"
                f"💰 取出：{format_num(result['amount'])} 星声\n"
                f"💵 实际到账：{format_num(result['actual'])} 星声{fee_info}\n"
                f"🏦 银行存款：{format_num(result['new_bank'])} 星声\n"
                f"💳 现金余额：{format_num(result['new_cash'])} 星声"
            )
        else:
            yield event.plain_result(f"❌ {result['message']}")

    @filter.command("转账")
    async def cmd_transfer(self, event: AstrMessageEvent):
        """银行转账"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        args = event.message_str.split()
        
        if len(args) < 2:
            yield event.plain_result("❌ 用法：/转账 @用户/QQ号 [金额]")
            return
        
        # 提取目标用户
        target_user = self._extract_target_user(event)
        if not target_user:
            # 尝试从参数中提取
            if len(args) >= 2 and args[1].isdigit():
                target_user = args[1]
            else:
                yield event.plain_result("❌ 请指定目标用户（@用户或输入QQ号）")
                return
        
        # 提取金额
        amount = 0
        for part in args:
            if part.isdigit():
                amount = int(part)
                break
        
        if amount <= 0:
            yield event.plain_result("❌ 请输入有效金额")
            return
        
        result = await self.bank_service.transfer(user_id, target_user, amount)
        
        if result["success"]:
            yield event.plain_result(
                f"✅ 转账成功！\n"
                f"💰 金额：{format_num(amount)} 星声\n"
                f"👤 收款人：{mask_id(target_user)}"
            )
        else:
            yield event.plain_result(f"❌ {result['message']}")

    @filter.command("商店")
    @filter.command("购买")
    async def cmd_shop(self, event: AstrMessageEvent):
        """商店购买"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        args = event.message_str.split(maxsplit=1)

        if len(args) < 2:
            # 显示商店列表
            items = await self.shop_service.get_shop_items()
            lines = ["🛒 商店", "═══════════════════"]
            for item_id, item in items.items():
                lines.append(f"{item['emoji']} {item['name']} - {format_num(item['price'])} 星声")
                lines.append(f"   📝 {item['desc']}")
            lines.append("\n💡 使用 /购买 [商品名] 购买")
            yield event.plain_result("\n".join(lines))
            return

        # 购买商品
        item_name = args[1].strip()
        result = await self.shop_service.buy_item(user_id, item_name)

        if result["success"]:
            # 检查成就
            new_achievements = await self.achievement_service.check_achievements(
                user_id, "buy", {"item": item_name}
            )

            lines = [
                f"✅ 购买成功！",
                f"🛒 {result['item_name']}",
                f"💰 花费：{format_num(result['price'])} 星声",
                f"💳 余额：{format_num(result['balance'])} 星声"
            ]

            if new_achievements:
                lines.append("\n🏆 【新成就】")
                for a in new_achievements:
                    lines.append(f"{a['emoji']} {a['name']}")

            yield event.plain_result("\n".join(lines))
        else:
            yield event.plain_result(f"❌ {result['message']}")

    @filter.command("背包")
    async def cmd_inventory(self, event: AstrMessageEvent):
        """查看背包"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        inventory = await self.shop_service.get_inventory(user_id)
        
        if not inventory:
            yield event.plain_result("🎒 背包是空的\n去 /商店 购买物品吧！")
            return
        
        lines = ["🎒 我的背包", "═══════════════════"]
        for item in inventory:
            lines.append(f"{item['emoji']} {item['name']} x{item['quantity']}")
        
        yield event.plain_result("\n".join(lines))

    @filter.command("占卜")
    async def cmd_lottery(self, event: AstrMessageEvent):
        """占卜抽奖 - /占卜 金额"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        parts = event.message_str.split()
        
        if len(parts) < 2:
            yield event.plain_result("🔮 用法：/占卜 金额\n💡 投入星声进行占卜抽奖\n🔥 全押请用 /Allin")
            return
        
        try:
            bet = int(parts[1])
            if bet <= 0:
                raise ValueError()
        except ValueError:
            yield event.plain_result("❌ 请输入有效的金额！")
            return

        result = await self.shop_service.do_lottery(user_id, bet)

        if result["success"]:
            new_achievements = await self.achievement_service.check_achievements(
                user_id, "lottery", {"multiplier": result['multiplier']}
            )

            profit_sign = "+" if result['profit'] >= 0 else ""
            lines = [
                f"🔮 占卜结果",
                f"═══════════════════",
                f"{result['result_emoji']} {result['result_type']}",
                f"🎲 倍率：{result['multiplier']:.2f}x",
                f"💰 投入：{format_num(result['bet'])} 星声",
                f"💵 获得：{format_num(result['final'])} 星声",
                f"📊 盈亏：{profit_sign}{format_num(result['profit'])} 星声",
                f"💳 余额：{format_num(result['new_cash'])} 星声",
                f"🎫 占卜券剩余：{result['ticket_count']}张",
                f"🔮 今日剩余次数：{result['remaining_count']}次"
            ]

            if new_achievements:
                lines.append("\n🏆 【新成就】")
                for a in new_achievements:
                    lines.append(f"{a['emoji']} {a['name']}")

            yield event.plain_result("\n".join(lines))
        else:
            yield event.plain_result(f"❌ {result['message']}")

    @filter.command("Allin")
    async def cmd_allin(self, event: AstrMessageEvent):
        """Allin - 全部资金抽奖，无占卜券时自动购买"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())

        # 获取用户余额
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT balance FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            if not row:
                yield event.plain_result("❌ 用户不存在，请先签到！")
                return
            balance = int(row[0]) if row[0] else 0

        if balance <= 0:
            yield event.plain_result("❌ 你没有星声可以Allin！")
            return

        # 检查占卜券，没有则自动购买
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?",
                (user_id, "占卜券")
            )
            row = await cursor.fetchone()
            ticket_count = int(row[0]) if row and row[0] else 0

        auto_bought = False
        if ticket_count <= 0:
            # 自动购买占卜券
            ticket_price = CONFIG.SHOP_ITEMS["占卜券"]["price"]
            if balance < ticket_price:
                yield event.plain_result(f"❌ 余额不足！Allin需要至少{format_num(ticket_price)}星声购买占卜券")
                return
            
            buy_result = await self.shop_service.buy_item(user_id, "占卜券", 1)
            if not buy_result["success"]:
                yield event.plain_result(f"❌ 自动购买占卜券失败：{buy_result['message']}")
                return
            
            auto_bought = True
            # 刷新余额
            balance = buy_result["new_balance"]

        # 检查今日占卜次数
        lottery_info = await self.shop_service.get_inventory(user_id)
        if lottery_info["remaining_lottery_count"] <= 0:
            yield event.plain_result(f"❌ 今日占卜次数已用完！（{lottery_info['used_lottery_count']}/{CONFIG.LOTTERY_LIMIT}次）")
            return

        # Allin：投入全部余额
        bet = balance
        result = await self.shop_service.do_lottery(user_id, bet, is_allin=True)

        if result["success"]:
            new_achievements = await self.achievement_service.check_achievements(
                user_id, "lottery", {"multiplier": result['multiplier']}
            )

            profit_sign = "+" if result['profit'] >= 0 else ""
            lines = [
                f"� ALL IN！",
                f"═══════════════════",
                f"{result['result_emoji']} {result['result_type']}",
                f"🎲 倍率：{result['multiplier']:.2f}x",
                f"💰 投入：{format_num(result['bet'])} 星声（全部家当）",
                f"💵 获得：{format_num(result['final'])} 星声",
                f"📊 盈亏：{profit_sign}{format_num(result['profit'])} 星声",
                f"💳 余额：{format_num(result['new_cash'])} 星声",
                f"🎫 占卜券剩余：{result['ticket_count']}张",
                f"🔮 今日剩余次数：{result['remaining_count']}次"
            ]

            if auto_bought:
                lines.insert(1, f"🎫 自动购买了一张占卜券（{format_num(CONFIG.SHOP_ITEMS['占卜券']['price'])}星声）")

            if new_achievements:
                lines.append("\n🏆 【新成就】")
                for a in new_achievements:
                    lines.append(f"{a['emoji']} {a['name']}")

            if result['profit'] < 0:
                lines.append("\n💀 倾家荡产...")
            elif result['multiplier'] >= 5.0:
                lines.append("\n👑 欧皇降临！！！")

            yield event.plain_result("\n".join(lines))
        else:
            yield event.plain_result(f"❌ {result['message']}")

    @filter.command("占卜概率")
    async def cmd_lottery_prob(self, event: AstrMessageEvent):
        """查看占卜概率分布"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        result = await self.shop_service.get_lottery_probability(user_id)

        lines = [
            "🔮 占卜概率分布",
            "═══════════════════",
            f"� 今日剩余次数：{result['remaining']}/{result['limit']}",
            "",
            "📊 倍率区间及概率："
        ]

        for multiplier_range, probability, result_type, emoji in result['prob_dist']:
            lines.append(f"{emoji} {multiplier_range} : {probability} ({result_type})")

        lines.extend([
            "",
            "💡 使用 /占卜 进行抽奖"
        ])

        yield event.plain_result("\n".join(lines))

    @filter.command("成就")
    async def cmd_achievements(self, event: AstrMessageEvent):
        """查看成就"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        
        # 获取所有成就
        all_achievements = await self.achievement_manager.get_all_achievements()
        
        # 获取用户已获得的成就
        user_achievements = await self.achievement_service.get_user_achievements(user_id)
        user_achievement_ids = {a['achievement_id'] for a in user_achievements}
        
        lines = ["🏆 我的成就", "═══════════════════"]
        
        # 按品质分组显示
        rarity_order = ["colorful", "gold", "purple", "blue"]
        rarity_names = {"colorful": "🌈 彩色", "gold": "🌟 金色", "purple": "💜 紫色", "blue": "🔵 蓝色"}

        for rarity in rarity_order:
            rarity_achievements = [(aid, a) for aid, a in all_achievements.items() if a['rarity'] == rarity]
            if rarity_achievements:
                lines.append(f"\n{rarity_names.get(rarity, rarity)}")
                for achievement_id, achievement in rarity_achievements:
                    if achievement_id in user_achievement_ids:
                        lines.append(f"  ✅ {achievement['emoji']} {achievement['name']}")
                    else:
                        lines.append(f"  ⬜ {achievement['emoji']} {achievement['name']} (未获得)")
        
        yield event.plain_result("\n".join(lines))

    @filter.command("所有人成就")
    async def cmd_all_achievements(self, event: AstrMessageEvent):
        """管理员查看所有人成就统计"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        
        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
            return
        
        # 获取所有用户的成就统计
        all_stats = await self.achievement_service.get_all_achievements()
        
        if not all_stats:
            yield event.plain_result("📊 暂无成就数据")
            return
        
        lines = ["🏆 所有人成就统计", "═══════════════════"]
        
        for stat in all_stats[:20]:  # 只显示前20名
            lines.append(
                f"{mask_id(stat['user_id'])}: {stat['count']}个成就 "
                f"(🌈{stat['colorful']} 🌟{stat['gold']} 💜{stat['purple']} 🔵{stat['blue']})"
            )
        
        yield event.plain_result("\n".join(lines))

    @filter.command("授予成就")
    async def cmd_grant_achievement(self, event: AstrMessageEvent):
        """管理员授予成就"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        
        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
            return
        
        args = event.message_str.split()
        if len(args) < 3:
            yield event.plain_result("❌ 用法：/授予成就 @用户/QQ号 成就ID\n使用 \"所有人\" 可授予所有用户")
            return
        
        # 提取目标用户
        target_user = self._extract_target_user(event)
        achievement_id = args[-1]  # 最后一个参数是成就ID
        
        if target_user == "所有人":
            # 授予所有用户
            result = await self.achievement_service.grant_achievement_to_all(achievement_id)
            if result["success"]:
                yield event.plain_result(f"✅ 已成功授予所有用户成就：{result['achievement_name']}")
            else:
                yield event.plain_result(f"❌ {result['message']}")
        elif target_user:
            # 授予单个用户
            result = await self.achievement_service.grant_achievement(target_user, achievement_id)
            if result["success"]:
                yield event.plain_result(f"✅ 已成功授予 {mask_id(target_user)} 成就：{result['achievement_name']}")
            else:
                yield event.plain_result(f"❌ {result['message']}")
        else:
            yield event.plain_result("❌ 请指定目标用户（@用户或输入QQ号）")

    @filter.command("成就i")
    async def cmd_achievements_info(self, event: AstrMessageEvent):
        """管理员查看所有成就ID"""
        await self._ensure_db()
        
        user_id = str(event.get_sender_id())
        
        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
            return
        
        # 获取所有成就
        all_achievements = await self.achievement_manager.get_all_achievements()
        
        lines = ["📋 所有成就ID列表", "═══════════════════"]
        
        # 按品质分组
        rarity_order = ["colorful", "gold", "purple", "blue"]
        rarity_names = {"colorful": "🌈 彩色", "gold": "🌟 金色", "purple": "💜 紫色", "blue": "🔵 蓝色"}
        
        for rarity in rarity_order:
            rarity_achievements = [a for a in all_achievements.values() if a['rarity'] == rarity]
            if rarity_achievements:
                lines.append(f"\n{rarity_names.get(rarity, rarity)}:")
                for achievement in rarity_achievements:
                    lines.append(f"  {achievement['id']} - {achievement['emoji']} {achievement['name']}")
        
        yield event.plain_result("\n".join(lines))

    @filter.command("创建成就")
    async def cmd_create_achievement(self, event: AstrMessageEvent):
        """管理员创建新成就（自动分配ID）"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())

        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
            return

        # 解析参数: /创建成就 <成就名> <品质> [emoji] [描述]
        parts = event.message_str.split(maxsplit=3)
        if len(parts) < 3:
            yield event.plain_result(
                "❌ 用法：/创建成就 <成就名> <品质> [emoji] [描述]\n"
                "📋 品质可选：blue(蓝色)、purple(紫色)、gold(金色)、colorful(彩色)\n"
                "💡 示例：/创建成就 我的成就 blue 🏆 这是一个自定义成就"
            )
            return

        name = parts[1]
        rarity = parts[2].lower()
        
        # 根据品质自动分配emoji（如果管理员未指定）
        default_emojis = {
            "blue": "🏆",
            "purple": "💜", 
            "gold": "🌟",
            "colorful": "🌈"
        }
        
        if len(parts) > 3 and parts[3].strip():
            # 管理员提供了emoji和描述
            first_part = parts[3].strip().split()[0]
            # 检查第一个部分是否是emoji（简单判断：不是普通字符）
            if len(first_part) <= 2 and not first_part.isalnum():
                emoji = first_part
                desc = parts[3][len(emoji):].strip()
            else:
                # 第一个部分是描述的一部分
                emoji = default_emojis.get(rarity, "🏆")
                desc = parts[3].strip()
        else:
            # 管理员没有提供emoji和描述
            emoji = default_emojis.get(rarity, "🏆")
            desc = "自定义成就"

        # 验证品质
        valid_rarities = ["blue", "purple", "gold", "colorful"]
        if rarity not in valid_rarities:
            yield event.plain_result(
                f"❌ 无效的品质：{rarity}\n"
                f"📋 品质可选：blue(蓝色)、purple(紫色)、gold(金色)、colorful(彩色)"
            )
            return

        # 自动生成成就ID
        # 格式：custom_时间戳_随机数
        import time
        achievement_id = f"custom_{int(time.time())}_{random.randint(1000, 9999)}"

        # 添加自定义成就
        success = await self.achievement_manager.add_custom_achievement(
            achievement_id, name, desc, emoji, rarity
        )

        if success:
            rarity_names = {"colorful": "🌈 彩色", "gold": "🌟 金色", "purple": "💜 紫色", "blue": "💙 蓝色"}
            yield event.plain_result(
                f"✅ 成就创建成功！\n"
                f"═══════════════════\n"
                f"🆔 自动分配ID：{achievement_id}\n"
                f"{emoji} 名称：{name}\n"
                f"📝 描述：{desc}\n"
                f"{rarity_names.get(rarity, '💙 蓝色')} 品质：{rarity}\n"
                f"═══════════════════\n"
                f"💡 使用 /授予成就 @用户/QQ号 {achievement_id} 授予此成就"
            )
        else:
            yield event.plain_result(f"❌ 成就创建失败，请稍后重试")

    @filter.command("重置签到")
    async def cmd_reset_signin(self, event: AstrMessageEvent):
        """管理员重置用户签到状态（支持@用户或输入QQ号）"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())

        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
            return

        # 提取目标用户
        target = self._extract_target_user(event)
        if not target:
            # 检查是否是"所有人"
            parts = event.message_str.split()
            if len(parts) >= 2 and parts[1] == "所有人":
                target = "所有人"
            else:
                yield event.plain_result('❌ 请指定用户（@用户或输入QQ号）或"所有人"')
                return

        # 使用admin_service重置签到
        if target == "所有人":
            result = await self.admin_service.reset_signin(user_id=None)
            yield event.plain_result(
                f"✅ 已重置 {result['signin_count']} 个用户的签到状态\n"
                f"✅ 已清除 {result['tarot_count']} 条今日塔罗牌记录\n"
                f"💡 这些用户现在可以重新签到和抽塔罗牌"
            )
        else:
            result = await self.admin_service.reset_signin(user_id=target)
            if result['success']:
                yield event.plain_result(f"✅ 已重置用户 {mask_id(target)} 的签到状态")
            else:
                yield event.plain_result(f"⚠️ {result['message']}")

    # ============== 帮助指令 ==============
    @filter.command("签到帮助")
    async def cmd_signin_help(self, event: AstrMessageEvent):
        """显示签到帮助信息（所有用户）"""
        yield event.plain_result(get_signin_help())

    @filter.command("高级签到帮助")
    async def cmd_admin_help(self, event: AstrMessageEvent):
        """显示管理员帮助信息（仅管理员）"""
        user_id = str(event.get_sender_id())

        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
            return

        yield event.plain_result(get_admin_help())

    @filter.command("好感度")
    async def cmd_favor(self, event: AstrMessageEvent):
        """查看好感度信息"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        args = event.message_str.split()

        # 检查是否是查看排行榜
        if len(args) > 1 and args[1] == "排行":
            ranking = await self.favor_system.get_favor_ranking()

            if not ranking:
                yield event.plain_result("📊 暂无好感度数据")
                return

            lines = ["💕 好感度排行榜", "═══════════════════"]

            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

            for idx, user in enumerate(ranking[:10]):
                medal = medals[idx] if idx < len(medals) else f"{idx+1}."
                user_id_rank = user["user_id"]
                favor_value = user["favor_value"]
                favor_level = user["favor_level"]

                lines.append(f"{medal} {mask_id(user_id_rank)}")
                lines.append(f"   💕 好感值：{favor_value}")
                lines.append(f"   💝 好感度：{favor_level}/520")
                lines.append("")

            yield event.plain_result("\n".join(lines))
        else:
            # 查看个人好感度
            favor_info = await self.favor_system.get_user_favor_info(user_id)
            rel_info = await self.favor_system.get_relationship_desc(user_id)

            lines = [
                f"💕 你与莫宁宁的好感度",
                "═══════════════════",
                f"💝 好感度：{favor_info['favor_level']:.2f}/520",
                f"💕 好感值：{favor_info['favor_value']}",
            ]

            if rel_info['desc']:
                lines.append(f"📝 关系描述：{rel_info['desc']}")
                if rel_info['can_update']:
                    lines.append("   ✅ 可更新关系描述")
                else:
                    lines.append(f"   ⏰ 下次可更新：{rel_info['next_update_time']}")

            lines.extend([
                "",
                "💡 使用 /送礼物 [物品名] 给莫宁宁送礼物",
                "📋 可用礼物：期刊论文、植物奶、神秘糖果、5090、莫宁宁的抱枕、定制蛋糕、手写信、音乐会门票、嘉年华"
            ])

            yield event.plain_result("\n".join(lines))

    @filter.command("送礼物")
    @filter.command("赠送")
    async def cmd_gift(self, event: AstrMessageEvent):
        """送礼物给莫宁宁"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        args = event.message_str.split(maxsplit=1)

        if len(args) < 2:
            items = self.favor_system.get_favor_items()
            yield event.plain_result(
                f"❌ 请指定要送的礼物\n"
                f"📋 用法：/赠送 [物品名]\n"
                f"🎁 可用礼物：{', '.join(items.keys())}"
            )
            return

        item_name = args[1].strip()
        result = await self.favor_system.gift_item(user_id, item_name)

        yield event.plain_result(result['message'])

    @filter.command("好感度排行")
    async def cmd_favor_ranking(self, event: AstrMessageEvent):
        """查看好感度排行榜"""
        await self._ensure_db()

        ranking = await self.favor_system.get_favor_ranking()

        if not ranking:
            yield event.plain_result("📊 暂无好感度数据")
            return

        lines = ["💕 好感度排行榜", "═══════════════════"]

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for idx, user in enumerate(ranking[:10]):
            medal = medals[idx] if idx < len(medals) else f"{idx+1}."
            user_id_rank = user["user_id"]
            favor_value = user["favor_value"]
            favor_level = user["favor_level"]

            lines.append(f"{medal} {mask_id(user_id_rank)}")
            lines.append(f"   💕 好感值：{favor_value}")
            lines.append(f"   💝 好感度：{favor_level}/520")
            lines.append("")

        yield event.plain_result("\n".join(lines))

    # ============== 公告系统命令 ==============

    @filter.command("公告")
    async def cmd_announcement(self, event: AstrMessageEvent):
        """查看公告"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        args = event.message_str.split()

        # 检查是否是管理员操作
        if len(args) > 1 and args[1] in ["删除", "置顶", "白名单"]:
            if user_id not in CONFIG.ADMIN_IDS:
                yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
                return

            if args[1] == "删除" and len(args) > 2:
                try:
                    ann_id = int(args[2])
                    success = await self.announcement_service.delete_announcement(ann_id)
                    if success:
                        yield event.plain_result(f"✅ 公告 #{ann_id} 已删除")
                    else:
                        yield event.plain_result("❌ 删除失败")
                except ValueError:
                    yield event.plain_result("❌ 公告ID必须是数字")
                return

            elif args[1] == "置顶" and len(args) > 2:
                try:
                    ann_id = int(args[2])
                    success = await self.announcement_service.pin_announcement(ann_id)
                    if success:
                        yield event.plain_result(f"✅ 公告 #{ann_id} 已置顶")
                    else:
                        yield event.plain_result("❌ 置顶失败")
                except ValueError:
                    yield event.plain_result("❌ 公告ID必须是数字")
                return

            elif args[1] == "白名单":
                if len(args) > 3 and args[2] in ["添加", "add"]:
                    group_id = args[3]
                    success = await self.announcement_service.add_whitelist(group_id)
                    if success:
                        whitelist = await self.announcement_service.get_whitelist()
                        yield event.plain_result(f"✅ 群 {group_id} 已添加到白名单\n📋 当前白名单共 {len(whitelist)} 个群")
                    else:
                        yield event.plain_result("❌ 添加失败")
                elif len(args) > 3 and args[2] in ["移除", "remove"]:
                    group_id = args[3]
                    success = await self.announcement_service.remove_whitelist(group_id)
                    if success:
                        whitelist = await self.announcement_service.get_whitelist()
                        yield event.plain_result(f"✅ 群 {group_id} 已从白名单移除\n📋 当前白名单共 {len(whitelist)} 个群")
                    else:
                        yield event.plain_result("❌ 移除失败")
                elif len(args) > 2 and args[2] in ["列表", "list"]:
                    whitelist = await self.announcement_service.get_whitelist()
                    if whitelist:
                        lines = ["📋 公告白名单", "═══════════════════"]
                        for i, group_id in enumerate(whitelist, 1):
                            lines.append(f"{i}. {group_id}")
                        yield event.plain_result("\n".join(lines))
                    else:
                        yield event.plain_result("📋 白名单为空")
                else:
                    yield event.plain_result("❌ 用法：/公告 白名单 添加 [群ID]\n       /公告 白名单 移除 [群ID]\n       /公告 白名单 列表")
                return

        # 获取所有公告
        announcements = await self.announcement_service.get_announcements(limit=10)

        if not announcements:
            yield event.plain_result("📢 暂无公告")
            return

        lines = ["📢 公告列表", "═══════════════════"]

        for ann in announcements:
            lines.append(f"#{ann['id']} {ann['title']}")
            lines.append(f"   📝 {ann['content']}")
            lines.append(f"   👤 {ann['author_name']} | 📅 {ann['publish_time']}")
            lines.append("")

        yield event.plain_result("\n".join(lines))

    @filter.command("发布公告")
    async def cmd_publish_announcement(self, event: AstrMessageEvent):
        """发布公告（管理员）"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())

        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
            return

        args = event.message_str.split(maxsplit=1)
        if len(args) < 2:
            yield event.plain_result("❌ 用法：/发布公告 [内容]")
            return

        content = args[1].strip()
        # 使用内容前20字作为标题
        title = content[:20] + "..." if len(content) > 20 else content

        result = await self.announcement_service.publish_announcement(
            title=title,
            content=content,
            author_id=user_id,
            author_name="管理员"
        )

        if result.get("success"):
            yield event.plain_result(
                f"✅ 公告发布成功！\n"
                f"═══════════════════\n"
                f"📝 {title}\n"
                f"📅 {result.get('publish_time', '')}"
            )
        else:
            yield event.plain_result(f"❌ {result.get('message', '发布失败')}")

    # ============== 股市系统命令 ==============

    @filter.command("股市")
    async def cmd_stock_market(self, event: AstrMessageEvent):
        """查看股市行情"""
        await self._ensure_db()

        stocks = await self.stock_service.get_stock_market()

        if not stocks:
            yield event.plain_result("📊 股市暂无上市公司\n发送 /创立公司 创建你的公司")
            return

        # 获取市场情绪
        market_sentiment = await self.stock_service.get_market_sentiment()
        sentiment_emoji = {"恐慌": "😱", "悲观": "😔", "中立": "😐", "乐观": "😊", "贪婪": "🤑"}

        lines = [
            f"📈 股市行情 - 市场情绪: {sentiment_emoji.get(market_sentiment, '😐')} {market_sentiment}",
            "═══════════════════"
        ]

        for stock in stocks:
            lines.append(
                f"{stock['emoji']} {stock['name']}"
                f"\n   💰 当前价: {format_num(int(stock['price']))} 星声 {stock['arrow']} {stock['change_pct']:.2f}%"
                f"\n   📊 市值: {format_num(stock['market_cap'])} 星声"
                f"{stock['owner_str']}"
            )

        lines.extend([
            "",
            "💡 使用 /买入 [股票名] [数量] 购买股票",
            "💡 使用 /持仓 查看你的股票持仓",
            "💡 使用 /k线 [股票名] 查看价格走势"
        ])

        yield event.plain_result("\n".join(lines))

    @filter.command("持仓")
    async def cmd_portfolio(self, event: AstrMessageEvent):
        """查看股票持仓"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        portfolio = await self.stock_service.get_portfolio(user_id)

        if not portfolio.get("success"):
            yield event.plain_result(portfolio.get("message", "获取持仓失败"))
            return

        lines = ["📊 我的股票持仓", "═══════════════════"]

        for item in portfolio["portfolio"]:
            lines.append(
                f"{item['emoji']} {item['stock_name']}"
                f"\n   📦 持有: {item['quantity']:.2f}股"
                f"\n   💰 现价: {format_num(int(item['current_price']))} | 成本: {format_num(int(item['avg_cost']))}"
                f"\n   📈 市值: {format_num(item['market_value'])} | 盈亏: {item['arrow']} {format_num(item['profit'])} ({item['profit_pct']:.1f}%)"
            )

        lines.extend([
            "",
            f"💎 总市值: {format_num(portfolio['total_value'])} 星声",
            f"💳 总成本: {format_num(portfolio['total_cost'])} 星声",
            f"📊 总盈亏: {format_num(portfolio['total_profit'])} ({portfolio['total_profit_pct']:.1f}%)"
        ])

        yield event.plain_result("\n".join(lines))

    @filter.command("买入")
    async def cmd_buy_stock(self, event: AstrMessageEvent):
        """买入股票"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        args = event.message_str.split()

        if len(args) < 3:
            yield event.plain_result(
                "❌ 用法：/买入 [股票名] [数量]\n"
                "📋 示例：/买入 腾讯 100"
            )
            return

        stock_name = args[1]
        try:
            quantity = float(args[2])
        except ValueError:
            yield event.plain_result("❌ 数量必须是数字")
            return

        result = await self.stock_service.buy_stock(user_id, stock_name, quantity)

        if result.get("success"):
            lines = [
                f"✅ 买入成功！",
                f"═══════════════════",
                f"📈 股票: {result['stock_name']}",
                f"💰 价格: {format_num(int(result['price']))} 星声/股",
                f"📦 数量: {result['quantity']:.2f}股",
                f"💳 总花费: {format_num(result['total_cost'])} 星声"
            ]
            if result.get("price_impact"):
                lines.append(result["price_impact"])
            yield event.plain_result("\n".join(lines))
        else:
            yield event.plain_result(f"❌ {result.get('message', '买入失败')}")

    @filter.command("卖出")
    async def cmd_sell_stock(self, event: AstrMessageEvent):
        """卖出股票"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        args = event.message_str.split()

        if len(args) < 3:
            yield event.plain_result(
                "❌ 用法：/卖出 [股票名] [数量]\n"
                "📋 示例：/卖出 腾讯 100"
            )
            return

        stock_name = args[1]
        try:
            quantity = float(args[2])
        except ValueError:
            yield event.plain_result("❌ 数量必须是数字")
            return

        result = await self.stock_service.sell_stock(user_id, stock_name, quantity)

        if result.get("success"):
            lines = [
                f"✅ 卖出成功！",
                f"═══════════════════",
                f"📉 股票: {result['stock_name']}",
                f"💰 价格: {format_num(int(result['price']))} 星声/股",
                f"📦 数量: {result['quantity']:.2f}股",
                f"💵 卖出金额: {format_num(result['sell_amount'])} 星声"
            ]
            if result.get("is_nuo_member"):
                lines.append("🎁 弗糯结社福利：免手续费")
            else:
                lines.append(f"💸 手续费: {format_num(result['fee'])} 星声")
            lines.append(f"💳 净收入: {format_num(result['net_amount'])} 星声")
            if result.get("price_impact"):
                lines.append(result["price_impact"])
            yield event.plain_result("\n".join(lines))
        else:
            yield event.plain_result(f"❌ {result.get('message', '卖出失败')}")

    @filter.command("创立公司")
    async def cmd_create_company(self, event: AstrMessageEvent):
        """创立上市公司"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        args = event.message_str.split(maxsplit=2)

        if len(args) < 3:
            yield event.plain_result(
                f"❌ 用法：/创立公司 [公司名] [初始股价] [描述]\n"
                f"📋 示例：/创立公司 我的公司 100 这是一家好公司\n"
                f"💰 需要资金: {format_num(CONFIG.STOCK_MIN_CAPITAL)} 星声"
            )
            return

        company_name = args[1]
        try:
            init_price = float(args[2].split()[0])  # 取数字部分
        except ValueError:
            yield event.plain_result("❌ 初始股价必须是数字")
            return

        desc = args[2][len(str(init_price)):].strip() if len(args[2].split()) > 1 else "玩家创立的公司"

        result = await self.stock_service.create_company(user_id, company_name, init_price, desc)

        if result.get("success"):
            yield event.plain_result(
                f"🎉 公司创立成功！\n"
                f"═══════════════════\n"
                f"🏢 公司名: {result['company_name']}\n"
                f"💰 初始股价: {format_num(int(result['init_price']))} 星声\n"
                f"📝 描述: {result['desc']}\n"
                f"💵 消耗资金: {format_num(result['required'])} 星声\n"
                f"📦 获得股份: 100,000股（创始人股份）"
            )
        else:
            yield event.plain_result(f"❌ {result.get('message', '创立失败')}")

    @filter.command("k线")
    async def cmd_kline(self, event: AstrMessageEvent):
        """查看股票K线图"""
        await self._ensure_db()

        args = event.message_str.split()

        if len(args) < 2:
            yield event.plain_result(
                "❌ 用法：/k线 [股票名]\n"
                "📋 示例：/k线 腾讯\n"
                "📊 显示最近24小时的价格走势"
            )
            return

        stock_name = args[1]

        # 获取K线数据
        kline_data = await self.stock_service.get_stock_kline(stock_name)

        if not kline_data.get("success"):
            yield event.plain_result(f"❌ {kline_data.get('message', '获取K线数据失败')}")
            return

        price_data = kline_data.get("price_data", [])

        if not price_data:
            yield event.plain_result(f"📊 {stock_name} 暂无价格数据")
            return

        # 构建简单的文本K线图
        lines = [f"📈 {stock_name} - 24小时价格走势", "═══════════════════"]

        # 找出最高和最低价
        prices = [p["price"] for p in price_data]
        max_price = max(prices)
        min_price = min(prices)
        current_price = prices[-1] if prices else 0

        lines.append(f"💰 当前: {format_num(int(current_price))} | 📈 最高: {format_num(int(max_price))} | 📉 最低: {format_num(int(min_price))}")
        lines.append("")

        # 显示最近10个数据点
        recent_data = price_data[-10:] if len(price_data) > 10 else price_data

        for data in recent_data:
            time_str = data["timestamp"][-5:] if len(data["timestamp"]) > 5 else data["timestamp"]  # 只显示 HH:MM
            price = data["price"]
            # 简单的可视化
            bar_length = int((price - min_price) / (max_price - min_price) * 20) if max_price > min_price else 10
            bar = "█" * bar_length
            lines.append(f"{time_str} |{bar} {format_num(int(price))}")

        yield event.plain_result("\n".join(lines))

    # ============== 结社系统命令 ==============

    @filter.command("结社")
    async def cmd_society(self, event: AstrMessageEvent):
        """查看结社信息（所有结社列表或我的结社）"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())

        # 先尝试获取我的结社
        my_society = await self.society_service.get_my_society(user_id)

        # 获取结社统计
        stats = await self.society_service.get_society_stats()

        lines = ["🏢 结社列表", "═══════════════════"]

        for name, config in CONFIG.SOCIETIES.items():
            emoji = config.get('emoji', '🔮')
            desc = config.get('desc', '')
            stat = stats.get('stats', {}).get(name, {})
            count = stat.get('count', 0)
            percentage = stat.get('percentage', 0)

            # 标记我所在的结社
            is_my_society = my_society.get('success') and my_society.get('society_name') == name
            marker = " ✅" if is_my_society else ""

            lines.append(f"{emoji} {name}{marker}")
            lines.append(f"   📝 {desc}")
            lines.append(f"   👥 成员：{count}人 ({percentage:.1f}%)")
            lines.append("")

        # 如果已加入结社，显示我的结社信息
        if my_society.get('success'):
            lines.extend([
                "═══════════════════",
                f"{my_society.get('emoji', '🔮')} 我的结社：{my_society.get('society_name', '')}",
                f"👥 成员数：{my_society.get('member_count', 0)} 人",
            ])

            # 显示福利
            benefits = my_society.get('benefits', {})
            if benefits:
                lines.append(f"🎁 福利：{benefits.get('detail', '')}")

            # 显示结社第一
            top_user = my_society.get('top_user', {})
            if top_user:
                is_me = top_user.get('is_me', False)
                title = top_user.get('title', '结社第一')
                if is_me:
                    lines.append(f"👑 你是本结社资产第一！({title})")

        lines.extend([
            "",
            "💡 使用 /结社信息 [结社名] 查看详情",
            "💡 使用 /加入结社 [结社名] 加入结社"
        ])

        yield event.plain_result("\n".join(lines))

    @filter.command("结社信息")
    async def cmd_society_info(self, event: AstrMessageEvent):
        """查看指定结社详情"""
        await self._ensure_db()

        args = event.message_str.split(maxsplit=1)
        if len(args) < 2:
            yield event.plain_result(
                "❌ 请指定结社名称\n"
                "📋 用法：/结社信息 [结社名]\n"
                "💡 可用结社：" + ", ".join(CONFIG.SOCIETIES.keys())
            )
            return

        society_name = args[1].strip()
        if society_name not in CONFIG.SOCIETIES:
            yield event.plain_result(
                f"❌ 结社不存在！\n"
                f"📋 可用结社：{', '.join(CONFIG.SOCIETIES.keys())}"
            )
            return

        config = CONFIG.SOCIETIES[society_name]
        benefits = await self.society_service.get_society_benefit_detail(society_name)

        lines = [
            f"{config.get('emoji', '🔮')} {society_name}",
            "═══════════════════",
            f"📝 {config.get('desc', '')}",
            ""
        ]

        # 显示福利详情
        if benefits:
            lines.append(f"🎁 结社福利：{benefits.get('type', '')}")
            lines.append(f"   {benefits.get('detail', '')}")
            lines.append("")

        lines.extend([
            f"⏰ 更换冷却：{CONFIG.SOCIETY_COOLDOWN}小时",
            "",
            "💡 使用 /加入结社 [结社名] 加入此结社"
        ])

        yield event.plain_result("\n".join(lines))

    @filter.command("加入结社")
    async def cmd_join_society(self, event: AstrMessageEvent):
        """加入指定结社"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        args = event.message_str.split(maxsplit=1)

        if len(args) < 2:
            yield event.plain_result(
                "❌ 请指定结社名称\n"
                "📋 用法：/加入结社 [结社名]\n"
                "💡 可用结社：" + ", ".join(CONFIG.SOCIETIES.keys())
            )
            return

        society_name = args[1].strip()
        result = await self.society_service.join_society(user_id, society_name)

        if result.get("success"):
            yield event.plain_result(
                f"✅ 成功加入 {result.get('emoji', '🔮')} {society_name}！\n"
                f"═══════════════════\n"
                f"📝 {result.get('desc', '')}\n"
                f"\n"
                f"💡 使用 /我的结社 查看结社详情和福利"
            )
        else:
            yield event.plain_result(f"❌ {result.get('message', '加入失败')}")

    @filter.command("离开结社")
    async def cmd_leave_society(self, event: AstrMessageEvent):
        """离开当前结社"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())

        # 使用society_service离开结社
        result = await self.society_service.leave_society(user_id)

        if not result['success']:
            yield event.plain_result(f"❌ {result['message']}")
            return

        yield event.plain_result(
            f"✅ {result['message']}\n"
            f"⏰ 冷却时间：{CONFIG.SOCIETY_COOLDOWN}小时后可以加入新结社"
        )

    @filter.command("我的结社")
    async def cmd_my_society(self, event: AstrMessageEvent):
        """查看我的结社信息"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        result = await self.society_service.get_my_society(user_id)

        if not result.get("success"):
            yield event.plain_result(
                f"💼 你还没有加入任何结社\n"
                f"═══════════════════\n"
                f"📋 可用结社：\n"
            )
            for name, config in CONFIG.SOCIETIES.items():
                yield event.plain_result(
                    f"{config.get('emoji', '🔮')} {name} - {config.get('desc', '')}"
                )
            yield event.plain_result(
                f"\n💡 使用 /加入结社 [结社名] 加入结社\n"
                f"💡 使用 /结社列表 查看所有结社"
            )
            return

        lines = [
            f"{result.get('emoji', '🔮')} 我的结社：{result.get('society_name', '')}",
            "═══════════════════",
            f"📝 {result.get('desc', '')}",
            f"👥 成员数：{result.get('member_count', 0)} 人",
            f"📅 加入时间：{result.get('join_time', '')}",
            ""
        ]

        # 显示福利
        benefits = result.get('benefits', {})
        if benefits:
            lines.append(f"🎁 结社福利：{benefits.get('type', '')}")
            lines.append(f"   {benefits.get('detail', '')}")
            lines.append("")

        # 显示结社第一
        top_user = result.get('top_user', {})
        if top_user:
            is_me = top_user.get('is_me', False)
            title = top_user.get('title', '结社第一')
            if is_me:
                lines.append(f"👑 你是本结社资产第一！({title})")
            else:
                lines.append(f"👑 本结社资产第一：{mask_id(top_user.get('uid', ''))} ({title})")
            lines.append("")

        lines.extend([
            f"⏰ 更换冷却：{result.get('cooldown', 24)}小时",
            "",
            "💡 使用 /离开结社 退出当前结社"
        ])

        yield event.plain_result("\n".join(lines))

    # ============== 工作系统命令 ==============

    @filter.command("找工作")
    async def cmd_find_work(self, event: AstrMessageEvent):
        """查看可应聘的工作列表"""
        await self._ensure_db()

        works = await self.work_service.get_works()

        lines = ["💼 工作列表", "═══════════════════"]

        for name, config in works.items():
            emoji = config.get('emoji', '💼')
            desc = config.get('desc', '')
            price = config.get('price', 0)
            min_pay = config.get('min', 0)
            max_pay = config.get('max', 0)

            lines.append(f"{emoji} {name}")
            lines.append(f"   📝 {desc}")
            lines.append(f"   💰 应聘费用：{format_num(price)} 星声")
            lines.append(f"   📈 时薪：{format_num(min_pay)}-{format_num(max_pay)} 星声/小时")
            lines.append("")

        lines.extend([
            "═══════════════════",
            "💡 使用 /应聘 [工作名] 应聘工作",
            "💡 使用 /工作状态 查看当前工作",
            "💡 使用 /领工资 领取累计工资"
        ])

        yield event.plain_result("\n".join(lines))

    @filter.command("应聘")
    async def cmd_apply_work(self, event: AstrMessageEvent):
        """应聘指定工作"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        args = event.message_str.split(maxsplit=1)

        if len(args) < 2:
            yield event.plain_result(
                "❌ 请指定工作名称\n"
                "📋 用法：/应聘 [工作名]\n"
                "💡 使用 /找工作 查看可应聘职位"
            )
            return

        work_name = args[1].strip()
        result = await self.work_service.apply_work(user_id, work_name)

        if result.get("success"):
            yield event.plain_result(
                f"✅ 应聘成功！\n"
                f"═══════════════════\n"
                f"{result.get('emoji', '💼')} {work_name}\n"
                f"📝 {CONFIG.WORKS.get(work_name, {}).get('desc', '')}\n"
                f"💰 应聘费用：{format_num(result.get('price', 0))} 星声\n"
                f"📅 开始时间：{result.get('start_time', '')}\n"
                f"\n"
                f"💡 使用 /工作状态 查看工作进度\n"
                f"💡 使用 /领工资 领取工资"
            )
        else:
            yield event.plain_result(f"❌ {result.get('message', '应聘失败')}")

    @filter.command("工作状态")
    async def cmd_work_status(self, event: AstrMessageEvent):
        """查看当前工作状态"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        result = await self.work_service.get_work_status(user_id)

        if not result.get("success"):
            yield event.plain_result(
                f"{result.get('message', '获取工作状态失败')}\n"
                f"💡 使用 /找工作 查看可应聘职位"
            )
            return

        lines = [
            f"{result.get('emoji', '💼')} 当前工作：{result.get('work_name', '')}",
            "═══════════════════",
            f"📝 {result.get('desc', '')}",
            f"⏰ 已工作时间：{result.get('hours_passed', 0)} 小时",
            f"💰 待领取工资：约 {format_num(result.get('pending', 0))} 星声",
            f"💵 累计收入：{format_num(result.get('total_earned', 0))} 星声",
            "",
            "💡 使用 /领工资 领取累计工资"
        ]

        yield event.plain_result("\n".join(lines))

    @filter.command("领工资")
    async def cmd_claim_salary(self, event: AstrMessageEvent):
        """领取工作工资"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        result = await self.work_service.claim_salary(user_id)

        if result.get("success"):
            lines = [
                f"✅ 工资领取成功！",
                "═══════════════════",
                f"{result.get('emoji', '💼')} {result.get('work_name', '')}",
                f"⏰ 工作时长：{result.get('hours', 0)} 小时",
                f"💰 基础工资：{format_num(result.get('total_earnings', 0))} 星声"
            ]

            # 千衢结社福利
            if result.get('qian_bonus', 0) > 0:
                lines.append(f"⚡ 千衢结社加成：+{format_num(result.get('qian_bonus', 0))} 星声")

            lines.extend([
                f"💵 总收入：{format_num(result.get('final_earnings', 0))} 星声",
                f"💳 当前余额：{format_num(result.get('new_balance', 0))} 星声"
            ])

            yield event.plain_result("\n".join(lines))
        else:
            yield event.plain_result(f"❌ {result.get('message', '领取失败')}")

    # ============== 塔罗牌系统命令 ==============

    @filter.command("塔罗牌")
    async def cmd_tarot(self, event: AstrMessageEvent):
        """抽取或查看今日塔罗牌"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        args = event.message_str.split()

        # 检查是否是查看效果
        if len(args) > 1 and args[1] == "效果":
            result = await self.tarot_service.get_tarot_effect(user_id)

            if not result['has_tarot']:
                yield event.plain_result(
                    "🎴 今日尚未抽取塔罗牌\n"
                    "═══════════════════\n"
                    "💡 使用 /塔罗牌 抽取今日塔罗牌"
                )
                return

            yield event.plain_result(
                f"🎴 今日塔罗牌效果\n"
                f"═══════════════════\n"
                f"【{result['card_name']}】\n"
                f"📝 {result['desc']}\n"
                f"\n"
                f"✨ 效果类型：{result['effect_type']}\n"
                f"📊 效果值：{result['effect_value']}\n"
                f"📝 效果描述：{result['effect_desc']}"
            )
            return

        # 抽取塔罗牌
        result = await self.tarot_service.draw_tarot(user_id)

        if result['already_drawn']:
            yield event.plain_result(
                f"🎴 今日已抽取塔罗牌\n"
                f"═══════════════════\n"
                f"【{result['card_name']}】\n"
                f"📝 {result['desc']}\n"
                f"✨ 效果：{result['effect'].get('desc', '')}\n"
                f"\n"
                f"💡 使用 /塔罗牌 效果 查看当前效果详情"
            )
            return

        lines = [
            f"🎴 今日塔罗牌",
            "═══════════════════",
            f"【{result['card_name']}】",
            f"📝 {result['desc']}",
            f"✨ 效果：{result['effect'].get('desc', '')}",
            ""
        ]

        if result['effect_result']:
            lines.append(f"🎯 效果已触发：{result['effect_result']}")

        lines.append("\n💡 使用 /塔罗牌 效果 查看详情")

        yield event.plain_result("\n".join(lines))

    # ============== 资产/余额查询命令（同义词）==============

    @filter.command("资产")
    async def cmd_asset(self, event: AstrMessageEvent):
        """查看个人资产详情"""
        await self._ensure_db()

        user_id = str(event.get_sender_id())
        total, cash, bank, stock = await self._get_user_asset(user_id)

        lines = [
            f"💎 我的资产",
            "═══════════════════",
            f"💰 总资产：{format_num(total)} 星声",
            f"",
            f"💳 现金：{format_num(cash)} 星声",
            f"🏦 银行存款：{format_num(bank)} 星声",
            f"📈 股票市值：{format_num(stock)} 星声",
        ]

        # 获取用户排名
        all_users = await self.stats_service.get_all_users_assets()
        if all_users:
            rank = sum(1 for u in all_users if u["total"] > total) + 1
            total_users = len(all_users)
            percentile = (rank / total_users) * 100
            lines.extend([
                f"",
                f"📊 排名：第 {rank} 名 / 共 {total_users} 人",
                f"📈 超过 {100 - percentile:.1f}% 的用户"
            ])

        yield event.plain_result("\n".join(lines))

    @filter.command("余额")
    async def cmd_balance(self, event: AstrMessageEvent):
        """查看个人余额（与/资产相同）"""
        # 直接调用cmd_asset的实现
        async for result in self.cmd_asset(event):
            yield result
