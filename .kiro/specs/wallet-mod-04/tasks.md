# Implementation Plan: wallet-mod-04

## Overview

Implementación incremental del módulo `wallet` (`src/acciones_ud/wallet/`) en Python 3.12 con FastAPI, SQLAlchemy 2.x async y Alembic, según `design.md`. El orden va de dentro hacia afuera: puntos abiertos y configuración, dominio puro, persistencia, adaptadores externos, casos de uso, HTTP, job de reconciliación y cableado en `main.py`.

Política de pruebas (instrucción del usuario: "Importante, no hagas tests obligatorios para todo, solo las partes críticas"): solo son obligatorias las pruebas de las propiedades 1 a 10 de `design.md` y los ejemplos críticos de la estrategia de pruebas. El resto de sub-tareas de prueba se marca opcional con `*`.

Validación de cierre de cada checkpoint: `uv run ruff check .`, `uv run mypy src`, `uv run pytest`.

## Tasks

- [ ] 1. Verificar puntos abiertos y preparar configuración y errores
  - [ ] 1.1 Verificar el rol en `CurrentUser` y crear `require_investor`
    - Revisar `identity` para confirmar cómo `get_current_user` expone el rol vigente (campo `role`, lista de roles o consulta adicional) y documentar el hallazgo en un comentario del módulo `deps.py`
    - Crear `wallet/adapters/inbound/http/deps.py` con `require_investor` que responde 403 `FORBIDDEN` si el rol `investor` no está vigente
    - Si `CurrentUser` no expone el rol, agregar el campo de forma aditiva en `identity` sin cambiar contratos existentes
    - _Requirements: 13.1, 13.2_
  - [ ] 1.2 Verificar el almacenamiento de preferencias y agregar `balance_changes`
    - Confirmar si las preferencias de notificación se guardan por fila o se derivan de `default_preferences()` al leer
    - Agregar `balance_changes` a `EVENT_TYPES` en `identity/domain/preferences.py` con `in_app` habilitado y los demás canales deshabilitados por defecto
    - Registrar el resultado de la verificación en la tarea 3.1 (si se guardan por fila, la migración inserta las filas por defecto para usuarios existentes)
    - _Requirements: 12.3, 12.5_
  - [ ]* 1.3 Escribir pruebas unitarias de preferencias `balance_changes`
    - `GET` devuelve el tipo nuevo con `in_app` habilitado; `PUT` lo acepta
    - _Requirements: 12.3_
  - [ ] 1.4 Agregar los nuevos `ErrorCode` y las variables de configuración
    - Agregar en `shared/domain/errors.py` los códigos de la tabla de errores de `design.md`
    - Agregar en `config/settings.py` las variables de Stripe (`SecretStr`, prefijos `sk_test_`, `whsec_`, `price_`), `WALLET_MAX_TRANSFER_AMOUNT`, `WALLET_RECONCILE_INTERVAL_SECONDS`, `WALLET_RECONCILER_ENABLED` y las URLs de Checkout (D3)
    - Extender `require_api_settings` para reportar solo nombres de variables inválidas
    - Actualizar `.env.example` con valores de ejemplo no reales
    - _Requirements: 13.7, 13.8_
  - [ ]* 1.5 Escribir pruebas unitarias de configuración
    - Clave `sk_live_`, intervalo fuera de 10–3600 y máximo con tres decimales se rechazan sin exponer el valor
    - _Requirements: 13.7, 13.8_

