# Decisiones de implementación MOD-07

Esta revisión prevalece sobre las propuestas originales de requirements.md,
design.md y tasks.md. Fuente adicional disponible: `.kiro/SAD.tex`.

## H1 — Separación de responsabilidades (aprobada)

Se incorporan `auditor` y `analyst` como roles asignables exclusivamente por
administradores mediante RBAC existente; no hay registro público de estos roles.
RF-03, RF-44, RF-45 y RF-47 del SAD, RNF-04, RNF-05, EC-04 y EC-05 justifican
separar consulta de evidencia, indicadores agregados y control operativo.

| Rol | Permisos iniciales MOD-07 |
| --- | --- |
| administrator | admin:fees, admin:commissions, admin:halts, admin:audit, admin:compliance, admin:compliance:read, admin:bi (además de sus permisos actuales) |
| auditor | admin:audit, admin:compliance:read |
| analyst | admin:bi |

`admin:compliance` permite restricciones y generación de reportes; las consultas
requieren `admin:compliance:read`. El auditor no crea reportes ni restricciones.
El analista recibe exclusivamente indicadores agregados, sin identificadores ni
evidencia individual. Los permisos de control `admin:*` no se pueden asignar a
otros roles; los permisos de lectura solo admiten los roles de la tabla. Tampoco
se puede otorgar `admin:rbac` a otros roles ni retirarlo de administrator. Se
mantienen investor y broker y la protección del último administrador. Se
reemplaza así G2/G26, ADR-6 y la Property 18 original.

## H3 — Términos económicos inmutables (aprobada)

Se guardan ID de versión, tasa y reparto al crear cada orden. La revalidación,
programación y cada ejecución parcial usan esos mismos términos. Cada ejecución
se redondea half-even a centavos; la comisión de la orden es la suma de sus
ejecuciones y la parte del broker se obtiene por diferencia para conservar el
total. No se cobra ni liquida en Alpaca (RF-43, RF-46; RNF-07).

**Corrección del criterio 2.6:** las órdenes anteriores conservan columnas nulas.
No se rellenan con la semilla ni con la configuración actual. Sus comisiones
oficiales son desconocidas (`historical_terms_unknown`), se cuentan como
excluidas en agregados y no se presentan como cero ni como ingresos oficiales.
En portfolio se conserva una estimación de referencia etiquetada `reference`
para compatibilidad de cálculos anteriores, nunca `official`. Una orden antigua
pendiente conserva su estimación de reserva de referencia y sus términos nulos.
La migración impide modificar los términos guardados posteriormente.

## H7 — Detección explicable (definición autorizada)

RF-45 del SAD deja los criterios sujetos a definición y exige autorización para
aplicar restricciones. Se implementan reglas deterministas, sin ML ni servicios
externos. Las señales no prueban fraude ni restringen automáticamente cuentas.
Solo administrator decide restringir/rehabilitar, con TOTP, motivo y evidencia.

Versión `atypical-v2`, configuración por entorno y capturada en cada reporte:

| Regla | Umbral inicial | Ventana y datos |
| --- | --- | --- |
| absolute_threshold | ejecución >= USD 10000 | importe qty × price |
| relative_to_history | ejecución > 3 × media, mínimo 5 antecedentes | 90 días anteriores, excluye el instante actual |
| order_frequency | >= 20 órdenes creadas | últimos 300 segundos, por usuario |
| cancellation_frequency | >= 10 cancelaciones locales confirmadas | últimos 300 segundos, por usuario |
| repeated_rejections | >= 5 órdenes rechazadas consecutivamente | últimos 3600 segundos, excluye FAILED y errores externos |

Las ventanas de comportamiento son `(t-ventana,t]`; la historia económica es
`[t-90 días,t)`. Eventos simultáneos se evalúan en conjunto y el resultado no
depende del orden de entrada. Solo el estado CANCELED cuenta como cancelación;
solicitudes fallidas y parciales no cuentan. Un rechazo externo/infraestructura
interrumpe la racha y no se atribuye al usuario. Cada señal conserva regla,
umbral, valor observado, ventana, referencias y configuración/versionado.

## Resto de propuestas y límites

La solicitud de implementación completa autoriza desarrollar las propuestas
técnicas H2/H4/H5/H6/H8/H11/H13/H14 dentro del alcance: TOTP; half-even por
ejecución; tasa 0–10%; zona horaria de lectura; KPI v1; Active_Link para broker;
evento de horarios y secuencia de sprints. Son decisiones de implementación,
no aprobaciones humanas inventadas. H9 (rol DB/anclaje), H10 (cobro Alpaca), H12
(intersección de calendario) y H15 (política de retención) se difieren: no se
cambian despliegue, cobros ni calendario y no se agrega purga. Los límites de
inmutabilidad frente al propietario de PostgreSQL siguen explícitos (G17).

## Verificación de dependencias

- Última migración previa: 0009_brokers_schema. Se reservan 0010, 0011 y 0012.
- orders captura contexto en register; portfolio resuelve su puerto al usarlo.
- ScheduleChangeService es idempotente por change_id; proposal_orders propaga
  errores >=500 y convierte rechazos de negocio anteriores a crear la orden.
- No se encontraron mutadores de order_events/order_executions/auth_events.
- Las pruebas offline actuales son por revisión explícita: se agregan pruebas
  para las tres revisiones nuevas; smoke usa head automáticamente.
- No se consultan datos reales de sandbox para validar exchanges; los códigos
  desconocidos usan default y solo halt global, como establece A2.

## Trazabilidad y pruebas adicionales

H1: RF-03/44/45/47, RNF-04, EC-04; pruebas de permisos permitidos/denegados y
asignaciones privilegiadas. H3: RF-43/46, RNF-07, EC-05; persistencia, trigger,
ejecuciones parciales, cambio de tarifa e históricos sin evidencia. H7:
RF-45/30/34, RNF-05/08; pruebas de límites, simultaneidad, orden de entrada,
separación de fallos externos y ventanas de cada regla.
