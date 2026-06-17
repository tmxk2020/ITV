# src/special_categories.py
"""特殊分类采集模块 - 根据频道名精确分类"""

import re
from typing import List, Dict, Tuple
from pathlib import Path

from src.logger import logger

# ========== 分类关键词（优先级从高到低）==========

# 韩国女团关键词
KOREAN_GIRL_KEYWORDS = [
    "韩国女团", "女团", "kpop", "K-pop", "KPOP",
    "BLACKPINK", "TWICE", "IVE", "NewJeans", "LESSERAFIM", 
    "aespa", "Red Velvet", "ITZY", "(G)I-DLE", "少女时代",
    "女团社", "颜老师", "歌团", "歌团★"
]

# 戏曲类关键词
OPERA_KEYWORDS = [
    "戏曲", "京剧", "越剧", "黄梅戏", "豫剧", "评剧", "秦腔", "昆曲",
    "粤剧", "河北梆子", "梨园", "梨园春", "移动戏曲", "岭南戏曲",
    "陕西戏曲", "河南戏曲", "安徽戏曲", "戏曲广播"
]

# 电影类关键词
MOVIE_KEYWORDS = [
    "电影", "影院", "影片", "CHC", "动作电影", "家庭影院", "影迷电影",
    "经典电影", "华语影院", "峨眉电影", "第一剧场", "怀旧剧场", "风云剧场",
    "家庭剧场", "惊悚悬疑", "超级电影", "黑莓电影", "新片放映厅",
    "抗战经典影片", "经典香港电影", "CHC影迷电影", "CHC动作电影", "CHC家庭影院"
]

# 电台类关键词（优先级提高，放在音乐之前）
RADIO_KEYWORDS = [
    "电台", "广播", "FM", "AM", "网络电台", "音频", "听书", "有声",
    "动听", "音乐广播", "交通广播", "新闻广播", "经济广播", "文艺广播"
]

# 音乐类关键词（放在电台之后）
MUSIC_KEYWORDS = [
    "音乐", "歌曲", "老歌", "金曲", "流行", "经典老歌", "香香音乐",
    "好听", "DJ", "舞曲", "动感", "节奏", "音悦", "经典歌曲",
    "热门歌曲", "动感舞曲"
]

# ========== 需要排除的关键词 ==========
EXCLUDE_KEYWORDS = [
    "广场舞", "健身", "教学", "讲座", "访谈", "天气预报",
    "CCTV", "卫视", "电视台", "新闻", "财经", "体育", "少儿", "卡通",
    "直播", "回放", "全场", "世界杯", "NBA", "英超", "中超", "村超",
    "穿越", "专区", "全折", "片段", "剧院", "演出"
]

# ========== 韩国女团中需要移除的频道名（精确匹配）==========
KOREAN_GIRL_BLACKLIST = [
    "周杰伦颜老师",
    "三国颜老师",
    "女团社颜老师"
    "花花与三猫"
]


def classify_channel_by_name(channel_name: str) -> str:
    """根据频道名精确分类（优先级从高到低）"""
    name_lower = channel_name.lower()
    
    # 1. 先排除不相关的内容
    for exclude in EXCLUDE_KEYWORDS:
        if exclude.lower() in name_lower:
            return "跳过"
    
    # 2. 韩国女团（最高优先级）
    for kw in KOREAN_GIRL_KEYWORDS:
        if kw.lower() in name_lower:
            return "韩国女团"
    
    # 3. 戏曲类
    for kw in OPERA_KEYWORDS:
        if kw.lower() in name_lower:
            return "戏曲频道"
    
    # 4. 电影类
    for kw in MOVIE_KEYWORDS:
        if kw.lower() in name_lower:
            return "每日电影/经典电影"
    
    # 5. 电台类（优先级高于音乐，避免广播被分到音乐）
    for kw in RADIO_KEYWORDS:
        if kw.lower() in name_lower:
            return "网络电台"
    
    # 6. 音乐类
    for kw in MUSIC_KEYWORDS:
        if kw.lower() in name_lower:
            return "热门歌曲/动感舞曲"
    
    return "其他"


def parse_and_classify_special_categories(content: str) -> Dict[str, List[Tuple[str, str]]]:
    """
    从源内容中解析并精确分类
    返回: {分类名: [(频道名, URL), ...]}
    """
    if not content:
        return {}
    
    # 初始化结果
    result = {
        "韩国女团": [],
        "戏曲频道": [],
        "每日电影/经典电影": [],
        "热门歌曲/动感舞曲": [],
        "网络电台": []
    }
    
    lines = content.splitlines()
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 跳过注释和分类行
        if line.startswith('#') or line.endswith(',#genre#'):
            continue
        
        # 解析频道行（格式：频道名,URL）
        if ',' in line:
            parts = line.split(',', 1)
            if len(parts) == 2:
                name = parts[0].strip()
                url = parts[1].strip()
                
                # 验证URL有效性
                if not url.startswith(('http://', 'https://')):
                    continue
                
                # 根据频道名精确分类
                category = classify_channel_by_name(name)
                
                if category != "跳过" and category in result:
                    # 去重检查（基于URL）
                    existing_urls = [u for _, u in result[category]]
                    if url not in existing_urls:
                        result[category].append((name, url))
    
    # ========== 后处理：从韩国女团中移除黑名单频道 ==========
    if "韩国女团" in result:
        original_count = len(result["韩国女团"])
        result["韩国女团"] = [
            (name, url) for name, url in result["韩国女团"]
            if name not in KOREAN_GIRL_BLACKLIST
        ]
        removed = original_count - len(result["韩国女团"])
        if removed > 0:
            logger.info(f"📌 从韩国女团中移除了 {removed} 个指定频道")
    
    # 统计结果
    for cat in result:
        if result[cat]:
            logger.info(f"📁 {cat}: {len(result[cat])} 个频道")
            # 打印前3个样例用于调试
            sample_names = [name for name, _ in result[cat][:3]]
            logger.debug(f"    样例: {', '.join(sample_names)}")
    
    return {k: v for k, v in result.items() if v}


