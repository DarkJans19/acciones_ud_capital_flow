# Requirements Document

## Introduction

Este spec cubre el módulo de desarrollo MOD-03 "Motor de Órdenes y Negociación Bursátil" del backend de Acciones UD (responsable: Juan José León Gómez). El módulo se implementa como el paquete `orders` dentro del monolito modular hexagonal (`src/acciones_ud/orders/`). Depende de MOD-01 (`identity`) y MOD-02 (`market_data`), ya implementados en `identity-market-backend`, y de MOD-04 (`wallet`, spec `wallet-mod-04`). Por eso se construye después de MOD-04 y antes de MOD-05, según el orden del catálogo (MOD-04 → MOD-03 → MOD-05 → MOD-06 → MOD-07).

Las órdenes se envían a Alpaca Broker API sandbox. El módulo no construye un motor de calce interno ni un libro de órdenes propio (Marco de la especificación).

Alcance trazable (los textos originales están en `.kiro/steering/requerimientos-proyecto.md`, sección MOD-03):

- RF-29: crear orden bursátil y validar sus parámetros (Requisitos 1 y 2).
- RF-30: validaciones previas al envío, autorización adicional y revisión con el comisionista (Requisitos 3, 4 y 5).
- RF-34: reserva de saldo y tenencia (Requisito 6) y cancelación de orden (Requisito 12).
- RF-31: ratificar nueva cotización (Requisito 7).
- RF-32: enviar la orden al bróker con idempotencia, registrar actualizaciones y ejecuciones, y estados de orden (Requisitos 8, 9 y 10).
- RF-33: consultar seguimiento y notificar la ejecución (Requisito 11).
- RF-35: programar orden fuera de horario (Requisito 13).
- RFP-10: estados de orden y paso a En Revisión ante un cambio de horario (Requisitos 10 y 14), obligatorio por la Decisión R1.
- Requisitos transversales de autorización, propiedad, configuración, errores y contrato OpenAPI (Requisito 15).

Fuera de alcance: modificación (replace) de órdenes ya enviadas a Alpaca; órdenes en horario extendido; venta en corto; órdenes por importe (`notional`); creación de órdenes por el comisionista a partir de propuestas (RF-16 a RF-20, MOD-06); cálculo, cotización y consulta oficial de comisiones (RF-43, MOD-07); parametrización de horarios y tarifas (RF-46, MOD-07); posiciones e histórico de portafolio (MOD-05); RFP-06 y RFP-07 (descartados por las Decisiones R2 y R3).

### Decisiones y supuestos del módulo

Cada punto abierto del catálogo para MOD-03 queda resuelto aquí como decisión (O) o supuesto (A).

