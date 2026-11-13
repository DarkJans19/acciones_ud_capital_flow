# Base de datos desechable para los tests de DB

Los tests marcados con `db` (migraciones, constraints, concurrencia y la API
contra Postgres real) quedan `skipped` mientras `TEST_DATABASE_URL` no exista.
Esta carpeta levanta un Postgres 16 desechable para correrlos.

> **Advertencia:** el fixture `migrated_database` hace `alembic upgrade head` y,
> al terminar, `alembic downgrade base`. **Borra el esquema**. Nunca apuntes
> `TEST_DATABASE_URL` a una base compartida o con datos reales.

## Con Dockerfile

```powershell
docker build -t acciones-ud-test-db tests/db
docker run --rm -d --name acciones-ud-test-db -e POSTGRES_PASSWORD=postgres -p 55432:5432 acciones-ud-test-db

# Esperar a que esté sano
docker inspect --format '{{.State.Health.Status}}' acciones-ud-test-db
```

## Con docker compose

```powershell
docker compose -f tests/db/docker-compose.yml up -d --build
docker compose -f tests/db/docker-compose.yml ps
```

## Correr los tests

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:55432/postgres"
uv run pytest -q
```

Con esa variable, los 18 tests marcados `db` dejan de saltarse y se ejecutan
contra el contenedor. `APP_ENV=test` lo fija el propio fixture, así que la URL
local no necesita `ssl=require`.

## Limpiar

```powershell
docker rm -f acciones-ud-test-db
# o: docker compose -f tests/db/docker-compose.yml down
```

El contenedor no monta volúmenes: al borrarlo, no queda estado.
