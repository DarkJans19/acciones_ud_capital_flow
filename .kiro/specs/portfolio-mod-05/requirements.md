# Requirements Document

## Introduction

Este spec cubre el módulo de desarrollo MOD-05 "Portafolio de Inversiones y Métricas Financieras" del backend de Acciones UD (responsable: Juan José León Gómez). El módulo se implementa como el paquete `portfolio` dentro del monolito modular hexagonal (`src/acciones_ud/portfolio/`). Depende de MOD-01 (`identity`) y MOD-02 (`market_data`), ya implementados en `identity-market-backend`, de MOD-04 (`wallet`, spec `wallet-mod-04`) y de MOD-03 (`orders`, spec `orders-mod-03`). Por eso se construye después de MOD-03 y antes de MOD-06 y MOD-07, según el orden del catálogo (MOD-04 → MOD-03 → MOD-05 → MOD-06 → MOD-07).

Alcance trazable (los textos originales están en `.kiro/steering/requerimientos-proyecto.md`, sección MOD-05):

- RF-41: consultar posiciones del portafolio (Requisito 1) e historial de operaciones ejecutadas (Requisito 2).
- RF-41 y RF-42: costo promedio y resultado realizado y no realizado (Requisito 3).
- RF-05: estadísticas descriptivas de inversiones por periodo (Requisito 4).
- RF-04: perfil de actividad inversora y clasificación de riesgo (Requisito 5).
- RF-42: reporte de inversión bajo demanda (Requisito 6), resumen diario y reporte mensual programados (Requisito 7) y consulta de reportes (Requisito 8).
- RFP-12: reportes por perfil de cliente y de comisionista (Requisito 9), obligatorio por la Decisión R1.
- Contrato del Position_Port de `orders` provisto por `portfolio` (Requisito 10).
- Requisitos transversales de precisión decimal, autorización, propiedad, configuración, errores y contrato OpenAPI (Requisitos 11 y 12).

Fuera de alcance: creación, envío y seguimiento de órdenes (MOD-03); saldos, movimientos y transferencias (MOD-04); cálculo, cotización y consulta oficial de comisiones (RF-43, MOD-07); vinculación inversionista–comisionista (RF-13 a RF-15, MOD-06); exportación de reportes a PDF; capitalización bursátil; RFP-06 y RFP-07 (descartados por las Decisiones R2 y R3).

### Decisiones y supuestos del módulo

Cada punto abierto del catálogo para MOD-05 queda resuelto aquí como decisión (P) o supuesto (A).

