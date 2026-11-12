---
inclusion: auto
name: requerimientos-proyecto
description: Catálogo completo de requerimientos de Acciones UD (RF-01 a RF-47 y RFP vigentes) organizado por módulo de desarrollo, con decisiones de alcance, dependencias y puntos abiertos. Usar al crear o actualizar el spec de un módulo (MOD-03 a MOD-07) o al decidir qué entra en un módulo.
---

# Requerimientos del proyecto Acciones UD

Catálogo de referencia para crear los specs de los módulos pendientes. Fuente:
`requerimientos_acciones_ud_v2 (1).pdf` ("Requerimientos funcionales unificados",
versión del 10 de noviembre de 2026, equipo CapitalFlow, Grupo 4). Los textos de
cada RF y RFP se copian literalmente del catálogo; las notas marcadas como
**Decisión** o **Nota del equipo** son añadidos de este repositorio.

## Cómo usar este documento al crear un spec

1. Un spec por módulo de desarrollo, nombrado por su módulo (por ejemplo
   `wallet-mod-04`, `orders-mod-03`). No agrupar módulos (ver `product.md`).
2. El spec del módulo debe cubrir **todos** sus RF principales y **todos** sus
   RFP asignados en este documento. Cada requisito del spec conserva el ID
   original (`RF-xx` o `RFP-xx`) para la trazabilidad.
3. Los RF de los que el módulo es solo "secundario" (participa) se respetan como
   contrato: el módulo aporta su parte, pero no los reimplementa.
4. Los puntos abiertos de cada módulo (sección "Puntos abiertos") se resuelven en
   el spec como decisión o supuesto explícito. Ninguno queda como supuesto
   silencioso.
5. Antes de diseñar, revisar qué ya existe en `identity` y `market_data` para no
   duplicarlo (ver "Lo que ya existe" en cada módulo).

## Decisiones de alcance

- **Decisión R1: los RFP vigentes son obligatorios.** El catálogo los presenta
  como propuestos, fuera de los 462 puntos de función y sujetos a aprobación del
  cliente (Acta §1.3.5). Por decisión del equipo, todos los RFP vigentes se tratan
  como requisitos obligatorios del módulo al que se asignan, con la misma fuerza
  que un RF. La prioridad P1/P2/P3 que trae cada uno solo ordena el trabajo dentro
  del módulo.
- **Decisión R2: RFP-06 queda descartado.** "Distinguir ejecución simulada de
  ejecución real" no se implementa como requisito propio. Lo que ya exigen RF-37 y
  RF-39 (dejar explícito que los fondos son virtuales en sandbox) sigue vigente
  porque es parte de esos RF, no de RFP-06.
- **Decisión R3: RFP-07 queda descartado.** "Liquidar comisiones devengadas del
  comisionista" no se implementa. RF-43 sigue vigente: se calcula, cotiza y
  consulta la comisión, pero no se liquida por mes ni se registra su pago.
- **Nota del equipo:** el catálogo advierte que agregar RFP al alcance desplaza
  trabajo de la Ola A y que habría que medirlos y presupuestarlos. Hacerlos
  obligatorios es una decisión consciente del equipo, no algo que el catálogo
  establezca.

## Marco de la especificación (aplica a todos los módulos)

Resumen de la sección 2 del catálogo:

- Alpaca es la única integración bursátil: Broker API para cuentas, saldos,
  órdenes, posiciones, actividades y transferencias; Market Data API para
  cotizaciones, históricos y streaming. Todo en sandbox.
- Stripe se usa en modo sandbox solo para suscripciones premium. Los flujos de
  Stripe y Alpaca permanecen separados.
- Depósitos y retiros son simulados y no mueven dinero real.
- Cobertura, latencia y tipo de datos de mercado dependen del plan de Alpaca.
- No se comparan rutas de ejecución entre proveedores.
- Las conversiones de divisas solo existen si Alpaca las ofrece.
- Mercados: el alcance es el catálogo de Alpaca (AMEX, ARCA, BATS, NYSE, NASDAQ,
  NYSEARCA, OTC y TXSE). No hay Londres, Tokio ni Sídney, aunque el enunciado
  pida LSE, TSE y ASX; el recorte debe justificarse en el SAD.
- Las órdenes se envían a Alpaca (RF-32). No se construye un motor de calce
  interno ni un libro de órdenes propio (la Medición lo planeaba en CU-09 y
  CU-10; prevalece la especificación).

Acuerdos con el cliente (tabla 2 del catálogo):

| Acuerdo | Qué establece | RF |
| --- | --- | --- |
| Relación inversionista–comisionista | Descubrir comisionistas por sugerencias o búsqueda directa, consultar su reputación y gestionar la vinculación. | RF-13 a RF-15, RF-22, RF-23 |
| Propuestas y aprobación interna | El comisionista envía propuestas desde la aplicación; el inversionista las acepta o rechaza; la revisión, devolución y aprobación de órdenes usa procesos y mensajes internos. | RF-16 a RF-20, RF-30 |
| Cotización y ejecución | Las órdenes se distinguen de sus ejecuciones; la confirmación al usuario representa la adquisición o venta efectiva, con precio y momento. | RF-32, RF-33 |
| Órdenes fuera de horario | Las órdenes que no se procesan por cierre permanecen en cola; si el precio cambia antes de ejecutarse, se pide nueva autorización. | RF-31, RF-35 |
| Mercados y horarios | Horarios por mercado, zona horaria, apertura, cierre y festivos; la búsqueda presenta el mercado que informa Alpaca. | RF-24, RF-27, RF-28, RF-46 |
| Comisiones | Referencia del 2 % sobre el precio de ejecución, variable por mercado; solo el administrador la configura y modifica. | RF-43, RF-46 |
| Reputación y perfil de riesgo | Calificaciones por estrellas y señales de experiencia para el comisionista; perfil del inversionista con métricas, rating o porcentaje. | RF-04, RF-22, RF-23 |
| Notificaciones | Las notificaciones de propuestas y eventos relevantes se muestran en la aplicación; los canales externos (SMS, Telegram, correo) siguen las preferencias del usuario. | RF-07, RF-26, RF-33 |
| Integraciones | Alpaca único proveedor bursátil (Broker API y Market Data API); Stripe en sandbox para suscripciones premium. | RF-10 a RF-12, RF-24, RF-25, RF-29 a RF-40 |

