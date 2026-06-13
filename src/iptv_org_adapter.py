# src/iptv_org_adapter.py
"""iptv-org 官方源适配器：提供高质量全球频道、EPG ID 和元数据"""

import re
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

import aiohttp
from src.config import IPTV_ORG_ENABLE, IPTV_ORG_CDN, CACHE_HOURS
from src.logger import logger

@dataclass
class ChannelMetadata:
    """iptv-org 频道元数据"""
    id: str           # 频道唯一ID，如 "CCTV1.cn"
    name: str         # 频道名称
    network: str      # 所属网络，如 "CCTV"
    country: str      # 国家代码，如 "CN"
    languages: List[str]  # 语言列表
    categories: List[str] # 分类
    logo: str         # Logo URL
    epg_url: str      # EPG 数据源

class IPTVOrgAdapter:
    """iptv-org API 适配器"""
    
    def __init__(self):
        self.base_url = "https://iptv-org.github.io"
        self.api_url = "https://iptv-org.github.io/api"
        self.enabled = IPTV_ORG_ENABLE
        self.cache: Dict[str, ChannelMetadata] = {}
        
        # 国内常用频道的 ID 映射（硬编码核心频道）
        self.channel_id_map = self._load_channel_id_map()
    
    def _load_channel_id_map(self) -> Dict[str, str]:
        """加载频道名到 iptv-org ID 的映射表"""
        return {
            # 央视系列
            "CCTV-1": "CCTV1.cn",
            "CCTV-2": "CCTV2.cn",
            "CCTV-3": "CCTV3.cn",
            "CCTV-4": "CCTV4.cn",
            "CCTV-5": "CCTV5.cn",
            "CCTV-5+": "CCTV5Plus.cn",
            "CCTV-6": "CCTV6.cn",
            "CCTV-7": "CCTV7.cn",
            "CCTV-8": "CCTV8.cn",
            "CCTV-9": "CCTV9.cn",
            "CCTV-10": "CCTV10.cn",
            "CCTV-11": "CCTV11.cn",
            "CCTV-12": "CCTV12.cn",
            "CCTV-13": "CCTV13.cn",
            "CCTV-14": "CCTV14.cn",
            "CCTV-15": "CCTV15.cn",
            "CCTV-16": "CCTV16.cn",
            "CCTV-17": "CCTV17.cn",
            "CGTN": "CGTN.cn",
            "CGTN俄语": "CGTNRussian.cn",
            
            # 卫视系列
            "湖南卫视": "HunanTV.cn",
            "浙江卫视": "ZhejiangTV.cn",
            "江苏卫视": "JiangsuTV.cn",
            "东方卫视": "DragonTV.cn",
            "北京卫视": "BTV1.cn",
            "广东卫视": "GuangdongTV.cn",
            "深圳卫视": "SZTV.cn",
            "天津卫视": "TianjinTV.cn",
            "山东卫视": "ShandongTV.cn",
            "安徽卫视": "AnhuiTV.cn",
            "湖北卫视": "HubeiTV.cn",
            "黑龙江卫视": "HeilongjiangTV.cn",
            "江西卫视": "JiangxiTV.cn",
            "河南卫视": "HenanTV.cn",
            "河北卫视": "HebeiTV.cn",
            "山西卫视": "ShanxiTV.cn",
            "陕西卫视": "ShaanxiTV.cn",
            "甘肃卫视": "GansuTV.cn",
            "宁夏卫视": "NingxiaTV.cn",
            "青海卫视": "QinghaiTV.cn",
            "云南卫视": "YunnanTV.cn",
            "贵州卫视": "GuizhouTV.cn",
            "广西卫视": "GuangxiTV.cn",
            "内蒙古卫视": "NeimengguTV.cn",
            "新疆卫视": "XinjiangTV.cn",
            "西藏卫视": "XizangTV.cn",
            "海南卫视": "HainanTV.cn",
            "东南卫视": "SETV.cn",
            "重庆卫视": "ChongqingTV.cn",
            "四川卫视": "SichuanTV.cn",
            "辽宁卫视": "LiaoningTV.cn",
            "吉林卫视": "JilinTV.cn",
            "厦门卫视": "XiamenStar.cn",
            
            # 港澳台系列
            "凤凰中文": "PhoenixCNHD.hk",
            "凤凰资讯": "PhoenixInfohk.hk",
            "翡翠台": "TVBJade.hk",
            "明珠台": "TVBPearl.hk",
            "TVB无线新闻": "TVBNews.hk",
            "东森综合": "ETTV.ttv",
            "中视": "CTV.ttv",
            "华视": "CTS.ttv",
            "台视": "TTV.ttv",
            "民视": "FTV.ttv",
        }
    
    async def fetch_global_channels(self) -> Optional[List[Dict]]:
        """获取 iptv-org 的全球频道列表（仅限中国及常用海外频道）"""
        if not self.enabled:
            logger.info("🌍 iptv-org 适配器已禁用")
            return None
        
        try:
            # 获取所有频道
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/channels.json", timeout=15) as resp:
                    if resp.status != 200:
                        logger.warning(f"⚠️ iptv-org API 请求失败: {resp.status}")
                        return None
                    all_channels = await resp.json()
            
            # 过滤：中国频道 + 热门英文频道
            filtered = []
            for ch in all_channels:
                country = ch.get("country", "")
                lang = ch.get("languages", [])
                category = ch.get("categories", [])
                
                # 保留中国频道
                if country == "CN":
                    filtered.append(ch)
                # 保留热门英文新闻频道
                elif country == "US" and "news" in str(category).lower():
                    filtered.append(ch)
                # 保留部分国际知名频道
                elif ch.get("id") in ["BBCWorldNews.uk", "CNN.us", "SkyNews.uk"]:
                    filtered.append(ch)
            
            logger.info(f"🌍 从 iptv-org 加载了 {len(filtered)} 个全球频道")
            return filtered
            
        except Exception as e:
            logger.error(f"❌ iptv-org 适配器异常: {e}")
            return None
    
    def get_epg_id(self, channel_name: str) -> Optional[str]:
        """获取频道的 EPG ID"""
        # 精确匹配
        if channel_name in self.channel_id_map:
            return self.channel_id_map[channel_name]
        
        # 模糊匹配（处理 CCTV-1 综合 等变体）
        name_lower = channel_name.lower()
        for std_name, epg_id in self.channel_id_map.items():
            if std_name.lower() in name_lower:
                return epg_id
        
        return None
    
    def get_logo_url(self, epg_id: str) -> str:
        """获取频道 Logo URL"""
        return f"{IPTV_ORG_CDN}/logos/{epg_id}.png"
    
    async def get_epg_data(self, epg_id: str, date: str = None) -> Optional[Dict]:
        """获取 EPG 节目单数据（可选）"""
        # 集成 iptv-org/epg 项目
        if not IPTV_ORG_ENABLE:
            return None
        
        epg_url = f"https://iptv-org.github.io/epg/guides/{epg_id}.json"
        if date:
            epg_url += f"?date={date}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(epg_url, timeout=10) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception:
            pass
        return None

# 全局实例
_adapter = None

def get_iptv_org_adapter() -> IPTVOrgAdapter:
    global _adapter
    if _adapter is None:
        _adapter = IPTVOrgAdapter()
    return _adapter
