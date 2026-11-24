# 8. MOD-07: administración, auditoría, compliance y KPI

[Índice](README.md) · [Anterior](07-comisionistas.md) · [Siguiente](09-estrategias-datos.md)

**Paquete:** `src/acciones_ud/admin/`.  
**Trazabilidad:** RF-43..47, RFP-10 y RFP-13.
Consultar [requisitos](../admin-mod-07/requirements.md),
[diseño](../admin-mod-07/design.md) y, con prioridad sobre propuestas iniciales,
[decisiones de implementación](../admin-mod-07/implementation-decisions.md).

## 8.1 Responsabilidad y separación de facultades

Admin configura términos económicos y restricciones locales, consulta evidencia
y calcula indicadores. No llama a Alpaca/Stripe directamente y no convierte sus
políticas en órdenes de suspensión externas.

Los routers verifican **permiso y rol permitido**, no solo un string de permiso:

| Capacidad | Administrator | Auditor | Analyst |
| --- | --- | --- | --- |
| Tarifas, comisiones administrativas, mercados y halts | Según permiso | No | No |
| Rastro de auditoría | Sí | Sí | No |
| Lectura compliance | Sí | Sí | No |
| Restricciones y generación de reporte compliance | Sí | No | No |
| KPI agregados | Sí | No | Sí |

`adapters/inbound/http/deps.py` concentra estas dependencias y registra accesos
rechazados sin volcar cuerpos. Identity protege la asignación de permisos para
que otro rol no pueda convertirse en administrador por una modificación de RBAC.

**Por qué:** consultar evidencia individual, estudiar tendencias y controlar
operación son responsabilidades diferentes.

## 8.2 Tarifas versionadas

`FeeService` no sobrescribe una configuración global. Crea versiones con:

- Scope `default` o mercado.
- Número de versión y fecha de entrada en vigor.
- Comisión porcentual entre 0 y 10, hasta cuatro decimales.
- Porcentaje de reparto para plataforma entre 0 y 100, hasta dos decimales.
- Actor, motivo y evidencia de auditoría.

No se permiten vigencias retroactivas. El cliente envía
`expected_latest_version`; se compara bajo advisory lock por scope. El índice
único y la comparación evitan cambios perdidos si dos administradores editan
basándose en la misma versión.

La resolución toma la versión no cancelada más reciente efectiva para el mercado
y, si no existe, la default. La semilla inicial es comisión 2 % y reparto
plataforma 60 %. No encontrar default efectivo es fallo de configuración/esquema,
no autorización para inventar una tarifa de referencia.

El estado es derivado del tiempo: scheduled, in_force, superseded o canceled.
Solo se cancela una versión aún futura. Para cambiar una vigente se crea otra.

**Por qué versionar:** una tarifa nueva no debe reescribir lo que se pactó en una
orden antigua.

## 8.3 Captura inmutable en cada orden

Orders consulta el puerto `CommissionTermsPort` en el instante de creación y
guarda `fee_version_id`, `commission_rate_pct` y `platform_share_pct`.

El envío programado, revalidación y todas las ejecuciones parciales utilizan
estos términos. La migración protege su inmutabilidad con trigger.

**Históricos anteriores a MOD-07:** sus columnas permanecen nulas. No se rellenan
con 2 % ni con la tarifa actual, porque no existe evidencia de que esos fueran
los términos originales. La consulta oficial los señala
`historical_terms_unknown`, y los agregados informan exclusiones/completitud.

Portfolio puede seguir mostrando estimación `reference` para compatibilidad, pero
esa estimación no se transforma en ingreso oficial.

## 8.4 Cálculo y reparto de comisiones

`domain/commissions.py` calcula por ejecución:

```text
bruto = qty × price
comisión = half_even_centavos(bruto × tasa_pct / 100)
```

Si hay broker firmante:

```text
plataforma = half_even_centavos(comisión × reparto_plataforma_pct / 100)
broker = comisión - plataforma
```

Sin firma de broker, toda la comisión se asigna a plataforma. Calcular la parte
del broker por diferencia conserva exactamente la suma.

La comisión de una orden es suma de comisiones de ejecuciones. No es
necesariamente igual a redondear una vez el bruto total, porque cada ejecución
redondea independientemente.

### Ejemplo

Una ejecución de USD 1 000 con tasa 2 % produce USD 20 de comisión; con firma y
reparto 60 %, USD 12 son de plataforma y USD 8 del broker. Una compra tiene total
teórico 1 020; una venta, neto teórico 980.

