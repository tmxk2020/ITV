# src/special_categories.py
"""特殊分类采集模块 - 增强版：智能分类所有频道"""

import re
from typing import List, Dict, Tuple
from pathlib import Path

from src.logger import logger

# ========== 分类关键词 ==========
CATEGORY_KEYWORDS = {
    "🎬 电影频道": [
        "电影", "影院", "影片", "CHC", "动作电影", "家庭影院", "影迷电影",
        "经典电影", "华语影院", "峨眉电影", "第一剧场", "怀旧剧场", "风云剧场",
        "家庭剧场", "惊悚悬疑", "超级电影", "黑莓电影", "新片放映厅",
        "抗战经典影片", "经典香港电影"
    ],
    "📺 电视剧频道": [
        "电视剧", "剧场", "热播", "TVB", "港剧", "韩剧", "美剧", "日剧"
    ],
    "🎤 韩国女团": [
        "韩国女团", "女团", "kpop", "K-pop", "KPOP", "BLACKPINK", "TWICE",
        "IVE", "NewJeans", "LESSERAFIM", "aespa", "Red Velvet", "ITZY",
        "女团社", "颜老师", "歌团", "歌团★"
    ],
    "🎭 戏曲频道": [
        "戏曲", "京剧", "越剧", "黄梅戏", "豫剧", "评剧", "秦腔", "昆曲",
        "粤剧", "河北梆子", "梨园", "梨园春", "移动戏曲", "岭南戏曲",
        "陕西戏曲", "河南戏曲", "安徽戏曲"
    ],
    "🎵 音乐频道": [
        "音乐", "歌曲", "老歌", "金曲", "流行", "经典老歌", "香香音乐",
        "DJ", "舞曲", "动感", "节奏", "音悦", "经典歌曲"
    ],
    "📻 网络电台": [
        "电台", "广播", "FM", "AM", "网络电台", "音频", "听书", "有声",
        "动听", "音乐广播", "交通广播", "新闻广播"
    ],
    "🏀 体育频道": [
        "体育", "NBA", "CBA", "世界杯", "英超", "西甲", "德甲", "意甲",
        "法甲", "中超", "欧冠", "亚冠", "斯诺克", "WTA", "WTT", "BWF",
        "UFC", "赛车", "F1", "电竞", "五星体育"
    ],
    "📰 新闻频道": [
        "新闻", "资讯", "报道", "CGTN", "CNN", "BBC", "NHK", "凤凰",
        "卫视", "综合频道", "公共频道"
    ],
    "👶 少儿频道": [
        "少儿", "儿童", "卡通", "动画", "金鹰卡通", "嘉佳卡通", "卡酷",
        "炫动卡通", "优漫卡通"
    ],
    "💰 财经频道": [
        "财经", "经济", "财富", "金融", "股票", "投资"
    ],
    "📡 央视": [
        "CCTV", "央视", "中央台"
    ],
    "📡 卫视": [
        "卫视", "东方卫视", "北京卫视", "湖南卫视", "浙江卫视", "江苏卫视",
        "广东卫视", "深圳卫视", "天津卫视", "山东卫视", "安徽卫视",
        "湖北卫视", "黑龙江卫视", "江西卫视", "河南卫视", "河北卫视",
        "山西卫视", "陕西卫视", "甘肃卫视", "宁夏卫视", "青海卫视",
        "云南卫视", "贵州卫视", "广西卫视", "内蒙古卫视", "新疆卫视",
        "西藏卫视", "海南卫视", "东南卫视", "重庆卫视", "四川卫视",
        "辽宁卫视", "吉林卫视", "厦门卫视", "大湾区卫视", "海峡卫视"
    ],
    "🏛️ 地方频道": [
        "电视台", "频道", "新闻综合", "都市频道", "生活频道", "经济频道",
        "科教频道", "影视", "少儿", "公共", "文艺", "旅游", "农业"
    ],
    "🌍 国际频道": [
        "国际", "海外", "美洲", "欧洲", "亚洲", "环球"
    ]
}

# 需要排除的关键词（不采集）
EXCLUDE_KEYWORDS = [
    "广场舞", "健身", "教学", "讲座", "访谈", "天气预报",
    "直播", "回放", "全场", "解说", "原声", "字幕"
]


def classify_channel_by_name(channel_name: str) -> str:
    """根据频道名智能分类"""
    name = channel_name.strip()
    if not name:
        return "其他"
    
    name_lower = name.lower()
    
    # 先排除不相关的内容
    for exclude in EXCLUDE_KEYWORDS:
        if exclude.lower() in name_lower:
            return "跳过"
    
    # 按优先级匹配分类
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in name_lower:
                return category
    
    # 特殊处理：如果包含"频道"但未匹配任何分类，归入"地方频道"
    if "频道" in name:
        return "🏛️ 地方频道"
    
    return "其他"


