"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

REST API module for MCP tools
"""

from .rest_handlers import (
    search_help_handler,
    search_platform_api_handler,
    get_element_handler,
    get_type_members_handler,
    manage_help_handler
)

__all__ = [
    'search_help_handler',
    'search_platform_api_handler',
    'get_element_handler',
    'get_type_members_handler',
    'manage_help_handler'
]
