#!/usr/bin/env python3
"""
给指定用户授予斩断循环成就
"""
import asyncio
import os
import sys

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from achievement_service import AchievementService

async def main():
    db_path = os.path.join(os.path.dirname(__file__), "data", "signin.db")
    achievement_service = AchievementService(db_path)
    
    # 给2926991145用户授予斩断循环成就
    user_id = "2926991145"
    achievement_id = "cycle_breaker"
    
    success = await achievement_service.grant_achievement(user_id, achievement_id)
    
    if success:
        print(f"✅ 成功给用户 {user_id} 授予了斩断循环成就！")
    else:
        print(f"⚠️ 用户 {user_id} 已经拥有斩断循环成就，无需重复授予。")
    
    # 验证
    user_achievements = await achievement_service.get_user_achievements(user_id)
    print(f"\n用户 {user_id} 的成就列表：")
    for aid, obtain_time in user_achievements.get("obtained", {}).items():
        print(f"  - {aid}: {obtain_time}")

if __name__ == "__main__":
    asyncio.run(main())
