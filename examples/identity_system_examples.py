"""
Script de ejemplo: Uso del sistema de identidades de jugadores.

Demuestra cómo usar los diferentes componentes del sistema.
"""

import sys
import os

# Añadir directorio src al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ml.name_normalizer import NameNormalizer
from ml.player_identity_matcher import PlayerIdentityMatcher
import sqlite3


def ejemplo_1_normalizacion_nombres():
    """Ejemplo 1: Normalización y comparación de nombres."""
    print("=" * 80)
    print("EJEMPLO 1: Normalización de Nombres")
    print("=" * 80)
    
    normalizer = NameNormalizer()
    
    # Casos de prueba
    test_cases = [
        ("J. PÉREZ", "JUAN PÉREZ"),
        ("PÉREZ, JUAN", "JUAN PÉREZ GARCÍA"),
        ("J.M. GARCÍA", "JOSÉ MARÍA GARCÍA"),
        ("DE LA TORRE, MARÍA", "MARÍA DE LA TORRE"),
        ("FERNÁNDEZ LÓPEZ", "FERNANDEZ, JUAN"),
    ]
    
    print("\nComparando nombres:\n")
    
    for name1, name2 in test_cases:
        # Calcular similitud
        similarity = normalizer.calculate_name_similarity(name1, name2)
        fuzzy = normalizer.fuzzy_match_score(name1, name2)
        
        # Parsear componentes
        comp1 = normalizer.parse_name_components(name1)
        comp2 = normalizer.parse_name_components(name2)
        
        print(f"'{name1}' vs '{name2}'")
        print(f"  Componentes 1: inicial='{comp1[0]}', nombre='{comp1[1]}', apellidos='{comp1[2]}'")
        print(f"  Componentes 2: inicial='{comp2[0]}', nombre='{comp2[1]}', apellidos='{comp2[2]}'")
        print(f"  Similitud estructural: {similarity:.3f}")
        print(f"  Similitud difusa:      {fuzzy:.3f}")
        print(f"  Recomendación: {'MATCH ✓' if similarity >= 0.70 else 'NO MATCH ✗'}")
        print()


