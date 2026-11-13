# Implementation Plan: portfolio-mod-05

## Overview

Implementación incremental del módulo `portfolio` (`src/acciones_ud/portfolio/`) en Python 3.12 con FastAPI, SQLAlchemy 2.x async y Alembic, según `design.md`. El orden va de dentro hacia afuera: verificación de supuestos y configuración, dominio puro, cambios aditivos en `orders`, persistencia, adaptadores externos, casos de uso, HTTP, Report_Scheduler y cableado en `main.py`.

Política de pruebas (instrucción del usuario: "Importante, no hagas tests obligatorios para todo, solo las partes críticas"): solo son obligatorias las pruebas de las Properties 1 a 11 de `design.md` y el ejemplo de Null_Broker_Client (Req. 9.4). El resto de sub-tareas de prueba se marca opcional con `*`.

Validación de cierre de cada checkpoint: `uv run ruff check .`, `uv run mypy src`, `uv run pytest`.

## Tasks

- [ ] 1. Verificar supuestos y preparar configuración y errores
  - [ ] 1.1 Verificar dependencias de `orders-mod-03` y `wallet-mod-04`
    - Confirmar que los paquetes `src/acciones_ud/orders/` y `src/acciones_ud/wallet/` existen e implementan lo que usa este diseño: tablas `order_executions`, `orders`, `order_events`, `order_reservations`; `PositionPort.qty_available` en `orders/domain/ports.py`; consulta de saldo de `wallet` con `BalanceView.unavailable`; `RecipientDirectory.recipient(user_id, event_type)` en `market_data`
    - Si falta alguno, detener la implementación y reportar qué falta; no crear sustitutos
    - Confirmar el siguiente número libre de migración en `migrations/versions/` y su `down_revision`; si no es `0008` con dependencia de `0007_orders_schema`, ajustar el nombre en la tarea 4.1 y documentarlo en un comentario de la migración
    - _Requirements: 10.1, 12.9_
  - [ ] 1.2 Verificar el cableado de Position_Port en `orders.composition`
    - Revisar si `orders/composition.py` ya lee `app.state.order_position_port` (D5); si no, agregar de forma aditiva: usar ese valor si existe y, si no, el `positions_client.py` actual
    - Confirmar que `main.py` permite llamar `portfolio.register(app)` antes de `orders.startup(app)`
    - _Requirements: 10.1_
  - [ ] 1.3 Verificar el formato de paginación y errores reutilizables
    - Revisar el formato de cursor y respuesta paginada de `orders` (token opaco, nombres `items`/`next_cursor`, `page_size` 1 a 100) y usar el mismo en `portfolio`; si difiere de `design.md`, seguir el de `orders` y anotarlo en `portfolio/adapters/inbound/http/schemas/pagination.py`
    - Confirmar si `ACCOUNT_NOT_LINKED`, `FORBIDDEN` y `NOT_FOUND` ya existen en `shared/domain/errors.py` y cómo `identity` expone los roles vigentes del usuario autenticado
    - _Requirements: 2.2, 8.1, 12.2, 12.4_
  - [ ] 1.4 Agregar `ErrorCode` y variables de configuración
    - Agregar `INVALID_PERIOD` (y los códigos de la tabla de errores que no existan) en `shared/domain/errors.py` y su traducción en `shared/infrastructure/http_errors.py`
    - Agregar en `config/settings.py` `PORTFOLIO_RISK_WINDOW_DAYS` (7 a 365, defecto 90), `PORTFOLIO_REPORT_INTERVAL_SECONDS` (60 a 86400, defecto 900) y `PORTFOLIO_JOBS_ENABLED` (defecto `true`); extender `require_api_settings` para reportar solo nombres de variables inválidas
    - Actualizar `.env.example`
    - _Requirements: 12.6, 12.7_
  - [ ]* 1.5 Escribir pruebas unitarias de configuración
    - Valores fuera de rango o no enteros se rechazan y el mensaje no incluye el valor
    - _Requirements: 12.6_

