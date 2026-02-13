"""
ScoutingFEB - Widgets de Administración de Datos
Componentes para scraping, ETL y gestión de información.
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QLabel, QProgressBar, QTextEdit, QDateEdit, QSpinBox,
    QLineEdit, QComboBox, QMessageBox, QFormLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QFont, QTextCursor

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class ScrapingThread(QThread):
    """Thread para scraping sin bloquear UI."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, season: str, competition: Optional[str] = None):
        super().__init__()
        self.season = season
        self.competition = competition
    
    def run(self):
        try:
            from scraper.feb_scraper import FEBScraper
            from database.mongodb_client import MongoDBClient
            
            self.progress.emit(f"🔄 Iniciando scraping para temporada {self.season}...")
            
            scraper = FEBScraper()
            mongo_client = MongoDBClient()
            
            # Obtener competiciones
            self.progress.emit("📋 Obteniendo lista de competiciones...")
            competitions = scraper.get_competitions(self.season)
            
            if self.competition:
                competitions = [c for c in competitions if self.competition.lower() in c['name'].lower()]
            
            self.progress.emit(f"✓ Encontradas {len(competitions)} competiciones")
            
            total_games = 0
            for i, comp in enumerate(competitions, 1):
                self.progress.emit(f"\n[{i}/{len(competitions)}] {comp['name']}...")
                
                # Obtener partidos
                games = scraper.get_games(comp['id'], self.season)
                self.progress.emit(f"  • {len(games)} partidos encontrados")
                
                # Guardar en MongoDB
                for game in games:
                    mongo_client.save_game(game)
                
                total_games += len(games)
                self.progress.emit(f"  ✓ {len(games)} partidos guardados en MongoDB")
            
            mongo_client.close()
            
            message = f"✅ Scraping completado exitosamente!\n\n"
            message += f"Total: {total_games} partidos scrapeados\n"
            message += f"Temporada: {self.season}\n"
            message += f"Competiciones: {len(competitions)}"
            
            self.finished.emit(True, message)
            
        except Exception as e:
            self.finished.emit(False, f"❌ Error durante scraping: {str(e)}")


