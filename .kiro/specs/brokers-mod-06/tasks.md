# Implementation Plan: brokers-mod-06

## Overview

Implementación incremental de MOD-06 como el paquete `src/acciones_ud/brokers/` en Python 3.12 con arquitectura hexagonal. El orden es: verificación de dependencias y alineación de desviaciones, base del módulo (errores, configuración, entidades, puertos), reglas de dominio puras, persistencia, adaptadores de salida, casos de uso (directorio, vinculación, Broker_Link_Adapter, propuestas, calificaciones, clientes), cambios aditivos en `orders` e `identity`, notificaciones y Expiry_Job, endpoints HTTP y cableado en `main.py`.

Política de pruebas (indicación del usuario: "solo las partes críticas"): son obligatorias las pruebas de las Properties 1 a 12 del diseño y la prueba de humo del cableado (Req. 16.3). Todas las demás pruebas son opcionales y llevan `*`.

Validación antes de cerrar cada tarea: `uv run ruff check .`, `uv run mypy src` y `uv run pytest`.

## Tasks

- [ ] 1. Verificación previa y alineación de desviaciones
  - [ ] 1.1 Verificar que `orders-mod-03` y `portfolio-mod-05` están implementados y fijar el número de migración
    - Confirmar en `src/acciones_ud/orders/` que existen `NullBrokerLink`, la lectura de `app.state.order_broker_link`, el estado `BROKER_SIGNED`, la tabla `order_idempotency_keys` con clave única `(user_id, idempotency_key)`, `OrderSubmitter.submit` y el Order_Scheduler
    - Confirmar en `src/acciones_ud/portfolio/` que existen `NullBrokerClient`, la lectura de `app.state.portfolio_broker_clients` y `ExecutionLedger` con atribución por evento `actor_type = 'broker'`
    - Comprobar si `orders` y `portfolio` resuelven esos adaptadores en `register` o en `startup` y anotar el orden de registro necesario en `main.py`
    - Listar `migrations/versions/` y fijar el siguiente número libre y su `down_revision`; si no es `0009` sobre `0008_portfolio_schema`, actualizar el nombre en `design.md`
    - Confirmar si ya existen `CONFIRMATION_REQUIRED`, `ACCOUNT_NOT_LINKED`, `EXTRA_AUTHORIZATION_INVALID`, `QUOTE_UNAVAILABLE` y `ASSET_NOT_TRADABLE` en `ErrorCode`, `RecipientDirectory`, `ContractedPlanReader` y el modo de guardado de `EVENT_TYPES` en `identity/domain/preferences.py`
    - Si `orders-mod-03` o `portfolio-mod-05` no están implementados, detener el plan y reportarlo
    - _Requirements: 16.1, 16.2, 16.3, 16.5_

  - [ ] 1.2 Confirmar con el equipo las tres desviaciones del diseño frente al requisito y alinear los documentos
    - D1: conversión en dos transacciones (`orders` confirma la Order y luego `brokers` confirma `approved`); el Req. 10.2 pide "la misma transacción"
    - D4: umbral de TOTP en la aceptación con `estimated_cost >= high_order_threshold_usd`, mientras `orders` usa `>` estricto (O10)
    - B8 define `approved` → `conversion_failed`; el diseño registra `accepted` → `conversion_failed` con `attempted: approve` en el evento
    - Registrar la decisión del equipo en `requirements.md` (decisiones B/A) y en `design.md`; si el equipo rechaza alguna, ajustar el diseño antes de las tareas 3.3, 10.1, 11.3 y 11.6
    - No implementar las tareas 3.3, 10.1, 11.3 ni 11.6 hasta cerrar esta tarea
    - _Requirements: 9.3, 10.2, 10.5_

