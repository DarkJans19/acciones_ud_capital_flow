# Implementation Plan: brokers-mod-06

## Overview

ImplementaciÃ³n incremental de MOD-06 como el paquete `src/acciones_ud/brokers/` en Python 3.12 con arquitectura hexagonal. El orden es: verificaciÃ³n de dependencias y alineaciÃ³n de desviaciones, base del mÃ³dulo (errores, configuraciÃ³n, entidades, puertos), reglas de dominio puras, persistencia, adaptadores de salida, casos de uso (directorio, vinculaciÃ³n, Broker_Link_Adapter, propuestas, calificaciones, clientes), cambios aditivos en `orders` e `identity`, notificaciones y Expiry_Job, endpoints HTTP y cableado en `main.py`.

PolÃ­tica de pruebas (indicaciÃ³n del usuario: "solo las partes crÃ­ticas"): son obligatorias las pruebas de las Properties 1 a 12 del diseÃ±o y la prueba de humo del cableado (Req. 16.3). Todas las demÃ¡s pruebas son opcionales y llevan `*`.

ValidaciÃ³n antes de cerrar cada tarea: `uv run ruff check .`, `uv run mypy src` y `uv run pytest`.

## Tasks

- [x] 1. VerificaciÃ³n previa y alineaciÃ³n de desviaciones
  - [x] 1.1 Verificar que `orders-mod-03` y `portfolio-mod-05` estÃ¡n implementados y fijar el nÃºmero de migraciÃ³n
    - Confirmar en `src/acciones_ud/orders/` que existen `NullBrokerLink`, la lectura de `app.state.order_broker_link`, el estado `BROKER_SIGNED`, la tabla `order_idempotency_keys` con clave Ãºnica `(user_id, idempotency_key)`, `OrderSubmitter.submit` y el Order_Scheduler
    - Confirmar en `src/acciones_ud/portfolio/` que existen `NullBrokerClient`, la lectura de `app.state.portfolio_broker_clients` y `ExecutionLedger` con atribuciÃ³n por evento `actor_type = 'broker'`
    - Comprobar si `orders` y `portfolio` resuelven esos adaptadores en `register` o en `startup` y anotar el orden de registro necesario en `main.py`
    - Listar `migrations/versions/` y fijar el siguiente nÃºmero libre y su `down_revision`; si no es `0009` sobre `0008_portfolio_schema`, actualizar el nombre en `design.md`
    - Confirmar si ya existen `CONFIRMATION_REQUIRED`, `ACCOUNT_NOT_LINKED`, `EXTRA_AUTHORIZATION_INVALID`, `QUOTE_UNAVAILABLE` y `ASSET_NOT_TRADABLE` en `ErrorCode`, `RecipientDirectory`, `ContractedPlanReader` y el modo de guardado de `EVENT_TYPES` en `identity/domain/preferences.py`
    - Si `orders-mod-03` o `portfolio-mod-05` no estÃ¡n implementados, detener el plan y reportarlo
    - _Requirements: 16.1, 16.2, 16.3, 16.5_

  - [x] 1.2 Confirmar con el equipo las tres desviaciones del diseÃ±o frente al requisito y alinear los documentos
    - D1: conversiÃ³n en dos transacciones (`orders` confirma la Order y luego `brokers` confirma `approved`); el Req. 10.2 pide "la misma transacciÃ³n"
    - D4: umbral de TOTP en la aceptaciÃ³n con `estimated_cost >= high_order_threshold_usd`, mientras `orders` usa `>` estricto (O10)
    - B8 define `approved` â†’ `conversion_failed`; el diseÃ±o registra `accepted` â†’ `conversion_failed` con `attempted: approve` en el evento
    - Registrar la decisiÃ³n del equipo en `requirements.md` (decisiones B/A) y en `design.md`; si el equipo rechaza alguna, ajustar el diseÃ±o antes de las tareas 3.3, 10.1, 11.3 y 11.6
    - No implementar las tareas 3.3, 10.1, 11.3 ni 11.6 hasta cerrar esta tarea
    - _Requirements: 9.3, 10.2, 10.5_

