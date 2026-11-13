# Requirements Document

## Introduction

Este spec cubre el módulo de desarrollo MOD-04 "Billetera, Gestión de Fondos y Tesorería Multi-Moneda" del backend de Acciones UD (responsable: Davidson E. Sánchez Gordillo). El módulo se implementa como el paquete `wallet` dentro del monolito modular hexagonal (`src/acciones_ud/wallet/`) y depende solo de MOD-01 (`identity`), ya implementado. Es el primer módulo pendiente en el orden de dependencias del catálogo (MOD-04 → MOD-03 → MOD-05 → MOD-06 → MOD-07), porque MOD-03 necesita consultar el efectivo disponible antes de crear órdenes.

Alcance trazable (los textos originales están en `.kiro/steering/requerimientos-proyecto.md`, sección MOD-04):

- RF-36: consultar estado de la cuenta Alpaca asociada y sus saldos y capacidad de compra (Requisito 1).
- RF-37: depósito simulado en sandbox (Requisitos 2 y 3).
- RF-39: retiro simulado en sandbox (Requisitos 2 y 4).
- RF-40: seguimiento de confirmaciones externas y consulta de movimientos (Requisitos 5 y 6).
- RF-38: identificación de moneda sin conversión propia (Requisito 7).
- RF-10: contratar plan premium con Stripe sandbox (Requisito 8).
- RF-10, RF-11 y RF-12, operación complementaria: recepción de notificaciones de pago de Stripe (Requisito 9).
- RF-11: cancelar suscripción (Requisito 10).
- RF-12: consultar suscripción y pagos (Requisito 11).
- RFP-11: notificar cambios de saldo (Requisito 12), obligatorio por la Decisión R1.
- Requisitos transversales de autorización, configuración, errores y contrato OpenAPI (Requisito 13).

Fuera de alcance: RFP-06 y RFP-07 (descartados por las Decisiones R2 y R3); la captura de KYC y la apertura de la cuenta Alpaca (RFP-01, ya implementados en `identity` mediante `POST /kyc/account` y `GET /kyc/status`); la reserva de saldo al crear órdenes (RF-34, pertenece a MOD-03); posiciones e histórico de portafolio (brecha B1 en su parte de posiciones, pertenece a MOD-05); movimiento de dinero real.

### Decisiones y supuestos del módulo

Cada punto abierto del catálogo para MOD-04 queda resuelto aquí como decisión (W) o supuesto (A).

- **W1 (reutilizar la asociación existente, RF-36):** la parte "crear o asociar cuenta" de RF-36 queda cubierta por `identity`. El módulo `wallet` lee la asociación usuario–cuenta Alpaca a través de un puerto de lectura sobre `kyc_accounts` y no crea una segunda tabla de asociación ni un segundo endpoint de apertura.
- **W2 (mecanismo de fondeo, RF-37 y RF-39):** depósitos y retiros usan transferencias ACH de Alpaca Broker API sandbox (`/v1/accounts/{account_id}/ach_relationships` y `/v1/accounts/{account_id}/transfers`, tipo `ach`, dirección `INCOMING` o `OUTGOING`) sobre una relación bancaria de prueba. Se descarta el journal desde la cuenta prefondeada de la firma porque RF-39 exige dirección y relación bancaria de prueba, y el journal no modela un retiro hacia un banco. Las rutas exactas se confirman en el diseño contra la documentación de Broker API.
- **W3 (confirmaciones externas, RF-40):** las actualizaciones de estado de transferencias se obtienen por consulta periódica (Transfer_Reconciler) y no por el stream SSE de eventos de Alpaca, porque la consulta periódica no requiere conexión persistente ni URL pública y se prueba con fakes en memoria. El stream SSE queda como mejora futura no comprometida.
- **W4 (Stripe, RF-10 a RF-12):** se usa Stripe Checkout en modo suscripción con dos precios configurados por variables de entorno: mensual (USD 12) y anual (USD 120), según el enunciado. El estado de la suscripción y de los pagos lo determinan exclusivamente los eventos de webhook verificados por firma; el retorno del navegador desde Checkout no cambia ningún estado. Los flujos de Stripe y de Alpaca permanecen separados.
- **W5 (cancelación, RF-11):** cancelar programa la terminación al final del periodo pagado (`cancel_at_period_end`); el usuario conserva premium hasta esa fecha. No hay reembolsos prorrateados.
- **W6 (flag `is_premium`):** el flag del usuario se actualiza mediante un puerto hacia `identity` cuando el webhook cambia el estado de la suscripción: `active` o `trialing` lo ponen en true, y `canceled`, `unpaid` o `incomplete_expired` lo ponen en false. El endpoint existente `PUT /admin/users/{id}/premium` se mantiene sin cambios de contrato; un valor fijado por el administrador permanece hasta el siguiente cambio de estado de la suscripción de ese usuario (gana la última escritura).
- **W7 (plan contratado en `/users/me`, brecha D2):** `wallet` expone un puerto de consulta del plan vigente que `identity` usa para devolver `contracted_plan` en lugar del `null` fijo actual. El campo `associated_broker` sigue en `null` hasta MOD-06.
- **W8 (frescura de saldos, brecha B2):** si Alpaca falla al consultar saldos, la respuesta indica `unavailable: true` con los importes en `null`, nunca en cero, para no confundir "sin datos" con "sin dinero".
- **W9 (multi-moneda, RF-38):** el título del módulo es más amplio que su alcance. El sistema identifica y expone la moneda que Alpaca devuelve en saldos, transferencias y actividades, y no implementa conversión de divisas. **Supuesto A1:** la cuenta sandbox de la integración no tiene habilitado un endpoint de conversión de divisas de Alpaca; por eso la conversión queda fuera del alcance implementado y el sistema informa `conversion_supported: false`. Si Alpaca la habilita, se requiere una nueva versión de este spec.
- **W10 (notificación de cambios de saldo, RFP-11):** el aviso se genera cuando una transferencia llega a `COMPLETE` (depósito o retiro) y cuando el Transfer_Reconciler detecta actividades de tipo `FILL` (compra o venta) nuevas en una cuenta asociada. Se usa el Notifier existente de `market_data` y un nuevo tipo de evento `balance_changes` en las preferencias de notificación de `identity`, con el canal `in_app` habilitado por defecto como los demás tipos.
- **W11 (reserva de saldo, RF-34):** `wallet` solo expone el `buying_power` y el efectivo retirable que informa Alpaca. La reserva propia de saldo, si se necesita, se decide en el spec de MOD-03.
- **W12 (idempotencia de dinero):** las solicitudes de depósito y retiro aceptan un encabezado `Idempotency-Key` obligatorio para evitar transferencias duplicadas por reintentos del cliente.
- **A2 (límites de importe):** el importe por transferencia está entre USD 1.00 y un máximo configurable, por defecto USD 50,000.00, con exactamente dos decimales como máximo. El valor por defecto se basa en el prefondeo sandbox de USD 50.000 citado en el catálogo; Alpaca puede aplicar límites propios adicionales.
- **A3 (rol):** las operaciones de billetera y suscripción están disponibles para usuarios con rol `investor` vigente. Los comisionistas y administradores no operan billeteras propias en este módulo.

### Política de pruebas

Por indicación del usuario, las pruebas no son obligatorias para todo el módulo. Son obligatorias solo para las partes críticas: invariantes de importes y saldos (Requisito 1 criterios 3–4, Requisito 3 criterios 2–3 y 6, Requisito 4 criterios 2–4), transiciones de estado de transferencias e idempotencia (Requisito 3 criterio 5, Requisito 5 criterios 2–4), autorización y propiedad de recursos (Requisito 13 criterios 1–3) y verificación de firma e idempotencia del webhook de Stripe (Requisito 9 criterios 1–3 y 6–8). Las demás pruebas son opcionales.

## Glossary

