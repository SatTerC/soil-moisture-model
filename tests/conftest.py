"""Pytest configuration and fixtures."""

import sys
from pathlib import Path

# Make tests/regression_adapter.py importable from the test modules.
sys.path.insert(0, str(Path(__file__).parent))
