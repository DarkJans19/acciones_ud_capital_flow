# Revisión E2E — Módulo 7

**Fecha:** 24 de noviembre de 2026.  
**Alcance:** `.kiro/specs/admin-mod-07/`, RF-03, RF-43–47, RF-27,
RFP-10 y RFP-13.

No se modificó la implementación. Se revisaron los flujos HTTP, persistencia,
seguridad y regresión; los límites de la evidencia se indican explícitamente.

## Resultado

**Los flujos probados funcionan tanto con PostgreSQL local como con Supabase
después de aplicar las migraciones autorizadas.** No hubo respuestas HTTP
inesperadas ni comprobaciones funcionales fallidas. Sí se observó latencia
remota alta y quedan verificaciones de alcance/rendimiento pendientes.

| Entorno | Solicitudes registradas | Comprobaciones adicionales | Resultado |
|---|---:|---:|---|
| Local/Docker | 126 | 24 | Todas correctas; incluye complemento con fixtures |
| Supabase | 108 | 18 | Todas correctas |
| Regresión automatizada | 716 pruebas | Incluye PostgreSQL real y migraciones | Todas correctas |

Estas 234 solicitudes incluyen los errores negativos esperados y la
autenticación mínima necesaria. No significan 234 endpoints diferentes ni
cobertura exhaustiva de todas las combinaciones.

## Entornos y método

- **Local:** backend ejecutado en esta máquina y PostgreSQL 17 real en Docker.
  Contenedor aislado `acciones-ud-mod07-review`, puerto `127.0.0.1:55433`;
  base `mod07_e2e` para E2E y `mod07_tests` para la suite destructiva.
  No había un contenedor PostgreSQL disponible al comenzar.
- **Supabase:** el mismo backend local conectado a la base administrada real
  mediante la conexión de aplicación; Alembic usa la conexión de migraciones.
  Esto prueba el backend **contra Supabase**, no un backend desplegado en Internet.
- API local: `https://127.0.0.1:8447`; API con Supabase:
  `https://127.0.0.1:8448`. Certificado autofirmado únicamente para esta revisión.
  HTTPS permite probar las cookies `Secure` sin desactivar su protección.
- Dependencias instaladas desde `uv.lock`, con `uv`; Python 3.14.4 disponible
  en esta máquina. El proyecto declara Python 3.12+.
- El archivo existente se llama `env`, no `.env`. Se cargó explícitamente en
  cada proceso, sin copiarlo al repositorio ni divulgar sus valores.
- Sin mocks, sin `dependency_overrides`, sin fabricar sesiones ni omitir MFA.
  Las llamadas necesarias de órdenes usan Alpaca **sandbox**.
- Jobs periódicos deshabilitados en los procesos de revisión para evitar
  reconciliaciones y notificaciones ajenas al caso. El listener inmediato de
  cambios de horario permanece activo. El job periódico se valida en la suite,
  no mediante espera de su ciclo en este E2E.

### Preparación local de datos

En la base Docker recién migrada se copiaron únicamente los cinco usuarios de
prueba suministrados, sus cinco asignaciones de rol, los instrumentos AAPL/MSFT
y la cuenta KYC ya vinculada al investor. Se conservaron sus identificadores y
el cifrado MFA; se utilizó la misma clave de cifrado del entorno.

No se copiaron órdenes, ejecuciones ni todo el contenido de Supabase. Esta
preparación es un **fixture de entrada**, no evidencia de que funcionen el alta
de usuarios, el enrolamiento MFA o la creación de cuentas KYC en este flujo.
No se necesitó repetir esos módulos.

## Estado inicial de Supabase y migraciones

Ambas conexiones remotas funcionaban, pero `alembic_version` estaba en
`0009_brokers_schema`. Antes de migrar se verificó por HTTPS:

1. Login y MFA del administrador: HTTP 200.
2. `GET /api/v1/admin/fee-schedules`: HTTP 403 `FORBIDDEN`, porque faltaban
   las nuevas concesiones de permisos.
