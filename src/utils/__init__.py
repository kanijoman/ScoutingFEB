"""Utils package for shared utilities."""

# Import key utilities from the root utils.py module
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import from utils.py (not this package)
import importlib.util
spec = importlib.util.spec_from_file_location("utils_module", 
                                                os.path.join(os.path.dirname(__file__), "..", "utils.py"))
utils_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(utils_module)

# Export the functions
normalize_year = utils_module.normalize_year
get_form_field_name = utils_module.get_form_field_name
get_event_target = utils_module.get_event_target

__all__ = ['normalize_year', 'get_form_field_name', 'get_event_target']