- [ ] 2. Implementar el dominio puro
  - [ ] 2.1 Crear entidades, puertos y errores de dominio
    - Crear `portfolio/domain/model.py` con las dataclasses `frozen=True` de la sección Data Models
    - Crear `portfolio/domain/ports.py` con todos los Protocol de `design.md`, incluidos `CommissionPort`, `BrokerClientPort` y `ReportNotifierPort`
    - Crear `portfolio/domain/errors.py` con `InvalidPeriodError` (con `field` y `reason`)
    - _Requirements: 1.1, 2.1, 9.1, 10.1_
  - [ ] 2.2 Implementar `period.py` y `rounding.py`
    - `period.parse` según D9 y `Period.bounds()` en UTC desde `America/New_York`
    - `rounding.money/qty/price/pct` con `ROUND_HALF_EVEN` y `rounding.shares` por mayor residuo con desempate por clave ascendente
    - _Requirements: 2.4, 4.4, 6.5, 11.1_
  - [ ] 2.3 Escribir property test de redondeo
    - **Property 9: Redondeo solo en la salida**
    - **Validates: Requirements 11.1**
  - [ ]* 2.4 Escribir pruebas unitarias de Period
    - `from > to` da `from_after_to`; 367 días da `too_long`; 366 días es válido
    - _Requirements: 2.4, 4.6, 6.5_
  - [ ] 2.5 Implementar `pnl.py`
    - `replay` con orden `(executed_at, execution_id)`, costo total (D1), `decimal.localcontext(prec=40)`, venta excedente con `mismatch = True` y `RealizedEvent` por venta; `average_cost`
    - La comisión por venta se recibe como función `ExecutionRecord -> Decimal` para no acoplar `CommissionPort`
    - _Requirements: 3.1, 3.2, 3.3, 3.6_
  - [ ] 2.6 Escribir property test del Pnl_Calculator contra el modelo de referencia
    - **Property 2: Pnl_Calculator contra el modelo de referencia**
    - **Validates: Requirements 3.1, 3.2, 3.6**
  - [ ] 2.7 Escribir property test de conservación del resultado
    - **Property 3: Conservación del resultado**
    - **Validates: Requirements 3.4**
  - [ ] 2.8 Escribir property test de confluencia y determinismo
    - **Property 4: Confluencia y determinismo del replay**
    - **Validates: Requirements 3.3, 3.5**
  - [ ] 2.9 Implementar `valuation.py`
    - `value` con P2 y P3 y `arrange` con totales sobre todas las Positions, orden D4 con desempate por `symbol` y filtro `hide_threshold` estricto
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 1.6_
  - [ ] 2.10 Escribir property test de valoración
    - **Property 1: Valoración de una posición**
    - **Validates: Requirements 1.2, 1.3, 1.4**
  - [ ]* 2.11 Escribir pruebas unitarias de `arrange`
    - Los cuatro valores de `sort_by` en ambas direcciones; `hide_threshold` no cambia los totales
    - _Requirements: 1.5, 1.6_
  - [ ] 2.12 Implementar `statistics.py`
    - `summarize` con conteos, volumen y desgloses por mercado, instrumento y sector con `unclassified` (sector nulo, vacío o instrumento ausente) y `unknown` (D6); vacío con ceros
    - _Requirements: 4.1, 4.2, 4.3, 4.5_
  - [ ] 2.13 Escribir property test de desgloses
    - **Property 5: Desgloses de participación**
    - **Validates: Requirements 4.2, 4.3, 4.4**
  - [ ] 2.14 Implementar `risk.py` y `profitability.py`
    - `risk.profile` con F, C, E, T, Risk_Score redondeado a 2 decimales antes de clasificar, `insufficient_data` y `equity_unavailable`
    - `profitability.rate` según P14
    - _Requirements: 5.2, 5.3, 5.5, 5.6, 5.7, 6.3_
  - [ ] 2.15 Escribir property test del Risk_Profiler contra el modelo de referencia
    - **Property 6: Risk_Profiler contra el modelo de referencia**
    - **Validates: Requirements 5.2, 5.3, 5.5, 5.7**
  - [ ] 2.16 Escribir property test de concentración monótona
    - **Property 7: Concentración monótona**
    - **Validates: Requirements 5.4**
  - [ ] 2.17 Escribir property test de rentabilidad
    - **Property 8: Rentabilidad del periodo**
    - **Validates: Requirements 6.3**
  - [ ]* 2.18 Escribir pruebas unitarias de `insufficient_data`
    - Sin Executions ni Positions: clasificación `insufficient_data` y `risk_score` nulo
    - _Requirements: 5.6_
  - [ ] 2.19 Implementar `access.py`
    - `resolve(user, required)` lanza `ForbiddenError` si el rol no está vigente
    - _Requirements: 12.2_

