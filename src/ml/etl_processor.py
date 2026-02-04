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
        
        # Calcular porcentajes de tiro
        # FEB usa: p1m/p1a (tiros libres), p2m/p2a (tiros de 2), p3m/p3a (triples)
        three_made = safe_int(player.get("p3m", 0))
        three_att = safe_int(player.get("p3a", 0))
        three_pct = (three_made / three_att * 100) if three_att > 0 else 0.0
        
        two_made = safe_int(player.get("p2m", 0))
        two_att = safe_int(player.get("p2a", 0))
        two_pct = (two_made / two_att * 100) if two_att > 0 else 0.0
        
        field_goals_made = two_made + three_made
        field_goals_att = two_att + three_att
        field_goal_pct = (field_goals_made / field_goals_att * 100) if field_goals_att > 0 else 0.0
        
        ft_made = safe_int(player.get("p1m", 0))
        ft_att = safe_int(player.get("p1a", 0))
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
        
        # Preparar datos para calcular métricas avanzadas
        stats_for_advanced = {
            'pts': safe_int(player.get("pts", 0)),
            'fgm': field_goals_made,
            'fga': field_goals_att,
            'fg3m': three_made,
            'ftm': ft_made,
            'fta': ft_att,
            'orb': safe_int(player.get("offReb", 0)),
            'drb': safe_int(player.get("defReb", 0)),
            'reb': safe_int(player.get("totReb", 0)),
            'ast': safe_int(player.get("ass", 0)),
            'tov': safe_int(player.get("steals", 0)),  # Pérdidas
            'stl': safe_int(player.get("stl", 0)),
            'blk': safe_int(player.get("blocks", 0)),
            'minutes': minutes_played
        }
        
        # Calcular métricas avanzadas
        advanced_stats = calculate_all_advanced_stats(stats_for_advanced)
        
        return {
            "dorsal": player.get("no", ""),
            "name": player.get("name", "").strip(),
            "birth_year": birth_year,  # Usar la variable validada, no player.get()
            "age_at_game": age_at_game,
            "is_home": is_home,
            "is_starter": player.get("inn", "0") == "1",
            "team_won": team_won,
            
            # Tiempo
            "minutes_played": minutes_played,
            
            # Puntos
            "points": safe_int(player.get("pts", 0)),
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
            "offensive_rebounds": safe_int(player.get("ro", 0)),
            "defensive_rebounds": safe_int(player.get("rd", 0)),
            "total_rebounds": safe_int(player.get("rt", 0)),
            
            # Pases y balones
            "assists": safe_int(player.get("assist", 0)),
            "turnovers": safe_int(player.get("to", 0)),  # Pérdidas
            "steals": safe_int(player.get("st", 0)),  # Robos
            
            # Defensa
            "blocks": safe_int(player.get("bs", 0)),
            "blocks_received": safe_int(player.get("mt", 0)),
            "personal_fouls": safe_int(player.get("pf", 0)),
            "fouls_received": safe_int(player.get("rf", 0)),
            
            # Métricas legacy
            "plus_minus": safe_int(player.get("pllss", 0)),
            "efficiency_rating": safe_float(player.get("val", 0)),
            
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
            
            # Obtener stats del perfil
            cursor.execute("""
                SELECT 
                    COUNT(*) as games_played,
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
                        (points - (SELECT AVG(points) FROM player_game_stats WHERE player_id = ?))) as var_points
                FROM player_game_stats
                WHERE player_id = ?
            """, (profile_id, profile_id, profile_id, profile_id, profile_id))
            
            stats = cursor.fetchone()
            
            if stats and stats[0] > 0:
                # Calcular performance tier basado en z-scores
                avg_z_oer = stats[6] if stats[6] is not None else 0
                
                # Calcular desviaciones estándar desde varianza
                std_oer = (stats[9] ** 0.5) if stats[9] is not None and stats[9] > 0 else 0
                std_points = (stats[10] ** 0.5) if stats[10] is not None and stats[10] > 0 else 0
                
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
                
                # Insertar o actualizar métricas
                cursor.execute("""
                    INSERT OR REPLACE INTO player_profile_metrics (
                        profile_id, games_played, avg_minutes, avg_points,
                        avg_offensive_rating, avg_player_efficiency_rating,
                        avg_true_shooting_pct, avg_z_offensive_rating,
                        avg_z_player_efficiency_rating, avg_z_minutes,
                        std_offensive_rating, std_points, performance_tier
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    profile_id, stats[0], stats[1], stats[2],
                    stats[3], stats[4], stats[5], stats[6],
                    stats[7], stats[8], std_oer, std_points, tier
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
    
    def calculate_profile_potential_scores(self, conn: sqlite3.Connection):
        """
        Calcular scores de potencial para perfiles.
        
        Este score combina:
        - Edad y proyección
        - Tendencia de mejora
        - Consistencia
        - Métricas avanzadas
        
        Args:
            conn: Conexión SQLite
        """
        if not self.use_profiles:
            return
        
        self.logger.info("Calculando scores de potencial...")
        
        cursor = conn.cursor()
        
        # Obtener perfiles con métricas
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
                ppm.avg_true_shooting_pct
            FROM player_profiles pp
            JOIN player_profile_metrics ppm ON pp.profile_id = ppm.profile_id
        """)
        
        profiles = cursor.fetchall()
        
        for profile in profiles:
            profile_id, season, birth_year, avg_z_oer, avg_z_per, std_oer, std_points, games_played, avg_ts_pct = profile
            
            # Calcular edad estimada
            try:
                season_year = int(season.split('/')[0])
                age = season_year - birth_year if birth_year else None
            except:
                age = None
            
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
            
            # 2. Performance score basado en z-scores (0.0-1.0)
            if avg_z_oer is not None and avg_z_per is not None:
                # Normalizar z-scores a 0-1 (asumiendo rango -3 a +3)
                perf_score = ((avg_z_oer + avg_z_per) / 2 + 3) / 6
                perf_score = max(0.0, min(1.0, perf_score))
            else:
                perf_score = 0.5
            
            # 3. Consistency score (bajo std = más consistente)
            if std_oer is not None and std_oer > 0:
                # Normalizar: std bajo = score alto
                consistency_score = max(0.0, 1.0 - (std_oer / 50.0))
            else:
                consistency_score = 0.5
            
            # 4. Advanced metrics score (TS%)
            if avg_ts_pct is not None:
                # TS% > 55% es muy bueno
                adv_metrics_score = min(1.0, avg_ts_pct / 65.0)
            else:
                adv_metrics_score = 0.5
            
            # Calcular potential score combinado
            potential_score = (
                0.30 * age_score +
                0.40 * perf_score +
                0.20 * consistency_score +
                0.10 * adv_metrics_score
            )
            
            # Determinar tier
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
            is_young_talent = (age and age < 23 and perf_score >= 0.6)
            is_consistent = (consistency_score >= 0.7 and perf_score >= 0.6)
            
            # Insertar score de potencial
            cursor.execute("""
                INSERT OR REPLACE INTO player_profile_potential (
                    profile_id, age_projection_score, performance_trend_score,
                    consistency_score, advanced_metrics_score, potential_score,
                    potential_tier, is_young_talent, is_consistent_performer,
                    season
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile_id, age_score, perf_score, consistency_score,
                adv_metrics_score, potential_score, tier,
                is_young_talent, is_consistent, season
            ))
        
        conn.commit()
        self.logger.info(f"✓ Scores de potencial calculados para {len(profiles)} perfiles")
    
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
