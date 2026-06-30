# src/special_categories.py
"""特定分类采集模块 - 从 abc123 和 iptv-org 源采集指定类别，并过滤慢速/无效源"""

import re
import asyncio
from typing import List, Dict, Tuple
from pathlib import Path
from src.logger import logger
from src.config import SLOW_SPEED_THRESHOLD, HTTP_TIMEOUT


# 需要采集的分类关键词（小写）
TARGET_CATEGORIES = [
    "音乐", "广播", "韩国女团", "电影", "电视剧", "动漫", "体育竞赛"
]

# 分类显示名称映射
CATEGORY_DISPLAY_NAME = {
    "音乐": "🎵 音乐频道",
    "广播": "📻 网络电台",
    "韩国女团": "🎤 韩国女团",
    "电影": "🎬 电影频道",
    "电视剧": "📺 电视剧频道",
    "动漫": "🎬 动漫频道",
    "体育竞赛": "🏀 体育竞赛频道",
}


def parse_abc123_for_targets(content: str) -> Dict[str, List[Tuple[str, str]]]:
    """解析 abc123 源内容，提取目标分类下的频道"""
    if not content:
        return {}
    
    result = {cat: [] for cat in TARGET_CATEGORIES}
    lines = content.splitlines()
    current_category = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.endswith(",#genre#") or line.endswith(", #genre#"):
            cat_name = line.replace(",#genre#", "").replace(", #genre#", "").strip()
            current_category = None
            for target in TARGET_CATEGORIES:
                if target == "韩国女团" and ("歌团" in cat_name or "女团" in cat_name):
                    current_category = target
                    break
                elif target in cat_name:
                    current_category = target
                    break
            continue

        if line.startswith('#'):
            continue

        if ',' in line and current_category in result:
            parts = line.split(',', 1)
            if len(parts) == 2:
                name = parts[0].strip()
                url = parts[1].strip()
                if url.startswith(('http://', 'https://')):
                    existing_urls = [u for _, u in result[current_category]]
                    if url not in existing_urls:
                        result[current_category].append((name, url))

    return {k: v for k, v in result.items() if v}


def parse_iptvorg_for_sports(content: str) -> List[Tuple[str, str]]:
    """
    解析 iptv-org M3U 内容，提取体育类频道（group-title 含 Sport/Sports/体育）
    返回 [(频道名, URL), ...]
    """
    if not content:
        return []
    sports_channels = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            group_title = ""
            match = re.search(r'group-title="([^"]+)"', line)
            if match:
                group_title = match.group(1)
            name = line.split(",")[-1].strip()
            if group_title and re.search(r'(?i)sport|体育', group_title):
                if i + 1 < len(lines) and not lines[i + 1].startswith("#"):
                    url = lines[i + 1].strip()
                    if url.startswith(('http://', 'https://')):
                        sports_channels.append((name, url))
            i += 2
        else:
            i += 1
    return sports_channels


async def fetch_abc123_source() -> Dict[str, List[Tuple[str, str]]]:
    """直接拉取 abc123 源内容并解析目标分类"""
    import aiohttp
    source_url = "https://tv.19860519.xyz/abc123"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(source_url, timeout=10, headers=headers) as resp:
                if resp.status != 200:
                    logger.warning(f"⚠️ abc123 源返回 HTTP {resp.status}")
                    return {}
                content = await resp.text()
                return parse_abc123_for_targets(content)
    except Exception as e:
        logger.error(f"❌ 获取 abc123 源失败: {e}")
        return {}


async def fetch_iptvorg_sports() -> List[Tuple[str, str]]:
    """直接拉取 iptv-org 主列表并提取体育频道"""
    import aiohttp
    source_url = "https://iptv-org.github.io/iptv/index.m3u"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(source_url, timeout=15, headers=headers) as resp:
                if resp.status != 200:
                    logger.warning(f"⚠️ iptv-org 源返回 HTTP {resp.status}")
                    return []
                content = await resp.text()
                return parse_iptvorg_for_sports(content)
    except Exception as e:
        logger.error(f"❌ 获取 iptv-org 体育频道失败: {e}")
        return []


async def fetch_iptvorg_jp_sports() -> List[Tuple[str, str]]:
    """从 iptv-org 日语源拉取体育频道"""
    import aiohttp
    source_url = "https://iptv-org.github.io/iptv/languages/jpn.m3u"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(source_url, timeout=15, headers=headers) as resp:
                if resp.status != 200:
                    logger.warning(f"⚠️ iptv-org 日语源返回 HTTP {resp.status}")
                    return []
                content = await resp.text()
                return parse_iptvorg_for_sports(content)
    except Exception as e:
        logger.error(f"❌ 获取 iptv-org 日本体育频道失败: {e}")
        return []


