# 10. Configuración, operación, pruebas y límites

[Índice](README.md) · [Anterior](09-estrategias-datos.md) · [Siguiente](11-api-flujos.md)

## 10.1 Configuración y secretos

`Settings` en `src/acciones_ud/config/settings.py` lee primero variables del
proceso y después `.env` local. Los campos desconocidos se ignoran y los errores
ocultan valores. La configuración se cachea con `get_settings`.

`require_api_settings` valida antes de abrir clientes e iniciar jobs. Informa
nombres de variables faltantes o inválidas, no secretos. Tener valores por
defecto en algunos campos no elimina los obligatorios de otros módulos:
la aplicación completa también exige configuración Stripe de prueba.

### Conexión y autenticación

| Variable/grupo | Uso y precaución |
| --- | --- |
| `DATABASE_URL` | URL de aplicación `postgresql+asyncpg://...`; TLS con `ssl=require` fuera de test |
| `MIGRATION_DATABASE_URL` | URL separada para DDL/Alembic; no dar privilegios de migración por conveniencia a toda petición |
| `DATABASE_CONNECTION` | Compatibilidad legacy: normaliza dialecto y TLS si no existe DATABASE_URL |
| `JWT_SECRET` | Al menos 32 bytes; secreto de firma HS256 |
| `ACCESS_TOKEN_TTL_SECONDS` | Obligatorio, 1..900 s |
| `REFRESH_TOKEN_TTL_SECONDS` | Obligatorio, 1..604 800 s |
| `TOTP_ENCRYPTION_KEY` | Clave Fernet válida; perderla impide descifrar secretos existentes |
| `CORS_ALLOWED_ORIGINS` | Orígenes exactos separados por coma; no permite `*` |
| `COOKIE_SAMESITE` | lax por defecto; solo lax/strict |
| `COOKIE_DOMAIN` | Opcional; cambia ámbito de cookies, no permisos de usuario |
| `APP_ENV` | development por defecto; test permite URL PostgreSQL local sin TLS |
| `LOG_LEVEL` | INFO por defecto; uno de los niveles admitidos |

En Supabase se recomienda conexión directa si hay IPv6 o Session pooler para
entornos IPv4. No copiar `sslmode=require` a asyncpg: aquí se usa `ssl=require`.
El engine usa `pool_pre_ping`, espera de pool 10 s, command timeout 10 s,
statement cache desactivada y nombres preparados únicos. Eso no sustituye validar
la compatibilidad y privilegios del pool elegido.

### Alpaca y datos de mercado

| Variable/grupo | Uso |
| --- | --- |
| `ALPACA_BROKER_API_KEY`, `ALPACA_BROKER_API_SECRET` | Basic auth REST cuando no se usa OAuth; también credenciales del stream |
| `CLIENT_ID`, `CLIENT_SECRET`, `ALPACA_AUTH_URL` | Variante REST client credentials; no se confunde con las claves Basic |
| `ALPACA_BROKER_BASE_URL` | Cuentas, trading y fondos |
| `ALPACA_DATA_BASE_URL` | Snapshots, quotes y velas |
| `ALPACA_STREAM_BASE_URL` | Host WebSocket; debe corresponder al entorno/feed |
| `ALPACA_DATA_FEED` | iex, sip o delayed_sip |
| `ALPACA_BASE_URL` | Compatibilidad legacy de URL Broker |
| `PRICE_STALENESS_THRESHOLD_SECONDS` | 900 s por defecto |
| `CATALOG_MAX_AGE_HOURS` | 24 h |
| `DASHBOARD_DEFAULT_SYMBOLS` | Lista de fallback de diez símbolos en configuración inicial |

OAuth cachea bearer hasta poco antes de expirar y serializa renovación con lock
async. Un 401 invalida el token cacheado para la siguiente llamada; no significa
que el cliente repita automáticamente una operación financiera.

### Stripe y canales