- **Backend_API**: la aplicación FastAPI de Acciones UD que expone los endpoints de este spec.
- **Wallet_Service**: componente del módulo `wallet` que consulta saldos, monedas y movimientos de la cuenta Alpaca de un Investor.
- **Funding_Service**: componente del módulo `wallet` que gestiona Bank_Relationships y crea Transfers de depósito y retiro.
- **Transfer_Reconciler**: tarea periódica del módulo `wallet` que consulta en Alpaca el estado de los Transfers no terminales y las actividades `FILL` nuevas.
- **Subscription_Service**: componente del módulo `wallet` que inicia la contratación, cancela y consulta Subscriptions.
- **Stripe_Webhook_Handler**: endpoint del módulo `wallet` que recibe y aplica los eventos de Stripe.
- **Notifier**: componente existente de `market_data` que crea notificaciones y las despacha según las preferencias del usuario.
- **Alpaca_Broker_API**: Alpaca Broker API en entorno sandbox.
- **Stripe_API**: API de Stripe en modo de prueba (sandbox).
- **Investor**: usuario autenticado con el rol `investor` vigente.
- **Linked_Account**: registro de `kyc_accounts` del Investor con `alpaca_account_id` no nulo.
- **Active_Account**: Linked_Account cuyo último estado conocido en Alpaca es `ACTIVE`.
- **Balance_View**: respuesta de saldos con `cash`, `cash_withdrawable`, `buying_power`, `equity`, `portfolio_value`, `long_market_value`, `currency`, `retrieved_at` y `unavailable`.
- **Bank_Relationship**: relación ACH de prueba registrada en Alpaca para una Linked_Account, con su identificador externo y estado.
- **Transfer**: registro local de un depósito (`INCOMING`) o retiro (`OUTGOING`) con identificador externo de Alpaca, importe, moneda, dirección, estado, Idempotency_Key y marcas de tiempo.
- **Terminal_Status**: estado de Transfer que no admite cambios posteriores: `COMPLETE`, `CANCELED`, `RETURNED` o `REJECTED`.
- **Idempotency_Key**: valor del encabezado `Idempotency-Key`, de 8 a 128 caracteres imprimibles ASCII, único por Investor.
- **Activity**: movimiento de cuenta que devuelve Alpaca (por ejemplo `CSD`, `CSW`, `FILL`, `DIV`, `FEE`), con identificador, tipo, fecha, importe, moneda, dirección, estado y descripción cuando estén disponibles.
- **Plan**: plan premium ofrecido, `monthly` (USD 12 por mes) o `annual` (USD 120 por año), asociado a un precio de Stripe configurado.
- **Subscription**: registro local de la suscripción de un Investor con identificador de Stripe, Plan, estado, periodo actual, `cancel_at_period_end`, motivo de cancelación y marcas de tiempo.
- **Payment**: registro local de un cobro de una Subscription con referencia de Stripe, importe, moneda, periodo, resultado y fecha.
- **Stripe_Event**: evento de webhook de Stripe con identificador único, tipo y objeto de datos.
- **Error_Body**: cuerpo JSON de error con los campos `code`, `message` y `details`, definido por `identity-market-backend`.
- **Sandbox_Notice**: texto fijo incluido en las respuestas de depósitos, retiros y saldos que indica que los fondos son virtuales del entorno sandbox y no representan dinero real.

## Requirements

### Requirement 1: Consultar estado de cuenta y saldos (RF-36)

**User Story:** Como Investor, quiero consultar el estado de mi cuenta Alpaca y sus saldos y capacidad de compra, para saber cuánto puedo invertir o retirar.

#### Acceptance Criteria

1. WHEN un Investor con Linked_Account solicita sus saldos, THE Wallet_Service SHALL consultar la cuenta en Alpaca_Broker_API y devolver un Balance_View con `unavailable` en false, el estado actual de la cuenta, la moneda informada por Alpaca, `retrieved_at` y el Sandbox_Notice.
2. IF un Investor sin Linked_Account solicita sus saldos, THEN THE Wallet_Service SHALL responder HTTP 409 con un Error_Body de código `WALLET_ACCOUNT_REQUIRED` y SHALL omitir toda llamada a Alpaca_Broker_API.
3. THE Wallet_Service SHALL representar cada importe del Balance_View como cadena decimal exacta, sin pérdida de precisión respecto al valor devuelto por Alpaca_Broker_API.
4. IF Alpaca_Broker_API falla o no responde en 5 segundos al consultar saldos, THEN THE Wallet_Service SHALL devolver HTTP 200 con un Balance_View con `unavailable` en true y todos los importes en null, y SHALL omitir cualquier importe en cero que no provenga de Alpaca_Broker_API.
5. WHEN la consulta de saldos obtiene de Alpaca_Broker_API un estado de cuenta distinto del almacenado, THE Wallet_Service SHALL actualizar el estado de la Linked_Account mediante el puerto de `identity` y SHALL devolver el estado nuevo.
6. IF el puerto de `identity` falla o no responde al actualizar el estado de la Linked_Account, THEN THE Wallet_Service SHALL devolver el Balance_View con el estado obtenido de Alpaca_Broker_API y SHALL registrar el fallo en el log sin secretos.

