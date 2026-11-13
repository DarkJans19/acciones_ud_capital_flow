# Implementation Plan: orders-mod-03

## Overview

Implementación del paquete `orders` (`src/acciones_ud/orders/`) en Python 3.12 con arquitectura hexagonal: primero se verifican los supuestos del diseño, luego el dominio puro, la persistencia, los adaptadores, los casos de uso, los jobs y por último la API HTTP y el cableado en `main.py`.

**Prerrequisito:** `wallet-mod-04` debe estar implementado antes de empezar, porque `orders` usa el `AlpacaFundingPort` que publica `wallet` y el `RecipientDirectory` agregado por su diseño.

**Política de pruebas:** solo son obligatorias las pruebas de las partes críticas (Properties 1 a 11 del diseño y la prueba de integración del bloqueo concurrente). El resto de pruebas son opcionales y están marcadas con `*`.

Validación de cada checkpoint: `uv run ruff check .`, `uv run mypy src` y `uv run pytest`.

## Tasks

- [ ] 1. Verificar supuestos del diseño y preparar la base común
  - [ ] 1.1 Verificar los supuestos del diseño contra el código actual
    - Confirmar que `wallet` está implementado y que `wallet.register(app)` publica `app.state.wallet_funding_port`; si no lo publica, agregar esa asignación aditiva en `wallet/composition.py` sin cambiar su comportamiento (O7)
    - Confirmar que `RecipientDirectory.recipient(user_id, event_type)` y `Notifier.notify` existen en `market_data`
    - Localizar el caso de uso de verificación TOTP de `identity`; si no existe, agregar una función de aplicación en `identity` que verifique un código con el secreto cifrado (`SecretCipher`) y la ventana configurada, sin registrar el código
    - Localizar el nombre real del caso de uso de cotización de `market_data`, de `InstrumentRepository.get`, de `MarketRepository` y de `AlpacaBrokerMarketPort.calendar`
    - Confirmar si `MFA_ENROLLMENT_REQUIRED`, `IDEMPOTENCY_CONFLICT`, `ALPACA_UNAVAILABLE`, `ALPACA_RATE_LIMITED` y `DATABASE_UNAVAILABLE` existen en `ErrorCode`
    - Confirmar el siguiente número libre de migración en `migrations/versions/` (el diseño asume `0007`) y si las preferencias de `identity` se guardan por fila
    - Confirmar que existen `require_investor` (usado por `wallet`) y un guard para el rol `broker`; si falta `require_broker`, agregarlo en `identity` con la misma forma
    - Ajustar los nombres usados en las tareas siguientes a lo encontrado; si un supuesto no se cumple y no tiene ajuste aditivo, detenerse y reportar
    - _Requirements: 4.2, 11.3, 11.4, 15.1, 15.3, 15.9_

  - [ ] 1.2 Agregar los códigos de error de órdenes y su traducción HTTP
    - Agregar a `ErrorCode` en `shared/domain/errors.py`: `ORDER_ACCOUNT_NOT_ACTIVE`, `QUOTE_UNAVAILABLE`, `ASSET_NOT_TRADABLE`, `INSUFFICIENT_BUYING_POWER`, `INSUFFICIENT_POSITION`, `DAILY_ORDER_LIMIT_REACHED`, `EXTRA_AUTHORIZATION_REQUIRED`, `EXTRA_AUTHORIZATION_INVALID`, `ORDER_REJECTED`, `ORDER_NOT_FOUND`, `INVALID_ORDER_STATE`, `ORDER_NOT_CANCELLABLE`, `MARKET_CLOSED` y `MFA_ENROLLMENT_REQUIRED` si no existe
    - Mapear cada código a su estado HTTP en `shared/infrastructure/http_errors.py` según la tabla de Error Handling del diseño
    - _Requirements: 15.6, 15.7_

  - [ ] 1.3 Agregar la configuración del módulo
    - Agregar a `config/settings.py` las variables `ORDER_*` y `ORDERS_JOBS_ENABLED` con sus defectos y validarlas en `require_api_settings`; el error lista solo nombres de variables
    - Actualizar `.env.example`
    - _Requirements: 15.5_

  - [ ]* 1.4 Escribir pruebas unitarias de la configuración
    - Rangos inválidos de cada variable, defecto individual cuando falta una sola variable y mensaje sin valores
    - _Requirements: 15.5_