| Variable/grupo | Uso |
| --- | --- |
| `STRIPE_SECRET_KEY` | Obligatoria, solo prefijo `sk_test_` |
| `STRIPE_WEBHOOK_SECRET` | Firma del endpoint/listener, prefijo `whsec_` |
| `STRIPE_PRICE_MONTHLY_ID`, `STRIPE_PRICE_ANNUAL_ID` | IDs Price de la misma cuenta sandbox |
| `STRIPE_CHECKOUT_SUCCESS_URL`, `STRIPE_CHECKOUT_CANCEL_URL` | Retornos frontend HTTP(S), localhost por defecto |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Activa envío real de correo si se configura host |
| `TELEGRAM_BOT_TOKEN` | Activa Bot API; cada usuario necesita destino asociado |

SMTP usa 587 por defecto cuando no se da puerto al construir sender.
Sin credenciales/configuración se usan senders de log; SMS sigue simulado.
No publicar salida de Stripe CLI que incluya su secreto de firma.

### Políticas funcionales

| Variable | Valor por defecto y finalidad |
| --- | --- |
| `WALLET_MAX_TRANSFER_AMOUNT` | 50000.00, máximo de transferencia USD |
| `ORDER_CREATION_DEADLINE_SECONDS` | 5; 0 desactiva solo deadline exterior para diagnóstico |
| `ORDER_ALPACA_SUBMIT_TIMEOUT_SECONDS` | 4, validado entre 1 y 4 |
| `ORDER_REFERENCE_COMMISSION_RATE` | 0.02 como fracción de referencia, no porcentaje 2 |
| `ORDER_REAUTH_PRICE_DEVIATION_PCT` | 1.00 como porcentaje |
| `ORDER_REAUTH_WINDOW_MINUTES` | 30 |
| `ORDER_LOCAL_MAX_AGE_DAYS` | 5 |
| `PORTFOLIO_RISK_WINDOW_DAYS` | 90 |
| `BROKER_LINK_REQUEST_TTL_DAYS` | 7 |
| `PROPOSAL_TTL_HOURS` | 72 |
| `BROKER_LINK_CONSENT_VERSION`, `BROKER_TRADING_CONSENT_VERSION` | v1; versionan consentimiento guardado |
| `ADMIN_KPI_CACHE_TTL_SECONDS` | 300 |
| `ADMIN_ATYPICAL_ABSOLUTE_USD`, `ADMIN_ATYPICAL_MULTIPLIER` | 10000.00 y 3 |
| `ADMIN_ATYPICAL_WINDOW_DAYS`, `ADMIN_ATYPICAL_MIN_HISTORY` | 90 y 5 |
| `ADMIN_ORDER_FREQUENCY_COUNT`, `ADMIN_ORDER_FREQUENCY_SECONDS` | 20 y 300 |
| `ADMIN_CANCELLATION_COUNT`, `ADMIN_CANCELLATION_SECONDS` | 10 y 300 |
| `ADMIN_REJECTION_COUNT`, `ADMIN_REJECTION_SECONDS` | 5 y 3600 |

La tarifa oficial se administra mediante versiones en base de datos; cambiar la
tasa de referencia del entorno no reescribe términos de órdenes existentes.
Para rangos exactos de cada configuración, consultar `require_api_settings`:
esta tabla no sustituye sus validaciones.

## 10.2 Jobs: operación diferida dentro del proceso

