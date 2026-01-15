"""
Script unificado para scraping de datos de FEB.

Este script permite:
- Scraping incremental (solo encuentros nuevos)
- Scraping completo (re-scraping)
- Scraping de múltiples competiciones
- Consultar estado y base de datos
"""

from .main import FEBScoutingScraper
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def list_competitions():
    """Listar todas las competiciones disponibles."""
    print("\n" + "="*60)
    print("LISTAR COMPETICIONES DISPONIBLES")
    print("="*60 + "\n")
    
    scraper = FEBScoutingScraper()
    competitions = scraper.list_available_competitions()
    print(f"\nTotal competitions found: {len(competitions)}")
    scraper.close()


def scrape_interactive():
    """Scraping interactivo - permite elegir competición."""
    print("\n" + "="*60)
    print("SCRAPING INTERACTIVO (INCREMENTAL)")
    print("="*60 + "\n")
    
    scraper = FEBScoutingScraper()
    
    # Listar competiciones disponibles
    print("Competiciones disponibles:")
    print("-"*60)
    competitions = scraper.list_available_competitions()
    
    if not competitions:
        print("No se encontraron competiciones. Verifica la conexión.")
        scraper.close()
        return
    
    # Solicitar nombre de competición
    print("\n" + "="*60)
    comp_name = input("Introduce el nombre de la competición (ej: 'LF2', 'LEB ORO'): ").strip()
    
    if not comp_name:
        print("No se proporcionó nombre. Cancelando.")
        scraper.close()
        return
    
    # Scraping incremental (por defecto)
    print(f"\n🔄 Scraping incremental de: {comp_name}")
    print("Solo se procesarán encuentros nuevos que no estén en la BD")
    print("-"*60)
    
    stats = scraper.scrape_competition_by_name(comp_name, incremental=True)
    
    print("\n" + "="*60)
    print("📊 RESULTADOS:")
    print("="*60)
    print(f"Competición: {stats.get('competition', 'N/A')}")
    print(f"Género: {stats.get('gender', 'N/A')}")
    print(f"Colección: {stats.get('collection', 'N/A')}")
    print(f"Temporadas: {stats.get('total_seasons', 0)}")
    print(f"Grupos: {stats.get('total_groups', 0)}")
    print(f"Encuentros encontrados: {stats.get('total_matches_found', 0)}")
    print(f"✅ Encuentros nuevos procesados: {stats.get('total_matches_scraped', 0)}")
    print(f"⏭️  Encuentros omitidos (ya en BD): {stats.get('total_matches_skipped', 0)}")
    print(f"❌ Encuentros fallidos: {stats.get('total_matches_failed', 0)}")
    
    scraper.close()


def scrape_full_rescrape():
    """Scraping completo (re-scraping) - procesa todos los encuentros."""
    print("\n" + "="*60)
    print("SCRAPING COMPLETO (RE-SCRAPING)")
    print("="*60 + "\n")
    
    scraper = FEBScoutingScraper()
    
    # Listar competiciones
    print("Competiciones disponibles:")
    print("-"*60)
    scraper.list_available_competitions()
    
    # Solicitar nombre
    print("\n" + "="*60)
    comp_name = input("Introduce el nombre de la competición: ").strip()
    
    if not comp_name:
        print("No se proporcionó nombre. Cancelando.")
        scraper.close()
        return
    
    # Confirmar operación
    confirm = input(f"\n⚠️  ¿Confirmas re-scraping COMPLETO de '{comp_name}'? (s/n): ").strip().lower()
    
    if confirm not in ['s', 'si', 'sí', 'y', 'yes']:
        print("Operación cancelada.")
        scraper.close()
        return
    
    # Scraping completo
    print(f"\n🔄 Re-scraping completo de: {comp_name}")
    print("Se procesarán TODOS los encuentros, incluso los existentes")
    print("-"*60)
    
    stats = scraper.scrape_competition_by_name(comp_name, incremental=False)
    
    print("\n" + "="*60)
    print("📊 RESULTADOS:")
    print("="*60)
    print(f"Encuentros encontrados: {stats.get('total_matches_found', 0)}")
    print(f"Encuentros procesados: {stats.get('total_matches_scraped', 0)}")
    print(f"Encuentros fallidos: {stats.get('total_matches_failed', 0)}")
    
    scraper.close()