**No se cobra ese monto por esta función.** No se envían campos de comisión ni
se liquidan esos repartos en Alpaca. Son cifras oficiales del modelo local,
no prueba de cobro bancario real.

La cotización `/commissions/quote` usa términos efectivos para estimar antes de
crear; las consultas de ejecuciones usan términos capturados. El cálculo es puro
y se repite al leer para no introducir una dependencia de orders hacia un
servicio de admin durante reconciliación.

## 8.5 Step-up TOTP en controles sensibles

Crear/cancelar tarifa, activar/liberar halt y restringir/rehabilitar exigen TOTP,
además de sesión y facultad administrativa.

`StepUp` llama al servicio de identity **antes** de abrir la transacción de la
mutación. Evita retener locks de negocio durante la comprobación del factor y
reutiliza protección contra reuso.

**Consecuencia:** si el TOTP se consumió y luego la mutación falló por conflicto,
ese mismo código no debe considerarse reutilizable. La seguridad del segundo
factor y la transacción de negocio no constituyen una única transacción.

## 8.6 Interruptores de negociación y restricciones

### Trading halts

`HaltService` permite scope global o mercado, inicio y final opcional, motivo,
actor y posterior liberación. Evita solapamientos incompatibles bajo lock por
scope y registra cada mutación con auditoría.

Los estados scheduled/active/expired/released se deducen de tiempos y liberación.
Llegar al final no requiere un job que cambie todas las filas a expired.

### Restricciones individuales

`RestrictionService` registra una restricción local de trading por usuario con
motivo y evidencia, máximo una activa. No permite auto-restricción del actor en
esta operación. La rehabilitación conserva una decisión nueva, no borra la
restricción pasada.

El control no desactiva login ni consultas del usuario. Tampoco suspende la cuenta
en Alpaca ni cancela órdenes ya enviadas.

### Trading gate

El puerto instalado en orders evalúa:

1. Halt global, con prioridad.
2. Halt de mercado.
3. Restricción individual.
4. Permitir si no hay control aplicable.

Un halt devuelve 503 `TRADING_HALTED`; restricción individual devuelve 403
`ACCOUNT_TRADING_RESTRICTED`. La diferencia es funcional: la indisponibilidad
temporal de trading deja una conversión de propuesta reintentable; una
restricción de negocio puede producir rechazo de conversión.

Si no se puede comprobar el gate por fallo de datos, no se permite enviar por
defecto: **fail closed**.

**Ventana residual:** una orden que ya pasó el control puede salir mientras se
confirma un halt. El control local no es un cerrojo distribuido con Alpaca ni
revierte envíos en curso.

## 8.7 Vista de mercados y propagación de horarios

Los endpoints administrativos consolidan mercados, tarifas, halts e historial.
La edición de horarios sigue siendo de market_data; no se duplica con otra
tabla de calendario en admin.

Cada cambio deja un `admin_audit_log` y después invoca un listener. El listener
lanza tarea inmediata y un job cada 30 s reintenta entradas sin despacho:

1. Lock por identificador del evento.
2. Comprueba si ya se despachó.
3. Invoca `order_schedule_change_port.apply` con change ID estable.
4. Registra despacho y órdenes afectadas.
5. Tras commit, intenta avisos de `market_schedule_changes`.

La idempotencia de orders permite recuperar la caída entre aplicar el cambio y
guardar el marcador de admin. La tabla de despachos permite ver pending/dispatched.

**Garantía de avisos:** el marcador previo evita intentos duplicados, pero si cae
antes de enviar se pueden perder avisos. El patrón se parece a un despacho
durable especializado, no es un outbox universal de todos los eventos.

## 8.8 Auditoría unificada y cadena de custodia

Se reutiliza `admin_audit_log`; no se crea un registro paralelo con contenido
duplicado. La vista SQL `audit_trail` usa `UNION ALL` de:

| Fuente | Información |
| --- | --- |
| `admin` | Cambios de identidad, tarifas, horarios y controles |
| `orders` | Transiciones de órdenes |
| `brokers` | Vínculos, autorizaciones y propuestas |
| `auth` | Intentos de login y MFA |

Las columnas comunes permiten buscar por periodo, usuario implicado, fuente,
acción y entidad. Se pagina por `(occurred_at, source, event_id)`, no solo fecha,
para desempatar eventos simultáneos.

