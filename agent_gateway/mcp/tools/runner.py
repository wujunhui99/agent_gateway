"""Simple runner that executes a script located inside /app/scripts."""

import runpy
import sys
from pathlib import Path

SCRIPTS_DIR = Path("/app/scripts")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python -m tools.runner <script> [args...]")

    script = sys.argv[1]
    args = sys.argv[2:]
    script_path = (SCRIPTS_DIR / script).resolve()
    try:
        script_path.relative_to(SCRIPTS_DIR)
    except ValueError:
        raise SystemExit("Invalid script path outside scripts directory")

    if not script_path.is_file():
        raise SystemExit(f"Script {script} not found in {SCRIPTS_DIR}")

    sys.argv = [script] + args
    runpy.run_path(str(script_path), run_name="__main__")


if __name__ == "__main__":
    main()
