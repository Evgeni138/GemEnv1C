"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

MCP tools для работы со справкой 1С
"""

from .search_tool import search_1c_help
from .platform_tools import (
    search_1c_platform_api,
    get_1c_platform_element,
    get_1c_platform_type_members,
)
from .manage_help_tool import manage_platform_help

__all__ = [
    'search_1c_help',
    'search_1c_platform_api',
    'get_1c_platform_element',
    'get_1c_platform_type_members',
    'manage_platform_help',
]

