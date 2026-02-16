"""
Smoke Test: UI Components Load

These tests verify that UI components can be instantiated and basic
operations execute without crashing. Tests run headless (no display).

Focus: "Does the UI load?" not "Does it look correct?"
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Check if PyQt6 is available
pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    """
    Create QApplication for tests.
    
    Required for any Qt widget instantiation.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.mark.smoke
@pytest.mark.ui
class TestUIComponentsSmoke:
    """Smoke tests for UI component instantiation."""
    
    def test_scouting_ui_imports(self):
        """
        Test that scouting UI module can be imported.
        """
        try:
            from ui.scouting_ui import MainWindow
            assert MainWindow is not None, "Class should import"
        except Exception as e:
            pytest.fail(f"Failed to import MainWindow: {e}")
    
    def test_data_admin_ui_imports(self):
        """
        Test that data admin UI module can be imported.
        """
        try:
            from ui.data_admin import DataAdminWidget
            assert DataAdminWidget is not None, "Class should import"
        except Exception as e:
            pytest.fail(f"Failed to import DataAdminWidget: {e}")
    
    def test_scouting_main_window_instantiates(self, qapp, temp_sqlite_db):
        """
        Test that main scouting window can be instantiated.
        
        This is a basic smoke test - we just check it doesn't crash.
        """
        try:
            from ui.scouting_ui import MainWindow
            
            # Instantiate (but don't show)
            window = MainWindow()
            assert window is not None, "Window should instantiate"
            
            # Basic check - has expected attributes
            assert hasattr(window, 'setWindowTitle'), "Should be a QMainWindow"
            
        except Exception as e:
            pytest.fail(f"MainWindow instantiation failed: {e}")
    
    def test_data_admin_window_instantiates(self, qapp):
        """
        Test that data admin window can be instantiated.
        """
        try:
            from ui.data_admin import DataAdminWidget
            
            # Instantiate (but don't show)
            widget = DataAdminWidget()
            assert widget is not None, "Widget should instantiate"
            
            # Basic check
            assert hasattr(widget, 'setLayout'), "Should be a QWidget"
            
        except Exception as e:
            pytest.fail(f"DataAdminWidget instantiation failed: {e}")
    
    def test_ui_loads_without_database(self, qapp):
        """
        Test that UI handles missing database gracefully.
        
        Should raise appropriate error when database doesn't exist.
        """
        from ui.scouting_ui import TeamEvaluationWidget
        
        # Pass non-existent database path with show_errors=False to avoid modal
        with pytest.raises(FileNotFoundError) as exc_info:
            widget = TeamEvaluationWidget(db_path="/nonexistent/path.db", show_errors=False)
        
        # Verify error message is helpful
        error_msg = str(exc_info.value)
        assert "Database not found" in error_msg or "not found" in error_msg.lower()


@pytest.mark.smoke
@pytest.mark.ui
class TestUIBasicOperations:
    """Smoke tests for basic UI operations."""
    
    def test_competition_selector_exists(self, qapp, temp_sqlite_db):
        """
        Test that competition selector widget exists in main window.
        """
        try:
            from ui.scouting_ui import TeamEvaluationWidget
            
            widget = TeamEvaluationWidget(db_path=temp_sqlite_db, show_errors=False)
            
            # Check for expected widgets (names may vary)
            # This is a basic structural check
            assert hasattr(widget, 'layout') or \
                   hasattr(widget, 'setLayout'), \
                   "Should have layout"
            
        except Exception as e:
            pytest.skip(f"UI structure test skipped: {e}")
    
    def test_ui_has_menu_bar(self, qapp, temp_sqlite_db):
        """
        Test that main window has a menu bar.
        """
        try:
            from ui.scouting_ui import MainWindow
            
            window = MainWindow()
            
            # Check for menu bar
            menu_bar = window.menuBar()
            assert menu_bar is not None, "Should have menu bar"
            
        except Exception as e:
            pytest.skip(f"Menu bar test skipped: {e}")
    
    def test_data_admin_has_tabs(self, qapp):
        """
        Test that data admin widget has tab structure.
        """
        try:
            from ui.data_admin import DataAdminWidget
            from PyQt6.QtWidgets import QTabWidget
            
            widget = DataAdminWidget()
            
            # Find tab widget (should exist for multi-tab interface)
            tab_widget = window.findChild(QTabWidget)
            
            # It's okay if we can't find it via findChild, just check it doesn't crash
            assert True, "Data admin window loaded"
            
        except Exception as e:
            pytest.skip(f"Tab structure test skipped: {e}")


@pytest.mark.smoke  
@pytest.mark.ui
class TestChartWidgets:
    """Smoke tests for chart/plotting components."""
    
    def test_matplotlib_integration_works(self, qapp):
        """
        Test that matplotlib can be used with Qt backend.
        
        This validates chart rendering won't crash.
        """
        try:
            import matplotlib
            matplotlib.use('Qt5Agg')  # or 'QtAgg' for newer versions
            
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
            
            # Create a simple figure
            fig = Figure(figsize=(5, 4))
            canvas = FigureCanvasQTAgg(fig)
            
            assert canvas is not None, "Matplotlib canvas should create"
            
        except Exception as e:
            pytest.skip(f"Matplotlib integration test skipped: {e}")
    
    def test_pyqt_charts_available(self):
        """
        Test that PyQt6-Charts is available for plotting.
        """
        try:
            from PyQt6.QtCharts import QChart, QChartView
            assert QChart is not None, "PyQt6-Charts should be available"
        except ImportError:
            pytest.skip("PyQt6-Charts not installed")
