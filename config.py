"""
配置文件
"""
from decimal import Decimal


class Config:
    """配置类"""
    # 税收
    TAX_RATES = [0.10, 0.09, 0.08, 0.07, 0.06, 0.05, 0.04, 0.03, 0.02, 0.01]
    MAX_TAX_RATE = 0.99
    WEALTH_GAP_DIVISOR = 8888.0
    
    # 慈善
    CHARITY_FEE_RATE = 0.01
    CHARITY_RECIPIENT = "1312857963"
    
    # 银行
    BANK_NORMAL_RATE = 0.01
    BANK_VIP_RATE = 0.015
    BANK_WITHDRAW_FEE = 0.001
    
    # 股票
    STOCK_SHARES = Decimal("1000000")
    STOCK_MIN_CAPITAL = Decimal("10000000")
    STOCK_DELIST_PRICE = Decimal("1.00")
    STOCK_COOLDOWN = 60
    STOCK_FEE = Decimal("0.001")
    
    # 商店
    SHOP_ITEMS = {
        "占卜券": {"price": 10, "daily_limit": 10, "desc": "让卜灵给你占一卦吧！"},
        "莫塔里贵宾卡": {"price": 8888, "daily_limit": 1, 
                      "desc": "银行日1.5%，取星声免手续费"},
        "花花": {"price": 5, "daily_limit": 99, "desc": "给莫宁送一朵花花"},
        "索拉里斯之心": {"price": 88888888, "daily_limit": 1, 
                      "desc": "从此不会被莫宁宁禁言（也许）"},
        "真理碎片": {"price": 1000000000, "daily_limit": 1, 
                    "desc": "希望 是无谓的幻象"},
        "期刊论文": {"price": 12345, "daily_limit": 1, "desc": "增加莫宁宁10点好感值"},
        "植物奶": {"price": 250, "daily_limit": 2, "desc": "增加莫宁宁3点好感值"},
        "神秘糖果": {"price": 3000, "daily_limit": 1, "desc": "增加莫宁宁5点好感值"},
        "5090": {"price": 90000, "daily_limit": 1, "desc": "增加莫宁宁15点好感值"},
        "莫宁宁的抱枕": {"price": 5000, "daily_limit": 1, "desc": "增加莫宁宁8点好感值"},
        "定制蛋糕": {"price": 3000, "daily_limit": 1, "desc": "增加莫宁宁6点好感值"},
        "手写信": {"price": 500, "daily_limit": 2, "desc": "增加莫宁宁4点好感值"},
        "音乐会门票": {"price": 8000, "daily_limit": 1, "desc": "增加莫宁宁1点好感值，并有3%概率获得金色成就"},
        "嘉年华": {"price": 6480, "daily_limit": 9, "desc": "增加莫宁宁1点好感值"}
    }
    LOTTERY_LIMIT = 6
    
    # 工作
    WORKS = {
        "长离水军": {"price": 1, "min": 1, "max": 3, "desc": "我🍐一个焚身以火", "emoji": "🔥"},
        "呜呜物流": {"price": 233, "min": 5, "max": 20, "desc": "呜呜物流，使命必达", "emoji": "📦"},
        "金库保安": {"price": 1888, "min": 20, "max": 60, "desc": "别耽误我下班", "emoji": "💰"},
        "夜归军将领": {"price": 68888, "min": 100, "max": 3000, "desc": "乘风而起！", "emoji": "⚔️"},
        "七丘总督": {"price": 777777, "min": 5000, "max": 50000, "desc": "自豪吧，见证烈阳永耀", "emoji": "👑"},
        "黑海岸执花": {"price": 6666666, "min": 50000, "max": 200000, "desc": "这朵花送给你", "emoji": "🌸"},
        "救世主": {"price": 100000000, "min": 1, "max": 1000000, "desc": "你连莫宁宁都不记得了嘛", "emoji": "✨"}
    }
    
    # 结社
    SOCIETIES = {
        "拜月结社": {"emoji": "🌙", "desc": "月相轮转之间，我以我为锚点"},
        "负资产结社": {"emoji": "💸", "desc": "这温暖的光不能熄灭"},
        "千衢结社": {"emoji": "⚡", "desc": "我会切开这个死局"},
        "弗糯结社": {"emoji": "🍚", "desc": "我不会再等了"}
    }
    SOCIETY_COOLDOWN = 24
    
    # 塔罗牌
    TAROT_CARDS = [
        "愚者", "魔术师", "女祭司", "皇后", "皇帝", "教皇",
        "恋人", "战车", "力量", "隐士", "命运之轮", "正义",
        "倒吊人", "死神", "节制", "恶魔", "高塔", "星星",
        "月亮", "太阳", "审判", "世界"
    ]
    TAROT_DESC = {
        "愚者": "世事一场大梦，人生几度秋凉？",
        "魔术师": "那个旅人是个有著柔顺灰色飘逸头发的少女魔女。",
        "女祭司": "它梦见了古老的宫殿和楼阁，在水天辉映的波影里抖颤",
        "皇后": "践远游之文履，曳雾绡之轻裾。",
        "皇帝": "凤阁龙楼连霄汉，玉树琼枝作烟萝。",
        "教皇": "长风吹月度海来，遥劝仙人一杯酒。",
        "战车": "晓战随金鼓，宵眠抱玉鞍。愿将腰下剑，直为斩楼兰。",
        "恋人": "南风知我意，吹梦到西洲。",
        "力量": "己所欲者/杀而夺之/亦同天赐",
        "隐士": "何如鸱夷子，散发弄扁舟。",
        "命运之轮": "几孤风月，屡变星霜。",
        "正义": "聪明的人在这个世界会选择死亡，而更聪明的会选择不出生",
        "倒吊人": "天浆酹西州/昆仑不受/发诸水/千转向三丘",
        "死神": "山雪河冰野萧瑟，青是烽烟白人骨。",
        "节制": "我等待着，长夜漫漫",
        "恶魔": "罪人之狱/警钟长鸣/少女乃是/恶魔之身",
        "高塔": "将如白鸟般振翅/四海为家",
        "星星": "在冷峭的暮冬的黄昏，在寂寞的灰色的清晨",
        "月亮": "明月如霜，好风如水，清景无限。",
        "太阳": "那是古老犹如童话般的传说",
        "审判": "生命的鼓动/为受审而鸣响着",
        "世界": "我们把世界看错了，反说他欺骗我们。"
    }
    
    # 塔罗牌效果
    # 效果类型：
    # - favor_value_reward: 获得好感值
    # - favor_value_penalty: 扣除好感值
    # - balance_reward: 获得星声（绝对值）
    # - balance_penalty: 失去星声（按总资产比例）
    # - stock_price_up: 持仓股票立即上涨
    # - stock_price_down: 持仓股票立即下跌
    # - lose_job: 失去工作
    # - lottery_extra: 占卜次数增加1次
    TAROT_EFFECTS = {
        # 按TAROT_CARDS顺序排列
        "愚者": {"type": "balance_reward", "value": [10, 50], "desc": "获得10-50星声"},
        "魔术师": {"type": "balance_penalty", "value": [0.03, 0.08], "desc": "失去总资产3%-8%的星声"},
        "女祭司": {"type": "favor_value_reward", "value": [1, 10], "desc": "获得1-10点好感值"},
        "高塔": {"type": "favor_value_penalty", "value": [1, 5], "desc": "扣除1-5点好感值"},
        "皇帝": {"type": "stock_price_up", "value": [0.01, 0.03], "desc": "随机一只持仓股票立即上涨1%-3%"},
        "教皇": {"type": "stock_price_down", "value": [0.01, 0.03], "desc": "随机一只持仓股票立即下跌1%-3%"},
        "力量": {"type": "balance_reward", "value": [50, 100], "desc": "获得50-100星声"},
        "战车": {"type": "balance_penalty", "value": [0.05, 0.12], "desc": "失去总资产5%-12%的星声"},
        "恋人": {"type": "favor_value_reward", "value": [5, 20], "desc": "获得5-20点好感值"},
        "隐士": {"type": "favor_value_penalty", "value": [3, 10], "desc": "扣除3-10点好感值"},
        "命运之轮": {"type": "stock_price_up", "value": [0.01, 0.03], "desc": "随机一只持仓股票立即上涨1%-3%"},
        "正义": {"type": "stock_price_down", "value": [0.01, 0.03], "desc": "随机一只持仓股票立即下跌1%-3%"},
        "倒吊人": {"type": "lottery_extra", "value": 1, "desc": "占卜次数增加1次"},
        "死神": {"type": "lose_job", "value": 1, "desc": "失去当前工作"},
        "节制": {"type": "balance_reward", "value": [100, 200], "desc": "获得100-200星声"},
        "恶魔": {"type": "balance_penalty", "value": [0.08, 0.15], "desc": "失去总资产8%-15%的星声"},
        "皇后": {"type": "favor_value_reward", "value": [10, 50], "desc": "获得10-50点好感值"},
        "星星": {"type": "favor_value_penalty", "value": [5, 20], "desc": "扣除5-20点好感值"},
        "月亮": {"type": "balance_reward", "value": [200, 500], "desc": "获得200-500星声"},
        "太阳": {"type": "balance_penalty", "value": [0.10, 0.20], "desc": "失去总资产10%-20%的星声"},
        "审判": {"type": "balance_penalty", "value": [0.15, 0.25], "desc": "失去总资产15%-25%的星声"},
        "世界": {"type": "lottery_extra", "value": 2, "desc": "占卜次数增加2次"}
    }
    
    # 系统管理员
    ADMIN_IDS = ["1312857963"]
    # 特殊成就用户
    CYCLE_BREAKER_USERS = ["471009846", "2819524649", "2102611814"]
    # 系统密码
    SEASON_PASSWORD = "moningningning"
    
    # 签到
    BASE_SIGNIN_REWARD = 10
    
    # 赛季
    CURRENT_SEASON = 1
    
    # 成就加成配置
    # 根据用户要求，每个品质的成就都有特定的永久性加成效果：
    # 蓝色：每日签到额外增加1个星声
    # 紫色：银行存款利率永久性提升0.1个百分点
    # 金色：创立公司时额外赠送1000股
    # 彩色：每日签到额外获得1点好感值
    ACHIEVEMENT_BONUSES = {
        "blue": {
            "type": "signin_extra",
            "value": 1,  # 每日签到额外增加1个星声
            "desc": "每日签到额外增加1个星声"
        },
        "purple": {
            "type": "bank_rate_bonus",
            "value": 0.001,  # 银行存款利率永久性提升0.1个百分点 (0.1% = 0.001)
            "desc": "银行存款利率永久性提升0.1%"
        },
        "gold": {
            "type": "company_shares_bonus",
            "value": 1000,  # 创立公司时额外赠送1000股
            "desc": "创立公司时额外赠送1000股"
        },
        "colorful": {
            "type": "signin_favor_bonus",
            "value": 1,  # 每日签到额外获得1点好感值
            "desc": "每日签到额外获得1点好感值"
        }
    }


CONFIG = Config()
