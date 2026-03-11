"""
工具函数模块
统一存放项目中使用的工具函数，避免重复定义
"""
from datetime import datetime


def today_str() -> str:
    """获取今天的日期字符串"""
    return datetime.now().strftime("%Y-%m-%d")


def now_str() -> str:
    """获取当前时间的字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_num(n: int) -> str:
    """格式化数字，添加千位分隔符"""
    return f"{n:,}"


def mask_id(uid: str) -> str:
    """隐藏用户ID中间部分"""
    if len(uid) <= 4:
        return uid
    return uid[:3] + "***" + uid[-2:]


def parse_amount(amount_str: str) -> int:
    """解析金额字符串，支持k/m/b后缀"""
    amount_str = amount_str.lower().strip()
    multipliers = {
        'k': 1000,
        'm': 1000000,
        'b': 1000000000
    }
    
    for suffix, multiplier in multipliers.items():
        if amount_str.endswith(suffix):
            try:
                return int(float(amount_str[:-1]) * multiplier)
            except ValueError:
                return 0
    
    try:
        return int(amount_str)
    except ValueError:
        return 0


def calculate_percentage(value: int, percentage: float) -> int:
    """计算百分比值"""
    return int(value * percentage)


def truncate_string(s: str, max_length: int = 100) -> str:
    """截断字符串到指定长度"""
    if len(s) <= max_length:
        return s
    return s[:max_length-3] + "..."
