"""Gateway client — the ONLY code allowed to talk to backend services over
HTTP (docs/TEST_STRATEGIES.md §3).

Its four responsibilities (landing in Phase 2):

1. route to the right service (config, not hardcoded URLs)
2. build + validate requests before they leave (fail fast)
3. validate responses on the way back (contract enforcement)
4. map every service failure to one uniform error shape

Frontend pages never do HTTP directly; they call gateway functions only
(owner-confirmed hard rule, 2026-08-24).
"""
