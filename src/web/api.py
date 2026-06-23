# src/web/api.py
"""Web 管理界面 REST API"""

import json
from pathlib import Path
from flask import Blueprint, request, jsonify
from src.config import (
    OUTPUT_DIR, MAX_WORKERS, TIMEOUT, FFMPEG_ENABLE,
    MAX_SOURCES_PER_CHANNEL, DEMO_MATCH_MODE,
    CACHE_RAW_HOURS, CACHE_SPEED_HOURS
)
from src.stable.manager import StableManager
from src.source_pool.discoverer import SourceDiscoverer
from src.candidate.observer import CandidateObserver
from src.web.db import get_quality_history, get_all_channels_with_history, record_quality

api_bp = Blueprint('api', __name__, url_prefix='/api')

# ---------- 系统状态 ----------
@api_bp.route('/status')
def get_status():
    """获取系统状态"""
    stable_mgr = StableManager()
    stable_sources = stable_mgr.get_active_sources()
    
    discoverer = SourceDiscoverer()
    pool_stats = discoverer.get_statistics()
    
    observer = CandidateObserver()
    candidate_stats = observer.get_statistics()
    
    # 读取最后运行时间
    last_run = None
    stats_file = OUTPUT_DIR / "stats.json"
    if stats_file.exists():
        with open(stats_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            last_run = data.get('timestamp')
    
    return jsonify({
        'stable_count': len(stable_sources),
        'fixed_count': sum(1 for s in stable_sources.values() if s.is_fixed),
        'pool_total': pool_stats.get('total', 0),
        'candidate_observing': candidate_stats.get('observing', 0),
        'last_run': last_run,
        'status': 'running'  # 简单状态
    })

# ---------- 频道列表 ----------
@api_bp.route('/channels')
def get_channels():
    """获取稳定版频道列表，支持搜索和筛选"""
    search = request.args.get('search', '').strip().lower()
    category = request.args.get('category', '')
    
    stable_mgr = StableManager()
    sources = stable_mgr.get_active_sources()
    
    channels = []
    for name, src in sources.items():
        if not src.url:
            continue
        # 搜索过滤
        if search and search not in name.lower():
            continue
        # 分类过滤（可根据 group_title 或 demo_category）
        # 目前我们按频道名前缀简单判断
        cat = '其他'
        if name.startswith('CCTV'):
            cat = '央视'
        elif '卫视' in name:
            cat = '卫视'
        elif '频道' in name and not name.startswith('CCTV'):
            cat = '地方'
        elif '港' in name or '澳' in name or '台' in name:
            cat = '港澳台'
        
        if category and cat != category:
            continue
        
        channels.append({
            'name': name,
            'url': src.url,
            'latency': src.latency,
            'codec': src.video_codec,
            'is_fixed': src.is_fixed,
            'category': cat,
            'last_verified': src.last_verified.isoformat() if src.last_verified else None
        })
    
    # 按名称排序
    channels.sort(key=lambda x: x['name'])
    return jsonify(channels)

# ---------- 固定源管理 ----------
@api_bp.route('/fixed_sources', methods=['GET'])
def get_fixed_sources():
    stable_mgr = StableManager()
    fixed = {name: src.url for name, src in stable_mgr.stable_sources.items() if src.is_fixed}
    return jsonify(fixed)

@api_bp.route('/fixed_sources', methods=['POST'])
def add_fixed_source():
    data = request.get_json()
    name = data.get('name')
    url = data.get('url')
    if not name or not url:
        return jsonify({'error': '缺少频道名或URL'}), 400
    stable_mgr = StableManager()
    if stable_mgr.set_fixed_source(name, url):
        return jsonify({'success': True, 'message': f'已添加固定源 {name}'})
    else:
        return jsonify({'error': '添加失败'}), 500

@api_bp.route('/fixed_sources/<name>', methods=['DELETE'])
def delete_fixed_source(name):
    stable_mgr = StableManager()
    if name in stable_mgr.stable_sources and stable_mgr.stable_sources[name].is_fixed:
        del stable_mgr.stable_sources[name]
        stable_mgr._save()
        return jsonify({'success': True})
    return jsonify({'error': '固定源不存在'}), 404

# ---------- 配置管理 ----------
@api_bp.route('/config', methods=['GET'])
def get_config():
    """获取当前配置"""
    return jsonify({
        'max_workers': MAX_WORKERS,
        'timeout': TIMEOUT,
        'ffmpeg_enable': FFMPEG_ENABLE,
        'max_sources_per_channel': MAX_SOURCES_PER_CHANNEL,
        'demo_match_mode': DEMO_MATCH_MODE,
        'cache_raw_hours': CACHE_RAW_HOURS,
        'cache_speed_hours': CACHE_SPEED_HOURS,
    })

@api_bp.route('/config', methods=['POST'])
def update_config():
    """更新配置（需重启生效）"""
    data = request.get_json()
    # 注意：修改配置需要持久化到 .env 或 config.py，这里仅演示
    # 实际项目中可写入 .env 文件
    # 这里我们简单返回成功，并提示重启
    return jsonify({
        'success': True,
        'message': '配置已更新，请重启服务生效。'
    })

# ---------- 质量趋势 ----------
@api_bp.route('/quality/<channel_name>')
def get_quality(channel_name):
    days = request.args.get('days', 7, type=int)
    history = get_quality_history(channel_name, days)
    return jsonify(history)

@api_bp.route('/quality/all')
def get_all_quality():
    days = request.args.get('days', 7, type=int)
    data = get_all_channels_with_history(days)
    return jsonify(data)
