"""
Module for calculating advanced basketball statistics.

This module provides functions to calculate advanced metrics such as:
- True Shooting % (TS%)
- Effective Field Goal % (eFG%)
- Offensive Rating (OER)
- Player Efficiency Rating (PER)
- Turnover % (TOV%)
- Rebound % (ORB%, DRB%)
- Win Shares (WS)
"""

from typing import Dict, Optional
import math


def calculate_true_shooting_pct(pts: int, fga: int, fta: int) -> Optional[float]:
    """
    Calculate True Shooting Percentage.
    
    TS% = PTS / (2 * (FGA + 0.44 * FTA))
    
    Measures shooting efficiency considering FG, 3P and FT.
    
    Args:
        pts: Points scored
        fga: Field goals attempted
        fta: Free throws attempted
        
    Returns:
        True Shooting % or None if no data available
    """
    denominator = 2 * (fga + 0.44 * fta)
    if denominator == 0:
        return None
    return pts / denominator


def calculate_effective_fg_pct(fgm: int, fg3m: int, fga: int) -> Optional[float]:
    """
    Calculate Effective Field Goal Percentage.
    
    eFG% = (FGM + 0.5 * 3PM) / FGA
    
    Adjusts field goal percentage giving extra weight to three-pointers.
    
    Args:
        fgm: Field goals made
        fg3m: Three-pointers made
        fga: Field goals attempted
        
    Returns:
        Effective FG% or None if no data available
    """
    if fga == 0:
        return None
    return (fgm + 0.5 * fg3m) / fga


def calculate_turnover_pct(tov: int, fga: int, fta: int) -> Optional[float]:
    """
    Calculate Turnover Percentage.
    
    TOV% = TOV / (FGA + 0.44 * FTA + TOV)
    
    Estimates the percentage of possessions that end in a turnover.
    
    Args:
        tov: Turnovers
        fga: Field goals attempted
        fta: Free throws attempted
        
    Returns:
        Turnover % or None if no data available
    """
    denominator = fga + 0.44 * fta + tov
    if denominator == 0:
        return None
    return tov / denominator


def calculate_free_throw_rate(fta: int, fga: int) -> Optional[float]:
    """
    Calculate Free Throw Rate.
    
    FTr = FTA / FGA
    
    Measures the player's ability to get to the free-throw line.
    
    Args:
        fta: Free throws attempted
        fga: Field goals attempted
        
    Returns:
        Free Throw Rate or None if no data available
    """
    if fga == 0:
        return None
    return fta / fga


def calculate_assist_to_turnover_ratio(ast: int, tov: int) -> Optional[float]:
    """
    Calculate Assist to Turnover Ratio.
    
    AST/TOV = AST / TOV
    
    Measures ball-handling efficiency.
    
    Args:
        ast: Assists
        tov: Turnovers
        
    Returns:
        AST/TOV ratio or None if TOV = 0
    """
    if tov == 0:
        return None if ast == 0 else float(ast)  # Infinite ratio
    return ast / tov


def calculate_offensive_rating(pts: int, fga: int, fta: int, tov: int,
                               team_possessions: Optional[int] = None,
                               minutes: Optional[float] = None) -> Optional[float]:
    """
    Calculate simplified Offensive Rating (OER).
    
    OER estimates points produced per 100 possessions.
    
    Simplified version when team possessions are not available:
    OER = (PTS / Possessions_estimate) * 100
    
    Where Possessions_estimate = FGA + 0.44*FTA + TOV
    
    Args:
        pts: Points scored
        fga: Field goals attempted
        fta: Free throws attempted
        tov: Turnovers
        team_possessions: Team possessions (optional)
        minutes: Minutes played (optional, for adjustment)
        
    Returns:
        Offensive Rating or None if no data available
    """
    # Estimate individual possessions
    individual_possessions = fga + 0.44 * fta + tov
    
    if individual_possessions == 0:
        return None
    
    # Simplified OER
    oer = (pts / individual_possessions) * 100
    
    return oer


