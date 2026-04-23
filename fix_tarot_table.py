"""
修复塔罗牌表结构
SQLite 不能给已存在的表添加 NOT NULL 列，需要使用重建表的方式
"""
import aiosqlite
import os
from astrbot.api import logger


async def fix_tarot_table(db_path: str):
    """修复塔罗牌表结构"""
    if not os.path.exists(db_path):
        logger.info(f"【修复】数据库文件不存在，跳过: {db_path}")
        return

    async with aiosqlite.connect(db_path) as db:
        # 检查表是否存在
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_daily_tarot'"
        )
        table_exists = await cursor.fetchone()

        if not table_exists:
            # 表不存在，创建新表
            logger.info("【修复】创建 user_daily_tarot 表")
            await db.execute("""
                CREATE TABLE user_daily_tarot (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    card_name TEXT NOT NULL,
                    effect_type TEXT,
                    effect_value INTEGER DEFAULT 0,
                    UNIQUE(user_id, date)
                )
            """)
            await db.commit()
            logger.info("【修复】user_daily_tarot 表创建完成")
        else:
            # 表存在，检查字段
            cursor = await db.execute("PRAGMA table_info(user_daily_tarot)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            logger.info(f"【修复】user_daily_tarot 现有字段: {column_names}")

            # 检查是否缺少 card_name 字段
            if 'card_name' not in column_names:
                logger.info("【修复】缺少 card_name 字段，需要重建表")
                await _rebuild_tarot_table(db)
            else:
                # 只添加可选字段（这些可以有默认值或为NULL）
                optional_columns = {
                    'effect_type': 'TEXT',
                    'effect_value': 'INTEGER DEFAULT 0'
                }

                for col_name, col_type in optional_columns.items():
                    if col_name not in column_names:
                        logger.info(f"【修复】添加缺失字段: {col_name}")
                        await db.execute(f"ALTER TABLE user_daily_tarot ADD COLUMN {col_name} {col_type}")

                await db.commit()
                logger.info("【修复】user_daily_tarot 表修复完成")


async def _rebuild_tarot_table(db):
    """
    重建塔罗牌表以添加 NOT NULL 字段
    SQLite 不支持直接添加 NOT NULL 列，需要：
    1. 创建新表
    2. 迁移数据
    3. 删除旧表
    4. 重命名新表
    """
    logger.info("【修复】开始重建 user_daily_tarot 表")

    # 1. 创建新表（带完整字段）
    await db.execute("""
        CREATE TABLE user_daily_tarot_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            date TEXT NOT NULL,
            card_name TEXT NOT NULL DEFAULT '愚者',
            effect_type TEXT,
            effect_value INTEGER DEFAULT 0,
            UNIQUE(user_id, date)
        )
    """)

    # 2. 检查旧表有哪些字段
    cursor = await db.execute("PRAGMA table_info(user_daily_tarot)")
    old_columns = await cursor.fetchall()
    old_column_names = [col[1] for col in old_columns]
    logger.info(f"【修复】旧表字段: {old_column_names}")

    # 3. 尝试迁移数据（如果旧表有数据）
    try:
        # 获取旧表数据
        cursor = await db.execute("SELECT * FROM user_daily_tarot")
        rows = await cursor.fetchall()

        if rows:
            logger.info(f"【修复】迁移 {len(rows)} 条数据")
            for row in rows:
                # 根据旧表字段构建插入语句
                # row 是一个元组，对应旧表的列
                # 我们需要映射到新表的列
                user_id = row[1] if len(row) > 1 else ''
                date = row[2] if len(row) > 2 else ''

                # 插入新表，card_name 使用默认值
                await db.execute("""
                    INSERT INTO user_daily_tarot_new (user_id, date, card_name, effect_type, effect_value)
                    VALUES (?, ?, '愚者', '', 0)
                """, (user_id, date))

        await db.commit()
        logger.info("【修复】数据迁移完成")
    except Exception as e:
        logger.warning(f"【修复】数据迁移失败（可能旧表为空或结构不同）: {e}")

    # 4. 删除旧表
    await db.execute("DROP TABLE user_daily_tarot")
    logger.info("【修复】旧表已删除")

    # 5. 重命名新表
    await db.execute("ALTER TABLE user_daily_tarot_new RENAME TO user_daily_tarot")
    await db.commit()
    logger.info("【修复】表重建完成")


async def check_and_fix_tarot(db_path: str):
    """检查并修复塔罗牌表"""
    try:
        await fix_tarot_table(db_path)
    except Exception as e:
        logger.error(f"【修复】修复塔罗牌表失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise
