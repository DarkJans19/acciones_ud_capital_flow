# Implementation Plan: admin-mod-07

## Overview

Implementación incremental de MOD-07 como el paquete `src/acciones_ud/admin/` en Python 3.12 con arquitectura hexagonal, más los cambios aditivos en `shared`, `identity`, `market_data`, `orders`, `portfolio` y `brokers` descritos en el diseño. El plan conserva la intención de los tres sprints iniciales y aplica el reordenamiento de la decisión G27:

- **Sprint 1 — Base, auditoría de escritura y matriz de parametrización:** verificación previa, permisos, Step_Up, protección contra escalamiento, Audit_Log ampliado, matriz versionada, cálculo de comisión y cotización.
- **Sprint 2 — Registros append-only, triggers, horarios y control de negociación:** triggers de inmutabilidad, vista unificada de auditoría, auditoría y propagación de cambios de horario, interruptores de negociación, integración de términos y Trading_Gate en `orders`, comisión oficial en `portfolio` y consultas de comisiones.
- **Sprint 3 — Cumplimiento y tableros con RBAC estricto:** restricciones de cuenta, operaciones atípicas, reportes de auditoría, indicadores con caché, prueba de control de acceso de todo el módulo y cierre.

Implementación autorizada. La revisión vigente está en
[implementation-decisions.md](implementation-decisions.md); H1, H3 y H7 se
incorporan antes del código. El estado de cada tarea se registra al verificarla.

Política de pruebas adoptada para esta implementación: son obligatorias las Properties 1 a 18, las pruebas PostgreSQL de evidencia y migraciones, el humo del cableado y la regresión. Las pruebas de ejemplo opcionales conservan `*`.

Validación integrada por bloques y al cierre: `uv run ruff check .`, `uv run mypy src` y `uv run pytest`. Las migraciones se prueban solo en PostgreSQL desechable.

## Tasks

### Sprint 1 — Base, auditoría de escritura y matriz de parametrización

- [x] 1. Verificación previa y aprobación de decisiones
  - [x] 1.1 Verificar los supuestos de código del diseño y fijar la numeración de migraciones
    - Objetivo: confirmar que el diseño sigue siendo válido contra el código actual antes de escribir nada.
    - Listar `migrations/versions/` y fijar los números de `0010_admin_fees_audit`, `0011_admin_audit_trail_halts` y `0012_admin_compliance_bi` y su `down_revision`; si `0009_brokers_schema` no es la última, actualizar los nombres en `design.md`.
    - Confirmar que `orders.register` construye su contexto en `register` y captura adaptadores (`orders/composition.py`), que `portfolio` resuelve `app.state.portfolio_commission_port` en cada llamada (`InstalledCommission`) y que `brokers.estimates.estimated_cost` usa `ORDER_REFERENCE_COMMISSION_RATE`.
    - Confirmar que `create_from_proposal` propaga los `AppError` con estado 500 o superior y convierte los menores en `OrderRejected` (`orders/application/proposal_orders.py`).
    - Confirmar que `ScheduleChangeService.apply` es idempotente por `change_id` y que `orders.exchange` coincide con `markets.code` en datos reales de sandbox.
    - Confirmar que `tests/migrations/test_offline_schema.py` y `test_migration_smoke.py` cubrirán las migraciones nuevas sin ajustes, o anotar el ajuste necesario.
    - Si un supuesto no se cumple y no tiene ajuste aditivo, detener el plan y reportarlo.
    - Depende de: —
    - Criterio de finalización: hallazgos anotados en la sección "Verificación de dependencias" de `design.md`; ningún supuesto bloqueante abierto.
    - _Requirements: 20.1, 20.6_

  - [x] 1.2 Registrar H1/H3/H7 y concretar o diferir las demás propuestas
    - Objetivo: cerrar las decisiones de `requirements.md` que cambian el comportamiento antes de implementarlas.
    - Presentar al equipo la tabla de decisiones H; registrar el resultado de cada una en `requirements.md` y, si cambia el diseño, en `design.md`.
    - Bloqueos: H2 bloquea 4.2; H3 bloquea 13.2 a 13.4; H4 bloquea 6.1; H5 bloquea 5.1; H7 bloquea 18.x y 19.x; H8 bloquea 21.x; H11 bloquea 15.3; H13 bloquea 11.3.
    - Depende de: 1.1
    - Criterio de finalización: cada decisión H marcada como aprobada, rechazada (con el ajuste aplicado a los documentos) o diferida con su efecto sobre el plan.
    - _Requirements: 1.2, 2.3, 3.1, 9.3, 14.8, 15.2, 17.4, 19.6_

- [x] 2. Base del módulo: errores, configuración y paquete
  - [x] 2.1 Agregar los códigos de error nuevos y su traducción HTTP
    - Componentes: `shared/domain/errors.py` (`FEE_VERSION_CONFLICT`, `FEE_VERSION_NOT_CANCELABLE`, `TRADING_HALT_OVERLAP`, `TRADING_HALT_NOT_RELEASABLE`, `TRADING_HALTED`, `ACCOUNT_TRADING_RESTRICTED`, `RESTRICTION_ALREADY_ACTIVE`, `RESTRICTION_NOT_ACTIVE`, `PROTECTED_PERMISSION`) y `shared/infrastructure/http_errors.py` (estados de la tabla Error Handling).
    - Depende de: 1.1
    - Criterio de finalización: cada código tiene su estado HTTP; las pruebas existentes de `http_errors` pasan.
    - _Requirements: 21.2, 21.3_

  - [x] 2.2 Agregar la configuración del módulo
    - Componentes: `config/settings.py` (trece variables `ADMIN_*` con sus defectos), validación en `require_api_settings` con los rangos del diseño, `.env.example`.
    - Depende de: 1.1
    - Criterio de finalización: un valor fuera de rango hace fallar `require_api_settings` con el nombre de la variable y sin su valor.
    - _Requirements: 15.5, 21.1, 21.8_

  - [x]* 2.3 Escribir pruebas unitarias de la configuración
    - Defectos, límites y mensaje sin valores.
    - Depende de: 2.2
    - _Requirements: 21.1_

  - [x] 2.4 Crear entidades, errores de dominio y puertos de `admin`
    - Componentes: `admin/domain/` (`ports.py` con los Protocol del diseño, dataclasses de Data Models, `errors.py` como subclases de `AppError`), `admin/application/dtos.py`.
    - Sin imports de FastAPI, SQLAlchemy ni de otros paquetes de negocio en `domain/` y `application/`.
    - Depende de: 2.1
    - Criterio de finalización: `mypy` estricto sin errores; una prueba de importación verifica que `admin.domain` no importa infraestructura.
    - _Requirements: 20.1_

  - [x] 2.5 Implementar `periods.py` y `pagination.py`
    - Componentes: `admin/domain/periods.py` (G29, máximo 366 días, `America/New_York`), `admin/domain/pagination.py` (cursor opaco).
    - Depende de: 2.4
    - Criterio de finalización: `from > to`, rango mayor de 366 días y cursor inválido producen `VALIDATION_ERROR` con el campo.
    - _Requirements: 5.5, 12.3, 15.4, 16.6, 17.10, 21.6_

  - [x]* 2.6 Escribir pruebas unitarias de `periods` y `pagination`
    - Límites del Period, cambio de horario de verano en los extremos y cursores manipulados.
    - Depende de: 2.5
    - _Requirements: 12.3, 21.6_

