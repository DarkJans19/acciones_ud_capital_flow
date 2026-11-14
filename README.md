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

## Ejecutar con Docker

Requiere Docker con contenedores Linux y Docker Compose 2.30 o superior.
La imagen usa Python 3.12 y `uv.lock`; incluye FastAPI/Uvicorn, SQLAlchemy,
asyncpg, Alembic y las dependencias de autenticación, HTTP, WebSocket y SMTP.
Supabase y Alpaca siguen siendo servicios externos; no necesitas instalar
Python ni uv en el host para levantar el contenedor.

1. Copia `.env.example` a `.env` y completa las conexiones de Supabase, las
   credenciales de Alpaca (Basic o `CLIENT_ID`, `CLIENT_SECRET` y
   `ALPACA_AUTH_URL` para OAuth), un `JWT_SECRET` de al menos 32 bytes y una
   clave Fernet válida en `TOTP_ENCRYPTION_KEY`. Mantén las demás variables
   requeridas del ejemplo. SMTP y Telegram son opcionales.
2. Construye la imagen:

   ```powershell
   docker compose --env-file .env.example build
   ```

3. Para una base nueva o con migraciones pendientes, completa también
   `INITIAL_ADMIN_*` y ejecuta explícitamente:

   ```powershell
   docker compose --env-file .env.example --profile tools run --rm migrate
   ```

   Este comando modifica la base indicada por `MIGRATION_DATABASE_URL`.
   Las migraciones no se ejecutan automáticamente al iniciar la API.
   Puedes generar el hash Argon2id del administrador sin Python local con
   `docker compose --env-file .env.example run --rm --no-deps api python -m acciones_ud.shared.tools.hash_password`.

4. Inicia la API:

   ```powershell
   docker compose --env-file .env.example up -d api
   docker compose --env-file .env.example ps
   docker compose --env-file .env.example logs -f api
   ```

API: `http://localhost:8000`, Swagger: `http://localhost:8000/docs`,
salud: `http://localhost:8000/health` y WebSocket:
`ws://localhost:8000/ws/v1/market-feed` (requiere autenticación y
`PRICE_STREAMING_ENABLED=true`). Puedes cambiar el puerto del host añadiendo
`API_PORT=8010` al entorno de PowerShell (`$env:API_PORT = "8010"`). Para detener:
`docker compose --env-file .env.example down`.
Después de cambiar código, ejecuta
`docker compose --env-file .env.example up -d --build api`.

El `.env` se inyecta al ejecutar; queda excluido de la construcción. El parámetro
`--env-file .env.example` evita que Compose use automáticamente el `.env` real
para interpolar el YAML; el servicio recibe igualmente el `.env` real mediante
`env_file` con formato `raw`, preservando los `$` del hash Argon2id. Escribe
los valores sin comillas envolventes. No publiques la salida de
`docker compose config`, porque puede mostrar secretos; para validar usa
`docker compose --env-file .env.example config --quiet`.

El contenedor corre sin privilegios y con un único worker, porque las alertas,
el observador de mercado y las suscripciones WebSocket viven en el proceso.
No escales réplicas sin coordinar previamente esos trabajos. El healthcheck
solo comprueba HTTP; no acredita conexión con la base ni con Alpaca.
Se necesita salida de red hacia Supabase, Alpaca y, si se habilitan, SMTP y
Telegram. En Docker sin IPv6 usa el Session pooler de Supabase en ambas URL.
Las cookies mantienen `Secure`: para un despliegue con frontend configura
HTTPS en un proxy que soporte WebSocket y ajusta `CORS_ALLOWED_ORIGINS` y
`COOKIE_DOMAIN`. El puerto se publica en loopback del host por defecto.

El diseño y la trazabilidad están en
[el complemento Docker del spec](.kiro/specs/identity-market-backend/docker.md).
La construcción sigue el patrón de
[uv para imágenes multietapa](https://docs.astral.sh/uv/guides/integration/docker/).

## Validación

```powershell
uv run ruff check .
uv run mypy src
uv run pytest
```

Consulta [`AGENTS.md`](./AGENTS.md), [`constitution.md`](./constitution.md) y
[`.kiro/specs/`](./.kiro/specs/) para las convenciones de arquitectura y SDD.
El spec activo de MOD-01 y MOD-02 es
[`.kiro/specs/identity-market-backend/`](./.kiro/specs/identity-market-backend/);
`specs/` quedó reemplazada y se conserva solo como referencia histórica.

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