async def filter_channels_by_speed(
    channels: List[Tuple[str, str]],
    max_latency: int = SLOW_SPEED_THRESHOLD,
    timeout: int = HTTP_TIMEOUT
) -> List[Tuple[str, str]]:
    """
    对频道列表进行速度过滤，只保留延迟低于 max_latency 的有效源
    返回过滤后的列表
    """
    if not channels:
        return []
    
    # 导入测速函数（避免循环依赖）
    from src.speed_tester import probe_channel_advanced
    import aiohttp
    
    semaphore = asyncio.Semaphore(20)  # 限制并发
    valid_channels = []
    
    async def check_one(name, url):
        async with semaphore:
            # 构造 channel 字典
            channel = {"name": name, "url": url}
            # 调用测速函数，传入 db=None 表示不使用缓存
            try:
                # 注意：probe_channel_advanced 返回 (channel, latency, is_valid, speed, is_slow)
                # 但最新版本可能返回不同，我们适配一下
                # 如果函数签名变化，这里做简单处理
                import inspect
                sig = inspect.signature(probe_channel_advanced)
                if len(sig.parameters) == 3:
                    # 旧版本：probe_channel_advanced(session, channel, db)
                    # 这里我们需要传入 session
                    # 但由于我们无法在闭包中传递 session，我们直接用内部函数
                    # 重新实现简化版测速
                    return await _quick_check(name, url, timeout)
                else:
                    # 新版：probe_channel_advanced(session, channel, db)
                    # 我们不用它，用 _quick_check
                    return await _quick_check(name, url, timeout)
            except Exception as e:
                logger.debug(f"测速异常 {name}: {e}")
                return None
    
    async def _quick_check(name, url, timeout):
        """快速 HEAD + 小段下载检查"""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                # HEAD 请求
                async with session.head(url, timeout=timeout, allow_redirects=True) as resp:
                    if resp.status != 200:
                        return None
                    content_type = resp.headers.get("content-type", "").lower()
                    if "video" not in content_type and "mpegurl" not in content_type and "x-mpegurl" not in content_type:
                        return None
                # 小段下载
                start = asyncio.get_event_loop().time()
                async with session.get(url, timeout=timeout, headers={"Range": "bytes=0-65535"}) as resp:
                    if resp.status not in [200, 206]:
                        return None
                    data = await resp.content.read(65536)
                    # 检查是否视频内容
                    if data.startswith(b'#EXTM3U') or b'#EXTINF' in data:
                        pass
                    else:
                        # 检查文件头
                        if not any(data.startswith(sig) for sig in [
                            b'\x00\x00\x00\x18ftyp', b'\x00\x00\x00\x1cftyp',
                            b'\x1a\x45\xdf\xa3', b'\x47\x40\x00', b'FLV'
                        ]):
                            return None
                    latency = int((asyncio.get_event_loop().time() - start) * 1000)
                    if latency < max_latency:
                        return (name, url)
                    else:
                        return None
        except Exception:
            return None
    
    # 创建任务
    tasks = [check_one(name, url) for name, url in channels]
    results = await asyncio.gather(*tasks)
    
    valid_channels = [r for r in results if r is not None]
    return valid_channels


def append_special_to_output(
    special_data: Dict[str, List[Tuple[str, str]]],
    output_dir: Path
) -> int:
    """将特殊分类追加到输出文件"""
    if not special_data:
        return 0

    total_appended = 0
    m3u_path = output_dir / "tv.m3u"
    txt_path = output_dir / "tv.txt"

    with open(m3u_path, 'a', encoding='utf-8') as f:
        f.write(f"\n# ========== 智能补充分类 ==========\n")
        for cat, channels in special_data.items():
            if not channels:
                continue
            display_name = CATEGORY_DISPLAY_NAME.get(cat, cat)
            f.write(f"\n# ----- {display_name} ({len(channels)}个频道) -----\n")
            for name, url in channels:
                f.write(f'#EXTINF:-1 group-title="{display_name}",{name}\n{url}\n')
                total_appended += 1

    with open(txt_path, 'a', encoding='utf-8') as f:
        f.write(f"\n# ========== 智能补充分类 ==========\n")
        for cat, channels in special_data.items():
            if not channels:
                continue
            display_name = CATEGORY_DISPLAY_NAME.get(cat, cat)
            f.write(f"\n{display_name},#genre#\n")
            for name, url in channels:
                f.write(f"{name},{url}\n")

    return total_appended


async def collect_and_append_special_categories(output_dir: Path, db=None) -> Dict[str, int]:
    """
    主函数：从 abc123 和 iptv-org 采集指定分类，过滤慢速/无效源，然后追加
    """
    logger.info("🧠 开始智能补充采集（从 abc123 + iptv-org 体育专类 + 日本体育频道）...")

    # 1. 采集
    abc123_data = await fetch_abc123_source()
    iptv_sports = await fetch_iptvorg_sports()
    iptv_jp_sports = await fetch_iptvorg_jp_sports()

    # 合并
    combined_data = abc123_data.copy()
    if "体育竞赛" not in combined_data:
        combined_data["体育竞赛"] = []
    
    existing_urls = {url for _, url in combined_data["体育竞赛"]}
    for name, url in iptv_sports:
        if url not in existing_urls:
            combined_data["体育竞赛"].append((name, url))
            existing_urls.add(url)
    for name, url in iptv_jp_sports:
        if url not in existing_urls:
            combined_data["体育竞赛"].append((name, url))
            existing_urls.add(url)

    # 2. 对所有分类进行速度过滤
    filtered_data = {}
    logger.info("⏱️ 开始对智能补充频道进行速度过滤...")
    for cat, channels in combined_data.items():
        if not channels:
            continue
        # 过滤慢速/无效源
        valid = await filter_channels_by_speed(channels)
        if valid:
            filtered_data[cat] = valid
        else:
            logger.info(f"   {cat}: 所有频道均未通过速度测试，已丢弃")

    if not filtered_data:
        logger.warning("⚠️ 速度过滤后无任何可用频道")
        return {}

    # 统计
    stats = {cat: len(ch) for cat, ch in filtered_data.items()}
    total = sum(stats.values())
    logger.info(f"📊 速度过滤后统计: 共 {total} 个有效频道")
    for cat, count in stats.items():
        logger.info(f"   {CATEGORY_DISPLAY_NAME.get(cat, cat)}: {count} 个频道")

    # 3. 追加到输出文件
    appended = append_special_to_output(filtered_data, output_dir)
    logger.info(f"✅ 已将 {appended} 个智能补充频道（已过滤慢速源）追加到输出文件")

    return stats
