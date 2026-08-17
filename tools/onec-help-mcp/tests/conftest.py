"""Pytest configuration and fixtures"""

import pytest
from pathlib import Path


@pytest.fixture
def test_data_dir():
    """Path to test data directory"""
    return Path(__file__).parent / "data"


@pytest.fixture
def mock_version():
    """Mock platform version"""
    return "8.3.26"


@pytest.fixture
def mock_query():
    """Mock search query"""
    return "HTTPЗапрос"


@pytest.fixture
def mock_collection_name(mock_version):
    """Mock collection name"""
    return f"1c_help_{mock_version.replace('.', '_')}"
