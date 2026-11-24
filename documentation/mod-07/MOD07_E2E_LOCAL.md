# MOD-07 — transcripción E2E local

- Inicio UTC: `2026-11-24T14:01:23.369097+00:00`.
- Fin UTC: `2026-11-24T14:05:53.694519+00:00`.
- API: `https://127.0.0.1:8447`; HTTPS local con certificado de prueba.
- Backend real, PostgreSQL real, sin mocks ni overrides de dependencias.
- `null` en solicitud significa **sin cuerpo JSON**. Una respuesta `null` con HTTP 204 significa **cuerpo vacío**.
- `<REDACTED>` reemplaza contraseña, código MFA/TOTP o token real. No es el valor enviado.
- Solicitudes: **126**; estados inesperados: **0**.

## Comprobaciones adicionales

```json
[
  {
    "label": "Semilla default 2 % y reparto 60/40",
    "pass": true,
    "detail": null
  },
  {
    "label": "Cotización 37.47 = 22.48 + 14.99; total 1910.97",
    "pass": true,
    "detail": null
  },
  {
    "label": "Venta neta 1836.03 y broker 0",
    "pass": true,
    "detail": null
  },
  {
    "label": "No retroactividad: tarifa sigue al 2 %",
    "pass": true,
    "detail": null
  },
  {
    "label": "Orden nueva conserva fee_version_id y tasa",
    "pass": true,
    "detail": null
  },
  {
    "label": "Halt público no filtra motivo ni actor",
    "pass": true,
    "detail": null
  },
  {
    "label": "Código de bloqueo TRADING_HALTED",
    "pass": true,
    "detail": null
  },
  {
    "label": "Código ACCOUNT_TRADING_RESTRICTED",
    "pass": true,
    "detail": null
  },
  {
    "label": "SHA256 del reporte coincide con contenido HTTP",
    "pass": true,
    "detail": null
  },
  {
    "label": "Caché KPI hit y computed_at estable",
    "pass": true,
    "detail": null
  },
  {
    "label": "Páginas sin duplicados",
    "pass": true,
    "detail": null
  },
  {
    "label": "3 cambios de calendario auditados y despachados",
    "pass": true,
    "detail": [
      {
        "action": "schedule_override_deleted",
        "status": "dispatched"
      },
      {
        "action": "schedule_override_updated",
        "status": "dispatched"
      },
      {
        "action": "schedule_override_created",
        "status": "dispatched"
      }
    ]
  },
  {
    "label": "Sin bloqueos ni tarifas temporales residuales",
    "pass": true,
    "detail": null
  },
  {
    "label": "Horario por defecto restaurado exactamente",
    "pass": true,
    "detail": null
  },
  {
    "label": "Horario por defecto restaurado exactamente",
    "pass": true,
    "detail": null
  },
  {
    "label": "LOCAL FIXTURE: comisión oficial con firma 37.47/22.48/14.99",
    "pass": true,
    "detail": null
  },
  {
    "label": "LOCAL FIXTURE: histórico excluido de total oficial",
    "pass": true,
    "detail": null
  },
  {
    "label": "LOCAL FIXTURE: KPI plataforma 422.48 USD",
    "pass": true,
    "detail": null
  },
  {
    "label": "LOCAL FIXTURE: señal absolute_threshold y ninguna restricción automática",
    "pass": true,
    "detail": null
  },
  {
    "label": "LOCAL FIXTURE: reporte total oficial 437.47",
    "pass": true,
    "detail": null
  },
  {
    "label": "LOCAL FIXTURE: SHA256 con datos no vacíos",
    "pass": true,
    "detail": null
  },
  {
    "label": "Notificaciones market_schedule_changes entregadas",
    "pass": true,
    "detail": null
  },
  {
    "label": "Rol temporal revocado: broker",
    "pass": true,
    "detail": null
  },
  {
    "label": "Rol temporal revocado: broker2",
    "pass": true,
    "detail": null
  }
]
```


## Recursos y estado final

```json
{
  "users": {
    "admin": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
    "admin2": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
    "investor": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
    "broker": "19f5fcb4-9a1d-4d3e-affe-96da0057cf2d",
    "broker2": "39bf8e8a-d3ec-4172-82c5-99e9508ffce1"
  },
  "fee_id": "93eb4361-d37c-4e50-b5bb-24ea329aab3c",
  "order_id": "be2036d3-f849-44af-9acf-9714dbc89bca",
  "halt_id": "7176011e-7850-4d63-aaf6-0f5e77a7b901",
  "restriction_id": "7e0e3186-8a90-4fa2-97b7-4b8c8d180c6e",
  "report_id": "01fe0358-f3e1-45c8-8bb7-d9f498575660",
  "override_id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
  "residual": {
    "active_restrictions": [],
    "unreleased_halts": [],
    "uncanceled_fees": []
  },
  "LOCAL_ONLY_controlled_fixtures": [
    {
      "kind": "official_signed",
      "order_id": "5cb54b04-0359-47e8-8204-c066d818e317",
      "execution_id": "mod07-fixture-official_signed-9623fb45-f785-499a-9ba5-c8d114438f44"
    },
    {
      "kind": "historical",
      "order_id": "54eeb5a8-a705-4a85-93cb-d2678151b4dd",
      "execution_id": "mod07-fixture-historical-5293ba75-2c80-44e0-ae3a-774e43bf4d8e"
    },
    {
      "kind": "atypical",
      "order_id": "96cd531c-c3ed-41e6-8598-12199822f39f",
      "execution_id": "mod07-fixture-atypical-d8296feb-8929-4a64-a2f7-1cfbc8de25e8"
    }
  ]
}
```


## Flujo paso a paso


### 1. Salud (no demuestra conectividad DB)

**Actor:** `anon`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/health
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (457.8 ms). Request ID: `67cd529d-3cc4-4540-b942-2a1cd4fee285`.

```json
{
  "status": "ok"
}
```


### 2. Contrato OpenAPI

**Actor:** `anon`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/openapi.json
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (628.24 ms). Request ID: `3d76dfd6-6875-4574-9d5e-9e62a2ce36e0`.

```json
{
  "note": "Contrato completo en archivo OpenAPI anexo",
  "paths_count": 140
}
```


### 3. Acceso anónimo rechazado

**Actor:** `anon`. **Resultado:** OK; HTTP esperado: `[401]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/fee-schedules
```

JSON enviado:

```json
null
```

Respuesta **HTTP 401** (3.13 ms). Request ID: `7057150e-b670-4c9f-b39f-2908c8c38352`.

```json
{
  "code": "<REDACTED>",
  "message": "Authentication required.",
  "details": null
}
```


### 4. Login admin

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/login
```

JSON enviado:

```json
{
  "email": "admin.ti@accionesud.com",
  "password": "<REDACTED>"
}
```

Respuesta **HTTP 200** (188.61 ms). Request ID: `7a3f85a8-ec81-4bf3-87cd-9f61d5f8f008`.

```json
{
  "mfa_token": "<REDACTED>",
  "mfa_expires_at": "2026-11-24T14:06:24.676565Z",
  "totp_enrollment": null
}
```


### 5. MFA admin

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/mfa/verify
```

JSON enviado:

```json
{
  "mfa_token": "<REDACTED>",
  "code": "<REDACTED>"
}
```

Respuesta **HTTP 200** (14.58 ms). Request ID: `676fc446-b206-428d-97ee-ba7d7d281194`.

```json
{
  "user": {
    "user_id": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
    "email": "admin.ti@accionesud.com",
    "account_status": "active"
  },
  "recovery_codes": null,
  "recovery_codes_remaining": null
}
```


### 6. Login admin2

**Actor:** `admin2`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/login
```

JSON enviado:

```json
{
  "email": "admin2.ti@accionesud.com",
  "password": "<REDACTED>"
}
```

Respuesta **HTTP 200** (68.31 ms). Request ID: `842cb184-1577-45d1-a327-f3e0617cb16b`.

```json
{
  "mfa_token": "<REDACTED>",
  "mfa_expires_at": "2026-11-24T14:06:24.792430Z",
  "totp_enrollment": null
}
```


### 7. MFA admin2

**Actor:** `admin2`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/mfa/verify
```

JSON enviado:

```json
{
  "mfa_token": "<REDACTED>",
  "code": "<REDACTED>"
}
```

Respuesta **HTTP 200** (8.6 ms). Request ID: `2e7b681a-e85a-4e57-873d-7578684c26b7`.

```json
{
  "user": {
    "user_id": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
    "email": "admin2.ti@accionesud.com",
    "account_status": "active"
  },
  "recovery_codes": null,
  "recovery_codes_remaining": null
}
```


### 8. Login investor

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/login
```

JSON enviado:

```json
{
  "email": "investor.ti@accionesud.com",
  "password": "<REDACTED>"
}
```

Respuesta **HTTP 200** (68.37 ms). Request ID: `82893ec2-c469-4a9f-937b-d8afb197989d`.

```json
{
  "mfa_token": "<REDACTED>",
  "mfa_expires_at": "2026-11-24T14:06:24.871839Z",
  "totp_enrollment": null
}
```


### 9. MFA investor

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/mfa/verify
```

JSON enviado:

```json
{
  "mfa_token": "<REDACTED>",
  "code": "<REDACTED>"
}
```

Respuesta **HTTP 200** (8.18 ms). Request ID: `07274ad4-a7d7-4b48-8cf2-1aa26fefc7f7`.

```json
{
  "user": {
    "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
    "email": "investor.ti@accionesud.com",
    "account_status": "active"
  },
  "recovery_codes": null,
  "recovery_codes_remaining": null
}
```


### 10. Login broker

**Actor:** `broker`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/login
```

JSON enviado:

```json
{
  "email": "broker.ti@accionesud.com",
  "password": "<REDACTED>"
}
```

Respuesta **HTTP 200** (72.74 ms). Request ID: `5920e78b-dbda-4df1-b7a7-575d614cf24d`.

```json
{
  "mfa_token": "<REDACTED>",
  "mfa_expires_at": "2026-11-24T14:06:24.950522Z",
  "totp_enrollment": null
}
```


### 11. MFA broker

**Actor:** `broker`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/mfa/verify
```

JSON enviado:

```json
{
  "mfa_token": "<REDACTED>",
  "code": "<REDACTED>"
}
```

Respuesta **HTTP 200** (7.18 ms). Request ID: `418bec93-1c8a-4cda-b224-a1b570396930`.

```json
{
  "user": {
    "user_id": "19f5fcb4-9a1d-4d3e-affe-96da0057cf2d",
    "email": "broker.ti@accionesud.com",
    "account_status": "active"
  },
  "recovery_codes": null,
  "recovery_codes_remaining": null
}
```


### 12. Login broker2

**Actor:** `broker2`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/login
```

JSON enviado:

```json
{
  "email": "broker2.ti@accionesud.com",
  "password": "<REDACTED>"
}
```

Respuesta **HTTP 200** (83.74 ms). Request ID: `9f1cad24-cd82-4938-be55-2a6aefe8237e`.

```json
{
  "mfa_token": "<REDACTED>",
  "mfa_expires_at": "2026-11-24T14:06:25.033484Z",
  "totp_enrollment": null
}
```


### 13. MFA broker2

**Actor:** `broker2`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/mfa/verify
```

JSON enviado:

```json
{
  "mfa_token": "<REDACTED>",
  "code": "<REDACTED>"
}
```

Respuesta **HTTP 200** (8.08 ms). Request ID: `0a5c15b1-befb-48d6-bbde-26b76cf4b399`.

```json
{
  "user": {
    "user_id": "39bf8e8a-d3ec-4172-82c5-99e9508ffce1",
    "email": "broker2.ti@accionesud.com",
    "account_status": "active"
  },
  "recovery_codes": null,
  "recovery_codes_remaining": null
}
```


### 14. Roles y permisos efectivos del administrador

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/users/me
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (20.36 ms). Request ID: `7ae4acab-5530-468e-8062-053c3ee697d6`.

```json
{
  "user_id": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
  "first_names": "Admin",
  "last_names": "Bootstrap",
  "email": "admin.ti@accionesud.com",
  "phone": "+573001110001",
  "country": "CO",
  "account_status": "active",
  "registered_at": "2026-11-11T15:03:21.433581Z",
  "contracted_plan": null,
  "is_premium": false,
  "broker_requested": false,
  "associated_broker": null,
  "roles": [
    "administrator"
  ],
  "kyc_status": null,
  "kyc_status_unavailable": false,
  "interests": [],
  "investor_level": null,
  "mfa_enrolled": true
}
```


### 15. Semilla auditor/analyst y permisos

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/roles
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (6.03 ms). Request ID: `7d29d0bb-4bdc-41ed-8f5e-a1f94fe8b0fb`.

```json
[
  {
    "role": "administrator",
    "permissions": [
      "account:manage",
      "admin:audit",
      "admin:bi",
      "admin:commissions",
      "admin:compliance",
      "admin:compliance:read",
      "admin:fees",
      "admin:halts",
      "admin:markets",
      "admin:rbac",
      "admin:users",
      "market:read",
      "watchlist:manage"
    ]
  },
  {
    "role": "analyst",
    "permissions": [
      "admin:bi"
    ]
  },
  {
    "role": "auditor",
    "permissions": [
      "admin:audit",
      "admin:compliance:read"
    ]
  },
  {
    "role": "broker",
    "permissions": [
      "account:manage",
      "market:read",
      "watchlist:manage"
    ]
  },
  {
    "role": "investor",
    "permissions": [
      "account:manage",
      "kyc:submit",
      "market:read",
      "watchlist:manage"
    ]
  }
]
```


