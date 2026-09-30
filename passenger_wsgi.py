"""WSGI entrypoint for cPanel/Passenger. No development server is started."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
interpreter = os.getenv("PASSENGER_PYTHON", str(ROOT / ".venv" / "bin" / "python"))
if not Path(interpreter).is_file():
    raise RuntimeError("Crie .venv/bin/python ou configure PASSENGER_PYTHON com o interpretador do ambiente virtual.")
if os.path.abspath(sys.executable) != os.path.abspath(interpreter):
    os.execl(interpreter, interpreter, *sys.argv)
sys.path.insert(0, str(ROOT))
os.environ.setdefault("APP_ENV", "production")
from app import create_app  # noqa: E402

application = create_app()