- [ ] 2. Implementar el dominio puro de `orders`
  - [ ] 2.1 Crear modelo, errores y puertos
    - `orders/domain/model.py`: `OrderStatus`, `OrderRequest`, `Order`, `OrderLeg`, `OrderEvent`, `Execution`, `Reservation`, `ReauthorizationRequest`, `CancelRequest`, `ReviewComment`, `OrderControls`, `TradableAsset`, `LinkedAccount` como dataclasses `frozen=True`
    - `orders/domain/errors.py`: `OrderDomainError` y subclases sobre `AppError`, incluidas `InvalidTransitionError`, `InsufficientBuyingPowerError`, `InsufficientPositionError`, `OrderSubmissionNotReceived` y `OrderSubmissionUnknown`
    - `orders/domain/ports.py`: todos los Protocol del diseño, `OrderEventType` y `CancelOutcome`
    - Sin imports de FastAPI, SQLAlchemy ni `httpx`
    - _Requirements: 10.1, 15.9_

  - [ ] 2.2 Implementar `validation.py`
    - `validate(request, asset, base_price) -> list[FieldError]` con Req. 2.1 a 2.6, devolviendo todos los campos inválidos
    - `allows_fraction(asset, order_class, order_type, tif)` según O2
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.8, 2.9_

  - [ ] 2.3 Escribir prueba de propiedad de validación
    - **Property 1: Validación de parámetros contra el modelo de referencia**
    - `tests/orders/property/test_validation.py`, modelo de referencia escrito desde los Req. 2.1 a 2.6 y O2, `max_examples >= 100`
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.8, 2.9**

  - [ ] 2.4 Implementar `state_machine.py` y `status_mapping.py`
    - `ALLOWED` con la tabla completa del Req. 10.2, `transition(current, target, fully_filled)` e `is_terminal(status, fully_filled)`
    - `map_alpaca(provider_status, filled_qty) -> OrderStatus | None` según Req. 10.4
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.8_

  - [ ] 2.5 Escribir prueba de propiedad de la máquina de estados
    - **Property 2: Máquina de estados cerrada y terminales inmutables**
    - `tests/orders/property/test_state_machine.py`
    - **Validates: Requirements 10.2, 10.3, 10.6, 10.8**

  - [ ] 2.6 Escribir prueba de propiedad del mapeo de estados de Alpaca
    - **Property 3: Mapeo de estados de Alpaca**
    - En `tests/orders/property/test_state_machine.py`, función de prueba propia
    - **Validates: Requirements 10.4, 10.5**

  - [ ] 2.7 Implementar `estimates.py`, `reservations.py`, `reauthorization.py` e `idempotency.py`
    - `base_price`, `estimated_amount` con `ROUND_UP` a 0.01 (D5) y `requires_extra_authorization` con comparación estricta (O10)
    - `check_buy`, `check_sell` y `next_state` de Reservation (sin salida de `transferred` o `released`)
    - `requires_reauthorization(order_type, waited, reference_price, current_price, threshold_pct)` (O11)
    - `request_hash(request)` SHA-256 canónico con `Decimal.normalize()`, claves ordenadas, sin `totp_code`
    - _Requirements: 1.4, 3.1, 3.2, 3.5, 4.1, 4.4, 6.5, 7.1, 8.2, 8.3_

  - [ ]* 2.8 Escribir pruebas unitarias de estimaciones e idempotencia
    - Redondeo hacia arriba, umbral estricto, hash estable ante `"10"` y `"10.0"`
    - _Requirements: 1.4, 4.1, 8.3_

