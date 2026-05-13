"""Entrypoint wrapper. Run: poetry run python main.py (or `python main.py` after install)."""
from app.__main__ import run

if __name__ == "__main__":
    run()