- **P1 (fuente de las posiciones, punto abierto):** Alpaca Broker API prevalece para la posición vigente: la cantidad total, la cantidad disponible (`qty_available`) y el costo promedio (`avg_entry_price`) de cada símbolo se leen de las posiciones de Alpaca. Las Executions registradas por `orders` son la fuente del historial de operaciones y del resultado realizado. Cuando la cantidad reconstruida desde las Executions difiere de la cantidad de Alpaca para un símbolo, la posición se devuelve con `reconciliation_mismatch` en true y se registra en el log; no se corrige ninguna de las dos fuentes.
- **P2 (cantidad reservada):** la cantidad reservada de una posición es la cantidad total menos `qty_available` de Alpaca (acciones comprometidas en órdenes ya enviadas) más las acciones de las Reservations `active` de venta de `orders` para el símbolo (órdenes aún no enviadas). `portfolio` lee esas Reservations mediante un puerto de lectura y no las modifica.
- **P3 (precio de valoración):** el precio de una posición es el precio de la cotización vigente de `market_data`. Si la cotización no está disponible, se usa el `current_price` que informa Alpaca para la posición y la respuesta indica `price_source` en `alpaca_position`; con cotización disponible `price_source` vale `market_data`.
- **P4 (método de costo y resultado realizado):** el costo de las ventas se calcula por costo promedio ponderado móvil, el mismo criterio de `avg_entry_price` de Alpaca. Una compra recalcula el costo promedio; una venta fija el resultado realizado como (precio de ejecución − costo promedio vigente) × cantidad vendida y deja el costo promedio sin cambios. El resultado no realizado de una posición es (precio de valoración − costo promedio) × cantidad total.
- **P5 (comisión de cada ejecución, RF-41):** el cálculo oficial de comisiones es de MOD-07 (RF-43). `portfolio` obtiene la comisión de cada Execution mediante el puerto Commission_Port. Mientras MOD-07 no exista, el adaptador por defecto (Reference_Commission) calcula cantidad × precio de ejecución × `ORDER_REFERENCE_COMMISSION_RATE` (la misma tasa de referencia del 2 % de `orders`) y la respuesta indica `commission_source` en `reference`. Alpaca sandbox no cobra esa comisión; el resultado realizado se informa bruto y neto de comisión.
- **P6 (perfil de riesgo, RF-04 es Brecha):** el Risk_Profile se calcula sobre una ventana configurable (`PORTFOLIO_RISK_WINDOW_DAYS`, por defecto 90 días) con cuatro subíndices entre 0 y 100: frecuencia F = min(100, Executions por semana ÷ 10 × 100); concentración C = índice de Herfindahl de los pesos de valor de mercado de las posiciones vigentes × 100; exposición E = min(100, valor de mercado total de las posiciones ÷ `equity` de la cuenta × 100); rotación T = min(100, volumen negociado en USD en la ventana ÷ `equity` ÷ 4 × 100). El Risk_Score es 0,25 F + 0,30 C + 0,25 E + 0,20 T, con dos decimales. La clasificación es `conservative` para un Risk_Score menor o igual que 33,33, `moderate` para un valor mayor que 33,33 y menor o igual que 66,66, y `aggressive` para un valor mayor que 66,66. Los mercados e instrumentos utilizados y la distribución de activos se devuelven como métricas descriptivas del perfil y no ponderan el Risk_Score. Las constantes (10 Executions por semana, rotación 4, pesos y cortes) son de dominio y su cambio requiere una nueva versión de este spec.
- **P7 (sector y capitalización, RF-05 es Parcial):** el sector se toma de `instruments.sector` de `market_data`. Un instrumento sin sector se agrupa en el sector `unclassified`. La participación por capitalización queda fuera de alcance porque ni Alpaca ni `market_data` proveen ese dato.
- **P8 (reportes, RF-42 es Parcial):** los reportes se generan y almacenan como documentos JSON inmutables consultables por API; el frontend los presenta. La exportación PDF queda fuera de alcance. Las posiciones de un reporte son las vigentes al momento de generarlo, porque Alpaca no informa posiciones históricas; el reporte indica `positions_as_of`.
- **P9 (programación del resumen diario y del reporte mensual):** el Report_Scheduler genera el resumen diario de cada sesión cerrada según el calendario de `market_data` para los Investors con el tipo de evento `daily_summary` habilitado en algún canal en `identity` (RF-07), y genera el reporte mensual del mes calendario anterior el primer día de cada mes para los Investors con `monthly_report` en true en `identity` (RF-01). Ambos se notifican mediante el Notifier existente de `market_data` con el enlace al reporte; el reporte mensual usa el tipo de evento `daily_summary` para respetar las preferencias de canal existentes, sin crear un tipo nuevo.
- **P10 (comisionista y cliente, RFP-12 sin MOD-06):** `portfolio` define el puerto Broker_Client_Port, que devuelve los Investors vinculados a un Broker. Mientras MOD-06 no exista, el adaptador por defecto (Null_Broker_Client) devuelve una lista vacía: los reportes de Broker se generan sin clientes y la consulta del portafolio de un cliente responde `NOT_FOUND`. MOD-06 solo sustituye el adaptador, sin cambiar el contrato HTTP de `portfolio`. La atribución de una Execution a un Broker es el Broker que firmó la Order en `orders` (estado Firmada por Comisionista), según lo informe el puerto de lectura de Executions.
- **P11 (Position_Port de `orders`, decisión O3 de `orders-mod-03`):** `portfolio` provee el adaptador definitivo de Position_Port sobre su propia lectura de posiciones de Alpaca, con la misma semántica de `qty_available`. `orders` no cambia su contrato.
- **P12 (precisión decimal):** todos los cálculos usan aritmética decimal sin redondeos intermedios. Las salidas se redondean con redondeo al par más cercano (half-even): importes en USD a 2 decimales, cantidades a 9 decimales, precios a 4 decimales y porcentajes a 2 decimales. Los porcentajes de participación de un mismo desglose se ajustan por el método de mayor residuo para sumar exactamente 100,00.
- **P13 (preferencias de visualización, RF-08):** la consulta de posiciones aplica `sort_by`, `sort_direction` y `hide_threshold` de `portfolio_view_settings` de `identity`, leídos mediante un puerto, y devuelve `view_type` para el frontend. `portfolio` no almacena de nuevo esas preferencias.
- **P14 (rentabilidad del periodo):** la rentabilidad de un reporte es (resultado realizado del periodo + resultado no realizado vigente) ÷ (costo de las posiciones vigentes + costo de las acciones vendidas en el periodo) × 100. Si el denominador es cero, la rentabilidad es null.
- **A1 (rol):** consultar el portafolio propio, sus estadísticas, su perfil y sus reportes está disponible para usuarios con rol `investor` vigente y Linked_Account. Los reportes de comisionista y la consulta de clientes vinculados están disponibles para usuarios con rol `broker` vigente. Los administradores no consultan portafolios en este módulo; la supervisión es de MOD-07.
- **A2 (moneda):** todos los importes se expresan en USD, la moneda que Alpaca informa para la cuenta (W9 de `wallet`).
- **A3 (historial previo):** se supone que las cuentas sandbox no tienen posiciones anteriores a las Executions registradas por `orders`. Si existen, P1 las señala con `reconciliation_mismatch` y el resultado realizado de esas acciones queda sin calcular.