- [ ] 2. Base del módulo: errores, configuración, entidades y puertos
  - [ ] 2.1 Agregar los códigos de error nuevos y su traducción HTTP
    - En `shared/domain/errors.py` agregar a `ErrorCode`: `BROKER_NOT_FOUND`, `CONSENT_REQUIRED`, `LINK_ALREADY_EXISTS`, `INVALID_LINK_STATE`, `LINK_NOT_FOUND`, `PROPOSAL_NOT_FOUND`, `PROPOSAL_VERSION_CONFLICT`, `INVALID_PROPOSAL_STATE`, `TRADING_AUTHORIZATION_REQUIRED`, `RATING_NOT_ALLOWED`, `CLIENT_NOT_FOUND` y `CONFIRMATION_REQUIRED` si falta (según 1.1)
    - Registrar en `shared/infrastructure/http_errors.py` el estado HTTP de cada código según la tabla de Error Handling del diseño
    - _Requirements: 17.4, 18.3_

  - [ ] 2.2 Agregar la configuración de `brokers` a `config/settings.py`
    - `BROKER_LINK_REQUEST_TTL_DAYS` (7, 1–90), `PROPOSAL_TTL_HOURS` (72, 1–720), `BROKER_LINK_CONSENT_VERSION` y `BROKER_TRADING_CONSENT_VERSION` (`"v1"`, 1–32 caracteres), `BROKERS_EXPIRY_INTERVAL_SECONDS` (300, 10–86400), `BROKERS_JOBS_ENABLED` (`true`)
    - Un valor fuera de rango falla el arranque con error de configuración explícito; reutilizar `ORDER_REFERENCE_COMMISSION_RATE` de `orders`
    - Documentar las variables en `.env.example`
    - _Requirements: 18.2_

  - [ ] 2.3 Crear entidades, errores de dominio y puertos de `brokers`
    - `brokers/domain/entities.py`: `LinkStatus`, `LinkAction`, `Link`, `TradingAuthorization`, `ProposalStatus`, `ProposalAction`, `Proposal`, `ProposalVersion`, `ProposalDecision`, `ProposalMessage`, `BrokerProfile`, `Rating`, `Reputation`, `BrokerEvent`, `BrokerIdentity` como dataclasses `frozen=True`
    - `brokers/domain/errors.py`: errores de dominio de la tabla de Error Handling, subclases de `AppError`
    - `brokers/domain/ports.py`: Protocol de directorio, solicitud de Broker, Linked_Account, Order_Controls, TOTP, cotización, `OrderCreationPort`, `OrderQueryPort`, notificador y repositorios; `ProposalOrderCommand`, `OrderCreated`, `OrderRejected`
    - Sin imports de FastAPI, SQLAlchemy ni SDKs en `domain/`
    - _Requirements: 16.5, 17.5_

- [ ] 3. Reglas de dominio puras
  - [ ] 3.1 Implementar `brokers/domain/link_state_machine.py`
    - `transition`, `is_terminal`, `is_open`, `effective_status(link, now, ttl_days)` y `actor_allowed(action, actor_role)` según B1, B23 y D6
    - _Requirements: 3.5, 3.6, 3.7, 3.8, 3.9, 4.1_

  - [ ] 3.2 Escribir la prueba de propiedad de la tabla de transiciones de la Link
    - **Property 1: Tabla de transiciones de la Link**
    - **Validates: Requirements 3.5, 3.6, 3.7, 3.9, 4.1**
    - `tests/brokers/property/test_link_state_machine.py`, `@settings(max_examples=100)`

  - [ ] 3.3 Implementar `brokers/domain/proposal_state_machine.py`
    - `transition` con la tabla de B8 (incluida `conversion_fail` desde `accepted` según lo decidido en 1.2), `check_version` y `effective_status(proposal, now, ttl_hours)`; el estado se comprueba antes que la versión
    - _Requirements: 8.1, 8.3, 8.5, 9.2, 9.4_

  - [ ] 3.4 Escribir la prueba de propiedad de la tabla de transiciones de la Proposal
    - **Property 7: Tabla de transiciones de la Proposal**
    - **Validates: Requirements 8.3, 8.5, 9.2**
    - `tests/brokers/property/test_proposal_state_machine.py`

  - [ ] 3.5 Implementar `estimates.py`, `reputation.py`, `access.py` y `periods.py`
    - `estimates`: `reference_price`, `estimated_cost` (half-even, 2 decimales, `localcontext(prec=40)`), `requires_totp` con la comparación decidida en 1.2
    - `reputation`: `average` (None si vacía) y `upsert` por Link
    - `access`: `require_active_link` (404 con código del recurso) y `resolve_link_membership`
    - `periods`: `to_utc_range` en `America/New_York` e `InvalidPeriodError`; `link_overlaps` (B19)
    - _Requirements: 5.1, 7.5, 7.6, 9.3, 13.2, 14.2, 17.1, 17.2_

  - [ ] 3.6 Escribir la prueba de propiedad del promedio de reputación
    - **Property 12: Promedio de reputación**
    - **Validates: Requirements 14.2**
    - `tests/brokers/property/test_reputation.py`

  - [ ]* 3.7 Escribir pruebas unitarias de `estimates` y `periods`
    - Fórmula del costo estimado, precio de referencia `market`/`limit`, `QuoteUnavailableError`, Period con `from > to` y solapamiento de Links
    - _Requirements: 5.1, 7.5, 7.6_

