# Auditoría E2E, seguridad y casos extremos de Acciones UD

**Fecha:** 24 de noviembre de 2026.  
**Código auditado:** `5e895751ccd8fe7a3e8f00ce8076c35ad100f8c2`.  
**Resultado:** se encontraron defectos reproducibles; **no aprobaría una salida a
producción sin resolver y volver a probar las prioridades indicadas abajo**.
No se modificó código de negocio para corregirlos: esta entrega es una auditoría.

## 1. Resultado ejecutivo

| Comprobación | Resultado |
| --- | --- |
| Suite original sin PostgreSQL | 774 pasan, **47 omitidas**: no validaba persistencia |
| Suite original con PostgreSQL 16 desechable | **821 pasan**, ninguna omitida |
| Suite final con pruebas nuevas | **845 pasan + 15 fallos conocidos**, 860 casos |
| Regresiones sin ocultar fallos (`--runxfail`) | **15 fallan**, agrupadas en AUD-01..06 |
| Inventario | **164 operaciones HTTP, 141 rutas**, más un WebSocket |
| Denegaciones de autenticación | **308/308 correctas**: 154 operaciones × sin cookie/JWT inválido |
| HTTPS real, cinco cuentas y proveedores reales | **674 solicitudes**: 635 del barrido + 39 dirigidas |
| Recorrido integrado con PostgreSQL real | **79 solicitudes, cero resultados inesperados**, siete módulos |
| Ruff / mypy | Pasan; mypy revisa 396 archivos de `src` |
| Dependencias consultadas en OSV | 57 distribuciones; **3 CVE distintos**, dos paquetes afectados |
| Búsqueda heurística de secretos versionados actuales | Sin coincidencias; `.env` no está versionado |

**Importante:** `xfail` significa “defecto abierto reproducible”, **no aprobado**.
Se usa `strict=True`: una corrección que haga pasar la prueba obliga a retirar la
marca. La corrida explícita `--runxfail` quedó registrada con los 15 fallos.
No son 15 vulnerabilidades distintas: varias entradas reproducen la misma causa.

### Prioridades

1. **Antes de exposición pública:** definir y aplicar límites de autenticación
   (AUD-06), y revisar las dependencias afectadas (AUD-07/08).
2. **Antes de integrar perfil/comisiones:** corregir CORS PATCH y los decimales
   fuera de dominio (AUD-01/03).
3. **Antes de habilitar streaming:** manejo de frames y política de revocación/
   caducidad del WebSocket (AUD-04/05).
4. Alinear validación de login con requisito 3.11 (AUD-02).
5. Revisar riesgos aceptados CSRF/Origin y step-up de recovery codes. Requieren
   decisión explícita, no cambios silenciosos al spec.

Detalle, requests mínimos, causa, severidad, límites de la evidencia y propuesta
de corrección: **[HALLAZGOS.md](HALLAZGOS.md)**.

## 2. Qué se ejecutó y qué era real

### A. Suite existente y pruebas de propiedades

Se ejecutó la suite completa, no solo los tests de la funcionalidad más reciente.
Primero se observó que 47 pruebas se omiten sin `TEST_DATABASE_URL`; después se
habilitaron con PostgreSQL 16 en Docker, puerto 55432, sin volumen persistente.
Se probaron migraciones hasta `0012_admin_compliance_bi` y sus downgrades,
constraints, repositorios y carreras de concurrencia.

Cada test de propiedades puede generar muchas entradas; **821 tests no significa
821 requests HTTP**. Las pruebas unitarias/de propiedades suelen tener dobles de
puertos. No se etiquetan todas como E2E reales solo por haber ejecutado pytest.

### B. Barrido HTTPS real contra la configuración de `.env`

- Uvicorn local exclusivo en `https://127.0.0.1:8459`; certificado local de prueba
  validado por el cliente como CA, sin desactivar TLS verification.
- Base administrada y adaptadores reales de la aplicación; sin overrides de
  dependencias. APIs de proveedores configuradas en sandbox.
