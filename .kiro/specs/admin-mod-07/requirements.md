# Requirements Document

> Revisión vigente: [decisiones de implementación](implementation-decisions.md).
> Incorpora H1, H3 y H7 autorizadas por el equipo y corrige los criterios
> históricos, permisos de lectura y reglas atípicas del borrador original.

## Introduction

Este spec cubre el módulo de desarrollo MOD-07 "Administración Central, Regulación y Parametrización" del backend de Acciones UD (responsable: Jan Henrik Sánchez Jerez). El módulo se implementa como el paquete `admin` dentro del monolito modular hexagonal (`src/acciones_ud/admin/`). Depende de MOD-01 (`identity`) y MOD-02 (`market_data`), especificados en `identity-market-backend`, y de MOD-03 (`orders`), MOD-04 (`wallet`), MOD-05 (`portfolio`) y MOD-06 (`brokers`), con sus specs `orders-mod-03`, `wallet-mod-04`, `portfolio-mod-05` y `brokers-mod-06`. Los seis paquetes existen en `src/acciones_ud/` y sus migraciones llegan hasta `0009_brokers_schema`. MOD-07 es el último módulo funcional del orden del catálogo (§7.3: MOD-01 → MOD-02 y MOD-04 → MOD-03 → MOD-05 → MOD-06 y MOD-07).

El control administrativo de este módulo está sujeto a las reglas de autenticación, autorización, integridad y auditoría del sistema. Ninguna operación administrativa omite esas reglas.

Alcance trazable (los textos originales están en `.kiro/steering/requerimientos-proyecto.md`, sección MOD-07):

- RF-46: matriz de comisiones y reparto por mercado con periodos de vigencia (Requisito 1).
- RF-43 y RF-46: términos de comisión aplicables a cada orden (Requisito 2), cálculo oficial y reparto (Requisito 3), cotización (Requisito 4) y consulta de comisiones generadas (Requisito 5).
- RF-46 y RF-27: vista consolidada de mercados y horarios (Requisito 6) y trazabilidad y propagación de cambios de horario con RFP-10 (Requisito 7).
- RF-46 (restricciones con vigencia): interruptores de negociación, el "circuit breaker" del alcance inicial (Requisito 8), y su efecto sobre las órdenes (Requisito 9).
- RF-44: registro central de auditoría administrativa (Requisito 10), inmutabilidad de las fuentes de auditoría (Requisito 11), consulta de eventos auditables (Requisito 12) y cadena de custodia de una orden (Requisito 13).
- RF-45: restringir y rehabilitar cuentas (Requisito 14) e identificar operaciones potencialmente atípicas (Requisito 15).
- RFP-13: reporte de auditoría de un usuario (Requisito 16), obligatorio por la Decisión R1.
- RF-47: tablero de indicadores del negocio (Requisito 17) y su caché (Requisito 18).
- RF-03 (participa): permisos administrativos del módulo y protección contra escalamiento de privilegios (Requisito 19).
- Contratos con los módulos existentes (Requisito 20) y requisitos transversales de errores, configuración, contrato OpenAPI y rendimiento (Requisito 21).

Fuera de alcance:

