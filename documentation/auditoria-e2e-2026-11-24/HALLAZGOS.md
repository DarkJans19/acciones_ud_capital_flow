# Hallazgos y reproducción

Fecha: 2026-11-24. Código base: `5e895751ccd8fe7a3e8f00ce8076c35ad100f8c2`.
No se modificó `src/` ni se aplicaron correcciones para ocultar resultados.

**Lectura de severidad:** es una priorización contextual, no una certificación
CVSS del sistema. Separar siempre defecto reproducido, dependencia afectada,
riesgo aceptado y recomendación de endurecimiento.

## AUD-01 — CORS bloquea la edición de perfil

- **Tipo / severidad:** defecto funcional confirmado / media.
- **Contrato:** RF-06, RFP-01; requisitos 17.4 y 26 de identidad.
- **Ruta:** `PATCH /api/v1/users/me`.
- **Causa:** `src/acciones_ud/main.py:77-83` permite GET/POST/PUT/DELETE/OPTIONS,
  pero no PATCH. El router sí implementa PATCH.
- **Reproducción:** enviar OPTIONS a esa ruta, Origin igual al frontend permitido,
  `Access-Control-Request-Method: PATCH` y
  `Access-Control-Request-Headers: content-type`.
- **Esperado:** preflight 200 y PATCH autorizado por CORS.
- **Observado:** **400**, cuerpo `Disallowed CORS method`.
- **Impacto:** Swagger/cliente servidor puede editar; el frontend en otro origen
  no puede hacerlo. Es un caso de “API funciona manualmente, navegador no”.
- **Prueba:** `test_profile_patch_preflight_is_allowed`.
- **Corrección propuesta:** incluir PATCH y probar preflights de todos los métodos
  efectivamente publicados; mantener la restricción de orígenes.

## AUD-02 — Login no valida email ni contraseña vacíos según el spec

- **Tipo / severidad:** incumplimiento de validación confirmado / baja, combinado
  con AUD-06 aumenta el coste de peticiones no válidas.
- **Contrato:** RF-02, requisito **3.11**: rechazar email inválido o >254
  caracteres y contraseña vacía con 422 **sin verificar credenciales**.
- **Ruta:** `POST /api/v1/auth/login`.
- **Causa:** `identity/adapters/inbound/http/schemas/auth.py:88-90` declara email
  como `str` sin formato/longitud y password solo con máximo 128.
- **Cuatro entradas:** email `""`; email `not-an-email`; email compuesto por 255
  letras `a` más `@example.com`; email válido con password `""`.
- **Esperado:** 422, cero llamadas al servicio de autenticación.
- **Observado:** **401 INVALID_CREDENTIALS**; el espía registra **una llamada**
  por entrada. El comportamiento 401 también se observó con PostgreSQL real.
- **Impacto:** contrato incoherente para UI, consultas/auditoría y potencial
  verificación Argon2 innecesarias. No se demostró enumeración de cuentas.
- **Prueba:** cuatro variantes de
  `test_invalid_login_never_reaches_credential_verification`.
- **Corrección propuesta:** límites y validadores equivalentes a los de registro,
  aplicados antes del servicio; comprobar también ausencia de consultas y hashes.

## AUD-03 — Decimales extremos causan errores internos en comisiones

- **Tipo / severidad:** defecto de robustez confirmado / media.
- **Contrato:** MOD-07 RF-43; error de entrada debe ser explícito.
- **Ruta:** `GET /api/v1/commissions/quote`.
- **Requisito de ataque:** sesión de inversor o broker.
- **Requests mínimos:** `symbol=AAPL&side=buy&qty=1e100&price=1`;
  `qty=1&price=1e100`; `qty=1e999999&price=1`.
- **Esperado:** 422 por tamaño/precisión fuera del dominio financiero.
- **Observado aislado:** los tres devuelven **500 INTERNAL_ERROR**.
- **Observado HTTPS real:** `qty=1e100` devolvió 500, request ID
  `13f8bc6e-cdb0-4dc5-abd0-2620730aba1c`. La siguiente petición del barrido tuvo
  `RemoteProtocolError`, no un estado HTTP: **no se cuenta como otro 500 ni se
  afirma que haya caído todo el servidor**. Se hizo una repetición dirigida
  con cierre explícito de conexión; ver `live-followup.json`.