- [ ] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implementar la persistencia
  - [ ] 4.1 Crear la migración y las tablas
    - `migrations/versions/0007_orders_schema.py` (número confirmado en 1.1) con las once tablas, PK, UNIQUE, CHECK e índices del diseño, y `downgrade` en orden inverso
    - Si las preferencias se guardan por fila, insertar los defectos de `order_executions` y `order_updates`
    - `orders/adapters/outbound/persistence/tables.py` con las definiciones SQLAlchemy equivalentes (sin `create_all`)
    - _Requirements: 6.5, 9.3, 10.1, 14.5_

  - [ ] 4.2 Implementar repositorios y unidad de trabajo
    - `order_repository.py` (UPDATE condicional por estado esperado + Order_Event en la misma transacción, conteo diario en `America/New_York`, listado paginado por cursor), `reservation_repository.py`, `execution_repository.py` (`ON CONFLICT DO NOTHING`), `idempotency_repository.py`, `schedule_change_repository.py`, `cursor_repository.py`
    - `unit_of_work.py` con `pg_advisory_xact_lock` por `user_id` (D3) y `FOR UPDATE SKIP LOCKED` para el scheduler
    - Traducir la caída de base de datos a `DATABASE_UNAVAILABLE`
    - _Requirements: 3.3, 6.6, 9.3, 10.6, 11.2_

  - [ ] 4.3 Crear repositorios en memoria para pruebas
    - `tests/orders/fakes.py` con implementaciones en memoria de los repositorios y la unidad de trabajo, con la misma semántica de UPDATE condicional e inserción idempotente de Executions
    - _Requirements: 6.5, 9.3, 10.6_

- [ ] 5. Implementar los adaptadores de salida
  - [ ] 5.1 Implementar los clientes de Alpaca y su fake
    - `alpaca/orders_client.py`: `create` con timeout, `get_by_client_order_id`, `get` con `nested=true`, `cancel` (204 → `accepted`, 422 → `not_cancelable`), `list_fills` con paginación; clasificación de resultados según D2 reutilizando `raise_for_alpaca`
    - `alpaca/positions_client.py`: `qty_available` (404 → 0)
    - `alpaca/fake_orders.py`: implementa `AlpacaOrdersPort` y `PositionPort` en memoria, programable por resultado y con conteo de creaciones por Client_Order_Id
    - _Requirements: 3.2, 8.1, 8.4, 8.6, 8.7, 9.2, 9.6, 12.3_

  - [ ]* 5.2 Escribir pruebas unitarias de clasificación de errores del cliente de órdenes
    - Conexión, 429, 4xx, 5xx y timeout de lectura producen el resultado de D2
    - _Requirements: 8.4, 8.6, 8.7_

  - [ ] 5.3 Implementar los adaptadores hacia `identity`
    - `identity/account_reader.py`, `identity/controls_reader.py` (O9) y `identity/totp_verifier.py` según lo confirmado en 1.1
    - Agregar `order_executions` y `order_updates` a `EVENT_TYPES` de `identity/domain/preferences.py` con `in_app` habilitado por defecto (O15)
    - _Requirements: 1.2, 1.5, 4.2, 4.3, 11.4_

  - [ ] 5.4 Implementar los adaptadores hacia `market_data` y el notificador
    - `market_data/quote_reader.py` (`None` si no hay cotización), `market_data/asset_reader.py`, `market_data/market_session.py` (`is_open`, `next_open` por `exchange`)
    - `notifications/order_notifier.py` con `RecipientDirectory` y `Notifier`
    - _Requirements: 1.6, 2.7, 11.3, 11.4, 13.1, 13.2_

  - [ ] 5.5 Implementar los adaptadores hacia `wallet` y de Broker nulo
    - `wallet/buying_power.py` sobre `app.state.wallet_funding_port` con timeout de 4 s
    - `brokers/null_broker_link.py` (`None`, `False`, `[]`)
    - _Requirements: 3.4, 5.7_

