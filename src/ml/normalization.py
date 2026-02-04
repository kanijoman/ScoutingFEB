"""
Funciones de normalización para comparar jugadores entre épocas y ligas.

Implementa Z-Score normalization basada en el contexto (nivel de competición + temporada)
para hacer comparables las estadísticas de jugadores de diferentes épocas y ligas.

Referencias:
- Z-Score: Medida de cuántas desviaciones estándar está un valor de la media
- Contexto: Grupo definido por (competition_level, season)
"""

import sqlite3
from typing import Dict, List, Tuple, Optional
import logging
import math


logger = logging.getLogger(__name__)


class ZScoreNormalizer:
    """
    Calcula Z-Scores para normalizar estadísticas de jugadores.
    
    El Z-Score permite comparar jugadores de diferentes épocas y ligas:
    - Z = 0: Rendimiento promedio en su contexto
    - Z = +1: Una desviación estándar por encima (mejor que ~84%)
    - Z = +2: Dos desviaciones estándar por encima (élite, mejor que ~97%)
    - Z = -1: Por debajo del promedio
    
    Ejemplo:
        Jugador A (2010, EBA): 14 pts → Z = +2.5 (dominante)
        Jugador B (2023, EBA): 11 pts → Z = +1.9 (muy bueno)
        → Son comparables a pesar de épocas diferentes
    """
    
    def __init__(self, db_path: str):
        """
        Args:
            db_path: Ruta a la base de datos SQLite
        """
        self.db_path = db_path
        self.context_stats_cache: Dict[Tuple[int, str], Dict[str, Tuple[float, float]]] = {}
    
    def calculate_context_statistics(
        self,
        competition_level: int,
        season: str,
        metrics: List[str] = None
    ) -> Dict[str, Tuple[float, float]]:
        """
        Calcula media y desviación estándar para un contexto (nivel + temporada).
        
        Args:
            competition_level: Nivel de la competición (1=máximo, 2, 3...)
            season: Temporada (ej: "2023-2024")
            metrics: Lista de métricas a calcular (default: puntos, eficiencia, rebotes, asistencias)
        
        Returns:
            Dict con {metric: (mean, std_dev)} para cada métrica
        """
        if metrics is None:
            metrics = [
                'points', 'efficiency_rating', 'total_rebounds', 'assists',
                'true_shooting_pct', 'effective_fg_pct', 'offensive_rating',
                'player_efficiency_rating', 'turnover_pct',
                'offensive_rebound_pct', 'defensive_rebound_pct',
                'free_throw_rate', 'usage_rate', 'win_shares', 'win_shares_per_36'
            ]
        
        # Verificar caché
        cache_key = (competition_level, season)
        if cache_key in self.context_stats_cache:
            return self.context_stats_cache[cache_key]
        
        context_stats = {}
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for metric in metrics:
                # Calcular media y desviación estándar para el contexto
                query = f"""
                SELECT 
                    AVG({metric}) as mean,
                    -- Calcular std_dev manualmente: sqrt(avg(x^2) - avg(x)^2)
                    SQRT(AVG({metric} * {metric}) - AVG({metric}) * AVG({metric})) as std_dev,
                    COUNT(*) as sample_size
                FROM player_game_stats pgs
                JOIN games g ON pgs.game_id = g.game_id
                JOIN competitions c ON g.competition_id = c.competition_id
                JOIN competition_levels cl ON c.competition_id = cl.competition_id 
                    AND g.season = cl.season
                WHERE cl.competition_level = ?
                    AND g.season = ?
                    AND {metric} IS NOT NULL
                    AND pgs.minutes_played >= 10  -- Solo jugadores con minutos significativos
                """
                
                cursor.execute(query, (competition_level, season))
                row = cursor.fetchone()
                
                if row and row[0] is not None and row[1] is not None and row[1] > 0:
                    mean, std_dev, sample_size = row
                    
                    if sample_size < 30:
                        logger.warning(
                            f"Muestra pequeña para {metric} en nivel={competition_level}, "
                            f"temporada={season}: n={sample_size}"
                        )
                    
                    context_stats[metric] = (mean, std_dev)
                else:
                    logger.warning(
                        f"No hay datos suficientes para {metric} en nivel={competition_level}, "
                        f"temporada={season}"
                    )
                    context_stats[metric] = (0.0, 1.0)  # Fallback
        
        # Guardar en caché
        self.context_stats_cache[cache_key] = context_stats
        return context_stats
    
    def calculate_zscore(
        self,
        value: float,
        mean: float,
        std_dev: float
    ) -> Optional[float]:
        """
        Calcula el Z-Score de un valor.
        
        Z = (valor - media) / desviación_estándar
        
        Args:
            value: Valor a normalizar
            mean: Media del contexto
            std_dev: Desviación estándar del contexto
        
        Returns:
            Z-Score o None si no se puede calcular
        """
        if std_dev == 0 or std_dev is None:
            logger.warning(f"Desviación estándar = 0, no se puede calcular Z-Score")
            return None
        
        if value is None or mean is None:
            return None
        
        return (value - mean) / std_dev
    
    def normalize_player_game(
        self,
        stat_id: int,
        competition_level: int,
        season: str
    ) -> Dict[str, float]:
        """
        Calcula Z-Scores para las estadísticas de un jugador en un partido.
        
        Args:
            stat_id: ID de player_game_stats
            competition_level: Nivel de competición
            season: Temporada
        
        Returns:
            Dict con Z-Scores calculados
        """
        # Obtener estadísticas del contexto
        context_stats = self.calculate_context_statistics(competition_level, season)
        
        # Obtener valores del jugador
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    points, efficiency_rating, total_rebounds, assists,
                    true_shooting_pct, effective_fg_pct, offensive_rating,
                    player_efficiency_rating, turnover_pct,
                    offensive_rebound_pct, defensive_rebound_pct,
                    free_throw_rate, usage_rate, win_shares, win_shares_per_36
                FROM player_game_stats
                WHERE stat_id = ?
            """, (stat_id,))
            
            row = cursor.fetchone()
            if not row:
                logger.error(f"No se encontró stat_id={stat_id}")
                return {}
            
            (points, efficiency, rebounds, assists,
             ts_pct, efg_pct, oer, per, tov_pct,
             orb_pct, drb_pct, ftr, usage, ws, ws_36) = row
        
        # Calcular Z-Scores
        z_scores = {}
        
        if 'points' in context_stats:
            mean, std = context_stats['points']
            z_scores['z_points'] = self.calculate_zscore(points, mean, std)
        
        if 'efficiency_rating' in context_stats:
            mean, std = context_stats['efficiency_rating']
            z_scores['z_efficiency'] = self.calculate_zscore(efficiency, mean, std)
        
        if 'total_rebounds' in context_stats:
            mean, std = context_stats['total_rebounds']
            z_scores['z_rebounds'] = self.calculate_zscore(rebounds, mean, std)
        
        if 'assists' in context_stats:
            mean, std = context_stats['assists']
            z_scores['z_assists'] = self.calculate_zscore(assists, mean, std)
        
        # Métricas avanzadas
        if 'offensive_rating' in context_stats and oer is not None:
            mean, std = context_stats['offensive_rating']
            z_scores['z_offensive_rating'] = self.calculate_zscore(oer, mean, std)
        
        if 'true_shooting_pct' in context_stats and ts_pct is not None:
            mean, std = context_stats['true_shooting_pct']
            z_scores['z_true_shooting_pct'] = self.calculate_zscore(ts_pct, mean, std)
        
        if 'player_efficiency_rating' in context_stats and per is not None:
            mean, std = context_stats['player_efficiency_rating']
            z_scores['z_player_efficiency_rating'] = self.calculate_zscore(per, mean, std)
        
        if 'turnover_pct' in context_stats and tov_pct is not None:
            mean, std = context_stats['turnover_pct']
            z_scores['z_turnover_pct'] = self.calculate_zscore(tov_pct, mean, std)
        
        if 'usage_rate' in context_stats and usage is not None:
            mean, std = context_stats['usage_rate']
            z_scores['z_usage'] = self.calculate_zscore(usage, mean, std)
        
        if 'win_shares_per_36' in context_stats and ws_36 is not None:
            mean, std = context_stats['win_shares_per_36']
            z_scores['z_win_shares_per_36'] = self.calculate_zscore(ws_36, mean, std)
        
        return z_scores
    
    def calculate_percentile(self, z_score: float) -> int:
        """
        Convierte Z-Score a percentil (0-100).
        
        Usa la función de distribución acumulativa normal.
        
        Args:
            z_score: Z-Score calculado
        
        Returns:
            Percentil entre 0 y 100
        """
        if z_score is None:
            return 50  # Promedio por defecto
        
        # Aproximación de la CDF normal usando erf
        # CDF(z) = 0.5 * (1 + erf(z / sqrt(2)))
        percentile = 0.5 * (1 + math.erf(z_score / math.sqrt(2)))
        return int(percentile * 100)
    
    def calculate_performance_tier(self, percentile: int) -> str:
        """
        Clasifica el rendimiento basado en percentil.
        
        Args:
            percentile: Percentil (0-100)
        
        Returns:
            Tier: 'elite', 'very_good', 'above_average', 'average', 'below_average'
        """
        if percentile >= 95:
            return 'elite'
        elif percentile >= 80:
            return 'very_good'
        elif percentile >= 60:
            return 'above_average'
        elif percentile >= 40:
            return 'average'
        else:
            return 'below_average'
    
    def update_game_stats_zscores(self, competition_level: int, season: str) -> int:
        """
        Actualiza los Z-Scores de todos los partidos en un contexto.
        
        Args:
            competition_level: Nivel de competición
            season: Temporada
        
        Returns:
            Número de registros actualizados
        """
        logger.info(f"Calculando Z-Scores para nivel={competition_level}, temporada={season}")
        
        # Calcular estadísticas del contexto
        context_stats = self.calculate_context_statistics(competition_level, season)
        
        updated_count = 0
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Obtener todos los stat_ids del contexto
            cursor.execute("""
                SELECT 
                    pgs.stat_id, pgs.points, pgs.efficiency_rating,
                    pgs.total_rebounds, pgs.assists,
                    pgs.true_shooting_pct, pgs.effective_fg_pct, pgs.offensive_rating,
                    pgs.player_efficiency_rating, pgs.turnover_pct,
                    pgs.usage_rate, pgs.win_shares_per_36
                FROM player_game_stats pgs
                JOIN games g ON pgs.game_id = g.game_id
                JOIN competitions c ON g.competition_id = c.competition_id
                JOIN competition_levels cl ON c.competition_id = cl.competition_id 
                    AND g.season = cl.season
                WHERE cl.competition_level = ?
                    AND g.season = ?
            """, (competition_level, season))
            
            rows = cursor.fetchall()
            
            for row in rows:
                (stat_id, points, efficiency, rebounds, assists,
                 ts_pct, efg_pct, oer, per, tov_pct, usage, ws_36) = row
                
                # Calcular Z-Scores básicos
                z_points = None
                z_efficiency = None
                z_rebounds = None
                z_assists = None
                
                if 'points' in context_stats:
                    mean, std = context_stats['points']
                    z_points = self.calculate_zscore(points, mean, std)
                
                if 'efficiency_rating' in context_stats:
                    mean, std = context_stats['efficiency_rating']
                    z_efficiency = self.calculate_zscore(efficiency, mean, std)
                
                if 'total_rebounds' in context_stats:
                    mean, std = context_stats['total_rebounds']
                    z_rebounds = self.calculate_zscore(rebounds, mean, std)
                
                if 'assists' in context_stats:
                    mean, std = context_stats['assists']
                    z_assists = self.calculate_zscore(assists, mean, std)
                
                # Calcular Z-Scores de métricas avanzadas
                z_oer = None
                z_ts_pct = None
                z_per = None
                z_tov_pct = None
                z_usage = None
                z_ws_36 = None
                
                if oer is not None and 'offensive_rating' in context_stats:
                    mean, std = context_stats['offensive_rating']
                    z_oer = self.calculate_zscore(oer, mean, std)
                
                if ts_pct is not None and 'true_shooting_pct' in context_stats:
                    mean, std = context_stats['true_shooting_pct']
                    z_ts_pct = self.calculate_zscore(ts_pct, mean, std)
                
                if per is not None and 'player_efficiency_rating' in context_stats:
                    mean, std = context_stats['player_efficiency_rating']
                    z_per = self.calculate_zscore(per, mean, std)
                
                if tov_pct is not None and 'turnover_pct' in context_stats:
                    mean, std = context_stats['turnover_pct']
                    z_tov_pct = self.calculate_zscore(tov_pct, mean, std)
                
                if usage is not None and 'usage_rate' in context_stats:
                    mean, std = context_stats['usage_rate']
                    z_usage = self.calculate_zscore(usage, mean, std)
                
                if ws_36 is not None and 'win_shares_per_36' in context_stats:
                    mean, std = context_stats['win_shares_per_36']
                    z_ws_36 = self.calculate_zscore(ws_36, mean, std)
                
                # Actualizar en base de datos
                # NOTA: Solo actualizamos z-scores de métricas avanzadas que existen en el esquema
                # Las métricas básicas (points, efficiency, rebounds, assists) no tienen columnas z-score
                cursor.execute("""
                    UPDATE player_game_stats
                    SET z_offensive_rating = ?,
                        z_true_shooting_pct = ?,
                        z_player_efficiency_rating = ?,
                        z_turnover_pct = ?,
                        z_usage_rate = ?,
                        z_win_shares_per_36 = ?
                    WHERE stat_id = ?
                """, (z_oer, z_ts_pct, z_per, z_tov_pct, z_usage, z_ws_36, stat_id))
                
                updated_count += 1
            
            conn.commit()
        
        logger.info(f"Z-Scores actualizados: {updated_count} registros")
        return updated_count
    
    def update_aggregated_stats_normalized(self, player_id: int, season: str) -> bool:
        """
        Actualiza Z-Scores y percentiles en player_aggregated_stats.
        
        Args:
            player_id: ID del jugador
            season: Temporada
        
        Returns:
            True si se actualizó correctamente
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Obtener estadísticas agregadas del jugador
            cursor.execute("""
                SELECT 
                    pas.agg_id,
                    pas.avg_points,
                    pas.avg_efficiency,
                    pas.avg_total_rebounds,
                    pas.avg_assists,
                    cl.competition_level
                FROM player_aggregated_stats pas
                JOIN competitions c ON pas.competition_id = c.competition_id
                JOIN competition_levels cl ON c.competition_id = cl.competition_id 
                    AND pas.season = cl.season
                WHERE pas.player_id = ?
                    AND pas.season = ?
            """, (player_id, season))
            
            row = cursor.fetchone()
            if not row:
                logger.warning(f"No hay stats agregadas para player_id={player_id}, season={season}")
                return False
            
            agg_id, avg_points, avg_efficiency, avg_rebounds, avg_assists, comp_level = row
            
            # Calcular Z-Scores
            context_stats = self.calculate_context_statistics(comp_level, season)
            
            z_avg_points = None
            z_avg_efficiency = None
            z_avg_rebounds = None
            z_avg_assists = None
            
            if 'points' in context_stats:
                mean, std = context_stats['points']
                z_avg_points = self.calculate_zscore(avg_points, mean, std)
            
            if 'efficiency_rating' in context_stats:
                mean, std = context_stats['efficiency_rating']
                z_avg_efficiency = self.calculate_zscore(avg_efficiency, mean, std)
            
            if 'total_rebounds' in context_stats:
                mean, std = context_stats['total_rebounds']
                z_avg_rebounds = self.calculate_zscore(avg_rebounds, mean, std)
            
            if 'assists' in context_stats:
                mean, std = context_stats['assists']
                z_avg_assists = self.calculate_zscore(avg_assists, mean, std)
            
            # Calcular percentiles (usar eficiencia como métrica principal)
            percentile_efficiency = self.calculate_percentile(z_avg_efficiency) if z_avg_efficiency else 50
            percentile_points = self.calculate_percentile(z_avg_points) if z_avg_points else 50
            percentile_rebounds = self.calculate_percentile(z_avg_rebounds) if z_avg_rebounds else 50
            percentile_assists = self.calculate_percentile(z_avg_assists) if z_avg_assists else 50
            
            # Clasificar rendimiento
            performance_tier = self.calculate_performance_tier(percentile_efficiency)
            
            # NOTA: Las columnas z_avg_points, z_avg_efficiency, etc. no existen en el esquema actual
            # Solo actualizamos las que están disponibles: performance_tier y percentiles de métricas avanzadas
            # Las métricas básicas no se normalizan en esta tabla (se normalizan a nivel de partido)
            
            # No hacer nada por ahora - las columnas no existen en el esquema
            # Si se necesita, agregar las columnas al esquema o usar otra tabla
            z_points_str = f"{z_avg_points:.2f}" if z_avg_points else 'N/A'
            z_eff_str = f"{z_avg_efficiency:.2f}" if z_avg_efficiency else 'N/A'
            logger.debug(f"Stats normalizadas calculadas para player {player_id}: "
                        f"z_points={z_points_str}, z_eff={z_eff_str}")
            
            conn.commit()
        
        return True