### Requirement 2: Gestionar relación bancaria de prueba (RF-37, RF-39)

**User Story:** Como Investor, quiero registrar una relación bancaria de prueba, para poder simular depósitos y retiros en sandbox.

#### Acceptance Criteria

1. WHEN un Investor con Active_Account envía datos de una relación bancaria de prueba válidos (titular, tipo de cuenta `CHECKING` o `SAVINGS`, número de cuenta y número de ruta de 9 dígitos), THE Funding_Service SHALL crear la Bank_Relationship en Alpaca_Broker_API, almacenar su identificador externo, estado y los últimos 4 dígitos de la cuenta, y devolver HTTP 201 con esos datos.
2. THE Funding_Service SHALL almacenar y devolver solo los últimos 4 dígitos del número de cuenta bancaria.
3. WHEN un Investor solicita sus relaciones bancarias, THE Funding_Service SHALL devolver las Bank_Relationships de su Linked_Account con identificador, estado, tipo de cuenta, últimos 4 dígitos y fecha de creación.
4. IF un Investor sin Active_Account intenta crear una Bank_Relationship, THEN THE Funding_Service SHALL responder HTTP 409 con un Error_Body de código `WALLET_ACCOUNT_NOT_ACTIVE` y SHALL omitir toda llamada a Alpaca_Broker_API.
5. IF los datos de la relación bancaria son inválidos, THEN THE Funding_Service SHALL responder HTTP 422 con un Error_Body que nombre cada campo inválido sin incluir su valor.

### Requirement 3: Solicitar depósito simulado (RF-37)

**User Story:** Como Investor, quiero solicitar un depósito simulado, para acreditar fondos virtuales y poder operar en sandbox.

#### Acceptance Criteria

1. WHEN un Investor con Active_Account solicita un depósito indicando Bank_Relationship propia en estado `APPROVED`, importe, moneda `USD` e Idempotency_Key, THE Funding_Service SHALL crear un Transfer `INCOMING` en Alpaca_Broker_API, almacenarlo con el estado devuelto por Alpaca y devolver HTTP 201 con el Transfer y el Sandbox_Notice.
2. IF el importe del depósito es menor que 1.00, mayor que el máximo configurado o tiene más de dos decimales, THEN THE Funding_Service SHALL responder HTTP 422 con un Error_Body de código `VALIDATION_ERROR` y SHALL omitir la creación del Transfer.
3. IF la moneda del depósito es distinta de `USD`, THEN THE Funding_Service SHALL responder HTTP 422 con un Error_Body de código `CURRENCY_NOT_SUPPORTED` y SHALL omitir la creación del Transfer.
4. IF la Bank_Relationship indicada no pertenece a la Linked_Account del Investor o no está en estado `APPROVED`, THEN THE Funding_Service SHALL responder HTTP 409 con un Error_Body de código `BANK_RELATIONSHIP_NOT_USABLE` y SHALL omitir la creación del Transfer.
5. WHEN un Investor repite una solicitud de depósito con una Idempotency_Key ya usada por ese Investor y el mismo cuerpo, THE Funding_Service SHALL devolver el Transfer almacenado originalmente y SHALL omitir una segunda llamada de creación a Alpaca_Broker_API.
6. IF un Investor reutiliza una Idempotency_Key con un cuerpo distinto, THEN THE Funding_Service SHALL responder HTTP 409 con un Error_Body de código `IDEMPOTENCY_CONFLICT` y SHALL omitir la creación del Transfer.
7. IF Alpaca_Broker_API rechaza la creación del Transfer con un error de validación, THEN THE Funding_Service SHALL responder HTTP 422 con un Error_Body de código `TRANSFER_REJECTED` que incluya el motivo informado por Alpaca y SHALL omitir el almacenamiento del Transfer.

