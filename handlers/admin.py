"""
admin commands handler
"""
from config import CONFIG
from utils import today_str, mask_id, format_num, get_beijing_time
from astrbot.api.event import AstrMessageEvent
from datetime import timedelta

async def cmd_collect_tax(plugin, event: AstrMessageEvent):
    """管理员强制收税"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())

    # 检查是否为管理员
    if user_id not in CONFIG.ADMIN_IDS:
        yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
        return

    result = await plugin.tax_service.force_collect_tax()

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

async def cmd_yesterday_tax(plugin, event: AstrMessageEvent):
    """查看昨日税收"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())

    # 检查是否为管理员
    if user_id not in CONFIG.ADMIN_IDS:
        yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
        return

    yesterday = (get_beijing_time() - timedelta(days=1)).strftime("%Y-%m-%d")

    # 使用tax_service获取税收统计
    stats = await plugin.tax_service.get_tax_stats(days=2)
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

async def cmd_give_subsidy(plugin, event: AstrMessageEvent):
    """发放补贴给指定用户"""
    await plugin._ensure_db()

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
    target_user = plugin._extract_target_user(event)
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
    result = await plugin.admin_service.give_subsidy(target_user, amount)

    if result['success']:
        yield event.plain_result(
            f"✅ 补贴发放成功！\n"
            f"👤 用户：{mask_id(target_user)}\n"
            f"💰 金额：{format_num(amount)} 星声\n"
            f"💳 新余额：{format_num(result['new_balance'])} 星声"
        )
    else:
        yield event.plain_result(f"❌ {result['message']}")

async def cmd_deduct_asset(plugin, event: AstrMessageEvent):
    """扣除用户资产"""
    await plugin._ensure_db()

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
    target_user = plugin._extract_target_user(event)
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
    result = await plugin.admin_service.deduct_asset(target_user, amount)

    if result['success']:
        yield event.plain_result(
            f"✅ 资产扣除成功！\n"
            f"👤 用户：{mask_id(target_user)}\n"
            f"💰 扣除金额：{format_num(amount)} 星声\n"
            f"💳 新余额：{format_num(result['new_balance'])} 星声"
        )
    else:
        yield event.plain_result(f"❌ {result['message']}")

async def cmd_season_info(plugin, event: AstrMessageEvent):
    """查看当前赛季信息"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())

    # 检查是否为管理员
    if user_id not in CONFIG.ADMIN_IDS:
        yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
        return

    season = await plugin.config_manager.get_season()

    lines = [
        "🎮 当前赛季信息",
        "═══════════════════",
        f"📅 当前赛季：第 {season} 赛季",
        "",
        "💡 使用 /新赛季 开启新赛季",
        "⚠️ 开启新赛季将重置所有用户数据！"
    ]

    yield event.plain_result("\n".join(lines))

async def cmd_new_season(plugin, event: AstrMessageEvent):
    """开启新赛季"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())

    # 检查是否为管理员
    if user_id not in CONFIG.ADMIN_IDS:
        yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
        return

    # 获取当前赛季
    current_season = await plugin.config_manager.get_season()
    new_season = current_season + 1

    # 开启新赛季
    await plugin.admin_service.start_new_season()
    await plugin.config_manager.set_season(new_season)

    yield event.plain_result(
        f"🎉 新赛季开启成功！\n"
        f"═══════════════════\n"
        f"📅 当前赛季：第 {new_season} 赛季\n"
        f"✅ 所有用户数据已重置"
    )

async def cmd_all_achievements(plugin, event: AstrMessageEvent):
    """管理员查看所有人成就统计"""
    await plugin._ensure_db()
    
    user_id = str(event.get_sender_id())
    
    # 检查是否为管理员
    if user_id not in CONFIG.ADMIN_IDS:
        yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
        return
    
    # 获取所有用户的成就统计
    all_stats = await plugin.achievement_service.get_all_achievements()
    
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

async def cmd_grant_achievement(plugin, event: AstrMessageEvent):
    """管理员授予成就"""
    await plugin._ensure_db()
    
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
    target_user = plugin._extract_target_user(event)
    achievement_id = args[-1]  # 最后一个参数是成就ID
    
    if target_user == "所有人":
        # 授予所有用户
        result = await plugin.achievement_service.grant_achievement_to_all(achievement_id)
        if result["success"]:
            yield event.plain_result(f"✅ 已成功授予所有用户成就：{result['achievement_name']}")
        else:
            yield event.plain_result(f"❌ {result['message']}")
    elif target_user:
        # 授予单个用户
        result = await plugin.achievement_service.grant_achievement(target_user, achievement_id)
        if result["success"]:
            yield event.plain_result(f"✅ 已成功授予 {mask_id(target_user)} 成就：{result['achievement_name']}")
        else:
            yield event.plain_result(f"❌ {result['message']}")
    else:
        yield event.plain_result("❌ 请指定目标用户（@用户或输入QQ号）")

async def cmd_achievements_info(plugin, event: AstrMessageEvent):
    """管理员查看所有成就ID"""
    await plugin._ensure_db()
    
    user_id = str(event.get_sender_id())
    
    # 检查是否为管理员
    if user_id not in CONFIG.ADMIN_IDS:
        yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
        return
    
    # 获取所有成就
    all_achievements = await plugin.achievement_manager.get_all_achievements()
    
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

async def cmd_create_achievement(plugin, event: AstrMessageEvent):
    """管理员创建新成就（自动分配ID）"""
    await plugin._ensure_db()

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
    success = await plugin.achievement_manager.add_custom_achievement(
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

async def cmd_reset_signin(plugin, event: AstrMessageEvent):
    """管理员重置用户签到状态（支持@用户或输入QQ号）"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())

    # 检查是否为管理员
    if user_id not in CONFIG.ADMIN_IDS:
        yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
        return

    # 提取目标用户
    target = plugin._extract_target_user(event)
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
        result = await plugin.admin_service.reset_signin(user_id=None)
        yield event.plain_result(
            f"✅ 已重置 {result['signin_count']} 个用户的签到状态\n"
            f"✅ 已清除 {result['tarot_count']} 条今日塔罗牌记录\n"
            f"💡 这些用户现在可以重新签到和抽塔罗牌"
        )
    else:
        result = await plugin.admin_service.reset_signin(user_id=target)
        if result['success']:
            yield event.plain_result(f"✅ 已重置用户 {mask_id(target)} 的签到状态")
        else:
            yield event.plain_result(f"⚠️ {result['message']}")

async def cmd_admin_help(plugin, event: AstrMessageEvent):
    """显示管理员帮助信息（仅管理员）"""
    user_id = str(event.get_sender_id())

    # 检查是否为管理员
    if user_id not in CONFIG.ADMIN_IDS:
        yield event.plain_result("❌ 权限不足！此命令仅管理员可用")
        return

    yield event.plain_result(get_admin_help())

async def cmd_publish_announcement(plugin, event: AstrMessageEvent):
    """发布公告（管理员）"""
    await plugin._ensure_db()

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

    result = await plugin.announcement_service.publish_announcement(
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

