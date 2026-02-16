"""
ScoutingFEB - Interfaz Gráfica Principal
Aplicación de escritorio para análisis y evaluación de equipos de baloncesto femenino.
"""

import sys
import sqlite3
from pathlib import Path
from typing import Optional, List, Tuple

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QTableWidget, QTableWidgetItem,
    QTabWidget, QGroupBox, QProgressBar, QMessageBox, QLineEdit,
    QSplitter, QHeaderView, QStatusBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette, QPainter
from PyQt6.QtCharts import QChart, QChartView, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis

# Agregar src al path
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

# Default database path
DEFAULT_DB_PATH = PROJECT_ROOT / "scouting_feb.db"

from evaluate_team import TeamEvaluator, train_models_if_needed


class ModelTrainingThread(QThread):
    """Thread para entrenar modelos sin bloquear la UI."""
    finished = pyqtSignal(bool)
    progress = pyqtSignal(str)
    
    def __init__(self, db_path: str):
        super().__init__()
        self.db_path = db_path
    
    def run(self):
        try:
            self.progress.emit("Preparando datos de entrenamiento...")
            success = train_models_if_needed(self.db_path)
            self.finished.emit(success)
        except Exception as e:
            self.progress.emit(f"Error: {str(e)}")
            self.finished.emit(False)