- Cinco cuentas suministradas: admin, admin2, broker, investor y broker2.
  Las cinco completaron password + TOTP, sin usar códigos de recuperación.
- Una petición anónima a cada una de las 164 operaciones.
- Las **87 operaciones GET** se probaron con las cinco cuentas: 435 requests.
  Los POST/PUT/PATCH/DELETE protegidos se comprobaron anónimos, no se ejecutaron
  todas sus mutaciones válidas sobre datos compartidos.
- Se probaron previews de órdenes sin crear órdenes, formatos inválidos de
  login, entradas numéricas, candles válidas, búsquedas tipo SQL y preflight.
- Presupuesto máximo de concurrencia del barrido: tres peticiones.
- Seguimiento: 30 intentos acotados sobre un **email sintético inexistente**,
  no fuerza bruta sobre las cuentas compartidas.
- Se cerraron las cinco sesiones del barrido y la sesión del seguimiento.
  Las cinco comprobaciones HTTP después del logout dieron 401.

**Efectos laterales delimitados:** no se migró ni borró Supabase; no se crearon
órdenes, transferencias, enlaces, tarifas, restricciones ni suscripciones allí.
Login/logout sí crean/revocan sesiones y dejan auditoría. Algunos GET del producto
pueden actualizar cachés, snapshots, estado KYC o KPI; “lectura” no significa
ausencia absoluta de escrituras internas.

**Estados del barrido de 635:** 198×200, 16×422, 164×401, 6×204, 1×400,
23×404, 225×403, **1×500 y 1 error de transporte**. No se cuentan todos los 4xx
como defectos. El seguimiento confirmó otro 500 para otra entrada extrema,
PATCH preflight 400, candles válidas 200 y **30×401, cero 429**.

`live-http.json` contiene estado/código/Request-ID y forma de respuesta, no cuerpos
de éxito ni cookies/contraseñas. Sus tiempos incluyen espera en la cola del
semáforo: **no son un benchmark de latencia del servidor**. Los tiempos del
seguimiento son secuenciales y no incluyen esa cola.

### C. Recorrido integrado aislado, con autenticación y SQL reales

`tests/security/test_cross_module_journey.py` monta la aplicación completa y una
base desechable migrada. **No sustituye `get_current_user`**: registro, Argon2,
MFA, cifrado TOTP, JWT, cookies, roles, aplicación y repositorios SQL son reales.
Alpaca/Stripe son dobles explícitos; no se envía dinero ni órdenes al exterior.
Se prepara un administrador sintético y catálogo por SQL como prerrequisitos.

Secuencia ejecutada:

1. Crear inversor, otro inversor, broker, auditor y analista; enrolar MFA y entrar
   con cookies; administrador sintético autenticado por el mismo flujo.
2. Asignar auditor/analyst y activar broker mediante endpoints administrativos.
   Un broker pendiente no accede a billetera.
3. Abrir KYC y consultar billetera del inversor. KYC de proveedor es simulado.
4. Rechazar watchlists sin premium; crear checkout; rechazar webhook sin firma;
   aplicar webhook HMAC correcto **dos veces** y desbloquear premium una sola vez.
5. Buscar/cotizar el instrumento, crear watchlist, añadir símbolo y rechazar
   duplicado.
6. Crear banco; el otro propietario recibe 404 al consultarlo.
7. Depositar; repetir la misma clave/cuerpo devuelve el mismo ID. Cambiar monto
   con la misma clave da 409. Otro propietario no puede leer la transferencia.
8. Consultar tarifa y comisión del 2 %, previsualizar y crear orden. Repetir
   idempotencia devuelve la misma orden y conserva `fee_version_id`.
   Otro inversor recibe 404 al consultar la orden.
9. Consultar posiciones y generar reporte de portafolio; otro dueño recibe 404.
10. Solicitar enlace broker; otro inversor no lo puede cerrar; broker acepta,
    crea propuesta y un tercero no la puede leer. El inversor la rechaza y cierra
    el enlace; el broker deja de consultar sus órdenes.
