# build.spec
# PyInstaller 打包配置文件

import sys
from pathlib import Path

# 确保 resources 目录存在
Path('resources').mkdir(exist_ok=True)

block_cipher = None

icon_path = Path('resources/icon.ico')
if icon_path.exists():
    icon_file = str(icon_path)
else:
    icon_file = None

a = Analysis(
    ['src/main.py'],
    pathex=[str(Path('.')), str(Path('src'))],   # 添加 src 到搜索路径
    binaries=[],
    datas=[
        ('alias.txt', '.'),
        ('blacklist.txt', '.'),
        ('demo.txt', '.'),
        ('resources', 'resources'),
        ('src', 'src'),                          # 关键：将整个 src 目录复制到打包目录
    ],
    hiddenimports=[
        # 所有需要用到的模块
        'src',
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
        'src.stable',
        'src.stable.manager',
        'src.source_pool',
        'src.source_pool.discoverer',
        'src.candidate',
        'src.candidate.observer',
        'src.quality',
        'src.quality.monitor',
        'src.orchestrator',
        'src.iptv_org_adapter',
        'src.global_channels',
        'src.generator_enhanced',
        'src.overseas_filter',
        'src.special_categories',
        'src.gui',
        'src.gui.main_window',
        'src.gui.widgets',
        'src.gui.styles',
        'src.utils',
        'src.utils.logger_handler',
        'pypinyin',
        'pypinyin.core',
        'pypinyin.style',
        'aiohttp',
        'aiosqlite',
        'tqdm',
        'PySide6',
        'shiboken6',
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
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file if (sys.platform == 'win32' and icon_file) else None,
)