El endpoint de custodia de orden reúne orden, eventos, fills, cancelaciones,
reautorizaciones y propuestas asociadas; deriva creador, método de autorización,
firma y primer envío. Es una reconstrucción de evidencia, **no blockchain ni
cadena criptográfica global**.

Se sanitizan campos y payloads y se escriben entradas administrativas en la
misma transacción del cambio. Si no puede guardarse auditoría, la operación
administrativa no debe quedar confirmada sin evidencia.

## 8.9 Detección explicable de operaciones atípicas

Se usa `atypical-v2`, sin ML. Los umbrales iniciales configurables son:

| Regla | Criterio |
| --- | --- |
| Importe absoluto | Ejecución de al menos USD 10 000 |
| Relativa a historia | Mayor que 3 × media previa, mínimo 5 antecedentes en 90 días |
| Frecuencia de órdenes | Al menos 20 creadas en 300 s |
| Cancelaciones | Al menos 10 confirmadas en 300 s |
| Rechazos repetidos | Al menos 5 rechazos consecutivos de negocio en 3 600 s |

Historia económica: `[t-ventana,t)`. Comportamiento: `(t-ventana,t]`. Los eventos
simultáneos se evalúan en conjunto para no depender del orden de entrada.

Un error de red, FAILED o rechazo atribuible a infraestructura no se convierte
en acusación al usuario; puede cortar la racha en vez de contarla.

La señal conserva regla, umbral, valor, ventana, referencias y configuración.
**Atípico no significa fraude.** No restringe automáticamente: decide un
administrator con TOTP, motivo y evidencia.

## 8.10 Reportes de auditoría de usuario

`ComplianceService.generate_report` combina resumen del usuario, actividad,
ejecuciones, comisiones conocidas, comparación con población, señales y
restricciones del periodo.

Canonicaliza contenido sanitizado, calcula SHA-256 y guarda reporte inmutable
con versión de reglas y configuración; además registra su generación en auditoría.

**Qué prueba el hash:** permite comparar contenido con la huella guardada.
**Qué no prueba:** autenticidad independiente frente a quien pueda alterar tanto
contenido como hash o desactivar controles con privilegios de propietario.
No hay anclaje externo ni firma de tercero.

El auditor puede leer, pero no generar este recurso mediante una facultad de
solo lectura. Los reportes son JSON persistido, no expedientes PDF certificados.

## 8.11 KPI y caché versionada

`KpiService` publica métricas `kpi-v1`, con valor, unidad y definición:

- Usuarios registrados, nuevos y activos.
- Volumen negociado y número de ejecuciones, por mercado/lado.
- Comisiones de plataforma.
- Suscripciones activas e ingresos por fuente.
- Distribución de inversionistas por nivel y con/sin comisionista.

SQL obtiene agregados y Python calcula comisiones por ejecución con half-even.
Usar indiscriminadamente `round()` SQL introduciría diferencias en empates.
Los históricos sin términos se excluyen explícitamente de ingresos oficiales;
pagos no USD también se cuentan como excluidos, no se convierten implícitamente.

`admin_kpi_snapshots` identifica periodo y versión de definiciones. TTL normal
300 s; `refresh` fuerza recálculo. Devuelve `computed_at`, `as_of`, `cache_hit` y
`stale`. Si, después de leer un snapshot, recalcular falla por indisponibilidad
de datos, puede servir el anterior marcado stale.

**Límite:** si ni siquiera se pudo leer el snapshot inicial o el fallo no es
la categoría recuperable, no hay fallback garantizado. Son indicadores con
caché, no un stream en tiempo real ni un único snapshot transaccional de toda la
plataforma.

## 8.12 Inmutabilidad y decisiones pendientes

Las migraciones 0010..0012 añaden protección contra cambios/borrados y TRUNCATE
en fuentes relevantes, conservando excepciones controladas como liberar un halt.
El propietario de PostgreSQL puede desactivar triggers o alterar estructura:
el sistema no afirma resistencia criptográfica frente al administrador total.

Siguen diferidos, entre otros:

- Rol DB de mínimo privilegio y anclaje externo de evidencia.
- Cobro/liquidación de comisiones en Alpaca.
- Intersección adicional de calendario local y externo.
- Política de retención/purga; no se añade borrado automático.

Código principal: `application/{fee_service,commission_service,halt_service,
restriction_service,schedule_change_dispatcher,compliance_service,kpi_service}.py`.
Pruebas: `tests/admin/property/`, `api/test_access_control.py`,
`unit/test_database.py` y `unit/test_behavior_and_cache.py`.