- [x] 2. Base del mÃ³dulo: errores, configuraciÃ³n, entidades y puertos
  - [x] 2.1 Agregar los cÃ³digos de error nuevos y su traducciÃ³n HTTP
    - En `shared/domain/errors.py` agregar a `ErrorCode`: `BROKER_NOT_FOUND`, `CONSENT_REQUIRED`, `LINK_ALREADY_EXISTS`, `INVALID_LINK_STATE`, `LINK_NOT_FOUND`, `PROPOSAL_NOT_FOUND`, `PROPOSAL_VERSION_CONFLICT`, `INVALID_PROPOSAL_STATE`, `TRADING_AUTHORIZATION_REQUIRED`, `RATING_NOT_ALLOWED`, `CLIENT_NOT_FOUND` y `CONFIRMATION_REQUIRED` si falta (segÃºn 1.1)
    - Registrar en `shared/infrastructure/http_errors.py` el estado HTTP de cada cÃ³digo segÃºn la tabla de Error Handling del diseÃ±o
    - _Requirements: 17.4, 18.3_

  - [x] 2.2 Agregar la configuraciÃ³n de `brokers` a `config/settings.py`
    - `BROKER_LINK_REQUEST_TTL_DAYS` (7, 1â€“90), `PROPOSAL_TTL_HOURS` (72, 1â€“720), `BROKER_LINK_CONSENT_VERSION` y `BROKER_TRADING_CONSENT_VERSION` (`"v1"`, 1â€“32 caracteres), `BROKERS_EXPIRY_INTERVAL_SECONDS` (300, 10â€“86400), `BROKERS_JOBS_ENABLED` (`true`)
    - Un valor fuera de rango falla el arranque con error de configuraciÃ³n explÃ­cito; reutilizar `ORDER_REFERENCE_COMMISSION_RATE` de `orders`
    - Documentar las variables en `.env.example`
    - _Requirements: 18.2_

  - [x] 2.3 Crear entidades, errores de dominio y puertos de `brokers`
    - `brokers/domain/entities.py`: `LinkStatus`, `LinkAction`, `Link`, `TradingAuthorization`, `ProposalStatus`, `ProposalAction`, `Proposal`, `ProposalVersion`, `ProposalDecision`, `ProposalMessage`, `BrokerProfile`, `Rating`, `Reputation`, `BrokerEvent`, `BrokerIdentity` como dataclasses `frozen=True`
    - `brokers/domain/errors.py`: errores de dominio de la tabla de Error Handling, subclases de `AppError`
    - `brokers/domain/ports.py`: Protocol de directorio, solicitud de Broker, Linked_Account, Order_Controls, TOTP, cotizaciÃ³n, `OrderCreationPort`, `OrderQueryPort`, notificador y repositorios; `ProposalOrderCommand`, `OrderCreated`, `OrderRejected`
    - Sin imports de FastAPI, SQLAlchemy ni SDKs en `domain/`
    - _Requirements: 16.5, 17.5_

- [x] 3. Reglas de dominio puras
  - [x] 3.1 Implementar `brokers/domain/link_state_machine.py`
    - `transition`, `is_terminal`, `is_open`, `effective_status(link, now, ttl_days)` y `actor_allowed(action, actor_role)` segÃºn B1, B23 y D6
    - _Requirements: 3.5, 3.6, 3.7, 3.8, 3.9, 4.1_

  - [x] 3.2 Escribir la prueba de propiedad de la tabla de transiciones de la Link
    - **Property 1: Tabla de transiciones de la Link**
    - **Validates: Requirements 3.5, 3.6, 3.7, 3.9, 4.1**
    - `tests/brokers/property/test_link_state_machine.py`, `@settings(max_examples=100)`

  - [x] 3.3 Implementar `brokers/domain/proposal_state_machine.py`
    - `transition` con la tabla de B8 (incluida `conversion_fail` desde `accepted` segÃºn lo decidido en 1.2), `check_version` y `effective_status(proposal, now, ttl_hours)`; el estado se comprueba antes que la versiÃ³n
    - _Requirements: 8.1, 8.3, 8.5, 9.2, 9.4_

  - [x] 3.4 Escribir la prueba de propiedad de la tabla de transiciones de la Proposal
    - **Property 7: Tabla de transiciones de la Proposal**
    - **Validates: Requirements 8.3, 8.5, 9.2**
    - `tests/brokers/property/test_proposal_state_machine.py`

  - [x] 3.5 Implementar `estimates.py`, `reputation.py`, `access.py` y `periods.py`
    - `estimates`: `reference_price`, `estimated_cost` (half-even, 2 decimales, `localcontext(prec=40)`), `requires_totp` con la comparaciÃ³n decidida en 1.2
    - `reputation`: `average` (None si vacÃ­a) y `upsert` por Link
    - `access`: `require_active_link` (404 con cÃ³digo del recurso) y `resolve_link_membership`
    - `periods`: `to_utc_range` en `America/New_York` e `InvalidPeriodError`; `link_overlaps` (B19)
    - _Requirements: 5.1, 7.5, 7.6, 9.3, 13.2, 14.2, 17.1, 17.2_

  - [x] 3.6 Escribir la prueba de propiedad del promedio de reputaciÃ³n
    - **Property 12: Promedio de reputaciÃ³n**
    - **Validates: Requirements 14.2**
    - `tests/brokers/property/test_reputation.py`

  - [x]* 3.7 Escribir pruebas unitarias de `estimates` y `periods`
    - FÃ³rmula del costo estimado, precio de referencia `market`/`limit`, `QuoteUnavailableError`, Period con `from > to` y solapamiento de Links
    - _Requirements: 5.1, 7.5, 7.6_

