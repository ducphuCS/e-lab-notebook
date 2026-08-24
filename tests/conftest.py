"""Shared pytest configuration for ELN v2.

Puts the repository root on ``sys.path`` so tests can import ``backend.*``
and ``frontend.*`` modules without any packaging or root-config changes.

Per docs/TEST_STRATEGIES.md:
- ``tests/`` is a flat (non-package) tree, so test file names must be
  unique across the whole tree.
- Shared fixtures (domain data, gateway fakes) will live here as the
  suites in Phase 1+ land.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