- [x] 3. Registro central de auditoría (escritura)
  - [x] 3.1 Implementar el constructor compartido de Audit_Entries y los metadatos de la solicitud
    - Componentes: `shared/domain/audit_entry.py` (`AuditRecord`, `build_record` con lista blanca exacta) y `shared/infrastructure/request_meta.py` (`request.client.host` y `request_id` de `RequestIdMiddleware`).
    - `identity/domain/audit.py` no cambia (D12).
    - Depende de: 2.4
    - Criterio de finalización: `build_record` rechaza claves faltantes o sobrantes; `request_meta` devuelve IP y `request_id` en una prueba con `TestClient`.
    - _Requirements: 10.1, 10.4_

  - [x] 3.2 Implementar `admin/domain/audit.py`
    - Acciones de `admin` del Req. 10.1 y sus listas blancas; `SENSITIVE_KEYS` y `sanitize` recursivo e insensible a mayúsculas.
    - Depende de: 3.1
    - Criterio de finalización: cada acción del Req. 10.1 tiene lista blanca; `sanitize` elimina claves sensibles anidadas en listas y objetos.
    - _Requirements: 10.1, 10.4, 10.5, 12.5_

  - [x] 3.3 Escribir la parte de auditoría de la migración `0010`
    - `admin_audit_log`: columnas `ip_address` y `request_id` con sus CHECK, ampliación de `ck_admin_audit_action` (`fee_version_created`, `fee_version_canceled`) y de `ck_admin_audit_target_type` (`fee_version`), trigger `BEFORE TRUNCATE`; `downgrade` inverso.
    - `identity/adapters/outbound/persistence/tables.py`: columnas nuevas en la definición de `admin_audit_log`.
    - Depende de: 1.1
    - Criterio de finalización: `upgrade` y `downgrade` pasan en la base desechable; las pruebas de `identity` del Audit_Log siguen pasando.
    - _Requirements: 10.1, 10.6, 11.1_

  - [x] 3.4 Implementar la unidad de trabajo de `admin` y `AuditWriter`
    - Componentes: `admin/adapters/outbound/persistence/tables.py`, `unit_of_work.py`, `audit_writer.py` (solo `append`; sin métodos de actualización ni borrado).
    - Depende de: 3.1, 3.3
    - Criterio de finalización: `AuditWriter.append` escribe todas las columnas en la sesión de la unidad de trabajo; no existe otro método público.
    - _Requirements: 10.1, 10.2, 11.3_

  - [x] 3.5 Escribir la prueba de propiedad de la lista blanca y la ausencia de secretos
    - **Property 9: Lista blanca y ausencia de secretos en Audit_Entries**
    - **Validates: Requirements 10.4, 10.5, 19.7**
    - `tests/admin/property/test_audit_whitelist.py`; la parte de Step_Up se completa en 8.4.
    - Depende de: 3.2
    - _Requirements: 10.4, 10.5, 19.7_

  - [x] 3.6 Registrar en el log los rechazos 401 y 403 de `admin`
    - Manejador en los routers de `admin` que agrega `request_id`, ruta, método, código y usuario si existe; reutiliza la traducción de `http_errors.py`; no guarda Audit_Entry.
    - Depende de: 3.1
    - Criterio de finalización: una prueba captura el registro sin cookies, tokens ni cuerpo de la solicitud.
    - _Requirements: 10.7_

- [x] 4. Seguridad: permisos, Step_Up y protección contra escalamiento
  - [x] 4.1 Escribir la parte de permisos de la migración `0010`
    - Inserta siete permisos, auditor/analyst y sus concesiones cerradas de lectura (H1); `downgrade` los elimina.
    - Depende de: 3.3
    - Criterio de finalización: tras `upgrade`, `GET /admin/roles` muestra los permisos solo en `administrator`.
    - _Requirements: 19.1_

  - [x] 4.2 Implementar el Step_Up
    - Requiere 1.2 cerrada (H2).
    - Componentes: `admin/adapters/outbound/identity/totp_verifier.py` (mismo patrón que `orders` y `brokers`), `admin/application/step_up.py` con los tres errores del Req. 19.6.
    - Depende de: 2.4, 1.2
    - Criterio de finalización: código ausente, inválido y actor sin TOTP producen los códigos del Req. 19.6; el código no aparece en logs.
    - _Requirements: 19.6, 19.7_

  - [x] 4.3 Implementar la protección de permisos administrativos en `identity`
    - `identity/application/rbac_admin.py::change_permission`: rechazo con `PROTECTED_PERMISSION` antes de persistir; `routers/admin.py` declara el 409 en `add_permission` y `remove_permission`.
    - Depende de: 2.1
    - Criterio de finalización: las pruebas existentes de RBAC pasan; los dos casos protegidos responden 409 sin Audit_Entry.
    - _Requirements: 19.4, 19.5_

  - [x] 4.4 Escribir la prueba de propiedad de la protección de permisos
    - **Property 18: Protección de permisos administrativos**
    - **Validates: Requirements 19.4, 19.5**
    - `tests/identity/property/test_protected_permissions.py`
    - Depende de: 4.3
    - _Requirements: 19.4, 19.5_

  - [x] 4.5 Crear las dependencias HTTP de `admin`
    - `admin/adapters/inbound/http/deps.py`: alias `Annotated` por permiso con `require_permission`, `require_investor_or_broker` para la cotización y reutilización de `require_broker` e `require_investor`.
    - Depende de: 4.1
    - Criterio de finalización: cada alias responde 401 y 403 antes de validar parámetros en una ruta de prueba.
    - _Requirements: 4.5, 19.2, 19.3_

- [x] 5. Reglas puras de la matriz de comisiones
  - [x] 5.1 Implementar `admin/domain/fees.py`
    - Requiere 1.2 cerrada (H5).
    - `SEED_TERMS`, `validate_new_version`, `resolve_terms`, `version_status`, `matrix` y `can_cancel` según el diseño.
    - Depende de: 2.4, 1.2
    - Criterio de finalización: funciones puras tipadas; sin I/O.
    - _Requirements: 1.2, 1.3, 1.7, 1.8, 1.10, 1.11, 2.1, 2.2, 2.6_

  - [x] 5.2 Escribir la prueba de propiedad de la resolución de términos
    - **Property 1: Resolución total y no retroactiva de Commission_Terms**
    - **Validates: Requirements 1.7, 1.9, 2.1, 2.2, 2.5**
    - `tests/admin/property/test_fee_resolution.py`
    - Depende de: 5.1
    - _Requirements: 2.1, 2.2, 2.5_

  - [x] 5.3 Escribir la prueba de propiedad de la validación de Fee_Versions
    - **Property 2: Validación de una Fee_Version nueva**
    - **Validates: Requirements 1.2, 1.3**
    - `tests/admin/property/test_fee_validation.py`
    - Depende de: 5.1
    - _Requirements: 1.2, 1.3_

- [x] 6. Cálculo oficial de la comisión
  - [x] 6.1 Implementar `admin/domain/commissions.py`
    - Requiere 1.2 cerrada (H4).
    - `compute` y `terms_from` (sin herencia histórica, H3) con `localcontext(prec=40)` y `ROUND_HALF_EVEN`.
    - Depende de: 5.1, 1.2
    - Criterio de finalización: el ejemplo del diseño (10 × 187.35 al 2 %, 60/40) da 37.47, 22.48 y 14.99.
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.7_

  - [x] 6.2 Escribir la prueba de propiedad del cálculo y el reparto
    - **Property 4: Cálculo y reparto de la comisión**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.7**
    - `tests/admin/property/test_commission_calculation.py` con referencia en `Fraction`.
    - Depende de: 6.1
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.7_

- [x] 7. Persistencia de la matriz
  - [x] 7.1 Escribir la parte de Fee_Versions de la migración `0010`
    - `admin_fee_versions` con CHECK, índices únicos, semilla con `SEED_ID` y trigger guard; RLS; `downgrade` inverso.
    - Depende de: 4.1
    - Criterio de finalización: `upgrade`, `downgrade` y la prueba fuera de línea pasan.
    - _Requirements: 1.4, 1.9, 1.12, 11.2_

  - [x] 7.2 Implementar `FeeRepository` SQL
    - `admin/adapters/outbound/persistence/fee_repository.py`: lock asesor por Fee_Scope (D2), `latest_version_no`, `all_versions`, `page` por cursor, `get_for_update`, `insert` (violación de índice → `FeeVersionConflictError`) y `cancel` condicional (D3).
    - Depende de: 7.1, 3.4
    - Criterio de finalización: sin métodos de borrado; `cancel` devuelve false si el campo ya estaba fijado.
    - _Requirements: 1.4, 1.7, 1.11, 1.13_

  - [x] 7.3 Escribir pruebas `db` de la tabla y el trigger de Fee_Versions
    - Semilla presente; `DELETE` y `TRUNCATE` fallan; `UPDATE` de tasa falla; cancelar una versión futura pasa una vez y falla la segunda; cancelar una vigente falla.
    - Depende de: 7.2
    - Criterio de finalización: pruebas pasan contra la base desechable y se saltan sin `TEST_DATABASE_URL`.
    - _Requirements: 1.9, 1.12, 11.2_

- [x] 8. Caso de uso y endpoints de la matriz
  - [x] 8.1 Implementar `admin/application/fee_service.py`
    - `create` y `cancel` con Step_Up previo, transacción de la tabla de límites transaccionales y Audit_Entry; `matrix` y `history` con `fees.matrix` y `version_status`.
    - Depende de: 5.1, 7.2, 4.2, 3.2
    - Criterio de finalización: cada operación de escritura deja exactamente un Audit_Entry con `before`, `after`, IP y `request_id`.
    - _Requirements: 1.1, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.10, 1.11, 1.13, 10.1_

  - [x] 8.2 Escribir la prueba de propiedad de secuencias sobre la matriz
    - **Property 3: Secuencias de operaciones sobre la matriz**
    - **Validates: Requirements 1.1, 1.4, 1.5, 1.7, 1.8, 1.9, 1.13**
    - `tests/admin/property/test_fee_service.py` con `RuleBasedStateMachine` y repositorio en memoria con los mismos índices.
    - Depende de: 8.1
    - _Requirements: 1.1, 1.4, 1.5, 1.13_

  - [x] 8.3 Implementar `fees_router.py` y sus schemas
    - Cuatro rutas de la tabla de endpoints; decimales como cadenas; `effective_from` con zona horaria obligatoria; `error_responses` declarados; tag `admin-fees`.
    - Depende de: 8.1, 4.5
    - Criterio de finalización: `/openapi.json` muestra request, response y errores de cada ruta.
    - _Requirements: 1.1, 1.6, 1.10, 1.11, 21.4, 21.5_

  - [x] 8.4 Escribir la prueba de propiedad de atomicidad para la matriz
    - **Property 10: Atomicidad entre la operación y su Audit_Entry** (primera parte: `create` y `cancel` de Fee_Version)
    - **Validates: Requirements 10.1, 10.2, 10.3**
    - `tests/admin/property/test_audit_atomicity.py` con fallos inyectados; completar la Property 9 con el Step_Up.
    - Depende de: 8.1
    - _Requirements: 10.1, 10.2, 10.3, 19.7_

  - [x]* 8.5 Escribir pruebas de API de la matriz
    - Caminos felices y errores declarados, incluida la concurrencia con dos solicitudes simultáneas.
    - Depende de: 8.3
    - _Requirements: 1.1–1.13_

- [x] 9. Cotización de comisiones
  - [x] 9.1 Implementar `MarketCatalogPort` y `CommissionQuoteService`
    - `admin/adapters/outbound/market_data/market_catalog.py` (lectura con la unidad de trabajo de `market_data`), `admin/application/commission_quote_service.py`.
    - Depende de: 6.1, 7.2
    - Criterio de finalización: símbolo desconocido produce `SYMBOL_NOT_FOUND`; `binding` siempre false.
    - _Requirements: 4.1, 4.2, 4.4_

  - [x] 9.2 Implementar `GET /commissions/quote`
    - `admin/adapters/inbound/http/commissions_router.py` con `require_investor_or_broker`; tag `commissions`.
    - Depende de: 9.1, 4.5
    - Criterio de finalización: 403 para un usuario sin `investor` ni `broker`; 422 para cantidad o precio no positivos.
    - _Requirements: 4.1, 4.3, 4.5, 21.4_

- [x] 10. Cableado inicial y cierre del Sprint 1
  - [x] 10.1 Implementar `admin/composition.py` y registrarlo en `main.py`
    - `register`: routers de Sprint 1; `startup` y `shutdown` vacíos salvo validaciones; orden de `main.py` del diseño.
    - Depende de: 8.3, 9.2
    - Criterio de finalización: la aplicación arranca; `GET /health` responde; las rutas aparecen en `/openapi.json`.
    - _Requirements: 20.1_

  - [x] 10.2 Checkpoint del Sprint 1
    - Ejecutar `ruff`, `mypy` y la suite completa con la base desechable; revisar con el equipo antes de seguir.
    - Depende de: 10.1, 2.3*, 2.6*, 3.5, 3.6, 4.4, 5.2, 5.3, 6.2, 7.3, 8.2, 8.4
    - Criterio de finalización: suite verde; dudas registradas en los documentos.

### Sprint 2 — Registros append-only, triggers, horarios y control de negociación

- [x] 11. Auditoría y propagación de cambios de horario
  - [x] 11.1 Auditar los cambios de horario en `market_data`
    - `market_data/domain/schedule_audit.py` (acciones y listas blancas), `AuditActor` y `ScheduleAuditWriter` en `domain/ports.py`, repositorio en `adapters/outbound/persistence/` sobre `admin_audit_log`, `ScheduleAdminService` con lectura del valor anterior y Audit_Entry en la misma unidad de trabajo.
    - Migración `0011`: ampliar CHECK de acción y objetivo para las acciones de horario.
    - Depende de: 3.1, 10.2
    - Criterio de finalización: cada operación de horario guarda un Audit_Entry con `before`, `after` y `effective_from`; las pruebas existentes de `market_data` pasan.
    - _Requirements: 7.1, 7.2, 10.1_

  - [x] 11.2 Pasar el actor y avisar al listener desde el router de `market_data`
    - `admin_markets.py`: construir `AuditActor` con `request_meta`, pasarlo al servicio y llamar `app.state.market_schedule_change_listener.changed(entry_id)` si existe; rutas, cuerpos y códigos de éxito sin cambios.
    - Depende de: 11.1
    - Criterio de finalización: sin listener instalado el comportamiento es el actual.
    - _Requirements: 6.4, 20.5, 20.6_

  - [x] 11.3 Implementar el Schedule_Change_Dispatcher y el tipo de evento
    - Requiere 1.2 cerrada (H13).
    - `admin/application/schedule_change_dispatcher.py` según D6; `dispatch_repository.py`; `admin/adapters/outbound/orders/schedule_change.py` (Schedule_Change_Port de `app.state`); `admin/adapters/outbound/market_data/notifier.py` (`RecipientDirectory.recipients` y `Notifier.notify`).
    - Migración `0011`: `admin_schedule_dispatches`; ampliación del CHECK de `notification_preferences` y preferencias por defecto para usuarios existentes; `identity/domain/preferences.py` agrega `market_schedule_changes`.
    - Depende de: 11.1, 1.2
    - Criterio de finalización: un cambio despachado dos veces no vuelve a llamar a `orders` ni a notificar.
    - _Requirements: 7.3, 7.4, 7.6, 7.7, 7.9_

  - [x] 11.4 Implementar el listener y el job de despacho
    - `admin/adapters/outbound/market_data/schedule_listener.py` (tarea asyncio registrada en `app.state.admin_dispatch_tasks`), `admin/adapters/inbound/jobs/schedule_dispatch_job.py` con `PeriodicJob`; `startup` y `shutdown` en `composition.py`.
    - Depende de: 11.3
    - Criterio de finalización: con `ADMIN_JOBS_ENABLED=false` el job no arranca y el despacho inmediato funciona; `shutdown` espera las tareas en curso.
    - _Requirements: 7.5, 21.8_

  - [x] 11.5 Escribir la prueba de propiedad del despacho idempotente
    - **Property 12: Despacho idempotente de cambios de horario**
    - **Validates: Requirements 7.3, 7.4, 7.6, 7.7**
    - `tests/admin/property/test_schedule_dispatch.py`; extender la Property 10 con los cambios de horario (Req. 7.1, 7.2).
    - Depende de: 11.4
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.6, 7.7_

  - [x] 11.6 Implementar la vista consolidada de mercados
    - `admin/application/market_admin_view.py`, `admin/adapters/inbound/http/markets_router.py` (`GET /admin/markets`, `GET /admin/markets/{market_code}`), tag `admin-markets`. Usa `fees.matrix` y, cuando exista 12.3, los Trading_Halts.
    - Depende de: 9.1, 12.3
    - Criterio de finalización: la zona horaria se devuelve y no hay ruta para modificarla.
    - _Requirements: 6.1, 6.2, 6.3, 6.5_

  - [x] 11.7 Implementar el historial de cambios de horario
    - `ScheduleChangeSource.history` y `GET /admin/markets/{market_code}/schedule-changes` con estado del despacho.
    - Depende de: 11.3, 11.6
    - Criterio de finalización: cada cambio muestra despacho, órdenes afectadas y usuarios notificados.
    - _Requirements: 7.8_

  - [ ]* 11.8 Escribir pruebas de API de horarios, vista y historial
    - Depende de: 11.7
    - _Requirements: 6.1–6.5, 7.8_

- [x] 12. Interruptores de negociación
  - [x] 12.1 Implementar `admin/domain/halts.py`
    - `effective_status`, `overlaps` y `gate` con la prioridad del diseño.
    - Depende de: 2.4
    - Criterio de finalización: funciones puras tipadas.
    - _Requirements: 8.2, 8.6, 9.1, 9.2_

  - [x] 12.2 Escribir la prueba de propiedad del estado y del Trading_Gate
    - **Property 6: Estado efectivo del Trading_Halt y decisión del Trading_Gate**
    - **Validates: Requirements 8.6, 9.1, 9.2**
    - `tests/admin/property/test_halts_gate.py`
    - Depende de: 12.1
    - _Requirements: 8.6, 9.1, 9.2_

  - [x] 12.3 Persistir los Trading_Halts
    - Migración `0011`: `admin_trading_halts` con CHECK, índice y trigger guard; ampliación de CHECK de acción y objetivo; `halt_repository.py` con lock asesor, `overlapping`, `release` condicional, `page` y `candidates`.
    - Depende de: 3.4, 11.1
    - Criterio de finalización: prueba `db` del trigger (borrado prohibido, liberación una sola vez).
    - _Requirements: 8.2, 8.10, 11.2_

  - [x] 12.4 Implementar `HaltService` y sus endpoints
    - `admin/application/halt_service.py` (Step_Up, transacción y Audit_Entry); `halts_router.py` con las rutas administrativas y `GET /trading-halts/active` sin motivo ni actores; tag `admin-halts`.
    - Depende de: 12.1, 12.3, 4.2
    - Criterio de finalización: la respuesta pública no contiene `reason`, `created_by` ni `released_by`.
    - _Requirements: 8.1, 8.3, 8.4, 8.5, 8.7, 8.8, 10.1_

  - [x] 12.5 Escribir la prueba de propiedad del no solapamiento
    - **Property 7: Trading_Halts sin solapamiento por alcance**
    - **Validates: Requirements 8.2, 8.4, 8.5, 8.10**
    - `tests/admin/property/test_halt_service.py`; extender la Property 10 con activación y liberación.
    - Depende de: 12.4
    - _Requirements: 8.2, 8.4, 8.5, 8.10, 10.1_

