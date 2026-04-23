"""
work commands handler
"""
from config import CONFIG
from utils import today_str, mask_id, format_num, get_beijing_time
from astrbot.api.event import AstrMessageEvent

async def cmd_find_work(plugin, event: AstrMessageEvent):
    """查看可应聘的工作列表"""
    await plugin._ensure_db()

    works = await plugin.work_service.get_works()

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

async def cmd_apply_work(plugin, event: AstrMessageEvent):
    """应聘指定工作"""
    await plugin._ensure_db()

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
    result = await plugin.work_service.apply_work(user_id, work_name)

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

async def cmd_work_status(plugin, event: AstrMessageEvent):
    """查看当前工作状态"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())
    result = await plugin.work_service.get_work_status(user_id)

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

async def cmd_claim_salary(plugin, event: AstrMessageEvent):
    """领取工作工资"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())
    result = await plugin.work_service.claim_salary(user_id)

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

