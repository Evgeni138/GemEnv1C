"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

Парсеры для обработки файлов справки 1С
"""

from .hbk_reader import HbkHelpReader, HbkEntity, TocChunk, TocPage
from .html_parser import HtmlParser, BslFunction, BslObject, BslEnum

__all__ = [
    'HbkHelpReader',
    'HbkEntity',
    'TocChunk',
    'TocPage',
    'HtmlParser',
    'BslFunction',
    'BslObject',
    'BslEnum'
]