- [x] 13. Integración de términos y Trading_Gate en `orders`
  - [x] 13.1 Verificar las tablas que recibirán triggers de inmutabilidad
    - Buscar en `src/` y `tests/` cualquier `UPDATE`, `DELETE`, `TRUNCATE`, `save` o `delete` sobre `order_events`, `order_executions`, `auth_events` y `broker_events`, incluidas limpiezas de pruebas.
    - Depende de: 10.2
    - Criterio de finalización: resultado anotado en `design.md`; si hay un uso, detener 16.1 y proponer el ajuste.
    - _Requirements: 11.1, 11.5_

  - [x] 13.2 Agregar los términos de comisión a las órdenes
    - Requiere 1.2 cerrada (H3).
    - Migración `0011`: columnas de `orders` con FK y CHECK; `orders/domain/model.py::Order` con los tres campos opcionales al final; `orders/adapters/outbound/persistence/tables.py` con `Numeric(6, 4)` y `Numeric(5, 2)`.
    - Depende de: 7.1, 1.2
    - Criterio de finalización: las pruebas existentes de `orders` pasan; las órdenes previas tienen NULL.
    - _Requirements: 2.3, 2.6_

  - [x] 13.3 Usar Commission_Terms_Port en `orders`
    - `orders/domain/ports.py` (`CommissionTermsPort`), `ReferenceCommissionTerms` por defecto, `InstalledCommissionTerms` en `composition.py`; `prepare(at, terms)`; `_create` con `now` único (D8) y términos guardados; `preview` y `get` con términos.
    - Depende de: 13.2
    - Criterio de finalización: sin `admin` instalado, la vista previa, el `estimated_amount` y la Reservation son iguales a los actuales.
    - _Requirements: 2.3, 2.4, 2.5, 2.7, 2.8, 20.6_

  - [x] 13.4 Implementar el adaptador de términos en `admin`
    - `admin/adapters/outbound/orders/commission_terms_adapter.py`: carga las Fee_Versions y aplica `fees.resolve_terms`; error de base de datos clasificado como `DATABASE_UNAVAILABLE`.
    - Depende de: 13.3, 7.2
    - Criterio de finalización: una orden creada con `admin` instalado guarda la Fee_Version vigente del mercado o de `default`.
    - _Requirements: 2.1, 2.2, 2.3, 2.7_

  - [x] 13.5 Usar Trading_Gate_Port en `orders`
    - `orders/domain/ports.py` (`TradingGatePort`, `GateDecision`), `AllowAllGate`, `InstalledTradingGate`; evaluación en `prepare` con 503 `TRADING_HALTED` y 403 `ACCOUNT_TRADING_RESTRICTED`; errores declarados en los routers de `orders`.
    - Depende de: 13.3
    - Criterio de finalización: con `AllowAllGate` la suite de `orders` pasa sin cambios.
    - _Requirements: 9.1, 9.2, 9.7, 20.4, 20.6_

  - [x] 13.6 Diferir el envío de órdenes bloqueadas
    - `OrderSubmitter._defer` según el diseño; `MarketSessionAdapter.current_window`; Order_Event sin cambio de estado con la causa y notificación única `order_updates`.
    - Depende de: 13.5
    - Criterio de finalización: una orden programada bajo un Trading_Halt no se envía, queda en el mismo estado y se envía en el primer ciclo tras la liberación.
    - _Requirements: 9.3, 9.4, 9.5_

  - [x] 13.7 Implementar el adaptador del Trading_Gate en `admin`
    - `admin/adapters/outbound/persistence/gate_reader.py` (una consulta indexada de halts y restricción activa; la restricción devuelve "ninguna" hasta 18.1) y `admin/adapters/outbound/orders/trading_gate_adapter.py` con `halts.gate`.
    - Depende de: 13.5, 12.3
    - Criterio de finalización: una activación afecta a la siguiente evaluación sin caché.
    - _Requirements: 8.9, 9.1, 9.2_

  - [x] 13.8 Escribir la prueba de propiedad del bloqueo de órdenes
    - **Property 8: Bloqueo de órdenes sin llamadas a Alpaca**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.5, 9.6, 9.7, 20.6**
    - `tests/orders/property/test_trading_gate.py` con los fakes de `orders`; incluye la regresión de `create_from_proposal` (503 se propaga, 403 da `OrderRejected`) y comprueba que la reconciliación de órdenes enviadas, las lecturas de mercado y las transferencias de `wallet` no consultan el Trading_Gate.
    - Depende de: 13.6, 13.7
    - _Requirements: 9.1, 9.2, 9.3, 9.5, 9.6, 9.7, 9.8, 20.6_

- [x] 14. Comisión oficial en `portfolio` y consulta de plataforma en `orders`
  - [x] 14.1 Extender el ledger de `orders` y conectar la comisión oficial
    - `LedgerExecution` con términos; `ExecutionLedger.list_platform_page`, `iterate_platform` y `volume` con la misma atribución de firma; `portfolio/domain/model.py::ExecutionRecord` y `execution_reader.py` con los términos; `admin/adapters/outbound/portfolio/official_commission.py` (`source = "official"`) y `admin/adapters/outbound/orders/platform_ledger.py`.
    - Depende de: 13.2, 6.1
    - Criterio de finalización: las pruebas de `portfolio` pasan con el adaptador de referencia; con `admin` instalado `commission_source` es `official`.
    - _Requirements: 3.6, 20.2_

  - [x] 14.2 Escribir la prueba de propiedad de reproducibilidad
    - **Property 5: Reproducibilidad de la comisión de una Execution**
    - **Validates: Requirements 2.5, 2.6, 3.6, 5.6**
    - `tests/admin/property/test_commission_reproducibility.py`; la parte del agregado de KPIs se completa en 21.2.
    - Depende de: 14.1
    - _Requirements: 2.5, 2.6, 3.6, 5.6_

  - [x] 14.3 Implementar `CommissionQueryService`
    - `for_investor` (ledger por usuario), `for_broker` (firmadas por el Broker y filtradas con `BrokerLinkPort.linked_investors`) y `for_admin` (ledger de plataforma con totales por mercado y Broker).
    - Depende de: 14.1, 2.5
    - Criterio de finalización: totales iguales a la suma de los elementos de todas las páginas.
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.6_

  - [x] 14.4 Implementar el lector de vinculaciones
    - `admin/adapters/outbound/brokers/link_reader.py` sobre `app.state.order_broker_link`; error de configuración en `startup` si falta.
    - Depende de: 10.1
    - Criterio de finalización: prueba de humo con el adaptador de `brokers` instalado.
    - _Requirements: 5.2, 5.3_

  - [x] 14.5 Usar los términos vigentes en el costo estimado de `brokers`
    - `brokers/domain/ports.py` (`CommissionTermsBySymbolPort`), adaptador por defecto, resolución desde `app.state.brokers_commission_terms`; `estimates.estimated_cost` con tasa en porcentaje; `admin/adapters/outbound/brokers/proposal_terms_adapter.py`; 503 `TRADING_HALTED` declarado en la decisión del Broker.
    - Depende de: 13.4
    - Criterio de finalización: las Properties de `brokers` pasan con el adaptador por defecto.
    - _Requirements: 9.6, 20.3, 20.6_

