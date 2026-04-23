"""
stock commands handler
"""
from config import CONFIG
from utils import today_str, mask_id, format_num, get_beijing_time
from astrbot.api.event import AstrMessageEvent

async def cmd_stock_market(plugin, event: AstrMessageEvent):
    """查看股市行情"""
    await plugin._ensure_db()

    stocks = await plugin.stock_service.get_stock_market()

    if not stocks:
        yield event.plain_result("📊 股市暂无上市公司\n发送 /创立公司 创建你的公司")
        return

    # 获取市场情绪
    market_sentiment = await plugin.stock_service.get_market_sentiment()
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

async def cmd_portfolio(plugin, event: AstrMessageEvent):
    """查看股票持仓"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())
    portfolio = await plugin.stock_service.get_portfolio(user_id)

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

async def cmd_buy_stock(plugin, event: AstrMessageEvent):
    """买入股票"""
    await plugin._ensure_db()

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

    result = await plugin.stock_service.buy_stock(user_id, stock_name, quantity)

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

async def cmd_sell_stock(plugin, event: AstrMessageEvent):
    """卖出股票"""
    await plugin._ensure_db()

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

    result = await plugin.stock_service.sell_stock(user_id, stock_name, quantity)

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

async def cmd_create_company(plugin, event: AstrMessageEvent):
    """创立上市公司"""
    await plugin._ensure_db()

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

    result = await plugin.stock_service.create_company(user_id, company_name, init_price, desc)

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

async def cmd_kline(plugin, event: AstrMessageEvent):
    """查看股票K线图"""
    await plugin._ensure_db()

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
    kline_data = await plugin.stock_service.get_stock_kline(stock_name)

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