async def fetch_special_categories_source(db=None) -> Dict[str, List[Tuple[str, str]]]:
    """获取特殊分类源并解析"""
    from src.fetcher import fetch_url_with_metadata
    import aiohttp
    
    source_url = "https://tv.19860519.xyz/abc123"
    
    try:
        async with aiohttp.ClientSession() as session:
            content = await fetch_url_with_metadata(session, source_url, db)
            if content:
                return parse_and_classify_special_categories(content)
            else:
                logger.warning(f"⚠️ 无法获取特殊分类源: {source_url}")
                return {}
    except Exception as e:
        logger.error(f"❌ 获取特殊分类源失败: {e}")
        return {}


# 分类显示名称映射
CATEGORY_DISPLAY_NAME = {
    "韩国女团": "🎤 韩国女团",
    "戏曲频道": "🎭 戏曲频道",
    "每日电影/经典电影": "🎬 每日电影/经典电影",
    "热门歌曲/动感舞曲": "🎵 热门歌曲/动感舞曲",
    "网络电台": "📻 网络电台",
}


def append_special_categories_to_m3u(
    special_data: Dict[str, List[Tuple[str, str]]],
    output_path: Path
) -> int:
    """将特殊分类追加到 M3U 文件末尾"""
    if not special_data:
        return 0
    
    total_appended = 0
    
    with open(output_path, 'a', encoding='utf-8') as f:
        f.write(f"\n# ========== 特色分类内容 ==========\n")
        
        # 按照固定顺序输出
        order = ["韩国女团", "戏曲频道", "每日电影/经典电影", "热门歌曲/动感舞曲", "网络电台"]
        
        for cat in order:
            channels = special_data.get(cat, [])
            if not channels:
                continue
            
            display_name = CATEGORY_DISPLAY_NAME.get(cat, cat)
            f.write(f"\n# ----- {display_name} ({len(channels)}个频道) -----\n")
            
            for name, url in channels:
                f.write(f'#EXTINF:-1 group-title="{display_name}",{name}\n{url}\n')
                total_appended += 1
    
    logger.info(f"✅ 已将 {total_appended} 个特色频道追加到 M3U: {output_path}")
    return total_appended


def append_special_categories_to_txt(
    special_data: Dict[str, List[Tuple[str, str]]],
    output_path: Path
) -> int:
    """将特殊分类追加到 TXT 文件末尾"""
    if not special_data:
        return 0
    
    total_appended = 0
    
    with open(output_path, 'a', encoding='utf-8') as f:
        f.write(f"\n# ========== 特色分类内容 ==========\n")
        
        order = ["韩国女团", "戏曲频道", "每日电影/经典电影", "热门歌曲/动感舞曲", "网络电台"]
        
        for cat in order:
            channels = special_data.get(cat, [])
            if not channels:
                continue
            
            display_name = CATEGORY_DISPLAY_NAME.get(cat, cat)
            f.write(f"\n{display_name},#genre#\n")
            
            for name, url in channels:
                f.write(f"{name},{url}\n")
                total_appended += 1
    
    logger.info(f"✅ 已将 {total_appended} 个特色频道追加到 TXT: {output_path}")
    return total_appended


async def collect_and_append_special_categories(output_dir: Path, db=None) -> Dict[str, int]:
    """主函数：采集特殊分类并追加到输出文件"""
    logger.info("🎬 开始采集特色分类内容...")
    
    special_data = await fetch_special_categories_source(db)
    
    if not special_data:
        logger.warning("⚠️ 未获取到任何特色分类内容")
        return {}
    
    stats = {cat: len(channels) for cat, channels in special_data.items()}
    total = sum(stats.values())
    logger.info(f"📊 特色分类统计: 共 {total} 个有效频道")
    for cat, count in stats.items():
        logger.info(f"   {CATEGORY_DISPLAY_NAME.get(cat, cat)}: {count}")
    
    if total == 0:
        logger.warning("⚠️ 没有符合分类规则的频道")
        return {}
    
    # 追加到输出文件
    m3u_path = output_dir / "tv.m3u"
    txt_path = output_dir / "tv.txt"
    
    append_special_categories_to_m3u(special_data, m3u_path)
    append_special_categories_to_txt(special_data, txt_path)
    
    # 追加到 EPG 版本
    epg_path = output_dir / "tv_epg.m3u"
    if epg_path.exists():
        append_special_categories_to_m3u(special_data, epg_path)
    
    # 追加到精简版
    lite_path = output_dir / "tv_lite.m3u"
    if lite_path.exists():
        append_special_categories_to_m3u(special_data, lite_path)
    
    return stats