- [ ] 2. Implementar reglas puras del dominio
  - [ ] 2.1 Crear entidades, puertos y errores de dominio
    - Crear `wallet/domain/` con `balances.py`, `bank.py`, `transfers.py`, `activities.py`, `subscriptions.py` (dataclasses `frozen=True` de `design.md`) y `ports.py` con los Protocol de puertos y repositorios, incluido `WalletWork`
    - Definir excepciones de dominio (`InvalidAmountError`, `InsufficientFundsError`, `InvalidSignatureError`, `StripeUnavailableError`, `StripeRejectedError`)
    - Definir los planes fijos `monthly` (12.00 USD, `month`) y `annual` (120.00 USD, `year`)
    - _Requirements: 7.1, 8.1, 13.5_
  - [ ] 2.2 Implementar `money.py`: `parse_transfer_amount` y `exact_amount`, más validación de moneda `USD`
    - _Requirements: 1.3, 3.2, 3.3, 4.4, 7.3_
  - [ ] 2.3 Escribir prueba de propiedad de validación de importe y moneda
    - **Property 1: Validación de importe y moneda de transferencias**
    - **Validates: Requirements 3.2, 3.3, 4.4**
    - En esta tarea se prueba la función pura; la parte "cero llamadas a Alpaca" se cubre en la tarea 6.4
  - [ ] 2.4 Escribir prueba de propiedad de importes exactos
    - **Property 2: Importes de saldo exactos**
    - **Validates: Requirements 1.3**
  - [ ] 2.5 Implementar `transfers.py`: `check_withdrawable` y `decide_update` con el conjunto de Terminal_Status (`COMPLETE`, `CANCELED`, `RETURNED`, `REJECTED`)
    - _Requirements: 4.2, 5.2, 5.3, 5.4_
  - [ ] 2.6 Escribir prueba de propiedad de transición de estados de Transfer
    - **Property 5: Modelo de transición de estados de Transfer**
    - **Validates: Requirements 5.2, 5.3, 5.4**
  - [ ] 2.7 Implementar `idempotency.py`: `request_hash` canónico con importe normalizado a dos decimales
    - _Requirements: 3.5, 3.6_
  - [ ] 2.8 Implementar `stripe_signature.py`: `verify` con HMAC-SHA256, `hmac.compare_digest`, varios `v1` y tolerancia de 300 s
    - _Requirements: 9.1, 9.2_
  - [ ] 2.9 Escribir prueba de propiedad de firma del webhook
    - **Property 7: Verificación de firma del webhook**
    - **Validates: Requirements 9.1, 9.2**
    - En esta tarea se prueba la función pura; la ausencia de cambios en estado se cubre en la tarea 7.6
  - [ ] 2.10 Implementar `subscriptions.premium_effect` según W6
    - _Requirements: 9.6, 9.7, 10.5_

- [ ] 3. Implementar persistencia
  - [ ] 3.1 Crear la migración `migrations/versions/0006_wallet_schema.py`
    - Revisar el último número de revisión existente y ajustar `down_revision` (y el número si `0006` ya existe)
    - Crear las tablas de `design.md` con PK, UNIQUE, CHECK, índices y el índice único parcial de `subscriptions`
    - Insertar preferencias `balance_changes` para usuarios existentes solo si la tarea 1.2 confirmó almacenamiento por fila
    - `downgrade` elimina las tablas en orden inverso
    - _Requirements: 13.10, 12.3, 2.2_
  - [ ] 3.2 Crear `wallet/adapters/outbound/persistence/tables.py` y los repositorios SQLAlchemy
    - Repositorios de transfers (incluido el UPDATE condicional del reconciliador), bank relationships, idempotency keys (`reserve`, `complete`, `release`), subscriptions, payments, stripe events (`INSERT … ON CONFLICT DO NOTHING`), cursores de actividades y marcadores de notificación
    - Fábrica de unidad de trabajo `WalletWork` sobre `shared/infrastructure/db.py`, que traduce errores de conexión a 503 `DATABASE_UNAVAILABLE`
    - _Requirements: 3.5, 5.2, 5.3, 5.4, 9.3, 12.4, 13.6_
  - [ ] 3.3 Crear repositorios en memoria para pruebas en `tests/wallet/fakes.py`, con la misma semántica de UPDATE condicional, reserva idempotente y `ON CONFLICT`
    - _Requirements: 3.5, 9.3, 12.4_
  - [ ]* 3.4 Escribir pruebas `db` de repositorios y migración
    - Marcadas `db`; se saltan sin `TEST_DATABASE_URL`
    - _Requirements: 13.10_