- **O1 (tipos de orden, punto abierto de Stop Loss, Take Profit y trailing stop):** se admiten los tipos que Alpaca Broker API ofrece y que coinciden con los valores de `default_order_type` de `identity`: `market`, `limit`, `stop`, `stop_limit` y `trailing_stop`. "Stop Loss" se representa con `stop` o con la pierna `stop_loss` de una orden `bracket`; "Take Profit" se representa con `limit` o con la pierna `take_profit` de una orden `bracket`. Las clases de orden admitidas son `simple` y `bracket`; `oco` y `oto` quedan fuera. Las vigencias admitidas son `day`, `gtc`, `ioc` y `fok`; `opg`, `cls` y el horario extendido quedan fuera. Las combinaciones exactas se confirman en el diseño contra la documentación de Broker API.
- **O2 (fracciones):** se admiten cantidades fraccionarias solo si el instrumento es `fractionable` en el catálogo de `market_data`, la clase es `simple`, el tipo es `market`, `limit`, `stop` o `stop_limit` y la vigencia es `day`. Las órdenes por importe (`notional`) quedan fuera; la orden siempre indica cantidad.
- **O3 (tenencia al vender, punto abierto "al menos 1 acción"):** la posición disponible se consulta en Alpaca Broker API (`qty_available` de la posición del símbolo) mediante un puerto propio de `orders` (Position_Port). Cuando MOD-05 exista, podrá proveer otro adaptador del mismo puerto. Una venta exige `qty_available` mayor que cero y mayor o igual que la cantidad de la orden más las acciones ya reservadas por otras órdenes locales del mismo símbolo. No hay venta en corto.
- **O4 (confirmación en 5 segundos, punto abierto):** se mide la respuesta propia del Backend_API a la solicitud de creación de una orden con mercado abierto, que incluye el acuse de Alpaca. La llamada de envío a Alpaca tiene un límite de 4 segundos. Si Alpaca no responde en ese límite, la orden queda Enviada sin identificador externo y el Order_Reconciler la resuelve por su Client_Order_Id. La confirmación de operación al usuario (RF-32) es la ejecución efectiva y no esta respuesta.
- **O5 (mapeo de estados, punto abierto):** se conservan los diez estados del enunciado (RFP-10) con códigos internos: Pendiente `PENDING`, Enviada `SUBMITTED`, Firmada por Comisionista `BROKER_SIGNED`, En Ejecución `EXECUTING`, Cancelada `CANCELED`, Rechazada `REJECTED`, Expirada `EXPIRED`, En Revisión `IN_REVIEW`, Fallida `FAILED` y Detenida `HELD`. El enunciado no define un estado "Ejecutada": una orden completamente ejecutada permanece en En Ejecución con `fully_filled` en true y es terminal. Detenida es un estado local que significa "a la espera de nueva autorización por cambio de precio"; los estados de Alpaca `held`, `stopped` y `suspended` se mapean a Enviada conservando el estado del proveedor. El mapeo completo está en el Requisito 10.
- **O6 (revisión con el comisionista sin MOD-06, punto abierto):** `orders` define el puerto Broker_Link_Port, que responde si un Investor tiene un Broker vinculado con revisión de órdenes habilitada y si un Broker está vinculado a un Investor. `orders` implementa ya los casos de uso y endpoints de revisión (cola de revisión, devolver para ajustes y aprobar) autorizados al rol `broker`. Mientras MOD-06 no exista, el adaptador por defecto (Null_Broker_Link) responde que no hay vínculos: toda orden sigue el flujo directo del Investor y los endpoints de revisión devuelven listas vacías o `ORDER_NOT_FOUND`. MOD-06 solo sustituye el adaptador, sin cambiar el contrato HTTP de `orders`. Los mensajes internos de la revisión se registran como comentarios de la orden; la mensajería general entre usuarios es de MOD-06.
- **O7 (reserva de saldo, RF-34, decisión W11 diferida desde `wallet-mod-04`):** `orders` mantiene una Reservation local por orden mientras la orden no ha sido enviada a Alpaca: importe estimado en USD para compras y cantidad de acciones para ventas. El Available_Buying_Power es el `buying_power` que `wallet` obtiene de Alpaca menos las Reservations activas del Investor. Cuando Alpaca acusa recibo de la orden y se registra su identificador externo, la Reservation se marca `transferred`, porque desde ese momento Alpaca descuenta la orden abierta de su propio `buying_power`. Cancelada, Rechazada, Expirada y Fallida de una orden sin identificador externo liberan la Reservation (`released`). `wallet` no cambia.
- **O8 (precio de referencia y comisión estimada):** el Reference_Price es el precio de la cotización vigente que devuelve `market_data` para el símbolo. La estimación de una compra incluye una comisión de referencia del 2 % configurable (`ORDER_REFERENCE_COMMISSION_RATE`), tomada de la tarifa base del catálogo. Esta comisión solo sirve para estimar y reservar; el cálculo oficial es de MOD-07 (RF-43). Alpaca sandbox no cobra esa comisión.
- **O9 (controles de `identity`, RF-09):** `orders` lee mediante un puerto los controles existentes `default_order_type`, `daily_order_limit`, `high_order_threshold_usd` y `extra_confirmation`, sin almacenarlos de nuevo. El límite diario cuenta las órdenes creadas por el Investor en el día calendario de la zona horaria `America/New_York`, que es la del mercado.
- **O10 (autorización adicional, RF-30):** una orden cuyo Estimated_Amount supera `high_order_threshold_usd` exige autorización adicional. Si `extra_confirmation` es true, la autorización es un código TOTP válido del Investor verificado mediante un puerto hacia `identity`. Si `extra_confirmation` es false, la autorización es el campo `high_amount_acknowledged` en true.
- **O11 (nueva cotización, RF-31):** la nueva autorización se exige solo para órdenes `market` que esperaron antes del envío (programadas o en revisión), cuando el precio vigente al momento de enviar difiere del Reference_Price registrado en más del umbral configurable `ORDER_REAUTH_PRICE_DEVIATION_PCT` (por defecto 1.00 %). Las órdenes con precio límite o stop ya acotan el precio y no requieren nueva autorización. La ventana de respuesta es configurable (`ORDER_REAUTH_WINDOW_MINUTES`, por defecto 30).
- **O12 (actualizaciones de Alpaca, RF-32):** igual que la decisión W3 de `wallet`, las actualizaciones y ejecuciones se obtienen por consulta periódica (Order_Reconciler) de las órdenes no terminales y de las actividades `FILL`, no por el stream SSE de eventos.
- **O13 (programación fuera de horario, RF-35):** con el mercado cerrado, `orders` no envía la orden a Alpaca; la guarda programada para la próxima apertura que informa el calendario de `market_data` y la envía el Order_Scheduler. No se usa la cola propia de Alpaca para órdenes fuera de horario.
- **O14 (cambio de horario, RFP-10):** la parametrización de horarios es de MOD-07 (RF-46) y hoy los horarios son datos semilla. `orders` expone el puerto de entrada Schedule_Change_Port que MOD-07 invocará; mientras tanto, el puerto se prueba en la capa de aplicación y no tiene endpoint HTTP propio.
- **O15 (notificaciones, RF-33 y RF-07):** se usan el Notifier existente de `market_data` y dos tipos de evento nuevos en las preferencias de notificación de `identity`: `order_executions` (ejecuciones) y `order_updates` (nueva autorización, devolución, revisión por cambio de horario, rechazo, fallo y expiración), con el canal `in_app` habilitado por defecto como los demás tipos. El aviso de cambio de saldo por `FILL` sigue siendo de `wallet` (W10).
- **O16 (idempotencia):** la creación de órdenes exige el encabezado `Idempotency-Key`, igual que la decisión W12 de `wallet`. Cada orden envía a Alpaca un Client_Order_Id igual a su identificador local, de modo que un reintento del envío nunca crea dos órdenes en Alpaca.
- **O17 (antigüedad máxima local):** una orden no enviada a Alpaca (Pendiente, En Revisión, Firmada por Comisionista o Detenida) que supera `ORDER_LOCAL_MAX_AGE_DAYS` (por defecto 5) pasa a Expirada y libera su Reservation. Una orden programada con vigencia `day` que no se envía durante su sesión prevista también pasa a Expirada.
- **A1 (rol):** crear, confirmar, cancelar y consultar órdenes está disponible para usuarios con rol `investor` vigente y Active_Account. Las acciones de revisión están disponibles para usuarios con rol `broker` vigente. Los administradores no operan órdenes en este módulo; la supervisión es de MOD-07.
- **A2 (moneda):** todas las órdenes y estimaciones se expresan en USD, la moneda que Alpaca informa para la cuenta (W9 de `wallet`).

### Política de pruebas

