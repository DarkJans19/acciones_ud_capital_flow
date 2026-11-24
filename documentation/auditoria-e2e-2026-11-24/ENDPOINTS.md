# Matriz de endpoints HTTP

**164 operaciones / 141 rutas** de OpenAPI.
Cada operación es un par método+ruta, no un caso funcional completo.

- Sin cookie / cookie inválida: ASGI aislado, solo rutas protegidas; 401 esperado.
- Anónimo real: HTTPS y configuración real; cuerpos vacíos y UUID ficticios.
- Columnas de cuentas: barrido GET autenticado; no se ejecutan mutaciones
  financieras en la base compartida. `—` significa no ejecutado en ese barrido.
- 403 por rol/premium y 404 por UUID inexistente pueden ser resultados correctos.
- Cinco 422 de candles provienen de parámetros genéricos inválidos; la repetición
  con fechas ISO válidas devolvió 200 (`live-followup.json`).
- El perfil público del broker es público por contrato, no un bypass.
- Esta tabla no demuestra cobertura de todas las ramas ni todos los cuerpos.

| Método | Ruta | Acceso | Sin cookie | JWT inválido | Anónimo real | admin | admin2 | broker | investor | broker2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/auth/interest-options` | público | — | — | 200 | 200 | 200 | 200 | 200 | 200 |
| POST | `/api/v1/auth/register` | público | — | — | 422 | — | — | — | — | — |
| POST | `/api/v1/auth/register/broker` | público | — | — | 422 | — | — | — | — | — |
| POST | `/api/v1/auth/login` | público | — | — | 422 | — | — | — | — | — |
| POST | `/api/v1/auth/mfa/verify` | público | — | — | 422 | — | — | — | — | — |
| POST | `/api/v1/admin/users/administrators` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/admin/users/{user_id}/broker-activation` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/admin/users` | sesión | 401 | 401 | 401 | 200 | 200 | 403 | 403 | 403 |
| GET | `/api/v1/admin/users/{user_id}` | sesión | 401 | 401 | 401 | 200 | 200 | 403 | 403 | 403 |
| POST | `/api/v1/admin/kyc/{user_id}/reconcile` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| PUT | `/api/v1/admin/users/{user_id}/premium` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/admin/users/{user_id}/roles` | sesión | 401 | 401 | 401 | 200 | 200 | 403 | 403 | 403 |
| POST | `/api/v1/admin/users/{user_id}/roles` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| PUT | `/api/v1/admin/users/{user_id}/roles/{assignment_id}` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/admin/users/{user_id}/roles/{assignment_id}/revoke` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/admin/roles` | sesión | 401 | 401 | 401 | 200 | 200 | 403 | 403 | 403 |
| GET | `/api/v1/admin/permissions` | sesión | 401 | 401 | 401 | 200 | 200 | 403 | 403 | 403 |
| POST | `/api/v1/admin/roles/{role}/permissions` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| DELETE | `/api/v1/admin/roles/{role}/permissions/{permission_code}` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/admin/audit-log` | sesión | 401 | 401 | 401 | 200 | 200 | 403 | 403 | 403 |
| POST | `/api/v1/auth/refresh` | público | — | — | 401 | — | — | — | — | — |
| POST | `/api/v1/auth/logout` | público | — | — | 204 | — | — | — | — | — |
| GET | `/api/v1/users/me/sessions` | sesión | 401 | 401 | 401 | 200 | 200 | 200 | 200 | 200 |
| DELETE | `/api/v1/users/me/sessions/{session_id}` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/users/me/sessions/revoke-others` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/users/me` | sesión | 401 | 401 | 401 | 200 | 200 | 200 | 200 | 200 |
| PATCH | `/api/v1/users/me` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/users/me/mfa/recovery-codes` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| PUT | `/api/v1/users/me/interests` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/users/preferences/channels` | sesión | 401 | 401 | 401 | 200 | 200 | 200 | 200 | 200 |
| PUT | `/api/v1/users/preferences/channels` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/users/preferences/portfolio` | sesión | 401 | 401 | 401 | 200 | 200 | 200 | 200 | 200 |
| PUT | `/api/v1/users/preferences/portfolio` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/users/preferences/orders` | sesión | 401 | 401 | 401 | 200 | 200 | 200 | 200 | 200 |
| PUT | `/api/v1/users/preferences/orders` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| PUT | `/api/v1/users/me/telegram` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/kyc/status` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| POST | `/api/v1/kyc/account` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/markets` | sesión | 401 | 401 | 401 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/markets/calendar` | sesión | 401 | 401 | 401 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/markets/clock` | sesión | 401 | 401 | 401 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/markets/{market_code}/status` | sesión | 401 | 401 | 401 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/instruments/search` | sesión | 401 | 401 | 401 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/instruments/{symbol}/quote` | sesión | 401 | 401 | 401 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/instruments/{symbol}/candles` | sesión | 401 | 401 | 401 | 422 | 422 | 422 | 422 | 422 |
| GET | `/api/v1/instruments/{symbol}/depth` | sesión | 401 | 401 | 401 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/instruments/{symbol}` | sesión | 401 | 401 | 401 | 200 | 200 | 200 | 200 | 200 |
| PUT | `/api/v1/admin/markets/{market_code}/default-schedule` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| DELETE | `/api/v1/admin/markets/{market_code}/default-schedule` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/admin/markets/{market_code}/schedule-overrides` | sesión | 401 | 401 | 401 | 200 | 200 | 403 | 403 | 403 |
| POST | `/api/v1/admin/markets/{market_code}/schedule-overrides` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| PUT | `/api/v1/admin/markets/{market_code}/schedule-overrides/{override_id}` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| DELETE | `/api/v1/admin/markets/{market_code}/schedule-overrides/{override_id}` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/watchlists` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| POST | `/api/v1/watchlists` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/watchlists/{watchlist_id}` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 404 | 403 |
| POST | `/api/v1/watchlists/{watchlist_id}/items` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| DELETE | `/api/v1/watchlists/{watchlist_id}/items/{symbol}` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/price-alerts` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| POST | `/api/v1/price-alerts` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/price-alerts/{alert_id}/activate` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/price-alerts/{alert_id}/deactivate` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| DELETE | `/api/v1/price-alerts/{alert_id}` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/notifications` | sesión | 401 | 401 | 401 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/dashboard` | sesión | 401 | 401 | 401 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/wallet/balances` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| GET | `/api/v1/wallet/currencies` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| GET | `/api/v1/wallet/bank-relationships` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| POST | `/api/v1/wallet/bank-relationships` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/wallet/bank-relationships/{id}` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 404 | 403 |
| POST | `/api/v1/wallet/deposits` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/wallet/withdrawals` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/wallet/transfers` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| GET | `/api/v1/wallet/transfers/{id}` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 404 | 403 |
| GET | `/api/v1/wallet/activities` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| GET | `/api/v1/subscriptions/plans` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| POST | `/api/v1/subscriptions/checkout` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/subscriptions/me/cancel` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/subscriptions/me` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| GET | `/api/v1/subscriptions/me/payments` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| GET | `/api/v1/subscriptions/me/payments/{id}` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 404 | 403 |
| POST | `/api/v1/webhooks/stripe` | público | — | — | 400 | — | — | — | — | — |
| GET | `/api/v1/portfolio/positions` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| GET | `/api/v1/portfolio/executions` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| GET | `/api/v1/portfolio/statistics` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| GET | `/api/v1/portfolio/risk-profile` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| POST | `/api/v1/portfolio/reports` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/portfolio/reports` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| GET | `/api/v1/portfolio/reports/{report_id}` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 404 | 403 |
| POST | `/api/v1/portfolio/broker/reports` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/portfolio/broker/reports` | sesión | 401 | 401 | 401 | 403 | 403 | 200 | 403 | 200 |
| GET | `/api/v1/portfolio/broker/reports/{report_id}` | sesión | 401 | 401 | 401 | 403 | 403 | 404 | 403 | 404 |
| GET | `/api/v1/portfolio/broker/clients/{investor_id}/positions` | sesión | 401 | 401 | 401 | 403 | 403 | 404 | 403 | 200 |
| GET | `/api/v1/portfolio/broker/clients/{investor_id}/reports/{report_id}` | sesión | 401 | 401 | 401 | 403 | 403 | 404 | 403 | 404 |
| POST | `/api/v1/orders/preview` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/orders` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/orders` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| GET | `/api/v1/orders/{id}` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 404 | 403 |
| POST | `/api/v1/orders/{id}/cancel` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/orders/{id}/reauthorization` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/orders/{id}/resubmit` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/orders/{id}/resume` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/broker/order-reviews` | sesión | 401 | 401 | 401 | 403 | 403 | 200 | 403 | 200 |
| POST | `/api/v1/broker/order-reviews/{id}/return` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/broker/order-reviews/{id}/approve` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/brokers/suggestions` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| GET | `/api/v1/brokers` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| PUT | `/api/v1/brokers/me/profile` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/brokers/{broker_id}` | público | — | — | 404 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/brokers/{broker_id}/reputation` | sesión | 401 | 401 | 401 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/brokers/{broker_id}/reviews` | sesión | 401 | 401 | 401 | 200 | 200 | 200 | 200 | 200 |
| PUT | `/api/v1/brokers/{broker_id}/rating` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/broker-links` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/broker-links` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| GET | `/api/v1/broker-links/current` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| POST | `/api/v1/broker-links/{id}/cancel` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/broker-links/{id}/end` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| PUT | `/api/v1/broker-links/{id}/order-review` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/broker-links/{id}/trading-authorization` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/broker-links/{id}/trading-authorization/revoke` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/proposals` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| GET | `/api/v1/proposals/{id}` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 404 | 403 |
| POST | `/api/v1/proposals/{id}/decision` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/proposals/{id}/messages` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/proposals/{id}/messages` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 404 | 403 |
| GET | `/api/v1/broker/link-requests` | sesión | 401 | 401 | 401 | 403 | 403 | 200 | 403 | 200 |
| POST | `/api/v1/broker/link-requests/{id}/accept` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/broker/link-requests/{id}/decline` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/broker/proposals` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/broker/proposals` | sesión | 401 | 401 | 401 | 403 | 403 | 200 | 403 | 200 |
| GET | `/api/v1/broker/proposals/{id}` | sesión | 401 | 401 | 401 | 403 | 403 | 404 | 403 | 404 |
| PUT | `/api/v1/broker/proposals/{id}` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/broker/proposals/{id}/withdraw` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/broker/proposals/{id}/decision` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/broker/proposals/{id}/messages` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/broker/proposals/{id}/messages` | sesión | 401 | 401 | 401 | 403 | 403 | 404 | 403 | 404 |
| GET | `/api/v1/broker/clients` | sesión | 401 | 401 | 401 | 403 | 403 | 200 | 403 | 200 |
| GET | `/api/v1/broker/clients/{investor_id}/orders` | sesión | 401 | 401 | 401 | 403 | 403 | 404 | 403 | 200 |
| GET | `/api/v1/admin/fee-schedules` | sesión | 401 | 401 | 401 | 200 | 200 | 403 | 403 | 403 |
| GET | `/api/v1/admin/fee-schedules/{scope}/versions` | sesión | 401 | 401 | 401 | 200 | 200 | 403 | 403 | 403 |
| POST | `/api/v1/admin/fee-schedules/{scope}/versions` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/admin/fee-schedules/{scope}/versions/{version_id}/cancel` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/commissions/quote` | sesión | 401 | 401 | 401 | 403 | 403 | 200 | 200 | 200 |
| GET | `/api/v1/commissions` | sesión | 401 | 401 | 401 | 403 | 403 | 403 | 200 | 403 |
| GET | `/api/v1/broker/commissions` | sesión | 401 | 401 | 401 | 403 | 403 | 200 | 403 | 200 |
| GET | `/api/v1/admin/commissions` | sesión | 401 | 401 | 401 | 200 | 200 | 403 | 403 | 403 |
| GET | `/api/v1/admin/markets` | sesión | 401 | 401 | 401 | 200 | 200 | 403 | 403 | 403 |
| GET | `/api/v1/admin/markets/{market_code}/schedule-changes` | sesión | 401 | 401 | 401 | 200 | 200 | 403 | 403 | 403 |
| GET | `/api/v1/admin/markets/{market_code}` | sesión | 401 | 401 | 401 | 200 | 200 | 403 | 403 | 403 |
| GET | `/api/v1/admin/trading-halts` | sesión | 401 | 401 | 401 | 200 | 200 | 403 | 403 | 403 |
| POST | `/api/v1/admin/trading-halts` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| POST | `/api/v1/admin/trading-halts/{halt_id}/release` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/trading-halts/active` | sesión | 401 | 401 | 401 | 200 | 200 | 200 | 200 | 200 |
| GET | `/api/v1/admin/audit-trail` | sesión | 401 | 401 | 401 | 200 | 200 | 403 | 403 | 403 |
| GET | `/api/v1/admin/audit-trail/orders/{order_id}` | sesión | 401 | 401 | 401 | 404 | 404 | 403 | 403 | 403 |
| POST | `/api/v1/admin/compliance/restrictions` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/admin/compliance/restrictions` | sesión | 401 | 401 | 401 | 200 | 200 | 403 | 403 | 403 |
| POST | `/api/v1/admin/compliance/restrictions/{restriction_id}/lift` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/admin/compliance/atypical-operations` | sesión | 401 | 401 | 401 | 200 | 200 | 403 | 403 | 403 |
| POST | `/api/v1/admin/compliance/users/{user_id}/audit-reports` | sesión | 401 | 401 | 401 | — | — | — | — | — |
| GET | `/api/v1/admin/compliance/users/{user_id}/audit-reports` | sesión | 401 | 401 | 401 | 200 | 200 | 403 | 403 | 403 |
| GET | `/api/v1/admin/compliance/audit-reports/{report_id}` | sesión | 401 | 401 | 401 | 404 | 404 | 403 | 403 | 403 |
| GET | `/api/v1/admin/kpis` | sesión | 401 | 401 | 401 | 200 | 200 | 403 | 403 | 403 |
| GET | `/health` | público | — | — | 200 | 200 | 200 | 200 | 200 | 200 |

## WebSocket (fuera de OpenAPI HTTP)

`/ws/v1/market-feed`: suite existente de suscripciones y cierre con streaming
deshabilitado; pruebas adversariales de frames y revocación con autenticación
controlada. No se presenta como un flujo WebSocket live contra Alpaca.
