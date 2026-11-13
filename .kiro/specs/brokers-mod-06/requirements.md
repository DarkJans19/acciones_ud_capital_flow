# Requirements Document

## Introduction

Este spec cubre el módulo de desarrollo MOD-06 "Red y Portal de Comisionistas Financieros" del backend de Acciones UD (responsable: María Fernanda Vélez Benítez). El módulo se implementa como el paquete `brokers` dentro del monolito modular hexagonal (`src/acciones_ud/brokers/`). Depende de MOD-01 (`identity`) y MOD-02 (`market_data`), ya implementados en `identity-market-backend`, de MOD-03 (`orders`, spec `orders-mod-03`) y de MOD-05 (`portfolio`, spec `portfolio-mod-05`). Por eso se construye después de MOD-05, según el orden del catálogo (MOD-04 → MOD-03 → MOD-05 → MOD-06 y MOD-07).

Alcance trazable (los textos originales están en `.kiro/steering/requerimientos-proyecto.md`, sección MOD-06):

- Perfil público del comisionista (Requisito 1), soporte de RF-13 y RF-23.
- RF-13: consultar comisionistas por sugerencias o búsqueda (Requisito 2) y solicitar la vinculación (Requisito 3).
- RF-13, RF-14 y RFP-04: ciclo de vida de la vinculación (Requisitos 3 y 4).
- RF-15: historial de vinculaciones (Requisito 5).
- RFP-09: solicitud de comisionista desde el registro o el perfil y autorización para operar en nombre del Investor (Requisito 6).
- RF-16, RF-17 y RF-18: crear, modificar y retirar propuestas (Requisitos 7 y 8).
- RF-19: aceptar o rechazar una propuesta (Requisito 9).
- RF-20: aprobación interna de la propuesta y conversión en orden (Requisito 10), con mensajes internos (Requisito 11).
- RF-21: historial de propuestas (Requisito 12).
- RF-22 y RF-23: calificaciones y reputación (Requisitos 13 y 14).
- RFP-05: clientes asignados, su portafolio y sus órdenes (Requisito 15).
- Contratos de Broker_Link_Port de `orders`, Broker_Client_Port de `portfolio` y `associated_broker` de `identity` (Requisito 16).
- RFP-04 y requisitos transversales de autorización, propiedad, trazabilidad, notificaciones, configuración, errores y contrato OpenAPI (Requisitos 17 y 18).

Fuera de alcance: liquidación y pago de comisiones del comisionista (RFP-07, descartado por la Decisión R3); cálculo, cotización y consulta oficial de comisiones (RF-43, MOD-07); RFP-06 (descartado por la Decisión R2); mensajería general o chat libre entre usuarios fuera de una propuesta; moderación de reseñas y supervisión administrativa (MOD-07); registro y activación de comisionistas (ya en `identity`); creación, envío y seguimiento de órdenes, y la cola de revisión de órdenes del Investor (MOD-03).

### Decisiones y supuestos del módulo

Cada punto abierto del catálogo para MOD-06 queda resuelto aquí como decisión (B) o supuesto (A).

- **B1 (modelo de la vinculación, punto abierto):** una Link tiene los estados `requested`, `active`, `declined`, `canceled`, `expired` y `ended`. Las transiciones permitidas son: `requested` → `active` (el Broker acepta), `requested` → `declined` (el Broker declina con motivo), `requested` → `canceled` (el Investor cancela su solicitud), `requested` → `expired` (pasan `BROKER_LINK_REQUEST_TTL_DAYS` días, por defecto 7, sin respuesta) y `active` → `ended` (el Investor se desvincula con motivo, RF-14). `declined`, `canceled`, `expired` y `ended` son terminales. Ninguna otra transición es válida.
- **B2 (un comisionista por Investor):** un Investor tiene como máximo una Link en `requested` o `active` a la vez, porque `/users/me` expone un único `associated_broker` (RF-06). Un Broker no tiene límite de clientes.
- **B3 (consentimiento de la vinculación):** la solicitud exige `consent_accepted` en true y registra la versión del texto de consentimiento vigente (`BROKER_LINK_CONSENT_VERSION`) y la marca de tiempo. El texto del consentimiento lo presenta el frontend; el backend guarda la versión aceptada.
- **B4 (RFP-04 como regla de pertenencia):** la pertenencia Broker–Investor se evalúa en cada caso de uso del Backend_API, no como filtro de interfaz. Un Broker accede a datos de un Investor solo con una Link `active` entre ambos y con el rol `broker` vigente. Un recurso de otro usuario o de un Investor no vinculado responde 404 con el código del recurso, igual que `orders` (`ORDER_NOT_FOUND`), para no revelar su existencia. Al terminar la Link, el Broker pierde el acceso de inmediato, incluido el historial de propuestas de ese Investor.
- **B5 (RFP-09, solicitud al registrarse):** `identity` ya guarda `broker_requested` en `users`. `brokers` lo lee mediante un puerto y no crea otro indicador ni modifica ese dato. Mientras `broker_requested` es true y el Investor no tiene Link en `requested` o `active`, la consulta de la vinculación propia devuelve `pending_broker_selection` en true junto con las sugerencias del Requisito 2. La solicitud desde el perfil es la misma solicitud de vinculación del Requisito 3.
- **B6 (RFP-09, autorización para operar en nombre del Investor, punto abierto):** la Trading_Authorization es un consentimiento explícito, separado de la Link, que el Investor otorga sobre una Link `active` y revoca en cualquier momento. Registra versión del consentimiento (`BROKER_TRADING_CONSENT_VERSION`), fecha de otorgamiento y fecha de revocación. Termina automáticamente cuando termina la Link. Sin Trading_Authorization vigente, una propuesta aceptada no se convierte en Order.
- **B7 (revisión de órdenes propias, contrato O6 de `orders`):** la Link tiene `order_review_enabled`, falso por defecto, que solo el Investor cambia. `reviewing_broker(investor_id)` de Broker_Link_Port devuelve el Broker de la Link `active` cuando `order_review_enabled` es true; en otro caso devuelve null. La cola, devolución y aprobación de esas órdenes siguen en `orders`.
- **B8 (ciclo de vida de la propuesta):** una Proposal tiene los estados `sent`, `accepted`, `rejected`, `withdrawn`, `approved`, `declined_by_broker`, `conversion_failed` y `expired`. Transiciones permitidas: `sent` → `accepted` o `rejected` (RF-19, Investor); `sent` o `accepted` → `sent` con versión nueva (RF-17, Broker); `sent` o `accepted` → `withdrawn` (RF-18, Broker, o terminación de la Link); `accepted` → `approved` o `declined_by_broker` (RF-20, Broker); `approved` → `conversion_failed` (rechazo de negocio de `orders`); `sent` → `expired` (pasan `PROPOSAL_TTL_HOURS` horas, por defecto 72, desde la última versión; una Proposal `accepted` no expira automáticamente). "Propuesta no aprobada" (RF-17) significa estado `sent` o `accepted`. Los demás estados son terminales.
- **B9 (versiones):** cada modificación crea una versión nueva con número consecutivo e inmutable; las versiones anteriores se conservan. Modificar una Proposal `accepted` anula la aceptación y la devuelve a `sent`. Toda acción sobre una Proposal (modificar, retirar, aceptar, rechazar, aprobar) indica la versión vista; si no es la vigente, la acción se rechaza. Así el Investor acepta exactamente la versión que vio.
- **B10 (precio de referencia y costo estimado, RF-16):** la Proposal define símbolo, lado (`buy` o `sell`), cantidad, tipo (`market` o `limit`), precio límite para `limit` y vigencia `day`. El precio de referencia es el precio de la cotización vigente de `market_data` al crear o modificar la versión, o el precio límite para `limit`. El costo estimado es cantidad × precio de referencia × (1 + `ORDER_REFERENCE_COMMISSION_RATE`), la tasa de referencia de `orders`, redondeado a 2 decimales con half-even. La comisión oficial es de MOD-07 (RF-43).
- **B11 (aprobación interna y conversión, RF-20 y RF-30):** el orden es: el Broker envía, el Investor acepta y el Broker registra su aprobación interna con evidencia. La aprobación crea la Order una sola vez mediante Order_Creation_Port, en nombre del Investor y en el estado Firmada por Comisionista (`BROKER_SIGNED`) de `orders`, que luego la envía o programa con sus reglas. La aceptación del Investor de una versión concreta con TOTP válido (B12) y la Trading_Authorization vigente sustituyen la autorización adicional de `POST /orders`; `orders` conserva todas sus demás validaciones (instrumento negociable, poder de compra, tenencia, límite diario). Esto exige que `orders` exponga en su capa de aplicación un caso de uso `create_from_proposal`, sin cambiar su contrato HTTP; se documenta como contrato nuevo entre módulos.
- **B12 (MFA en la aceptación):** aceptar una Proposal exige un código TOTP válido del Investor cuando el costo estimado alcanza el umbral de autorización adicional configurado en `orders`; por debajo del umbral no se exige.
- **B13 (exactamente una Order por propuesta):** la conversión usa el identificador de la Proposal como clave de idempotencia ante `orders`. Una Proposal `approved` tiene exactamente un `order_id`. Repetir la aprobación devuelve la misma Order. Si `orders` rechaza por regla de negocio, la Proposal pasa a `conversion_failed` con el código de error recibido. Si falla por indisponibilidad (Alpaca o base de datos), la aprobación no se registra, la Proposal sigue `accepted` y el Broker puede reintentar.
- **B14 (mensajes internos, punto abierto):** el mínimo de "mensajes internos" es un hilo por Proposal donde el Broker y el Investor de la Link publican Proposal_Messages de 1 a 1000 caracteres, inmutables. La evidencia de RF-20 es la lista de identificadores de Proposal_Messages del hilo más un texto opcional de hasta 1000 caracteres. Los comentarios de revisión de órdenes (RF-30) siguen siendo de `orders` (O6). No hay chat libre fuera de una Proposal.
- **B15 (perfil del comisionista):** `identity` guarda `firm_name` y `license_number`. `brokers` agrega un Broker_Profile editable por el propio Broker: especialidad (1 a 100 caracteres), años de experiencia (0 a 60), certificaciones (hasta 10, de 1 a 100 caracteres cada una) y descripción (hasta 1000 caracteres). Un Broker sin Broker_Profile aparece con esos campos vacíos.
- **B16 (sugerencias, RF-13):** las sugerencias son hasta 10 Brokers con rol vigente, ordenados por calificación promedio descendente (sin calificaciones al final), cantidad de reseñas descendente y nombre ascendente, excluyendo al Broker con el que el Investor tiene Link `requested` o `active`. La búsqueda por nombre es por subcadena sin distinguir mayúsculas, sobre nombre y `firm_name`, con 2 a 100 caracteres.
- **B17 (calificación, RF-22):** la calificación queda asociada a una Link que estuvo `active` (estado `active` o `ended`). Hay como máximo una Rating por Link; publicar de nuevo sobre la misma Link reemplaza estrellas y comentario y actualiza la fecha. Las estrellas son un entero de 1 a 5 y el comentario tiene hasta 1000 caracteres.
- **B18 (reputación, RF-23):** el promedio es la media aritmética de las estrellas de las Ratings del Broker con 2 decimales half-even, o null sin Ratings. Las señales de experiencia son: cantidad de Proposals convertidas en Order, cantidad de Investors distintos con alguna Link que llegó a `active`, años de experiencia del Broker_Profile y fecha de activación del Broker en `identity`.
- **B19 (historiales por periodo, RF-15 y RF-21):** el Period de RF-15 selecciona las Links cuyo intervalo [fecha de solicitud, fecha de fin o ahora] se solapa con el Period. El Period de RF-21 selecciona las Proposals por fecha de creación. Ambos aceptan filtro por estado y paginan por cursor.
- **B20 (terminación de la Link):** cuando una Link pasa a `ended`, la Trading_Authorization vigente se revoca, las Proposals `sent` y `accepted` pasan a `withdrawn` con motivo `link_ended` y `order_review_enabled` deja de aplicar. Las Orders ya creadas siguen su curso en `orders`.
- **B21 (notificaciones):** se usa el Notifier existente de `market_data` con dos tipos de evento nuevos en las preferencias de `identity`: `broker_link_updates` (solicitud, aceptación, declinación, expiración y fin de la Link, y cambios de Trading_Authorization) y `proposal_updates` (propuesta nueva, modificada, retirada, aceptada, rechazada, aprobada, fallida, expirada y mensaje nuevo), con `in_app` habilitado por defecto, igual que O15 de `orders`.
- **B22 (trazabilidad):** cada transición de Link, Trading_Authorization y Proposal se registra como evento inmutable con estado anterior, estado nuevo, actor, motivo y marca de tiempo. MOD-07 leerá esos eventos; la aprobación de RF-20 guarda su evidencia en el mismo registro, con el patrón de `admin_audit_log` de `identity`.
- **B23 (expiración):** la expiración de Links `requested` y Proposals `sent` se evalúa al leer o al intentar una transición y también en un job periódico (`BROKERS_EXPIRY_INTERVAL_SECONDS`, por defecto 300) que persiste el estado y notifica.
- **A1 (roles):** las acciones de Investor exigen rol `investor` vigente; las de Broker exigen rol `broker` vigente. Un usuario con ambos roles (activación de comisionista, tarea 24.1 de `identity`) no puede vincularse consigo mismo ni crearse propuestas. Los administradores no operan en este módulo; la supervisión es de MOD-07.
- **A2 (moneda):** todos los importes se expresan en USD, la moneda que Alpaca informa para la cuenta (W9 de `wallet`).
- **A3 (Linked_Account):** recibir y aceptar propuestas exige que el Investor tenga Linked_Account; solicitar vinculación no la exige.

### Política de pruebas

Por indicación del usuario, las pruebas no son obligatorias para todo el módulo. Son obligatorias solo para las partes críticas: la máquina de estados de la Link y la unicidad por Investor (Requisito 3 criterios 3–7, Requisito 4), la autorización del Broker sobre datos del Investor y la propiedad de recursos (Requisito 15 criterios 2–4, Requisito 16 criterios 1–3, Requisito 17 criterios 1–4), las transiciones de la Proposal y el control de versión (Requisito 8, Requisito 9 criterios 1–4), la conversión en Order exactamente una vez (Requisito 10 criterios 2–6), las reglas de la Trading_Authorization (Requisito 6 criterios 3–5) y las reglas de calificación y su agregación (Requisito 13, Requisito 14 criterios 2–3). Las demás pruebas son opcionales.

## Glossary

- **Backend_API**: la aplicación FastAPI de Acciones UD que expone los endpoints de este spec.
- **Directory_Service**: componente del módulo `brokers` que gestiona Broker_Profiles, sugerencias y búsqueda de Brokers.
- **Link_Service**: componente del módulo `brokers` que gestiona Links y Trading_Authorizations.
- **Link_State_Machine**: regla de dominio pura del módulo `brokers` que define las transiciones válidas de una Link según la decisión B1.
- **Proposal_Service**: componente del módulo `brokers` que gestiona Proposals, sus versiones, decisiones, aprobación y conversión.
- **Proposal_State_Machine**: regla de dominio pura del módulo `brokers` que define las transiciones válidas de una Proposal según la decisión B8.
- **Message_Service**: componente del módulo `brokers` que gestiona los Proposal_Messages.
- **Rating_Service**: componente del módulo `brokers` que gestiona Ratings y calcula la reputación.
- **Client_Service**: componente del módulo `brokers` que expone al Broker sus clientes vinculados y las órdenes de cada uno.
- **Expiry_Job**: tarea periódica del módulo `brokers` que expira Links `requested` y Proposals vencidas.
- **Broker_Link_Adapter**: adaptador de `brokers` que implementa Broker_Link_Port de `orders` y Broker_Client_Port de `portfolio`.
- **Broker_Link_Port**: puerto de salida de `orders` con `reviewing_broker`, `is_linked` y `linked_investors`, definido en `orders-mod-03` con adaptador por defecto Null_Broker_Link.
- **Broker_Client_Port**: puerto de salida de `portfolio` con `linked_investors` e `is_linked`, definido en `portfolio-mod-05` con adaptador por defecto Null_Broker_Client.
- **Order_Creation_Port**: puerto de salida de `brokers` que crea una Order de `orders` a partir de una Proposal aprobada, con clave de idempotencia.
- **Order_Query_Port**: puerto de salida de `brokers` que lee las Orders de un Investor desde `orders` sin modificarlas.
- **Quote_Port**: puerto de salida de `brokers` que obtiene la cotización vigente y el estado de negociación de un símbolo desde `market_data`.
- **Notifier**: componente existente de `market_data` que crea notificaciones y las despacha según las preferencias del usuario.
- **Investor**: usuario autenticado con el rol `investor` vigente.
- **Broker**: usuario autenticado con el rol `broker` vigente (comisionista).
- **Linked_Account**: registro de `kyc_accounts` del Investor con `alpaca_account_id` no nulo.
- **Broker_Profile**: datos públicos del Broker según la decisión B15.
- **Link**: vinculación entre un Investor y un Broker con estado, fechas de solicitud, respuesta y fin, consentimiento, `order_review_enabled` y motivo de fin.
- **Active_Link**: Link en estado `active` cuyo Broker tiene el rol `broker` vigente.
- **Trading_Authorization**: consentimiento del Investor para que las Proposals aprobadas de su Broker se conviertan en Orders a su nombre, según la decisión B6.
- **Proposal**: propuesta de operación de un Broker a un Investor con estado, versión vigente, `order_id` y fechas.
- **Proposal_Version**: contenido inmutable de una versión de Proposal: número, símbolo, lado, cantidad, tipo, precio límite, precio de referencia, costo estimado y fecha.
- **Proposal_Message**: mensaje inmutable del hilo de una Proposal con autor, texto y fecha.
- **Rating**: calificación de un Investor a un Broker asociada a una Link, con estrellas, comentario y fecha.
- **Order**: orden de `orders` definida en `orders-mod-03`.
- **Period**: intervalo de fechas `from` y `to` inclusivas en la zona horaria `America/New_York`.
- **Error_Body**: cuerpo JSON de error con los campos `code`, `message` y `details`, definido por `identity-market-backend`.

## Requirements

### Requirement 1: Perfil público del comisionista (soporte de RF-13 y RF-23)

**User Story:** Como Broker, quiero mantener mi especialidad, experiencia y certificaciones, para que los inversionistas me conozcan antes de vincularse.

#### Acceptance Criteria

1. WHEN un Broker actualiza su Broker_Profile con valores válidos según la decisión B15, THE Directory_Service SHALL guardar especialidad, años de experiencia, certificaciones y descripción y SHALL devolver el Broker_Profile actualizado.
2. IF un campo del Broker_Profile no cumple los límites de la decisión B15, THEN THE Backend_API SHALL responder 422 con el código `VALIDATION_ERROR` y el campo inválido en `details`.
3. WHEN cualquier usuario, autenticado o anónimo, consulta el perfil de un Broker con rol vigente, THE Directory_Service SHALL devolver nombre, `firm_name`, especialidad, años de experiencia, certificaciones, descripción y el resumen de reputación del Requisito 14.
4. IF el Broker consultado no existe o no tiene el rol `broker` vigente, THEN THE Backend_API SHALL responder 404 con el código `BROKER_NOT_FOUND`.
5. THE Directory_Service SHALL limitar la respuesta del perfil a los campos públicos del criterio 3, sin correo, teléfono, documento, otros datos personales ni lista de clientes.

### Requirement 2: Consultar comisionistas disponibles (RF-13, RFP-09)

**User Story:** Como Investor, quiero ver sugerencias de comisionistas o buscarlos por nombre, para elegir con quién vincularme.

#### Acceptance Criteria

1. WHEN un Investor solicita sugerencias, THE Directory_Service SHALL devolver hasta 10 Brokers ordenados según la decisión B16, cada uno con nombre, especialidad, años de experiencia, certificaciones, calificación promedio y cantidad de reseñas.
2. WHEN un Investor busca con un texto de 2 a 100 caracteres, THE Directory_Service SHALL devolver, paginados por cursor, los Brokers con rol vigente cuyo nombre o `firm_name` contiene el texto sin distinguir mayúsculas, con los mismos campos del criterio 1.
3. IF el texto de búsqueda tiene menos de 2 o más de 100 caracteres, THEN THE Backend_API SHALL responder 422 con el código `VALIDATION_ERROR`.
4. THE Directory_Service SHALL excluir de las sugerencias y de la búsqueda al propio usuario que consulta.

### Requirement 3: Solicitar y responder la vinculación (RF-13)

**User Story:** Como Investor, quiero solicitar la vinculación con un comisionista dejando mi consentimiento, para que pueda asesorarme; como Broker, quiero aceptar o declinar esa solicitud.

#### Acceptance Criteria

1. WHEN un Investor solicita la vinculación con un Broker existente con `consent_accepted` en true, THE Link_Service SHALL crear una Link en `requested` con el Investor, el Broker, la fecha de solicitud, la versión de consentimiento vigente y la marca de tiempo del consentimiento, y SHALL notificar al Broker con el tipo `broker_link_updates`.
2. IF la solicitud no trae `consent_accepted` en true, THEN THE Backend_API SHALL responder 422 con el código `CONSENT_REQUIRED`.
3. IF el Investor ya tiene una Link en `requested` o `active`, THEN THE Backend_API SHALL responder 409 con el código `LINK_ALREADY_EXISTS`.
4. IF el Broker indicado es el mismo usuario que solicita, THEN THE Backend_API SHALL responder 422 con el código `VALIDATION_ERROR`.
5. WHEN el Broker de una Link `requested` la acepta, THE Link_Service SHALL pasarla a `active`, registrar la fecha de inicio y notificar al Investor con el tipo `broker_link_updates`.
6. WHEN el Broker de una Link `requested` la declina con un motivo de 1 a 500 caracteres, THE Link_Service SHALL pasarla a `declined`, registrar el motivo y notificar al Investor.
7. WHEN el Investor cancela su Link `requested`, THE Link_Service SHALL pasarla a `canceled`.
8. WHEN una Link `requested` cumple `BROKER_LINK_REQUEST_TTL_DAYS` días desde la solicitud, THE Link_Service SHALL pasarla a `expired` y notificar al Investor.
9. IF una acción pide una transición que la Link_State_Machine no permite desde el estado actual, THEN THE Backend_API SHALL responder 409 con el código `INVALID_LINK_STATE` y el estado actual en `details`.
10. WHEN un Broker consulta sus solicitudes pendientes, THE Link_Service SHALL devolver las Links `requested` dirigidas a ese Broker con nombre del Investor y fecha de solicitud.

### Requirement 4: Desvincular comisionista (RF-14)

**User Story:** Como Investor, quiero desvincularme de mi comisionista indicando el motivo, para terminar la relación de forma explícita.

#### Acceptance Criteria

1. WHEN el Investor de una Active_Link solicita la desvinculación con un motivo de 1 a 500 caracteres y `confirmed` en true, THE Link_Service SHALL pasar la Link a `ended`, registrar la fecha de fin y el motivo y notificar al Broker con el tipo `broker_link_updates`.
2. IF la solicitud de desvinculación no trae `confirmed` en true, THEN THE Backend_API SHALL responder 422 con el código `CONFIRMATION_REQUIRED` sin modificar la Link.
3. WHEN una Link pasa a `ended`, THE Link_Service SHALL pasar las Proposals `sent` y `accepted` de esa Link a `withdrawn` con motivo `link_ended` y aplicar el resto de la decisión B20 en la misma transacción que termina la Link.
4. THE Link_Service SHALL conservar las Links terminadas y sus eventos sin borrarlos.
5. IF la Link que pasa a `ended` tiene una Trading_Authorization vigente, THEN THE Link_Service SHALL revocarla en la misma transacción que termina la Link.
6. IF la revocación de la Trading_Authorization vigente falla, THEN THE Link_Service SHALL rechazar la desvinculación completa y dejar sin cambios la Link, la Trading_Authorization y las Proposals.
7. WHEN la Link que pasa a `ended` no tiene una Trading_Authorization vigente, THE Link_Service SHALL terminar la Link sin error.

### Requirement 5: Historial de vinculaciones (RF-15)

**User Story:** Como Investor, quiero consultar el historial de mis vinculaciones por periodo y estado, para saber con quién he trabajado y por qué terminó.

#### Acceptance Criteria

1. WHEN un Investor consulta su historial de vinculaciones, THE Link_Service SHALL devolver sus Links con Broker, fecha de solicitud, fecha de inicio, fecha de fin, estado y motivo de fin cuando exista, ordenadas por fecha de solicitud descendente y paginadas por cursor.
2. WHERE la consulta incluye un Period, THE Link_Service SHALL devolver solo las Links seleccionadas según la decisión B19.
3. WHERE la consulta incluye un estado, THE Link_Service SHALL devolver solo las Links en ese estado.
4. IF `from` es posterior a `to` o el estado no es uno de la decisión B1, THEN THE Backend_API SHALL responder 422 con el código `VALIDATION_ERROR`.
5. WHEN un Investor consulta su vinculación vigente, THE Link_Service SHALL devolver la Link `requested` o `active`, su Trading_Authorization, `order_review_enabled` y `pending_broker_selection` según la decisión B5.
6. WHEN un Investor sin Link en `requested` o `active` consulta su vinculación vigente, THE Link_Service SHALL responder 200 con los campos de la Link y de la Trading_Authorization en null y `pending_broker_selection` calculado según la decisión B5.

### Requirement 6: Solicitud de comisionista y autorización para operar (RFP-09, RF-30)

**User Story:** Como Investor, quiero pedir un comisionista desde el registro o el perfil y decidir si puede generar órdenes por mí, para delegar con control.

#### Acceptance Criteria

1. WHILE `broker_requested` es true en `identity` y el Investor no tiene Link en `requested` o `active`, THE Link_Service SHALL devolver `pending_broker_selection` en true y las sugerencias del Requisito 2 en la consulta de vinculación vigente.
2. WHEN el Investor de una Active_Link otorga la Trading_Authorization con `consent_accepted` en true, THE Link_Service SHALL registrar la versión de consentimiento vigente y la fecha de otorgamiento y SHALL notificar al Broker con el tipo `broker_link_updates`.
3. IF el Investor otorga la Trading_Authorization sin Active_Link, THEN THE Backend_API SHALL responder 409 con el código `INVALID_LINK_STATE`.
4. WHEN el Investor revoca la Trading_Authorization vigente, THE Link_Service SHALL registrar la fecha de revocación y SHALL notificar al Broker.
5. THE Link_Service SHALL mantener como máximo una Trading_Authorization vigente por Link.
6. WHEN el Investor de una Active_Link cambia `order_review_enabled`, THE Link_Service SHALL guardar el valor nuevo y SHALL registrar el cambio como evento.

### Requirement 7: Crear y enviar propuesta (RF-16)

**User Story:** Como Broker, quiero crear y enviar una propuesta de operación a un cliente vinculado, para recomendarle una inversión concreta.

#### Acceptance Criteria

1. WHEN un Broker con Active_Link a un Investor con Linked_Account crea una Proposal con símbolo, lado, cantidad, tipo y precio límite válidos, THE Proposal_Service SHALL crear la Proposal en `sent` con la Proposal_Version 1, el precio de referencia y el costo estimado según la decisión B10, y SHALL notificar al Investor con el tipo `proposal_updates`.
2. IF el símbolo no existe o no es negociable según Quote_Port, THEN THE Backend_API SHALL responder 422 con el código `ASSET_NOT_TRADABLE`.
3. IF la cantidad no es mayor que cero, el lado no es `buy` o `sell`, el tipo no es `market` o `limit`, o una orden `limit` no trae precio límite mayor que cero, THEN THE Backend_API SHALL responder 422 con el código `VALIDATION_ERROR`.
4. IF la cotización vigente no está disponible para una Proposal `market`, THEN THE Backend_API SHALL responder 503 con el código `QUOTE_UNAVAILABLE`.
5. IF el Investor no tiene Linked_Account, THEN THE Backend_API SHALL responder 409 con el código `ACCOUNT_NOT_LINKED`.
6. THE Proposal_Service SHALL calcular el costo estimado como cantidad × precio de referencia × (1 + `ORDER_REFERENCE_COMMISSION_RATE`) redondeado a 2 decimales con half-even.

### Requirement 8: Modificar y retirar propuesta (RF-17, RF-18)

**User Story:** Como Broker, quiero modificar una propuesta no aprobada o retirarla con un motivo, para corregirla o cancelarla antes de que se ejecute.

#### Acceptance Criteria

1. WHEN el Broker autor modifica una Proposal en `sent` o `accepted` indicando la versión vigente, THE Proposal_Service SHALL crear una Proposal_Version con el número siguiente, recalcular precio de referencia y costo estimado, dejar la Proposal en `sent`, anular la aceptación previa y notificar al Investor con el tipo `proposal_updates`.
2. THE Proposal_Service SHALL conservar sin cambios todas las Proposal_Versions anteriores.
3. WHEN el Broker autor retira una Proposal en `sent` o `accepted` con un motivo de 1 a 500 caracteres, `confirmed` en true y la versión vigente, THE Proposal_Service SHALL pasarla a `withdrawn`, registrar el motivo y notificar al Investor.
4. IF la versión indicada no es la vigente, THEN THE Backend_API SHALL responder 409 con el código `PROPOSAL_VERSION_CONFLICT` y la versión vigente en `details`.
5. IF una acción pide una transición que la Proposal_State_Machine no permite desde el estado actual, THEN THE Backend_API SHALL responder 409 con el código `INVALID_PROPOSAL_STATE` y el estado actual en `details`.
6. WHEN una Proposal en `sent` cumple `PROPOSAL_TTL_HOURS` horas desde su última Proposal_Version, THE Proposal_Service SHALL pasarla a `expired` y notificar al Broker y al Investor; una Proposal en `accepted` queda excluida de la expiración automática.

### Requirement 9: Aceptar o rechazar propuesta (RF-19)

**User Story:** Como Investor, quiero aceptar o rechazar una propuesta con un comentario, para decidir sobre cada recomendación de mi comisionista.

#### Acceptance Criteria

1. WHEN el Investor destinatario acepta una Proposal en `sent` indicando la versión vigente, THE Proposal_Service SHALL pasarla a `accepted` y registrar la decisión, la versión aceptada, el comentario de hasta 500 caracteres y la fecha de decisión.
2. WHEN el Investor destinatario rechaza una Proposal en `sent` indicando la versión vigente, THE Proposal_Service SHALL pasarla a `rejected` y registrar la decisión, el comentario de hasta 500 caracteres y la fecha de decisión.
3. IF el costo estimado alcanza el umbral de autorización adicional de `orders` y la aceptación no trae un código TOTP válido del Investor, THEN THE Backend_API SHALL responder 401 con el código `EXTRA_AUTHORIZATION_INVALID` sin modificar la Proposal.
4. IF la versión indicada no es la vigente, THEN THE Backend_API SHALL responder 409 con el código `PROPOSAL_VERSION_CONFLICT`.
5. WHEN el Investor registra su decisión, THE Proposal_Service SHALL notificar al Broker con el tipo `proposal_updates`.

### Requirement 10: Aprobación interna y conversión en orden (RF-20, RF-30)

**User Story:** Como Broker, quiero registrar mi aprobación interna de una propuesta aceptada con evidencia de la interacción, para que se convierta en una orden del cliente.

#### Acceptance Criteria

1. WHEN el Broker autor registra su decisión sobre una Proposal `accepted` con la versión vigente, THE Proposal_Service SHALL registrar la Proposal, el Broker, la decisión (`approve` o `decline`), la fecha y la evidencia según la decisión B14.
2. WHEN la decisión es `approve` y la Link tiene Trading_Authorization vigente, THE Proposal_Service SHALL crear la Order mediante Order_Creation_Port con la Proposal_Version aceptada, en nombre del Investor, en estado Firmada por Comisionista y con el identificador de la Proposal como clave de idempotencia, y SHALL pasar la Proposal a `approved` con el `order_id` en la misma transacción.
3. IF la decisión es `approve` y la Link no tiene Trading_Authorization vigente, THEN THE Backend_API SHALL responder 409 con el código `TRADING_AUTHORIZATION_REQUIRED` sin modificar la Proposal.
4. WHEN el Broker repite la aprobación de una Proposal `approved`, THE Proposal_Service SHALL devolver la misma Order sin crear otra.
5. IF `orders` rechaza la creación por una regla de negocio, THEN THE Proposal_Service SHALL pasar la Proposal a `conversion_failed`, registrar el código de error recibido y notificar al Broker y al Investor.
6. IF la creación falla porque Alpaca o la base de datos no están disponibles, THEN THE Backend_API SHALL responder con el error clasificado (502 `ALPACA_UNAVAILABLE`, 503 `ALPACA_RATE_LIMITED` o 503 `DATABASE_UNAVAILABLE`) y la Proposal SHALL quedar en `accepted`.
7. WHEN la decisión es `decline`, THE Proposal_Service SHALL pasar la Proposal a `declined_by_broker` y notificar al Investor.
8. IF un identificador de evidencia no corresponde a un Proposal_Message del hilo de esa Proposal, THEN THE Backend_API SHALL responder 422 con el código `VALIDATION_ERROR`.

### Requirement 11: Mensajes internos de la propuesta (RF-20)

**User Story:** Como Broker o Investor, quiero intercambiar mensajes dentro de una propuesta, para dejar evidencia de la interacción que respalda la aprobación.

#### Acceptance Criteria

1. WHEN el Broker o el Investor de una Proposal con Active_Link publica un mensaje de 1 a 1000 caracteres, THE Message_Service SHALL guardar un Proposal_Message inmutable con autor, texto y fecha y SHALL notificar a la otra parte con el tipo `proposal_updates`.
2. WHEN el Broker o el Investor consulta el hilo de una Proposal, THE Message_Service SHALL devolver los Proposal_Messages en orden cronológico ascendente, paginados por cursor.
3. IF el texto está vacío o supera 1000 caracteres, THEN THE Backend_API SHALL responder 422 con el código `VALIDATION_ERROR`.

### Requirement 12: Historial de propuestas (RF-21)

**User Story:** Como Investor o Broker, quiero consultar el historial de propuestas por periodo y estado, para revisar qué se propuso y qué se decidió.

#### Acceptance Criteria

1. WHEN un Investor consulta su historial de propuestas, THE Proposal_Service SHALL devolver sus Proposals con Broker, instrumento, lado, importe estimado, número de versión vigente, estado y fechas, ordenadas por fecha de creación descendente y paginadas por cursor.
2. WHEN un Broker consulta su historial de propuestas, THE Proposal_Service SHALL devolver solo las Proposals que creó para Investors con Active_Link, con los mismos campos del criterio 1 y el Investor en lugar del Broker.
3. WHERE la consulta incluye un Period o un estado, THE Proposal_Service SHALL filtrar según la decisión B19.
4. WHEN el Investor o el Broker de una Proposal consulta su detalle, THE Proposal_Service SHALL devolver todas sus Proposal_Versions, decisiones y `order_id` cuando exista.

### Requirement 13: Publicar calificación (RF-22)

**User Story:** Como Investor, quiero calificar con estrellas a un comisionista con el que trabajé, para orientar a otros inversionistas.

#### Acceptance Criteria

1. WHEN un Investor publica una Rating de 1 a 5 estrellas con un comentario de hasta 1000 caracteres sobre un Broker con el que tiene una Link `active` o `ended`, THE Rating_Service SHALL guardar la Rating asociada a esa Link con la valoración, el comentario y la fecha.
2. WHEN el Investor publica de nuevo sobre la misma Link, THE Rating_Service SHALL reemplazar estrellas y comentario de la Rating existente y actualizar su fecha, manteniendo una sola Rating por Link.
3. IF el Investor no tiene una Link `active` o `ended` con ese Broker, THEN THE Backend_API SHALL responder 409 con el código `RATING_NOT_ALLOWED`.
4. IF las estrellas no son un entero de 1 a 5 o el comentario supera 1000 caracteres, THEN THE Backend_API SHALL responder 422 con el código `VALIDATION_ERROR`.

### Requirement 14: Consultar reputación y reseñas (RF-23)

**User Story:** Como Investor, quiero ver la reputación y las reseñas de un comisionista, para decidir si me vinculo con él.

#### Acceptance Criteria

1. WHEN un usuario autenticado consulta la reputación de un Broker, THE Rating_Service SHALL devolver nombre, calificación promedio, cantidad de reseñas y las señales de experiencia de la decisión B18.
2. THE Rating_Service SHALL calcular la calificación promedio como la media aritmética de las estrellas de todas las Ratings del Broker con 2 decimales half-even, y SHALL devolver null cuando el Broker no tiene Ratings.
3. THE Rating_Service SHALL contar una sola Rating por Link en la cantidad de reseñas y en el promedio.
4. WHEN un usuario autenticado consulta las reseñas de un Broker, THE Rating_Service SHALL devolver estrellas, comentario y fecha de cada Rating, ordenadas por fecha descendente y paginadas por cursor.

### Requirement 15: Clientes asignados, portafolio y órdenes (RFP-05, RFP-04)

**User Story:** Como Broker, quiero ver mis clientes vinculados con su portafolio y sus órdenes, y solo los míos, para asesorarlos.

#### Acceptance Criteria

1. WHEN un Broker consulta sus clientes, THE Client_Service SHALL devolver los Investors con Active_Link a ese Broker con nombre, fecha de inicio de la Link, estado de la Trading_Authorization y `order_review_enabled`.
2. WHEN un Broker consulta las órdenes de un Investor con Active_Link, THE Client_Service SHALL devolver las Orders del Investor leídas mediante Order_Query_Port con los mismos filtros y paginación de `GET /orders`.
3. IF el Investor consultado no tiene Active_Link con el Broker, THEN THE Backend_API SHALL responder 404 con el código `CLIENT_NOT_FOUND`.
4. THE Broker_Link_Adapter SHALL ser la única fuente de pertenencia Broker–Investor que usan los endpoints de comisionista de `portfolio` (`/portfolio/broker/...`) y de `orders` (`/broker/order-reviews...`), de modo que el portafolio del cliente se consulta en `portfolio` sin duplicar endpoints.

### Requirement 16: Contratos con orders, portfolio e identity

**User Story:** Como desarrollador del backend, quiero que MOD-06 sustituya los adaptadores nulos de los módulos previos, para activar la revisión de órdenes, los reportes de comisionista y el comisionista asociado sin cambiar sus contratos HTTP.

#### Acceptance Criteria

1. THE Broker_Link_Adapter SHALL implementar `linked_investors(broker_id)` devolviendo los Investors con Active_Link al Broker, e `is_linked(broker_id, investor_id)` devolviendo true solo con Active_Link entre ambos.
2. THE Broker_Link_Adapter SHALL implementar `reviewing_broker(investor_id)` según la decisión B7.
3. WHEN la aplicación se registra, THE Backend_API SHALL instalar el mismo Broker_Link_Adapter en `app.state.order_broker_link` y en `app.state.portfolio_broker_clients` antes de `orders.startup` y `portfolio.startup`.
4. WHEN un Investor consulta `/users/me`, THE Backend_API SHALL devolver en `associated_broker` el identificador, nombre, `firm_name` y fecha de inicio del Broker de su Active_Link, o null sin Active_Link, mediante un puerto de `identity` cuyo adaptador provee `brokers`.
5. THE Order_Creation_Port SHALL invocar el caso de uso `create_from_proposal` de la capa de aplicación de `orders` según la decisión B11, sin endpoints HTTP nuevos en `orders`.

### Requirement 17: Autorización, propiedad y trazabilidad (RFP-04)

**User Story:** Como Investor, quiero que cada comisionista solo vea y gestione la información de sus clientes vinculados, para proteger mis datos.

#### Acceptance Criteria

1. THE Backend_API SHALL evaluar la pertenencia Broker–Investor en cada caso de uso de Broker de este módulo según la decisión B4.
2. IF un Broker accede a una Link, Proposal, Proposal_Message o cliente sin Active_Link con el Investor correspondiente, THEN THE Backend_API SHALL responder 404 con el código del recurso (`LINK_NOT_FOUND`, `PROPOSAL_NOT_FOUND` o `CLIENT_NOT_FOUND`).
3. IF un Investor accede a una Link, Proposal o Proposal_Message de otro Investor, THEN THE Backend_API SHALL responder 404 con el código del recurso.
4. IF el usuario no tiene el rol requerido por la decisión A1, THEN THE Backend_API SHALL responder 403 con el código `FORBIDDEN`; sin sesión válida SHALL responder 401, excepto en la consulta del perfil del Broker (Requisito 1 criterio 3), que es pública.
5. WHEN una Link, Trading_Authorization o Proposal cambia de estado, THE Backend_API SHALL registrar un evento inmutable con estado anterior, estado nuevo, actor, motivo y marca de tiempo según la decisión B22.

### Requirement 18: Notificaciones, configuración, errores y contrato OpenAPI

**User Story:** Como equipo de frontend, quiero un contrato estable con errores y notificaciones declaradas, para integrar el portal de comisionistas sin ambigüedades.

#### Acceptance Criteria

1. THE Backend_API SHALL agregar los tipos de evento `broker_link_updates` y `proposal_updates` a las preferencias de notificación de `identity` con el canal `in_app` habilitado por defecto.
2. THE Backend_API SHALL leer `BROKER_LINK_REQUEST_TTL_DAYS`, `PROPOSAL_TTL_HOURS`, `BROKER_LINK_CONSENT_VERSION`, `BROKER_TRADING_CONSENT_VERSION` y `BROKERS_EXPIRY_INTERVAL_SECONDS` desde `Settings`, con los valores por defecto de este spec.
3. IF la base de datos no está disponible, THEN THE Backend_API SHALL responder 503 con el código `DATABASE_UNAVAILABLE`.
4. THE Backend_API SHALL responder todo error con un Error_Body sin secretos ni datos de otros usuarios.
5. THE Backend_API SHALL declarar en el contrato OpenAPI los schemas de request, de response y de cada respuesta de error de cada endpoint de este módulo.
6. WHEN el Expiry_Job se ejecuta, THE Expiry_Job SHALL expirar en la misma ejecución las Links `requested` vencidas y las Proposals `sent` vencidas según la decisión B23 y SHALL enviar una notificación por cada transición de ambas categorías.
7. THE Backend_API SHALL exigir sesión válida en todos los endpoints de este módulo excepto la consulta del perfil del Broker (Requisito 1 criterio 3), que es pública.