- [ ] 6. Implementar reservas, envío y creación
  - [ ] 6.1 Implementar `ReservationLedger`
    - `reserve`, `adjust`, `transfer`, `release`, `active_usd`, `active_shares` sobre el repositorio de reservas y las reglas de `reservations.py`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [ ] 6.2 Escribir prueba de propiedad del invariante de reservas
    - **Property 4: Invariante del Reservation_Ledger**
    - `tests/orders/property/test_reservations.py` con los repositorios de `tests/orders/fakes.py`
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.7, 12.2**

  - [ ] 6.3 Escribir prueba de propiedad de reservas serializadas
    - **Property 5: Reservas serializadas sin sobrecompromiso**
    - En `tests/orders/property/test_reservations.py`, función de prueba propia
    - **Validates: Requirements 3.1, 3.2, 6.6**

  - [ ] 6.4 Implementar `OrderSubmitter`
    - `submit(order_id, waited)`: con `waited` repite las validaciones del Req. 3.5 descontando la Reservation propia y aplica `requires_reauthorization` (pasa a Detenida, crea la Reauthorization_Request y notifica `order_updates`)
    - Envío con `client_order_id = order.id` en la segunda transacción (D1); acuse → `transferred`; rechazo → Rechazada; no recibida → Fallida; 5xx → una consulta por Client_Order_Id (D2); timeout → queda en Enviada
    - Nunca envía una Order en Detenida
    - _Requirements: 3.5, 6.3, 6.4, 7.1, 7.6, 8.1, 8.4, 8.6, 8.7_

  - [ ] 6.5 Implementar `OrderService.preview` y `OrderService.create`
    - Orden de validaciones del diseño: cuenta activa, activo, cotización, `validate`, controles y tipo por defecto, autorización adicional (TOTP o reconocimiento, sin guardar el código), mercado abierto o programación, lecturas de `buying_power` y `qty_available` fuera del bloqueo
    - TX1 bajo bloqueo: idempotencia, límite diario, fondos o tenencia, Order, Reservation y Order_Events; luego enrutamiento con `ReviewService.route_new_order` (En Revisión), programación (Pendiente con `scheduled_for`) o `OrderSubmitter.submit`
    - Repetición idempotente devuelve la Order almacenada
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.7, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 8.2, 8.3, 13.1, 13.2_

  - [ ] 6.6 Escribir prueba de propiedad de detección de cambio de precio
    - **Property 6: Detección de cambio de precio y bloqueo de envío**
    - `tests/orders/property/test_reauthorization.py` con fakes de cotización y `fake_orders.py`
    - **Validates: Requirements 7.1, 7.6**

  - [ ] 6.7 Escribir prueba de propiedad de idempotencia de la creación
    - **Property 8: Idempotencia de la creación**
    - `tests/orders/property/test_idempotency.py` contando creaciones en `fake_orders.py`
    - **Validates: Requirements 8.2, 8.3**

  - [ ]* 6.8 Escribir pruebas unitarias de creación y vista previa
    - Tipo por defecto, `confirmed`, sin cuenta activa, sin cotización, activo no negociable, límite diario, autorización adicional, rechazo y fallo de Alpaca, mercado cerrado con y sin programación
    - _Requirements: 1.1-1.6, 2.7, 3.3, 3.4, 4.1-4.5, 8.6, 8.7, 13.1, 13.2_

- [ ] 7. Implementar consulta, cancelación, nueva autorización y revisión
  - [ ] 7.1 Implementar `OrderService.get`, `list` y `cancel`
    - Detalle completo con comisión de referencia rotulada como estimada; listado paginado con filtros
    - Cancelación: valida motivo y confirmación, registra `CancelRequest`; Unsent_Order → Cancelada y `released` (200); Enviada o En Ejecución → `AlpacaOrdersPort.cancel` (202); terminal → `ORDER_NOT_CANCELLABLE` sin llamar a Alpaca
    - Order ajena o inexistente → `ORDER_NOT_FOUND`
    - _Requirements: 11.1, 11.2, 11.5, 12.1, 12.2, 12.3, 12.4, 12.5, 15.2_

  - [ ] 7.2 Implementar `OrderService.answer_reauthorization` y `expire_stale`
    - Aceptar: recalcula Reference_Price, Estimated_Amount y Reservation (fondos más Reservation propia), luego envía o programa; rechazar: Cancelada con `reauthorization_rejected`
    - Respuesta tardía sin expirar: expira y responde `INVALID_ORDER_STATE` (D7)
    - `expire_stale`: Reauthorization_Requests vencidas, Unsent_Orders antiguas y programadas `day` sin envío, con `released` y notificación `order_updates`
    - _Requirements: 7.2, 7.3, 7.4, 7.5, 10.7_

  - [ ] 7.3 Escribir prueba de propiedad de la respuesta a la nueva autorización
    - **Property 7: Respuesta a la nueva autorización**
    - En `tests/orders/property/test_reauthorization.py`, función de prueba propia
    - **Validates: Requirements 7.2, 7.3, 7.4, 7.5**

  - [ ] 7.4 Implementar `ReviewService` y `OrderService.resubmit`
    - `route_new_order`, `queue` filtrada por `linked_investors`, `return_for_changes` (comentario 1 a 500, Pendiente devuelta, notificación `order_updates`), `approve` (registra de inmediato Broker, instante y paso a Firmada por Comisionista; luego envío con mercado abierto o programación del Req. 13 con mercado cerrado)
    - `resubmit`: repite validaciones de los Req. 2, 3 y 4, ajusta la Reservation y pasa a En Revisión
    - Broker no vinculado → `ORDER_NOT_FOUND`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [ ]* 7.5 Escribir pruebas unitarias de revisión con un fake de Broker_Link_Port
    - Cola filtrada, devolución, reenvío, aprobación y cola vacía con `NullBrokerLink`
    - _Requirements: 5.1-5.7_

  - [ ]* 7.6 Escribir pruebas unitarias de cancelación
    - 200, 202, 409 terminal, 422 por motivo `other` sin texto
    - _Requirements: 12.1-12.5_

