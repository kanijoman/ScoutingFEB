"""
Módulo para calcular estadísticas avanzadas de baloncesto.

Este módulo proporciona funciones para calcular métricas avanzadas como:
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
    Calcular True Shooting Percentage.
    
    TS% = PTS / (2 * (FGA + 0.44 * FTA))
    
    Mide la eficiencia de tiro considerando FG, 3P y FT.
    
    Args:
        pts: Puntos anotados
        fga: Tiros de campo intentados
        fta: Tiros libres intentados
        
    Returns:
        True Shooting % o None si no hay datos
    """
    denominator = 2 * (fga + 0.44 * fta)
    if denominator == 0:
        return None
    return pts / denominator


def calculate_effective_fg_pct(fgm: int, fg3m: int, fga: int) -> Optional[float]:
    """
    Calcular Effective Field Goal Percentage.
    
    eFG% = (FGM + 0.5 * 3PM) / FGA
    
    Ajusta el porcentaje de tiro de campo dando peso extra a los triples.
    
    Args:
        fgm: Tiros de campo convertidos
        fg3m: Triples convertidos
        fga: Tiros de campo intentados
        
    Returns:
        Effective FG% o None si no hay datos
    """
    if fga == 0:
        return None
    return (fgm + 0.5 * fg3m) / fga


def calculate_turnover_pct(tov: int, fga: int, fta: int) -> Optional[float]:
    """
    Calcular Turnover Percentage.
    
    TOV% = TOV / (FGA + 0.44 * FTA + TOV)
    
    Estima el porcentaje de posesiones que terminan en pérdida.
    
    Args:
        tov: Pérdidas de balón
        fga: Tiros de campo intentados
        fta: Tiros libres intentados
        
    Returns:
        Turnover % o None si no hay datos
    """
    denominator = fga + 0.44 * fta + tov
    if denominator == 0:
        return None
    return tov / denominator


def calculate_free_throw_rate(fta: int, fga: int) -> Optional[float]:
    """
    Calcular Free Throw Rate.
    
    FTr = FTA / FGA
    
    Mide la capacidad del jugador para generar tiros libres.
    
    Args:
        fta: Tiros libres intentados
        fga: Tiros de campo intentados
        
    Returns:
        Free Throw Rate o None si no hay datos
    """
    if fga == 0:
        return None
    return fta / fga


def calculate_assist_to_turnover_ratio(ast: int, tov: int) -> Optional[float]:
    """
    Calcular Assist to Turnover Ratio.
    
    AST/TOV = AST / TOV
    
    Mide la eficiencia en el manejo del balón.
    
    Args:
        ast: Asistencias
        tov: Pérdidas
        
    Returns:
        AST/TOV ratio o None si TOV = 0
    """
    if tov == 0:
        return None if ast == 0 else float(ast)  # Infinite ratio
    return ast / tov


def calculate_offensive_rating(pts: int, fga: int, fta: int, tov: int,
                               team_possessions: Optional[int] = None,
                               minutes: Optional[float] = None) -> Optional[float]:
    """
    Calcular Offensive Rating (OER) simplificado.
    
    OER estima los puntos generados por 100 posesiones.
    
    Versión simplificada cuando no tenemos posesiones del equipo:
    OER = (PTS / Possessions_estimate) * 100
    
    Donde Possessions_estimate = FGA + 0.44*FTA + TOV
    
    Args:
        pts: Puntos anotados
        fga: Tiros de campo intentados
        fta: Tiros libres intentados
        tov: Pérdidas
        team_possessions: Posesiones del equipo (opcional)
        minutes: Minutos jugados (opcional, para ajuste)
        
    Returns:
        Offensive Rating o None si no hay datos
    """
    # Estimación de posesiones individuales
    individual_possessions = fga + 0.44 * fta + tov
    
    if individual_possessions == 0:
        return None
    
    # OER simplificado
    oer = (pts / individual_possessions) * 100
    
    return oer


def calculate_player_efficiency_rating(stats: Dict) -> Optional[float]:
    """
    Calcular Player Efficiency Rating (PER) simplificado.
    
    PER combina múltiples estadísticas en una métrica única de eficiencia.
    
    Fórmula simplificada (sin ajustes de pace y liga):
    PER = (PTS + REB + AST + STL + BLK - Missed_FG - Missed_FT - TOV) / MP
    
    Args:
        stats: Diccionario con estadísticas del jugador:
            - pts, reb, ast, stl, blk, fgm, fga, ftm, fta, tov, minutes
            
    Returns:
        PER o None si no hay minutos
    """
    minutes = stats.get('minutes', 0)
    if minutes == 0:
        return None
    
    # Componentes positivos
    positive = (
        stats.get('pts', 0) +
        stats.get('reb', 0) +
        stats.get('ast', 0) +
        stats.get('stl', 0) +
        stats.get('blk', 0)
    )
    
    # Componentes negativos
    missed_fg = stats.get('fga', 0) - stats.get('fgm', 0)
    missed_ft = stats.get('fta', 0) - stats.get('ftm', 0)
    
    negative = (
        missed_fg +
        missed_ft +
        stats.get('tov', 0)
    )
    
    per = (positive - negative) / minutes
    
    # Escalar a valores típicos (multiplicar por factor)
    per = per * 15  # Factor de escala para aproximar PER estándar
    
    return per


