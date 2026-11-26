import os

# Path to the real backend application package (backend/app)
_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend', 'app'))
if not os.path.isdir(_backend_path):
    raise RuntimeError(f"Backend app directory not found at {_backend_path}")
# Extend this package's __path__ so that submodules (e.g., app.core) resolve to the backend package.
__path__.append(_backend_path)
