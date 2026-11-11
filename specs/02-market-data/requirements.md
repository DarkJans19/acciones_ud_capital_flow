# SPEC-0200: Explorador de mercados y cotizaciones bursátiles

## Estado

Propuesto

## Trazabilidad

- Catálogo actualizado: RF-24, RF-25, RF-26, RF-27 y RF-28.
- Calidad del SAD: RNF-01, RNF-03, RNF-06, RNF-07, RNF-08 y RNF-10.
- Casos de uso y escenarios de calidad: pendientes de IDs `CU` y `EC` aprobados.
- Mockups: 01 (Market Ticker) y 05 (Explorador y filtros multi-bolsa).

El catálogo actualizado establece Alpaca como única integración bursátil. RF-28
solo muestra bolsa, estado y negociabilidad; no compara ni selecciona rutas de
ejecución entre proveedores.

## Propósito

Permitir descubrir instrumentos soportados por Alpaca sin conocer previamente la
bolsa, consultar calendario y estado de mercado, recibir cotizaciones actuales,
profundidad disponible e históricos, administrar instrumentos observados y alertas,
y difundir actualizaciones mediante WebSocket.

Supabase PostgreSQL conserva catálogo, configuración y estado propio. No sustituye
Alpaca Market Data ni se usa Supabase Realtime para el feed bursátil.

## Alcance

### Incluido

- RF-24: catálogo de Alpaca, búsqueda por nombre/símbolo, bolsa y negociabilidad.
- RF-25: último precio, bid/ask, volumen, hora, históricos OHLCV y profundidad que
  el plan/feed de Alpaca permita.
- RF-26: listas observadas para usuarios premium, umbrales de precio, activación y
  emisión de evento de alerta para el canal configurado en MOD-01.
- RF-27: calendario, reloj, sesiones, feriados, zona horaria, estado soportado y
  emisión opcional de eventos de apertura/cierre para usuarios que los habiliten.
- RF-28: bolsa reportada, estado y disponibilidad de negociación del activo.
- Alcance inicial de presentación centrado en NYSE y NASDAQ, limitado por los
  activos y metadatos que Alpaca entregue.
- Identificación explícita de datos en tiempo real o diferidos.
- Difusión WebSocket validada por FastAPI.

### Excluido

- Alpha Vantage u otros proveedores bursátiles.
- Comparación o selección de rutas de ejecución.
- Ejecución de órdenes, fondos, portafolios y recomendaciones de inversión.
- Supabase Realtime como fuente de precios.
- Profundidad que el plan o licencia de Alpaca no suministre.
- Presentar datos vencidos o simulados como cotizaciones actuales reales.

## Reglas e invariantes de dominio

1. Un símbolo se interpreta dentro de un mercado; existe un identificador estable.
2. Cada precio incluye moneda, fuente Alpaca, `as_of`, frescura y condición diferida.
3. El spread es `ask - bid` solo cuando ambos valores son válidos.
4. Los instantes se normalizan a UTC y el mercado conserva su zona IANA.
5. “Tiempo real” solo se usa si el plan/feed contratado lo garantiza.
6. Un valor en caché indica antigüedad; una falla de Alpaca se informa explícitamente.
7. Dominio y aplicación dependen de un puerto, nunca de tipos del SDK de Alpaca.
8. Las alertas registran comparador, umbral, precio observado e instante, y emiten un
   evento idempotente; el transporte de notificación se resuelve mediante un puerto.
9. Crear o modificar listas y alertas exige una suscripción premium activa consultada
   mediante un puerto; MOD-02 no administra planes ni pagos.
10. Los eventos de apertura/cierre son idempotentes y respetan las preferencias de
    MOD-01; MOD-02 no implementa el canal de entrega.

## Contrato HTTP y WebSocket inicial

| Método y ruta | Resultado esperado |
|---|---|
| `GET /api/v1/markets` | Lista mercados soportados y capacidades |
| `GET /api/v1/markets/{market_id}/status` | Sesión, horario y próxima transición |
| `GET /api/v1/instruments/search?q=...` | Búsqueda paginada con bolsa y negociabilidad |
| `GET /api/v1/instruments/{instrument_id}/quote` | Quote actual con frescura y fuente |
| `GET /api/v1/instruments/{instrument_id}/candles` | OHLCV por intervalo y rango |
| `GET /api/v1/instruments/{instrument_id}/depth` | Profundidad disponible en el plan |
| `GET /api/v1/watchlists` | Lista instrumentos observados del usuario premium |
| `POST /api/v1/watchlists/{watchlist_id}/items` | Agrega un instrumento observado |
| `DELETE /api/v1/watchlists/{watchlist_id}/items/{instrument_id}` | Elimina un instrumento |
| `POST /api/v1/price-alerts` | Crea un umbral superior/inferior |
| `DELETE /api/v1/price-alerts/{alert_id}` | Desactiva una alerta propia |
| `WS /ws/v1/market-feed` | Suscripción autorizada a instrumentos |