- [x] 4. Persistencia
  - [x] 4.1 Crear la migraciÃ³n de esquema de `brokers`
    - `migrations/versions/<nÃºmero de 1.1>_brokers_schema.py` con las tablas, CHECK, Ã­ndices Ãºnicos parciales (`ux_broker_links_open_investor`, `ux_trading_auth_active_link`), CHECK `(status = 'approved') = (order_id IS NOT NULL)`, triggers de inmutabilidad de versiones, decisiones, mensajes y `broker_events`, y RLS sin polÃ­ticas
    - Insertar preferencias por defecto de `broker_link_updates` y `proposal_updates` si `identity` guarda preferencias por fila (segÃºn 1.1)
    - `downgrade` en orden inverso; no modifica datos existentes de otros mÃ³dulos
    - _Requirements: 3.3, 6.5, 9.4, 11.2, 13.2, 17.5_

  - [x] 4.2 Implementar modelos y repositorios SQLAlchemy
    - `brokers/adapters/outbound/persistence/`: `models.py`, `link_repository.py`, `proposal_repository.py`, `rating_repository.py`, `profile_repository.py`, `event_repository.py`
    - `SELECT ... FOR UPDATE`, actualizaciones condicionales `WHERE status = :esperado`, `ON CONFLICT (link_id) DO UPDATE` para Ratings, paginaciÃ³n por cursor opaco base64
    - Traducir la violaciÃ³n de `ux_broker_links_open_investor` a `LinkAlreadyExistsError`
    - _Requirements: 3.3, 5.1, 5.2, 12.3, 13.2, 14.4, 17.5_

  - [x]* 4.3 Escribir pruebas `db` de la migraciÃ³n y los repositorios
    - `upgrade`/`downgrade`, Ã­ndices Ãºnicos parciales, CHECK de `broker_proposals`, triggers de inmutabilidad y filtros por Period; se saltan sin `TEST_DATABASE_URL`
    - _Requirements: 3.3, 6.5, 17.5_

- [x] 5. Adaptadores de salida y fakes en memoria
  - [x] 5.1 Implementar los adaptadores de `identity`
    - `brokers/adapters/outbound/identity/`: `broker_directory.py`, `linked_account_reader.py`, `controls_reader.py`, `totp_verifier.py`, `broker_request_reader.py` (solo lectura, D8)
    - _Requirements: 1.4, 2.1, 2.2, 5.5, 9.3_

  - [x] 5.2 Implementar `brokers/adapters/outbound/market_data/quote_reader.py`
    - Usa el caso de uso de cotizaciÃ³n existente y `InstrumentRepository.get(symbol)` (`active` y `tradable`)
    - _Requirements: 7.3, 7.4, 7.5_

  - [x] 5.3 Crear los fakes en memoria para las pruebas de propiedad
    - `tests/brokers/fakes.py`: repositorios que aplican las mismas restricciones Ãºnicas que la migraciÃ³n, `Clock` falso, TOTP falso, Order_Creation_Port con idempotencia por clave `proposal:{id}` y contador de llamadas, Order_Query_Port con contador, notificador que registra llamadas
    - Necesarios para las Properties 2 a 6 y 8 a 11
    - _Requirements: 10.3, 16.1_

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Directorio y perfil del comisionista
  - [x] 7.1 Implementar `brokers/application/directory_service.py`
    - `update_profile` con lÃ­mites del perfil, `get_profile` (404 `BROKER_NOT_FOUND`), `suggestions` y `search` paginada que excluyen al propio usuario
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4_

  - [x]* 7.2 Escribir pruebas unitarias del directorio
    - LÃ­mites del perfil, Broker sin rol vigente, exclusiÃ³n del solicitante y paginaciÃ³n
    - _Requirements: 1.1â€“1.4, 2.1â€“2.4_