### Política de pruebas

Por indicación del usuario, las pruebas no son obligatorias para todo el módulo. Son obligatorias solo para las partes críticas: cálculos de resultado, costo promedio y valor de mercado (Requisito 1 criterios 2–3, Requisito 3 criterios 1–5), porcentajes de participación y su suma (Requisito 4 criterios 2–4), cálculo y clasificación del Risk_Score (Requisito 5 criterios 2–5), rentabilidad de reportes (Requisito 6 criterio 3), precisión decimal (Requisito 11) y autorización y propiedad de recursos (Requisito 12 criterios 1–4 y Requisito 9 criterios 3–4). Las demás pruebas son opcionales.

## Glossary

- **Backend_API**: la aplicación FastAPI de Acciones UD que expone los endpoints de este spec.
- **Portfolio_Service**: componente del módulo `portfolio` que consulta posiciones e historial de operaciones de un Investor.
- **Pnl_Calculator**: regla de dominio pura del módulo `portfolio` que calcula costo promedio, resultado realizado y resultado no realizado.
- **Statistics_Service**: componente del módulo `portfolio` que calcula las estadísticas descriptivas de un periodo.
- **Risk_Profiler**: regla de dominio pura del módulo `portfolio` que calcula el Risk_Profile.
- **Report_Service**: componente del módulo `portfolio` que genera, almacena y consulta Reports.
- **Report_Scheduler**: tarea periódica del módulo `portfolio` que genera los resúmenes diarios y los reportes mensuales.
- **Execution_Query_Port**: puerto de salida de `portfolio` que devuelve las Executions de un Investor registradas por `orders`, con el lado, el símbolo y el Broker firmante de su Order.
- **Reservation_Query_Port**: puerto de salida de `portfolio` que devuelve las acciones de las Reservations `active` de venta de `orders` por símbolo.
- **Alpaca_Position_Port**: puerto de salida de `portfolio` que devuelve las posiciones de la cuenta Alpaca de un Investor.
- **Commission_Port**: puerto de salida de `portfolio` que devuelve la comisión de una Execution; su adaptador por defecto es Reference_Commission.
- **Broker_Client_Port**: puerto de salida de `portfolio` que devuelve los Investors vinculados a un Broker; su adaptador por defecto es Null_Broker_Client.
- **Position_Port**: puerto de salida de `orders` que devuelve la posición disponible (`qty_available`) de un símbolo, definido en `orders-mod-03`.
- **Notifier**: componente existente de `market_data` que crea notificaciones y las despacha según las preferencias del usuario.
- **Alpaca_Broker_API**: Alpaca Broker API en entorno sandbox.
- **Investor**: usuario autenticado con el rol `investor` vigente.
- **Broker**: usuario autenticado con el rol `broker` vigente (comisionista).
- **Linked_Account**: registro de `kyc_accounts` del Investor con `alpaca_account_id` no nulo.
- **Execution**: ejecución de una Order registrada por `orders`, con identificador, cantidad, precio y marca de tiempo de ejecución.
- **Position**: posición de un símbolo con cantidad total, cantidad reservada, precio de valoración, `price_source`, costo promedio, valor de mercado, resultado no realizado, mercado, sector y `reconciliation_mismatch`.
- **Market_Value**: cantidad total × precio de valoración de una Position.
- **Cost_Basis**: cantidad total × costo promedio de una Position.
- **Realized_Pnl**: resultado realizado de las ventas según la decisión P4, bruto y neto de comisión.
- **Unrealized_Pnl**: Market_Value − Cost_Basis de una Position.
- **Period**: intervalo de fechas `from` y `to` inclusivas en la zona horaria `America/New_York`.
- **Risk_Profile**: resultado del Risk_Profiler con subíndices F, C, E y T, Risk_Score, clasificación, ventana y métricas descriptivas.
- **Risk_Score**: valor entre 0 y 100 con dos decimales calculado según la decisión P6.
- **Report**: documento JSON inmutable con identificador, propietario, tipo (`on_demand`, `daily_summary`, `monthly`, `broker`), Period, `positions_as_of`, contenido y marca de tiempo de generación.
- **Error_Body**: cuerpo JSON de error con los campos `code`, `message` y `details`, definido por `identity-market-backend`.

## Requirements

### Requirement 1: Consultar posiciones del portafolio (RF-41, RF-08)

**User Story:** Como Investor, quiero consultar las posiciones de mi portafolio con su valor y resultado, para conocer en qué estoy invertido y cómo va cada inversión.

#### Acceptance Criteria

1. WHEN un Investor consulta sus posiciones, THE Portfolio_Service SHALL devolver una Position por cada símbolo con cantidad total mayor que cero en Alpaca_Broker_API, con instrumento, cantidad total, cantidad reservada, precio, costo promedio, Market_Value y Unrealized_Pnl.
2. THE Portfolio_Service SHALL calcular la cantidad reservada de cada Position como cantidad total − `qty_available` + acciones de las Reservations `active` de venta del símbolo informadas por Reservation_Query_Port.
3. THE Pnl_Calculator SHALL calcular Market_Value como cantidad total × precio de valoración y Unrealized_Pnl como Market_Value − Cost_Basis.
4. IF la cotización vigente de un símbolo no está disponible en `market_data`, THEN THE Portfolio_Service SHALL usar el `current_price` de Alpaca para esa Position y SHALL devolver `price_source` con el valor `alpaca_position`.
5. WHEN un Investor consulta sus posiciones, THE Portfolio_Service SHALL ordenar las Positions según `sort_by` y `sort_direction`, SHALL omitir las Positions con Market_Value menor que `hide_threshold` y SHALL devolver `view_type`, leídos de las preferencias de visualización de `identity`.
6. WHEN un Investor consulta sus posiciones, THE Portfolio_Service SHALL devolver los totales de Market_Value, Cost_Basis y Unrealized_Pnl de todas las Positions, incluidas las omitidas por `hide_threshold`.
7. IF la cantidad reconstruida desde las Executions de un símbolo difiere de la cantidad total de Alpaca, THEN THE Portfolio_Service SHALL devolver la Position con `reconciliation_mismatch` en true y SHALL registrar en el log el símbolo y ambas cantidades.
8. IF Alpaca_Broker_API falla al consultar las posiciones, THEN THE Portfolio_Service SHALL responder HTTP 502 con un Error_Body de código `ALPACA_UNAVAILABLE`, o HTTP 503 con código `ALPACA_RATE_LIMITED` cuando Alpaca devolvió HTTP 429.