La búsqueda siempre devuelve `instrument_id`, símbolo, bolsa, estado y
negociabilidad. Una ruta por `{symbol}` solo se expondrá junto con el mercado o si
se demuestra que no existe ambigüedad.

El WebSocket debe definir autenticación/`Origin`, `subscribe`/`unsubscribe`, snapshot,
secuencia o cursor, heartbeat, límites, errores, reconexión, backpressure y
resincronización. La semántica se define en contrato antes de implementarla.

## Modelo relacional propuesto (3FN)

Las tablas se alojarán en Supabase PostgreSQL y se versionarán con Alembic:

- `markets`: MIC, nombre, país, moneda, zona IANA y estado.
- `trading_weekly_sessions`: mercado, día, apertura y cierre local.
- `market_calendar_exceptions`: fecha, cierre o sesión especial.
- `instruments`: mercado, símbolo, identificador Alpaca, nombre, clase de activo,
  sector cuando exista, moneda, estado y negociabilidad.
- `price_snapshots`: instrumento, bid, ask, último, volumen, moneda, feed, instante
  de origen/recepción y condición diferida.
- `price_candles`: instrumento, feed, intervalo, inicio y OHLCV.
- `watchlists` y `watchlist_items`: propietario e instrumentos observados.
- `price_alerts`: propietario, instrumento, comparador, umbral, estado y última
  activación.

No se presupone que cada tick del stream deba persistirse. Retención, caché e
históricos dependen de licencia, volumen y necesidades verificadas. La combinación
mercado+símbolo será única; Trigram se agrega solo con migración y evidencia de uso.

## Seguridad de Supabase y proveedores

- Next.js consume FastAPI; no recibe credenciales PostgreSQL ni claves privilegiadas.
- Las tablas no se exponen por Data API sin decisión y políticas RLS revisadas.
- Las credenciales de Alpaca permanecen en el adaptador backend y secretos de entorno.
- Las listas y alertas siempre se filtran por el propietario autenticado.

## Estrategia de pruebas

- Unitarias: spread, zonas, estado, frescura, alertas y validación OHLCV.
- Integración: Supabase/PostgreSQL, índices, búsquedas, listas y calendarios.
- Contrato Alpaca: catálogo, quote, históricos, reloj, rate limit y reconexión.
- Contrato HTTP/WS: paginación, errores, snapshot, secuencia y resuscripción.
- Rendimiento: búsqueda y fan-out WebSocket con percentiles acordados.

## Criterios de aceptación

- [ ] La búsqueda identifica bolsa, estado y negociabilidad reportados por Alpaca.
- [ ] Quote e históricos indican moneda, feed, instante y condición real/diferida.
- [ ] No se presenta silenciosamente información vencida como actual.
- [ ] RF-26 permite observar instrumentos y evaluar umbrales sin acceder a datos de
  otro usuario.
- [ ] RF-26 rechaza mutaciones sin una suscripción premium activa.
- [ ] RF-27 emite eventos de apertura/cierre sin duplicarlos y solo cuando estén
  habilitados.
- [ ] RF-28 no compara rutas ni proveedores.
- [ ] Horarios y cierres usan zona IANA y excepciones de calendario.
- [ ] El dominio no importa el SDK de Alpaca ni librerías de Supabase.
- [ ] El WebSocket limita suscripciones y resuelve pérdidas mediante resincronización.
- [ ] Las migraciones construyen el esquema en un proyecto Supabase vacío.
- [ ] OpenAPI genera tipos reproducibles para el frontend.
- [ ] Ruff, Mypy y Pytest finalizan correctamente.

## Decisiones pendientes

- Plan, feed, permisos, profundidad, cobertura, latencia y límites de Alpaca.
- Definición contractual de tiempo real y retraso máximo permitido.
- Tratamiento de sectores/capitalización que Alpaca no entregue.
- Política de caché y retención compatible con la licencia.
- Intervalos y rangos máximos de velas.
- Autenticación y límites finales del WebSocket.
- Canales habilitados para entregar eventos de alerta de RF-26.
- Contrato del puerto de suscripciones con MOD-04 y comportamiento ante indisponibilidad.
- Objetivos medibles de rendimiento y disponibilidad.
- Estrategia de schemas/RLS en Supabase si alguna tabla llegara a exponerse.