- [ ] 4. Implementar adaptadores externos y hacia otros módulos
  - [ ] 4.1 Implementar `AlpacaFundingClient` y `fake_funding.py`
    - Cuenta de trading (timeout 5 s), relaciones ACH, transfers y actividades con paginación por `page_token`
    - Reutilizar `alpaca_http.py`, `raise_for_alpaca` y `shared/domain/alpaca_errors.py`; distinguir rechazo de validación (4xx) para `TRANSFER_REJECTED`
    - Logs sin cuerpos con números de cuenta ni credenciales
    - _Requirements: 1.4, 2.1, 3.7, 6.2, 13.5, 13.8_
  - [ ] 4.2 Implementar `StripeClient` con `httpx` y `fake_stripe.py`
    - `Stripe-Version: 2024-06-20`, timeout 10 s, `StripeUnavailableError` ante red, timeout, 5xx o 429 y `StripeRejectedError` ante 4xx
    - Checkout en modo `subscription` con `client_reference_id`, `metadata[user_id]` y URLs de D3; cancelación con `cancel_at_period_end=true`
    - _Requirements: 8.2, 8.5, 10.1, 10.4, 13.8_
  - [ ] 4.3 Implementar adaptadores hacia `identity`
    - `account_reader.py` (`LinkedAccountReader`), `AccountStatusWriter` y `premium_flag_writer.py` sobre las tablas de `identity` dentro de la sesión de `WalletWork`
    - _Requirements: 1.2, 1.5, 9.6, 9.7_
  - [ ] 4.4 Agregar `ContractedPlanReader` en `identity` y su implementación en `wallet`
    - Protocol en `identity/domain/`, resuelto desde `app.state.contracted_plan_reader`, con `null` si no existe
    - Cambiar el esquema de `/users/me` a `contracted_plan: Literal["monthly", "annual"] | None`
    - Implementación en `wallet/adapters/outbound/identity/contracted_plan_reader.py` sobre `subscriptions` con estado `active`, `trialing` o `past_due`
    - _Requirements: 11.4_
  - [ ]* 4.5 Escribir pruebas unitarias de `contracted_plan` en `/users/me`
    - _Requirements: 11.4_
  - [ ] 4.6 Agregar `RecipientDirectory.recipient(user_id, event_type)` en `market_data` e implementar `BalanceNotifierAdapter`
    - Devuelve `None` si todos los canales están deshabilitados y entonces no se notifica
    - _Requirements: 12.1, 12.2, 12.5_
  - [ ]* 4.7 Escribir pruebas unitarias de `recipient` y del adaptador de notificación
    - _Requirements: 12.5_

- [ ] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implementar casos de uso de billetera y fondeo
  - [ ] 6.1 Implementar `WalletService`: `get_balances`, `get_currencies` y `list_activities`
    - Saldos no disponibles (W8) con importes `null`; actualización de estado de cuenta por puerto en transacción propia, cuyo fallo o timeout se registra sin secretos y no impide devolver el estado de Alpaca (Req. 1.6); moneda por defecto `USD` con log e importes sin modificar; periodo por defecto de 30 días, máximo 366, paginación 1–100 (defecto 50); exclusión de conversiones de divisas
    - DTOs en `application/dtos.py` con importes como cadena
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 6.2, 6.3, 6.4, 6.5, 6.6, 7.1, 7.2, 7.3_
  - [ ] 6.2 Escribir pruebas unitarias de saldos no disponibles
    - Timeout, 5xx y 429 de Alpaca devuelven `unavailable: true` con todos los importes `null`
    - _Requirements: 1.4_
  - [ ]* 6.3 Escribir pruebas unitarias de monedas, actividades y periodos
    - _Requirements: 6.3, 6.4, 6.6, 7.2, 7.3_
  - [ ] 6.4 Implementar `FundingService`
    - Relaciones bancarias (solo últimos 4 dígitos, cuenta `ACTIVE`), `request_transfer(direction)` con el flujo de `design.md` (validación pura, relación propia `APPROVED`, reserva idempotente, `cash_withdrawable` en retiros, `release` si Alpaca rechaza), `list_transfers` y `get_transfer` con 404 indistinguible
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.1, 4.2, 4.3, 4.4, 5.6, 6.1, 13.3_
  - [ ] 6.5 Escribir prueba de propiedad de rechazo sin llamadas a Alpaca
    - **Property 1: Validación de importe y moneda de transferencias**
    - **Validates: Requirements 3.2, 3.3, 4.4**
    - Parametrizada por dirección; verifica cero llamadas de creación en el fake
  - [ ] 6.6 Escribir prueba de propiedad del límite de retiro
    - **Property 3: Retiro limitado por el efectivo retirable**
    - **Validates: Requirements 4.2**
  - [ ] 6.7 Escribir prueba de propiedad de idempotencia de transferencias
    - **Property 4: Idempotencia de depósitos y retiros**
    - **Validates: Requirements 3.5, 3.6, 4.4**
  - [ ] 6.8 Escribir prueba de propiedad de recursos ajenos
    - **Property 6: Recursos ajenos indistinguibles de inexistentes**
    - **Validates: Requirements 13.3**
    - Cubre Transfer y Bank_Relationship en esta tarea; Payment se agrega en la tarea 7.7
  - [ ]* 6.9 Escribir pruebas unitarias de relaciones bancarias y `TRANSFER_REJECTED`
    - _Requirements: 2.4, 2.5, 3.4, 3.7_

