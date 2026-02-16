"""
Pytest configuration and shared fixtures for ScoutingFEB tests.

This module provides reusable fixtures for database connections,
sample data, and test utilities.
"""

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Generator, Dict, Any

import pytest
import mongomock


# ============================================================================
# Path Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Return the path to the fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def sample_data_dir(fixtures_dir: Path) -> Path:
    """Return the path to the sample data directory."""
    return fixtures_dir / "sample_data"


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture
def temp_sqlite_db() -> Generator[str, None, None]:
    """
    Create a temporary SQLite database for testing.
    
    Yields:
        Path to temporary database file
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
        db_path = f.name
    
    yield db_path
    
    # Cleanup - ensure all connections are closed before deleting
    if os.path.exists(db_path):
        try:
            # Give time for connections to close
            import time
            time.sleep(0.1)
            os.unlink(db_path)
        except PermissionError:
            # If file is still locked, try to force close any open connections
            import gc
            gc.collect()
            time.sleep(0.2)
            try:
                os.unlink(db_path)
            except PermissionError:
                # If still can't delete, just leave it - OS will clean up temp files
                pass


@pytest.fixture
def sqlite_connection(temp_sqlite_db: str) -> Generator[sqlite3.Connection, None, None]:
    """
    Create SQLite connection with row factory configured.
    
    Yields:
        SQLite connection object
    """
    conn = sqlite3.connect(temp_sqlite_db)
    conn.row_factory = sqlite3.Row
    
    yield conn
    
    conn.close()


@pytest.fixture
def mock_mongo_client():
    """
    Create a mock MongoDB client using mongomock.
    
    Returns:
        Mongomock client instance
    """
    return mongomock.MongoClient()


@pytest.fixture
def mock_mongo_db(mock_mongo_client):
    """
    Create a mock MongoDB database.
    
    Returns:
        Mongomock database instance
    """
    return mock_mongo_client['scouting_test']


# ============================================================================
# Sample Data Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def sample_games_data(sample_data_dir: Path) -> Dict[str, Any]:
    """
    Load sample games data from fixtures.
    
    Returns:
        Dictionary containing sample game documents
    """
    games_file = sample_data_dir / "sample_games.json"
    if games_file.exists():
        with open(games_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"games": []}


@pytest.fixture(scope="session")
def sample_players_data(sample_data_dir: Path) -> Dict[str, Any]:
    """
    Load sample players data from fixtures.
    
    Returns:
        Dictionary containing sample player profiles
    """
    players_file = sample_data_dir / "sample_players.json"
    if players_file.exists():
        with open(players_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"players": []}


@pytest.fixture
def populated_mongo_db(mock_mongo_db, sample_games_data: Dict[str, Any]):
    """
    Create a MongoDB test database populated with sample games.
    
    Args:
        mock_mongo_db: Mock MongoDB database
        sample_games_data: Sample games data fixture
        
    Returns:
        Populated mongomock database
    """
    # Insert sample games
    if sample_games_data.get("games"):
        mock_mongo_db.all_feb_games_fem.insert_many(sample_games_data["games"])
    
    return mock_mongo_db


# ============================================================================
# Environment and Config Fixtures
# ============================================================================

@pytest.fixture
def test_env_vars(monkeypatch, temp_sqlite_db: str):
    """
    Set up test environment variables.
    
    Args:
        monkeypatch: Pytest monkeypatch fixture
        temp_sqlite_db: Temporary SQLite database path
    """
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017/")
    monkeypatch.setenv("SQLITE_DB_PATH", temp_sqlite_db)
    monkeypatch.setenv("ENV", "test")


# ============================================================================
# Utility Functions
# ============================================================================

def assert_no_nan_values(df, columns: list = None):
    """
    Assert that DataFrame has no NaN values in specified columns.
    
    Args:
        df: Pandas DataFrame to check
        columns: List of column names to check (None = check all)
    """
    if columns is None:
        columns = df.columns.tolist()
    
    for col in columns:
        assert not df[col].isna().any(), f"Column '{col}' contains NaN values"


def assert_values_in_range(df, column: str, min_val: float, max_val: float):
    """
    Assert that all values in a DataFrame column are within a valid range.
    
    Args:
        df: Pandas DataFrame
        column: Column name to check
        min_val: Minimum valid value
        max_val: Maximum valid value
    """
    values = df[column]
    assert values.min() >= min_val, f"{column} has values below {min_val}"
    assert values.max() <= max_val, f"{column} has values above {max_val}"