11. Auditor lee audit trail pero no KPI; analyst lee KPI pero no audit trail.
    Ambos tienen denegadas las mutaciones de trading halt.
12. Logout de todos; cada `/users/me` posterior devuelve 401.

Transcripción de **las 79 peticiones**:
**[RECORRIDO.md](RECORRIDO.md)** / `cross-module-journey.json`.
La aprobación de propuestas que crea órdenes `BROKER_SIGNED` también pasó en la
suite PostgreSQL existente de brokers, para market y limit. No se confunde esa
prueba, que usa dobles de autenticación/proveedores, con el recorrido anterior.

### D. Matriz administrativa determinista

`tests/security/test_admin_matrix.py` complementa el muestreo de Hypothesis:
prueba cada entrada de `ROUTES` con administrator/auditor/analyst/investor/broker,
y sesión válida, ausente, inactiva o sin permisos.

El servicio es un espía que responde 418 cuando se le permite llegar. **418 es
un centinela del test, no una respuesta funcional del producto**. Se comprueba que
las denegaciones 401/403 no lleguen al servicio. La matriz distingue rol de
permiso, no basta con conceder un permiso amplio a un rol de solo lectura.
Son **25 operaciones × 5 roles × 4 estados = 500 requests deterministas**,
además del muestreo existente.

### E. Revisión de seguridad de código y dependencias

- Autenticación JWT fijada a HS256, caducidad, sesiones revocadas, cookies
  HttpOnly/Secure, rotación de refresh y reuso de TOTP/recovery.
- Comprobaciones de ownership, privilegios y roles efectivos con vigencia.
- Contratos HTTP y WebSocket, entradas inesperadas y números fuera de dominio.
- SQL parametrizado, escaping de LIKE, fallos externos, tratamiento de secretos
  y errores. Las búsquedas reales `q=' OR 1=1 --` se trataron como literales:
  instrumentos devolvió total 0 y brokers devolvió 200. Dos payloads no
  constituyen una prueba exhaustiva de ausencia de SQLi.
- OSV `querybatch` para versiones instaladas, y consulta de los seis advisories;
  se deduplicaron sus aliases a tres CVE. Versiones afectadas coinciden con lock.
- Búsqueda heurística en archivos versionados actuales de claves privadas,
  secretos Stripe/GitHub y literales TOTP; sin imprimir valores.
  **No** se auditó todo el historial de Git ni se certifica ausencia de secretos.

## 3. Qué pasó en los casos extremos

| Área | Casos comprobados | Resultado |
| --- | --- | --- |
| MFA | Reuso TOTP, desafío caducado/desconocido, máximo cinco fallos, carrera de recovery/regeneración | Pasan en suite original, incluida concurrencia SQL |
| Refresh/logout | Rotación/reuso concurrente, revocación ajena, revocar otras sesiones | Pasan; logout HTTP real validado |
| RBAC | Último administrador concurrente, vigencias futuras, cancelación, roles de solo lectura | Pasan |
| Registro/perfil/KYC | Escalada mediante campos extra, menor de edad, consentimientos, reserva concurrente, fallback proveedor | Pasan; **CORS PATCH falla** |
| Login | Email vacío/inválido/largo y password vacío; intentos repetidos | **Falla validación y no hay throttle observado** |
| Mercado | Búsqueda, calendarios/timezones, fallback de cotización, snapshots stale, alertas y límites premium | Suite pasa; lecturas reales comprobadas |
| WebSocket | Suscripciones inválidas conservan anterior, desconocidas, streaming apagado | Pasan; **frames malformados y revalidación fallan** |
| Órdenes | Cero, negativo, NaN, precisión >9 decimales, precios/tipos/bracket, cierres de mercado | Rechazo correcto en casos comprobados |
| Órdenes | Idempotencia, reservas simultáneas, fill duplicado, timeout ambiguo, cancelación diferida, revalidación al enviar | Suite pasa, incluida reserva SQL |
| Comisiones | NaN, cero, negativo | 422 correcto |
| Comisiones | `1e100`, precio `1e100`, `1e999999` | **500 inducible** |
| Wallet/Stripe | Firmas inválidas, replays, eventos fuera de orden, facturas modernas, idempotencia cuerpo diferente | Pasan en suite y recorrido aislado |
| Portafolio | Sin KYC, discrepancias, redondeo, pérdida/ganancia, periodos, reporte ajeno, proveedor 429 | Pasan |
| Broker | Enlace ajeno, versiones, propuesta ajena, aprobación/rechazo, cierre y cascada | Pasan en alcance ejercitado |
| Administración | Tarifas inmutables, halts, restricciones, trazabilidad append-only, KPI cache | Suite pasa; lectura real y roles verificados |

