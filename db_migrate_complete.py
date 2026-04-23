"""
完整数据库迁移脚本
用于修复所有缺失的数据库表和字段
基于现有数据库结构进行增量更新
"""
import aiosqlite
import os
from astrbot.api import logger


async def migrate_database(db_path: str):
    """
    执行完整数据库迁移
    安全地添加所有缺失的表和字段，不影响现有数据
    """
    if not os.path.exists(db_path):
        logger.info(f"【数据库迁移】数据库文件不存在，跳过迁移: {db_path}")
        return

    async with aiosqlite.connect(db_path) as db:
        # ==================== 1. 检查并创建缺失的表 ====================

        # 1.1 用户成就表 (user_achievements)
        await _create_table_if_not_exists(db, "user_achievements", """
            CREATE TABLE IF NOT EXISTS user_achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                achievement_id TEXT NOT NULL,
                obtain_time TEXT NOT NULL,
                UNIQUE(user_id, achievement_id)
            )
        """)

        # 1.2 成就加成表 (achievement_bonuses)
        await _create_table_if_not_exists(db, "achievement_bonuses", """
            CREATE TABLE IF NOT EXISTS achievement_bonuses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                achievement_id TEXT NOT NULL,
                bonus_type TEXT NOT NULL,
                bonus_value INTEGER DEFAULT 0,
                UNIQUE(user_id, achievement_id, bonus_type)
            )
        """)

        # 1.3 自定义成就表 (custom_achievements)
        await _create_table_if_not_exists(db, "custom_achievements", """
            CREATE TABLE IF NOT EXISTS custom_achievements (
                achievement_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                desc TEXT NOT NULL,
                emoji TEXT DEFAULT '🏆',
                rarity TEXT DEFAULT 'blue'
            )
        """)

        # 1.4 公告表 (announcements)
        await _create_table_if_not_exists(db, "announcements", """
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                author_id TEXT NOT NULL,
                author_name TEXT,
                publish_time TEXT NOT NULL,
                is_broadcast INTEGER DEFAULT 0
            )
        """)

        # 1.5 插件配置表 (plugin_config)
        await _create_table_if_not_exists(db, "plugin_config", """
            CREATE TABLE IF NOT EXISTS plugin_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 1.6 塔罗牌表 (user_daily_tarot)
        await _create_table_if_not_exists(db, "user_daily_tarot", """
            CREATE TABLE IF NOT EXISTS user_daily_tarot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                date TEXT NOT NULL,
                card_name TEXT NOT NULL,
                effect_type TEXT,
                effect_value INTEGER DEFAULT 0,
                UNIQUE(user_id, date)
            )
        """)

        # ==================== 2. 检查并添加缺失的字段 ====================

        # 2.1 tax_pool 表 - 检查 bonus_claimed 字段
        await _add_column_if_not_exists(db, "tax_pool", "bonus_claimed", "INTEGER DEFAULT 0")

        # 2.2 users 表 - 检查可能缺失的字段
        await _add_column_if_not_exists(db, "users", "favor_value", "INTEGER DEFAULT 0")
        await _add_column_if_not_exists(db, "users", "consecutive_days", "INTEGER DEFAULT 0")
        await _add_column_if_not_exists(db, "users", "bank_last_date", "TEXT")

        # 2.3 stock_holdings 表 - 检查可能缺失的字段
        await _add_column_if_not_exists(db, "stock_holdings", "remaining", "REAL DEFAULT 0")
        await _add_column_if_not_exists(db, "stock_holdings", "last_dividend_date", "TEXT")

        # 2.4 user_work 表 - 检查可能缺失的字段
        await _add_column_if_not_exists(db, "user_work", "total_earned", "INTEGER DEFAULT 0")

        # 2.5 user_society 表 - 检查可能缺失的字段
        await _add_column_if_not_exists(db, "user_society", "join_time", "TEXT")
        await _add_column_if_not_exists(db, "user_society", "last_change_time", "TEXT")

        # 2.6 achievement_bonuses 表 - bonus_value 改为 REAL 支持浮点利率
        await _add_column_if_not_exists(db, "achievement_bonuses", "bonus_value", "REAL DEFAULT 0")

        # 2.7 user_daily_tarot 表 - 检查可能缺失的字段
        await _add_column_if_not_exists(db, "user_daily_tarot", "effect_type", "TEXT")
        await _add_column_if_not_exists(db, "user_daily_tarot", "effect_value", "INTEGER DEFAULT 0")

        await db.commit()
        logger.info("【数据库迁移】数据库迁移完成")


async def _create_table_if_not_exists(db, table_name: str, create_sql: str):
    """检查并创建表（如果不存在）"""
    try:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        if not await cursor.fetchone():
            await db.execute(create_sql)
            logger.info(f"【数据库迁移】创建表: {table_name}")
        else:
            logger.info(f"【数据库迁移】表已存在: {table_name}")
    except Exception as e:
        logger.error(f"【数据库迁移】创建表 {table_name} 时出错: {e}")


async def _add_column_if_not_exists(db, table_name: str, column_name: str, column_def: str):
    """检查并添加列（如果不存在）"""
    try:
        cursor = await db.execute(f"PRAGMA table_info({table_name})")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        if column_name not in column_names:
            await db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
            logger.info(f"【数据库迁移】表 {table_name} 添加列: {column_name}")
        else:
            logger.info(f"【数据库迁移】表 {table_name} 已存在列: {column_name}")
    except Exception as e:
        logger.error(f"【数据库迁移】添加列 {column_name} 到 {table_name} 时出错: {e}")


async def check_and_migrate(db_path: str):
    """检查并执行迁移"""
    try:
        await migrate_database(db_path)
    except Exception as e:
        logger.error(f"【数据库迁移】迁移失败: {e}")
        raise
