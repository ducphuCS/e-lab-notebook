"""ELN v2 entrypoint — runs the app.

Launches the backend entrypoint, then the frontend (Streamlit) entrypoint.
Run with: `uv run python main.py`
"""
from pathlib import Path

from streamlit.web import cli as stcli

ROOT = Path(__file__).resolve().parent


def main() -> None:
    # 1. Backend entrypoint (placeholder — starts no services yet).
    from backend.app import main as run_backend

    run_backend()

    # 2. Frontend entrypoint — run the Streamlit page router.
    #    Blocks until the server is stopped.
    stcli.main_run(args=[str(ROOT / "frontend" / "app.py")], prog_name="streamlit")


if __name__ == "__main__":
    main()