### Requirement 2: Consultar historial de operaciones ejecutadas (RF-41)

**User Story:** Como Investor, quiero consultar las operaciones ejecutadas por periodo e instrumento, para revisar qué compré y vendí, a qué precio y con qué comisión.

#### Acceptance Criteria

1. WHEN un Investor consulta su historial con un Period y opcionalmente un símbolo, THE Portfolio_Service SHALL devolver las Executions propias de ese Period y símbolo con fecha, instrumento, sentido, cantidad, precio de ejecución, comisión y `commission_source`.
2. THE Portfolio_Service SHALL ordenar el historial por marca de tiempo de ejecución descendente y SHALL paginarlo con un tamaño máximo de 100 Executions por página.
3. WHILE Commission_Port usa el adaptador Reference_Commission, THE Portfolio_Service SHALL devolver como comisión cantidad × precio de ejecución × `ORDER_REFERENCE_COMMISSION_RATE` y `commission_source` con el valor `reference`.
4. IF el Period tiene `from` posterior a `to` o abarca más de 366 días, THEN THE Portfolio_Service SHALL responder HTTP 422 con un Error_Body de código `INVALID_PERIOD`.

### Requirement 3: Calcular costo promedio y resultados (RF-41, RF-42)

**User Story:** Como Investor, quiero conocer el resultado realizado y no realizado de mis inversiones, para saber cuánto he ganado o perdido.

#### Acceptance Criteria

1. WHEN el Pnl_Calculator procesa una Execution de compra, THE Pnl_Calculator SHALL recalcular el costo promedio como (cantidad previa × costo promedio previo + cantidad comprada × precio de ejecución) ÷ (cantidad previa + cantidad comprada).
2. WHEN el Pnl_Calculator procesa una Execution de venta, THE Pnl_Calculator SHALL registrar un Realized_Pnl bruto de (precio de ejecución − costo promedio vigente) × cantidad vendida, un Realized_Pnl neto igual al bruto menos la comisión, y SHALL conservar el costo promedio.
3. THE Pnl_Calculator SHALL procesar las Executions de un símbolo en orden de marca de tiempo de ejecución y, ante igual marca de tiempo, en orden de identificador de Execution.
4. FOR ALL secuencias de Executions de un símbolo sin venta mayor que la cantidad acumulada, THE Pnl_Calculator SHALL cumplir que la suma de Realized_Pnl bruto más Unrealized_Pnl valorado al precio P es igual a P × cantidad final − Σ importes de compra + Σ importes de venta (invariante de conservación).
5. FOR ALL secuencias de Executions de un símbolo, THE Pnl_Calculator SHALL producir el mismo costo promedio y el mismo Realized_Pnl al procesar dos veces la misma secuencia (determinismo).
6. IF una Execution de venta supera la cantidad acumulada del símbolo, THEN THE Pnl_Calculator SHALL omitir el Realized_Pnl de la cantidad excedente y SHALL marcar el símbolo con `reconciliation_mismatch` en true.

### Requirement 4: Estadísticas descriptivas de inversiones (RF-05)

