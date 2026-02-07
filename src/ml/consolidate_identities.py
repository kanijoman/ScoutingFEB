"""
Script para consolidar identidades de jugadoras automáticamente.
Crea consolidated_player_id basándose en matching por nombre normalizado.
"""

import sqlite3
import sys
from pathlib import Path

# Ajustar path para imports cuando se ejecuta standalone
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.name_normalizer import NameNormalizer

def consolidate_identities(db_path='scouting_feb.db', min_score=0.85):
    """
    Consolidar perfiles de jugadoras usando matching por nombre normalizado.
    
    Args:
        db_path: Ruta a la base de datos
        min_score: Score mínimo de similitud (0-1)
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    normalizer = NameNormalizer()
    
    print(f"Consolidando identidades con score mínimo: {min_score}")
    
    # 1. Resetear consolidaciones previas
    print("\n1. Limpiando consolidaciones previas...")
    cursor.execute("UPDATE player_profiles SET consolidated_player_id = NULL, is_consolidated = 0")
    conn.commit()
    
    # 2. Agrupar perfiles por nombre normalizado
    print("\n2. Agrupando perfiles por nombre normalizado...")
    query = """
    SELECT profile_id, name_normalized, season, birth_year
    FROM player_profiles
    ORDER BY name_normalized, season
    """
    cursor.execute(query)
    profiles = cursor.fetchall()
    
    # 3. Crear grupos de identidad
    print("\n3. Creando grupos de identidad...")
    identity_groups = {}  # {nombre_base: [(profile_id, birth_year)]}
    
    # OPTIMIZACIÓN: Primero agrupar por match exacto
    exact_groups = {}
    for profile_id, name_norm, season, birth_year in profiles:
        if not name_norm:
            continue
        if name_norm not in exact_groups:
            exact_groups[name_norm] = []
        exact_groups[name_norm].append((profile_id, birth_year))
    
    print(f"   Grupos por match exacto: {len(exact_groups)}")
    
    # Asignar los grupos exactos directamente
    for name_norm, group_data in exact_groups.items():
        identity_groups[name_norm] = [pid for pid, _ in group_data]
    
    print(f"   Total grupos creados: {len(identity_groups)}")
    
    # 4. Asignar consolidated_player_id
    print("\n4. Asignando IDs consolidados...")
    consolidated_count = 0
    multi_profile_count = 0
    
    for group_profiles in identity_groups.values():
        if len(group_profiles) > 1:
            multi_profile_count += 1
        
        # Usar el profile_id más antiguo como consolidated_player_id
        consolidated_id = min(group_profiles)
        
        for profile_id in group_profiles:
            cursor.execute("""
                UPDATE player_profiles 
                SET consolidated_player_id = ?, 
                    is_consolidated = 1
                WHERE profile_id = ?
            """, (consolidated_id, profile_id))
            consolidated_count += 1
    
    conn.commit()
    
    # 5. Estadísticas
    print("\n" + "="*70)
    print("RESULTADOS DE CONSOLIDACIÓN")
    print("="*70)
    print(f"Total perfiles procesados: {len(profiles)}")
    print(f"Grupos de identidad creados: {len(identity_groups)}")
    print(f"Jugadoras con múltiples perfiles: {multi_profile_count}")
    print(f"Perfiles consolidados: {consolidated_count}")
    
    # Ver ejemplos de consolidación
    query = """
    SELECT consolidated_player_id, COUNT(*) as num_profiles,
           COUNT(DISTINCT season) as num_seasons,
           GROUP_CONCAT(DISTINCT season ORDER BY season) as seasons,
           MAX(name_normalized) as name
    FROM player_profiles
    WHERE is_consolidated = 1
    GROUP BY consolidated_player_id
    HAVING num_profiles > 1
    ORDER BY num_profiles DESC
    LIMIT 10
    """
    cursor.execute(query)
    results = cursor.fetchall()
    
    if results:
        print("\nTop 10 jugadoras con más perfiles consolidados:")
        print("-" * 70)
        for cons_id, num_prof, num_seas, seasons, name in results:
            print(f"{name[:30]:<30} | {num_prof} perfiles | {num_seas} temporadas")
            print(f"  Temporadas: {seasons}")
    
    conn.close()
    print("\n✓ Consolidación completada")

if __name__ == "__main__":
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description="Consolidar identidades de jugadoras")
    parser.add_argument("--db", default=None, help="Ruta a la base de datos")
    parser.add_argument("--min-score", type=float, default=0.95, help="Score mínimo de similitud (0-1)")
    
    args = parser.parse_args()
    
    # Si no se especifica DB, buscar en raíz del proyecto
    if args.db is None:
        db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'scouting_feb.db')
    else:
        db_path = args.db
    
    consolidate_identities(db_path, args.min_score)
