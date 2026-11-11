"""Dev helper: load .env, then run `alembic upgrade head`."""
import os
import pathlib
import sys

from alembic import command
from alembic.config import Config

root = pathlib.Path(__file__).parent
for line in (root / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

cfg = Config(str(root / "alembic.ini"))
target = sys.argv[1] if len(sys.argv) > 1 else "head"
command.upgrade(cfg, target)
print("ALEMBIC_DONE", target)