class TeamEvaluationWidget(QWidget):
    """Widget principal para evaluación de equipos."""
    
    def __init__(self, db_path: str = None, show_errors: bool = True):
        super().__init__()
        self.db_path = db_path or str(DEFAULT_DB_PATH)
        self.evaluator: Optional[TeamEvaluator] = None
        self.current_roster = []
        self.show_errors = show_errors  # Flag para controlar si se muestran modales de error
        
        self.init_ui()
        self.load_evaluator()
    
    def init_ui(self):
        """Inicializar interfaz."""
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("🏀 Evaluación de Equipos")
        header.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        header.setStyleSheet("color: #2196F3; padding: 10px;")
        layout.addWidget(header)
        
        # Controles de selección
        controls_layout = QHBoxLayout()
        
        # Competición
        comp_group = QGroupBox("Competición")
        comp_layout = QVBoxLayout()
        self.competition_combo = QComboBox()
        self.competition_combo.currentTextChanged.connect(self.on_competition_changed)
        comp_layout.addWidget(self.competition_combo)
        comp_group.setLayout(comp_layout)
        controls_layout.addWidget(comp_group)
        
        # Equipo
        team_group = QGroupBox("Equipo")
        team_layout = QVBoxLayout()
        self.team_combo = QComboBox()
        self.team_combo.currentTextChanged.connect(self.on_team_changed)
        team_layout.addWidget(self.team_combo)
        team_group.setLayout(team_layout)
        controls_layout.addWidget(team_group)
        
        # Búsqueda rápida
        search_group = QGroupBox("Búsqueda rápida")
        search_layout = QVBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Nombre del equipo...")
        self.search_input.textChanged.connect(self.filter_teams)
        search_layout.addWidget(self.search_input)
        search_group.setLayout(search_layout)
        controls_layout.addWidget(search_group)
        
        layout.addLayout(controls_layout)
        
        # Splitter para tabla y gráfico
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Tabla de jugadoras
        table_widget = QWidget()
        table_layout = QVBoxLayout()
        
        table_header = QLabel("Plantilla y Proyecciones")
        table_header.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        table_layout.addWidget(table_header)
        
        self.roster_table = QTableWidget()
        self.roster_table.setColumnCount(9)
        self.roster_table.setHorizontalHeaderLabels([
            "Jugadora", "Edad", "PJ", "PTS", "EFF", "→PTS", "→EFF", "POT", "⚠"
        ])
        self.roster_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.roster_table.setAlternatingRowColors(True)
        self.roster_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table_layout.addWidget(self.roster_table)
        
        # Leyenda
        legend = QLabel(
            "→PTS/→EFF = Proyección 2026/2027 | "
            "POT: ELI(Elite) VER(Very High) HIG(High) MED(Medium) LOW(Low) | "
            "⚠ = Predicción conservadora"
        )
        legend.setStyleSheet("color: #666; font-size: 9pt; padding: 5px;")
        legend.setWordWrap(True)
        table_layout.addWidget(legend)
        
        table_widget.setLayout(table_layout)
        splitter.addWidget(table_widget)
        
        # Panel de estadísticas
        stats_widget = QWidget()
        stats_layout = QVBoxLayout()
        
        stats_header = QLabel("Resumen y Gráficos")
        stats_header.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        stats_layout.addWidget(stats_header)
        
        # Estadísticas generales
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 15px;
                font-size: 11pt;
            }
        """)
        self.stats_label.setWordWrap(True)
        stats_layout.addWidget(self.stats_label)
        
        # Gráfico de distribución de potencial
        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        stats_layout.addWidget(self.chart_view)
        
        stats_widget.setLayout(stats_layout)
        splitter.addWidget(stats_widget)
        
        splitter.setSizes([600, 400])
        layout.addWidget(splitter)
        
        self.setLayout(layout)
    
    def load_evaluator(self):
        """Cargar evaluador y datos."""
        try:
            # Verificar si modelos existen
            models_path = Path("models")
            if not (models_path / "points_predictor.joblib").exists():
                if self.show_errors:
                    reply = QMessageBox.question(
                        self,
                        "Modelos no encontrados",
                        "Los modelos de predicción no existen. ¿Deseas entrenarlos ahora?\n\n"
                        "Esto tomará 1-2 minutos.",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    
                    if reply == QMessageBox.StandardButton.Yes:
                        self.train_models()
                        return
                else:
                    # En modo test, simplemente retornar sin cargar
                    return
            
            self.evaluator = TeamEvaluator(self.db_path)
            self.load_competitions()
            
        except Exception as e:
            if self.show_errors:
                QMessageBox.critical(self, "Error", f"Error al cargar evaluador: {str(e)}")
            else:
                # En modo test, re-lanzar la excepción para que el test la capture
                raise
    
    def train_models(self):
        """Entrenar modelos en background."""
        progress = QProgressBar()
        progress.setRange(0, 0)  # Indeterminate
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Entrenando modelos")
        msg.setText("Entrenando modelos ML...\nEsto puede tardar 1-2 minutos.")
        msg.setStandardButtons(QMessageBox.StandardButton.NoButton)
        msg.layout().addWidget(progress)
        msg.show()
        
        self.training_thread = ModelTrainingThread(self.db_path)
        self.training_thread.finished.connect(lambda success: self.on_training_finished(success, msg))
        self.training_thread.start()
    
    def on_training_finished(self, success: bool, msg: QMessageBox):
        """Callback cuando termina el entrenamiento."""
        msg.close()
        
        if success:
            QMessageBox.information(
                self,
                "Éxito",
                "✓ Modelos entrenados exitosamente.\nCargando evaluador..."
            )
            self.evaluator = TeamEvaluator(self.db_path)
            self.load_competitions()
        else:
            QMessageBox.warning(
                self,
                "Error",
                "No se pudieron entrenar los modelos.\nLas proyecciones no estarán disponibles."
            )
    
    def load_competitions(self):
        """Cargar lista de competiciones."""
        if not self.evaluator:
            return
        
        competitions = self.evaluator.list_competitions()
        self.competition_combo.clear()
        self.competition_combo.addItem("-- Seleccionar competición --", None)
        
        for comp_id, comp_name, gender, level in competitions:
            display = f"{comp_name} ({gender})"
            self.competition_combo.addItem(display, comp_id)
    
    def on_competition_changed(self, text: str):
        """Callback cuando cambia la competición."""
        comp_id = self.competition_combo.currentData()
        if comp_id is None:
            self.team_combo.clear()
            return
        
        teams = self.evaluator.list_teams(competition_id=comp_id)
        self.team_combo.clear()
        self.team_combo.addItem("-- Seleccionar equipo --", None)
        
        for team_id, team_name, competition_name, player_count in teams:
            display = f"{team_name} ({player_count} jugadoras)"
            self.team_combo.addItem(display, team_id)
    
    def filter_teams(self, text: str):
        """Filtrar equipos por nombre."""
        if len(text) < 3:
            return
        
        # Búsqueda en todos los equipos
        # TODO: Implementar búsqueda global
        pass
    
    def on_team_changed(self, text: str):
        """Callback cuando cambia el equipo."""
        team_id = self.team_combo.currentData()
        if team_id is None:
            self.roster_table.setRowCount(0)
            return
        
        self.load_roster(team_id, text.split(" (")[0])
    
    def load_roster(self, team_id: int, team_name: str):
        """Cargar roster del equipo."""
        roster = self.evaluator.get_team_roster(team_id)
        self.current_roster = roster
        
        # Llenar tabla
        self.roster_table.setRowCount(len(roster))
        
        for i, player in enumerate(roster):
            # Nombre
            self.roster_table.setItem(i, 0, QTableWidgetItem(player['name']))
            
            # Edad
            age = player['age'] if player['age'] is not None else "N/D"
            self.roster_table.setItem(i, 1, QTableWidgetItem(str(age)))
            
            # PJ
            self.roster_table.setItem(i, 2, QTableWidgetItem(str(player['games_played'])))
            
            # PTS
            self.roster_table.setItem(i, 3, QTableWidgetItem(f"{player['avg_points']:.1f}"))
            
            # EFF
            self.roster_table.setItem(i, 4, QTableWidgetItem(f"{player['avg_efficiency']:.1f}"))
            
            # →PTS
            pred_pts = player.get('predicted_points')
            if pred_pts:
                self.roster_table.setItem(i, 5, QTableWidgetItem(f"{pred_pts:.1f}"))
            else:
                self.roster_table.setItem(i, 5, QTableWidgetItem("--"))
            
            # →EFF
            pred_eff = player.get('predicted_efficiency')
            if pred_eff:
                self.roster_table.setItem(i, 6, QTableWidgetItem(f"{pred_eff:.1f}"))
            else:
                self.roster_table.setItem(i, 6, QTableWidgetItem("--"))
            
            # POT
            pot_cat = player.get('potential_category', '')
            pot_str = self.format_potential(pot_cat)
            pot_item = QTableWidgetItem(pot_str)
            
            # Color según potencial
            if pot_cat and 'elite' in pot_cat.lower():
                pot_item.setBackground(QColor("#FFD700"))  # Gold
            elif pot_cat and 'very_high' in pot_cat.lower():
                pot_item.setBackground(QColor("#87CEEB"))  # Sky blue
            elif pot_cat and 'high' in pot_cat.lower():
                pot_item.setBackground(QColor("#90EE90"))  # Light green
            
            self.roster_table.setItem(i, 7, pot_item)
            
            # ⚠ (Alerta)
            is_high_pot = pot_cat and pot_cat.lower() in ['elite', 'very_high', 'high']
            predicts_decline = (pred_pts and pred_pts < player['avg_points']) or \
                             (pred_eff and pred_eff < player['avg_efficiency'])
            
            alert = "⚠" if (is_high_pot and predicts_decline) else ""
            self.roster_table.setItem(i, 8, QTableWidgetItem(alert))
        
        # Actualizar estadísticas
        self.update_stats(roster)
        
        # Actualizar gráfico
        self.update_chart(roster)
    
    def format_potential(self, pot_cat: str) -> str:
        """Formatear categoría de potencial."""
        if not pot_cat:
            return "---"
        
        pot_lower = pot_cat.lower()
        if 'elite' in pot_lower:
            return "ELI"
        elif 'very_high' in pot_lower:
            return "VER"
        elif 'high' in pot_lower:
            return "HIG"
        elif 'medium' in pot_lower:
            return "MED"
        elif 'low' in pot_lower:
            return "LOW"
        return "---"
    
    def update_stats(self, roster: List[dict]):
        """Actualizar panel de estadísticas."""
        if not roster:
            self.stats_label.setText("No hay datos disponibles")
            return
        
        # Calcular promedios
        total_pts = sum(p['avg_points'] for p in roster)
        total_eff = sum(p['avg_efficiency'] for p in roster)
        avg_pts = total_pts / len(roster)
        avg_eff = total_eff / len(roster)
        
        # Proyecciones
        pred_players = [p for p in roster if p.get('predicted_points')]
        if pred_players:
            avg_pred_pts = sum(p['predicted_points'] for p in pred_players) / len(pred_players)
            avg_pred_eff = sum(p['predicted_efficiency'] for p in pred_players) / len(pred_players)
            
            stats_text = f"""
