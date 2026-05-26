# src/demo_filter.py
# Demo 频道筛选与排序模块（包含匹配，保留港澳台）

from pathlib import Path
from typing import List, Tuple
from src.config import DEMO_FILE, OUTPUT_DIR
from src.alias_matcher import get_alias_matcher

# 使用包含匹配，确保港澳台频道能匹配 demo 中相应条目
DEMO_MATCH_MODE = "contains"

def parse_demo_order_with_categories(demo_file: Path = DEMO_FILE) -> List[Tuple[str, str]]:
    """解析 demo.txt，返回 [(分类, 标准化频道名), ...]"""
    if not demo_file.exists():
        print(f"⚠️ Demo 文件不存在: {demo_file}")
        return []
    matcher = get_alias_matcher()
    order = []
    current_category = None
    with open(demo_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.endswith(",#genre#"):
                current_category = line[:-7]
                continue
            if line.startswith('#'):
                continue
            if current_category is not None:
                demo_name = line
                if matcher:
                    demo_name = matcher.normalize(demo_name)
                order.append((current_category, demo_name))
            else:
                order.append(("其他", line))
    print(f"📋 从 demo.txt 解析到 {len(order)} 个有序频道，共 {len(set(c for c,_ in order))} 个分类")
    return order

def match_channel_name(channel_name: str, demo_name: str) -> bool:
    """包含匹配（忽略大小写）"""
    if DEMO_MATCH_MODE == "exact":
        return channel_name == demo_name
    else:
        cn_lower = channel_name.lower()
        dn_lower = demo_name.lower()
        return dn_lower in cn_lower or cn_lower in dn_lower

def filter_and_order_by_demo(channels: list) -> tuple:
    """
    返回 (matched_channels, unmatched_channels)
    matched_channels: 按 demo 顺序排列，每个频道增加 'demo_category' 字段
    """
    demo_order = parse_demo_order_with_categories()
    if not demo_order:
        print("⚠️ demo.txt 为空，跳过筛选")
        return channels, []

    name_to_channel = {ch["name"]: ch for ch in channels}
    matched = []
    unmatched = list(channels)
    matched_names = set()
    matched_demo_items = set()

    for category, demo_name in demo_order:
        # 精确匹配
        if demo_name in name_to_channel:
            ch = name_to_channel[demo_name].copy()
            ch["demo_category"] = category
            if ch["name"] not in matched_names:
                matched.append(ch)
                matched_names.add(ch["name"])
                matched_demo_items.add(demo_name)
                unmatched = [c for c in unmatched if c["name"] != ch["name"]]
                continue
        # 包含匹配
        found = False
        for i, ch in enumerate(unmatched[:]):
            if ch["name"] in matched_names:
                continue
            if match_channel_name(ch["name"], demo_name):
                ch_copy = ch.copy()
                ch_copy["demo_category"] = category
                matched.append(ch_copy)
                matched_names.add(ch["name"])
                matched_demo_items.add(demo_name)
                unmatched.pop(i)
                found = True
                break
        if not found:
            # 可选记录未匹配的 demo
            pass

    # 重要：将未匹配但属于港澳台的频道追加到末尾，避免完全丢失
    # 检查 unmatched 中是否有港澳台频道（通过分类器判断）
    from src.classifier import classify_channel
    hk_tw_unmatched = []
    other_unmatched = []
    for ch in unmatched:
        cat = classify_channel(ch)
        if cat == "港澳台":
            ch_copy = ch.copy()
            ch_copy["demo_category"] = "🌊港·澳·台"   # 或直接使用 "港澳台"
            hk_tw_unmatched.append(ch_copy)
        else:
            other_unmatched.append(ch)
    
    if hk_tw_unmatched:
        print(f"📌 发现 {len(hk_tw_unmatched)} 个港澳台频道未在 demo 中定义，已自动追加到输出")
        matched.extend(hk_tw_unmatched)
        unmatched = other_unmatched

    print(f"🎯 Demo 筛选：原始 {len(channels)} 个频道 -> 匹配 {len(matched)} 个频道，未匹配 {len(unmatched)} 个（匹配模式: {DEMO_MATCH_MODE}）")
    return matched, unmatched

def write_shai_file(unmatched_channels: list, matched_count: int, total_raw: int):
    """输出未匹配的频道到 output/shai.txt"""
    shai_path = OUTPUT_DIR / "shai.txt"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(shai_path, "w", encoding="utf-8") as f:
        f.write(f"# Demo筛选丢弃的频道\n")
        f.write(f"# 原始频道总数: {total_raw}\n")
        f.write(f"# Demo匹配成功: {matched_count}\n")
        f.write(f"# 丢弃数量: {len(unmatched_channels)}\n")
        f.write(f"# 格式: 频道名,URL\n\n")
        for ch in unmatched_channels:
            url = ch["urls"][0] if ch.get("urls") else ch["url"]
            f.write(f"{ch['name']},{url}\n")
    print(f"📄 未匹配频道列表已保存到: {shai_path}")
