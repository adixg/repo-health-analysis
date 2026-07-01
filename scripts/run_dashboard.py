"""Launch the Streamlit dashboard from the project root."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
app_path = ROOT / "src" / "dashboard" / "app.py"

raise SystemExit(
    subprocess.call(
        [sys.executable, "-m", "streamlit", "run", str(app_path)],
        cwd=ROOT,
    )
)
