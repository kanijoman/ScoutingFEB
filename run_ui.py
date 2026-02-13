#!/usr/bin/env python3
"""
ScoutingFEB - Launcher Script
Punto de entrada para la interfaz gráfica.
"""

import sys
from pathlib import Path

# Asegurar que el directorio raíz está en el path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from ui.scouting_ui import main

if __name__ == "__main__":
    main()