### 16. Investor no administra tarifas

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[403]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/fee-schedules
```

JSON enviado:

```json
null
```

Respuesta **HTTP 403** (4.16 ms). Request ID: `0f0c21a4-ba8a-423b-9961-7457cc22d901`.

```json
{
  "code": "<REDACTED>",
  "message": "Permission required.",
  "details": null
}
```


### 17. Matriz inicial

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/fee-schedules
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (10.02 ms). Request ID: `19b5d720-a465-42e0-ba67-91c4700a6259`.

```json
{
  "items": [
    {
      "scope": "default",
      "terms": {
        "fee_version_id": "00000000-0000-0000-0000-000000000701",
        "commission_rate_pct": "2",
        "platform_share_pct": "60"
      },
      "current": {
        "id": "00000000-0000-0000-0000-000000000701",
        "scope": "default",
        "version_no": 1,
        "commission_rate_pct": "2",
        "platform_share_pct": "60",
        "broker_share_pct": "40",
        "effective_from": "1970-01-01T00:00:00Z",
        "status": "in_force",
        "reason": "Tarifa base del catálogo (RF-43)",
        "created_by": null,
        "created_at": "2026-11-24T13:56:48.047067Z",
        "canceled_at": null,
        "canceled_by": null,
        "cancel_reason": null
      },
      "origin": "default",
      "scheduled": []
    },
    {
      "scope": "AMEX",
      "terms": {
        "fee_version_id": "00000000-0000-0000-0000-000000000701",
        "commission_rate_pct": "2",
        "platform_share_pct": "60"
      },
      "current": {
        "id": "00000000-0000-0000-0000-000000000701",
        "scope": "default",
        "version_no": 1,
        "commission_rate_pct": "2",
        "platform_share_pct": "60",
        "broker_share_pct": "40",
        "effective_from": "1970-01-01T00:00:00Z",
        "status": "in_force",
        "reason": "Tarifa base del catálogo (RF-43)",
        "created_by": null,
        "created_at": "2026-11-24T13:56:48.047067Z",
        "canceled_at": null,
        "canceled_by": null,
        "cancel_reason": null
      },
      "origin": "default",
      "scheduled": []
    },
    {
      "scope": "ARCA",
      "terms": {
        "fee_version_id": "00000000-0000-0000-0000-000000000701",
        "commission_rate_pct": "2",
        "platform_share_pct": "60"
      },
      "current": {
        "id": "00000000-0000-0000-0000-000000000701",
        "scope": "default",
        "version_no": 1,
        "commission_rate_pct": "2",
        "platform_share_pct": "60",
        "broker_share_pct": "40",
        "effective_from": "1970-01-01T00:00:00Z",
        "status": "in_force",
        "reason": "Tarifa base del catálogo (RF-43)",
        "created_by": null,
        "created_at": "2026-11-24T13:56:48.047067Z",
        "canceled_at": null,
        "canceled_by": null,
        "cancel_reason": null
      },
      "origin": "default",
      "scheduled": []
    },
    {
      "scope": "BATS",
      "terms": {
        "fee_version_id": "00000000-0000-0000-0000-000000000701",
        "commission_rate_pct": "2",
        "platform_share_pct": "60"
      },
      "current": {
        "id": "00000000-0000-0000-0000-000000000701",
        "scope": "default",
        "version_no": 1,
        "commission_rate_pct": "2",
        "platform_share_pct": "60",
        "broker_share_pct": "40",
        "effective_from": "1970-01-01T00:00:00Z",
        "status": "in_force",
        "reason": "Tarifa base del catálogo (RF-43)",
        "created_by": null,
        "created_at": "2026-11-24T13:56:48.047067Z",
        "canceled_at": null,
        "canceled_by": null,
        "cancel_reason": null
      },
      "origin": "default",
      "scheduled": []
    },
    {
      "scope": "NASDAQ",
      "terms": {
        "fee_version_id": "00000000-0000-0000-0000-000000000701",
        "commission_rate_pct": "2",
        "platform_share_pct": "60"
      },
      "current": {
        "id": "00000000-0000-0000-0000-000000000701",
        "scope": "default",
        "version_no": 1,
        "commission_rate_pct": "2",
        "platform_share_pct": "60",
        "broker_share_pct": "40",
        "effective_from": "1970-01-01T00:00:00Z",
        "status": "in_force",
        "reason": "Tarifa base del catálogo (RF-43)",
        "created_by": null,
        "created_at": "2026-11-24T13:56:48.047067Z",
        "canceled_at": null,
        "canceled_by": null,
        "cancel_reason": null
      },
      "origin": "default",
      "scheduled": []
    },
    {
      "scope": "NYSE",
      "terms": {
        "fee_version_id": "00000000-0000-0000-0000-000000000701",
        "commission_rate_pct": "2",
        "platform_share_pct": "60"
      },
      "current": {
        "id": "00000000-0000-0000-0000-000000000701",
        "scope": "default",
        "version_no": 1,
        "commission_rate_pct": "2",
        "platform_share_pct": "60",
        "broker_share_pct": "40",
        "effective_from": "1970-01-01T00:00:00Z",
        "status": "in_force",
        "reason": "Tarifa base del catálogo (RF-43)",
        "created_by": null,
        "created_at": "2026-11-24T13:56:48.047067Z",
        "canceled_at": null,
        "canceled_by": null,
        "cancel_reason": null
      },
      "origin": "default",
      "scheduled": []
    },
    {
      "scope": "NYSEARCA",
      "terms": {
        "fee_version_id": "00000000-0000-0000-0000-000000000701",
        "commission_rate_pct": "2",
        "platform_share_pct": "60"
      },
      "current": {
        "id": "00000000-0000-0000-0000-000000000701",
        "scope": "default",
        "version_no": 1,
        "commission_rate_pct": "2",
        "platform_share_pct": "60",
        "broker_share_pct": "40",
        "effective_from": "1970-01-01T00:00:00Z",
        "status": "in_force",
        "reason": "Tarifa base del catálogo (RF-43)",
        "created_by": null,
        "created_at": "2026-11-24T13:56:48.047067Z",
        "canceled_at": null,
        "canceled_by": null,
        "cancel_reason": null
      },
      "origin": "default",
      "scheduled": []
    },
    {
      "scope": "OTC",
      "terms": {
        "fee_version_id": "00000000-0000-0000-0000-000000000701",
        "commission_rate_pct": "2",
        "platform_share_pct": "60"
      },
      "current": {
        "id": "00000000-0000-0000-0000-000000000701",
        "scope": "default",
        "version_no": 1,
        "commission_rate_pct": "2",
        "platform_share_pct": "60",
        "broker_share_pct": "40",
        "effective_from": "1970-01-01T00:00:00Z",
        "status": "in_force",
        "reason": "Tarifa base del catálogo (RF-43)",
        "created_by": null,
        "created_at": "2026-11-24T13:56:48.047067Z",
        "canceled_at": null,
        "canceled_by": null,
        "cancel_reason": null
      },
      "origin": "default",
      "scheduled": []
    }
  ]
}
```


### 18. Vista consolidada de mercados

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/markets
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (9.02 ms). Request ID: `03c1b334-1a94-4255-ac38-10dcd1c61d0e`.

```json
[
  {
    "code": "<REDACTED>",
    "name": "NYSE American",
    "timezone": "America/New_York",
    "default_schedule": null,
    "overrides": [],
    "commission_terms": {
      "fee_version_id": "00000000-0000-0000-0000-000000000701",
      "commission_rate_pct": "2",
      "platform_share_pct": "60"
    },
    "fee_origin": "default",
    "trading_halts": []
  },
  {
    "code": "<REDACTED>",
    "name": "NYSE Arca",
    "timezone": "America/New_York",
    "default_schedule": null,
    "overrides": [],
    "commission_terms": {
      "fee_version_id": "00000000-0000-0000-0000-000000000701",
      "commission_rate_pct": "2",
      "platform_share_pct": "60"
    },
    "fee_origin": "default",
    "trading_halts": []
  },
  {
    "code": "<REDACTED>",
    "name": "Cboe BZX",
    "timezone": "America/New_York",
    "default_schedule": null,
    "overrides": [],
    "commission_terms": {
      "fee_version_id": "00000000-0000-0000-0000-000000000701",
      "commission_rate_pct": "2",
      "platform_share_pct": "60"
    },
    "fee_origin": "default",
    "trading_halts": []
  },
  {
    "code": "<REDACTED>",
    "name": "Nasdaq",
    "timezone": "America/New_York",
    "default_schedule": null,
    "overrides": [],
    "commission_terms": {
      "fee_version_id": "00000000-0000-0000-0000-000000000701",
      "commission_rate_pct": "2",
      "platform_share_pct": "60"
    },
    "fee_origin": "default",
    "trading_halts": []
  },
  {
    "code": "<REDACTED>",
    "name": "New York Stock Exchange",
    "timezone": "America/New_York",
    "default_schedule": null,
    "overrides": [],
    "commission_terms": {
      "fee_version_id": "00000000-0000-0000-0000-000000000701",
      "commission_rate_pct": "2",
      "platform_share_pct": "60"
    },
    "fee_origin": "default",
    "trading_halts": []
  },
  {
    "code": "<REDACTED>",
    "name": "NYSE Arca",
    "timezone": "America/New_York",
    "default_schedule": null,
    "overrides": [],
    "commission_terms": {
      "fee_version_id": "00000000-0000-0000-0000-000000000701",
      "commission_rate_pct": "2",
      "platform_share_pct": "60"
    },
    "fee_origin": "default",
    "trading_halts": []
  },
  {
    "code": "<REDACTED>",
    "name": "Over the counter",
    "timezone": "America/New_York",
    "default_schedule": null,
    "overrides": [],
    "commission_terms": {
      "fee_version_id": "00000000-0000-0000-0000-000000000701",
      "commission_rate_pct": "2",
      "platform_share_pct": "60"
    },
    "fee_origin": "default",
    "trading_halts": []
  }
]
```


### 19. /api/v1/admin/markets/NASDAQ

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/markets/NASDAQ
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (7.16 ms). Request ID: `cb790176-9f6f-49f8-ad96-56fe1b712eb5`.

```json
{
  "code": "<REDACTED>",
  "name": "Nasdaq",
  "timezone": "America/New_York",
  "default_schedule": null,
  "overrides": [],
  "commission_terms": {
    "fee_version_id": "00000000-0000-0000-0000-000000000701",
    "commission_rate_pct": "2",
    "platform_share_pct": "60"
  },
  "fee_origin": "default",
  "trading_halts": []
}
```


### 20. /api/v1/admin/markets/NOEXISTE

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[404]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/markets/NOEXISTE
```

JSON enviado:

```json
null
```

Respuesta **HTTP 404** (6.18 ms). Request ID: `440a8f68-2b06-4bed-8559-f21dc3f2e04d`.

```json
{
  "code": "<REDACTED>",
  "message": "Resource not found.",
  "details": {
    "resource": "market"
  }
}
```


### 21. Compra con broker: cálculo RF-43

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/commissions/quote?symbol=AAPL&side=buy&qty=10&price=187.35&with_broker=true
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (7.43 ms). Request ID: `c4a8740f-2a53-4805-beea-6b8834ce6318`.

```json
{
  "fee_version_id": "00000000-0000-0000-0000-000000000701",
  "commission_rate_pct": "2",
  "platform_share_pct": "60",
  "gross_amount": "1873.5",
  "commission": "37.47",
  "platform_share": "22.48",
  "broker_share": "14.99",
  "total": "1910.97",
  "net": null,
  "symbol": "AAPL",
  "market": "NASDAQ",
  "binding": false,
  "quoted_at": "2026-11-24T14:01:25.197337Z"
}
```


### 22. Venta sin broker

**Actor:** `broker`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/commissions/quote?symbol=AAPL&side=sell&qty=10&price=187.35&with_broker=false
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (7.78 ms). Request ID: `4b66fa62-3f2d-48e3-91a8-63209a470ea4`.

```json
{
  "fee_version_id": "00000000-0000-0000-0000-000000000701",
  "commission_rate_pct": "2",
  "platform_share_pct": "60",
  "gross_amount": "1873.5",
  "commission": "37.47",
  "platform_share": "37.47",
  "broker_share": "0",
  "total": null,
  "net": "1836.03",
  "symbol": "AAPL",
  "market": "NASDAQ",
  "binding": false,
  "quoted_at": "2026-11-24T14:01:25.205496Z"
}
```


### 23. Admin sin rol trader no cotiza

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[403]`.

```http
GET https://127.0.0.1:8447/api/v1/commissions/quote?symbol=AAPL&side=buy&qty=10&price=187.35&with_broker=true
```

JSON enviado:

```json
null
```

Respuesta **HTTP 403** (4.22 ms). Request ID: `e3492210-2a05-4c53-8764-656cc4bea287`.

```json
{
  "code": "<REDACTED>",
  "message": "Investor or broker role required.",
  "details": null
}
```


### 24. /api/v1/commissions/quote

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[422]`.

```http
GET https://127.0.0.1:8447/api/v1/commissions/quote?symbol=AAPL&side=buy&qty=0&price=187.35&with_broker=true
```

JSON enviado:

```json
null
```

Respuesta **HTTP 422** (3.83 ms). Request ID: `37492b64-dd6d-47dc-be2e-ffe97627afc9`.

```json
{
  "code": "<REDACTED>",
  "message": "Invalid field: query.qty",
  "details": {
    "errors": [
      {
        "field": "query.qty",
        "issue": "greater_than"
      }
    ]
  }
}
```


### 25. /api/v1/commissions/quote

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[404]`.

```http
GET https://127.0.0.1:8447/api/v1/commissions/quote?symbol=NOEXISTE&side=buy&qty=10&price=187.35&with_broker=true
```

JSON enviado:

```json
null
```

Respuesta **HTTP 404** (5.5 ms). Request ID: `8903f403-a0a5-41d0-8263-af67a5f64325`.

```json
{
  "code": "<REDACTED>",
  "message": "Unknown symbol.",
  "details": null
}
```


### 26. /api/v1/commissions/quote

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[422]`.

```http
GET https://127.0.0.1:8447/api/v1/commissions/quote?symbol=AAPL&side=other&qty=10&price=187.35&with_broker=true
```

JSON enviado:

```json
null
```

Respuesta **HTTP 422** (7.85 ms). Request ID: `ec08af84-2f27-4cf8-a55c-028782b4c74c`.

```json
{
  "code": "<REDACTED>",
  "message": "Invalid administrative field.",
  "details": {
    "field": "side",
    "reason": "invalid"
  }
}
```


### 27. Comisiones investor

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/commissions?from=2026-11-01&to=2026-11-24&page_size=2
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (10.41 ms). Request ID: `abd9de89-d263-4733-8fdf-cc24f59b30d0`.

```json
{
  "items": [],
  "next_cursor": null,
  "totals": {
    "commission": "0",
    "platform_share": "0",
    "broker_share": "0",
    "gross_amount": "0",
    "historical_terms_unknown_count": 0,
    "complete": true
  },
  "by_market": {},
  "by_broker": {}
}
```


### 28. Comisiones broker

**Actor:** `broker`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/broker/commissions?from=2026-11-01&to=2026-11-24&page_size=2
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (11.45 ms). Request ID: `777c4ff5-90a7-4cf3-b0b2-c0305698eec4`.

```json
{
  "items": [],
  "next_cursor": null,
  "totals": {
    "commission": "0",
    "platform_share": "0",
    "broker_share": "0",
    "gross_amount": "0",
    "historical_terms_unknown_count": 0,
    "complete": true
  },
  "by_market": {},
  "by_broker": {}
}
```


### 29. Comisiones admin

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/commissions?from=2026-11-01&to=2026-11-24&page_size=2
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (8.69 ms). Request ID: `0c1cea00-16cc-4bab-9c23-b1d066eb2d29`.

```json
{
  "items": [],
  "next_cursor": null,
  "totals": {
    "commission": "0",
    "platform_share": "0",
    "broker_share": "0",
    "gross_amount": "0",
    "historical_terms_unknown_count": 0,
    "complete": true
  },
  "by_market": {},
  "by_broker": {}
}
```


### 30. Broker sin vínculo: CLIENT_NOT_FOUND

**Actor:** `broker2`. **Resultado:** OK; HTTP esperado: `[404]`.

```http
GET https://127.0.0.1:8447/api/v1/broker/commissions?from=2026-11-01&to=2026-11-24&investor_id=3f83ecc7-00e5-4b95-9e86-f4b305b3f46c
```

JSON enviado:

```json
null
```

Respuesta **HTTP 404** (6.98 ms). Request ID: `5794b16c-df18-4a5b-92a3-dd53d07fce64`.

```json
{
  "code": "<REDACTED>",
  "message": "Client not found.",
  "details": null
}
```


### 31. Periodo invertido

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[422]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/commissions?from=2026-11-24&to=2026-11-01
```

JSON enviado:

```json
null
```

Respuesta **HTTP 422** (3.31 ms). Request ID: `635ad6d9-06d6-43f4-8166-e92f898e3d40`.

```json
{
  "code": "<REDACTED>",
  "message": "Invalid administrative field.",
  "details": {
    "field": "period",
    "reason": "invalid"
  }
}
```


### 32. /api/v1/admin/fee-schedules/NASDAQ/versions

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/fee-schedules/NASDAQ/versions
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (6.41 ms). Request ID: `5d913c51-37a0-404e-8584-42c67e55c034`.

```json
{
  "items": [],
  "next_cursor": null
}
```


### 33. Escritura crítica exige step-up

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[409]`.

```http
POST https://127.0.0.1:8447/api/v1/admin/fee-schedules/NASDAQ/versions
```

JSON enviado:

```json
{
  "commission_rate_pct": "2.5000",
  "platform_share_pct": "65.00",
  "expected_latest_version": 0,
  "effective_from": "2026-12-01T14:01:25.284719+00:00",
  "reason": "E2E MOD07 local: tarifa futura temporal"
}
```

Respuesta **HTTP 409** (7.74 ms). Request ID: `7185023c-6bfb-4db0-b97a-161719a0f2b3`.

```json
{
  "code": "<REDACTED>",
  "message": "TOTP required.",
  "details": null
}
```


### 34. Step-up inválido

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[401]`.

```http
POST https://127.0.0.1:8447/api/v1/admin/fee-schedules/NASDAQ/versions
```

JSON enviado:

```json
{
  "commission_rate_pct": "2.5000",
  "platform_share_pct": "65.00",
  "expected_latest_version": 0,
  "effective_from": "2026-12-01T14:01:25.284719+00:00",
  "reason": "E2E MOD07 local: tarifa futura temporal",
  "totp_code": "<REDACTED>"
}
```

Respuesta **HTTP 401** (8.11 ms). Request ID: `a4173ca5-5583-4d63-8d01-530fd34abc9b`.

```json
{
  "code": "<REDACTED>",
  "message": "Invalid TOTP.",
  "details": null
}
```


### 35. Tasa fuera de rango

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[422]`.

```http
POST https://127.0.0.1:8447/api/v1/admin/fee-schedules/NASDAQ/versions
```

JSON enviado:

```json
{
  "commission_rate_pct": "11",
  "platform_share_pct": "65.00",
  "expected_latest_version": 0,
  "effective_from": "2026-12-01T14:01:25.284719+00:00",
  "reason": "E2E MOD07 local: tarifa futura temporal"
}
```

Respuesta **HTTP 422** (4.28 ms). Request ID: `a00a54dd-e6b3-4fd6-9b33-a82b2620282f`.

```json
{
  "code": "<REDACTED>",
  "message": "Invalid field: body.commission_rate_pct",
  "details": {
    "errors": [
      {
        "field": "body.commission_rate_pct",
        "issue": "less_than_equal"
      }
    ]
  }
}
```


### 36. Crear tarifa futura

**Actor:** `admin2`. **Resultado:** OK; HTTP esperado: `[201]`.

```http
POST https://127.0.0.1:8447/api/v1/admin/fee-schedules/NASDAQ/versions
```

JSON enviado:

```json
{
  "commission_rate_pct": "2.5000",
  "platform_share_pct": "65.00",
  "expected_latest_version": 0,
  "effective_from": "2026-12-01T14:01:25.284719+00:00",
  "reason": "E2E MOD07 local: tarifa futura temporal",
  "totp_code": "<REDACTED>"
}
```

Respuesta **HTTP 201** (17.42 ms). Request ID: `855f5f49-0b56-458a-b079-756cf80d7960`.

```json
{
  "id": "93eb4361-d37c-4e50-b5bb-24ea329aab3c",
  "scope": "NASDAQ",
  "version_no": 1,
  "commission_rate_pct": "2.5",
  "platform_share_pct": "65",
  "broker_share_pct": "35",
  "effective_from": "2026-12-01T14:01:25.284719Z",
  "status": "scheduled",
  "reason": "E2E MOD07 local: tarifa futura temporal",
  "created_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
  "created_at": "2026-11-24T14:01:25.312275Z",
  "canceled_at": null,
  "canceled_by": null,
  "cancel_reason": null
}
```


