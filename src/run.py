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
    IPTV_SOURCES, ENABLE_DEMO_FILTER, ENABLE_ALIAS, ENABLE_BLACKLIST,
    DATABASE_ENABLE, CACHE_HOURS, OUTPUT_DIR, MAX_WORKERS, TIMEOUT, FFMPEG_ENABLE,
    RUN_MODE, SCHEDULE_INTERVAL, WEB_SERVER_PORT, WEB_SERVER_HOST
)
from src.fetcher import fetch_all_sources_incremental
from src.parser import parse_and_dedupe
from src.speed_tester import test_channels_concurrent
from src.ffmpeg_validator import validate_batch, cleanup as ffmpeg_cleanup
from src.generator import generate_outputs_from_demo
from src.merger import merge_channels_by_name
from src.blacklist_filter import get_blacklist_filter
from src.demo_filter import filter_and_order_by_demo, write_shai_file, parse_demo_order_with_categories
from src.database import get_db_cache
from src.logger import logger

async def main():
    logger.info("🚀 IPTV 智能整理平台启动")
    logger.info(f"📡 配置：超时={TIMEOUT}s, 并发={MAX_WORKERS}, ffmpeg={FFMPEG_ENABLE}")
    logger.info(f"📋 增强过滤: demo={ENABLE_DEMO_FILTER}, alias={ENABLE_ALIAS}, blacklist={ENABLE_BLACKLIST}")

    # 获取 demo 顺序
    demo_order = parse_demo_order_with_categories() if ENABLE_DEMO_FILTER else []
    logger.info(f"📋 Demo 顺序: {len(demo_order)} 个频道")

    db = await get_db_cache()

    logger.info("\n📥 拉取 IPTV 源...")
    raw_contents = await fetch_all_sources_incremental(IPTV_SOURCES, db)
    
    channels_dict = parse_and_dedupe(raw_contents)
    if not channels_dict:
        logger.error("❌ 未获取到任何频道")
        return 1

    logger.info(f"📊 原始频道数（去重后）: {len(channels_dict)}")

    # HTTP 测速
    valid_channels = await test_channels_concurrent(channels_dict)
    logger.info(f"📊 通过HTTP测速的频道数: {len(valid_channels)}")

    # ffmpeg 验证
    if FFMPEG_ENABLE:
        valid_channels = await validate_batch(valid_channels)
        logger.info(f"📊 通过ffmpeg验证的频道数: {len(valid_channels)}")

    # 保存到数据库
    if DATABASE_ENABLE and valid_channels:
        await db.save_speed_results(valid_channels)
        await db.set_last_update_time()

    # 合并频道
    merged_channels = merge_channels_by_name(valid_channels)
    logger.info(f"📊 合并后的频道数: {len(merged_channels)}")

    # 黑名单过滤
    if ENABLE_BLACKLIST:
        blacklist_filter = get_blacklist_filter()
        before = len(merged_channels)
        merged_channels = blacklist_filter.filter_channels(merged_channels)
        logger.info(f"📊 黑名单过滤后: {len(merged_channels)} (减少 {before - len(merged_channels)})")

    # Demo 筛选
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

    # 最终统计
    cat_counter = Counter(ch.get("demo_category", "其他") for ch in ordered_channels)
    logger.info("\n🎉 最终有效频道分类统计：")
    for cat, cnt in cat_counter.items():
        logger.info(f"  {cat}: {cnt} 个频道")

    # 生成输出文件（传入 demo_order 保持顺序）
    generate_outputs_from_demo(ordered_channels, demo_order)

    total = len(ordered_channels)
    logger.info(f"🎉 完成！有效频道总数: {total}")
    
    # 保存统计
    stats = {
        "total_channels": total,
        "timestamp": datetime.datetime.now().isoformat(),
        "category_stats": dict(cat_counter)
    }
    stats_path = OUTPUT_DIR / "stats.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
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