- [x] 15. Endpoints de comisiones
  - [x] 15.1 Crear los schemas de comisiones
    - `CommissionPage`, `BrokerCommissionPage`, `AdminCommissionPage` con decimales como cadenas y totales.
    - Depende de: 14.3
    - _Requirements: 5.1, 5.2, 5.4, 21.5_

  - [x] 15.2 Implementar `GET /commissions`
    - Rol `investor`; filtro por símbolo; Period obligatorio.
    - Depende de: 15.1
    - _Requirements: 5.1, 5.5_

  - [x] 15.3 Implementar `GET /broker/commissions`
    - Requiere 1.2 cerrada (H11).
    - Rol `broker`; `investor_id` sin Active_Link responde 404 `CLIENT_NOT_FOUND`.
    - Depende de: 15.1, 14.4, 1.2
    - _Requirements: 5.2, 5.3, 5.5_

  - [x] 15.4 Implementar `GET /admin/commissions`
    - Permiso `admin:commissions`; filtros `broker_id`, `investor_id` y `market`.
    - Depende de: 15.1
    - _Requirements: 5.4, 5.5_

  - [x]* 15.5 Escribir pruebas de API de comisiones
    - Depende de: 15.2, 15.3, 15.4
    - _Requirements: 5.1–5.6_

- [x] 16. Inmutabilidad y rastro unificado de auditoría
  - [x] 16.1 Escribir la parte de inmutabilidad, índices y vista de la migración `0011`
    - Requiere 13.1 sin hallazgos bloqueantes.
    - Triggers de `order_events`, `order_executions` y `auth_events`; `BEFORE TRUNCATE` en `broker_events`; índices de auditoría; vista `audit_trail`; `downgrade` inverso.
    - Depende de: 13.1, 11.1
    - Criterio de finalización: prueba `db` de triggers del Req. 11.1 y regresión completa de `orders`, `identity`, `brokers` y `portfolio` en verde.
    - _Requirements: 11.1, 11.5, 21.7_

  - [x] 16.2 Implementar `AuditTrailReader`
    - `admin/adapters/outbound/persistence/audit_trail_reader.py` sobre la vista con keyset y filtros; lector en memoria para pruebas con la misma regla.
    - Depende de: 16.1, 2.5
    - _Requirements: 12.1, 12.2, 12.4_

  - [x] 16.3 Escribir la prueba de propiedad del rastro unificado
    - **Property 11: Selección y paginación del rastro de auditoría**
    - **Validates: Requirements 12.1, 12.2, 12.4, 12.5**
    - `tests/admin/property/test_audit_trail.py` y la prueba `db` de la vista contra el mismo modelo.
    - Depende de: 16.2
    - _Requirements: 12.1, 12.2, 12.4, 12.5_

  - [x] 16.4 Implementar `AuditTrailService` y `GET /admin/audit-trail`
    - `sanitize` de detalles, validación del Period y de `source`, descripción de garantía G17 en OpenAPI; tag `admin-audit`.
    - Depende de: 16.2, 3.2
    - _Requirements: 11.4, 12.1, 12.3, 12.5, 12.6_

  - [x] 16.5 Implementar la cadena de custodia
    - `AuditTrailReader.order_custody` y `GET /admin/audit-trail/orders/{order_id}` con Commission_Terms, firma, envío, cancelaciones y Executions.
    - Depende de: 16.4, 13.2
    - _Requirements: 13.1, 13.2, 13.3_

  - [ ]* 16.6 Escribir pruebas de API del rastro y de la cadena de custodia
    - Depende de: 16.5
    - _Requirements: 12.1–12.6, 13.1–13.3_

- [x] 17. Checkpoint del Sprint 2
  - Completar `register` de `admin` con los adaptadores de `app.state` y escribir la prueba de humo del cableado (los cinco adaptadores instalados y usados por `orders`, `portfolio`, `brokers` y `market_data` después de `startup`).
  - Ejecutar la suite completa con la base desechable, incluidas las pruebas `db` de triggers y vista.
  - Depende de: 11.5, 11.7, 12.2, 12.5, 13.8, 14.2, 14.5, 15.2, 15.3, 15.4, 16.3, 16.5
  - Criterio de finalización: suite verde; dudas registradas en los documentos.
  - _Requirements: 20.1, 20.6_

### Sprint 3 — Cumplimiento y tableros con RBAC estricto

- [x] 18. Restricciones de cuenta
  - [x] 18.1 Persistir las Account_Restrictions
    - Requiere 1.2 cerrada (H7).
    - Migración `0012`: `admin_account_restrictions` con CHECK, índice único parcial y trigger guard; ampliación de CHECK de acción; `restriction_repository.py`; `gate_reader.py` incluye la restricción activa.
    - Depende de: 17, 1.2
    - Criterio de finalización: prueba `db` del índice único y del trigger.
    - _Requirements: 11.2, 14.2_

  - [x] 18.2 Implementar `RestrictionService`
    - `restrict` y `lift` con Step_Up, validación de evidencia, usuario existente, autorrestricción prohibida y Audit_Entry; `page`.
    - Depende de: 18.1, 4.2
    - _Requirements: 14.1, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8, 14.9, 10.1_

  - [x] 18.3 Implementar los endpoints de restricciones
    - `compliance_router.py`: `POST /admin/compliance/restrictions`, `POST .../{id}/lift`, `GET /admin/compliance/restrictions`; tag `admin-compliance`.
    - Depende de: 18.2
    - _Requirements: 14.1, 14.4, 14.6, 21.4_

  - [x] 18.4 Escribir la prueba de propiedad de las restricciones
    - **Property 13: Restricciones de cuenta únicas**
    - **Validates: Requirements 9.2, 14.2, 14.3, 14.4, 14.5**
    - `tests/admin/property/test_restrictions.py`; extender la Property 10 con restringir y rehabilitar.
    - Depende de: 18.2
    - _Requirements: 9.2, 14.2, 14.3, 14.4, 14.5_