### 37. Conflicto optimista de versión

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[409]`.

```http
POST https://127.0.0.1:8447/api/v1/admin/fee-schedules/NASDAQ/versions
```

JSON enviado:

```json
{
  "commission_rate_pct": "2.5000",
  "platform_share_pct": "65.00",
  "expected_latest_version": 0,
  "effective_from": "2026-12-01T14:01:25.284719+00:00",
  "reason": "E2E MOD07 local: tarifa futura temporal",
  "totp_code": "<REDACTED>"
}
```

Respuesta **HTTP 409** (12.78 ms). Request ID: `723ff68c-1668-4cdd-8b37-8bfff3297b91`.

```json
{
  "code": "<REDACTED>",
  "message": "Administrative operation conflicts with stored state.",
  "details": {
    "latest_version": 1
  }
}
```


### 38. Historial paginado de tarifas

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/fee-schedules/NASDAQ/versions?page_size=1
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (7.29 ms). Request ID: `667f15b4-9440-46c3-b972-5531b8a5d59e`.

```json
{
  "items": [
    {
      "id": "93eb4361-d37c-4e50-b5bb-24ea329aab3c",
      "scope": "NASDAQ",
      "version_no": 1,
      "commission_rate_pct": "2.5",
      "platform_share_pct": "65",
      "broker_share_pct": "35",
      "effective_from": "2026-12-01T14:01:25.284719Z",
      "status": "scheduled",
      "reason": "E2E MOD07 local: tarifa futura temporal",
      "created_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
      "created_at": "2026-11-24T14:01:25.312275Z",
      "canceled_at": null,
      "canceled_by": null,
      "cancel_reason": null
    }
  ],
  "next_cursor": null
}
```


### 39. Matriz incluye tarifa programada

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/fee-schedules
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (7.38 ms). Request ID: `d28adef6-5782-48c7-9127-2ae6036dcae9`.

```json
{
  "items": [
    {
      "scope": "default",
      "terms": {
        "fee_version_id": "00000000-0000-0000-0000-000000000701",
        "commission_rate_pct": "2",
        "platform_share_pct": "60"
      },
      "current": {
        "id": "00000000-0000-0000-0000-000000000701",
        "scope": "default",
        "version_no": 1,
        "commission_rate_pct": "2",
        "platform_share_pct": "60",
        "broker_share_pct": "40",
        "effective_from": "1970-01-01T00:00:00Z",
        "status": "in_force",
        "reason": "Tarifa base del catálogo (RF-43)",
        "created_by": null,
        "created_at": "2026-11-24T13:56:48.047067Z",
        "canceled_at": null,
        "canceled_by": null,
        "cancel_reason": null
      },
      "origin": "default",
      "scheduled": []
    },
    {
      "scope": "AMEX",
      "terms": {
        "fee_version_id": "00000000-0000-0000-0000-000000000701",
        "commission_rate_pct": "2",
        "platform_share_pct": "60"
      },
      "current": {
        "id": "00000000-0000-0000-0000-000000000701",
        "scope": "default",
        "version_no": 1,
        "commission_rate_pct": "2",
        "platform_share_pct": "60",
        "broker_share_pct": "40",
        "effective_from": "1970-01-01T00:00:00Z",
        "status": "in_force",
        "reason": "Tarifa base del catálogo (RF-43)",
        "created_by": null,
        "created_at": "2026-11-24T13:56:48.047067Z",
        "canceled_at": null,
        "canceled_by": null,
        "cancel_reason": null
      },
      "origin": "default",
      "scheduled": []
    },
    {
      "scope": "ARCA",
      "terms": {
        "fee_version_id": "00000000-0000-0000-0000-000000000701",
        "commission_rate_pct": "2",
        "platform_share_pct": "60"
      },
      "current": {
        "id": "00000000-0000-0000-0000-000000000701",
        "scope": "default",
        "version_no": 1,
        "commission_rate_pct": "2",
        "platform_share_pct": "60",
        "broker_share_pct": "40",
        "effective_from": "1970-01-01T00:00:00Z",
        "status": "in_force",
        "reason": "Tarifa base del catálogo (RF-43)",
        "created_by": null,
        "created_at": "2026-11-24T13:56:48.047067Z",
        "canceled_at": null,
        "canceled_by": null,
        "cancel_reason": null
      },
      "origin": "default",
      "scheduled": []
    },
    {
      "scope": "BATS",
      "terms": {
        "fee_version_id": "00000000-0000-0000-0000-000000000701",
        "commission_rate_pct": "2",
        "platform_share_pct": "60"
      },
      "current": {
        "id": "00000000-0000-0000-0000-000000000701",
        "scope": "default",
        "version_no": 1,
        "commission_rate_pct": "2",
        "platform_share_pct": "60",
        "broker_share_pct": "40",
        "effective_from": "1970-01-01T00:00:00Z",
        "status": "in_force",
        "reason": "Tarifa base del catálogo (RF-43)",
        "created_by": null,
        "created_at": "2026-11-24T13:56:48.047067Z",
        "canceled_at": null,
        "canceled_by": null,
        "cancel_reason": null
      },
      "origin": "default",
      "scheduled": []
    },
    {
      "scope": "NASDAQ",
      "terms": {
        "fee_version_id": "00000000-0000-0000-0000-000000000701",
        "commission_rate_pct": "2",
        "platform_share_pct": "60"
      },
      "current": {
        "id": "00000000-0000-0000-0000-000000000701",
        "scope": "default",
        "version_no": 1,
        "commission_rate_pct": "2",
        "platform_share_pct": "60",
        "broker_share_pct": "40",
        "effective_from": "1970-01-01T00:00:00Z",
        "status": "in_force",
        "reason": "Tarifa base del catálogo (RF-43)",
        "created_by": null,
        "created_at": "2026-11-24T13:56:48.047067Z",
        "canceled_at": null,
        "canceled_by": null,
        "cancel_reason": null
      },
      "origin": "default",
      "scheduled": [
        {
          "id": "93eb4361-d37c-4e50-b5bb-24ea329aab3c",
          "market_code": "NASDAQ",
          "version_no": 1,
          "commission_rate_pct": "2.5",
          "platform_share_pct": "65",
          "effective_from": "2026-12-01T14:01:25.284719+00:00",
          "reason": "E2E MOD07 local: tarifa futura temporal",
          "created_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
          "created_at": "2026-11-24T14:01:25.312275+00:00",
          "canceled_at": null,
          "canceled_by": null,
          "cancel_reason": null,
          "scope": "NASDAQ",
          "broker_share_pct": "35",
          "status": "scheduled"
        }
      ]
    },
    {
      "scope": "NYSE",
      "terms": {
        "fee_version_id": "00000000-0000-0000-0000-000000000701",
        "commission_rate_pct": "2",
        "platform_share_pct": "60"
      },
      "current": {
        "id": "00000000-0000-0000-0000-000000000701",
        "scope": "default",
        "version_no": 1,
        "commission_rate_pct": "2",
        "platform_share_pct": "60",
        "broker_share_pct": "40",
        "effective_from": "1970-01-01T00:00:00Z",
        "status": "in_force",
        "reason": "Tarifa base del catálogo (RF-43)",
        "created_by": null,
        "created_at": "2026-11-24T13:56:48.047067Z",
        "canceled_at": null,
        "canceled_by": null,
        "cancel_reason": null
      },
      "origin": "default",
      "scheduled": []
    },
    {
      "scope": "NYSEARCA",
      "terms": {
        "fee_version_id": "00000000-0000-0000-0000-000000000701",
        "commission_rate_pct": "2",
        "platform_share_pct": "60"
      },
      "current": {
        "id": "00000000-0000-0000-0000-000000000701",
        "scope": "default",
        "version_no": 1,
        "commission_rate_pct": "2",
        "platform_share_pct": "60",
        "broker_share_pct": "40",
        "effective_from": "1970-01-01T00:00:00Z",
        "status": "in_force",
        "reason": "Tarifa base del catálogo (RF-43)",
        "created_by": null,
        "created_at": "2026-11-24T13:56:48.047067Z",
        "canceled_at": null,
        "canceled_by": null,
        "cancel_reason": null
      },
      "origin": "default",
      "scheduled": []
    },
    {
      "scope": "OTC",
      "terms": {
        "fee_version_id": "00000000-0000-0000-0000-000000000701",
        "commission_rate_pct": "2",
        "platform_share_pct": "60"
      },
      "current": {
        "id": "00000000-0000-0000-0000-000000000701",
        "scope": "default",
        "version_no": 1,
        "commission_rate_pct": "2",
        "platform_share_pct": "60",
        "broker_share_pct": "40",
        "effective_from": "1970-01-01T00:00:00Z",
        "status": "in_force",
        "reason": "Tarifa base del catálogo (RF-43)",
        "created_by": null,
        "created_at": "2026-11-24T13:56:48.047067Z",
        "canceled_at": null,
        "canceled_by": null,
        "cancel_reason": null
      },
      "origin": "default",
      "scheduled": []
    }
  ]
}
```


### 40. Cancelar tarifa futura

**Actor:** `admin2`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/admin/fee-schedules/NASDAQ/versions/93eb4361-d37c-4e50-b5bb-24ea329aab3c/cancel
```

JSON enviado:

```json
{
  "reason": "E2E MOD07: restauración, cancelar tarifa de prueba",
  "totp_code": "<REDACTED>"
}
```

Respuesta **HTTP 200** (17.49 ms). Request ID: `44ec02d9-677a-4846-a3d9-aad65adaf91c`.

```json
{
  "id": "93eb4361-d37c-4e50-b5bb-24ea329aab3c",
  "scope": "NASDAQ",
  "version_no": 1,
  "commission_rate_pct": "2.5",
  "platform_share_pct": "65",
  "broker_share_pct": "35",
  "effective_from": "2026-12-01T14:01:25.284719Z",
  "status": "canceled",
  "reason": "E2E MOD07 local: tarifa futura temporal",
  "created_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
  "created_at": "2026-11-24T14:01:25.312275Z",
  "canceled_at": "2026-11-24T14:01:30.216860Z",
  "canceled_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
  "cancel_reason": "E2E MOD07: restauración, cancelar tarifa de prueba"
}
```


### 41. Tarifa cancelada no altera cotización actual

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/commissions/quote?symbol=AAPL&side=buy&qty=10&price=187.35&with_broker=true
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (8.87 ms). Request ID: `afddfb49-3d21-4289-a8bb-5427add7edfd`.

```json
{
  "fee_version_id": "00000000-0000-0000-0000-000000000701",
  "commission_rate_pct": "2",
  "platform_share_pct": "60",
  "gross_amount": "1873.5",
  "commission": "37.47",
  "platform_share": "22.48",
  "broker_share": "14.99",
  "total": "1910.97",
  "net": null,
  "symbol": "AAPL",
  "market": "NASDAQ",
  "binding": false,
  "quoted_at": "2026-11-24T14:01:30.231691Z"
}
```


### 42. Dependencia real de órdenes: preview

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/orders/preview
```

JSON enviado:

```json
{
  "symbol": "AAPL",
  "side": "buy",
  "qty": "1",
  "type": "limit",
  "limit_price": "1.00",
  "time_in_force": "day",
  "schedule_if_closed": true,
  "confirmed": true
}
```

Respuesta **HTTP 200** (5123.34 ms). Request ID: `051d952d-883f-458e-b47d-837c75ddbe65`.

```json
{
  "reference_price": "347.1",
  "estimated_amount": "1.02",
  "reference_commission": "0.02",
  "reference_commission_estimated": true,
  "available_buying_power": "1143.92",
  "requires_extra_authorization": false,
  "authorization_method": "none",
  "market_open": false,
  "scheduled_for": "2026-11-24T09:30:00-05:00"
}
```


### 43. Crear orden sandbox limitada USD 1 (términos congelados)

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[201]`.

```http
POST https://127.0.0.1:8447/api/v1/orders
```

Encabezados adicionales:

```json
{
  "Idempotency-Key": "mod07-local-6ac1d346-dba8-45c9-b32a-8422daf84719"
}
```

JSON enviado:

```json
{
  "symbol": "AAPL",
  "side": "buy",
  "qty": "1",
  "type": "limit",
  "limit_price": "1.00",
  "time_in_force": "day",
  "schedule_if_closed": true,
  "confirmed": true
}
```

Respuesta **HTTP 201** (449.26 ms). Request ID: `57afecaf-1407-4ba3-a8af-df6ac0385d2f`.

```json
{
  "id": "be2036d3-f849-44af-9acf-9714dbc89bca",
  "status": "PENDING",
  "status_cause": null,
  "provider_status": null,
  "created_at": "2026-11-24T14:01:35.369136Z",
  "updated_at": "2026-11-24T14:01:35.369136Z",
  "symbol": "AAPL",
  "exchange": "NASDAQ",
  "side": "buy",
  "qty": "1.000000000",
  "filled_qty": "0.000000000",
  "filled_avg_price": null,
  "fully_filled": false,
  "type": "limit",
  "order_class": "simple",
  "time_in_force": "day",
  "limit_price": "1.0000",
  "stop_price": null,
  "trail_price": null,
  "trail_percent": null,
  "reference_price": "347.1",
  "estimated_amount": "1.020000000",
  "scheduled_for": "2026-11-24T14:30:00Z",
  "returned_for_changes": false,
  "alpaca_order_id": null,
  "completed_at": null,
  "broker_id": null,
  "broker_signed_at": null,
  "fee_version_id": "00000000-0000-0000-0000-000000000701",
  "commission_rate_pct": "2.0000",
  "platform_share_pct": "60.00",
  "reference_commission": "0.02",
  "reference_commission_estimated": true,
  "legs": [],
  "executions": [],
  "events": [
    {
      "id": "c35e2495-2648-4990-8b4c-6fb615061b49",
      "from_status": null,
      "to_status": "PENDING",
      "cause": "created",
      "actor_type": "investor",
      "actor_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "metadata": {},
      "at": "2026-11-24T14:01:35.369136Z"
    }
  ],
  "reservation": {
    "kind": "usd",
    "symbol": "AAPL",
    "amount": "1.020000000",
    "status": "active",
    "updated_at": "2026-11-24T14:01:35.369136Z"
  },
  "reauthorizations": [],
  "cancels": [],
  "review_comments": []
}
```


