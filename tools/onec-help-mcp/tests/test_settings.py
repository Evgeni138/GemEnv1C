"""Tests for settings and configuration"""

import pytest
from src.config import settings


class TestSettings:
    """Test configuration settings"""

    def test_default_search_limit(self):
        """Test default search limit is set correctly"""
        assert settings.DEFAULT_SEARCH_LIMIT == 10

    def test_max_search_limit(self):
        """Test max search limit is reasonable"""
        assert settings.MAX_SEARCH_LIMIT == 100
        assert settings.MAX_SEARCH_LIMIT >= settings.DEFAULT_SEARCH_LIMIT

    def test_server_port(self):
        """Test server port is valid"""
        assert 1024 <= settings.SERVER_PORT <= 65535

    def test_sparse_boost_range(self):
        """Test sparse boost is in valid range"""
        assert 0.0 <= settings.SPARSE_BOOST <= 1.0

    def test_hybrid_search_enabled(self):
        """Test hybrid search is enabled by default"""
        assert settings.USE_HYBRID_SEARCH is True
