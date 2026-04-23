#!/usr/bin/env python3
"""
检查和修复现有数据库结构
添加缺失的表和字段，不删除任何现有数据
"""
import sqlite3
import os

DB_PATH = '/root/ai/astrbot/data/plugin_data/astrbot_plugin_monningsignin/signin.db'


def check_and_fix_database():
    """检查并修复数据库"""
    if not os.path.exists(DB_PATH):
        print(f"数据库不存在: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("=== 开始检查数据库结构 ===\n")

    # 获取现有表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cursor.fetchall()}
    print(f"现有表: {', '.join(sorted(existing_tables))}\n")

    # 1. 检查并创建缺失的表
    tables_to_create = {
        'user_achievements': """
            CREATE TABLE IF NOT EXISTS user_achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                achievement_id TEXT NOT NULL,
                obtain_time TEXT NOT NULL,
                UNIQUE(user_id, achievement_id)
            )
        """,
        'achievement_bonuses': """
            CREATE TABLE IF NOT EXISTS achievement_bonuses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                achievement_id TEXT NOT NULL,
                bonus_type TEXT NOT NULL,
                bonus_value INTEGER DEFAULT 0,
                UNIQUE(user_id, achievement_id, bonus_type)
            )
        """,
        'custom_achievements': """
            CREATE TABLE IF NOT EXISTS custom_achievements (
                achievement_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                desc TEXT NOT NULL,
                emoji TEXT DEFAULT '🏆',
                rarity TEXT DEFAULT 'blue'
            )
        """,
        'announcements': """
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                author_id TEXT NOT NULL,
                author_name TEXT,
                publish_time TEXT NOT NULL,
                is_broadcast INTEGER DEFAULT 0
            )
        """,
        'plugin_config': """
            CREATE TABLE IF NOT EXISTS plugin_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
    }

    for table_name, create_sql in tables_to_create.items():
        if table_name not in existing_tables:
            print(f"创建表: {table_name}")
            cursor.execute(create_sql)
        else:
            print(f"表已存在: {table_name}")

    conn.commit()

    # 2. 检查并添加缺失的字段
    print("\n=== 检查表字段 ===\n")

    # 检查 tax_pool 表
    cursor.execute("PRAGMA table_info(tax_pool)")
    tax_pool_columns = {row[1] for row in cursor.fetchall()}
    print(f"tax_pool 现有字段: {', '.join(sorted(tax_pool_columns))}")

    if 'bonus_claimed' not in tax_pool_columns:
        print("  -> 添加字段: bonus_claimed")
        cursor.execute("ALTER TABLE tax_pool ADD COLUMN bonus_claimed INTEGER DEFAULT 0")

    # 检查 users 表
    cursor.execute("PRAGMA table_info(users)")
    users_columns = {row[1] for row in cursor.fetchall()}
    print(f"\nusers 现有字段: {', '.join(sorted(users_columns))}")

    users_new_columns = {
        'favor_value': 'INTEGER DEFAULT 0',
        'consecutive_days': 'INTEGER DEFAULT 0',
        'bank_last_date': 'TEXT'
    }
    for col_name, col_type in users_new_columns.items():
        if col_name not in users_columns:
            print(f"  -> 添加字段: {col_name}")
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")

    # 检查 stock_holdings 表
    if 'stock_holdings' in existing_tables:
        cursor.execute("PRAGMA table_info(stock_holdings)")
        stock_columns = {row[1] for row in cursor.fetchall()}
        print(f"\nstock_holdings 现有字段: {', '.join(sorted(stock_columns))}")

        stock_new_columns = {
            'remaining': 'REAL DEFAULT 0',
            'last_dividend_date': 'TEXT'
        }
        for col_name, col_type in stock_new_columns.items():
            if col_name not in stock_columns:
                print(f"  -> 添加字段: {col_name}")
                cursor.execute(f"ALTER TABLE stock_holdings ADD COLUMN {col_name} {col_type}")

    # 检查 user_work 表
    if 'user_work' in existing_tables:
        cursor.execute("PRAGMA table_info(user_work)")
        work_columns = {row[1] for row in cursor.fetchall()}
        print(f"\nuser_work 现有字段: {', '.join(sorted(work_columns))}")

        if 'total_earned' not in work_columns:
            print("  -> 添加字段: total_earned")
            cursor.execute("ALTER TABLE user_work ADD COLUMN total_earned INTEGER DEFAULT 0")

    # 检查 user_daily_tarot 表
    if 'user_daily_tarot' in existing_tables:
        cursor.execute("PRAGMA table_info(user_daily_tarot)")
        tarot_columns = {row[1] for row in cursor.fetchall()}
        print(f"\nuser_daily_tarot 现有字段: {', '.join(sorted(tarot_columns))}")

        tarot_new_columns = {
            'effect_type': 'TEXT',
            'effect_value': 'INTEGER DEFAULT 0'
        }
        for col_name, col_type in tarot_new_columns.items():
            if col_name not in tarot_columns:
                print(f"  -> 添加字段: {col_name}")
                cursor.execute(f"ALTER TABLE user_daily_tarot ADD COLUMN {col_name} {col_type}")

    conn.commit()
    conn.close()

    print("\n=== 数据库检查和修复完成 ===")


if __name__ == "__main__":
    check_and_fix_database()
