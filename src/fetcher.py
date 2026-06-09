# src/fetcher.py
# 支持代理 fallback 的源拉取模块，缓存优先

import asyncio
import aiohttp
from datetime import datetime, timedelta
from src.config import HEADERS, TIMEOUT, RETRY_MAX_ATTEMPTS, RETRY_BACKOFF_FACTOR, RETRY_MAX_WAIT, ENABLE_RETRY
from src.database import get_db_cache
from src.logger import logger
from src.proxy_utils import fetch_with_proxy_fallback

class FetchError(Exception):
    pass

async def fetch_url_with_metadata(session: aiohttp.ClientSession, url: str, db):
    """
    拉取单个源，优先使用数据库缓存（24小时内有效），否则通过代理 fallback 拉取。
    """
    # 1. 尝试从数据库获取有效缓存
    if db and db._conn:
        cursor = await db._conn.execute(
            "SELECT content, updated_at FROM channel_cache_raw WHERE url = ?",
            (url,)
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row:
            content, updated_at_str = row
            if updated_at_str:
                try:
                    updated_at = datetime.fromisoformat(updated_at_str)
                    if datetime.now() - updated_at < timedelta(hours=24):
                        logger.debug(f"📦 使用缓存: {url}")
                        return content
                except:
                    pass

    # 2. 缓存不存在或过期，执行网络拉取（带代理 fallback）
    logger.info(f"🔄 拉取源: {url}")
    attempt = 0
    while True:
        attempt += 1
        try:
            content, used_proxy = await fetch_with_proxy_fallback(session, url)
            if content is None:
                raise FetchError(f"所有代理尝试失败: {url}")

            # 成功拉取，保存到数据库
            if db and db._conn:
                await db._conn.execute(
                    """INSERT OR REPLACE INTO channel_cache_raw 
                       (url, content, updated_at) VALUES (?, ?, ?)""",
                    (url, content, datetime.now().isoformat())
                )
                await db._conn.commit()
            return content
        except Exception as e:
            if not ENABLE_RETRY or attempt >= RETRY_MAX_ATTEMPTS:
                raise FetchError(str(e))
            wait_time = min(RETRY_BACKOFF_FACTOR ** (attempt - 1), RETRY_MAX_WAIT)
            logger.warning(f"  重试 {url} ({attempt}/{RETRY_MAX_ATTEMPTS})，等待 {wait_time}s")
            await asyncio.sleep(wait_time)

async def fetch_all_sources_incremental(sources: list, db) -> dict:
    """并发拉取所有源，返回 {url: content} 字典"""
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_url_with_metadata(session, url, db) for url in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        output = {}
        for url, res in zip(sources, results):
            if isinstance(res, Exception):
                logger.warning(f"⚠️ 拉取失败 {url}: {res}")
                # 尝试从数据库获取旧缓存（即使过期也作为兜底）
                if db and db._conn:
                    cursor = await db._conn.execute(
                        "SELECT content FROM channel_cache_raw WHERE url = ?",
                        (url,)
                    )
                    row = await cursor.fetchone()
                    await cursor.close()
                    if row:
                        output[url] = row[0]
                        logger.info(f"📦 使用数据库旧缓存: {url}")
                    else:
                        output[url] = None
                else:
                    output[url] = None
            else:
                output[url] = res
        return output