Prioridades del catálogo: P1 = núcleo mínimo para registrarse, autenticarse,
fondear, consultar mercado, operar y ver el portafolio; P2 = complementa el
producto; P3 = diferible a Fase 2 o sujeto a confirmación.

## Estado y orden de los módulos

| MOD | Nombre | Responsable | RF principales | RFP obligatorios | Estado |
| --- | --- | --- | --- | --- | --- |
| MOD-01 | Identidad, Seguridad y Control de Acceso | Daniel Sanabria Rivera | RF-01–03, 06–09 | RFP-01, 02, 03, 08 | Implementado (`identity-market-backend`); brechas de `readme_agregar.md` especificadas en las tareas 22–30, pendientes |
| MOD-02 | Explorador de Mercados y Cotizaciones Bursátiles | Davidson E. Sánchez Gordillo | RF-24–28 | — | En `identity-market-backend` |
| MOD-03 | Motor de Órdenes y Negociación Bursátil | Juan José León Gómez | RF-29–35 | RFP-10 | Sin spec |
| MOD-04 | Billetera, Gestión de Fondos y Tesorería Multi-Moneda | Davidson E. Sánchez Gordillo | RF-10–12, 36–40 | RFP-11 | Sin spec |
| MOD-05 | Portafolio de Inversiones y Métricas Financieras | Juan José León Gómez | RF-04–05, 41–42 | RFP-12 | Sin spec |
| MOD-06 | Red y Portal de Comisionistas Financieros | María Fernanda Vélez Benítez | RF-13–23 | RFP-04, 05, 09 | Sin spec |
| MOD-07 | Administración Central, Regulación y Parametrización | Jan Henrik Sánchez Jerez | RF-43–47 | RFP-13 | Sin spec |
| MOD-08 | Experiencia Móvil Adaptativa y Rendimiento Cross-Platform | Daniel Sanabria Rivera | ninguno (transversal) | — | Solo frontend |

Orden sugerido por el catálogo (§7.3): MOD-01 → (MOD-02 y MOD-04 en paralelo) →
MOD-03 → MOD-05 → MOD-06 y MOD-07, con MOD-08 durante todo el proceso.

Dependencias (tabla 21 del catálogo):

| MOD | Depende de | Motivo |
| --- | --- | --- |
| MOD-01 | — (base) | Provee identidad, MFA, roles, preferencias y canales de notificación a todos los demás. |
| MOD-02 | MOD-01; Alpaca (Market Data y calendario) | Búsqueda, cotizaciones y horarios requieren sesión y la fuente externa de datos. |
| MOD-04 | MOD-01; Alpaca (cuentas y transferencias); Stripe | Cuenta, saldos y movimientos dependen del usuario y de Alpaca; los pagos premium, de Stripe. |
| MOD-03 | MOD-01, MOD-02, MOD-04; Alpaca (órdenes) | Crear y validar una orden consulta cotización, horario, cuenta y efectivo disponible; la revisión usa mensajes de MOD-06. |
| MOD-05 | MOD-03, MOD-02, MOD-04 | Posiciones, perfil de riesgo y reportes se alimentan de órdenes y ejecuciones. |
| MOD-06 | MOD-01, MOD-03, MOD-05 | La propuesta aceptada se convierte en orden; la aprobación y las comisiones salen de las ejecuciones. |
| MOD-07 | MOD-01; datos de todos los módulos | RBAC, tarifas, auditoría y BI leen lo que producen los demás módulos. |
| MOD-08 | Todos | Adapta las pantallas ya construidas. |

Oleadas del catálogo (tabla 19): Ola A (P1) RF-01–03, 24–25, 27, 29–34, 36–37,
39, 41 con RFP-01 y RFP-04; Ola B (P2) RF-04–09, 13–20, 22–23, 26, 28, 35, 40,
42–44, 46–47; Ola C (P3) RF-10–12, 21, 38, 45. Los datos de administración que
la Ola A necesita (mercados, horarios y la tarifa base del 2 %) se cargan como
datos semilla; la pantalla de parametrización (RF-46) llega en la Ola B.

---

## MOD-03 — Motor de Órdenes y Negociación Bursátil

Responsable: Juan José León Gómez. Mockups: 06, 03 (entrada rápida). Participa
en: RF-07, 09, 20, 28, 43.

### RF principales

**RF-29 — Crear orden bursátil mediante Alpaca Broker API** (Inversionista; Comisionista; P1)
El sistema debe permitir crear una orden de compra o venta para un activo
negociable en la cuenta de inversión del usuario, indicando símbolo, cantidad,
lado, tipo de orden, precio límite o stop cuando aplique y vigencia. Los tipos,
parámetros, fracciones y horarios permitidos deberán corresponder a los
soportados por Alpaca para la cuenta y el entorno utilizados.

**RF-30 — Validar y confirmar orden** (Inversionista; Comisionista; P1)
El sistema debe gestionar la revisión de la orden entre inversionista y
comisionista mediante los procesos y mensajes internos de la aplicación,
permitiendo enviarla, revisarla, devolverla para ajustes y aprobarla antes de su
envío al proveedor. Antes del envío deberá validar el estado de la cuenta
Alpaca, la negociabilidad del activo, los parámetros admitidos por la API, la
disponibilidad de efectivo o capacidad de compra y los controles internos de
Acciones UD. Para órdenes que superen los umbrales configurados deberá exigir
autorización adicional. Si el precio cambia mientras la orden está pendiente y
corresponde solicitar una nueva autorización, deberá registrar la decisión del
inversionista y los precios anterior y actualizado. La aceptación final de la
orden dependerá de la respuesta de Alpaca.
*Enunciado:* exige al menos 1 acción disponible para vender, fondos suficientes
para comprar y confirmación en 5 segundos o menos.