<b>📊 ESTADÍSTICAS DEL EQUIPO</b><br><br>
<b>Plantilla:</b> {len(roster)} jugadoras<br><br>
<b>Temporada Actual (2025/2026):</b><br>
• Promedio puntos: {avg_pts:.1f} pts/jugadora<br>
• Promedio eficiencia: {avg_eff:.1f} OER/jugadora<br><br>
<b>Proyección 2026/2027:</b><br>
• Promedio puntos: <span style='color: #2196F3;'><b>{avg_pred_pts:.1f}</b></span> pts/jugadora ({avg_pred_pts - avg_pts:+.1f})<br>
• Promedio eficiencia: <span style='color: #2196F3;'><b>{avg_pred_eff:.1f}</b></span> OER/jugadora ({avg_pred_eff - avg_eff:+.1f})<br>
• Jugadoras con proyección: {len(pred_players)}/{len(roster)}
            """
        else:
            stats_text = f"""
<b>📊 ESTADÍSTICAS DEL EQUIPO</b><br><br>
<b>Plantilla:</b> {len(roster)} jugadoras<br><br>
<b>Temporada Actual (2025/2026):</b><br>
• Promedio puntos: {avg_pts:.1f} pts/jugadora<br>
• Promedio eficiencia: {avg_eff:.1f} OER/jugadora<br><br>
<b>⚠ No hay proyecciones disponibles</b><br>
Los modelos ML no están entrenados.
            """
        
        self.stats_label.setText(stats_text)
    
    def update_chart(self, roster: List[dict]):
        """Actualizar gráfico de distribución de potencial."""
        # Contar por categoría
        categories = {'ELI': 0, 'VER': 0, 'HIG': 0, 'MED': 0, 'LOW': 0}
        
        for player in roster:
            pot = self.format_potential(player.get('potential_category', ''))
            if pot in categories:
                categories[pot] += 1
        
        # Crear gráfico
        series = QBarSeries()
        bar_set = QBarSet("Jugadoras")
        
        for category, count in categories.items():
            bar_set.append(count)
        
        series.append(bar_set)
        
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("Distribución de Potencial")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        
        # Ejes
        axis_x = QBarCategoryAxis()
        axis_x.append(list(categories.keys()))
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)
        
        axis_y = QValueAxis()
        axis_y.setRange(0, max(categories.values()) + 2)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)
        
        chart.legend().setVisible(False)
        
        self.chart_view.setChart(chart)


class MainWindow(QMainWindow):
    """Ventana principal de la aplicación."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ScoutingFEB - Sistema de Análisis de Baloncesto Femenino")
        self.setGeometry(100, 100, 1400, 800)
        
        self.init_ui()
        self.apply_dark_theme()
    
    def init_ui(self):
        """Inicializar interfaz."""
        # Importar widget de administración
        from ui.data_admin import DataAdminWidget
        
        # Crear tabs
        tabs = QTabWidget()
        
        # Tab 1: Evaluación de equipos
        team_eval_widget = TeamEvaluationWidget()
        tabs.addTab(team_eval_widget, "🏀 Evaluación de Equipos")
        
        # Tab 2: Análisis de jugadoras (TODO)
        player_widget = QLabel("Análisis de jugadoras individuales\n\n(En desarrollo)")
        player_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tabs.addTab(player_widget, "👤 Análisis de Jugadoras")
        
        # Tab 3: Estadísticas generales (TODO)
        stats_widget = QLabel("Estadísticas y rankings generales\n\n(En desarrollo)")
        stats_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tabs.addTab(stats_widget, "📊 Estadísticas")
        
        # Tab 4: Administración de datos
        data_admin_widget = DataAdminWidget()
        tabs.addTab(data_admin_widget, "⚙️ Administración")
        
        self.setCentralWidget(tabs)
        
        # Status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Listo")
    
    def apply_dark_theme(self):
        """Aplicar tema oscuro moderno."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                font-family: "Segoe UI", Arial, sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #444;
                background-color: #2d2d2d;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #ffffff;
                padding: 10px 20px;
                margin-right: 2px;
                border: 1px solid #444;
            }
            QTabBar::tab:selected {
                background-color: #0d47a1;
                border-bottom: 3px solid #2196F3;
            }
            QTableWidget {
                background-color: #2d2d2d;
                alternate-background-color: #363636;
                gridline-color: #444;
                border: 1px solid #444;
            }
            QHeaderView::section {
                background-color: #0d47a1;
                color: white;
                padding: 8px;
                border: 1px solid #444;
                font-weight: bold;
            }
            QComboBox {
                background-color: #2d2d2d;
                border: 1px solid #444;
                padding: 5px;
                border-radius: 3px;
            }
            QComboBox:hover {
                border: 1px solid #2196F3;
            }
            QComboBox::drop-down {
                border: none;
            }
            QLineEdit {
                background-color: #2d2d2d;
                border: 1px solid #444;
                padding: 5px;
                border-radius: 3px;
            }
            QLineEdit:focus {
                border: 1px solid #2196F3;
            }
            QGroupBox {
                border: 1px solid #444;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                color: #2196F3;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                background-color: #0d47a1;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
            QPushButton:pressed {
                background-color: #0a3d91;
            }
            QStatusBar {
                background-color: #252525;
                color: #aaa;
            }
        """)


def main():
    """Punto de entrada de la aplicación."""
    app = QApplication(sys.argv)
    app.setApplicationName("ScoutingFEB")
    app.setOrganizationName("ScoutingFEB")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
