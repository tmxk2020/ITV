# src/generator_enhanced.py
"""增强版输出生成器：支持多种输出格式"""

import json
from pathlib import Path
from typing import List, Dict
from src.config import OUTPUT_DIR
from src.epg_injector import get_epg_injector
from src.logger import logger

class EnhancedOutputGenerator:
    """多种输出格式生成器"""
    
    def __init__(self):
        self.epg_injector = get_epg_injector()
    
    def generate_all_outputs(self, channels: List[Dict], demo_order: List[tuple]) -> None:
        """生成所有格式的输出文件"""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        # 1. 标准国内版（原有格式）
        self._generate_standard_m3u(channels, demo_order, OUTPUT_DIR / "tv.m3u")
        self._generate_standard_txt(channels, demo_order, OUTPUT_DIR / "tv.txt")
        
        # 2. EPG 就绪版（带 tvg-id 和 logo）
        channels_with_epg = self.epg_injector.inject_epg_metadata(channels.copy())
        self._generate_epg_m3u(channels_with_epg, demo_order, OUTPUT_DIR / "tv_epg.m3u")
        
        # 3. JSON API 版（供其他程序调用）
        self._generate_json_api(channels, OUTPUT_DIR / "channels.json")
        
        # 4. 多源切换版（同一频道多个源）
        self._generate_multi_source_m3u(channels, demo_order, OUTPUT_DIR / "tv_multi.m3u")
        
        # 5. 精简手机版（只保留最稳定的源）
        self._generate_lite_version(channels, OUTPUT_DIR / "tv_lite.m3u")
        
        logger.info("✅ 所有格式输出完成")
    
    def _generate_standard_m3u(self, channels: List[Dict], demo_order: List[tuple], path: Path) -> None:
        """标准 M3U（原逻辑）"""
        # ... 保持原有实现 ...
        pass
    
    def _generate_epg_m3u(self, channels: List[Dict], demo_order: List[tuple], path: Path) -> None:
        """EPG 就绪版 M3U"""
        with open(path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for cat, demo_name in demo_order:
                for ch in channels:
                    if ch["name"] == demo_name:
                        tags = []
                        if ch.get("tvg_id"):
                            tags.append(f'tvg-id="{ch["tvg_id"]}"')
                        if ch.get("logo"):
                            tags.append(f'tvg-logo="{ch["logo"]}"')
                        tags.append(f'group-title="{cat}"')
                        
                        tags_str = " ".join(tags)
                        url = ch.get("urls", [ch.get("url")])[0]
                        f.write(f'#EXTINF:-1 {tags_str},{ch["name"]}\n{url}\n')
                        break
        logger.info(f"✅ EPG 就绪版已生成: {path}")
    
    def _generate_json_api(self, channels: List[Dict], path: Path) -> None:
        """JSON API 格式"""
        api_data = {
            "version": "2.0",
            "total": len(channels),
            "generated": __import__("datetime").datetime.now().isoformat(),
            "channels": [
                {
                    "name": ch["name"],
                    "urls": ch.get("urls", [ch.get("url")]),
                    "latency": ch.get("latency"),
                    "codec": ch.get("video_codec"),
                    "tvg_id": ch.get("tvg_id", ""),
                    "logo": ch.get("logo", ""),
                    "category": ch.get("demo_category", "")
                }
                for ch in channels
            ]
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(api_data, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ JSON API 已生成: {path}")
    
    def _generate_multi_source_m3u(self, channels: List[Dict], demo_order: List[tuple], path: Path) -> None:
        """多源 M3U（同一频道多个备源）"""
        with open(path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for cat, demo_name in demo_order:
                for ch in channels:
                    if ch["name"] == demo_name:
                        urls = ch.get("urls", [ch.get("url")])
                        multi_url = " # ".join(urls)
                        f.write(f'#EXTINF:-1 group-title="{cat}",{ch["name"]}\n{multi_url}\n')
                        break
        logger.info(f"✅ 多源 M3U 已生成: {path}")
    
    def _generate_lite_version(self, channels: List[Dict], path: Path) -> None:
        """精简版：只保留延迟最低的源（按分类限制数量）"""
        # 央视全部保留，其他分类只保留前 50 个
        lite_channels = []
        cat_counts = {}
        
        for ch in channels:
            cat = ch.get("demo_category", "其他")
            if cat == "央视":
                lite_channels.append(ch)
            else:
                if cat_counts.get(cat, 0) < 50:
                    lite_channels.append(ch)
                    cat_counts[cat] = cat_counts.get(cat, 0) + 1
        
        # 生成精简版 M3U
        with open(path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n# 精简版 - 仅保留最稳定源\n")
            for ch in lite_channels:
                url = ch.get("urls", [ch.get("url")])[0]
                f.write(f'#EXTINF:-1 group-title="{ch.get("demo_category", "")}",{ch["name"]}\n{url}\n')
        
        logger.info(f"✅ 精简版已生成: {path} (共 {len(lite_channels)} 个频道)")