**User Story:** Como Investor, quiero estadísticas de mis inversiones en un periodo, para entender cuánto opero y cómo se distribuye mi actividad.

#### Acceptance Criteria

1. WHEN un Investor solicita estadísticas para un Period, THE Statistics_Service SHALL devolver el número de Executions, el número de compras y de ventas y el volumen en USD calculado como Σ cantidad × precio de ejecución de las Executions del Period.
2. WHEN un Investor solicita estadísticas para un Period, THE Statistics_Service SHALL devolver la participación porcentual del volumen por mercado, por instrumento y por sector, tomando mercado y sector de `market_data`.
3. THE Statistics_Service SHALL agrupar en el sector `unclassified` el volumen de los instrumentos sin sector, entendido como sector nulo, cadena vacía o instrumento ausente del catálogo de `market_data`.
4. FOR ALL desgloses de participación con volumen total mayor que cero, THE Statistics_Service SHALL devolver porcentajes no negativos que suman exactamente 100,00 (invariante).
5. IF el Period no tiene Executions, THEN THE Statistics_Service SHALL devolver conteos y volumen en cero y desgloses vacíos.
6. IF el Period es inválido según el Requisito 2 criterio 4, THEN THE Statistics_Service SHALL responder HTTP 422 con un Error_Body de código `INVALID_PERIOD`.

### Requirement 5: Perfil de actividad inversora (RF-04)

**User Story:** Como Investor, quiero conocer mi perfil de riesgo calculado a partir de mi actividad, para entender qué tan arriesgada es mi forma de invertir.

#### Acceptance Criteria

1. WHEN un Investor consulta su Risk_Profile, THE Risk_Profiler SHALL devolver los subíndices F, C, E y T, el Risk_Score, la clasificación, la ventana usada y las métricas descriptivas: cantidad y frecuencia de Executions, volumen en USD, mercados e instrumentos utilizados y distribución de activos por Market_Value.
2. THE Risk_Profiler SHALL calcular cada subíndice y el Risk_Score según las fórmulas de la decisión P6.
3. FOR ALL entradas del Risk_Profiler, THE Risk_Profiler SHALL devolver subíndices y Risk_Score entre 0 y 100 inclusive (invariante).
4. FOR ALL pares de entradas que difieren solo en que una concentra más el Market_Value en una Position, THE Risk_Profiler SHALL devolver un subíndice C mayor o igual para la entrada más concentrada (metamórfica).
5. THE Risk_Profiler SHALL clasificar el Risk_Score como `conservative`, `moderate` o `aggressive` según los cortes de la decisión P6.
6. IF el Investor no tiene Executions en la ventana ni Positions vigentes, THEN THE Risk_Profiler SHALL devolver la clasificación `insufficient_data` con Risk_Score null.
7. IF el `equity` de la cuenta es cero o no está disponible mediante el puerto de `wallet`, THEN THE Risk_Profiler SHALL asignar 0 a los subíndices E y T y SHALL indicar `equity_unavailable` en true.

### Requirement 6: Generar reporte de inversión bajo demanda (RF-42)

**User Story:** Como Investor, quiero generar un reporte de mis inversiones para un periodo, para revisar posiciones, volumen, resultados y comisiones en un solo documento.

#### Acceptance Criteria

1. WHEN un Investor solicita un reporte para un Period válido, THE Report_Service SHALL generar y almacenar un Report de tipo `on_demand` con Positions vigentes, volumen del Period, Realized_Pnl del Period bruto y neto, Unrealized_Pnl vigente, comisiones del Period, rentabilidad, `positions_as_of` y tipo de reporte, y SHALL responder HTTP 201 con el Report.
2. THE Report_Service SHALL calcular el Realized_Pnl del Period cumpliendo de forma conjunta e incondicional tres condiciones: usar el Pnl_Calculator, procesar todas las Executions hasta `to` y sumar solo el Realized_Pnl de las ventas ejecutadas dentro del Period.
3. THE Report_Service SHALL calcular la rentabilidad según la decisión P14 y SHALL devolverla null cuando el denominador es cero.
4. THE Report_Service SHALL conservar sin cambios el contenido de un Report almacenado (inmutable).
5. IF el Period es inválido según el Requisito 2 criterio 4, THEN THE Report_Service SHALL responder HTTP 422 con un Error_Body de código `INVALID_PERIOD` y SHALL omitir el almacenamiento del Report.