### 44. Cancelar orden de prueba

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200, 202]`.

```http
POST https://127.0.0.1:8447/api/v1/orders/be2036d3-f849-44af-9acf-9714dbc89bca/cancel
```

JSON enviado:

```json
{
  "reason": "other",
  "reason_text": "E2E MOD07: limpiar orden sandbox",
  "confirmed": true
}
```

Respuesta **HTTP 200** (22.61 ms). Request ID: `f7549b1b-a73d-41fa-861c-f069ed5cbcc6`.

```json
{
  "id": "be2036d3-f849-44af-9acf-9714dbc89bca",
  "status": "CANCELED",
  "status_cause": "user_canceled",
  "provider_status": null,
  "created_at": "2026-11-24T14:01:35.369136Z",
  "updated_at": "2026-11-24T14:01:35.815415Z",
  "symbol": "AAPL",
  "exchange": "NASDAQ",
  "side": "buy",
  "qty": "1.000000000",
  "filled_qty": "0.000000000",
  "filled_avg_price": null,
  "fully_filled": false,
  "type": "limit",
  "order_class": "simple",
  "time_in_force": "day",
  "limit_price": "1.0000",
  "stop_price": null,
  "trail_price": null,
  "trail_percent": null,
  "reference_price": "347.1",
  "estimated_amount": "1.020000000",
  "scheduled_for": "2026-11-24T14:30:00Z",
  "returned_for_changes": false,
  "alpaca_order_id": null,
  "completed_at": null,
  "broker_id": null,
  "broker_signed_at": null,
  "fee_version_id": "00000000-0000-0000-0000-000000000701",
  "commission_rate_pct": "2.0000",
  "platform_share_pct": "60.00",
  "reference_commission": "0.02",
  "reference_commission_estimated": true,
  "legs": [],
  "executions": [],
  "events": [
    {
      "id": "c35e2495-2648-4990-8b4c-6fb615061b49",
      "from_status": null,
      "to_status": "PENDING",
      "cause": "created",
      "actor_type": "investor",
      "actor_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "metadata": {},
      "at": "2026-11-24T14:01:35.369136Z"
    },
    {
      "id": "f72f03c6-d448-4abc-a137-debe49a3d0b2",
      "from_status": "PENDING",
      "to_status": "CANCELED",
      "cause": "user_canceled",
      "actor_type": "investor",
      "actor_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "metadata": {},
      "at": "2026-11-24T14:01:35.815415Z"
    }
  ],
  "reservation": {
    "kind": "usd",
    "symbol": "AAPL",
    "amount": "1.020000000",
    "status": "released",
    "updated_at": "2026-11-24T14:01:35.824103Z"
  },
  "reauthorizations": [],
  "cancels": [
    {
      "id": "7013013b-db37-4c8a-b847-60eb3ed1512c",
      "previous_status": "PENDING",
      "reason": "other",
      "reason_text": "E2E MOD07: limpiar orden sandbox",
      "confirmed": true,
      "requested_at": "2026-11-24T14:01:35.815415Z",
      "outcome": "applied"
    }
  ],
  "review_comments": []
}
```


### 45. Cadena de custodia de orden real

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/audit-trail/orders/be2036d3-f849-44af-9acf-9714dbc89bca
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (12.82 ms). Request ID: `2d980f5b-1f7c-4ec0-9c1f-8bbc8536958a`.

```json
{
  "order": {
    "id": "be2036d3-f849-44af-9acf-9714dbc89bca",
    "status": "CANCELED",
    "status_cause": "user_canceled",
    "provider_status": null,
    "created_at": "2026-11-24T14:01:35.369136Z",
    "updated_at": "2026-11-24T14:01:35.815415Z",
    "symbol": "AAPL",
    "exchange": "NASDAQ",
    "side": "buy",
    "qty": "1",
    "filled_qty": "0",
    "filled_avg_price": null,
    "fully_filled": false,
    "type": "limit",
    "order_class": "simple",
    "time_in_force": "day",
    "limit_price": "1",
    "stop_price": null,
    "trail_price": null,
    "trail_percent": null,
    "reference_price": "347.1",
    "estimated_amount": "1.02",
    "scheduled_for": "2026-11-24T14:30:00Z",
    "returned_for_changes": false,
    "alpaca_order_id": null,
    "completed_at": null,
    "broker_id": null,
    "broker_signed_at": null,
    "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
    "client_order_id": "be2036d3-f849-44af-9acf-9714dbc89bca",
    "fee_version_id": "00000000-0000-0000-0000-000000000701",
    "commission_rate_pct": "2",
    "platform_share_pct": "60",
    "submit_attempted_at": null,
    "scheduled_session_end": "2026-11-24T21:00:00Z"
  },
  "events": [
    {
      "id": "c35e2495-2648-4990-8b4c-6fb615061b49",
      "from_status": null,
      "to_status": "PENDING",
      "cause": "created",
      "actor_type": "investor",
      "actor_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "metadata": {},
      "at": "2026-11-24T14:01:35.369136Z"
    },
    {
      "id": "f72f03c6-d448-4abc-a137-debe49a3d0b2",
      "from_status": "PENDING",
      "to_status": "CANCELED",
      "cause": "user_canceled",
      "actor_type": "investor",
      "actor_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "metadata": {},
      "at": "2026-11-24T14:01:35.815415Z"
    }
  ],
  "executions": [],
  "cancel_requests": [
    {
      "id": "7013013b-db37-4c8a-b847-60eb3ed1512c",
      "previous_status": "PENDING",
      "reason": "other",
      "reason_text": "E2E MOD07: limpiar orden sandbox",
      "confirmed": true,
      "requested_at": "2026-11-24T14:01:35.815415Z",
      "outcome": "applied"
    }
  ],
  "reauthorizations": [],
  "proposals": [],
  "created_by": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
  "authorization_method": null,
  "signed_by": null,
  "signed_at": null,
  "first_submitted_at": null
}
```


### 46. /api/v1/admin/audit-trail/orders/6219ac00-2158-4f96-b784-10eb1716b742

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[404]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/audit-trail/orders/6219ac00-2158-4f96-b784-10eb1716b742
```

JSON enviado:

```json
null
```

Respuesta **HTTP 404** (5.26 ms). Request ID: `c341a457-3639-4e2f-94dc-b2acbbe161b0`.

```json
{
  "code": "<REDACTED>",
  "message": "Resource not found.",
  "details": {
    "resource": "order"
  }
}
```


### 47. Activar halt NASDAQ

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[201]`.

```http
POST https://127.0.0.1:8447/api/v1/admin/trading-halts
```

JSON enviado:

```json
{
  "scope": "NASDAQ",
  "ends_at": "2026-11-24T14:11:35.855321+00:00",
  "reason": "E2E MOD07 local: bloqueo temporal",
  "totp_code": "<REDACTED>"
}
```

Respuesta **HTTP 201** (16.87 ms). Request ID: `292d9e52-55ab-427f-8ca1-a88301e7760e`.

```json
{
  "id": "7176011e-7850-4d63-aaf6-0f5e77a7b901",
  "scope": "NASDAQ",
  "status": "active",
  "reason": "E2E MOD07 local: bloqueo temporal",
  "starts_at": "2026-11-24T14:01:35.860283Z",
  "ends_at": "2026-11-24T14:11:35.855321Z",
  "created_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
  "created_at": "2026-11-24T14:01:35.860283Z",
  "released_at": null,
  "released_by": null,
  "release_reason": null
}
```


### 48. /api/v1/admin/trading-halts

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/trading-halts?scope=NASDAQ&status=active
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (5.73 ms). Request ID: `0d631aca-61fe-4eae-b977-02a1f2aa68db`.

```json
{
  "items": [
    {
      "id": "7176011e-7850-4d63-aaf6-0f5e77a7b901",
      "scope": "NASDAQ",
      "status": "active",
      "reason": "E2E MOD07 local: bloqueo temporal",
      "starts_at": "2026-11-24T14:01:35.860283Z",
      "ends_at": "2026-11-24T14:11:35.855321Z",
      "created_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
      "created_at": "2026-11-24T14:01:35.860283Z",
      "released_at": null,
      "released_by": null,
      "release_reason": null
    }
  ],
  "next_cursor": null
}
```


### 49. Vista de halt sin metadatos privados

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/trading-halts/active
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (5.95 ms). Request ID: `8292ee9b-7f2e-430e-823d-2f15d2fc5204`.

```json
[
  {
    "scope": "NASDAQ",
    "starts_at": "2026-11-24T14:01:35.860283Z",
    "ends_at": "2026-11-24T14:11:35.855321Z"
  }
]
```


### 50. Halt bloquea órdenes

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[503]`.

```http
POST https://127.0.0.1:8447/api/v1/orders/preview
```

JSON enviado:

```json
{
  "symbol": "AAPL",
  "side": "buy",
  "qty": "1",
  "type": "limit",
  "limit_price": "1.00",
  "time_in_force": "day",
  "schedule_if_closed": true,
  "confirmed": true
}
```

Respuesta **HTTP 503** (15.06 ms). Request ID: `729dcc45-1fb0-4ddb-bee3-b0501730732c`.

```json
{
  "code": "<REDACTED>",
  "message": "Trading is currently restricted.",
  "details": {
    "halt_id": "7176011e-7850-4d63-aaf6-0f5e77a7b901",
    "scope": "NASDAQ",
    "ends_at": "2026-11-24T14:11:35.855321+00:00"
  }
}
```


### 51. Halt no bloquea lecturas

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/commissions/quote?symbol=AAPL&side=buy&qty=10&price=187.35&with_broker=true
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (10.75 ms). Request ID: `5012bbe4-2cca-4e74-ac25-17c95be2d2b8`.

```json
{
  "fee_version_id": "00000000-0000-0000-0000-000000000701",
  "commission_rate_pct": "2",
  "platform_share_pct": "60",
  "gross_amount": "1873.5",
  "commission": "37.47",
  "platform_share": "22.48",
  "broker_share": "14.99",
  "total": "1910.97",
  "net": null,
  "symbol": "AAPL",
  "market": "NASDAQ",
  "binding": false,
  "quoted_at": "2026-11-24T14:01:35.911741Z"
}
```


### 52. Liberar halt

**Actor:** `admin2`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/admin/trading-halts/7176011e-7850-4d63-aaf6-0f5e77a7b901/release
```

JSON enviado:

```json
{
  "reason": "E2E MOD07: liberar bloqueo de prueba",
  "totp_code": "<REDACTED>"
}
```

Respuesta **HTTP 200** (36.59 ms). Request ID: `84d3d1b2-18fa-4b82-8f93-78e29628a159`.

```json
{
  "id": "7176011e-7850-4d63-aaf6-0f5e77a7b901",
  "scope": "NASDAQ",
  "status": "released",
  "reason": "E2E MOD07 local: bloqueo temporal",
  "starts_at": "2026-11-24T14:01:35.860283Z",
  "ends_at": "2026-11-24T14:11:35.855321Z",
  "created_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
  "created_at": "2026-11-24T14:01:35.860283Z",
  "released_at": "2026-11-24T14:02:00.248584Z",
  "released_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
  "release_reason": "E2E MOD07: liberar bloqueo de prueba"
}
```


### 53. Órdenes tras liberar halt

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/orders/preview
```

JSON enviado:

```json
{
  "symbol": "AAPL",
  "side": "buy",
  "qty": "1",
  "type": "limit",
  "limit_price": "1.00",
  "time_in_force": "day",
  "schedule_if_closed": true,
  "confirmed": true
}
```

Respuesta **HTTP 200** (949.49 ms). Request ID: `a77b37d4-bd0b-46fd-b90d-3b08e1ffc565`.

```json
{
  "reference_price": "347.1",
  "estimated_amount": "1.02",
  "reference_commission": "0.02",
  "reference_commission_estimated": true,
  "available_buying_power": "1143.92",
  "requires_extra_authorization": false,
  "authorization_method": "none",
  "market_open": false,
  "scheduled_for": "2026-11-24T09:30:00-05:00"
}
```


### 54. Restringir negociación del investor

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[201]`.

```http
POST https://127.0.0.1:8447/api/v1/admin/compliance/restrictions
```

JSON enviado:

```json
{
  "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
  "reason": "E2E MOD07 local: restricción temporal",
  "evidence_text": "Prueba técnica autorizada; no constituye sospecha real.",
  "evidence_refs": [],
  "totp_code": "<REDACTED>"
}
```

Respuesta **HTTP 201** (41.15 ms). Request ID: `3437ba21-7fad-4444-a2b6-9f598baa5547`.

```json
{
  "id": "7e0e3186-8a90-4fa2-97b7-4b8c8d180c6e",
  "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
  "restriction_type": "trading",
  "status": "active",
  "reason": "E2E MOD07 local: restricción temporal",
  "evidence_text": "Prueba técnica autorizada; no constituye sospecha real.",
  "evidence_refs": [],
  "restricted_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
  "restricted_at": "2026-11-24T14:02:01.246566Z",
  "lifted_at": null,
  "lifted_by": null,
  "lift_reason": null,
  "lift_evidence_text": null,
  "lift_evidence_refs": null
}
```


### 55. /api/v1/admin/compliance/restrictions

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/compliance/restrictions?user_id=c0674321-9a64-4f13-9070-e57dfb35b4e8&status=active
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (13.58 ms). Request ID: `be943da9-42f8-41e0-be34-2b8246d0e624`.

```json
{
  "items": [
    {
      "id": "7e0e3186-8a90-4fa2-97b7-4b8c8d180c6e",
      "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "restriction_type": "trading",
      "status": "active",
      "reason": "E2E MOD07 local: restricción temporal",
      "evidence_text": "Prueba técnica autorizada; no constituye sospecha real.",
      "evidence_refs": [],
      "restricted_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
      "restricted_at": "2026-11-24T14:02:01.246566Z",
      "lifted_at": null,
      "lifted_by": null,
      "lift_reason": null,
      "lift_evidence_text": null,
      "lift_evidence_refs": null
    }
  ],
  "next_cursor": null
}
```


### 56. Restricción bloquea negociación

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[403]`.

```http
POST https://127.0.0.1:8447/api/v1/orders/preview
```

JSON enviado:

```json
{
  "symbol": "AAPL",
  "side": "buy",
  "qty": "1",
  "type": "limit",
  "limit_price": "1.00",
  "time_in_force": "day",
  "schedule_if_closed": true,
  "confirmed": true
}
```

Respuesta **HTTP 403** (26.65 ms). Request ID: `08963b30-393c-4bd5-a6cc-612ff54880d7`.

```json
{
  "code": "<REDACTED>",
  "message": "Trading is currently restricted.",
  "details": {}
}
```


### 57. Restricción conserva acceso a perfil

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/users/me
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (142.4 ms). Request ID: `4a43ba30-3ba6-4503-b726-1f6d2911f004`.

```json
{
  "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
  "first_names": "Prueba",
  "last_names": "Ti",
  "email": "investor.ti@accionesud.com",
  "phone": "+573001112236",
  "country": "CO",
  "account_status": "active",
  "registered_at": "2026-11-11T15:04:21.760287Z",
  "contracted_plan": null,
  "is_premium": true,
  "broker_requested": false,
  "associated_broker": null,
  "roles": [
    "investor"
  ],
  "kyc_status": "ACTIVE",
  "kyc_status_unavailable": false,
  "interests": [
    "NASDAQ",
    "Technology"
  ],
  "investor_level": "beginner",
  "mfa_enrolled": true
}
```


### 58. Rehabilitar cuenta

**Actor:** `admin2`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/admin/compliance/restrictions/7e0e3186-8a90-4fa2-97b7-4b8c8d180c6e/lift
```

JSON enviado:

```json
{
  "reason": "E2E MOD07: rehabilitación",
  "evidence_text": "Finalizó la prueba autorizada.",
  "evidence_refs": [],
  "totp_code": "<REDACTED>"
}
```

Respuesta **HTTP 200** (17.21 ms). Request ID: `28c29cf8-6824-428b-b260-2878ed0bb27a`.

```json
{
  "id": "7e0e3186-8a90-4fa2-97b7-4b8c8d180c6e",
  "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
  "restriction_type": "trading",
  "status": "lifted",
  "reason": "E2E MOD07 local: restricción temporal",
  "evidence_text": "Prueba técnica autorizada; no constituye sospecha real.",
  "evidence_refs": [],
  "restricted_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
  "restricted_at": "2026-11-24T14:02:01.246566Z",
  "lifted_at": "2026-11-24T14:02:30.242811Z",
  "lifted_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
  "lift_reason": "E2E MOD07: rehabilitación",
  "lift_evidence_text": "Finalizó la prueba autorizada.",
  "lift_evidence_refs": []
}
```


### 59. Detectar operaciones atípicas reales

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/compliance/atypical-operations?from=2026-11-01&to=2026-11-24&page_size=2
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (11.8 ms). Request ID: `9c77ead1-5bf3-47ed-8338-f86bc34c1fe4`.

```json
{
  "items": [],
  "next_cursor": null,
  "rules_version": "atypical-v2",
  "configuration": {
    "absolute_usd": "10000",
    "multiplier": "3",
    "window_days": 90,
    "min_history": 5,
    "frequency_count": 20,
    "frequency_seconds": 300,
    "cancellation_count": 10,
    "cancellation_seconds": 300,
    "rejection_count": 5,
    "rejection_seconds": 3600
  }
}
```


### 60. Generar reporte de cumplimiento

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[201]`.

```http
POST https://127.0.0.1:8447/api/v1/admin/compliance/users/c0674321-9a64-4f13-9070-e57dfb35b4e8/audit-reports
```

JSON enviado:

```json
{
  "from": "2026-11-01",
  "to": "2026-11-24"
}
```

Respuesta **HTTP 201** (22.74 ms). Request ID: `c278e836-e3f2-4324-a2fb-dd446b496203`.

```json
{
  "id": "01fe0358-f3e1-45c8-8bb7-d9f498575660",
  "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
  "period_from": "2026-11-01",
  "period_to": "2026-11-24",
  "rules_version": "atypical-v2",
  "content": {
    "user": {
      "id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "created_at": "2026-11-11T15:04:21.760287+00:00",
      "roles": [
        "investor"
      ]
    },
    "period": {
      "from": "2026-11-01",
      "to": "2026-11-24"
    },
    "activity": [
      {
        "source": "admin",
        "action": "account_rehabilitated",
        "count": 1
      },
      {
        "source": "admin",
        "action": "account_restricted",
        "count": 1
      },
      {
        "source": "auth",
        "action": "login.success",
        "count": 1
      },
      {
        "source": "auth",
        "action": "mfa_verify.success",
        "count": 1
      },
      {
        "source": "orders",
        "action": "created",
        "count": 1
      },
      {
        "source": "orders",
        "action": "user_canceled",
        "count": 1
      }
    ],
    "executions_count": 0,
    "volume_usd": "0",
    "commission_usd": "0",
    "historical_terms_unknown_count": 0,
    "average": {
      "execution_count": "0",
      "volume_usd": "0"
    },
    "ratios": {
      "execution_count": null,
      "volume": null
    },
    "atypical_operations": [],
    "restrictions": [
      {
        "id": "7e0e3186-8a90-4fa2-97b7-4b8c8d180c6e",
        "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
        "restriction_type": "trading",
        "reason": "E2E MOD07 local: restricción temporal",
        "evidence_text": "Prueba técnica autorizada; no constituye sospecha real.",
        "evidence_refs": [],
        "restricted_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
        "restricted_at": "2026-11-24T14:02:01.246566+00:00",
        "lifted_at": "2026-11-24T14:02:30.242811+00:00",
        "lifted_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
        "lift_reason": "E2E MOD07: rehabilitación",
        "lift_evidence_text": "Finalizó la prueba autorizada.",
        "lift_evidence_refs": []
      }
    ],
    "rules_version": "atypical-v2",
    "configuration": {
      "absolute_usd": "10000",
      "multiplier": "3",
      "window_days": 90,
      "min_history": 5,
      "frequency_count": 20,
      "frequency_seconds": 300,
      "cancellation_count": 10,
      "cancellation_seconds": 300,
      "rejection_count": 5,
      "rejection_seconds": 3600
    }
  },
  "content_sha256": "94f30aa2352aeccd7cb6970a4b0cba2ff91268a7f99ffa6dbcd7c624e731e351",
  "generated_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
  "generated_at": "2026-11-24T14:02:30.265209Z"
}
```


