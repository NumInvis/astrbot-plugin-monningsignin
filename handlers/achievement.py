"""
achievement commands handler
"""
from config import CONFIG
from utils import today_str, mask_id, format_num, get_beijing_time
from astrbot.api.event import AstrMessageEvent

async def cmd_achievements(plugin, event: AstrMessageEvent):
    """查看成就"""
    await plugin._ensure_db()
    
    user_id = str(event.get_sender_id())
    
    # 获取所有成就
    all_achievements = await plugin.achievement_manager.get_all_achievements()
    
    # 获取用户已获得的成就
    user_achievements = await plugin.achievement_service.get_user_achievements(user_id)
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