### Requirement 4: Solicitar retiro simulado (RF-39)

**User Story:** Como Investor, quiero solicitar un retiro simulado, para retirar fondos virtuales hacia mi relación bancaria de prueba.

#### Acceptance Criteria

1. WHEN un Investor con Active_Account solicita un retiro indicando Bank_Relationship propia en estado `APPROVED`, importe, moneda `USD` e Idempotency_Key, THE Funding_Service SHALL crear un Transfer `OUTGOING` en Alpaca_Broker_API, almacenarlo con el estado devuelto y devolver HTTP 201 con el Transfer y el Sandbox_Notice.
2. IF el importe del retiro es mayor que el `cash_withdrawable` que Alpaca_Broker_API informa en el momento de la solicitud, THEN THE Funding_Service SHALL responder HTTP 422 con un Error_Body de código `INSUFFICIENT_FUNDS` que incluya el importe retirable y SHALL omitir la creación del Transfer.
3. IF el saldo retirable no se puede obtener porque Alpaca_Broker_API falla, THEN THE Funding_Service SHALL responder con el error de Alpaca del Requisito 13 criterio 5 y SHALL omitir la creación del Transfer.
4. THE Funding_Service SHALL aplicar al retiro las mismas validaciones de importe, moneda, Bank_Relationship e Idempotency_Key del Requisito 3 criterios 2 a 7.

### Requirement 5: Registrar confirmaciones externas de transferencias (RF-40)

**User Story:** Como Investor, quiero que el estado de mis depósitos y retiros se actualice con lo que confirma Alpaca, para saber si la transferencia terminó.

#### Acceptance Criteria

1. WHILE existan Transfers en estado no terminal, THE Transfer_Reconciler SHALL consultar su estado en Alpaca_Broker_API con el intervalo configurado, por defecto 60 segundos.
2. WHEN el Transfer_Reconciler obtiene para un Transfer un estado distinto del almacenado con una marca de actualización de Alpaca posterior a la almacenada, THE Transfer_Reconciler SHALL almacenar el estado nuevo, la marca de actualización y el motivo informado por Alpaca.
3. WHILE un Transfer está en un Terminal_Status, THE Transfer_Reconciler SHALL conservar ese estado sin cambios ante cualquier actualización posterior recibida de Alpaca_Broker_API.
4. IF el Transfer_Reconciler recibe para un Transfer una actualización con marca de tiempo igual o anterior a la almacenada, THEN THE Transfer_Reconciler SHALL descartar la actualización y conservar el estado almacenado.
5. IF Alpaca_Broker_API falla durante una ejecución del Transfer_Reconciler, THEN THE Transfer_Reconciler SHALL registrar el fallo en el log sin secretos, conservar los estados almacenados y reintentar en la siguiente ejecución.
6. WHEN un Investor consulta un Transfer propio, THE Funding_Service SHALL devolver su estado almacenado, el Sandbox_Notice y la fecha de la última confirmación recibida de Alpaca.
7. IF un Investor consulta un Transfer que no pertenece a su Linked_Account, THEN THE Funding_Service SHALL responder según el Requisito 13 criterio 3 sin incluir ningún dato del Transfer, el Sandbox_Notice ni la fecha de la última confirmación.

### Requirement 6: Consultar movimientos financieros (RF-40)

**User Story:** Como Investor, quiero consultar mis movimientos por periodo y tipo, para revisar depósitos, retiros y demás actividades de mi cuenta.

#### Acceptance Criteria

