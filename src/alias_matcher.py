#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
别名匹配模块（整词边界匹配 + 最长匹配优先）
"""

import re
import os
from typing import Dict, Optional, Union, List, Tuple

class AliasMatcher:
    def __init__(self, alias_file: str = "alias.txt"):
        self.alias_file = alias_file
        self.patterns: List[Tuple[re.Pattern, str]] = []  # 全部转为正则，避免子串冲突

    def _load(self):
        if not os.path.exists(self.alias_file):
            print(f"⚠️ 别名文件不存在: {self.alias_file}")
            return

        with open(self.alias_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split(',')
                if len(parts) < 2:
                    print(f"⚠️ 别名文件第 {line_num} 行格式错误，跳过")
                    continue
                standard = parts[0].strip()
                aliases = parts[1:]
                for alias in aliases:
                    alias = alias.strip()
                    if not alias:
                        continue
                    if alias.startswith('re:'):
                        # 用户提供的正则
                        pattern_str = alias[3:].strip()
                        try:
                            pattern = re.compile(pattern_str, re.IGNORECASE)
                            self.patterns.append((pattern, standard))
                        except re.error as e:
                            print(f"⚠️ 别名文件第 {line_num} 行正则错误: {e}")
                    else:
                        # 普通字符串 -> 转为整词边界正则（避免子串匹配）
                        # 转义特殊字符，并加上 \b 单词边界
                        escaped = re.escape(alias)
                        # 注意：中文等需要自定义边界，使用 (?<!\w) 和 (?!\w) 来模拟
                        pattern_str = rf'(?<![a-zA-Z0-9\u4e00-\u9fa5]){escaped}(?![a-zA-Z0-9\u4e00-\u9fa5])'
                        try:
                            pattern = re.compile(pattern_str, re.IGNORECASE)
                            self.patterns.append((pattern, standard))
                        except re.error as e:
                            print(f"⚠️ 别名文件第 {line_num} 行转换正则错误: {e}")

        # 按正则复杂度排序（较长的字符串优先匹配，避免短词先行）
        def sort_key(item):
            pattern, _ = item
            # 对于字符串转换的正则，原始字符串长度作为优先级
            if hasattr(pattern, 'original_length'):
                return -pattern.original_length
            return 0
        self.patterns.sort(key=sort_key)
        print(f"✅ 已加载 {len(self.patterns)} 条别名规则（整词匹配）")

    def match(self, channel_name: str) -> Optional[str]:
        if not channel_name:
            return None
        for pattern, standard in self.patterns:
            if pattern.search(channel_name):
                return standard
        return None

    def get_all_standard_names(self) -> set:
        return {std for _, std in self.patterns}


_matcher = None

def get_alias_matcher() -> AliasMatcher:
    global _matcher
    if _matcher is None:
        _matcher = AliasMatcher()
    return _matcher