- **Causa:** `admin/adapters/inbound/http/commissions_router.py:30-38` acepta
  Decimal positivo sin máximo de dígitos/exponente.
  `admin/domain/commissions.py:35-48` usa precisión 60 y cuantiza a centavos;
  cantidades aceptadas por el contrato desbordan ese cálculo.
- **Impacto:** 500 inducible por usuario autenticado, ruido operacional y posible
  abuso de recursos. No se ejecutó carga ni se probó denegación global de servicio.
- **Prueba:** tres variantes de `test_extreme_commission_input_is_a_client_error`.
- **Corrección propuesta:** máximo monetario, `max_digits`, precisión fraccionaria
  y longitud/exponente coherentes antes del cálculo; traducir errores decimales.
  No basta con capturar la excepción y devolver una comisión truncada.

## AUD-04 — Mensajes WebSocket no-objeto o JSON roto no tienen manejo controlado

- **Tipo / severidad:** defecto de protocolo confirmado / baja-media.
- **Ruta:** `/ws/v1/market-feed`, con streaming habilitado y usuario autorizado.
- **Frames probados, uno por conexión:** `[]`, `null`, `1`, `"text"` y `{`.
- **Esperado:** mensaje de error o cierre controlado 1003/1007/1008; limpieza de
  suscripciones, sin excepción de aplicación.
- **Observado:** cuatro `AttributeError` al usar `.get` sobre algo que no es dict;
  un `JSONDecodeError` para `{`. La limpieza se intenta en `finally`, pero el
  error escapa del bucle y no hay respuesta de protocolo.
- **Causa:** `market_data/adapters/inbound/http/routers/stream.py:40-42,61-64`
  asume objeto JSON y solo captura `WebSocketDisconnect`.
- **Alcance de evidencia:** TestClient + hub real + upstream/autenticación
  controlados. No se habilitó streaming contra el proveedor compartido ni se
  verificó el código exacto que observaría un navegador tras el error de Uvicorn.
- **Impacto:** conexión terminada inesperadamente, reintentos y registros de
  error evitables. No demuestra por sí solo caída de otras conexiones.
- **Prueba:** cinco variantes de
  `test_websocket_invalid_frame_is_handled_without_uncaught_exception`.
- **Corrección propuesta:** validar tipo/tamaño/esquema del mensaje, manejar JSON
  inválido y frame binario y definir cierres; conservar la suscripción previa
  cuando se rechace un cambio.

## AUD-05 — El WebSocket no vuelve a comprobar la sesión tras el handshake

- **Tipo / severidad:** control de sesión incompleto / media.
- **Contrato afectado:** RF-02/03/25; revocación y autorización continua.
- **Causa:** `stream.py:22-29` autentica una vez. `stream.py:40-60` y
  `market_data/application/stream_hub.py:41-59` no revalidan sesión, expiración
  del JWT, rol ni permiso al suscribirse o entregar precios.
- **Reproducción controlada:** abrir socket autenticado; cambiar el verificador
  a “sesión revocada”; enviar `subscribe` para AAPL.
- **Esperado de seguridad:** cierre 1008 o denegación de la nueva suscripción.
- **Observado:** `{"type":"subscribed","symbols":["AAPL"]}`; el verificador no se
  consulta otra vez.
- **Alcance:** prueba de componente con verificador controlado + inspección del
  bucle. No se realizó logout simultáneo sobre un socket real de Supabase.
  La revocación HTTP sí se verificó con cuentas reales y funciona.
- **Impacto:** una conexión ya abierta puede sobrevivir al logout/expiración o a
  retirar permisos. Aquí el recurso observado son precios, no retiros ni órdenes.
- **Prueba:** `test_websocket_revoked_session_cannot_resubscribe`.
- **Corrección propuesta:** política explícita de caducidad del socket,
  revalidación periódica/en cambio de suscripción e invalidación por sesión.
  Evitar una consulta SQL por cada tick; usar un mecanismo acotado.

## AUD-06 — Sin presupuesto de intentos de contraseña en la aplicación