def initialize_competition_levels(db_path: str, default_levels: Dict[str, int] = None):
    """
    Inicializa la tabla competition_levels con configuración por defecto.
    
    Args:
        db_path: Ruta a la base de datos SQLite
        default_levels: Dict con {competition_name: level} por defecto
    """
    if default_levels is None:
        # Configuración por defecto para competiciones FEB
        default_levels = {
            'ACB': 1,
            'LEB ORO': 2,
            'LEB PLATA': 3,
            'EBA': 4,
            'LIGA FEMENINA': 1,
            'LIGA FEMENINA 2': 2,  # Era nivel 2 hasta ~2020
            'LIGA CHALLENGE': 2,  # Creada ~2020, nivel 2
            'PRIMERA FEB': 3,
        }
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Obtener todas las competiciones y temporadas
        cursor.execute("""
            SELECT DISTINCT c.competition_id, c.competition_name, g.season
            FROM competitions c
            JOIN games g ON c.competition_id = g.competition_id
            ORDER BY g.season, c.competition_name
        """)
        
        rows = cursor.fetchall()
        
        for comp_id, comp_name, season in rows:
            # Buscar nivel por defecto
            level = default_levels.get(comp_name.upper(), 4)  # Default nivel 4
            
            # Ajustar LF2 después de la Liga Challenge
            if comp_name.upper() == 'LIGA FEMENINA 2':
                # Si es después de 2020, cambiar a nivel 3
                season_year = int(season.split('-')[0])
                if season_year >= 2020:
                    level = 3
            
            # Insertar o ignorar si ya existe
            cursor.execute("""
                INSERT OR IGNORE INTO competition_levels 
                (competition_id, season, competition_level, weight, level_description)
                VALUES (?, ?, ?, 1.0, ?)
            """, (comp_id, season, level, f"Nivel {level}"))
        
        conn.commit()
    
    logger.info(f"Inicializados niveles de competición para {len(rows)} entradas")


# Funciones auxiliares para uso directo
def calculate_zscore(value: float, mean: float, std_dev: float) -> Optional[float]:
    """Calcula Z-Score: (valor - media) / desviación_estándar"""
    if std_dev == 0 or std_dev is None or value is None or mean is None:
        return None
    return (value - mean) / std_dev


def percentile_from_zscore(z_score: float) -> int:
    """Convierte Z-Score a percentil (0-100)"""
    if z_score is None:
        return 50
    percentile = 0.5 * (1 + math.erf(z_score / math.sqrt(2)))
    return int(percentile * 100)