def ejemplo_2_buscar_candidatos(db_path: str = None):
    """Ejemplo 2: Búsqueda de candidatos para identidad."""
    if db_path is None:
        db_path = str(Path(__file__).parent.parent.absolute() / "scouting_feb.db")
    """Ejemplo 2: Buscar candidatos de matching para un perfil."""
    print("=" * 80)
    print("EJEMPLO 2: Búsqueda de Candidatos")
    print("=" * 80)
    
    try:
        matcher = PlayerIdentityMatcher(db_path)
        
        # Obtener un perfil de ejemplo
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT profile_id, name_raw, team_id, season
            FROM player_profiles
            LIMIT 1
        """)
        
        profile = cursor.fetchone()
        
        if not profile:
            print("No hay perfiles en la base de datos.\n")
            conn.close()
            return
        
        profile_id = profile['profile_id']
        print(f"\nBuscando candidatos para perfil {profile_id}: {profile['name_raw']}")
        print(f"Equipo: {profile['team_id']} | Temporada: {profile['season']}\n")
        
        # Buscar candidatos
        candidates = matcher.find_candidate_matches(profile_id, min_score=0.30)
        
        if not candidates:
            print("No se encontraron candidatos.\n")
        else:
            print(f"Encontrados {len(candidates)} candidatos:\n")
            
            for i, cand in enumerate(candidates[:5], 1):
                print(f"{i}. [{cand['candidate_score']:.3f}] {cand['name_raw']}")
                print(f"   Equipo: {cand['team_id']} | Temporada: {cand['season']}")
                print(f"   Componentes: N={cand['name_match_score']:.2f}, "
                      f"E={cand['age_match_score']:.2f}, "
                      f"T={cand['team_overlap_score']:.2f}, "
                      f"TL={cand['timeline_fit_score']:.2f}")
                print(f"   Confianza: {cand['confidence_level']}")
                print()
        
        conn.close()
        
    except sqlite3.OperationalError as e:
        print(f"Error: Base de datos no encontrada o sin las tablas necesarias.")
        print(f"Ejecutar primero: python src/ml/etl_processor.py\n")


def ejemplo_3_estadisticas_sistema(db_path: str = None):
    """Ejemplo 3: Estadísticas del sistema."""
    if db_path is None:
        db_path = str(Path(__file__).parent.parent.absolute() / "scouting_feb.db")
    
    print("=" * 80)
    print("EJEMPLO 3: Estadísticas del Sistema")
    print("=" * 80)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Contar perfiles
        cursor.execute("SELECT COUNT(*) FROM player_profiles")
        total_profiles = cursor.fetchone()[0]
        
        # Contar candidatos
        cursor.execute("SELECT COUNT(*) FROM player_identity_candidates")
        total_candidates = cursor.fetchone()[0]
        
        # Candidatos por nivel de confianza
        cursor.execute("""
            SELECT confidence_level, COUNT(*) as count
            FROM player_identity_candidates
            GROUP BY confidence_level
        """)
        by_confidence = cursor.fetchall()
        
        # Candidatos por estado de validación
        cursor.execute("""
            SELECT validation_status, COUNT(*) as count
            FROM player_identity_candidates
            GROUP BY validation_status
        """)
        by_validation = cursor.fetchall()
        
        # Perfiles con alto potencial
        cursor.execute("""
            SELECT COUNT(*) FROM player_profile_potential
            WHERE potential_tier IN ('very_high', 'high')
        """)
        high_potential = cursor.fetchone()[0]
        
        # Jugadores jóvenes con talento
        cursor.execute("""
            SELECT COUNT(*) FROM player_profile_potential
            WHERE is_young_talent = 1
        """)
        young_talent = cursor.fetchone()[0]
        
        # Imprimir resultados
        print(f"\nPerfiles de jugadores: {total_profiles}")
        print(f"Candidatos de matching: {total_candidates}")
        
        print("\nPor nivel de confianza:")
        for conf_level, count in by_confidence:
            print(f"  {conf_level}: {count}")
        
        print("\nPor estado de validación:")
        for status, count in by_validation:
            print(f"  {status}: {count}")
        
        print(f"\nPerfiles con alto potencial: {high_potential}")
        print(f"Jugadores jóvenes con talento: {young_talent}")
        print()
        
        conn.close()
        
    except sqlite3.OperationalError as e:
        print(f"Error: Base de datos no encontrada o sin las tablas necesarias.")
        print(f"Ejecutar primero: python src/ml/etl_processor.py\n")


def ejemplo_4_consultas_scouting(db_path: str = None):
    """Ejemplo 4: Consultas típicas de scouting."""
    if db_path is None:
        db_path = str(Path(__file__).parent.parent.absolute() / "scouting_feb.db")
    
    print("=" * 80)
    print("EJEMPLO 4: Consultas de Scouting")
    print("=" * 80)
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Top 10 jugadores jóvenes con mayor potencial
        print("\nTop 10 Jugadores Jóvenes con Mayor Potencial:\n")
        
        cursor.execute("""
            SELECT 
                pp.profile_id,
                pp.name_raw,
                pp.birth_year,
                pp.season,
                t.team_name,
                ppm.avg_points,
                ppm.avg_offensive_rating,
                ppp.potential_score
            FROM player_profiles pp
            JOIN player_profile_potential ppp ON pp.profile_id = ppp.profile_id
            LEFT JOIN player_profile_metrics ppm ON pp.profile_id = ppm.profile_id
            LEFT JOIN teams t ON pp.team_id = t.team_id
            WHERE ppp.is_young_talent = 1
            ORDER BY ppp.potential_score DESC
            LIMIT 10
        """)
        
        results = cursor.fetchall()
        
        if not results:
            print("No hay jugadores jóvenes con potencial en la base de datos.\n")
        else:
            for i, row in enumerate(results, 1):
                age = 2026 - row['birth_year'] if row['birth_year'] else "N/A"
                print(f"{i}. {row['name_raw']} ({age} años)")
                print(f"   Equipo: {row['team_name']} | Temporada: {row['season']}")
                print(f"   Stats: {row['avg_points']:.1f} pts, OER={row['avg_offensive_rating']:.1f}")
                print(f"   Potencial: {row['potential_score']:.3f}")
                print()
        
        conn.close()
        
    except sqlite3.OperationalError as e:
        print(f"Error: Base de datos no encontrada o sin las tablas necesarias.")
        print(f"Ejecutar primero: python src/ml/etl_processor.py\n")


def main():
    """Ejecutar todos los ejemplos."""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "EJEMPLOS - SISTEMA DE IDENTIDADES" + " " * 25 + "║")
    print("╚" + "═" * 78 + "╝")
    print()
    
    # Ejemplo 1: Normalización (no requiere BD)
    ejemplo_1_normalizacion_nombres()
    
    input("Presiona Enter para continuar al siguiente ejemplo...")
    print("\n")
    
    # Ejemplo 2: Búsqueda de candidatos (requiere BD)
    ejemplo_2_buscar_candidatos()
    
    input("Presiona Enter para continuar al siguiente ejemplo...")
    print("\n")
    
    # Ejemplo 3: Estadísticas (requiere BD)
    ejemplo_3_estadisticas_sistema()
    
    input("Presiona Enter para continuar al siguiente ejemplo...")
    print("\n")
    
    # Ejemplo 4: Consultas de scouting (requiere BD)
    ejemplo_4_consultas_scouting()
    
    print("=" * 80)
    print("FIN DE LOS EJEMPLOS")
    print("=" * 80)
    print("\nPara más información, consultar: PLAYER_IDENTITY_SYSTEM.md")
    print()


if __name__ == "__main__":
    main()