**RF-31 — Ratificar nueva cotización** (Inversionista; P1)
El sistema debe permitir solicitar y registrar una nueva autorización del
inversionista cuando el precio de una orden pendiente cambie antes de su
ejecución. Debe conservar la orden, el precio anterior, el precio actualizado,
la decisión del inversionista y el instante de respuesta. La orden no continuará
su proceso de ejecución hasta contar con la autorización correspondiente.

**RF-32 — Enviar orden al bróker y registrar resultado de ejecución** (Sistema; P1)
El sistema debe enviar a Alpaca Broker API las órdenes aprobadas y validadas,
registrando el identificador externo, el estado devuelto y una clave de
idempotencia cuando corresponda. También debe recibir y registrar las
actualizaciones y ejecuciones mediante los mecanismos disponibles en la API,
incluyendo identificadores de orden y ejecución, estado, cantidad ejecutada,
precio de ejecución y marcas de tiempo. La confirmación de operación al usuario
debe corresponder a la ejecución efectiva y adquisición de las acciones, no
únicamente a la recepción de la orden.
*Enunciado:* define diez estados de orden: Pendiente, Enviada, Firmada por
Comisionista, En Ejecución, Cancelada, Rechazada, Expirada, En Revisión, Fallida
y Detenida (RFP-10).

**RF-33 — Consultar seguimiento de órdenes y notificar ejecución** (Inversionista; Sistema; P1)
El sistema debe permitir consultar el seguimiento de una orden, mostrando su
estado, instante de actualización, cantidad, precio, ejecuciones y referencia
del proveedor. Asimismo, debe notificar al usuario la ejecución efectiva de la
operación, indicando instrumento, sentido, cantidad adquirida o vendida, precio
de ejecución, comisión, fecha y hora de cruce o ejecución. La notificación se
presentará dentro de la aplicación y, cuando el usuario lo haya habilitado, por
el canal externo seleccionado.

**RF-34 — Solicitar cancelación de orden** (Inversionista; P1)
El sistema debe permitir solicitar la cancelación de una orden, identificando la
orden, su estado previo, el motivo de cancelación y la confirmación del usuario.
*Enunciado (escenario 10):* cancelar una orden pendiente libera el saldo
reservado.

**RF-35 — Programar orden fuera de horario** (Inversionista; P2)
El sistema debe permitir guardar una instrucción de orden para su envío en la
próxima sesión elegible cuando el mercado esté cerrado, registrando activo,
parámetros, fecha/hora prevista y confirmación del usuario. La programación será
administrada por Acciones UD; el envío efectivo se realizará únicamente cuando
se cumplan las condiciones de horario y las reglas vigentes de Alpaca.

Nota del catálogo: tipos de orden Market, Limit, Stop Loss y Take Profit, según
lo que Alpaca soporte. RF-30 y RF-31 concentran la revisión, la autorización
adicional y la nueva autorización por cambio de precio.

### RFP obligatorios

**RFP-10 — Gestionar estados de orden y poner en revisión las pendientes ante un cambio de horario** (P2; también MOD-07 y MOD-01)
Mantiene los diez estados de orden del enunciado y, cuando el administrador
cambia un horario, pasa las órdenes pendientes a En Revisión y avisa a los
usuarios afectados.
Fuente: Enunciado (estados de orden; escenario 7). Relación: complementa RF-32,
RF-33 y RF-46.

### Lo que ya existe y se reutiliza

- Controles de órdenes del usuario (RF-09): `identity`, tabla `order_controls`,
  endpoint `GET/PUT /users/preferences/orders`. MOD-03 los aplica en la
  validación de RF-30; no los vuelve a almacenar.
- Preferencias y canales de notificación (RF-07): `identity`. El `Notifier` y
  sus senders (in-app, correo, Telegram, SMS simulado) están en `market_data`.
- Cotización vigente, catálogo de instrumentos, negociabilidad (RF-25, RF-28) y
  calendario/reloj de mercado (RF-27): `market_data`.
- Cuenta Alpaca del usuario y su estado: `identity`, tabla `kyc_accounts`
  (`alpaca_account_id`, `status`). `can_trade` no es columna: se deriva del
  estado (`status == "ACTIVE"`, `identity/domain/kyc.py`).
- Permisos: el RBAC de `identity` (`require_permission`, `require_premium`).

### Puntos abiertos

- Confirmar en la API de Alpaca el soporte de Stop Loss, Take Profit y trailing
  stop (el enunciado incluye trailing stop entre los tipos predeterminados de
  RF-09).
- Validación de tenencia al vender ("al menos 1 acción", tabla 25): definir de
  dónde sale la posición (Alpaca o MOD-05).
- Confirmación en 5 segundos o menos: definir qué se mide (aceptación de Alpaca
  o respuesta propia).
- Mapeo entre los diez estados del enunciado y los estados que devuelve Alpaca.
- La revisión con el comisionista (RF-30) depende de MOD-06: definir el contrato
  mínimo si MOD-03 se construye antes.
- Reserva de saldo al crear la orden y su liberación al cancelar (RF-34):
  definir si se apoya en `buying_power` de Alpaca o en una reserva propia.

---

## MOD-04 — Billetera, Gestión de Fondos y Tesorería Multi-Moneda

Responsable: Davidson E. Sánchez Gordillo. Mockups: 07. Participa en: RF-30.
Con aporte de: RFP-01.

### RF principales

**RF-10 — Contratar plan premium** (Inversionista; P3)
El sistema debe permitir al usuario contratar un plan premium, seleccionando el
plan y su periodicidad, e iniciando el proceso de pago mediante el identificador
de checkout. La contratación debe considerar el estado de confirmación recibido
del proveedor de pagos.
*Enunciado:* fija USD 12 al mes o USD 120 al año; se contrata al registrarse o
desde el perfil.