- [ ] 7. Implementar casos de uso de suscripciones y webhook de Stripe
  - [ ] 7.1 Implementar `SubscriptionService`: `list_plans`, `start_checkout`, `cancel`, `get_current`, `list_payments` y `get_payment`
    - `pending_checkout` solo tras éxito de Stripe; 409 `SUBSCRIPTION_ALREADY_ACTIVE` y `SUBSCRIPTION_NOT_CANCELABLE` sin llamar a Stripe; Subscription sin cambios si Stripe falla al cancelar
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 10.1, 10.2, 10.3, 10.4, 11.1, 11.2, 11.3, 13.3_
  - [ ]* 7.2 Escribir pruebas unitarias de planes, checkout y cancelación
    - _Requirements: 8.1, 8.2, 8.3, 8.5, 10.1, 10.2, 10.4_
  - [ ] 7.3 Implementar `StripeWebhookService.handle`
    - Verificar firma, registrar el evento y aplicar efectos en una transacción; eventos `checkout.session.completed`, `customer.subscription.*`, `invoice.paid` e `invoice.payment_failed`
    - Orden por `stripe_event_created_at` (D7), resultado `applied`, `unassociated` o `stale`, `is_premium` con `premium_effect`, conservar premium con `cancel_at_period_end`
    - 503 `DATABASE_UNAVAILABLE` con log `event_id` y `applied=false`
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9, 10.5_
  - [ ] 7.4 Escribir prueba de propiedad de idempotencia de Stripe_Events
    - **Property 8: Idempotencia de Stripe_Events**
    - **Validates: Requirements 9.3**
  - [ ] 7.5 Escribir prueba de propiedad del efecto sobre `is_premium`
    - **Property 9: Efecto de la suscripción sobre `is_premium`**
    - **Validates: Requirements 9.6, 9.7**
  - [ ] 7.6 Escribir pruebas de propiedad de eventos no asociados y firma sin efectos
    - **Property 10: Eventos no asociados sin efectos**
    - **Validates: Requirements 9.8**
    - Incluir la parte de estado de **Property 7** (firma inválida no cambia Subscriptions, Payments ni flag premium), **Validates: Requirements 9.2**
  - [ ] 7.7 Extender la prueba de la Property 6 a Payments
    - **Property 6: Recursos ajenos indistinguibles de inexistentes**
    - **Validates: Requirements 13.3**
  - [ ] 7.8 Escribir prueba unitaria de base de datos caída en el webhook
    - Responde 503 `DATABASE_UNAVAILABLE` y registra el `event_id` como no aplicado
    - _Requirements: 9.9_