### Requirement 7: Resumen diario y reporte mensual programados (RF-42, RF-07, RF-01)

**User Story:** Como Investor, quiero recibir un resumen diario y un reporte mensual de mis operaciones, para seguir mis inversiones sin generarlos manualmente.

#### Acceptance Criteria

1. WHEN termina una sesión de mercado según el calendario de `market_data`, THE Report_Scheduler SHALL generar un Report de tipo `daily_summary` de esa sesión para cada Investor con el tipo de evento `daily_summary` habilitado en algún canal y con al menos una Execution o una Position vigente.
2. WHEN comienza el primer día de un mes calendario en `America/New_York`, THE Report_Scheduler SHALL generar un Report de tipo `monthly` del mes anterior para cada Investor con `monthly_report` en true.
3. WHEN el Report_Scheduler genera un Report programado, THE Report_Scheduler SHALL crear una notificación mediante el Notifier con el tipo de evento `daily_summary`, las operaciones del periodo, los importes, la rentabilidad, las comisiones y el enlace al Report.
4. IF el Report_Scheduler ya generó un Report del mismo tipo y Period para un Investor, THEN THE Report_Scheduler SHALL omitir la generación de un segundo Report y SHALL omitir la notificación en ese ciclo (idempotencia); como única excepción, si la notificación de ese Report nunca se completó (`notified_at` nulo), THE Report_Scheduler SHALL reintentar solo la notificación, sin generar el Report de nuevo.
5. IF falla la generación del Report de un Investor, THEN THE Report_Scheduler SHALL registrar el fallo sin secretos, SHALL continuar con los demás Investors y SHALL reintentar ese Report en el siguiente ciclo.

### Requirement 8: Consultar reportes (RF-42)

**User Story:** Como Investor, quiero listar y abrir mis reportes, para consultar los que generé o recibí.

#### Acceptance Criteria

1. WHEN un Investor lista sus reportes, THE Report_Service SHALL devolver sus Reports con identificador, tipo, Period y fecha de generación, ordenados por fecha de generación descendente y paginados con un máximo de 100 por página.
2. WHEN un Investor consulta un Report propio por identificador, THE Report_Service SHALL devolver el contenido completo almacenado.
3. WHERE la consulta indica un tipo de Report, THE Report_Service SHALL devolver solo los Reports de ese tipo.

### Requirement 9: Reportes por perfil de comisionista y cliente (RFP-12)

**User Story:** Como Broker, quiero reportes por periodo de mis clientes y de mi actividad como comisionista, para revisar ganancias, pérdidas, activos, comisiones y transacciones.

#### Acceptance Criteria

1. WHEN un Broker solicita un reporte para un Period válido, THE Report_Service SHALL generar y almacenar un Report de tipo `broker` con, por cada Investor que devuelve Broker_Client_Port, Realized_Pnl y Unrealized_Pnl, resumen de activos, Positions, comisiones pagadas y Executions del Period, y con los totales agregados del Broker.
2. THE Report_Service SHALL calcular las comisiones atribuidas al Broker como la suma de comisiones de las Executions cuya Order firmó ese Broker según Execution_Query_Port.
3. IF un Broker consulta el portafolio o un reporte de un Investor que Broker_Client_Port no devuelve como vinculado, THEN THE Backend_API SHALL responder HTTP 404 con un Error_Body de código `NOT_FOUND`, sin revelar si el Investor existe.
4. WHILE Broker_Client_Port usa el adaptador Null_Broker_Client, THE Report_Service SHALL generar los Reports de tipo `broker` sin clientes y con totales en cero.
5. WHEN un Investor solicita su reporte de cliente, THE Report_Service SHALL incluir en el Report de tipo `on_demand` el resumen de activos, las comisiones pagadas y las Executions del Period, según el Requisito 6.

