# E2E manual: flujo principal de portfolio (fase 1)

Fecha de ejecuci?n: 2026-11-16. Usuario: `investor.ti@accionesud.com`.

## Entorno y resultado

Prueba ejecutada sobre la aplicaci?n FastAPI mediante transporte ASGI HTTPS (`https://api.test`), con autenticaci?n, base de datos y proveedores del `.env` reales. No se usaron overrides de autenticaci?n ni fakes de Alpaca. No se inici? un servidor Uvicorn para esta ejecuci?n.

Resultado: **17/17 comprobaciones HTTP correctas**. Se comprob? adem?s que el reporte recuperado coincide exactamente con el creado y que el valor de mercado y resultado no realizado de las posiciones son consistentes con sus cantidades, precios y costos.

Se detect? la migraci?n pendiente `0008_portfolio_schema`: las rutas de reportes devolv?an 500 `DATABASE_SCHEMA_ERROR`. Se verific? la revisi?n 0007 y se aplic? ?nicamente la migraci?n aditiva 0008 mediante `uv run alembic upgrade 0008_portfolio_schema`. La repetici?n completa pas?.

Reporte persistido durante la prueba: `0098a5f2-a0af-4661-ba0f-fcbc3df09ea6`. Se utilizaron posiciones y ejecuciones existentes; no se enviaron nuevas ?rdenes ni transferencias. Los trabajos de fondo se deshabilitaron para esta ejecuci?n; su programaci?n no forma parte de esta prueba HTTP. La revisi?n general de los dem?s endpoints queda para la fase 2.

## C?mo repetir

1. Configura el `.env` del mismo entorno. No copies secretos a este documento.
2. Verifica `uv run alembic current`: debe indicar `0008_portfolio_schema`.
3. Levanta la API con `uv run uvicorn acciones_ud.main:app --host 127.0.0.1 --port 8000` y usa `http://localhost:8000` como `BASE_URL`, o la URL HTTPS de tu despliegue.
4. Ejecuta las peticiones en orden desde Postman o un cliente HTTP. El login devuelve `mfa_token`: ?salo en el JSON del segundo paso de autenticaci?n.
5. Genera el c?digo TOTP vigente con tu autenticador. No uses los c?digos de recuperaci?n para este recorrido.
6. Tras verificar MFA, conserva las cookies `access_token` y `refresh_token` de `Set-Cookie`. Son Secure: usa HTTPS o env?a expl?citamente `Cookie: access_token={{access_token}}; refresh_token={{refresh_token}}` en tu cliente local HTTP. No cambies la pol?tica de cookies del backend.
7. Sustituye las fechas por el periodo que quieras consultar (fechas inclusivas de Nueva York, m?ximo 366 d?as). Sustituye el identificador del reporte por el devuelto por tu propio POST.

Los valores `${E2E_PASSWORD}`, `${MFA_TOKEN}` y `${CURRENT_TOTP}` son marcadores: sustit?yelos en el cliente HTTP. La contrase?a y el secreto TOTP compartidos no se guardan aqu?. Los GET no necesitan body. Los POST usan `Content-Type: application/json`.

## Peticiones ejecutadas y evidencia

### 1. GET /health

Estado observado y esperado: **HTTP 200**.

Sin JSON de entrada. Los filtros, cuando existen, est?n en la URL.

Respuesta observada:

```json
{
  "status": "ok"
}
```

### 2. GET /api/v1/portfolio/positions

Estado observado y esperado: **HTTP 401**.

Sin JSON de entrada. Los filtros, cuando existen, est?n en la URL.

Respuesta observada:

```json
{
  "code": "NOT_AUTHENTICATED",
  "message": "Authentication required.",
  "details": null
}
```

### 3. POST /api/v1/auth/login

Estado observado y esperado: **HTTP 200**.

JSON de entrada:

```json
{
  "email": "investor.ti@accionesud.com",
  "password": "${E2E_PASSWORD}"
}
```

Respuesta observada (datos de autenticaci?n omitidos):

```json
{
  "omitted": "Authentication secrets"
}
```

### 4. POST /api/v1/auth/mfa/verify