| Trabajo | Flag y defecto | Intervalo por defecto |
| --- | --- | --- |
| Refresh KYC | `KYC_STATUS_REFRESH_ENABLED=false` | `KYC_STATUS_REFRESH_INTERVAL_SECONDS=900` |
| Alertas | `ALERT_ENGINE_ENABLED=true` | `ALERT_EVALUATION_INTERVAL_SECONDS=60` |
| Reloj apertura/cierre | Mismo flag de alertas | `MARKET_CLOCK_CHECK_INTERVAL_SECONDS=60` |
| Reconciliación de fondos | `WALLET_RECONCILER_ENABLED=true` | `WALLET_RECONCILE_INTERVAL_SECONDS=60` |
| Reconciliación de órdenes | `ORDERS_JOBS_ENABLED=true` | `ORDER_RECONCILE_INTERVAL_SECONDS=15` |
| Scheduler de órdenes | Mismo flag orders | `ORDER_SCHEDULER_INTERVAL_SECONDS=30` |
| Reportes | `PORTFOLIO_JOBS_ENABLED=true` | `PORTFOLIO_REPORT_INTERVAL_SECONDS=900` |
| Expiración/reconciliación brokers | `BROKERS_JOBS_ENABLED=true` | `BROKERS_EXPIRY_INTERVAL_SECONDS=300` |
| Despacho de horarios | `ADMIN_JOBS_ENABLED=true` | `ADMIN_SCHEDULE_DISPATCH_INTERVAL_SECONDS=30` |
| Stream de precios | `PRICE_STREAMING_ENABLED=false` | Conexión continua, no intervalo de polling |

Los jobs periódicos generales hacen trabajo y después esperan el intervalo:
el periodo efectivo también incluye tiempo de ejecución. El job KYC tiene su
propio ciclo, espera antes de la primera ejecución y detención cooperativa.

Apagar jobs permite pruebas/diagnóstico sin efectos laterales, pero **no es
equivalente a operación completa**: no avanzan estados externos, expiraciones
persistidas o reportes automáticos mientras estén deshabilitados.

La imagen usa un worker Uvicorn. Añadir `--workers N` duplica jobs y conexiones
upstream y fragmenta registros WebSocket. Algunos invariantes SQL resisten
varios procesos, pero no todos los avisos y estados locales están coordinados.
Para escalar hay que diseñar propiedad de jobs y distribución del stream.

## 10.3 Inicio local

Requisitos: Python 3.12+, `uv`, credenciales exclusivamente de prueba y acceso a
PostgreSQL configurado. Copiar `.env.example` a `.env` y sustituir marcadores
fuera de Git.

```bash
uv sync --locked
uv run uvicorn acciones_ud.main:app --reload
```

- API: `http://localhost:8000`.
- Salud: `/health`.
- Swagger: `/docs`.
- Contrato: `/openapi.json`.
- ReDoc: `/redoc`.

Las cookies son Secure incluso en desarrollo. Usar localhost con comportamiento
compatible del navegador o HTTPS local; otros hosts HTTP pueden no servir para
autenticación por cookies.

Para frontend: servir same-site, configurar CORS y usar proxy que conserve
`/api/v1/...`, porque la ruta del refresh es la que observa el navegador.
`fetch` requiere `credentials: "include"`.

`run_dev.py` y `run_migrations.py` son helpers con parsers simples de `.env`, no
la fuente normativa de configuración. El comentario de run_dev que dice que la
app no carga `.env` está desactualizado: Settings sí lo carga. Además, run_dev
manipula variables derivadas; se prefieren los comandos estándar de arriba.

## 10.4 Migraciones y administrador inicial

Aplicar migraciones es una acción explícita sobre la URL indicada:

```bash
uv run alembic current
uv run alembic heads
uv run alembic upgrade head
```

Antes de upgrade comprobar entorno, privilegios, respaldo y revisiones
pendientes. No ejecutar downgrade sobre una base compartida solo para “probar”.
Arrancar la API no aplica automáticamente migraciones.

La revisión 0002 aprovisiona administrador con `INITIAL_ADMIN_EMAIL`,
`INITIAL_ADMIN_PASSWORD_HASH`, `INITIAL_ADMIN_FIRST_NAMES`,
`INITIAL_ADMIN_LAST_NAMES`, `INITIAL_ADMIN_PHONE` y `INITIAL_ADMIN_COUNTRY`.
El hash se prepara con la utilidad:

```bash
uv run python -m acciones_ud.shared.tools.hash_password
```

