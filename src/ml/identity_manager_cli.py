"""
Herramienta CLI para gestión de identidades de jugadores.

Permite revisar y validar candidatos de matching de perfiles.
"""

import sys
import os

# Agregar el directorio src al path para imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import sqlite3
import argparse
import logging
from typing import List, Dict
from ml.player_identity_matcher import PlayerIdentityMatcher


class PlayerIdentityManager:
    """Gestor interactivo de identidades de jugadores."""
    
    def __init__(self, db_path: str = None):
        """
        Inicializar el gestor.
        
        Args:
            db_path: Ruta a la base de datos SQLite
        """
        if db_path is None:
            # Buscar la base de datos en raíz primero, luego en src/
            root_db = os.path.join(os.path.dirname(__file__), "..", "..", "scouting_feb.db")
            src_db = os.path.join(os.path.dirname(__file__), "..", "scouting_feb.db")
            
            if os.path.exists(root_db):
                db_path = root_db
            elif os.path.exists(src_db):
                db_path = src_db
            else:
                db_path = "scouting_feb.db"
        
        self.db_path = os.path.abspath(db_path)
        print(f"Usando base de datos: {self.db_path}")
        self.matcher = PlayerIdentityMatcher(db_path)
        self.logger = logging.getLogger(__name__)
    
    def list_high_confidence_candidates(self, min_score: float = 0.70, limit: int = 50):
        """
        Listar candidatos de alta confianza.
        
        Args:
            min_score: Score mínimo
            limit: Límite de candidatos a mostrar
        """
        candidates = self.matcher.get_high_confidence_candidates(min_score=min_score)
        
        print("=" * 100)
        print(f"CANDIDATOS DE ALTA CONFIANZA (Score >= {min_score})")
        print("=" * 100)
        print(f"Total encontrados: {len(candidates)}\n")
        
        if not candidates:
            print("No se encontraron candidatos con el threshold especificado.\n")
            return
        
        for i, cand in enumerate(candidates[:limit], 1):
            print(f"{i}. [Score: {cand['candidate_score']:.3f}] ID: {cand['candidate_id']}")
            print(f"   Perfil 1: {cand['name_1']} | Equipo: {cand['team_1']} | Temporada: {cand['season_1']} | Edad: {cand['birth_year_1'] or 'N/A'}")
            print(f"   Perfil 2: {cand['name_2']} | Equipo: {cand['team_2']} | Temporada: {cand['season_2']} | Edad: {cand['birth_year_2'] or 'N/A'}")
            print(f"   Componentes: Nombre={cand['name_match_score']:.2f}, Edad={cand['age_match_score']:.2f}, "
                  f"Equipo={cand['team_overlap_score']:.2f}, Timeline={cand['timeline_fit_score']:.2f}")
            print(f"   Confianza: {cand['confidence_level'].upper()}")
            print()
        
        if len(candidates) > limit:
            print(f"... y {len(candidates) - limit} más.\n")
    
    def get_profile_details(self, profile_id: int):
        """
        Obtener detalles de un perfil.
        
        Args:
            profile_id: ID del perfil
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Información del perfil
        cursor.execute("""
            SELECT 
                pp.*,
                t.team_name,
                c.competition_name,
                ppm.games_played,
                ppm.avg_points,
                ppm.avg_minutes,
                ppm.avg_offensive_rating,
                ppm.performance_tier,
                ppp.potential_score,
                ppp.potential_tier,
                ppp.is_young_talent
            FROM player_profiles pp
            LEFT JOIN teams t ON pp.team_id = t.team_id
            LEFT JOIN competitions c ON pp.competition_id = c.competition_id
            LEFT JOIN player_profile_metrics ppm ON pp.profile_id = ppm.profile_id
            LEFT JOIN player_profile_potential ppp ON pp.profile_id = ppp.profile_id
            WHERE pp.profile_id = ?
        """, (profile_id,))
        
        profile = cursor.fetchone()
        
        if not profile:
            print(f"Perfil {profile_id} no encontrado.\n")
            conn.close()
            return
        
        print("=" * 80)
        print(f"PERFIL ID: {profile['profile_id']}")
        print("=" * 80)
        print(f"Nombre: {profile['name_raw']}")
        print(f"Nombre normalizado: {profile['name_normalized']}")
        print(f"FEB ID: {profile['feb_id'] or 'N/A'}")
        print(f"Equipo: {profile['team_name']}")
        print(f"Temporada: {profile['season']}")
        print(f"Competición: {profile['competition_name']}")
        print(f"Año nacimiento: {profile['birth_year'] or 'N/A'}")
        print(f"Dorsal: {profile['dorsal'] or 'N/A'}")
        print(f"\nEstadísticas:")
        print(f"  Partidos: {profile['games_played'] or 0}")
        print(f"  Minutos promedio: {profile['avg_minutes']:.1f}" if profile['avg_minutes'] else "  Minutos promedio: N/A")
        print(f"  Puntos promedio: {profile['avg_points']:.1f}" if profile['avg_points'] else "  Puntos promedio: N/A")
        print(f"  OER promedio: {profile['avg_offensive_rating']:.1f}" if profile['avg_offensive_rating'] else "  OER promedio: N/A")
        print(f"  Performance tier: {profile['performance_tier'] or 'N/A'}")
        print(f"\nPotencial:")
        print(f"  Score: {profile['potential_score']:.3f}" if profile['potential_score'] else "  Score: N/A")
        print(f"  Tier: {profile['potential_tier'] or 'N/A'}")
        print(f"  Joven talento: {'Sí' if profile['is_young_talent'] else 'No'}")
        print()
        
        conn.close()
    
    def validate_candidate(
        self,
        candidate_id: int,
        status: str,
        notes: str = None
    ):
        """
        Validar un candidato.
        
        Args:
            candidate_id: ID del candidato
            status: 'confirmed', 'rejected', 'unsure'
            notes: Notas opcionales
        """
        if status not in ['confirmed', 'rejected', 'unsure']:
            print(f"Estado inválido: {status}. Debe ser 'confirmed', 'rejected' o 'unsure'.\n")
            return
        
        success = self.matcher.validate_candidate(
            candidate_id,
            status,
            validated_by="cli_user",
            notes=notes
        )
        
        if success:
            print(f"✓ Candidato {candidate_id} marcado como '{status}'.\n")
        else:
            print(f"✗ Error validando candidato {candidate_id}.\n")
    
    def get_validation_stats(self):
        """Mostrar estadísticas de validación."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                validation_status,
                COUNT(*) as count
            FROM player_identity_candidates
            GROUP BY validation_status
        """)
        
        stats = cursor.fetchall()
        
        print("=" * 80)
        print("ESTADÍSTICAS DE VALIDACIÓN")
        print("=" * 80)
        
        for stat in stats:
            print(f"{stat['validation_status'].upper()}: {stat['count']}")
        
        # Total
        cursor.execute("SELECT COUNT(*) FROM player_identity_candidates")
        total = cursor.fetchone()[0]
        
        print(f"\nTOTAL: {total}")
        print()
        
        conn.close()
    
    def list_profiles_by_potential(self, min_score: float = 0.60, limit: int = 50):
        """
        Listar jugadoras por potencial consolidado de carrera.
        
        Args:
            min_score: Score mínimo de potencial
            limit: Límite de jugadoras a mostrar
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                pcp.career_potential_id,
                pcp.player_name,
                pcp.unified_potential_score,
                pcp.potential_tier,
                pcp.career_avg_performance,
                pcp.recent_performance,
                pcp.seasons_played,
                pcp.last_season,
                pcp.birth_year,
                pcp.current_age,
                pcp.is_rising_star,
                pcp.is_peak_performer,
                pcp.is_established_talent,
                pcp.career_trajectory,
                pp_latest.team_id,
                t.team_name,
                c.competition_name,
                ppm_latest.avg_points,
                ppm_latest.avg_offensive_rating
            FROM player_career_potential pcp
            LEFT JOIN (
                SELECT name_raw, season, team_id, competition_id, profile_id,
                       ROW_NUMBER() OVER (PARTITION BY name_raw, season ORDER BY profile_id DESC) as rn
                FROM player_profiles
            ) pp_latest ON 
                pcp.player_name = pp_latest.name_raw 
                AND pcp.last_season = pp_latest.season
                AND pp_latest.rn = 1
            LEFT JOIN teams t ON pp_latest.team_id = t.team_id
            LEFT JOIN competitions c ON pp_latest.competition_id = c.competition_id
            LEFT JOIN player_profile_metrics ppm_latest ON pp_latest.profile_id = ppm_latest.profile_id
            WHERE pcp.unified_potential_score >= ?
            GROUP BY pcp.career_potential_id
            ORDER BY pcp.unified_potential_score DESC
            LIMIT ?
        """, (min_score, limit))
        
        profiles = cursor.fetchall()
        
        print("=" * 120)
        print(f"JUGADORAS CON ALTO POTENCIAL (Score >= {min_score})")
        print("=" * 120)
        print(f"Total encontradas: {len(profiles)}\n")
        
        if not profiles:
            print("No se encontraron jugadoras con el threshold especificado.\n")
            conn.close()
            return
        
        for i, profile in enumerate(profiles, 1):
            flags = []
            if profile['is_rising_star']:
                flags.append("🌟 JOVEN")
            if profile['is_peak_performer']:
                flags.append("🔥 PICO")
            if profile['is_established_talent']:
                flags.append("👑 VETERANA")
            
            # Indicadores de tendencia
            if profile['career_trajectory'] and profile['career_trajectory'] > 0.15:
                flags.append("📈 ASCENSO")
            elif profile['career_trajectory'] and profile['career_trajectory'] < -0.10:
                flags.append("📉 DECLIVE")
            
            flags_str = " ".join(flags) if flags else ""
            
            age = profile['current_age'] if profile['current_age'] else "N/A"
            
            # Manejar valores None en estadísticas
            avg_pts = profile['avg_points'] if profile['avg_points'] is not None else 0.0
            avg_oer = profile['avg_offensive_rating'] if profile['avg_offensive_rating'] is not None else 0.0
            pot_tier = profile['potential_tier'] or "N/A"
            seasons = profile['seasons_played'] or 0
            team = profile['team_name'] or "N/A"
            
            print(f"{i}. [{profile['unified_potential_score']:.3f}] {profile['player_name']} {flags_str}")
            print(f"   ID: {profile['career_potential_id']} | {seasons} temporadas")
            print(f"   Última: {team} | {profile['last_season']} | Edad: {age}")
            print(f"   Stats Última Temp: {avg_pts:.1f} pts, OER={avg_oer:.1f} | Potencial: {pot_tier}")
            print()
        
        conn.close()


def main():
    """CLI principal."""
    logging.basicConfig(level=logging.INFO)
    
    parser = argparse.ArgumentParser(
        description='Herramienta de gestión de identidades de jugadores'
    )
    
    # Argumento global (debe ir antes de subparsers)
    parser.add_argument('--db', type=str, default=None,
                       help='Ruta a la base de datos (default: src/scouting_feb.db)')
    
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponibles')
    
    # Comando: list-candidates
    candidates_parser = subparsers.add_parser('list-candidates', 
                                             help='Listar candidatos de matching')
    candidates_parser.add_argument('--min-score', type=float, default=0.70,
                                  help='Score mínimo (default: 0.70)')
    candidates_parser.add_argument('--limit', type=int, default=50,
                                  help='Límite de resultados (default: 50)')
    
    # Comando: profile
    profile_parser = subparsers.add_parser('profile', help='Ver detalles de un perfil')
    profile_parser.add_argument('profile_id', type=int, help='ID del perfil')
    
    # Comando: validate
    validate_parser = subparsers.add_parser('validate', help='Validar un candidato')
    validate_parser.add_argument('candidate_id', type=int, help='ID del candidato')
    validate_parser.add_argument('status', choices=['confirmed', 'rejected', 'unsure'],
                                help='Estado de validación')
    validate_parser.add_argument('--notes', type=str, help='Notas opcionales')
    
    # Comando: stats
    subparsers.add_parser('stats', help='Ver estadísticas de validación')
    
    # Comando: potential
    potential_parser = subparsers.add_parser('potential', 
                                            help='Listar perfiles con alto potencial')
    potential_parser.add_argument('--min-score', type=float, default=0.60,
                                 help='Score mínimo de potencial (default: 0.60)')
    potential_parser.add_argument('--limit', type=int, default=50,
                                 help='Límite de resultados (default: 50)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Crear manager
    manager = PlayerIdentityManager(args.db)
    
    # Ejecutar comando
    if args.command == 'list-candidates':
        manager.list_high_confidence_candidates(args.min_score, args.limit)
    
    elif args.command == 'profile':
        manager.get_profile_details(args.profile_id)
    
    elif args.command == 'validate':
        manager.validate_candidate(args.candidate_id, args.status, args.notes)
    
    elif args.command == 'stats':
        manager.get_validation_stats()
    
    elif args.command == 'potential':
        manager.list_profiles_by_potential(args.min_score, args.limit)


if __name__ == "__main__":
    from datetime import datetime
    main()
