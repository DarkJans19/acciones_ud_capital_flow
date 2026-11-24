# 6. MOD-05: portafolio, resultados y reportes

[Índice](README.md) · [Anterior](05-fondos-suscripciones.md) · [Siguiente](07-comisionistas.md)

**Paquete:** `src/acciones_ud/portfolio/`.  
**Trazabilidad:** RF-04..05, RF-08, RF-41..42, RFP-12;
[requisitos](../portfolio-mod-05/requirements.md), [diseño](../portfolio-mod-05/design.md).

## 6.1 Responsabilidad y fuentes de verdad

Portfolio transforma datos de varios módulos en una vista financiera explicable:

| Dato | Fuente |
| --- | --- |
| Posición y disponibilidad actual | Alpaca |
| Ejecuciones registradas localmente | Ledger de orders |
| Reservas locales de venta | Orders |
| Precio preferente y clasificación de instrumento | Market data |
| Configuración visual y preferencias de reportes | Identity |
| Equity | Wallet |
| Vínculo cliente–broker | Brokers |
| Comisión reproducible | Adaptador de admin |

Solo persiste sus reportes; no crea un segundo inventario mutable de posiciones.
**Motivo:** copiar posiciones como estado propio introduciría otro proceso de
sincronización y ambigüedad sobre cuál saldo es autoritativo.

Una consecuencia es que las posiciones externas pueden no coincidir con el
historial local: por actividad previa, retrasos de reconciliación u operaciones
fuera del backend. La solución **marca** esa diferencia, no fabrica ejecuciones.

## 6.2 Consulta y valoración de posiciones

`PortfolioService` carga cuenta, posiciones positivas, reservas, ejecuciones,
cotizaciones y metadatos. Las lecturas independientes pueden ejecutarse en
paralelo sin compartir una `AsyncSession`.

Por símbolo:

```text
precio = cotización de market_data, o current_price de Alpaca si no está disponible
cantidad_reservada = qty - qty_available + reserva_local_activa
valor_mercado = qty × precio
costo_base = qty × avg_entry_price
resultado_no_realizado = valor_mercado - costo_base
```

`price_source` distingue la procedencia usada. La reserva combina compromiso
externo y local todavía no transferido; sumar nuevamente todas las reservas
transferidas duplicaría cantidades.

Se marca `reconciliation_mismatch` cuando la cantidad reconstruida del ledger no
coincide con Alpaca o el replay detecta una venta sin compras suficientes. No
significa automáticamente fraude ni pérdida de activos.

Los totales se calculan sobre **todas** las posiciones y luego se aplica la
preferencia visual. Ocultar posiciones por umbral no reduce el patrimonio
mostrado en totales.

Se ordena por símbolo, valor, ganancia/pérdida o allocation; el desempate es
símbolo ascendente. El umbral oculta importes estrictamente menores que él, no
los iguales.

## 6.3 Historial de operaciones

El historial viene de ejecuciones, no de intenciones de orden. Una orden sin
fill no aparece como compra ya realizada.

`ExecutionLedger` de orders une ejecución y orden, y aporta lado, instrumento,
exchange, actor firmante y términos económicos. El adaptador de portfolio
convierte el contrato a sus propios registros.

La paginación usa cursor de timestamp e identificador textual de ejecución;
no asume que el ID de actividad Alpaca sea UUID. La comisión se acompaña de
`commission_source`, `official` o `reference`.

Los periodos por fecha abarcan de 00:00 del día inicial a 00:00 del siguiente al
día final en `America/New_York`, convertidos a UTC; el límite superior es
exclusivo. Se acepta hasta 366 días y se rechaza inicio posterior al final.

## 6.4 Costo promedio y resultado realizado

`domain/pnl.py` reconstruye posiciones mediante replay ordenado por
`(executed_at, execution_id)`. Ese desempate hace el resultado independiente del
orden en que llegaron las filas.

Mantiene **costo total**, no un promedio ya redondeado:

- Compra de `q` a `p`: suma `q` a cantidad y `q × p` al costo.
- Venta de `q`: retira `costo_total × q / cantidad_previa`.
- Venta total: retira exactamente todo el costo restante.
- Resultado bruto: ingreso de venta menos costo retirado.
- Resultado neto de la venta: bruto menos comisión aplicada a esa ejecución.

El promedio se calcula para presentar `costo_total / cantidad`, si queda cantidad.
No se trata de FIFO ni de lotes tributarios.

### Ejemplo

```text
Compra 2 × 100 = costo 200, cantidad 2
Compra 1 × 130 = costo 330, cantidad 3, promedio 110
Venta 1 × 140 = retira costo 110, resultado bruto 30
Quedan 2 acciones, costo 220, promedio 110
```

Una venta no cambia el costo promedio de las restantes. Si se venden más acciones
que las reconstruidas, solo se calcula resultado sobre la cantidad disponible
y se marca mismatch. Una venta totalmente sin respaldo local no genera un
resultado inventado.

**Precisión:** las divisiones usan contexto decimal de precisión 40 y las sumas/
restas relevantes usan `domain/decimal_math.py` para conservar residuos exactos.
Esta decisión corrige la propuesta inicial de usar precisión fija para todo:
Hypothesis demostró que podía romper la igualdad de conservación.

## 6.5 Resultado no realizado y rentabilidad

El resultado no realizado valora las posiciones actuales; el realizado se
obtiene de ventas del periodo, reproduciendo también el historial anterior
necesario para conocer su costo.

La rentabilidad definida por este módulo es:

```text
(realizado_del_periodo + no_realizado_actual)
------------------------------------------------ × 100
(costo_actual + costo_retirado_por_ventas_del_periodo)
```

