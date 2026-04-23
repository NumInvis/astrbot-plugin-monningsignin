"""
society commands handler
"""
from config import CONFIG
from utils import today_str, mask_id, format_num, get_beijing_time
from astrbot.api.event import AstrMessageEvent

async def cmd_society(plugin, event: AstrMessageEvent):
    """查看结社信息（所有结社列表或我的结社）"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())

    # 先尝试获取我的结社
    my_society = await plugin.society_service.get_my_society(user_id)

    # 获取结社统计
    stats = await plugin.society_service.get_society_stats()

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

async def cmd_society_info(plugin, event: AstrMessageEvent):
    """查看指定结社详情"""
    await plugin._ensure_db()

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
    benefits = await plugin.society_service.get_society_benefit_detail(society_name)

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

async def cmd_join_society(plugin, event: AstrMessageEvent):
    """加入指定结社"""
    await plugin._ensure_db()

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
    result = await plugin.society_service.join_society(user_id, society_name)

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

async def cmd_leave_society(plugin, event: AstrMessageEvent):
    """离开当前结社"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())

    # 使用society_service离开结社
    result = await plugin.society_service.leave_society(user_id)

    if not result['success']:
        yield event.plain_result(f"❌ {result['message']}")
        return

    yield event.plain_result(
        f"✅ {result['message']}\n"
        f"⏰ 冷却时间：{CONFIG.SOCIETY_COOLDOWN}小时后可以加入新结社"
    )

async def cmd_my_society(plugin, event: AstrMessageEvent):
    """查看我的结社信息"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())
    result = await plugin.society_service.get_my_society(user_id)

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

