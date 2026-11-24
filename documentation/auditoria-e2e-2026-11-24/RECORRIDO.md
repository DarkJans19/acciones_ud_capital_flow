# Recorrido integrado de los siete módulos

**ASGI + PostgreSQL real; JWT/cookies/MFA/RBAC reales; Alpaca y Stripe simulados.**
Los usuarios y recursos son sintéticos. No hay overrides de `get_current_user`.
El administrador y catálogo inicial se preparan en SQL; el resto se opera por HTTP.
Las rutas de esta tabla llevan el prefijo `/api/v1`.

Solicitudes: **79**. Resultados inesperados: **0**.

| # | Actor | Método | Ruta | Esperado | Real | Código de error |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | admin | POST | `/auth/login` | 200 | 200 | — |
| 2 | admin | POST | `/auth/mfa/verify` | 200 | 200 | — |
| 3 | investor | POST | `/auth/register` | 201 | 201 | — |
| 4 | investor | POST | `/auth/login` | 200 | 200 | — |
| 5 | investor | POST | `/auth/mfa/verify` | 200 | 200 | — |
| 6 | other | POST | `/auth/register` | 201 | 201 | — |
| 7 | other | POST | `/auth/login` | 200 | 200 | — |
| 8 | other | POST | `/auth/mfa/verify` | 200 | 200 | — |
| 9 | broker | POST | `/auth/register/broker` | 201 | 201 | — |
| 10 | broker | POST | `/auth/login` | 200 | 200 | — |
| 11 | broker | POST | `/auth/mfa/verify` | 200 | 200 | — |
| 12 | auditor | POST | `/auth/register` | 201 | 201 | — |
| 13 | auditor | POST | `/auth/login` | 200 | 200 | — |
| 14 | auditor | POST | `/auth/mfa/verify` | 200 | 200 | — |
| 15 | analyst | POST | `/auth/register` | 201 | 201 | — |
| 16 | analyst | POST | `/auth/login` | 200 | 200 | — |
| 17 | analyst | POST | `/auth/mfa/verify` | 200 | 200 | — |
| 18 | admin | POST | `/admin/users/93b8ad1a-97c8-4182-bbe7-6a80373c4a38/roles` | 201 | 201 | — |
| 19 | admin | POST | `/admin/users/336cac7b-e80a-4824-974a-33987e202a6f/roles` | 201 | 201 | — |
| 20 | broker | GET | `/wallet/balances` | 403 | 403 | FORBIDDEN |
| 21 | admin | POST | `/admin/users/1b7ed0b2-325c-487a-be07-95d17e24ff11/broker-activation` | 200 | 200 | — |
| 22 | investor | GET | `/admin/fee-schedules` | 403 | 403 | FORBIDDEN |
| 23 | broker | GET | `/wallet/balances` | 409 | 409 | WALLET_ACCOUNT_REQUIRED |
| 24 | investor | POST | `/kyc/account` | 201 | 201 | — |
| 25 | investor | GET | `/kyc/status` | 200 | 200 | — |
| 26 | investor | GET | `/wallet/balances` | 200 | 200 | — |
| 27 | investor | GET | `/watchlists` | 403 | 403 | PREMIUM_REQUIRED |
| 28 | investor | POST | `/subscriptions/checkout` | 201 | 201 | — |
| 29 | anonymous | POST | `/webhooks/stripe` | 400 | 400 | WEBHOOK_SIGNATURE_INVALID |
| 30 | anonymous | POST | `/webhooks/stripe` | 200 | 200 | — |
| 31 | anonymous | POST | `/webhooks/stripe` | 200 | 200 | — |
| 32 | investor | GET | `/users/me` | 200 | 200 | — |
| 33 | investor | GET | `/instruments/search` | 200 | 200 | — |
| 34 | investor | GET | `/instruments/TD2303F3/quote` | 200 | 200 | — |
| 35 | investor | POST | `/watchlists` | 201 | 201 | — |
| 36 | investor | POST | `/watchlists/34035eb2-bf93-48e3-b43c-27d5df3da81e/items` | 200 | 200 | — |
| 37 | investor | POST | `/watchlists/34035eb2-bf93-48e3-b43c-27d5df3da81e/items` | 409 | 409 | SYMBOL_ALREADY_IN_WATCHLIST |
| 38 | investor | POST | `/wallet/bank-relationships` | 201 | 201 | — |
| 39 | other | GET | `/wallet/bank-relationships/565d95f6-c643-4b41-adf8-9d3e852cb66b` | 404 | 404 | NOT_FOUND |
| 40 | investor | POST | `/wallet/deposits` | 201 | 201 | — |
| 41 | investor | POST | `/wallet/deposits` | 201 | 201 | — |
| 42 | investor | POST | `/wallet/deposits` | 409 | 409 | IDEMPOTENCY_CONFLICT |
| 43 | other | GET | `/wallet/transfers/750c7215-4f6d-49b7-9ca6-248283301500` | 404 | 404 | NOT_FOUND |
| 44 | admin | GET | `/admin/fee-schedules` | 200 | 200 | — |
| 45 | investor | GET | `/commissions/quote` | 200 | 200 | — |
| 46 | investor | POST | `/orders/preview` | 200 | 200 | — |
| 47 | investor | POST | `/orders` | 201 | 201 | — |
| 48 | investor | POST | `/orders` | 201 | 201 | — |
| 49 | other | GET | `/orders/7a9088a7-00f0-495f-83e8-00c7acc36bbf` | 404 | 404 | ORDER_NOT_FOUND |
| 50 | investor | GET | `/portfolio/positions` | 200 | 200 | — |
| 51 | investor | POST | `/portfolio/reports` | 201 | 201 | — |
| 52 | other | GET | `/portfolio/reports/bf4ca8f2-fe1f-4bbc-9a58-2bec7161b9d9` | 404 | 404 | NOT_FOUND |
| 53 | investor | POST | `/broker-links` | 201 | 201 | — |
| 54 | other | POST | `/broker-links/2e54426d-373c-46e1-98d9-c197e13d4c25/end` | 404 | 404 | LINK_NOT_FOUND |
| 55 | broker | POST | `/broker/link-requests/2e54426d-373c-46e1-98d9-c197e13d4c25/accept` | 200 | 200 | — |
| 56 | broker | POST | `/broker/proposals` | 201 | 201 | — |
| 57 | other | GET | `/proposals/8ba40332-79a0-458f-8b11-05f5b9799c6b` | 404 | 404 | PROPOSAL_NOT_FOUND |
| 58 | investor | POST | `/proposals/8ba40332-79a0-458f-8b11-05f5b9799c6b/decision` | 200 | 200 | — |
| 59 | investor | POST | `/broker-links/2e54426d-373c-46e1-98d9-c197e13d4c25/end` | 200 | 200 | — |
| 60 | broker | GET | `/broker/clients/94ff0fa9-2184-44e7-be88-5dff4902354e/orders` | 404 | 404 | CLIENT_NOT_FOUND |
| 61 | admin | GET | `/admin/audit-trail` | 200 | 200 | — |
| 62 | auditor | GET | `/admin/audit-trail` | 200 | 200 | — |
| 63 | analyst | GET | `/admin/kpis` | 200 | 200 | — |
| 64 | analyst | GET | `/admin/audit-trail` | 403 | 403 | FORBIDDEN |
| 65 | auditor | GET | `/admin/kpis` | 403 | 403 | FORBIDDEN |
| 66 | auditor | POST | `/admin/trading-halts` | 403 | 403 | FORBIDDEN |
| 67 | analyst | POST | `/admin/trading-halts` | 403 | 403 | FORBIDDEN |
| 68 | investor | POST | `/auth/logout` | 204 | 204 | — |
| 69 | investor | GET | `/users/me` | 401 | 401 | NOT_AUTHENTICATED |
| 70 | other | POST | `/auth/logout` | 204 | 204 | — |
| 71 | other | GET | `/users/me` | 401 | 401 | NOT_AUTHENTICATED |
| 72 | broker | POST | `/auth/logout` | 204 | 204 | — |
| 73 | broker | GET | `/users/me` | 401 | 401 | NOT_AUTHENTICATED |
| 74 | admin | POST | `/auth/logout` | 204 | 204 | — |
| 75 | admin | GET | `/users/me` | 401 | 401 | NOT_AUTHENTICATED |
| 76 | auditor | POST | `/auth/logout` | 204 | 204 | — |
| 77 | auditor | GET | `/users/me` | 401 | 401 | NOT_AUTHENTICATED |
| 78 | analyst | POST | `/auth/logout` | 204 | 204 | — |
| 79 | analyst | GET | `/users/me` | 401 | 401 | NOT_AUTHENTICATED |
