# Prueba E2E — `brokers-mod-06`

Fecha: 2026-11-16  
Base URL usada: `http://127.0.0.1:8002/api/v1` (API local iniciada con la configuración de `.env`).

## Resultado

- `POST /auth/login` y `POST /auth/mfa/verify`: **200 OK** para `broker.ti@accionesud.com` e `investor.ti@accionesud.com`.
- El primer endpoint del módulo (`GET /brokers?q=...`) respondió **500 DATABASE_SCHEMA_ERROR** en las consultas internas del portal broker (`GET /broker/link-requests` y `GET /broker/clients`), con SQLSTATE `42P01`.
- Diagnóstico: la base de datos configurada no tiene aplicada la migración `0009_brokers_schema` (faltan tablas del módulo). No se ejecutaron mutaciones parciales de enlaces/propuestas.

### Repetición correcta con Docker (`tests/db`)

Se levantó `acciones-ud-test-db` en `localhost:55432` y se ejecutó la suite contra:

```text
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:55432/postgres
```

Resultado: **102 passed, 4 warnings, 0 failed** (`tests/brokers` + `tests/identity/test_postgres_api.py`). La prueba E2E PostgreSQL `test_complete_broker_http_flow_uses_postgres_and_real_order_application` verificó el flujo completo: solicitud/aceptación de enlace, creación de propuesta, mensajes/evidencia, autorización de trading, aceptación TOTP, aprobación broker, creación de orden `BROKER_SIGNED`, idempotencia, consulta de órdenes, cierre de enlace y valoración.

Antes de repetir la sección funcional, aplicar migraciones contra la base configurada:

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.cache/uv'
uv run alembic upgrade head
```

## Autenticación

No se incluyen contraseñas, secretos TOTP ni tokens en este documento. Genera el código TOTP con tu aplicación/autenticador.

```http
POST /auth/login
Content-Type: application/json

{
  "email": "investor.ti@accionesud.com",
  "password": "<PASSWORD>"
}
```

```http
POST /auth/mfa/verify
Content-Type: application/json

{
  "mfa_token": "<MFA_TOKEN>",
  "code": "<TOTP_6_DIGITOS>"
}
```

Repetir ambos requests para `broker.ti@accionesud.com`. La API entrega cookies HttpOnly `access_token` y `refresh_token`; conservarlas en el cliente HTTP.

## Flujo completo reproducible

### 1. Buscar broker (inversor)

```http
GET /brokers?q=broker
Cookie: access_token=<INVESTOR_ACCESS_TOKEN>
```

Guardar `items[0].user_id` como `<BROKER_ID>`.

### 2. Solicitar enlace (inversor)

```http
POST /broker-links
Cookie: access_token=<INVESTOR_ACCESS_TOKEN>
Content-Type: application/json

{
  "broker_id": "<BROKER_ID>",
  "consent_accepted": true
}
```

Guardar `id` como `<LINK_ID>`.

### 3. Aceptar enlace (broker)

```http
GET /broker/link-requests
Cookie: access_token=<BROKER_ACCESS_TOKEN>
```

```http
POST /broker/link-requests/<LINK_ID>/accept
Cookie: access_token=<BROKER_ACCESS_TOKEN>
```

### 4. Autorizar trading (inversor)

```http
POST /broker-links/<LINK_ID>/trading-authorization
Cookie: access_token=<INVESTOR_ACCESS_TOKEN>
Content-Type: application/json

{
  "consent_accepted": true
}
```

### 5. Crear propuesta (broker)

Usar el UUID del inversor autenticado como `<INVESTOR_ID>`.

```http
POST /broker/proposals
Cookie: access_token=<BROKER_ACCESS_TOKEN>
Content-Type: application/json

{
  "investor_id": "<INVESTOR_ID>",
  "symbol": "AAPL",
  "side": "buy",
  "qty": "1",
  "type": "market"
}
```

Guardar `id` como `<PROPOSAL_ID>` y `version` como `<VERSION>`.

### 6. Mensaje y aceptación (inversor)

```http
POST /proposals/<PROPOSAL_ID>/messages
Cookie: access_token=<INVESTOR_ACCESS_TOKEN>
Content-Type: application/json

{
  "body": "Confirmo recepción de la propuesta."
}
```

```http
POST /proposals/<PROPOSAL_ID>/decision
Cookie: access_token=<INVESTOR_ACCESS_TOKEN>
Content-Type: application/json

{
  "version": <VERSION>,
  "decision": "accept",
  "comment": "Acepto la propuesta.",
  "totp_code": "<TOTP_6_DIGITOS>"
}
```

La aprobación debe crear una orden `BROKER_SIGNED`. Repetir exactamente el mismo request permite comprobar la idempotencia y debe devolver la misma orden sin duplicarla.

### 7. Verificación de estado y órdenes

```http
GET /proposals/<PROPOSAL_ID>
Cookie: access_token=<INVESTOR_ACCESS_TOKEN>
```

```http
GET /broker/proposals/<PROPOSAL_ID>
Cookie: access_token=<BROKER_ACCESS_TOKEN>
```

```http
GET /broker/clients
Cookie: access_token=<BROKER_ACCESS_TOKEN>
```

### 8. Valoración y cierre

```http
PUT /brokers/<BROKER_ID>/rating
Cookie: access_token=<INVESTOR_ACCESS_TOKEN>
Content-Type: application/json

{
  "stars": 5,
  "comment": "Prueba E2E completada."
}
```

```http
POST /broker-links/<LINK_ID>/end
Cookie: access_token=<INVESTOR_ACCESS_TOKEN>
Content-Type: application/json

{
  "reason": "Cierre de prueba E2E",
  "confirmed": true
}
```

## Códigos esperados

`200/201` en operaciones válidas; `401` sin cookie; `403` por rol o falta de enlace; `409` por versión/estado concurrente; `422` por JSON inválido; y `500 DATABASE_SCHEMA_ERROR` únicamente mientras no se aplique `0009_brokers_schema`.
