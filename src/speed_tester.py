# src/speed_tester.py
# 轻量级 HTTP 头探测（快速测速），支持缓存

import asyncio
import aiohttp
import time
from src.config import HEADERS, TIMEOUT, MAX_WORKERS, ENABLE_IP_RESOLVE
from src.ip_resolver import get_resolver
from src.database import get_db_cache, channel_key

async def probe_channel(session: aiohttp.ClientSession, channel: dict) -> tuple:
    """异步探测单个频道，返回 (channel_dict, latency, success, ip_info)"""
    url = channel["url"]
    try:
        start = time.time()
        async with session.head(url, timeout=TIMEOUT, allow_redirects=True, headers=HEADERS) as resp:
            latency = int((time.time() - start) * 1000)
            if resp.status == 200:
                ip_info = None
                if ENABLE_IP_RESOLVE:
                    resolver = get_resolver()
                    if resolver.is_available:
                        ip_info = resolver.resolve_channel_ip(channel)  # 需要实现接受 dict
                return channel, latency, True, ip_info
            else:
                return channel, latency, False, None
    except Exception:
        return channel, 0, False, None

async def test_channels_concurrent(channels_dict: dict) -> list:
    """并发测速，返回有效的频道列表（按延迟排序），使用数据库缓存减少重复探测"""
    channels = list(channels_dict.values())
    db = await get_db_cache()
    
    # 先尝试从缓存读取结果
    cached_results = []
    to_probe = []
    for ch in channels:
        key = channel_key(ch["name"], ch["url"])
        cached = await db.get_speed_result(key)
        if cached and cached["latency"] < 9999:
            # 缓存有效
            ch["latency"] = cached["latency"]
            ch["video_codec"] = cached.get("video_codec", "")
            ch["ip_info"] = cached.get("ip_info")
            cached_results.append(ch)
        else:
            to_probe.append(ch)
    
    print(f"⚡ 测速: {len(to_probe)} 个新频道需探测，{len(cached_results)} 个来自缓存")
    
    valid = cached_results.copy()
    if to_probe:
        semaphore = asyncio.Semaphore(MAX_WORKERS)
        async def bounded_probe(session, ch):
            async with semaphore:
                return await probe_channel(session, ch)
        
        connector = aiohttp.TCPConnector(limit=MAX_WORKERS, limit_per_host=5)
        timeout_config = aiohttp.ClientTimeout(total=TIMEOUT + 5)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout_config) as session:
            tasks = [bounded_probe(session, ch) for ch in to_probe]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for res in results:
            if isinstance(res, Exception):
                continue
            ch, latency, ok, ip_info = res
            if ok:
                ch["latency"] = latency
                if ip_info:
                    ch["ip_info"] = ip_info
                else:
                    ch["ip_info"] = None
                valid.append(ch)
                # 保存到缓存
                key = channel_key(ch["name"], ch["url"])
                await db.set_speed_result(key, ch)
    
    valid.sort(key=lambda x: x.get("latency", 9999))
    print(f"✅ 测速完成，有效频道 {len(valid)}/{len(channels)}")
    return valid