def calculate_player_efficiency_rating(stats: Dict) -> Optional[float]:
    """
    Calculate simplified Player Efficiency Rating (PER).
    
    PER combines multiple statistics into a single efficiency metric.
    This is a simplified version without pace and league adjustments.
    
    Formula:
        PER = [(PTS + REB + AST + STL + BLK - Missed_FG - Missed_FT - TOV) / MP] * 15
    
    The result is scaled by 15 to approximate standard PER values.
    
    Args:
        stats: Dictionary with player statistics:
            - pts, reb, ast, stl, blk: Positive contributions
            - fgm, fga, ftm, fta: Shooting stats (to calculate misses)
            - tov: Turnovers
            - minutes: Minutes played
            
    Returns:
        Player Efficiency Rating (scaled) or None if no minutes played
    """
    minutes = stats.get('minutes', 0)
    if minutes == 0:
        return None
    
    # Positive components
    positive = (
        stats.get('pts', 0) +
        stats.get('reb', 0) +
        stats.get('ast', 0) +
        stats.get('stl', 0) +
        stats.get('blk', 0)
    )
    
    # Negative components
    missed_fg = stats.get('fga', 0) - stats.get('fgm', 0)
    missed_ft = stats.get('fta', 0) - stats.get('ftm', 0)
    
    negative = (
        missed_fg +
        missed_ft +
        stats.get('tov', 0)
    )
    
    per = (positive - negative) / minutes
    
    # Scale to typical values (multiply by factor)
    per = per * 15  # Scaling factor to approximate standard PER
    
    return per


def calculate_usage_rate(fga: int, fta: int, tov: int,
                         team_fga: Optional[int] = None,
                         team_fta: Optional[int] = None,
                         team_tov: Optional[int] = None,
                         minutes: Optional[float] = None,
                         team_minutes: Optional[float] = None) -> Optional[float]:
    """
    Calculate Usage Rate (USG%).
    
    Usage Rate estimates the percentage of team possessions used by the player
    while on the court. A higher usage rate indicates the player is more involved
    in the team's offensive possessions.
    
    Formula with team stats:
        USG% = 100 * [(FGA + 0.44*FTA + TOV) * (TM_MP/5)] / (MP * (TM_FGA + 0.44*TM_FTA + TM_TOV))
    
    Simplified formula without team stats:
        USG% = [(FGA + 0.44*FTA + TOV) / Minutes] * 100
    
    Args:
        fga, fta, tov: Player field goal attempts, free throw attempts, turnovers
        team_fga, team_fta, team_tov: Team statistics (optional, for full formula)
        minutes: Player minutes played
        team_minutes: Total team minutes (optional, for full formula)
        
    Returns:
        Usage Rate percentage or None if insufficient data
    """
    if minutes is None or minutes == 0:
        return None
    
    player_possessions = fga + 0.44 * fta + tov
    
    # If we have team stats, use complete formula
    if all(x is not None for x in [team_fga, team_fta, team_tov, team_minutes]):
        team_possessions = team_fga + 0.44 * team_fta + team_tov
        if team_possessions == 0:
            return None
        
        usage = 100 * (player_possessions * (team_minutes / 5)) / (minutes * team_possessions)
        return usage
    
    # Simplified estimate
    usage = (player_possessions / minutes) * 100
    return usage


def calculate_rebound_percentages(player_orb: int, player_drb: int,
                                  team_orb: Optional[int] = None,
                                  team_drb: Optional[int] = None,
                                  opponent_orb: Optional[int] = None,
                                  opponent_drb: Optional[int] = None,
                                  minutes: Optional[float] = None,
                                  team_minutes: Optional[float] = None) -> Dict[str, Optional[float]]:
    """
    Calculate Offensive and Defensive Rebound Percentages.
    
    ORB% = ORB / (ORB_team + DRB_opponent)
    DRB% = DRB / (DRB_team + ORB_opponent)
    
    Args:
        player_orb, player_drb: Player rebounds
        team_orb, team_drb: Team rebounds (optional)
        opponent_orb, opponent_drb: Opponent rebounds (optional)
        minutes, team_minutes: For adjustment (optional)
        
    Returns:
        Dict with 'orb_pct' and 'drb_pct' or None if no data available
    """
    result = {
        'orb_pct': None,
        'drb_pct': None
    }
    
    # Calculate ORB% if we have team and opponent data
    if all(x is not None for x in [team_orb, opponent_drb]) and (team_orb + opponent_drb) > 0:
        result['orb_pct'] = player_orb / (team_orb + opponent_drb)
        
        # Adjust by minutes if available
        if minutes and team_minutes and team_minutes > 0:
            result['orb_pct'] = result['orb_pct'] * (team_minutes / (5 * minutes))
    
    # Calculate DRB% if we have team and opponent data
    if all(x is not None for x in [team_drb, opponent_orb]) and (team_drb + opponent_orb) > 0:
        result['drb_pct'] = player_drb / (team_drb + opponent_orb)
        
        # Adjust by minutes if available
        if minutes and team_minutes and team_minutes > 0:
            result['drb_pct'] = result['drb_pct'] * (team_minutes / (5 * minutes))
    
    return result