### 61. Leer reporte persistido

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/compliance/audit-reports/01fe0358-f3e1-45c8-8bb7-d9f498575660
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (7.85 ms). Request ID: `a594afd6-cf56-4be6-b9c2-734975f5bc1d`.

```json
{
  "id": "01fe0358-f3e1-45c8-8bb7-d9f498575660",
  "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
  "period_from": "2026-11-01",
  "period_to": "2026-11-24",
  "rules_version": "atypical-v2",
  "content": {
    "user": {
      "id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "roles": [
        "investor"
      ],
      "created_at": "2026-11-11T15:04:21.760287+00:00"
    },
    "period": {
      "to": "2026-11-24",
      "from": "2026-11-01"
    },
    "ratios": {
      "volume": null,
      "execution_count": null
    },
    "average": {
      "volume_usd": "0",
      "execution_count": "0"
    },
    "activity": [
      {
        "count": 1,
        "action": "account_rehabilitated",
        "source": "admin"
      },
      {
        "count": 1,
        "action": "account_restricted",
        "source": "admin"
      },
      {
        "count": 1,
        "action": "login.success",
        "source": "auth"
      },
      {
        "count": 1,
        "action": "mfa_verify.success",
        "source": "auth"
      },
      {
        "count": 1,
        "action": "created",
        "source": "orders"
      },
      {
        "count": 1,
        "action": "user_canceled",
        "source": "orders"
      }
    ],
    "volume_usd": "0",
    "restrictions": [
      {
        "id": "7e0e3186-8a90-4fa2-97b7-4b8c8d180c6e",
        "reason": "E2E MOD07 local: restricción temporal",
        "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
        "lifted_at": "2026-11-24T14:02:30.242811+00:00",
        "lifted_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
        "lift_reason": "E2E MOD07: rehabilitación",
        "evidence_refs": [],
        "evidence_text": "Prueba técnica autorizada; no constituye sospecha real.",
        "restricted_at": "2026-11-24T14:02:01.246566+00:00",
        "restricted_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
        "restriction_type": "trading",
        "lift_evidence_refs": [],
        "lift_evidence_text": "Finalizó la prueba autorizada."
      }
    ],
    "configuration": {
      "multiplier": "3",
      "min_history": 5,
      "window_days": 90,
      "absolute_usd": "10000",
      "frequency_count": 20,
      "rejection_count": 5,
      "frequency_seconds": 300,
      "rejection_seconds": 3600,
      "cancellation_count": 10,
      "cancellation_seconds": 300
    },
    "rules_version": "atypical-v2",
    "commission_usd": "0",
    "executions_count": 0,
    "atypical_operations": [],
    "historical_terms_unknown_count": 0
  },
  "content_sha256": "94f30aa2352aeccd7cb6970a4b0cba2ff91268a7f99ffa6dbcd7c624e731e351",
  "generated_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
  "generated_at": "2026-11-24T14:02:30.265209Z"
}
```


### 62. /api/v1/admin/compliance/users/c0674321-9a64-4f13-9070-e57dfb35b4e8/audit-reports

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/compliance/users/c0674321-9a64-4f13-9070-e57dfb35b4e8/audit-reports
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (8.65 ms). Request ID: `4ac497f6-0a9f-4acf-9ecf-50bd0de4807f`.

```json
{
  "items": [
    {
      "id": "01fe0358-f3e1-45c8-8bb7-d9f498575660",
      "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "period_from": "2026-11-01",
      "period_to": "2026-11-24",
      "rules_version": "atypical-v2",
      "content": {
        "user": {
          "id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
          "roles": [
            "investor"
          ],
          "created_at": "2026-11-11T15:04:21.760287+00:00"
        },
        "period": {
          "to": "2026-11-24",
          "from": "2026-11-01"
        },
        "ratios": {
          "volume": null,
          "execution_count": null
        },
        "average": {
          "volume_usd": "0",
          "execution_count": "0"
        },
        "activity": [
          {
            "count": 1,
            "action": "account_rehabilitated",
            "source": "admin"
          },
          {
            "count": 1,
            "action": "account_restricted",
            "source": "admin"
          },
          {
            "count": 1,
            "action": "login.success",
            "source": "auth"
          },
          {
            "count": 1,
            "action": "mfa_verify.success",
            "source": "auth"
          },
          {
            "count": 1,
            "action": "created",
            "source": "orders"
          },
          {
            "count": 1,
            "action": "user_canceled",
            "source": "orders"
          }
        ],
        "volume_usd": "0",
        "restrictions": [
          {
            "id": "7e0e3186-8a90-4fa2-97b7-4b8c8d180c6e",
            "reason": "E2E MOD07 local: restricción temporal",
            "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
            "lifted_at": "2026-11-24T14:02:30.242811+00:00",
            "lifted_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
            "lift_reason": "E2E MOD07: rehabilitación",
            "evidence_refs": [],
            "evidence_text": "Prueba técnica autorizada; no constituye sospecha real.",
            "restricted_at": "2026-11-24T14:02:01.246566+00:00",
            "restricted_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
            "restriction_type": "trading",
            "lift_evidence_refs": [],
            "lift_evidence_text": "Finalizó la prueba autorizada."
          }
        ],
        "configuration": {
          "multiplier": "3",
          "min_history": 5,
          "window_days": 90,
          "absolute_usd": "10000",
          "frequency_count": 20,
          "rejection_count": 5,
          "frequency_seconds": 300,
          "rejection_seconds": 3600,
          "cancellation_count": 10,
          "cancellation_seconds": 300
        },
        "rules_version": "atypical-v2",
        "commission_usd": "0",
        "executions_count": 0,
        "atypical_operations": [],
        "historical_terms_unknown_count": 0
      },
      "content_sha256": "94f30aa2352aeccd7cb6970a4b0cba2ff91268a7f99ffa6dbcd7c624e731e351",
      "generated_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
      "generated_at": "2026-11-24T14:02:30.265209Z"
    }
  ],
  "next_cursor": null
}
```


### 63. Calcular KPIs y guardar snapshot

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/kpis?from=2026-11-01&to=2026-11-24&refresh=true
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (19.52 ms). Request ID: `9fdd0af7-9d6b-4cfa-a8f8-c690d0b3e299`.

```json
{
  "period": {
    "from": "2026-11-01",
    "to": "2026-11-24",
    "time_zone": "America/New_York"
  },
  "definitions_version": "kpi-v1",
  "computed_at": "2026-11-24T14:02:30.308503Z",
  "as_of": "2026-11-24T14:02:30.308503Z",
  "cache_hit": false,
  "stale": false,
  "metrics": {
    "registered_users": {
      "value": 5,
      "unit": "users",
      "definition": "kpi-v1.registered_users"
    },
    "new_registrations": {
      "value": 5,
      "unit": "users",
      "definition": "kpi-v1.new_registrations",
      "by_level": {
        "unspecified": 4,
        "beginner": 1
      },
      "by_interest": {
        "Technology": 1,
        "NASDAQ": 1
      }
    },
    "active_users": {
      "value": 5,
      "unit": "users",
      "definition": "kpi-v1.active_users"
    },
    "traded_volume_usd": {
      "value": "0",
      "unit": "USD",
      "definition": "kpi-v1.traded_volume_usd",
      "by_market": {},
      "by_side": {}
    },
    "executions_count": {
      "value": 0,
      "unit": "executions",
      "definition": "kpi-v1.executions_count",
      "by_market": {},
      "by_side": {}
    },
    "platform_commissions_usd": {
      "value": "0",
      "unit": "USD",
      "definition": "kpi-v1.platform_commissions_usd",
      "by_market": {},
      "historical_terms_unknown_count": 0,
      "complete": true
    },
    "active_subscriptions": {
      "value": 0,
      "unit": "subscriptions",
      "definition": "kpi-v1.active_subscriptions"
    },
    "revenue_by_source": {
      "value": "0",
      "unit": "USD",
      "definition": "kpi-v1.revenue_by_source",
      "commissions": "0",
      "subscriptions": "0",
      "excluded_non_usd_payments": 0,
      "complete": true
    },
    "users_by_type": {
      "value": 1,
      "unit": "users",
      "definition": "kpi-v1.users_by_type",
      "by_level": {
        "beginner": 1
      },
      "by_broker": {
        "without_broker": 1
      }
    }
  }
}
```


### 64. Reutilizar caché de KPIs

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/kpis?from=2026-11-01&to=2026-11-24
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (6.01 ms). Request ID: `5ae9e628-62cb-40ee-a8ec-8e1269b04e1f`.

```json
{
  "period": {
    "from": "2026-11-01",
    "to": "2026-11-24",
    "time_zone": "America/New_York"
  },
  "definitions_version": "kpi-v1",
  "computed_at": "2026-11-24T14:02:30.308503Z",
  "as_of": "2026-11-24T14:02:30.308503Z",
  "cache_hit": true,
  "stale": false,
  "metrics": {
    "active_users": {
      "unit": "users",
      "value": 5,
      "definition": "kpi-v1.active_users"
    },
    "users_by_type": {
      "unit": "users",
      "value": 1,
      "by_level": {
        "beginner": 1
      },
      "by_broker": {
        "without_broker": 1
      },
      "definition": "kpi-v1.users_by_type"
    },
    "executions_count": {
      "unit": "executions",
      "value": 0,
      "by_side": {},
      "by_market": {},
      "definition": "kpi-v1.executions_count"
    },
    "registered_users": {
      "unit": "users",
      "value": 5,
      "definition": "kpi-v1.registered_users"
    },
    "new_registrations": {
      "unit": "users",
      "value": 5,
      "by_level": {
        "beginner": 1,
        "unspecified": 4
      },
      "definition": "kpi-v1.new_registrations",
      "by_interest": {
        "NASDAQ": 1,
        "Technology": 1
      }
    },
    "revenue_by_source": {
      "unit": "USD",
      "value": "0",
      "complete": true,
      "definition": "kpi-v1.revenue_by_source",
      "commissions": "0",
      "subscriptions": "0",
      "excluded_non_usd_payments": 0
    },
    "traded_volume_usd": {
      "unit": "USD",
      "value": "0",
      "by_side": {},
      "by_market": {},
      "definition": "kpi-v1.traded_volume_usd"
    },
    "active_subscriptions": {
      "unit": "subscriptions",
      "value": 0,
      "definition": "kpi-v1.active_subscriptions"
    },
    "platform_commissions_usd": {
      "unit": "USD",
      "value": "0",
      "complete": true,
      "by_market": {},
      "definition": "kpi-v1.platform_commissions_usd",
      "historical_terms_unknown_count": 0
    }
  }
}
```


### 65. Rastro unificado: primera página

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/audit-trail?from=2026-11-01&to=2026-11-24&source=admin&page_size=2
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (8.27 ms). Request ID: `a8aa4d45-02ef-4881-876a-84700d3ecbc2`.

```json
{
  "items": [
    {
      "source": "admin",
      "event_id": "e7a08e71-a2ce-4e88-afee-c63918bc9327",
      "occurred_at": "2026-11-24T14:02:30.265209Z",
      "actor_type": "user",
      "actor_id": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
      "subject_user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "related_user_id": null,
      "action": "compliance_report_generated",
      "entity_type": "user",
      "entity_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "from_state": null,
      "to_state": null,
      "details": {
        "period_to": "2026-11-24",
        "report_id": "01fe0358-f3e1-45c8-8bb7-d9f498575660",
        "period_from": "2026-11-01",
        "rules_version": "atypical-v2",
        "content_sha256": "94f30aa2352aeccd7cb6970a4b0cba2ff91268a7f99ffa6dbcd7c624e731e351"
      },
      "ip_address": "127.0.0.1"
    },
    {
      "source": "admin",
      "event_id": "bf0f4e45-5830-4c78-82dc-210e5868b20f",
      "occurred_at": "2026-11-24T14:02:30.242811Z",
      "actor_type": "user",
      "actor_id": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
      "subject_user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "related_user_id": null,
      "action": "account_rehabilitated",
      "entity_type": "user",
      "entity_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "from_state": null,
      "to_state": null,
      "details": {
        "reason": "E2E MOD07: rehabilitación",
        "evidence": {
          "refs": [],
          "text": "Finalizó la prueba autorizada."
        },
        "restriction_id": "7e0e3186-8a90-4fa2-97b7-4b8c8d180c6e",
        "restriction_type": "trading"
      },
      "ip_address": "127.0.0.1"
    }
  ],
  "next_cursor": "WyIyMDI2LTExLTI0VDE0OjAyOjMwLjI0MjgxMSswMDowMCIsImFkbWluIiwiYmYwZjRlNDUtNTgzMC00Yzc4LTgyZGMtMjEwZTU4NjhiMjBmIl0="
}
```


### 66. Rastro unificado: segunda página

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/audit-trail?from=2026-11-01&to=2026-11-24&source=admin&page_size=2&cursor=WyIyMDI2LTExLTI0VDE0OjAyOjMwLjI0MjgxMSswMDowMCIsImFkbWluIiwiYmYwZjRlNDUtNTgzMC00Yzc4LTgyZGMtMjEwZTU4NjhiMjBmIl0%3D
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (7.85 ms). Request ID: `6a8a11da-e31f-4b43-b652-49602d212728`.

```json
{
  "items": [
    {
      "source": "admin",
      "event_id": "654d0d5f-f81e-4233-9166-36e66818b788",
      "occurred_at": "2026-11-24T14:02:01.246566Z",
      "actor_type": "user",
      "actor_id": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
      "subject_user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "related_user_id": null,
      "action": "account_restricted",
      "entity_type": "user",
      "entity_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "from_state": null,
      "to_state": null,
      "details": {
        "reason": "E2E MOD07 local: restricción temporal",
        "evidence": {
          "refs": [],
          "text": "Prueba técnica autorizada; no constituye sospecha real."
        },
        "restriction_id": "7e0e3186-8a90-4fa2-97b7-4b8c8d180c6e",
        "restriction_type": "trading"
      },
      "ip_address": "127.0.0.1"
    },
    {
      "source": "admin",
      "event_id": "331b75df-cebf-4396-91c4-b0350157ba65",
      "occurred_at": "2026-11-24T14:02:00.248584Z",
      "actor_type": "user",
      "actor_id": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
      "subject_user_id": null,
      "related_user_id": null,
      "action": "trading_halt_released",
      "entity_type": "trading_halt",
      "entity_id": "7176011e-7850-4d63-aaf6-0f5e77a7b901",
      "from_state": null,
      "to_state": null,
      "details": {
        "after": {
          "id": "7176011e-7850-4d63-aaf6-0f5e77a7b901",
          "reason": "E2E MOD07 local: bloqueo temporal",
          "ends_at": "2026-11-24T14:11:35.855321+00:00",
          "starts_at": "2026-11-24T14:01:35.860283+00:00",
          "created_at": "2026-11-24T14:01:35.860283+00:00",
          "created_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
          "market_code": "NASDAQ",
          "released_at": "2026-11-24T14:02:00.248584+00:00",
          "released_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
          "release_reason": "E2E MOD07: liberar bloqueo de prueba"
        },
        "scope": "NASDAQ",
        "before": {
          "id": "7176011e-7850-4d63-aaf6-0f5e77a7b901",
          "reason": "E2E MOD07 local: bloqueo temporal",
          "ends_at": "2026-11-24T14:11:35.855321+00:00",
          "starts_at": "2026-11-24T14:01:35.860283+00:00",
          "created_at": "2026-11-24T14:01:35.860283+00:00",
          "created_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
          "market_code": "NASDAQ",
          "released_at": null,
          "released_by": null,
          "release_reason": null
        },
        "reason": "E2E MOD07: liberar bloqueo de prueba"
      },
      "ip_address": "127.0.0.1"
    }
  ],
  "next_cursor": "WyIyMDI2LTExLTI0VDE0OjAyOjAwLjI0ODU4NCswMDowMCIsImFkbWluIiwiMzMxYjc1ZGYtY2ViZi00Mzk2LTkxYzQtYjAzNTAxNTdiYTY1Il0="
}
```


### 67. /api/v1/admin/audit-trail

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[422]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/audit-trail?from=2026-11-01&to=2026-11-24&source=invalid
```

JSON enviado:

```json
null
```

Respuesta **HTTP 422** (4.62 ms). Request ID: `8f9f1ae9-7224-4f14-94e8-31809d90d8c9`.

```json
{
  "code": "<REDACTED>",
  "message": "Invalid administrative field.",
  "details": {
    "field": "source",
    "reason": "invalid"
  }
}
```


### 68. /api/v1/admin/audit-trail

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[422]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/audit-trail?from=2026-11-01&to=2026-11-24&cursor=bad-cursor
```

JSON enviado:

```json
null
```

