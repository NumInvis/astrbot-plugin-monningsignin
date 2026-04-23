"""
工具函数模块
统一存放项目中使用的工具函数，避免重复定义
"""
from datetime import datetime, timedelta, timezone


def get_beijing_time() -> datetime:
    """获取北京时间（UTC+8）"""
    utc_now = datetime.now(timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    return utc_now.astimezone(beijing_tz)


def today_str() -> str:
    """获取今天的日期字符串（北京时间）"""
    return get_beijing_time().strftime("%Y-%m-%d")


def now_str() -> str:
    """获取当前时间的字符串（北京时间）"""
    return get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")


def format_num(n: int) -> str:
    """格式化数字，添加千位分隔符"""
    return f"{n:,}"


def mask_id(uid: str) -> str:
    """隐藏用户ID中间部分"""
    if len(uid) <= 4:
        return uid
    return uid[:3] + "***" + uid[-2:]