def calculate_win_shares(stats: Dict, team_stats: Optional[Dict] = None) -> Optional[float]:
    """
    Calculate simplified Win Shares (WS).
    
    WS estimates the player's contribution to team wins.
    
    Simplified formula:
    WS = (PER * minutes / 40) / 100
    
    Args:
        stats: Player statistics (must include what's needed for PER)
        team_stats: Team statistics (optional)
        
    Returns:
        Win Shares or None if cannot be calculated
    """
    per = calculate_player_efficiency_rating(stats)
    if per is None:
        return None
    
    minutes = stats.get('minutes', 0)
    if minutes == 0:
        return None
    
    # Simplified Win Shares estimate
    ws = (per * minutes / 40) / 100
    
    return ws


def calculate_all_advanced_stats(stats: Dict, 
                                 team_stats: Optional[Dict] = None,
                                 opponent_stats: Optional[Dict] = None) -> Dict[str, Optional[float]]:
    """
    Calculate all advanced statistics for a player.
    
    Computes comprehensive advanced metrics including efficiency ratings,
    usage rates, rebound percentages, and win shares.
    
    Args:
        stats: Dict with basic player statistics (pts, fga, fta, fgm, fg3m,
               ast, tov, orb, drb, stl, blk, minutes, etc.)
        team_stats: Dict with team statistics (optional, improves accuracy)
        opponent_stats: Dict with opponent statistics (optional)
        
    Returns:
        Dict with all calculated advanced metrics. Keys include:
        - true_shooting_pct, effective_fg_pct
        - turnover_pct, free_throw_rate
        - assist_to_turnover_ratio
        - offensive_rating, player_efficiency_rating
        - usage_rate
        - offensive_rebound_pct, defensive_rebound_pct
        - win_shares, win_shares_per_36
    """
    result = {}
    
    # Efficiency metrics
    result['true_shooting_pct'] = calculate_true_shooting_pct(
        stats.get('pts', 0),
        stats.get('fga', 0),
        stats.get('fta', 0)
    )
    
    result['effective_fg_pct'] = calculate_effective_fg_pct(
        stats.get('fgm', 0),
        stats.get('fg3m', 0),
        stats.get('fga', 0)
    )
    
    # Percentages
    result['turnover_pct'] = calculate_turnover_pct(
        stats.get('tov', 0),
        stats.get('fga', 0),
        stats.get('fta', 0)
    )
    
    result['free_throw_rate'] = calculate_free_throw_rate(
        stats.get('fta', 0),
        stats.get('fga', 0)
    )
    
    result['assist_to_turnover_ratio'] = calculate_assist_to_turnover_ratio(
        stats.get('ast', 0),
        stats.get('tov', 0)
    )
    
    # Ratings
    result['offensive_rating'] = calculate_offensive_rating(
        stats.get('pts', 0),
        stats.get('fga', 0),
        stats.get('fta', 0),
        stats.get('tov', 0),
        team_possessions=team_stats.get('possessions') if team_stats else None,
        minutes=stats.get('minutes')
    )
    
    result['player_efficiency_rating'] = calculate_player_efficiency_rating(stats)
    
    result['usage_rate'] = calculate_usage_rate(
        stats.get('fga', 0),
        stats.get('fta', 0),
        stats.get('tov', 0),
        team_fga=team_stats.get('fga') if team_stats else None,
        team_fta=team_stats.get('fta') if team_stats else None,
        team_tov=team_stats.get('tov') if team_stats else None,
        minutes=stats.get('minutes'),
        team_minutes=team_stats.get('minutes') if team_stats else None
    )
    
    # Rebounds
    reb_pcts = calculate_rebound_percentages(
        stats.get('orb', 0),
        stats.get('drb', 0),
        team_orb=team_stats.get('orb') if team_stats else None,
        team_drb=team_stats.get('drb') if team_stats else None,
        opponent_orb=opponent_stats.get('orb') if opponent_stats else None,
        opponent_drb=opponent_stats.get('drb') if opponent_stats else None,
        minutes=stats.get('minutes'),
        team_minutes=team_stats.get('minutes') if team_stats else None
    )
    result['offensive_rebound_pct'] = reb_pcts['orb_pct']
    result['defensive_rebound_pct'] = reb_pcts['drb_pct']
    
    # Win Shares
    result['win_shares'] = calculate_win_shares(stats, team_stats)
    
    # Win Shares per 36
    if result['win_shares'] is not None and stats.get('minutes', 0) > 0:
        result['win_shares_per_36'] = result['win_shares'] * (36 / stats['minutes'])
    else:
        result['win_shares_per_36'] = None
    
    return result