Por indicación del usuario, las pruebas no son obligatorias para todo el módulo. Son obligatorias solo para las partes críticas: validación de cantidad, precio, tipo y vigencia (Requisito 2), invariantes de reserva y liberación de saldo y tenencia (Requisito 6 y Requisito 12 criterios 2 y 6), nueva autorización por cambio de precio (Requisito 7 criterios 1 a 5), idempotencia del envío de órdenes y de las ejecuciones (Requisito 8 criterios 2 a 5 y Requisito 9 criterio 3), transiciones de la máquina de estados (Requisito 10) y autorización y propiedad de recursos (Requisito 15 criterios 1 a 3). Las propiedades de la máquina de estados, de las reservas y de la validación se prueban con `hypothesis`. Las demás pruebas son opcionales.

## Glossary

- **Backend_API**: la aplicación FastAPI de Acciones UD que expone los endpoints de este spec.
- **Order_Service**: componente del módulo `orders` que valida, crea, confirma, cancela y consulta Orders.
- **Order_Validator**: regla de dominio pura del módulo `orders` que valida los parámetros de una Order.
- **Order_State_Machine**: regla de dominio pura del módulo `orders` que define los Order_Status y sus transiciones permitidas.
- **Reservation_Ledger**: componente del módulo `orders` que crea, transfiere y libera Reservations.
- **Review_Service**: componente del módulo `orders` que gestiona la revisión de Orders por el Broker.
- **Order_Submitter**: componente del módulo `orders` que envía Orders a Alpaca_Broker_API.
- **Order_Reconciler**: tarea periódica del módulo `orders` que consulta en Alpaca_Broker_API el estado de las Orders enviadas no terminales y las actividades `FILL` nuevas.
- **Order_Scheduler**: tarea periódica del módulo `orders` que envía las Orders programadas cuando abre la sesión elegible.
- **Broker_Link_Port**: puerto de salida de `orders` que informa los vínculos Investor–Broker; su adaptador por defecto es Null_Broker_Link.
- **Null_Broker_Link**: adaptador de Broker_Link_Port que responde que ningún Investor tiene Broker vinculado.
- **Position_Port**: puerto de salida de `orders` que devuelve la posición disponible (`qty_available`) de un símbolo en la cuenta Alpaca del Investor.
- **Schedule_Change_Port**: puerto de entrada de `orders` que recibe la notificación de un cambio de horario de un mercado.
- **Notifier**: componente existente de `market_data` que crea notificaciones y las despacha según las preferencias del usuario.
- **Alpaca_Broker_API**: Alpaca Broker API en entorno sandbox.
- **Investor**: usuario autenticado con el rol `investor` vigente.
- **Broker**: usuario autenticado con el rol `broker` vigente (comisionista).
- **Active_Account**: registro de `kyc_accounts` del Investor con `alpaca_account_id` no nulo y último estado conocido `ACTIVE`.
- **Order**: registro local de una orden con identificador, Investor, símbolo, lado (`buy` o `sell`), cantidad, tipo, clase, vigencia, precios aplicables, Reference_Price, Estimated_Amount, Order_Status, estado del proveedor, identificador externo de Alpaca, Client_Order_Id, Idempotency_Key, cantidad ejecutada, precio promedio de ejecución, `fully_filled`, `scheduled_for` y marcas de tiempo.
- **Order_Leg**: pierna `take_profit` o `stop_loss` de una Order `bracket`, con su identificador externo, precio y estado del proveedor.
- **Order_Status**: uno de los diez estados del Requisito 10.
- **Terminal_Order**: Order en Cancelada, Rechazada, Expirada o Fallida, o en En Ejecución con `fully_filled` en true.
- **Unsent_Order**: Order en Pendiente, En Revisión, Firmada por Comisionista o Detenida, sin identificador externo ni envío a Alpaca.
- **Order_Event**: registro inmutable de una transición de Order_Status con estado anterior, estado nuevo, causa, actor y marca de tiempo.
- **Execution**: registro de una ejecución de una Order con identificador de ejecución de Alpaca, cantidad, precio, marca de tiempo de ejecución y marca de tiempo de registro.
- **Reservation**: registro local asociado a una Order con importe en USD (compra) o cantidad de acciones (venta) y estado `active`, `transferred` o `released`.
- **Reference_Price**: precio de la cotización vigente del símbolo devuelta por `market_data` en el momento de crear la Order o de aceptar una nueva autorización.
- **Estimated_Amount**: importe estimado en USD de una Order, calculado como cantidad × precio base × (1 + tasa de comisión de referencia) para compras y cantidad × precio base para ventas; el precio base es `limit_price` en `limit` y `stop_limit`, `stop_price` en `stop` y el Reference_Price en `market` y `trailing_stop`.
- **Available_Buying_Power**: `buying_power` de la cuenta Alpaca obtenido mediante el puerto de `wallet`, menos la suma de las Reservations `active` en USD del Investor.
- **Order_Controls**: controles de órdenes de `identity` (`default_order_type`, `daily_order_limit`, `high_order_threshold_usd`, `extra_confirmation`).
- **Reauthorization_Request**: solicitud de nueva autorización de una Order con precio anterior, precio actualizado, fecha límite, decisión del Investor e instante de respuesta.
- **Client_Order_Id**: identificador que `orders` envía a Alpaca_Broker_API en `client_order_id`, igual al identificador local de la Order.
- **Idempotency_Key**: valor del encabezado `Idempotency-Key`, de 8 a 128 caracteres imprimibles ASCII, único por Investor.
- **Error_Body**: cuerpo JSON de error con los campos `code`, `message` y `details`, definido por `identity-market-backend`.

## Requirements

### Requirement 1: Crear orden bursátil (RF-29)

**User Story:** Como Investor, quiero crear una orden de compra o venta para un activo negociable, para invertir desde mi cuenta Alpaca.

#### Acceptance Criteria