- [ ] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Persistencia y cambios aditivos en `orders`
  - [ ] 4.1 Crear la migración y la tabla `portfolio_reports`
    - Crear `migrations/versions/0008_portfolio_schema.py` (o el número confirmado en 1.1) con columnas, CHECK, índices, índice único parcial y trigger `portfolio_reports_immutable` (D8); `downgrade` elimina trigger, función y tabla
    - Crear `portfolio/adapters/outbound/persistence/tables.py`
    - _Requirements: 6.4, 7.4, 12.9_
  - [ ] 4.2 Implementar `report_repository.py` y `unit_of_work.py`
    - `add` (INSERT con `ON CONFLICT DO NOTHING` para tipos programados), `get(owner_id, id)`, `list_page(owner_id, type, cursor, size)`, `pending_notification()` y `mark_notified(id, at)`; sin UPDATE ni DELETE de contenido
    - Traducir errores de base de datos a `DatabaseUnavailableError`
    - _Requirements: 6.4, 7.4, 8.1, 8.2, 8.3, 12.5_
  - [ ]* 4.3 Escribir pruebas de base de datos de Reports (marca `db`)
    - Trigger rechaza UPDATE de `content`; índice único evita duplicados programados; paginación descendente; `upgrade`/`downgrade`
    - _Requirements: 6.4, 7.4, 8.1, 8.3, 12.9_
  - [ ] 4.4 Agregar `ExecutionLedger` en `orders`
    - Crear `orders/application/execution_ledger.py` con `list`, `list_page` y `active_share_reservations` (D2, D3)
    - Agregar en `orders/adapters/outbound/persistence/execution_repository.py` la consulta con JOIN a `orders` y subconsulta lateral del último `order_events` hacia `BROKER_SIGNED` con `actor_type = 'broker'`, y la suma de reservas `shares` activas por símbolo
    - Sin cambios en el contrato HTTP ni en el esquema de `orders`
    - _Requirements: 1.2, 2.1, 9.2_
  - [ ]* 4.5 Escribir pruebas de base de datos de `ExecutionLedger` (marca `db`)
    - `signed_by_broker_id` presente solo con firma de Broker; paginación por `(executed_at DESC, execution_id DESC)`
    - _Requirements: 2.2, 9.2_

- [ ] 5. Adaptadores de salida
  - [ ] 5.1 Implementar `AlpacaPositionsClient` y su fake
    - `adapters/outbound/alpaca/positions_client.py` con `list` y `get` (404 → `None`), usando `raise_for_alpaca`; sin `alpaca_account_id` en logs
    - `fake_positions.py` en memoria con contador de llamadas para las pruebas
    - _Requirements: 1.1, 1.8, 10.2, 10.3, 12.7_
  - [ ] 5.2 Implementar adaptadores hacia `orders`
    - `adapters/outbound/orders/execution_reader.py` y `reservation_reader.py` sobre `ExecutionLedger`
    - _Requirements: 1.2, 2.1, 9.2_
  - [ ] 5.3 Implementar adaptadores hacia `market_data`
    - `quote_reader.py` (cotización o `None`), `instrument_reader.py` (`exchange` y `sector`), `session_reader.py` (última sesión cerrada de `NYSE`) y `report_notifier.py` con `RecipientDirectory` y `Notifier`
    - _Requirements: 1.4, 4.2, 7.1, 7.3_
  - [ ] 5.4 Implementar adaptadores hacia `identity` y `wallet`
    - `account_reader.py`, `view_settings_reader.py` con `PORTFOLIO_DEFAULTS` (P13), `report_preferences_reader.py`
    - `wallet/equity_reader.py` que devuelve `None` con `BalanceView.unavailable` o cuenta no activa
    - _Requirements: 1.5, 5.7, 7.1, 7.2, 12.4_
  - [ ] 5.5 Implementar `ReferenceCommission` y `NullBrokerClient`
    - `commissions/reference_commission.py` con `qty × price × ORDER_REFERENCE_COMMISSION_RATE` y `source = "reference"`
    - `brokers/null_broker_client.py` con `[]` y `False`
    - _Requirements: 2.3, 9.4_
  - [ ]* 5.6 Escribir pruebas unitarias de adaptadores
    - Comisión de referencia; errores clasificados de Alpaca; defaults de vista
    - _Requirements: 1.8, 2.3, 10.3_