- [ ] 4. Persistencia
  - [ ] 4.1 Crear la migración de esquema de `brokers`
    - `migrations/versions/<número de 1.1>_brokers_schema.py` con las tablas, CHECK, índices únicos parciales (`ux_broker_links_open_investor`, `ux_trading_auth_active_link`), CHECK `(status = 'approved') = (order_id IS NOT NULL)`, triggers de inmutabilidad de versiones, decisiones, mensajes y `broker_events`, y RLS sin políticas
    - Insertar preferencias por defecto de `broker_link_updates` y `proposal_updates` si `identity` guarda preferencias por fila (según 1.1)
    - `downgrade` en orden inverso; no modifica datos existentes de otros módulos
    - _Requirements: 3.3, 6.5, 9.4, 11.2, 13.2, 17.5_

  - [ ] 4.2 Implementar modelos y repositorios SQLAlchemy
    - `brokers/adapters/outbound/persistence/`: `models.py`, `link_repository.py`, `proposal_repository.py`, `rating_repository.py`, `profile_repository.py`, `event_repository.py`
    - `SELECT ... FOR UPDATE`, actualizaciones condicionales `WHERE status = :esperado`, `ON CONFLICT (link_id) DO UPDATE` para Ratings, paginación por cursor opaco base64
    - Traducir la violación de `ux_broker_links_open_investor` a `LinkAlreadyExistsError`
    - _Requirements: 3.3, 5.1, 5.2, 12.3, 13.2, 14.4, 17.5_

  - [ ]* 4.3 Escribir pruebas `db` de la migración y los repositorios
    - `upgrade`/`downgrade`, índices únicos parciales, CHECK de `broker_proposals`, triggers de inmutabilidad y filtros por Period; se saltan sin `TEST_DATABASE_URL`
    - _Requirements: 3.3, 6.5, 17.5_

- [ ] 5. Adaptadores de salida y fakes en memoria
  - [ ] 5.1 Implementar los adaptadores de `identity`
    - `brokers/adapters/outbound/identity/`: `broker_directory.py`, `linked_account_reader.py`, `controls_reader.py`, `totp_verifier.py`, `broker_request_reader.py` (solo lectura, D8)
    - _Requirements: 1.4, 2.1, 2.2, 5.5, 9.3_

  - [ ] 5.2 Implementar `brokers/adapters/outbound/market_data/quote_reader.py`
    - Usa el caso de uso de cotización existente y `InstrumentRepository.get(symbol)` (`active` y `tradable`)
    - _Requirements: 7.3, 7.4, 7.5_

  - [ ] 5.3 Crear los fakes en memoria para las pruebas de propiedad
    - `tests/brokers/fakes.py`: repositorios que aplican las mismas restricciones únicas que la migración, `Clock` falso, TOTP falso, Order_Creation_Port con idempotencia por clave `proposal:{id}` y contador de llamadas, Order_Query_Port con contador, notificador que registra llamadas
    - Necesarios para las Properties 2 a 6 y 8 a 11
    - _Requirements: 10.3, 16.1_

