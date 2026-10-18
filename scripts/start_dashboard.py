#!/usr/bin/env python3
"""
Start the theTwoCubes dashboard.
Runs FastAPI backend (port 8000) + Vite frontend (port 5173) simultaneously.

Usage: python scripts/start_dashboard.py
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent


def main():
    print("\ntheTwoCubes Learning Dashboard\n")

    api_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.server:app", "--reload", "--port", "8000"],
        cwd=str(ROOT),
    )

    time.sleep(1.5)

    gui_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(ROOT / "gui"),
    )

    try:
        api_proc.wait()
    except KeyboardInterrupt:
        print("\n  Shutting down...")
        api_proc.terminate()
        gui_proc.terminate()


if __name__ == "__main__":
    main()
