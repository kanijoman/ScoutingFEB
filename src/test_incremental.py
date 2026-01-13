"""
Script de prueba para validar el sistema de scraping incremental.
Este script ejecuta pruebas básicas sin realizar scraping real.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import MongoDBClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_mongodb_connection():
    """Prueba la conexión a MongoDB."""
    logger.info("Test 1: Conexión a MongoDB")
    try:
        db = MongoDBClient()
        # Intentar obtener una colección
        collection = db.get_collection("test_connection")
        logger.info("✓ Conexión exitosa a MongoDB")
        db.close()
        return True
    except Exception as e:
        logger.error(f"✗ Error de conexión: {e}")
        return False


def test_scraping_state_methods():
    """Prueba los métodos de scraping_state."""
    logger.info("\nTest 2: Métodos de estado de scraping")
    
    db = MongoDBClient()
    
    try:
        # Test 1: Actualizar estado
        logger.info("  - Actualizando estado de prueba...")
        success = db.update_scraping_state(
            competition_name="TEST_COMP",
            season="2024-2025",
            group="Test Group",
            collection_name="test_collection",
            last_match_code="99999",
            total_matches=10,
            timestamp="2026-01-12T10:00:00Z"
        )
        
        if not success:
            logger.error("  ✗ Error al actualizar estado")
            return False
        
        logger.info("  ✓ Estado actualizado")
        
        # Test 2: Recuperar estado
        logger.info("  - Recuperando estado...")
        state = db.get_scraping_state(
            competition_name="TEST_COMP",
            season="2024-2025",
            group="Test Group",
            collection_name="test_collection"
        )
        
        if not state:
            logger.error("  ✗ No se pudo recuperar el estado")
            return False
        
        logger.info(f"  ✓ Estado recuperado: {state['last_match_code']}")
        
        # Test 3: Validar datos
        assert state["competition_name"] == "TEST_COMP"
        assert state["season"] == "2024-2025"
        assert state["group"] == "Test Group"
        assert state["last_match_code"] == "99999"
        assert state["total_matches"] == 10
        
        logger.info("  ✓ Datos validados correctamente")
        
        # Limpieza
        logger.info("  - Limpiando datos de prueba...")
        state_collection = db.get_collection("scraping_state")
        state_collection.delete_many({"competition_name": "TEST_COMP"})
        logger.info("  ✓ Limpieza completada")
        
        return True
        
    except Exception as e:
        logger.error(f"  ✗ Error en test: {e}")
        return False
    finally:
        db.close()


def test_get_processed_matches():
    """Prueba el método get_all_processed_matches."""
    logger.info("\nTest 3: Obtener encuentros procesados")
    
    db = MongoDBClient()
    
    try:
        # Crear algunos documentos de prueba
        logger.info("  - Insertando encuentros de prueba...")
        collection = db.get_collection("test_matches")
        
        test_matches = [
            {
                "_id": 1001,
                "HEADER": {
                    "game_code": "1001",
                    "competition_name": "TEST_LEAGUE",
                    "season": "2024-2025",
                    "group": "Group A"
                }
            },
            {
                "_id": 1002,
                "HEADER": {
                    "game_code": "1002",
                    "competition_name": "TEST_LEAGUE",
                    "season": "2024-2025",
                    "group": "Group A"
                }
            },
            {
                "_id": 1003,
                "HEADER": {
                    "game_code": "1003",
                    "competition_name": "TEST_LEAGUE",
                    "season": "2024-2025",
                    "group": "Group B"  # Diferente grupo
                }
            }
        ]
        
        collection.insert_many(test_matches)
        logger.info("  ✓ Encuentros insertados")
        
        # Recuperar encuentros de Group A
        logger.info("  - Recuperando encuentros de Group A...")
        matches = db.get_all_processed_matches(
            competition_name="TEST_LEAGUE",
            season="2024-2025",
            group="Group A",
            collection_name="test_matches"
        )
        
        logger.info(f"  ✓ Encuentros recuperados: {len(matches)}")
        
        # Validar
        assert len(matches) == 2, f"Esperados 2 encuentros, encontrados {len(matches)}"
        assert "1001" in matches, "Falta encuentro 1001"
        assert "1002" in matches, "Falta encuentro 1002"
        assert "1003" not in matches, "No debería incluir encuentro 1003 (diferente grupo)"
        
        logger.info("  ✓ Filtrado por grupo correcto")
        
        # Limpieza
        logger.info("  - Limpiando datos de prueba...")
        collection.drop()
        logger.info("  ✓ Limpieza completada")
        
        return True
        
    except Exception as e:
        logger.error(f"  ✗ Error en test: {e}")
        return False
    finally:
        db.close()


def test_incremental_logic_simulation():
    """Simula la lógica incremental sin scraping real."""
    logger.info("\nTest 4: Simulación de lógica incremental")
    
    try:
        # Simular lista de encuentros de la web
        web_matches = ["1001", "1002", "1003", "1004", "1005"]
        logger.info(f"  - Encuentros en la web: {len(web_matches)}")
        
        # Simular encuentros ya procesados
        processed_matches = {"1001", "1002", "1003"}
        logger.info(f"  - Encuentros procesados: {len(processed_matches)}")
        
        # Filtrar nuevos
        new_matches = [m for m in web_matches if m not in processed_matches]
        logger.info(f"  ✓ Encuentros nuevos: {len(new_matches)} - {new_matches}")
        
        # Validar
        assert len(new_matches) == 2
        assert new_matches == ["1004", "1005"]
        
        logger.info("  ✓ Lógica de filtrado correcta")
        
        # Simular caso sin encuentros nuevos
        all_processed_matches = {"1001", "1002", "1003", "1004", "1005"}
        new_matches_2 = [m for m in web_matches if m not in all_processed_matches]
        
        logger.info(f"  - Todos procesados: {len(new_matches_2)} nuevos")
        assert len(new_matches_2) == 0
        logger.info("  ✓ Caso sin encuentros nuevos - correcto")
        
        return True
        
    except Exception as e:
        logger.error(f"  ✗ Error en test: {e}")
        return False


def run_all_tests():
    """Ejecuta todos los tests."""
    logger.info("="*60)
    logger.info("TESTS DEL SISTEMA DE SCRAPING INCREMENTAL")
    logger.info("="*60)
    
    tests = [
        ("Conexión MongoDB", test_mongodb_connection),
        ("Métodos de estado", test_scraping_state_methods),
        ("Obtener procesados", test_get_processed_matches),
        ("Lógica incremental", test_incremental_logic_simulation)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Error en {test_name}: {e}")
            results.append((test_name, False))
    
    # Resumen
    logger.info("\n" + "="*60)
    logger.info("RESUMEN DE TESTS")
    logger.info("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status} - {test_name}")
    
    logger.info("-"*60)
    logger.info(f"Total: {passed}/{total} tests pasados")
    
    if passed == total:
        logger.info("✓ ¡Todos los tests pasaron exitosamente!")
        return True
    else:
        logger.error(f"✗ {total - passed} test(s) fallaron")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
