# src/generator.py
# 输出 M3U 和 TXT 文件模块，严格保持 demo.txt 的顺序

from pathlib import Path
from typing import List, Dict, Tuple
from src.config import OUTPUT_DIR, M3U_FILE, TXT_FILE
from src.logger import logger
from src.demo_filter import parse_demo_order_with_categories

def generate_m3u(channels_by_category: Dict[str, List[dict]], 
                 output_path: Path) -> None:
    """
    生成 M3U8 格式文件，严格按照 demo.txt 的分类和频道顺序
    """
    # 获取 demo.txt 的顺序
    demo_order = parse_demo_order_with_categories()
    if not demo_order:
        logger.warning("demo.txt 为空，将按分类名排序输出")
        # 降级方案
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for cat, channels in sorted(channels_by_category.items()):
                if channels:
                    f.write(f'\n#EXTINF:-1 group-title="{cat}",{cat}\n')
                    for ch in sorted(channels, key=lambda x: x["name"]):
                        url = ch.get("urls", [ch.get("url")])[0]
                        tvg_id = ch.get("id", "")
                        tvg_logo = ch.get("logo", "")
                        group = ch.get("group_title", cat)
                        name = ch["name"]
                        extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{tvg_logo}" group-title="{group}",{name}'
                        f.write(f"{extinf}\n{url}\n")
        logger.info(f"✅ M3U 文件已生成: {output_path}")
        return

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        
        # 记录已经处理过的分类，避免重复
        processed_categories = set()
        
        # 第一步：按照 demo.txt 的顺序输出分类
        for category, _ in demo_order:
            if category in processed_categories:
                continue
            
            if category in channels_by_category:
                channels = channels_by_category[category]
                if channels:
                    # 写入分类注释行
                    f.write(f'\n#EXTINF:-1 group-title="{category}",{category}\n')
                    
                    # 创建该分类下频道的名称映射
                    channel_map = {ch["name"]: ch for ch in channels}
                    
                    # 按照 demo.txt 中该分类下的频道顺序输出
                    for cat, demo_name in demo_order:
                        if cat == category and demo_name in channel_map:
                            ch = channel_map[demo_name]
                            url = ch.get("urls", [ch.get("url")])[0]
                            tvg_id = ch.get("id", "")
                            tvg_logo = ch.get("logo", "")
                            group = ch.get("group_title", category)
                            name = ch["name"]
                            extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{tvg_logo}" group-title="{group}",{name}'
                            f.write(f"{extinf}\n{url}\n")
                            # 标记已处理
                            channel_map.pop(demo_name, None)
                    
                    # 输出该分类下 demo.txt 中没有的频道（按名称排序）
                    remaining = sorted(channel_map.values(), key=lambda x: x["name"])
                    for ch in remaining:
                        url = ch.get("urls", [ch.get("url")])[0]
                        tvg_id = ch.get("id", "")
                        tvg_logo = ch.get("logo", "")
                        group = ch.get("group_title", category)
                        name = ch["name"]
                        extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{tvg_logo}" group-title="{group}",{name}'
                        f.write(f"{extinf}\n{url}\n")
                
                processed_categories.add(category)
        
        # 第二步：输出 demo.txt 中没有但实际存在的分类
        for category, channels in channels_by_category.items():
            if category not in processed_categories and channels:
                f.write(f'\n#EXTINF:-1 group-title="{category}",{category}\n')
                for ch in sorted(channels, key=lambda x: x["name"]):
                    url = ch.get("urls", [ch.get("url")])[0]
                    tvg_id = ch.get("id", "")
                    tvg_logo = ch.get("logo", "")
                    group = ch.get("group_title", category)
                    name = ch["name"]
                    extinf = f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{tvg_logo}" group-title="{group}",{name}'
                    f.write(f"{extinf}\n{url}\n")
    
    logger.info(f"✅ M3U 文件已生成（按 demo.txt 顺序）: {output_path}")

def generate_txt(channels_by_category: Dict[str, List[dict]], 
                 output_path: Path) -> None:
    """
    生成 TXT 文件，格式与 demo.txt 兼容，严格保持顺序
    """
    # 获取 demo.txt 的顺序
    demo_order = parse_demo_order_with_categories()
    if not demo_order:
        logger.warning("demo.txt 为空，将按分类名排序输出")
        with open(output_path, 'w', encoding='utf-8') as f:
            for cat, channels in sorted(channels_by_category.items()):
                if channels:
                    f.write(f"\n{cat},#genre#\n")
                    for ch in sorted(channels, key=lambda x: x["name"]):
                        url = ch.get("urls", [ch.get("url")])[0]
                        f.write(f"{ch['name']},{url}\n")
        logger.info(f"✅ TXT 文件已生成: {output_path}")
        return

    with open(output_path, 'w', encoding='utf-8') as f:
        processed_categories = set()
        
        # 第一步：按照 demo.txt 的顺序输出分类
        for category, _ in demo_order:
            if category in processed_categories:
                continue
            
            if category in channels_by_category:
                channels = channels_by_category[category]
                if channels:
                    f.write(f"\n{category},#genre#\n")
                    
                    # 创建该分类下频道的名称映射
                    channel_map = {ch["name"]: ch for ch in channels}
                    
                    # 按照 demo.txt 中该分类下的频道顺序输出
                    for cat, demo_name in demo_order:
                        if cat == category and demo_name in channel_map:
                            ch = channel_map[demo_name]
                            url = ch.get("urls", [ch.get("url")])[0]
                            f.write(f"{demo_name},{url}\n")
                            channel_map.pop(demo_name, None)
                    
                    # 输出该分类下 demo.txt 中没有的频道
                    remaining = sorted(channel_map.values(), key=lambda x: x["name"])
                    for ch in remaining:
                        url = ch.get("urls", [ch.get("url")])[0]
                        f.write(f"{ch['name']},{url}\n")
                
                processed_categories.add(category)
        
        # 第二步：输出 demo.txt 中没有的分类
        for category, channels in channels_by_category.items():
            if category not in processed_categories and channels:
                f.write(f"\n{category},#genre#\n")
                for ch in sorted(channels, key=lambda x: x["name"]):
                    url = ch.get("urls", [ch.get("url")])[0]
                    f.write(f"{ch['name']},{url}\n")
    
    logger.info(f"✅ TXT 文件已生成（按 demo.txt 顺序）: {output_path}")

def generate_outputs_from_demo(ordered_channels: List[dict]) -> None:
    """
    ordered_channels 已按照 demo.txt 的顺序排列（包含 demo_category 字段）。
    此函数保持该顺序，按 demo_category 分组后输出 M3U 和 TXT。
    """
    if not ordered_channels:
        logger.warning("无频道数据，跳过输出生成")
        return

    # 按 demo_category 分组
    groups = {}
    for ch in ordered_channels:
        cat = ch.get("demo_category", "其他")
        groups.setdefault(cat, []).append(ch)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generate_m3u(groups, OUTPUT_DIR / M3U_FILE)
    generate_txt(groups, OUTPUT_DIR / TXT_FILE)
