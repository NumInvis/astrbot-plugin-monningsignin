"""
basic commands handler
"""
from config import CONFIG
from utils import today_str, mask_id, format_num, get_beijing_time
from astrbot.api.event import AstrMessageEvent

async def cmd_signin(plugin, event: AstrMessageEvent):
    """每日签到 - 自动结算利息、领取工资、抽取塔罗牌、领取分红"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())
    nickname = plugin._get_sender_name(event)

    # ========== 签到前自动结算 ==========

    # 1. 自动结算银行利息
    bank_info = await plugin.bank_service.get_bank_info(user_id)
    bank_before = bank_info["bank"]

    # 2. 自动领取工资
    salary_result = await plugin.work_service.claim_salary(user_id)

    # 3. 自动抽取塔罗牌
    tarot_result = await plugin.tarot_service.draw_tarot(user_id)

    # 获取用户排名百分比（用于低保加成）
    total, cash, bank, stock = await plugin._get_user_asset(user_id)
    all_users = await plugin.stats_service.get_all_users_assets()
    if len(all_users) > 1:
        rank = sum(1 for u in all_users if u["total"] > total) + 1
        percentile = rank / len(all_users)
    else:
        percentile = 0.5

    # 执行签到
    result = await plugin.signin_service.signin(user_id, percentile)

    if result["success"]:
        # 检查成就
        new_achievements = await plugin.achievement_service.check_achievements(
            user_id, "signin", {"consecutive": result["consecutive_days"]}
        )

        # 获取更新后的银行余额（用于计算利息）
        bank_info_after = await plugin.bank_service.get_bank_info(user_id)
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
        tax_bonus, remaining_pool = await plugin.tax_service.claim_tax_bonus(user_id)
        if tax_bonus > 0:
            lines.append(f"🎁 税收分红：+{format_num(tax_bonus)} 星声（奖池剩余{format_num(remaining_pool)}）")

        # 显示新成就
        if new_achievements:
            lines.append("\n🏆 【新成就】")
            for a in new_achievements:
                lines.append(f"{a['emoji']} {a['name']}\n   📝 {a['desc']}")

        # 重新查询实际余额（包含所有收入）
        total, cash, bank, stock = await plugin._get_user_asset(user_id)
        lines.append(f"\n💳 实际余额：{format_num(cash)} 星声")
        lines.append(f"🏦 银行存款：{format_num(bank)} 星声")
        lines.append(f"📈 总资产：{format_num(total)} 星声")

        yield event.plain_result("\n".join(lines))
    else:
        yield event.plain_result(f"❌ {result['message']}")

async def cmd_asset_ranking(plugin, event: AstrMessageEvent):
    """查看资产排行榜前十名"""
    await plugin._ensure_db()

    top10 = await plugin.stats_service.get_top10_assets()
    
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
    total_wealth = await plugin.stats_service.get_total_wealth()
    player_count = await plugin.stats_service.get_player_count()
    avg_wealth = await plugin.stats_service.get_average_wealth()
    
    lines.extend([
        "═══════════════════",
        f"📊 服务器统计：",
        f"   玩家总数：{player_count} 人",
        f"   经济总量：{format_num(total_wealth)} 星声",
        f"   人均资产：{format_num(int(avg_wealth))} 星声"
    ])

    yield event.plain_result("\n".join(lines))

async def cmd_economy_stats(plugin, event: AstrMessageEvent):
    """查看经济统计（最近7天）"""
    await plugin._ensure_db()

    stats = await plugin.stats_service.get_economy_stats(days=7)
    tax_stats = await plugin.tax_service.get_tax_stats(days=7)

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

async def cmd_signin_help(plugin, event: AstrMessageEvent):
    """显示签到帮助信息（所有用户）"""
    yield event.plain_result(get_signin_help())

async def cmd_asset(plugin, event: AstrMessageEvent):
    """查看个人资产详情"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())
    total, cash, bank, stock = await plugin._get_user_asset(user_id)

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
    all_users = await plugin.stats_service.get_all_users_assets()
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

async def cmd_balance(plugin, event: AstrMessageEvent):
    """查看个人余额（与/资产相同）"""
    # 直接调用cmd_asset的实现
    async for result in plugin.cmd_asset(event):
        yield result

