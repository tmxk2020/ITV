# src/special_categories.py
"""特定分类采集模块 - 仅从 abc123 源采集指定类别：音乐、广播、歌团、电影、电视剧、动漫、体育竞赛"""

import re
from typing import List, Dict, Tuple
from pathlib import Path
from src.logger import logger

# 需要采集的分类关键词（小写），只采集这些
TARGET_CATEGORIES = [
    "音乐", "广播", "歌团", "电影", "电视剧", "动漫", "体育竞赛"
]

# 分类显示名称映射
CATEGORY_DISPLAY_NAME = {
    "音乐": "🎵 音乐频道",
    "广播": "📻 网络电台",
    "歌团": "🎤 歌团频道",
    "电影": "🎬 电影频道",
    "电视剧": "📺 电视剧频道",
    "动漫": "🎬 动漫频道",
    "体育竞赛": "🏀 体育竞赛频道",
}


def parse_abc123_for_targets(content: str) -> Dict[str, List[Tuple[str, str]]]:
    """
    解析 abc123 源内容，只提取目标分类下的频道
    返回: {分类名: [(频道名, URL), ...]}
    """
    if not content:
        return {}
    
    result = {cat: [] for cat in TARGET_CATEGORIES}
    lines = content.splitlines()
    current_category = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 检测分类行（格式：分类名,#genre#）
        if line.endswith(",#genre#") or line.endswith(", #genre#"):
            cat_name = line.replace(",#genre#", "").replace(", #genre#", "").strip()
            # 检查是否为目标分类
            for target in TARGET_CATEGORIES:
                if target in cat_name:
                    current_category = target
                    break
            else:
                current_category = None
            continue

        # 跳过注释
        if line.startswith('#'):
            continue

        # 解析频道行（格式：频道名,URL）
        if ',' in line and current_category in result:
            parts = line.split(',', 1)
            if len(parts) == 2:
                name = parts[0].strip()
                url = parts[1].strip()
                if url.startswith(('http://', 'https://')):
                    result[current_category].append((name, url))

    # 去重（基于URL）
    for cat in result:
        if result[cat]:
            seen_urls = set()
            unique = []
            for name, url in result[cat]:
                if url not in seen_urls:
                    seen_urls.add(url)
                    unique.append((name, url))
            result[cat] = unique

    # 只返回非空分类
    return {k: v for k, v in result.items() if v}


async def fetch_abc123_source(db=None) -> Dict[str, List[Tuple[str, str]]]:
    """获取 abc123 源并解析目标分类"""
    import aiohttp
    from src.fetcher import fetch_url_with_metadata

    source_url = "https://tv.19860519.xyz/abc123"

    try:
        async with aiohttp.ClientSession() as session:
            content = await fetch_url_with_metadata(session, source_url, db)
            if content:
                return parse_abc123_for_targets(content)
            else:
                logger.warning(f"⚠️ 无法获取 abc123 源: {source_url}")
                return {}
    except Exception as e:
        logger.error(f"❌ 获取 abc123 源失败: {e}")
        return {}


def append_special_to_output(
    special_data: Dict[str, List[Tuple[str, str]]],
    output_dir: Path
) -> int:
    """
    将特殊分类追加到输出文件（仅追加到 tv.m3u 和 tv.txt）
    返回追加的总频道数
    """
    if not special_data:
        return 0

    total_appended = 0
    m3u_path = output_dir / "tv.m3u"
    txt_path = output_dir / "tv.txt"

    # 追加到 M3U
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

    # 追加到 TXT
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
    主函数：采集指定分类并追加到输出文件
    只接受两个参数：output_dir 和 db（可选）
    """
    logger.info("🧠 开始智能补充采集（从 abc123 源）...")

    special_data = await fetch_abc123_source(db)

    if not special_data:
        logger.warning("⚠️ 未获取到任何智能补充分类内容")
        return {}

    stats = {cat: len(channels) for cat, channels in special_data.items()}
    total = sum(stats.values())
    logger.info(f"📊 智能补充统计: 共 {total} 个频道")
    for cat, count in stats.items():
        logger.info(f"   {CATEGORY_DISPLAY_NAME.get(cat, cat)}: {count} 个频道")

    if total == 0:
        logger.warning("⚠️ 没有符合分类规则的频道")
        return {}

    # 追加到输出文件（只传两个参数）
    appended = append_special_to_output(special_data, output_dir)
    logger.info(f"✅ 已将 {appended} 个智能补充频道追加到输出文件")

    return stats