## 4. Cobertura por módulo de la suite final

| Carpeta | Pasan | Fallos conocidos |
| --- | ---: | ---: |
| identity | 292 | 0 en suite previa |
| market_data | 97 | 0 en suite previa |
| orders | 111 | 0 |
| wallet | 67 | 0 |
| portfolio | 63 | 0 |
| brokers | 97 | 0 |
| admin | 52 | 0 |
| migrations | 9 | 0 |
| shared + unit/health | 33 | 0 |
| security — nuevas pruebas transversales | 24 | **15** |
| **Total** | **845** | **15** |

Los fallos transversales de identidad/mercado/admin se cuentan en `security`,
no duplicados en sus módulos. Lista de nombres y resultados individuales:
`test-results.json`. La corrida final tuvo 2966 warnings, principalmente
deprecaciones de asyncio en Python 3.14, TestClient y configuración de Alembic;
no se transformaron en vulnerabilidades ni se ocultó su número.

## 5. Límites y pendientes explícitos

- No existe frontend en este repositorio: **no hay recorrido de navegador/UI**,
  captura visual ni validación de cómo renderiza HTML el cliente. CORS se probó
  a nivel de preflight, no con Playwright.
- No es posible “probar todos los casos” de entrada. Se cubrieron todos los
  endpoints en rechazo anónimo y todas las lecturas con cinco cuentas, pero no
  todas las mutaciones positivas/estados/combinaciones.
- WebSocket adversarial usa autenticación/hub controlados. No se realizó
  streaming real ni logout simultáneo sobre conexión real de Supabase.
- No se hicieron cargas, explotación masiva, ataques a infraestructura externa,
  auditoría de red Supabase/RLS del despliegue ni escaneo de la imagen/SO.
- No se activaron SMTP/Telegram ni pagos/transferencias reales. Las CVE se
  identifican por versión/advisory, no por explotación de esos proveedores.
- Se deshabilitaron los jobs en el servidor compartido de auditoría para no
  conciliar órdenes ni disparar notificaciones ajenas. Schedulers/reconciliadores
  se probaron en suite con dependencias aisladas y PostgreSQL donde aplica.
- El entorno local es Python **3.14.4**, aunque Docker declara **3.12**.
  Queda pendiente repetir en esa imagen y en la topología exacta de producción.
- Los cinco logins suministrados no incluyen auditor/analyst dedicados;
  esos perfiles se crearon **solo en la base desechable**, con roles reales.
- No se demuestra ninguna toma de cuentas ni extracción masiva de datos.
  Tampoco se certifica que no existan otras vulnerabilidades.

## 6. Reproducción

Usar una base **desechable**. El fixture hace `downgrade base` y borra su esquema.
**Jamás copiar una URL de Supabase/producción a `TEST_DATABASE_URL`.**

```bash
docker compose -p acciones-audit -f tests/db/docker-compose.yml up -d --build
export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:55432/postgres
export AUDIT_JOURNEY_EVIDENCE=documentation/auditoria-e2e-2026-11-24/cross-module-journey.json
uv run --no-sync ruff check .
uv run --no-sync mypy src
uv run --no-sync pytest --disable-warnings --tb=short --junitxml=/tmp/opencode/audit-final.xml

# Estos quince deben FALLAR hasta que se corrijan los hallazgos.
uv run --no-sync pytest tests/security/test_known_findings.py --runxfail -q
```