### Requirement 10: Proveer el Position_Port de `orders`

**User Story:** Como integrante del equipo, quiero que `portfolio` provea la posición disponible que `orders` usa al validar ventas, para tener una sola lectura de posiciones.

#### Acceptance Criteria

1. THE Backend_API SHALL cablear en `orders` el adaptador de Position_Port provisto por `portfolio`, que devuelve el `qty_available` que Alpaca_Position_Port informa para el símbolo.
2. IF el Investor no tiene posición del símbolo en Alpaca, THEN THE adaptador de Position_Port SHALL devolver un `qty_available` de cero.
3. IF Alpaca_Broker_API falla al consultar la posición, THEN THE adaptador de Position_Port SHALL propagar el error clasificado de Alpaca definido en `shared/domain/`, según el contrato de Position_Port de `orders-mod-03`.

### Requirement 11: Precisión decimal (transversal MOD-05)

**User Story:** Como Investor, quiero importes y porcentajes exactos y consistentes, para confiar en las métricas de mi portafolio.

#### Acceptance Criteria

1. THE Pnl_Calculator, THE Statistics_Service, THE Risk_Profiler y THE Report_Service SHALL calcular con aritmética decimal y SHALL redondear solo en la salida según la decisión P12.
2. THE Backend_API SHALL serializar importes, cantidades, precios y porcentajes como cadenas decimales en las respuestas JSON.
3. FOR ALL valores decimales de salida, THE Backend_API SHALL producir el mismo valor decimal al serializar y deserializar el valor (round-trip).

### Requirement 12: Autorización, configuración, errores y contrato (transversal MOD-05)

**User Story:** Como integrante del equipo, quiero reglas comunes de seguridad, errores y configuración, para que el módulo sea consistente con el resto del backend.

#### Acceptance Criteria

1. IF una solicitud a un endpoint de portafolio no tiene autenticación válida, THEN THE Backend_API SHALL responder HTTP 401 con un Error_Body y SHALL omitir toda llamada a Alpaca_Broker_API.
2. IF un usuario autenticado sin rol `investor` vigente solicita un endpoint de portafolio del Investor, o sin rol `broker` vigente solicita un endpoint de comisionista, THEN THE Backend_API SHALL responder HTTP 403 con un Error_Body de código `FORBIDDEN`.
3. IF un Investor solicita un Report que no le pertenece, THEN THE Backend_API SHALL responder HTTP 404 con un Error_Body de código `NOT_FOUND`, sin revelar si el Report existe.
4. IF un Investor sin Linked_Account consulta posiciones, perfil o reportes, THEN THE Backend_API SHALL responder HTTP 409 con un Error_Body de código `ACCOUNT_NOT_LINKED`.
5. IF la base de datos no está disponible durante una solicitud de portafolio, THEN THE Backend_API SHALL responder HTTP 503 con un Error_Body de código `DATABASE_UNAVAILABLE`.
6. IF falta o es inválida alguna de las variables `PORTFOLIO_RISK_WINDOW_DAYS` o `PORTFOLIO_REPORT_INTERVAL_SECONDS`, THEN THE Backend_API SHALL negarse a iniciar y SHALL reportar el nombre de cada variable inválida sin su valor.
7. THE Backend_API SHALL excluir credenciales de Alpaca y secretos de logs, respuestas y Error_Body.
8. THE Backend_API SHALL declarar en el contrato OpenAPI el esquema de request, response y cada Error_Body posible de cada endpoint de este módulo.
9. THE Backend_API SHALL crear las tablas del módulo `portfolio` mediante migraciones Alembic en `migrations/versions/`.
