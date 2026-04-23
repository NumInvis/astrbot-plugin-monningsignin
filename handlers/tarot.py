"""
tarot commands handler
"""
from config import CONFIG
from utils import today_str, mask_id, format_num, get_beijing_time
from astrbot.api.event import AstrMessageEvent

async def cmd_tarot(plugin, event: AstrMessageEvent):
    """抽取或查看今日塔罗牌"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())
    args = event.message_str.split()

    # 检查是否是查看效果
    if len(args) > 1 and args[1] == "效果":
        result = await plugin.tarot_service.get_tarot_effect(user_id)

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
    result = await plugin.tarot_service.draw_tarot(user_id)

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