Con denominador cero devuelve `null`, no división por cero ni un porcentaje
falso. Es una métrica descriptiva concreta, **no** TWR, IRR ni rentabilidad
tributaria ajustada por todos los flujos de caja.

## 6.6 Estadísticas y distribución

`StatisticsService` resume:

- Número de ejecuciones y compras/ventas.
- Volumen `suma(qty × price)`.
- Desglose por mercado, instrumento y sector.

Un instrumento sin catálogo usa mercado `unknown`; sin sector usa `unclassified`.
No se elimina volumen porque falte clasificación.

Para porcentajes se utiliza mayor residuo:

1. Se calculan porcentajes exactos.
2. Se truncan a centésimas.
3. Las centésimas restantes se reparten por mayor residuo y desempate por clave.

**Por qué:** redondear cada categoría de forma independiente puede producir
99,99 % o 100,01 %. Con total positivo, esta estrategia conserva 100,00 %.

## 6.7 Perfil conductual de riesgo

`RiskProfileService` utiliza una ventana configurable, normalmente 90 días.
No es el nivel beginner/experienced declarado en el registro, ni un cuestionario
regulatorio de idoneidad.

`domain/risk.py` calcula:

| Subíndice | Fórmula, acotada a 100 donde aplica |
| --- | --- |
| F: frecuencia | `min(100, numero_ejecuciones × 70 / dias_ventana)` |
| C: concentración | `100 × suma((valor_posicion / valor_total)²)` |
| E: exposición | `min(100, valor_total / equity × 100)` |
| T: rotación | `min(100, volumen / equity / 4 × 100)` |

```text
score = 0,25 F + 0,30 C + 0,25 E + 0,20 T
```

Se redondea a dos decimales antes de clasificar:

- Hasta 33,33: conservative.
- Hasta 66,66: moderate.
- Por encima: aggressive.

Si no hay equity positivo se pone E=T=0 y `equity_unavailable=true`; eso no debe
interpretarse como demostración de riesgo bajo. Sin ejecuciones ni posiciones:
`insufficient_data`, sin score.

**Por qué reglas y pesos explícitos:** son deterministas, verificables y
explicables sin entrenar modelos ni llamar a un proveedor de scoring.

## 6.8 Reportes bajo demanda y programados

`ReportBuilder` construye un contenido con posiciones, resumen de activos,
ejecuciones, volumen, resultados, comisiones y rentabilidad. `ReportService`
lo persiste como JSONB con decimales serializados en strings.

**Distinción temporal esencial:** las posiciones son actuales al generar el
reporte y se etiquetan con `positions_as_of`. Pedir un periodo pasado **no
reconstruye posiciones al cierre de ese periodo**. Se combinan actividad del
periodo y valoración vigente según el diseño.

La persistencia conserva exactamente lo generado. El trigger impide cambiar el
contenido; `notified_at` es la excepción permitida para seguimiento de entrega.

`ReportScheduler` corre normalmente cada 900 s:

- Diario: última sesión cerrada, para usuarios con preferencia de resumen.
  Evita crear uno vacío sin ejecuciones ni posiciones vigentes.
- Mensual: mes anterior, para quienes lo solicitaron.
- Si falla un usuario, registra fallo y sigue con los demás.
- Un índice único parcial evita duplicar reporte programado por dueño/tipo/periodo.
- Si existe reporte sin `notified_at`, intenta notificarlo de nuevo sin regenerar.

**Tradeoff:** si la entrega ocurrió y se perdió la marca posterior, puede repetirse
el aviso. Se prioriza reintento de este aviso, a diferencia del marcador previo
de wallet que prioriza no duplicar.

No se genera automáticamente un PDF ni se envía un adjunto: el recurso de
reporte es contenido JSON consultable por API.

## 6.9 Reportes del broker y acceso

Los endpoints de comisionista usan el vínculo vigente publicado por brokers:

- Consultar posiciones/reportes de un cliente exige pertenencia actual.
- Un reporte de broker agrega clientes vinculados y atribuye comisiones de
  ejecuciones firmadas por él.
- El acceso a un reporte propio usa su propietario, no solo conocer su ID.
- Un adaptador nulo devuelve conjunto vacío durante desarrollo aislado; en la
  aplicación completa está instalado el de brokers.

Se publica además `PortfolioPositionPort` para que orders consulte acciones
disponibles usando la integración de posiciones ya centralizada.

## 6.10 Redondeo y comisiones

En salidas se usa half-even:

| Tipo | Escala |
| --- | --- |
| Dinero | 2 decimales |
| Cantidad | 9 |
| Precio | 4 |
| Porcentaje | 2 |

Los cálculos internos no se reducen indiscriminadamente a esas escalas.
Las comisiones oficiales se obtienen por ejecución con términos de la orden.
Para históricos sin términos, el adaptador de admin conserva una estimación
`reference`, nunca la etiqueta como oficial. Las consultas oficiales y KPI
cuentan esos históricos como desconocidos/excluidos.

## 6.11 Código y comprobación

Núcleo: `domain/{pnl,decimal_math,valuation,statistics,rounding,risk,profitability}.py`.
Aplicación: `portfolio_service.py`, `statistics_service.py`,
`risk_profile_service.py`, `report_builder.py`, `report_service.py` y
`report_scheduler.py`.

Las pruebas en `tests/portfolio/property/` verifican conservación, determinismo,
porcentajes, riesgo y serialización. `api/test_postgres_flow.py` cubre recorrido
con repositorios reales y proveedores fake; no equivale a ejecutar trading real.