**RF-11 — Cancelar suscripción** (Inversionista; P3)
El sistema debe permitir solicitar la cancelación de una suscripción,
identificando la suscripción correspondiente, registrando el motivo y
confirmando la solicitud.

**RF-12 — Consultar suscripción y pagos** (Inversionista; P3)
El sistema debe permitir consultar la información de la suscripción y sus pagos,
incluyendo el plan, precio, periodo actual, estado de la suscripción, pago
reciente y fecha de cobro.
Operación complementaria asociada a RF-10, RF-11 y RF-12: recepción y aplicación
de notificaciones de pago de Stripe (referencia del proveedor, usuario, plan,
importe, periodo, resultado y fecha) para actualizar la suscripción y el cobro.

**RF-36 — Crear o asociar cuenta de inversión Alpaca y consultar saldos** (Inversionista; Sistema; P1)
El sistema debe permitir iniciar y administrar el proceso de apertura de una
cuenta de inversión mediante Alpaca Broker API, asociando el identificador de la
cuenta externa con el usuario de Acciones UD y consultando su estado. Una vez
habilitada, debe permitir consultar los saldos y capacidades de compra que
Alpaca exponga, incluyendo efectivo, fondos disponibles y otros valores
relevantes devueltos por el proveedor. En sandbox, la cuenta y sus fondos serán
simulados.

**RF-37 — Solicitar depósito simulado en cuenta Alpaca** (Inversionista; P1)
El sistema debe permitir registrar una solicitud de depósito en el entorno
sandbox de Alpaca, indicando cuenta, importe, moneda y referencia del medio o
relación de financiación de prueba cuando corresponda. El sistema mostrará el
estado devuelto por Alpaca y dejará explícito que el saldo acreditado es virtual
y no representa una transferencia de dinero real.

**RF-38 — Consultar moneda y registrar conversión solo si está soportada** (Inversionista; P3)
El sistema debe identificar la moneda de los saldos y movimientos devueltos por
Alpaca. No ejecutará conversiones de divisas por cuenta propia. Si el programa y
los endpoints habilitados por Alpaca ofrecen una operación de conversión
aplicable, podrá solicitarla y registrar importe, monedas, tasa, cargos y
estado; de lo contrario, la conversión quedará fuera del alcance implementado.

**RF-39 — Solicitar retiro simulado de fondos** (Inversionista; P1)
El sistema debe permitir solicitar un retiro en el entorno sandbox de Alpaca,
indicando la cuenta, importe, dirección y relación bancaria de prueba exigida
por el proveedor. Debe registrar el estado de la transferencia y aclarar que la
operación solo modifica fondos virtuales. Los medios, monedas y destinos
habilitados en producción no se presuponen en esta especificación.

**RF-40 — Consultar movimientos financieros y registrar confirmaciones externas** (Inversionista; P2)
El sistema debe permitir consultar las actividades y transferencias asociadas a
la cuenta Alpaca por periodo y tipo, presentando identificador externo, fecha,
importe, moneda, dirección, estado y descripción cuando estén disponibles.
También debe registrar las actualizaciones recibidas del proveedor para
depósitos y retiros simulados. Las conversiones solo se incluirán si el servicio
correspondiente está habilitado para la integración.

### RFP obligatorios

**RFP-11 — Notificar cambios de saldo** (P3; también MOD-01)
Avisa al usuario cuando cambia su saldo por depósitos, retiros, compras o
ventas.
Fuente: Enunciado (notificaciones: actualizaciones de saldo). Relación: RF-07 no
lista este aviso.

**RFP-01 — Capturar datos de identidad para abrir la cuenta Alpaca (KYC)** (P1; compartido con MOD-01)
Recoge los datos de identidad y de perfil financiero que Alpaca exige para abrir
la cuenta y muestra el estado de la verificación antes de permitir operar.
Fuente: Plan Maestro MOD-01 (kyc_status); Medición §7 (CU-04); Alpaca Broker API.
Relación: complementa RF-01 y RF-36.
**Nota del equipo:** la parte de MOD-01 ya está implementada (ver abajo). MOD-04
no vuelve a capturar KYC; parte de la cuenta ya creada.

### Lo que ya existe y se reutiliza

- La apertura de la cuenta Alpaca ya ocurre en `identity`: `POST /kyc/account`
  crea la cuenta en Alpaca Broker API y guarda `alpaca_account_id` y `status` en
  `kyc_accounts`; `GET /kyc/status` refresca el estado. La parte "crear o
  asociar cuenta" de RF-36 está cubierta; MOD-04 debe reutilizar
  `kyc_accounts` y no crear una segunda asociación.
- Brechas que `identity-market-backend` dejó fuera a propósito y que pertenecen
  a este módulo (de `readme_agregar.md`):
  - B1: no existe endpoint de saldos ni posiciones; en `src/` no se consume
    `/v2/accounts/{id}`, `/v2/accounts/{id}/positions` ni
    `/v2/portfolio/history` (rutas citadas en el readme; confirmar las de
    Broker API al diseñar).
  - B2: `AccountResponse` del cliente de cuentas descarta `cash`,
    `buying_power`, `portfolio_value`, `equity` y `long_market_value`.
  - D2 (parte del plan): `/users/me` devuelve `contracted_plan` en `null`
    fijo; el plan contratado lo provee este módulo (RF-10 a RF-12).
- Regla de frescura propuesta en el readme para saldos: si Alpaca falla,
  responder `unavailable: true` en vez de ceros, para no confundir "sin datos"
  con "sin dinero".
- Flag `is_premium` del usuario: hoy lo fija un administrador
  (`PUT /admin/users/{id}/premium`). RF-10 a RF-12 deben definir cómo la
  suscripción de Stripe actualiza ese flag sin romper el endpoint actual.