3. Login y MFA del investor: HTTP 200.
4. `GET /api/v1/commissions/quote?symbol=AAPL&side=buy&qty=10&price=187.35&with_broker=true`:
   HTTP 500 `DATABASE_SCHEMA_ERROR`, porque faltaba el esquema del módulo.

**Esto no era un problema de “commit” de Git:** faltaba desplegar las
migraciones de Alembic. Tras solicitar y recibir autorización explícita,
se aplicaron, en orden:

```text
0009_brokers_schema
  → 0010_admin_fees_audit
  → 0011_admin_audit_trail_halts
  → 0012_admin_compliance_bi
```

La migración terminó correctamente. No se ejecutaron `downgrade`, borrados
de tablas ni fixtures destructivos sobre Supabase. Los históricos conservaron
sus términos de comisión nulos, sin inventar datos mediante backfill.

Evidencia: [antes de migrar](MOD07_SUPABASE_ANTES_MIGRACION.json).

## Usuarios y autenticación

Se utilizaron las cuentas suministradas:

| Alias | Correo | Uso |
|---|---|---|
| admin | admin.ti@accionesud.com | Administración, consultas y step-up |
| admin2 | admin2.ti@accionesud.com | Segunda identidad administrativa para step-up |
| investor | investor.ti@accionesud.com | Cotización, órdenes y cuenta restringida temporalmente |
| broker | broker.ti@accionesud.com | Comisiones; prueba temporal de analyst |
| broker2 | broker2.ti@accionesud.com | Aislamiento de clientes; prueba temporal de auditor |

**No fue necesario crear usuarios ni contraseñas nuevas.** Las contraseñas,
semillas TOTP, códigos de recuperación, tokens y cookies existentes no se
reproducen en este documento. No se consumieron códigos de recuperación.

Flujo de acceso, por cada usuario:

```http
POST /api/v1/auth/login
Content-Type: application/json
```

```json
{"email":"admin.ti@accionesud.com","password":"<CONTRASEÑA_SUMINISTRADA>"}
```

La respuesta entrega `mfa_token`, su caducidad y `totp_enrollment: null`.
Después:

```http
POST /api/v1/auth/mfa/verify
```

```json
{"mfa_token":"<TOKEN_DEL_LOGIN>","code":"<TOTP_VIGENTE_DE_6_DÍGITOS>"}
```

La API responde con el usuario y establece las cookies de sesión. Las
solicitudes siguientes usan esas cookies; no se sustituyeron por un Bearer
token ni por un JWT fabricado. Cada operación crítica emplea un TOTP nuevo,
respetando la protección contra reutilización. Se alternaron admin/admin2
y se esperó la ventana necesaria, sin modificar el reloj ni el estado MFA.

Para las pruebas de mínimo privilegio se asignan temporalmente `auditor`
a broker2 y `analyst` a broker, mediante los endpoints RBAC existentes.
Esos usuarios conservan su rol broker: se comprueban las capacidades
administrativas añadidas, no usuarios de rol único recién registrados.
Las asignaciones temporales se revocan al terminar.

## Lectura del flujo completo

Los anexos son transcripciones ordenadas de las solicitudes reales:

- [Local: paso a paso, JSON y respuestas](MOD07_E2E_LOCAL.md).
- [Supabase: paso a paso, JSON y respuestas](MOD07_E2E_SUPABASE.md).
- [Evidencia JSON local](MOD07_E2E_LOCAL.json).
- [Evidencia JSON Supabase](MOD07_E2E_SUPABASE.json).
- [Comprobación de seguridad remota](MOD07_SUPABASE_SEGURIDAD.json).
- [Contrato OpenAPI consultado](MOD07_OPENAPI.json).
- [Estado final de las dos bases y triggers](MOD07_ESTADO_FINAL_DB.json).

Cada paso incluye actor, método, URL con filtros, JSON enviado, estado esperado,
estado real, JSON recibido, duración y `X-Request-ID`. `<REDACTED>` significa
que se envió un secreto real y se ocultó **después** de la ejecución; no es
el valor usado para autenticar. HTTP 204 tiene cuerpo vacío.

## Resumen funcional del recorrido