- [ ] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Directorio y perfil del comisionista
  - [ ] 7.1 Implementar `brokers/application/directory_service.py`
    - `update_profile` con límites del perfil, `get_profile` (404 `BROKER_NOT_FOUND`), `suggestions` y `search` paginada que excluyen al propio usuario
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4_

  - [ ]* 7.2 Escribir pruebas unitarias del directorio
    - Límites del perfil, Broker sin rol vigente, exclusión del solicitante y paginación
    - _Requirements: 1.1–1.4, 2.1–2.4_

- [ ] 8. Vinculación y Trading_Authorization
  - [ ] 8.1 Implementar en `brokers/application/link_service.py` la solicitud y la respuesta
    - `request_link` con el orden de comprobaciones del diseño y persistencia previa de la expiración vencida del Investor (D6); `accept`, `decline`, `cancel`, `pending_requests`, `current` (con `pending_broker_selection`, B5) y `history` filtrado por estado y Period
    - `BrokerEvent` por transición dentro de la transacción; notificación después del commit
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.9, 3.10, 5.1, 5.2, 5.3, 5.4, 5.5, 17.5_

  - [ ] 8.2 Escribir la prueba de propiedad de Link abierta única por Investor
    - **Property 2: Como máximo una Link abierta por Investor**
    - **Validates: Requirements 3.3, 3.4, 3.8**
    - `tests/brokers/property/test_link_uniqueness.py` con `RuleBasedStateMachine`

  - [ ] 8.3 Implementar en `link_service.py` el fin de la Link y la autorización
    - `end_link` en una transacción: Link → `ended`, revocación con `link_ended` solo si hay Trading_Authorization vigente (sin vigente termina sin error), Proposals `sent`/`accepted` → `withdrawn(link_ended)`, un evento por entidad; si la revocación falla se revierte todo y la Link queda sin cambios; `CONFIRMATION_REQUIRED` sin `confirmed`
    - `grant_trading` idempotente con consentimiento, `revoke_trading` (409 `INVALID_LINK_STATE` con `no_active_authorization`), `set_order_review` con evento
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ] 8.4 Escribir la prueba de propiedad de la cascada del fin de la Link
    - **Property 3: Cascada del fin de la Link**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7**
    - `tests/brokers/property/test_link_end_cascade.py`

  - [ ] 8.5 Escribir la prueba de propiedad de la Trading_Authorization
    - **Property 4: Trading_Authorization única y ligada a la Active_Link**
    - **Validates: Requirements 6.3, 6.4, 6.5**
    - `tests/brokers/property/test_trading_authorization.py`

  - [ ]* 8.6 Escribir pruebas unitarias de historial y vinculación vigente
    - Filtros por estado y Period, `pending_broker_selection`, consentimiento ausente y `order_review_enabled`
    - _Requirements: 3.1, 3.2, 3.10, 5.1–5.5, 6.1, 6.2, 6.6_

- [ ] 9. Broker_Link_Adapter
  - [ ] 9.1 Implementar `brokers/adapters/outbound/broker_link_adapter.py`
    - `is_linked`, `linked_investors` y `reviewing_broker` con una consulta por llamada, join con `role_assignments` en `ACTIVE` y sin caché; implementa `BrokerLinkPort` de `orders` y `BrokerClientPort` de `portfolio`
    - _Requirements: 15.4, 16.1, 16.2_

  - [ ] 9.2 Escribir la prueba de propiedad de pertenencia
    - **Property 5: Pertenencia del Broker_Link_Adapter**
    - **Validates: Requirements 16.1, 16.2, 15.4**
    - `tests/brokers/property/test_link_membership.py` contra `access.resolve_link_membership` y un adaptador en memoria con la misma regla

  - [ ]* 9.3 Escribir la prueba `db` del adaptador SQL contra el modelo
    - _Requirements: 16.1, 16.2_

