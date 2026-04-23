"""
favor commands handler
"""
from config import CONFIG
from utils import today_str, mask_id, format_num, get_beijing_time
from astrbot.api.event import AstrMessageEvent

async def cmd_favor(plugin, event: AstrMessageEvent):
    """查看好感度信息"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())
    args = event.message_str.split()

    # 检查是否是查看排行榜
    if len(args) > 1 and args[1] == "排行":
        ranking = await plugin.favor_system.get_favor_ranking()

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
        favor_info = await plugin.favor_system.get_user_favor_info(user_id)
        rel_info = await plugin.favor_system.get_relationship_desc(user_id)

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

async def cmd_gift(plugin, event: AstrMessageEvent):
    """送礼物给莫宁宁"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())
    args = event.message_str.split(maxsplit=1)

    if len(args) < 2:
        items = plugin.favor_system.get_favor_items()
        yield event.plain_result(
            f"❌ 请指定要送的礼物\n"
            f"📋 用法：/赠送 [物品名]\n"
            f"🎁 可用礼物：{', '.join(items.keys())}"
        )
        return

    item_name = args[1].strip()
    result = await plugin.favor_system.gift_item(user_id, item_name)

    yield event.plain_result(result['message'])

async def cmd_favor_ranking(plugin, event: AstrMessageEvent):
    """查看好感度排行榜"""
    await plugin._ensure_db()

    ranking = await plugin.favor_system.get_favor_ranking()

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