Los números concretos de paso, identificadores y respuestas completas están en
los anexos. Este es el orden de negocio:

| Bloque | Solicitudes principales | Verificación |
|---|---|---|
| Acceso | Login → MFA → `/users/me` → `/admin/roles` | Sesión real, roles nuevos y permisos efectivos; anónimo 401 e investor 403 |
| Parametrización | `GET /admin/fee-schedules`, `GET/POST /admin/fee-schedules/NASDAQ/versions`, `POST .../{id}/cancel` | Semilla 2 %, reparto 60/40, versión futura, conflicto optimista 409, cancelación y no retroactividad |
| Cotización | `GET /commissions/quote` | Compra/venta, con/sin broker, decimales exactos; cantidad inválida 422, símbolo inexistente 404, rol no habilitado 403 |
| Comisiones | `GET /commissions`, `/broker/commissions`, `/admin/commissions` | Periodos, aislamiento por investor/broker y vínculo; histórico desconocido sin backfill |
| Órdenes mínimas | `POST /orders/preview`, `POST /orders`, `POST /orders/{id}/cancel` | Orden AAPL limitada a USD 1, términos fijados y cancelación posterior; solo sandbox |
| Custodia | `GET /admin/audit-trail/orders/{id}` | Orden, eventos, términos, firma, envío y ejecuciones disponibles; desconocida 404 |
| Halt | `POST /admin/trading-halts`, `GET /admin/trading-halts`, `GET /trading-halts/active`, `POST .../{id}/release` | Bloqueo NASDAQ devuelve 503 `TRADING_HALTED`; lecturas disponibles; vista pública no filtra motivo/actor; liberación |
| Cumplimiento | `POST/GET /admin/compliance/restrictions`, `POST .../{id}/lift` | Bloqueo 403 `ACCOUNT_TRADING_RESTRICTED`, perfil sigue disponible y rehabilitación |
| Señales | `GET /admin/compliance/atypical-operations` | Reglas/versionado y validación; señal positiva controlada local sin restricción automática |
| Reportes | `POST/GET /admin/compliance/users/{id}/audit-reports`, `GET /admin/compliance/audit-reports/{id}` | Persistencia y SHA-256 recalculado sobre el JSON recibido |
| Indicadores | `GET /admin/kpis?from=...&to=...&refresh=true`, después sin refresh | Cálculo, snapshot, `cache_hit=true` y mismo `computed_at` |
| Auditoría | `GET /admin/audit-trail` con fuente, periodo y cursor | Páginas sin eventos repetidos; fuente/cursor inválidos 422 |
| Mínimo privilegio | Asignación temporal auditor/analyst mediante `/admin/users/{id}/roles` | Auditor lee evidencia/cumplimiento, no escribe ni consulta BI; analyst lee BI, no auditoría; revocación final |
| Protección RBAC | `POST /admin/roles/investor/permissions`, `DELETE /admin/roles/administrator/permissions/admin:rbac` | Ambos intentos prohibidos devuelven 409 `PROTECTED_PERMISSION` |
| Mercados | `GET /admin/markets`, `GET /admin/markets/{code}` | Vista consolidada; mercado inexistente 404 |
| Excepciones | `GET/POST/PUT/DELETE /admin/markets/OTC/schedule-overrides[...]` | Crear, modificar y eliminar excepción futura; tres eventos auditados y despachados |
| Horario base | `PUT/DELETE /admin/markets/OTC/default-schedule` | Se comprueba que no hay órdenes OTC afectables, se cambia y se restaura exactamente |
| Notificaciones | `GET /notifications` | Avisos `market_schedule_changes` reales en el canal in_app |
| Cierre | `POST /auth/logout` y consultas de comprobación de DB | Cierre de sesiones de revisión y ausencia de bloqueos/tarifas de prueba vigentes |

### Ejemplo económico verificado

```http
GET /api/v1/commissions/quote?symbol=AAPL&side=buy&qty=10&price=187.35&with_broker=true
```

No lleva cuerpo JSON. Con tasa 2 % y reparto 60/40:

```json
{
  "gross_amount": "1873.5",
  "commission": "37.47",
  "platform_share": "22.48",
  "broker_share": "14.99",
  "total": "1910.97",
  "net": null,
  "commission_rate_pct": "2",
  "platform_share_pct": "60",
  "binding": false
}
```

Es un extracto; el anexo conserva también símbolo, mercado, identificador de
versión y fecha de cotización. Para venta sin broker el neto es `1836.03`,
la plataforma recibe `37.47` y el broker `0`.

### Evidencia adicional local: ejecuciones controladas

Las órdenes limitadas de USD 1 no se hicieron ejecutar a propósito. Para
verificar también comisiones **no vacías**, se prepararon tres ejecuciones
sintéticas exclusivamente en Docker, mediante repositorios reales:

| Fixture local | Operación | Comisión oficial | Plataforma | Broker |
|---|---|---:|---:|---:|
| `official_signed` | 10 × 187.35, firma de broker, términos 2 % / 60 % | 37.47 | 22.48 | 14.99 |
| `historical` | 1 × 100, sin términos históricos | desconocida | desconocida | desconocida |
| `atypical` | 100 × 200, sin broker, términos 2 % | 400.00 | 400.00 | 0 |

Se verificaron por HTTP:

- `/commissions`: histórico excluido del importe oficial, contador 1 y
  `complete=false`; total oficial de las otras dos ejecuciones `437.47`.
- `/portfolio/executions`: `37.47` y `400.00` con `commission_source=official`;
  el histórico conserva estimación `2.00` con `commission_source=reference`.
  Esa estimación **no** se presentó como comisión oficial.
- `/admin/kpis?refresh=true`: comisión de plataforma `422.48`.
- `/admin/compliance/atypical-operations`: señal `absolute_threshold` por
  USD 20.000; no se restringió automáticamente al usuario.
- Nuevo reporte de cumplimiento: total oficial `437.47` y SHA-256 correcto.

**Esta parte es integración HTTP con fixtures, no una ejecución real de Alpaca
de extremo a extremo.** No se insertaron ejecuciones sintéticas en Supabase,
ni se reescribieron históricos existentes.

## Seguridad de Supabase

Se consultó el catálogo PostgreSQL y se hizo una prueba externa de lectura:

```http
GET <SUPABASE_URL>/rest/v1/audit_trail?select=source,event_id,action&limit=1
apikey: <CLAVE_PUBLICA_PUBLISHABLE>
```

Sin sesión de usuario, JWT privado ni `service_role`:

```json
{
  "code": "42501",
  "details": null,
  "hint": null,
  "message": "permission denied for view audit_trail"
}
```

Resultado: **HTTP 401**. Las siete tablas administrativas tienen RLS activado
y `anon`/`authenticated` no tienen `SELECT` sobre la vista.

Se confirmó la instalación de los triggers de evidencia y términos de órdenes.
Los ensayos de `UPDATE`, `DELETE`, `TRUNCATE`, concurrencia y downgrade se
ejecutaron **solo en la base desechable de la suite**, no sobre Supabase.

La vista sigue siendo propiedad de `postgres` y no tiene `security_invoker`.
No se observó exposición anónima gracias a los permisos actuales; mantener
cerradas esas concesiones es importante. Esto no constituye una auditoría
exhaustiva de toda la configuración de Supabase.

## Validación automatizada

| Comando | Resultado |
|---|---|
| `uv run ruff check .` | Sin errores |
| `uv run mypy src` | Sin errores; 394 archivos |
| `uv run pytest -q --tb=short` con DB Docker aislada | **716 passed**, sin fallos ni skips, 210.88 s |

La suite produjo 2525 advertencias, principalmente deprecaciones de
Starlette/httpx, pytest-asyncio/Python y configuración de Alembic. No son fallos
de los casos de negocio, pero conviene planificar su actualización.

Para ejecutar la suite sin riesgo sobre Supabase se usó **la misma URL local
explícita** en `DATABASE_URL` y `TEST_DATABASE_URL`, apuntando a `mod07_tests`.
El fixture de la suite hace downgrade/upgrade y nunca debe apuntar a una base
compartida.

