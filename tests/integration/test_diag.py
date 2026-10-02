"""Temporary diagnostic — prints what pytest sees for custom_components, then
imports the integration with a real (unswallowed) traceback. Remove once the
discovery issue is resolved. Run: python -m pytest tests/integration/test_diag.py -s
"""


def test_diag_custom_components_resolution():
    import sys
    import custom_components
    print("\n==== DIAG ====")
    print("sys.path[:6]:", sys.path[:6])
    print("custom_components.__path__:", list(getattr(custom_components, "__path__", [])))
    print("custom_components.__file__:", getattr(custom_components, "__file__", None))
    import importlib
    importlib.import_module("custom_components.jarvis")   # real traceback if this fails
    print("JARVIS IMPORT: OK")
    print("==== /DIAG ====")