- [ ] 8. Implementar reconciliación, programación y cambio de horario
  - [ ] 8.1 Implementar `OrderReconciler.run_once`
    - Pasos 1 a 5 del diseño por cuenta: búsqueda por Client_Order_Id con `lookup_misses` (2 fallos → Fallida), estado con `map_alpaca` y Order_Legs, Executions desde `FILL` con recálculo desde la tabla (D4), rechazo de Executions que superan `qty`, cancelación no aplicada si llega `filled`, error por cuenta sin detener el ciclo
    - Notificación `order_executions` después de confirmar; cursor propio (D6)
    - _Requirements: 8.5, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 10.4, 10.5, 11.3, 11.4, 12.3, 12.6, 12.7_

  - [ ] 8.2 Escribir prueba de propiedad de ejecuciones
    - **Property 10: Ejecuciones idempotentes y acotadas**
    - `tests/orders/property/test_executions.py`
    - **Validates: Requirements 9.3, 9.4, 9.5, 12.6**

  - [ ] 8.3 Escribir prueba de propiedad de envío como máximo una vez
    - **Property 9: Envío como máximo una vez por Order**
    - En `tests/orders/property/test_idempotency.py`, función de prueba propia, combinando `OrderSubmitter` y ciclos de `OrderReconciler`
    - **Validates: Requirements 8.4, 8.5**

  - [ ] 8.4 Implementar `OrderScheduler.run_once`
    - Selecciona Pendiente o Firmada por Comisionista con `scheduled_for <= now`, no devueltas, con `SKIP LOCKED`; envía con `waited=True` solo con mercado abierto; nunca selecciona En Revisión
    - Llama a `OrderService.expire_stale`
    - _Requirements: 7.5, 10.7, 13.3, 13.4, 13.5_

  - [ ] 8.5 Implementar `ScheduleChangeService` y `OrderService.resume`
    - `apply(change, now)`: idempotente por `change_id`; pasa a En Revisión con causa `schedule_change` las Unsent_Orders en Pendiente, Firmada o Detenida del mercado (por `exchange`), conserva la Reservation y notifica una vez por Investor
    - `resume`: envía si el mercado está abierto; con mercado cerrado recalcula `scheduled_for`, pasa a Pendiente y notifica `order_updates` con la nueva fecha programada
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

  - [ ]* 8.6 Escribir pruebas unitarias de reconciliación, programación y cambio de horario
    - Order_Legs, fallo de Alpaca en una cuenta, mercado cerrado, Order en revisión, expiraciones, doble recepción del cambio de horario
    - _Requirements: 9.1, 9.6, 9.7, 10.7, 13.3-13.5, 14.1-14.5_

