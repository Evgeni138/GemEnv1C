"""Tests for version resolution logic"""

import pytest
from src.config.version import normalize_version, get_collection_name


class TestVersionNormalization:
    """Test version normalization"""

    def test_normalize_full_version(self):
        """Test normalizing full version string"""
        assert normalize_version("8.3.26") == "8.3.26"
        assert normalize_version("8.3.25") == "8.3.25"

    def test_normalize_with_spaces(self):
        """Test normalizing version with spaces"""
        assert normalize_version(" 8.3.26 ") == "8.3.26"

    def test_collection_name_format(self):
        """Test collection name formatting"""
        assert get_collection_name("8.3.26") == "1c_help_8_3_26"
        assert get_collection_name("8.3.25") == "1c_help_8_3_25"

    def test_collection_name_with_dots(self):
        """Test that dots are replaced with underscores"""
        collection = get_collection_name("8.3.24")
        assert "." not in collection
        assert collection.startswith("1c_help_")