- [x] 8. VinculaciÃ³n y Trading_Authorization
  - [x] 8.1 Implementar en `brokers/application/link_service.py` la solicitud y la respuesta
    - `request_link` con el orden de comprobaciones del diseÃ±o y persistencia previa de la expiraciÃ³n vencida del Investor (D6); `accept`, `decline`, `cancel`, `pending_requests`, `current` (con `pending_broker_selection`, B5) y `history` filtrado por estado y Period
    - `BrokerEvent` por transiciÃ³n dentro de la transacciÃ³n; notificaciÃ³n despuÃ©s del commit
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.9, 3.10, 5.1, 5.2, 5.3, 5.4, 5.5, 17.5_

  - [x] 8.2 Escribir la prueba de propiedad de Link abierta Ãºnica por Investor
    - **Property 2: Como mÃ¡ximo una Link abierta por Investor**
    - **Validates: Requirements 3.3, 3.4, 3.8**
    - `tests/brokers/property/test_link_uniqueness.py` con `RuleBasedStateMachine`

  - [x] 8.3 Implementar en `link_service.py` el fin de la Link y la autorizaciÃ³n
    - `end_link` en una transacciÃ³n: Link â†’ `ended`, revocaciÃ³n con `link_ended` solo si hay Trading_Authorization vigente (sin vigente termina sin error), Proposals `sent`/`accepted` â†’ `withdrawn(link_ended)`, un evento por entidad; si la revocaciÃ³n falla se revierte todo y la Link queda sin cambios; `CONFIRMATION_REQUIRED` sin `confirmed`
    - `grant_trading` idempotente con consentimiento, `revoke_trading` (409 `INVALID_LINK_STATE` con `no_active_authorization`), `set_order_review` con evento
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 8.4 Escribir la prueba de propiedad de la cascada del fin de la Link
    - **Property 3: Cascada del fin de la Link**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7**
    - `tests/brokers/property/test_link_end_cascade.py`

  - [x] 8.5 Escribir la prueba de propiedad de la Trading_Authorization
    - **Property 4: Trading_Authorization Ãºnica y ligada a la Active_Link**
    - **Validates: Requirements 6.3, 6.4, 6.5**
    - `tests/brokers/property/test_trading_authorization.py`

  - [x]* 8.6 Escribir pruebas unitarias de historial y vinculaciÃ³n vigente
    - Filtros por estado y Period, `pending_broker_selection`, consentimiento ausente y `order_review_enabled`
    - _Requirements: 3.1, 3.2, 3.10, 5.1â€“5.5, 6.1, 6.2, 6.6_

- [x] 9. Broker_Link_Adapter
  - [x] 9.1 Implementar `brokers/adapters/outbound/broker_link_adapter.py`
    - `is_linked`, `linked_investors` y `reviewing_broker` con una consulta por llamada, join con `role_assignments` en `ACTIVE` y sin cachÃ©; implementa `BrokerLinkPort` de `orders` y `BrokerClientPort` de `portfolio`
    - _Requirements: 15.4, 16.1, 16.2_

  - [x] 9.2 Escribir la prueba de propiedad de pertenencia
    - **Property 5: Pertenencia del Broker_Link_Adapter**
    - **Validates: Requirements 16.1, 16.2, 15.4**
    - `tests/brokers/property/test_link_membership.py` contra `access.resolve_link_membership` y un adaptador en memoria con la misma regla

  - [x]* 9.3 Escribir la prueba `db` del adaptador SQL contra el modelo
    - _Requirements: 16.1, 16.2_

- [x] 10. Cambios aditivos en `orders`
  - [x] 10.1 Implementar `create_from_proposal` y publicar los puertos de `orders`
    - Requiere 1.2 cerrada (D1)
    - `orders/application/proposal_orders.py`: `OrderRequest` con `simple`, `day`, `schedule_if_closed = true`, `confirmed = true`, clave `proposal:{proposal_id}` del Investor; mismas validaciones que `POST /orders` sin autorizaciÃ³n adicional; estado inicial `BROKER_SIGNED` con evento `actor_type = 'broker'` y `reason = proposal:{id}`; envÃ­o o programaciÃ³n segÃºn el mercado; repeticiÃ³n devuelve la misma Order
    - Resultados `OrderCreated` / `OrderRejected(code)` y propagaciÃ³n de excepciones de indisponibilidad (D2)
    - Admitir `BROKER_SIGNED` como estado inicial solo para este caso de uso en la mÃ¡quina de estados de `orders`
    - `orders.register` publica `app.state.order_proposal_creation` y `app.state.order_query_port` (`list_for_investor`, `find_by_idempotency_key`)
    - Implementar `brokers/adapters/outbound/orders/order_creation.py` y `order_query.py` sobre esos puertos
    - Sin endpoints HTTP nuevos en `orders`
    - _Requirements: 10.2, 10.3, 10.5, 10.6, 15.2, 16.5_

  - [x]* 10.2 Escribir pruebas unitarias de `create_from_proposal`
    - Idempotencia por clave, rechazo de negocio sin persistir, mercado cerrado y atribuciÃ³n al Broker
    - _Requirements: 16.5_