1. WHEN un Investor con Active_Account envía una solicitud de orden válida con símbolo, lado, cantidad, tipo, clase, vigencia, precios aplicables, Idempotency_Key y confirmación explícita (`confirmed` en true), THE Order_Service SHALL crear la Order, registrar el Reference_Price, el Estimated_Amount y el primer Order_Event, y devolver HTTP 201 con la Order.
2. WHEN la solicitud de orden omite el tipo, THE Order_Service SHALL usar el `default_order_type` de las Order_Controls del Investor.
3. IF la solicitud de orden tiene `confirmed` distinto de true, THEN THE Order_Service SHALL responder HTTP 422 con un Error_Body de código `VALIDATION_ERROR` que nombre el campo `confirmed` y SHALL omitir la creación de la Order.
4. WHEN un Investor solicita una vista previa de orden con los mismos parámetros, THE Order_Service SHALL devolver el Reference_Price, el Estimated_Amount, la comisión de referencia, el Available_Buying_Power, si se exige autorización adicional y si el mercado está abierto, sin crear Order ni Reservation.
5. IF un Investor sin Active_Account solicita crear una orden, THEN THE Order_Service SHALL responder HTTP 409 con un Error_Body de código `ORDER_ACCOUNT_NOT_ACTIVE` y SHALL omitir toda llamada a Alpaca_Broker_API.
6. IF la cotización vigente del símbolo no está disponible en `market_data`, THEN THE Order_Service SHALL responder HTTP 503 con un Error_Body de código `QUOTE_UNAVAILABLE` y SHALL omitir la creación de la Order.

### Requirement 2: Validar parámetros de la orden (RF-29, RF-30)

**User Story:** Como Investor, quiero que el sistema rechace parámetros de orden inválidos antes de enviarla, para no generar órdenes que Alpaca no admita.

#### Acceptance Criteria

1. THE Order_Validator SHALL aceptar como lado solo `buy` o `sell`, como tipo solo `market`, `limit`, `stop`, `stop_limit` o `trailing_stop`, como clase solo `simple` o `bracket` y como vigencia solo `day`, `gtc`, `ioc` o `fok`.
2. THE Order_Validator SHALL exigir una cantidad decimal mayor que cero con un máximo de 9 decimales, y SHALL exigir una cantidad entera cuando la Order no cumple las condiciones de fracción de la decisión O2.
3. THE Order_Validator SHALL exigir `limit_price` en `limit` y `stop_limit`, `stop_price` en `stop` y `stop_limit`, y exactamente uno de `trail_percent` o `trail_price` en `trailing_stop`, y SHALL rechazar cualquier precio no aplicable al tipo.
4. THE Order_Validator SHALL exigir que cada precio sea mayor que cero, con un máximo de 2 decimales cuando el precio es mayor o igual que 1.00 y de 4 decimales cuando es menor que 1.00, y que `trail_percent` esté entre 0.1 y 50.0.
5. THE Order_Validator SHALL exigir la vigencia `day` o `gtc` en `trailing_stop` y en la clase `bracket`.
6. WHERE la clase es `bracket`, THE Order_Validator SHALL exigir lado `buy`, tipo `market` o `limit`, cantidad entera, `take_profit.limit_price` mayor o igual que el precio base más 0.01 y `stop_loss.stop_price` menor o igual que el precio base menos 0.01.
7. IF el símbolo no existe en el catálogo de `market_data`, no está activo o no es negociable, THEN THE Order_Service SHALL responder HTTP 422 con un Error_Body de código `ASSET_NOT_TRADABLE` y SHALL omitir la creación de la Order.
8. IF algún parámetro incumple los criterios 1 a 6, THEN THE Order_Service SHALL responder HTTP 422 con un Error_Body de código `VALIDATION_ERROR` que nombre cada campo inválido y SHALL omitir la creación de la Order.
9. FOR ALL solicitudes de orden, THE Order_Validator SHALL producir el mismo resultado de validación al evaluar dos veces la misma solicitud (determinismo).

### Requirement 3: Validaciones previas al envío (RF-30)

**User Story:** Como Investor, quiero que el sistema verifique mi cuenta, mis fondos, mi tenencia y mis controles antes de enviar la orden, para que Alpaca reciba solo órdenes que puedo cumplir.

#### Acceptance Criteria

1. IF el Estimated_Amount de una compra supera el Available_Buying_Power del Investor, THEN THE Order_Service SHALL responder HTTP 409 con un Error_Body de código `INSUFFICIENT_BUYING_POWER` que incluya el Estimated_Amount y el Available_Buying_Power, y SHALL omitir la creación de la Order.
2. IF la `qty_available` de la posición del símbolo que devuelve Position_Port, menos las acciones con Reservation `active` del mismo símbolo, es menor que la cantidad de una venta o es cero, THEN THE Order_Service SHALL responder HTTP 409 con un Error_Body de código `INSUFFICIENT_POSITION` y SHALL omitir la creación de la Order.
3. IF el Investor ya creó en el día calendario de `America/New_York` un número de Orders igual a su `daily_order_limit`, THEN THE Order_Service SHALL responder HTTP 409 con un Error_Body de código `DAILY_ORDER_LIMIT_REACHED` y SHALL omitir la creación de la Order.
4. IF el `buying_power` de `wallet` o la posición de Position_Port no están disponibles, THEN THE Order_Service SHALL responder HTTP 502 con un Error_Body de código `ALPACA_UNAVAILABLE` y SHALL omitir la creación de la Order.
5. WHEN el Order_Submitter va a enviar una Order que esperó antes del envío, THE Order_Submitter SHALL repetir las validaciones de cuenta activa, negociabilidad, fondos y tenencia de este requisito, descontando la Reservation propia de la Order, y SHALL pasar la Order a Rechazada con el motivo cuando alguna validación falla.

### Requirement 4: Autorización adicional por umbral (RF-30)

**User Story:** Como Investor, quiero que las órdenes de importe alto exijan una autorización adicional, para protegerme de errores y usos no autorizados.

#### Acceptance Criteria

