"""
Módulo ETL para transformar datos de MongoDB raw a SQLite procesado.

Este módulo extrae datos de partidos desde MongoDB, los transforma en un formato
estructurado y relacional, y los carga en SQLite para análisis y ML.
"""

import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.mongodb_client import MongoDBClient
from database.sqlite_schema import SQLiteSchemaManager
from ml.normalization import ZScoreNormalizer, initialize_competition_levels
from ml.advanced_stats import calculate_all_advanced_stats
from ml.name_normalizer import NameNormalizer
from ml.player_identity_matcher import PlayerIdentityMatcher
from ml.career_potential_calculator import CareerPotentialCalculator
from ml.profile_metrics_calculator import ProfileMetricsCalculator, ProfileQueryBuilder
from ml.profile_potential_scorer import EligibilityChecker, PotentialScoreCalculator
from ml.profile_metrics_computer import ProfileMetricsComputer
from ml.player_aggregator import StatsExtractor, StatsAggregator, AggregationQueryBuilder
import numpy as np


class FEBDataETL:
    """Proceso ETL de MongoDB a SQLite para datos de FEB."""
    
    def __init__(self, mongodb_uri: str = "mongodb://localhost:27017/",
                 mongodb_db: str = "scouting_feb",
                 sqlite_path: str = "scouting_feb.db",
                 use_profiles: bool = True):
        """
        Inicializar el proceso ETL.
        
        Args:
            mongodb_uri: URI de conexión a MongoDB
            mongodb_db: Nombre de la base de datos MongoDB
            sqlite_path: Ruta al archivo SQLite
            use_profiles: Si True, usa sistema de perfiles. Si False, usa jugadores únicos
        """
        self.mongo_client = MongoDBClient(mongodb_uri, mongodb_db)
        self.mongo_db = self.mongo_client.db  # Acceso directo a la BD
        self.sqlite_path = sqlite_path
        self.logger = logging.getLogger(__name__)
        self.use_profiles = use_profiles
        
        # Inicializar normalizador de nombres y matcher
        self.name_normalizer = NameNormalizer()
        self.identity_matcher = PlayerIdentityMatcher(sqlite_path) if use_profiles else None
        
        # Crear esquema SQLite si no existe
        schema_manager = SQLiteSchemaManager(sqlite_path)
        schema_manager.create_database()
    
    def get_connection(self) -> sqlite3.Connection:
        """Obtener conexión a SQLite."""
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_processed_game_ids(self, conn: sqlite3.Connection) -> set:
        """Obtener IDs de partidos ya procesados en SQLite.
        
        Args:
            conn: Conexión SQLite
            
        Returns:
            Set con los game_ids ya procesados
        """
        cursor = conn.cursor()
        cursor.execute("SELECT game_id FROM games")
        return {row[0] for row in cursor.fetchall()}
    
    # =========================================================================
    # EXTRACT - Extracción desde MongoDB
    # =========================================================================
    
    def extract_games_from_mongodb(self, collection_name: str, 
                                   limit: Optional[int] = None,
                                   exclude_game_ids: Optional[set] = None) -> List[Dict]:
        """
        Extraer partidos desde MongoDB.
        
        Args:
            collection_name: Nombre de la colección ('all_feb_games_masc' o 'all_feb_games_fem')
            limit: Límite opcional de documentos
            exclude_game_ids: Set de game_ids a excluir (para modo incremental)
            
        Returns:
            Lista de documentos de partidos
        """
        self.logger.info(f"Extrayendo partidos desde {collection_name}...")
        
        collection = self.mongo_db[collection_name]
        
        # Para modo incremental con muchos IDs a excluir, ordenar por _id descendente
        # y procesar por lotes pequeños hasta encontrar suficientes partidos nuevos
        if exclude_game_ids and len(exclude_game_ids) > 1000:
            self.logger.info(f"Modo incremental optimizado: procesando partidos recientes primero...")
            exclude_codes_str = {str(gid) for gid in exclude_game_ids}
            
            # Ordenar por fecha/ID descendente para obtener los más recientes primero
            cursor = collection.find({}).sort([("_id", -1)])
            
            games = []
            processed = 0
            batch_size = 500
            
            # Procesar en lotes hasta encontrar suficientes nuevos
            for game in cursor:
                processed += 1
                game_code = game["HEADER"]["game_code"]
                
                # Si no está en la lista de excluidos, es nuevo
                if game_code not in exclude_codes_str:
                    games.append(game)
                
                # Parar si ya tenemos suficientes o hemos procesado muchos sin encontrar nuevos
                if len(games) >= 500 or (processed > 2000 and len(games) > 0):
                    break
            
            self.logger.info(f"✓ Procesados {processed} documentos, encontrados {len(games)} partidos nuevos")
            
        else:
            # Modo normal: extraer todos (para colecciones pequeñas o sin exclusión)
            cursor = collection.find({})
            
            if limit:
                cursor = cursor.limit(limit)
            
            games = list(cursor)
            self.logger.info(f"✓ Extraídos {len(games)} partidos desde MongoDB")
            
            # Filtrar si hay exclusiones
            if exclude_game_ids:
                exclude_codes_str = {str(gid) for gid in exclude_game_ids}
                games_before = len(games)
                games = [g for g in games if g["HEADER"]["game_code"] not in exclude_codes_str]
                games_excluded = games_before - len(games)
                self.logger.info(f"Filtrados {games_excluded} ya procesados, {len(games)} nuevos")
        
        return games
    
    # =========================================================================
    # TRANSFORM - Transformación de datos
    # =========================================================================
    
    def calculate_match_weight(self, group_name: str) -> float:
        """
        Calcular el peso de un partido según su fase/importancia.
        
        Partidos más importantes (play-offs, finales, copas) reciben mayor peso
        para reflejar que el rendimiento en estos partidos es más significativo.
        
        Args:
            group_name: Nombre del grupo/fase del partido
            
        Returns:
            Peso del partido (1.0 = regular, >1.0 = importante)
        """
        if not group_name:
            return 1.0
        
        group_lower = group_name.lower()
        
        # Orden importante: comprobar términos más específicos primero
        
        # Supercopa: peso moderado (1.2x) - ANTES de Copa para evitar match con "copa"
        if any(keyword in group_lower for keyword in ["supercopa", "super copa"]):
            return 1.2
        
        # Finales: máximo peso (1.5x) - Buscar "final" que no sea parte de "semifinal" o "cuartos de final"
        if "final" in group_lower and not any(prefix in group_lower for prefix in ["semifinal", "cuartos", "octavos"]):
            return 1.5
        
        # Play-offs: alto peso (1.4x) - Incluye semifinales, cuartos, etc.
        if any(keyword in group_lower for keyword in ["play", "playoff", "eliminatoria", "semifinal", "cuartos", "octavos"]):
            return 1.4
        
        # Copa: alto peso (1.3x)
        if any(keyword in group_lower for keyword in ["copa"]):
            return 1.3
        
        # Liga regular: peso base
        return 1.0
    
    def transform_game_data(self, mongo_game: Dict) -> Dict:
        """
        Transformar un partido de MongoDB al formato SQLite.
        
        Args:
            mongo_game: Documento de partido de MongoDB
            
        Returns:
            Diccionario con datos transformados
        """
        header = mongo_game.get("HEADER", {})
        boxscore = mongo_game.get("BOXSCORE", {})
        
        # Extraer información básica del partido
        group_name = header.get("group", "")
        
        game_data = {
            "game_id": int(header.get("game_code", 0)),
            "season": header.get("season", ""),
            "group_name": group_name,
            "game_date": header.get("starttime", ""),
            "venue": header.get("location", ""),
            "attendance": None,  # Si está disponible en los datos
            "competition_name": header.get("competition_name", ""),
            "gender": header.get("gender", "masc"),
            "match_weight": self.calculate_match_weight(group_name)
        }
        
        # Extraer información de equipos
        teams = header.get("TEAM", [])
        if len(teams) >= 2:
            game_data["home_team"] = {
                "code": teams[0].get("id", ""),
                "name": teams[0].get("name", ""),
                "score": int(teams[0].get("pts", 0))
            }
            game_data["away_team"] = {
                "code": teams[1].get("id", ""),
                "name": teams[1].get("name", ""),
                "score": int(teams[1].get("pts", 0))
            }
            game_data["home_score"] = game_data["home_team"]["score"]
            game_data["away_score"] = game_data["away_team"]["score"]
            game_data["score_diff"] = game_data["home_score"] - game_data["away_score"]
        
        # Extraer estadísticas de jugadores
        game_data["player_stats"] = []
        
        if isinstance(boxscore, dict):
            # Manejar formato nuevo: BOXSCORE = {'TEAM': [team1, team2]}
            if 'TEAM' in boxscore and isinstance(boxscore['TEAM'], list):
                teams_list = boxscore['TEAM']
                for team_idx, team_data in enumerate(teams_list):
                    if isinstance(team_data, dict):
                        players = team_data.get("PLAYER", [])
                        team_won = team_data.get("win_lose", "L") == "W"
                        
                        # El primer equipo (idx=0) suele ser local
                        is_home = team_idx == 0
                        
                        for player in players:
                            player_stat = self._transform_player_stats(
                                player, is_home, team_won, game_data.get("game_date")
                            )
                            game_data["player_stats"].append(player_stat)
            
            # Manejar formato antiguo: BOXSCORE = {'1': team1, '2': team2}
            else:
                for team_key, team_data in boxscore.items():
                    if isinstance(team_data, dict):
                        players = team_data.get("PLAYER", [])
                        team_won = team_data.get("won", "0") == "1"
                        
                        # Determinar si es equipo local (team_key = "1" suele ser local)
                        is_home = team_key == "1"
                        
                        for player in players:
                            player_stat = self._transform_player_stats(
                                player, is_home, team_won, game_data.get("game_date")
                            )
                            game_data["player_stats"].append(player_stat)
        
        return game_data
    
    def _transform_player_stats(self, player: Dict, is_home: bool, 
                                team_won: bool, game_date: str = None) -> Dict:
        """
        Transformar estadísticas de un jugador.
        
        Delegado a StatsTransformer para mantener bajo la complejidad.
        
        Args:
            player: Datos del jugador del boxscore
            is_home: Si es equipo local
            team_won: Si su equipo ganó
            game_date: Fecha del partido (para calcular edad)
            
        Returns:
            Diccionario con estadísticas transformadas
        """
        from .stats_transformer import StatsTransformer
        from .advanced_stats import calculate_all_advanced_stats
        
        return StatsTransformer.transform_player_stats(
            player=player,
            is_home=is_home,
            team_won=team_won,
            game_date=game_date,
            advanced_stats_calculator=calculate_all_advanced_stats
        )
    
    # =========================================================================
    # LOAD - Carga a SQLite
    # =========================================================================
    
    def load_or_get_player_profile(
        self,
        conn: sqlite3.Connection,
        name: str,
        team_id: int,
        season: str,
        competition_id: int,
        game_date: str,
        feb_id: str = None,
        dorsal: str = None,
        birth_year: int = None
    ) -> int:
        """
        Crear o obtener un perfil de jugador.
        
        En el sistema de perfiles, cada combinación única de nombre+equipo+temporada
        genera un perfil separado. La consolidación se hace posteriormente.
        
        Args:
            conn: Conexión SQLite
            name: Nombre del jugador
            team_id: ID del equipo
            season: Temporada
            competition_id: ID de competición
            game_date: Fecha del partido
            feb_id: ID FEB del jugador (opcional)
            dorsal: Dorsal (opcional)
            birth_year: Año de nacimiento (opcional)
            
        Returns:
            profile_id
        """
        cursor = conn.cursor()
        
        # Normalizar nombre
        name_normalized = self.name_normalizer.normalize_name(name)
        
        # Intentar encontrar perfil existente
        cursor.execute("""
            SELECT profile_id, first_game_date, last_game_date, total_games,
                   birth_year, dorsal
            FROM player_profiles
            WHERE name_normalized = ? 
                AND team_id = ? 
                AND season = ?
        """, (name_normalized, team_id, season))
        
        existing = cursor.fetchone()
        
        if existing:
            profile_id, first_date, last_date, total_games, existing_birth_year, existing_dorsal = existing
            
            # Actualizar información del perfil
            new_first = min(first_date, game_date) if first_date else game_date
            new_last = max(last_date, game_date) if last_date else game_date
            
            # Actualizar birth_year y dorsal si no existían
            final_birth_year = existing_birth_year if existing_birth_year else birth_year
            final_dorsal = existing_dorsal if existing_dorsal else dorsal
            
            cursor.execute("""
                UPDATE player_profiles
                SET first_game_date = ?,
                    last_game_date = ?,
                    total_games = total_games + 1,
                    birth_year = ?,
                    dorsal = ?,
                    updated_at = ?
                WHERE profile_id = ?
            """, (new_first, new_last, final_birth_year, final_dorsal,
                  datetime.now().isoformat(), profile_id))
            
            return profile_id
        
        else:
            # Crear nuevo perfil
            cursor.execute("""
                INSERT INTO player_profiles (
                    feb_id, name_raw, name_normalized,
                    team_id, season, competition_id,
                    first_game_date, last_game_date, total_games,
                    birth_year, dorsal
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """, (feb_id, name, name_normalized, team_id, season, competition_id,
                  game_date, game_date, birth_year, dorsal))
            
            return cursor.lastrowid
    
    def load_competition(self, conn: sqlite3.Connection, comp_name: str, 
                        gender: str) -> int:
        """
        Insertar o recuperar ID de competición.
        
        Args:
            conn: Conexión SQLite
            comp_name: Nombre de la competición
            gender: 'masc' o 'fem'
            
        Returns:
            competition_id
        """
        cursor = conn.cursor()
        
        # Intentar insertar
        try:
            cursor.execute("""
                INSERT INTO competitions (competition_name, gender)
                VALUES (?, ?)
            """, (comp_name, gender))
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Ya existe, obtener ID
            cursor.execute("""
                SELECT competition_id FROM competitions
                WHERE competition_name = ? AND gender = ?
            """, (comp_name, gender))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def load_team(self, conn: sqlite3.Connection, team_code: str, 
                 team_name: str) -> int:
        """
        Insertar o recuperar ID de equipo.
        
        Args:
            conn: Conexión SQLite
            team_code: Código del equipo
            team_name: Nombre del equipo
            
        Returns:
            team_id
        """
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO teams (team_code, team_name)
                VALUES (?, ?)
            """, (team_code, team_name))
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            cursor.execute("""
                SELECT team_id FROM teams WHERE team_code = ?
            """, (team_code,))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def load_player(self, conn: sqlite3.Connection, name: str, 
                   first_seen: str, dorsal: str = None, 
                   birth_year: int = None) -> int:
        """
        Insertar o recuperar ID de jugador.
        
        Args:
            conn: Conexión SQLite
            name: Nombre del jugador
            first_seen: Fecha de primera aparición
            dorsal: Dorsal del jugador (opcional)
            birth_year: Año de nacimiento (opcional)
            
        Returns:
            player_id
        """
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO players (name, first_seen_date, last_seen_date, 
                                   total_games, dorsal, birth_year)
                VALUES (?, ?, ?, 1, ?, ?)
            """, (name, first_seen, first_seen, dorsal, birth_year))
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Ya existe, actualizar last_seen, total_games y birth_year si no existe
            cursor.execute("""
                UPDATE players 
                SET last_seen_date = ?,
                    total_games = total_games + 1,
                    dorsal = COALESCE(dorsal, ?),
                    birth_year = COALESCE(birth_year, ?)
                WHERE name = ?
            """, (first_seen, dorsal, birth_year, name))
            
            cursor.execute("""
                SELECT player_id FROM players WHERE name = ?
            """, (name,))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def load_game(self, conn: sqlite3.Connection, game_data: Dict) -> bool:
        """
        Cargar un partido completo a SQLite.
        
        Args:
            conn: Conexión SQLite
            game_data: Datos del partido transformados
            
        Returns:
            True si se cargó exitosamente
        """
        try:
            cursor = conn.cursor()
            
            # 1. Cargar competición
            comp_id = self.load_competition(
                conn, 
                game_data["competition_name"],
                game_data["gender"]
            )
            
            # 2. Cargar equipos
            home_team_id = self.load_team(
                conn,
                game_data["home_team"]["code"],
                game_data["home_team"]["name"]
            )
            
            away_team_id = self.load_team(
                conn,
                game_data["away_team"]["code"],
                game_data["away_team"]["name"]
            )
            
            # 3. Cargar partido
            cursor.execute("""
                INSERT OR REPLACE INTO games (
                    game_id, competition_id, season, group_name, game_date,
                    home_team_id, away_team_id, home_score, away_score, score_diff, venue, match_weight
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game_data["game_id"],
                comp_id,
                game_data["season"],
                game_data["group_name"],
                game_data["game_date"],
                home_team_id,
                away_team_id,
                game_data["home_score"],
                game_data["away_score"],
                game_data["score_diff"],
                game_data["venue"],
                game_data["match_weight"]
            ))
            
            # 4. Cargar estadísticas de jugadores
            for player_stat in game_data["player_stats"]:
                # Determinar team_id
                team_id = home_team_id if player_stat["is_home"] else away_team_id
                
                if self.use_profiles:
                    # Usar sistema de perfiles
                    profile_id = self.load_or_get_player_profile(
                        conn,
                        name=player_stat["name"],
                        team_id=team_id,
                        season=game_data["season"],
                        competition_id=comp_id,
                        game_date=game_data["game_date"],
                        dorsal=player_stat.get("dorsal"),
                        birth_year=player_stat.get("birth_year")
                    )
                    player_id = profile_id
                    
                else:
                    # Sistema legacy: jugadores únicos por nombre
                    player_id = self.load_player(
                        conn,
                        name=player_stat["name"],
                        first_seen=game_data["game_date"],
                        dorsal=player_stat.get("dorsal"),
                        birth_year=player_stat.get("birth_year")
                    )
                
                # Insertar estadísticas del jugador en el partido
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO player_game_stats (
                            game_id, player_id, team_id, is_home, is_starter,
                            age_at_game, games_played_season,
                            minutes_played, points,
                            field_goals_made, field_goals_attempted, field_goal_pct,
                            three_points_made, three_points_attempted, three_point_pct,
                            two_points_made, two_points_attempted, two_point_pct,
                            free_throws_made, free_throws_attempted, free_throw_pct,
                            offensive_rebounds, defensive_rebounds, total_rebounds,
                            assists, turnovers, steals,
                            blocks, blocks_received, personal_fouls, fouls_received,
                            plus_minus, efficiency_rating,
                            true_shooting_pct, effective_fg_pct, offensive_rating,
                            player_efficiency_rating, turnover_pct,
                            offensive_rebound_pct, defensive_rebound_pct,
                            free_throw_rate, assist_to_turnover_ratio, usage_rate,
                            win_shares, win_shares_per_36,
                            team_won
                        ) VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                        )
                    """, (
                        game_data["game_id"], player_id, team_id,
                        player_stat["is_home"], player_stat["is_starter"],
                        player_stat.get("age_at_game"),
                        None,  # games_played_season - se calculará después en agregados
                        player_stat["minutes_played"], player_stat["points"],
                        player_stat["field_goals_made"], player_stat["field_goals_attempted"],
                        player_stat["field_goal_pct"],
                        player_stat["three_points_made"], player_stat["three_points_attempted"],
                        player_stat["three_point_pct"],
                        player_stat["two_points_made"], player_stat["two_points_attempted"],
                        player_stat["two_point_pct"],
                        player_stat["free_throws_made"], player_stat["free_throws_attempted"],
                        player_stat["free_throw_pct"],
                        player_stat["offensive_rebounds"], player_stat["defensive_rebounds"],
                        player_stat["total_rebounds"],
                        player_stat["assists"], player_stat["turnovers"], player_stat["steals"],
                        player_stat["blocks"], player_stat["blocks_received"],
                        player_stat["personal_fouls"], player_stat["fouls_received"],
                        player_stat["plus_minus"], player_stat["efficiency_rating"],
                        player_stat["true_shooting_pct"], player_stat["effective_fg_pct"],
                        player_stat["offensive_rating"], player_stat["player_efficiency_rating"],
                        player_stat["turnover_pct"], player_stat["offensive_rebound_pct"],
                        player_stat["defensive_rebound_pct"], player_stat["free_throw_rate"],
                        player_stat["assist_to_turnover_ratio"], player_stat["usage_rate"],
                        player_stat["win_shares"], player_stat["win_shares_per_36"],
                        player_stat["team_won"]
                    ))
                except Exception as insert_error:
                    self.logger.error(f"Error insertando jugador {player_stat.get('name')}: {insert_error}")
                    self.logger.error(f"Claves en player_stat: {list(player_stat.keys())}")
                    raise
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error cargando partido {game_data.get('game_id')}: {e}")
            return False
    
    # =========================================================================
    # GESTIÓN DE PERFILES E IDENTIDADES
    # =========================================================================
    
    def compute_profile_metrics(self, conn: sqlite3.Connection):
        """
        Calculate aggregated metrics for each player profile.
        
        Uses ProfileMetricsComputer helper to orchestrate metric calculation.
        
        Args:
            conn: SQLite connection
        """
        if not self.use_profiles:
            return
        
        self.logger.info("Calculando métricas de perfiles...")
        
        computer = ProfileMetricsComputer(logger=self.logger)
        computer.compute_all_profiles(conn)
    
    def generate_identity_candidates(
        self,
        conn: sqlite3.Connection,
        min_score: float = 0.50
    ):
        """
        Generar candidatos de matching entre perfiles.
        
        Args:
            conn: Conexión SQLite
            min_score: Score mínimo para considerar candidato
        """
        if not self.use_profiles or not self.identity_matcher:
            return
        
        self.logger.info("Generando candidatos de matching de identidades...")
        self.logger.info(f"  Threshold mínimo: {min_score}")
        
        candidates_count = self.identity_matcher.generate_all_candidates(min_score=min_score)
        
        self.logger.info(f"✓ Generados {candidates_count} candidatos")
        
        # Mostrar resumen de candidatos de alta confianza
        high_confidence = self.identity_matcher.get_high_confidence_candidates(min_score=0.70)
        
        if high_confidence:
            self.logger.info(f"\n  Candidatos de alta confianza (score >= 0.70): {len(high_confidence)}")
            
            # Mostrar top 10
            for i, candidate in enumerate(high_confidence[:10], 1):
                self.logger.info(f"    {i}. [{candidate['candidate_score']:.2f}] "
                               f"{candidate['name_1']} ({candidate['season_1']}) <-> "
                               f"{candidate['name_2']} ({candidate['season_2']})")
    
    @staticmethod
    def calculate_confidence_multiplier(games_played: int, total_minutes: float,
                                       avg_minutes: float) -> float:
        """
        Calcular multiplicador de confianza basado en muestra estadística.
        
        Evalúa la fiabilidad de las estadísticas de un jugador basándose en:
        - Número de partidos jugados
        - Total de minutos acumulados
        - Rol en el equipo (minutos promedio)
        
        Args:
            games_played: Número total de partidos
            total_minutes: Minutos totales jugados
            avg_minutes: Promedio de minutos por partido
            
        Returns:
            float: Multiplicador entre 0.0 y 1.0
                - 1.0 = Máxima confianza (muestra grande y representativa)
                - 0.5 = Confianza media
                - 0.0 = Sin confianza (muestra insuficiente)
        """
        # Sub-score 1: Número de partidos (0-1)
        if games_played >= 15:
            games_conf = 1.0
        elif games_played >= 10:
            games_conf = 0.9
        elif games_played >= 8:
            games_conf = 0.7
        elif games_played >= 5:
            games_conf = 0.5
        else:
            games_conf = 0.2  # Penalización fuerte
        
        # Sub-score 2: Minutos totales (0-1)
        if total_minutes >= 200:
            minutes_conf = 1.0
        elif total_minutes >= 120:
            minutes_conf = 0.8
        elif total_minutes >= 80:
            minutes_conf = 0.6
        else:
            minutes_conf = 0.3
        
        # Sub-score 3: Rol en equipo (minutos promedio) (0-1)
        if avg_minutes >= 15:
            role_conf = 1.0  # Jugador importante
        elif avg_minutes >= 10:
            role_conf = 0.8
        elif avg_minutes >= 5:
            role_conf = 0.5
        else:
            role_conf = 0.3  # Rol marginal
        
        # Combinación (peso equilibrado)
        confidence = (0.40 * games_conf + 
                      0.30 * minutes_conf + 
                      0.30 * role_conf)
        
        return confidence
    
    def calculate_profile_potential_scores(self, conn: sqlite3.Connection):
        """
        Calculate potential scores for player profiles.
        
        This score combines:
        - Age and projection
        - Improvement trends
        - Consistency
        - Advanced metrics
        
        Includes eligibility filters and confidence weighting
        to avoid biases from outliers with small samples.
        
        Args:
            conn: SQLite connection
        """
        if not self.use_profiles:
            return
        
        self.logger.info("Calculando scores de potencial...")
        self.logger.info(f"  Filtros de elegibilidad: games>={EligibilityChecker.MIN_GAMES_FOR_POTENTIAL}, "
                        f"total_min>={EligibilityChecker.MIN_TOTAL_MINUTES}, "
                        f"avg_min>={EligibilityChecker.MIN_AVG_MINUTES}")
        
        cursor = conn.cursor()
        
        # Get profiles with metrics, competition level, and team context
        cursor.execute("""
            SELECT 
                pp.profile_id,
                pp.season,
                pp.birth_year,
                ppm.avg_z_offensive_rating,
                ppm.avg_z_player_efficiency_rating,
                ppm.std_offensive_rating,
                ppm.std_points,
                ppm.games_played,
                ppm.total_minutes,
                ppm.avg_minutes,
                ppm.avg_true_shooting_pct,
                c.competition_name,
                cl.competition_level,
                ppm.pts_per_36,
                ppm.momentum_index,
                ppm.trend_points,
                ppm.cv_points,
                ppm.stability_index,
                ppm.efficiency_vs_team_avg,
                ppm.player_pts_share,
                ppm.last_5_games_pts,
                ppm.last_10_games_pts
            FROM player_profiles pp
            JOIN player_profile_metrics ppm ON pp.profile_id = ppm.profile_id
            LEFT JOIN competitions c ON pp.competition_id = c.competition_id
            LEFT JOIN competition_levels cl ON pp.competition_id = cl.competition_id 
                AND pp.season = cl.season
        """)
        
        profiles = cursor.fetchall()
        
        eligible_count = 0
        ineligible_count = 0
        
        for profile in profiles:
            (profile_id, season, birth_year, avg_z_oer, avg_z_per, std_oer, 
             std_points, games_played, total_minutes, avg_minutes, avg_ts_pct,
             competition_name, competition_level, pts_per_36, momentum_index,
             trend_points, cv_points, stability_index, efficiency_vs_team_avg,
             player_pts_share, last_5_games_pts, last_10_games_pts) = profile
            
            # Check eligibility
            meets_eligibility, eligibility_notes = EligibilityChecker.check_eligibility(
                games_played, total_minutes, avg_minutes
            )
            
            eligibility_note_str = "; ".join(eligibility_notes) if eligibility_notes else None
            
            if meets_eligibility:
                eligible_count += 1
            else:
                ineligible_count += 1
            
            # Calculate age and temporal weight
            age = PotentialScoreCalculator.calculate_age_from_season(season, birth_year)
            temporal_weight = PotentialScoreCalculator.calculate_temporal_weight(season)
            
            # Calculate component scores
            age_score = PotentialScoreCalculator.calculate_age_projection_score(age)
            perf_score = PotentialScoreCalculator.calculate_performance_score(
                avg_z_oer, avg_z_per, competition_level
            )
            consistency_score = PotentialScoreCalculator.calculate_consistency_score(
                cv_points, std_oer
            )
            adv_metrics_score = PotentialScoreCalculator.calculate_advanced_metrics_score(
                avg_ts_pct, efficiency_vs_team_avg
            )
            momentum_score = PotentialScoreCalculator.calculate_momentum_score(
                momentum_index, trend_points
            )
            production_score = PotentialScoreCalculator.calculate_production_score(
                pts_per_36, player_pts_share
            )
            
            # Calculate composite score
            base_potential_score = PotentialScoreCalculator.calculate_composite_potential_score(
                age_score, perf_score, production_score, consistency_score,
                adv_metrics_score, momentum_score
            )
            
            # Apply temporal adjustment
            base_potential_score = PotentialScoreCalculator.apply_temporal_adjustment(
                base_potential_score, temporal_weight
            )
            
            # Apply confidence multiplier
            confidence_score = self.calculate_confidence_multiplier(
                games_played=games_played or 0,
                total_minutes=total_minutes or 0.0,
                avg_minutes=avg_minutes or 0.0
            )
            
            potential_score = base_potential_score * confidence_score
            
            # Determine tier and special flags
            tier = PotentialScoreCalculator.determine_potential_tier(potential_score)
            is_young_talent, is_consistent = PotentialScoreCalculator.calculate_special_flags(
                age, perf_score, consistency_score, meets_eligibility
            )
            
            # Insert potential score
            cursor.execute("""
                INSERT OR REPLACE INTO player_profile_potential (
                    profile_id, age_projection_score, performance_trend_score,
                    consistency_score, advanced_metrics_score, 
                    base_potential_score, confidence_score, potential_score,
                    potential_tier, meets_eligibility, eligibility_notes,
                    is_young_talent, is_consistent_performer,
                    season
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile_id, age_score, perf_score, consistency_score,
                adv_metrics_score, base_potential_score, confidence_score, potential_score,
                tier, meets_eligibility, eligibility_note_str,
                is_young_talent, is_consistent, season
            ))
        
        conn.commit()
        
        self.logger.info(f"✓ Scores de potencial calculados para {len(profiles)} perfiles")
        if len(profiles) > 0:
            self.logger.info(f"  ✓ Elegibles: {eligible_count} ({eligible_count/len(profiles)*100:.1f}%)")
            self.logger.info(f"  ⚠ No elegibles: {ineligible_count} ({ineligible_count/len(profiles)*100:.1f}%)")
        else:
            self.logger.info(f"  ✓ Elegibles: 0 (0.0%)")
            self.logger.info(f"  ⚠ No elegibles: 0 (0.0%)")
    
    def calculate_team_strength_factors(self, conn: sqlite3.Connection) -> Dict[Tuple[int, str], float]:
        """
        Calcular factores de ajuste por contexto de equipo.
        
        Para cada equipo/temporada, calcula un factor basado en win_percentage
        normalizado por competición. Esto permite contextualizar el rendimiento
        de jugadores según la fuerza de su equipo.
        
        Principio: Equipos fuertes → ligero boost (+5-8%)
                   Equipos débiles → ligero dampening (-5-8%)
        
        Returns:
            Dict[(team_id, season): team_factor] donde team_factor ∈ [0.94, 1.06]
        """
        cursor = conn.cursor()
        team_factors = {}
        
        # Por cada competición/temporada
        cursor.execute("""
            SELECT DISTINCT competition_id, season
            FROM games
            WHERE competition_id IS NOT NULL
        """)
        
        contexts = cursor.fetchall()
        
        for comp_id, season in contexts:
            # Calcular win_percentage para cada equipo en esta comp/season desde games
            cursor.execute("""
                SELECT 
                    t.team_id,
                    COUNT(*) as games,
                    CAST(SUM(CASE 
                        WHEN (g.home_team_id = t.team_id AND g.home_score > g.away_score) OR
                             (g.away_team_id = t.team_id AND g.away_score > g.home_score)
                        THEN 1 ELSE 0 
                    END) AS FLOAT) / COUNT(*) as win_pct
                FROM teams t
                JOIN games g ON (t.team_id = g.home_team_id OR t.team_id = g.away_team_id)
                WHERE g.competition_id = ? AND g.season = ?
                GROUP BY t.team_id
                HAVING games >= 3
            """, (comp_id, season))
            
            teams_data = cursor.fetchall()
            
            if len(teams_data) < 3:  # Muy pocos equipos, skip normalization
                for team_id, _, _ in teams_data:
                    team_factors[(team_id, season)] = 1.0
                continue
            
            win_pcts = [w for _, _, w in teams_data]
            
            # Calcular media y desv. estándar
            μ = np.mean(win_pcts)
            σ = np.std(win_pcts)
            
            if σ < 0.01:  # Sin variación, todos iguales
                for team_id, _, _ in teams_data:
                    team_factors[(team_id, season)] = 1.0
                continue
            
            # Calcular z-score y factor para cada equipo
            α = 0.06  # Máximo ±6% de ajuste
            
            for team_id, _, win_pct in teams_data:
                # Z-score normalizado
                z = (win_pct - μ) / σ
                
                # Clampear para evitar extremos
                z = np.clip(z, -2.0, 2.0)
                
                # Factor usando tanh para suavizar
                # tanh(-2) ≈ -0.96, tanh(+2) ≈ +0.96
                # Con α=0.06: factor ∈ [0.942, 1.058]
                factor = 1.0 + α * np.tanh(z)
                
                team_factors[(team_id, season)] = factor
        
        self.logger.info(f"  Team context factors calculados para {len(team_factors)} equipos/temporadas")
        
        return team_factors
    
    def calculate_career_potential_scores(self, conn: sqlite3.Connection):
        """
        Calculate consolidated potential scores per unique player.
        
        Analyzes entire player trajectory (all seasons) and generates
        a unified score considering:
        - Historical average performance
        - Improvement/decline trend
        - Recent seasons (weighted more heavily)
        - Career consistency
        - Age and current projection
        
        Args:
            conn: SQLite connection
        """
        if not self.use_profiles:
            return
        
        self.logger.info("Calculando scores de potencial CONSOLIDADO por jugador...")
        
        cursor = conn.cursor()
        calculator = CareerPotentialCalculator(logger=self.logger)
        
        # Clean previous entries to avoid UNIQUE constraint issues
        self.logger.info("  Limpiando tabla player_career_potential...")
        cursor.execute("DELETE FROM player_career_potential")
        conn.commit()
        
        # Get all unique players (grouped by normalized_name + birth_year)
        cursor.execute("""
            SELECT 
                pp.name_normalized,
                pp.birth_year,
                COUNT(DISTINCT pp.season) as seasons_count,
                MIN(pp.season) as first_season,
                MAX(pp.season) as last_season
            FROM player_profiles pp
            WHERE pp.name_normalized IS NOT NULL 
              AND TRIM(pp.name_normalized) != ''
            GROUP BY pp.name_normalized, COALESCE(pp.birth_year, -9999)
            HAVING seasons_count >= 1
        """)
        
        players = cursor.fetchall()
        self.logger.info(f"  Procesando {len(players)} jugadores únicos...")
        
        # Calculate team strength factors for context adjustment
        self.logger.info("  Calculando team strength factors...")
        team_factors = self.calculate_team_strength_factors(conn)
        
        for player in players:
            name_normalized, birth_year, seasons_count, first_season, last_season = player
            
            # Get all seasons for this player with scores and competition level
            cursor.execute("""
                SELECT 
                    pp.season,
                    pp.profile_id,
                    pp.team_id,
                    ppm.games_played,
                    ppm.total_minutes,
                    ppm.avg_minutes,
                    ppp.base_potential_score,
                    ppp.potential_score,
                    ppp.confidence_score,
                    ppp.meets_eligibility,
                    ppm.avg_z_offensive_rating,
                    ppm.avg_z_player_efficiency_rating,
                    COALESCE(cl.competition_level, 2) as competition_level
                FROM player_profiles pp
                JOIN player_profile_metrics ppm ON pp.profile_id = ppm.profile_id
                LEFT JOIN player_profile_potential ppp ON pp.profile_id = ppp.profile_id
                LEFT JOIN competition_levels cl ON pp.competition_id = cl.competition_id AND pp.season = cl.season
                WHERE pp.name_normalized = ?
                    AND (pp.birth_year = ? OR pp.birth_year IS NULL)
                ORDER BY pp.season DESC
            """, (name_normalized, birth_year))
            
            season_data = cursor.fetchall()
            
            if not season_data:
                continue
            
            # Calculate current age (based on last season)
            try:
                last_season_year = int(last_season.split('/')[0])
                current_age = last_season_year - birth_year if birth_year else None
            except:
                current_age = None
            
            # Aggregate career metrics
            total_games = sum(s[3] for s in season_data if s[3])
            total_minutes = sum(s[4] for s in season_data if s[4])
            
            # Aggregate seasons by performance using extracted function
            seasons_aggregated = calculator.aggregate_seasons_by_performance(
                season_data, 
                team_factors
            )
            
            if not seasons_aggregated:
                continue  # No eligible seasons, skip player
            
            # Build eligible seasons list
            eligible_seasons = calculator.build_eligible_seasons(seasons_aggregated)
            
            # Calculate career metrics using extracted functions
            career_avg_performance = calculator.calculate_career_average(eligible_seasons)
            recent_performance = calculator.calculate_recent_performance(
                eligible_seasons, 
                career_avg_performance
            )
            career_trajectory = calculator.calculate_trajectory(eligible_seasons)
            career_trajectory = calculator.adjust_trajectory_for_performance(
                career_trajectory,
                recent_performance
            )
            career_consistency = calculator.calculate_consistency(eligible_seasons)
            age_score = calculator.calculate_age_score(current_age)
            career_confidence = calculator.calculate_confidence_score(
                seasons_count,
                total_games
            )
            level_jump_bonus = calculator.calculate_level_jump_bonus(eligible_seasons)
            
            # Calculate unified potential score
            unified_score = calculator.calculate_unified_score(
                recent_performance,
                career_trajectory,
                career_avg_performance,
                age_score,
                career_consistency,
                career_confidence,
                level_jump_bonus
            )
            
            # Apply inactivity penalty if applicable
            unified_score = calculator.apply_inactivity_penalty(
                unified_score,
                last_season,
                current_year=2026,
                logger=self.logger,
                player_name=name_normalized
            )
            
            # Determine tier
            tier = calculator.determine_tier(unified_score)
            
            # Calculate special flags
            is_rising_star, is_established_talent, is_peak_performer = \
                calculator.calculate_special_flags(
                    seasons_count,
                    current_age,
                    recent_performance,
                    career_avg_performance,
                    career_trajectory,
                    career_consistency
                )
            
            # Find best season
            best_season_data = max(eligible_seasons, key=lambda s: s['score'])
            best_season = best_season_data['season']
            best_season_score = best_season_data['score']
            
            # Insert into database
            cursor.execute("""
                INSERT INTO player_career_potential (
                    player_name, birth_year, seasons_played, total_games, total_minutes,
                    first_season, last_season, current_age,
                    career_avg_performance, recent_performance, career_trajectory,
                    career_consistency, unified_potential_score, career_confidence,
                    potential_tier, is_rising_star, is_established_talent, is_peak_performer,
                    best_season, best_season_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name_normalized, birth_year, seasons_count, total_games, total_minutes,
                first_season, last_season, current_age,
                career_avg_performance, recent_performance, career_trajectory,
                career_consistency, unified_score, career_confidence,
                tier, is_rising_star, is_established_talent, is_peak_performer,
                best_season, best_season_score
            ))
        
        conn.commit()
        self.logger.info(f"✓ Scores de potencial consolidado calculados para {len(players)} jugadores únicos")

    
    # =========================================================================
    # AGREGACIONES Y FEATURES
    # =========================================================================
    
    def compute_player_aggregates(self, conn: sqlite3.Connection, 
                                  player_id: int, season: str,
                                  competition_id: int):
        """
        Calculate aggregated statistics for a player in a season.
        
        Args:
            conn: SQLite connection
            player_id: Player ID
            season: Season
            competition_id: Competition ID
        """
        cursor = conn.cursor()
        
        # Get all player stats for the season
        cursor.execute(
            AggregationQueryBuilder.get_player_season_stats_query(),
            (player_id, season, competition_id)
        )
        
        stats = cursor.fetchall()
        
        if not stats:
            return
        
        games_played = len(stats)
        
        # Extract stats into numpy arrays
        basic_stats = StatsExtractor.extract_basic_stats(stats)
        advanced_stats = StatsExtractor.extract_advanced_stats(stats)
        
        # Calculate aggregations
        basic_avgs = StatsAggregator.calculate_basic_averages(basic_stats)
        advanced_avgs = StatsAggregator.calculate_advanced_averages(advanced_stats)
        totals = StatsAggregator.calculate_totals(basic_stats)
        std_devs = StatsAggregator.calculate_std_deviations(basic_stats)
        trends = StatsAggregator.calculate_trends(basic_stats, games_played)
        win_pct = StatsAggregator.calculate_win_percentage(basic_stats)
        total_ws = StatsAggregator.calculate_total_win_shares(advanced_stats)
        date_from, date_to = StatsAggregator.extract_date_range(stats)
        
        # Calculate average age
        avg_age = StatsAggregator.calculate_average_age(stats)
        
        # Insert aggregated stats
        cursor.execute(
            AggregationQueryBuilder.get_insert_aggregates_query(),
            (
                player_id, season, competition_id, games_played,
                date_from, date_to, avg_age,
                basic_avgs['avg_minutes'], basic_avgs['avg_points'], basic_avgs['avg_fg_pct'],
                basic_avgs['avg_three_pct'], basic_avgs['avg_ft_pct'],
                basic_avgs['avg_rebounds'], basic_avgs['avg_assists'], basic_avgs['avg_efficiency'],
                totals['total_points'], totals['total_rebounds'], totals['total_assists'],
                std_devs['std_points'], std_devs['std_efficiency'],
                trends['trend_points'], trends['trend_efficiency'],
                advanced_avgs['avg_ts_pct'], advanced_avgs['avg_efg_pct'], advanced_avgs['avg_oer'],
                advanced_avgs['avg_per'], advanced_avgs['avg_tov_pct'],
                advanced_avgs['avg_orb_pct'], advanced_avgs['avg_drb_pct'],
                advanced_avgs['avg_ws_36'],
                win_pct
            )
        )
    
    def compute_all_aggregates(self, conn: sqlite3.Connection):
        """Calcular agregados para todos los jugadores."""
        cursor = conn.cursor()
        
        # Obtener todas las combinaciones player/season/competition
        cursor.execute("""
            SELECT DISTINCT 
                pgs.player_id,
                g.season,
                g.competition_id
            FROM player_game_stats pgs
            JOIN games g ON pgs.game_id = g.game_id
        """)
        
        combinations = cursor.fetchall()
        self.logger.info(f"Calculando agregados para {len(combinations)} combinaciones...")
        
        for i, (player_id, season, comp_id) in enumerate(combinations, 1):
            if i % 100 == 0:
                self.logger.info(f"  Progreso: {i}/{len(combinations)}")
            
            self.compute_player_aggregates(conn, player_id, season, comp_id)
        
        conn.commit()
        self.logger.info("✓ Agregados calculados")
    
    def normalize_all_stats(self, conn: sqlite3.Connection, collections: List[str]):
        """
        Calcular Z-Scores y percentiles para todas las estadísticas cargadas.
        
        Este paso debe ejecutarse DESPUÉS de cargar todos los partidos,
        ya que necesita las estadísticas del contexto completo.
        
        Args:
            conn: Conexión SQLite
            collections: Lista de colecciones procesadas
        """
        self.logger.info("========================================")
        self.logger.info("PASO 4: NORMALIZACIÓN (Z-SCORES)")
        self.logger.info("========================================")
        
        # Inicializar normalizador
        normalizer = ZScoreNormalizer(self.sqlite_path)
        
        # Inicializar niveles de competición
        self.logger.info("Inicializando niveles de competición...")
        initialize_competition_levels(self.sqlite_path)
        
        # Determinar géneros a procesar
        genders = []
        if any('masc' in col for col in collections):
            genders.append('masc')
        if any('fem' in col for col in collections):
            genders.append('fem')
        
        for gender in genders:
            self.logger.info(f"\nProcesando género: {gender}")
            
            # Obtener todos los contextos (nivel + temporada) únicos
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT cl.competition_level, g.season
                FROM games g
                JOIN competitions c ON g.competition_id = c.competition_id
                JOIN competition_levels cl ON c.competition_id = cl.competition_id 
                    AND g.season = cl.season
                WHERE c.gender = ?
                ORDER BY g.season, cl.competition_level
            """, (gender,))
            
            contexts = cursor.fetchall()
            
            self.logger.info(f"Encontrados {len(contexts)} contextos únicos (nivel + temporada)")
            
            # Calcular Z-Scores para cada contexto
            for comp_level, season in contexts:
                self.logger.info(f"  Contexto: nivel={comp_level}, temporada={season}")
                
                try:
                    # Actualizar Z-Scores de player_game_stats
                    updated = normalizer.update_game_stats_zscores(comp_level, season)
                    self.logger.info(f"    ✓ Actualizados {updated} registros")
                    
                except Exception as e:
                    self.logger.error(f"    ✗ Error: {e}")
            
            # Actualizar percentiles en player_aggregated_stats
            self.logger.info(f"\nCalculando percentiles para stats agregadas ({gender})...")
            
            cursor.execute("""
                SELECT DISTINCT pas.player_id, pas.season
                FROM player_aggregated_stats pas
                JOIN competitions c ON pas.competition_id = c.competition_id
                WHERE c.gender = ?
            """, (gender,))
            
            player_seasons = cursor.fetchall()
            
            updated_players = 0
            for player_id, season in player_seasons:
                try:
                    if normalizer.update_aggregated_stats_normalized(player_id, season):
                        updated_players += 1
                        if updated_players % 100 == 0:
                            conn.commit()  # Commit periódico
                except Exception as e:
                    self.logger.error(f"Error actualizando jugador {player_id}: {e}")
            
            conn.commit()
            self.logger.info(f"  ✓ Percentiles actualizados para {updated_players} jugadores")
        
        self.logger.info("\n========================================")
        self.logger.info("NORMALIZACIÓN COMPLETADA")
        self.logger.info("========================================")
    
    # =========================================================================
    # PROCESO ETL COMPLETO
    # =========================================================================
    
    def run_full_etl(self, collections: List[str] = None, 
                    limit: Optional[int] = None,
                    generate_candidates: bool = True,
                    candidate_min_score: float = 0.50,
                    incremental: bool = True):
        """
        Ejecutar el proceso ETL completo.
        
        Args:
            collections: Lista de colecciones a procesar (default: ambas)
            limit: Límite opcional de partidos por colección
            generate_candidates: Si True, genera candidatos de matching (solo con use_profiles=True)
            candidate_min_score: Score mínimo para generar candidatos
            incremental: Si True, solo procesa partidos nuevos (default: True)
        """
        if collections is None:
            collections = ["all_feb_games_masc", "all_feb_games_fem"]
        
        self.logger.info("="*70)
        self.logger.info("INICIANDO PROCESO ETL: MongoDB -> SQLite")
        self.logger.info("="*70)
        self.logger.info(f"Modo: {'PERFILES' if self.use_profiles else 'JUGADORES ÚNICOS'}")
        self.logger.info(f"Procesamiento: {'INCREMENTAL' if incremental else 'COMPLETO'}")
        
        start_time = datetime.now()
        total_games = 0
        total_games_skipped = 0
        total_players = 0
        
        conn = self.get_connection()
        
        try:
            # Obtener game_ids ya procesados si modo incremental
            processed_game_ids = set()
            if incremental:
                processed_game_ids = self.get_processed_game_ids(conn)
                self.logger.info(f"Partidos ya procesados en SQLite: {len(processed_game_ids)}")
            
            for collection_name in collections:
                self.logger.info(f"\nProcesando colección: {collection_name}")
                
                # EXTRACT (con exclusión de partidos ya procesados si incremental)
                games = self.extract_games_from_mongodb(
                    collection_name, 
                    limit,
                    exclude_game_ids=processed_game_ids if incremental else None
                )
                
                if incremental and len(games) == 0:
                    self.logger.info(f"✓ No hay partidos nuevos en {collection_name}")
                    continue
                
                # TRANSFORM & LOAD
                self.logger.info(f"Transformando y cargando {len(games)} partidos...")
                
                for i, mongo_game in enumerate(games, 1):
                    if i % 10 == 0:
                        self.logger.info(f"  Progreso: {i}/{len(games)}")
                        conn.commit()  # Commit periódico
                    
                    try:
                        game_data = self.transform_game_data(mongo_game)
                        self.load_game(conn, game_data)
                        total_games += 1
                    except Exception as e:
                        self.logger.error(f"Error procesando partido: {e}")
                        continue
                
                conn.commit()
                self.logger.info(f"✓ Colección {collection_name} procesada")
            
            # Calcular agregados
            self.logger.info("\nCalculando estadísticas agregadas...")
            self.compute_all_aggregates(conn)
            
            # Normalizar (Z-Scores y percentiles)
            self.logger.info("\nCalculando Z-Scores y percentiles...")
            self.normalize_all_stats(conn, collections)
            
            # Si usamos perfiles, calcular métricas y candidatos
            if self.use_profiles:
                self.logger.info("\n" + "="*70)
                self.logger.info("PROCESAMIENTO DE PERFILES E IDENTIDADES")
                self.logger.info("="*70)
                
                # Calcular métricas de perfiles
                self.compute_profile_metrics(conn)
                
                # Calcular scores de potencial
                self.calculate_profile_potential_scores(conn)
                
                # Calcular potencial de carrera consolidado (por jugador único)
                self.calculate_career_potential_scores(conn)
                
                # Generar candidatos de matching
                if generate_candidates:
                    self.generate_identity_candidates(conn, min_score=candidate_min_score)
            
            # Estadísticas finales
            cursor = conn.cursor()
            
            if self.use_profiles:
                cursor.execute("SELECT COUNT(*) FROM player_profiles")
                total_profiles = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM player_identity_candidates")
                total_candidates = cursor.fetchone()[0]
                
                cursor.execute("""
                    SELECT COUNT(*) FROM player_identity_candidates 
                    WHERE confidence_level IN ('high', 'very_high')
                """)
                high_confidence = cursor.fetchone()[0]
            else:
                cursor.execute("SELECT COUNT(*) FROM players")
                total_players = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM games")
            final_games = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM player_game_stats")
            total_stats = cursor.fetchone()[0]
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            self.logger.info("\n" + "="*70)
            self.logger.info("ETL COMPLETADO")
            self.logger.info("="*70)
            self.logger.info(f"Duración: {duration:.2f} segundos")
            self.logger.info(f"Partidos procesados: {final_games}")
            
            if self.use_profiles:
                self.logger.info(f"Perfiles de jugador: {total_profiles}")
                self.logger.info(f"Candidatos de matching: {total_candidates}")
                self.logger.info(f"  - Alta confianza: {high_confidence}")
            else:
                self.logger.info(f"Jugadores únicos: {total_players}")
            
            self.logger.info(f"Estadísticas de jugador: {total_stats}")
            self.logger.info("="*70)
            
        except Exception as e:
            self.logger.error(f"Error en ETL: {e}", exc_info=True)
            conn.rollback()
        finally:
            conn.close()
            self.mongo_client.close()


def main():
    """Ejecutar ETL."""
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    parser = argparse.ArgumentParser(description='ETL MongoDB -> SQLite')
    parser.add_argument('--limit', type=int, help='Limitar número de partidos por colección')
    parser.add_argument('--masc-only', action='store_true', help='Solo procesar masculino')
    parser.add_argument('--fem-only', action='store_true', help='Solo procesar femenino')
    parser.add_argument('--legacy-mode', action='store_true', 
                       help='Usar sistema legacy (jugadores únicos) en lugar de perfiles')
    parser.add_argument('--no-candidates', action='store_true',
                       help='No generar candidatos de matching automático')
    parser.add_argument('--candidate-threshold', type=float, default=0.50,
                       help='Score mínimo para generar candidatos (default: 0.50)')
    
    args = parser.parse_args()
    
    # Determinar colecciones a procesar
    collections = None
    if args.masc_only:
        collections = ["all_feb_games_masc"]
    elif args.fem_only:
        collections = ["all_feb_games_fem"]
    
    # Ejecutar ETL
    etl = FEBDataETL(use_profiles=not args.legacy_mode)
    etl.run_full_etl(
        collections=collections, 
        limit=args.limit,
        generate_candidates=not args.no_candidates,
        candidate_min_score=args.candidate_threshold
    )


if __name__ == "__main__":
    main()
