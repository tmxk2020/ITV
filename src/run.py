#!/usr/bin/env python3
# src/run.py

import asyncio
import sys
import json
import datetime
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import (
    IPTV_SOURCES,
    ENABLE_DEMO_FILTER,
    ENABLE_ALIAS,
    ENABLE_BLACKLIST,
    DATABASE_ENABLE,
    OUTPUT_DIR,
    MAX_WORKERS,
    TIMEOUT,
    FFMPEG_ENABLE,
    ENABLE_GLOBAL_CHANNELS,
    ENABLE_JSON_OUTPUT,
    ENABLE_LITE_VERSION,
    ENABLE_EPG_OUTPUT,
    ENABLE_INCREMENTAL_FETCH,
    CACHE_RAW_HOURS,
    IPTV_ORG_ENABLE,
)
from src.fetcher import fetch_all_sources_incremental
from src.parser import parse_and_dedupe
from src.speed_tester import test_channels_concurrent
from src.ffmpeg_validator import validate_batch, cleanup as ffmpeg_cleanup
from src.generator import generate_outputs_from_demo
from src.merger import merge_channels_by_name
from src.blacklist_filter import get_blacklist_filter
from src.demo_filter import (
    filter_and_order_by_demo,
    write_shai_file,
    parse_demo_order_with_categories,
)
from src.database import get_db_cache
from src.logger import logger

# 新增导入
from src.iptv_org_adapter import get_iptv_org_adapter
from src.global_channels import get_global_selector
from src.generator_enhanced import EnhancedOutputGenerator
from src.overseas_filter import process_overseas_channels


