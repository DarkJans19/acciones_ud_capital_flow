# MOD-07 — transcripción E2E supabase

- Inicio UTC: `2026-11-24T14:01:23.373203+00:00`.
- Fin UTC: `2026-11-24T14:09:14.650542+00:00`.
- API: `https://127.0.0.1:8448`; HTTPS local con certificado de prueba.
- Backend real, PostgreSQL real, sin mocks ni overrides de dependencias.
- `null` en solicitud significa **sin cuerpo JSON**. Una respuesta `null` con HTTP 204 significa **cuerpo vacío**.
- `<REDACTED>` reemplaza contraseña, código MFA/TOTP o token real. No es el valor enviado.
- Solicitudes: **108**; estados inesperados: **0**.

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
    "label": "Históricos sin backfill: comisión nula y complete=false",
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
  "fee_id": "9f983300-a1e7-44e5-86bc-951e14039416",
  "order_id": "6a4c5af7-10aa-4b6f-9f7d-15f48798ee54",
  "halt_id": "b566c83b-9c31-48c1-8af5-4840f290a805",
  "restriction_id": "5bf88b18-abf5-4a13-9b14-a67885c3fb4a",
  "report_id": "4f46c891-a30e-4d68-bbd8-a81de8e9f717",
  "override_id": "f531c3fb-1316-4029-9395-dc22474bd785",
  "residual": {
    "active_restrictions": [],
    "unreleased_halts": [],
    "uncanceled_fees": []
  }
}
```


## Flujo paso a paso


### 1. Salud (no demuestra conectividad DB)

**Actor:** `anon`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/health
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (479.46 ms). Request ID: `27cca9a0-faad-474b-84d9-b15bb219dc87`.

```json
{
  "status": "ok"
}
```


### 2. Contrato OpenAPI

**Actor:** `anon`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/openapi.json
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (613.54 ms). Request ID: `e5bcd0a1-96e4-4db0-9bd0-7a066dd0d495`.

```json
{
  "note": "Contrato completo en archivo OpenAPI anexo",
  "paths_count": 140
}
```


### 3. Acceso anónimo rechazado

**Actor:** `anon`. **Resultado:** OK; HTTP esperado: `[401]`.

```http
GET https://127.0.0.1:8448/api/v1/admin/fee-schedules
```

JSON enviado:

```json
null
```

Respuesta **HTTP 401** (2.55 ms). Request ID: `91a7ea23-519f-45eb-904a-067338341972`.

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
POST https://127.0.0.1:8448/api/v1/auth/login
```

JSON enviado:

```json
{
  "email": "admin.ti@accionesud.com",
  "password": "<REDACTED>"
}
```

Respuesta **HTTP 200** (4487.74 ms). Request ID: `8348b64e-e20d-4766-b9a0-12286f7eb874`.

```json
{
  "mfa_token": "<REDACTED>",
  "mfa_expires_at": "2026-11-24T14:06:24.682435Z",
  "totp_enrollment": null
}
```


### 5. MFA admin

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8448/api/v1/auth/mfa/verify
```

JSON enviado:

```json
{
  "mfa_token": "<REDACTED>",
  "code": "<REDACTED>"
}
```

Respuesta **HTTP 200** (2883.81 ms). Request ID: `62f40a21-3c0b-47c3-9113-8cf4f891ad3d`.

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
POST https://127.0.0.1:8448/api/v1/auth/login
```

JSON enviado:

```json
{
  "email": "admin2.ti@accionesud.com",
  "password": "<REDACTED>"
}
```

Respuesta **HTTP 200** (1646.18 ms). Request ID: `4e0e58b3-1415-4c34-9d38-d17c147bb991`.

```json
{
  "mfa_token": "<REDACTED>",
  "mfa_expires_at": "2026-11-24T14:06:35.311894Z",
  "totp_enrollment": null
}
```


### 7. MFA admin2

**Actor:** `admin2`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8448/api/v1/auth/mfa/verify
```

JSON enviado:

```json
{
  "mfa_token": "<REDACTED>",
  "code": "<REDACTED>"
}
```

Respuesta **HTTP 200** (2007.75 ms). Request ID: `72571f31-f6e4-4f58-ba4c-684c980ac85e`.

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
POST https://127.0.0.1:8448/api/v1/auth/login
```

JSON enviado:

```json
{
  "email": "investor.ti@accionesud.com",
  "password": "<REDACTED>"
}
```

Respuesta **HTTP 200** (1708.99 ms). Request ID: `4785cfb8-abcd-4ae3-9b29-28dd18417d51`.

```json
{
  "mfa_token": "<REDACTED>",
  "mfa_expires_at": "2026-11-24T14:06:39.414363Z",
  "totp_enrollment": null
}
```


### 9. MFA investor

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8448/api/v1/auth/mfa/verify
```

JSON enviado:

```json
{
  "mfa_token": "<REDACTED>",
  "code": "<REDACTED>"
}
```

Respuesta **HTTP 200** (2085.98 ms). Request ID: `fbd014ae-babf-48b7-b13b-be2afb2ae1bc`.

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
POST https://127.0.0.1:8448/api/v1/auth/login
```

JSON enviado:

```json
{
  "email": "broker.ti@accionesud.com",
  "password": "<REDACTED>"
}
```

Respuesta **HTTP 200** (1680.6 ms). Request ID: `32190eea-095b-40e6-af49-77db8a93f5af`.

```json
{
  "mfa_token": "<REDACTED>",
  "mfa_expires_at": "2026-11-24T14:06:43.724077Z",
  "totp_enrollment": null
}
```


### 11. MFA broker

**Actor:** `broker`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8448/api/v1/auth/mfa/verify
```

JSON enviado:

```json
{
  "mfa_token": "<REDACTED>",
  "code": "<REDACTED>"
}
```

Respuesta **HTTP 200** (2079.96 ms). Request ID: `009b9122-49ff-4255-8c26-ca8ebc9aa2fb`.

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
POST https://127.0.0.1:8448/api/v1/auth/login
```

JSON enviado:

```json
{
  "email": "broker2.ti@accionesud.com",
  "password": "<REDACTED>"
}
```

Respuesta **HTTP 200** (1795.55 ms). Request ID: `0a1f9866-7807-4968-a52a-0df303f0fe76`.

```json
{
  "mfa_token": "<REDACTED>",
  "mfa_expires_at": "2026-11-24T14:06:47.967683Z",
  "totp_enrollment": null
}
```


### 13. MFA broker2

**Actor:** `broker2`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8448/api/v1/auth/mfa/verify
```

JSON enviado:

```json
{
  "mfa_token": "<REDACTED>",
  "code": "<REDACTED>"
}
```

Respuesta **HTTP 200** (2135.34 ms). Request ID: `a00145ae-3975-425b-a3db-59036d6c71cf`.

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
GET https://127.0.0.1:8448/api/v1/users/me
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (6808.61 ms). Request ID: `273b5a1c-fd2b-4f32-a69f-0c4d386d0861`.

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
GET https://127.0.0.1:8448/api/v1/admin/roles
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (2369.29 ms). Request ID: `7f4c27f3-7399-4078-be79-eca5f5602675`.

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
GET https://127.0.0.1:8448/api/v1/admin/fee-schedules
```

JSON enviado:

```json
null
```

Respuesta **HTTP 403** (1167.67 ms). Request ID: `8a35252e-98b7-47f8-bbac-1198b73094b3`.

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
GET https://127.0.0.1:8448/api/v1/admin/fee-schedules
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (4531.81 ms). Request ID: `a41f5e8e-550b-4896-9ade-65229addba6f`.

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
        "created_at": "2026-11-24T13:58:21.023664Z",
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
        "created_at": "2026-11-24T13:58:21.023664Z",
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
        "created_at": "2026-11-24T13:58:21.023664Z",
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
        "created_at": "2026-11-24T13:58:21.023664Z",
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
        "created_at": "2026-11-24T13:58:21.023664Z",
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
        "created_at": "2026-11-24T13:58:21.023664Z",
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
        "created_at": "2026-11-24T13:58:21.023664Z",
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
        "created_at": "2026-11-24T13:58:21.023664Z",
        "canceled_at": null,
        "canceled_by": null,
        "cancel_reason": null
      },
      "origin": "default",
      "scheduled": []
    },
    {
      "scope": "TXSE",
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
        "created_at": "2026-11-24T13:58:21.023664Z",
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
GET https://127.0.0.1:8448/api/v1/admin/markets
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (3920.3 ms). Request ID: `ecb76438-3782-49ce-a0b8-66f0e8d1f9a3`.

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
  },
  {
    "code": "<REDACTED>",
    "name": "TXSE",
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
GET https://127.0.0.1:8448/api/v1/admin/markets/NASDAQ
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (3657.4 ms). Request ID: `56e46e46-f76d-4323-bf47-e450d881318a`.

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
GET https://127.0.0.1:8448/api/v1/admin/markets/NOEXISTE
```

JSON enviado:

```json
null
```

Respuesta **HTTP 404** (2422.82 ms). Request ID: `0f2a45ec-addd-4c90-8887-68614198492a`.

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
GET https://127.0.0.1:8448/api/v1/commissions/quote?symbol=AAPL&side=buy&qty=10&price=187.35&with_broker=true
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (3565.8 ms). Request ID: `bf273e8d-e859-4c80-b5a8-54cbac711ff3`.

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
  "quoted_at": "2026-11-24T14:02:19.611577Z"
}
```


### 22. Venta sin broker

**Actor:** `broker`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/api/v1/commissions/quote?symbol=AAPL&side=sell&qty=10&price=187.35&with_broker=false
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (3383.03 ms). Request ID: `69381a3d-3b95-47c3-8163-f082e1a1005f`.

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
  "quoted_at": "2026-11-24T14:02:23.102950Z"
}
```


### 23. Admin sin rol trader no cotiza

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[403]`.

```http
GET https://127.0.0.1:8448/api/v1/commissions/quote?symbol=AAPL&side=buy&qty=10&price=187.35&with_broker=true
```

JSON enviado:

```json
null
```

Respuesta **HTTP 403** (1126.77 ms). Request ID: `26cafeb6-e0a0-4960-88ad-da5ed3f0f638`.

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
GET https://127.0.0.1:8448/api/v1/commissions/quote?symbol=AAPL&side=buy&qty=0&price=187.35&with_broker=true
```

JSON enviado:

```json
null
```

Respuesta **HTTP 422** (1099.69 ms). Request ID: `4af81887-462f-4cf3-bba5-206cbe11aec2`.

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
GET https://127.0.0.1:8448/api/v1/commissions/quote?symbol=NOEXISTE&side=buy&qty=10&price=187.35&with_broker=true
```

JSON enviado:

```json
null
```

