#!/usr/bin/env python3
"""
ScoutingFEB - Launcher Script
Punto de entrada para la interfaz gráfica.
"""

import sys
from pathlib import Path

# Asegurar que el directorio raíz está en el path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Verificar que existe la base de datos
db_path = project_root / "scouting_feb.db"
if not db_path.exists():
    print("="*70)
    print("❌ ERROR: Base de datos no encontrada")
    print("="*70)
    print(f"Expected database at: {db_path}")
    print(f"Current directory: {Path.cwd()}")
    print(f"\nPlease run from project root:")
    print(f"  cd {project_root}")
    print(f"  python run_ui.py")
    print("="*70)
    sys.exit(1)

from ui.scouting_ui import main

if __name__ == "__main__":
    main()
