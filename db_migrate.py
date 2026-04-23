"""
数据库迁移脚本
用于修复数据库表结构缺失的列
"""
import aiosqlite
import os
from astrbot.api import logger


async def migrate_database(db_path: str):
    """
    执行数据库迁移
    安全地添加缺失的列，不影响现有数据
    """
    if not os.path.exists(db_path):
        logger.info(f"【数据库迁移】数据库文件不存在，跳过迁移: {db_path}")
        return

    async with aiosqlite.connect(db_path) as db:
        # 检查tax_pool表是否存在bonus_claimed列
        try:
            cursor = await db.execute("PRAGMA table_info(tax_pool)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

            if 'bonus_claimed' not in column_names:
                logger.info("【数据库迁移】tax_pool表缺少bonus_claimed列，正在添加...")
                await db.execute(
                    "ALTER TABLE tax_pool ADD COLUMN bonus_claimed INTEGER DEFAULT 0"
                )
                await db.commit()
                logger.info("【数据库迁移】成功添加bonus_claimed列")
            else:
                logger.info("【数据库迁移】tax_pool表已存在bonus_claimed列，跳过")

        except Exception as e:
            logger.error(f"【数据库迁移】检查tax_pool表时出错: {e}")

        # 检查其他可能缺失的列...
        # 这里可以添加其他表的迁移检查

    logger.info("【数据库迁移】数据库迁移完成")


async def check_and_migrate(db_path: str):
    """检查并执行迁移"""
    try:
        await migrate_database(db_path)
    except Exception as e:
        logger.error(f"【数据库迁移】迁移失败: {e}")
        raise