Dos incidencias del proceso de revisión, ajenas al comportamiento HTTP:

- Un primer intento de pytest no pudo importar la aplicación sin `DATABASE_URL`.
  Se repitió con la URL Docker explícita.
- El límite inicial de 120 segundos interrumpió un intento de suite y los
  primeros servidores. Se repitió con tiempo suficiente; el resultado válido
  es la ejecución completa indicada arriba.
- Un helper complementario local no encontraba el paquete `tests` al lanzarse
  desde `/tmp/opencode`. Se corrigió únicamente el helper temporal de revisión,
  no el código del backend, y se repitió. Por eso el anexo local incluye dos
  comprobaciones de horario base, ambas restauradas.

## Estado que quedó al terminar

Las comprobaciones finales de ambas bases confirman:

- Migración `0012_admin_compliance_bi`.
- Ninguna tarifa temporal de esta revisión quedó sin cancelar.
- Ningún halt temporal quedó sin liberar.
- Ninguna restricción temporal quedó activa.
- Los roles temporales auditor/analyst de broker2/broker quedaron revocados.
- El calendario OTC volvió a su configuración anterior y se eliminó la
  excepción futura de prueba.
- Las dos órdenes creadas por HTTP están `CANCELED`, sin `alpaca_order_id`;
  nunca llegaron a enviarse para ejecución en Alpaca. Conservan la semilla
  de comisión `00000000-0000-0000-0000-000000000701`, tasa `2.0000` y reparto
  `60.00`.
- No hay notificaciones de horario duplicadas por usuario y `change_id`.
- Los cambios de horario se despacharon con 0 órdenes afectadas. En Docker
  se registraron 5 destinatarios por cambio y en Supabase 20.

Permanecen intencionalmente los registros append-only: auditoría, historial de
tarifa cancelada, halt liberado, restricción levantada, asignaciones revocadas,
órdenes canceladas, reportes y notificaciones. También permanece el snapshot
KPI. **No se borraron para “limpiar” la evidencia.** Las notificaciones de
cambios OTC de prueba son visibles para los usuarios suscritos de Supabase.
Las tres ejecuciones sintéticas existen únicamente en la base Docker.

Referencias principales en Supabase:

| Recurso | Identificador |
|---|---|
| Tarifa futura cancelada | `9f983300-a1e7-44e5-86bc-951e14039416` |
| Orden cancelada | `6a4c5af7-10aa-4b6f-9f7d-15f48798ee54` |
| Halt liberado | `b566c83b-9c31-48c1-8af5-4840f290a805` |
| Restricción levantada | `5bf88b18-abf5-4a13-9b14-a67885c3fb4a` |
| Reporte conservado | `4f46c891-a30e-4d68-bbd8-a81de8e9f717` |

## Cómo repetir las consultas

No se recomienda repetir ciegamente los POST de los anexos: los UUID,
`expected_latest_version`, fechas futuras, claves de idempotencia y códigos
TOTP son específicos de esta ejecución. Consultar de nuevo el estado y usar
identificadores/códigos nuevos.

El contenedor creado para la revisión se conserva, con su base local; se
detiene al finalizar. Para iniciarlo otra vez:

```bash
docker start acciones-ud-mod07-review
```

Para cargar el archivo de configuración con uv, sin renombrarlo:

```bash
uv run --env-file env uvicorn acciones_ud.main:app
```

Ese comando usa **Supabase** según el archivo actual; para Docker se deben
sobrescribir explícitamente `DATABASE_URL` y `MIGRATION_DATABASE_URL` y usar
`APP_ENV=test`, ya que el PostgreSQL local no tiene TLS. En esta revisión se
usó una conexión a `127.0.0.1:55433/mod07_e2e`, usuario `mod07` y contraseña
**solo de la DB desechable** `mod07_disposable`.

El ejemplo de arranque anterior usa HTTP. Para reproducir autenticación desde
clientes que respeten estrictamente cookies `Secure`, utilizar HTTPS local
con `--ssl-keyfile`/`--ssl-certfile`, como en la revisión; no quitar `Secure`
de las cookies para facilitar la prueba.

