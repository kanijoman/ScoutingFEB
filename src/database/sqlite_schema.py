"""
Esquema de base de datos SQLite para el sistema de scouting con ML.

Este módulo define la estructura de tablas optimizada para análisis de jugadores
y entrenamiento de modelos de Machine Learning con XGBoost.
"""

import sqlite3
from typing import Optional
import logging


# Definición del esquema SQL
SCHEMA_SQL = """
-- ============================================================================
-- TABLAS PRINCIPALES
-- ============================================================================

-- Tabla de jugadores (dimensión)
CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    position TEXT,  -- Base, Escolta, Alero, Ala-Pívot, Pívot
    height_cm REAL,
    birth_year INTEGER,  -- Año de nacimiento (para calcular edad)
    dorsal TEXT,  -- Dorsal (opcional, no relevante para ML)
    first_seen_date TEXT,  -- Primera vez que apareció en datos
    last_seen_date TEXT,   -- Última vez que apareció
    total_games INTEGER DEFAULT 0,
    years_experience INTEGER DEFAULT 0,  -- Años de experiencia estimados
    UNIQUE(name)  -- Solo nombre como unique (jugadores pueden cambiar de dorsal)
);

-- Tabla de equipos (dimensión)
CREATE TABLE IF NOT EXISTS teams (
    team_id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_code TEXT UNIQUE,
    team_name TEXT NOT NULL,
    UNIQUE(team_code)
);

-- Tabla de competiciones (dimensión)
CREATE TABLE IF NOT EXISTS competitions (
    competition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    competition_name TEXT NOT NULL,
    gender TEXT CHECK(gender IN ('masc', 'fem')),
    level TEXT,  -- ACB, LEB ORO, LF, LF2, etc.
    UNIQUE(competition_name, gender)
);

-- Tabla de niveles de competición por temporada (pesos dinámicos)
-- Permite modelar cambios en la jerarquía de competiciones a lo largo del tiempo
-- Ejemplo: LF2 era nivel 2 hasta 2021, pasó a nivel 3 con la Liga Challenge
CREATE TABLE IF NOT EXISTS competition_levels (
    level_id INTEGER PRIMARY KEY AUTOINCREMENT,
    competition_id INTEGER NOT NULL,
    season TEXT NOT NULL,
    competition_level INTEGER NOT NULL,  -- 1=máximo (ACB/LF), 2, 3, etc.
    weight REAL DEFAULT 1.0,  -- Peso relativo para normalización (1.0=referencia)
    level_description TEXT,  -- Ej: "Primera División Femenina"
    notes TEXT,  -- Cambios históricos o contexto
    FOREIGN KEY (competition_id) REFERENCES competitions(competition_id),
    UNIQUE(competition_id, season)
);

-- Tabla de partidos (hechos)
CREATE TABLE IF NOT EXISTS games (
    game_id INTEGER PRIMARY KEY,  -- game_code de FEB
    competition_id INTEGER,
    season TEXT,
    group_name TEXT,
    game_date TEXT,  -- ISO format
    home_team_id INTEGER,
    away_team_id INTEGER,
    home_score INTEGER,
    away_score INTEGER,
    score_diff INTEGER,  -- home - away
    venue TEXT,
    attendance INTEGER,
    FOREIGN KEY (competition_id) REFERENCES competitions(competition_id),
    FOREIGN KEY (home_team_id) REFERENCES teams(team_id),
    FOREIGN KEY (away_team_id) REFERENCES teams(team_id)
);

-- ============================================================================
-- ESTADÍSTICAS POR PARTIDO (para ML)
-- ============================================================================

-- Estadísticas de jugador por partido (hechos granulares)
CREATE TABLE IF NOT EXISTS player_game_stats (
    stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    is_home BOOLEAN,
    is_starter BOOLEAN,
    
    -- Información contextual del jugador
    age_at_game INTEGER,  -- Edad del jugador en este partido (años)
    games_played_season INTEGER,  -- Partidos jugados en la temporada hasta este momento
    
    -- Tiempo de juego
    minutes_played REAL,
    
    -- Puntos
    points INTEGER,
    field_goals_made INTEGER,
    field_goals_attempted INTEGER,
    field_goal_pct REAL,
    three_points_made INTEGER,
    three_points_attempted INTEGER,
    three_point_pct REAL,
    two_points_made INTEGER,
    two_points_attempted INTEGER,
    two_point_pct REAL,
    free_throws_made INTEGER,
    free_throws_attempted INTEGER,
    free_throw_pct REAL,
    
    -- Rebotes
    offensive_rebounds INTEGER,
    defensive_rebounds INTEGER,
    total_rebounds INTEGER,
    
    -- Pases y balones
    assists INTEGER,
    turnovers INTEGER,
    steals INTEGER,
    
    -- Defensa
    blocks INTEGER,
    blocks_received INTEGER,
    personal_fouls INTEGER,
    fouls_received INTEGER,
    
    -- Métricas avanzadas
    plus_minus INTEGER,
    efficiency_rating REAL,  -- Valoración
    usage_rate REAL,  -- % de posesiones usadas
    
    -- Métricas per-36 minutos (pace-adjusted)
    -- Normalizan el rendimiento eliminando el efecto de minutos jugados
    -- Fundamentales para comparar jugadores con diferentes roles/minutos
    points_per_36 REAL,  -- Puntos por 36 min
    rebounds_per_36 REAL,  -- Rebotes por 36 min
    assists_per_36 REAL,  -- Asistencias por 36 min
    steals_per_36 REAL,  -- Robos por 36 min
    blocks_per_36 REAL,  -- Tapones por 36 min
    turnovers_per_36 REAL,  -- Pérdidas por 36 min
    efficiency_per_36 REAL,  -- Eficiencia por 36 min
    
    -- Z-Scores normalizados (comparables entre épocas/ligas)
    -- Fórmula: Z = (valor - media_grupo) / std_grupo
    -- Grupo = nivel_competición + temporada
    z_points REAL,  -- Puntos normalizados
    z_efficiency REAL,  -- Eficiencia normalizada
    z_rebounds REAL,  -- Rebotes totales normalizados
    z_assists REAL,  -- Asistencias normalizadas
    z_usage REAL,  -- Uso normalizado
    
    -- Resultado del partido para el equipo
    team_won BOOLEAN,
    
    FOREIGN KEY (game_id) REFERENCES games(game_id),
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    UNIQUE(game_id, player_id)
);

-- ============================================================================
-- ESTADÍSTICAS AGREGADAS (features para ML)
-- ============================================================================

-- Estadísticas agregadas de jugador (rolling averages)
CREATE TABLE IF NOT EXISTS player_aggregated_stats (
    agg_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    season TEXT NOT NULL,
    competition_id INTEGER,
    
    -- Periodo de agregación
    games_played INTEGER,
    date_from TEXT,
    date_to TEXT,
    avg_age REAL,  -- Edad promedio durante este periodo
    
    -- Promedios por partido
    avg_minutes REAL,
    avg_points REAL,
    avg_field_goal_pct REAL,
    avg_three_point_pct REAL,
    avg_two_point_pct REAL,
    avg_free_throw_pct REAL,
    avg_offensive_rebounds REAL,
    avg_defensive_rebounds REAL,
    avg_total_rebounds REAL,
    avg_assists REAL,
    avg_turnovers REAL,
    avg_steals REAL,
    avg_blocks REAL,
    avg_personal_fouls REAL,
    avg_plus_minus REAL,
    avg_efficiency REAL,
    
    -- Totales
    total_points INTEGER,
    total_rebounds INTEGER,
    total_assists INTEGER,
    
    -- Consistencia (desviación estándar)
    std_points REAL,
    std_efficiency REAL,
    
    -- Tendencias (últimos N juegos)
    trend_points REAL,  -- Pendiente de regresión lineal
    trend_efficiency REAL,
    
    -- Métricas per-36 agregadas (pace-adjusted)
    avg_points_per_36 REAL,
    avg_rebounds_per_36 REAL,
    avg_assists_per_36 REAL,
    avg_efficiency_per_36 REAL,
    
    -- Porcentaje de victorias
    win_percentage REAL,
    
    -- Z-Scores agregados (comparación contextual)
    z_avg_points REAL,
    z_avg_efficiency REAL,
    z_avg_rebounds REAL,
    z_avg_assists REAL,
    
    -- Z-Scores para métricas per-36 (CRÍTICO para comparar roles diferentes)
    z_points_per_36 REAL,
    z_rebounds_per_36 REAL,
    z_assists_per_36 REAL,
    z_efficiency_per_36 REAL,
    
    -- Percentiles (comunicación clara para scouts)
    -- Percentil 90 = mejor que 90% de jugadores en su contexto
    percentile_points INTEGER,  -- 0-100
    percentile_efficiency INTEGER,
    percentile_rebounds INTEGER,
    percentile_assists INTEGER,
    
    -- Clasificación de rendimiento
    performance_tier TEXT CHECK(performance_tier IN 
        ('elite', 'very_good', 'above_average', 'average', 'below_average')),
    -- elite: percentil 95+, very_good: 80-95, above_average: 60-80, 
    -- average: 40-60, below_average: <40
    
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (competition_id) REFERENCES competitions(competition_id),
    UNIQUE(player_id, season, competition_id, date_from, date_to)
);

-- ============================================================================
-- CARACTERÍSTICAS CONTEXTUALES (features adicionales para ML)
-- ============================================================================

-- Características del equipo por partido
CREATE TABLE IF NOT EXISTS team_game_context (
    context_id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    
    -- Racha del equipo
    team_streak INTEGER,  -- Positivo = victorias, negativo = derrotas
    games_in_last_7_days INTEGER,
    days_since_last_game INTEGER,
    
    -- Posición en clasificación (si disponible)
    league_position INTEGER,
    
    -- Rendimiento reciente del equipo (últimos 5 partidos)
    team_last5_avg_points REAL,
    team_last5_avg_points_allowed REAL,
    team_last5_wins INTEGER,
    
    FOREIGN KEY (game_id) REFERENCES games(game_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    UNIQUE(game_id, team_id)
);

-- Rivalidades y factores del partido
CREATE TABLE IF NOT EXISTS game_context (
    game_id INTEGER PRIMARY KEY,
    is_playoff BOOLEAN,
    is_final BOOLEAN,
    is_derby BOOLEAN,  -- Partidos locales importantes
    rivalry_score REAL,  -- 0-1, basado en historial
    
    FOREIGN KEY (game_id) REFERENCES games(game_id)
);

-- ============================================================================
-- TARGETS PARA ML (variables objetivo)
-- ============================================================================

-- Targets de predicción por jugador
CREATE TABLE IF NOT EXISTS player_targets (
    target_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    game_id INTEGER NOT NULL,
    
    -- Targets de rendimiento para próximo partido
    next_game_points REAL,
    next_game_efficiency REAL,
    next_game_minutes REAL,
    
    -- Targets de rendimiento futuro (próximos N juegos)
    next5_avg_points REAL,
    next5_avg_efficiency REAL,
    next10_avg_points REAL,
    next10_avg_efficiency REAL,
    
    -- Target de clasificación: rendimiento
    performance_level TEXT CHECK(performance_level IN 
        ('very_poor', 'poor', 'average', 'good', 'excellent')),
    
    -- Target binario: superará su promedio
    will_exceed_avg_points BOOLEAN,
    will_exceed_avg_efficiency BOOLEAN,
    
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (game_id) REFERENCES games(game_id),
    UNIQUE(player_id, game_id)
);

-- ============================================================================
-- METADATOS Y TRACKING
-- ============================================================================

-- Tracking de procesamiento ETL
CREATE TABLE IF NOT EXISTS etl_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    process_name TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    status TEXT CHECK(status IN ('running', 'completed', 'failed')),
    records_processed INTEGER,
    error_message TEXT
);

-- Metadata de características para ML
CREATE TABLE IF NOT EXISTS feature_metadata (
    feature_id INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_name TEXT UNIQUE NOT NULL,
    feature_type TEXT CHECK(feature_type IN ('numeric', 'categorical', 'boolean')),
    description TEXT,
    importance_score REAL,  -- SHAP importance
    last_updated TEXT
);

-- ============================================================================
-- ÍNDICES PARA OPTIMIZACIÓN
-- ============================================================================

-- Índices para consultas frecuentes
CREATE INDEX IF NOT EXISTS idx_player_game_stats_player ON player_game_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_player_game_stats_game ON player_game_stats(game_id);
CREATE INDEX IF NOT EXISTS idx_player_game_stats_team ON player_game_stats(team_id);

CREATE INDEX IF NOT EXISTS idx_player_agg_player_season ON player_aggregated_stats(player_id, season);
CREATE INDEX IF NOT EXISTS idx_player_agg_competition ON player_aggregated_stats(competition_id);

CREATE INDEX IF NOT EXISTS idx_games_date ON games(game_date);
CREATE INDEX IF NOT EXISTS idx_games_competition ON games(competition_id);
CREATE INDEX IF NOT EXISTS idx_games_season ON games(season);

CREATE INDEX IF NOT EXISTS idx_players_name ON players(name);
CREATE INDEX IF NOT EXISTS idx_teams_name ON teams(team_name);

CREATE INDEX IF NOT EXISTS idx_targets_player ON player_targets(player_id);
CREATE INDEX IF NOT EXISTS idx_targets_game ON player_targets(game_id);

CREATE INDEX IF NOT EXISTS idx_comp_levels_season ON competition_levels(competition_id, season);
CREATE INDEX IF NOT EXISTS idx_player_stats_zscore ON player_game_stats(z_efficiency, z_points);
CREATE INDEX IF NOT EXISTS idx_player_agg_percentile ON player_aggregated_stats(percentile_efficiency, percentile_points);

-- ============================================================================
-- VISTAS ÚTILES PARA ML
-- ============================================================================

-- Vista con todas las features para un partido de jugador
CREATE VIEW IF NOT EXISTS ml_features_view AS
SELECT 
    pgs.stat_id,
    pgs.game_id,
    pgs.player_id,
    p.name as player_name,
    p.position,
    p.height_cm,
    p.birth_year,
    p.years_experience,
    
    -- Stats del partido
    pgs.*,
    
    -- Métricas per-36 del partido
    pgs.points_per_36,
    pgs.rebounds_per_36,
    pgs.assists_per_36,
    pgs.efficiency_per_36,
    
    -- Info del partido
    g.season,
    g.game_date,
    c.competition_name,
    c.gender,
    c.level,
    
    -- Stats agregadas del jugador
    pas.avg_points,
    pas.avg_efficiency,
    pas.avg_minutes,
    pas.win_percentage,
    pas.std_points,
    pas.trend_points,
    
    -- Métricas per-36 agregadas
    pas.avg_points_per_36,
    pas.avg_rebounds_per_36,
    pas.avg_assists_per_36,
    pas.avg_efficiency_per_36,
    
    -- Z-Scores normalizados
    pgs.z_points,
    pgs.z_efficiency,
    pgs.z_rebounds,
    pgs.z_assists,
    pas.z_avg_points,
    pas.z_avg_efficiency,
    pas.z_points_per_36,
    pas.z_efficiency_per_36,
    
    -- Percentiles
    pas.percentile_points,
    pas.percentile_efficiency,
    pas.performance_tier,
    
    -- Contexto del equipo
    tgc.team_streak,
    tgc.days_since_last_game,
    tgc.team_last5_wins,
    
    -- Contexto del juego
    gc.is_playoff,
    gc.is_derby
    
FROM player_game_stats pgs
JOIN players p ON pgs.player_id = p.player_id
JOIN games g ON pgs.game_id = g.game_id
JOIN competitions c ON g.competition_id = c.competition_id
LEFT JOIN player_aggregated_stats pas ON pgs.player_id = pas.player_id 
    AND g.season = pas.season
    AND g.competition_id = pas.competition_id
LEFT JOIN team_game_context tgc ON pgs.game_id = tgc.game_id 
    AND pgs.team_id = tgc.team_id
LEFT JOIN game_context gc ON pgs.game_id = gc.game_id;

-- Vista de dataset completo para entrenamiento
CREATE VIEW IF NOT EXISTS ml_training_dataset AS
SELECT 
    mlf.*,
    pt.next_game_points as target_next_points,
    pt.next_game_efficiency as target_next_efficiency,
    pt.next5_avg_points as target_next5_points,
    pt.performance_level as target_performance,
    pt.will_exceed_avg_points as target_exceed_avg
FROM ml_features_view mlf
LEFT JOIN player_targets pt ON mlf.player_id = pt.player_id 
    AND mlf.game_id = pt.game_id;
"""


