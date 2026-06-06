#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3
import json
import time
import os
from typing import List, Dict, Optional, Any

DB_PATH = "iptv_cache.db"
DATA_EXPIRY_SECONDS = 7 * 24 * 3600  # 7天有效期
CONSECUTIVE_FAILURE_THRESHOLD = 3

class IPTVDatabase:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    group_title TEXT,
                    tvg_id TEXT,
                    tvg_logo TEXT,
                    latency INTEGER DEFAULT 9999,
                    video_codec TEXT,
                    ip_info TEXT,
                    last_verified INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    UNIQUE(name, url)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            conn.commit()
            print("✅ 数据库初始化完成（增量更新模式）")

    def get_last_update_time(self) -> Optional[int]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM metadata WHERE key = 'last_update'")
            row = cursor.fetchone()
            if row:
                return int(row[0])
        return None

    def set_last_update_time(self, timestamp: int = None):
        if timestamp is None:
            timestamp = int(time.time())
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                           ("last_update", str(timestamp)))
            conn.commit()

    def get_last_full_update_time(self) -> Optional[int]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM metadata WHERE key = 'last_full_update'")
            row = cursor.fetchone()
            if row:
                return int(row[0])
        return None

    def set_last_full_update_time(self, timestamp: int = None):
        if timestamp is None:
            timestamp = int(time.time())
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                           ("last_full_update", str(timestamp)))
            conn.commit()

    def save_channels(self, channels: List[Dict[str, Any]]):
        now = int(time.time())
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for ch in channels:
                name = ch.get("name", "")
                url = ch.get("url", "")
                if not url:
                    continue
                group_title = ch.get("group_title", "")
                tvg_id = ch.get("id", "")
                tvg_logo = ch.get("logo", "")
                latency = ch.get("latency", 9999)
                video_codec = ch.get("video_codec", "")
                ip_info = json.dumps(ch.get("ip_info")) if ch.get("ip_info") else None
                cursor.execute('''
                    INSERT OR REPLACE INTO channels
                    (name, url, group_title, tvg_id, tvg_logo, latency, video_codec, ip_info, last_verified, failure_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                ''', (name, url, group_title, tvg_id, tvg_logo, latency, video_codec, ip_info, now))
            conn.commit()
            print(f"💾 数据库已保存 {len(channels)} 条记录")

    def load_valid_channels(self, skip_old: bool = True) -> List[Dict[str, Any]]:
        now = int(time.time())
        expiry_threshold = now - DATA_EXPIRY_SECONDS
        channels = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if skip_old:
                cursor.execute('''
                    SELECT * FROM channels
                    WHERE last_verified >= ?
                    ORDER BY name, latency
                ''', (expiry_threshold,))
            else:
                cursor.execute('SELECT * FROM channels ORDER BY name, latency')
            for row in cursor.fetchall():
                ch = dict(row)
                if ch.get("ip_info"):
                    ch["ip_info"] = json.loads(ch["ip_info"])
                else:
                    ch["ip_info"] = None
                channels.append(ch)
        return channels

    def mark_failed(self, url: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE channels SET failure_count = failure_count + 1 WHERE url = ?", (url,))
            conn.commit()
            cursor.execute("SELECT failure_count FROM channels WHERE url = ?", (url,))
            row = cursor.fetchone()
            return row[0] if row else 0

    def is_stale(self) -> bool:
        last_update = self.get_last_update_time()
        if last_update is None:
            return True
        return (int(time.time()) - last_update) > DATA_EXPIRY_SECONDS

    def get_stats(self) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM channels")
            total = cursor.fetchone()[0]

            now = int(time.time())
            expiry = now - DATA_EXPIRY_SECONDS
            cursor.execute("SELECT COUNT(*) FROM channels WHERE last_verified >= ?", (expiry,))
            recent_valid = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM channels WHERE failure_count >= ?", (CONSECUTIVE_FAILURE_THRESHOLD,))
            failed = cursor.fetchone()[0]

            active = total - failed
            return {
                "total_channels": total,
                "active": active,
                "failed": failed,
                "recent_valid": recent_valid
            }