Respuesta **HTTP 422** (4.09 ms). Request ID: `d0af4ae3-0ebf-4bc6-9bd0-a91ea0916971`.

```json
{
  "code": "<REDACTED>",
  "message": "Invalid administrative field.",
  "details": {
    "field": "cursor",
    "reason": "invalid"
  }
}
```


### 69. Asignar temporalmente auditor a broker2

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[201]`.

```http
POST https://127.0.0.1:8447/api/v1/admin/users/39bf8e8a-d3ec-4172-82c5-99e9508ffce1/roles
```

JSON enviado:

```json
{
  "role": "auditor",
  "valid_from": "2026-11-24T14:02:30.362044+00:00"
}
```

Respuesta **HTTP 201** (11.96 ms). Request ID: `80c049ed-c33b-4ade-b7a8-67c3ef76700f`.

```json
{
  "id": "6d2d65e7-7c4c-4cf8-9b29-e2dd37f1794e",
  "role": "auditor",
  "valid_from": "2026-11-24T14:02:30.362044Z",
  "valid_to": null,
  "effective": true,
  "status": "ACTIVE",
  "cancelled_at": null,
  "cancelled_by": null
}
```


### 70. Asignar temporalmente analyst a broker

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[201]`.

```http
POST https://127.0.0.1:8447/api/v1/admin/users/19f5fcb4-9a1d-4d3e-affe-96da0057cf2d/roles
```

JSON enviado:

```json
{
  "role": "analyst",
  "valid_from": "2026-11-24T14:02:30.375020+00:00"
}
```

Respuesta **HTTP 201** (9.31 ms). Request ID: `1b2b6edd-0f47-4274-8c4b-7857978bd9e4`.

```json
{
  "id": "46d3ae10-c7ae-469d-960b-381863292043",
  "role": "analyst",
  "valid_from": "2026-11-24T14:02:30.375020Z",
  "valid_to": null,
  "effective": true,
  "status": "ACTIVE",
  "cancelled_at": null,
  "cancelled_by": null
}
```


### 71. Auditor consulta evidencia

**Actor:** `broker2`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/audit-trail?from=2026-11-01&to=2026-11-24&page_size=1
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (10.45 ms). Request ID: `7d05a46e-44c2-456c-bed5-aaf4e7143e26`.

```json
{
  "items": [
    {
      "source": "admin",
      "event_id": "4d77ac6c-f35f-4a33-883d-3909fd434be2",
      "occurred_at": "2026-11-24T14:02:30.378744Z",
      "actor_type": "user",
      "actor_id": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
      "subject_user_id": "19f5fcb4-9a1d-4d3e-affe-96da0057cf2d",
      "related_user_id": null,
      "action": "role_assignment_created",
      "entity_type": "user",
      "entity_id": "19f5fcb4-9a1d-4d3e-affe-96da0057cf2d",
      "from_state": null,
      "to_state": null,
      "details": {
        "role": "analyst",
        "valid_to": null,
        "valid_from": "2026-11-24T14:02:30.375020+00:00",
        "assignment_id": "46d3ae10-c7ae-469d-960b-381863292043"
      },
      "ip_address": null
    }
  ],
  "next_cursor": "WyIyMDI2LTExLTI0VDE0OjAyOjMwLjM3ODc0NCswMDowMCIsImFkbWluIiwiNGQ3N2FjNmMtZjM1Zi00YTMzLTg4M2QtMzkwOWZkNDM0YmUyIl0="
}
```


### 72. Auditor lee cumplimiento

**Actor:** `broker2`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/compliance/restrictions
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (6.2 ms). Request ID: `82d9431c-119f-42db-a527-436575fbd6b5`.

```json
{
  "items": [
    {
      "id": "7e0e3186-8a90-4fa2-97b7-4b8c8d180c6e",
      "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "restriction_type": "trading",
      "status": "lifted",
      "reason": "E2E MOD07 local: restricción temporal",
      "evidence_text": "Prueba técnica autorizada; no constituye sospecha real.",
      "evidence_refs": [],
      "restricted_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
      "restricted_at": "2026-11-24T14:02:01.246566Z",
      "lifted_at": "2026-11-24T14:02:30.242811Z",
      "lifted_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
      "lift_reason": "E2E MOD07: rehabilitación",
      "lift_evidence_text": "Finalizó la prueba autorizada.",
      "lift_evidence_refs": []
    }
  ],
  "next_cursor": null
}
```


### 73. Auditor no accede a BI

**Actor:** `broker2`. **Resultado:** OK; HTTP esperado: `[403]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/kpis?from=2026-11-01&to=2026-11-24
```

JSON enviado:

```json
null
```

Respuesta **HTTP 403** (3.94 ms). Request ID: `779210f9-1186-4dbd-ba5c-934a2b840b03`.

```json
{
  "code": "<REDACTED>",
  "message": "Permission required.",
  "details": null
}
```


### 74. Auditor no restringe

**Actor:** `broker2`. **Resultado:** OK; HTTP esperado: `[403]`.

```http
POST https://127.0.0.1:8447/api/v1/admin/compliance/restrictions
```

JSON enviado:

```json
{
  "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
  "reason": "Debe rechazarse"
}
```

Respuesta **HTTP 403** (3.96 ms). Request ID: `c98aebab-b237-415e-bdb1-0e60c6a672c9`.

```json
{
  "code": "<REDACTED>",
  "message": "Permission required.",
  "details": null
}
```


### 75. Analyst consulta KPIs

**Actor:** `broker`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/kpis?from=2026-11-01&to=2026-11-24
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (8.05 ms). Request ID: `1415cd41-1876-446f-b7fe-1896cb69fb11`.

```json
{
  "period": {
    "from": "2026-11-01",
    "to": "2026-11-24",
    "time_zone": "America/New_York"
  },
  "definitions_version": "kpi-v1",
  "computed_at": "2026-11-24T14:02:30.308503Z",
  "as_of": "2026-11-24T14:02:30.308503Z",
  "cache_hit": true,
  "stale": false,
  "metrics": {
    "active_users": {
      "unit": "users",
      "value": 5,
      "definition": "kpi-v1.active_users"
    },
    "users_by_type": {
      "unit": "users",
      "value": 1,
      "by_level": {
        "beginner": 1
      },
      "by_broker": {
        "without_broker": 1
      },
      "definition": "kpi-v1.users_by_type"
    },
    "executions_count": {
      "unit": "executions",
      "value": 0,
      "by_side": {},
      "by_market": {},
      "definition": "kpi-v1.executions_count"
    },
    "registered_users": {
      "unit": "users",
      "value": 5,
      "definition": "kpi-v1.registered_users"
    },
    "new_registrations": {
      "unit": "users",
      "value": 5,
      "by_level": {
        "beginner": 1,
        "unspecified": 4
      },
      "definition": "kpi-v1.new_registrations",
      "by_interest": {
        "NASDAQ": 1,
        "Technology": 1
      }
    },
    "revenue_by_source": {
      "unit": "USD",
      "value": "0",
      "complete": true,
      "definition": "kpi-v1.revenue_by_source",
      "commissions": "0",
      "subscriptions": "0",
      "excluded_non_usd_payments": 0
    },
    "traded_volume_usd": {
      "unit": "USD",
      "value": "0",
      "by_side": {},
      "by_market": {},
      "definition": "kpi-v1.traded_volume_usd"
    },
    "active_subscriptions": {
      "unit": "subscriptions",
      "value": 0,
      "definition": "kpi-v1.active_subscriptions"
    },
    "platform_commissions_usd": {
      "unit": "USD",
      "value": "0",
      "complete": true,
      "by_market": {},
      "definition": "kpi-v1.platform_commissions_usd",
      "historical_terms_unknown_count": 0
    }
  }
}
```


### 76. Analyst no consulta auditoría

**Actor:** `broker`. **Resultado:** OK; HTTP esperado: `[403]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/audit-trail?from=2026-11-01&to=2026-11-24
```

JSON enviado:

```json
null
```

Respuesta **HTTP 403** (4.02 ms). Request ID: `565fadba-09a8-4183-b778-46bc728cfcb9`.

```json
{
  "code": "<REDACTED>",
  "message": "Permission required.",
  "details": null
}
```


### 77. Protección contra escalamiento admin:*

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[409]`.

```http
POST https://127.0.0.1:8447/api/v1/admin/roles/investor/permissions
```

JSON enviado:

```json
{
  "permission_code": "admin:fees"
}
```

Respuesta **HTTP 409** (3.7 ms). Request ID: `19889f56-5eaa-4648-82fa-e8d99959f7d8`.

```json
{
  "code": "<REDACTED>",
  "message": "Protected administrative permission.",
  "details": {
    "permission_code": "admin:fees",
    "role": "investor"
  }
}
```


### 78. No quitar admin:rbac del administrador

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[409]`.

```http
DELETE https://127.0.0.1:8447/api/v1/admin/roles/administrator/permissions/admin:rbac
```

JSON enviado:

```json
null
```

Respuesta **HTTP 409** (3.75 ms). Request ID: `0427f943-995c-40d9-a33c-606f3c9c4491`.

```json
{
  "code": "<REDACTED>",
  "message": "Protected administrative permission.",
  "details": {
    "permission_code": "admin:rbac",
    "role": "administrator"
  }
}
```


### 79. Restaurar roles de broker2

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/admin/users/39bf8e8a-d3ec-4172-82c5-99e9508ffce1/roles/6d2d65e7-7c4c-4cf8-9b29-e2dd37f1794e/revoke
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (10.65 ms). Request ID: `62b7fa24-fb09-4f5e-962a-633ae064da62`.

```json
{
  "id": "6d2d65e7-7c4c-4cf8-9b29-e2dd37f1794e",
  "role": "auditor",
  "valid_from": "2026-11-24T14:02:30.362044Z",
  "valid_to": "2026-11-24T14:02:30.441101Z",
  "effective": false,
  "status": "ACTIVE",
  "cancelled_at": null,
  "cancelled_by": null
}
```


### 80. Restaurar roles de broker

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/admin/users/19f5fcb4-9a1d-4d3e-affe-96da0057cf2d/roles/46d3ae10-c7ae-469d-960b-381863292043/revoke
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (9.14 ms). Request ID: `1e0ace22-7ced-4c95-b6d3-383483a0e5ba`.

```json
{
  "id": "46d3ae10-c7ae-469d-960b-381863292043",
  "role": "analyst",
  "valid_from": "2026-11-24T14:02:30.375020Z",
  "valid_to": "2026-11-24T14:02:30.453029Z",
  "effective": false,
  "status": "ACTIVE",
  "cancelled_at": null,
  "cancelled_by": null
}
```


### 81. Comprobar fecha de calendario de prueba libre

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/markets/OTC/schedule-overrides?from=2027-02-02&to=2027-02-02
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (8.05 ms). Request ID: `f07e574c-ed12-422b-afec-7765ab95af24`.

```json
[]
```


### 82. Crear excepción futura OTC

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[201]`.

```http
POST https://127.0.0.1:8447/api/v1/admin/markets/OTC/schedule-overrides
```

JSON enviado:

```json
{
  "date": "2027-02-02",
  "closed": true
}
```

Respuesta **HTTP 201** (8.5 ms). Request ID: `3ac78a8d-3a90-475b-b530-8cc9793d3957`.

```json
{
  "id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
  "market": "OTC",
  "date": "2027-02-02",
  "closed": true,
  "open_time": null,
  "close_time": null
}
```


### 83. Modificar excepción futura

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
PUT https://127.0.0.1:8447/api/v1/admin/markets/OTC/schedule-overrides/b93665ab-4b19-41b5-ad43-1b8ec10881ca
```

JSON enviado:

```json
{
  "closed": false,
  "open_time": "10:00:00",
  "close_time": "15:00:00"
}
```

Respuesta **HTTP 200** (10.19 ms). Request ID: `d8a18764-c18d-4512-ac89-1dd9c7ac7515`.

```json
{
  "id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
  "market": "OTC",
  "date": "2027-02-02",
  "closed": false,
  "open_time": "10:00:00",
  "close_time": "15:00:00"
}
```


### 84. Eliminar excepción y restaurar calendario

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[204]`.

```http
DELETE https://127.0.0.1:8447/api/v1/admin/markets/OTC/schedule-overrides/b93665ab-4b19-41b5-ad43-1b8ec10881ca
```

JSON enviado:

```json
null
```

Respuesta **HTTP 204** (17.02 ms). Request ID: `bbe99a0f-2274-47ca-8574-e31388ced3a9`.

```json
null
```


### 85. Auditoría y despacho de los 3 cambios

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/markets/OTC/schedule-changes?from=2026-11-24&to=2026-11-24&page_size=10
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (13.0 ms). Request ID: `082e9973-1f02-4c01-9ab0-dc19fe19466b`.

```json
{
  "items": [
    {
      "id": "283815b0-89f9-4654-9616-f844afcac745",
      "actor_user_id": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
      "action": "schedule_override_deleted",
      "target_id": "OTC",
      "occurred_at": "2026-11-24T14:02:30.504852Z",
      "override_id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
      "effective_from": "2027-02-02",
      "before": {
        "id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
        "date": "2027-02-02",
        "closed": false,
        "open_time": "10:00:00",
        "close_time": "15:00:00",
        "market_code": "OTC"
      },
      "after": null,
      "payload": {
        "after": null,
        "before": {
          "id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
          "date": "2027-02-02",
          "closed": false,
          "open_time": "10:00:00",
          "close_time": "15:00:00",
          "market_code": "OTC"
        },
        "override_id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
        "effective_from": "2027-02-02"
      },
      "dispatch_status": "dispatched",
      "dispatched_at": "2026-11-24T14:02:30.519047Z",
      "affected_orders": 0,
      "notified_users": 5
    },
    {
      "id": "3b5988c5-c723-49e3-8571-14310eaa774b",
      "actor_user_id": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
      "action": "schedule_override_updated",
      "target_id": "OTC",
      "occurred_at": "2026-11-24T14:02:30.486827Z",
      "override_id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
      "effective_from": "2027-02-02",
      "before": {
        "id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
        "date": "2027-02-02",
        "closed": true,
        "open_time": null,
        "close_time": null,
        "market_code": "OTC"
      },
      "after": {
        "id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
        "date": "2027-02-02",
        "closed": false,
        "open_time": "10:00:00",
        "close_time": "15:00:00",
        "market_code": "OTC"
      },
      "payload": {
        "after": {
          "id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
          "date": "2027-02-02",
          "closed": false,
          "open_time": "10:00:00",
          "close_time": "15:00:00",
          "market_code": "OTC"
        },
        "before": {
          "id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
          "date": "2027-02-02",
          "closed": true,
          "open_time": null,
          "close_time": null,
          "market_code": "OTC"
        },
        "override_id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
        "effective_from": "2027-02-02"
      },
      "dispatch_status": "dispatched",
      "dispatched_at": "2026-11-24T14:02:30.507502Z",
      "affected_orders": 0,
      "notified_users": 5
    },
    {
      "id": "79ea6d79-6940-4db1-ab3f-2ec63a8a30d9",
      "actor_user_id": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
      "action": "schedule_override_created",
      "target_id": "OTC",
      "occurred_at": "2026-11-24T14:02:30.475852Z",
      "override_id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
      "effective_from": "2027-02-02",
      "before": null,
      "after": {
        "id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
        "date": "2027-02-02",
        "closed": true,
        "open_time": null,
        "close_time": null,
        "market_code": "OTC"
      },
      "payload": {
        "after": {
          "id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
          "date": "2027-02-02",
          "closed": true,
          "open_time": null,
          "close_time": null,
          "market_code": "OTC"
        },
        "before": null,
        "override_id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
        "effective_from": "2027-02-02"
      },
      "dispatch_status": "dispatched",
      "dispatched_at": "2026-11-24T14:02:30.499774Z",
      "affected_orders": 0,
      "notified_users": 5
    }
  ],
  "next_cursor": null
}
```


### 86. Cerrar sesión E2E admin

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[204]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/logout
```

JSON enviado:

```json
null
```

Respuesta **HTTP 204** (6.49 ms). Request ID: `51c71b6e-ff52-4d8d-8684-6a4dce66d5df`.

```json
null
```


### 87. Cerrar sesión E2E admin2

**Actor:** `admin2`. **Resultado:** OK; HTTP esperado: `[204]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/logout
```

JSON enviado:

```json
null
```

Respuesta **HTTP 204** (4.03 ms). Request ID: `cdaf4d63-4709-4db5-b16c-43aa10a0d1da`.

```json
null
```


### 88. Cerrar sesión E2E investor

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[204]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/logout
```

JSON enviado:

```json
null
```

Respuesta **HTTP 204** (6.37 ms). Request ID: `1205d381-c5d4-4863-85d3-7dac94500cbb`.

```json
null
```


### 89. Cerrar sesión E2E broker

**Actor:** `broker`. **Resultado:** OK; HTTP esperado: `[204]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/logout
```

JSON enviado:

```json
null
```

Respuesta **HTTP 204** (3.58 ms). Request ID: `ad6f3fdc-8e89-4269-8da1-311f0913d530`.

```json
null
```


### 90. Cerrar sesión E2E broker2

**Actor:** `broker2`. **Resultado:** OK; HTTP esperado: `[204]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/logout
```

JSON enviado:

```json
null
```

Respuesta **HTTP 204** (3.29 ms). Request ID: `3564e8fa-b8c1-4eb2-92ff-dbdd4c51ab54`.

```json
null
```


### 91. Acceso para comprobaciones adicionales: admin

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/login
```