async def main():
    logger.info("🚀 IPTV 智能整理平台启动")
    logger.info(f"📡 配置：超时={TIMEOUT}s, 并发={MAX_WORKERS}, ffmpeg={FFMPEG_ENABLE}")
    logger.info(
        f"📋 增强过滤: demo={ENABLE_DEMO_FILTER}, alias={ENABLE_ALIAS}, blacklist={ENABLE_BLACKLIST}"
    )
    
    # 打印 iptv-org 状态
    if IPTV_ORG_ENABLE:
        logger.info("🌍 iptv-org 融合模式已启用")
        if ENABLE_GLOBAL_CHANNELS:
            logger.info("🌍 全球频道扩展已启用")
        else:
            logger.info("🌍 全球频道扩展已禁用（可通过 ENABLE_GLOBAL_CHANNELS=true 启用）")

    # 获取 demo 顺序（用于输出排序）
    demo_order = parse_demo_order_with_categories() if ENABLE_DEMO_FILTER else []
    logger.info(f"📋 Demo 顺序: {len(demo_order)} 个频道")

    # 初始化数据库
    db = await get_db_cache()

    # ========== 增量更新模式检查 ==========
    raw_contents = {}
    last_update = await db.get_last_update_time() if DATABASE_ENABLE else None
    is_fresh = last_update and (datetime.datetime.now().timestamp() - last_update) < CACHE_RAW_HOURS * 3600
    
    if is_fresh and ENABLE_INCREMENTAL_FETCH:
        logger.info("⚡ 启用增量更新模式（缓存有效，跳过重复拉取）")
        # 从缓存加载已有内容
        for url in IPTV_SOURCES:
            cached = await db.get_raw_source(url)
            if cached:
                raw_contents[url] = cached
                logger.debug(f"📦 从缓存加载: {url}")
            else:
                # 缓存未命中才拉取
                logger.info(f"🔄 缓存未命中，拉取: {url}")
                fetched = await fetch_all_sources_incremental([url], db)
                raw_contents.update(fetched)
    else:
        if last_update:
            logger.info(f"📊 缓存已过期（最后更新: {datetime.datetime.fromtimestamp(last_update)}），执行完整采集")
        else:
            logger.info("📊 首次运行，执行完整采集")
        raw_contents = await fetch_all_sources_incremental(IPTV_SOURCES, db)

    # 解析并去重
    channels_dict = parse_and_dedupe(raw_contents)
    if not channels_dict:
        logger.error("❌ 未获取到任何频道")
        return 1

    logger.info(f"📊 原始频道数（去重后）: {len(channels_dict)}")

    # HTTP 测速（过滤无效/广告源）
    valid_channels = await test_channels_concurrent(channels_dict)
    logger.info(f"📊 通过HTTP测速的频道数: {len(valid_channels)}")

    # ffmpeg 深度验证
    if FFMPEG_ENABLE:
        valid_channels = await validate_batch(valid_channels)
        logger.info(f"📊 通过ffmpeg验证的频道数: {len(valid_channels)}")

    # 保存测速结果到数据库
    if DATABASE_ENABLE and valid_channels:
        await db.save_speed_results(valid_channels)
        await db.set_last_update_time()

    # 合并频道（H.264 优先 + 延迟排序，固定源优先）
    merged_channels = merge_channels_by_name(valid_channels)
    logger.info(f"📊 合并后的频道数: {len(merged_channels)}")

    # 黑名单过滤
    if ENABLE_BLACKLIST:
        blacklist_filter = get_blacklist_filter()
        before = len(merged_channels)
        merged_channels = blacklist_filter.filter_channels(merged_channels)
        logger.info(f"📊 黑名单过滤后: {len(merged_channels)} (减少 {before - len(merged_channels)})")

    # Demo 筛选（按 demo.txt 顺序匹配和归类）
    unmatched_channels = []
    if ENABLE_DEMO_FILTER:
        before = len(merged_channels)
        ordered_channels, unmatched_channels = filter_and_order_by_demo(merged_channels)
        logger.info(f"📊 Demo筛选后: {len(ordered_channels)} (减少 {before - len(ordered_channels)})")

        if unmatched_channels:
            write_shai_file(unmatched_channels, len(ordered_channels), before)

        if not ordered_channels:
            logger.warning("❌ Demo 筛选后无频道，尝试不筛选")
            ordered_channels = merged_channels
    else:
        ordered_channels = merged_channels

    if not ordered_channels:
        logger.error("❌ 过滤后无有效频道")
        return 1

    # ========== 全球频道扩展 ==========
    if ENABLE_GLOBAL_CHANNELS:
        logger.info("🌍 正在合并全球频道...")
        global_selector = get_global_selector()
        ordered_channels = await global_selector.merge_with_domestic(ordered_channels)

    # 最终分类统计
    cat_counter = Counter(ch.get("demo_category", "其他") for ch in ordered_channels)
    logger.info("\n🎉 最终有效频道分类统计：")
    for cat, cnt in cat_counter.items():
        logger.info(f"  {cat}: {cnt} 个频道")

    # ========== 生成标准输出（保持原有兼容性） ==========
    generate_outputs_from_demo(ordered_channels, demo_order)

    # ========== 生成增强版输出（新增功能） ==========
    output_gen = EnhancedOutputGenerator()
    output_gen.generate_all_outputs(
        ordered_channels, 
        demo_order,
        enable_json=ENABLE_JSON_OUTPUT,
        enable_lite=ENABLE_LITE_VERSION,
        enable_epg=ENABLE_EPG_OUTPUT
    )

    # ========== 处理国外频道（从未匹配的频道中筛选） ==========
    if ENABLE_DEMO_FILTER and unmatched_channels:
        logger.info(f"🌍 正在处理 {len(unmatched_channels)} 个未匹配频道（国外频道）...")
        process_overseas_channels(unmatched_channels, OUTPUT_DIR)
    else:
        logger.info("⏭️ 未启用 demo 筛选或无未匹配频道，跳过国外频道处理")

    total = len(ordered_channels)
    logger.info(f"🎉 完成！有效频道总数: {total}")

    # 保存统计信息
    stats = {
        "total_channels": total,
        "timestamp": datetime.datetime.now().isoformat(),
        "category_stats": dict(cat_counter),
        "unmatched_count": len(unmatched_channels) if unmatched_channels else 0,
        "features": {
            "iptv_org_enabled": IPTV_ORG_ENABLE,
            "global_channels_enabled": ENABLE_GLOBAL_CHANNELS,
            "epg_injection_enabled": ENABLE_EPG_OUTPUT,
            "incremental_mode": is_fresh and ENABLE_INCREMENTAL_FETCH
        }
    }
    stats_path = OUTPUT_DIR / "stats.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

        # ========== 采集特色分类内容并追加到输出文件 ==========
    from src.special_categories import collect_and_append_special_categories
    
    try:
        special_stats = await collect_and_append_special_categories(OUTPUT_DIR, db)
        if special_stats:
            stats["special_categories"] = special_stats
            logger.info("🎉 特色分类内容已追加到输出文件")
    except Exception as e:
        logger.warning(f"⚠️ 特色分类采集失败: {e}")
        
    # 清理资源
    ffmpeg_cleanup()
    await db.close()
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.warning("\n⚠️ 用户中断")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"❌ 发生错误: {e}")
        sys.exit(1)