- [x] 11. Propuestas y mensajes
  - [x] 11.1 Implementar en `brokers/application/proposal_service.py` creaciÃ³n, modificaciÃ³n y retiro
    - `create` con Active_Link (404 `CLIENT_NOT_FOUND`), Linked_Account, sÃ­mbolo negociable, precio de referencia y costo estimado; Proposal `sent` + Version 1 + evento
    - `modify` (versiÃ³n nueva, anula la aceptaciÃ³n) y `withdraw` con motivo y `confirmed`; estado antes que versiÃ³n
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 11.2 Escribir la prueba de propiedad del control de versiÃ³n
    - **Property 8: Control de versiÃ³n de la Proposal**
    - **Validates: Requirements 8.1, 8.2, 8.4, 9.1, 9.4**
    - `tests/brokers/property/test_proposal_versions.py`

  - [x] 11.3 Implementar en `proposal_service.py` la decisiÃ³n del Investor
    - Requiere 1.2 cerrada (D4)
    - `investor_decide` (`accept`/`reject` con comentario): Linked_Account, estado, versiÃ³n y TOTP antes de abrir la transacciÃ³n si `requires_totp`; el cÃ³digo nunca se guarda ni se registra; notificaciÃ³n `proposal_updates` al Broker
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 18.4_

  - [x] 11.4 Escribir la prueba de propiedad del TOTP en la aceptaciÃ³n
    - **Property 9: TOTP en la aceptaciÃ³n**
    - **Validates: Requirements 9.3**
    - `tests/brokers/property/test_acceptance_totp.py`

  - [x] 11.5 Implementar `brokers/application/message_service.py`
    - `post` (1 a 1000 caracteres, inmutable) y `thread` paginado por cursor; notificaciÃ³n a la otra parte
    - _Requirements: 11.1, 11.2, 11.3_

  - [x] 11.6 Implementar en `proposal_service.py` la decisiÃ³n del Broker y la conversiÃ³n
    - Requiere 1.2 cerrada (D1 y `accepted` â†’ `conversion_failed`)
    - `broker_decide`: orden de comprobaciones del diseÃ±o, evidencia del hilo, Trading_Authorization vigente; llamada a `OrderCreationPort` fuera del bloqueo y segunda transacciÃ³n con relectura `FOR UPDATE`; `approved` con `order_id`, `conversion_failed` con `failure_code`, Proposal en `accepted` ante indisponibilidad, `orphan_order` en el evento si cambiÃ³ el estado; repeticiÃ³n sobre `approved` devuelve la misma Order; `decline` con evidencia
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8_

  - [x] 11.7 Escribir la prueba de propiedad de la conversiÃ³n exactamente una vez
    - **Property 10: ConversiÃ³n en Order exactamente una vez**
    - **Validates: Requirements 10.2, 10.3, 10.4, 10.5, 10.6**
    - `tests/brokers/property/test_proposal_conversion.py`

  - [x] 11.8 Implementar en `proposal_service.py` historial y detalle
    - `history_investor`, `history_broker` (estado, Period, cursor) y `detail` con versiones, decisiones y `order_id`; `effective_status` al leer sin escribir (D6)
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

  - [x]* 11.9 Escribir pruebas unitarias de propuestas y mensajes
    - ValidaciÃ³n de creaciÃ³n, `QUOTE_UNAVAILABLE`, evidencia ajena, `decline`, mensajes vacÃ­os o largos e historial
    - _Requirements: 7.1â€“7.6, 10.1, 10.7, 10.8, 11.1â€“11.3, 12.1â€“12.4_