- Notificaciones (RFP-11): `Notifier` de `market_data` y preferencias de
  `identity`.

### Puntos abiertos

- El título "Multi-Moneda" es más amplio que el alcance: RF-38 solo identifica
  la moneda salvo que Alpaca ofrezca conversión.
- Sandbox de Broker API: cuenta de la firma prefondeada con USD 50.000 y fondeo
  simulado por ACH, transferencia o journal. Elegir el mecanismo para RF-37 y
  RF-39.
- Webhook o consulta periódica para registrar confirmaciones externas (RF-40).
- Stripe: modelar suscripción, checkout y webhook de pago en sandbox (RF-10 a
  RF-12 son Brecha en el Plan Maestro).

---

## MOD-05 — Portafolio de Inversiones y Métricas Financieras

Responsable: Juan José León Gómez. Mockups: 03, 04. Participa en: RF-08, 32–33.
Con aporte de: RFP-05, RFP-08.

### RF principales

**RF-04 — Construir perfil de actividad inversora** (Sistema; P2)
El sistema debe construir un perfil de riesgo del inversionista mediante
métricas de actividad y comportamiento, presentándolo como una clasificación,
rating o porcentaje. El perfil podrá considerar la cantidad y frecuencia de sus
operaciones, el volumen negociado en USD, los mercados e instrumentos utilizados
y la distribución de sus activos.

**RF-05 — Estadísticas descriptivas de inversiones** (Inversionista; P2)
El sistema debe generar estadísticas descriptivas de las inversiones para un
periodo definido, incluyendo operaciones, volumen en USD y porcentajes de
participación por mercado, instrumento y sector.

**RF-41 — Consultar posiciones de portafolio e historial de operaciones** (Inversionista; P1)
El sistema debe permitir consultar las posiciones del portafolio, mostrando
instrumento, cantidad total, cantidad reservada, precio, costo promedio, valor
de mercado y resultado. También debe permitir consultar el historial de
operaciones ejecutadas por periodo e instrumento, incluyendo fecha,
instrumento, sentido de la operación, cantidad, precio de ejecución y comisión.

**RF-42 — Generar reportes de inversiones** (Inversionista; P2)
El sistema debe permitir generar reportes de inversión para un periodo
determinado, incluyendo posiciones, volumen, ganancias realizadas y no
realizadas, comisiones y tipo de reporte. El análisis funcional también
contempla la emisión de resúmenes diarios y reportes mensuales con información
de operaciones, importes, rentabilidad, comisiones y enlace al reporte
generado.

Nota del catálogo: RF-04 y RF-05 necesitan órdenes y ejecuciones; por eso se
construyen sobre el portafolio. RF-42 agrupa el reporte bajo demanda, el resumen
diario y el reporte mensual.

### RFP obligatorios

**RFP-12 — Reportes por perfil (comisionista y cliente)** (P2; también MOD-06)
Genera por periodo ganancias y pérdidas, resumen de activos, portafolio por
cliente y por comisionista, comisiones pagadas y transacciones.
Fuente: Enunciado (módulo de reportes). Relación: RF-42 cubre solo al
inversionista.

### Lo que ya existe y se reutiliza

- Preferencias de visualización del portafolio (RF-08): `identity`, tabla
  `portfolio_view_settings`, endpoint `GET/PUT /users/preferences/portfolio`.
  MOD-05 las aplica; no las vuelve a almacenar.
- Opción de reporte mensual elegida en el registro (RF-01) y preferencia de
  resumen diario (RF-07): `identity`.
- Sector de los instrumentos: `market_data`, `instruments.sector` (Alpaca no lo
  provee; es dato propio).
- Cotizaciones para valorar posiciones: `market_data`.

### Puntos abiertos

- RF-04 es Brecha: definir las métricas y la fórmula del rating o porcentaje de
  riesgo.
- RF-05 es Parcial: la estadística por sector exige datos propios (sector no lo
  da Alpaca); la capitalización tampoco.
- Fuente de las posiciones: Alpaca (`positions`) o reconstrucción desde las
  ejecuciones de MOD-03. Definir cuál prevalece.
- Exportación PDF de reportes y la programación del resumen diario y el reporte
  mensual (RF-42 es Parcial).
- RFP-12 por comisionista depende de la vinculación de MOD-06 y debe respetar
  RFP-04.

---

## MOD-06 — Red y Portal de Comisionistas Financieros

Responsable: María Fernanda Vélez Benítez. Mockups: 08, 10, 11, 12. Participa
en: RF-30, 43. Con aporte de: RFP-02, RFP-12.

### RF principales

**RF-13 — Consultar comisionistas disponibles y vincular comisionista** (Inversionista; P2)
El sistema debe permitir consultar comisionistas disponibles mediante
sugerencias de la plataforma o búsqueda directa por nombre. Los resultados
presentarán información como nombre, especialidad, experiencia, certificaciones
y reputación. También debe permitir que un inversionista solicite la vinculación
con un comisionista, registrando las partes involucradas, la fecha de solicitud
y el consentimiento correspondiente.

**RF-14 — Desvincular comisionista** (Inversionista; P2)
El sistema debe permitir al inversionista solicitar la desvinculación de un
comisionista asociado, identificando la vinculación, registrando el motivo y
confirmando la operación.

**RF-15 — Consultar historial de vinculaciones** (Inversionista; P2)
El sistema debe permitir consultar el historial de vinculaciones de un
inversionista, utilizando criterios como el periodo y el estado de la
vinculación. La información presentada debe incluir el comisionista, las fechas
de inicio y finalización, el estado y el motivo de finalización cuando
corresponda.

**RF-16 — Crear y enviar propuesta** (Comisionista; P2)
El sistema debe permitir al comisionista crear y enviar una propuesta para un
inversionista, especificando el instrumento, el sentido de la operación, la
cantidad, el precio de referencia y el costo estimado.