Al comenzar `uv` no estaba en PATH: se usó el entorno `.venv` existente para las
primeras corridas. Para validación final se instaló uv 0.13.9 temporalmente en
`/tmp/opencode/tools`, sin modificar dependencias ni lock. `--no-sync` conserva
exactamente el entorno auditado; para una reproducción limpia usar primero
`uv sync --locked` y comprobar versiones/Python.

Para repetir HTTPS, levantar un servidor **dedicado loopback** con certificado
local que incluya SAN `127.0.0.1`, las variables normales de `.env` y:

```bash
export ALERT_ENGINE_ENABLED=false PRICE_STREAMING_ENABLED=false
export KYC_STATUS_REFRESH_ENABLED=false WALLET_RECONCILER_ENABLED=false
export ORDERS_JOBS_ENABLED=false PORTFOLIO_JOBS_ENABLED=false
export BROKERS_JOBS_ENABLED=false ADMIN_JOBS_ENABLED=false
uv run uvicorn acciones_ud.main:app --host 127.0.0.1 --port 8459 \
  --ssl-keyfile /ruta/privada/audit.key --ssl-certfile /ruta/privada/audit.crt \
  --no-access-log
```

Preparar fuera del repositorio un JSON privado `chmod 600`, con claves `admin`,
`admin2`, `broker`, `investor`, `broker2`; cada objeto tiene `email`, `password`,
`totp_secret`. **No incluir recovery codes ni versionar el archivo.**

```bash
uv run python documentation/auditoria-e2e-2026-11-24/probe_live.py \
  --ca /ruta/privada/audit.crt --accounts-file /ruta/privada/cuentas.json \
  --output /tmp/opencode/nueva-evidencia-live.json
uv run python documentation/auditoria-e2e-2026-11-24/probe_followup.py \
  --ca /ruta/privada/audit.crt --accounts-file /ruta/privada/cuentas.json \
  --output /tmp/opencode/nueva-evidencia-dirigida.json
```

No ejecutar ambos scripts simultáneamente: el reuso de TOTP en el mismo paso
temporal se rechaza correctamente. No automatizar reintentos con recovery codes.

## 7. Archivos entregados

- [HALLAZGOS.md](HALLAZGOS.md): fallos y riesgos, cómo reproducir y corregir.
- [ENDPOINTS.md](ENDPOINTS.md): matriz de las 164 operaciones, estados por cuenta.
- [RECORRIDO.md](RECORRIDO.md): las 79 solicitudes del flujo integrado.
- `attack-surface.json`: inventario y 308 rechazos de autenticación.
- `live-http.json` / `live-followup.json`: 674 solicitudes reales sanitizadas.
- `cross-module-journey.json`: expected/actual de cada paso aislado.
- `test-results.json`: corridas, estadísticas y nombres individuales.
- `dependencies-osv.json`: avisos y referencias originales, deduplicables.
- `secret-scan.json`: alcance y resultado de búsqueda heurística.
- `cleanup.json`: servidor detenido, contenedor retirado y credenciales/TLS
  temporales eliminados; quedan los eventos de autenticación y cachés legítimos.
- `probe_live.py`, `probe_followup.py`: reproducción HTTP acotada y sin secretos.
- `build_evidence.py`: reconstruye tablas Markdown desde JSON.
- `tests/security/`: 39 pruebas nuevas, incluidas regresiones estrictas abiertas.
- `.kiro/specs/identity-market-backend/security-audit-2026-11-24.md`:
  trazabilidad a specs y decisiones no modificadas.

Los recursos temporales de ejecución se retiraron al finalizar. Las evidencias
sanitizadas y la herramienta uv temporal no son credenciales.

**Seguridad de las credenciales entregadas:** contraseña, secretos TOTP y códigos
de recuperación ya fueron compartidos en el contexto de esta solicitud. Deben
considerarse exclusivos de sandbox; rotarlos antes de cualquier uso fuera de
pruebas. No se copiaron a los informes ni a archivos del repositorio.