1. WHEN un Investor con Linked_Account consulta sus transferencias con un periodo opcional y una dirección opcional (`INCOMING` u `OUTGOING`), THE Funding_Service SHALL devolver sus Transfers del periodo ordenados por fecha de creación descendente, con identificador externo, fecha, importe, moneda, dirección, estado y descripción cuando exista.
2. WHEN un Investor con Linked_Account consulta sus actividades con un periodo y tipos de Activity opcionales, THE Wallet_Service SHALL obtener las Activities de Alpaca_Broker_API y devolverlas con identificador externo, tipo, fecha, importe, moneda, dirección, estado y descripción cuando estén disponibles.
3. IF el periodo solicitado tiene la fecha inicial posterior a la final o supera 366 días, THEN THE Backend_API SHALL responder HTTP 422 con un Error_Body de código `VALIDATION_ERROR`.
4. WHERE la consulta no indica periodo, THE Wallet_Service SHALL usar los últimos 30 días.
5. THE Wallet_Service SHALL paginar las listas de transferencias y actividades con un tamaño de página de 1 a 100 elementos, por defecto 50, y un cursor de página siguiente.
6. THE Wallet_Service SHALL excluir de las actividades toda operación de conversión de divisas mientras `conversion_supported` sea false.

### Requirement 7: Identificar moneda sin conversión propia (RF-38)

**User Story:** Como Investor, quiero conocer la moneda de mis saldos y movimientos, para interpretar correctamente los importes.

#### Acceptance Criteria

1. THE Wallet_Service SHALL incluir en cada Balance_View, Transfer y Activity el código de moneda ISO 4217 que devuelve Alpaca_Broker_API.
2. WHEN un Investor consulta las capacidades de moneda, THE Wallet_Service SHALL devolver las monedas de su Linked_Account y `conversion_supported` en false.
3. IF Alpaca_Broker_API devuelve un saldo, Transfer o Activity sin moneda, THEN THE Wallet_Service SHALL devolver `USD` como moneda con los importes sin modificar y SHALL registrar en el log la ausencia del dato.

### Requirement 8: Contratar plan premium (RF-10)

**User Story:** Como Investor, quiero contratar un plan premium mensual o anual, para acceder a las funcionalidades premium.

#### Acceptance Criteria

1. WHEN un Investor consulta los planes, THE Subscription_Service SHALL devolver los Plans `monthly` y `annual` con precio, moneda y periodicidad configurados.
2. WHEN un Investor sin Subscription vigente solicita contratar un Plan válido, THE Subscription_Service SHALL crear una sesión de Stripe Checkout en modo suscripción en Stripe_API, almacenar una Subscription en estado `pending_checkout` y devolver HTTP 201 con el identificador de checkout y la URL de pago.
3. IF el Investor ya tiene una Subscription en estado `active`, `trialing` o `past_due`, THEN THE Subscription_Service SHALL responder HTTP 409 con un Error_Body de código `SUBSCRIPTION_ALREADY_ACTIVE` y SHALL omitir la creación de la sesión de Checkout.
4. IF el Plan solicitado no es `monthly` ni `annual`, THEN THE Subscription_Service SHALL responder HTTP 422 con un Error_Body de código `VALIDATION_ERROR`.
5. IF Stripe_API falla o no responde en 10 segundos al crear la sesión de Checkout, THEN THE Subscription_Service SHALL responder HTTP 502 con un Error_Body de código `STRIPE_UNAVAILABLE` y SHALL omitir el almacenamiento de la Subscription nueva.
6. THE Subscription_Service SHALL cambiar el estado de una Subscription solo a partir de Stripe_Events verificados, según el Requisito 9.

### Requirement 9: Recibir notificaciones de pago de Stripe (RF-10, RF-11, RF-12)

**User Story:** Como operador de la plataforma, quiero aplicar las notificaciones de pago de Stripe, para que la suscripción y los cobros reflejen lo confirmado por el proveedor.

#### Acceptance Criteria

