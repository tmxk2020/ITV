# src/special_categories.py
"""特定分类采集模块 - 从 abc123 和 iptv-org 源采集指定类别，并经过测速过滤后追加"""

import re
import os
from typing import List, Dict, Tuple
from pathlib import Path
from src.logger import logger
from src.speed_tester import test_channels_concurrent
from src.config import SLOW_SPEED_THRESHOLD

# 从环境变量读取是否启用测速过滤
ENABLE_SPEED_FILTER = os.getenv("ENABLE_SPEED_FILTER", "true").lower() == "true"
SPEED_FILTER_MAX_LATENCY = int(os.getenv("SPEED_FILTER_MAX_LATENCY", SLOW_SPEED_THRESHOLD))

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
    channels: List[Dict],
    max_latency: int = SPEED_FILTER_MAX_LATENCY
) -> List[Dict]:
    """
    对频道列表进行并发测速过滤，只保留延迟低于 max_latency 的有效频道
    """
    if not channels:
        return []
    
    # 如果不启用测速过滤，直接返回所有频道
    if not ENABLE_SPEED_FILTER:
        logger.info("⏭️ 测速过滤已禁用，保留所有频道")
        return channels
    
    # 构建 URL -> category 映射（用于恢复分类）
    url_to_category = {ch["url"]: ch.get("category", "其他") for ch in channels}
    
    # 构建测速所需的字典格式
    channels_dict = {}
    for ch in channels:
        key = f"{ch['name']}|{ch['url']}"
        channels_dict[key] = {"name": ch["name"], "url": ch["url"]}
    
    logger.info(f"⏳ 开始对 {len(channels_dict)} 个智能补充频道进行测速过滤...")
    
    # 调用现有测速函数
    valid = await test_channels_concurrent(channels_dict)
    
    # 给有效频道补回 category 字段
    for ch in valid:
        ch["category"] = url_to_category.get(ch["url"], "其他")
    
    # 过滤出延迟小于阈值的频道
    filtered = [ch for ch in valid if ch.get("latency", 9999) <= max_latency]
    
    removed = len(channels) - len(filtered)
    if removed > 0:
        logger.info(f"📊 测速过滤: {len(channels)} -> {len(filtered)}，移除 {removed} 个无效或慢速源")
    else:
        logger.info(f"📊 测速过滤: 全部 {len(filtered)} 个频道均有效")
    
    return filtered


def append_special_to_output(
    special_data: Dict[str, List[Tuple[str, str]]],
    output_dir: Path
) -> int:
    """将特殊分类追加到输出文件（仅追加到 tv.m3u 和 tv.txt）"""
    if not special_data:
        return 0

    total_appended = 0
    m3u_path = output_dir / "tv.m3u"
    txt_path = output_dir / "tv.txt"

    # 追加到 M3U
    with open(m3u_path, 'a', encoding='utf-8') as f:
        f.write(f"\n# ========== 智能补充分类（经测速过滤） ==========\n")
        for cat, channels in special_data.items():
            if not channels:
                continue
            display_name = CATEGORY_DISPLAY_NAME.get(cat, cat)
            f.write(f"\n# ----- {display_name} ({len(channels)}个频道) -----\n")
            for name, url in channels:
                f.write(f'#EXTINF:-1 group-title="{display_name}",{name}\n{url}\n')
                total_appended += 1

    # 追加到 TXT
    with open(txt_path, 'a', encoding='utf-8') as f:
        f.write(f"\n# ========== 智能补充分类（经测速过滤） ==========\n")
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
    主函数：从 abc123 和 iptv-org 采集指定分类，经测速过滤后追加到输出文件
    """
    logger.info("🧠 开始智能补充采集（从 abc123 + iptv-org 体育专类 + 日本体育频道）...")

    # 1. 从 abc123 获取所有目标分类
    abc123_data = await fetch_abc123_source()
    
    # 2. 从 iptv-org 主列表获取体育频道
    iptv_sports = await fetch_iptvorg_sports()
    
    # 3. 从 iptv-org 日语源获取日本体育频道
    iptv_jp_sports = await fetch_iptvorg_jp_sports()
    
    # 4. 合并到 combined_data（暂时用列表存放所有频道，分类信息保留）
    all_channels = []  # 每个元素为 {"name": name, "url": url, "category": cat}
    for cat, channels in abc123_data.items():
        for name, url in channels:
            all_channels.append({"name": name, "url": url, "category": cat})
    
    # 添加体育频道（去重）
    existing_urls = {ch["url"] for ch in all_channels}
    for name, url in iptv_sports:
        if url not in existing_urls:
            all_channels.append({"name": name, "url": url, "category": "体育竞赛"})
            existing_urls.add(url)
    for name, url in iptv_jp_sports:
        if url not in existing_urls:
            all_channels.append({"name": name, "url": url, "category": "体育竞赛"})
            existing_urls.add(url)
    
    if not all_channels:
        logger.warning("⚠️ 未获取到任何智能补充分类内容")
        return {}
    
    # 5. 测速过滤
    filtered_channels = await filter_channels_by_speed(all_channels)
    
    if not filtered_channels:
        logger.warning("⚠️ 测速过滤后无有效频道")
        return {}
    
    # 6. 按分类重组
    result = {cat: [] for cat in TARGET_CATEGORIES}
    for ch in filtered_channels:
        cat = ch.get("category", "其他")
        if cat in result:
            result[cat].append((ch["name"], ch["url"]))
        else:
            # 如果分类不在预定义中，单独创建一个 "其他" 分类（但不会发生）
            if "其他" not in result:
                result["其他"] = []
            result["其他"].append((ch["name"], ch["url"]))
    
    # 移除空分类
    result = {k: v for k, v in result.items() if v}
    
    # 7. 统计并追加
    stats = {cat: len(channels) for cat, channels in result.items()}
    total = sum(stats.values())
    logger.info(f"📊 智能补充统计（测速后）: 共 {total} 个有效频道")
    for cat, count in stats.items():
        logger.info(f"   {CATEGORY_DISPLAY_NAME.get(cat, cat)}: {count} 个频道")
    
    appended = append_special_to_output(result, output_dir)
    logger.info(f"✅ 已将 {appended} 个智能补充频道追加到输出文件")
    
    return stats
