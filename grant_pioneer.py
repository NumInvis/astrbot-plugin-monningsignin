#!/usr/bin/env python3
"""
给所有用户发放先行者成就
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
    
    # 给所有用户授予先行者成就
    success_count = await achievement_service.grant_achievement_to_all("pioneer")
    print(f"成功给 {success_count} 个用户发放了先行者成就")
    
    # 验证发放结果
    all_achievements = await achievement_service.get_all_achievements()
    print(f"共有 {len(all_achievements)} 个用户")
    for user_id, achievements in all_achievements.items():
        has_pioneer = "pioneer" in achievements
        print(f"用户 {user_id}: {'已获得先行者成就' if has_pioneer else '未获得先行者成就'}")

if __name__ == "__main__":
    asyncio.run(main())