def scrape_multiple_competitions():
    """Scraping de múltiples competiciones."""
    print("\n" + "="*60)
    print("SCRAPING MÚLTIPLES COMPETICIONES")
    print("="*60 + "\n")
    
    scraper = FEBScoutingScraper()
    
    # Solicitar competiciones
    print("Introduce las competiciones separadas por comas")
    print("Ejemplo: LF2, LF, LEB ORO, ACB")
    comp_input = input("\nCompeticiones: ").strip()
    
    if not comp_input:
        print("No se proporcionaron competiciones. Cancelando.")
        scraper.close()
        return
    
    competiciones = [c.strip() for c in comp_input.split(',')]
    
    print(f"\n🔄 Procesando {len(competiciones)} competiciones...")
    print("-"*60)
    
    resultados = {}
    
    for comp in competiciones:
        print(f"\n📥 Procesando: {comp}")
        stats = scraper.scrape_competition_by_name(comp, incremental=True)
        resultados[comp] = stats
        
        print(f"  ✅ {stats.get('total_matches_scraped', 0)} nuevos, "
              f"⏭️  {stats.get('total_matches_skipped', 0)} omitidos")
    
    # Resumen final
    print("\n" + "="*60)
    print("📊 RESUMEN FINAL:")
    print("="*60)
    total_nuevos = sum(r.get('total_matches_scraped', 0) for r in resultados.values())
    total_omitidos = sum(r.get('total_matches_skipped', 0) for r in resultados.values())
    total_fallidos = sum(r.get('total_matches_failed', 0) for r in resultados.values())
    
    print(f"Total encuentros nuevos: {total_nuevos}")
    print(f"Total encuentros omitidos: {total_omitidos}")
    print(f"Total encuentros fallidos: {total_fallidos}")
    
    scraper.close()


def query_database():
    """Consultar estado de la base de datos."""
    print("\n" + "="*60)
    print("CONSULTAR BASE DE DATOS")
    print("="*60 + "\n")
    
    scraper = FEBScoutingScraper()
    
    # Contar partidos
    masc_count = scraper.db_client.count_games("all_feb_games_masc")
    fem_count = scraper.db_client.count_games("all_feb_games_fem")
    
    print(f"🏀 Partidos masculinos: {masc_count}")
    print(f"🏀 Partidos femeninos: {fem_count}")
    print(f"📊 Total partidos: {masc_count + fem_count}")
    
    # Muestra de partido
    if fem_count > 0 or masc_count > 0:
        print("\n" + "-"*60)
        print("MUESTRA DE PARTIDO:")
        print("-"*60)
        
        collection = "all_feb_games_fem" if fem_count > 0 else "all_feb_games_masc"
        games = scraper.db_client.get_all_games(collection)
        
        if games:
            sample = games[0]
            header = sample.get("HEADER", {})
            print(f"Competición: {header.get('competition_name', 'N/A')}")
            print(f"Temporada: {header.get('season', 'N/A')}")
            print(f"Grupo: {header.get('group', 'N/A')}")
            print(f"Fecha: {header.get('starttime', 'N/A')}")
            
            teams = header.get("TEAM", [])
            if len(teams) == 2:
                print(f"\nPartido: {teams[0].get('name', 'N/A')} {teams[0].get('pts', '?')} - "
                      f"{teams[1].get('pts', '?')} {teams[1].get('name', 'N/A')}")
    
    scraper.close()


def view_scraping_state():
    """Ver el estado actual del scraping incremental."""
    print("\n" + "="*60)
    print("ESTADO DEL SCRAPING INCREMENTAL")
    print("="*60 + "\n")
    
    from .database import MongoDBClient
    
    db = MongoDBClient()
    
    try:
        state_collection = db.get_collection("scraping_state")
        states = list(state_collection.find().sort("last_update", -1))
        
        if not states:
            print("ℹ️  No hay estados de scraping guardados.")
            print("El estado se crea automáticamente al hacer scraping incremental.")
            return
        
        print(f"{'Competición':<20} {'Temporada':<15} {'Grupo':<30} {'Partidos':<10} {'Última Act.'}")
        print("-" * 110)
        
        for state in states:
            comp = state.get('competition_name', 'N/A')[:19]
            season = state.get('season', 'N/A')[:14]
            group = state.get('group', 'N/A')[:29]
            total = state.get('total_matches', 0)
            update = state.get('last_update', 'N/A')[:19]
            
            print(f"{comp:<20} {season:<15} {group:<30} {total:<10} {update}")
        
        print(f"\nTotal grupos procesados: {len(states)}")
        
    finally:
        db.close()