Respuesta **HTTP 404** (2330.54 ms). Request ID: `fee7f0e1-1441-4eb1-9c1c-8759b3df55d1`.

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
GET https://127.0.0.1:8448/api/v1/commissions/quote?symbol=AAPL&side=other&qty=10&price=187.35&with_broker=true
```

JSON enviado:

```json
null
```

Respuesta **HTTP 422** (3420.58 ms). Request ID: `b094c0b0-8f8c-467b-8c2c-262c71c2c48a`.

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
GET https://127.0.0.1:8448/api/v1/commissions?from=2026-11-01&to=2026-11-24&page_size=2
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (3703.05 ms). Request ID: `78216663-79fa-42ac-91f9-540cbb23af59`.

```json
{
  "items": [
    {
      "gross_amount": "355.07",
      "commission": null,
      "platform_share": null,
      "broker_share": null,
      "total": null,
      "net": null,
      "execution_id": "20261116112728987::f5a87be5-df7b-4f37-b344-1843a5a99c03",
      "order_id": "1681af57-432a-4fe1-baf8-4385eef6696e",
      "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "symbol": "AAPL",
      "exchange": "NASDAQ",
      "side": "buy",
      "qty": "1",
      "price": "355.07",
      "executed_at": "2026-11-16T16:27:28.987275Z",
      "signed_by_broker_id": null,
      "fee_version_id": null,
      "commission_rate_pct": null,
      "platform_share_pct": null,
      "commission_status": "historical_terms_unknown",
      "investor_name": "Prueba Ti"
    }
  ],
  "next_cursor": null,
  "totals": {
    "commission": "0",
    "platform_share": "0",
    "broker_share": "0",
    "gross_amount": "355.07",
    "historical_terms_unknown_count": 1,
    "complete": false
  },
  "by_market": {},
  "by_broker": {}
}
```


### 28. Comisiones broker

**Actor:** `broker`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/api/v1/broker/commissions?from=2026-11-01&to=2026-11-24&page_size=2
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (3672.09 ms). Request ID: `c51c2d83-289c-4f39-87e4-01d1441ce371`.

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
GET https://127.0.0.1:8448/api/v1/admin/commissions?from=2026-11-01&to=2026-11-24&page_size=2
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (3608.0 ms). Request ID: `a0900de8-5a4c-47d9-8fc3-1f0c312e9848`.

```json
{
  "items": [
    {
      "gross_amount": "3.67",
      "commission": null,
      "platform_share": null,
      "broker_share": null,
      "total": null,
      "net": null,
      "execution_id": "20261119093024260::97d9d3ae-79f5-41f7-9650-811d89e3b6be",
      "order_id": "61a737ea-1008-4230-967d-8a7b159d9d52",
      "user_id": "490698da-5059-4207-ae38-325809d893a5",
      "symbol": "ACCS",
      "exchange": "AMEX",
      "side": "buy",
      "qty": "1",
      "price": "3.67",
      "executed_at": "2026-11-19T14:30:24.260471Z",
      "signed_by_broker_id": null,
      "fee_version_id": null,
      "commission_rate_pct": null,
      "platform_share_pct": null,
      "commission_status": "historical_terms_unknown",
      "investor_name": "jordan beltford"
    },
    {
      "gross_amount": "355.07",
      "commission": null,
      "platform_share": null,
      "broker_share": null,
      "total": null,
      "net": null,
      "execution_id": "20261116112728987::f5a87be5-df7b-4f37-b344-1843a5a99c03",
      "order_id": "1681af57-432a-4fe1-baf8-4385eef6696e",
      "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "symbol": "AAPL",
      "exchange": "NASDAQ",
      "side": "buy",
      "qty": "1",
      "price": "355.07",
      "executed_at": "2026-11-16T16:27:28.987275Z",
      "signed_by_broker_id": null,
      "fee_version_id": null,
      "commission_rate_pct": null,
      "platform_share_pct": null,
      "commission_status": "historical_terms_unknown",
      "investor_name": "Prueba Ti"
    }
  ],
  "next_cursor": null,
  "totals": {
    "commission": "0",
    "platform_share": "0",
    "broker_share": "0",
    "gross_amount": "358.74",
    "historical_terms_unknown_count": 2,
    "complete": false
  },
  "by_market": {},
  "by_broker": {}
}
```


### 30. Broker sin vínculo: CLIENT_NOT_FOUND

**Actor:** `broker2`. **Resultado:** OK; HTTP esperado: `[404]`.

```http
GET https://127.0.0.1:8448/api/v1/broker/commissions?from=2026-11-01&to=2026-11-24&investor_id=97154d28-d50a-4727-8289-9b4e7aa46cae
```

JSON enviado:

```json
null
```

Respuesta **HTTP 404** (2224.81 ms). Request ID: `d4b7a2e1-599b-41bd-bef7-3f3f09c76346`.

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
GET https://127.0.0.1:8448/api/v1/admin/commissions?from=2026-11-24&to=2026-11-01
```

JSON enviado:

```json
null
```

Respuesta **HTTP 422** (1281.46 ms). Request ID: `22a45fb1-a33b-4b58-973c-1902d58c8081`.

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
GET https://127.0.0.1:8448/api/v1/admin/fee-schedules/NASDAQ/versions
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (3497.71 ms). Request ID: `0b6e29d2-111b-47f6-b935-2711e5f7a9a5`.

```json
{
  "items": [],
  "next_cursor": null
}
```


### 33. Escritura crítica exige step-up

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[409]`.

```http
POST https://127.0.0.1:8448/api/v1/admin/fee-schedules/NASDAQ/versions
```

JSON enviado:

```json
{
  "commission_rate_pct": "2.5000",
  "platform_share_pct": "65.00",
  "expected_latest_version": 0,
  "effective_from": "2026-12-01T14:02:50.187863+00:00",
  "reason": "E2E MOD07 supabase: tarifa futura temporal"
}
```

Respuesta **HTTP 409** (2221.51 ms). Request ID: `2ab9159d-664c-4e96-96c5-a05e5ba1752b`.

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
POST https://127.0.0.1:8448/api/v1/admin/fee-schedules/NASDAQ/versions
```

JSON enviado:

```json
{
  "commission_rate_pct": "2.5000",
  "platform_share_pct": "65.00",
  "expected_latest_version": 0,
  "effective_from": "2026-12-01T14:02:50.187863+00:00",
  "reason": "E2E MOD07 supabase: tarifa futura temporal",
  "totp_code": "<REDACTED>"
}
```

Respuesta **HTTP 401** (3321.26 ms). Request ID: `b28f6eb7-2069-497e-aa93-5be532bcc7f7`.

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
POST https://127.0.0.1:8448/api/v1/admin/fee-schedules/NASDAQ/versions
```

JSON enviado:

```json
{
  "commission_rate_pct": "11",
  "platform_share_pct": "65.00",
  "expected_latest_version": 0,
  "effective_from": "2026-12-01T14:02:50.187863+00:00",
  "reason": "E2E MOD07 supabase: tarifa futura temporal"
}
```

Respuesta **HTTP 422** (1107.47 ms). Request ID: `dbb03f67-b4b8-4b0a-a35e-afd15cb61666`.

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
POST https://127.0.0.1:8448/api/v1/admin/fee-schedules/NASDAQ/versions
```

JSON enviado:

```json
{
  "commission_rate_pct": "2.5000",
  "platform_share_pct": "65.00",
  "expected_latest_version": 0,
  "effective_from": "2026-12-01T14:02:50.187863+00:00",
  "reason": "E2E MOD07 supabase: tarifa futura temporal",
  "totp_code": "<REDACTED>"
}
```

Respuesta **HTTP 201** (6942.66 ms). Request ID: `c2b7a84f-6be7-478a-bceb-628858f2b1e3`.

```json
{
  "id": "9f983300-a1e7-44e5-86bc-951e14039416",
  "scope": "NASDAQ",
  "version_no": 1,
  "commission_rate_pct": "2.5",
  "platform_share_pct": "65",
  "broker_share_pct": "35",
  "effective_from": "2026-12-01T14:02:50.187863Z",
  "status": "scheduled",
  "reason": "E2E MOD07 supabase: tarifa futura temporal",
  "created_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
  "created_at": "2026-11-24T14:02:58.424533Z",
  "canceled_at": null,
  "canceled_by": null,
  "cancel_reason": null
}
```