1. IF el Estimated_Amount supera `high_order_threshold_usd`, `extra_confirmation` es true y la solicitud no incluye un código TOTP, THEN THE Order_Service SHALL responder HTTP 409 con un Error_Body de código `EXTRA_AUTHORIZATION_REQUIRED` que indique el método `totp` y SHALL omitir la creación de la Order.
2. IF el código TOTP incluido no es válido según el puerto de verificación de `identity`, THEN THE Order_Service SHALL responder HTTP 401 con un Error_Body de código `EXTRA_AUTHORIZATION_INVALID` y SHALL omitir la creación de la Order.
3. IF el Estimated_Amount supera `high_order_threshold_usd`, `extra_confirmation` es true y el Investor no tiene TOTP activo, THEN THE Order_Service SHALL responder HTTP 409 con un Error_Body de código `MFA_ENROLLMENT_REQUIRED` y SHALL omitir la creación de la Order.
4. IF el Estimated_Amount supera `high_order_threshold_usd`, `extra_confirmation` es false y `high_amount_acknowledged` no es true, THEN THE Order_Service SHALL responder HTTP 409 con un Error_Body de código `EXTRA_AUTHORIZATION_REQUIRED` que indique el método `acknowledgement` y SHALL omitir la creación de la Order.
5. WHEN una Order se crea con autorización adicional, THE Order_Service SHALL registrar en su Order_Event el método de autorización y el instante, sin almacenar el código TOTP.

### Requirement 5: Revisión de la orden con el comisionista (RF-30)

**User Story:** Como Investor con comisionista vinculado, quiero que mi comisionista revise, devuelva o apruebe mis órdenes antes de enviarlas, para contar con su asesoría según el proceso interno.

#### Acceptance Criteria

1. WHEN se crea una Order de un Investor para quien Broker_Link_Port informa un Broker vinculado con revisión habilitada, THE Review_Service SHALL pasar la Order a En Revisión con causa `broker_review` y SHALL omitir el envío a Alpaca_Broker_API.
2. WHEN un Broker solicita su cola de revisión, THE Review_Service SHALL devolver solo las Orders en En Revisión con causa `broker_review` de Investors vinculados a ese Broker según Broker_Link_Port.
3. WHEN un Broker vinculado devuelve una Order en revisión con un comentario de 1 a 500 caracteres, THE Review_Service SHALL pasar la Order a Pendiente marcada como devuelta, registrar el comentario y notificar al Investor con el tipo `order_updates`.
4. WHEN un Investor modifica cantidad, precios o vigencia de su Order devuelta y la reenvía, THE Review_Service SHALL repetir las validaciones de los Requisitos 2, 3 y 4, ajustar la Reservation y pasar la Order a En Revisión.
5. WHEN un Broker vinculado aprueba una Order en revisión, THE Review_Service SHALL registrar de inmediato el Broker y el instante de aprobación, pasar la Order a Firmada por Comisionista y continuar con el envío del Requisito 8 si el mercado está abierto o con la programación del Requisito 13 si el mercado está cerrado.
6. IF un Broker actúa sobre una Order de un Investor no vinculado a ese Broker según Broker_Link_Port, THEN THE Review_Service SHALL responder HTTP 404 con un Error_Body de código `ORDER_NOT_FOUND`.
7. WHILE Broker_Link_Port usa el adaptador Null_Broker_Link, THE Review_Service SHALL tratar toda Order como de flujo directo del Investor y SHALL devolver una cola de revisión vacía a cualquier Broker.

### Requirement 6: Reservar y liberar saldo y tenencia (RF-34)

**User Story:** Como Investor, quiero que el saldo y las acciones comprometidas en mis órdenes no enviadas queden reservadas, para no comprometer el mismo dinero o las mismas acciones dos veces.

#### Acceptance Criteria

1. WHEN se crea una Order de compra, THE Reservation_Ledger SHALL crear una Reservation `active` por el Estimated_Amount.
2. WHEN se crea una Order de venta, THE Reservation_Ledger SHALL crear una Reservation `active` por la cantidad de acciones.
3. WHEN Alpaca_Broker_API acusa recibo de una Order y se registra su identificador externo, THE Reservation_Ledger SHALL cambiar su Reservation a `transferred`.
4. WHEN una Order sin identificador externo de Alpaca pasa a Cancelada, Rechazada, Expirada o Fallida, THE Reservation_Ledger SHALL cambiar su Reservation a `released`.
5. THE Reservation_Ledger SHALL mantener como máximo una Reservation por Order y SHALL rechazar toda transición desde `transferred` o `released` hacia otro estado.
6. WHEN se crean Orders concurrentes del mismo Investor, THE Reservation_Ledger SHALL serializar la verificación y creación de Reservations, de modo que cada verificación posterior espere a que termine la anterior y calcule el disponible incluyendo la Reservation creada por la anterior, que la suma de las Reservations `active` en USD no supere el `buying_power` usado en cada verificación y la suma de acciones reservadas por símbolo no supere la `qty_available` usada en cada verificación.
7. FOR ALL secuencias de creación, cancelación, envío y expiración de Orders, THE Reservation_Ledger SHALL cumplir que el importe `active` reservado de un Investor es igual a la suma de los Estimated_Amount de sus Orders de compra que no son Terminal_Orders y no tienen identificador externo de Alpaca (invariante).

### Requirement 7: Ratificar nueva cotización (RF-31, RF-30)

**User Story:** Como Investor, quiero autorizar de nuevo una orden pendiente cuyo precio cambió antes del envío, para no ejecutar a un precio que no acepté.

#### Acceptance Criteria