- [ ] 6. Servicios de aplicación
  - [ ] 6.1 Implementar `PortfolioService` y DTOs
    - `positions`, `client_positions` y `executions` según `design.md`, con lecturas en paralelo (`asyncio.gather`), `reconciliation_mismatch` y log `portfolio.reconciliation_mismatch` sin identificadores de cuenta
    - Redondeo solo al construir DTOs en `application/dtos.py`
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.6, 1.7, 2.1, 2.2, 2.3, 11.1, 12.4_
  - [ ]* 6.2 Escribir pruebas unitarias de `PortfolioService` con fakes
    - Fallback de precio; `reconciliation_mismatch` y log; 409 sin Linked_Account
    - _Requirements: 1.4, 1.7, 12.4_
  - [ ] 6.3 Implementar `StatisticsService` y `RiskProfileService`
    - Estadísticas del Period sin requerir Linked_Account; perfil con ventana `PORTFOLIO_RISK_WINDOW_DAYS`, `EquityPort` y métricas descriptivas con `rounding.shares`
    - _Requirements: 4.1, 4.5, 4.6, 5.1, 5.6, 5.7_
  - [ ] 6.4 Implementar `ReportBuilder` y `ReportService`
    - Contenido del Report según `design.md` (Realized_Pnl solo de ventas del Period, resumen de activos, rentabilidad); `create_on_demand`, `create_broker` con comisiones atribuidas por `signed_by_broker_id`, `list`, `get` y `get_client_report` con `is_linked` antes de buscar
    - Un fallo de Alpaca no almacena el Report
    - _Requirements: 6.1, 6.2, 6.3, 6.5, 8.1, 8.2, 8.3, 9.1, 9.2, 9.3, 9.5_
  - [ ] 6.5 Escribir prueba de ejemplo de Report `broker` con Null_Broker_Client
    - El Report se genera sin clientes y con totales en cero
    - _Requirements: 9.4_
  - [ ]* 6.6 Escribir pruebas unitarias del contenido de Reports
    - Realized_Pnl del Period con ventas fuera del Period; rentabilidad nula; comisiones atribuidas al Broker
    - _Requirements: 6.1, 6.2, 9.1, 9.2, 9.5_
  - [ ] 6.7 Implementar `PortfolioPositionPort`
    - `qty_available(alpaca_account_id, symbol)` con `AlpacaPositionPort.get`; `0` sin posición; propaga errores clasificados
    - _Requirements: 10.1, 10.2, 10.3_
  - [ ]* 6.8 Escribir pruebas unitarias de `PortfolioPositionPort`
    - _Requirements: 10.2, 10.3_
  - [ ] 6.9 Implementar `ReportScheduler`
    - `run_cycle(now)` con resúmenes diarios, mensuales, idempotencia, notificación con `notified_at`, reintento (D7) y log `portfolio.report_failed` sin secretos
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
  - [ ]* 6.10 Escribir pruebas unitarias del `ReportScheduler` con reloj y calendario falsos
    - Sin actividad no genera; fallo de un Investor no detiene a los demás; segundo ciclo no duplica ni notifica un Report con `notified_at` no nulo, y reintenta solo la notificación cuando `notified_at` es nulo
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Adaptadores HTTP y job
  - [ ] 8.1 Implementar esquemas HTTP
    - `adapters/inbound/http/schemas/` con `DecimalStr`, respuestas de posiciones, historial, estadísticas, perfil, reportes y páginas, con el formato de paginación confirmado en 1.3
    - _Requirements: 11.2, 12.8_
  - [ ] 8.2 Escribir property test de round-trip de decimales
    - **Property 10: Round-trip de decimales serializados**
    - **Validates: Requirements 11.2, 11.3**
  - [ ] 8.3 Implementar routers y dependencias
    - `deps.py` con `require_investor`/`require_broker` sobre la autenticación de `identity`
    - `routers/portfolio.py` y `routers/broker_portfolio.py` con los endpoints de la tabla de `design.md` y `responses={...: {"model": ErrorBody}}` por ruta
    - _Requirements: 1.1, 2.1, 4.1, 5.1, 6.1, 8.1, 8.2, 9.1, 9.3, 12.1, 12.2, 12.3, 12.4, 12.5, 12.8_
  - [ ] 8.4 Implementar `report_scheduler_job.py`
    - Tarea asyncio con intervalo `PORTFOLIO_REPORT_INTERVAL_SECONDS` y cancelación limpia en `shutdown`
    - _Requirements: 7.1, 7.2, 7.5_

