"""
announcement commands handler
"""
from config import CONFIG
from utils import today_str, mask_id, format_num, get_beijing_time
from astrbot.api.event import AstrMessageEvent

async def cmd_announcement(plugin, event: AstrMessageEvent):
    """查看公告"""
    await plugin._ensure_db()

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
                success = await plugin.announcement_service.delete_announcement(ann_id)
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
                success = await plugin.announcement_service.pin_announcement(ann_id)
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
                success = await plugin.announcement_service.add_whitelist(group_id)
                if success:
                    whitelist = await plugin.announcement_service.get_whitelist()
                    yield event.plain_result(f"✅ 群 {group_id} 已添加到白名单\n📋 当前白名单共 {len(whitelist)} 个群")
                else:
                    yield event.plain_result("❌ 添加失败")
            elif len(args) > 3 and args[2] in ["移除", "remove"]:
                group_id = args[3]
                success = await plugin.announcement_service.remove_whitelist(group_id)
                if success:
                    whitelist = await plugin.announcement_service.get_whitelist()
                    yield event.plain_result(f"✅ 群 {group_id} 已从白名单移除\n📋 当前白名单共 {len(whitelist)} 个群")
                else:
                    yield event.plain_result("❌ 移除失败")
            elif len(args) > 2 and args[2] in ["列表", "list"]:
                whitelist = await plugin.announcement_service.get_whitelist()
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
    announcements = await plugin.announcement_service.get_announcements(limit=10)

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