- [ ] 10. Cambios aditivos en `orders`
  - [ ] 10.1 Implementar `create_from_proposal` y publicar los puertos de `orders`
    - Requiere 1.2 cerrada (D1)
    - `orders/application/proposal_orders.py`: `OrderRequest` con `simple`, `day`, `schedule_if_closed = true`, `confirmed = true`, clave `proposal:{proposal_id}` del Investor; mismas validaciones que `POST /orders` sin autorización adicional; estado inicial `BROKER_SIGNED` con evento `actor_type = 'broker'` y `reason = proposal:{id}`; envío o programación según el mercado; repetición devuelve la misma Order
    - Resultados `OrderCreated` / `OrderRejected(code)` y propagación de excepciones de indisponibilidad (D2)
    - Admitir `BROKER_SIGNED` como estado inicial solo para este caso de uso en la máquina de estados de `orders`
    - `orders.register` publica `app.state.order_proposal_creation` y `app.state.order_query_port` (`list_for_investor`, `find_by_idempotency_key`)
    - Implementar `brokers/adapters/outbound/orders/order_creation.py` y `order_query.py` sobre esos puertos
    - Sin endpoints HTTP nuevos en `orders`
    - _Requirements: 10.2, 10.3, 10.5, 10.6, 15.2, 16.5_

  - [ ]* 10.2 Escribir pruebas unitarias de `create_from_proposal`
    - Idempotencia por clave, rechazo de negocio sin persistir, mercado cerrado y atribución al Broker
    - _Requirements: 16.5_

- [ ] 11. Propuestas y mensajes
  - [ ] 11.1 Implementar en `brokers/application/proposal_service.py` creación, modificación y retiro
    - `create` con Active_Link (404 `CLIENT_NOT_FOUND`), Linked_Account, símbolo negociable, precio de referencia y costo estimado; Proposal `sent` + Version 1 + evento
    - `modify` (versión nueva, anula la aceptación) y `withdraw` con motivo y `confirmed`; estado antes que versión
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ] 11.2 Escribir la prueba de propiedad del control de versión
    - **Property 8: Control de versión de la Proposal**
    - **Validates: Requirements 8.1, 8.2, 8.4, 9.1, 9.4**
    - `tests/brokers/property/test_proposal_versions.py`

  - [ ] 11.3 Implementar en `proposal_service.py` la decisión del Investor
    - Requiere 1.2 cerrada (D4)
    - `investor_decide` (`accept`/`reject` con comentario): Linked_Account, estado, versión y TOTP antes de abrir la transacción si `requires_totp`; el código nunca se guarda ni se registra; notificación `proposal_updates` al Broker
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 18.4_

  - [ ] 11.4 Escribir la prueba de propiedad del TOTP en la aceptación
    - **Property 9: TOTP en la aceptación**
    - **Validates: Requirements 9.3**
    - `tests/brokers/property/test_acceptance_totp.py`

  - [ ] 11.5 Implementar `brokers/application/message_service.py`
    - `post` (1 a 1000 caracteres, inmutable) y `thread` paginado por cursor; notificación a la otra parte
    - _Requirements: 11.1, 11.2, 11.3_

  - [ ] 11.6 Implementar en `proposal_service.py` la decisión del Broker y la conversión
    - Requiere 1.2 cerrada (D1 y `accepted` → `conversion_failed`)
    - `broker_decide`: orden de comprobaciones del diseño, evidencia del hilo, Trading_Authorization vigente; llamada a `OrderCreationPort` fuera del bloqueo y segunda transacción con relectura `FOR UPDATE`; `approved` con `order_id`, `conversion_failed` con `failure_code`, Proposal en `accepted` ante indisponibilidad, `orphan_order` en el evento si cambió el estado; repetición sobre `approved` devuelve la misma Order; `decline` con evidencia
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8_

  - [ ] 11.7 Escribir la prueba de propiedad de la conversión exactamente una vez
    - **Property 10: Conversión en Order exactamente una vez**
    - **Validates: Requirements 10.2, 10.3, 10.4, 10.5, 10.6**
    - `tests/brokers/property/test_proposal_conversion.py`

  - [ ] 11.8 Implementar en `proposal_service.py` historial y detalle
    - `history_investor`, `history_broker` (estado, Period, cursor) y `detail` con versiones, decisiones y `order_id`; `effective_status` al leer sin escribir (D6)
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

  - [ ]* 11.9 Escribir pruebas unitarias de propuestas y mensajes
    - Validación de creación, `QUOTE_UNAVAILABLE`, evidencia ajena, `decline`, mensajes vacíos o largos e historial
    - _Requirements: 7.1–7.6, 10.1, 10.7, 10.8, 11.1–11.3, 12.1–12.4_