- [x] 12. Calificaciones y portal de clientes
  - [x] 12.1 Implementar `brokers/application/rating_service.py`
    - `publish` con la Link mÃ¡s reciente `active` o `ended` (D5) y reemplazo por Link; `reputation` y `reviews` paginadas
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 14.1, 14.2, 14.3, 14.4_

  - [x] 12.2 Escribir la prueba de propiedad de Rating por Link
    - **Property 11: Una Rating por Link con reemplazo**
    - **Validates: Requirements 13.1, 13.2, 13.3, 14.3**
    - `tests/brokers/property/test_ratings.py`

  - [x] 12.3 Implementar `brokers/application/client_service.py`
    - `clients` (Active_Links del Broker) y `client_orders` con Active_Link (404 `CLIENT_NOT_FOUND`) sobre `OrderQueryPort.list_for_investor`
    - _Requirements: 15.1, 15.2, 15.3_

  - [x]* 12.4 Escribir pruebas unitarias de reputaciÃ³n, reseÃ±as y clientes
    - _Requirements: 14.1, 14.4, 15.1_

- [x] 13. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Notificaciones, Expiry_Job y cambios aditivos en `identity`
  - [x] 14.1 Implementar el notificador y los tipos de evento
    - Agregar `broker_link_updates` y `proposal_updates` a `EVENT_TYPES` de `identity/domain/preferences.py` con `in_app` por defecto
    - `brokers/adapters/outbound/notifications/brokers_notifier.py` sobre `RecipientDirectory` y `Notifier.notify`; un fallo se registra en log y no revierte
    - _Requirements: 18.1_

  - [x] 14.2 Implementar `ExpiryService` y el Expiry_Job
    - `brokers/application/expiry_service.py`: `run_once(now)` que en la misma ejecuciÃ³n expira Links `requested` y Proposals `sent` vencidas con actualizaciÃ³n condicional en lotes `FOR UPDATE SKIP LOCKED`, un evento y una notificaciÃ³n por transiciÃ³n de cada categorÃ­a; las Proposals `accepted` no expiran y solo reciben la reconciliaciÃ³n D3
    - `brokers/adapters/inbound/jobs/expiry_job.py`: tarea asyncio con `BROKERS_EXPIRY_INTERVAL_SECONDS`; una excepciÃ³n se registra y el ciclo siguiente reintenta
    - _Requirements: 3.8, 8.6, 18.6_

  - [x]* 14.3 Escribir pruebas unitarias del Expiry_Job y las notificaciones
    - Reloj falso, una notificaciÃ³n por transiciÃ³n, D3 con Order existente
    - _Requirements: 3.8, 8.6, 9.5, 11.1, 18.6_

  - [x] 14.4 Implementar `associated_broker` en `/users/me`
    - Protocol `AssociatedBrokerReader` en `identity/domain/`, resuelto desde `app.state.associated_broker_reader` (null si no existe); esquema `AssociatedBrokerOut` con `id`, `name`, `firm_name` y `since`
    - `brokers/adapters/outbound/identity/associated_broker_reader.py`
    - _Requirements: 16.4_

  - [x]* 14.5 Escribir prueba de API de `associated_broker`
    - _Requirements: 16.4_

- [x] 15. Endpoints HTTP
  - [x] 15.1 Crear los esquemas Pydantic
    - `brokers/adapters/inbound/http/schemas/`: request y response de la tabla de endpoints; decimales como cadenas; `page_size` 1â€“100 (defecto 20); reutilizar `OrderPage` y filtros de `orders`
    - _Requirements: 12.1, 12.4, 15.2, 18.5_

  - [x] 15.2 Implementar los routers de Investor y pÃºblicos
    - `directory_router.py`, `links_router.py`, `proposals_router.py` con `get_current_user` y `require_investor`; `responses={cÃ³digo: {"model": ErrorBody}}` por ruta
    - `GET /brokers/{broker_id}` es pÃºblico: sin `get_current_user`, sin 401, y la respuesta solo expone los campos pÃºblicos del perfil (Req. 1.5)
    - `GET /broker-links/current` responde 200 con campos de Link y Trading_Authorization en null cuando no hay Link abierta (Req. 5.6)
    - _Requirements: 1.3, 2.1â€“2.4, 3.1, 3.7, 4.1, 5.1, 5.5, 6.2â€“6.6, 9.1, 11.1, 12.1, 13.1, 14.1, 14.4, 17.4, 18.5_

  - [x] 15.3 Implementar los routers de Broker
    - `broker_links_router.py`, `broker_proposals_router.py`, `broker_clients_router.py` y `PUT /brokers/me/profile` con `require_broker` y prefijo `/broker/` (D7)
    - _Requirements: 1.1, 3.5, 3.6, 3.10, 7.1, 8.1, 8.3, 10.1, 11.1, 12.2, 15.1, 15.2, 17.4, 18.5_

  - [x] 15.4 Escribir la prueba de propiedad del control de acceso
    - **Property 6: Control de acceso de los endpoints**
    - **Validates: Requirements 15.2, 15.3, 17.1, 17.2, 17.3, 17.4**
    - `tests/brokers/property/test_access_control.py` con `TestClient` y fakes que cuentan llamadas

  - [x]* 15.5 Escribir pruebas de contrato OpenAPI y ausencia de secretos
    - Errores declarados por endpoint en `/openapi.json`; TOTP y `alpaca_account_id` ausentes de Error_Body, logs y eventos
    - _Requirements: 18.4, 18.5_