**RF-17 — Modificar propuesta no aprobada** (Comisionista; P2)
El sistema debe permitir modificar una propuesta que no haya sido aprobada,
identificando la propuesta y la versión correspondiente.

**RF-18 — Retirar propuesta** (Comisionista; P2)
El sistema debe permitir retirar una propuesta, identificándola, registrando el
motivo del retiro y confirmando la acción.

**RF-19 — Aceptar o rechazar propuesta** (Inversionista; P2)
El sistema debe permitir registrar la decisión del inversionista frente a una
propuesta, indicando si la acepta o la rechaza, junto con un comentario y la
fecha de decisión.

**RF-20 — Registrar aprobación interna de propuesta** (Comisionista; P2)
El sistema debe permitir al comisionista registrar dentro de la aplicación su
aprobación o autorización de una propuesta, identificando la propuesta, el
comisionista, la decisión, la fecha y la evidencia de la interacción. La
aprobación se gestionará mediante los procesos y mensajes internos de la
plataforma.

**RF-21 — Consultar historial de propuestas** (Inversionista; Comisionista; P3)
El sistema debe permitir consultar el historial de propuestas mediante criterios
como el periodo y el estado. Los resultados deben presentar información del
comisionista, instrumentos incluidos, importe y versión de cada propuesta.

**RF-22 — Publicar calificación** (Inversionista; P2)
El sistema debe permitir publicar una calificación de un comisionista mediante
una puntuación por estrellas, registrando la valoración, el comentario y la
fecha correspondiente.

**RF-23 — Consultar reseñas de comisionista** (Inversionista; P2)
El sistema debe permitir consultar la reputación de un comisionista, mostrando
su nombre, calificación promedio por estrellas, cantidad de reseñas y señales de
experiencia como el número de operaciones o servicios realizados, con sus fechas
y comentarios publicados cuando existan.

Notas del catálogo: RF-13 cubre dos funciones (consultar comisionistas y
solicitar la vinculación). La calificación queda asociada a una vinculación
existente entre inversionista y comisionista. RF-20 se integra con MOD-03 y deja
rastro de auditoría (MOD-07).

### RFP obligatorios

**RFP-04 — Restringir al comisionista a sus clientes asociados** (P1; también MOD-01)
Cada comisionista consulta y gestiona solo la información de los clientes
vinculados que lo contrataron.
Fuente: Enunciado (comisionistas); Acta §3.1.2 y §3.3 (meta 5). Relación: regla
transversal a RF-13 a RF-21 y RF-30. Es P1 porque el enunciado y el Acta exigen
que cada comisionista vea solo a sus clientes.

**RFP-05 — Consultar clientes asignados, su portafolio y sus órdenes (comisionista)** (P2; también MOD-05)
Lista los clientes vinculados al comisionista y permite ver el portafolio y las
órdenes de cada uno, y solo de ellos.
Fuente: Enunciado (comisionistas); Plan Maestro MOD-06 (Mockup 10,
`GET /advisors/my-clients`). Relación: contraparte de RF-15 para el
comisionista.

**RFP-09 — Solicitar comisionista al registrarse o desde el perfil y autorizar que opere en nombre del usuario** (P2; también MOD-01)
El usuario puede pedir un comisionista durante el registro o después, y
autoriza si este genera órdenes por él.
Fuente: Enunciado (comisionistas; escenario 6). Relación: complementa RF-13.

### Lo que ya existe y se reutiliza

- Registro y activación de comisionistas (implementado): `identity`
  (`POST /auth/register/broker` con `firm_name` y `license_number`;
  `POST /admin/users/{id}/broker-activation`, que hoy asigna solo el rol
  `broker`). Especificado y pendiente (tarea 24.1): que la activación asigne
  también el rol `investor`.
- Solicitud de comisionista al registrarse: `identity` ya acepta y guarda
  `broker_requested` en `users`, pero hoy no se lee en ninguna parte.
  Especificado y pendiente (tareas 24.3 y 25): exponerlo en `/users/me` y en el
  directorio de usuarios del admin. RFP-09 debe partir de ese dato y no crear
  otro flag.
- Brecha D2 de `readme_agregar.md`: `/users/me` devuelve `associated_broker` en
  `null` fijo. La relación broker–cliente la crea este módulo y debe alimentar
  ese campo (RF-06).
- Audit log de acciones administrativas: especificado en `identity`
  (`admin_audit_log`, tarea 28), pendiente de implementar. Sirve como patrón
  para la evidencia de RF-20.

### Puntos abiertos

- Modelo de la vinculación (estados, consentimiento, motivo de fin) y cómo se
  expresa RFP-04 en el control de acceso: una regla de pertenencia
  comisionista–cliente aplicada en cada consulta, no un filtro en la interfaz.
- Autorización para operar en nombre del usuario (RFP-09): consentimiento
  explícito, trazable y revocable.
- Chat interno: el Plan Maestro lo contempla; definir el mínimo de "mensajes
  internos" que necesitan RF-20 y RF-30.
- Señales de experiencia de RF-23 (número de operaciones o servicios) dependen
  de MOD-03.

---

## MOD-07 — Administración Central, Regulación y Parametrización

Responsable: Jan Henrik Sánchez Jerez. Mockups: 13, 14, 15, 16. Participa en:
RF-03, 20, 27. Con aporte de: RFP-02, RFP-10.

### RF principales

**RF-43 — Consultar y cotizar comisiones** (Inversionista; Comisionista; P2)
El sistema debe calcular la comisión de una operación tomando como referencia
una tasa base del 2 % sobre el precio de ejecución, aplicando la tasa vigente
configurada para el mercado correspondiente. Debe presentar el importe de la
operación, la tasa aplicada y el valor de la comisión. También debe permitir
consultar las comisiones generadas por periodo, comisionista y cliente asociado,
presentando las operaciones y los importes correspondientes.
*Enunciado:* compra suma la comisión y venta la resta; con comisionista se
reparte 60 % plataforma y 40 % comisionista (parametrizable); se redondea a 2
decimales y se informa antes.

