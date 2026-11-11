# Acciones UD - Backend

Backend de Acciones UD construido con FastAPI, Supabase PostgreSQL y arquitectura
hexagonal dentro de un monolito modular.

El alcance activo comprende únicamente los módulos `identity` y `market_data`.
Las capacidades restantes del catálogo funcional y del SAD se agregarán cuando
cuenten con un spec aprobado.

## Inicio rápido

Requiere Python 3.12 y `uv`.

```powershell
uv sync
uv run uvicorn acciones_ud.main:app --reload
```

La API estará disponible en `http://localhost:8000` y su documentación en
`/docs`. El endpoint inicial es `GET /health`.

## Validación

```powershell
uv run ruff check .
uv run mypy src
uv run pytest
```

Consulta [`AGENTS.md`](./AGENTS.md), [`constitution.md`](./constitution.md) y
[`specs/`](./specs/) para las convenciones de arquitectura y SDD.

Las migraciones de Supabase PostgreSQL se gestionan con Alembic en
[`migrations/`](./migrations/).
Esta carpeta debe conservarse porque los cambios de tablas, índices y restricciones
deben quedar versionados y poder aplicarse de forma reproducible.

## Conexión a Supabase

Copia `.env.example` como `.env` y reemplaza los marcadores con los datos de
`Connect` en Supabase. Para este backend persistente se usa una conexión directa
cuando el despliegue dispone de IPv6 o el Session pooler cuando solo dispone de
IPv4. Alembic usa su propia URL, preferiblemente directa.

Las URL de este proyecto llevan el dialecto `postgresql+asyncpg` y
`ssl=require`. Si se copia una URL genérica de Supabase, hay que reemplazar
`postgresql://` y `sslmode=require` por esos valores compatibles con SQLAlchemy y
`asyncpg`. No se debe usar el Transaction pooler sin configurar además sus
restricciones de prepared statements y tamaño de pool.