class ETLThread(QThread):
    """Thread para ETL sin bloquear UI."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, full_rebuild: bool = False):
        super().__init__()
        self.full_rebuild = full_rebuild
    
    def run(self):
        try:
            from ml.etl_processor import ETLProcessor
            
            self.progress.emit("🔄 Iniciando proceso ETL...")
            
            etl = ETLProcessor()
            
            if self.full_rebuild:
                self.progress.emit("🗑️ Limpiando base de datos SQLite...")
                etl.clean_database()
            
            self.progress.emit("📥 Extrayendo datos de MongoDB...")
            raw_data = etl.extract_from_mongodb()
            self.progress.emit(f"✓ {len(raw_data)} registros extraídos")
            
            self.progress.emit("🔧 Transformando datos...")
            transformed = etl.transform_data(raw_data)
            self.progress.emit(f"✓ {len(transformed)} registros transformados")
            
            self.progress.emit("💾 Cargando a SQLite...")
            etl.load_to_sqlite(transformed)
            self.progress.emit("✓ Datos cargados en SQLite")
            
            self.progress.emit("🧮 Calculando métricas avanzadas...")
            etl.calculate_advanced_metrics()
            self.progress.emit("✓ Métricas calculadas")
            
            self.progress.emit("🌟 Calculando potencial de jugadoras...")
            etl.calculate_player_potential()
            self.progress.emit("✓ Potencial calculado")
            
            message = "✅ Proceso ETL completado exitosamente!\n\n"
            message += "Datos listos en SQLite para análisis."
            
            self.finished.emit(True, message)
            
        except Exception as e:
            self.finished.emit(False, f"❌ Error durante ETL: {str(e)}")


class DataAdminWidget(QWidget):
    """Widget principal para administración de datos."""
    
    def __init__(self):
        super().__init__()
        self.scraping_thread = None
        self.etl_thread = None
        self.init_ui()
    
    def init_ui(self):
        """Inicializar interfaz."""
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("⚙️ Administración de Datos")
        header.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        header.setStyleSheet("color: #FF9800; padding: 10px;")
        layout.addWidget(header)
        
        # Sub-tabs
        tabs = QTabWidget()
        
        # Tab 1: Scraping
        scraping_tab = self.create_scraping_tab()
        tabs.addTab(scraping_tab, "🌐 Scraping de Partidos")
        
        # Tab 2: ETL
        etl_tab = self.create_etl_tab()
        tabs.addTab(etl_tab, "🔄 Procesamiento ETL")
        
        # Tab 3: Datos biográficos
        bio_tab = self.create_biographical_tab()
        tabs.addTab(bio_tab, "👤 Datos Biográficos")
        
        layout.addWidget(tabs)
        self.setLayout(layout)
    
    def create_scraping_tab(self) -> QWidget:
        """Crear tab de scraping."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Descripción
        desc = QLabel(
            "Scrapear nuevos partidos de la FEB y almacenarlos en MongoDB.\n"
            "Esto actualiza los datos brutos antes del procesamiento ETL."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #aaa; padding: 10px;")
        layout.addWidget(desc)
        
        # Controles
        controls_group = QGroupBox("Configuración de Scraping")
        controls_layout = QFormLayout()
        
        # Temporada
        self.season_input = QLineEdit()
        self.season_input.setText("2025/2026")
        self.season_input.setPlaceholderText("YYYY/YYYY")
        controls_layout.addRow("Temporada:", self.season_input)
        
        # Competición (opcional)
        self.competition_filter = QLineEdit()
        self.competition_filter.setPlaceholderText("Ej: LF1, LF2 (opcional - todas si vacío)")
        controls_layout.addRow("Filtro Competición:", self.competition_filter)
        
        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)
        
        # Botones
        buttons_layout = QHBoxLayout()
        
        self.scrape_btn = QPushButton("▶️ Iniciar Scraping")
        self.scrape_btn.clicked.connect(self.start_scraping)
        self.scrape_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                padding: 10px 20px;
                font-size: 12pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #555;
            }
        """)
        buttons_layout.addWidget(self.scrape_btn)
        
        self.stop_scrape_btn = QPushButton("⏸️ Detener")
        self.stop_scrape_btn.setEnabled(False)
        self.stop_scrape_btn.clicked.connect(self.stop_scraping)
        buttons_layout.addWidget(self.stop_scrape_btn)
        
        layout.addLayout(buttons_layout)
        
        # Progress bar
        self.scrape_progress = QProgressBar()
        self.scrape_progress.setRange(0, 0)  # Indeterminate
        self.scrape_progress.setVisible(False)
        layout.addWidget(self.scrape_progress)
        
        # Log
        log_label = QLabel("📋 Log de Scraping:")
        log_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(log_label)
        
        self.scrape_log = QTextEdit()
        self.scrape_log.setReadOnly(True)
        self.scrape_log.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #00ff00;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
                border: 1px solid #444;
            }
        """)
        layout.addWidget(self.scrape_log)
        
        widget.setLayout(layout)
        return widget
    
    def create_etl_tab(self) -> QWidget:
        """Crear tab de ETL."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Descripción
        desc = QLabel(
            "Procesar datos de MongoDB y cargarlos en SQLite.\n"
            "Incluye cálculo de métricas avanzadas y potencial de jugadoras."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #aaa; padding: 10px;")
        layout.addWidget(desc)
        
        # Opciones
        options_group = QGroupBox("Opciones de Procesamiento")
        options_layout = QVBoxLayout()
        
        info_layout = QHBoxLayout()
        info_icon = QLabel("ℹ️")
        info_text = QLabel(
            "<b>Modo Incremental:</b> Procesa solo datos nuevos (rápido)<br>"
            "<b>Rebuild Completo:</b> Reconstruye toda la BD desde cero (lento, ~5-10 min)"
        )
        info_text.setWordWrap(True)
        info_layout.addWidget(info_icon)
        info_layout.addWidget(info_text)
        options_layout.addLayout(info_layout)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Botones
        buttons_layout = QHBoxLayout()
        
        self.etl_incremental_btn = QPushButton("▶️ Procesamiento Incremental")
        self.etl_incremental_btn.clicked.connect(lambda: self.start_etl(False))
        self.etl_incremental_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                padding: 10px 20px;
                font-size: 11pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #555;
            }
        """)
        buttons_layout.addWidget(self.etl_incremental_btn)
        
        self.etl_rebuild_btn = QPushButton("🔄 Rebuild Completo")
        self.etl_rebuild_btn.clicked.connect(lambda: self.start_etl(True))
        self.etl_rebuild_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                padding: 10px 20px;
                font-size: 11pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #E64A19;
            }
            QPushButton:disabled {
                background-color: #555;
            }
        """)
        buttons_layout.addWidget(self.etl_rebuild_btn)
        
        layout.addLayout(buttons_layout)
        
        # Progress bar
        self.etl_progress = QProgressBar()
        self.etl_progress.setRange(0, 0)
        self.etl_progress.setVisible(False)
        layout.addWidget(self.etl_progress)
        
        # Log
        log_label = QLabel("📋 Log de Procesamiento:")
        log_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(log_label)
        
        self.etl_log = QTextEdit()
        self.etl_log.setReadOnly(True)
        self.etl_log.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #00bfff;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
                border: 1px solid #444;
            }
        """)
        layout.addWidget(self.etl_log)
        
        widget.setLayout(layout)
        return widget
    
    def create_biographical_tab(self) -> QWidget:
        """Crear tab de datos biográficos."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Descripción
        desc = QLabel(
            "Añadir o actualizar información biográfica de jugadoras manualmente.\n"
            "Útil para corregir fechas de nacimiento, altura, nacionalidad, etc."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #aaa; padding: 10px;")
        layout.addWidget(desc)
        
        # Búsqueda de jugadora
        search_group = QGroupBox("Buscar Jugadora")
        search_layout = QHBoxLayout()
        
        self.player_search = QLineEdit()
        self.player_search.setPlaceholderText("Nombre de la jugadora...")
        self.player_search.textChanged.connect(self.search_players)
        search_layout.addWidget(self.player_search)
        
        search_btn = QPushButton("🔍 Buscar")
        search_btn.clicked.connect(self.search_players)
        search_layout.addWidget(search_btn)
        
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)
        
        # Resultados de búsqueda
        results_label = QLabel("Resultados:")
        results_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(results_label)
        
        self.player_results = QTableWidget()
        self.player_results.setColumnCount(6)
        self.player_results.setHorizontalHeaderLabels([
            "ID", "Nombre", "Año Nac.", "Altura (cm)", "Temporadas", "Editar"
        ])
        self.player_results.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.player_results.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.player_results)
        
        # Formulario de edición
        edit_group = QGroupBox("Editar Información Biográfica")
        edit_layout = QFormLayout()
        
        self.edit_player_name = QLineEdit()
        self.edit_player_name.setReadOnly(True)
        edit_layout.addRow("Jugadora:", self.edit_player_name)
        
        self.edit_birth_year = QSpinBox()
        self.edit_birth_year.setRange(1980, 2015)
        self.edit_birth_year.setValue(2000)
        edit_layout.addRow("Año de Nacimiento:", self.edit_birth_year)
        
        self.edit_height = QSpinBox()
        self.edit_height.setRange(140, 220)
        self.edit_height.setSuffix(" cm")
        edit_layout.addRow("Altura:", self.edit_height)
        
        self.edit_position = QComboBox()
        self.edit_position.addItems(["", "Base", "Escolta", "Alero", "Ala-Pívot", "Pívot"])
        edit_layout.addRow("Posición:", self.edit_position)
        
        self.edit_nationality = QLineEdit()
        self.edit_nationality.setPlaceholderText("ESP, USA, FRA, etc.")
        edit_layout.addRow("Nacionalidad:", self.edit_nationality)
        
        # Botones de edición
        edit_buttons = QHBoxLayout()
        
        save_btn = QPushButton("💾 Guardar Cambios")
        save_btn.clicked.connect(self.save_biographical_data)
        save_btn.setStyleSheet("background-color: #4CAF50;")
        edit_buttons.addWidget(save_btn)
        
        cancel_btn = QPushButton("❌ Cancelar")
        cancel_btn.clicked.connect(self.clear_edit_form)
        edit_buttons.addWidget(cancel_btn)
        
        edit_layout.addRow("", edit_buttons)
        
        edit_group.setLayout(edit_layout)
        edit_group.setEnabled(False)
        self.bio_edit_group = edit_group
        layout.addWidget(edit_group)
        
        # Botón de importación masiva
        import_btn = QPushButton("📁 Importar desde CSV")
        import_btn.clicked.connect(self.import_biographical_csv)
        import_btn.setStyleSheet("background-color: #9C27B0; margin-top: 10px;")
        layout.addWidget(import_btn)
        
        widget.setLayout(layout)
        return widget
    
    def start_scraping(self):
        """Iniciar proceso de scraping."""
        season = self.season_input.text().strip()
        if not season:
            QMessageBox.warning(self, "Error", "Por favor especifica una temporada")
            return
        
        competition = self.competition_filter.text().strip() or None
        
        # Confirmar
        msg = f"¿Iniciar scraping de partidos?\n\n"
        msg += f"Temporada: {season}\n"
        msg += f"Competición: {competition or 'Todas'}\n\n"
        msg += "Esto puede tardar varios minutos."
        
        reply = QMessageBox.question(
            self, "Confirmar Scraping", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Iniciar thread
        self.scraping_thread = ScrapingThread(season, competition)
        self.scraping_thread.progress.connect(self.update_scrape_log)
        self.scraping_thread.finished.connect(self.on_scraping_finished)
        
        self.scrape_btn.setEnabled(False)
        self.stop_scrape_btn.setEnabled(True)
        self.scrape_progress.setVisible(True)
        self.scrape_log.clear()
        
        self.scraping_thread.start()
    
    def stop_scraping(self):
        """Detener scraping."""
        if self.scraping_thread and self.scraping_thread.isRunning():
            self.scraping_thread.terminate()
            self.update_scrape_log("\n⚠️ Scraping detenido por el usuario")
            self.on_scraping_finished(False, "Scraping cancelado")
    
    def update_scrape_log(self, message: str):
        """Actualizar log de scraping."""
        self.scrape_log.append(message)
        self.scrape_log.moveCursor(QTextCursor.MoveOperation.End)
    
    def on_scraping_finished(self, success: bool, message: str):
        """Callback cuando termina scraping."""
        self.scrape_btn.setEnabled(True)
        self.stop_scrape_btn.setEnabled(False)
        self.scrape_progress.setVisible(False)
        
        self.update_scrape_log(f"\n{message}")
        
        if success:
            QMessageBox.information(self, "Scraping Completado", message)
        else:
            QMessageBox.warning(self, "Error en Scraping", message)
    
    def start_etl(self, full_rebuild: bool):
        """Iniciar proceso ETL."""
        mode = "Rebuild Completo" if full_rebuild else "Incremental"
        
        msg = f"¿Iniciar procesamiento ETL en modo {mode}?\n\n"
        if full_rebuild:
            msg += "⚠️ ADVERTENCIA: Esto borrará y reconstruirá toda la base de datos SQLite.\n"
            msg += "Tiempo estimado: 5-10 minutos.\n\n"
        else:
            msg += "Solo procesará datos nuevos desde MongoDB.\n"
            msg += "Tiempo estimado: 1-3 minutos.\n\n"
        msg += "¿Continuar?"
        
        reply = QMessageBox.question(
            self, f"Confirmar ETL {mode}", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Iniciar thread
        self.etl_thread = ETLThread(full_rebuild)
        self.etl_thread.progress.connect(self.update_etl_log)
        self.etl_thread.finished.connect(self.on_etl_finished)
        
        self.etl_incremental_btn.setEnabled(False)
        self.etl_rebuild_btn.setEnabled(False)
        self.etl_progress.setVisible(True)
        self.etl_log.clear()
        
        self.etl_thread.start()
    
    def update_etl_log(self, message: str):
        """Actualizar log de ETL."""
        self.etl_log.append(message)
        self.etl_log.moveCursor(QTextCursor.MoveOperation.End)
    
    def on_etl_finished(self, success: bool, message: str):
        """Callback cuando termina ETL."""
        self.etl_incremental_btn.setEnabled(True)
        self.etl_rebuild_btn.setEnabled(True)
        self.etl_progress.setVisible(False)
        
        self.update_etl_log(f"\n{message}")
        
        if success:
            QMessageBox.information(self, "ETL Completado", message)
        else:
            QMessageBox.warning(self, "Error en ETL", message)
    
    def search_players(self):
        """Buscar jugadoras."""
        search_text = self.player_search.text().strip()
        if len(search_text) < 3:
            return
        
        try:
            import sqlite3
            db_path = Path(__file__).parent.parent / "scouting_feb.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            query = """
            SELECT DISTINCT
                player_name,
                birth_year,
                COUNT(DISTINCT season) as seasons
            FROM player_profiles
            WHERE name_normalized LIKE ?
            GROUP BY player_name
            ORDER BY seasons DESC, player_name
            LIMIT 50
            """
            
            cursor.execute(query, (f"%{search_text}%",))
            results = cursor.fetchall()
            
            self.player_results.setRowCount(len(results))
            
            for i, (name, birth_year, seasons) in enumerate(results):
                self.player_results.setItem(i, 0, QTableWidgetItem(str(i+1)))
                self.player_results.setItem(i, 1, QTableWidgetItem(name))
                self.player_results.setItem(i, 2, QTableWidgetItem(str(birth_year) if birth_year else "N/D"))
                self.player_results.setItem(i, 3, QTableWidgetItem("N/D"))  # TODO: altura
                self.player_results.setItem(i, 4, QTableWidgetItem(str(seasons)))
                
                edit_btn = QPushButton("✏️")
                edit_btn.clicked.connect(lambda checked, n=name, by=birth_year: self.edit_player(n, by))
                self.player_results.setCellWidget(i, 5, edit_btn)
            
            conn.close()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al buscar jugadoras: {str(e)}")
    
    def edit_player(self, name: str, birth_year: Optional[int]):
        """Editar información de jugadora."""
        self.edit_player_name.setText(name)
        self.edit_birth_year.setValue(birth_year if birth_year else 2000)
        self.bio_edit_group.setEnabled(True)
    
    def save_biographical_data(self):
        """Guardar datos biográficos."""
        # TODO: Implementar guardado en BD
        QMessageBox.information(
            self,
            "Funcionalidad en desarrollo",
            "El guardado de datos biográficos se implementará próximamente."
        )
    
    def clear_edit_form(self):
        """Limpiar formulario de edición."""
        self.edit_player_name.clear()
        self.edit_birth_year.setValue(2000)
        self.edit_height.setValue(170)
        self.edit_position.setCurrentIndex(0)
        self.edit_nationality.clear()
        self.bio_edit_group.setEnabled(False)
    
    def import_biographical_csv(self):
        """Importar datos biográficos desde CSV."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        # TODO: Implementar importación CSV
        QMessageBox.information(
            self,
            "Funcionalidad en desarrollo",
            f"Importación desde CSV se implementará próximamente.\nArchivo seleccionado: {file_path}"
        )
