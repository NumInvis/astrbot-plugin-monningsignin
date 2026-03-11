"""
公告服务模块
提供系统公告发布、查询和广播功能
"""
import aiosqlite
from datetime import datetime
from typing import List, Dict, Optional


class AnnouncementService:
    """公告服务类"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def init_table(self):
        """初始化公告表"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
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
            await db.commit()
    
    async def publish_announcement(self, title: str, content: str, 
                                   author_id: str, author_name: str = "管理员") -> Dict:
        """发布公告"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor = await db.execute(
                    """INSERT INTO announcements (title, content, author_id, author_name, publish_time, is_broadcast)
                       VALUES (?, ?, ?, ?, ?, 1)""",
                    (title, content, author_id, author_name, now)
                )
                await db.commit()
                announcement_id = cursor.lastrowid
                
                return {
                    "success": True,
                    "id": announcement_id,
                    "title": title,
                    "content": content,
                    "publish_time": now
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"发布公告失败: {str(e)}"
            }
    
    async def get_announcements(self, limit: int = 10) -> List[Dict]:
        """获取历史公告列表"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT id, title, content, author_name, publish_time 
                   FROM announcements 
                   ORDER BY publish_time DESC 
                   LIMIT ?""",
                (limit,)
            )
            rows = await cursor.fetchall()
            
            announcements = []
            for row in rows:
                announcements.append({
                    "id": row[0],
                    "title": row[1],
                    "content": row[2],
                    "author_name": row[3],
                    "publish_time": row[4]
                })
            
            return announcements
    
    async def get_latest_announcement(self) -> Optional[Dict]:
        """获取最新公告"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT id, title, content, author_name, publish_time 
                   FROM announcements 
                   ORDER BY publish_time DESC 
                   LIMIT 1"""
            )
            row = await cursor.fetchone()
            
            if row:
                return {
                    "id": row[0],
                    "title": row[1],
                    "content": row[2],
                    "author_name": row[3],
                    "publish_time": row[4]
                }
            return None
    
    async def delete_announcement(self, announcement_id: int) -> bool:
        """删除公告"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "DELETE FROM announcements WHERE id = ?",
                    (announcement_id,)
                )
                await db.commit()
                return True
        except:
            return False
