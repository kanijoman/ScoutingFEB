"""
Database Context Utilities

Provides centralized database connection management and common patterns
for SQLite operations throughout the application.
"""

import sqlite3
from typing import Generator, Optional
from contextlib import contextmanager
import logging


logger = logging.getLogger(__name__)


@contextmanager
def get_db_connection(db_path: str, row_factory: bool = True) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for SQLite database connections.
    
    Handles connection lifecycle, commit/rollback, and cleanup automatically.
    
    Args:
        db_path: Path to SQLite database file
        row_factory: If True, use Row factory for dict-like access
        
    Yields:
        SQLite connection object
        
    Example:
        with get_db_connection('scouting.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM players")
            results = cursor.fetchall()
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        
        if row_factory:
            conn.row_factory = sqlite3.Row
        
        yield conn
        
        conn.commit()
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
        
    finally:
        if conn:
            conn.close()


def execute_query(
    db_path: str,
    query: str,
    params: tuple = (),
    fetch_one: bool = False,
    fetch_all: bool = True
) -> Optional[list]:
    """
    Execute a SELECT query and return results.
    
    Args:
        db_path: Path to SQLite database
        query: SQL query string
        params: Query parameters tuple
        fetch_one: If True, return only first result
        fetch_all: If True and fetch_one=False, return all results
        
    Returns:
        Query results or None
        
    Example:
        results = execute_query(
            'scouting.db',
            'SELECT * FROM players WHERE id = ?',
            (player_id,),
            fetch_one=True
        )
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        if fetch_one:
            return cursor.fetchone()
        elif fetch_all:
            return cursor.fetchall()
        
        return None


def execute_update(
    db_path: str,
    query: str,
    params: tuple = ()
) -> int:
    """
    Execute an INSERT/UPDATE/DELETE query.
    
    Args:
        db_path: Path to SQLite database
        query: SQL query string
        params: Query parameters tuple
        
    Returns:
        Number of affected rows
        
    Example:
        rows_affected = execute_update(
            'scouting.db',
            'UPDATE players SET name = ? WHERE id = ?',
            (new_name, player_id)
        )
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.rowcount


def execute_many(
    db_path: str,
    query: str,
    params_list: list
) -> int:
    """
    Execute a query with multiple parameter sets (bulk insert/update).
    
    Args:
        db_path: Path to SQLite database
        query: SQL query string
        params_list: List of parameter tuples
        
    Returns:
        Number of affected rows
        
    Example:
        rows = execute_many(
            'scouting.db',
            'INSERT INTO players (name, team) VALUES (?, ?)',
            [('Player1', 'Team A'), ('Player2', 'Team B')]
        )
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.executemany(query, params_list)
        return cursor.rowcount


class DatabaseContext:
    """
    Database context manager with transaction support.
    
    Provides a cleaner interface for database operations with
    automatic transaction management.
    
    Example:
        db = DatabaseContext('scouting.db')
        
        with db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO players ...")
            # Automatically commits on success, rolls back on error
    """
    
    def __init__(self, db_path: str, row_factory: bool = True):
        """
        Initialize database context.
        
        Args:
            db_path: Path to SQLite database file
            row_factory: If True, use Row factory for dict-like access
        """
        self.db_path = db_path
        self.row_factory = row_factory
        self.logger = logging.getLogger(__name__)
    
    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for database transactions.
        
        Yields:
            SQLite connection object
        """
        with get_db_connection(self.db_path, self.row_factory) as conn:
            yield conn
    
    def query(self, sql: str, params: tuple = (), fetch_one: bool = False):
        """
        Execute a SELECT query.
        
        Args:
            sql: SQL query string
            params: Query parameters
            fetch_one: If True, return only first result
            
        Returns:
            Query results
        """
        return execute_query(
            self.db_path,
            sql,
            params,
            fetch_one=fetch_one
        )
    
    def execute(self, sql: str, params: tuple = ()) -> int:
        """
        Execute an INSERT/UPDATE/DELETE query.
        
        Args:
            sql: SQL query string
            params: Query parameters
            
        Returns:
            Number of affected rows
        """
        return execute_update(self.db_path, sql, params)
    
    def execute_batch(self, sql: str, params_list: list) -> int:
        """
        Execute a query with multiple parameter sets.
        
        Args:
            sql: SQL query string
            params_list: List of parameter tuples
            
        Returns:
            Number of affected rows
        """
        return execute_many(self.db_path, sql, params_list)
