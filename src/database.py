# src/database.py
# 异步 SQLite 数据库缓存模块，统一管理原始源缓存和频道测速缓存

import json
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from pathlib import Path

from src.config import DATABASE_ENABLE, DATABASE_PATH, DATABASE_TABLE, CACHE_EXPIRY_SECONDS

class DatabaseCache:
    """异步数据库缓存管理器（单例）"""
    
    _instance = None
    _conn = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def init(self):
        if not DATABASE_ENABLE:
            print("⚙️ 数据库缓存未启用")
            return
        try:
            # 确保数据库目录存在
            DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._conn = await aiosqlite.connect(str(DATABASE_PATH))
            await self._create_tables()
            print(f"✅ 数据库缓存已启用: {DATABASE_PATH}")
        except Exception as e:
            print(f"⚠️ 数据库初始化失败: {e}，缓存功能禁用")
            self._conn = None
    
    async def _create_tables(self):
        """创建所有数据表"""
        # 原始源缓存表（增加 hash 字段用于源变更检测）
        await self._conn.execute(f'''
            CREATE TABLE IF NOT EXISTS {DATABASE_TABLE}_raw (
                url TEXT PRIMARY KEY,
                content TEXT,
                etag TEXT,
                last_modified TEXT,
                hash TEXT,
                updated_at TIMESTAMP
            )
        ''')
        
        # 频道测速结果缓存表
        await self._conn.execute(f'''
            CREATE TABLE IF NOT EXISTS {DATABASE_TABLE}_speed (
                channel_key TEXT PRIMARY KEY,
                name TEXT,
                url TEXT,
                latency INTEGER,
                video_codec TEXT,
                ip_info TEXT,
                updated_at TIMESTAMP
            )
        ''')
        
        # 元数据表（存储最后更新时间等）
        await self._conn.execute('''
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        # 创建索引
        await self._conn.execute(f'''
            CREATE INDEX IF NOT EXISTS idx_raw_updated 
            ON {DATABASE_TABLE}_raw (updated_at)
        ''')
        await self._conn.execute(f'''
            CREATE INDEX IF NOT EXISTS idx_speed_updated 
            ON {DATABASE_TABLE}_speed (updated_at)
        ''')
        
        await self._conn.commit()
    
    # ==================== 原始源缓存方法 ====================
    
    async def get_raw_source(self, url: str, max_age_hours: int = 24) -> Optional[str]:
        """获取缓存的原始源内容（如果未过期）"""
        if not self._conn:
            return None
        try:
            cursor = await self._conn.execute(
                f'SELECT content, updated_at FROM {DATABASE_TABLE}_raw WHERE url = ?',
                (url,)
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row:
                content, updated_at = row
                if datetime.now() - datetime.fromisoformat(updated_at) < timedelta(hours=max_age_hours):
                    return content
        except Exception as e:
            print(f"⚠️ 读取缓存失败 {url}: {e}")
        return None
    
    async def set_raw_source(self, url: str, content: str, etag: str = "", last_modified: str = ""):
        """保存原始源内容到缓存"""
        if not self._conn:
            return
        try:
            await self._conn.execute(
                f'''INSERT OR REPLACE INTO {DATABASE_TABLE}_raw 
                    (url, content, etag, last_modified, updated_at) 
                    VALUES (?, ?, ?, ?, ?)''',
                (url, content, etag, last_modified, datetime.now().isoformat())
            )
            await self._conn.commit()
        except Exception as e:
            print(f"⚠️ 保存缓存失败 {url}: {e}")
    
    async def get_source_hash(self, url: str) -> Optional[str]:
        """获取源内容的哈希值（用于检测变更）"""
        if not self._conn:
            return None
        try:
            cursor = await self._conn.execute(
                f'SELECT hash FROM {DATABASE_TABLE}_raw WHERE url = ?',
                (url,)
            )
            row = await cursor.fetchone()
            await cursor.close()
            return row[0] if row else None
        except Exception as e:
            print(f"⚠️ 获取源哈希失败 {url}: {e}")
            return None
    
    async def set_source_hash(self, url: str, hash_value: str):
        """设置源内容的哈希值"""
        if not self._conn:
            return
        try:
            await self._conn.execute(
                f'UPDATE {DATABASE_TABLE}_raw SET hash = ? WHERE url = ?',
                (hash_value, url)
            )
            await self._conn.commit()
        except Exception as e:
            print(f"⚠️ 保存源哈希失败 {url}: {e}")
    
    # ==================== 频道测速缓存方法 ====================
    
    async def get_speed_result(self, channel_key: str, max_age_hours: int = 6) -> Optional[Dict]:
        """获取缓存的测速结果"""
        if not self._conn:
            return None
        try:
            cursor = await self._conn.execute(
                f'SELECT name, url, latency, video_codec, ip_info, updated_at FROM {DATABASE_TABLE}_speed WHERE channel_key = ?',
                (channel_key,)
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row:
                name, url, latency, video_codec, ip_info_json, updated_at = row
                if datetime.now() - datetime.fromisoformat(updated_at) < timedelta(hours=max_age_hours):
                    return {
                        "name": name,
                        "url": url,
                        "latency": latency,
                        "video_codec": video_codec,
                        "ip_info": json.loads(ip_info_json) if ip_info_json else None
                    }
        except Exception as e:
            print(f"⚠️ 读取测速缓存失败: {e}")
        return None
    
    async def set_speed_result(self, channel_key: str, channel_data: Dict):
        """保存测速结果到缓存"""
        if not self._conn:
            return
        try:
            await self._conn.execute(
                f'''INSERT OR REPLACE INTO {DATABASE_TABLE}_speed 
                    (channel_key, name, url, latency, video_codec, ip_info, updated_at) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (
                    channel_key,
                    channel_data.get("name", ""),
                    channel_data.get("url", ""),
                    channel_data.get("latency", 9999),
                    channel_data.get("video_codec", ""),
                    json.dumps(channel_data.get("ip_info")) if channel_data.get("ip_info") else None,
                    datetime.now().isoformat()
                )
            )
            await self._conn.commit()
        except Exception as e:
            print(f"⚠️ 保存测速缓存失败: {e}")
    
    # ==================== 元数据管理方法 ====================
    
    async def get_last_update_time(self) -> Optional[int]:
        """获取最后更新时间戳"""
        if not self._conn:
            return None
        cursor = await self._conn.execute("SELECT value FROM metadata WHERE key = 'last_update'")
        row = await cursor.fetchone()
        await cursor.close()
        if row:
            return int(row[0])
        return None
    
    async def set_last_update_time(self, timestamp: int = None):
        """设置最后更新时间戳"""
        if timestamp is None:
            timestamp = int(datetime.now().timestamp())
        if not self._conn:
            return
        await self._conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            ("last_update", str(timestamp))
        )
        await self._conn.commit()
    
    async def is_stale(self, expiry_seconds: int = None) -> bool:
        """检查缓存是否过期"""
        if expiry_seconds is None:
            expiry_seconds = CACHE_EXPIRY_SECONDS
        last = await self.get_last_update_time()
        if last is None:
            return True
        return (int(datetime.now().timestamp()) - last) > expiry_seconds
    
    # ==================== 统计和清理方法 ====================
    
    async def get_stats(self) -> Dict:
        """获取缓存统计信息"""
        if not self._conn:
            return {"enabled": False}
        try:
            raw_cursor = await self._conn.execute(f'SELECT COUNT(*) FROM {DATABASE_TABLE}_raw')
            raw_count = (await raw_cursor.fetchone())[0]
            await raw_cursor.close()
            
            speed_cursor = await self._conn.execute(f'SELECT COUNT(*) FROM {DATABASE_TABLE}_speed')
            speed_count = (await speed_cursor.fetchone())[0]
            await speed_cursor.close()
            
            return {
                "enabled": True,
                "raw_sources": raw_count,
                "speed_results": speed_count
            }
        except Exception:
            return {"enabled": True, "raw_sources": 0, "speed_results": 0}
    
    async def clear_expired(self, max_age_days: int = 7):
        """清理过期缓存"""
        if not self._conn:
            return
        try:
            expire_time = (datetime.now() - timedelta(days=max_age_days)).isoformat()
            await self._conn.execute(
                f'DELETE FROM {DATABASE_TABLE}_raw WHERE updated_at < ?',
                (expire_time,)
            )
            await self._conn.execute(
                f'DELETE FROM {DATABASE_TABLE}_speed WHERE updated_at < ?',
                (expire_time,)
            )
            await self._conn.commit()
            print(f"🧹 已清理 {max_age_days} 天前的过期缓存")
        except Exception as e:
            print(f"⚠️ 清理过期缓存失败: {e}")
    
    async def close(self):
        """关闭数据库连接"""
        if self._conn:
            await self._conn.close()
            self._conn = None

# 全局单例
_db_cache = None

async def get_db_cache() -> DatabaseCache:
    """获取数据库缓存单例"""
    global _db_cache
    if _db_cache is None:
        _db_cache = DatabaseCache()
        await _db_cache.init()
    return _db_cache

def channel_key(name: str, url: str) -> str:
    """生成频道的唯一键"""
    import hashlib
    return hashlib.md5(f"{name}|{url}".encode()).hexdigest()
