# src/merger.py
# 频道合并模块，H.264优先 + 延迟排序 + 固定源优先（支持多个固定源）

import re
import copy
from collections import defaultdict
from src.config import MAX_SOURCES_PER_CHANNEL
from src.logo_matcher import get_logo_matcher
from src.logger import logger
from src.fixed_sources import CCTV_FIXED_SOURCES, ENABLE_FIXED_SOURCES, FIXED_SOURCE_LATENCY, FIXED_SOURCE_CODEC


def normalize_channel_name(name: str) -> str:
    """标准化频道名，去除清晰度标签和括号内容"""
    name = re.sub(r'\s*(?:1080[pi]|720[pi]|4K|8K|HD|高清|超清|标清|流畅|付费|备\d*|备用\d*|备播|备源)\s*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[（(][^）)]*[）)]', '', name)
    name = re.sub(r'[备用备播备源]+', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def is_cctv5plus(name: str) -> bool:
    """判断是否为 CCTV-5+ 频道"""
    name_lower = name.lower()
    if '+' in name or '＋' in name:
        return True
    if '5plus' in name_lower or '5+' in name_lower:
        return True
    if '央视5+' in name or '中央5+' in name:
        return True
    return False


def is_cctv5(name: str) -> bool:
    """判断是否为 CCTV-5 频道（排除 CCTV-5+）"""
    name_lower = name.lower()
    if '+' in name or '＋' in name:
        return False
    if '5plus' in name_lower:
        return False
    if re.search(r'cctv[-\s]*5\b', name_lower):
        return True
    if '央视5' in name or '中央5' in name:
        return True
    return False


def get_cctv_standard_name(name: str) -> str:
    """将央视频道名转换为标准格式"""
    if is_cctv5plus(name):
        return "CCTV-5+"
    if is_cctv5(name):
        return "CCTV-5"
    
    match = re.search(r'cctv[-\s]*(\d+)', name.lower())
    if match:
        num = match.group(1)
        return f"CCTV-{num}"
    
    match = re.search(r'央视[-\s]*(\d+)', name)
    if match:
        num = match.group(1)
        return f"CCTV-{num}"
    
    return None


def get_fixed_sources(channel_name: str) -> list:
    """获取固定源列表"""
    if not ENABLE_FIXED_SOURCES:
        return []
    
    std_name = get_cctv_standard_name(channel_name)
    if not std_name:
        return []
    
    urls = CCTV_FIXED_SOURCES.get(std_name, [])
    if not urls:
        return []
    
    # 为每个 URL 构造固定源字典
    fixed_sources = []
    for url in urls:
        if url:
            fixed_sources.append({
                "name": std_name,
                "url": url,
                "latency": FIXED_SOURCE_LATENCY,
                "video_codec": FIXED_SOURCE_CODEC,
                "is_fixed": True
            })
    return fixed_sources


def get_channel_quality_score(channel: dict) -> tuple:
    """获取频道质量评分（固定源优先级最高）"""
    if channel.get("is_fixed"):
        return (0, 0, 0)
    
    codec = channel.get("video_codec", "").lower()
    if codec == "h264":
        codec_priority = 1
    elif codec in ["hevc", "h265"]:
        codec_priority = 2
    else:
        codec_priority = 3
    
    latency = channel.get("latency", 9999)
    
    url = channel.get("url", "").lower()
    url_bonus = 0
    if ".m3u8" in url:
        url_bonus = 0
    elif ".ts" in url:
        url_bonus = 1
    else:
        url_bonus = 2
    
    return (codec_priority, latency, url_bonus)


def merge_channels_by_name(valid_channels: list) -> list:
    """合并频道，固定源优先（支持每个频道多个固定源）"""
    groups = defaultdict(list)
    
    # 首先添加固定源
    fixed_sources_added = set()
    for ch in valid_channels:
        raw_name = ch["name"]
        std_name = get_cctv_standard_name(raw_name)
        if std_name:
            norm_name = std_name
        else:
            norm_name = normalize_channel_name(raw_name)
            if not norm_name or len(norm_name) < 2:
                norm_name = raw_name
        groups[norm_name].append(ch)
        
        # 检查是否有固定源
        if std_name and std_name not in fixed_sources_added:
            fixed_list = get_fixed_sources(raw_name)
            if fixed_list:
                # 将固定源插入到最前面（倒序插入，保持顺序）
                for fixed in reversed(fixed_list):
                    groups[std_name].insert(0, fixed)
                fixed_sources_added.add(std_name)
                logger.info(f"📌 已添加 {len(fixed_list)} 个固定源: {std_name} -> {[f['url'] for f in fixed_list]}")
    
    logo_matcher = get_logo_matcher()
    merged = []
    
    for norm_name, ch_list in groups.items():
        # 去重（基于URL）
        seen_urls = set()
        unique_list = []
        for ch in ch_list:
            if ch["url"] not in seen_urls:
                seen_urls.add(ch["url"])
                unique_list.append(ch)
        
        # 按质量评分排序
        unique_list.sort(key=get_channel_quality_score)
        
        # 取前 MAX_SOURCES_PER_CHANNEL 个
        top = unique_list[:MAX_SOURCES_PER_CHANNEL]
        primary = top[0] if top else None
        
        if not primary:
            continue
        
        logo_url = primary.get("tvg_logo", "")
        if not logo_url:
            logo_url = logo_matcher.get_logo_url(norm_name)
        
        merged.append({
            "name": norm_name,
            "urls": [c["url"] for c in top],
            "url": primary["url"],
            "latency": primary.get("latency", 9999),
            "video_codec": primary.get("video_codec", ""),
            "is_fixed": primary.get("is_fixed", False),
            "group_title": primary.get("group_title", "央视"),
            "id": primary.get("tvg_id", ""),
            "logo": logo_url,
        })
    
    # 统计固定源使用情况
    fixed_count = sum(1 for ch in merged if ch.get("is_fixed"))
    if fixed_count > 0:
        logger.info(f"📌 已使用 {fixed_count} 个固定优质源")
    
    logger.info(f"🔄 频道合并完成：{len(merged)} 个频道")
    return merged
