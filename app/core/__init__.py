import importlib, sys
_backend_core = importlib.import_module('backend.app.core')
# expose everything
for _name in dir(_backend_core):
    if not _name.startswith('__'):
        globals()[_name] = getattr(_backend_core, _name)
# ensure submodule import works
sys.modules[__name__] = _backend_core
