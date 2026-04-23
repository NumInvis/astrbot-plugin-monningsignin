"""
bank commands handler
"""
from config import CONFIG
from utils import today_str, mask_id, format_num, get_beijing_time
from astrbot.api.event import AstrMessageEvent

async def cmd_bank(plugin, event: AstrMessageEvent):
    """银行存取款"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())
    args = event.message_str.split()

    if len(args) >= 2:
        action = args[1]
        if action in ["存", "存款"]:
            # 存款
            amount = int(args[2]) if len(args) >= 3 else 0
            if amount <= 0:
                yield event.plain_result("❌ 请输入有效金额")
                return

            result = await plugin.bank_service.deposit(user_id, amount)
            if result["success"]:
                yield event.plain_result(
                    f"✅ 存款成功！\n"
                    f"💰 存入：{format_num(amount)} 星声\n"
                    f"🏦 银行存款：{format_num(result['new_bank'])} 星声\n"
                    f"💳 现金余额：{format_num(result['new_cash'])} 星声\n"
                    f"📈 利率：{result['rate_pct']}%{' (贵宾卡)' if result['has_vip'] else ''}"
                )
            else:
                yield event.plain_result(f"❌ {result['message']}")
            return

        elif action in ["取", "取款"]:
            # 取款
            amount = int(args[2]) if len(args) >= 3 else 0
            if amount <= 0:
                yield event.plain_result("❌ 请输入有效金额")
                return

            result = await plugin.bank_service.withdraw(user_id, amount)
            if result["success"]:
                fee_info = " (免手续费)" if result['is_nuo_member'] else f" (手续费 {format_num(result['fee'])} 星声)"
                yield event.plain_result(
                    f"✅ 取款成功！\n"
                    f"💰 取出：{format_num(result['amount'])} 星声\n"
                    f"💵 实际到账：{format_num(result['net_amount'])} 星声{fee_info}\n"
                    f"🏦 银行存款：{format_num(result['new_bank'])} 星声\n"
                    f"💳 现金余额：{format_num(result['new_cash'])} 星声"
                )
            else:
                yield event.plain_result(f"❌ {result['message']}")
            return

    # 查询银行信息
    bank_info = await plugin.bank_service.get_bank_info(user_id)
    rate_info = f"{bank_info['rate_pct']}%"
    if bank_info['has_vip']:
        rate_info += " (贵宾卡特权)"

    yield event.plain_result(
        f"🏦 银行信息\n"
        f"═══════════════════\n"
        f"💰 银行存款：{format_num(bank_info['bank'])} 星声\n"
        f"💳 现金余额：{format_num(bank_info['balance'])} 星声\n"
        f"📈 日利率：{rate_info}\n"
        f"\n💡 使用 /存款 [金额] 或 /取款 [金额]"
    )

async def cmd_deposit(plugin, event: AstrMessageEvent):
    """银行存款"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())
    args = event.message_str.split()

    if len(args) < 2:
        yield event.plain_result("❌ 用法：/存款 [金额]\n💡 示例：/存款 1000")
        return

    try:
        amount = int(args[1])
    except ValueError:
        yield event.plain_result("❌ 请输入有效的数字金额")
        return

    if amount <= 0:
        yield event.plain_result("❌ 请输入大于0的金额")
        return

    result = await plugin.bank_service.deposit(user_id, amount)
    if result["success"]:
        yield event.plain_result(
            f"✅ 存款成功！\n"
            f"💰 存入：{format_num(amount)} 星声\n"
            f"🏦 银行存款：{format_num(result['new_bank'])} 星声\n"
            f"💳 现金余额：{format_num(result['new_cash'])} 星声\n"
            f"📈 利率：{result['rate_pct']}%{' (贵宾卡)' if result['has_vip'] else ''}"
        )
    else:
        yield event.plain_result(f"❌ {result['message']}")

async def cmd_withdraw(plugin, event: AstrMessageEvent):
    """银行取款"""
    await plugin._ensure_db()

    user_id = str(event.get_sender_id())
    args = event.message_str.split()

    if len(args) < 2:
        yield event.plain_result("❌ 用法：/取款 [金额]\n💡 示例：/取款 1000")
        return

    try:
        amount = int(args[1])
    except ValueError:
        yield event.plain_result("❌ 请输入有效的数字金额")
        return

    if amount <= 0:
        yield event.plain_result("❌ 请输入大于0的金额")
        return

    result = await plugin.bank_service.withdraw(user_id, amount)
    if result["success"]:
        fee_info = " (免手续费)" if result['has_vip'] else f" (手续费 {format_num(result['fee'])} 星声)"
        yield event.plain_result(
            f"✅ 取款成功！\n"
            f"💰 取出：{format_num(result['amount'])} 星声\n"
            f"💵 实际到账：{format_num(result['actual'])} 星声{fee_info}\n"
            f"🏦 银行存款：{format_num(result['new_bank'])} 星声\n"
            f"💳 现金余额：{format_num(result['new_cash'])} 星声"
        )
    else:
        yield event.plain_result(f"❌ {result['message']}")

async def cmd_transfer(plugin, event: AstrMessageEvent):
    """银行转账"""
    await plugin._ensure_db()
    
    user_id = str(event.get_sender_id())
    args = event.message_str.split()
    
    if len(args) < 2:
        yield event.plain_result("❌ 用法：/转账 @用户/QQ号 [金额]")
        return
    
    # 提取目标用户
    target_user = plugin._extract_target_user(event)
    if not target_user:
        # 尝试从参数中提取
        if len(args) >= 2 and args[1].isdigit():
            target_user = args[1]
        else:
            yield event.plain_result("❌ 请指定目标用户（@用户或输入QQ号）")
            return
    
    # 提取金额
    amount = 0
    for part in args:
        if part.isdigit():
            amount = int(part)
            break
    
    if amount <= 0:
        yield event.plain_result("❌ 请输入有效金额")
        return
    
    result = await plugin.bank_service.transfer(user_id, target_user, amount)
    
    if result["success"]:
        yield event.plain_result(
            f"✅ 转账成功！\n"
            f"💰 金额：{format_num(amount)} 星声\n"
            f"👤 收款人：{mask_id(target_user)}"
        )
    else:
        yield event.plain_result(f"❌ {result['message']}")

