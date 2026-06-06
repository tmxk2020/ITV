# 轻量级 HTTP 头探测（快速测速，增加容错）
import asyncio
import aiohttp
import time
import random
from src.config import HEADERS, TIMEOUT, MAX_WORKERS, ENABLE_IP_RESOLVE
from src.ip_resolver import get_resolver

# 备用 User-Agent 列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
]

async def probe_channel(session, channel, retry_count=2):
    """异步探测单个频道，支持重试"""
    url = channel.url
    # 跳过非 http/https 协议
    if not url.startswith(('http://', 'https://')):
        # 非 HTTP 协议（rtmp/rtsp）直接视为有效（后续 ffmpeg 验证）
        latency = 0
        return channel, latency, True, None

    for attempt in range(retry_count + 1):
        try:
            # 每次尝试使用不同的 User-Agent
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            start = time.time()
            # 使用 GET 而非 HEAD，部分服务器不支持 HEAD 请求
            async with session.get(url, timeout=TIMEOUT, allow_redirects=True, headers=headers) as resp:
                latency = int((time.time() - start) * 1000)
                # 200 或 206（部分内容）都认为有效
                if resp.status in (200, 206):
                    ip_info = None
                    if ENABLE_IP_RESOLVE:
                        resolver = get_resolver()
                        if resolver.is_available:
                            ip_info = resolver.resolve_channel_ip(channel)
                    return channel, latency, True, ip_info
                else:
                    # 非成功状态码，等待后重试
                    if attempt < retry_count:
                        await asyncio.sleep(0.5)
                        continue
                    return channel, latency, False, None
        except asyncio.TimeoutError:
            if attempt < retry_count:
                await asyncio.sleep(0.5)
                continue
            return channel, 0, False, None
        except Exception:
            if attempt < retry_count:
                await asyncio.sleep(0.5)
                continue
            return channel, 0, False, None
    return channel, 0, False, None

async def test_channels_concurrent(channels_dict: dict) -> list:
    """并发测速，返回有效的频道列表（按延迟排序）"""
    channels = list(channels_dict.values())
    print(f"⚡ 开始测速，共 {len(channels)} 个频道，并发数 {MAX_WORKERS}，超时 {TIMEOUT}s...")
    
    semaphore = asyncio.Semaphore(MAX_WORKERS)
    
    async def bounded_probe(session, ch):
        async with semaphore:
            return await probe_channel(session, ch)
    
    # 配置连接器：增加连接池大小、开启 DNS 缓存
    connector = aiohttp.TCPConnector(
        limit=MAX_WORKERS,
        limit_per_host=5,
        ttl_dns_cache=300,
        use_dns_cache=True
    )
    timeout_config = aiohttp.ClientTimeout(total=TIMEOUT + 5, sock_connect=10, sock_read=10)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout_config) as session:
        tasks = [bounded_probe(session, ch) for ch in channels]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    valid = []
    for res in results:
        if isinstance(res, Exception):
            continue
        ch, latency, ok, ip_info = res
        if ok:
            ch.latency = latency
            if ip_info:
                ch.ip_info = ip_info
            else:
                ch.ip_info = None
            valid.append(ch)
    
    valid.sort(key=lambda x: getattr(x, 'latency', 9999))
    print(f"✅ 测速完成，有效频道 {len(valid)}/{len(channels)}")
    if len(valid) == 0:
        print("⚠️ 请检查网络连接或目标源是否可访问。可能是 User-Agent 被屏蔽，尝试更换：", random.choice(USER_AGENTS))
    return valid
