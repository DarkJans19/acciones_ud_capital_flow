# Stack y convenciones tecnicas

## Lenguaje y herramientas

- Python 3.12+, tipado explicito y estricto (mypy strict).
- Dependencias y comandos con `uv`.
- Lint y formato con `ruff`. Pruebas con `pytest` (y `hypothesis` para property-based).
- Validacion obligatoria antes de dar algo por terminado:
  - `uv run ruff check .`
  - `uv run mypy src`
  - `uv run pytest`

## Framework y persistencia

- API con FastAPI. Contratos de entrada/salida y configuracion con Pydantic (no sustituye entidades de dominio).
- Persistencia con SQLAlchemy 2.x async + `asyncpg` sobre Supabase PostgreSQL.
- Migraciones con Alembic en `migrations/versions/`. Aplicar es un paso manual del desarrollador
  (`uv run alembic upgrade head`), no un gate de CI ni una aprobacion. No usar ORM `create_all`.

## Conexion a Supabase

- `DATABASE_URL` (app) y `MIGRATION_DATABASE_URL` (Alembic). Con `asyncpg` el parametro es `ssl=require`, no `sslmode=require`.
- El host directo `db.<ref>.supabase.co` es solo IPv6. En redes IPv4 usar el Session pooler
  (`aws-<n>-<region>.pooler.supabase.com`, usuario `postgres.<ref>`).
- El transaction pooler no soporta prepared statements: asyncpg usa `statement_cache_size=0`.
- `Settings` carga el `.env` (el entorno del proceso tiene prioridad). El endpoint `/health` no requiere base de datos.

## Autenticacion y seguridad

- Auth propia (no Supabase Auth): contrasenas con Argon2id, JWT en cookies HttpOnly, segundo factor TOTP (RFC 6238).
- Cookies `access_token` y `refresh_token` con rotacion de refresh. En desarrollo sobre HTTP la cookie `secure=True` no se guarda; tenerlo en cuenta al probar.
- Secretos solo desde variables de entorno; nunca en logs, respuestas ni `Error_Body`.
- CSRF y validacion de Origin quedaron fuera por decision de equipo (D4): solo SameSite + allowlist de CORS.

## Errores e integraciones externas

- Errores explicitos traducidos en la frontera HTTP con `Error_Body` (`code`, `message`, `details`).
  `application/problem+json` no se adopto.
- Fallos de Alpaca: 502 `ALPACA_UNAVAILABLE`, 429 -> 503 `ALPACA_RATE_LIMITED`.
- Base de datos caida: 503 `DATABASE_UNAVAILABLE`.

## Entregable para el frontend

- El contrato OpenAPI es el entregable; mantener schemas de request/response y errores declarados por endpoint.