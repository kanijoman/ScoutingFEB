"""
Script para limpiar la base de datos MongoDB antes de un re-scrape completo.

ADVERTENCIA: Este script eliminará TODAS las colecciones de datos de partidos.
Solo ejecutar si estás seguro de que quieres empezar desde cero.
"""

import sys
sys.path.insert(0, 'src')

from database.mongodb_client import MongoDBClient
import pymongo

def clean_database():
    """Limpiar todas las colecciones de partidos."""
    
    print("=" * 80)
    print("LIMPIEZA DE BASE DE DATOS MONGODB")
    print("=" * 80)
    print()
    print("⚠️  ADVERTENCIA: Esta operación eliminará TODOS los datos de partidos.")
    print()
    
    # Pedir confirmación
    confirm = input("¿Estás seguro? Escribe 'CONFIRMAR' para continuar: ")
    
    if confirm != "CONFIRMAR":
        print("\nOperación cancelada.")
        return
    
    try:
        db = MongoDBClient()
        
        # Colecciones a limpiar
        collections = [
            "all_feb_games_fem",
            "all_feb_games_masc",
            "scraping_state"
        ]
        
        print("\nLimpiando colecciones...")
        
        for collection_name in collections:
            collection = db.get_collection(collection_name)
            count = collection.count_documents({})
            
            if count > 0:
                print(f"\n  - {collection_name}: {count} documentos")
                result = collection.delete_many({})
                print(f"    ✓ Eliminados {result.deleted_count} documentos")
            else:
                print(f"\n  - {collection_name}: Ya está vacía")
        
        print("\n" + "=" * 80)
        print("✓ Base de datos limpiada exitosamente")
        print("=" * 80)
        print("\nAhora puedes ejecutar el scraping desde cero:")
        print("  python src/run_scraping.py")
        
    except Exception as e:
        print(f"\n✗ Error al limpiar la base de datos: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        clean_database()
    except KeyboardInterrupt:
        print("\n\nOperación cancelada por el usuario.")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