Consultar la revisión para la semántica exacta ante datos ya existentes. No
modificar a mano roles en producción como sustituto de los casos de uso
administrativos y su auditoría.

## 10.5 Docker y Stripe CLI

La imagen tiene build multietapa, dependencias resueltas con lock, paquete
instalado no editable y runtime Python 3.12 sin herramientas dev. Corre como UID
10001 y `.env` se excluye de la imagen.

Compose expone API solo en `127.0.0.1`, retira capabilities y configura
`no-new-privileges`. Son controles locales útiles, no configuración completa de
TLS, proxy público o seguridad de producción.

Requiere Compose >=2.30 por `env_file.format: raw`, que conserva `$` de secretos.
Con `.env` ya preparado:

```bash
docker compose --env-file .env.example up -d --build --wait api
```

El flag `.env.example` alimenta interpolación de Compose; el `env_file` del
servicio sigue leyendo el `.env` privado en formato raw. No confundir ambas
funciones.

Migraciones, solo cuando se pretenda modificar esa base:

```bash
docker compose --env-file .env.example --profile tools run --rm migrate
```

Stripe CLI corre fuera del contenedor:

```bash
stripe login
stripe listen --forward-to http://localhost:8000/api/v1/webhooks/stripe --events checkout.session.completed,customer.subscription.created,customer.subscription.updated,customer.subscription.deleted,invoice.paid,invoice.payment_failed
```

Guardar el secreto del listener en `.env` sin publicarlo y recrear API al
cambiar variables. La cuenta sandbox de CLI debe coincidir con key y Price IDs.
No cargar todas las variables de `.env` en Stripe CLI.

Detener API con `docker compose --env-file .env.example down`; detener listener
con Ctrl+C. Ver [spec Docker](../identity-market-backend/docker.md) para detalles.

## 10.6 Estrategia de pruebas y qué demuestra cada nivel

| Nivel | Instrumentos | Demuestra / no demuestra |
| --- | --- | --- |
| Regla unitaria | pytest y funciones puras | Ejemplos locales, no persistencia |
| Propiedades | Hypothesis, normalmente 100 ejemplos, deadline deshabilitado | Invariantes en muchas entradas; no prueba matemática universal |
| Caso de uso con fakes | Puertos en memoria y reloj controlado | Orquestación y fallos simulados, no proveedor real |
| API aislada | ASGITransport/TestClient y lifespan | Contratos y controles HTTP según overrides usados |
| PostgreSQL | Marker db, base desechable | Migraciones, constraints, repositorios y carreras reales |
| E2E externo | Credenciales sandbox y servidor dedicado | Integración en un entorno/fecha; no certificación de producción |

Fakes de proveedores implementan los mismos puertos. Facilitan forzar timeout,
429, 5xx, duplicados y eventos fuera de orden sin mover dinero ni depender del
horario bursátil real.

Comandos estándar:

```bash
uv run ruff check .
uv run mypy src
uv run pytest
```

### PostgreSQL desechable

**Advertencia crítica:** `migrated_database` ejecuta downgrade base antes/después
del fixture. Borra el esquema. Nunca usar Supabase compartido o producción en
`TEST_DATABASE_URL`.

```bash
docker compose -f tests/db/docker-compose.yml up -d --build
export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:55432/postgres
uv run pytest
```

Ver [instrucciones de test DB](../../../tests/db/README.md). Sus cifras históricas
de cantidad de tests no deben utilizarse como conteo actual.

### Validación durante esta revisión documental

Se usó el entorno existente con `uv run --no-sync` y se excluyó explícitamente
`TEST_DATABASE_URL` para no intervenir una base:

| Comprobación | Resultado |
| --- | --- |
| Ruff | Sin errores |
| mypy | Sin errores, 396 archivos fuente |
| pytest sin PostgreSQL | **797 passed, 48 skipped, 15 xfailed** |

