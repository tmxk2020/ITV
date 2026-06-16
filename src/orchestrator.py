# src/orchestrator.py
"""协调器 - 整合所有模块，实现自治系统"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from src.logger import logger
from src.database import get_db_cache
from src.source_pool import SourceDiscoverer
from src.candidate import CandidateObserver
from src.stable import StableManager
from src.quality import QualityMonitor
from src.config import (
    ENABLE_DEMO_FILTER, 
    OUTPUT_DIR,
    CANDIDATE_OBSERVATION_HOURS,
    CANDIDATE_MIN_SUCCESS,
    CANDIDATE_MIN_SUCCESS_RATE,
    CANDIDATE_MAX_LATENCY
)
from src.demo_filter import parse_demo_order_with_categories
from src.generator import generate_outputs_from_demo


class IPTVOrchestrator:
    """
    IPTV 自治系统协调器 - 优化版
    
    工作流程:
    1. 发现新源 -> 源池（限制数量）
    2. 从缓存快速观察候选源
    3. 候选源稳定后提升到稳定版
    4. 从稳定版生成输出
    """
    
    MAX_NEW_SOURCES_PER_RUN = 500      # 每次最多处理500个新源
    MAX_OBSERVE_PER_RUN = 300          # 每次最多观察300个候选源
    
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化各模块
        self.discoverer = SourceDiscoverer(self.data_dir / "source_pool.json")
        self.candidate_observer = CandidateObserver(self.data_dir / "candidate_pool.json")
        self.stable_manager = StableManager()
        self.quality_monitor = QualityMonitor(self.stable_manager)
        
        # 运行统计
        self.stats = {
            "last_discover": None,
            "last_observe": None,
            "total_promoted": 0,
            "new_sources_count": 0,
            "observed_count": 0
        }
        
        # 更新候选观察器配置
        CandidateObserver.MIN_SUCCESS_COUNT = CANDIDATE_MIN_SUCCESS
        CandidateObserver.MIN_SUCCESS_RATE = CANDIDATE_MIN_SUCCESS_RATE
        CandidateObserver.MAX_AVG_LATENCY = CANDIDATE_MAX_LATENCY
    
    async def discover_phase(self) -> Dict:
        """阶段1: 发现新源"""
        logger.info("=" * 50)
        logger.info("阶段1: 发现新源")
        logger.info("=" * 50)
        
        try:
            db = await get_db_cache()
            new_sources = await self.discoverer.discover(db)
            
            total_new = sum(len(s) for s in new_sources.values())
            self.stats["new_sources_count"] = total_new
            self.stats["last_discover"] = datetime.now()
            
            if total_new == 0:
                logger.info("✅ 没有发现新源")
                return {}
            
            # 限制新源数量
            if total_new > self.MAX_NEW_SOURCES_PER_RUN:
                logger.warning(f"⚠️ 新源数量 {total_new} 超过限制 {self.MAX_NEW_SOURCES_PER_RUN}，只取前 {self.MAX_NEW_SOURCES_PER_RUN} 个")
            
            # 批量添加到候选池
            added_sources = []
            count = 0
            for channel_name, sources in new_sources.items():
                for src in sources:
                    if count >= self.MAX_NEW_SOURCES_PER_RUN:
                        break
                    added_sources.append((src.get_key(), channel_name, src.url))
                    count += 1
                if count >= self.MAX_NEW_SOURCES_PER_RUN:
                    break
            
            self.candidate_observer.add_candidates_batch(added_sources)
            
            logger.info(f"✅ 发现阶段完成: {len(added_sources)} 个新源进入候选池")
            return new_sources
            
        except asyncio.TimeoutError:
            logger.warning("⚠️ 发现新源阶段超时")
            return {}
        except Exception as e:
            logger.error(f"❌ 发现新源阶段失败: {e}")
            return {}
    
    async def observe_phase(self) -> List:
        """阶段2: 从缓存快速观察候选源"""
        logger.info("=" * 50)
        logger.info("阶段2: 从缓存观察候选源")
        logger.info("=" * 50)
        
        try:
            observing_count = self.candidate_observer.get_observing_count()
            if observing_count == 0:
                logger.info("📭 没有候选源需要观察")
                return []
            
            stable_count = len(self.candidate_observer.get_stable_candidates())
            logger.info(f"📊 候选池状态: {observing_count} 个正在观察，{stable_count} 个已稳定")
            
            # 从缓存观察（快速）
            stable_candidates = await self.candidate_observer.observe_batch_from_cache(
                batch_size=self.MAX_OBSERVE_PER_RUN
            )
            
            self.stats["last_observe"] = datetime.now()
            self.stats["observed_count"] = len(stable_candidates)
            
            logger.info(f"✅ 观察阶段完成: {len(stable_candidates)} 个源达到稳定标准")
            return stable_candidates
            
        except asyncio.TimeoutError:
            logger.warning("⚠️ 观察候选源阶段超时")
            return []
        except Exception as e:
            logger.error(f"❌ 观察候选源阶段失败: {e}")
            return []
    
    async def promote_phase(self, stable_candidates: List = None) -> int:
        """阶段3: 提升稳定源"""
        logger.info("=" * 50)
        logger.info("阶段3: 提升稳定源")
        logger.info("=" * 50)
        
        try:
            if stable_candidates is None:
                stable_candidates = self.candidate_observer.get_stable_candidates()
            
            if not stable_candidates:
                logger.info("📭 没有稳定的候选源需要提升")
                return 0
            
            promoted_count = 0
            for obs in stable_candidates:
                # 检查稳定版是否已有该频道
                existing = self.stable_manager.stable_sources.get(obs.channel_name)
                
                if existing and existing.is_fixed:
                    logger.debug(f"⏭️ {obs.channel_name} 是固定源，跳过自动提升")
                    continue
                
                if existing and existing.latency < obs.avg_latency:
                    logger.debug(f"⏭️ {obs.channel_name} 现有源延迟更低 ({existing.latency} < {obs.avg_latency})")
                    continue
                
                # 提升为稳定源
                if self.stable_manager.promote_candidate(
                    obs.channel_name, obs.url, obs.avg_latency, ""
                ):
                    promoted_count += 1
                    self.candidate_observer.mark_promoted(obs.source_key)
                    logger.info(f"📌 已提升: {obs.channel_name}")
            
            self.stats["total_promoted"] += promoted_count
            logger.info(f"✅ 提升阶段完成: {promoted_count} 个源被提升到稳定版")
            return promoted_count
            
        except Exception as e:
            logger.error(f"❌ 提升稳定源阶段失败: {e}")
            return 0
    
    async def generate_output_phase(self):
        """阶段4: 生成输出"""
        logger.info("=" * 50)
        logger.info("阶段4: 生成输出")
        logger.info("=" * 50)
        
        try:
            channels = self.stable_manager.get_output_channels()
            
            if not channels:
                # 如果没有稳定源，尝试从固定源加载
                logger.warning("⚠️ 没有可输出的稳定源，尝试加载固定源...")
                try:
                    from src.fixed_sources import CCTV_FIXED_SOURCES
                    loaded_count = 0
                    for name, url in CCTV_FIXED_SOURCES.items():
                        if url:
                            self.stable_manager.set_fixed_source(name, url)
                            loaded_count += 1
                    logger.info(f"📌 已加载 {loaded_count} 个固定源")
                    channels = self.stable_manager.get_output_channels()
                except ImportError:
                    logger.warning("⚠️ fixed_sources.py 未找到，跳过固定源加载")
            
            if not channels:
                logger.warning("⚠️ 仍然没有可输出的源，跳过输出生成")
                return
            
            # 获取 demo 顺序
            demo_order = parse_demo_order_with_categories() if ENABLE_DEMO_FILTER else []
            
            # 生成输出
            if demo_order:
                generate_outputs_from_demo(channels, demo_order)
            else:
                from src.generator_enhanced import EnhancedOutputGenerator
                output_gen = EnhancedOutputGenerator()
                output_gen.generate_all_outputs(
                    channels, [], 
                    enable_json=True, 
                    enable_lite=True, 
                    enable_epg=True
                )
            
            logger.info(f"✅ 输出生成完成: {len(channels)} 个稳定源")
            
        except Exception as e:
            logger.error(f"❌ 生成输出阶段失败: {e}")
    
    async def run_once(self) -> Dict:
        """完整执行一次自治流程（带超时控制）"""
        logger.info("🚀 IPTV 自治系统启动")
        logger.info(f"📊 配置: 每批观察 {self.MAX_OBSERVE_PER_RUN} 个")
        
        try:
            # 1. 发现新源（带超时）
            try:
                await asyncio.wait_for(self.discover_phase(), timeout=60)
            except asyncio.TimeoutError:
                logger.warning("⚠️ 发现新源阶段超时，跳过")
            except Exception as e:
                logger.error(f"❌ 发现新源阶段异常: {e}")
            
            # 2. 从缓存观察候选源（带超时）
            stable_candidates = []
            try:
                stable_candidates = await asyncio.wait_for(self.observe_phase(), timeout=30)
            except asyncio.TimeoutError:
                logger.warning("⚠️ 观察候选源阶段超时，跳过")
            except Exception as e:
                logger.error(f"❌ 观察候选源阶段异常: {e}")
            
            # 3. 提升稳定源（带超时）
            try:
                await asyncio.wait_for(self.promote_phase(stable_candidates), timeout=30)
            except asyncio.TimeoutError:
                logger.warning("⚠️ 提升稳定源阶段超时，跳过")
            except Exception as e:
                logger.error(f"❌ 提升稳定源阶段异常: {e}")
            
            # 4. 生成输出
            await self.generate_output_phase()
            
            # 打印统计
            logger.info("=" * 50)
            logger.info("📊 运行统计")
            logger.info("=" * 50)
            logger.info(f"  源池总数: {self.discoverer.get_statistics()['total']}")
            logger.info(f"  候选池总数: {self.candidate_observer.get_statistics()['total']}")
            logger.info(f"  候选池观察中: {self.candidate_observer.get_statistics()['observing']}")
            logger.info(f"  稳定源数量: {len(self.stable_manager.get_active_sources())}")
            logger.info(f"  固定源数量: {sum(1 for s in self.stable_manager.stable_sources.values() if s.is_fixed)}")
            logger.info(f"  累计提升: {self.stats['total_promoted']}")
            
        except Exception as e:
            logger.exception(f"❌ 自治流程执行失败: {e}")
        
        return self.stats


# 全局实例
_orchestrator = None


def get_orchestrator() -> IPTVOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = IPTVOrchestrator()
    return _orchestrator


async def run_autonomous_mode():
    """运行自治模式"""
    orchestrator = get_orchestrator()
    return await orchestrator.run_once()