- [x] 16. Cableado
  - [x] 16.1 Implementar `brokers/composition.py` y registrarlo en `main.py`
    - `register`: routers, `BrokerLinkAdapter` en `app.state.order_broker_link` y `app.state.portfolio_broker_clients`, `app.state.associated_broker_reader`
    - `startup`: resolver `order_proposal_creation` y `order_query_port` (error de configuraciÃ³n si faltan) y arrancar el Expiry_Job si `BROKERS_JOBS_ENABLED`; `shutdown` lo detiene
    - Orden en `main.py` segÃºn el diseÃ±o, ajustado con lo verificado en 1.1
    - _Requirements: 16.1, 16.2, 16.3_

  - [x] 16.2 Escribir la prueba de humo del cableado
    - `tests/brokers/unit/test_composition.py`: el mismo objeto queda en `app.state.order_broker_link` y `app.state.portfolio_broker_clients`, y `orders` y `portfolio` lo usan despuÃ©s de `startup`
    - _Requirements: 16.3_

- [x] 17. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

### VerificaciÃ³n final â€” 2026-11-16

- Checklist completo: 73 de 73 entradas verificadas, incluidas las pruebas opcionales.
- `uv run ruff check .`: correcto.
- `uv run mypy src`: correcto, 345 archivos de cÃ³digo fuente.
- `uv run pytest` con `TEST_DATABASE_URL` del PostgreSQL desechable de `tests/db`:
  **648 passed**, sin pruebas omitidas. Incluye las 12 propiedades crÃ­ticas con
  100 ejemplos configurados, el humo de cableado y el flujo HTTP sobre PostgreSQL
  con la capa real de aplicaciÃ³n de `orders`.
- `uv run python -m compileall -q src`: correcto.
- `uv build`: distribuciÃ³n fuente y wheel construidos; el wheel contiene los
  50 archivos Python de MOD-06. Artefactos en `.cache/brokers-build/`.
- MigraciÃ³n `0009_brokers_schema` probada con upgrade/downgrade, RLS,
  restricciones Ãºnicas, CHECK e inmutabilidad; no se aplicÃ³ a una base compartida.

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


## Revision funcional de suscripciones y brokers (2026-11-16)

Trazabilidad: RF-10/RF-11, RF-13 y RFP-09, ademas de los flujos de propuestas,
autorizacion y ordenes de MOD-06. Se amplifica el directorio para permitir
GET /api/v1/brokers sin q, con paginacion; q presente conserva el rango 2..100.

- API sandbox reconstruida y healthy. Usuario del pago mensual existente:
  status active, is_premium true y periodo hasta 2026-12-16 17:45:25 Bogota.
- Lecturas HTTP autenticadas con su sesion existente y token de auditoria
  temporal en memoria: planes, suscripcion, pagos, watchlists, price-alerts,
  directorio, sugerencias, perfil/reputacion/resenas de ambos brokers,
  vinculos, propuestas y posiciones devolvieron 200. Directorio sin filtro:
  dos brokers, coincidentes con los dos roles broker vigentes de la base.
- El usuario no tiene vinculo abierto; no se eligio un broker por el. La
  operacion requiere solicitud, aceptacion y consentimiento para operar.
- Prueba de contrato nueva: las 33 operaciones HTTP de MOD-06 recorren estados
  exitosos con proveedores/repositorios en memoria. Incluye cancelacion y rechazo
  de solicitud, perfil, vinculo activo, autorizacion/revocacion, modificacion y
  retiro de propuesta, mensajes, aprobacion, orden simulada y calificacion.
