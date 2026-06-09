# src/merger.py
# 频道合并模块：严格按标准化名称分组，优化排序解决卡顿

import re
from collections import defaultdict
from src.config import MAX_SOURCES_PER_CHANNEL

def normalize_channel_name(name: str) -> str:
    """
    标准化频道名用于合并分组。
    只去除清晰度标签和括号内容，不做任何字符转换。
    特别保留 "CCTV-1" 和 "CCTV-17" 的差异。
    """
    # 去除清晰度标签（但保留数字和连字符）
    name = re.sub(r'\s*(?:1080[pi]|720[pi]|4K|8K|HD|高清|超清|标清|流畅|付费|备\d*)\s*', '', name, flags=re.IGNORECASE)
    # 去除括号内容
    name = re.sub(r'[（(][^）)]*[）)]', '', name)
    # 去除多余空格
    name = re.sub(r'\s+', ' ', name).strip()
    # 关键：不做任何 "CCTV1" -> "CCTV-1" 的转换，保持原样
    return name

def merge_channels_by_name(valid_channels: list) -> list:
    """
    合并频道，按以下优先级排序：
    1. H.264 编码（兼容性最好）
    2. 延迟越低越好
    3. 有 IP 地域信息的优先
    """
    groups = defaultdict(list)
    for ch in valid_channels:
        norm_name = normalize_channel_name(ch["name"])
        groups[norm_name].append(ch)

    merged = []
    for norm_name, ch_list in groups.items():
        def sort_key(ch):
            # 1. H.264 优先（兼容性最好，播放卡顿少）
            codec = ch.get("video_codec", "")
            codec_priority = 0 if codec == "h264" else 1 if codec == "hevc" else 2
            
            # 2. 延迟越低越好（单位毫秒）
            latency = ch.get("latency", 9999)
            
            # 3. 有 IP 地域信息的优先（可能更稳定）
            has_ip = 0 if ch.get("ip_info") else 1
            
            # 4. URL 以 .ts 或 .m3u8 结尾的优先
            url = ch.get("url", "")
            url_priority = 0 if url.endswith(('.ts', '.m3u8')) else 1
            
            return (codec_priority, latency, has_ip, url_priority)
        
        ch_list.sort(key=sort_key)
        
        # 只取前 MAX_SOURCES_PER_CHANNEL 个最佳源
        top = ch_list[:MAX_SOURCES_PER_CHANNEL]
        primary = top[0]
        
        merged_ch = {
            "name": primary["name"],
            "urls": [c["url"] for c in top],
            "url": primary["url"],      # 最佳 URL
            "latency": primary["latency"],
            "video_codec": primary["video_codec"],
            "group_title": primary.get("group_title", ""),
            "id": primary.get("tvg_id", ""),
            "logo": primary.get("tvg_logo", ""),
            "ip_info": primary.get("ip_info")
        }
        merged.append(merged_ch)

    print(f"🔄 频道合并完成：{len(valid_channels)} 个源 -> {len(merged)} 个频道")
    
    # 打印延迟统计（调试用）
    if merged:
        latencies = [ch.get("latency", 9999) for ch in merged]
        avg_latency = sum(latencies) / len(latencies)
        print(f"📊 平均延迟: {avg_latency:.0f}ms, 最低: {min(latencies)}ms, 最高: {max(latencies)}ms")
    
    return merged
