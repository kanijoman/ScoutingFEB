"""
Season Parsing Utilities

Centralized utilities for parsing and manipulating season strings
used throughout the FEB scouting system.
"""

from typing import Tuple, Optional
import re


def parse_season(season_str: str) -> Tuple[int, int]:
    """
    Parse season string into start and end years.
    
    Args:
        season_str: Season string in format "YYYY-YYYY" (e.g., "2024-2025")
        
    Returns:
        Tuple of (start_year, end_year)
        
    Raises:
        ValueError: If season string format is invalid
        
    Example:
        >>> parse_season("2024-2025")
        (2024, 2025)
    """
    if not season_str:
        raise ValueError("Season string cannot be empty")
    
    # Handle "YYYY-YYYY" format
    if '-' in season_str:
        parts = season_str.split('-')
        if len(parts) == 2:
            try:
                start_year = int(parts[0])
                end_year = int(parts[1])
                
                # Validate years are reasonable
                if 1900 <= start_year <= 2100 and 1900 <= end_year <= 2100:
                    if end_year == start_year + 1:
                        return (start_year, end_year)
                    else:
                        raise ValueError(f"End year must be start year + 1, got {start_year}-{end_year}")
                
            except ValueError as e:
                raise ValueError(f"Invalid year values in season string: {season_str}") from e
    
    # Handle single year "YYYY" format
    match = re.match(r'^(\d{4})$', season_str)
    if match:
        year = int(match.group(1))
        return (year, year + 1)
    
    raise ValueError(f"Invalid season format: {season_str}. Expected 'YYYY-YYYY' or 'YYYY'")


def get_season_start_year(season_str: str) -> int:
    """
    Get the starting year from a season string.
    
    Args:
        season_str: Season string (e.g., "2024-2025")
        
    Returns:
        Starting year as integer
        
    Example:
        >>> get_season_start_year("2024-2025")
        2024
    """
    start_year, _ = parse_season(season_str)
    return start_year


def get_season_end_year(season_str: str) -> int:
    """
    Get the ending year from a season string.
    
    Args:
        season_str: Season string (e.g., "2024-2025")
        
    Returns:
        Ending year as integer
        
    Example:
        >>> get_season_end_year("2024-2025")
        2025
    """
    _, end_year = parse_season(season_str)
    return end_year


def format_season(start_year: int, end_year: Optional[int] = None) -> str:
    """
    Format years into season string.
    
    Args:
        start_year: Starting year
        end_year: Ending year (if None, uses start_year + 1)
        
    Returns:
        Formatted season string "YYYY-YYYY"
        
    Example:
        >>> format_season(2024, 2025)
        '2024-2025'
        >>> format_season(2024)
        '2024-2025'
    """
    if end_year is None:
        end_year = start_year + 1
    
    return f"{start_year}-{end_year}"


def is_valid_season(season_str: str) -> bool:
    """
    Check if a season string is valid.
    
    Args:
        season_str: Season string to validate
        
    Returns:
        True if valid, False otherwise
        
    Example:
        >>> is_valid_season("2024-2025")
        True
        >>> is_valid_season("invalid")
        False
    """
    try:
        parse_season(season_str)
        return True
    except ValueError:
        return False


def get_previous_season(season_str: str) -> str:
    """
    Get the previous season string.
    
    Args:
        season_str: Current season string
        
    Returns:
        Previous season string
        
    Example:
        >>> get_previous_season("2024-2025")
        '2023-2024'
    """
    start_year, _ = parse_season(season_str)
    return format_season(start_year - 1)


def get_next_season(season_str: str) -> str:
    """
    Get the next season string.
    
    Args:
        season_str: Current season string
        
    Returns:
        Next season string
        
    Example:
        >>> get_next_season("2024-2025")
        '2025-2026'
    """
    start_year, _ = parse_season(season_str)
    return format_season(start_year + 1)


def seasons_between(start_season: str, end_season: str) -> list:
    """
    Generate list of all seasons between start and end (inclusive).
    
    Args:
        start_season: Starting season string
        end_season: Ending season string
        
    Returns:
        List of season strings
        
    Example:
        >>> seasons_between("2022-2023", "2024-2025")
        ['2022-2023', '2023-2024', '2024-2025']
    """
    start_year = get_season_start_year(start_season)
    end_year = get_season_start_year(end_season)
    
    return [format_season(year) for year in range(start_year, end_year + 1)]


def season_to_int(season_str: str) -> int:
    """
    Convert season string to integer for sorting/comparison.
    
    Args:
        season_str: Season string (e.g., "2024-2025")
        
    Returns:
        Integer representation (e.g., 20242025)
        
    Example:
        >>> season_to_int("2024-2025")
        20242025
    """
    start_year, end_year = parse_season(season_str)
    return start_year * 10000 + end_year


def compare_seasons(season1: str, season2: str) -> int:
    """
    Compare two seasons.
    
    Args:
        season1: First season string
        season2: Second season string
        
    Returns:
        -1 if season1 < season2, 0 if equal, 1 if season1 > season2
        
    Example:
        >>> compare_seasons("2023-2024", "2024-2025")
        -1
    """
    int1 = season_to_int(season1)
    int2 = season_to_int(season2)
    
    if int1 < int2:
        return -1
    elif int1 > int2:
        return 1
    else:
        return 0