def calculate_usage_rate(fga: int, fta: int, tov: int,
                         team_fga: Optional[int] = None,
                         team_fta: Optional[int] = None,
                         team_tov: Optional[int] = None,
                         minutes: Optional[float] = None,
                         team_minutes: Optional[float] = None) -> Optional[float]:
    """
    Calcular Usage Rate.
    
    USG% estima el porcentaje de posesiones del equipo usadas por el jugador.
    
    Fórmula simplificada sin stats del equipo:
    USG% = (FGA + 0.44*FTA + TOV) / Minutes * Factor
    
    Args:
        fga, fta, tov: Estadísticas del jugador
        team_fga, team_fta, team_tov: Estadísticas del equipo (opcional)
        minutes: Minutos del jugador
        team_minutes: Minutos totales del equipo (opcional)
        
    Returns:
        Usage Rate o None si no hay datos
    """
    if minutes is None or minutes == 0:
        return None
    
    player_possessions = fga + 0.44 * fta + tov
    
    # Si tenemos stats del equipo, usar fórmula completa
    if all(x is not None for x in [team_fga, team_fta, team_tov, team_minutes]):
        team_possessions = team_fga + 0.44 * team_fta + team_tov
        if team_possessions == 0:
            return None
        
        usage = 100 * (player_possessions * (team_minutes / 5)) / (minutes * team_possessions)
        return usage
    
    # Estimación simplificada
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
    Calcular Offensive y Defensive Rebound Percentages.
    
    ORB% = ORB / (ORB_team + DRB_opponent)
    DRB% = DRB / (DRB_team + ORB_opponent)
    
    Args:
        player_orb, player_drb: Rebotes del jugador
        team_orb, team_drb: Rebotes del equipo (opcional)
        opponent_orb, opponent_drb: Rebotes del rival (opcional)
        minutes, team_minutes: Para ajuste (opcional)
        
    Returns:
        Dict con 'orb_pct' y 'drb_pct' o None si no hay datos
    """
    result = {
        'orb_pct': None,
        'drb_pct': None
    }
    
    # Calcular ORB% si tenemos datos del equipo y rival
    if all(x is not None for x in [team_orb, opponent_drb]) and (team_orb + opponent_drb) > 0:
        result['orb_pct'] = player_orb / (team_orb + opponent_drb)
        
        # Ajustar por minutos si disponible
        if minutes and team_minutes and team_minutes > 0:
            result['orb_pct'] = result['orb_pct'] * (team_minutes / (5 * minutes))
    
    # Calcular DRB% si tenemos datos del equipo y rival
    if all(x is not None for x in [team_drb, opponent_orb]) and (team_drb + opponent_orb) > 0:
        result['drb_pct'] = player_drb / (team_drb + opponent_orb)
        
        # Ajustar por minutos si disponible
        if minutes and team_minutes and team_minutes > 0:
            result['drb_pct'] = result['drb_pct'] * (team_minutes / (5 * minutes))
    
    return result


def calculate_win_shares(stats: Dict, team_stats: Optional[Dict] = None) -> Optional[float]:
    """
    Calcular Win Shares (WS) simplificado.
    
    WS estima la contribución del jugador a las victorias del equipo.
    
    Fórmula simplificada:
    WS = (PER * minutes / 40) / 100
    
    Args:
        stats: Estadísticas del jugador (debe incluir lo necesario para PER)
        team_stats: Estadísticas del equipo (opcional)
        
    Returns:
        Win Shares o None si no se puede calcular
    """
    per = calculate_player_efficiency_rating(stats)
    if per is None:
        return None
    
    minutes = stats.get('minutes', 0)
    if minutes == 0:
        return None
    
    # Estimación simplificada de Win Shares
    ws = (per * minutes / 40) / 100
    
    return ws


def calculate_all_advanced_stats(stats: Dict, 
                                 team_stats: Optional[Dict] = None,
                                 opponent_stats: Optional[Dict] = None) -> Dict[str, Optional[float]]:
    """
    Calcular todas las estadísticas avanzadas de un jugador.
    
    Args:
        stats: Dict con estadísticas básicas del jugador
        team_stats: Dict con estadísticas del equipo (opcional)
        opponent_stats: Dict con estadísticas del rival (opcional)
        
    Returns:
        Dict con todas las métricas avanzadas calculadas
    """
    result = {}
    
    # Métricas de eficiencia
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
    
    # Porcentajes
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
    
    # Rebotes
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