1. WHEN el Stripe_Webhook_Handler recibe una solicitud con encabezado `Stripe-Signature` válido para el secreto configurado y con marca de tiempo dentro de 300 segundos, THE Stripe_Webhook_Handler SHALL aplicar el Stripe_Event y responder HTTP 200.
2. IF la solicitud al Stripe_Webhook_Handler no tiene encabezado `Stripe-Signature`, la firma no coincide o la marca de tiempo excede 300 segundos, THEN THE Stripe_Webhook_Handler SHALL responder HTTP 400 con un Error_Body de código `WEBHOOK_SIGNATURE_INVALID` y SHALL dejar sin cambios toda Subscription, Payment y flag premium.
3. WHEN el Stripe_Webhook_Handler recibe un Stripe_Event cuyo identificador ya fue aplicado, THE Stripe_Webhook_Handler SHALL responder HTTP 200 sin volver a aplicar sus efectos.
4. WHEN el Stripe_Webhook_Handler aplica un Stripe_Event de checkout completado o de suscripción creada o actualizada, THE Stripe_Webhook_Handler SHALL almacenar en la Subscription el identificador de Stripe, el estado, el periodo actual y `cancel_at_period_end` informados por Stripe.
5. WHEN el Stripe_Webhook_Handler aplica un Stripe_Event de factura pagada o de pago fallido, THE Stripe_Webhook_Handler SHALL almacenar un Payment con referencia de Stripe, Investor, Plan, importe, moneda, periodo, resultado y fecha.
6. WHEN el estado de una Subscription cambia a `active` o `trialing`, THE Stripe_Webhook_Handler SHALL fijar el flag `is_premium` del Investor en true mediante el puerto de `identity`.
7. WHEN el estado de una Subscription cambia a `canceled`, `unpaid` o `incomplete_expired`, THE Stripe_Webhook_Handler SHALL fijar el flag `is_premium` del Investor en false mediante el puerto de `identity`.
8. IF el Stripe_Event referencia una suscripción o cliente de Stripe que no corresponde a ninguna Subscription almacenada, THEN THE Stripe_Webhook_Handler SHALL registrar el evento como no asociado, responder HTTP 200 y dejar sin cambios toda Subscription y flag premium.
9. IF la base de datos no está disponible al aplicar un Stripe_Event, THEN THE Stripe_Webhook_Handler SHALL responder HTTP 503 con un Error_Body de código `DATABASE_UNAVAILABLE` y SHALL registrar el identificador del Stripe_Event como no aplicado, para que Stripe lo reintente.

### Requirement 10: Cancelar suscripción (RF-11)

**User Story:** Como Investor, quiero cancelar mi suscripción indicando el motivo, para dejar de pagar el plan premium.

#### Acceptance Criteria

1. WHEN un Investor solicita cancelar su Subscription en estado `active`, `trialing` o `past_due` con un motivo de 1 a 500 caracteres, THE Subscription_Service SHALL solicitar a Stripe_API la cancelación al final del periodo, almacenar el motivo y la fecha de solicitud, y devolver HTTP 200 con la Subscription, `cancel_at_period_end` en true y la fecha de fin del periodo.
2. IF el Investor no tiene una Subscription cancelable, THEN THE Subscription_Service SHALL responder HTTP 409 con un Error_Body de código `SUBSCRIPTION_NOT_CANCELABLE` y SHALL omitir toda llamada a Stripe_API.
3. IF el motivo está vacío o supera 500 caracteres, THEN THE Subscription_Service SHALL responder HTTP 422 con un Error_Body de código `VALIDATION_ERROR`.
4. IF Stripe_API falla al cancelar, THEN THE Subscription_Service SHALL responder HTTP 502 con un Error_Body de código `STRIPE_UNAVAILABLE` y SHALL dejar la Subscription sin cambios.
5. WHILE una Subscription tiene `cancel_at_period_end` en true y su periodo actual no ha terminado, THE Subscription_Service SHALL conservar el flag `is_premium` del Investor en true.

### Requirement 11: Consultar suscripción y pagos (RF-12)

**User Story:** Como Investor, quiero consultar mi suscripción y sus pagos, para conocer mi plan, su estado y la fecha de cobro.

#### Acceptance Criteria

1. WHEN un Investor consulta su suscripción, THE Subscription_Service SHALL devolver el Plan, precio, moneda, periodo actual, estado, `cancel_at_period_end`, el Payment más reciente y la fecha del próximo cobro.
2. WHEN un Investor sin Subscription consulta su suscripción, THE Subscription_Service SHALL devolver HTTP 200 con `subscription` en null.
3. WHEN un Investor consulta sus pagos, THE Subscription_Service SHALL devolver sus Payments ordenados por fecha descendente, paginados como en el Requisito 6 criterio 5.
4. WHEN un usuario consulta `/users/me`, THE Backend_API SHALL devolver en `contracted_plan` el Plan de la Subscription en estado `active`, `trialing` o `past_due` del usuario, o null si no tiene ninguna.