- La prueba PostgreSQL existente verifico la vinculacion y la creacion real de
  una orden local BROKER_SIGNED mediante la aplicacion orders, con proveedores
  externos simulados. No se enviaron ordenes a Alpaca.
- Prueba HTTP de suscripcion: acceso Premium rechazado antes del pago, Checkout,
  webhook firmado, factura paid de 12 USD, activacion, creacion de watchlist y
  adicion de AAPL. Duplicados no repiten pagos/eventos y una suscripcion activa
  rechaza otro Checkout. Cancelar al fin de periodo conserva Premium.
- Suite general inicial: 647 passed; una prueba no inicio por permisos de la
  carpeta temporal de pytest. Se repitieron migraciones, brokers y wallet con
  directorio temporal nuevo: 162 passed, sin skips ni errores. Hay solapamiento
  entre ambas ejecuciones; la segunda incluye las tres pruebas nuevas.
- Ruff y mypy correctos (345 archivos). Advertencias de dependencias FastAPI y
  Alembic, sin fallos funcionales. Se uso una base PostgreSQL desechable separada
  para las pruebas; no se migraron ni alteraron las suscripciones del sandbox.

Limites: no se simulo otra compra en Checkout alojado ni se envio una orden a
proveedores. El pago sandbox existente ya habia sido confirmado en Stripe y
recuperado por su listener real. Esta revision comprueba backend, no interfaz
frontend. No se verificaron mutaciones de brokers sobre datos del usuario para
no asociarlo arbitrariamente ni disparar notificaciones externas.


## Correccion detectada en prueba sandbox de orden limit (2026-11-16)

RF-20 y validacion de ordenes MOD-03: PostgreSQL devuelve limit_price con escala
fija, por ejemplo 100.0000. Reconstruir el comando de orden conservando esos
ceros hacia que la validacion de dos decimales lo rechazara con VALIDATION_ERROR.
Se normalizan solo los precios reconstruidos desde propuestas/ordenes guardadas,
sin redondearlos ni relajar la validacion de nuevas entradas HTTP. La misma
correccion evita el rechazo al revalidar una orden programada al abrir el mercado.
Se agregan casos de regresion y el flujo PostgreSQL se prueba con market y limit.


### Resultado de los dos recorridos en API sandbox (2026-11-16)

- Broker elegido: Broker Dos. Vinculo cb0aed62-405a-49fa-b931-b2c2d79dedb5
  solicitado por el usuario y aceptado por el broker: active. Revision de
  ordenes habilitada y autorizacion de trading otorgada por el usuario.
- Orden del usuario 60e743a7-146e-4de0-8171-de376fdf1825:
  PENDING -> IN_REVIEW -> BROKER_SIGNED. La bandeja del broker la mostro y
  la aprobacion registro a Broker Dos como actor y firmante.
- Propuesta del broker 6eac1e18-d2e4-4354-90ed-cfa93a400b76:
  sent -> accepted por el usuario -> approved por el broker. Creo la orden
  9dbe3d6d-4888-40c7-97d6-cf92f8105916 en BROKER_SIGNED. Repetir la
  aprobacion devolvio exactamente la misma orden, sin duplicados.
- Ambas pruebas fueron compras limitadas sandbox de 0.01 AAPL a USD 100 por
  accion, estimado USD 1.02 cada una con comision de referencia. Mercado cerrado:
  programacion para 2026-11-17 09:30 America/Bogota, sin envio a Alpaca.
- Tras comprobar las aprobaciones, ambas se cancelaron mediante la API:
  CANCELED, reservas released, filled_qty=0, cero ejecuciones y alpaca_order_id
  nulo. El vinculo permanece activo con la autorizacion y revision habilitadas.
- El primer intento de propuesta e178a0b5-cdec-4e3e-a8e9-eb6ef573845d se
  conserva como conversion_failed por el defecto de escala descrito arriba.
  No se altero su historial; la prueba exitosa uso una nueva propuesta.
- Evidencia contrastada en HTTP y PostgreSQL: decisiones accept/approve,
  eventos con actor correcto, ordenes, reservas liberadas y ausencia de fills.
- Validacion de la correccion: 114 pruebas aprobadas de orders, conversion de
  propuestas y recorridos PostgreSQL market/limit; Ruff y mypy correctos.
  Base desechable retirada y scripts de auditoria temporales eliminados.

Limite: esta prueba confirma el flujo de aprobacion y programacion; no acredita
la ejecucion bursatil ni el llenado en Alpaca, porque el mercado estaba cerrado.