JSON enviado:

```json
{
  "email": "admin.ti@accionesud.com",
  "password": "<REDACTED>"
}
```

Respuesta **HTTP 200** (148.33 ms). Request ID: `9410a033-0748-4faa-be59-9c97c40a934e`.

```json
{
  "mfa_token": "<REDACTED>",
  "mfa_expires_at": "2026-11-24T14:10:22.542554Z",
  "totp_enrollment": null
}
```


### 92. /api/v1/auth/mfa/verify

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/mfa/verify
```

JSON enviado:

```json
{
  "mfa_token": "<REDACTED>",
  "code": "<REDACTED>"
}
```

Respuesta **HTTP 200** (22.43 ms). Request ID: `5e05870f-d9bd-4a41-a894-3bbec161a77b`.

```json
{
  "user": {
    "user_id": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
    "email": "admin.ti@accionesud.com",
    "account_status": "active"
  },
  "recovery_codes": null,
  "recovery_codes_remaining": null
}
```


### 93. Acceso para comprobaciones adicionales: investor

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/login
```

JSON enviado:

```json
{
  "email": "investor.ti@accionesud.com",
  "password": "<REDACTED>"
}
```

Respuesta **HTTP 200** (123.13 ms). Request ID: `e6c60f1b-b433-4055-ad34-f21da7c842a8`.

```json
{
  "mfa_token": "<REDACTED>",
  "mfa_expires_at": "2026-11-24T14:10:22.713015Z",
  "totp_enrollment": null
}
```


### 94. /api/v1/auth/mfa/verify

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/mfa/verify
```

JSON enviado:

```json
{
  "mfa_token": "<REDACTED>",
  "code": "<REDACTED>"
}
```

Respuesta **HTTP 200** (19.23 ms). Request ID: `335c62ba-5254-4c1b-a88c-85b0b9de778d`.

```json
{
  "user": {
    "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
    "email": "investor.ti@accionesud.com",
    "account_status": "active"
  },
  "recovery_codes": null,
  "recovery_codes_remaining": null
}
```


### 95. /api/v1/admin/markets/OTC

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/markets/OTC
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (22.26 ms). Request ID: `04ef0957-fd94-4593-b836-b16088c8883d`.

```json
{
  "code": "<REDACTED>",
  "name": "Over the counter",
  "timezone": "America/New_York",
  "default_schedule": null,
  "overrides": [],
  "commission_terms": {
    "fee_version_id": "00000000-0000-0000-0000-000000000701",
    "commission_rate_pct": "2",
    "platform_share_pct": "60"
  },
  "fee_origin": "default",
  "trading_halts": []
}
```


### 96. Fijar horario por defecto OTC sin órdenes afectables

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
PUT https://127.0.0.1:8447/api/v1/admin/markets/OTC/default-schedule
```

JSON enviado:

```json
{
  "open_time": "09:30:00",
  "close_time": "16:00:00"
}
```

Respuesta **HTTP 200** (18.59 ms). Request ID: `77e04285-daca-4e05-9b13-7a3380b4212f`.

```json
{
  "market": "OTC",
  "open_time": "09:30:00",
  "close_time": "16:00:00"
}
```


### 97. Restaurar horario por defecto nulo

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[204]`.

```http
DELETE https://127.0.0.1:8447/api/v1/admin/markets/OTC/default-schedule
```

JSON enviado:

```json
null
```

Respuesta **HTTP 204** (21.37 ms). Request ID: `762d290b-0924-4282-be54-4ac36a441a22`.

```json
null
```


### 98. /api/v1/admin/markets/OTC

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/markets/OTC
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (29.97 ms). Request ID: `01502fd5-2a5f-486c-82c8-1037980ac0e8`.

```json
{
  "code": "<REDACTED>",
  "name": "Over the counter",
  "timezone": "America/New_York",
  "default_schedule": null,
  "overrides": [],
  "commission_terms": {
    "fee_version_id": "00000000-0000-0000-0000-000000000701",
    "commission_rate_pct": "2",
    "platform_share_pct": "60"
  },
  "fee_origin": "default",
  "trading_halts": []
}
```


### 99. Importe negativo rechazado en cumplimiento

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[422]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/compliance/atypical-operations?from=2026-11-01&to=2026-11-24&min_amount=-1
```

JSON enviado:

```json
null
```

Respuesta **HTTP 422** (10.27 ms). Request ID: `d96db72f-322e-4433-9ce7-43bf49ff7219`.

```json
{
  "code": "<REDACTED>",
  "message": "Invalid administrative field.",
  "details": {
    "field": "min_amount",
    "reason": "invalid"
  }
}
```


### 100. /api/v1/admin/trading-halts

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[422]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/trading-halts?status=invalid
```

JSON enviado:

```json
null
```

Respuesta **HTTP 422** (9.99 ms). Request ID: `1cbd4fee-1095-4640-aa84-9f720381a749`.

```json
{
  "code": "<REDACTED>",
  "message": "Invalid administrative field.",
  "details": {
    "field": "status",
    "reason": "invalid"
  }
}
```


### 101. /api/v1/admin/compliance/restrictions

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[422]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/compliance/restrictions?status=invalid
```

JSON enviado:

```json
null
```

Respuesta **HTTP 422** (10.49 ms). Request ID: `b15c7788-cf17-45d6-b1e4-6216228f3056`.

```json
{
  "code": "<REDACTED>",
  "message": "Invalid administrative field.",
  "details": {
    "field": "status",
    "reason": "invalid"
  }
}
```


### 102. /api/v1/admin/fee-schedules/NOEXISTE/versions

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[404]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/fee-schedules/NOEXISTE/versions
```

JSON enviado:

```json
null
```

Respuesta **HTTP 404** (17.1 ms). Request ID: `371b74d8-5178-4126-85af-6dc973ceb8d1`.

```json
{
  "code": "<REDACTED>",
  "message": "Resource not found.",
  "details": {
    "resource": "fee_scope"
  }
}
```


### 103. Consultar históricos tras migración

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/commissions?from=2026-11-01&to=2026-11-24
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (18.06 ms). Request ID: `658b12c9-a41d-4ea4-a9f4-cf3de9696ad7`.

```json
{
  "items": [],
  "next_cursor": null,
  "totals": {
    "commission": "0",
    "platform_share": "0",
    "broker_share": "0",
    "gross_amount": "0",
    "historical_terms_unknown_count": 0,
    "complete": true
  },
  "by_market": {},
  "by_broker": {}
}
```


### 104. Acceso para comprobaciones adicionales: admin

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/login
```

JSON enviado:

```json
{
  "email": "admin.ti@accionesud.com",
  "password": "<REDACTED>"
}
```

Respuesta **HTTP 200** (165.78 ms). Request ID: `cb133a80-e107-482b-aea7-c0ab3a753c74`.

```json
{
  "mfa_token": "<REDACTED>",
  "mfa_expires_at": "2026-11-24T14:10:52.837012Z",
  "totp_enrollment": null
}
```


### 105. /api/v1/auth/mfa/verify

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/mfa/verify
```

JSON enviado:

```json
{
  "mfa_token": "<REDACTED>",
  "code": "<REDACTED>"
}
```

Respuesta **HTTP 200** (14.67 ms). Request ID: `6d1f99d2-fb17-4501-a041-3151b782679d`.

```json
{
  "user": {
    "user_id": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
    "email": "admin.ti@accionesud.com",
    "account_status": "active"
  },
  "recovery_codes": null,
  "recovery_codes_remaining": null
}
```


### 106. Acceso para comprobaciones adicionales: investor

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/login
```

JSON enviado:

```json
{
  "email": "investor.ti@accionesud.com",
  "password": "<REDACTED>"
}
```

Respuesta **HTTP 200** (142.07 ms). Request ID: `5cb97cc8-e24e-4257-9b35-1733fabe6160`.

```json
{
  "mfa_token": "<REDACTED>",
  "mfa_expires_at": "2026-11-24T14:10:53.014578Z",
  "totp_enrollment": null
}
```


### 107. /api/v1/auth/mfa/verify

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/mfa/verify
```

JSON enviado:

```json
{
  "mfa_token": "<REDACTED>",
  "code": "<REDACTED>"
}
```

Respuesta **HTTP 200** (15.33 ms). Request ID: `8f763897-5401-4bf7-9ac2-3e138e0cd5f9`.

```json
{
  "user": {
    "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
    "email": "investor.ti@accionesud.com",
    "account_status": "active"
  },
  "recovery_codes": null,
  "recovery_codes_remaining": null
}
```


### 108. /api/v1/admin/markets/OTC

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/markets/OTC
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (17.36 ms). Request ID: `7420facc-f9aa-47a5-8677-7239145c13e4`.

```json
{
  "code": "<REDACTED>",
  "name": "Over the counter",
  "timezone": "America/New_York",
  "default_schedule": null,
  "overrides": [],
  "commission_terms": {
    "fee_version_id": "00000000-0000-0000-0000-000000000701",
    "commission_rate_pct": "2",
    "platform_share_pct": "60"
  },
  "fee_origin": "default",
  "trading_halts": []
}
```


### 109. Fijar horario por defecto OTC sin órdenes afectables

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
PUT https://127.0.0.1:8447/api/v1/admin/markets/OTC/default-schedule
```

JSON enviado:

```json
{
  "open_time": "09:30:00",
  "close_time": "16:00:00"
}
```

Respuesta **HTTP 200** (13.5 ms). Request ID: `fd3e3326-f62a-4dee-a5c4-63d724e920c1`.

```json
{
  "market": "OTC",
  "open_time": "09:30:00",
  "close_time": "16:00:00"
}
```


### 110. Restaurar horario por defecto nulo

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[204]`.

```http
DELETE https://127.0.0.1:8447/api/v1/admin/markets/OTC/default-schedule
```

JSON enviado:

```json
null
```

Respuesta **HTTP 204** (17.89 ms). Request ID: `b880022b-6590-4107-ad04-c25e528025ec`.

```json
null
```


### 111. /api/v1/admin/markets/OTC

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/markets/OTC
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (28.15 ms). Request ID: `465d518d-9df7-4407-9cf5-8b35fd3a4ac7`.

```json
{
  "code": "<REDACTED>",
  "name": "Over the counter",
  "timezone": "America/New_York",
  "default_schedule": null,
  "overrides": [],
  "commission_terms": {
    "fee_version_id": "00000000-0000-0000-0000-000000000701",
    "commission_rate_pct": "2",
    "platform_share_pct": "60"
  },
  "fee_origin": "default",
  "trading_halts": []
}
```


### 112. Importe negativo rechazado en cumplimiento

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[422]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/compliance/atypical-operations?from=2026-11-01&to=2026-11-24&min_amount=-1
```

JSON enviado:

```json
null
```

Respuesta **HTTP 422** (11.21 ms). Request ID: `0c23714e-b5b4-498a-81a7-cb5b60509c67`.

```json
{
  "code": "<REDACTED>",
  "message": "Invalid administrative field.",
  "details": {
    "field": "min_amount",
    "reason": "invalid"
  }
}
```


### 113. /api/v1/admin/trading-halts

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[422]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/trading-halts?status=invalid
```

JSON enviado:

```json
null
```

Respuesta **HTTP 422** (10.83 ms). Request ID: `b773c363-0e68-4069-aaf8-4167d1ae476b`.

```json
{
  "code": "<REDACTED>",
  "message": "Invalid administrative field.",
  "details": {
    "field": "status",
    "reason": "invalid"
  }
}
```


### 114. /api/v1/admin/compliance/restrictions

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[422]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/compliance/restrictions?status=invalid
```

JSON enviado:

```json
null
```

Respuesta **HTTP 422** (11.58 ms). Request ID: `dc4664c1-d5b5-41b0-a5b7-7d66294567ce`.

```json
{
  "code": "<REDACTED>",
  "message": "Invalid administrative field.",
  "details": {
    "field": "status",
    "reason": "invalid"
  }
}
```