**RF-44 — Consultar eventos auditables** (Auditor; Administrador; P2)
El sistema debe permitir consultar los eventos de auditoría asociados a un
usuario investigado y a un periodo determinado, con el fin de revisar las
acciones y operaciones registradas.
*Enunciado:* exige registrar quién creó y validó la orden, qué comisionista la
firmó y cuándo se envió al mercado (no repudio).

**RF-45 — Restringir o rehabilitar cuenta e identificar operaciones potencialmente atípicas** (Administrador; Analista; P3)
El sistema debe permitir restringir o rehabilitar una cuenta, registrando la
cuenta afectada, el motivo, el tipo de restricción, la decisión, la evidencia y
el analista responsable. También debe identificar operaciones potencialmente
atípicas mediante información como periodo, usuario y monto.
*Enunciado:* asigna automáticamente el estado Operaciones Restringidas al
detectar actividad inusual.

**RF-46 — Configurar mercados, horarios, restricciones, tarifas y reparto** (Administrador; P2)
El sistema debe permitir al administrador configurar los parámetros de operación
de cada mercado, incluyendo zona horaria, horarios de apertura y cierre,
feriados y vigencias de las restricciones. También debe permitir configurar y
modificar exclusivamente las tasas de comisión aplicables por mercado, tomando
como referencia una comisión base del 2 %, así como los porcentajes de
distribución que correspondan y sus periodos de vigencia.
*Enunciado:* al cambiar un horario se notifica a los usuarios suscritos y las
órdenes pendientes pasan a En Revisión (RFP-10).

**RF-47 — Generar tablero de inteligencia de negocio (BI)** (Administrador; P2)
El sistema debe generar un tablero de indicadores del negocio para un periodo
seleccionado, incluyendo cantidad de usuarios registrados, usuarios activos,
volumen negociado, comisiones de la plataforma y suscripciones activas.
*Enunciado:* agrega crecimiento por interés, ingresos por fuente y mercado, y
tipos de usuario (principiante o experimentado, con o sin comisionista).

Notas del catálogo: el registro de auditoría debe ser inmutable (Plan Maestro).
RF-45 no define el algoritmo de operaciones atípicas. RF-46 reúne la
configuración de mercados y horarios y la de tarifas y reparto. RF-43 se traza a
MOD-07 para no duplicar el cálculo y la consulta administrativa de comisiones.

### RFP obligatorios

**RFP-13 — Reporte de auditoría de un usuario** (P2)
Resume la actividad de un usuario en un periodo, la compara con el patrón
promedio, señala operaciones anómalas y se puede compartir con cumplimiento.
Fuente: Enunciado, escenario 8. Relación: complementa RF-44 y RF-45.

RFP-07 (liquidar comisiones devengadas) está descartado (Decisión R3).

### Lo que ya existe y se reutiliza

- Horarios por defecto y excepciones de calendario por mercado (parte de RF-46):
  `market_data`, endpoints `/admin/markets/{market_code}/default-schedule` y
  `/admin/markets/{market_code}/schedule-overrides`. MOD-07 añade restricciones,
  tarifas y reparto; no duplica la configuración de horarios.
- RBAC (RF-03): `identity`, endpoints `/admin/roles`, `/admin/permissions` y
  `/admin/users/{id}/roles`. La pantalla de gestión vive en MOD-07; la lógica ya
  existe.
- Audit log de acciones administrativas de identidad: especificado en
  `identity` (Requirement 25, tarea 28), pendiente de implementar:
  `admin_audit_log` con `GET /admin/audit-log` (`admin:rbac`), inmutable por
  trigger. RF-44 debe ampliarlo a operaciones (órdenes, propuestas) en lugar de
  crear un segundo registro paralelo.
- Directorio de usuarios del admin: especificado en `identity`
  (`GET /admin/users`, Requirements 20 y 21, tarea 25), pendiente de
  implementar.
- Estado de cuenta del usuario (`users.account_status`): hoy `active` o
  `pending_broker_activation`. La restricción de RF-45 debe definir cómo convive
  con ese campo.

### Puntos abiertos

- RF-45 es Brecha: definir un alcance mínimo y una regla explícita de
  operaciones atípicas (la fuente no la define). Lo mismo para la comparación con
  el "patrón promedio" de RFP-13.
- Fórmula de la comisión: tasa por mercado, suma en compra y resta en venta,
  reparto 60/40 parametrizable, redondeo a 2 decimales e información previa.
  Registrarla en los criterios de aceptación.
- Desgloses del BI por mercado, sector y tipo de usuario (RF-47 es Parcial).
- No repudio de cada orden (RF-44): qué datos de MOD-03 y MOD-06 se auditan.

---

## MOD-08 — Experiencia Móvil Adaptativa y Rendimiento Cross-Platform

Responsable: Daniel Sanabria Rivera. Mockups: 17. Sin RF propios: es transversal
a RF-01 a RF-47 y no crea lógica de negocio. Adapta al móvil (viewport de
referencia 390 × 844 px, Lighthouse superior a 90 en Performance y
Accessibility) las pantallas de todos los módulos. Es trabajo de frontend: no
requiere spec en este repositorio de backend, salvo optimizaciones de respuesta
que se pidan explícitamente.

---

## Módulos ya especificados (referencia)

Estos RF y RFP están cubiertos por `.kiro/specs/identity-market-backend`. Se
listan para que los specs nuevos no los dupliquen y respeten su contrato.

### MOD-01 — Identidad, Seguridad y Control de Acceso

**RF-01 — Registrar inversionista** (Visitante / Inversionista; P1)
El sistema debe permitir el registro de un inversionista mediante sus nombres,
apellidos, correo electrónico, teléfono, país de residencia y clave. Durante el
registro se contempla la aceptación de términos y la configuración de la opción
de reporte mensual.
*Enunciado:* agrega al registro los intereses, el nivel (principiante o
experimentado), la solicitud de comisionista y la opción premium (RFP-08,
RFP-09); Alpaca exige datos de identidad (RFP-01).