1. WHEN el Order_Submitter va a enviar una Order `market` que esperó antes del envío y el precio vigente difiere del Reference_Price en más de `ORDER_REAUTH_PRICE_DEVIATION_PCT`, THE Order_Submitter SHALL pasar la Order a Detenida, crear una Reauthorization_Request con precio anterior, precio actualizado y fecha límite, omitir el envío a Alpaca_Broker_API y notificar al Investor con el tipo `order_updates`.
2. WHEN el Investor acepta la Reauthorization_Request antes de la fecha límite, THE Order_Service SHALL registrar la decisión y el instante de respuesta, actualizar el Reference_Price, el Estimated_Amount y la Reservation, y continuar con el envío del Requisito 8 si el mercado está abierto o con la programación del Requisito 13 si está cerrado.
3. IF el Investor acepta la Reauthorization_Request de una compra y el nuevo Estimated_Amount supera el Available_Buying_Power más la Reservation propia, THEN THE Order_Service SHALL responder HTTP 409 con un Error_Body de código `INSUFFICIENT_BUYING_POWER` y SHALL mantener la Order en Detenida.
4. WHEN el Investor rechaza la Reauthorization_Request, THE Order_Service SHALL registrar la decisión y el instante de respuesta y SHALL pasar la Order a Cancelada con causa `reauthorization_rejected`.
5. WHEN vence la fecha límite de una Reauthorization_Request sin respuesta, THE Order_Service SHALL registrar la falta de respuesta y SHALL pasar la Order a Expirada.
6. WHILE una Order está en Detenida, THE Order_Submitter SHALL omitir todo envío de la Order a Alpaca_Broker_API.

### Requirement 8: Enviar la orden al bróker (RF-32)

**User Story:** Como Investor, quiero que mi orden validada se envíe a Alpaca una sola vez, para que se ejecute sin duplicados aunque haya reintentos.

#### Acceptance Criteria

1. WHEN una Order validada está lista para envío con el mercado abierto, THE Order_Submitter SHALL enviarla a Alpaca_Broker_API con su Client_Order_Id, registrar el identificador externo y el estado del proveedor, pasarla a Enviada y devolver la respuesta del Backend_API en 5 segundos o menos.
2. WHEN un Investor repite una solicitud de creación con una Idempotency_Key ya usada por ese Investor y el mismo cuerpo, THE Order_Service SHALL devolver la Order almacenada originalmente y SHALL omitir la creación de otra Order y otro envío a Alpaca_Broker_API.
3. IF un Investor reutiliza una Idempotency_Key con un cuerpo distinto, THEN THE Order_Service SHALL responder HTTP 409 con un Error_Body de código `IDEMPOTENCY_CONFLICT` y SHALL omitir la creación de la Order.
4. IF Alpaca_Broker_API no responde en 4 segundos al envío, THEN THE Order_Submitter SHALL mantener la Order en Enviada sin identificador externo y SHALL omitir el reenvío de la Order.
5. WHILE una Order está en Enviada sin identificador externo, THE Order_Reconciler SHALL buscarla en Alpaca_Broker_API por su Client_Order_Id y SHALL pasarla a Fallida, liberando su Reservation, si la Order no aparece después de 2 consultas.
6. IF Alpaca_Broker_API rechaza la Order con un error de validación o de capacidad de compra, THEN THE Order_Submitter SHALL pasar la Order a Rechazada con el motivo informado por Alpaca, liberar la Reservation y, en la creación, responder HTTP 422 con un Error_Body de código `ORDER_REJECTED` que incluya el motivo y el identificador de la Order.
7. IF Alpaca_Broker_API falla sin recibir la Order, THEN THE Order_Submitter SHALL pasar la Order a Fallida, liberar la Reservation y, en la creación, responder HTTP 502 con código `ALPACA_UNAVAILABLE` o HTTP 503 con código `ALPACA_RATE_LIMITED` cuando Alpaca responde 429, incluyendo el identificador de la Order.

### Requirement 9: Registrar actualizaciones y ejecuciones (RF-32)

**User Story:** Como Investor, quiero que el sistema registre cada actualización y ejecución que informa Alpaca, para conocer el resultado real de mi orden.

#### Acceptance Criteria

1. WHILE existan Orders en Enviada o en En Ejecución con `fully_filled` en false, THE Order_Reconciler SHALL consultar su estado en Alpaca_Broker_API con un intervalo configurable, por defecto 15 segundos, y aplicar el mapeo del Requisito 10.
2. WHEN el Order_Reconciler obtiene una actividad `FILL` nueva de una Order, THE Order_Reconciler SHALL registrar una Execution con identificador de ejecución, cantidad, precio y marca de tiempo de ejecución, y actualizar la cantidad ejecutada y el precio promedio ponderado de la Order.
3. WHEN el Order_Reconciler obtiene una actividad `FILL` cuyo identificador de ejecución ya está registrado, THE Order_Reconciler SHALL omitir el registro de una segunda Execution.
4. THE Order_Reconciler SHALL mantener la cantidad ejecutada de cada Order igual a la suma de las cantidades de sus Executions y menor o igual que la cantidad de la Order.
5. WHEN la cantidad ejecutada alcanza la cantidad de la Order, THE Order_Reconciler SHALL poner `fully_filled` en true y registrar el instante de finalización.
6. WHEN Alpaca_Broker_API informa el estado de las Order_Legs de una Order `bracket`, THE Order_Reconciler SHALL registrar el identificador externo y el estado de cada Order_Leg.
7. IF Alpaca_Broker_API falla durante una consulta, THEN THE Order_Reconciler SHALL conservar el estado de las Orders, registrar el fallo sin secretos y reintentar en el siguiente ciclo.

### Requirement 10: Gestionar estados de orden (RF-32, RFP-10)

**User Story:** Como Investor, quiero que cada orden tenga un estado claro con transiciones controladas, para entender en qué punto del proceso está.

#### Acceptance Criteria

