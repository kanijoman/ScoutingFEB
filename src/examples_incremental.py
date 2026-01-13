"""
Ejemplo de uso del sistema de scraping incremental.

Este script demuestra cómo usar el sistema incremental para añadir
solo los encuentros nuevos sin procesar toda la lista cada vez.
"""

from src.main import FEBScoutingScraper
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def ejemplo_scraping_incremental():
    """Ejemplo de scraping incremental básico."""
    
    scraper = FEBScoutingScraper()
    
    try:
        logger.info("=== Ejemplo 1: Scraping Incremental ===")
        logger.info("Solo procesará encuentros nuevos que no estén en la BD")
        
        # Scraping incremental (por defecto)
        stats = scraper.scrape_competition_by_name("LF2", incremental=True)
        
        logger.info(f"\n📊 Resultados:")
        logger.info(f"   - Encuentros encontrados: {stats['total_matches_found']}")
        logger.info(f"   - Encuentros nuevos procesados: {stats['total_matches_scraped']}")
        logger.info(f"   - Encuentros omitidos (ya en BD): {stats['total_matches_skipped']}")
        logger.info(f"   - Encuentros fallidos: {stats['total_matches_failed']}")
        
        return stats
        
    finally:
        scraper.close()


def ejemplo_scraping_completo():
    """Ejemplo de scraping completo (re-scraping)."""
    
    scraper = FEBScoutingScraper()
    
    try:
        logger.info("\n=== Ejemplo 2: Scraping Completo ===")
        logger.info("Procesará TODOS los encuentros, incluso los ya existentes")
        
        # Scraping completo - útil para actualizar datos o corregir errores
        stats = scraper.scrape_competition_by_name("LF2", incremental=False)
        
        logger.info(f"\n📊 Resultados:")
        logger.info(f"   - Encuentros encontrados: {stats['total_matches_found']}")
        logger.info(f"   - Encuentros procesados: {stats['total_matches_scraped']}")
        logger.info(f"   - Encuentros actualizados: {stats['total_matches_skipped']}")
        
        return stats
        
    finally:
        scraper.close()


def ejemplo_multiples_competiciones():
    """Ejemplo de scraping de múltiples competiciones."""
    
    scraper = FEBScoutingScraper()
    
    try:
        logger.info("\n=== Ejemplo 3: Múltiples Competiciones ===")
        
        competiciones = ["LF2", "LF", "LEB ORO", "ACB"]
        resultados = {}
        
        for comp in competiciones:
            logger.info(f"\nProcesando {comp}...")
            stats = scraper.scrape_competition_by_name(comp, incremental=True)
            resultados[comp] = stats
            
            logger.info(f"  ✅ {comp}: {stats['total_matches_scraped']} nuevos, "
                       f"{stats['total_matches_skipped']} omitidos")
        
        # Resumen final
        logger.info("\n" + "="*50)
        logger.info("RESUMEN FINAL:")
        total_nuevos = sum(r['total_matches_scraped'] for r in resultados.values())
        total_omitidos = sum(r['total_matches_skipped'] for r in resultados.values())
        logger.info(f"Total encuentros nuevos: {total_nuevos}")
        logger.info(f"Total encuentros omitidos: {total_omitidos}")
        
        return resultados
        
    finally:
        scraper.close()


def ver_estado_scraping():
    """Ver el estado actual del scraping."""
    
    from src.database import MongoDBClient
    
    db = MongoDBClient()
    
    try:
        logger.info("\n=== Estado del Scraping ===\n")
        
        state_collection = db.get_collection("scraping_state")
        states = list(state_collection.find().sort("last_update", -1))
        
        if not states:
            logger.info("No hay estados de scraping guardados.")
            return
        
        logger.info(f"{'Competición':<20} {'Temporada':<15} {'Grupo':<30} {'Encuentros':<12} {'Última Act.'}")
        logger.info("-" * 100)
        
        for state in states:
            comp = state.get('competition_name', 'N/A')
            season = state.get('season', 'N/A')
            group = state.get('group', 'N/A')
            total = state.get('total_matches', 0)
            update = state.get('last_update', 'N/A')[:19]  # Solo fecha y hora
            
            logger.info(f"{comp:<20} {season:<15} {group:<30} {total:<12} {update}")
        
        logger.info(f"\nTotal de grupos procesados: {len(states)}")
        
    finally:
        db.close()


def resetear_estado(competition_name=None):
    """
    Resetear el estado del scraping para forzar un re-scraping completo.
    
    Args:
        competition_name: Si se proporciona, solo resetea esa competición.
                         Si es None, resetea todo.
    """
    from src.database import MongoDBClient
    
    db = MongoDBClient()
    
    try:
        state_collection = db.get_collection("scraping_state")
        
        if competition_name:
            result = state_collection.delete_many({"competition_name": competition_name})
            logger.info(f"✅ Estado reseteado para {competition_name}: "
                       f"{result.deleted_count} documentos eliminados")
        else:
            confirm = input("⚠️  ¿Estás seguro de que quieres resetear TODO el estado? (sí/no): ")
            if confirm.lower() in ['sí', 'si', 's', 'yes', 'y']:
                result = state_collection.delete_many({})
                logger.info(f"✅ Todo el estado reseteado: "
                           f"{result.deleted_count} documentos eliminados")
            else:
                logger.info("❌ Operación cancelada")
        
    finally:
        db.close()


def main():
    """Función principal - ejecuta los ejemplos."""
    
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║         Sistema de Scraping Incremental - Ejemplos        ║
    ╚════════════════════════════════════════════════════════════╝
    
    Selecciona una opción:
    
    1. Scraping incremental (solo encuentros nuevos)
    2. Scraping completo (re-scraping total)
    3. Múltiples competiciones
    4. Ver estado del scraping
    5. Resetear estado de scraping
    0. Salir
    """)
    
    opcion = input("Opción: ").strip()
    
    if opcion == "1":
        ejemplo_scraping_incremental()
    elif opcion == "2":
        ejemplo_scraping_completo()
    elif opcion == "3":
        ejemplo_multiples_competiciones()
    elif opcion == "4":
        ver_estado_scraping()
    elif opcion == "5":
        comp = input("Nombre de competición (o Enter para resetear todo): ").strip()
        resetear_estado(comp if comp else None)
    elif opcion == "0":
        print("¡Hasta luego!")
    else:
        print("❌ Opción no válida")


if __name__ == "__main__":
    main()