La instalación de uv realizada para esta sesión está en
`/tmp/opencode/bin/uv` si `uv` todavía no está en el PATH del terminal.

## Cosas por corregir y límites

### Incidencias reproducidas

1. **Latencia elevada con Supabase — pendiente de investigar.** Aunque las
   solicitudes funcionaron, estas lecturas tardaron más de 2 segundos:

   | Lectura real | Docker local | Supabase |
   |---|---:|---:|
   | Matriz inicial | 10.02 ms | 4531.81 ms |
   | Vista consolidada de mercados | 9.02 ms | 3920.30 ms |
   | Comisiones administrativas | 8.69 ms | 3608.00 ms |
   | KPI servido desde caché | 6.01 ms | 2332.17 ms |
   | Primera página de auditoría | 8.27 ms | 2396.18 ms |

   Son muestras individuales con pocos datos, no un p95 con 5.000 usuarios.
   No demuestran que RNF-01 se cumpla. Investigar latencia de red/región,
   costo de transacciones y viajes a la DB, consultas y tamaño del pool antes
   de concluir una causa. No se aplicaron optimizaciones.
   Como dependencia adicional, la creación de la orden tardó 24888.13 ms y
   su preview 17283.20 ms contra Supabase/cuenta Alpaca sandbox.
2. **Despliegue de Supabase pendiente al inicio — resuelto con autorización.**
   Faltaban 0010–0012 y sus permisos/esquema. Se observaron 403/500 reales antes
   del despliegue. Incorporar la verificación de `alembic current` y migración
   previa al arranque en el procedimiento de despliegue.
3. **Configuración local no autodetectada.** El archivo `env` no coincide con
   el nombre `.env` que buscan `Settings`, `run_dev.py`, `run_migrations.py`
   y Compose. El arranque/pytest sin carga explícita puede fallar durante el
   import de la DB. Se solucionó solo para los procesos de revisión cargando
   el archivo; no se renombró ni cambió el código. Definir y documentar una
   única convención de carga.
4. **Advertencias de dependencias.** Revisar las deprecaciones de la suite,
   especialmente antes de subir a futuras versiones de Python/Starlette.

Los 401, 403, 404, 409, 422 y 503 solicitados como casos negativos en los anexos
son resultados esperados, no defectos. En particular, `TRADING_HALTED` debe
devolver 503 y una cuenta restringida debe devolver 403.

### Verificaciones aún pendientes / no demostradas por este E2E

- **Fill nuevo real en Supabase:** no se forzó una compra a mercado ni una
  ejecución pagada. La consistencia positiva de comisión/portfolio/KPI se
  comprobó con fixtures solo locales y con la suite; falta repetirla con un
  fill sandbox nuevo persistido en Supabase.
- **Propagación con órdenes afectadas:** los cambios OTC se eligieron sin
  órdenes pendientes afectables. Se probó auditoría/despacho/notificación
  reales, pero no se alteraron órdenes ajenas para demostrar RFP-10 en
  Supabase. La transición e idempotencia se cubren en la suite.
- **RNF-01/p95 con 5.000 usuarios:** las duraciones individuales de los anexos
  no son una prueba de carga ni certifican el objetivo de 2 segundos.
- **Fallos de red, proveedor y reinicios durante un despacho:** no se
  provocaron caídas de Supabase ni de Alpaca. Los casos de error, caché stale,
  rollback y reintentos de integración se cubren en pruebas automatizadas.
- **Jobs en producción y canales externos:** no se validó un despliegue con
  varias instancias ni entregas SMTP, Telegram o SMS. Sí se leyó in_app.
- **Inmutabilidad frente al dueño del esquema:** los triggers no impiden
  que un owner/superusuario los desactive. Sigue pendiente el rol de aplicación
  de menor privilegio y, si se exige, anclaje externo de evidencia (H9).
- **Calendario y retención:** permanecen las decisiones abiertas de
  intersección del horario interno con Alpaca y política de retención (H12/H15).

No convertir estos límites en una afirmación de “todo el sistema está
certificado”: el resultado corresponde a los flujos y datos descritos.