- **Tipo / severidad:** control preventivo ausente / media, prioridad alta por
  tratarse de autenticación financiera.
- **Ruta:** `POST /api/v1/auth/login`.
- **Evidencia aislada:** 30 intentos consecutivos al mismo email/IP llegan al
  servicio; todos 401, ninguno 429. El servicio se sustituye por un espía para no
  hacer fuerza bruta ni hashing masivo en el test.
- **Corroboración:** no se encontró middleware/servicio de limitación para login
  en el código. La prueba HTTPS dirigida usa únicamente un email sintético
  inexistente y 30 intentos acotados; resultado en `live-followup.json`.
- **Distinción importante:** sí hay máximo de **cinco fallos por MFA_Challenge**.
  Eso no limita intentos de contraseña ni desafíos nuevos si se conoce la clave.
  No se afirma que se haya saltado MFA.
- **Impacto:** password spraying, generación excesiva de desafíos/auditoría y
  coste de Argon2. No se verificó un WAF/rate limiter externo al backend.
- **Prueba:** `test_login_has_a_bounded_attempt_budget`.
- **Corrección propuesta:** límites por IP y cuenta con almacenamiento compartido,
  backoff y 429/Retry-After; evitar bloquear cuentas a voluntad de un tercero.
  Definir el umbral como requisito: 30 es el presupuesto de esta prueba, no una
  cifra actualmente aprobada por el negocio.

## AUD-07 — aiosmtplib instalado y fijado en una versión con avisos conocidos

- **Tipo:** dependencia afectada confirmada por OSV; explotación de esta
  aplicación **no demostrada**.
- **Versión:** `aiosmtplib==4.0.2` en entorno y `uv.lock:74-75`.
  `pyproject.toml:8` exige `<5.0`, por lo que actualizar solo el lock no alcanza.
