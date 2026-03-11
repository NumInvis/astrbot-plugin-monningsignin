"""
帮助命令模块
集中管理所有帮助相关的命令
"""
from astrbot.api.event import filter, AstrMessageEvent
from config import CONFIG


class HelpCommands:
    """帮助命令类"""
    
    @staticmethod
    async def cmd_signin_help(event: AstrMessageEvent):
        """普通用户帮助"""
        help_text = """📋 指令列表

💰 基础：/签到 /余额 /转账 @用户 金额 /资产排行榜 /经济 /税收
🏦 银行：/银行 /存款 金额 /取款 金额
🛍️ 商店：/商店 /购买 商品 数量 /背包 /使用 物品 /占卜概率 /Allin
💼 工作：/找工作 /应聘 工作名 /工作状态 /领工资
📈 股票：/股市 /买入 股票 数量 /卖出 股票 数量 /持仓 /创立公司 名称 价格 描述 /宣告破产 公司 /研发 公司 金额 /股东 股票 /k线 股票
🏛️ 结社：/结社 /加入结社 名称 /我的结社
💖 好感：/好感度 /好感度排行
🏆 成就：/成就 /塔罗牌
🔧 管理：/高级签到帮助"""
        yield event.plain_result(help_text)
    
    @staticmethod
    async def cmd_advanced_signin_help(event: AstrMessageEvent):
        """管理员帮助"""
        user_id = str(event.get_sender_id())
        
        # 检查是否为管理员
        if user_id not in CONFIG.ADMIN_IDS:
            yield event.plain_result("⛔ 权限不足！此命令仅管理员可用")
            return
        
        help_text = """🔧 管理员指令

系统：/admin reset 用户 /admin add 用户 金额 /admin remove 用户 金额 /admin clear
统计：/admin stats /admin users /admin logs
经济：/admin tax 税率 /admin bank 利率 /admin shop 商品 价格 数量
股票：/admin stock add 名称 价格 描述 /admin stock remove 名称 /admin stock price 名称 价格
商店：/admin shop add 商品名 价格 限购 好感值 描述 /admin shop remove 商品名 /admin shop edit 商品名 属性 值
好感：/admin favor add 用户 数量 /admin favor remove 用户 数量 /admin favor reset 用户
成就：/所有人成就 /授予成就 用户ID/所有人 成就ID /重置签到 用户ID/所有人
赛季：/新赛季 密码"""
        yield event.plain_result(help_text)