- [x] 19. Operaciones atípicas y reportes de auditoría
  - [x] 19.1 Implementar `admin/domain/atypical.py`
    - Requiere 1.2 cerrada (H7).
    - `flag` con ventana deslizante y razones; configuración desde `Settings`.
    - Depende de: 2.2, 1.2
    - _Requirements: 15.2, 15.3, 15.5_

  - [x] 19.2 Escribir la prueba de propiedad de la regla de operaciones atípicas
    - **Property 14: Regla de operaciones atípicas**
    - **Validates: Requirements 15.2, 15.3**
    - `tests/admin/property/test_atypical_rule.py`
    - Depende de: 19.1
    - _Requirements: 15.2, 15.3_

  - [x] 19.3 Implementar `admin/domain/reports.py`
    - `canonical_json`, `digest` y `build` con razones redondeadas y null con patrón cero.
    - Depende de: 2.4
    - _Requirements: 16.1, 16.2, 16.4_

  - [x] 19.4 Implementar la consulta de operaciones atípicas
    - `ComplianceService.atypical` (carga la ventana previa al Period con `iterate_platform`) y `GET /admin/compliance/atypical-operations`.
    - Depende de: 19.1, 14.1, 18.3
    - _Requirements: 15.1, 15.4_

  - [x] 19.5 Persistir y exponer los Compliance_Reports
    - Migración `0012`: `admin_compliance_reports` con trigger de inmutabilidad; `report_repository.py`; `generate_report`, `get_report`, `reports_for_user` con Audit_Entry; tres rutas del diseño.
    - Depende de: 19.3, 19.4, 16.2
    - Criterio de finalización: el resumen guardado coincide con el recalculado sobre el contenido devuelto.
    - _Requirements: 16.1, 16.3, 16.5, 16.6, 10.1, 11.1_

  - [x] 19.6 Escribir la prueba de propiedad del resumen canónico
    - **Property 15: Resumen canónico del Compliance_Report**
    - **Validates: Requirements 16.2, 16.4**
    - `tests/admin/property/test_report_digest.py`
    - Depende de: 19.3
    - _Requirements: 16.2, 16.4_

  - [x]* 19.7 Escribir pruebas de API de cumplimiento
    - Depende de: 19.5
    - _Requirements: 14.1–14.9, 15.1–15.5, 16.1–16.6_

- [x] 20. Fuentes de datos de los indicadores
  - [x] 20.1 Implementar `KpiSourcePort`
    - Requiere 1.2 cerrada (H8).
    - `kpi_identity_source.py` (`users`, `auth_events`, `role_assignments` vigentes en T), `kpi_wallet_source.py` (`subscription_payments`), `kpi_brokers_source.py` (`broker_links` iniciadas antes de T y no terminadas en T); solo lectura (G25).
    - Depende de: 17, 1.2
    - Criterio de finalización: cada consulta usa parámetros enlazados y no escribe.
    - _Requirements: 17.2, 17.3, 17.4, 17.7, 17.8, 17.9_

  - [x] 20.2 Agregar el volumen agregado al ledger de plataforma
    - `ExecutionLedger.volume(start, end)` por mercado y lado; `PlatformLedgerPort.volume`.
    - Depende de: 14.1
    - _Requirements: 17.5_

- [x] 21. Tablero de indicadores
  - [x] 21.1 Implementar `admin/domain/kpis.py`
    - `compute` con las definiciones `kpi-v1` y `KPI_DEFINITIONS_VERSION`.
    - Depende de: 6.1, 2.5
    - _Requirements: 17.2, 17.3, 17.4, 17.5, 17.6, 17.7, 17.8, 17.9, 17.11, 17.12_

  - [x] 21.2 Escribir la prueba de propiedad de los indicadores
    - **Property 16: Fórmulas y consistencia de los indicadores**
    - **Validates: Requirements 17.2, 17.3, 17.4, 17.5, 17.6, 17.7, 17.8, 17.9, 17.11, 17.12**
    - `tests/admin/property/test_kpis.py`; completar la Property 5 con el agregado de comisiones.
    - Depende de: 21.1
    - _Requirements: 17.2–17.12, 5.6_

  - [x] 21.3 Persistir los KPI_Snapshots
    - Migración `0012`: `admin_kpi_snapshots`; `kpi_snapshot_repository.py` con `INSERT ... ON CONFLICT DO UPDATE`.
    - Depende de: 18.1
    - _Requirements: 18.1, 18.4_

  - [x] 21.4 Implementar `KpiService`
    - Caché por TTL, `refresh`, respaldo `stale`, 503 sin respaldo y TTL 0; recorrido de Executions en lotes de 1000 (D9).
    - Depende de: 21.1, 21.3, 20.1, 20.2
    - _Requirements: 17.1, 18.1, 18.2, 18.3, 18.4, 18.5_

  - [x] 21.5 Implementar `GET /admin/kpis`
    - Permiso `admin:bi`; schema `KpiDashboardOut` con valor, unidad y definición por indicador; tag `admin-bi`.
    - Depende de: 21.4
    - _Requirements: 17.1, 17.10, 21.4_

  - [x]* 21.6 Escribir pruebas de la caché con reloj falso
    - Depende de: 21.4
    - _Requirements: 18.1–18.5_

- [x] 22. Control de acceso, contrato y documentación
  - [x] 22.1 Escribir la prueba de propiedad del control de acceso
    - **Property 17: Control de acceso de los endpoints**
    - **Validates: Requirements 4.5, 5.3, 19.2, 19.3, 19.6**
    - `tests/admin/property/test_access_control.py` con `TestClient` y fakes que cuentan escrituras y llamadas, sobre todas las rutas del módulo.
    - Depende de: 21.5, 19.5, 18.3, 16.5, 15.4, 12.4, 11.7, 8.3, 9.2
    - _Requirements: 4.5, 5.3, 19.2, 19.3, 19.6_

  - [x]* 22.2 Escribir pruebas de contrato OpenAPI
    - Cada ruta de `admin` declara request, response y errores; tags del Req. 21.4; descripción G17 en las rutas de auditoría.
    - Depende de: 22.1
    - _Requirements: 11.4, 21.4_

  - [x] 22.3 Documentar los cambios de contrato para el frontend
    - Agregar a `readme_cambios_frontend.md` las rutas nuevas, los errores nuevos de `orders` y `brokers`, el tipo de evento `market_schedule_changes` y la tabla de componentes de referencia del diseño, indicando que la gestión de accesos usa los endpoints existentes de `identity`.
    - Depende de: 22.1
    - Criterio de finalización: cada cambio visible del contrato tiene una entrada; `admin` no define rutas de roles, permisos, asignaciones ni directorio.
    - _Requirements: 19.8, 20.4, 21.4_

  - [ ]* 22.4 Ejecutar una prueba de carga con el volumen de referencia
    - Datos sintéticos del diseño en la base desechable; medir el percentil 95 de las consultas del Req. 21.7.
    - Depende de: 22.1
    - _Requirements: 21.7_

