# src/parser.py
# M3U/TXT 解析，解析后立即应用别名标准化，并保留 logo 信息
# 支持港澳台日源的自动分类

import re
from src.alias_matcher import get_alias_matcher


def infer_category_from_name(name: str) -> str:
    """根据频道名推断分类（用于港澳台日源）"""
    name_lower = name.lower()
    if any(kw in name_lower for kw in ["tvb", "翡翠", "明珠", "无线", "rthk", "hoy", "viu", "香港"]):
        return "香港频道"
    if any(kw in name_lower for kw in ["澳视", "澳门", "macau", "tdm"]):
        return "澳门频道"
    if any(kw in name_lower for kw in ["东森", "民视", "台视", "华视", "中视", "三立", "纬来", "tvbs", "年代", "壹电视", "台湾"]):
        return "台湾频道"
    if any(kw in name_lower for kw in ["nhk", "japan", "tokyo", "fuji", "tbs", "tv asahi", "ntv", "japanese", "日本"]):
        return "日本频道"
    return "港澳台日"


def parse_m3u(content: str) -> list:
    """解析 M3U 内容，返回频道列表"""
    channels = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            group_title = ""
            tvg_id = ""
            tvg_logo = ""
            match = re.search(r'group-title="([^"]+)"', line)
            if match:
                group_title = match.group(1)
            match = re.search(r'tvg-id="([^"]+)"', line)
            if match:
                tvg_id = match.group(1)
            match = re.search(r'tvg-logo="([^"]+)"', line)
            if match:
                tvg_logo = match.group(1)
            # 提取频道名（逗号之后）
            parts = line.split(",")
            if len(parts) >= 2:
                name = ",".join(parts[1:]).strip()
            else:
                name = line
            # 如果 group_title 为空，尝试推断
            if not group_title:
                group_title = infer_category_from_name(name)
            if i + 1 < len(lines) and not lines[i + 1].startswith("#"):
                url = lines[i + 1].strip()
                if url.startswith(("http://", "https://", "rtmp://", "rtsp://")):
                    channels.append({
                        "name": name,
                        "url": url,
                        "group_title": group_title,
                        "tvg_id": tvg_id,
                        "tvg_logo": tvg_logo
                    })
            i += 2
        else:
            i += 1
    return channels


def parse_txt(content: str) -> list:
    """解析 TXT 内容，返回频道列表"""
    channels = []
    lines = content.splitlines()
    current_name = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            if not line.startswith("#EXT"):
                current_name = line.lstrip("#").strip()
            continue
        if line.startswith(("http://", "https://", "rtmp://", "rtsp://")):
            name = current_name if current_name else "未知频道"
            channels.append({
                "name": name,
                "url": line,
                "group_title": "",
                "tvg_id": "",
                "tvg_logo": ""
            })
            current_name = None
    return channels


def apply_alias_to_channels(channels: list) -> list:
    """应用别名标准化"""
    matcher = get_alias_matcher()
    if not matcher:
        return channels
    for ch in channels:
        original = ch["name"]
        normalized = matcher.normalize(original)
        if normalized != original:
            ch["name"] = normalized
    return channels


def parse_and_dedupe(raw_contents: dict) -> dict:
    """解析并去重所有源"""
    all_channels = {}
    for url, content in raw_contents.items():
        if not content:
            continue
        if content.strip().startswith("#EXTM3U"):
            channels = parse_m3u(content)
        else:
            channels = parse_txt(content)
        channels = apply_alias_to_channels(channels)
        for ch in channels:
            key = f"{ch['name']}|{ch['url']}"
            if key not in all_channels:
                all_channels[key] = ch
    print(f"✅ 解析完成，去重后共 {len(all_channels)} 个频道（已标准化名称）")
    return all_channels
