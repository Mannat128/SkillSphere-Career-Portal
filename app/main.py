# Shim to expose the FastAPI app instance from the backend package

from backend.app.main import app  # re-export the FastAPI instance