- [ ] 12. Calificaciones y portal de clientes
  - [ ] 12.1 Implementar `brokers/application/rating_service.py`
    - `publish` con la Link más reciente `active` o `ended` (D5) y reemplazo por Link; `reputation` y `reviews` paginadas
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 14.1, 14.2, 14.3, 14.4_

  - [ ] 12.2 Escribir la prueba de propiedad de Rating por Link
    - **Property 11: Una Rating por Link con reemplazo**
    - **Validates: Requirements 13.1, 13.2, 13.3, 14.3**
    - `tests/brokers/property/test_ratings.py`

  - [ ] 12.3 Implementar `brokers/application/client_service.py`
    - `clients` (Active_Links del Broker) y `client_orders` con Active_Link (404 `CLIENT_NOT_FOUND`) sobre `OrderQueryPort.list_for_investor`
    - _Requirements: 15.1, 15.2, 15.3_

  - [ ]* 12.4 Escribir pruebas unitarias de reputación, reseñas y clientes
    - _Requirements: 14.1, 14.4, 15.1_

- [ ] 13. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 14. Notificaciones, Expiry_Job y cambios aditivos en `identity`
  - [ ] 14.1 Implementar el notificador y los tipos de evento
    - Agregar `broker_link_updates` y `proposal_updates` a `EVENT_TYPES` de `identity/domain/preferences.py` con `in_app` por defecto
    - `brokers/adapters/outbound/notifications/brokers_notifier.py` sobre `RecipientDirectory` y `Notifier.notify`; un fallo se registra en log y no revierte
    - _Requirements: 18.1_

  - [ ] 14.2 Implementar `ExpiryService` y el Expiry_Job
    - `brokers/application/expiry_service.py`: `run_once(now)` que en la misma ejecución expira Links `requested` y Proposals `sent` vencidas con actualización condicional en lotes `FOR UPDATE SKIP LOCKED`, un evento y una notificación por transición de cada categoría; las Proposals `accepted` no expiran y solo reciben la reconciliación D3
    - `brokers/adapters/inbound/jobs/expiry_job.py`: tarea asyncio con `BROKERS_EXPIRY_INTERVAL_SECONDS`; una excepción se registra y el ciclo siguiente reintenta
    - _Requirements: 3.8, 8.6, 18.6_

  - [ ]* 14.3 Escribir pruebas unitarias del Expiry_Job y las notificaciones
    - Reloj falso, una notificación por transición, D3 con Order existente
    - _Requirements: 3.8, 8.6, 9.5, 11.1, 18.6_

  - [ ] 14.4 Implementar `associated_broker` en `/users/me`
    - Protocol `AssociatedBrokerReader` en `identity/domain/`, resuelto desde `app.state.associated_broker_reader` (null si no existe); esquema `AssociatedBrokerOut` con `id`, `name`, `firm_name` y `since`
    - `brokers/adapters/outbound/identity/associated_broker_reader.py`
    - _Requirements: 16.4_

  - [ ]* 14.5 Escribir prueba de API de `associated_broker`
    - _Requirements: 16.4_

