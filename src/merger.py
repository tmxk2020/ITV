# src/merger.py
# 频道合并模块，H.264优先 + 延迟排序 + 固定源保护

import re
import copy
from collections import defaultdict
from src.config import MAX_SOURCES_PER_CHANNEL
from src.logo_matcher import get_logo_matcher
from src.logger import logger
from src.fixed_sources import CCTV_FIXED_SOURCES


def normalize_channel_name(name: str) -> str:
    """标准化频道名，去除清晰度标签和括号内容"""
    name = re.sub(r'\s*(?:1080[pi]|720[pi]|4K|8K|HD|高清|超清|标清|流畅|付费|备\d*|备用\d*|备播|备源)\s*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[（(][^）)]*[）)]', '', name)
    name = re.sub(r'[备用备播备源]+', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def is_cctv5plus(name: str) -> bool:
    """判断是否为 CCTV-5+ 频道（必须包含加号或 plus）"""
    name_lower = name.lower()
    # 必须包含加号或 plus
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
    # 排除加号和 plus
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
    """
    将央视频道名转换为标准格式
    优先匹配 CCTV-5+，然后 CCTV-5，最后其他数字
    """
    name_clean = re.sub(r'\s*\([^)]*\)', '', name)
    name_lower = name_clean.lower()
    
    # 1. CCTV-5+（必须含加号或 plus）
    if is_cctv5plus(name_clean):
        return "CCTV-5+"
    
    # 2. CCTV-5（不含加号或 plus）
    if is_cctv5(name_clean):
        return "CCTV-5"
    
    # 3. 其他 CCTV-数字
    match = re.search(r'cctv[-\s]*(\d+)', name_lower)
    if match:
        num = int(match.group(1))
        if 1 <= num <= 17:
            return f"CCTV-{num}"
    
    # 4. 央视+数字
    match = re.search(r'央视[-\s]*(\d+)', name_clean)
    if match:
        num = int(match.group(1))
        if 1 <= num <= 17:
            return f"CCTV-{num}"
    
    return None


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
    """合并频道，确保固定源被保留，CCTV-5 和 CCTV-5+ 严格分离"""
    groups = defaultdict(list)
    
    # 分组
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
    
    logo_matcher = get_logo_matcher()
    merged = []
    
    for norm_name, ch_list in groups.items():
        # 按质量评分排序
        ch_list.sort(key=get_channel_quality_score)
        
        # 取前 MAX_SOURCES_PER_CHANNEL 个
        top = ch_list[:MAX_SOURCES_PER_CHANNEL]
        primary = top[0] if top else None
        
        if not primary:
            logger.warning(f"⚠️ {norm_name} 没有有效源")
            continue
        
        # 构建频道数据
        merged.append({
            "name": norm_name,
            "urls": [c["url"] for c in top],
            "url": primary["url"],
            "latency": primary.get("latency", 9999),
            "video_codec": primary.get("video_codec", ""),
            "group_title": primary.get("group_title", ""),
            "id": primary.get("tvg_id", ""),
            "logo": logo_matcher.get_logo_url(norm_name) if not primary.get("tvg_logo") else primary.get("tvg_logo"),
            "is_fixed": primary.get("is_fixed", False),
        })
    
    # ========== 确保所有固定源都存在于 merged 中 ==========
    for name, url in CCTV_FIXED_SOURCES.items():
        if not url:
            continue
        # 检查是否已在 merged 中
        exists = any(ch["name"] == name for ch in merged)
        if not exists:
            logger.info(f"📌 补充缺失的固定源: {name}")
            merged.append({
                "name": name,
                "urls": [url],
                "url": url,
                "latency": 50,
                "video_codec": "h264",
                "group_title": "央视",
                "id": "",
                "logo": logo_matcher.get_logo_url(name),
                "is_fixed": True,
            })

        # ========== 新增：强制 url 为字符串 ==========
    for ch in merged:
        if isinstance(ch.get("url"), list):
            ch["url"] = ch["url"][0] if ch["url"] else ""
            
    # 统计固定源使用情况
    fixed_count = sum(1 for ch in merged if ch.get("is_fixed"))
    if fixed_count > 0:
        logger.info(f"📌 已使用 {fixed_count} 个固定优质源")
    
    # 统计结果
    cctv_channels = [ch for ch in merged if ch["name"].startswith("CCTV-")]
    logger.info(f"📊 合并完成: 共 {len(merged)} 个频道，其中央视 {len(cctv_channels)} 个")
    
    return merged