### 37. Conflicto optimista de versión

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[409]`.

```http
POST https://127.0.0.1:8448/api/v1/admin/fee-schedules/NASDAQ/versions
```

JSON enviado:

```json
{
  "commission_rate_pct": "2.5000",
  "platform_share_pct": "65.00",
  "expected_latest_version": 0,
  "effective_from": "2026-12-01T14:02:50.187863+00:00",
  "reason": "E2E MOD07 supabase: tarifa futura temporal",
  "totp_code": "<REDACTED>"
}
```

Respuesta **HTTP 409** (5976.37 ms). Request ID: `25b1bdfb-4bdf-4bcd-b0e6-21f19208857d`.

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
GET https://127.0.0.1:8448/api/v1/admin/fee-schedules/NASDAQ/versions?page_size=1
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (3532.5 ms). Request ID: `aecb36d6-7b07-497c-b79e-ef5aa172a12f`.

```json
{
  "items": [
    {
      "id": "9f983300-a1e7-44e5-86bc-951e14039416",
      "scope": "NASDAQ",
      "version_no": 1,
      "commission_rate_pct": "2.5",
      "platform_share_pct": "65",
      "broker_share_pct": "35",
      "effective_from": "2026-12-01T14:02:50.187863Z",
      "status": "scheduled",
      "reason": "E2E MOD07 supabase: tarifa futura temporal",
      "created_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
      "created_at": "2026-11-24T14:02:58.424533Z",
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
GET https://127.0.0.1:8448/api/v1/admin/fee-schedules
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (3838.35 ms). Request ID: `a1a06004-9c64-46b6-8dcd-ed8014d90346`.

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
        "created_at": "2026-11-24T13:58:21.023664Z",
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
        "created_at": "2026-11-24T13:58:21.023664Z",
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
        "created_at": "2026-11-24T13:58:21.023664Z",
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
        "created_at": "2026-11-24T13:58:21.023664Z",
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
        "created_at": "2026-11-24T13:58:21.023664Z",
        "canceled_at": null,
        "canceled_by": null,
        "cancel_reason": null
      },
      "origin": "default",
      "scheduled": [
        {
          "id": "9f983300-a1e7-44e5-86bc-951e14039416",
          "market_code": "NASDAQ",
          "version_no": 1,
          "commission_rate_pct": "2.5",
          "platform_share_pct": "65",
          "effective_from": "2026-12-01T14:02:50.187863+00:00",
          "reason": "E2E MOD07 supabase: tarifa futura temporal",
          "created_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
          "created_at": "2026-11-24T14:02:58.424533+00:00",
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
        "created_at": "2026-11-24T13:58:21.023664Z",
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
        "created_at": "2026-11-24T13:58:21.023664Z",
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
        "created_at": "2026-11-24T13:58:21.023664Z",
        "canceled_at": null,
        "canceled_by": null,
        "cancel_reason": null
      },
      "origin": "default",
      "scheduled": []
    },
    {
      "scope": "TXSE",
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
        "created_at": "2026-11-24T13:58:21.023664Z",
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
POST https://127.0.0.1:8448/api/v1/admin/fee-schedules/NASDAQ/versions/9f983300-a1e7-44e5-86bc-951e14039416/cancel
```

JSON enviado:

```json
{
  "reason": "E2E MOD07: restauración, cancelar tarifa de prueba",
  "totp_code": "<REDACTED>"
}
```

Respuesta **HTTP 200** (5537.3 ms). Request ID: `038ade9f-3094-4878-8b52-bc71f2aaf900`.

```json
{
  "id": "9f983300-a1e7-44e5-86bc-951e14039416",
  "scope": "NASDAQ",
  "version_no": 1,
  "commission_rate_pct": "2.5",
  "platform_share_pct": "65",
  "broker_share_pct": "35",
  "effective_from": "2026-12-01T14:02:50.187863Z",
  "status": "canceled",
  "reason": "E2E MOD07 supabase: tarifa futura temporal",
  "created_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
  "created_at": "2026-11-24T14:02:58.424533Z",
  "canceled_at": "2026-11-24T14:03:22.213064Z",
  "canceled_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
  "cancel_reason": "E2E MOD07: restauración, cancelar tarifa de prueba"
}
```


### 41. Tarifa cancelada no altera cotización actual

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/api/v1/commissions/quote?symbol=AAPL&side=buy&qty=10&price=187.35&with_broker=true
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (3361.68 ms). Request ID: `1b2bab84-c955-4018-a81d-bed1496a7813`.

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
  "quoted_at": "2026-11-24T14:03:26.364843Z"
}
```


### 42. Dependencia real de órdenes: preview

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8448/api/v1/orders/preview
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

Respuesta **HTTP 200** (17283.2 ms). Request ID: `6878f4b4-07e4-46ba-95df-06a10bdfd248`.

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
POST https://127.0.0.1:8448/api/v1/orders
```

Encabezados adicionales:

```json
{
  "Idempotency-Key": "mod07-supabase-f85edfb6-0c52-4fde-8c6d-975e308beb96"
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

Respuesta **HTTP 201** (24888.13 ms). Request ID: `1269ef6d-20f1-4115-a6cc-ed9bf7a24bf7`.

```json
{
  "id": "6a4c5af7-10aa-4b6f-9f7d-15f48798ee54",
  "status": "IN_REVIEW",
  "status_cause": "broker_review",
  "provider_status": null,
  "created_at": "2026-11-24T14:03:47.805360Z",
  "updated_at": "2026-11-24T14:04:05.935881Z",
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
      "id": "b62a03a1-51ac-43a0-86ca-9ea920575b9d",
      "from_status": null,
      "to_status": "PENDING",
      "cause": "created",
      "actor_type": "investor",
      "actor_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "metadata": {},
      "at": "2026-11-24T14:03:47.805360Z"
    },
    {
      "id": "e50898f4-7942-462e-85fd-deedbf64e3c6",
      "from_status": "PENDING",
      "to_status": "IN_REVIEW",
      "cause": "broker_review",
      "actor_type": "system",
      "actor_id": null,
      "metadata": {
        "reviewing_broker_id": "39bf8e8a-d3ec-4172-82c5-99e9508ffce1"
      },
      "at": "2026-11-24T14:04:05.935881Z"
    }
  ],
  "reservation": {
    "kind": "usd",
    "symbol": "AAPL",
    "amount": "1.020000000",
    "status": "active",
    "updated_at": "2026-11-24T14:03:47.805360Z"
  },
  "reauthorizations": [],
  "cancels": [],
  "review_comments": []
}
```


### 44. Cancelar orden de prueba

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200, 202]`.

```http
POST https://127.0.0.1:8448/api/v1/orders/6a4c5af7-10aa-4b6f-9f7d-15f48798ee54/cancel
```

JSON enviado:

```json
{
  "reason": "other",
  "reason_text": "E2E MOD07: limpiar orden sandbox",
  "confirmed": true
}
```

Respuesta **HTTP 200** (7824.62 ms). Request ID: `b16f1448-965b-4440-bea5-9c507a973df6`.

```json
{
  "id": "6a4c5af7-10aa-4b6f-9f7d-15f48798ee54",
  "status": "CANCELED",
  "status_cause": "user_canceled",
  "provider_status": null,
  "created_at": "2026-11-24T14:03:47.805360Z",
  "updated_at": "2026-11-24T14:04:11.423000Z",
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
      "id": "b62a03a1-51ac-43a0-86ca-9ea920575b9d",
      "from_status": null,
      "to_status": "PENDING",
      "cause": "created",
      "actor_type": "investor",
      "actor_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "metadata": {},
      "at": "2026-11-24T14:03:47.805360Z"
    },
    {
      "id": "e50898f4-7942-462e-85fd-deedbf64e3c6",
      "from_status": "PENDING",
      "to_status": "IN_REVIEW",
      "cause": "broker_review",
      "actor_type": "system",
      "actor_id": null,
      "metadata": {
        "reviewing_broker_id": "39bf8e8a-d3ec-4172-82c5-99e9508ffce1"
      },
      "at": "2026-11-24T14:04:05.935881Z"
    },
    {
      "id": "665a7f4f-1b52-4e97-a0cd-9a795c839258",
      "from_status": "IN_REVIEW",
      "to_status": "CANCELED",
      "cause": "user_canceled",
      "actor_type": "investor",
      "actor_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "metadata": {},
      "at": "2026-11-24T14:04:11.423000Z"
    }
  ],
  "reservation": {
    "kind": "usd",
    "symbol": "AAPL",
    "amount": "1.020000000",
    "status": "released",
    "updated_at": "2026-11-24T14:04:13.885962Z"
  },
  "reauthorizations": [],
  "cancels": [
    {
      "id": "9b6908c9-e5ed-4763-99d0-9a607bcf2501",
      "previous_status": "IN_REVIEW",
      "reason": "other",
      "reason_text": "E2E MOD07: limpiar orden sandbox",
      "confirmed": true,
      "requested_at": "2026-11-24T14:04:11.423000Z",
      "outcome": "applied"
    }
  ],
  "review_comments": []
}
```


### 45. Cadena de custodia de orden real

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/api/v1/admin/audit-trail/orders/6a4c5af7-10aa-4b6f-9f7d-15f48798ee54
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (4227.31 ms). Request ID: `5c5beda5-7f18-4511-884d-f46da2c5d946`.

```json
{
  "order": {
    "id": "6a4c5af7-10aa-4b6f-9f7d-15f48798ee54",
    "status": "CANCELED",
    "status_cause": "user_canceled",
    "provider_status": null,
    "created_at": "2026-11-24T14:03:47.805360Z",
    "updated_at": "2026-11-24T14:04:11.423000Z",
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
    "client_order_id": "6a4c5af7-10aa-4b6f-9f7d-15f48798ee54",
    "fee_version_id": "00000000-0000-0000-0000-000000000701",
    "commission_rate_pct": "2",
    "platform_share_pct": "60",
    "submit_attempted_at": null,
    "scheduled_session_end": "2026-11-24T21:00:00Z"
  },
  "events": [
    {
      "id": "b62a03a1-51ac-43a0-86ca-9ea920575b9d",
      "from_status": null,
      "to_status": "PENDING",
      "cause": "created",
      "actor_type": "investor",
      "actor_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "metadata": {},
      "at": "2026-11-24T14:03:47.805360Z"
    },
    {
      "id": "e50898f4-7942-462e-85fd-deedbf64e3c6",
      "from_status": "PENDING",
      "to_status": "IN_REVIEW",
      "cause": "broker_review",
      "actor_type": "system",
      "actor_id": null,
      "metadata": {
        "reviewing_broker_id": "39bf8e8a-d3ec-4172-82c5-99e9508ffce1"
      },
      "at": "2026-11-24T14:04:05.935881Z"
    },
    {
      "id": "665a7f4f-1b52-4e97-a0cd-9a795c839258",
      "from_status": "IN_REVIEW",
      "to_status": "CANCELED",
      "cause": "user_canceled",
      "actor_type": "investor",
      "actor_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "metadata": {},
      "at": "2026-11-24T14:04:11.423000Z"
    }
  ],
  "executions": [],
  "cancel_requests": [
    {
      "id": "9b6908c9-e5ed-4763-99d0-9a607bcf2501",
      "previous_status": "IN_REVIEW",
      "reason": "other",
      "reason_text": "E2E MOD07: limpiar orden sandbox",
      "confirmed": true,
      "requested_at": "2026-11-24T14:04:11.423000Z",
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


### 46. /api/v1/admin/audit-trail/orders/0dd56754-b5ef-43b9-8176-f806f7952ba0

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[404]`.

```http
GET https://127.0.0.1:8448/api/v1/admin/audit-trail/orders/0dd56754-b5ef-43b9-8176-f806f7952ba0
```

JSON enviado:

```json
null
```

Respuesta **HTTP 404** (2250.25 ms). Request ID: `f4c7482a-0470-44a7-8e51-9fb868ed7406`.

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
POST https://127.0.0.1:8448/api/v1/admin/trading-halts
```

JSON enviado:

```json
{
  "scope": "NASDAQ",
  "ends_at": "2026-11-24T14:14:24.598844+00:00",
  "reason": "E2E MOD07 supabase: bloqueo temporal",
  "totp_code": "<REDACTED>"
}
```

Respuesta **HTTP 201** (7368.11 ms). Request ID: `b7519ad8-3857-442a-aa8f-9572a787f16f`.

```json
{
  "id": "b566c83b-9c31-48c1-8af5-4840f290a805",
  "scope": "NASDAQ",
  "status": "active",
  "reason": "E2E MOD07 supabase: bloqueo temporal",
  "starts_at": "2026-11-24T14:04:26.207222Z",
  "ends_at": "2026-11-24T14:14:24.598844Z",
  "created_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
  "created_at": "2026-11-24T14:04:26.207222Z",
  "released_at": null,
  "released_by": null,
  "release_reason": null
}
```


### 48. /api/v1/admin/trading-halts

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/api/v1/admin/trading-halts?scope=NASDAQ&status=active
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (2249.69 ms). Request ID: `5d5cfd26-5827-49b9-819a-677b84922fcb`.

```json
{
  "items": [
    {
      "id": "b566c83b-9c31-48c1-8af5-4840f290a805",
      "scope": "NASDAQ",
      "status": "active",
      "reason": "E2E MOD07 supabase: bloqueo temporal",
      "starts_at": "2026-11-24T14:04:26.207222Z",
      "ends_at": "2026-11-24T14:14:24.598844Z",
      "created_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
      "created_at": "2026-11-24T14:04:26.207222Z",
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
GET https://127.0.0.1:8448/api/v1/trading-halts/active
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (2165.96 ms). Request ID: `d6d42139-26aa-4633-a116-298cbb78d28e`.

```json
[
  {
    "scope": "NASDAQ",
    "starts_at": "2026-11-24T14:04:26.207222Z",
    "ends_at": "2026-11-24T14:14:24.598844Z"
  }
]
```


### 50. Halt bloquea órdenes

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[503]`.

```http
POST https://127.0.0.1:8448/api/v1/orders/preview
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

Respuesta **HTTP 503** (6084.42 ms). Request ID: `10f6afc1-c094-4f7d-a09e-625efd1e3c91`.

```json
{
  "code": "<REDACTED>",
  "message": "Trading is currently restricted.",
  "details": {
    "halt_id": "b566c83b-9c31-48c1-8af5-4840f290a805",
    "scope": "NASDAQ",
    "ends_at": "2026-11-24T14:14:24.598844+00:00"
  }
}
```


### 51. Halt no bloquea lecturas

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/api/v1/commissions/quote?symbol=AAPL&side=buy&qty=10&price=187.35&with_broker=true
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (3636.59 ms). Request ID: `8cf313af-fc30-4795-bb09-8b6e78fc428b`.

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
  "quoted_at": "2026-11-24T14:04:45.300731Z"
}
```


### 52. Liberar halt

**Actor:** `admin2`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8448/api/v1/admin/trading-halts/b566c83b-9c31-48c1-8af5-4840f290a805/release
```

JSON enviado:

```json
{
  "reason": "E2E MOD07: liberar bloqueo de prueba",
  "totp_code": "<REDACTED>"
}
```

Respuesta **HTTP 200** (5530.74 ms). Request ID: `a231bf3f-72f6-49d0-81f4-25f5231b1cf2`.

```json
{
  "id": "b566c83b-9c31-48c1-8af5-4840f290a805",
  "scope": "NASDAQ",
  "status": "released",
  "reason": "E2E MOD07 supabase: bloqueo temporal",
  "starts_at": "2026-11-24T14:04:26.207222Z",
  "ends_at": "2026-11-24T14:14:24.598844Z",
  "created_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
  "created_at": "2026-11-24T14:04:26.207222Z",
  "released_at": "2026-11-24T14:04:50.885909Z",
  "released_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
  "release_reason": "E2E MOD07: liberar bloqueo de prueba"
}
```


### 53. Órdenes tras liberar halt

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8448/api/v1/orders/preview
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

Respuesta **HTTP 200** (13869.99 ms). Request ID: `34d1a8b3-1124-4ea5-b605-61bf7388f7ed`.

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
POST https://127.0.0.1:8448/api/v1/admin/compliance/restrictions
```

JSON enviado:

```json
{
  "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
  "reason": "E2E MOD07 supabase: restricción temporal",
  "evidence_text": "Prueba técnica autorizada; no constituye sospecha real.",
  "evidence_refs": [],
  "totp_code": "<REDACTED>"
}
```

Respuesta **HTTP 201** (6837.78 ms). Request ID: `f1e18f62-ef10-46bf-b288-fc913e7941a0`.

```json
{
  "id": "5bf88b18-abf5-4a13-9b14-a67885c3fb4a",
  "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
  "restriction_type": "trading",
  "status": "active",
  "reason": "E2E MOD07 supabase: restricción temporal",
  "evidence_text": "Prueba técnica autorizada; no constituye sospecha real.",
  "evidence_refs": [],
  "restricted_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
  "restricted_at": "2026-11-24T14:05:11.857259Z",
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
GET https://127.0.0.1:8448/api/v1/admin/compliance/restrictions?user_id=c0674321-9a64-4f13-9070-e57dfb35b4e8&status=active
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (2182.52 ms). Request ID: `0aef52b3-4604-4bcc-8b09-9c0397f956a8`.

```json
{
  "items": [
    {
      "id": "5bf88b18-abf5-4a13-9b14-a67885c3fb4a",
      "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "restriction_type": "trading",
      "status": "active",
      "reason": "E2E MOD07 supabase: restricción temporal",
      "evidence_text": "Prueba técnica autorizada; no constituye sospecha real.",
      "evidence_refs": [],
      "restricted_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
      "restricted_at": "2026-11-24T14:05:11.857259Z",
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
POST https://127.0.0.1:8448/api/v1/orders/preview
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

Respuesta **HTTP 403** (5944.89 ms). Request ID: `10c66eb2-c7d4-4422-a89f-5a9dc0c94fbd`.

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
GET https://127.0.0.1:8448/api/v1/users/me
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (7501.71 ms). Request ID: `2a14b6ab-654a-4382-aa7b-6c3152482dd3`.

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
  "contracted_plan": "monthly",
  "is_premium": true,
  "broker_requested": false,
  "associated_broker": {
    "id": "39bf8e8a-d3ec-4172-82c5-99e9508ffce1",
    "name": "Broker Dos",
    "firm_name": "Firma Dos",
    "since": "2026-11-17T03:47:48.650132Z"
  },
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
POST https://127.0.0.1:8448/api/v1/admin/compliance/restrictions/5bf88b18-abf5-4a13-9b14-a67885c3fb4a/lift
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

Respuesta **HTTP 200** (5328.71 ms). Request ID: `470f39b5-6425-4671-b52e-0804bfab14ae`.

```json
{
  "id": "5bf88b18-abf5-4a13-9b14-a67885c3fb4a",
  "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
  "restriction_type": "trading",
  "status": "lifted",
  "reason": "E2E MOD07 supabase: restricción temporal",
  "evidence_text": "Prueba técnica autorizada; no constituye sospecha real.",
  "evidence_refs": [],
  "restricted_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
  "restricted_at": "2026-11-24T14:05:11.857259Z",
  "lifted_at": "2026-11-24T14:05:33.443130Z",
  "lifted_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
  "lift_reason": "E2E MOD07: rehabilitación",
  "lift_evidence_text": "Finalizó la prueba autorizada.",
  "lift_evidence_refs": []
}
```


### 59. Detectar operaciones atípicas reales

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/api/v1/admin/compliance/atypical-operations?from=2026-11-01&to=2026-11-24&page_size=2
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (3516.41 ms). Request ID: `45f3c690-83af-4368-89ac-6cbcf1cc2a52`.

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
POST https://127.0.0.1:8448/api/v1/admin/compliance/users/c0674321-9a64-4f13-9070-e57dfb35b4e8/audit-reports
```

JSON enviado:

```json
{
  "from": "2026-11-01",
  "to": "2026-11-24"
}
```

Respuesta **HTTP 201** (10722.66 ms). Request ID: `cfffa043-b592-43a8-b012-64ca7c991c2b`.

```json
{
  "id": "4f46c891-a30e-4d68-bbd8-a81de8e9f717",
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
        "count": 24
      },
      {
        "source": "auth",
        "action": "mfa_verify.invalid_totp",
        "count": 2
      },
      {
        "source": "auth",
        "action": "mfa_verify.success",
        "count": 22
      },
      {
        "source": "brokers",
        "action": "link.active",
        "count": 2
      },
      {
        "source": "brokers",
        "action": "link.requested",
        "count": 1
      },
      {
        "source": "brokers",
        "action": "proposal.accepted",
        "count": 4
      },
      {
        "source": "brokers",
        "action": "proposal.approved",
        "count": 1
      },
      {
        "source": "brokers",
        "action": "proposal.conversion_failed",
        "count": 1
      },
      {
        "source": "brokers",
        "action": "proposal.sent",
        "count": 2
      },
      {
        "source": "brokers",
        "action": "trading_authorization.active",
        "count": 1
      },
      {
        "source": "orders",
        "action": "broker_approved",
        "count": 1
      },
      {
        "source": "orders",
        "action": "broker_review",
        "count": 2
      },
      {
        "source": "orders",
        "action": "created",
        "count": 5
      },
      {
        "source": "orders",
        "action": "proposal:6eac1e18-d2e4-4354-90ed-cfa93a400b76",
        "count": 1
      },
      {
        "source": "orders",
        "action": "provider_status",
        "count": 1
      },
      {
        "source": "orders",
        "action": "submission_started",
        "count": 1
      },
      {
        "source": "orders",
        "action": "user_canceled",
        "count": 5
      }
    ],
    "executions_count": 1,
    "volume_usd": "355.07",
    "commission_usd": "0",
    "historical_terms_unknown_count": 1,
    "average": {
      "execution_count": "1",
      "volume_usd": "179.37"
    },
    "ratios": {
      "execution_count": "1",
      "volume": "1.98"
    },
    "atypical_operations": [],
    "restrictions": [
      {
        "id": "5bf88b18-abf5-4a13-9b14-a67885c3fb4a",
        "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
        "restriction_type": "trading",
        "reason": "E2E MOD07 supabase: restricción temporal",
        "evidence_text": "Prueba técnica autorizada; no constituye sospecha real.",
        "evidence_refs": [],
        "restricted_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
        "restricted_at": "2026-11-24T14:05:11.857259+00:00",
        "lifted_at": "2026-11-24T14:05:33.443130+00:00",
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
  "content_sha256": "59d0d8d0ea8a7ade22d80696352c374fa46074fc0fb51cdb306cfd164a30873b",
  "generated_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
  "generated_at": "2026-11-24T14:05:39.990647Z"
}
```


### 61. Leer reporte persistido

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/api/v1/admin/compliance/audit-reports/4f46c891-a30e-4d68-bbd8-a81de8e9f717
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (2388.19 ms). Request ID: `c821a009-65c3-4c4c-92ff-d9bcbcf62022`.

```json
{
  "id": "4f46c891-a30e-4d68-bbd8-a81de8e9f717",
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
      "volume": "1.98",
      "execution_count": "1"
    },
    "average": {
      "volume_usd": "179.37",
      "execution_count": "1"
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
        "count": 24,
        "action": "login.success",
        "source": "auth"
      },
      {
        "count": 2,
        "action": "mfa_verify.invalid_totp",
        "source": "auth"
      },
      {
        "count": 22,
        "action": "mfa_verify.success",
        "source": "auth"
      },
      {
        "count": 2,
        "action": "link.active",
        "source": "brokers"
      },
      {
        "count": 1,
        "action": "link.requested",
        "source": "brokers"
      },
      {
        "count": 4,
        "action": "proposal.accepted",
        "source": "brokers"
      },
      {
        "count": 1,
        "action": "proposal.approved",
        "source": "brokers"
      },
      {
        "count": 1,
        "action": "proposal.conversion_failed",
        "source": "brokers"
      },
      {
        "count": 2,
        "action": "proposal.sent",
        "source": "brokers"
      },
      {
        "count": 1,
        "action": "trading_authorization.active",
        "source": "brokers"
      },
      {
        "count": 1,
        "action": "broker_approved",
        "source": "orders"
      },
      {
        "count": 2,
        "action": "broker_review",
        "source": "orders"
      },
      {
        "count": 5,
        "action": "created",
        "source": "orders"
      },
      {
        "count": 1,
        "action": "proposal:6eac1e18-d2e4-4354-90ed-cfa93a400b76",
        "source": "orders"
      },
      {
        "count": 1,
        "action": "provider_status",
        "source": "orders"
      },
      {
        "count": 1,
        "action": "submission_started",
        "source": "orders"
      },
      {
        "count": 5,
        "action": "user_canceled",
        "source": "orders"
      }
    ],
    "volume_usd": "355.07",
    "restrictions": [
      {
        "id": "5bf88b18-abf5-4a13-9b14-a67885c3fb4a",
        "reason": "E2E MOD07 supabase: restricción temporal",
        "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
        "lifted_at": "2026-11-24T14:05:33.443130+00:00",
        "lifted_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
        "lift_reason": "E2E MOD07: rehabilitación",
        "evidence_refs": [],
        "evidence_text": "Prueba técnica autorizada; no constituye sospecha real.",
        "restricted_at": "2026-11-24T14:05:11.857259+00:00",
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
    "executions_count": 1,
    "atypical_operations": [],
    "historical_terms_unknown_count": 1
  },
  "content_sha256": "59d0d8d0ea8a7ade22d80696352c374fa46074fc0fb51cdb306cfd164a30873b",
  "generated_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
  "generated_at": "2026-11-24T14:05:39.990647Z"
}
```


### 62. /api/v1/admin/compliance/users/c0674321-9a64-4f13-9070-e57dfb35b4e8/audit-reports

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/api/v1/admin/compliance/users/c0674321-9a64-4f13-9070-e57dfb35b4e8/audit-reports
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (3739.92 ms). Request ID: `6f2b0e29-0c5d-4947-b7ce-923f6c8d488e`.

```json
{
  "items": [
    {
      "id": "4f46c891-a30e-4d68-bbd8-a81de8e9f717",
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
          "volume": "1.98",
          "execution_count": "1"
        },
        "average": {
          "volume_usd": "179.37",
          "execution_count": "1"
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
            "count": 24,
            "action": "login.success",
            "source": "auth"
          },
          {
            "count": 2,
            "action": "mfa_verify.invalid_totp",
            "source": "auth"
          },
          {
            "count": 22,
            "action": "mfa_verify.success",
            "source": "auth"
          },
          {
            "count": 2,
            "action": "link.active",
            "source": "brokers"
          },
          {
            "count": 1,
            "action": "link.requested",
            "source": "brokers"
          },
          {
            "count": 4,
            "action": "proposal.accepted",
            "source": "brokers"
          },
          {
            "count": 1,
            "action": "proposal.approved",
            "source": "brokers"
          },
          {
            "count": 1,
            "action": "proposal.conversion_failed",
            "source": "brokers"
          },
          {
            "count": 2,
            "action": "proposal.sent",
            "source": "brokers"
          },
          {
            "count": 1,
            "action": "trading_authorization.active",
            "source": "brokers"
          },
          {
            "count": 1,
            "action": "broker_approved",
            "source": "orders"
          },
          {
            "count": 2,
            "action": "broker_review",
            "source": "orders"
          },
          {
            "count": 5,
            "action": "created",
            "source": "orders"
          },
          {
            "count": 1,
            "action": "proposal:6eac1e18-d2e4-4354-90ed-cfa93a400b76",
            "source": "orders"
          },
          {
            "count": 1,
            "action": "provider_status",
            "source": "orders"
          },
          {
            "count": 1,
            "action": "submission_started",
            "source": "orders"
          },
          {
            "count": 5,
            "action": "user_canceled",
            "source": "orders"
          }
        ],
        "volume_usd": "355.07",
        "restrictions": [
          {
            "id": "5bf88b18-abf5-4a13-9b14-a67885c3fb4a",
            "reason": "E2E MOD07 supabase: restricción temporal",
            "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
            "lifted_at": "2026-11-24T14:05:33.443130+00:00",
            "lifted_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
            "lift_reason": "E2E MOD07: rehabilitación",
            "evidence_refs": [],
            "evidence_text": "Prueba técnica autorizada; no constituye sospecha real.",
            "restricted_at": "2026-11-24T14:05:11.857259+00:00",
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
        "executions_count": 1,
        "atypical_operations": [],
        "historical_terms_unknown_count": 1
      },
      "content_sha256": "59d0d8d0ea8a7ade22d80696352c374fa46074fc0fb51cdb306cfd164a30873b",
      "generated_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
      "generated_at": "2026-11-24T14:05:39.990647Z"
    }
  ],
  "next_cursor": null
}
```


### 63. Calcular KPIs y guardar snapshot

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/api/v1/admin/kpis?from=2026-11-01&to=2026-11-24&refresh=true
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (10877.96 ms). Request ID: `d1cdae83-e2df-4776-9cad-365c1bba9fe1`.

```json
{
  "period": {
    "from": "2026-11-01",
    "to": "2026-11-24",
    "time_zone": "America/New_York"
  },
  "definitions_version": "kpi-v1",
  "computed_at": "2026-11-24T14:05:56.697311Z",
  "as_of": "2026-11-24T14:05:56.697311Z",
  "cache_hit": false,
  "stale": false,
  "metrics": {
    "registered_users": {
      "value": 20,
      "unit": "users",
      "definition": "kpi-v1.registered_users"
    },
    "new_registrations": {
      "value": 20,
      "unit": "users",
      "definition": "kpi-v1.new_registrations",
      "by_level": {
        "unspecified": 9,
        "beginner": 9,
        "experienced": 2
      },
      "by_interest": {
        "string": 2,
        "Tecnología & Semiconductores": 3,
        "Technology": 1,
        "NASDAQ": 1,
        "Sector Financiero & Banca USA": 3,
        "Materias Primas: Oro & Metales": 1,
        "Inteligencia Artificial & Cloud": 1,
        "Mercados Tradicionales (NYSE & S&P 500)": 1,
        "Salud & Biotecnología": 1
      }
    },
    "active_users": {
      "value": 15,
      "unit": "users",
      "definition": "kpi-v1.active_users"
    },
    "traded_volume_usd": {
      "value": "358.74",
      "unit": "USD",
      "definition": "kpi-v1.traded_volume_usd",
      "by_market": {
        "AMEX": "3.67",
        "NASDAQ": "355.07"
      },
      "by_side": {
        "buy": "358.74"
      }
    },
    "executions_count": {
      "value": 2,
      "unit": "executions",
      "definition": "kpi-v1.executions_count",
      "by_market": {
        "AMEX": 1,
        "NASDAQ": 1
      },
      "by_side": {
        "buy": 2
      }
    },
    "platform_commissions_usd": {
      "value": "0",
      "unit": "USD",
      "definition": "kpi-v1.platform_commissions_usd",
      "by_market": {},
      "historical_terms_unknown_count": 2,
      "complete": false
    },
    "active_subscriptions": {
      "value": 2,
      "unit": "subscriptions",
      "definition": "kpi-v1.active_subscriptions"
    },
    "revenue_by_source": {
      "value": "24",
      "unit": "USD",
      "definition": "kpi-v1.revenue_by_source",
      "commissions": "0",
      "subscriptions": "24",
      "excluded_non_usd_payments": 0,
      "complete": false
    },
    "users_by_type": {
      "value": 12,
      "unit": "users",
      "definition": "kpi-v1.users_by_type",
      "by_level": {
        "unspecified": 3,
        "beginner": 7,
        "experienced": 2
      },
      "by_broker": {
        "without_broker": 11,
        "with_broker": 1
      }
    }
  }
}
```


### 64. Reutilizar caché de KPIs

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/api/v1/admin/kpis?from=2026-11-01&to=2026-11-24
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (2332.17 ms). Request ID: `6f62f3fe-f7ba-4a5c-ac39-898b3b2c9f31`.

```json
{
  "period": {
    "from": "2026-11-01",
    "to": "2026-11-24",
    "time_zone": "America/New_York"
  },
  "definitions_version": "kpi-v1",
  "computed_at": "2026-11-24T14:05:56.697311Z",
  "as_of": "2026-11-24T14:05:56.697311Z",
  "cache_hit": true,
  "stale": false,
  "metrics": {
    "active_users": {
      "unit": "users",
      "value": 15,
      "definition": "kpi-v1.active_users"
    },
    "users_by_type": {
      "unit": "users",
      "value": 12,
      "by_level": {
        "beginner": 7,
        "experienced": 2,
        "unspecified": 3
      },
      "by_broker": {
        "with_broker": 1,
        "without_broker": 11
      },
      "definition": "kpi-v1.users_by_type"
    },
    "executions_count": {
      "unit": "executions",
      "value": 2,
      "by_side": {
        "buy": 2
      },
      "by_market": {
        "AMEX": 1,
        "NASDAQ": 1
      },
      "definition": "kpi-v1.executions_count"
    },
    "registered_users": {
      "unit": "users",
      "value": 20,
      "definition": "kpi-v1.registered_users"
    },
    "new_registrations": {
      "unit": "users",
      "value": 20,
      "by_level": {
        "beginner": 9,
        "experienced": 2,
        "unspecified": 9
      },
      "definition": "kpi-v1.new_registrations",
      "by_interest": {
        "NASDAQ": 1,
        "string": 2,
        "Technology": 1,
        "Salud & Biotecnología": 1,
        "Sector Financiero & Banca USA": 3,
        "Tecnología & Semiconductores": 3,
        "Materias Primas: Oro & Metales": 1,
        "Inteligencia Artificial & Cloud": 1,
        "Mercados Tradicionales (NYSE & S&P 500)": 1
      }
    },
    "revenue_by_source": {
      "unit": "USD",
      "value": "24",
      "complete": false,
      "definition": "kpi-v1.revenue_by_source",
      "commissions": "0",
      "subscriptions": "24",
      "excluded_non_usd_payments": 0
    },
    "traded_volume_usd": {
      "unit": "USD",
      "value": "358.74",
      "by_side": {
        "buy": "358.74"
      },
      "by_market": {
        "AMEX": "3.67",
        "NASDAQ": "355.07"
      },
      "definition": "kpi-v1.traded_volume_usd"
    },
    "active_subscriptions": {
      "unit": "subscriptions",
      "value": 2,
      "definition": "kpi-v1.active_subscriptions"
    },
    "platform_commissions_usd": {
      "unit": "USD",
      "value": "0",
      "complete": false,
      "by_market": {},
      "definition": "kpi-v1.platform_commissions_usd",
      "historical_terms_unknown_count": 2
    }
  }
}
```


### 65. Rastro unificado: primera página

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/api/v1/admin/audit-trail?from=2026-11-01&to=2026-11-24&source=admin&page_size=2
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (2396.18 ms). Request ID: `54d34257-127f-4a0d-a521-5d071d42016a`.

```json
{
  "items": [
    {
      "source": "admin",
      "event_id": "837d79f2-324b-4b15-bccf-303b639e52b1",
      "occurred_at": "2026-11-24T14:05:39.990647Z",
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
        "report_id": "4f46c891-a30e-4d68-bbd8-a81de8e9f717",
        "period_from": "2026-11-01",
        "rules_version": "atypical-v2",
        "content_sha256": "59d0d8d0ea8a7ade22d80696352c374fa46074fc0fb51cdb306cfd164a30873b"
      },
      "ip_address": "127.0.0.1"
    },
    {
      "source": "admin",
      "event_id": "18a5a6ef-a2b4-4907-b84c-8b44da6515b2",
      "occurred_at": "2026-11-24T14:05:33.443130Z",
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
        "restriction_id": "5bf88b18-abf5-4a13-9b14-a67885c3fb4a",
        "restriction_type": "trading"
      },
      "ip_address": "127.0.0.1"
    }
  ],
  "next_cursor": "WyIyMDI2LTExLTI0VDE0OjA1OjMzLjQ0MzEzMCswMDowMCIsImFkbWluIiwiMThhNWE2ZWYtYTJiNC00OTA3LWI4NGMtOGI0NGRhNjUxNWIyIl0="
}
```


### 66. Rastro unificado: segunda página

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/api/v1/admin/audit-trail?from=2026-11-01&to=2026-11-24&source=admin&page_size=2&cursor=WyIyMDI2LTExLTI0VDE0OjA1OjMzLjQ0MzEzMCswMDowMCIsImFkbWluIiwiMThhNWE2ZWYtYTJiNC00OTA3LWI4NGMtOGI0NGRhNjUxNWIyIl0%3D
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (2505.74 ms). Request ID: `bde7b6ec-26f3-4ed5-8bcc-116b4b7e932f`.

```json
{
  "items": [
    {
      "source": "admin",
      "event_id": "549ea8bd-adc0-4b19-b5f5-5230e984c083",
      "occurred_at": "2026-11-24T14:05:11.857259Z",
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
        "reason": "E2E MOD07 supabase: restricción temporal",
        "evidence": {
          "refs": [],
          "text": "Prueba técnica autorizada; no constituye sospecha real."
        },
        "restriction_id": "5bf88b18-abf5-4a13-9b14-a67885c3fb4a",
        "restriction_type": "trading"
      },
      "ip_address": "127.0.0.1"
    },
    {
      "source": "admin",
      "event_id": "0b26c7ca-e574-4e1b-a19a-0606dfc539a6",
      "occurred_at": "2026-11-24T14:04:50.885909Z",
      "actor_type": "user",
      "actor_id": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
      "subject_user_id": null,
      "related_user_id": null,
      "action": "trading_halt_released",
      "entity_type": "trading_halt",
      "entity_id": "b566c83b-9c31-48c1-8af5-4840f290a805",
      "from_state": null,
      "to_state": null,
      "details": {
        "after": {
          "id": "b566c83b-9c31-48c1-8af5-4840f290a805",
          "reason": "E2E MOD07 supabase: bloqueo temporal",
          "ends_at": "2026-11-24T14:14:24.598844+00:00",
          "starts_at": "2026-11-24T14:04:26.207222+00:00",
          "created_at": "2026-11-24T14:04:26.207222+00:00",
          "created_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
          "market_code": "NASDAQ",
          "released_at": "2026-11-24T14:04:50.885909+00:00",
          "released_by": "afe9aa95-8f19-4593-bb42-fe7613792d0c",
          "release_reason": "E2E MOD07: liberar bloqueo de prueba"
        },
        "scope": "NASDAQ",
        "before": {
          "id": "b566c83b-9c31-48c1-8af5-4840f290a805",
          "reason": "E2E MOD07 supabase: bloqueo temporal",
          "ends_at": "2026-11-24T14:14:24.598844+00:00",
          "starts_at": "2026-11-24T14:04:26.207222+00:00",
          "created_at": "2026-11-24T14:04:26.207222+00:00",
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
  "next_cursor": "WyIyMDI2LTExLTI0VDE0OjA0OjUwLjg4NTkwOSswMDowMCIsImFkbWluIiwiMGIyNmM3Y2EtZTU3NC00ZTFiLWExOWEtMDYwNmRmYzUzOWE2Il0="
}
```


### 67. /api/v1/admin/audit-trail

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[422]`.

```http
GET https://127.0.0.1:8448/api/v1/admin/audit-trail?from=2026-11-01&to=2026-11-24&source=invalid
```

JSON enviado:

```json
null
```

Respuesta **HTTP 422** (1123.84 ms). Request ID: `acd358ac-4f83-422e-9c71-a11136e93c64`.

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
GET https://127.0.0.1:8448/api/v1/admin/audit-trail?from=2026-11-01&to=2026-11-24&cursor=bad-cursor
```

JSON enviado:

```json
null
```

Respuesta **HTTP 422** (1070.57 ms). Request ID: `1c8755ea-6094-47e3-838e-75fe03a84f0a`.

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
POST https://127.0.0.1:8448/api/v1/admin/users/39bf8e8a-d3ec-4172-82c5-99e9508ffce1/roles
```

JSON enviado:

```json
{
  "role": "auditor",
  "valid_from": "2026-11-24T14:06:15.934960+00:00"
}
```

Respuesta **HTTP 201** (4043.01 ms). Request ID: `bd519070-960e-4592-b5a4-b001f2a06ab1`.

```json
{
  "id": "48e892af-ef6d-47e6-b955-134489c65cfe",
  "role": "auditor",
  "valid_from": "2026-11-24T14:06:15.934960Z",
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
POST https://127.0.0.1:8448/api/v1/admin/users/19f5fcb4-9a1d-4d3e-affe-96da0057cf2d/roles
```

JSON enviado:

```json
{
  "role": "analyst",
  "valid_from": "2026-11-24T14:06:19.980220+00:00"
}
```

Respuesta **HTTP 201** (3063.09 ms). Request ID: `53991bc2-1178-4606-8cd5-5eab43efab7c`.

```json
{
  "id": "0a94440a-2707-44d8-8b51-bf9760d642a1",
  "role": "analyst",
  "valid_from": "2026-11-24T14:06:19.980220Z",
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
GET https://127.0.0.1:8448/api/v1/admin/audit-trail?from=2026-11-01&to=2026-11-24&page_size=1
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (2461.35 ms). Request ID: `9b3b64eb-d86a-4e4c-b83a-c272921952bc`.

```json
{
  "items": [
    {
      "source": "admin",
      "event_id": "e85c0c44-266e-4b8a-9d63-8d719fb93226",
      "occurred_at": "2026-11-24T14:06:21.060339Z",
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
        "valid_from": "2026-11-24T14:06:19.980220+00:00",
        "assignment_id": "0a94440a-2707-44d8-8b51-bf9760d642a1"
      },
      "ip_address": null
    }
  ],
  "next_cursor": "WyIyMDI2LTExLTI0VDE0OjA2OjIxLjA2MDMzOSswMDowMCIsImFkbWluIiwiZTg1YzBjNDQtMjY2ZS00YjhhLTlkNjMtOGQ3MTlmYjkzMjI2Il0="
}
```


### 72. Auditor lee cumplimiento

**Actor:** `broker2`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/api/v1/admin/compliance/restrictions
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (2313.64 ms). Request ID: `7f49d308-10ee-41f0-8488-d86c493a53dc`.

```json
{
  "items": [
    {
      "id": "5bf88b18-abf5-4a13-9b14-a67885c3fb4a",
      "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "restriction_type": "trading",
      "status": "lifted",
      "reason": "E2E MOD07 supabase: restricción temporal",
      "evidence_text": "Prueba técnica autorizada; no constituye sospecha real.",
      "evidence_refs": [],
      "restricted_by": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
      "restricted_at": "2026-11-24T14:05:11.857259Z",
      "lifted_at": "2026-11-24T14:05:33.443130Z",
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
GET https://127.0.0.1:8448/api/v1/admin/kpis?from=2026-11-01&to=2026-11-24
```

JSON enviado:

```json
null
```

Respuesta **HTTP 403** (1161.1 ms). Request ID: `28dc097a-45cb-4041-b7d5-38eba481de22`.

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
POST https://127.0.0.1:8448/api/v1/admin/compliance/restrictions
```

JSON enviado:

```json
{
  "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
  "reason": "Debe rechazarse"
}
```

Respuesta **HTTP 403** (1072.8 ms). Request ID: `528d041c-fb4c-490e-bfdd-3c94344f4214`.

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
GET https://127.0.0.1:8448/api/v1/admin/kpis?from=2026-11-01&to=2026-11-24
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (2145.43 ms). Request ID: `ecb4e42e-e9a2-4ff4-b2d7-7e51dc52c4d1`.

```json
{
  "period": {
    "from": "2026-11-01",
    "to": "2026-11-24",
    "time_zone": "America/New_York"
  },
  "definitions_version": "kpi-v1",
  "computed_at": "2026-11-24T14:05:56.697311Z",
  "as_of": "2026-11-24T14:05:56.697311Z",
  "cache_hit": true,
  "stale": false,
  "metrics": {
    "active_users": {
      "unit": "users",
      "value": 15,
      "definition": "kpi-v1.active_users"
    },
    "users_by_type": {
      "unit": "users",
      "value": 12,
      "by_level": {
        "beginner": 7,
        "experienced": 2,
        "unspecified": 3
      },
      "by_broker": {
        "with_broker": 1,
        "without_broker": 11
      },
      "definition": "kpi-v1.users_by_type"
    },
    "executions_count": {
      "unit": "executions",
      "value": 2,
      "by_side": {
        "buy": 2
      },
      "by_market": {
        "AMEX": 1,
        "NASDAQ": 1
      },
      "definition": "kpi-v1.executions_count"
    },
    "registered_users": {
      "unit": "users",
      "value": 20,
      "definition": "kpi-v1.registered_users"
    },
    "new_registrations": {
      "unit": "users",
      "value": 20,
      "by_level": {
        "beginner": 9,
        "experienced": 2,
        "unspecified": 9
      },
      "definition": "kpi-v1.new_registrations",
      "by_interest": {
        "NASDAQ": 1,
        "string": 2,
        "Technology": 1,
        "Salud & Biotecnología": 1,
        "Sector Financiero & Banca USA": 3,
        "Tecnología & Semiconductores": 3,
        "Materias Primas: Oro & Metales": 1,
        "Inteligencia Artificial & Cloud": 1,
        "Mercados Tradicionales (NYSE & S&P 500)": 1
      }
    },
    "revenue_by_source": {
      "unit": "USD",
      "value": "24",
      "complete": false,
      "definition": "kpi-v1.revenue_by_source",
      "commissions": "0",
      "subscriptions": "24",
      "excluded_non_usd_payments": 0
    },
    "traded_volume_usd": {
      "unit": "USD",
      "value": "358.74",
      "by_side": {
        "buy": "358.74"
      },
      "by_market": {
        "AMEX": "3.67",
        "NASDAQ": "355.07"
      },
      "definition": "kpi-v1.traded_volume_usd"
    },
    "active_subscriptions": {
      "unit": "subscriptions",
      "value": 2,
      "definition": "kpi-v1.active_subscriptions"
    },
    "platform_commissions_usd": {
      "unit": "USD",
      "value": "0",
      "complete": false,
      "by_market": {},
      "definition": "kpi-v1.platform_commissions_usd",
      "historical_terms_unknown_count": 2
    }
  }
}
```


### 76. Analyst no consulta auditoría

**Actor:** `broker`. **Resultado:** OK; HTTP esperado: `[403]`.

```http
GET https://127.0.0.1:8448/api/v1/admin/audit-trail?from=2026-11-01&to=2026-11-24
```

JSON enviado:

```json
null
```

Respuesta **HTTP 403** (1166.8 ms). Request ID: `1e497a92-6d60-42e2-9ca6-e30cd0267634`.

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
POST https://127.0.0.1:8448/api/v1/admin/roles/investor/permissions
```

JSON enviado:

```json
{
  "permission_code": "admin:fees"
}
```

Respuesta **HTTP 409** (1089.3 ms). Request ID: `f0682526-255f-4f1e-9f8e-ce020cc678f1`.

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
DELETE https://127.0.0.1:8448/api/v1/admin/roles/administrator/permissions/admin:rbac
```

JSON enviado:

```json
null
```

Respuesta **HTTP 409** (1183.84 ms). Request ID: `6b106a64-45eb-4dc9-949e-a4f1ab4bbec4`.

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
POST https://127.0.0.1:8448/api/v1/admin/users/39bf8e8a-d3ec-4172-82c5-99e9508ffce1/roles/48e892af-ef6d-47e6-b955-134489c65cfe/revoke
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (4333.7 ms). Request ID: `a5297aa4-6bf4-4e53-98f7-a207dfd21e26`.

```json
{
  "id": "48e892af-ef6d-47e6-b955-134489c65cfe",
  "role": "auditor",
  "valid_from": "2026-11-24T14:06:15.934960Z",
  "valid_to": "2026-11-24T14:06:36.733567Z",
  "effective": false,
  "status": "ACTIVE",
  "cancelled_at": null,
  "cancelled_by": null
}
```


### 80. Restaurar roles de broker

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8448/api/v1/admin/users/19f5fcb4-9a1d-4d3e-affe-96da0057cf2d/roles/0a94440a-2707-44d8-8b51-bf9760d642a1/revoke
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (2900.21 ms). Request ID: `04a1e874-8abe-4b35-a00b-2064b535e4f3`.

```json
{
  "id": "0a94440a-2707-44d8-8b51-bf9760d642a1",
  "role": "analyst",
  "valid_from": "2026-11-24T14:06:19.980220Z",
  "valid_to": "2026-11-24T14:06:41.069425Z",
  "effective": false,
  "status": "ACTIVE",
  "cancelled_at": null,
  "cancelled_by": null
}
```


### 81. Comprobar fecha de calendario de prueba libre

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/api/v1/admin/markets/OTC/schedule-overrides?from=2027-02-02&to=2027-02-02
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (2264.6 ms). Request ID: `c7d5356e-7f9a-461e-8443-3ae76286a1d8`.

```json
[]
```


### 82. Crear excepción futura OTC

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[201]`.

```http
POST https://127.0.0.1:8448/api/v1/admin/markets/OTC/schedule-overrides
```

JSON enviado:

```json
{
  "date": "2027-02-02",
  "closed": true
}
```

Respuesta **HTTP 201** (2595.73 ms). Request ID: `d6b2c602-5cdd-4a04-8d44-3f4c627f6c3f`.

```json
{
  "id": "f531c3fb-1316-4029-9395-dc22474bd785",
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
PUT https://127.0.0.1:8448/api/v1/admin/markets/OTC/schedule-overrides/f531c3fb-1316-4029-9395-dc22474bd785
```

JSON enviado:

```json
{
  "closed": false,
  "open_time": "10:00:00",
  "close_time": "15:00:00"
}
```

Respuesta **HTTP 200** (2732.77 ms). Request ID: `64a87012-3280-45cd-aaf2-9c5678518958`.

```json
{
  "id": "f531c3fb-1316-4029-9395-dc22474bd785",
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
DELETE https://127.0.0.1:8448/api/v1/admin/markets/OTC/schedule-overrides/f531c3fb-1316-4029-9395-dc22474bd785
```

JSON enviado:

```json
null
```

Respuesta **HTTP 204** (3490.02 ms). Request ID: `b63977ac-d62b-44f2-9efc-8806963ff719`.

```json
null
```


### 85. Auditoría y despacho de los 3 cambios

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/api/v1/admin/markets/OTC/schedule-changes?from=2026-11-24&to=2026-11-24&page_size=10
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (5170.19 ms). Request ID: `6fa181fd-6637-4dd4-96ce-01f9c4a024bc`.

```json
{
  "items": [
    {
      "id": "c34c7e97-e626-4b9c-a824-3e73fc0d6731",
      "actor_user_id": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
      "action": "schedule_override_deleted",
      "target_id": "OTC",
      "occurred_at": "2026-11-24T14:06:53.537124Z",
      "override_id": "f531c3fb-1316-4029-9395-dc22474bd785",
      "effective_from": "2027-02-02",
      "before": {
        "id": "f531c3fb-1316-4029-9395-dc22474bd785",
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
          "id": "f531c3fb-1316-4029-9395-dc22474bd785",
          "date": "2027-02-02",
          "closed": false,
          "open_time": "10:00:00",
          "close_time": "15:00:00",
          "market_code": "OTC"
        },
        "override_id": "f531c3fb-1316-4029-9395-dc22474bd785",
        "effective_from": "2027-02-02"
      },
      "dispatch_status": "dispatched",
      "dispatched_at": "2026-11-24T14:06:57.761057Z",
      "affected_orders": 0,
      "notified_users": 20
    },
    {
      "id": "1db7e9ed-354d-4192-8d03-53c4bf15f6a3",
      "actor_user_id": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
      "action": "schedule_override_updated",
      "target_id": "OTC",
      "occurred_at": "2026-11-24T14:06:50.184156Z",
      "override_id": "f531c3fb-1316-4029-9395-dc22474bd785",
      "effective_from": "2027-02-02",
      "before": {
        "id": "f531c3fb-1316-4029-9395-dc22474bd785",
        "date": "2027-02-02",
        "closed": true,
        "open_time": null,
        "close_time": null,
        "market_code": "OTC"
      },
      "after": {
        "id": "f531c3fb-1316-4029-9395-dc22474bd785",
        "date": "2027-02-02",
        "closed": false,
        "open_time": "10:00:00",
        "close_time": "15:00:00",
        "market_code": "OTC"
      },
      "payload": {
        "after": {
          "id": "f531c3fb-1316-4029-9395-dc22474bd785",
          "date": "2027-02-02",
          "closed": false,
          "open_time": "10:00:00",
          "close_time": "15:00:00",
          "market_code": "OTC"
        },
        "before": {
          "id": "f531c3fb-1316-4029-9395-dc22474bd785",
          "date": "2027-02-02",
          "closed": true,
          "open_time": null,
          "close_time": null,
          "market_code": "OTC"
        },
        "override_id": "f531c3fb-1316-4029-9395-dc22474bd785",
        "effective_from": "2027-02-02"
      },
      "dispatch_status": "dispatched",
      "dispatched_at": "2026-11-24T14:06:55.346568Z",
      "affected_orders": 0,
      "notified_users": 20
    },
    {
      "id": "2d4f0b69-e469-413b-b3e7-b7163e1cfae6",
      "actor_user_id": "932792e8-d8b7-43ac-a268-122eb5cfaea7",
      "action": "schedule_override_created",
      "target_id": "OTC",
      "occurred_at": "2026-11-24T14:06:47.456595Z",
      "override_id": "f531c3fb-1316-4029-9395-dc22474bd785",
      "effective_from": "2027-02-02",
      "before": null,
      "after": {
        "id": "f531c3fb-1316-4029-9395-dc22474bd785",
        "date": "2027-02-02",
        "closed": true,
        "open_time": null,
        "close_time": null,
        "market_code": "OTC"
      },
      "payload": {
        "after": {
          "id": "f531c3fb-1316-4029-9395-dc22474bd785",
          "date": "2027-02-02",
          "closed": true,
          "open_time": null,
          "close_time": null,
          "market_code": "OTC"
        },
        "before": null,
        "override_id": "f531c3fb-1316-4029-9395-dc22474bd785",
        "effective_from": "2027-02-02"
      },
      "dispatch_status": "dispatched",
      "dispatched_at": "2026-11-24T14:06:52.793469Z",
      "affected_orders": 0,
      "notified_users": 20
    }
  ],
  "next_cursor": null
}
```


### 86. Cerrar sesión E2E admin

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[204]`.

```http
POST https://127.0.0.1:8448/api/v1/auth/logout
```

JSON enviado:

```json
null
```

Respuesta **HTTP 204** (1206.62 ms). Request ID: `cac94367-f340-4545-adfc-f4c8b3c6302d`.

```json
null
```


### 87. Cerrar sesión E2E admin2

**Actor:** `admin2`. **Resultado:** OK; HTTP esperado: `[204]`.

```http
POST https://127.0.0.1:8448/api/v1/auth/logout
```

JSON enviado:

```json
null
```

Respuesta **HTTP 204** (1234.89 ms). Request ID: `eb96f18d-ab65-400f-bdf9-31b5c25ed811`.

```json
null
```


### 88. Cerrar sesión E2E investor

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[204]`.

```http
POST https://127.0.0.1:8448/api/v1/auth/logout
```

JSON enviado:

```json
null
```

Respuesta **HTTP 204** (1219.53 ms). Request ID: `1b97bce4-5a39-40ab-8bb2-3cf163a70ba2`.

```json
null
```


### 89. Cerrar sesión E2E broker

**Actor:** `broker`. **Resultado:** OK; HTTP esperado: `[204]`.

```http
POST https://127.0.0.1:8448/api/v1/auth/logout
```

JSON enviado:

```json
null
```

Respuesta **HTTP 204** (1181.88 ms). Request ID: `06bc0793-5395-4517-960d-6639d740c522`.

```json
null
```


### 90. Cerrar sesión E2E broker2

**Actor:** `broker2`. **Resultado:** OK; HTTP esperado: `[204]`.

```http
POST https://127.0.0.1:8448/api/v1/auth/logout
```

JSON enviado:

```json
null
```

Respuesta **HTTP 204** (1217.65 ms). Request ID: `207e7c18-93d3-4924-8efb-20218ab7958c`.

```json
null
```


### 91. Acceso para comprobaciones adicionales: admin

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8448/api/v1/auth/login
```

JSON enviado:

```json
{
  "email": "admin.ti@accionesud.com",
  "password": "<REDACTED>"
}
```

Respuesta **HTTP 200** (2505.24 ms). Request ID: `999b1ec3-21a7-428a-a4e1-859ba64136b8`.

```json
{
  "mfa_token": "<REDACTED>",
  "mfa_expires_at": "2026-11-24T14:13:27.460315Z",
  "totp_enrollment": null
}
```


### 92. /api/v1/auth/mfa/verify

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8448/api/v1/auth/mfa/verify
```

JSON enviado:

```json
{
  "mfa_token": "<REDACTED>",
  "code": "<REDACTED>"
}
```

Respuesta **HTTP 200** (2242.0 ms). Request ID: `324b0341-76cd-4cc7-9d30-bfa2515193f9`.

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
POST https://127.0.0.1:8448/api/v1/auth/login
```

JSON enviado:

```json
{
  "email": "investor.ti@accionesud.com",
  "password": "<REDACTED>"
}
```

Respuesta **HTTP 200** (2423.64 ms). Request ID: `6591cc81-6611-4bdf-9c87-0c16672df10a`.

```json
{
  "mfa_token": "<REDACTED>",
  "mfa_expires_at": "2026-11-24T14:13:35.381700Z",
  "totp_enrollment": null
}
```


### 94. /api/v1/auth/mfa/verify

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
POST https://127.0.0.1:8448/api/v1/auth/mfa/verify
```

JSON enviado:

```json
{
  "mfa_token": "<REDACTED>",
  "code": "<REDACTED>"
}
```

Respuesta **HTTP 200** (3360.35 ms). Request ID: `181615d9-1c1d-43e6-941d-205e9e0ce6fe`.

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
GET https://127.0.0.1:8448/api/v1/admin/markets/OTC
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (3976.51 ms). Request ID: `d5e73a70-a0ee-41ad-a379-ebbd5c65e32f`.

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
PUT https://127.0.0.1:8448/api/v1/admin/markets/OTC/default-schedule
```

JSON enviado:

```json
{
  "open_time": "09:30:00",
  "close_time": "16:00:00"
}
```

Respuesta **HTTP 200** (3266.49 ms). Request ID: `b02525f5-4ba9-4208-9fb8-3e18bc8a7a64`.

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
DELETE https://127.0.0.1:8448/api/v1/admin/markets/OTC/default-schedule
```

JSON enviado:

```json
null
```

Respuesta **HTTP 204** (2615.67 ms). Request ID: `1842cbe5-c41b-4a70-b9d5-ae91f5b38ecb`.

```json
null
```


### 98. /api/v1/admin/markets/OTC

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/api/v1/admin/markets/OTC
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (3529.42 ms). Request ID: `2483e72b-c50f-4078-a864-d9ea4cd48b2c`.

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
GET https://127.0.0.1:8448/api/v1/admin/compliance/atypical-operations?from=2026-11-01&to=2026-11-24&min_amount=-1
```

JSON enviado:

```json
null
```

Respuesta **HTTP 422** (1065.81 ms). Request ID: `7ad7748e-2cb6-4fae-9fc6-157310601195`.

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
GET https://127.0.0.1:8448/api/v1/admin/trading-halts?status=invalid
```

JSON enviado:

```json
null
```

Respuesta **HTTP 422** (1062.74 ms). Request ID: `f4e81778-a004-47c9-9cba-b0dd4ee4d043`.

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
GET https://127.0.0.1:8448/api/v1/admin/compliance/restrictions?status=invalid
```

JSON enviado:

```json
null
```

Respuesta **HTTP 422** (1052.45 ms). Request ID: `415bdb90-9ee5-4a48-ae98-5177ac66f0eb`.

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
GET https://127.0.0.1:8448/api/v1/admin/fee-schedules/NOEXISTE/versions
```

JSON enviado:

```json
null
```

Respuesta **HTTP 404** (2280.44 ms). Request ID: `9f47ed37-4003-4d88-bff8-7ac43b7e954c`.

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
GET https://127.0.0.1:8448/api/v1/admin/commissions?from=2026-11-01&to=2026-11-24
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (3436.76 ms). Request ID: `b6f187b2-4ff3-4f98-8b1e-db8e8fee955f`.

```json
{
  "items": [
    {
      "gross_amount": "3.67",
      "commission": null,
      "platform_share": null,
      "broker_share": null,
      "total": null,
      "net": null,
      "execution_id": "20261119093024260::97d9d3ae-79f5-41f7-9650-811d89e3b6be",
      "order_id": "61a737ea-1008-4230-967d-8a7b159d9d52",
      "user_id": "490698da-5059-4207-ae38-325809d893a5",
      "symbol": "ACCS",
      "exchange": "AMEX",
      "side": "buy",
      "qty": "1",
      "price": "3.67",
      "executed_at": "2026-11-19T14:30:24.260471Z",
      "signed_by_broker_id": null,
      "fee_version_id": null,
      "commission_rate_pct": null,
      "platform_share_pct": null,
      "commission_status": "historical_terms_unknown",
      "investor_name": "jordan beltford"
    },
    {
      "gross_amount": "355.07",
      "commission": null,
      "platform_share": null,
      "broker_share": null,
      "total": null,
      "net": null,
      "execution_id": "20261116112728987::f5a87be5-df7b-4f37-b344-1843a5a99c03",
      "order_id": "1681af57-432a-4fe1-baf8-4385eef6696e",
      "user_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "symbol": "AAPL",
      "exchange": "NASDAQ",
      "side": "buy",
      "qty": "1",
      "price": "355.07",
      "executed_at": "2026-11-16T16:27:28.987275Z",
      "signed_by_broker_id": null,
      "fee_version_id": null,
      "commission_rate_pct": null,
      "platform_share_pct": null,
      "commission_status": "historical_terms_unknown",
      "investor_name": "Prueba Ti"
    }
  ],
  "next_cursor": null,
  "totals": {
    "commission": "0",
    "platform_share": "0",
    "broker_share": "0",
    "gross_amount": "358.74",
    "historical_terms_unknown_count": 2,
    "complete": false
  },
  "by_market": {},
  "by_broker": {}
}
```


### 104. Notificaciones in_app reales de cambios de horario

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/api/v1/notifications?page_size=100
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (2250.3 ms). Request ID: `56914d46-461c-4bfc-8010-dd95d7bf3d7d`.

```json
[
  {
    "id": "74527627-7bd2-45b6-9d77-244dbd891f57",
    "event_type": "market_schedule_changes",
    "payload": {
      "after": null,
      "before": {
        "id": "f531c3fb-1316-4029-9395-dc22474bd785",
        "date": "2027-02-02",
        "closed": false,
        "open_time": "10:00:00",
        "close_time": "15:00:00",
        "market_code": "OTC"
      },
      "market": "OTC",
      "change_id": "c34c7e97-e626-4b9c-a824-3e73fc0d6731",
      "override_id": "f531c3fb-1316-4029-9395-dc22474bd785",
      "effective_from": "2027-02-02"
    },
    "created_at": "2026-11-24T14:07:36.574354Z"
  },
  {
    "id": "c09b7fbf-e823-40c7-a508-8fc0033901d1",
    "event_type": "market_schedule_changes",
    "payload": {
      "after": {
        "id": "f531c3fb-1316-4029-9395-dc22474bd785",
        "date": "2027-02-02",
        "closed": false,
        "open_time": "10:00:00",
        "close_time": "15:00:00",
        "market_code": "OTC"
      },
      "before": {
        "id": "f531c3fb-1316-4029-9395-dc22474bd785",
        "date": "2027-02-02",
        "closed": true,
        "open_time": null,
        "close_time": null,
        "market_code": "OTC"
      },
      "market": "OTC",
      "change_id": "1db7e9ed-354d-4192-8d03-53c4bf15f6a3",
      "override_id": "f531c3fb-1316-4029-9395-dc22474bd785",
      "effective_from": "2027-02-02"
    },
    "created_at": "2026-11-24T14:07:34.356764Z"
  },
  {
    "id": "f20edbc7-177e-46f8-a7a6-8b51e7331bfc",
    "event_type": "market_schedule_changes",
    "payload": {
      "after": {
        "id": "f531c3fb-1316-4029-9395-dc22474bd785",
        "date": "2027-02-02",
        "closed": true,
        "open_time": null,
        "close_time": null,
        "market_code": "OTC"
      },
      "before": null,
      "market": "OTC",
      "change_id": "2d4f0b69-e469-413b-b3e7-b7163e1cfae6",
      "override_id": "f531c3fb-1316-4029-9395-dc22474bd785",
      "effective_from": "2027-02-02"
    },
    "created_at": "2026-11-24T14:07:32.126511Z"
  },
  {
    "id": "2a84f44f-51a1-4971-8ddf-e851f5f3055a",
    "event_type": "daily_summary",
    "payload": {
      "link": "/portfolio/reports/5e7f603a-4529-4403-a7c6-230454937f56",
      "period": {
        "to": "2026-11-23",
        "from": "2026-11-23"
      },
      "volume": "0.00",
      "report_id": "5e7f603a-4529-4403-a7c6-230454937f56",
      "commissions": "0.00",
      "report_type": "daily_summary",
      "realized_pnl": {
        "net": "0.00",
        "gross": "0.00"
      },
      "profitability": "-1.50",
      "unrealized_pnl": "-5.33",
      "executions_count": 0
    },
    "created_at": "2026-11-23T21:57:56.646166Z"
  },
  {
    "id": "81137236-c598-42d2-abe2-413bc2d914e3",
    "event_type": "daily_summary",
    "payload": {
      "link": "/portfolio/reports/1c9085ec-17ae-4fc1-bb86-4455a8b63ad2",
      "period": {
        "to": "2026-11-20",
        "from": "2026-11-20"
      },
      "volume": "0.00",
      "report_id": "1c9085ec-17ae-4fc1-bb86-4455a8b63ad2",
      "commissions": "0.00",
      "report_type": "daily_summary",
      "realized_pnl": {
        "net": "0.00",
        "gross": "0.00"
      },
      "profitability": "-3.29",
      "unrealized_pnl": "-11.67",
      "executions_count": 0
    },
    "created_at": "2026-11-21T00:31:11.953243Z"
  },
  {
    "id": "acd4cf12-4549-4fd0-9b1f-9f243ba22c61",
    "event_type": "daily_summary",
    "payload": {
      "link": "/portfolio/reports/f3277e99-2e81-4db7-9891-b09c8bc8fcd7",
      "period": {
        "to": "2026-11-19",
        "from": "2026-11-19"
      },
      "volume": "0.00",
      "report_id": "f3277e99-2e81-4db7-9891-b09c8bc8fcd7",
      "commissions": "0.00",
      "report_type": "daily_summary",
      "realized_pnl": {
        "net": "0.00",
        "gross": "0.00"
      },
      "profitability": "-1.32",
      "unrealized_pnl": "-4.67",
      "executions_count": 0
    },
    "created_at": "2026-11-20T01:29:25.883990Z"
  },
  {
    "id": "8853d3e5-d623-49c3-bc19-90bf572280b6",
    "event_type": "market_open",
    "payload": {
      "event": "market_open",
      "next_open": "2026-11-20T09:30:00-05:00",
      "observed_at": "2026-11-19T09:30:53.371599-05:00"
    },
    "created_at": "2026-11-19T14:30:55.603993Z"
  },
  {
    "id": "47cf5e58-d308-485d-b695-c650b5fa552a",
    "event_type": "daily_summary",
    "payload": {
      "link": "/portfolio/reports/a3f3b12f-ba12-4105-b687-a46c2eca81b7",
      "period": {
        "to": "2026-11-18",
        "from": "2026-11-18"
      },
      "volume": "0.00",
      "report_id": "a3f3b12f-ba12-4105-b687-a46c2eca81b7",
      "commissions": "0.00",
      "report_type": "daily_summary",
      "realized_pnl": {
        "net": "0.00",
        "gross": "0.00"
      },
      "profitability": "-0.93",
      "unrealized_pnl": "-3.30",
      "executions_count": 0
    },
    "created_at": "2026-11-19T00:29:32.538732Z"
  },
  {
    "id": "5688744c-e80b-4b34-adeb-bb2e11712df9",
    "event_type": "proposal_updates",
    "payload": {
      "status": "approved",
      "proposal_id": "6eac1e18-d2e4-4354-90ed-cfa93a400b76"
    },
    "created_at": "2026-11-17T03:55:11.482061Z"
  },
  {
    "id": "0b18f23d-2625-451f-80c4-08e4c6b0a7f6",
    "event_type": "proposal_updates",
    "payload": {
      "message_id": "a04fb292-a63c-4566-bedc-14a92473ef38",
      "proposal_id": "6eac1e18-d2e4-4354-90ed-cfa93a400b76"
    },
    "created_at": "2026-11-17T03:54:21.120615Z"
  },
  {
    "id": "484c62f4-ec0c-49a6-a659-87a488b782a2",
    "event_type": "proposal_updates",
    "payload": {
      "status": "sent",
      "proposal_id": "6eac1e18-d2e4-4354-90ed-cfa93a400b76"
    },
    "created_at": "2026-11-17T03:54:05.570221Z"
  },
  {
    "id": "1810b777-510e-4729-a162-4a17dbd4d829",
    "event_type": "proposal_updates",
    "payload": {
      "status": "conversion_failed",
      "proposal_id": "e178a0b5-cdec-4e3e-a8e9-eb6ef573845d"
    },
    "created_at": "2026-11-17T03:50:01.672541Z"
  },
  {
    "id": "a501c72b-cd07-4459-a107-18ac5927831b",
    "event_type": "proposal_updates",
    "payload": {
      "message_id": "bcc926a4-3343-4b9e-8619-db3f1b239ae1",
      "proposal_id": "e178a0b5-cdec-4e3e-a8e9-eb6ef573845d"
    },
    "created_at": "2026-11-17T03:49:19.227964Z"
  },
  {
    "id": "3842babd-2511-43f9-82bb-47b7451adc17",
    "event_type": "proposal_updates",
    "payload": {
      "status": "sent",
      "proposal_id": "e178a0b5-cdec-4e3e-a8e9-eb6ef573845d"
    },
    "created_at": "2026-11-17T03:49:04.945974Z"
  },
  {
    "id": "d04340c8-c025-4673-87fc-6a54bcc4d4c7",
    "event_type": "broker_link_updates",
    "payload": {
      "status": "active",
      "link_id": "cb0aed62-405a-49fa-b931-b2c2d79dedb5"
    },
    "created_at": "2026-11-17T03:47:50.384041Z"
  },
  {
    "id": "44662567-af2c-406d-8d49-ee1e5c88cd4e",
    "event_type": "daily_summary",
    "payload": {
      "link": "/portfolio/reports/83c8a583-4424-4998-b3ae-d31c27df2ce8",
      "period": {
        "to": "2026-11-16",
        "from": "2026-11-16"
      },
      "volume": "355.07",
      "report_id": "83c8a583-4424-4998-b3ae-d31c27df2ce8",
      "commissions": "7.10",
      "report_type": "daily_summary",
      "realized_pnl": {
        "net": "0.00",
        "gross": "0.00"
      },
      "profitability": "-0.68",
      "unrealized_pnl": "-2.41",
      "executions_count": 1
    },
    "created_at": "2026-11-16T22:19:44.821954Z"
  },
  {
    "id": "2dbfdf00-42dd-4c25-8547-b1a76bb5f09e",
    "event_type": "market_close",
    "payload": {
      "event": "market_close",
      "next_close": "2026-11-17T16:00:00-05:00",
      "observed_at": "2026-11-16T16:00:31.960543-05:00"
    },
    "created_at": "2026-11-16T21:00:33.280719Z"
  },
  {
    "id": "1c026040-fe77-4822-b4bb-a15eec319594",
    "event_type": "market_close",
    "payload": {
      "event": "market_close",
      "next_close": "2026-11-17T16:00:00-05:00",
      "observed_at": "2026-11-16T16:00:04.623768-05:00"
    },
    "created_at": "2026-11-16T21:00:06.403027Z"
  },
  {
    "id": "e59cd10f-451b-4350-bd11-106e7036720e",
    "event_type": "market_close",
    "payload": {
      "event": "market_close",
      "next_close": "2026-11-13T16:00:00-05:00",
      "observed_at": "2026-11-12T16:00:43.068265-05:00"
    },
    "created_at": "2026-11-12T21:00:44.338281Z"
  },
  {
    "id": "6fc07be0-45fd-4d15-9811-eb8ed8a3c746",
    "event_type": "market_close",
    "payload": {
      "event": "market_close",
      "next_close": "2026-11-13T16:00:00-05:00",
      "observed_at": "2026-11-12T16:00:21.436731-05:00"
    },
    "created_at": "2026-11-12T21:00:22.159552Z"
  },
  {
    "id": "1dc82f23-6e90-4e17-8646-2fbec8df0f2f",
    "event_type": "market_close",
    "payload": {
      "event": "market_close",
      "next_close": "2026-11-12T16:00:00-05:00",
      "observed_at": "2026-11-11T16:00:04.346123-05:00"
    },
    "created_at": "2026-11-11T21:00:05.544805Z"
  }
]
```


### 105. Verificar roles finales de broker

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/api/v1/admin/users/19f5fcb4-9a1d-4d3e-affe-96da0057cf2d/roles
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (2525.41 ms). Request ID: `3db37798-eee9-46c2-b296-a11e5d98ac0a`.

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
    "id": "0a94440a-2707-44d8-8b51-bf9760d642a1",
    "role": "analyst",
    "valid_from": "2026-11-24T14:06:19.980220Z",
    "valid_to": "2026-11-24T14:06:41.069425Z",
    "effective": false,
    "status": "ACTIVE",
    "cancelled_at": null,
    "cancelled_by": null
  }
]
```


### 106. Verificar roles finales de broker2

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[200]`.

```http
GET https://127.0.0.1:8448/api/v1/admin/users/39bf8e8a-d3ec-4172-82c5-99e9508ffce1/roles
```

JSON enviado:

```json
null
```

Respuesta **HTTP 200** (2767.77 ms). Request ID: `6fec4b22-d87c-4907-a2fc-21dc7f1a1d16`.

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
    "id": "48e892af-ef6d-47e6-b955-134489c65cfe",
    "role": "auditor",
    "valid_from": "2026-11-24T14:06:15.934960Z",
    "valid_to": "2026-11-24T14:06:36.733567Z",
    "effective": false,
    "status": "ACTIVE",
    "cancelled_at": null,
    "cancelled_by": null
  }
]
```


### 107. /api/v1/auth/logout

**Actor:** `admin`. **Resultado:** OK; HTTP esperado: `[204]`.

```http
POST https://127.0.0.1:8448/api/v1/auth/logout
```

JSON enviado:

```json
null
```

Respuesta **HTTP 204** (1265.49 ms). Request ID: `b340f503-034d-4845-a056-d5ca294d21c2`.

```json
null
```


### 108. /api/v1/auth/logout

**Actor:** `investor`. **Resultado:** OK; HTTP esperado: `[204]`.

```http
POST https://127.0.0.1:8448/api/v1/auth/logout
```

JSON enviado:

```json
null
```

Respuesta **HTTP 204** (1130.77 ms). Request ID: `e00660c5-ce44-4b91-ab85-268610659cc8`.

```json
null
```
