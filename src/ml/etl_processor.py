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
    
    # =========================================================================
    # EXTRACT - Extracción desde MongoDB
    # =========================================================================
    
    def extract_games_from_mongodb(self, collection_name: str, 
                                   limit: Optional[int] = None) -> List[Dict]:
        """
        Extraer partidos desde MongoDB.
        
        Args:
            collection_name: Nombre de la colección ('all_feb_games_masc' o 'all_feb_games_fem')
            limit: Límite opcional de documentos
            
        Returns:
            Lista de documentos de partidos
        """
        self.logger.info(f"Extrayendo partidos desde {collection_name}...")
        
        collection = self.mongo_client.get_collection(collection_name)
        
        query = {}
        cursor = collection.find(query)
        
        if limit:
            cursor = cursor.limit(limit)
        
        games = list(cursor)
        self.logger.info(f"✓ Extraídos {len(games)} partidos")
        
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
        
        Args:
            player: Datos del jugador del boxscore
            is_home: Si es equipo local
            team_won: Si su equipo ganó
            game_date: Fecha del partido (para calcular edad)
            
        Returns:
            Diccionario con estadísticas transformadas
        """
        # Función auxiliar para convertir a int/float de forma segura
        def safe_int(value, default=0):
            try:
                return int(value) if value else default
            except (ValueError, TypeError):
                return default
        
        def safe_float(value, default=0.0):
            try:
                return float(value) if value else default
            except (ValueError, TypeError):
                return default
        
        # Parsear tiempo de juego
        # Puede venir en formato "MM:SS" (minFormatted) o en segundos (min)
        minutes_played = 0.0
        time_str = player.get("minFormatted", player.get("min", "0:00"))
        
        # Si es un número (segundos), convertir a minutos
        if isinstance(time_str, (int, float)):
            minutes_played = time_str / 60.0
        # Si es string con formato MM:SS
        elif isinstance(time_str, str) and ":" in time_str:
            parts = time_str.split(":")
            if len(parts) == 2:
                minutes_played = safe_int(parts[0]) + safe_int(parts[1]) / 60.0
        # Si es string con solo número
        elif isinstance(time_str, str) and time_str.isdigit():
            minutes_played = safe_int(time_str) / 60.0
        
        # Detectar formato legacy (datos ya transformados con claves en inglés)
        is_legacy_format = "playername" in player
        
        # Calcular porcentajes de tiro según el formato
        if is_legacy_format:
            # Formato legacy: claves en inglés
            three_made = safe_int(player.get("three_points_made", 0))
            three_att = safe_int(player.get("three_points_attempted", 0))
            two_made = safe_int(player.get("two_points_made", 0))
            two_att = safe_int(player.get("two_points_attempted", 0))
            field_goals_made = safe_int(player.get("field_goals_made", 0))
            field_goals_att = safe_int(player.get("field_goals_attempted", 0))
            ft_made = safe_int(player.get("free_throws_made", 0))
            ft_att = safe_int(player.get("free_throws_attempted", 0))
        else:
            # Formato moderno: claves FEB (p1m/p1a, p2m/p2a, p3m/p3a)
            three_made = safe_int(player.get("p3m", 0))
            three_att = safe_int(player.get("p3a", 0))
            two_made = safe_int(player.get("p2m", 0))
            two_att = safe_int(player.get("p2a", 0))
            field_goals_made = two_made + three_made
            field_goals_att = two_att + three_att
            ft_made = safe_int(player.get("p1m", 0))
            ft_att = safe_int(player.get("p1a", 0))
        
        # Calcular porcentajes
        three_pct = (three_made / three_att * 100) if three_att > 0 else 0.0
        two_pct = (two_made / two_att * 100) if two_att > 0 else 0.0
        field_goal_pct = (field_goals_made / field_goals_att * 100) if field_goals_att > 0 else 0.0
        ft_pct = (ft_made / ft_att * 100) if ft_att > 0 else 0.0
        
        # Calcular edad si tenemos la información
        age_at_game = None
        birth_year = player.get("birth_year")  # Si está disponible en los datos
        
        # Validar birth_year - debe estar en un rango razonable para baloncesto profesional
        # Jugadores típicamente tienen entre 15 y 45 años
        if birth_year and game_date:
            try:
                from datetime import datetime
                
                # Intentar parsear game_date en diferentes formatos
                game_year = None
                
                # Formato ISO: "2025-10-04T19:00:00"
                if 'T' in game_date or game_date.count('-') >= 2:
                    try:
                        game_year = datetime.fromisoformat(game_date.replace('Z', '+00:00')).year
                    except:
                        pass
                
                # Formato FEB: "04-10-2025 - 19:00" o "04-10-2025"
                if not game_year:
                    date_part = game_date.split(' - ')[0].strip() if ' - ' in game_date else game_date.strip()
                    parts = date_part.split('-')
                    if len(parts) == 3:
                        # Puede ser DD-MM-YYYY o YYYY-MM-DD
                        if len(parts[0]) == 4:  # YYYY-MM-DD
                            game_year = int(parts[0])
                        else:  # DD-MM-YYYY
                            game_year = int(parts[2])
                
                if game_year:
                    calculated_age = game_year - int(birth_year)
                    
                    # Validar que la edad sea razonable (entre 12 y 50 años)
                    if 12 <= calculated_age <= 50:
                        age_at_game = calculated_age
                    else:
                        # Edad no razonable - intentar parsear birth_date
                        birth_date_str = player.get("birth_date", "")
                        if birth_date_str and "/" in birth_date_str:
                            parts = birth_date_str.split("/")
                            if len(parts) == 3:
                                # Formato DD/MM/YYYY
                                potential_year = safe_int(parts[2])
                                if potential_year and 12 <= (game_year - potential_year) <= 50:
                                    birth_year = potential_year
                                    age_at_game = game_year - potential_year
                                else:
                                    birth_year = None
                        else:
                            birth_year = None
            except Exception as e:
                # En caso de error, mantener birth_year original si es razonable
                # Solo invalidar si está fuera del rango 1950-2020
                try:
                    by = int(birth_year)
                    if not (1950 <= by <= 2020):
                        birth_year = None
                except:
                    birth_year = None
        
        # Extraer datos según el formato (legacy vs moderno)
        if is_legacy_format:
            # Formato legacy: claves ya en inglés
            player_name = player.get("playername", "").strip()
            dorsal = player.get("shirtnumber", "")
            is_starter = player.get("is_starter", False)
            points = safe_int(player.get("points", 0))
            offensive_rebounds = safe_int(player.get("offensive_rebounds", 0))
            defensive_rebounds = safe_int(player.get("defensive_rebounds", 0))
            total_rebounds = safe_int(player.get("total_rebounds", 0))
            assists = safe_int(player.get("assists", 0))
            turnovers = safe_int(player.get("turnovers", 0))
            steals = safe_int(player.get("steals", 0))
            blocks = safe_int(player.get("blocks", 0))
            blocks_received = safe_int(player.get("blocks_received", 0))
            personal_fouls = safe_int(player.get("personal_fouls", 0))
            fouls_received = safe_int(player.get("fouls_received", 0))
            plus_minus = safe_int(player.get("plus_minus", 0))
            efficiency = safe_float(player.get("efficiency", 0))
        else:
            # Formato moderno: claves de API FEB
            player_name = player.get("name", "").strip()
            dorsal = player.get("no", "")
            is_starter = player.get("inn", "0") == "1"
            points = safe_int(player.get("pts", 0))
            offensive_rebounds = safe_int(player.get("ro", 0))
            defensive_rebounds = safe_int(player.get("rd", 0))
            total_rebounds = safe_int(player.get("rt", 0))
            assists = safe_int(player.get("assist", 0))
            turnovers = safe_int(player.get("to", 0))
            steals = safe_int(player.get("st", 0))
            blocks = safe_int(player.get("bs", 0))
            blocks_received = safe_int(player.get("mt", 0))
            personal_fouls = safe_int(player.get("pf", 0))
            fouls_received = safe_int(player.get("rf", 0))
            plus_minus = safe_int(player.get("pllss", 0))
            efficiency = safe_float(player.get("val", 0))
        
        # Preparar datos para calcular métricas avanzadas
        stats_for_advanced = {
            'pts': points,
            'fgm': field_goals_made,
            'fga': field_goals_att,
            'fg3m': three_made,
            'ftm': ft_made,
            'fta': ft_att,
            'orb': offensive_rebounds,
            'drb': defensive_rebounds,
            'reb': total_rebounds,
            'ast': assists,
            'tov': turnovers,
            'stl': steals,
            'blk': blocks,
            'minutes': minutes_played
        }
        
        # Calcular métricas avanzadas
        advanced_stats = calculate_all_advanced_stats(stats_for_advanced)
        
        return {
            "dorsal": dorsal,
            "name": player_name,
            "birth_year": birth_year,  # Usar la variable validada, no player.get()
            "age_at_game": age_at_game,
            "is_home": is_home,
            "is_starter": is_starter,
            "team_won": team_won,
            
            # Tiempo
            "minutes_played": minutes_played,
            
            # Puntos
            "points": points,
            "field_goals_made": field_goals_made,
            "field_goals_attempted": field_goals_att,
            "field_goal_pct": field_goal_pct,
            "three_points_made": three_made,
            "three_points_attempted": three_att,
            "three_point_pct": three_pct,
            "two_points_made": two_made,
            "two_points_attempted": two_att,
            "two_point_pct": two_pct,
            "free_throws_made": ft_made,
            "free_throws_attempted": ft_att,
            "free_throw_pct": ft_pct,
            
            # Rebotes
            "offensive_rebounds": offensive_rebounds,
            "defensive_rebounds": defensive_rebounds,
            "total_rebounds": total_rebounds,
            
            # Pases y balones
            "assists": assists,
            "turnovers": turnovers,
            "steals": steals,
            
            # Defensa
            "blocks": blocks,
            "blocks_received": blocks_received,
            "personal_fouls": personal_fouls,
            "fouls_received": fouls_received,
            
            # Métricas legacy
            "plus_minus": plus_minus,
            "efficiency_rating": efficiency,
            
            # Métricas avanzadas
            "true_shooting_pct": advanced_stats.get('true_shooting_pct'),
            "effective_fg_pct": advanced_stats.get('effective_fg_pct'),
            "offensive_rating": advanced_stats.get('offensive_rating'),
            "player_efficiency_rating": advanced_stats.get('player_efficiency_rating'),
            "turnover_pct": advanced_stats.get('turnover_pct'),
            "offensive_rebound_pct": advanced_stats.get('offensive_rebound_pct'),
            "defensive_rebound_pct": advanced_stats.get('defensive_rebound_pct'),
            "free_throw_rate": advanced_stats.get('free_throw_rate'),
            "assist_to_turnover_ratio": advanced_stats.get('assist_to_turnover_ratio'),
            "usage_rate": advanced_stats.get('usage_rate'),
            "win_shares": advanced_stats.get('win_shares'),
            "win_shares_per_36": advanced_stats.get('win_shares_per_36')
        }
    
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
        Calcular métricas agregadas para cada perfil de jugador.
        
        Args:
            conn: Conexión SQLite
        """
        if not self.use_profiles:
            return
        
        self.logger.info("Calculando métricas de perfiles...")
        
        cursor = conn.cursor()
        
        # Obtener todos los perfiles
        cursor.execute("SELECT profile_id FROM player_profiles")
        profiles = cursor.fetchall()
        
        for i, (profile_id,) in enumerate(profiles, 1):
            if i % 100 == 0:
                self.logger.info(f"  Progreso: {i}/{len(profiles)}")
            
            # Obtener stats del perfil con totales para per_36
            cursor.execute("""
                SELECT 
                    COUNT(*) as games_played,
                    SUM(minutes_played) as total_minutes,
                    AVG(minutes_played) as avg_minutes,
                    AVG(points) as avg_points,
                    AVG(offensive_rating) as avg_offensive_rating,
                    AVG(player_efficiency_rating) as avg_per,
                    AVG(true_shooting_pct) as avg_ts_pct,
                    AVG(z_offensive_rating) as avg_z_oer,
                    AVG(z_player_efficiency_rating) as avg_z_per,
                    AVG(z_minutes) as avg_z_minutes,
                    AVG((offensive_rating - (SELECT AVG(offensive_rating) FROM player_game_stats WHERE player_id = ?)) * 
                        (offensive_rating - (SELECT AVG(offensive_rating) FROM player_game_stats WHERE player_id = ?))) as var_oer,
                    AVG((points - (SELECT AVG(points) FROM player_game_stats WHERE player_id = ?)) * 
                        (points - (SELECT AVG(points) FROM player_game_stats WHERE player_id = ?))) as var_points,
                    SUM(points) as total_points,
                    SUM(assists) as total_assists,
                    SUM(total_rebounds) as total_rebounds,
                    SUM(steals) as total_steals,
                    SUM(blocks) as total_blocks,
                    SUM(turnovers) as total_turnovers,
                    SUM(field_goals_made) as total_fgm,
                    SUM(field_goals_attempted) as total_fga,
                    SUM(three_points_made) as total_3pm
                FROM player_game_stats
                WHERE player_id = ?
            """, (profile_id, profile_id, profile_id, profile_id, profile_id))
            
            stats = cursor.fetchone()
            
            if stats and stats[0] > 0:
                games = stats[0]
                total_minutes = stats[1]
                avg_minutes = stats[2]
                avg_points = stats[3]
                avg_z_oer = stats[7] if stats[7] is not None else 0
                
                # Calcular desviaciones estándar desde varianza
                std_oer = (stats[10] ** 0.5) if stats[10] is not None and stats[10] > 0 else 0
                std_points = (stats[11] ** 0.5) if stats[11] is not None and stats[11] > 0 else 0
                
                # ✨ NUEVO: Coeficiente de variación y stability index
                cv_points = (std_points / avg_points) if avg_points and avg_points > 0 else None
                stability_index = (std_points / (games ** 0.5)) if games > 0 else None
                
                # ✨ NUEVO: Estadísticas per-36
                pts_per_36 = None
                ast_per_36 = None
                reb_per_36 = None
                stl_per_36 = None
                blk_per_36 = None
                tov_per_36 = None
                fgm_per_36 = None
                fga_per_36 = None
                fg3m_per_36 = None
                
                if total_minutes and total_minutes > 0:
                    factor_36 = 36.0 / total_minutes
                    pts_per_36 = stats[12] * factor_36 if stats[12] else 0
                    ast_per_36 = stats[13] * factor_36 if stats[13] else 0
                    reb_per_36 = stats[14] * factor_36 if stats[14] else 0
                    stl_per_36 = stats[15] * factor_36 if stats[15] else 0
                    blk_per_36 = stats[16] * factor_36 if stats[16] else 0
                    tov_per_36 = stats[17] * factor_36 if stats[17] else 0
                    fgm_per_36 = stats[18] * factor_36 if stats[18] else 0
                    fga_per_36 = stats[19] * factor_36 if stats[19] else 0
                    fg3m_per_36 = stats[20] * factor_36 if stats[20] else 0
                
                # ✨ NUEVO: Rolling windows (últimos 5 y 10 partidos)
                cursor.execute("""
                    WITH recent_games AS (
                        SELECT pgs.points, pgs.offensive_rating, g.game_date,
                               ROW_NUMBER() OVER (ORDER BY g.game_date DESC) as rn
                        FROM player_game_stats pgs
                        JOIN games g ON pgs.game_id = g.game_id
                        WHERE pgs.player_id = ?
                    )
                    SELECT 
                        AVG(CASE WHEN rn <= 5 THEN points END) as last_5_pts,
                        AVG(CASE WHEN rn <= 5 THEN offensive_rating END) as last_5_oer,
                        AVG(CASE WHEN rn <= 10 THEN points END) as last_10_pts,
                        AVG(CASE WHEN rn <= 10 THEN offensive_rating END) as last_10_oer
                    FROM recent_games
                """, (profile_id,))
                
                rolling = cursor.fetchone()
                last_5_pts = rolling[0] if rolling and rolling[0] else None
                last_5_oer = rolling[1] if rolling and rolling[1] else None
                last_10_pts = rolling[2] if rolling and rolling[2] else None
                last_10_oer = rolling[3] if rolling and rolling[3] else None
                
                # Momentum index
                momentum_index = None
                if last_5_pts is not None and last_10_pts is not None:
                    momentum_index = last_5_pts - last_10_pts
                
                # Trend points (pendiente de últimos 10 partidos)
                cursor.execute("""
                    WITH recent_trend AS (
                        SELECT pgs.points, g.game_date,
                               ROW_NUMBER() OVER (ORDER BY g.game_date DESC) as rn
                        FROM player_game_stats pgs
                        JOIN games g ON pgs.game_id = g.game_id
                        WHERE pgs.player_id = ?
                        LIMIT 10
                    )
                    SELECT AVG(points * rn) - AVG(points) * AVG(rn),
                           AVG(rn * rn) - AVG(rn) * AVG(rn)
                    FROM recent_trend
                """, (profile_id,))
                
                trend_calc = cursor.fetchone()
                trend_points = None
                if trend_calc and trend_calc[1] and trend_calc[1] != 0:
                    trend_points = trend_calc[0] / trend_calc[1]
                
                # ✨ NUEVO: Ratios jugadora/equipo
                # Obtener totales del equipo en la misma temporada
                cursor.execute("""
                    SELECT pp.team_id, pp.season
                    FROM player_profiles pp
                    WHERE pp.profile_id = ?
                """, (profile_id,))
                
                team_season = cursor.fetchone()
                player_pts_share = None
                player_usage_share = None
                efficiency_vs_team_avg = None
                minutes_share = None
                
                if team_season:
                    team_id, season = team_season
                    
                    # Totales del equipo
                    cursor.execute("""
                        SELECT 
                            SUM(pgs.points) as team_total_pts,
                            SUM(pgs.minutes_played) as team_total_minutes,
                            AVG(pgs.true_shooting_pct) as team_avg_ts,
                            AVG(pgs.usage_rate) as team_avg_usage
                        FROM player_game_stats pgs
                        JOIN player_profiles pp ON pgs.player_id = pp.profile_id
                        WHERE pp.team_id = ? AND pp.season = ?
                    """, (team_id, season))
                    
                    team_stats = cursor.fetchone()
                    
                    if team_stats and team_stats[0]:
                        team_total_pts = team_stats[0]
                        team_total_minutes = team_stats[1]
                        team_avg_ts = team_stats[2]
                        team_avg_usage = team_stats[3]
                        
                        # Calcular ratios
                        if team_total_pts > 0 and stats[12]:
                            player_pts_share = stats[12] / team_total_pts
                        
                        if team_total_minutes and total_minutes:
                            minutes_share = total_minutes / team_total_minutes
                        
                        if team_avg_ts and stats[6]:
                            efficiency_vs_team_avg = stats[6] / team_avg_ts
                        
                        # Usage share (requiere calcular usage del jugador primero)
                        cursor.execute("""
                            SELECT AVG(usage_rate)
                            FROM player_game_stats
                            WHERE player_id = ?
                        """, (profile_id,))
                        player_usage = cursor.fetchone()
                        if player_usage and player_usage[0] and team_avg_usage:
                            player_usage_share = player_usage[0] / team_avg_usage
                
                # Performance tier
                if avg_z_oer > 1.5:
                    tier = 'elite'
                elif avg_z_oer > 0.5:
                    tier = 'very_good'
                elif avg_z_oer > -0.5:
                    tier = 'above_average'
                elif avg_z_oer > -1.5:
                    tier = 'average'
                else:
                    tier = 'below_average'
                
                # Insertar o actualizar métricas con TODAS las nuevas columnas
                cursor.execute("""
                    INSERT OR REPLACE INTO player_profile_metrics (
                        profile_id, games_played, total_minutes, avg_minutes, avg_points,
                        avg_offensive_rating, avg_player_efficiency_rating,
                        avg_true_shooting_pct, avg_z_offensive_rating,
                        avg_z_player_efficiency_rating, avg_z_minutes,
                        std_offensive_rating, std_points, performance_tier,
                        pts_per_36, ast_per_36, reb_per_36, stl_per_36, blk_per_36,
                        tov_per_36, fgm_per_36, fga_per_36, fg3m_per_36,
                        cv_points, stability_index,
                        last_5_games_pts, last_5_games_oer, last_10_games_pts, last_10_games_oer,
                        trend_points, momentum_index,
                        player_pts_share, player_usage_share, efficiency_vs_team_avg, minutes_share
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    profile_id, games, total_minutes, avg_minutes, avg_points,
                    stats[4], stats[5], stats[6], stats[7],
                    stats[8], stats[9], std_oer, std_points, tier,
                    pts_per_36, ast_per_36, reb_per_36, stl_per_36, blk_per_36,
                    tov_per_36, fgm_per_36, fga_per_36, fg3m_per_36,
                    cv_points, stability_index,
                    last_5_pts, last_5_oer, last_10_pts, last_10_oer,
                    trend_points, momentum_index,
                    player_pts_share, player_usage_share, efficiency_vs_team_avg, minutes_share
                ))
        
        conn.commit()
        self.logger.info(f"✓ Métricas calculadas para {len(profiles)} perfiles")
    
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
        Calcular scores de potencial para perfiles.
        
        Este score combina:
        - Edad y proyección
        - Tendencia de mejora
        - Consistencia
        - Métricas avanzadas
        
        Incluye sistema de filtros de elegibilidad y ponderación por confianza
        para evitar sesgos por outliers con muestras pequeñas.
        
        Args:
            conn: Conexión SQLite
        """
        if not self.use_profiles:
            return
        
        # Constantes de filtros de elegibilidad (Fase 1: Quick Win)
        MIN_GAMES_FOR_POTENTIAL = 8      # Mínimo 8 partidos jugados
        MIN_TOTAL_MINUTES = 80           # Mínimo 80 minutos totales
        MIN_AVG_MINUTES = 8              # Mínimo 8 minutos promedio por partido
        
        self.logger.info("Calculando scores de potencial...")
        self.logger.info(f"  Filtros de elegibilidad: games>={MIN_GAMES_FOR_POTENTIAL}, "
                        f"total_min>={MIN_TOTAL_MINUTES}, avg_min>={MIN_AVG_MINUTES}")
        
        cursor = conn.cursor()
        
        # Obtener perfiles con métricas, nivel de competición y contexto de equipo
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
            
            # FASE 1: Evaluar elegibilidad
            meets_eligibility = True
            eligibility_notes = []
            
            if games_played < MIN_GAMES_FOR_POTENTIAL:
                meets_eligibility = False
                eligibility_notes.append(f"Pocos partidos ({games_played}<{MIN_GAMES_FOR_POTENTIAL})")
            
            if total_minutes is None or total_minutes < MIN_TOTAL_MINUTES:
                meets_eligibility = False
                total_min_str = f"{total_minutes:.0f}" if total_minutes else "0"
                eligibility_notes.append(f"Pocos minutos totales ({total_min_str}<{MIN_TOTAL_MINUTES})")
            
            if avg_minutes is None or avg_minutes < MIN_AVG_MINUTES:
                meets_eligibility = False
                avg_min_str = f"{avg_minutes:.1f}" if avg_minutes else "0"
                eligibility_notes.append(f"Rol marginal ({avg_min_str}<{MIN_AVG_MINUTES} min/partido)")
            
            eligibility_note_str = "; ".join(eligibility_notes) if eligibility_notes else None
            
            if meets_eligibility:
                eligible_count += 1
            else:
                ineligible_count += 1
            
            # Calcular edad estimada y antigüedad de temporada
            try:
                season_year = int(season.split('/')[0])
                age = season_year - birth_year if birth_year else None
                # Calcular peso temporal: más peso a temporadas recientes
                # 2025/2026 = 1.0, 2024/2025 = 0.95, 2023/2024 = 0.90, etc.
                current_year = 2026  # Actualizar cada año
                years_ago = current_year - season_year
                temporal_weight = max(0.5, 1.0 - (years_ago * 0.05))
            except:
                age = None
                temporal_weight = 1.0
            
            # 1. Age projection score (0.0-1.0)
            if age:
                if age <= 21:
                    age_score = 1.0  # Muy joven, alto potencial
                elif age <= 24:
                    age_score = 0.8
                elif age <= 27:
                    age_score = 0.5
                elif age <= 30:
                    age_score = 0.3
                else:
                    age_score = 0.1
            else:
                age_score = 0.5  # Neutral si no tenemos edad
            
            # 2. Performance score basado en z-scores con ajuste por competición (0.0-1.0)
            if avg_z_oer is not None and avg_z_per is not None:
                # Normalizar z-scores a 0-1 (asumiendo rango -3 a +3)
                base_perf_score = ((avg_z_oer + avg_z_per) / 2 + 3) / 6
                base_perf_score = max(0.0, min(1.0, base_perf_score))
                
                # Ajustar por nivel de competición
                # Nivel 1 (LF ENDESA): +10% bonus, Nivel 2: neutral, Nivel 3: -5%
                competition_bonus = 0.0
                if competition_level == 1:
                    competition_bonus = 0.10
                elif competition_level == 3:
                    competition_bonus = -0.05
                
                perf_score = min(1.0, base_perf_score * (1.0 + competition_bonus))
            else:
                perf_score = 0.5
            
            # 3. Consistency score (mejorado con CV y stability index)
            if cv_points is not None and cv_points >= 0:
                # Coeficiente de variación: menor es mejor
                # CV < 0.3 = muy consistente, CV > 0.8 = muy inconsistente
                consistency_score = max(0.0, min(1.0, 1.0 - (cv_points / 0.8)))
            elif std_oer is not None and std_oer > 0:
                # Fallback al método anterior
                consistency_score = max(0.0, 1.0 - (std_oer / 50.0))
            else:
                consistency_score = 0.5
            
            # 4. Advanced metrics score (TS% y efficiency vs team)
            adv_metrics_score = 0.5  # Default
            if avg_ts_pct is not None:
                # TS% > 55% es muy bueno
                base_ts_score = min(1.0, avg_ts_pct / 65.0)
                
                # Ajustar por efficiency vs equipo si disponible
                if efficiency_vs_team_avg is not None:
                    # > 1.0 = mejor que el equipo, < 1.0 = peor
                    team_adj = min(1.2, max(0.8, efficiency_vs_team_avg))
                    adv_metrics_score = base_ts_score * team_adj
                else:
                    adv_metrics_score = base_ts_score
            
            # ✨ 5. Momentum/Trend score (NUEVO - detecta breakouts)
            momentum_score = 0.5  # Default neutral
            if momentum_index is not None:
                # momentum_index = avg(last5) - avg(last10)
                # Positivo = mejorando, negativo = empeorando
                # Normalizar entre -5 y +5 puntos de diferencia
                normalized_momentum = (momentum_index + 5) / 10
                momentum_score = max(0.0, min(1.0, normalized_momentum))
            elif trend_points is not None:
                # Trend como fallback
                # Pendiente positiva = mejorando
                normalized_trend = (trend_points + 2) / 4
                momentum_score = max(0.0, min(1.0, normalized_trend))
            
            # ✨ 6. Production per-36 score (NUEVO - normalizado por tiempo)
            production_score = 0.5  # Default
            if pts_per_36 is not None:
                # pts_per_36 > 15 = excelente, < 5 = muy bajo
                production_score = min(1.0, pts_per_36 / 20.0)
                
                # Ajustar por share del equipo si disponible
                if player_pts_share is not None:
                    # > 0.15 = líder ofensiva, < 0.05 = rol secundario
                    share_bonus = min(0.2, player_pts_share * 1.0)
                    production_score = min(1.0, production_score + share_bonus)
            
            # ✨ NUEVA PONDERACIÓN con features mejoradas:
            # - 20% Edad (proyección temporal)
            # - 30% Performance (z-scores ajustados por competición)
            # - 15% Production per-36 (producción normalizada)
            # - 15% Consistency (CV points, stability)
            # - 10% Advanced metrics (TS%, efficiency vs team)
            # - 10% Momentum (breakout detection)
            base_potential_score = (
                0.20 * age_score +
                0.30 * perf_score +
                0.15 * production_score +
                0.15 * consistency_score +
                0.10 * adv_metrics_score +
                0.10 * momentum_score
            )
            
            # Aplicar peso temporal al score final para priorizar datos recientes
            base_potential_score = base_potential_score * (0.85 + 0.15 * temporal_weight)
            
            # FASE 2: Calcular multiplicador de confianza
            confidence_score = self.calculate_confidence_multiplier(
                games_played=games_played or 0,
                total_minutes=total_minutes or 0.0,
                avg_minutes=avg_minutes or 0.0
            )
            
            # Aplicar ajuste de confianza al score final
            potential_score = base_potential_score * confidence_score
            
            # Determinar tier basado en score AJUSTADO
            if potential_score >= 0.75:
                tier = 'very_high'
            elif potential_score >= 0.60:
                tier = 'high'
            elif potential_score >= 0.45:
                tier = 'medium'
            elif potential_score >= 0.30:
                tier = 'low'
            else:
                tier = 'very_low'
            
            # Flags especiales
            is_young_talent = (age and age < 23 and perf_score >= 0.6 and meets_eligibility)
            is_consistent = (consistency_score >= 0.7 and perf_score >= 0.6 and meets_eligibility)
            
            # Insertar score de potencial con TODOS los nuevos campos
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
        self.logger.info(f"  ✓ Elegibles: {eligible_count} ({eligible_count/len(profiles)*100:.1f}%)")
        self.logger.info(f"  ⚠ No elegibles: {ineligible_count} ({ineligible_count/len(profiles)*100:.1f}%)")
    
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
        Calcular scores de potencial CONSOLIDADO por jugador único.
        
        Analiza toda la trayectoria del jugador (todas sus temporadas) y genera
        un score unificado que considera:
        - Rendimiento histórico promedio
        - Tendencia de mejora/deterioro
        - Últimas temporadas (con más peso)
        - Consistencia a lo largo de la carrera
        - Edad y proyección actual
        
        Args:
            conn: Conexión SQLite
        """
        if not self.use_profiles:
            return
        
        self.logger.info("Calculando scores de potencial CONSOLIDADO por jugador...")
        
        cursor = conn.cursor()
        
        # LIMPIAR DUPLICADOS PREVIOS: Eliminar todas las entradas antes de recalcular
        # Esto evita problemas con UNIQUE constraint y NULL birth_year
        self.logger.info("  Limpiando tabla player_career_potential...")
        cursor.execute("DELETE FROM player_career_potential")
        conn.commit()
        
        # Obtener todos los jugadores únicos (agrupados por nombre normalizado + birth_year)
        # IMPORTANTE: Filtrar nombres vacíos/NULL para evitar agregaciones incorrectas
        # IMPORTANTE: Usar COALESCE en birth_year para evitar duplicados por NULL
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
            HAVING seasons_count >= 1  -- Al menos 1 temporada
        """)
        
        players = cursor.fetchall()
        self.logger.info(f"  Procesando {len(players)} jugadores únicos...")
        
        # NUEVO: Calcular team strength factors para ajuste por contexto de equipo
        self.logger.info("  Calculando team strength factors...")
        team_factors = self.calculate_team_strength_factors(conn)
        
        for player in players:
            name_normalized, birth_year, seasons_count, first_season, last_season = player
            
            # Obtener todas las temporadas del jugador con sus scores Y nivel de competición
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
            
            # Calcular edad actual (basada en última temporada)
            try:
                last_season_year = int(last_season.split('/')[0])
                current_age = last_season_year - birth_year if birth_year else None
            except:
                current_age = None
            
            # Métricas de carrera
            total_games = sum(s[2] for s in season_data if s[2])
            total_minutes = sum(s[3] for s in season_data if s[3])
            
            # AGREGACIÓN POR TEMPORADA: Si un jugador tiene múltiples perfiles en la misma temporada
            # (por jugar en varios equipos/competiciones), AGREGAR sumando partidos/minutos y 
            # promediando scores ponderado por minutos Y nivel de competición.
            # IMPORTANTE: Aplicar multiplicador por nivel para valorar más las competiciones fuertes.
            # IMPORTANTE: Aplicar team context factor para ajustar por fuerza del equipo.
            seasons_aggregated = {}
            for s in season_data:
                season, profile_id, team_id, games, minutes, avg_min, base_score, pot_score, conf, eligible, off_rat, per, comp_level = s
                
                # Solo considerar perfiles elegibles con datos válidos
                if not eligible or pot_score is None or minutes is None or minutes == 0:
                    continue
                
                # NUEVO: Obtener team context factor
                # Este ajusta el rendimiento según la fuerza del equipo
                # Equipos top → ligero boost (+5-8%), equipos débiles → ligero dampening (-5-8%)
                team_factor = team_factors.get((team_id, season), 1.0)
                
                # Aplicar team context SOLO a las métricas de rendimiento (no a trajectory, age, etc)
                # Esto evita inflar/penalizar excesivamente
                adjusted_off_rat = off_rat * team_factor if off_rat is not None else None
                adjusted_per = per * team_factor if per is not None else None
                
                # NOTA: pot_score ya fue calculado previamente, no lo ajustamos directamente
                # El ajuste se aplicará en agregación de carrera (usando las z-scores ajustadas)
                # Por ahora mantenemos pot_score original para la agregación por temporada
                
                # Multiplicador por nivel de competición
                # Nivel 3 (LF ENDESA, máxima categoría) = 1.0
                # Nivel 2 (Primera División regional) = 0.90
                # Nivel 1 (LF CHALLENGE, segunda categoría nacional) = 0.85
                # Nivel 0 o desconocido = 0.80
                if comp_level == 3:
                    level_multiplier = 1.0
                elif comp_level == 2:
                    level_multiplier = 0.90
                elif comp_level == 1:
                    level_multiplier = 0.85
                else:
                    level_multiplier = 0.80
                
                # Score ajustado por nivel de competición Y team context
                # El team_factor ya está implícito en el pot_score a través de las métricas
                # pero para ser conservadores, aplicamos un factor reducido al score final
                team_adjusted_score = pot_score * (1.0 + 0.5 * (team_factor - 1.0))  # 50% del ajuste
                adjusted_score = team_adjusted_score * level_multiplier
                
                if season not in seasons_aggregated:
                    seasons_aggregated[season] = {
                        'games': games or 0,
                        'minutes': minutes,
                        'weighted_score_sum': adjusted_score * minutes,
                        'profiles': 1,
                        'max_level': comp_level  # Trackear el nivel máximo jugado
                    }
                else:
                    # Agregar: sumar partidos, minutos y scores ponderados
                    seasons_aggregated[season]['games'] += (games or 0)
                    seasons_aggregated[season]['minutes'] += minutes
                    seasons_aggregated[season]['weighted_score_sum'] += (adjusted_score * minutes)
                    seasons_aggregated[season]['profiles'] += 1
                    seasons_aggregated[season]['max_level'] = max(seasons_aggregated[season]['max_level'], comp_level)
            
            if not seasons_aggregated:
                # Si no hay temporadas elegibles, skip este jugador
                continue
            
            # Calcular score promedio ponderado por temporada
            eligible_seasons = []
            for season, data in sorted(seasons_aggregated.items(), reverse=True):
                avg_score = data['weighted_score_sum'] / data['minutes']
                eligible_seasons.append({
                    'season': season,
                    'games': data['games'],
                    'minutes': data['minutes'],
                    'score': avg_score,
                    'profiles': data['profiles'],  # Info: cuántos equipos jugó
                    'max_level': data['max_level']  # Nivel máximo de competición en esta temporada
                })
            
            # 1. Career Average Performance (promedio histórico ponderado por minutos)
            total_weighted_score = sum(s['score'] * s['minutes'] for s in eligible_seasons)
            total_minutes = sum(s['minutes'] for s in eligible_seasons)
            career_avg_performance = total_weighted_score / total_minutes if total_minutes > 0 else 0.5
            
            # 2. Recent Performance (últimas 2 temporadas, ponderado por minutos)
            # IMPORTANTE: Calcular de forma independiente para detectar mejoras
            recent_limit = min(2, len(eligible_seasons))
            recent_seasons = eligible_seasons[:recent_limit]
            recent_weighted_score = sum(s['score'] * s['minutes'] for s in recent_seasons)
            recent_minutes = sum(s['minutes'] for s in recent_seasons)
            recent_performance = recent_weighted_score / recent_minutes if recent_minutes > 0 else career_avg_performance
            
            # 3. Career Trajectory (tendencia de mejora) - OPTIMIZADO PARA SALTOS RÁPIDOS
            valid_perf_scores = [s['score'] for s in eligible_seasons[::-1]]  # Orden cronológico
            
            if len(valid_perf_scores) >= 3:
                # Para detectar mejoras explosivas, dar más peso a las últimas temporadas
                # Comparar últimas 2 vs todas las anteriores
                recent_avg = np.mean(valid_perf_scores[-2:])
                older_avg = np.mean(valid_perf_scores[:-2])
                improvement = recent_avg - older_avg
                
                # Regresión lineal tradicional
                x = np.arange(len(valid_perf_scores))
                y = np.array(valid_perf_scores)
                slope = np.polyfit(x, y, 1)[0] if len(x) > 1 else 0
                trajectory_from_slope = (slope / 0.15) * 0.5 + 0.5
                trajectory_from_slope = max(0.0, min(1.0, trajectory_from_slope))
                
                # Trajectory desde comparación directa (más sensible a saltos)
                if improvement > 0.10:  # Salto explosivo (>10%)
                    trajectory_from_improvement = 0.95
                elif improvement > 0.05:  # Salto significativo (>5%)
                    trajectory_from_improvement = 0.80
                elif improvement > 0.02:  # Mejora moderada
                    trajectory_from_improvement = 0.65
                elif improvement > -0.02:  # Estable
                    trajectory_from_improvement = 0.50
                else:  # Empeorando
                    trajectory_from_improvement = 0.30
                
                # Combinar ambos (70% comparación directa, 30% regresión)
                career_trajectory = 0.70 * trajectory_from_improvement + 0.30 * trajectory_from_slope
                    
            elif len(valid_perf_scores) == 2:
                # Solo 2 temporadas: comparar directamente con más granularidad
                improvement = valid_perf_scores[-1] - valid_perf_scores[0]
                if improvement > 0.10:  # Salto explosivo (>10%)
                    career_trajectory = 0.90
                elif improvement > 0.05:  # Mejora significativa (>5%)
                    career_trajectory = 0.75
                elif improvement > 0.02:  # Mejora moderada
                    career_trajectory = 0.65
                elif improvement > -0.02:  # Estable
                    career_trajectory = 0.50
                elif improvement > -0.05:  # Leve descenso
                    career_trajectory = 0.35
                else:  # Empeora significativamente
                    career_trajectory = 0.20
            else:
                career_trajectory = 0.50  # No hay suficiente histórico
            
            # AJUSTE: Si performance reciente es baja (<0.40), penalizar trayectoria
            # No tiene sentido dar alta trayectoria si el rendimiento actual es realmente malo
            # (Relajado de 0.45 a 0.40 para no penalizar jugadores en desarrollo)
            if recent_performance < 0.40:
                career_trajectory = min(career_trajectory, 0.40)  # Cap máximo 0.4
            
            # 4. Career Consistency (consistencia entre temporadas)
            if len(valid_perf_scores) >= 2:
                std_career = np.std(valid_perf_scores)
                career_consistency = max(0.0, 1.0 - (std_career / 0.5))  # Normalizar
            else:
                career_consistency = 0.5
            
            # 5. Age Projection Score (igual que antes pero con edad actual)
            if current_age:
                if current_age <= 21:
                    age_score = 1.0
                elif current_age <= 24:
                    age_score = 0.8
                elif current_age <= 27:
                    age_score = 0.5
                elif current_age <= 30:
                    age_score = 0.3
                else:
                    age_score = 0.1
            else:
                age_score = 0.5
            
            # 6. Career Confidence (basado en cantidad de datos)
            # AJUSTADO: No penalizar tanto a jugadores jóvenes con pocas temporadas
            # Un jugador con 2 temporadas sólidas puede tener alto potencial
            if seasons_count >= 4 and total_games >= 50:
                career_confidence = 1.0
            elif seasons_count >= 3 and total_games >= 30:
                career_confidence = 0.95
            elif seasons_count >= 2 and total_games >= 20:
                career_confidence = 0.90  # Era 0.8, ahora menos penalización
            elif seasons_count >= 2 and total_games >= 10:
                career_confidence = 0.85  # Nuevo: 2 temporadas con pocos partidos
            elif seasons_count >= 1 and total_games >= 15:
                career_confidence = 0.75  # Era 0.6
            else:
                career_confidence = 0.60  # Era 0.4
            
            # Detectar SALTOS DE NIVEL de competición (indicador de potencial explosivo)
            level_jump_bonus = 0.0
            if len(eligible_seasons) >= 2:
                # Comparar nivel máximo de últimas 2 temporadas vs temporadas anteriores
                recent_max_level = max([s['max_level'] for s in eligible_seasons[:2]])
                if len(eligible_seasons) > 2:
                    past_max_level = max([s['max_level'] for s in eligible_seasons[2:]])
                    level_jump = recent_max_level - past_max_level
                    if level_jump >= 2:  # Salto de 2+ niveles (ej: nivel 4 -> nivel 2)
                        level_jump_bonus = 0.15  # Bonus significativo
                    elif level_jump >= 1:
                        level_jump_bonus = 0.08
            
            # CALCULAR UNIFIED POTENTIAL SCORE
            # Ponderación OPTIMIZADA PARA CRECIMIENTO EXPLOSIVO:
            # - 50% Performance reciente (lo que hace AHORA es más importante)
            # - 25% Trayectoria de mejora (detectar momentum)
            # - 5% Performance histórica (pasado lejano poco relevante)
            # - 10% Edad/proyección (margen de crecimiento)
            # - 5% Consistencia (jugadores en desarrollo pueden ser inconsistentes)
            # - 5% Confianza de datos (no penalizar tanto a jóvenes con pocas temporadas)
            
            base_unified_score = (
                0.50 * recent_performance +
                0.25 * career_trajectory +
                0.05 * career_avg_performance +
                0.10 * age_score +
                0.05 * career_consistency +
                0.05 * career_confidence
            )
            
            # Aplicar bonus por salto de nivel
            unified_score = min(1.0, base_unified_score + level_jump_bonus)
            
            # PENALIZACIÓN POR INACTIVIDAD
            # Calcular cuántas temporadas han pasado desde la última temporada jugada
            current_year = 2026  # Actualizar cada año
            try:
                # Usar el año de FIN de la temporada (2025/2026 -> jugó hasta 2026)
                last_season_end_year = int(last_season.split('/')[1])
                seasons_inactive = current_year - last_season_end_year
                
                # Penalización progresiva por inactividad
                if seasons_inactive >= 1:
                    # 1 temporada sin jugar: -15% (puede ser lesión/académico)
                    # 2 temporadas sin jugar: -35% (preocupante)
                    # 3+ temporadas sin jugar: -60% (probablemente retirada o fuera de FEB)
                    if seasons_inactive == 1:
                        inactivity_penalty = 0.15
                    elif seasons_inactive == 2:
                        inactivity_penalty = 0.35
                    else:  # 3 o más temporadas
                        inactivity_penalty = 0.60
                    
                    unified_score = unified_score * (1.0 - inactivity_penalty)
                    
                    # Log para debugging
                    if unified_score >= 0.50:  # Solo loggear jugadores con potencial relevante
                        self.logger.info(
                            f"⚠️  {name_normalized}: {seasons_inactive} temporadas inactiva "
                            f"(última: {last_season}). Penalización: -{inactivity_penalty*100:.0f}%. "
                            f"Score ajustado: {unified_score:.3f}"
                        )
            except:
                pass  # Si no se puede parsear la temporada, no aplicar penalización
            
            # Determinar tier
            if unified_score >= 0.70:
                tier = 'elite'
            elif unified_score >= 0.60:
                tier = 'very_high'
            elif unified_score >= 0.50:
                tier = 'high'
            elif unified_score >= 0.40:
                tier = 'medium'
            else:
                tier = 'low'
            
            # Flags especiales
            # Rising Star: Jugador joven mejorando
            is_rising_star = (
                seasons_count >= 2 and
                current_age and current_age <= 24 and
                recent_performance > career_avg_performance + 0.02 and  # Mejora mínima 2%
                career_trajectory >= 0.55 and
                recent_performance >= 0.45
            )
            
            # Established Talent: Jugador consolidado
            is_established_talent = (
                seasons_count >= 3 and
                career_avg_performance >= 0.50 and
                career_consistency >= 0.7 and
                recent_performance >= 0.45
            )
            
            # Peak Performer: Jugador en su mejor momento
            is_peak_performer = (
                recent_performance >= 0.55 and
                (recent_performance > career_avg_performance * 1.05 or  # 5% mejor que carrera
                 recent_performance >= 0.65) and  # O directamente muy alto
                current_age and 22 <= current_age <= 29
            )
            
            # Encontrar mejor temporada
            best_season_data = max(eligible_seasons, key=lambda s: s['score'])
            best_season = best_season_data['season']
            best_season_score = best_season_data['score']
            
            # Insertar en base de datos
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
        Calcular estadísticas agregadas de un jugador para una temporada.
        
        Args:
            conn: Conexión SQLite
            player_id: ID del jugador
            season: Temporada
            competition_id: ID de competición
        """
        cursor = conn.cursor()
        
        # Obtener todas las stats del jugador en esa temporada
        cursor.execute("""
            SELECT 
                pgs.*,
                g.game_date
            FROM player_game_stats pgs
            JOIN games g ON pgs.game_id = g.game_id
            WHERE pgs.player_id = ?
                AND g.season = ?
                AND g.competition_id = ?
            ORDER BY g.game_date
        """, (player_id, season, competition_id))
        
        stats = cursor.fetchall()
        
        if not stats:
            return
        
        # Convertir a numpy arrays para cálculos
        games_played = len(stats)
        minutes = np.array([s["minutes_played"] for s in stats])
        points = np.array([s["points"] for s in stats])
        efficiency = np.array([s["efficiency_rating"] for s in stats])
        fg_pct = np.array([s["field_goal_pct"] for s in stats])
        three_pct = np.array([s["three_point_pct"] for s in stats])
        ft_pct = np.array([s["free_throw_pct"] for s in stats])
        rebounds = np.array([s["total_rebounds"] for s in stats])
        assists = np.array([s["assists"] for s in stats])
        wins = np.array([s["team_won"] for s in stats])
        
        # Métricas avanzadas
        ts_pct = np.array([s["true_shooting_pct"] if s["true_shooting_pct"] is not None else 0 for s in stats])
        efg_pct = np.array([s["effective_fg_pct"] if s["effective_fg_pct"] is not None else 0 for s in stats])
        oer = np.array([s["offensive_rating"] if s["offensive_rating"] is not None else 0 for s in stats])
        per = np.array([s["player_efficiency_rating"] if s["player_efficiency_rating"] is not None else 0 for s in stats])
        tov_pct = np.array([s["turnover_pct"] if s["turnover_pct"] is not None else 0 for s in stats])
        orb_pct = np.array([s["offensive_rebound_pct"] if s["offensive_rebound_pct"] is not None else 0 for s in stats])
        drb_pct = np.array([s["defensive_rebound_pct"] if s["defensive_rebound_pct"] is not None else 0 for s in stats])
        ws = np.array([s["win_shares"] if s["win_shares"] is not None else 0 for s in stats])
        ws_36 = np.array([s["win_shares_per_36"] if s["win_shares_per_36"] is not None else 0 for s in stats])
        
        # Calcular promedios
        avg_minutes = np.mean(minutes)
        avg_points = np.mean(points)
        avg_efficiency = np.mean(efficiency)
        avg_fg_pct = np.mean(fg_pct[fg_pct > 0])  # Solo donde hubo tiros
        avg_three_pct = np.mean(three_pct[three_pct > 0])
        avg_ft_pct = np.mean(ft_pct[ft_pct > 0])
        avg_rebounds = np.mean(rebounds)
        avg_assists = np.mean(assists)
        
        # Calcular desviaciones estándar
        std_points = np.std(points)
        std_efficiency = np.std(efficiency)
        
        # Calcular tendencias (regresión lineal simple)
        if games_played >= 3:
            x = np.arange(games_played)
            trend_points = np.polyfit(x, points, 1)[0]  # Pendiente
            trend_efficiency = np.polyfit(x, efficiency, 1)[0]
        else:
            trend_points = 0.0
            trend_efficiency = 0.0
        
        # Win percentage
        win_pct = np.mean(wins) * 100
        
        # Promedios de métricas avanzadas
        avg_ts_pct = np.mean(ts_pct[ts_pct > 0]) if np.any(ts_pct > 0) else None
        avg_efg_pct = np.mean(efg_pct[efg_pct > 0]) if np.any(efg_pct > 0) else None
        avg_oer = np.mean(oer[oer > 0]) if np.any(oer > 0) else None
        avg_per = np.mean(per[per != 0]) if np.any(per != 0) else None
        avg_tov_pct = np.mean(tov_pct[tov_pct > 0]) if np.any(tov_pct > 0) else None
        avg_orb_pct = np.mean(orb_pct[orb_pct > 0]) if np.any(orb_pct > 0) else None
        avg_drb_pct = np.mean(drb_pct[drb_pct > 0]) if np.any(drb_pct > 0) else None
        total_ws = np.sum(ws)
        avg_ws_36 = np.mean(ws_36[ws_36 > 0]) if np.any(ws_36 > 0) else None
        
        # Fechas
        date_from = stats[0]["game_date"]
        date_to = stats[-1]["game_date"]
        
        # Insertar agregados
        cursor.execute("""
            INSERT OR REPLACE INTO player_aggregated_stats (
                player_id, season, competition_id, games_played,
                date_from, date_to,
                avg_minutes, avg_points, avg_field_goal_pct,
                avg_three_point_pct, avg_free_throw_pct,
                avg_total_rebounds, avg_assists, avg_efficiency,
                total_points, total_rebounds, total_assists,
                std_points, std_efficiency,
                trend_points, trend_efficiency,
                avg_true_shooting_pct, avg_effective_fg_pct, avg_offensive_rating,
                avg_player_efficiency_rating, avg_turnover_pct,
                avg_offensive_rebound_pct, avg_defensive_rebound_pct,
                avg_win_shares_per_36,
                win_percentage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            player_id, season, competition_id, games_played,
            date_from, date_to,
            float(avg_minutes), float(avg_points), float(avg_fg_pct),
            float(avg_three_pct), float(avg_ft_pct),
            float(avg_rebounds), float(avg_assists), float(avg_efficiency),
            int(np.sum(points)), int(np.sum(rebounds)), int(np.sum(assists)),
            float(std_points), float(std_efficiency),
            float(trend_points), float(trend_efficiency),
            float(avg_ts_pct) if avg_ts_pct is not None else None,
            float(avg_efg_pct) if avg_efg_pct is not None else None,
            float(avg_oer) if avg_oer is not None else None,
            float(avg_per) if avg_per is not None else None,
            float(avg_tov_pct) if avg_tov_pct is not None else None,
            float(avg_orb_pct) if avg_orb_pct is not None else None,
            float(avg_drb_pct) if avg_drb_pct is not None else None,
            float(avg_ws_36) if avg_ws_36 is not None else None,
            float(win_pct)
        ))
    
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
                    candidate_min_score: float = 0.50):
        """
        Ejecutar el proceso ETL completo.
        
        Args:
            collections: Lista de colecciones a procesar (default: ambas)
            limit: Límite opcional de partidos por colección
            generate_candidates: Si True, genera candidatos de matching (solo con use_profiles=True)
            candidate_min_score: Score mínimo para generar candidatos
        """
        if collections is None:
            collections = ["all_feb_games_masc", "all_feb_games_fem"]
        
        self.logger.info("="*70)
        self.logger.info("INICIANDO PROCESO ETL: MongoDB -> SQLite")
        self.logger.info("="*70)
        self.logger.info(f"Modo: {'PERFILES' if self.use_profiles else 'JUGADORES ÚNICOS'}")
        
        start_time = datetime.now()
        total_games = 0
        total_players = 0
        
        conn = self.get_connection()
        
        try:
            for collection_name in collections:
                self.logger.info(f"\nProcesando colección: {collection_name}")
                
                # EXTRACT
                games = self.extract_games_from_mongodb(collection_name, limit)
                
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