### 115. /api/v1/admin/fee-schedules/NOEXISTE/versions

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[404]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/fee-schedules/NOEXISTE/versions
```

JSON enviado:

```json
null
```

Respuesta **HTTP 404** (16.66 ms). Request ID: `1ac80e4e-271f-4e29-b832-c83ad4ae318a`.

```json
{
  "code": "<REDACTED>",
  "message": "Resource not found.",
  "details": {
    "resource": "fee_scope"
  }
}
```


### 116. Consultar históricos tras migración

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/commissions?from=2026-11-01&to=2026-11-24
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (17.4 ms). Request ID: `257c960f-7fcc-4c74-92c7-ff5401a6a58b`.

```json
{
  "items": [],
  "next_cursor": null,
  "totals": {
    "commission": "0",
    "platform_share": "0",
    "broker_share": "0",
    "gross_amount": "0",
    "historical_terms_unknown_count": 0,
    "complete": true
  },
  "by_market": {},
  "by_broker": {}
}
```


### 117. LOCAL FIXTURE: comisiones oficiales e histórico desconocido

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/commissions?from=2026-11-01&to=2026-11-24
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (22.22 ms). Request ID: `571d67c6-79dd-4034-ad5d-c316f362429c`.

```json
{
  "items": [
    {
      "gross_amount": "1873.5",
      "commission": "37.47",
      "platform_share": "22.48",
      "broker_share": "14.99",
      "total": "1910.97",
      "net": null,
      "execution_id": "mod07-fixture-official_signed-9623fb45-f785-499a-9ba5-c8d114438f44",
      "order_id": "5cb54b04-0359-47e8-8204-c066d818e317",
      "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "symbol": "AAPL",
      "exchange": "NASDAQ",
      "side": "buy",
      "qty": "10",
      "price": "187.35",
      "executed_at": "2026-11-24T14:05:53.407565Z",
      "signed_by_broker_id": "19f5fcb4-9a1d-4d3e-affe-96da0057cf2d",
      "fee_version_id": "00000000-0000-0000-0000-000000000701",
      "commission_rate_pct": "2",
      "platform_share_pct": "60",
      "commission_status": "official",
      "investor_name": "Prueba Ti"
    },
    {
      "gross_amount": "100",
      "commission": null,
      "platform_share": null,
      "broker_share": null,
      "total": null,
      "net": null,
      "execution_id": "mod07-fixture-historical-5293ba75-2c80-44e0-ae3a-774e43bf4d8e",
      "order_id": "54eeb5a8-a705-4a85-93cb-d2678151b4dd",
      "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "symbol": "AAPL",
      "exchange": "NASDAQ",
      "side": "buy",
      "qty": "1",
      "price": "100",
      "executed_at": "2026-11-24T14:05:53.407565Z",
      "signed_by_broker_id": null,
      "fee_version_id": null,
      "commission_rate_pct": null,
      "platform_share_pct": null,
      "commission_status": "historical_terms_unknown",
      "investor_name": "Prueba Ti"
    },
    {
      "gross_amount": "20000",
      "commission": "400",
      "platform_share": "400",
      "broker_share": "0",
      "total": "20400",
      "net": null,
      "execution_id": "mod07-fixture-atypical-d8296feb-8929-4a64-a2f7-1cfbc8de25e8",
      "order_id": "96cd531c-c3ed-41e6-8598-12199822f39f",
      "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "symbol": "AAPL",
      "exchange": "NASDAQ",
      "side": "buy",
      "qty": "100",
      "price": "200",
      "executed_at": "2026-11-24T14:05:53.407565Z",
      "signed_by_broker_id": null,
      "fee_version_id": "00000000-0000-0000-0000-000000000701",
      "commission_rate_pct": "2",
      "platform_share_pct": "60",
      "commission_status": "official",
      "investor_name": "Prueba Ti"
    }
  ],
  "next_cursor": null,
  "totals": {
    "commission": "437.47",
    "platform_share": "422.48",
    "broker_share": "14.99",
    "gross_amount": "21973.5",
    "historical_terms_unknown_count": 1,
    "complete": false
  },
  "by_market": {
    "NASDAQ": {
      "commission": "437.47",
      "platform_share": "422.48",
      "broker_share": "14.99"
    }
  },
  "by_broker": {
    "19f5fcb4-9a1d-4d3e-affe-96da0057cf2d": {
      "commission": "37.47",
      "platform_share": "22.48",
      "broker_share": "14.99"
    },
    "unassigned": {
      "commission": "400",
      "platform_share": "400",
      "broker_share": "0"
    }
  }
}
```


### 118. LOCAL FIXTURE: consistencia de comisión con portfolio

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/portfolio/executions?from=2026-11-01&to=2026-11-24
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (16.89 ms). Request ID: `3deff5ff-7dfb-41ac-aee9-e3a37c1df40b`.

```json
{
  "items": [
    {
      "execution_id": "mod07-fixture-official_signed-9623fb45-f785-499a-9ba5-c8d114438f44",
      "order_id": "5cb54b04-0359-47e8-8204-c066d818e317",
      "symbol": "AAPL",
      "exchange": "NASDAQ",
      "side": "buy",
      "qty": "10.000000000",
      "price": "187.3500",
      "executed_at": "2026-11-24T14:05:53.407565Z",
      "commission": "37.47",
      "commission_source": "official"
    },
    {
      "execution_id": "mod07-fixture-historical-5293ba75-2c80-44e0-ae3a-774e43bf4d8e",
      "order_id": "54eeb5a8-a705-4a85-93cb-d2678151b4dd",
      "symbol": "AAPL",
      "exchange": "NASDAQ",
      "side": "buy",
      "qty": "1.000000000",
      "price": "100.0000",
      "executed_at": "2026-11-24T14:05:53.407565Z",
      "commission": "2.00",
      "commission_source": "reference"
    },
    {
      "execution_id": "mod07-fixture-atypical-d8296feb-8929-4a64-a2f7-1cfbc8de25e8",
      "order_id": "96cd531c-c3ed-41e6-8598-12199822f39f",
      "symbol": "AAPL",
      "exchange": "NASDAQ",
      "side": "buy",
      "qty": "100.000000000",
      "price": "200.0000",
      "executed_at": "2026-11-24T14:05:53.407565Z",
      "commission": "400.00",
      "commission_source": "official"
    }
  ],
  "next_cursor": null
}
```


### 119. LOCAL FIXTURE: consistencia de KPI con comisión oficial

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/kpis?from=2026-11-01&to=2026-11-24&refresh=true
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (43.48 ms). Request ID: `392e5b49-15ad-4db9-9b7d-15e60d192f63`.

```json
{
  "period": {
    "from": "2026-11-01",
    "to": "2026-11-24",
    "time_zone": "America/New_York"
  },
  "definitions_version": "kpi-v1",
  "computed_at": "2026-11-24T14:05:53.495560Z",
  "as_of": "2026-11-24T14:05:53.495560Z",
  "cache_hit": false,
  "stale": false,
  "metrics": {
    "registered_users": {
      "value": 5,
      "unit": "users",
      "definition": "kpi-v1.registered_users"
    },
    "new_registrations": {
      "value": 5,
      "unit": "users",
      "definition": "kpi-v1.new_registrations",
      "by_level": {
        "unspecified": 4,
        "beginner": 1
      },
      "by_interest": {
        "Technology": 1,
        "NASDAQ": 1
      }
    },
    "active_users": {
      "value": 5,
      "unit": "users",
      "definition": "kpi-v1.active_users"
    },
    "traded_volume_usd": {
      "value": "21973.5",
      "unit": "USD",
      "definition": "kpi-v1.traded_volume_usd",
      "by_market": {
        "NASDAQ": "21973.5"
      },
      "by_side": {
        "buy": "21973.5"
      }
    },
    "executions_count": {
      "value": 3,
      "unit": "executions",
      "definition": "kpi-v1.executions_count",
      "by_market": {
        "NASDAQ": 3
      },
      "by_side": {
        "buy": 3
      }
    },
    "platform_commissions_usd": {
      "value": "422.48",
      "unit": "USD",
      "definition": "kpi-v1.platform_commissions_usd",
      "by_market": {
        "NASDAQ": "422.48"
      },
      "historical_terms_unknown_count": 1,
      "complete": false
    },
    "active_subscriptions": {
      "value": 0,
      "unit": "subscriptions",
      "definition": "kpi-v1.active_subscriptions"
    },
    "revenue_by_source": {
      "value": "422.48",
      "unit": "USD",
      "definition": "kpi-v1.revenue_by_source",
      "commissions": "422.48",
      "subscriptions": "0",
      "excluded_non_usd_payments": 0,
      "complete": false
    },
    "users_by_type": {
      "value": 1,
      "unit": "users",
      "definition": "kpi-v1.users_by_type",
      "by_level": {
        "beginner": 1
      },
      "by_broker": {
        "without_broker": 1
      }
    }
  }
}
```


### 120. LOCAL FIXTURE: detectar ejecución USD 20000

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/compliance/atypical-operations?from=2026-11-01&to=2026-11-24
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (23.04 ms). Request ID: `7190dd2f-f94b-405e-ba11-0f57ee0ba495`.

```json
{
  "items": [
    {
      "event_id": "mod07-fixture-atypical-d8296feb-8929-4a64-a2f7-1cfbc8de25e8",
      "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "at": "2026-11-24T14:05:53.407565Z",
      "reasons": [
        "absolute_threshold"
      ],
      "observed": {
        "gross_amount": "20000",
        "baseline_mean": null,
        "baseline_count": 0,
        "symbol": "AAPL",
        "market": "NASDAQ",
        "side": "buy",
        "order_id": "96cd531c-c3ed-41e6-8598-12199822f39f"
      },
      "references": [
        "mod07-fixture-atypical-d8296feb-8929-4a64-a2f7-1cfbc8de25e8"
      ],
      "rules_version": "atypical-v2",
      "configuration": {
        "absolute_usd": "10000",
        "multiplier": "3",
        "window_days": 90,
        "min_history": 5,
        "frequency_count": 20,
        "frequency_seconds": 300,
        "cancellation_count": 10,
        "cancellation_seconds": 300,
        "rejection_count": 5,
        "rejection_seconds": 3600
      }
    }
  ],
  "next_cursor": null,
  "rules_version": "atypical-v2",
  "configuration": {
    "absolute_usd": "10000",
    "multiplier": "3",
    "window_days": 90,
    "min_history": 5,
    "frequency_count": 20,
    "frequency_seconds": 300,
    "cancellation_count": 10,
    "cancellation_seconds": 300,
    "rejection_count": 5,
    "rejection_seconds": 3600
  }
}
```


### 121. LOCAL FIXTURE: reporte con ejecuciones, señales y comisión

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[201]`.

```http
POST https://127.0.0.1:8447/api/v1/admin/compliance/users/c0674321-9a64-4f13-9070-e57dfb35b4e8/audit-reports
```

JSON enviado:

```json
{
  "from": "2026-11-01",
  "to": "2026-11-24"
}
```

Respuesta **HTTP 201** (50.88 ms). Request ID: `b6be1d9c-333c-4464-8483-9a9d8e4c9cf6`.

```json
{
  "id": "d01ffed9-d568-4af2-8bc5-141a30d3988c",
  "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
  "period_from": "2026-11-01",
  "period_to": "2026-11-24",
  "rules_version": "atypical-v2",
  "content": {
    "user": {
      "id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "created_at": "2026-11-11T15:04:21.760287+00:00",
      "roles": [
        "investor"
      ]
    },
    "period": {
      "from": "2026-11-01",
      "to": "2026-11-24"
    },
    "activity": [
      {
        "source": "admin",
        "action": "account_rehabilitated",
        "count": 1
      },
      {
        "source": "admin",
        "action": "account_restricted",
        "count": 1
      },
      {
        "source": "admin",
        "action": "compliance_report_generated",
        "count": 1
      },
      {
        "source": "auth",
        "action": "login.success",
        "count": 3
      },
      {
        "source": "auth",
        "action": "mfa_verify.success",
        "count": 3
      },
      {
        "source": "orders",
        "action": "created",
        "count": 1
      },
      {
        "source": "orders",
        "action": "mod07_fixture",
        "count": 4
      },
      {
        "source": "orders",
        "action": "user_canceled",
        "count": 1
      }
    ],
    "executions_count": 3,
    "volume_usd": "21973.5",
    "commission_usd": "437.47",
    "historical_terms_unknown_count": 1,
    "average": {
      "execution_count": "3",
      "volume_usd": "21973.5"
    },
    "ratios": {
      "execution_count": "1",
      "volume": "1"
    },
    "atypical_operations": [
      {
        "event_id": "mod07-fixture-atypical-d8296feb-8929-4a64-a2f7-1cfbc8de25e8",
        "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
        "at": "2026-11-24T14:05:53.407565+00:00",
        "reasons": [
          "absolute_threshold"
        ],
        "observed": {
          "gross_amount": "20000",
          "baseline_mean": null,
          "baseline_count": 0,
          "symbol": "AAPL",
          "market": "NASDAQ",
          "side": "buy",
          "order_id": "96cd531c-c3ed-41e6-8598-12199822f39f"
        },
        "references": [
          "mod07-fixture-atypical-d8296feb-8929-4a64-a2f7-1cfbc8de25e8"
        ],
        "rules_version": "atypical-v2",
        "configuration": {
          "absolute_usd": "10000",
          "multiplier": "3",
          "window_days": 90,
          "min_history": 5,
          "frequency_count": 20,
          "frequency_seconds": 300,
          "cancellation_count": 10,
          "cancellation_seconds": 300,
          "rejection_count": 5,
          "rejection_seconds": 3600
        }
      }
    ],
    "restrictions": [
      {
        "id": "7e0e3186-8a90-4fa2-97b7-4b8c8d180c6e",
        "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
        "restriction_type": "trading",
        "reason": "E2E MOD07 local: restricción temporal",
        "evidence_text": "Prueba técnica autorizada; no constituye sospecha real.",
        "evidence_refs": [],
        "restricted_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
        "restricted_at": "2026-11-24T14:02:01.246566+00:00",
        "lifted_at": "2026-11-24T14:02:30.242811+00:00",
        "lifted_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
        "lift_reason": "E2E MOD07: rehabilitación",
        "lift_evidence_text": "Finalizó la prueba autorizada.",
        "lift_evidence_refs": []
      }
    ],
    "rules_version": "atypical-v2",
    "configuration": {
      "absolute_usd": "10000",
      "multiplier": "3",
      "window_days": 90,
      "min_history": 5,
      "frequency_count": 20,
      "frequency_seconds": 300,
      "cancellation_count": 10,
      "cancellation_seconds": 300,
      "rejection_count": 5,
      "rejection_seconds": 3600
    }
  },
  "content_sha256": "3df24c7215995dc6359ba642a9a68440a6295df2e64e71ba6cbe843e2b490bab",
  "generated_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
  "generated_at": "2026-11-24T14:05:53.574942Z"
}
```


### 122. Notificaciones in_app reales de cambios de horario

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/notifications?page_size=100
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (12.64 ms). Request ID: `08445e22-8197-47eb-a48c-aab364ea8a74`.

```json
[
  {
    "id": "5af85a59-c9d5-46a5-b237-171682b10948",
    "event_type": "market_schedule_changes",
    "payload": {
      "after": null,
      "before": {
        "code": "OTC",
        "name": "Over the counter",
        "timezone": "America/New_York",
        "default_open_time": "09:30:00",
        "default_close_time": "16:00:00"
      },
      "market": "OTC",
      "change_id": "87b14785-bf3c-45f8-9e1c-4e07384da44f",
      "override_id": null,
      "effective_from": "2026-11-24"
    },
    "created_at": "2026-11-24T14:05:53.264392Z"
  },
  {
    "id": "29b040a1-f6ad-4c93-aa98-cab8b36959fe",
    "event_type": "market_schedule_changes",
    "payload": {
      "after": {
        "code": "OTC",
        "name": "Over the counter",
        "timezone": "America/New_York",
        "default_open_time": "09:30:00",
        "default_close_time": "16:00:00"
      },
      "before": {
        "code": "OTC",
        "name": "Over the counter",
        "timezone": "America/New_York",
        "default_open_time": null,
        "default_close_time": null
      },
      "market": "OTC",
      "change_id": "2a0d6f45-f4dd-40cd-996c-88e812723b63",
      "override_id": null,
      "effective_from": "2026-11-24"
    },
    "created_at": "2026-11-24T14:05:53.239435Z"
  },
  {
    "id": "268f5437-4fb4-478c-8b7f-012659d16664",
    "event_type": "market_schedule_changes",
    "payload": {
      "after": null,
      "before": {
        "code": "OTC",
        "name": "Over the counter",
        "timezone": "America/New_York",
        "default_open_time": "09:30:00",
        "default_close_time": "16:00:00"
      },
      "market": "OTC",
      "change_id": "625b7021-c920-4021-a8fd-44070d0c46c8",
      "override_id": null,
      "effective_from": "2026-11-24"
    },
    "created_at": "2026-11-24T14:05:22.960351Z"
  },
  {
    "id": "7485a71f-8335-45a7-a138-3a169f64fc5f",
    "event_type": "market_schedule_changes",
    "payload": {
      "after": {
        "code": "OTC",
        "name": "Over the counter",
        "timezone": "America/New_York",
        "default_open_time": "09:30:00",
        "default_close_time": "16:00:00"
      },
      "before": {
        "code": "OTC",
        "name": "Over the counter",
        "timezone": "America/New_York",
        "default_open_time": null,
        "default_close_time": null
      },
      "market": "OTC",
      "change_id": "4503f823-205c-4ef0-a034-fd37e5a09df8",
      "override_id": null,
      "effective_from": "2026-11-24"
    },
    "created_at": "2026-11-24T14:05:22.935727Z"
  },
  {
    "id": "f4e82365-f983-4fdf-be82-0f48c7933363",
    "event_type": "market_schedule_changes",
    "payload": {
      "after": null,
      "before": {
        "id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
        "date": "2027-02-02",
        "closed": false,
        "open_time": "10:00:00",
        "close_time": "15:00:00",
        "market_code": "OTC"
      },
      "market": "OTC",
      "change_id": "283815b0-89f9-4654-9616-f844afcac745",
      "override_id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
      "effective_from": "2027-02-02"
    },
    "created_at": "2026-11-24T14:02:30.523076Z"
  },
  {
    "id": "eb496bb2-af23-455e-8679-ec54693bd9b2",
    "event_type": "market_schedule_changes",
    "payload": {
      "after": {
        "id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
        "date": "2027-02-02",
        "closed": false,
        "open_time": "10:00:00",
        "close_time": "15:00:00",
        "market_code": "OTC"
      },
      "before": {
        "id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
        "date": "2027-02-02",
        "closed": true,
        "open_time": null,
        "close_time": null,
        "market_code": "OTC"
      },
      "market": "OTC",
      "change_id": "3b5988c5-c723-49e3-8571-14310eaa774b",
      "override_id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
      "effective_from": "2027-02-02"
    },
    "created_at": "2026-11-24T14:02:30.511988Z"
  },
  {
    "id": "fd98792d-a3d3-4c4b-a0da-24c907ee0882",
    "event_type": "market_schedule_changes",
    "payload": {
      "after": {
        "id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
        "date": "2027-02-02",
        "closed": true,
        "open_time": null,
        "close_time": null,
        "market_code": "OTC"
      },
      "before": null,
      "market": "OTC",
      "change_id": "79ea6d79-6940-4db1-ab3f-2ec63a8a30d9",
      "override_id": "b93665ab-4b19-41b5-ad43-1b8ec10881ca",
      "effective_from": "2027-02-02"
    },
    "created_at": "2026-11-24T14:02:30.505372Z"
  }
]
```


### 123. Verificar roles finales de broker

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/users/19f5fcb4-9a1d-4d3e-affe-96da0057cf2d/roles
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (14.29 ms). Request ID: `79d189e5-0919-47bb-bc16-fb5d33b0706c`.

```json
[
  {
    "id": "570ac2d3-dcee-4b32-9639-6378da22647f",
    "role": "broker",
    "valid_from": "2026-11-11T15:04:12.375358Z",
    "valid_to": null,
    "effective": true,
    "status": "ACTIVE",
    "cancelled_at": null,
    "cancelled_by": null
  },
  {
    "id": "46d3ae10-c7ae-469d-960b-381863292043",
    "role": "analyst",
    "valid_from": "2026-11-24T14:02:30.375020Z",
    "valid_to": "2026-11-24T14:02:30.453029Z",
    "effective": false,
    "status": "ACTIVE",
    "cancelled_at": null,
    "cancelled_by": null
  }
]
```


### 124. Verificar roles finales de broker2

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8447/api/v1/admin/users/39bf8e8a-d3ec-4172-82c5-99e9508ffce1/roles
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (13.32 ms). Request ID: `a4ceb110-131f-40c8-bb31-372e153dcc68`.

```json
[
  {
    "id": "00cb50ec-6f33-49bf-ae15-de93e477db24",
    "role": "broker",
    "valid_from": "2026-11-11T15:10:04.529725Z",
    "valid_to": null,
    "effective": true,
    "status": "ACTIVE",
    "cancelled_at": null,
    "cancelled_by": null
  },
  {
    "id": "6d2d65e7-7c4c-4cf8-9b29-e2dd37f1794e",
    "role": "auditor",
    "valid_from": "2026-11-24T14:02:30.362044Z",
    "valid_to": "2026-11-24T14:02:30.441101Z",
    "effective": false,
    "status": "ACTIVE",
    "cancelled_at": null,
    "cancelled_by": null
  }
]
```


### 125. /api/v1/auth/logout

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[204]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/logout
```

JSON enviado:

```json
null
```

Respuesta **HTTP 204** (6.7 ms). Request ID: `6ee055dc-ba1c-4696-98ff-3e73635a3159`.

```json
null
```


### 126. /api/v1/auth/logout

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[204]`.

```http
POST https://127.0.0.1:8447/api/v1/auth/logout
```

JSON enviado:

```json
null
```

Respuesta **HTTP 204** (6.44 ms). Request ID: `4a973c4d-69a8-4099-9157-9db7fc9ea5ad`.

```json
null
```
