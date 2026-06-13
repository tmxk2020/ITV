# src/merger.py
# 频道合并模块，H.264优先 + 延迟排序

import re
import copy
from collections import defaultdict
from src.config import MAX_SOURCES_PER_CHANNEL
from src.logo_matcher import get_logo_matcher
from src.logger import logger


def normalize_channel_name(name: str) -> str:
    """标准化频道名，去除清晰度标签和括号内容"""
    name = re.sub(r'\s*(?:1080[pi]|720[pi]|4K|8K|HD|高清|超清|标清|流畅|付费|备\d*|备用\d*|备播|备源)\s*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[（(][^）)]*[）)]', '', name)
    name = re.sub(r'[备用备播备源]+', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def is_cctv5plus(name: str) -> bool:
    """判断是否为 CCTV-5+ 频道（必须包含加号）"""
    name_lower = name.lower()
    # 必须包含加号
    if '+' in name or '＋' in name:
        return True
    # 包含 plus 关键词
    if '5plus' in name_lower or '5+' in name_lower:
        return True
    # 央视5+ 或 中央5+
    if '央视5+' in name or '中央5+' in name:
        return True
    return False


def is_cctv5(name: str) -> bool:
    """判断是否为 CCTV-5 频道（排除 CCTV-5+）"""
    name_lower = name.lower()
    # 如果包含加号，不是 CCTV-5
    if '+' in name or '＋' in name:
        return False
    # 如果包含 plus，不是 CCTV-5
    if '5plus' in name_lower:
        return False
    # 匹配 CCTV-5 或 央视5
    if re.search(r'cctv[-\s]*5\b', name_lower):
        return True
    if '央视5' in name or '中央5' in name:
        return True
    return False


def get_cctv_standard_name(name: str) -> str:
    """将央视频道名转换为标准格式，CCTV-5+ 优先于 CCTV-5"""
    if is_cctv5plus(name):
        return "CCTV-5+"
    if is_cctv5(name):
        return "CCTV-5"
    
    # 其他 CCTV-数字
    match = re.search(r'cctv[-\s]*(\d+)', name.lower())
    if match:
        num = match.group(1)
        return f"CCTV-{num}"
    
    # 央视+数字
    match = re.search(r'央视[-\s]*(\d+)', name)
    if match:
        num = match.group(1)
        return f"CCTV-{num}"
    
    return None


def get_channel_quality_score(channel: dict) -> tuple:
    """获取频道质量评分（用于排序，分数越低越好）"""
    # 视频编码优先级：h264 > h265 > 其他
    codec = channel.get("video_codec", "").lower()
    if codec == "h264":
        codec_priority = 0
    elif codec in ["hevc", "h265"]:
        codec_priority = 1
    else:
        codec_priority = 2
    
    # 延迟优先级：延迟越低越好
    latency = channel.get("latency", 9999)
    
    # 额外加分：URL 特征（更稳定的源优先）
    url = channel.get("url", "").lower()
    url_bonus = 0
    if "m3u8" in url:
        url_bonus = 0  # m3u8 标准格式
    elif "flv" in url:
        url_bonus = 1  # flv 可能较老
    elif "ts" in url:
        url_bonus = 0  # ts 分片也可以
    else:
        url_bonus = 2  # 其他格式
    
    return (codec_priority, latency, url_bonus)


def merge_channels_by_name(valid_channels: list) -> list:
    """合并频道，确保 CCTV-5 和 CCTV-5+ 正确分离"""
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
    matched_logos = 0
    merged = []
    
    # 统计 CCTV-5 和 CCTV-5+ 的源数量
    cctv5_sources = []
    cctv5plus_sources = []
    
    for norm_name, ch_list in groups.items():
        # 按质量评分排序
        ch_list.sort(key=get_channel_quality_score)
        
        # 记录 CCTV-5 和 CCTV-5+ 的源
        if norm_name == "CCTV-5":
            cctv5_sources = ch_list.copy()
        elif norm_name == "CCTV-5+":
            cctv5plus_sources = ch_list.copy()
        
        # 取前 MAX_SOURCES_PER_CHANNEL 个
        top = ch_list[:MAX_SOURCES_PER_CHANNEL]
        primary = top[0] if top else None
        
        if not primary:
            logger.warning(f"⚠️ {norm_name} 没有有效源")
            continue
        
        logo_url = primary.get("tvg_logo", "")
        if not logo_url:
            logo_url = logo_matcher.get_logo_url(norm_name)
            matched_logos += 1
        
        merged.append({
            "name": norm_name,
            "urls": [c["url"] for c in top],
            "url": primary["url"],
            "latency": primary.get("latency", 9999),
            "video_codec": primary.get("video_codec", ""),
            "group_title": primary.get("group_title", ""),
            "id": primary.get("tvg_id", ""),
            "logo": logo_url,
        })
    
    # ========== 修复：确保 CCTV-5+ 有自己的源，不复制 CCTV-5 ==========
    has_cctv5 = any(ch["name"] == "CCTV-5" for ch in merged)
    has_cctv5plus = any(ch["name"] == "CCTV-5+" for ch in merged)
    
    logger.info(f"📊 CCTV-5 源数量: {len(cctv5_sources)}")
    logger.info(f"📊 CCTV-5+ 源数量: {len(cctv5plus_sources)}")
    
    # 情况1：没有 CCTV-5+ 但有 CCTV-5 的源
    if not has_cctv5plus and cctv5_sources:
        logger.warning("⚠️ 未找到 CCTV-5+ 专用源，尝试从 CCTV-5 源中筛选真正的 CCTV-5+")
        
        # 从 CCTV-5 的源中筛选可能包含 5+ 的 URL
        potential_5plus = []
        for ch in cctv5_sources:
            url_lower = ch["url"].lower()
            # 检查 URL 中是否包含 5+ 相关关键词
            if any(kw in url_lower for kw in ['5plus', '5+', 'cctv5%2B', 'cctv-5%2B']):
                potential_5plus.append(ch)
        
        if potential_5plus:
            # 使用找到的 5+ 源
            best = potential_5plus[0]
            logger.info(f"✅ 从 URL 识别到 CCTV-5+ 源: {best['url'][:100]}")
            merged.append({
                "name": "CCTV-5+",
                "urls": [best["url"]],
                "url": best["url"],
                "latency": best.get("latency", 9999),
                "video_codec": best.get("video_codec", ""),
                "group_title": "央视",
                "id": "",
                "logo": logo_matcher.get_logo_url("CCTV-5+"),
            })
            has_cctv5plus = True
        else:
            logger.warning("⚠️ 未找到 CCTV-5+ 专用源，CCTV-5+ 将使用独立源（如果有）")
    
    # 情况2：既没有 CCTV-5+ 也没有 CCTV-5 的源
    if not has_cctv5plus and not has_cctv5:
        logger.warning("⚠️ 未找到任何 CCTV-5/5+ 源，创建占位符")
        merged.append({
            "name": "CCTV-5+",
            "urls": [],
            "url": "",
            "latency": 9999,
            "video_codec": "",
            "group_title": "央视",
            "id": "",
            "logo": logo_matcher.get_logo_url("CCTV-5+"),
        })
    
    # 统计结果
    cctv5_count = sum(1 for ch in merged if ch["name"] == "CCTV-5")
    cctv5plus_count = sum(1 for ch in merged if ch["name"] == "CCTV-5+")
    logger.info(f"📊 合并结果: CCTV-5={cctv5_count}, CCTV-5+={cctv5plus_count}")
    
    # 输出 CCTV-5 和 CCTV-5+ 的源信息（用于调试）
    for ch in merged:
        if ch["name"] in ["CCTV-5", "CCTV-5+"]:
            logger.info(f"  {ch['name']}: {ch['url'][:80]}... (延迟: {ch['latency']}ms)")
    
    logger.info(f"🔄 频道合并完成：{len(valid_channels)} 个源 -> {len(merged)} 个频道")
    
    return merged