- [ ] 15. Endpoints HTTP
  - [ ] 15.1 Crear los esquemas Pydantic
    - `brokers/adapters/inbound/http/schemas/`: request y response de la tabla de endpoints; decimales como cadenas; `page_size` 1–100 (defecto 20); reutilizar `OrderPage` y filtros de `orders`
    - _Requirements: 12.1, 12.4, 15.2, 18.5_

  - [ ] 15.2 Implementar los routers de Investor y públicos
    - `directory_router.py`, `links_router.py`, `proposals_router.py` con `get_current_user` y `require_investor`; `responses={código: {"model": ErrorBody}}` por ruta
    - `GET /brokers/{broker_id}` es público: sin `get_current_user`, sin 401, y la respuesta solo expone los campos públicos del perfil (Req. 1.5)
    - `GET /broker-links/current` responde 200 con campos de Link y Trading_Authorization en null cuando no hay Link abierta (Req. 5.6)
    - _Requirements: 1.3, 2.1–2.4, 3.1, 3.7, 4.1, 5.1, 5.5, 6.2–6.6, 9.1, 11.1, 12.1, 13.1, 14.1, 14.4, 17.4, 18.5_

  - [ ] 15.3 Implementar los routers de Broker
    - `broker_links_router.py`, `broker_proposals_router.py`, `broker_clients_router.py` y `PUT /brokers/me/profile` con `require_broker` y prefijo `/broker/` (D7)
    - _Requirements: 1.1, 3.5, 3.6, 3.10, 7.1, 8.1, 8.3, 10.1, 11.1, 12.2, 15.1, 15.2, 17.4, 18.5_

  - [ ] 15.4 Escribir la prueba de propiedad del control de acceso
    - **Property 6: Control de acceso de los endpoints**
    - **Validates: Requirements 15.2, 15.3, 17.1, 17.2, 17.3, 17.4**
    - `tests/brokers/property/test_access_control.py` con `TestClient` y fakes que cuentan llamadas

  - [ ]* 15.5 Escribir pruebas de contrato OpenAPI y ausencia de secretos
    - Errores declarados por endpoint en `/openapi.json`; TOTP y `alpaca_account_id` ausentes de Error_Body, logs y eventos
    - _Requirements: 18.4, 18.5_

- [ ] 16. Cableado
  - [ ] 16.1 Implementar `brokers/composition.py` y registrarlo en `main.py`
    - `register`: routers, `BrokerLinkAdapter` en `app.state.order_broker_link` y `app.state.portfolio_broker_clients`, `app.state.associated_broker_reader`
    - `startup`: resolver `order_proposal_creation` y `order_query_port` (error de configuración si faltan) y arrancar el Expiry_Job si `BROKERS_JOBS_ENABLED`; `shutdown` lo detiene
    - Orden en `main.py` según el diseño, ajustado con lo verificado en 1.1
    - _Requirements: 16.1, 16.2, 16.3_

  - [ ] 16.2 Escribir la prueba de humo del cableado
    - `tests/brokers/unit/test_composition.py`: el mismo objeto queda en `app.state.order_broker_link` y `app.state.portfolio_broker_clients`, y `orders` y `portfolio` lo usan después de `startup`
    - _Requirements: 16.3_

- [ ] 17. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Las tareas con `*` son opcionales. Las obligatorias de prueba son las Properties 1 a 12 y la prueba de humo 16.2.
- Las tareas 3.3, 10.1, 11.3 y 11.6 dependen de cerrar 1.2 con el equipo.
- Cada prueba de propiedad lleva `# Feature: brokers-mod-06, Property {n}: {texto}` y `@settings(max_examples=100)`.
- Las pruebas `db` se saltan sin `TEST_DATABASE_URL`.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1", "2.2"] },
    { "id": 2, "tasks": ["2.3"] },
    { "id": 3, "tasks": ["3.1", "3.3", "3.5", "4.1"] },
    { "id": 4, "tasks": ["3.2", "3.4", "3.6", "3.7", "4.2"] },
    { "id": 5, "tasks": ["4.3", "5.1", "5.2", "5.3"] },
    { "id": 6, "tasks": ["7.1", "8.1", "9.1", "10.1", "12.1"] },
    { "id": 7, "tasks": ["7.2", "8.2", "8.3", "9.2", "9.3", "10.2", "11.1", "12.2"] },
    { "id": 8, "tasks": ["8.4", "8.5", "8.6", "11.2", "11.3", "11.5", "12.3"] },
    { "id": 9, "tasks": ["11.4", "11.6", "12.4", "14.1", "14.4"] },
    { "id": 10, "tasks": ["11.7", "11.8", "14.2", "14.5"] },
    { "id": 11, "tasks": ["11.9", "14.3", "15.1"] },
    { "id": 12, "tasks": ["15.2", "15.3"] },
    { "id": 13, "tasks": ["15.4", "15.5", "16.1"] },
    { "id": 14, "tasks": ["16.2"] }
  ]
}
```