**RF-02 — Autenticar con MFA** (Todos los roles; P1)
El sistema debe permitir la autenticación del usuario mediante correo
electrónico y clave, incorporando un código de segundo factor y la validación
del resultado de autenticación.
*Decisión ya tomada (spec D1):* el segundo factor es TOTP.

**RF-03 — Administrar roles y permisos** (Administrador; P1)
El sistema debe permitir administrar la asignación de roles y permisos a los
usuarios, incluyendo la definición de los periodos de vigencia de dichas
asignaciones.

**RF-06 — Consultar información de cuenta** (Inversionista; P2)
El sistema debe permitir al inversionista consultar la información de su cuenta,
incluyendo sus datos de usuario, correo, estado de cuenta, fecha de registro,
plan contratado y comisionista asociado.
*Nota del equipo:* `contracted_plan` lo alimenta MOD-04 y `associated_broker`
MOD-06; hoy se devuelven en `null`.

**RF-07 — Configurar preferencias de avisos** (Inversionista; P2)
El sistema debe permitir configurar las preferencias de notificación del
usuario, incluyendo avisos de apertura y cierre de mercados, propuestas,
solicitudes de aprobación, cambios de precio, confirmaciones de ejecución y
resúmenes diarios. El usuario podrá elegir voluntariamente los canales externos
disponibles, como SMS, Telegram o correo electrónico, y podrá desactivar los
canales que no desee utilizar.

**RF-08 — Configurar visualización del portafolio** (Inversionista; P2)
El sistema debe permitir personalizar la visualización del portafolio mediante
la selección del tipo de vista, el criterio de ordenamiento y el umbral para
ocultar información.

**RF-09 — Configurar controles de órdenes** (Inversionista; P2)
El sistema debe permitir configurar controles para la creación de órdenes,
incluyendo el tipo de orden predeterminado, el límite diario de órdenes, el
umbral para considerar una orden elevada y la exigencia de una confirmación
adicional.
*Enunciado:* incluye trailing stop entre los tipos de orden predeterminados.

RFP de MOD-01, ya implementados:

- **RFP-01 — Capturar datos de identidad para abrir la cuenta Alpaca (KYC)** (P1).
  La parte de MOD-04 se describe en ese módulo.
- **RFP-02 — Registro diferenciado por rol** (P2): permite crear cuentas de
  comisionista y de administrador, además de la de inversionista, con los datos
  propios de cada rol.
- **RFP-03 — Gestionar sesiones, dispositivos y cierre de sesión** (P2): muestra
  las sesiones y dispositivos activos, permite cerrarlos y ofrece el cierre de
  sesión seguro.
- **RFP-08 — Registrar intereses y nivel de experiencia, y mostrar dashboard
  inicial** (P2): al crear la cuenta el usuario indica sus intereses (mercado o
  sector) y si es principiante o experimentado; el dashboard inicial se ajusta a
  ellos.

### MOD-02 — Explorador de Mercados y Cotizaciones Bursátiles

**RF-24 — Buscar instrumentos y consultar bolsas disponibles en Alpaca** (Inversionista; Comisionista; P1)
El sistema debe permitir buscar directamente una empresa o acción por nombre o
símbolo y consultar el catálogo de activos expuesto por Alpaca Broker API. La
plataforma identificará y mostrará el mercado o bolsa asociado al activo,
utilizando los datos devueltos por el proveedor y distinguiendo los activos
habilitados para negociación de aquellos disponibles únicamente para consulta.

**RF-25 — Consultar datos de mercado actuales e históricos** (Inversionista; Comisionista; P1)
El sistema debe permitir consultar los datos de mercado disponibles para un
activo mediante Alpaca Market Data API, incluyendo los campos que entregue el
proveedor (por ejemplo, último precio, bid/ask, volumen y hora de
actualización). También debe permitir consultar barras o históricos para un
activo y rango de fechas, con apertura, máximo, mínimo, cierre y volumen cuando
estén disponibles. La cobertura, latencia y tipo de feed dependerán del plan y
permisos de datos habilitados para el proyecto.

**RF-26 — Gestionar instrumentos observados y alertas por precio** (Inversionista; P2)
El sistema debe permitir administrar listas de instrumentos observados,
agregando o quitando instrumentos. Asimismo, debe permitir configurar alertas de
precio mediante un comparador y un valor umbral, activar la alerta y emitir una
notificación cuando se cumpla la condición, indicando destinatario, instrumento,
precio observado, umbral, fecha y canal.
*Enunciado:* reserva esta función a usuarios premium.

**RF-27 — Consultar calendario y estado del mercado soportado** (Inversionista; P1)
El sistema debe permitir consultar, mediante los servicios de calendario y reloj
disponibles en Alpaca, las sesiones, horarios, días festivos y estado del
mercado soportado para una fecha determinada. La plataforma deberá presentar los
horarios según la zona horaria correspondiente y permitir parametrizar los
horarios de apertura y cierre y las variaciones de calendario por mercado.
Cuando se habiliten notificaciones, podrá informar la apertura y el cierre de
las sesiones correspondientes.

**RF-28 — Consultar bolsa y disponibilidad de negociación de un activo** (Inversionista; Comisionista; P2)
El sistema debe mostrar la bolsa reportada por Alpaca para cada activo y sus
indicadores de disponibilidad, estado y negociabilidad. No comparará ni
seleccionará rutas alternativas de ejecución entre distintos proveedores o
mercados, ya que Alpaca será la única integración bursátil.

---

## Requisitos del enunciado que no son funcionales

Van al SAD como atributos de calidad, no a un spec funcional (tabla 25 del
catálogo):

- Logs centralizados (Splunk o ElasticSearch) y alarmas.
- 5.000 usuarios, 1.500 concurrentes y respuesta menor a 2 s; requiere pruebas
  de carga (Acta §3.3).
