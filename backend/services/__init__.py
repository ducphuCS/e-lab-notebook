"""In-repo microservices (Phase 2+).

External microservices live outside this repository and are reached through
the gateway client (backend/gateway/). In-repo services land here, each as
its own module, written testable: pure functions, no ``streamlit`` imports,
no hidden global state (docs/TEST_STRATEGIES.md §4.1).
"""