class SQLiteSchemaManager:
    """Gestor del esquema de la base de datos SQLite."""
    
    def __init__(self, db_path: str = "scouting_feb.db"):
        """
        Inicializar gestor de esquema.
        
        Args:
            db_path: Ruta al archivo de base de datos SQLite
        """
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
    
    def create_database(self) -> bool:
        """
        Crear la base de datos con todas las tablas, índices y vistas.
        
        Returns:
            True si se creó exitosamente, False en caso contrario
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Ejecutar todo el esquema
            cursor.executescript(SCHEMA_SQL)
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"✓ Base de datos creada exitosamente: {self.db_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"✗ Error creando base de datos: {e}")
            return False
    
    def get_table_info(self, table_name: str) -> list:
        """
        Obtener información de una tabla.
        
        Args:
            table_name: Nombre de la tabla
            
        Returns:
            Lista de tuplas con información de columnas
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(f"PRAGMA table_info({table_name})")
            info = cursor.fetchall()
            
            conn.close()
            return info
            
        except Exception as e:
            self.logger.error(f"Error obteniendo info de tabla {table_name}: {e}")
            return []
    
    def list_tables(self) -> list:
        """
        Listar todas las tablas en la base de datos.
        
        Returns:
            Lista de nombres de tablas
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            return tables
            
        except Exception as e:
            self.logger.error(f"Error listando tablas: {e}")
            return []
    
    def get_row_count(self, table_name: str) -> int:
        """
        Contar registros en una tabla.
        
        Args:
            table_name: Nombre de la tabla
            
        Returns:
            Número de registros
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            
            conn.close()
            return count
            
        except Exception as e:
            self.logger.error(f"Error contando registros en {table_name}: {e}")
            return 0
    
    def print_schema_summary(self):
        """Imprimir resumen del esquema de la base de datos."""
        tables = self.list_tables()
        
        print("\n" + "="*70)
        print("ESQUEMA DE BASE DE DATOS SQLITE - SCOUTING FEB")
        print("="*70)
        print(f"\nBase de datos: {self.db_path}")
        print(f"Total de tablas: {len(tables)}\n")
        
        for table in tables:
            count = self.get_row_count(table)
            print(f"  • {table:<30} {count:>10} registros")
        
        print("="*70 + "\n")


def main():
    """Crear la base de datos con el esquema completo."""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Crear base de datos
    schema_manager = SQLiteSchemaManager("scouting_feb.db")
    
    print("Creando base de datos SQLite con esquema completo...")
    success = schema_manager.create_database()
    
    if success:
        print("✓ Base de datos creada exitosamente\n")
        schema_manager.print_schema_summary()
    else:
        print("✗ Error creando base de datos")


if __name__ == "__main__":
    main()