- [x] 23. Cierre
  - [x] 23.1 Ejecutar la regresión completa y la prueba de humo final
    - Suite completa con `TEST_DATABASE_URL`; humo del cableado; `uv build` opcional.
    - Depende de: 22.1, 22.3
    - _Requirements: 11.5, 20.1, 20.6_

  - [x] 23.2 Probar `upgrade` y `downgrade` de las tres migraciones
    - De `0009` a la última y de vuelta, más la prueba fuera de línea; sin aplicar a bases compartidas.
    - Depende de: 23.1
    - _Requirements: 11.1, 11.2_

  - [x] 23.3 Final checkpoint
    - Ejecutar `uv run ruff check .`, `uv run mypy src` y `uv run pytest`; registrar el resultado en este archivo; preguntar al equipo si quedan dudas.
    - Depende de: 23.2

## Notes

- Las tareas con `*` son opcionales. Las obligatorias de prueba son las Properties 1 a 18, las pruebas `db` de 7.3, 12.3, 16.1, 16.3, 18.1 y 23.2, la prueba de humo de 17 y la regresión de 23.1.
- Las tareas 4.2, 5.1, 6.1, 11.3, 13.2, 15.3, 18.1, 19.1 y 20.1 dependen de cerrar 1.2.
- La tarea 16.1 depende de que 13.1 no encuentre actualizaciones ni borrados sobre las tablas que reciben triggers.
- Cada prueba de propiedad lleva `# Feature: admin-mod-07, Property {n}: {texto}` y `@settings(max_examples=100)`.
- Las pruebas `db` se saltan sin `TEST_DATABASE_URL`.
- Las migraciones `0010`, `0011` y `0012` se escriben a lo largo de su sprint y solo se prueban en la base desechable hasta su checkpoint.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1", "2.2", "3.3"] },
    { "id": 2, "tasks": ["2.3", "2.4", "4.1", "4.3"] },
    { "id": 3, "tasks": ["2.5", "3.1", "4.2", "4.4", "4.5", "5.1", "7.1", "12.1"] },
    { "id": 4, "tasks": ["2.6", "3.2", "3.4", "3.6", "5.2", "5.3", "6.1", "12.2", "19.3"] },
    { "id": 5, "tasks": ["3.5", "6.2", "7.2", "19.6"] },
    { "id": 6, "tasks": ["7.3", "8.1", "9.1"] },
    { "id": 7, "tasks": ["8.2", "8.3", "8.4", "9.2"] },
    { "id": 8, "tasks": ["8.5", "10.1"] },
    { "id": 9, "tasks": ["10.2"] },
    { "id": 10, "tasks": ["11.1", "13.1", "14.4"] },
    { "id": 11, "tasks": ["11.2", "11.3", "12.3", "13.2"] },
    { "id": 12, "tasks": ["11.4", "12.4", "13.3", "16.1"] },
    { "id": 13, "tasks": ["11.5", "11.6", "12.5", "13.4", "13.5", "16.2"] },
    { "id": 14, "tasks": ["11.7", "13.6", "13.7", "14.1", "14.5", "16.3", "16.4"] },
    { "id": 15, "tasks": ["11.8", "13.8", "14.2", "14.3", "16.5"] },
    { "id": 16, "tasks": ["15.1", "16.6"] },
    { "id": 17, "tasks": ["15.2", "15.3", "15.4"] },
    { "id": 18, "tasks": ["15.5", "17"] },
    { "id": 19, "tasks": ["18.1", "19.1", "20.1", "20.2", "21.1"] },
    { "id": 20, "tasks": ["18.2", "19.2", "21.2", "21.3"] },
    { "id": 21, "tasks": ["18.3", "18.4", "21.4"] },
    { "id": 22, "tasks": ["19.4", "21.5", "21.6"] },
    { "id": 23, "tasks": ["19.5"] },
    { "id": 24, "tasks": ["19.7", "22.1"] },
    { "id": 25, "tasks": ["22.2", "22.3", "22.4"] },
    { "id": 26, "tasks": ["23.1"] },
    { "id": 27, "tasks": ["23.2"] },
    { "id": 28, "tasks": ["23.3"] }
  ]
}
```

## Evidencia de implementación y decisiones de cierre

- H1/H3/H7 se incorporaron antes del código en implementation-decisions.md y se
  reconciliaron con requirements/design. H2/H4/H5/H6/H8/H11/H13/H14 se adoptaron
  técnicamente; H9/H10/H12/H15 permanecen diferidas con efecto explícito.
- Arquitectura: puertos propios, dominio/aplicación sin FastAPI/SQLAlchemy/Pydantic,
  cinco adaptadores resueltos al usar y prueba de importación aislada.
- Se agrupan repositorios y lectores como documenta el diseño. No se crean
  paquetes vacíos para reproducir nombres de archivo del plan inicial.
- Properties 1–18: funciones puras con referencia, Fraction, máquinas de estados,
  matriz de accesos, errores, reversión atómica e idempotencia; 100 ejemplos.
- PostgreSQL 17 desechable en `.cache/mod07-postgres`, puerto local 55433:
  triggers UPDATE/DELETE/TRUNCATE, cambios únicos, restricciones, términos
  inmutables, históricos, vista/filtros/custodia, fuentes KPI, despacho real y
  concurrencia de tarifas e interruptores. No se usa Supabase compartido.
- Se actualizaron las limpiezas de fixtures para la evidencia ahora protegida.
  Las aserciones previas solo cambian donde H1 incorpora roles nuevos.
- El contrato de frontend se documenta en readme_cambios_frontend.md.
- Opcionales pendientes: 11.8 (matriz exhaustiva HTTP de horarios), 16.6 (matriz
  exhaustiva HTTP de custodia/auditoría) y 22.4 (carga con el volumen de referencia).
  Su lógica se verifica mediante propiedades, humo, API y PostgreSQL; no se
  declara verificado el objetivo p95 de RNF-01 sin esa prueba de carga.

### Validación final — 24 de noviembre de 2026

| Comprobación | Resultado |
| --- | --- |
| `uv run ruff check .` | Sin errores |
| `uv run mypy src` | Sin errores, 394 archivos |
| `uv run pytest -q --tb=short` con TEST_DATABASE_URL local | 715 passed, sin skips ni fallos, 301.81 s |
| Migraciones: suite de migrations y admin/unit/test_migrations.py | 12 passed, incluido downgrade tras concesiones adicionales a auditor |
| `git diff --check` | Sin errores |

Se utilizó caché de uv dentro del workspace y `--offline`, con las dependencias
instaladas. Las advertencias corresponden a deprecaciones de Starlette/httpx y
la configuración existente de Alembic. La prueba completa figura en
`.cache/mod07-final-tests.log`. El cierre no despliega ni aplica migraciones
a bases compartidas. El servidor PostgreSQL desechable se detiene al terminar.