- **Avisos distintos, sin duplicar aliases PYSEC:**
  - [CVE-2026-53533 / GHSA-v3q9-hj7j-63hq](https://osv.dev/vulnerability/GHSA-v3q9-hj7j-63hq):
    inyección SMTP por CR/LF en remitente/destinatario; corregido en **5.1.1**.
  - [CVE-2026-55558 / GHSA-vxj7-4xrp-5vr4](https://osv.dev/vulnerability/GHSA-vxj7-4xrp-5vr4):
    inyección de respuesta STARTTLS; corregido en **5.1.2**.
- **Contexto:** `market_data/adapters/outbound/senders/smtp.py:35-49` usa la
  dependencia. SMTP no estaba configurado en el entorno auditado; se usa
  `EmailMessage`, que también valida encabezados. No se demostró que un usuario
  pueda inyectar CR/LF hasta el transporte ni se atacó servidor de correo.
- **Prioridad:** alta antes de habilitar SMTP; riesgo actual condicionado.
- **Acción propuesta:** revisar compatibilidad, permitir al menos 5.1.2, regenerar
  lock y probar TLS, validación de direcciones y entregas.

## AUD-08 — pytest de desarrollo afectado por manejo vulnerable de temporales

- **Tipo:** dependencia de desarrollo; no endpoint remoto vulnerable.
- **Versión:** `pytest==8.4.2`, fijado además a `<9.0` en `pyproject.toml:31`.
- **Aviso:** [CVE-2025-71176 / GHSA-6w46-j5rx-g56g](https://osv.dev/vulnerability/GHSA-6w46-j5rx-g56g),
  corregido en **9.0.3**. Requiere contexto local/temporales manipulables.
- **Impacto:** entorno de desarrolladores/CI compartido, no runtime Docker,
  cuyo build instala `--no-dev`. No se ejecutó explotación local.
- **Acción propuesta:** revisar pytest-asyncio y compatibilidad antes de subir a
  9.0.3+; aislar usuarios y directorios temporales de CI.
- **Evidencia AUD-07/08:** `dependencies-osv.json`: 57 distribuciones consultadas,
  seis registros devueltos que representan **tres CVE distintos**, no seis fallos.

## Riesgos de diseño y endurecimiento, no fallos del contrato actual

### RD-01 — D4: sin CSRF ni validación Origin/Referer

El spec de identidad lo excluye expresamente. SameSite Lax/Strict reduce ataques
cross-site, pero **same-site no significa same-origin**: un subdominio comprometido
de la misma organización puede quedar dentro del mismo sitio. CORS limita lectura
en navegadores, no es un control general para impedir mutaciones ni valida Origin
de WebSocket. No se demostró una explotación CSRF en un navegador real.

Revisar D4 antes de producción: orígenes confiables en HTTP y WebSocket, protección
de métodos de estado y CSRF/Fetch Metadata, preservando los webhooks firmados.

### RD-02 — Regeneración de recovery codes sin step-up

`POST /api/v1/users/me/mfa/recovery-codes` requiere solo sesión;
`identity/application/login.py:156-163` genera y entrega diez códigos nuevos.
**Cumple el requisito 18.7** y las pruebas de atomicidad pasan. Una sesión robada
puede invalidar el juego anterior y obtener otro. Esto no basta, por sí solo,
para iniciar sesión sin contraseña. Solicitar contraseña/TOTP reciente sería
endurecimiento y cambio de requisito, no corrección silenciosa.

### RD-03 — Política de caché explícita para respuestas sensibles

Revisar `Cache-Control: no-store` en login/enrollment/MFA/recovery y perfil.
La ausencia de cabecera se comprueba en el follow-up de `/users/me`; no se ha
demostrado que un proxy esté guardando o filtrando esos datos. No confundir
ausencia de política defensiva con fuga ya explotada.

### RD-04 — Documentación de alcance desactualizada

`AGENTS.md` y README anuncian solo identity/market_data; el ejecutable registra
siete módulos y existen seis specs de módulos. README contiene mojibake. Esto
no prueba una vulnerabilidad, pero facilita dejar áreas nuevas sin revisar y
ejecutar procedimientos de despliegue con expectativas equivocadas.

### RD-05 — PostgreSQL de tests publica el puerto en todas las interfaces

`tests/db/docker-compose.yml:9-10` publica `55432:5432` con credenciales de ejemplo.
Se observó `0.0.0.0:55432` y `[::]:55432` al levantarlo. Es infraestructura
desechable de desarrollo, **no evidencia de exposición de Supabase ni de la base
de producción**; su accesibilidad remota también depende de firewall/red.
En una estación o runner conectado a una LAN puede exponer la base de pruebas.
Recomendación: `127.0.0.1:55432:5432`, o red Docker sin puerto publicado cuando
tests y base estén en la misma red. Se retiró el contenedor al terminar la auditoría.

### RD-06 — El logger de Uvicorn sigue emitiendo tracebacks completos

Los dos 500 reales registraron `decimal.InvalidOperation` con traceback completo
en `uvicorn.error`, además del mensaje sanitizado de la aplicación.
`shared/infrastructure/logging.py:47-66` añade redacción a su propio handler,
pero no a los handlers separados que instala Uvicorn. **No se observaron secretos
en estos tracebacks**; sí se confirma que la política de “no emitir objetos de
excepción” de ese filtro no cubre toda la salida del servidor. Revisar handlers
de servidor/hosting y probar con excepciones sintéticas que contengan valores
marcadores antes de afirmar que todos los logs están sanitizados.

## Observaciones de flujo que NO se clasifican como vulnerabilidad

- Registro broker produce un usuario inicialmente pendiente; al activarse tiene
  también rol investor. Por ello acceder a billetera puede dar 409 por falta de
  KYC, no 403. Se confirmó en el flujo integrado y se corrigió la expectativa del
  test, **no el producto**.
- El catálogo debe estar cargado antes de cotizar un símbolo nuevo. El primer
  borrador del fixture recibió 404 porque no lo había sembrado. Fue un problema
  del montaje, no un fallo funcional reportado.
- El barrido genérico envió `start=NASDAQ&end=NASDAQ` a candles por inferir
  parámetros string sin formato. Sus cinco 422 son validaciones correctas; el
  follow-up repite con fechas ISO válidas.
- Los UUID ficticios de órdenes/propuestas/reportes producen 404; no equivalen a
  fallos de esos flujos ni prueban BOLA. Para BOLA se usaron recursos reales de
  otro propietario en PostgreSQL aislado.