- [ ] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Implementar entradas HTTP y job de reconciliación
  - [ ] 9.1 Implementar routers y schemas de `wallet` y `subscriptions`
    - Endpoints de la tabla de `design.md` con `get_current_user` y `require_investor`; encabezado `Idempotency-Key` de 8 a 128 caracteres ASCII imprimibles; importes como cadena; Sandbox_Notice fijo
    - Declarar en OpenAPI cada respuesta de error por endpoint
    - Ajustar el manejador de validación para que `details` de rutas `wallet` contenga solo nombres de campo
    - _Requirements: 2.5, 6.1, 6.2, 13.1, 13.2, 13.8, 13.9_
  - [ ] 9.2 Implementar el router `POST /webhooks/stripe`
    - Sin cookie; lee `await request.body()` antes de parsear; nunca registra `Stripe-Signature`
    - _Requirements: 9.1, 9.2, 13.4, 13.8_
  - [ ] 9.3 Escribir pruebas unitarias de autorización
    - 401 sin cookie y 403 sin rol `investor`, sin llamadas a los fakes de Alpaca ni Stripe
    - _Requirements: 13.1, 13.2_
  - [ ] 9.4 Implementar `TransferReconciler.run_once` y `transfer_reconcile_job.py`
    - Agrupar por cuenta, UPDATE condicional, marcadores con `ON CONFLICT DO NOTHING` antes de notificar, cursor inicial de actividades en la hora actual (D6), cursor avanzado por toda Activity y notificación solo para `FILL`, continuar con la siguiente cuenta ante error de Alpaca
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 12.1, 12.2, 12.4, 12.6_
  - [ ]* 9.5 Escribir pruebas unitarias del reconciliador
    - Una sola notificación por Transfer y por Activity procesados dos veces; fallo de Alpaca en una cuenta no detiene las demás
    - _Requirements: 5.5, 12.1, 12.2, 12.4_

- [ ] 10. Cablear el módulo
  - [ ] 10.1 Crear `wallet/composition.py` y registrar el módulo en `main.py`
    - `register(app)` monta routers e instala `app.state.contracted_plan_reader`; `startup(app)` arranca el job si `WALLET_RECONCILER_ENABLED`; `shutdown(app)` lo detiene y cierra clientes `httpx`
    - _Requirements: 5.1, 11.4, 13.4_
  - [ ] 10.2 Escribir pruebas API de punta a punta con fakes
    - Un depósito completo, un retiro con `INSUFFICIENT_FUNDS` y un webhook firmado
    - _Requirements: 3.1, 4.2, 9.1_
  - [ ]* 10.3 Escribir prueba de contrato OpenAPI
    - Cada endpoint de `wallet` declara request, response y errores
    - _Requirements: 13.9_

- [ ] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Las sub-tareas con `*` son opcionales. Las pruebas sin `*` corresponden a las partes críticas: propiedades 1 a 10, saldos no disponibles, autorización 401/403, base de datos caída en el webhook y los tres flujos API.
- Las pruebas de propiedad usan Hypothesis con `@settings(max_examples=100)` y el comentario `# Feature: wallet-mod-04, Property N: <texto>`, en `tests/wallet/property/`.
- Las tareas 1.1 y 1.2 resuelven los puntos abiertos del diseño antes de escribir el resto del código.
- Las pruebas `db` se saltan sin `TEST_DATABASE_URL`.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.4", "2.1"] },
    { "id": 1, "tasks": ["1.3", "1.5", "2.2", "2.5", "2.7", "2.8", "2.10"] },
    { "id": 2, "tasks": ["2.3", "2.4", "2.6", "2.9", "3.1"] },
    { "id": 3, "tasks": ["3.2", "3.3", "4.1", "4.2", "4.6"] },
    { "id": 4, "tasks": ["3.4", "4.3", "4.7"] },
    { "id": 5, "tasks": ["4.4", "6.1"] },
    { "id": 6, "tasks": ["4.5", "6.2", "6.3", "6.4"] },
    { "id": 7, "tasks": ["6.5", "6.6", "6.7", "6.8", "6.9", "7.1"] },
    { "id": 8, "tasks": ["7.2", "7.3", "9.4"] },
    { "id": 9, "tasks": ["7.4", "7.5", "7.6", "7.8", "9.1"] },
    { "id": 10, "tasks": ["7.7", "9.2", "9.5"] },
    { "id": 11, "tasks": ["9.3", "10.1"] },
    { "id": 12, "tasks": ["10.2", "10.3"] }
  ]
}
```
