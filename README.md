# Acciones UD - Backend

## Documentación del sistema

Consulta [el índice de documentación](documentation/README.md) y la
[guía completa del backend](.kiro/specs/guia-del-sistema/README.md): arquitectura,
tecnologías, funcionamiento e implementación de los siete módulos, decisiones,
API, operación, pruebas y límites conocidos.

Backend de Acciones UD construido con FastAPI, Supabase PostgreSQL y arquitectura
hexagonal dentro de un monolito modular.

El código actual incluye `identity`, `market_data`, `orders`, `wallet`,
`portfolio`, `brokers` y `admin`, con sus specs en `.kiro/specs/`.
La guía distingue implementación, decisiones vigentes y asuntos pendientes;
no declara el sistema certificado para producción.

## Inicio rápido

Requiere Python 3.12 y `uv`.

```powershell
uv sync
uv run uvicorn acciones_ud.main:app --reload
```

La API estará disponible en `http://localhost:8000` y su documentación en
`/docs`. El endpoint inicial es `GET /health`.

## Docker y Stripe CLI local

Requiere Docker con contenedores Linux, Compose >= 2.30 y Stripe CLI local.
Copia `.env.example` a `.env` y configura las credenciales sandbox.

1. Autentica Stripe CLI en la misma cuenta sandbox de la API:

   ```powershell
   stripe login
   ```

2. Inicia el listener en una terminal local y mantenla abierta:

   ```powershell
   stripe listen --forward-to http://localhost:8000/api/v1/webhooks/stripe --events checkout.session.completed,customer.subscription.created,customer.subscription.updated,customer.subscription.deleted,invoice.paid,invoice.payment_failed
   ```

   Configura el secreto de firma mostrado por el listener como
   `STRIPE_WEBHOOK_SECRET` en `.env`. Su salida contiene ese secreto: no la
   publiques. No cargues todas las variables de `.env` en Stripe CLI.

3. En otra terminal, inicia la API:

   ```powershell
   docker compose --env-file .env.example up -d --build --wait api
   ```

La API queda en `http://localhost:8000`, con `/docs` y `/health`. API y
migraciones reciben `.env` mediante `env_file.format: raw`, preservando `$`.
El archivo queda excluido de la imagen por `.dockerignore`. Stripe CLI corre
fuera de Docker y usa su propia autenticación local.

Tras cambiar `.env`, vuelve a ejecutar el comando de inicio para recrear la API.
Si cambias de cuenta o clave Stripe, verifica el secreto del listener. Si cambias
`API_PORT`, ajusta también el puerto de `--forward-to`.

Las migraciones se ejecutan explícitamente, solo cuando corresponda modificar
la base indicada por `MIGRATION_DATABASE_URL`:

```powershell
docker compose --env-file .env.example --profile tools run --rm migrate
```

Para detener la API: `docker compose --env-file .env.example down`.
Para detener el listener en primer plano: Ctrl+C. El listener recibe eventos
nuevos; puedes reenviar eventos anteriores con `stripe events resend EVENT_ID`
utilizando la misma cuenta sandbox, sin crear otro pago.

Los administradores de Docker pueden consultar el entorno del backend. No
publiques `docker inspect` ni la salida completa de `docker compose config`.
Para validar sin mostrar valores:
`docker compose --env-file .env.example --profile tools config --quiet`.

El diseño y la evidencia están en
[el spec Docker](.kiro/specs/identity-market-backend/docker.md).

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
