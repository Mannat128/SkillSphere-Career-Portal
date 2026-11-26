import os, sys
# Add the backend tests directory to the Python path so that imports work.
_backend_tests_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend', 'tests'))
if os.path.isdir(_backend_tests_dir):
    sys.path.append(_backend_tests_dir)
else:
    raise RuntimeError(f"Backend tests directory not found at {_backend_tests_dir}")

# Re-export helper functions used by other test modules.
from test_recruiter_assessment import (
    create_recruiter_and_login,
    create_candidate_and_login,
    approve_job_as_admin,
)

__all__ = [
    'create_recruiter_and_login',
    'create_candidate_and_login',
    'approve_job_as_admin',
]