### Requirement 12: Notificar cambios de saldo (RFP-11)

**User Story:** Como Investor, quiero recibir un aviso cuando cambia mi saldo, para enterarme de depósitos, retiros, compras y ventas.

#### Acceptance Criteria

1. WHEN un Transfer pasa a estado `COMPLETE`, THE Transfer_Reconciler SHALL crear mediante el Notifier una notificación de tipo `balance_changes` para el Investor con dirección, importe, moneda y el Sandbox_Notice.
2. WHEN el Transfer_Reconciler detecta una Activity de tipo `FILL` de una Linked_Account con fecha posterior al último cursor procesado, THE Transfer_Reconciler SHALL crear una notificación de tipo `balance_changes` con lado (compra o venta), símbolo, cantidad, precio y moneda.
3. THE Backend_API SHALL aceptar `balance_changes` como tipo de evento en las preferencias de notificación de `identity`, con el canal `in_app` habilitado por defecto.
4. THE Transfer_Reconciler SHALL crear como máximo una notificación `balance_changes` por Transfer y por Activity, aunque la misma confirmación se procese más de una vez.
5. WHERE el Investor deshabilitó un canal para `balance_changes`, THE Notifier SHALL omitir el envío por ese canal, según el comportamiento existente de preferencias.
6. WHEN el Transfer_Reconciler procesa una Activity de una Linked_Account con fecha posterior al último cursor procesado, THE Transfer_Reconciler SHALL avanzar el cursor hasta esa Activity cualquiera sea su tipo, y SHALL crear notificaciones solo para Activities de tipo `FILL`.

### Requirement 13: Autorización, configuración, errores y contrato (transversal MOD-04)

**User Story:** Como integrante del equipo, quiero reglas comunes de seguridad, errores y configuración, para que el módulo sea consistente con el resto del backend.

#### Acceptance Criteria

1. IF una solicitud a un endpoint de billetera o suscripción no tiene autenticación válida, THEN THE Backend_API SHALL responder HTTP 401 con un Error_Body y SHALL omitir toda llamada a Alpaca_Broker_API y Stripe_API.
2. IF un usuario autenticado sin rol `investor` vigente solicita un endpoint de billetera o suscripción, THEN THE Backend_API SHALL responder HTTP 403 con un Error_Body de código `FORBIDDEN`.
3. IF un Investor solicita un Transfer, Bank_Relationship o Payment que no pertenece a su Linked_Account o a su Subscription, THEN THE Backend_API SHALL responder HTTP 404 con un Error_Body de código `NOT_FOUND`, sin revelar si el recurso existe.
4. THE Backend_API SHALL exceptuar el Stripe_Webhook_Handler de la autenticación por cookie y SHALL autenticarlo solo por la firma del Requisito 9.
5. IF Alpaca_Broker_API falla en una operación distinta de la consulta de saldos del Requisito 1 criterio 4, THEN THE Backend_API SHALL responder HTTP 502 con un Error_Body de código `ALPACA_UNAVAILABLE`, o HTTP 503 con código `ALPACA_RATE_LIMITED` cuando Alpaca devolvió HTTP 429.
6. IF la base de datos no está disponible durante una solicitud de billetera o suscripción, THEN THE Backend_API SHALL responder HTTP 503 con un Error_Body de código `DATABASE_UNAVAILABLE`.
7. IF falta o es inválida alguna de las variables `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_MONTHLY_ID`, `STRIPE_PRICE_ANNUAL_ID`, `WALLET_MAX_TRANSFER_AMOUNT` o `WALLET_RECONCILE_INTERVAL_SECONDS`, THEN THE Backend_API SHALL negarse a iniciar y SHALL reportar el nombre de cada variable inválida sin su valor.
8. THE Backend_API SHALL excluir claves de Stripe, secretos de webhook, credenciales de Alpaca y números completos de cuenta bancaria de logs, respuestas y Error_Body.
9. THE Backend_API SHALL declarar en el contrato OpenAPI el esquema de request, response y cada Error_Body posible de cada endpoint de este módulo.
10. THE Backend_API SHALL crear las tablas del módulo `wallet` mediante migraciones Alembic en `migrations/versions/`.