1. THE Order_State_Machine SHALL definir los diez Order_Status: Pendiente `PENDING`, Enviada `SUBMITTED`, Firmada por Comisionista `BROKER_SIGNED`, En Ejecución `EXECUTING`, Cancelada `CANCELED`, Rechazada `REJECTED`, Expirada `EXPIRED`, En Revisión `IN_REVIEW`, Fallida `FAILED` y Detenida `HELD`.
2. THE Order_State_Machine SHALL permitir solo estas transiciones: `PENDING` → `IN_REVIEW`, `SUBMITTED`, `HELD`, `CANCELED`, `REJECTED`, `EXPIRED` o `FAILED`; `IN_REVIEW` → `PENDING`, `BROKER_SIGNED`, `CANCELED` o `EXPIRED`; `BROKER_SIGNED` → `IN_REVIEW`, `SUBMITTED`, `HELD`, `CANCELED`, `REJECTED`, `EXPIRED` o `FAILED`; `HELD` → `PENDING`, `BROKER_SIGNED`, `IN_REVIEW`, `SUBMITTED`, `CANCELED`, `REJECTED`, `EXPIRED` o `FAILED`; `SUBMITTED` → `EXECUTING`, `CANCELED`, `REJECTED`, `EXPIRED` o `FAILED`; `EXECUTING` → `EXECUTING`, `CANCELED` o `EXPIRED` mientras `fully_filled` es false.
3. IF un caso de uso solicita una transición no permitida o desde una Terminal_Order, THEN THE Order_State_Machine SHALL rechazar la transición y conservar la Order sin cambios sea cual sea el origen de la solicitud (Backend_API, Order_Reconciler, Order_Scheduler o puertos de entrada), y THE Order_Service SHALL responder HTTP 409 con un Error_Body de código `INVALID_ORDER_STATE` solo cuando la solicitud provenga del Backend_API.
4. THE Order_Reconciler SHALL mapear los estados de Alpaca así: `new`, `accepted`, `pending_new`, `accepted_for_bidding`, `calculated`, `held`, `stopped`, `suspended`, `pending_cancel` y `pending_replace` a `SUBMITTED`; `partially_filled` y `filled` a `EXECUTING`; `done_for_day` a `EXECUTING` si la cantidad ejecutada es mayor que cero y a `SUBMITTED` en otro caso; `canceled` a `CANCELED`; `expired` a `EXPIRED`; y `rejected` a `REJECTED`.
5. IF Alpaca_Broker_API informa un estado no incluido en el criterio 4 o cuya transición no está permitida, THEN THE Order_Reconciler SHALL conservar el Order_Status, almacenar el estado del proveedor y registrar una advertencia.
6. WHEN una Order cambia de Order_Status, THE Order_Service SHALL registrar un Order_Event con estado anterior, estado nuevo, causa, actor y marca de tiempo en la misma transacción que el cambio.
7. WHEN una Unsent_Order supera `ORDER_LOCAL_MAX_AGE_DAYS` o una Order programada con vigencia `day` no se envía durante su sesión prevista, THE Order_Service SHALL pasar la Order a Expirada y notificar al Investor con el tipo `order_updates`.
8. FOR ALL secuencias de eventos aplicadas a una Order, THE Order_State_Machine SHALL dejar la Order en uno de los diez Order_Status y SHALL mantener sin cambios toda Terminal_Order (invariante).

### Requirement 11: Consultar seguimiento y notificar ejecución (RF-33)

**User Story:** Como Investor, quiero consultar el seguimiento de mis órdenes y recibir aviso de su ejecución efectiva, para saber qué compré o vendí, a qué precio y cuándo.

#### Acceptance Criteria

1. WHEN un Investor consulta una Order propia, THE Order_Service SHALL devolver su Order_Status, estado del proveedor, instante de última actualización, cantidad, cantidad ejecutada, precios, precio promedio de ejecución, Executions, Order_Legs, Order_Events, Reservation, Reauthorization_Requests, comentarios de revisión e identificador externo de Alpaca.
2. WHEN un Investor lista sus Orders, THE Order_Service SHALL devolverlas paginadas en orden descendente de creación, con filtros opcionales por Order_Status, símbolo y rango de fechas, y con un tamaño de página de 1 a 100, por defecto 20.
3. WHEN el Order_Reconciler registra una Execution, THE Order_Service SHALL notificar al Investor mediante el Notifier con el tipo `order_executions`, indicando instrumento, lado, cantidad ejecutada, precio de ejecución, comisión de referencia, fecha y hora de ejecución.
4. THE Order_Service SHALL presentar la notificación de ejecución en el canal `in_app` y SHALL despachar por los canales externos que el Investor tenga habilitados para `order_executions` en sus preferencias de `identity`.
5. THE Order_Service SHALL rotular la comisión de la notificación y de la consulta como comisión de referencia estimada.

### Requirement 12: Solicitar cancelación de orden (RF-34)

**User Story:** Como Investor, quiero cancelar una orden que aún no se ejecutó por completo, para liberar mi saldo y evitar una operación que ya no deseo.

#### Acceptance Criteria

1. WHEN un Investor solicita cancelar una Order propia con un motivo (`price_changed`, `no_longer_needed`, `input_error` u `other`) y `confirmed` en true, THE Order_Service SHALL registrar el estado previo, el motivo, la confirmación y el instante de la solicitud.
2. WHEN la Order a cancelar es una Unsent_Order, THE Order_Service SHALL pasarla a Cancelada, liberar su Reservation y responder HTTP 200 con la Order.
3. WHEN la Order a cancelar está en Enviada o en En Ejecución con `fully_filled` en false, THE Order_Service SHALL solicitar la cancelación a Alpaca_Broker_API, responder HTTP 202 con la Order y dejar el cambio a Cancelada al Order_Reconciler cuando Alpaca informe `canceled`.
4. IF el motivo es `other` y no incluye un texto de 1 a 500 caracteres, o `confirmed` es distinto de true, THEN THE Order_Service SHALL responder HTTP 422 con un Error_Body de código `VALIDATION_ERROR` y SHALL conservar la Order sin cambios.
5. IF la Order es una Terminal_Order, THEN THE Order_Service SHALL responder HTTP 409 con un Error_Body de código `ORDER_NOT_CANCELLABLE` y SHALL omitir toda llamada a Alpaca_Broker_API.
6. WHEN una Order en En Ejecución parcial pasa a Cancelada, THE Order_Service SHALL conservar sus Executions y su cantidad ejecutada.
7. IF Alpaca_Broker_API informa que la Order ya se ejecutó por completo al cancelar, THEN THE Order_Service SHALL marcar la solicitud de cancelación como no aplicada y conservar el Order_Status que informe el Order_Reconciler.