- [ ] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Exponer la API HTTP y cablear el módulo
  - [ ] 10.1 Crear esquemas y dependencias HTTP
    - `adapters/inbound/http/schemas/*.py` con decimales como `str` y patrón decimal, conversión a `Decimal` sin `float`; validación de `Idempotency-Key` (8 a 128 ASCII imprimibles)
    - `deps.py` con `require_investor`, `require_broker` y acceso a los servicios desde `app.state`
    - _Requirements: 15.1, 15.4_

  - [ ] 10.2 Implementar el router de órdenes
    - `routers/orders.py` con los ocho endpoints del diseño, tag `orders` y `responses=` por endpoint
    - _Requirements: 1.1, 1.4, 5.4, 7.2, 7.4, 11.1, 11.2, 12.1, 14.4, 15.1, 15.2, 15.7_

  - [ ] 10.3 Implementar el router de revisión del Broker
    - `routers/broker_reviews.py` con cola, devolución y aprobación, tag `broker-reviews` y `responses=` por endpoint
    - _Requirements: 5.2, 5.3, 5.5, 5.6, 15.1, 15.7_

  - [ ] 10.4 Implementar los jobs
    - `jobs/order_reconcile_job.py` y `jobs/order_scheduler_job.py` como tareas asyncio con intervalo configurable y cierre limpio; logs sin secretos ni TOTP
    - _Requirements: 9.1, 9.7, 13.3, 15.8_

  - [ ] 10.5 Crear `composition.py` y registrar el módulo en `main.py`
    - `register(app)`: cablea puertos y adaptadores, usa `app.state.order_broker_link` si existe o `NullBrokerLink`, publica `app.state.order_schedule_change_port`, incluye los routers
    - `startup`/`shutdown` arrancan y detienen los jobs solo si `ORDERS_JOBS_ENABLED`
    - `main.py` llama `orders.register/startup/shutdown` después de `wallet`
    - _Requirements: 5.7, 14.1, 15.9_

  - [ ] 10.6 Escribir prueba de propiedad de propiedad de recursos y pruebas de acceso
    - **Property 11: Propiedad de recursos sin filtración**
    - `tests/orders/api/test_ownership.py` sobre la API con fakes; además un ejemplo por endpoint para 401 sin sesión y 403 sin rol
    - **Validates: Requirements 15.2, 5.6, 15.1, 15.3**

  - [ ] 10.7 Escribir prueba de integración del bloqueo concurrente
    - `tests/orders/unit/test_reservation_lock_db.py` marcada `db` (se salta sin `TEST_DATABASE_URL`): dos creaciones concurrentes del mismo Investor; la suma de Reservations `active` no supera `buying_power`
    - _Requirements: 6.6_

  - [ ]* 10.8 Escribir pruebas del contrato OpenAPI
    - Esquemas declarados, decimales como cadenas, errores por endpoint, tags
    - _Requirements: 15.4, 15.6, 15.7_

- [ ] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- `wallet-mod-04` debe estar implementado antes de iniciar este plan; la tarea 1.1 lo verifica.
- Las tareas marcadas con `*` son opcionales; las pruebas de las Properties 1 a 11 y la prueba `db` del bloqueo son obligatorias por ser partes críticas.
- Cada prueba de propiedad implementa una sola propiedad, usa `max_examples >= 100` y lleva el comentario `# Feature: orders-mod-03, Property N: <título>`.
- Ninguna prueba automática llama al sandbox de Alpaca; se usa `fake_orders.py`.
- Aplicar la migración es un paso manual (`uv run alembic upgrade head`).

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "2.1"] },
    { "id": 2, "tasks": ["1.4", "2.2", "2.4", "2.7", "4.1"] },
    { "id": 3, "tasks": ["2.3", "2.5", "2.8", "4.2", "4.3", "5.1", "5.3", "5.4", "5.5"] },
    { "id": 4, "tasks": ["2.6", "5.2", "6.1"] },
    { "id": 5, "tasks": ["6.2", "6.4"] },
    { "id": 6, "tasks": ["6.3", "6.5", "6.6"] },
    { "id": 7, "tasks": ["6.7", "6.8", "7.1"] },
    { "id": 8, "tasks": ["7.2", "7.6"] },
    { "id": 9, "tasks": ["7.3", "7.4", "8.1"] },
    { "id": 10, "tasks": ["7.5", "8.2", "8.3", "8.4"] },
    { "id": 11, "tasks": ["8.5"] },
    { "id": 12, "tasks": ["8.6", "10.1"] },
    { "id": 13, "tasks": ["10.2", "10.3", "10.4"] },
    { "id": 14, "tasks": ["10.5"] },
    { "id": 15, "tasks": ["10.6", "10.7", "10.8"] }
  ]
}
```
