# src/alias_matcher.py
# 别名匹配模块，仅支持精确匹配和正则匹配，无子串匹配

import re
from pathlib import Path
from typing import Dict, Optional

from src.config import ALIAS_FILE, ENABLE_ALIAS

class AliasMatcher:
    def __init__(self, alias_file: Path = ALIAS_FILE):
        self.alias_file = alias_file
        self.exact_mappings: Dict[str, str] = {}      # 完全相等（忽略大小写）
        self.regex_mappings: Dict[re.Pattern, str] = {}
        self._load()

    def _load(self):
        if not self.alias_file.exists():
            print(f"⚠️ 别名文件不存在: {self.alias_file}")
            return
        with open(self.alias_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split(',')
                if len(parts) < 2:
                    print(f"⚠️ 别名文件第 {line_num} 行格式错误，跳过: {line}")
                    continue
                standard = parts[0].strip()
                aliases = parts[1:]
                for alias in aliases:
                    alias = alias.strip()
                    if not alias:
                        continue
                    if alias.startswith('re:'):
                        pattern_str = alias[3:].strip()
                        try:
                            pattern = re.compile(pattern_str, re.IGNORECASE)
                            self.regex_mappings[pattern] = standard
                        except re.error as e:
                            print(f"⚠️ 别名文件第 {line_num} 行正则错误: {e}")
                    else:
                        # 所有非正则别名都视为精确匹配（必须整个字符串相等，忽略大小写）
                        self.exact_mappings[alias.lower()] = standard
        print(f"✅ 已加载别名规则：精确 {len(self.exact_mappings)}，正则 {len(self.regex_mappings)}")

    def match(self, channel_name: str) -> Optional[str]:
        """返回标准化名称，若无匹配则返回 None。只做精确匹配和正则匹配，无子串！"""
        if not channel_name:
            return None
        name_lower = channel_name.lower()
        # 精确匹配（最高优先级）
        if name_lower in self.exact_mappings:
            return self.exact_mappings[name_lower]
        # 正则匹配
        for pattern, standard in self.regex_mappings.items():
            if pattern.search(channel_name):
                return standard
        return None

    def normalize(self, channel_name: str) -> str:
        """标准化频道名，若无匹配则返回原名称"""
        mapped = self.match(channel_name)
        return mapped if mapped is not None else channel_name

_matcher = None

def get_alias_matcher() -> AliasMatcher:
    global _matcher
    if _matcher is None and ENABLE_ALIAS:
        _matcher = AliasMatcher()
    return _matcher
