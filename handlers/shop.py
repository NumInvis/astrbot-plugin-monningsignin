"""
shop commands handler
"""
from config import CONFIG
from utils import today_str, mask_id, format_num, get_beijing_time
from astrbot.api.event import AstrMessageEvent

async def cmd_shop(plugin, event: AstrMessageEvent):
    """商店购买"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())
    args = event.message_str.split(maxsplit=1)

    if len(args) < 2:
        # 显示商店列表
        items = await plugin.shop_service.get_shop_items()
        lines = ["🛒 商店", "═══════════════════"]
        for item_id, item in items.items():
            lines.append(f"{item['emoji']} {item['name']} - {format_num(item['price'])} 星声")
            lines.append(f"   📝 {item['desc']}")
        lines.append("\n💡 使用 /购买 [商品名] 购买")
        yield event.plain_result("\n".join(lines))
        return

    # 购买商品
    item_name = args[1].strip()
    result = await plugin.shop_service.buy_item(user_id, item_name)

    if result["success"]:
        # 检查成就
        new_achievements = await plugin.achievement_service.check_achievements(
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

async def cmd_inventory(plugin, event: AstrMessageEvent):
    """查看背包"""
    await plugin._ensure_db()
    
    user_id = str(event.get_sender_id())
    inventory = await plugin.shop_service.get_inventory(user_id)
    
    if not inventory:
        yield event.plain_result("🎒 背包是空的\n去 /商店 购买物品吧！")
        return
    
    lines = ["🎒 我的背包", "═══════════════════"]
    for item in inventory:
        lines.append(f"{item['emoji']} {item['name']} x{item['quantity']}")
    
    yield event.plain_result("\n".join(lines))

async def cmd_lottery(plugin, event: AstrMessageEvent):
    """占卜抽奖 - /占卜 金额"""
    await plugin._ensure_db()

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

    result = await plugin.shop_service.do_lottery(user_id, bet)

    if result["success"]:
        new_achievements = await plugin.achievement_service.check_achievements(
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

async def cmd_allin(plugin, event: AstrMessageEvent):
    """Allin - 全部资金抽奖，无占卜券时自动购买"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())

    # 获取用户余额
    async with aiosqlite.connect(plugin.db_path) as db:
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
    async with aiosqlite.connect(plugin.db_path) as db:
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
        
        buy_result = await plugin.shop_service.buy_item(user_id, "占卜券", 1)
        if not buy_result["success"]:
            yield event.plain_result(f"❌ 自动购买占卜券失败：{buy_result['message']}")
            return
        
        auto_bought = True
        # 刷新余额
        balance = buy_result["new_balance"]

    # 检查今日占卜次数
    lottery_info = await plugin.shop_service.get_inventory(user_id)
    if lottery_info["remaining_lottery_count"] <= 0:
        yield event.plain_result(f"❌ 今日占卜次数已用完！（{lottery_info['used_lottery_count']}/{CONFIG.LOTTERY_LIMIT}次）")
        return

    # Allin：投入全部余额
    bet = balance
    result = await plugin.shop_service.do_lottery(user_id, bet, is_allin=True)

    if result["success"]:
        new_achievements = await plugin.achievement_service.check_achievements(
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

async def cmd_lottery_prob(plugin, event: AstrMessageEvent):
    """查看占卜概率分布"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())
    result = await plugin.shop_service.get_lottery_probability(user_id)

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