Estado observado y esperado: **HTTP 200**.

JSON de entrada:

```json
{
  "mfa_token": "${MFA_TOKEN}",
  "code": "${CURRENT_TOTP}"
}
```

Respuesta observada (datos de autenticaci?n omitidos):

```json
{
  "omitted": "Authentication secrets"
}
```

### 5. GET /api/v1/users/me

Estado observado y esperado: **HTTP 200**.

Sin JSON de entrada. Los filtros, cuando existen, est?n en la URL.

Respuesta observada:

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
  "is_premium": false,
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

### 6. GET /api/v1/kyc/status

Estado observado y esperado: **HTTP 200**.

Sin JSON de entrada. Los filtros, cuando existen, est?n en la URL.

Respuesta observada:

```json
{
  "has_account": true,
  "status": "ACTIVE",
  "status_updated_at": "2026-11-11T15:38:14.716608Z",
  "can_trade": true,
  "stale": false
}
```

### 7. GET /api/v1/wallet/balances

Estado observado y esperado: **HTTP 200**.

Sin JSON de entrada. Los filtros, cuando existen, est?n en la URL.

Respuesta observada:

```json
{
  "status": "ACTIVE",
  "currency": "USD",
  "cash": "1143.92",
  "cash_withdrawable": "143.92",
  "buying_power": "1143.92",
  "equity": "1495.66",
  "portfolio_value": "1495.66",
  "long_market_value": "351.74",
  "retrieved_at": "2026-11-16T19:26:59.489238Z",
  "unavailable": false,
  "sandbox_notice": "Virtual funds in the Alpaca sandbox environment. They do not represent real money."
}
```

### 8. GET /api/v1/users/preferences/portfolio

Estado observado y esperado: **HTTP 200**.

Sin JSON de entrada. Los filtros, cuando existen, est?n en la URL.

Respuesta observada:

```json
{
  "view_type": "table",
  "sort_by": "symbol",
  "sort_direction": "asc",
  "hide_threshold": "0.00"
}
```

### 9. GET /api/v1/portfolio/positions

Estado observado y esperado: **HTTP 200**.

Sin JSON de entrada. Los filtros, cuando existen, est?n en la URL.

Respuesta observada:

```json
{
  "positions": [
    {
      "symbol": "AAPL",
      "exchange": "NASDAQ",
      "sector": null,
      "qty": "1.000000000",
      "reserved_qty": "0E-9",
      "price": "351.7400",
      "price_source": "market_data",
      "average_cost": "355.0700",
      "market_value": "351.74",
      "cost_basis": "355.07",
      "unrealized_pnl": "-3.33",
      "reconciliation_mismatch": false
    }
  ],
  "totals": {
    "market_value": "351.74",
    "cost_basis": "355.07",
    "unrealized_pnl": "-3.33"
  },
  "view_type": "table",
  "positions_as_of": "2026-11-16T19:27:03.582900Z",
  "currency": "USD"
}
```

### 10. GET /api/v1/portfolio/executions?from=2026-11-16&to=2026-11-16&page_size=1

Estado observado y esperado: **HTTP 200**.

Sin JSON de entrada. Los filtros, cuando existen, est?n en la URL.

Respuesta observada:

```json
{
  "items": [
    {
      "execution_id": "20261116112728987::f5a87be5-df7b-4f37-b344-1843a5a99c03",
      "order_id": "1681af57-432a-4fe1-baf8-4385eef6696e",
      "symbol": "AAPL",
      "exchange": "NASDAQ",
      "side": "buy",
      "qty": "1.000000000",
      "price": "355.0700",
      "executed_at": "2026-11-16T16:27:28.987275Z",
      "commission": "7.10",
      "commission_source": "reference"
    }
  ],
  "next_cursor": null
}
```

### 11. GET /api/v1/portfolio/statistics?from=2026-11-16&to=2026-11-16

Estado observado y esperado: **HTTP 200**.

Sin JSON de entrada. Los filtros, cuando existen, est?n en la URL.

Respuesta observada:

```json
{
  "execution_count": 1,
  "buy_count": 1,
  "sell_count": 0,
  "volume": "355.07",
  "by_market": [
    {
      "key": "NASDAQ",
      "volume": "355.07",
      "percentage": "100.00"
    }
  ],
  "by_instrument": [
    {
      "key": "AAPL",
      "volume": "355.07",
      "percentage": "100.00"
    }
  ],
  "by_sector": [
    {
      "key": "unclassified",
      "volume": "355.07",
      "percentage": "100.00"
    }
  ]
}
```

### 12. GET /api/v1/portfolio/risk-profile

Estado observado y esperado: **HTTP 200**.

Sin JSON de entrada. Los filtros, cuando existen, est?n en la URL.

Respuesta observada:

```json
{
  "window_days": 90,
  "f": "0.78",
  "c": "100.00",
  "e": "23.52",
  "t": "5.93",
  "risk_score": "37.26",
  "classification": "moderate",
  "equity_unavailable": false,
  "metrics": {
    "execution_count": 1,
    "executions_per_week": "0.08",
    "volume": "355.07",
    "markets": [
      "NASDAQ"
    ],
    "instruments": [
      "AAPL"
    ],
    "asset_distribution": {
      "AAPL": "100.00"
    },
    "window_from": "2026-08-18T19:27:14.109114Z",
    "window_to": "2026-11-16T19:27:14.109114Z"
  }
}
```

### 13. POST /api/v1/portfolio/reports

Estado observado y esperado: **HTTP 201**.

JSON de entrada:

```json
{
  "from": "2026-11-16",
  "to": "2026-11-16"
}
```

Respuesta observada:

```json
{
  "id": "0098a5f2-a0af-4661-ba0f-fcbc3df09ea6",
  "owner_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
  "owner_role": "investor",
  "type": "on_demand",
  "period": {
    "from": "2026-11-16",
    "to": "2026-11-16"
  },
  "positions_as_of": "2026-11-16T19:27:23.839306Z",
  "generated_at": "2026-11-16T19:27:27.347709Z",
  "notified_at": null,
  "content": {
    "market_value": "351.80",
    "cost_basis": "355.07",
    "volume": "355.07",
    "realized_pnl": {
      "gross": "0.00",
      "net": "0.00"
    },
    "unrealized_pnl": "-3.27",
    "commissions": "7.10",
    "profitability": "-0.92",
    "currency": "USD",
    "period": {
      "from": "2026-11-16",
      "to": "2026-11-16"
    },
    "positions_as_of": "2026-11-16T19:27:23.839306+00:00",
    "positions": [
      {
        "symbol": "AAPL",
        "exchange": "NASDAQ",
        "sector": null,
        "qty": "1.000000000",
        "reserved_qty": "0E-9",
        "price": "351.8000",
        "price_source": "market_data",
        "average_cost": "355.0700",
        "market_value": "351.80",
        "cost_basis": "355.07",
        "unrealized_pnl": "-3.27",
        "reconciliation_mismatch": false
      }
    ],
    "executions_count": 1,
    "executions": [
      {
        "execution_id": "20261116112728987::f5a87be5-df7b-4f37-b344-1843a5a99c03",
        "order_id": "1681af57-432a-4fe1-baf8-4385eef6696e",
        "symbol": "AAPL",
        "exchange": "NASDAQ",
        "side": "buy",
        "qty": "1.000000000",
        "price": "355.0700",
        "executed_at": "2026-11-16T16:27:28.987275+00:00",
        "commission": "7.10",
        "commission_source": "reference"
      }
    ],
    "asset_summary": {
      "market_value": "351.80",
      "cost_basis": "355.07",
      "position_count": 1
    },
    "report_type": "on_demand"
  }
}
```

### 14. GET /api/v1/portfolio/reports?page_size=1

Estado observado y esperado: **HTTP 200**.

Sin JSON de entrada. Los filtros, cuando existen, est?n en la URL.

Respuesta observada:

```json
{
  "items": [
    {
      "id": "0098a5f2-a0af-4661-ba0f-fcbc3df09ea6",
      "owner_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
      "owner_role": "investor",
      "type": "on_demand",
      "period": {
        "from": "2026-11-16",
        "to": "2026-11-16"
      },
      "positions_as_of": "2026-11-16T19:27:23.839306Z",
      "generated_at": "2026-11-16T19:27:27.347709Z",
      "notified_at": null
    }
  ],
  "next_cursor": null
}
```

### 15. GET /api/v1/portfolio/reports/0098a5f2-a0af-4661-ba0f-fcbc3df09ea6

Estado observado y esperado: **HTTP 200**.

Sin JSON de entrada. Los filtros, cuando existen, est?n en la URL.

Respuesta observada:

```json
{
  "id": "0098a5f2-a0af-4661-ba0f-fcbc3df09ea6",
  "owner_id": "c0674321-9a64-4f13-9070-e57dfb35b4e8",
  "owner_role": "investor",
  "type": "on_demand",
  "period": {
    "from": "2026-11-16",
    "to": "2026-11-16"
  },
  "positions_as_of": "2026-11-16T19:27:23.839306Z",
  "generated_at": "2026-11-16T19:27:27.347709Z",
  "notified_at": null,
  "content": {
    "period": {
      "to": "2026-11-16",
      "from": "2026-11-16"
    },
    "volume": "355.07",
    "currency": "USD",
    "positions": [
      {
        "qty": "1.000000000",
        "price": "351.8000",
        "sector": null,
        "symbol": "AAPL",
        "exchange": "NASDAQ",
        "cost_basis": "355.07",
        "average_cost": "355.0700",
        "market_value": "351.80",
        "price_source": "market_data",
        "reserved_qty": "0E-9",
        "unrealized_pnl": "-3.27",
        "reconciliation_mismatch": false
      }
    ],
    "cost_basis": "355.07",
    "executions": [
      {
        "qty": "1.000000000",
        "side": "buy",
        "price": "355.0700",
        "symbol": "AAPL",
        "exchange": "NASDAQ",
        "order_id": "1681af57-432a-4fe1-baf8-4385eef6696e",
        "commission": "7.10",
        "executed_at": "2026-11-16T16:27:28.987275+00:00",
        "execution_id": "20261116112728987::f5a87be5-df7b-4f37-b344-1843a5a99c03",
        "commission_source": "reference"
      }
    ],
    "commissions": "7.10",
    "report_type": "on_demand",
    "market_value": "351.80",
    "realized_pnl": {
      "net": "0.00",
      "gross": "0.00"
    },
    "asset_summary": {
      "cost_basis": "355.07",
      "market_value": "351.80",
      "position_count": 1
    },
    "profitability": "-0.92",
    "unrealized_pnl": "-3.27",
    "positions_as_of": "2026-11-16T19:27:23.839306+00:00",
    "executions_count": 1
  }
}
```

### 16. GET /api/v1/portfolio/statistics?from=2026-02-01&to=2026-01-01

Estado observado y esperado: **HTTP 422**.

Sin JSON de entrada. Los filtros, cuando existen, est?n en la URL.

Respuesta observada:

```json
{
  "code": "INVALID_PERIOD",
  "message": "Invalid period.",
  "details": {
    "field": "from",
    "reason": "from_after_to"
  }
}
```

### 17. GET /api/v1/portfolio/broker/reports

Estado observado y esperado: **HTTP 403**.

Sin JSON de entrada. Los filtros, cuando existen, est?n en la URL.

Respuesta observada:

```json
{
  "code": "FORBIDDEN",
  "message": "Required role is not active.",
  "details": null
}
```

## Efectos y l?mites

El recorrido abre una sesi?n del inversionista y crea un reporte `on_demand` inmutable. Los importes y precios reflejan la ejecuci?n indicada; pueden cambiar al repetir las consultas de mercado. HTTP 200 de saldos debe interpretarse junto con `unavailable`, y HTTP 200 de posiciones junto con `reconciliation_mismatch`.

Esta fase valida el recorrido del inversionista y los rechazos de seguridad indicados. No acredita todos los endpoints de administraci?n, broker, ?rdenes, Stripe ni tareas programadas. Continuar con esa revisi?n requiere la siguiente fase solicitada por el usuario.
