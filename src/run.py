#!/usr/bin/env python3
# src/run.py

import asyncio
import sys
import json
import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import (
    IPTV_SOURCES, ENABLE_REGION_FILTER, PREFERRED_LOCATION, PREFERRED_ISP,
    ENABLE_IP_RESOLVE, ENABLE_DEMO_FILTER, ENABLE_ALIAS, ENABLE_BLACKLIST,
    DATABASE_ENABLE, CACHE_RAW_HOURS, CACHE_SPEED_HOURS, DATABASE_TABLE,
    OUTPUT_DIR, MAX_WORKERS, TIMEOUT, FFMPEG_ENABLE
)
from src.fetcher import fetch_all_sources_incremental
from src.parser import parse_and_dedupe
from src.speed_tester import test_channels_concurrent
from src.ffmpeg_validator import validate_batch, cleanup as ffmpeg_cleanup
from src.generator import generate_outputs_from_demo
from src.merger import merge_channels_by_name
from src.ip_resolver import get_resolver, matches_region
from src.blacklist_filter import get_blacklist_filter
from src.demo_filter import filter_and_order_by_demo, write_shai_file
from src.alias_matcher import get_alias_matcher
from src.database import get_db_cache, channel_key
from src.logger import logger

async def init_ip_resolver():
    if not ENABLE_IP_RESOLVE:
        logger.info("⚙️ IP解析未启用")
        return
    resolver = get_resolver()
    if resolver.is_available:
        logger.info("✅ IP解析器已就绪")
    else:
        logger.warning("⚠️ IP解析器不可用，将跳过地域筛选")

def filter_by_region(channels):
    if not ENABLE_REGION_FILTER:
        return channels
    preferred_locations = [loc.strip() for loc in PREFERRED_LOCATION.split(",") if loc.strip()]
    preferred_isps = [isp.strip() for isp in PREFERRED_ISP.split(",") if isp.strip()]
    if not preferred_locations and not preferred_isps:
        return channels
    logger.info(f"🎯 地域筛选: 地域={preferred_locations}, 运营商={preferred_isps}")
    resolver = get_resolver()
    if not resolver.is_available:
        logger.warning("⚠️ IP解析器不可用，跳过地域筛选")
        return channels
    filtered = []
    for ch in channels:
        ip_info = ch.get("ip_info")
        if ip_info and matches_region(ip_info, preferred_locations, preferred_isps):
            filtered.append(ch)
    logger.info(f"  筛选结果: {len(filtered)}/{len(channels)} 个频道通过地域筛选")
    return filtered

async def save_to_cache(db, channels):
    for ch in channels:
        key = channel_key(ch["name"], ch["url"])
        await db.set_speed_result(key, ch)
    logger.info(f"💾 已保存 {len(channels)} 个频道源到数据库缓存")

async def load_merged_from_db(db) -> list:
    if not db._conn:
        return []
    table = f"{DATABASE_TABLE}_speed"
    expire_time = datetime.datetime.now() - datetime.timedelta(hours=CACHE_SPEED_HOURS)
    cursor = await db._conn.execute(
        f"SELECT name, url, latency, video_codec, ip_info, updated_at FROM {table} WHERE updated_at > ?",
        (expire_time.isoformat(),)
    )
    rows = await cursor.fetchall()
    await cursor.close()
    if not rows:
        return []
    valid_channels = []
    for row in rows:
        name, url, latency, video_codec, ip_info_json, _ = row
        ch = {
            "name": name,
            "url": url,
            "latency": latency,
            "video_codec": video_codec,
            "ip_info": json.loads(ip_info_json) if ip_info_json else None
        }
        valid_channels.append(ch)
    merged = merge_channels_by_name(valid_channels)
    logger.info(f"📂 从数据库加载并合并，得到 {len(merged)} 个频道")
    return merged

async def main():
    logger.info("🚀 IPTV智能整理平台启动")
    logger.info(f"📡 配置：超时={TIMEOUT}s, 并发={MAX_WORKERS}, ffmpeg={FFMPEG_ENABLE}")
    logger.info(f"📋 增强过滤: demo={ENABLE_DEMO_FILTER}, alias={ENABLE_ALIAS}, blacklist={ENABLE_BLACKLIST}")

    await init_ip_resolver()
    if FFMPEG_ENABLE:
        from src.ffmpeg_validator import check_ffprobe
        await check_ffprobe()

    db = await get_db_cache()
    if DATABASE_ENABLE:
        await db.cleanup_expired(raw_hours=CACHE_RAW_HOURS, speed_hours=CACHE_SPEED_HOURS)

    logger.info("\n📥 执行增量源检测和拉取...")
    raw_contents = await fetch_all_sources_incremental(IPTV_SOURCES, db)
    
    channels_dict = parse_and_dedupe(raw_contents)
    if not channels_dict:
        logger.error("❌ 未获取到任何频道，尝试使用数据库缓存")
        merged_channels = await load_merged_from_db(db)
        if not merged_channels:
            logger.error("❌ 无任何频道数据，退出")
            return 1
    else:
        logger.info(f"📊 原始频道数（去重后）: {len(channels_dict)}")

        valid_channels = await test_channels_concurrent(channels_dict)
        logger.info(f"📊 通过HTTP测速的频道数: {len(valid_channels)}")

        valid_channels = await validate_batch(valid_channels)
        logger.info(f"📊 通过ffmpeg深度验证的频道数: {len(valid_channels)}")

        if DATABASE_ENABLE and valid_channels:
            await save_to_cache(db, valid_channels)
            await db.set_last_update_time()

        merged_channels = merge_channels_by_name(valid_channels)
        logger.info(f"📊 合并后的频道数: {len(merged_channels)}")

    if ENABLE_BLACKLIST:
        blacklist_filter = get_blacklist_filter()
        before = len(merged_channels)
        merged_channels = blacklist_filter.filter_channels(merged_channels)
        logger.info(f"📊 黑名单过滤后: {len(merged_channels)} (减少 {before - len(merged_channels)})")

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

    ordered_channels = filter_by_region(ordered_channels)
    if not ordered_channels:
        logger.error("❌ 过滤后无有效频道")
        return 1

    generate_outputs_from_demo(ordered_channels)

    total = len(ordered_channels)
    logger.info(f"🎉 完成！有效频道总数: {total}")
    
    stats = {
        "total_channels": total,
        "timestamp": datetime.datetime.now().isoformat(),
        "config": {
            "max_workers": MAX_WORKERS,
            "timeout": TIMEOUT,
            "ffmpeg_enable": FFMPEG_ENABLE,
            "demo_filter": ENABLE_DEMO_FILTER,
        }
    }
    stats_path = OUTPUT_DIR / "stats.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    logger.info(f"📊 统计信息已保存至 {stats_path}")
    
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
