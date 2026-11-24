# 3. MOD-02: exploración y datos de mercado

[Índice](README.md) · [Anterior](02-identidad.md) · [Siguiente](04-ordenes.md)

**Paquete:** `src/acciones_ud/market_data/`.  
**Trazabilidad:** RF-24..28, RFP-08; [spec compartido](../identity-market-backend/design.md).

## 3.1 Responsabilidad y fuentes

Este módulo responde qué instrumentos existen, cómo se encuentran, cuál es su
cotización, qué históricos hay y cuándo puede negociarse. También soporta
watchlists, alertas, notificaciones y el dashboard.

Separa dos fuentes externas:

- **Alpaca Broker API:** activos, calendario y reloj.
- **Alpaca Market Data API:** snapshots, latest quote, velas y stream.

Los catálogos y snapshots locales no convierten PostgreSQL en proveedor de
precios en tiempo real: conservan una copia con procedencia y antigüedad.

## 3.2 Catálogo de instrumentos

`application/catalog.py` coordina la carga del catálogo de activos `us_equity`.
La antigüedad máxima configurable es normalmente 24 horas. La búsqueda puede
asegurar que el catálogo está cargado antes de consultarlo.

La actualización mezcla la información externa con la representación local.
Los instrumentos que dejan de aparecer se marcan `listed=false`, no se borran.
**Por qué:** listas observadas, alertas y referencias históricas pueden seguir
apuntando a su símbolo.

`domain/symbols.py` valida símbolos y los normaliza. La API identifica
instrumentos por símbolo, no por UUID artificial; las rutas usan `{symbol:path}`
para aceptar la forma del identificador y validarla en el dominio.

Los flags de listado, actividad y negociabilidad son distintos. Estar presente
en una búsqueda no debe interpretarse como permiso incondicional para enviar
una orden.

## 3.3 Búsqueda y detalle

`domain/search.py` define un ranking determinista:

1. Coincidencia exacta de símbolo.
2. Símbolo con el prefijo consultado.
3. Coincidencia en el nombre.
4. Desempate alfabético por símbolo.

La consulta admite de 1 a 50 caracteres después de recortar espacios y filtros
de exchange/clasificación. El repositorio refleja el orden del modelo puro y
pagina los resultados. Las búsquedas SQL parametrizan valores y tratan los
comodines conforme al contrato; no concatenan entradas como SQL ejecutable.

`AssetDetailService` aporta el detalle y puede consultar/actualizar datos del
activo. `ExchangesService` obtiene exchanges del catálogo; una ruta administrativa
de mercados representa otra vista, no otro proveedor de instrumentos.

**Decisión:** reglas puras de ranking más implementación SQL permiten comparar
ambas contra las mismas expectativas sin introducir un buscador externo.

## 3.4 Cotizaciones y degradación explícita

`QuoteService.quote`:

1. Valida símbolo y exige instrumento local.
2. Lee el último snapshot almacenado.
3. Solicita snapshot actual a Alpaca fuera de la transacción.
4. Usa el actual o, si falla el proveedor y existe copia, el almacenado.
5. Persiste la respuesta actual y construye etiquetas de frescura.

Las etiquetas describen moneda, fuente/feed, fecha, edad, retraso, obsolescencia
y uso de caché. El umbral de precio obsoleto es configurable, normalmente 900 s.
`iex`, `sip` y `delayed_sip` no son equivalentes: el feed contratado condiciona
cobertura, retraso y profundidad.

**Por qué no devolver cero ante un fallo:** cero sería un dato financiero falso.
La falta de precio se expresa como indisponibilidad, `null` o error según el
endpoint. Si no hay respuesta externa ni copia válida para servir, el caso de
uso no inventa una cotización.

Un precio servido desde caché puede mantener utilizable la pantalla, pero no
garantiza un precio de ejecución. Los lectores utilizados por órdenes y
portafolio tienen su propia política de qué campos consumen.

## 3.5 Velas e históricos

`CandleService` y `domain/bars.py` gestionan OHLCV:

| Parámetro | Política |
| --- | --- |
| Timeframe | `1Min`, `5Min`, `15Min`, `1Hour`, `1Day` |
| Página | 1..10 000, por defecto 1 000 |
| Orden | Ascendente por timestamp dentro de la página |
| Continuación | Token de página del proveedor |

Acepta fechas o timestamps; una fecha sin hora se interpreta en UTC, comienzo
del día para `start` y final del día para `end`. Los timestamps sin zona también
se interpretan como UTC en esta entrada.

Esto es **distinto** del periodo financiero de portfolio, basado en fechas de
Nueva York. Un consumidor no debe reutilizar un parser de periodos suponiendo
que todos los endpoints tienen la misma semántica temporal.

## 3.6 Profundidad de mercado

`DepthService` usa latest quote para el mejor bid/ask y sus tamaños. No reconstruye
un libro completo de órdenes bursátiles ni inventa niveles a partir de un precio.
Cuando el feed solo entrega top-of-book se muestra ese alcance.

**Decisión y motivo:** representar la limitación real de Alpaca y del plan es
preferible a dar apariencia de profundidad completa. Una ampliación necesita
proveedor y contrato de datos que realmente soporten niveles adicionales.

## 3.7 Calendario, reloj y horarios administrativos

Hay tres operaciones relacionadas pero distintas:

- `ClockService`: reloj global que reporta Alpaca.
- `CalendarService`: días/sesiones para un rango.
- `MarketStatusService`: estado del mercado con configuración local.

`domain/schedule.py` resuelve:

1. Override de fecha: puede cerrar el día o fijar apertura/cierre.
2. Sesión Alpaca: si existe, puede usar horas predeterminadas locales del mercado.
3. Sin override ni sesión: día cerrado, clasificado como fin de semana o festivo.

Las horas se interpretan con zona de mercado y se convierten a la zona solicitada
mediante `zoneinfo`, respetando horario de verano. Un horario abierto exige
apertura y cierre y que cierre sea posterior; un override cerrado no acepta horas.

**Límite:** un override puede definir apertura local que no coincida con una
sesión real negociable del proveedor. No se implementa una intersección nueva
con el calendario de Alpaca ni se promete que Alpaca ejecutará en ese horario.

`ScheduleAdminService` escribe horario y auditoría en la misma transacción.
Después del commit informa al listener instalado por admin, que propaga el
cambio a órdenes. La separación evita mezclar la modificación del calendario
con toda la orquestación de órdenes en una misma llamada HTTP.

## 3.8 Listas observadas premium

Los routers exigen permisos y condición premium; el caso de uso mantiene reglas
independientes del transporte:

- Máximo veinte listas por usuario.
- Máximo cincuenta símbolos distintos por lista.
- Nombre recortado de 1..100 caracteres.
- Símbolo repetido: conflicto `SYMBOL_ALREADY_IN_WATCHLIST`.
- Recurso ajeno: respuesta de no encontrado, no contenido parcial.

Para crear o añadir se bloquea el propietario durante contar/verificar/insertar,
de modo que dos peticiones simultáneas no superen los límites.

**Distinción:** estas listas sirven para seguimiento, no constituyen posiciones
reales ni órdenes de compra.

## 3.9 Alertas de precio

Las alertas también se protegen en HTTP como capacidad premium. Se crean con
símbolo, comparador y umbral positivo. El dominio admite:

- `above`: precio actual mayor o igual al umbral.
- `below`: menor o igual.
- Cruce: igualdad actual o paso de un lado del umbral al otro usando el precio
  previamente evaluado.

`PriceAlertLoop` obtiene alertas activas agrupadas y realiza una consulta de
snapshots para el conjunto de símbolos. Para cada alerta relee/bloquea el estado
activo y usa transición condicional a `triggered`.

La transición evita que dos evaluadores disparen la misma activación. Después
se notifica al propietario; una alerta disparada no se evalúa de nuevo hasta
reactivarse. Si falta precio, se conserva el estado y no se inventa un cruce.

