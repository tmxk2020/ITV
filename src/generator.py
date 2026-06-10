# src/generator.py
# 输出 M3U 和 TXT 文件模块，按 demo.txt 顺序输出
# 使用 #EXTINF 的 group-title 实现播放器内分组

from pathlib import Path
from typing import List, Dict
from src.config import OUTPUT_DIR, M3U_FILE, TXT_FILE, CCTV_ORDER
from src.logger import logger

def get_cctv_order_index(name: str) -> int:
    """获取央视频道排序索引"""
    name_lower = name.lower()
    for idx, std in enumerate(CCTV_ORDER):
        if std.lower() == name_lower or name_lower.startswith(std.lower()):
            return idx
    return len(CCTV_ORDER)

def sort_channels_by_demo_order(channels: List[dict], demo_categories: List[tuple]) -> List[dict]:
    """
    按 demo.txt 的顺序排序频道
    demo_categories: [(category, demo_name), ...] 保持原顺序
    """
    if not demo_categories:
        return channels
    
    # 构建 demo 顺序映射
    demo_index = {demo_name: idx for idx, (_, demo_name) in enumerate(demo_categories)}
    
    def sort_key(ch):
        ch_name = ch["name"]
        # 央视频道特殊排序
        if "CCTV" in ch_name or "央视" in ch_name:
            return (0, get_cctv_order_index(ch_name), ch_name)
        # 其他频道按 demo 顺序
        idx = demo_index.get(ch_name, len(demo_index))
        return (1, idx, ch_name)
    
    return sorted(channels, key=sort_key)

def generate_m3u(channels_by_category: Dict[str, List[dict]], output_path: Path, demo_order: List[tuple] = None) -> None:
    """生成标准 M3U8 格式文件"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        
        for cat, channels in channels_by_category.items():
            if not channels:
                continue
            
            # 按 demo 顺序排序频道
            if demo_order:
                channels = sort_channels_by_demo_order(channels, demo_order)
            
            for ch in channels:
                url = ch.get("urls", [ch.get("url")])[0]
                name = ch["name"]
                
                # 使用 group-title 实现播放器内分组
                extinf = f'#EXTINF:-1 group-title="{cat}",{name}'
                f.write(f"{extinf}\n{url}\n")
    
    logger.info(f"✅ M3U 文件已生成: {output_path}")

def generate_txt(channels_by_category: Dict[str, List[dict]], output_path: Path, demo_order: List[tuple] = None) -> None:
    """生成 TXT 文件，保持 demo.txt 的格式和顺序"""
    with open(output_path, 'w', encoding='utf-8') as f:
        for cat, channels in channels_by_category.items():
            if not channels:
                continue
            
            # 按 demo 顺序排序频道
            if demo_order:
                channels = sort_channels_by_demo_order(channels, demo_order)
            
            f.write(f"\n{cat},#genre#\n")
            for ch in channels:
                url = ch.get("urls", [ch.get("url")])[0]
                f.write(f"{ch['name']},{url}\n")
    
    logger.info(f"✅ TXT 文件已生成: {output_path}")

def generate_outputs_from_demo(ordered_channels: List[dict], demo_order: List[tuple] = None) -> None:
    """输出 M3U 和 TXT 文件"""
    if not ordered_channels:
        logger.warning("无频道数据，跳过输出生成")
        return

    # 按 demo_category 分组
    groups = {}
    for ch in ordered_channels:
        cat = ch.get("demo_category", "其他")
        groups.setdefault(cat, []).append(ch)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generate_m3u(groups, OUTPUT_DIR / M3U_FILE, demo_order)
    generate_txt(groups, OUTPUT_DIR / TXT_FILE, demo_order)
    
    # 生成带自动切换功能的 M3U（多个源用 # 分隔）
    with open(OUTPUT_DIR / "tv_multi.m3u", 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for cat, channels in groups.items():
            for ch in channels:
                urls = ch.get("urls", [ch.get("url")])
                # 多个源用 # 分隔，播放器可自动切换
                multi_url = " # ".join(urls)
                f.write(f'#EXTINF:-1 group-title="{cat}",{ch["name"]}\n{multi_url}\n')
    
    logger.info(f"✅ 多源 M3U 文件已生成: {OUTPUT_DIR / 'tv_multi.m3u'}，支持自动切换")
