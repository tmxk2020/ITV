import asyncio
import aiohttp
import time
from src.config import HEADERS, TIMEOUT, MAX_WORKERS, ENABLE_IP_RESOLVE
from src.ip_resolver import get_resolver

REAL_TIMEOUT = 15

async def probe_channel(session, channel):
    url = channel.url
    try:
        start = time.time()
        async with session.get(url, timeout=REAL_TIMEOUT, headers=HEADERS, allow_redirects=True) as resp:
            latency = int((time.time() - start) * 1000)
            if resp.status in (200, 206, 302, 301, 303, 307, 308):
                # 可选：检查 content-type
                content_type = resp.headers.get('Content-Type', '')
                if 'video' in content_type or 'mpeg' in content_type or 'octet-stream' in content_type or resp.status == 200:
                    ip_info = None
                    if ENABLE_IP_RESOLVE:
                        resolver = get_resolver()
                        if resolver.is_available:
                            ip_info = resolver.resolve_channel_ip(channel)
                    return channel, latency, True, ip_info
                else:
                    # 状态码200但内容不是视频，也允许通过（保守）
                    ip_info = None
                    if ENABLE_IP_RESOLVE:
                        resolver = get_resolver()
                        if resolver.is_available:
                            ip_info = resolver.resolve_channel_ip(channel)
                    return channel, latency, True, ip_info
            else:
                return channel, 0, False, None
    except asyncio.TimeoutError:
        return channel, 0, False, None
    except Exception as e:
        # 打印前10个错误帮助调试
        if not hasattr(probe_channel, 'error_count'):
            probe_channel.error_count = 0
        if probe_channel.error_count < 10:
            print(f"❌ 请求错误 {url[:80]}: {type(e).__name__}: {e}")
            probe_channel.error_count += 1
        return channel, 0, False, None

async def test_channels_concurrent(channels_dict: dict) -> list:
    channels = list(channels_dict.values())
    print(f"⚡ 开始测速，共 {len(channels)} 个频道，并发数 {MAX_WORKERS}，超时 {REAL_TIMEOUT}s...")
    
    connector = aiohttp.TCPConnector(limit=MAX_WORKERS, limit_per_host=5)
    timeout = aiohttp.ClientTimeout(total=REAL_TIMEOUT, connect=REAL_TIMEOUT//2)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=HEADERS) as session:
        semaphore = asyncio.Semaphore(MAX_WORKERS)
        async def bounded_probe(ch):
            async with semaphore:
                return await probe_channel(session, ch)
        
        tasks = [bounded_probe(ch) for ch in channels]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    valid = []
    for res in results:
        if isinstance(res, Exception):
            continue
        ch, lat, ok, ip = res
        if ok:
            ch.latency = lat
            ch.ip_info = ip
            valid.append(ch)
    
    print(f"✅ 测速完成，有效频道 {len(valid)}/{len(channels)}")
    if len(valid) == 0:
        print("⚠️ 请检查网络连接或目标源是否可访问。可能是 User-Agent 被屏蔽，尝试更换：", HEADERS.get('User-Agent'))
    return valid