def reset_scraping_state():
    """Resetear el estado del scraping incremental."""
    print("\n" + "="*60)
    print("RESETEAR ESTADO DEL SCRAPING")
    print("="*60 + "\n")
    
    from database import MongoDBClient
    
    db = MongoDBClient()
    
    try:
        state_collection = db.get_collection("scraping_state")
        
        print("Opciones:")
        print("1. Resetear una competición específica")
        print("2. Resetear TODO el estado")
        print("0. Cancelar")
        
        opcion = input("\nSelecciona opción: ").strip()
        
        if opcion == "1":
            comp_name = input("Nombre de la competición: ").strip()
            if comp_name:
                result = state_collection.delete_many({"competition_name": comp_name})
                print(f"\n✅ Estado reseteado para '{comp_name}': "
                      f"{result.deleted_count} documentos eliminados")
            else:
                print("❌ No se proporcionó nombre.")
        
        elif opcion == "2":
            confirm = input("\n⚠️  ¿Confirmas resetear TODO el estado? (s/n): ").strip().lower()
            if confirm in ['s', 'si', 'sí', 'y', 'yes']:
                result = state_collection.delete_many({})
                print(f"\n✅ Todo el estado reseteado: "
                      f"{result.deleted_count} documentos eliminados")
            else:
                print("❌ Operación cancelada")
        
        elif opcion == "0":
            print("Operación cancelada.")
        
        else:
            print("❌ Opción no válida")
        
    finally:
        db.close()


def custom_database():
    """Usar configuración personalizada de MongoDB."""
    print("\n" + "="*60)
    print("CONFIGURACIÓN PERSONALIZADA DE MONGODB")
    print("="*60 + "\n")
    
    print("Configuración por defecto:")
    print("  URI: mongodb://localhost:27017/")
    print("  Database: scouting_feb")
    print()
    
    uri = input("URI de MongoDB (Enter para usar por defecto): ").strip()
    db_name = input("Nombre de base de datos (Enter para usar por defecto): ").strip()
    
    if not uri:
        uri = "mongodb://localhost:27017/"
    if not db_name:
        db_name = "scouting_feb"
    
    print(f"\n📡 Conectando a: {uri}")
    print(f"📊 Base de datos: {db_name}")
    
    scraper = FEBScoutingScraper(
        mongodb_uri=uri,
        database_name=db_name
    )
    
    competitions = scraper.list_available_competitions()
    print(f"\n✅ Conectado exitosamente")
    print(f"Competiciones encontradas: {len(competitions)}")
    
    scraper.close()


def main():
    """Función principal con menú interactivo."""
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║            ScoutingFEB - Sistema de Scraping                 ║
╚══════════════════════════════════════════════════════════════╝

Selecciona una opción:

[SCRAPING]
  1. Listar competiciones disponibles
  2. Scraping interactivo (incremental)
  3. Scraping completo (re-scraping)
  4. Múltiples competiciones

[CONSULTAS]
  5. Consultar base de datos
  6. Ver estado del scraping incremental
  
[ADMINISTRACIÓN]
  7. Resetear estado del scraping
  8. Configuración personalizada de MongoDB

  0. Salir
""")
    
    opcion = input("Opción: ").strip()
    
    opciones = {
        "1": list_competitions,
        "2": scrape_interactive,
        "3": scrape_full_rescrape,
        "4": scrape_multiple_competitions,
        "5": query_database,
        "6": view_scraping_state,
        "7": reset_scraping_state,
        "8": custom_database
    }
    
    if opcion in opciones:
        try:
            opciones[opcion]()
        except KeyboardInterrupt:
            print("\n\n⚠️  Operación interrumpida por el usuario")
        except Exception as e:
            logger.error(f"❌ Error: {e}", exc_info=True)
    elif opcion == "0":
        print("\n¡Hasta luego! 👋")
    else:
        print("\n❌ Opción no válida")


if __name__ == "__main__":
    main()