La corrida produjo 2567 warnings, principalmente deprecaciones del entorno local
Python 3.14/asyncio. No se validó nuevamente PostgreSQL ni proveedores externos
como parte de esta tarea de documentación.

Un `xfail` no es funcionalidad aprobada: representa fallo conocido. Las quince
regresiones están en `tests/security/test_known_findings.py` y pueden verse como
fallos normales con `--runxfail`. Los resultados E2E anteriores se consultan en
su evidencia fechada, no se atribuyen a esta corrida.

## 10.7 Diagnóstico operativo por síntoma

| Síntoma | Qué comprobar antes de reintentar |
| --- | --- |
| No arranca | Nombres reportados por require_api_settings; no imprimir secretos |
| Health responde pero falla API | DB, migraciones y proveedor: health no los consulta |
| 401 tras refresh simultáneo | Rotación/reuso; centralizar renovación en frontend |
| Usuario entra pero no opera | Estado local, rol, KYC ACTIVE y trading gate son dimensiones distintas |
| Precio viejo | Feed, as_of, age, stale y served_from_cache |
| Orden SUBMITTED sin ID | Reconciliador, búsqueda por client ID; no crear otra con nueva clave |
| Transferencia in_progress | Posible resultado ambiguo externo; no borrar clave a ciegas |
| Pago no habilita premium | Firma/cuenta Stripe, asociación, evento y estado; no URL de retorno |
| Falta correo/SMS | Configuración de sender; SMS es simulado y email puede ser log |
| No llega reporte | Jobs, preferencia, periodo, reporte existente y notified_at |
| Broker pierde acceso | Vigencia del rol y vínculo activo, no solo sesión válida |
| 500 DATABASE_SCHEMA_ERROR | Revisión aplicada/consulta, no asumir caída de red |
| PATCH falla solo desde frontend | Preflight CORS conocido; probar no equivale a haberlo corregido |

## 10.8 Límites conocidos y trabajo pendiente

La [auditoría del 24/11/2026](../../../documentation/auditoria-e2e-2026-11-24/README.md)
y [sus hallazgos](../../../documentation/auditoria-e2e-2026-11-24/HALLAZGOS.md)
registran, entre otros:

1. PATCH ausente de `allow_methods` CORS aunque existe edición de perfil.
2. Contrato de login demasiado permisivo para algunas entradas.
3. Magnitudes decimales extremas en cotización de comisión pueden causar 500.
4. Manejo incompleto de frames WebSocket.
5. WebSocket no revalida sesión/permisos tras handshake.
6. Falta de presupuesto efectivo de intentos en login.
7. Dependencias con avisos de seguridad en versiones auditadas.

Esta entrega documenta; **no corrige ni vuelve a certificar** esos hallazgos.

Además, D4 excluye token CSRF y validación Origin/Referer, incluso en WebSocket.
SameSite y CORS ayudan, pero CORS no es un control CSRF completo y subdominios
same-site requieren atención. Recuperación MFA sin step-up adicional es otra
decisión existente, no una protección ausente por accidente documental.

No se han implementado cobros bursátiles reales, conversión de divisas, SMS real,
libro de profundidad completo, reconstrucción histórica completa de posiciones,
retención/purga definitiva ni coordinación durable genérica de jobs/avisos.

## 10.9 Cómo extender sin romper el diseño

1. Abrir/actualizar spec en `.kiro/specs/` y trazar a RF/RNF/CU/EC.
2. Resolver decisiones de negocio pendientes expresamente.
3. Escribir reglas y puertos en el módulo dueño, sin framework/SQL.
4. Orquestar en application; decidir atomicidad, idempotencia y recuperación.
5. Implementar adaptadores y conectarlos en composition.
6. Versionar DDL con Alembic y mantener contratos compatibles o migrarlos.
7. Probar caminos felices, rechazos, carreras y resultados externos ambiguos.
8. Actualizar OpenAPI, guía y evidencia sin convertir un test omitido o xfail
   en una aprobación.