- [ ] 9. Cableado e integración
  - [ ] 9.1 Implementar `portfolio/composition.py` y registrar en `main.py`
    - `register(app)` cablea puertos, usa `app.state.portfolio_commission_port` y `app.state.portfolio_broker_clients` si existen, asigna `app.state.order_position_port` e incluye los routers
    - `startup` arranca el job solo con `PORTFOLIO_JOBS_ENABLED`; `shutdown` lo detiene
    - En `main.py`, `portfolio.register(app)` antes de `orders.startup(app)` y `startup`/`shutdown` de `portfolio` después de los de `orders` (D5)
    - _Requirements: 9.4, 10.1_
  - [ ] 9.2 Escribir property test de control de acceso
    - **Property 11: Control de acceso de los endpoints**
    - **Validates: Requirements 9.3, 12.1, 12.2, 12.3, 12.4**
  - [ ]* 9.3 Escribir pruebas de API con fakes
    - 422 `INVALID_PERIOD`; 502/503 de Alpaca; 503 `DATABASE_UNAVAILABLE`; esquemas de error en `/openapi.json`; ausencia de secretos en Error_Body y logs
    - _Requirements: 1.8, 2.4, 6.5, 12.5, 12.7, 12.8_

- [ ] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Las pruebas obligatorias son las Properties 1 a 11 (`tests/portfolio/property/`, `@settings(max_examples=100)`, comentario `# Feature: portfolio-mod-05, Property {n}: {texto}`) y el ejemplo de Null_Broker_Client (`tests/portfolio/unit/`)
- Las pruebas marcadas `db` se saltan sin `TEST_DATABASE_URL`
- La tarea 1 puede bloquear el resto: si `orders-mod-03` o `wallet-mod-04` no están implementados, se reporta y no se continúa
- Aplicar la migración es un paso manual (`uv run alembic upgrade head`)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["1.4", "2.1"] },
    { "id": 2, "tasks": ["1.5", "2.2", "2.19", "4.1", "4.4"] },
    { "id": 3, "tasks": ["2.3", "2.4", "2.5", "4.2", "5.2"] },
    { "id": 4, "tasks": ["2.6", "2.9", "4.3", "4.5", "5.1", "5.3", "5.4", "5.5"] },
    { "id": 5, "tasks": ["2.7", "2.10", "2.12", "5.6"] },
    { "id": 6, "tasks": ["2.8", "2.11", "2.13", "2.14"] },
    { "id": 7, "tasks": ["2.15", "6.1", "6.7"] },
    { "id": 8, "tasks": ["2.16", "6.2", "6.3", "6.8"] },
    { "id": 9, "tasks": ["2.17", "6.4"] },
    { "id": 10, "tasks": ["2.18", "6.5", "6.9", "8.1"] },
    { "id": 11, "tasks": ["6.6", "6.10", "8.2", "8.3", "8.4"] },
    { "id": 12, "tasks": ["9.1"] },
    { "id": 13, "tasks": ["9.2", "9.3"] }
  ]
}
```
