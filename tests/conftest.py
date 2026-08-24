"""Shared pytest configuration for ELN v2.

The project is installed editable (``uv sync``), so ``frontend.*`` and
``backend.*`` are importable from anywhere without sys.path manipulation.

Per docs/TEST_STRATEGIES.md:
- ``tests/`` is a flat (non-package) tree, so test file names must be
  unique across the whole tree.
- Shared fixtures (domain data, gateway fakes) will live here as the
  suites in Phase 1+ land.
"""
