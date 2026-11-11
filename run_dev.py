"""Dev launcher: load .env into the process, then start uvicorn.

The app does not autoload .env, so this reads it first. For development only.
"""
import os
import pathlib

import uvicorn

# Clear derived vars that the .env may not set explicitly, so a stale shell
# value never shadows what legacy_connection_names() computes from DATABASE_CONNECTION.
for derived in ("DATABASE_URL", "MIGRATION_DATABASE_URL"):
    os.environ.pop(derived, None)

env_path = pathlib.Path(__file__).with_name(".env")
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()

if __name__ == "__main__":
    port = int(os.environ.get("DEV_PORT", "8010"))
    uvicorn.run("acciones_ud.main:app", host="127.0.0.1", port=port, reload=False)
