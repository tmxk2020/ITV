# build.spec
# PyInstaller 打包配置文件

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['src/main.py'],                     # 入口文件
    pathex=[],
    binaries=[],
    datas=[
        ('alias.txt', '.'),              # 别名文件
        ('blacklist.txt', '.'),          # 黑名单文件
        ('demo.txt', '.'),               # Demo 文件
        ('resources', 'resources'),      # 图标资源
    ],
    hiddenimports=[
        # 核心模块
        'src.config',
        'src.run',
        'src.fetcher',
        'src.parser',
        'src.speed_tester',
        'src.ffmpeg_validator',
        'src.merger',
        'src.generator',
        'src.demo_filter',
        'src.classifier',
        'src.blacklist_filter',
        'src.database',
        'src.logger',
        'src.alias_matcher',
        'src.fixed_sources',
        # 自治模式模块
        'src.stable',
        'src.stable.manager',
        'src.source_pool',
        'src.source_pool.discoverer',
        'src.candidate',
        'src.candidate.observer',
        'src.quality',
        'src.quality.monitor',
        'src.orchestrator',
        # 扩展功能
        'src.iptv_org_adapter',
        'src.global_channels',
        'src.generator_enhanced',
        'src.overseas_filter',
        'src.special_categories',
        # GUI 模块
        'src.gui',
        'src.gui.main_window',
        'src.gui.widgets',
        'src.gui.styles',
        # 工具模块
        'src.utils',
        'src.utils.logger_handler',
        # 第三方库
        'pypinyin',
        'pypinyin.core',
        'pypinyin.style',
        'aiohttp',
        'aiosqlite',
        'tqdm',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyd = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyd,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='IPTV_Manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 显示控制台，方便查看日志
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/icon.ico' if sys.platform == 'win32' else None,
)