### Requirement 13: Programar orden fuera de horario (RF-35)

**User Story:** Como Investor, quiero dejar programada una orden cuando el mercado está cerrado, para que se envíe en la próxima sesión elegible.

#### Acceptance Criteria

1. IF un Investor crea una Order con el mercado cerrado según el calendario de `market_data` y la solicitud no incluye `schedule_if_closed` en true, THEN THE Order_Service SHALL responder HTTP 409 con un Error_Body de código `MARKET_CLOSED` que incluya la próxima apertura y SHALL omitir la creación de la Order.
2. WHEN un Investor crea una Order con el mercado cerrado y `schedule_if_closed` en true, THE Order_Service SHALL crear la Order en Pendiente con `scheduled_for` igual a la próxima apertura informada por `market_data`, registrar activo, parámetros y confirmación del Investor, crear la Reservation y omitir el envío a Alpaca_Broker_API.
3. WHEN llega `scheduled_for` y el calendario de `market_data` informa el mercado abierto, THE Order_Scheduler SHALL aplicar a cada Order programada las validaciones del Requisito 3 criterio 5 y la comparación de precio del Requisito 7, y SHALL enviar las Orders que las superan según el Requisito 8.
4. WHILE el mercado esté cerrado, THE Order_Scheduler SHALL omitir el envío de Orders programadas a Alpaca_Broker_API.
5. WHERE una Order programada está en revisión del Broker, THE Order_Scheduler SHALL enviarla solo cuando esté en Firmada por Comisionista.

### Requirement 14: Revisar órdenes pendientes ante un cambio de horario (RFP-10)

**User Story:** Como Investor, quiero que mis órdenes pendientes pasen a revisión y recibir aviso cuando el administrador cambia el horario de un mercado, para decidir si siguen siendo válidas.

#### Acceptance Criteria

1. WHEN Schedule_Change_Port recibe un cambio de horario de un mercado, THE Order_Service SHALL pasar a En Revisión con causa `schedule_change` cada Unsent_Order en Pendiente, Firmada por Comisionista o Detenida de un instrumento de ese mercado, conservando su Reservation.
2. WHEN Schedule_Change_Port pasa Orders a En Revisión, THE Order_Service SHALL enviar a cada Investor afectado una notificación con el tipo `order_updates` que identifique sus Orders afectadas y el mercado.
3. THE Order_Service SHALL conservar sin cambios las Orders en Enviada, en En Ejecución y las Terminal_Orders al aplicar un cambio de horario.
4. WHEN un Investor reanuda una Order propia en En Revisión con causa `schedule_change`, THE Order_Service SHALL enviarla según el Requisito 8 si el mercado está abierto, o, si el mercado está cerrado, recalcular `scheduled_for` con el calendario vigente, pasar la Order a Pendiente y notificar al Investor con el tipo `order_updates` la nueva fecha programada.
5. WHEN Schedule_Change_Port recibe dos veces el mismo cambio de horario, THE Order_Service SHALL dejar las Orders en el mismo estado que tras la primera recepción y SHALL omitir notificaciones duplicadas (idempotencia).

### Requirement 15: Autorización, configuración, errores y contrato (transversal)

**User Story:** Como integrante del equipo de frontend, quiero un contrato OpenAPI completo con errores explícitos y controles de acceso, para consumir el módulo sin ambigüedades.

#### Acceptance Criteria

1. THE Backend_API SHALL exigir sesión autenticada y el rol `investor` vigente en los endpoints de creación, vista previa, consulta, cancelación, nueva autorización, reenvío y reanudación de Orders, y el rol `broker` vigente en los endpoints de revisión.
2. IF un usuario consulta o modifica una Order que no le pertenece, THEN THE Backend_API SHALL responder HTTP 404 con un Error_Body de código `ORDER_NOT_FOUND`, sin revelar la existencia de la Order.
3. IF una solicitud carece de sesión válida o del rol requerido, THEN THE Backend_API SHALL responder HTTP 401 o HTTP 403 con el Error_Body definido por `identity-market-backend`.
4. THE Backend_API SHALL representar cantidades, precios e importes como cadenas decimales exactas, sin pérdida de precisión respecto a los valores de Alpaca_Broker_API y de `market_data`.
5. THE Backend_API SHALL obtener cada uno de estos cinco valores desde su propia variable de entorno: la tasa de comisión de referencia, el umbral de nueva autorización, la ventana de nueva autorización, la antigüedad máxima local y el intervalo del Order_Reconciler; y SHALL usar, para cada variable ausente, el valor por defecto de este spec de forma independiente de las demás.
6. IF la base de datos no está disponible, THEN THE Backend_API SHALL responder HTTP 503 con un Error_Body de código `DATABASE_UNAVAILABLE`.
7. THE Backend_API SHALL declarar en el contrato OpenAPI los esquemas de solicitud, respuesta y cada Error_Body de cada endpoint de `orders`.
8. THE Order_Service SHALL omitir credenciales de Alpaca, códigos TOTP y secretos en logs, respuestas y Error_Body.
9. THE Order_Service SHALL acceder a `identity`, `market_data` y `wallet` solo mediante puertos, sin leer directamente sus tablas.