def parse_and_classify_special_categories(content: str) -> Dict[str, List[Tuple[str, str]]]:
    """
    从源内容中解析所有频道并智能分类
    返回: {分类名: [(频道名, URL), ...]}
    """
    if not content:
        return {}
    
    # 初始化结果字典
    result = {cat: [] for cat in CATEGORY_KEYWORDS.keys()}
    result["其他"] = []
    result["跳过"] = []  # 用于统计
    
    lines = content.splitlines()
    current_category = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 检测分类行（格式：分类名,#genre#）
        if line.endswith(",#genre#"):
            current_category = line.replace(",#genre#", "").strip()
            continue
        
        # 跳过注释行
        if line.startswith('#'):
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
                
                # 智能分类
                category = classify_channel_by_name(name)
                
                if category == "跳过":
                    result["跳过"].append((name, url))
                    continue
                
                # 去重检查（基于URL）
                existing_urls = [u for _, u in result[category]]
                if url not in existing_urls:
                    result[category].append((name, url))
    
    # 过滤掉空分类，并移除"跳过"分类
    result.pop("跳过", None)
    result = {k: v for k, v in result.items() if v}
    
    # 统计结果
    total = sum(len(v) for v in result.values())
    logger.info(f"📊 智能分类统计: 共 {total} 个频道")
    for cat, channels in result.items():
        if channels:
            logger.info(f"   {cat}: {len(channels)} 个频道")
    
    return result


async def fetch_special_categories_source(db=None) -> Dict[str, List[Tuple[str, str]]]:
    """获取特殊分类源并解析"""
    from src.fetcher import fetch_url_with_metadata
    
    source_url = "https://tv.19860519.xyz/abc123"
    
    try:
        content = await fetch_url_with_metadata(source_url, db)
        if content:
            return parse_and_classify_special_categories(content)
        else:
            logger.warning(f"⚠️ 无法获取特殊分类源: {source_url}")
            return {}
    except Exception as e:
        logger.error(f"❌ 获取特殊分类源失败: {e}")
        return {}


# 分类显示名称映射（用于输出）
CATEGORY_DISPLAY_NAME = {
    "🎬 电影频道": "🎬 电影频道",
    "📺 电视剧频道": "📺 电视剧频道",
    "🎤 韩国女团": "🎤 韩国女团",
    "🎭 戏曲频道": "🎭 戏曲频道",
    "🎵 音乐频道": "🎵 音乐频道",
    "📻 网络电台": "📻 网络电台",
    "🏀 体育频道": "🏀 体育频道",
    "📰 新闻频道": "📰 新闻频道",
    "👶 少儿频道": "👶 少儿频道",
    "💰 财经频道": "💰 财经频道",
    "📡 央视": "📡 央视",
    "📡 卫视": "📡 卫视",
    "🏛️ 地方频道": "🏛️ 地方频道",
    "🌍 国际频道": "🌍 国际频道",
    "其他": "其他",
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
        f.write(f"\n# ========== 智能分类内容 ==========\n")
        
        # 按照固定顺序输出
        order = [
            "🎬 电影频道", "📺 电视剧频道", "🎤 韩国女团", "🎭 戏曲频道",
            "🎵 音乐频道", "📻 网络电台", "🏀 体育频道", "📰 新闻频道",
            "👶 少儿频道", "💰 财经频道", "📡 央视", "📡 卫视",
            "🏛️ 地方频道", "🌍 国际频道", "其他"
        ]
        
        for cat in order:
            channels = special_data.get(cat, [])
            if not channels:
                continue
            
            display_name = CATEGORY_DISPLAY_NAME.get(cat, cat)
            f.write(f"\n# ----- {display_name} ({len(channels)}个频道) -----\n")
            
            for name, url in channels:
                f.write(f'#EXTINF:-1 group-title="{display_name}",{name}\n{url}\n')
                total_appended += 1
    
    logger.info(f"✅ 已将 {total_appended} 个频道追加到 M3U: {output_path}")
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
        f.write(f"\n# ========== 智能分类内容 ==========\n")
        
        order = [
            "🎬 电影频道", "📺 电视剧频道", "🎤 韩国女团", "🎭 戏曲频道",
            "🎵 音乐频道", "📻 网络电台", "🏀 体育频道", "📰 新闻频道",
            "👶 少儿频道", "💰 财经频道", "📡 央视", "📡 卫视",
            "🏛️ 地方频道", "🌍 国际频道", "其他"
        ]
        
        for cat in order:
            channels = special_data.get(cat, [])
            if not channels:
                continue
            
            display_name = CATEGORY_DISPLAY_NAME.get(cat, cat)
            f.write(f"\n{display_name},#genre#\n")
            
            for name, url in channels:
                f.write(f"{name},{url}\n")
                total_appended += 1
    
    logger.info(f"✅ 已将 {total_appended} 个频道追加到 TXT: {output_path}")
    return total_appended


async def collect_and_append_special_categories(output_dir: Path, db=None) -> Dict[str, int]:
    """主函数：采集并智能分类所有频道"""
    logger.info("🎬 开始采集智能分类内容...")
    
    special_data = await fetch_special_categories_source(db)
    
    if not special_data:
        logger.warning("⚠️ 未获取到任何内容")
        return {}
    
    stats = {cat: len(channels) for cat, channels in special_data.items()}
    total = sum(stats.values())
    logger.info(f"📊 智能分类统计: 共 {total} 个有效频道")
    
    if total == 0:
        logger.warning("⚠️ 没有可用的频道")
        return {}
    
    # 追加到输出文件
    m3u_path = output_dir / "tv.m3u"
    txt_path = output_dir / "tv.txt"
    
    append_special_categories_to_m3u(special_data, m3u_path)
    append_special_categories_to_txt(special_data, txt_path)
    
    return stats