**Garantía acotada:** la unicidad de la transición no asegura entrega externa
exactamente una vez. Hay una ventana entre el commit y la notificación.

## 3.10 Notificaciones y canales

`application/notifier.py` se reutiliza desde órdenes, wallet, portfolio, brokers
y admin mediante adaptadores propios de esos módulos.

1. Resuelve destinatarios y canales permitidos por preferencias.
2. Persiste notificación y entregas `pending`.
3. Confirma la transacción.
4. Despacha cada canal y registra `sent` o `failed`.

El fallo de un canal no impide probar los demás:

| Canal | Implementación actual |
| --- | --- |
| `in_app` | Persistencia y consulta por API |
| `email` | SMTP si hay configuración; de lo contrario sender de log |
| `sms` | Siempre simulado |
| `telegram` | Bot API si hay token; de lo contrario sender de log |

Una entrega marcada por un sender de log no equivale a correo real recibido.
La tabla de entregas tampoco implica que exista una cola durable de reintentos
para todos los avisos fallidos.

`ClockWatcher` compara el reloj externo con su observación anterior y emite
apertura/cierre al cambiar. El estado previo es local al proceso: varios workers
pueden observar la misma transición y generar avisos duplicados.

## 3.11 Streaming WebSocket

Ruta: `/ws/v1/market-feed`. Se habilita con `PRICE_STREAMING_ENABLED=true`.
En el handshake exige cookie válida, cuenta activa y permiso `market:read`.
Si está apagado o falta acceso, cierra con código 1008.

Una suscripción tiene esta forma:

```json
{"action": "subscribe", "symbols": ["AAPL", "MSFT"]}
```

Se normaliza a símbolos únicos y admite de 1 a 30 por cliente, todos del catálogo.
Una solicitud válida **reemplaza** la suscripción anterior; una inválida no la
borra. Las respuestas usan `subscribed`, `error` y actualizaciones `price`.

`StreamHub` mantiene una conexión upstream por proceso y suscribe la unión de
símbolos de todos los clientes. Luego distribuye cada precio únicamente a los
interesados. **Motivo:** evitar abrir una conexión Alpaca por navegador y
consumir el límite del proveedor innecesariamente.

**Límites actuales, no garantías implícitas:**

- El handshake autentica, pero el loop no revalida periódicamente expiración,
  revocación de sesión o permisos.
- Hay frames malformados/no objeto que no se manejan de forma robusta.
- El fan-out envía secuencialmente; no es un diseño de colas independientes
  por cliente lento.
- La autenticación REST OAuth no transforma el stream en OAuth: su cliente
  sigue recibiendo key/secret. Debe comprobarse la combinación de credenciales.

Los dos primeros aspectos tienen hallazgos de auditoría; habilitar streaming
requiere revisarlos, no solo activar una variable.

## 3.12 Dashboard personalizado

`DashboardService` lee intereses, nivel y catálogo, selecciona hasta diez
instrumentos y consulta snapshots y reloj.

La selección usa coincidencia de interés con exchange/sector; si no hay
coincidencias, usa `DASHBOARD_DEFAULT_SYMBOLS`, ordenado de forma determinista.
No es un algoritmo de recomendación de inversión ni usa aprendizaje automático.

Cotizaciones y reloj tienen cada uno timeout de 3 s, pero el código hace ambas
llamadas de forma secuencial. **No hay un presupuesto total de tres segundos
para todo el endpoint.** Ante fallo, la pantalla puede recibir instrumentos con
precio nulo y reloj no disponible.

## 3.13 Dónde comprobar las reglas

- Núcleo: `domain/{search,freshness,bars,schedule,alerts,streaming,dashboard}.py`.
- Orquestación: `application/` y `composition.py`.
- Proveedores: `adapters/outbound/alpaca/{broker_client,data_client,stream_client}.py`.
- Jobs: `adapters/inbound/jobs/{price_alert_loop,clock_watcher}.py`.
- Pruebas: `tests/market_data/property/`, `test_catalog_service.py`,
  `test_watchlists_alerts_api.py`, `test_engine_jobs.py` y `test_stream_api.py`.