- Liquidación y pago de comisiones al comisionista (RFP-07, descartado por la Decisión R3).
- Cobro efectivo de comisiones en la cuenta Alpaca del usuario. Alpaca Broker API admite los campos `commission` y `commission_type` al crear una orden ([Create an Order for an Account](https://docs.alpaca.markets/us/reference/createorderforaccount)), pero este módulo no los usa (decisión G9).
- RFP-06 (descartado por la Decisión R2).
- Alta de mercados nuevos o de mercados fuera del catálogo de Alpaca (LSE, TSE, ASX), según el Marco de la especificación.
- Suspender mercados bursátiles reales, detener la negociación en la bolsa o controlar infraestructura de Alpaca (decisión G14).
- Activación automática de interruptores de negociación y de restricciones de cuenta (decisiones G14 y G20).
- Cancelación masiva de órdenes ya enviadas a Alpaca.
- Registro público de roles de supervisión: auditor y analyst se asignan exclusivamente mediante RBAC administrativo (H1).
- Modificar la zona horaria de un mercado (decisión G11, pendiente de aprobación H6).
- Exportación de reportes a PDF o CSV y envío de reportes por correo, Telegram o SMS.
- Series temporales y desgloses por sector en el tablero (decisión G23).
- Moderación de reseñas de comisionistas.
- La interfaz frontend (la desarrolla otro equipo; `product.md`). Los componentes `components/admin/*.tsx` de referencia no están en este repositorio; este spec solo define sus contratos HTTP.
- Logs centralizados (Splunk o ElasticSearch) y alarmas (tabla 25 del catálogo, atributo de calidad del SAD).

### Fuentes analizadas y limitaciones

- Steering: `product.md`, `structure.md`, `tech.md` y `requerimientos-proyecto.md`; además `AGENTS.md` y `constitution.md`.
- Specs previos: `identity-market-backend` (Requisitos 5, 15, 20 y 25; decisiones D3 y D11), `orders-mod-03` (O8, O14, O17, Requisitos 10, 13 y 14; "Contratos publicados para módulos futuros"), `portfolio-mod-05` (P5 y Commission_Port), `wallet-mod-04` (W6) y `brokers-mod-06` (B4, B10, B22, D2 y D8).
- Código y migraciones: ver la tabla "Estado actual de la implementación".
- Limitación 1: los Mockups 13, 14, 15 y 16 no están en el repositorio. El único documento funcional es `requerimientos_acciones_ud_v2 (1).pdf`, cuyo texto usa fuentes CID sin capa de texto extraíble con las herramientas disponibles. Este spec usa la transcripción literal del steering y no define comportamientos visuales.
- SAD disponible: `.kiro/SAD.tex`, RF-03 y RF-43–47, RNF-01/04/05/07/08/10 y EC-04/05/10. RF-45 exige autorización para restringir y no exige restricción automática. La revisión H7 actualiza el conflicto del borrador anterior.

### Estado previo a la implementación de MOD-07

| Capacidad | Estado | Evidencia |
|---|---|---|
| Roles previos `investor`, `broker`, `administrator`, permisos por rol y asignaciones con vigencia | Implementado | `migrations/versions/0001_identity_schema.py` (CHECK de `roles.code`, semilla de permisos `admin:users`, `admin:rbac`, `admin:markets`); `identity/domain/rbac.py` |
| Protección del último administrador | Implementado | `identity/domain/rbac.py::guard_last_administrator` (409 `LAST_ADMINISTRATOR`) |
| Protección contra agregar permisos `admin:*` a roles no administrativos o quitar `admin:rbac` del administrador | No existe | `identity/application/rbac_admin.py::change_permission` no valida el permiso ni el rol |
| Audit_Log de acciones administrativas de `identity` y `GET /admin/audit-log` | Implementado | `0005_identity_admin_gaps.py` (tabla `admin_audit_log`, trigger `BEFORE UPDATE OR DELETE`), `identity/domain/audit.py` (lista blanca `PAYLOAD_KEYS`), `routers/admin.py` |
| Protección de `admin_audit_log` contra `TRUNCATE` | No existe | El trigger de `0005` es de fila y solo cubre `UPDATE` y `DELETE` |
| IP y request id en el Audit_Log | No existe | `admin_audit_log` no tiene esas columnas; `RequestIdMiddleware` ya genera `request_id` (`shared/infrastructure/logging.py`) |
| Directorio administrativo de usuarios | Implementado | `GET /admin/users`, `GET /admin/users/{id}` (`admin:users`) |
| Horario por defecto y excepciones de calendario por mercado | Implementado, sin auditoría ni propagación | `market_data/adapters/inbound/http/routers/admin_markets.py` (`admin:markets`), `market_data/application/schedule_admin.py` |
| Zona horaria por mercado | Columna existente, no editable y no usada | `markets.timezone` (`0003`); `market_data/domain/timezones.py::market_instant` usa siempre `America/New_York` |
| Consulta administrativa de la configuración de un mercado | No existe | `GET /markets` devuelve solo `code` y `name` (`MarketOut`) |
| Mercado TXSE en la semilla | No existe | La semilla de `0003` tiene AMEX, ARCA, BATS, NYSE, NASDAQ, NYSEARCA y OTC |
| Schedule_Change_Port (RFP-10) | Implementado, sin invocador | `orders/application/schedule_change.py`, `app.state.order_schedule_change_port`; nadie lo llama |
| Comisión de referencia del 2 % | Implementado en tres lugares | `OrderConfig.commission_rate` (`orders`), `ReferenceCommission` (`portfolio`), `estimates.estimated_cost` (`brokers`), todos con `ORDER_REFERENCE_COMMISSION_RATE` |
| Punto de extensión para la comisión oficial | Implementado, sin adaptador | `portfolio/composition.py::InstalledCommission` lee `app.state.portfolio_commission_port`; contrato síncrono (`portfolio/domain/ports.py::CommissionPort`) |
| Atribución de una ejecución al comisionista firmante | Implementado | `orders/adapters/outbound/persistence/execution_repository.py` (`signed_by_broker_id` desde el evento hacia `BROKER_SIGNED` con `actor_type = 'broker'`) |
| Consulta de ejecuciones de toda la plataforma | No existe | `ExecutionLedger` solo consulta por `user_id` |
| Términos de comisión guardados en la orden | No existe | `orders` no guarda tasa ni reparto; `Order.estimated_amount` usa la tasa de referencia |
| Eventos de orden inmutables | No | `order_events` y `order_executions` no tienen trigger (`0007`) |
| Eventos de vinculación y propuesta inmutables | Implementado (sin `TRUNCATE`) | `broker_events` con trigger `BEFORE UPDATE OR DELETE` (`0009`) |
| Eventos de autenticación | Existentes, sin trigger | `auth_events` (`0001`), con IP y agente de usuario |
| Restricción de cuenta por actividad | No existe | `users.account_status` admite solo `active` y `pending_broker_activation` |
| Interruptor de negociación | No existe | Ningún módulo bloquea la creación o el envío de órdenes por decisión administrativa |
| Tablero de indicadores | No existe | — |

### Clasificación usada en este spec

Cada decisión y supuesto lleva una etiqueta:

- **[Confirmado]**: requisito confirmado por el catálogo, el steering o un spec aprobado.
- **[Restricción]**: restricción arquitectónica existente.
- **[Derivado]**: requisito técnico derivado de otro requisito o del código.
- **[Propuesta]**: propuesta de diseño de este spec, aplicable salvo que la revisión la rechace.
- **[Supuesto]**: supuesto pendiente de validación.
- **[Conflicto]**: conflicto detectado entre fuentes, con la resolución adoptada.

### Decisiones y supuestos del módulo

Cada punto abierto del catálogo para MOD-07 y cada conflicto encontrado queda resuelto aquí como decisión (G) o supuesto (A). Ninguno queda como supuesto silencioso.

- **G1 [Restricción] (nombre y límites):** el spec se llama `admin-mod-07` (patrón `<módulo>-mod-0N` de `product.md`) y el paquete `admin`. El módulo no duplica autenticación, RBAC, directorio de usuarios ni la persistencia de horarios: los reutiliza de `identity` y `market_data`. Tampoco crea ni envía órdenes: `orders` sigue siendo el único módulo que habla con Alpaca Broker API para órdenes.
- **G2 [Confirmado H1] (separación de responsabilidades):** se incorporan `auditor` (`admin:audit`, `admin:compliance:read`) y `analyst` (`admin:bi`). `administrator` conserva sus permisos y recibe `admin:fees`, `admin:commissions`, `admin:halts`, `admin:audit`, `admin:compliance`, `admin:compliance:read` y `admin:bi`. Los roles nuevos solo se asignan por un administrador y no tienen registro público. El auditor consulta evidencia sin modificarla; analyst consulta exclusivamente indicadores agregados. Ver justificación y matriz en implementation-decisions.md (RF-03/44/45/47, RNF-04/05).
- **G3 [Propuesta] (reautenticación en operaciones críticas):** crear o cancelar una Fee_Version, activar o liberar un Trading_Halt y restringir o rehabilitar una cuenta exigen un código TOTP válido del actor (Step_Up), igual que la autorización adicional de `orders` (O10). El código nunca se guarda ni se registra.
- **G4 [Confirmado + Propuesta] (matriz versionada):** RF-46 exige configurar tasas, reparto y "sus periodos de vigencia". La matriz es un historial de Fee_Versions por Fee_Scope (`default` o un código de `markets`), cada una con `effective_from` y sin fin explícito: una versión rige hasta que empieza la siguiente. Las Fee_Versions guardadas no cambian; solo se puede cancelar una versión programada que aún no empezó. La migración crea la Fee_Version 1 de `default` con 2.0000 % y reparto 60.00 % para la plataforma, vigente desde 1970-01-01T00:00:00Z, que reproduce la comisión de referencia actual y el reparto 60/40 del enunciado. El modelo `market_fee_configurations` del alcance inicial (una fila mutable por mercado) no permite vigencias ni reproducibilidad, así que se sustituye.
- **G5 [Propuesta] (representación y rangos):** la tasa se expresa en porcentaje sobre el importe bruto (`commission_rate_pct`, de 0.0000 a 10.0000, cuatro decimales) y el reparto como porcentaje de la comisión para la plataforma (`platform_share_pct`, de 0.00 a 100.00, dos decimales). El porcentaje del comisionista se deriva como `100 − platform_share_pct` y no se guarda, para que la suma sea 100 por construcción. El límite de 10 % evita errores de captura (por ejemplo, 20 en lugar de 2.0); no viene del catálogo (aprobación H5).
- **G6 [Confirmado + Propuesta] (fórmula y redondeo):** el enunciado de RF-43 fija la tasa sobre el precio de ejecución, suma la comisión en compra, la resta en venta, reparte 60/40 cuando participa un comisionista y redondea a 2 decimales. Este spec fija los detalles: la comisión se calcula por Execution sobre `qty × price` sin redondear y se redondea a 0.01 con `ROUND_HALF_EVEN`, el mismo modo de `portfolio/domain/rounding.py::money` y de `brokers/domain/estimates.py`. La Platform_Share se redondea igual y la Broker_Share es la diferencia, de modo que ambas suman la comisión exacta (aprobación H4).
- **G7 [Confirmado H3] (términos al crear):** cada orden guarda versión, tasa y reparto al crearla; ejecuciones parciales, revalidaciones, reenvíos y nuevas autorizaciones conservan esos términos. Un trigger impide reescribirlos. Las órdenes anteriores mantienen NULL sin backfill. Sus comisiones oficiales son desconocidas y se excluyen de los importes oficiales con `historical_terms_unknown_count` y `complete=false`. Portfolio conserva la estimación `reference` para compatibilidad, nunca como comisión oficial.
- **G8 [Propuesta] (participación del comisionista):** el reparto con comisionista se aplica a una Execution cuya Order tiene firma de Broker según `ExecutionLedger` (`signed_by_broker_id` no nulo): órdenes aprobadas en la revisión de `orders` y órdenes creadas desde propuestas de `brokers`. Sin firma, toda la comisión es de la plataforma.
- **G9 [Supuesto] (cobro efectivo):** en este módulo la comisión se calcula, cotiza, informa y consulta, pero no se descuenta de la cuenta Alpaca. Así se cumple RF-43 sin RFP-07 y se mantiene O8 de `orders` ("Alpaca sandbox no cobra esa comisión"). Cobrarla con el campo `commission` de Broker API queda como decisión futura (H10).
- **G10 [Restricción + Conflicto] (horarios):** el steering indica que MOD-07 no duplica la configuración de horarios de `market_data`. Los endpoints existentes `PUT|DELETE /admin/markets/{market_code}/default-schedule` y `GET|POST|PUT|DELETE /admin/markets/{market_code}/schedule-overrides[...]` siguen siendo la única forma de modificar horarios. El endpoint `PUT /api/v1/admin/markets/{market_id}/schedule` del alcance inicial duplicaría esos endpoints y no se crea. MOD-07 agrega la auditoría, la propagación a `orders` (RFP-10), la notificación y una vista consolidada de solo lectura.
- **G11 [Conflicto → Propuesta] (zona horaria):** RF-46 pide configurar la zona horaria. Todos los mercados del alcance son de EE. UU. y operan en `America/New_York` (Marco de la especificación), las sesiones de Alpaca llegan en esa zona y `market_instant` ignora `markets.timezone`. Cambiar la zona desincronizaría los horarios internos de las sesiones de Alpaca sin aportar valor de negocio. En esta fase la zona horaria se expone en la vista consolidada pero no se modifica (aprobación H6).
- **G12 [Conflicto] (horarios internos frente a horarios efectivos):** `market_data/domain/schedule.py::resolve` sustituye la apertura y el cierre de Alpaca por el horario por defecto configurado incluso en días de cierre anticipado, y acepta excepciones que abren un mercado en días sin sesión de Alpaca. Como `orders` decide el envío con ese calendario (`orders/adapters/outbound/market_data/market_session.py`), una configuración interna puede hacer que la plataforma considere abierto un mercado que la bolsa tiene cerrado. La plataforma no puede extender el horario real de una bolsa. Este spec no cambia la regla de `market_data` y registra el riesgo con la propuesta de que el horario efectivo sea la intersección entre el horario interno y la sesión de Alpaca (aprobación H12).
- **G13 [Propuesta] ("usuarios suscritos" de RF-46):** se agrega el tipo de evento `market_schedule_changes` a las preferencias de `identity`, con `in_app` habilitado por defecto para usuarios nuevos y existentes, igual que O15 de `orders` y B21 de `brokers`. Los "usuarios suscritos" son los que tienen ese tipo habilitado en algún canal. Los Investors con órdenes afectadas reciben además el aviso `order_updates` que ya envía `orders` (Requisito 14 de `orders-mod-03`).
- **G14 [Propuesta] (interruptor de negociación):** el "circuit breaker" del alcance inicial es un Trading_Halt: una restricción de la plataforma, con alcance global o por mercado y vigencia (`starts_at`, `ends_at` opcional), que impide crear órdenes nuevas y enviar a Alpaca órdenes aún no enviadas. No suspende la bolsa, no cancela ni modifica órdenes ya enviadas a Alpaca y no afecta lecturas de mercado, transferencias de `wallet` ni la reconciliación de órdenes. La activación y la liberación son manuales; el catálogo no define condiciones de activación automática. Es distinto de un circuit breaker de infraestructura para llamadas a Alpaca, que este módulo no implementa. RF-46 ("restricciones" con "vigencias") es su requisito de origen.
- **G15 [Propuesta] (códigos de los bloqueos):** una orden bloqueada por un Trading_Halt responde 503 `TRADING_HALTED`, porque es temporal y reintentable; así `create_from_proposal` la propaga como indisponibilidad y la propuesta de `brokers` sigue `accepted` (D2 de `brokers-mod-06`). Una orden bloqueada por una Account_Restriction responde 403 `ACCOUNT_TRADING_RESTRICTED`, porque depende de una decisión sobre la cuenta; en propuestas se trata como rechazo de negocio (`conversion_failed`).
- **G16 [Restricción + Propuesta] (registro de auditoría único):** el steering indica que RF-44 amplía `admin_audit_log` "en lugar de crear un segundo registro paralelo". Por eso la tabla `audit_logs` del alcance inicial no se crea. (1) Las acciones administrativas de MOD-07 y los cambios de horario de `market_data` se escriben en `admin_audit_log`, que gana las columnas `ip_address` y `request_id` y nuevos códigos de acción y tipos de objetivo. Los valores anterior y nuevo van en las claves `before` y `after` del `payload` con lista blanca, el patrón de `identity/domain/audit.py`. (2) La consulta de RF-44 lee además las fuentes de eventos que ya existen (`order_events`, `broker_events`, `auth_events`) mediante una vista de solo lectura, sin copiar sus filas.
- **G17 [Propuesta] (nivel de garantía de la auditoría):** el registro es append-only en la aplicación (sin métodos de actualización ni borrado) y en la base de datos (triggers que rechazan `UPDATE`, `DELETE` y `TRUNCATE`). Eso protege contra errores de la aplicación y contra modificaciones de cualquier rol sin privilegios de propietario. No es inmutable frente al propietario del esquema o a un superusuario de Supabase, que pueden deshabilitar triggers. Hoy la aplicación se conecta con la cadena de `DATABASE_URL` y no hay un rol separado sin privilegios de propietario. Este spec no afirma inmutabilidad absoluta ni cumplimiento legal o regulatorio: el catálogo no cita normas concretas. Un rol de base de datos separado y el anclaje externo de resúmenes criptográficos quedan pendientes (aprobación H9).
- **G18 [Supuesto] (retención e IP):** no hay política de retención en el catálogo; los registros se conservan sin purga en esta fase (aprobación H15). La IP se toma de `request.client.host`, igual que `identity` en el login (`routers/auth.py`). Detrás de un proxy es la IP del proxy, salvo que el despliegue configure `--proxy-headers` y `--forwarded-allow-ips` de uvicorn; este spec no cambia el despliegue.
- **G19 [Propuesta] (qué se audita):** se registran las operaciones de escritura exitosas de este módulo y los cambios de horario. Las lecturas (consultas de auditoría, comisiones y KPIs) no generan Audit_Entry, igual que el directorio de usuarios (Requisito 20 criterio 15 de `identity-market-backend`), salvo la generación de un Compliance_Report, que es una escritura. Los intentos rechazados con 401 o 403 se registran en el log estructurado con `request_id`, no en `admin_audit_log`.
- **G20 [Definición H7] (restricción autorizada):** RF-45 del SAD permite imponer restricciones con autorización y deja sus criterios sujetos a definición. Una señal no prueba fraude ni restringe automáticamente. Solo administrator con `admin:compliance`, TOTP, motivo y evidencia puede restringir o rehabilitar `trading`. Se conservan login, roles, billetera y órdenes enviadas.
- **G21 [Definición H7] (detección determinista):** `atypical-v2` combina umbral absoluto de ejecución (USD 10000), volumen relativo (>3 veces media de 90 días, mínimo 5 antecedentes), frecuencia de órdenes (20/300 s), cancelaciones confirmadas (10/300 s) y rechazos de negocio consecutivos (5/3600 s). Ventanas, límites, exclusión de fallos externos y referencias están en implementation-decisions.md. La configuración proviene del entorno y se captura en cada reporte; no se usa ML ni otro proveedor.
- **G22 [Supuesto] (patrón promedio y compartir, RFP-13):** el patrón promedio del Period es la media, entre los usuarios con al menos una Execution en el Period, de la cantidad de Executions y del volumen negociado. "Compartir con cumplimiento" significa que el Compliance_Report queda guardado, sin cambios posteriores, con su resumen SHA-256, y se consulta por identificador con el permiso `admin:compliance:read`. No se envía por canales externos.
- **G23 [Propuesta] (indicadores de RF-47):** los indicadores se limitan a los que pide RF-47 y su enunciado, con datos existentes: usuarios registrados, nuevos registros por nivel e interés, usuarios activos, volumen negociado por mercado y lado, comisiones de la plataforma por mercado, suscripciones activas, ingresos por fuente y usuarios por tipo (nivel y con o sin comisionista). La definición exacta de cada uno está en el Requisito 17. "Usuario activo" es una propuesta: usuario con al menos una verificación MFA exitosa en el Period (`auth_events`). Los desgloses por sector quedan fuera, porque `instruments.sector` es opcional y suele estar vacío (A5 de `identity-market-backend`). Las series temporales quedan fuera porque el Mockup 13 no está disponible (aprobación H8).
- **G24 [Propuesta] (caché de indicadores):** la tabla `system_kpis_cache` del alcance inicial no guarda el Period, así que no distingue resultados de periodos distintos. Se sustituye por un KPI_Snapshot por Period y versión de definiciones, con vigencia `ADMIN_KPI_CACHE_TTL_SECONDS` (por defecto 300). Se guarda en la base de datos para que varias instancias compartan el resultado y la respuesta pueda mostrar su fecha de cálculo.
- **G25 [Derivado] (acceso a datos de otros módulos):** MOD-07 lee datos de `identity`, `market_data`, `wallet`, `orders` y `brokers` mediante adaptadores de salida propios de solo lectura en `admin/adapters/outbound/<módulo>/`, por decisión explícita de la regla de módulos (`structure.md`), igual que D8 de `brokers-mod-06`. Las escrituras en otros módulos usan sus puertos de aplicación (Schedule_Change_Port, Notifier). Las únicas excepciones son la escritura en `admin_audit_log` (G16) y las columnas nuevas de `orders` creadas por migración (G7).
- **G26 [Confirmado H1] (protección de permisos):** los permisos administrativos de control solo admiten administrator. Los de lectura tienen una lista cerrada: admin:audit y admin:compliance:read admiten auditor; admin:bi admite analyst. Cualquier otra concesión admin:* y quitar admin:rbac de administrator producen PROTECTED_PERMISSION sin cambios. MOD-07 comprueba el rol permitido además del permiso efectivo en cada solicitud.
- **G27 [Propuesta] (orden de los sprints):** el plan inicial pone la matriz en el Sprint 1 y los logs append-only en el Sprint 2. Cada cambio de la matriz debe auditarse en su misma transacción (Requisito 10) y exige permisos nuevos (Requisito 19), así que la escritura de auditoría y los permisos pasan al Sprint 1. El Sprint 2 conserva los triggers y la vista unificada de auditoría y agrega horarios, interruptores e integración de comisiones con `orders`. El Sprint 3 conserva los tableros con RBAC estricto y agrega cumplimiento (RF-45, RFP-13), que depende del Trading_Gate del Sprint 2.
- **G28 [Derivado] (estimaciones de otros módulos):** el costo estimado de una propuesta de `brokers` (B10) y la vista previa de `orders` usan los Commission_Terms vigentes del mercado en lugar de `ORDER_REFERENCE_COMMISSION_RATE`. Mientras `admin` no esté instalado, los adaptadores por defecto conservan el comportamiento actual.
- **G29 [Restricción] (Period):** un Period es un intervalo de fechas `from` y `to` inclusivas en `America/New_York`, igual que en `brokers-mod-06`, convertido a `[from 00:00, to + 1 día 00:00)` en UTC, con un máximo de 366 días.
- **G30 [Restricción + Propuesta] (comisiones visibles para el Broker):** por B4 de `brokers-mod-06`, un Broker solo ve datos de Investors con Active_Link. La consulta de comisiones del Broker se limita a las Executions que él firmó para Investors con Active_Link en el momento de la consulta. Las comisiones de clientes anteriores siguen en la consulta administrativa (aprobación H11).
- **A1 [Supuesto] (moneda):** todos los importes se expresan en USD, igual que A2 de `orders-mod-03`. Los pagos de suscripción en otra moneda se excluyen de los ingresos y se cuentan aparte.
- **A2 [Derivado] (código de mercado):** el mercado de una orden es `orders.exchange`, que `orders` toma del Instrument de `market_data` y usa también con Schedule_Change_Port. Coincide con `markets.code` para los mercados de la semilla. Un `exchange` sin fila en `markets` (por ejemplo TXSE, que el catálogo incluye y la semilla no) usa el Fee_Scope `default` y solo lo afecta un Trading_Halt global.
- **A3 [Supuesto] (reloj):** las comparaciones de vigencia usan el reloj de la aplicación (`shared/domain/clock.py`). Los triggers que dependen del tiempo usan `now()` de PostgreSQL; se asume una diferencia entre ambos relojes de pocos segundos.

### Registro de decisiones de la revisión humana

| ID | Decisión | Impacto | Prioridad | Bloquea |
|---|---|---|---|---|
| H1 | **Autorizada y adoptada:** auditor/analyst con permisos cerrados de lectura (G2) | Separación de responsabilidades; actualiza D3 de identity | Alta | Resuelta en G2/G26 y Req. 19 |
| H2 | Exigir Step_Up TOTP en operaciones críticas (G3) | Seguridad y fricción operativa | Media | Tarea 4.2 y las que la usan (8.1, 12.4, 18.2) |
| H3 | **Aprobada e implementada:** términos al crear y persistencia inmutable (G7) | No retroactividad; históricos sin evidencia permanecen desconocidos | Alta | Resuelta en Req. 2 y 3 |
| H4 | Redondeo `ROUND_HALF_EVEN` por Execution (G6) | Importes cobrados e informados | Media | Tarea 6.1 |
| H5 | Rango de tasa de 0 a 10 % (G5) | Validación de la matriz | Media | Tarea 5.1 |
| H6 | Zona horaria de solo lectura (G11) | Cobertura parcial de RF-46 | Media | Tarea 11.6 |
| H7 | **Definición autorizada e implementada:** reglas deterministas y restricción manual con evidencia (G20, G21) | Cumple RF-45 del SAD; sin ML ni bloqueo automático | Alta | Resuelta: tareas 18 y 19 |
| H8 | Definiciones de los indicadores, en especial "usuario activo" (G23) | Exactitud del tablero | Media | Tarea 20.1 |
| H9 | Rol de base de datos sin privilegios de propietario y anclaje externo de resúmenes (G17) | Nivel real de inmutabilidad | Alta | Nada; es operación del despliegue |
| H10 | Cobrar la comisión en Alpaca con `commission` (G9) | Movimiento de fondos virtuales | Baja | Nada en esta fase |
| H11 | Visibilidad de comisiones del Broker solo con Active_Link (G30) | Datos del Broker sobre ex clientes | Media | Tarea 15.3 |
| H12 | Horario efectivo como intersección con la sesión de Alpaca (G12) | Corrección del envío de órdenes en días especiales | Alta | Nada en esta fase; afecta a `market_data` |
| H13 | Nuevo tipo de evento `market_schedule_changes` con `in_app` por defecto (G13) | Notificaciones | Baja | Tarea 11.3 |
| H14 | Reordenar los sprints (G27) | Planificación | Baja | Plan de tareas |
| H15 | Retención indefinida de auditoría e IP (G18) | Protección de datos personales | Media | Nada en esta fase |

Las propuestas H2/H4/H5/H6/H8/H11/H13/H14 se adoptan como decisiones técnicas
de implementación dentro de la autorización de trabajo completo; no se registra
una aprobación humana que no haya ocurrido. H9/H10/H12/H15 se difieren con los
límites explícitos de implementation-decisions.md.

### Política de pruebas

**[Adoptada para esta implementación]** Las pruebas son obligatorias para las partes críticas: validación y resolución de Fee_Versions (Requisito 1 criterios 2 a 5, 7 a 9 y 13; Requisito 2 criterios 1, 2, 5 y 6), cálculo y reparto de la comisión (Requisito 3), estados de los Trading_Halts y su efecto sobre las órdenes (Requisito 8 criterios 2, 6 y 10; Requisito 9 criterios 1 a 3, 5 y 7), escritura atómica y lista blanca de auditoría (Requisito 10 criterios 1 a 5), triggers de inmutabilidad (Requisito 11 criterios 1 y 2), selección y paginación del rastro unificado (Requisito 12 criterios 1, 2 y 4), idempotencia del despacho de cambios de horario (Requisito 7 criterios 3 y 6), unicidad y efecto de las restricciones (Requisito 14 criterios 2, 4 y 5), regla de operaciones atípicas (Requisito 15 criterios 2 y 3), resumen del Compliance_Report (Requisito 16 criterio 4), fórmulas de los indicadores (Requisito 17 criterios 2 a 9 y 11), control de acceso (Requisito 19 criterios 2 a 5) y no regresión de los módulos previos (Requisito 11 criterio 5, Requisito 20 criterio 6). Las demás pruebas son opcionales.

## Glossary

- **Backend_API**: la aplicación FastAPI de Acciones UD que expone los endpoints de este spec.
- **Auditor**: usuario con rol `auditor` y permisos exclusivos de lectura de evidencia.
- **Analyst**: usuario con rol `analyst` y permiso exclusivo de BI agregado. El actor de seguridad del SAD se representa con auditor para consulta y administrator para decisiones.
- **Administrator**: usuario autenticado con el rol `administrator` vigente y `account_status` `active`, que además tiene el permiso que exige cada endpoint (Requisito 19).
- **Investor**: usuario autenticado con el rol `investor` vigente.
- **Broker**: usuario autenticado con el rol `broker` vigente (comisionista).
- **Active_Link**: vinculación `active` entre un Investor y un Broker según `brokers-mod-06`.
- **Market**: fila de la tabla `markets` de `market_data`, identificada por `code`.
- **Fee_Scope**: ámbito de una matriz de comisiones: `default` o el código de un Market.
- **Fee_Version**: versión de la matriz de un Fee_Scope con número, `commission_rate_pct`, `platform_share_pct`, `effective_from`, motivo, actor, fecha de creación y, si se canceló, fecha, actor y motivo de cancelación.
- **Commission_Terms**: tasa y reparto aplicables a una orden: `fee_version_id` (nulo con el adaptador por defecto), `commission_rate_pct` y `platform_share_pct`.
- **Fee_Service**: componente de `admin` que crea, cancela y consulta Fee_Versions.
- **Fee_Resolver**: regla pura de `admin` que obtiene los Commission_Terms de un Market en un instante.
- **Commission_Calculator**: regla pura de `admin` que calcula la comisión, la Platform_Share y la Broker_Share de una Execution o de una cotización.
- **Commission_Quote_Service**: componente de `admin` que cotiza comisiones.
- **Commission_Query_Service**: componente de `admin` que lista comisiones generadas.
- **Commission_Terms_Port**: puerto de salida de `orders` que devuelve los Commission_Terms de un Market en un instante; `admin` provee su adaptador.
- **Commission_Port**: puerto de `portfolio` definido en `portfolio-mod-05` que devuelve la comisión de una Execution; `admin` provee su adaptador oficial.
- **Gross_Amount**: `qty × price` de una Execution o de una cotización, sin redondear para el cálculo y presentado con 2 decimales.
- **Platform_Share** y **Broker_Share**: partes de la comisión para la plataforma y para el Broker firmante.
- **Order**, **Execution**, **Order_Event**, **Unsent_Order**, **Order_Scheduler**, **Order_Submitter**, **Schedule_Change_Port**: definidos en `orders-mod-03`.
- **Trading_Halt**: interruptor de negociación de la plataforma con alcance (Halt_Scope), motivo, `starts_at`, `ends_at` opcional y, si se liberó, fecha, actor y motivo de liberación.
- **Halt_Scope**: `global` o el código de un Market.
- **Halt_Service**: componente de `admin` que activa, libera y consulta Trading_Halts.
- **Account_Restriction**: restricción de tipo `trading` sobre la cuenta de un usuario, con motivo, evidencia, analista responsable y, si se levantó, datos de la rehabilitación.
- **Restriction_Service**: componente de `admin` que restringe, rehabilita y consulta cuentas.
- **Trading_Gate**: regla pura de `admin` que decide si un usuario puede operar un Market en un instante según los Trading_Halts y las Account_Restrictions.
- **Trading_Gate_Port**: puerto de salida de `orders` que evalúa el Trading_Gate; `admin` provee su adaptador.
- **Audit_Log**: la tabla `admin_audit_log`, ampliada por este módulo.
- **Audit_Entry**: fila del Audit_Log.
- **Audit_Source**: fuente de eventos de la consulta unificada: `admin` (Audit_Log), `orders` (`order_events`), `brokers` (`broker_events`) y `auth` (`auth_events`).
- **Audit_Trail_Service**: componente de `admin` que consulta los eventos de las Audit_Sources.
- **Schedule_Change_Dispatcher**: componente de `admin` que propaga cada cambio de horario a Schedule_Change_Port y notifica a los usuarios suscritos.
- **Market_Admin_View**: componente de `admin` que arma la vista consolidada de mercados.
- **Atypical_Rule**: regla pura de `admin` que señala Executions atípicas según la decisión G21.
- **Compliance_Report**: reporte de auditoría de un usuario de RFP-13, guardado sin cambios posteriores con su resumen SHA-256.
- **Compliance_Service**: componente de `admin` que detecta operaciones atípicas y genera Compliance_Reports.
- **KPI_Service**: componente de `admin` que calcula los indicadores de RF-47.
- **KPI_Snapshot**: resultado guardado de los indicadores de un Period.
- **Step_Up**: código TOTP del actor exigido en una operación crítica según la decisión G3.
- **Period**: intervalo de fechas según la decisión G29.
- **Notifier**: componente existente de `market_data` que crea notificaciones y las despacha según las preferencias del usuario.
- **Error_Body**: cuerpo JSON de error con los campos `code`, `message` y `details`, definido por `identity-market-backend`.

## Requirements

### Requirement 1: Versiones de la matriz de comisiones (RF-46)

**User Story:** Como Administrator, quiero registrar versiones con vigencia de la tasa de comisión y del reparto de cada mercado, para cambiar la política comercial sin alterar operaciones ya pactadas.

#### Acceptance Criteria

1. WHEN un Administrator con el permiso `admin:fees` crea una Fee_Version para un Fee_Scope existente con `commission_rate_pct`, `platform_share_pct`, `effective_from` opcional, `reason` de 1 a 500 caracteres, `expected_latest_version` y Step_Up válido, THE Fee_Service SHALL guardar la Fee_Version con el número siguiente al último número del Fee_Scope, `effective_from` igual al valor indicado o al instante de recepción de la solicitud si se omite, el actor y la fecha de creación, y SHALL responder 201 con la Fee_Version.
2. IF `commission_rate_pct` no es un decimal entre 0 y 10 inclusive con a lo sumo 4 decimales, o `platform_share_pct` no es un decimal entre 0 y 100 inclusive con a lo sumo 2 decimales, THEN THE Backend_API SHALL responder 422 con el código `VALIDATION_ERROR` y el campo inválido en `details`, sin guardar nada.
3. IF `effective_from` es anterior al instante en que el Backend_API recibe la solicitud, THEN THE Backend_API SHALL responder 422 con el código `VALIDATION_ERROR` y `details.reason` igual a `retroactive`, sin guardar nada.
4. IF ya existe una Fee_Version no cancelada del mismo Fee_Scope con el mismo `effective_from`, THEN THE Backend_API SHALL responder 409 con el código `FEE_VERSION_CONFLICT`, sin guardar nada.
5. IF `expected_latest_version` no es igual al último número de Fee_Version del Fee_Scope, THEN THE Backend_API SHALL responder 409 con el código `FEE_VERSION_CONFLICT` y el último número en `details.latest_version`, sin guardar nada.
6. IF el Fee_Scope no es `default` ni el código de un Market, THEN THE Backend_API SHALL responder 404 con el código `NOT_FOUND` y `details.resource` igual a `fee_scope`.
7. WHEN un Administrator con el permiso `admin:fees` cancela una Fee_Version no cancelada cuyo `effective_from` es posterior al instante de la solicitud, con `reason` de 1 a 500 caracteres y Step_Up válido, THE Fee_Service SHALL registrar la fecha, el actor y el motivo de la cancelación y SHALL excluir esa Fee_Version de toda resolución posterior de Commission_Terms.
8. IF la Fee_Version a cancelar ya está cancelada o su `effective_from` es igual o anterior al instante de la solicitud, THEN THE Backend_API SHALL responder 409 con el código `FEE_VERSION_NOT_CANCELABLE` y el estado efectivo en `details`.
9. THE Fee_Service SHALL conservar sin cambios el número, las tasas, el `effective_from`, el motivo, el actor y la fecha de creación de toda Fee_Version guardada, y SHALL admitir como única modificación la cancelación del criterio 7.
10. WHEN un Administrator con el permiso `admin:fees` consulta la matriz, THE Fee_Service SHALL devolver, para el Fee_Scope `default` y para cada Market, la Fee_Version vigente en el instante de la consulta, su origen (`market` si es del propio Market o `default` si se hereda) y las Fee_Versions programadas no canceladas con `effective_from` posterior.
11. WHEN un Administrator con el permiso `admin:fees` consulta el historial de un Fee_Scope, THE Fee_Service SHALL devolver todas sus Fee_Versions, incluidas las canceladas, con su estado efectivo (`scheduled`, `in_force`, `superseded` o `canceled`), en orden descendente de número y paginadas por cursor.
12. WHEN se aplica la migración del módulo, THE Migration_Set SHALL crear la Fee_Version 1 del Fee_Scope `default` con `commission_rate_pct` 2.0000, `platform_share_pct` 60.00 y `effective_from` 1970-01-01T00:00:00Z, sin actor.
13. WHEN dos solicitudes concurrentes crean Fee_Versions del mismo Fee_Scope con el mismo `expected_latest_version`, THE Fee_Service SHALL guardar como máximo una y SHALL responder 409 con el código `FEE_VERSION_CONFLICT` a las demás.

### Requirement 2: Términos de comisión aplicables a una orden (RF-43, RF-46)

**User Story:** Como Investor, quiero que la comisión que se me informa al crear una orden sea la que se aplique a sus ejecuciones, para operar sin sorpresas aunque el administrador cambie la tarifa.

#### Acceptance Criteria

1. THE Fee_Resolver SHALL obtener los Commission_Terms de un Market en un instante t de la Fee_Version no cancelada del Fee_Scope de ese Market con el mayor `effective_from` menor o igual que t, y, si no existe, de la Fee_Version no cancelada del Fee_Scope `default` con la misma regla.
2. IF el mercado de una orden no corresponde a ningún Market, THEN THE Fee_Resolver SHALL aplicar el Fee_Scope `default`.
3. WHEN `orders` crea una Order, THE Order_Service SHALL obtener mediante Commission_Terms_Port los Commission_Terms del mercado del instrumento en el instante `created_at` de la Order, SHALL usar su tasa en el Estimated_Amount y en la Reservation, y SHALL guardar en la Order `fee_version_id`, `commission_rate_pct` y `platform_share_pct` en la misma transacción que la crea.
4. WHEN `orders` atiende una vista previa de orden, THE Order_Service SHALL calcular la comisión estimada con los Commission_Terms vigentes en el instante de la vista previa.
5. THE Backend_API SHALL conservar sin cambios los Commission_Terms guardados en una Order después de crearla, aunque después se creen o cancelen Fee_Versions, la Order se ejecute parcialmente, se programe, se revise o se reanude.
6. WHERE una Order no tiene Commission_Terms guardados porque se creó antes de MOD-07, THE Backend_API SHALL conservar NULL, informar comisión oficial desconocida y excluirla de los importes oficiales con contador y `complete=false`; SHALL NOT asignar la semilla ni la configuración actual sin evidencia histórica (H3).
7. IF Commission_Terms_Port no puede leer las Fee_Versions porque la base de datos no está disponible, THEN THE Order_Service SHALL responder 503 con el código `DATABASE_UNAVAILABLE` sin crear la Order ni la Reservation.
8. WHILE el adaptador de `admin` no está instalado, THE Order_Service SHALL usar un adaptador por defecto que devuelve `fee_version_id` nulo, `commission_rate_pct` igual a `ORDER_REFERENCE_COMMISSION_RATE` × 100 y `platform_share_pct` 60.00.

### Requirement 3: Cálculo oficial de la comisión y su reparto (RF-43)

**User Story:** Como Investor o Broker, quiero que la comisión de cada ejecución se calcule con una fórmula exacta y conocida, para verificar lo que pago o lo que me corresponde.

#### Acceptance Criteria

1. THE Commission_Calculator SHALL calcular la comisión de cada Execution como `qty × price × commission_rate_pct / 100`, con los Commission_Terms de su Order, redondeada a 0.01 con `ROUND_HALF_EVEN`.
2. WHEN la Order de la Execution tiene firma de Broker (`signed_by_broker_id` no nulo), THE Commission_Calculator SHALL calcular la Platform_Share como la comisión × `platform_share_pct` / 100 redondeada a 0.01 con `ROUND_HALF_EVEN`, y la Broker_Share como la comisión menos la Platform_Share.
3. WHEN la Order de la Execution no tiene firma de Broker, THE Commission_Calculator SHALL asignar toda la comisión a la Platform_Share y SHALL fijar la Broker_Share en 0.00.
4. THE Commission_Calculator SHALL garantizar que la Platform_Share más la Broker_Share es igual a la comisión y que ambas están entre 0.00 y la comisión.
5. THE Commission_Calculator SHALL informar, para una compra, el total igual al Gross_Amount más la comisión y, para una venta, el neto igual al Gross_Amount menos la comisión, ambos redondeados a 0.01 con `ROUND_HALF_EVEN`.
6. WHEN portfolio solicita la comisión de una Execution con términos comprobados mediante Commission_Port, THE Backend_API SHALL devolver el cálculo del criterio 1 con `source=official`. Sin términos conservará una estimación etiquetada `reference`, sin presentarla como comisión oficial (H3).
7. THE Commission_Calculator SHALL devolver el mismo resultado para los mismos Commission_Terms, cantidad, precio, lado y firma, sin acceder a la base de datos ni a proveedores externos.

### Requirement 4: Cotizar comisión (RF-43)

**User Story:** Como Investor o Broker, quiero cotizar la comisión de una operación antes de crearla, para conocer la tasa, el importe y el total.

#### Acceptance Criteria

1. WHEN un Investor o un Broker cotiza con símbolo, lado (`buy` o `sell`), cantidad mayor que cero, precio mayor que cero y `with_broker` opcional (por defecto false), THE Commission_Quote_Service SHALL devolver el mercado del instrumento, el Gross_Amount, la tasa aplicada, el `fee_version_id`, la comisión, el total o el neto según el Requisito 3 criterio 5 y, si `with_broker` es true, la Platform_Share y la Broker_Share, con los Commission_Terms vigentes en el instante de la consulta.
2. IF el símbolo no existe en el catálogo de `market_data`, THEN THE Backend_API SHALL responder 404 con el código `SYMBOL_NOT_FOUND`.
3. IF la cantidad o el precio no son decimales mayores que cero, o el lado no es `buy` o `sell`, THEN THE Backend_API SHALL responder 422 con el código `VALIDATION_ERROR` y los campos inválidos en `details`.
4. THE Commission_Quote_Service SHALL indicar `binding` en false, porque los Commission_Terms definitivos se fijan al crear la orden según el Requisito 2 criterio 3.
5. IF el usuario no tiene el rol `investor` ni el rol `broker` vigentes, THEN THE Backend_API SHALL responder 403 con el código `FORBIDDEN`.

### Requirement 5: Consultar comisiones generadas (RF-43)

**User Story:** Como Investor, Broker o Administrator, quiero consultar las comisiones generadas por periodo, comisionista y cliente, para conocer importes y operaciones.

#### Acceptance Criteria

1. WHEN un Investor consulta sus comisiones en un Period, THE Commission_Query_Service SHALL devolver sus Executions del Period con identificador de Execution y de Order, símbolo, mercado, lado, cantidad, precio, Gross_Amount, tasa, comisión, total o neto y fecha de ejecución, ordenadas por fecha de ejecución descendente y paginadas por cursor, más los totales del Period de Gross_Amount y comisión.
2. WHEN un Broker consulta sus comisiones en un Period, THE Commission_Query_Service SHALL devolver las Executions del Period que él firmó para Investors con Active_Link en el momento de la consulta, con los campos del criterio 1, el identificador y el nombre del Investor, la Platform_Share y la Broker_Share, más los totales del Period, con filtro opcional por `investor_id`.
3. IF el `investor_id` del criterio 2 no tiene Active_Link con el Broker, THEN THE Backend_API SHALL responder 404 con el código `CLIENT_NOT_FOUND`.
4. WHEN un Administrator con el permiso `admin:commissions` consulta comisiones en un Period con filtros opcionales `broker_id`, `investor_id` y `market`, THE Commission_Query_Service SHALL devolver las Executions que cumplen los filtros con los campos del criterio 2 y los totales de comisión, Platform_Share y Broker_Share del Period por mercado y por Broker.
5. IF el Period no cumple la decisión G29, THEN THE Backend_API SHALL responder 422 con el código `VALIDATION_ERROR` y los parámetros inválidos en `details`.
6. THE Commission_Query_Service SHALL calcular cada importe con el Commission_Calculator, de modo que la comisión de una Execution es igual en esta consulta, en `portfolio` y en el tablero del Requisito 17.

### Requirement 6: Vista consolidada de mercados y horarios (RF-46, RF-27)

**User Story:** Como Administrator, quiero ver en una sola consulta la configuración de cada mercado, para revisar horarios, excepciones, tarifas e interruptores antes de modificarlos.

#### Acceptance Criteria

1. WHEN un Administrator con el permiso `admin:markets` consulta la lista de mercados, THE Market_Admin_View SHALL devolver para cada Market su código, nombre, zona horaria, horario por defecto o null, las excepciones de calendario con fecha desde el día actual en `America/New_York` hasta 90 días después, los Commission_Terms vigentes con su origen y los Trading_Halts `active` o `scheduled` del Market y globales.
2. WHEN un Administrator con el permiso `admin:markets` consulta un Market por su código, THE Market_Admin_View SHALL devolver los datos del criterio 1 para ese Market.
3. IF el código no corresponde a ningún Market, THEN THE Backend_API SHALL responder 404 con el código `NOT_FOUND` y `details.resource` igual a `market`.
4. THE Backend_API SHALL mantener los endpoints de horario por defecto y de excepciones de `market_data` como los únicos que modifican horarios, sin cambiar sus rutas, cuerpos ni respuestas exitosas (decisión G10).
5. THE Market_Admin_View SHALL exponer la zona horaria como dato de solo lectura (decisión G11).

### Requirement 7: Trazabilidad y propagación de cambios de horario (RF-46, RFP-10)

**User Story:** Como Investor, quiero que un cambio de horario quede registrado, ponga en revisión mis órdenes pendientes y me avise, para decidir si siguen siendo válidas.

#### Acceptance Criteria

1. WHEN un Administrator fija o elimina el horario por defecto de un Market, o crea, modifica o elimina un Schedule_Override, mediante los endpoints de `market_data`, THE Market_Service SHALL guardar en la misma transacción que el cambio un Audit_Entry con la acción correspondiente (`market_default_schedule_set`, `market_default_schedule_cleared`, `schedule_override_created`, `schedule_override_updated` o `schedule_override_deleted`), el Market como objetivo, los valores anteriores y nuevos, la fecha efectiva, el actor, la IP y el `request_id`.
2. IF guardar el Audit_Entry del criterio 1 falla, THEN THE Backend_API SHALL responder 503 con el código `DATABASE_UNAVAILABLE` y SHALL dejar el horario sin cambios.
3. WHEN un cambio del criterio 1 se confirma, THE Schedule_Change_Dispatcher SHALL invocar Schedule_Change_Port de `orders` con `change_id` igual al identificador del Audit_Entry, el código del Market, la fecha efectiva (la fecha de la excepción o el día actual en `America/New_York` para el horario por defecto) y una descripción del cambio.
4. WHEN Schedule_Change_Port responde para un cambio todavía no despachado, THE Schedule_Change_Dispatcher SHALL registrar el despacho con la cantidad de órdenes afectadas y SHALL enviar una notificación `market_schedule_changes` a cada usuario con ese tipo habilitado en algún canal, con el Market, la fecha efectiva y el horario nuevo, como máximo una vez por usuario y cambio.
5. THE Schedule_Change_Dispatcher SHALL intentar el despacho inmediatamente después de confirmar el cambio y también cada `ADMIN_SCHEDULE_DISPATCH_INTERVAL_SECONDS` segundos para los cambios sin despacho registrado.
6. WHEN el Schedule_Change_Dispatcher procesa un cambio con despacho registrado, THE Schedule_Change_Dispatcher SHALL omitir la invocación de Schedule_Change_Port y las notificaciones.
7. IF la invocación de Schedule_Change_Port falla, THEN THE Schedule_Change_Dispatcher SHALL dejar el cambio sin despacho registrado para el siguiente ciclo y SHALL registrar el fallo en el log sin secretos.
8. WHEN un Administrator con el permiso `admin:markets` consulta los cambios de horario de un Market en un Period, THE Backend_API SHALL devolver cada cambio con acción, actor, valores anteriores y nuevos, fecha efectiva, fecha del cambio, estado del despacho, cantidad de órdenes afectadas y cantidad de usuarios notificados, ordenados por fecha descendente y paginados por cursor.
9. THE Backend_API SHALL agregar el tipo de evento `market_schedule_changes` a las preferencias de notificación de `identity` con el canal `in_app` habilitado por defecto para usuarios nuevos y existentes (decisión G13).

### Requirement 8: Interruptores de negociación (RF-46)

**User Story:** Como Administrator, quiero activar y liberar un interruptor de negociación global o por mercado con motivo y vigencia, para detener la operación de la plataforma ante una contingencia.

#### Acceptance Criteria

1. WHEN un Administrator con el permiso `admin:halts` activa un Trading_Halt con Halt_Scope `global` o el código de un Market, `reason` de 1 a 500 caracteres, `starts_at` opcional, `ends_at` opcional y Step_Up válido, THE Halt_Service SHALL guardar el Trading_Halt con `starts_at` igual al valor indicado o al instante de recepción si se omite, el actor y la fecha de creación, y SHALL responder 201 con el Trading_Halt y su estado efectivo.
2. IF existe un Trading_Halt no liberado del mismo Halt_Scope cuyo intervalo `[starts_at, ends_at)` se solapa con el nuevo, tomando un `ends_at` nulo como sin fin, THEN THE Backend_API SHALL responder 409 con el código `TRADING_HALT_OVERLAP` y el identificador del Trading_Halt existente en `details`.
3. IF `starts_at` es anterior al instante de recepción, o `ends_at` es igual o anterior a `starts_at`, THEN THE Backend_API SHALL responder 422 con el código `VALIDATION_ERROR` y el campo inválido en `details`.
4. WHEN un Administrator con el permiso `admin:halts` libera un Trading_Halt en estado `active` o `scheduled` con `reason` de 1 a 500 caracteres y Step_Up válido, THE Halt_Service SHALL registrar la fecha, el actor y el motivo de la liberación y SHALL responder 200 con el Trading_Halt en estado `released`.
5. IF el Trading_Halt a liberar está en estado `released` o `expired`, THEN THE Backend_API SHALL responder 409 con el código `TRADING_HALT_NOT_RELEASABLE` y el estado efectivo en `details`.
6. THE Halt_Service SHALL calcular el estado efectivo de un Trading_Halt en un instante t así: `released` si tiene fecha de liberación menor o igual que t; si no, `scheduled` si t es anterior a `starts_at`; si no, `expired` si `ends_at` no es nulo y es menor o igual que t; y en otro caso `active`.
7. WHEN un Administrator con el permiso `admin:halts` lista los Trading_Halts con filtros opcionales de estado efectivo y Halt_Scope, THE Halt_Service SHALL devolverlos con motivo, actores y fechas, ordenados por `starts_at` descendente y paginados por cursor.
8. WHEN un usuario autenticado consulta los interruptores activos, THE Halt_Service SHALL devolver los Trading_Halts en estado `active` con Halt_Scope, `starts_at` y `ends_at`, sin motivo ni actores.
9. THE Backend_API SHALL aplicar una activación o una liberación a toda evaluación del Trading_Gate que empiece después de enviar la respuesta de esa activación o liberación.
10. WHEN dos solicitudes concurrentes activan Trading_Halts solapados del mismo Halt_Scope, THE Halt_Service SHALL guardar como máximo uno y SHALL responder 409 con el código `TRADING_HALT_OVERLAP` a las demás.

### Requirement 9: Efecto de interruptores y restricciones sobre las órdenes (RF-46, RF-45, RF-30, RF-35)

**User Story:** Como Administrator, quiero que un interruptor o una restricción de cuenta impidan operar en la plataforma sin tocar las órdenes que ya están en la bolsa, para contener un riesgo sin crear efectos que no se puedan revertir.

#### Acceptance Criteria

1. WHEN un Investor crea o previsualiza una Order de un instrumento cuyo mercado tiene un Trading_Halt `active`, o existe un Trading_Halt global `active`, THE Order_Service SHALL responder 503 con el código `TRADING_HALTED` con el Halt_Scope, el identificador y `ends_at` en `details`, sin crear la Order ni la Reservation y sin llamar a Alpaca_Broker_API.
2. WHEN un Investor con una Account_Restriction activa crea o previsualiza una Order, THE Order_Service SHALL responder 403 con el código `ACCOUNT_TRADING_RESTRICTED`, sin crear la Order ni la Reservation y sin llamar a Alpaca_Broker_API.
3. WHEN una Unsent_Order en Pendiente o en Firmada por Comisionista llega al paso de envío (Order_Scheduler, reenvío, reanudación, aprobación del Broker o conversión de una propuesta) y el Trading_Gate deniega la operación, THE Order_Submitter SHALL omitir la llamada a Alpaca_Broker_API, SHALL conservar su Order_Status y su Reservation, SHALL fijar `scheduled_for` en el instante actual si era nulo, de modo que el Order_Scheduler la reintente, y SHALL notificar al Investor una sola vez con el tipo `order_updates` y la causa `trading_halted` o `account_trading_restricted`.
4. WHEN el Trading_Gate vuelve a permitir la operación, THE Order_Scheduler SHALL enviar las Orders diferidas según las reglas de `orders-mod-03`, incluidas la nueva autorización por cambio de precio (Requisito 7 de `orders-mod-03`) y la expiración de O17.
5. THE Backend_API SHALL conservar sin cambios, por efecto de un Trading_Halt o de una Account_Restriction, las Orders en Enviada, en En Ejecución y las Terminal_Orders, y SHALL permitir su cancelación por el Investor según el Requisito 12 de `orders-mod-03`.
6. WHEN `create_from_proposal` de `orders` encuentra un Trading_Halt `active` aplicable, THE Order_Service SHALL lanzar el error `TRADING_HALTED` como indisponibilidad, de modo que la Proposal de `brokers` siga en `accepted` y la aprobación del Broker responda 503 con ese código; con una Account_Restriction activa SHALL devolver `OrderRejected` con el código `ACCOUNT_TRADING_RESTRICTED`.
7. IF el Trading_Gate no puede evaluarse porque la base de datos no está disponible, THEN THE Order_Service y THE Order_Submitter SHALL omitir el envío a Alpaca_Broker_API y SHALL propagar el error `DATABASE_UNAVAILABLE`.
8. THE Trading_Gate SHALL dejar sin cambios las consultas de datos de mercado, las transferencias de `wallet`, la reconciliación de órdenes enviadas y las operaciones de `brokers` distintas de la conversión en orden.

### Requirement 10: Registro central de auditoría administrativa (RF-44, RF-03)

**User Story:** Como Auditor, quiero que cada acción administrativa quede registrada con su actor, origen y valores anterior y nuevo, para reconstruir quién cambió qué, cuándo y desde dónde.

#### Acceptance Criteria

1. WHEN una de estas operaciones devuelve una respuesta exitosa, THE Backend_API SHALL guardar exactamente un Audit_Entry en el Audit_Log, en la misma transacción que la operación, con la acción, el actor, el tipo y el identificador del objetivo, el `payload` con las claves de su lista blanca, la IP, el `request_id` y la fecha:
   - creación de Fee_Version: acción `fee_version_created`, objetivo `fee_version`, claves `scope`, `version_no`, `before` (la última Fee_Version del Fee_Scope o null) y `after`;
   - cancelación de Fee_Version: acción `fee_version_canceled`, objetivo `fee_version`, claves `scope`, `version_no`, `reason`, `before` y `after`;
   - activación de Trading_Halt: acción `trading_halt_activated`, objetivo `trading_halt`, claves `scope`, `starts_at`, `ends_at` y `reason`;
   - liberación de Trading_Halt: acción `trading_halt_released`, objetivo `trading_halt`, claves `scope`, `reason`, `before` y `after`;
   - restricción de cuenta: acción `account_restricted`, objetivo `user`, claves `restriction_id`, `restriction_type`, `reason` y `evidence`;
   - rehabilitación de cuenta: acción `account_rehabilitated`, objetivo `user`, claves `restriction_id`, `restriction_type`, `reason` y `evidence`;
   - generación de Compliance_Report: acción `compliance_report_generated`, objetivo `user`, claves `report_id`, `period_from`, `period_to`, `rules_version` y `content_sha256`;
   - cambios de horario del Requisito 7 criterio 1: objetivo `market`, claves `override_id` (null para el horario por defecto), `effective_from`, `before` y `after`.
2. IF guardar el Audit_Entry falla, THEN THE Backend_API SHALL responder 503 con el código `DATABASE_UNAVAILABLE` y SHALL dejar sin guardar la operación de esa solicitud.
3. IF una operación del criterio 1 devuelve una respuesta de error (HTTP 400 o superior), THEN THE Backend_API SHALL omitir el Audit_Entry de esa solicitud.
4. IF un Audit_Entry se construye con claves de `payload` faltantes o distintas de las de su lista blanca, THEN THE Backend_API SHALL rechazar la construcción, SHALL dejar sin guardar la operación y SHALL responder 500 con el código `INTERNAL_ERROR`.
5. THE Backend_API SHALL excluir de todo Audit_Entry los códigos TOTP, contraseñas y sus hashes, tokens de acceso, refresh o MFA, códigos de recuperación, cookies, credenciales de Alpaca o Stripe y cualquier parte de un identificador tributario.
6. THE Backend_API SHALL conservar sin cambios los Audit_Entries existentes de `identity`, sus acciones y el contrato de `GET /api/v1/admin/audit-log`.
7. WHEN un endpoint de este módulo rechaza una solicitud con 401 o 403, THE Backend_API SHALL registrar en el log estructurado el `request_id`, la ruta, el método, el código de error y el identificador del usuario si se autenticó, sin secretos, y SHALL omitir el Audit_Entry.

### Requirement 11: Inmutabilidad de las fuentes de auditoría (RF-44)

**User Story:** Como Auditor, quiero que los registros de auditoría no se puedan modificar ni borrar desde la aplicación ni con roles sin privilegios de propietario, para confiar en la evidencia que reviso.

#### Acceptance Criteria

1. THE Migration_Set SHALL rechazar en la base de datos toda sentencia `UPDATE`, `DELETE` o `TRUNCATE` sobre `admin_audit_log`, `order_events`, `order_executions`, `auth_events`, `broker_events` y la tabla de Compliance_Reports.
2. THE Migration_Set SHALL rechazar `DELETE` y `TRUNCATE` sobre las tablas de Fee_Versions, Trading_Halts y Account_Restrictions, y SHALL admitir `UPDATE` solo para fijar una vez los campos de cancelación (Fee_Version programada), liberación (Trading_Halt) o rehabilitación (Account_Restriction), conservando sin cambios los demás campos.
3. THE Backend_API SHALL exponer los Audit_Entries, los eventos de las Audit_Sources y los Compliance_Reports solo mediante endpoints de lectura y de creación, sin endpoints ni métodos de repositorio que los modifiquen o borren.
4. THE Backend_API SHALL describir en el contrato OpenAPI de los endpoints de auditoría el nivel de garantía de la decisión G17.
5. WHEN se aplica la migración que agrega los triggers del criterio 1, THE Backend_API SHALL mantener el resultado de las pruebas existentes de `identity`, `orders`, `brokers` y `portfolio`.

### Requirement 12: Consultar eventos auditables (RF-44)

**User Story:** Como Auditor, quiero consultar los eventos asociados a un usuario investigado en un periodo, de todas las fuentes, para revisar sus acciones y operaciones en orden cronológico.

#### Acceptance Criteria

1. WHEN un usuario autorizado con el permiso `admin:audit` consulta el rastro de auditoría con un Period y filtros opcionales `user_id`, `source`, `action`, `entity_type` y `entity_id`, THE Audit_Trail_Service SHALL devolver los eventos de las Audit_Sources del Period que cumplen todos los filtros, cada uno con fuente, identificador, fecha, tipo e identificador del actor, usuario afectado, usuario relacionado, acción, tipo e identificador de la entidad, estado anterior y nuevo cuando existan, detalles e IP cuando exista, ordenados por fecha descendente, fuente e identificador descendentes, y paginados por cursor con `page_size` de 1 a 100 (por defecto 50).
2. WHERE la consulta incluye `user_id`, THE Audit_Trail_Service SHALL devolver solo los eventos cuyo actor, usuario afectado o usuario relacionado es ese usuario.
3. IF la consulta no incluye Period, el Period no cumple la decisión G29, `source` no es una Audit_Source o `page_size` está fuera de rango, THEN THE Backend_API SHALL responder 422 con el código `VALIDATION_ERROR` y los parámetros inválidos en `details`.
4. WHEN un cliente recorre todas las páginas de una consulta sin que se agreguen eventos al Period, THE Audit_Trail_Service SHALL devolver cada evento que cumple los filtros exactamente una vez.
5. THE Audit_Trail_Service SHALL excluir de los detalles las claves `totp_code`, `code`, `password`, `password_hash`, `token`, `access_token`, `refresh_token`, `mfa_token`, `secret`, `recovery_code`, `recovery_codes` y `tax_id`, en cualquier nivel de anidamiento.
6. WHEN el Audit_Trail_Service atiende una consulta, THE Audit_Trail_Service SHALL leer solo la base de datos, sin guardar Audit_Entries ni llamar a proveedores externos.

### Requirement 13: Cadena de custodia de una orden (RF-44)

**User Story:** Como Auditor, quiero ver quién creó y autorizó una orden, qué comisionista la firmó y cuándo se envió al mercado, para resolver disputas de no repudio.

#### Acceptance Criteria

1. WHEN un usuario autorizado con el permiso `admin:audit` consulta la cadena de custodia de una Order, THE Audit_Trail_Service SHALL devolver la Order, su dueño, el actor y la fecha de creación, el método de autorización registrado, el Broker firmante y la fecha de firma cuando existan, la referencia de la propuesta cuando exista, la fecha del primer paso a Enviada, el identificador de Alpaca, las solicitudes de cancelación, los Commission_Terms, las Executions y todos los Order_Events en orden cronológico ascendente.
2. IF la Order no existe, THEN THE Backend_API SHALL responder 404 con el código `NOT_FOUND` y `details.resource` igual a `order`.
3. THE Audit_Trail_Service SHALL construir la cadena de custodia solo con datos guardados por `orders` y `brokers`, sin llamar a Alpaca_Broker_API.

### Requirement 14: Restringir y rehabilitar cuentas (RF-45)

**User Story:** Como Analista, quiero restringir la operación de una cuenta con motivo y evidencia y rehabilitarla después, para contener una actividad sospechosa con trazabilidad.

#### Acceptance Criteria

1. WHEN un Administrator con el permiso `admin:compliance` restringe la cuenta de un usuario existente con tipo `trading`, `reason` de 1 a 500 caracteres, evidencia (texto de hasta 2000 caracteres y hasta 20 referencias a eventos del rastro de auditoría o a Executions) y Step_Up válido, THE Restriction_Service SHALL guardar una Account_Restriction activa con el usuario, el tipo, el motivo, la evidencia, el analista responsable y la fecha, y SHALL responder 201.
2. IF el usuario ya tiene una Account_Restriction activa del mismo tipo, THEN THE Backend_API SHALL responder 409 con el código `RESTRICTION_ALREADY_ACTIVE` y su identificador en `details`.
3. IF el usuario no existe, THEN THE Backend_API SHALL responder 404 con el código `NOT_FOUND` y `details.resource` igual a `user`; IF el usuario es el propio actor, THEN THE Backend_API SHALL responder 422 con el código `VALIDATION_ERROR`.
4. WHEN un Administrator con el permiso `admin:compliance` rehabilita una Account_Restriction activa con `reason` de 1 a 500 caracteres, evidencia y Step_Up válido, THE Restriction_Service SHALL registrar la fecha, el analista, el motivo y la evidencia de la rehabilitación y SHALL responder 200 con la Account_Restriction levantada.
5. IF la Account_Restriction a rehabilitar ya está levantada, THEN THE Backend_API SHALL responder 409 con el código `RESTRICTION_NOT_ACTIVE`.
6. WHEN un Administrator con el permiso `admin:compliance:read` lista Account_Restrictions con filtros opcionales de usuario y estado (`active` o `lifted`), THE Restriction_Service SHALL devolverlas con sus decisiones, ordenadas por fecha de restricción descendente y paginadas por cursor.
7. THE Restriction_Service SHALL registrar cada decisión (restringir o rehabilitar) con la cuenta afectada, el motivo, el tipo, la decisión, la evidencia y el analista responsable.
8. THE Restriction_Service SHALL crear Account_Restrictions solo por solicitud de un Administrator (decisión G20).
9. THE Restriction_Service SHALL dejar sin cambios `users.account_status`, las sesiones, los roles, la billetera y las Orders enviadas del usuario restringido.

### Requirement 15: Operaciones potencialmente atípicas (RF-45)

**User Story:** Como Analista, quiero obtener las operaciones potencialmente atípicas de un periodo con una regla explícita, para decidir qué cuentas revisar.

#### Acceptance Criteria

1. WHEN un usuario con `admin:compliance:read` consulta señales de un Period, THE Compliance_Service SHALL devolver ejecuciones y eventos persistidos señalados con usuario, fecha, razones, valores observados, referencias, versión y configuración. Se ordenan por instante descendente e identificador estable y se paginan por cursor. `user_id` y `min_amount` son opcionales; este último filtra el importe económico de la señal.
2. THE Atypical_Rule SHALL aplicar G21 y los límites de ventana de implementation-decisions.md. Los eventos simultáneos se evalúan juntos, la historia económica excluye el instante evaluado y los fallos externos no cuentan como rechazos del usuario.
3. THE Atypical_Rule SHALL devolver el mismo resultado para las mismas Executions y la misma configuración, sin acceder a proveedores externos.
4. IF el Period no cumple la decisión G29 o `min_amount` no es un decimal mayor o igual que cero, THEN THE Backend_API SHALL responder 422 con el código `VALIDATION_ERROR`.
5. THE Backend_API SHALL leer del entorno los cuatro valores ADMIN_ATYPICAL_* y los seis límites ADMIN_ORDER_FREQUENCY_*, ADMIN_CANCELLATION_* y ADMIN_REJECTION_*, validarlos sin exponer valores y capturarlos junto con `atypical-v2` en cada reporte.

### Requirement 16: Reporte de auditoría de un usuario (RFP-13)

**User Story:** Como Analista, quiero generar un reporte de la actividad de un usuario en un periodo, compararla con el patrón promedio y compartirlo con cumplimiento, para documentar una investigación.

#### Acceptance Criteria

1. WHEN un Administrator con el permiso `admin:compliance` genera un Compliance_Report de un usuario existente para un Period, THE Compliance_Service SHALL guardar el Compliance_Report con el resumen del usuario (fecha de registro, roles vigentes y Account_Restrictions del Period), la cantidad de eventos del rastro de auditoría por fuente y acción, la cantidad, el volumen y las comisiones de sus Executions, el patrón promedio de la decisión G22, la razón entre el usuario y el patrón, las operaciones atípicas del Period según la Atypical_Rule, el actor, la fecha, la versión de reglas y el resumen SHA-256, y SHALL responder 201.
2. THE Compliance_Service SHALL calcular cada razón del criterio 1 como el valor del usuario dividido por el patrón promedio, redondeada a 0.01 con `ROUND_HALF_EVEN`, y SHALL devolver null cuando el patrón promedio es cero.
3. WHEN un Administrator con el permiso `admin:compliance:read` consulta un Compliance_Report por identificador o lista los de un usuario, THE Compliance_Service SHALL devolver el contenido guardado y su resumen SHA-256 sin recalcular el contenido.
4. THE Compliance_Service SHALL calcular el resumen SHA-256 sobre la serialización canónica del contenido (JSON con claves ordenadas, sin espacios, decimales como cadenas y fechas en ISO 8601 UTC), de modo que recalcularlo sobre el contenido devuelto da el mismo valor.
5. THE Compliance_Service SHALL permitir consultar un reporte a administrator o auditor con `admin:compliance:read`, sin envío externo; generarlo requiere administrator con `admin:compliance`.
6. IF el usuario no existe o el reporte no existe, THEN THE Backend_API SHALL responder 404 con el código `NOT_FOUND` y el recurso en `details`; IF el Period no cumple la decisión G29, THEN THE Backend_API SHALL responder 422 con el código `VALIDATION_ERROR`.

### Requirement 17: Tablero de indicadores del negocio (RF-47)

**User Story:** Como Administrator, quiero un tablero de indicadores del negocio para un periodo, para seguir el crecimiento, la actividad y los ingresos de la plataforma.

#### Acceptance Criteria

1. WHEN un Administrator con el permiso `admin:bi` consulta los indicadores de un Period, THE KPI_Service SHALL devolver los indicadores de los criterios 2 a 9, cada uno con valor, unidad y el identificador de su definición, junto con el Period, la fecha de cálculo y la versión de definiciones.
2. THE KPI_Service SHALL calcular `registered_users` como la cantidad de usuarios con `created_at` anterior al fin del Period.
3. THE KPI_Service SHALL calcular `new_registrations` como la cantidad de usuarios con `created_at` dentro del Period, desglosada por `investor_level` (`beginner`, `experienced` o `unspecified`) y por cada interés de `users.interests`, donde un usuario con varios intereses cuenta en cada uno.
4. THE KPI_Service SHALL calcular `active_users` como la cantidad de usuarios distintos con al menos un evento `auth_events` de tipo `mfa_verify` y resultado `success` dentro del Period (decisión G23).
5. THE KPI_Service SHALL calcular `traded_volume_usd` como la suma de `qty × price` de las Executions con fecha de ejecución dentro del Period, redondeada a 0.01 con `ROUND_HALF_EVEN`, y `executions_count` como su cantidad, ambos desglosados por mercado y por lado.
6. THE KPI_Service SHALL calcular `platform_commissions_usd` como la suma de las Platform_Shares del Requisito 3 de las Executions del Period, desglosada por mercado.
7. THE KPI_Service SHALL calcular `active_subscriptions` como la cantidad de suscripciones distintas con un pago `paid` cuyo intervalo `[period_start, period_end)` contiene el instante T, donde T es el menor entre el fin del Period y el instante de la consulta.
8. THE KPI_Service SHALL calcular `revenue_by_source` con dos fuentes: `commissions`, igual a `platform_commissions_usd`, y `subscriptions`, igual a la suma de los pagos `paid` en USD con fecha dentro del Period, más la cantidad de pagos excluidos por estar en otra moneda.
9. THE KPI_Service SHALL calcular `users_by_type` en el instante T del criterio 7 como la cantidad de usuarios con rol `investor` vigente en T, desglosada por `investor_level` y por si tenían una vinculación de `brokers` iniciada antes de T y no terminada en T.
10. IF el Period no cumple la decisión G29, THEN THE Backend_API SHALL responder 422 con el código `VALIDATION_ERROR`.
11. THE KPI_Service SHALL garantizar que la suma de los desgloses por mercado y por lado de `traded_volume_usd` y `executions_count`, la suma por mercado de `platform_commissions_usd` y la suma por `investor_level` de `new_registrations` y `users_by_type` son iguales a su total.
12. WHEN no hay datos para un indicador en el Period, THE KPI_Service SHALL devolver 0 para cantidades e importes y null para porcentajes con denominador cero.

### Requirement 18: Caché y frescura de los indicadores (RF-47)

**User Story:** Como Administrator, quiero que el tablero responda rápido y me diga cuándo se calculó, para confiar en los datos sin sobrecargar la base de datos.

#### Acceptance Criteria

1. WHEN existe un KPI_Snapshot del mismo Period y versión de definiciones con menos de `ADMIN_KPI_CACHE_TTL_SECONDS` segundos de antigüedad, THE KPI_Service SHALL devolverlo con `cache_hit` en true, `stale` en false y su fecha de cálculo.
2. WHEN la consulta incluye `refresh` en true, THE KPI_Service SHALL recalcular los indicadores, guardar el KPI_Snapshot y devolverlo con `cache_hit` en false.
3. IF el cálculo falla y existe un KPI_Snapshot vencido del mismo Period y versión de definiciones, THEN THE KPI_Service SHALL devolverlo con `stale` en true; IF no existe, THEN THE Backend_API SHALL responder 503 con el código `DATABASE_UNAVAILABLE`.
4. WHEN cambia la versión de definiciones de los indicadores, THE KPI_Service SHALL ignorar los KPI_Snapshots de versiones anteriores.
5. WHERE `ADMIN_KPI_CACHE_TTL_SECONDS` es 0, THE KPI_Service SHALL recalcular en cada consulta y SHALL guardar el resultado solo para el uso del criterio 3.

### Requirement 19: Permisos administrativos y protección contra escalamiento (RF-03, RF-44, RF-45)

**User Story:** Como responsable de seguridad, quiero que cada función administrativa exija un permiso propio verificado en el backend y que los permisos de lectura se distingan de los permisos de control, para aplicar mínimo privilegio y evitar escalamientos mediante listas cerradas de roles.

#### Acceptance Criteria

1. WHEN se aplica la migración, THE Migration_Set SHALL crear los siete permisos de G2, asignarlos a administrator y conceder solo `admin:audit` y `admin:compliance:read` a auditor, y `admin:bi` a analyst. No se conceden permisos de control a esos roles.
2. THE Backend_API SHALL exigir en cada endpoint administrativo de este módulo el permiso indicado en su requisito, evaluado con `require_permission` de `identity` en el instante de la solicitud.
3. IF una solicitud administrativa no tiene sesión válida, THEN THE Backend_API SHALL responder 401; IF el usuario no tiene el permiso, THEN THE Backend_API SHALL responder 403 con el código `FORBIDDEN`; ambas comprobaciones SHALL ocurrir antes de validar parámetros y sin cambios en los datos guardados.
4. IF una solicitud concede admin:* fuera de la lista cerrada por rol de G26, THEN THE RBAC_Service SHALL responder 409 PROTECTED_PERMISSION sin cambiar permisos ni escribir auditoría. Los permisos de control permanecen reservados a administrator.
5. IF una solicitud quita el permiso `admin:rbac` del rol `administrator`, THEN THE RBAC_Service de `identity` SHALL responder 409 con el código `PROTECTED_PERMISSION` sin cambiar el rol.
6. IF una operación con Step_Up no trae código TOTP, THEN THE Backend_API SHALL responder 409 con el código `EXTRA_AUTHORIZATION_REQUIRED`; IF el código no es válido, THEN SHALL responder 401 con el código `EXTRA_AUTHORIZATION_INVALID`; IF el actor no tiene TOTP confirmado, THEN SHALL responder 409 con el código `MFA_ENROLLMENT_REQUIRED`; en los tres casos sin cambios en los datos guardados.
7. THE Backend_API SHALL omitir el código TOTP del Step_Up en los datos guardados, en los Audit_Entries, en los logs y en los Error_Body.
8. THE Backend_API SHALL reutilizar los endpoints de roles, permisos, asignaciones y directorio de `identity` para la gestión de accesos, sin duplicarlos en este módulo.

### Requirement 20: Contratos con los módulos existentes

**User Story:** Como desarrollador del backend, quiero que MOD-07 se conecte a los módulos previos mediante sus puntos de extensión, para activar la comisión oficial, los interruptores y la auditoría sin romper sus contratos HTTP.

#### Acceptance Criteria

1. WHEN la aplicación se registra, THE Backend_API SHALL instalar los adaptadores de `admin` en `app.state.order_commission_terms`, `app.state.order_trading_gate`, `app.state.portfolio_commission_port`, `app.state.brokers_commission_terms` y `app.state.market_schedule_change_listener`, y cada módulo consumidor SHALL resolverlos en cada uso.
2. THE `orders` module SHALL publicar en su capa de aplicación una consulta de Executions de toda la plataforma por Period, con filtros por usuario, Broker firmante y mercado, paginada por cursor e incluyendo los Commission_Terms de la Order, sin endpoints HTTP nuevos en `orders`.
3. WHEN `brokers` calcula el costo estimado de una Proposal_Version, THE Proposal_Service SHALL usar la tasa de los Commission_Terms vigentes del mercado del símbolo obtenidos mediante un puerto, en lugar de `ORDER_REFERENCE_COMMISSION_RATE`.
4. THE Backend_API SHALL mantener las rutas, los cuerpos y las respuestas exitosas de `orders`, `portfolio`, `brokers`, `market_data` e `identity`, salvo los errores nuevos declarados (`TRADING_HALTED`, `ACCOUNT_TRADING_RESTRICTED`, `PROTECTED_PERMISSION`) y los campos aditivos documentados en el diseño.
5. WHEN un Administrator modifica un horario mediante `market_data`, THE Backend_API SHALL pasar al Market_Service el actor, la IP y el `request_id` de la solicitud para el Audit_Entry del Requisito 7 criterio 1.
6. WHILE los adaptadores de `admin` no están instalados, THE Backend_API SHALL conservar en `orders`, `portfolio`, `brokers` y `market_data` el comportamiento actual, con los adaptadores por defecto.

### Requirement 21: Errores, configuración, contrato y rendimiento (transversal)

**User Story:** Como equipo de frontend, quiero un contrato OpenAPI completo con errores explícitos y respuestas en tiempo acotado, para integrar las pantallas administrativas sin ambigüedades.

#### Acceptance Criteria

1. THE Backend_API SHALL leer desde `Settings`, con los valores por defecto de este spec, `ADMIN_JOBS_ENABLED`, `ADMIN_SCHEDULE_DISPATCH_INTERVAL_SECONDS`, `ADMIN_KPI_CACHE_TTL_SECONDS`, `ADMIN_ATYPICAL_ABSOLUTE_USD`, `ADMIN_ATYPICAL_MULTIPLIER`, `ADMIN_ATYPICAL_WINDOW_DAYS` y `ADMIN_ATYPICAL_MIN_HISTORY`, y SHALL fallar al arrancar con un error que nombra cada variable fuera de rango, sin mostrar su valor.
2. IF la base de datos no está disponible, THEN THE Backend_API SHALL responder 503 con el código `DATABASE_UNAVAILABLE`.
3. THE Backend_API SHALL responder todo error con un Error_Body sin secretos ni datos de usuarios distintos del objeto consultado.
4. THE Backend_API SHALL declarar en el contrato OpenAPI los schemas de request, de response y de cada respuesta de error de cada endpoint de este módulo, con los tags `admin-fees`, `commissions`, `admin-markets`, `admin-halts`, `admin-audit`, `admin-compliance` y `admin-bi`.
5. THE Backend_API SHALL representar porcentajes, cantidades, precios e importes como cadenas decimales exactas.
6. THE Backend_API SHALL representar fechas y horas en ISO 8601 con desplazamiento UTC y SHALL interpretar todo Period según la decisión G29.
7. WHEN la base de datos tiene el volumen de referencia del diseño (5.000 usuarios), THE Backend_API SHALL responder en menos de 2 segundos en el percentil 95 las consultas de una página del rastro de auditoría, de comisiones, de la matriz, de la vista de mercados y de indicadores servidos desde un KPI_Snapshot vigente.
8. WHERE `ADMIN_JOBS_ENABLED` es false, THE Backend_API SHALL omitir el job periódico del Schedule_Change_Dispatcher y conservar el despacho inmediato del Requisito 7 criterio 5.
