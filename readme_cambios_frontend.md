# Cambios del backend que afectan al frontend — módulo Identity

Alcance: PR #1 (`feat/identity-admin-gaps`), mergeado en `main` como `16ed495`.
Cubre las brechas de `readme_agregar.md` (tareas 22-30) más el cambio de logout.

Todo está bajo el prefijo `/api/v1`. El contrato completo y actualizado está en
`/openapi.json` y `/docs`.

## Corrección de integración — 2026-11-24

Esta sección complementa el alcance histórico del documento. Detalles y
decisiones: `.kiro/specs/identity-market-backend/design.md`, sección
«Frontend integration correction».

### KYC

`POST /api/v1/kyc/account` mantiene su estructura y su respuesta 201
`{"alpaca_account_id":"…","status":"SUBMITTED"}`. Ahora rechaza localmente con
422 `VALIDATION_ERROR` fechas futuras, menores de 18 años cumplidos y documentos
inválidos, sin reservar ni llamar a Alpaca. Se usa la fecha UTC del servidor;
para nacidos el 29 de febrero, el aniversario no bisiesto es el 1 de marzo.

Tipos locales: `USA_SSN`, `USA_ITIN`, `COL_NIT`, `PASSPORT`, `NATIONAL_ID`,
`PERMANENT_RESIDENT`, `DRIVER_LICENSE`, `OTHER_GOV_ID`.
Las reglas comunes verificadas de Alpaca exigen 2–40 caracteres ASCII de
letras/dígitos/`-`/`.`/`+`, al menos un dígito y ausencia de placeholders.
No se reescribe el número. No son reglas de longitud propias de cada pasaporte.

Por ejemplo, dentro del body KYC completo existente:

```json
{
  "given_name": "Ana",
  "family_name": "Perez",
  "date_of_birth": "1990-01-31",
  "tax_id": "Ab829461",
  "tax_id_type": "PASSPORT",
  "country_of_citizenship": "COL",
  "country_of_tax_residence": "COL"
}
```

Este fragmento corresponde a `identity` y **omite** los campos financieros,
contacto, acuerdos y disclosures requeridos. Un pasaporte numérico como
`842617395` también supera la validación local. `COL_NIT` acepta base numérica
y DV opcional, por ejemplo `900.123.456-7`, solo con residencia fiscal `COL`;
las letras se rechazan. US SSN/ITIN exigen residencia fiscal `USA` y sus reglas
específicas. La elegibilidad del pasaporte y patrones nacionales definitivos
siguen sujetos a Alpaca; la validación local no garantiza su aprobación.

### Intereses: usar el catálogo, no listas estáticas

Nuevo endpoint **público**, utilizable antes del registro:

```http
GET /api/v1/auth/interest-options
```

Ejemplo 200 si esos datos están cargados:

```json
{"markets":["NASDAQ","NYSE"],"sectors":["Technology"]}
```

`sectors` puede estar vacío: Alpaca no proporciona sectores y el backend no
inventa clasificaciones. Mostrar etiquetas traducidas está permitido, pero
enviar el valor canónico devuelto por la API, no la traducción.

Registro y edición validan contra esa misma fuente, ignoran diferencias de
mayúsculas y eliminan duplicados. Registro sigue permitiendo `interests: []`;
PUT sigue requiriendo 1–20 entradas y `level`.

```http
PUT /api/v1/users/me/interests
Content-Type: application/json

{"interests":["nyse","technology","NYSE"],"level":"beginner"}
```

200, si `Technology` existe en el catálogo:

```json
{"interests":["NYSE","Technology"],"level":"beginner"}
```

`GET /users/me` devuelve lo persistido. Al editar usuarios anteriores, conservar
también sus selecciones actuales aunque ya no aparezcan entre las opciones:
solo su propietario puede retenerlas o retirarlas. No son opciones nuevas
para otros usuarios. Si se retiran, no pueden volver a seleccionarse mientras
no existan en el catálogo. No se traducen/migran automáticamente.

### Nuevo: edición parcial del perfil propio

```http
PATCH /api/v1/users/me
Content-Type: application/json

{"first_names":" Ana María ","phone":"+573001234567","country":"co"}
```

Requiere la cookie de acceso habitual. Ejemplo 200:

```json
{
  "first_names":"Ana María",
  "last_names":"Perez",
  "phone":"+573001234567",
  "country":"CO"
}
```

La respuesta contiene los cuatro datos personales actuales, **no** todo
`UserMeOut`. El GET completo no cambia. Los campos omitidos se conservan.
Nombres/apellidos: 1–100 tras trim; teléfono E.164; país ISO alpha-2.
`{}`, valores `null`, formatos inválidos y campos extra/protegidos devuelven
422. No enviar email, roles, documentos, estado KYC, MFA ni IDs externos.

**Limitación deliberada:** cualquier reserva o cuenta KYC, pendiente, aprobada,
rechazada o cerrada, impide editar estos cuatro campos:

```json
{
  "code":"PROFILE_KYC_LOCKED",
  "message":"Personal data cannot be edited after KYC has started.",
  "details":null
}
```

HTTP 409. No hay sincronización con Alpaca ni flujo aprobado de reverificación;
la UI debe explicar esta restricción, no reintentar cambiando estados. Sin
autenticación: 401. Fallo de persistencia: 503, sin cambios parciales.

**Acciones del frontend:** regenerar tipos de OpenAPI, cargar el catálogo en
registro/perfil, enviar solo cambios en PATCH, conservar selecciones históricas
propias y manejar 409 `PROFILE_KYC_LOCKED`. No se necesita migración nueva.

---

## TL;DR — lo que el frontend tiene que hacer

1. **Logout**: dejar de tratar el 401 como caso posible. Siempre limpia cookies y
   responde 204; el 503 solo ocurre si la base está caída (y aun así limpia cookies).
2. **`/users/me`**: agregar `broker_requested: boolean` al modelo de perfil.
3. **Activación de broker**: leer el nuevo campo `investor_assignment`.
4. **Panel de administración**: construir el listado y detalle de usuarios con
   `GET /admin/users` y `GET /admin/users/{id}`; ya no hace falta consultar SQL.
5. **KYC administrativo**: usar los campos KYC del directorio y agregar la acción
   de reconciliación (`POST /admin/kyc/{id}/reconcile`).
6. **Auditoría**: nueva pantalla para `GET /admin/audit-log` (permiso `admin:rbac`).
7. **Regenerar tipos** desde `/openapi.json`.
8. **Proxy**: el front debe enrutar `/api/v1/admin/*` (esto ya era un pendiente
   documentado en `readme_agregar.md`; el backend ahora sí expone los endpoints).

---

## 1. Logout — cambio de contrato

`POST /api/v1/auth/logout`

| Antes | Ahora |
|---|---|
| Exigía access token válido | Acepta access token, refresh token, ambos o ninguno |
| 401 si el access token había expirado | **Nunca 401** |
| Limpiaba cookies solo si la sesión se cerraba | **Siempre** limpia ambas cookies (`Max-Age=0`) |
| — | 503 `DATABASE_UNAVAILABLE` si la DB falla, **también limpiando cookies** |

**Qué debe hacer el front:**

- Llamar al endpoint sin condiciones y asumir `204` como éxito.
- Eliminar cualquier rama que trate `401` en logout.
- Ante `503`, limpiar igualmente el estado local de sesión: las cookies ya vienen
  borradas en la misma respuesta.
- No enviar `Authorization` ni credenciales extra: las cookies son suficientes.

OpenAPI declara las dos cookies como opcionales y solo documenta `204` y `503`.

---

## 2. `GET /api/v1/users/me` — campos y comportamiento

### Campo nuevo

```json
{
  "broker_requested": true
}
```

- Tipo: `boolean`, **nunca null**.
- Es el flag que el inversionista marcó al registrarse. Si no lo marcó, `false`.
- **No otorga permisos por sí solo.**
- Promover a alguien a broker **no lo limpia** (decisión A10, aún abierta).
  No lo uses para inferir el rol actual; para eso están `roles[]`.

### Comportamiento nuevo del estado KYC

El backend ahora cachea el estado KYC de Alpaca (`KYC_STATUS_CACHE_TTL_SECONDS`,
60 s por defecto):

- Si el estado en caché es fresco, `/users/me` **no llama a Alpaca** → respuesta
  más rápida.
- Si está vencido y el usuario tiene cuenta vinculada, llama a Alpaca con timeout
  de 10 s.
- Si Alpaca falla: `kyc_status: null` y `kyc_status_unavailable: true`.
- Si no hay cuenta KYC (`none`/`unlinked`): ambos quedan `null`/`false` y no se
  llama a Alpaca.
- Si la base falla antes de cualquier llamada externa: `503 DATABASE_UNAVAILABLE`.

**Qué debe hacer el front:** tolerar latencia ocasional en la primera carga o
cuando el caché venció (hasta 10 s), y seguir usando `kyc_status_unavailable`
para el estado degradado. No asumas que dos llamadas seguidas darán el mismo
`kyc_status` si Alpaca cambió en medio.

### Sin cambios

- `contracted_plan` y `associated_broker` siguen en `null` (dependen de MOD-04 y
  MOD-06).
- `roles[]` sigue siendo la lista de roles efectivos.
- `account_status`: `active` o `pending_broker_activation`.

---

## 3. Activación de broker — respuesta ampliada

`POST /api/v1/admin/users/{user_id}/broker-activation` (`admin:users` + rol
`administrator`)

Respuesta `200`:

```json
{
  "user_id": "uuid",
  "account_status": "active",
  "role_assignment": { "role": "broker", "...": "..." },
  "investor_assignment": { "role": "investor", "...": "..." }
}
```

- `role_assignment` sigue siendo la asignación de **broker** (compatibilidad).
- **Nuevo**: `investor_assignment`. La activación ahora crea los dos roles en una
  sola transacción para que el broker tenga `kyc:submit`.
- Consecuencia visible: después de activar, `GET /users/me` devolverá
  `roles: ["broker", "investor"]` y permisos de ambos roles.
- Errores sin cambio: `404 NOT_FOUND`, `409 BROKER_NOT_PENDING`, `403 FORBIDDEN`.

**Qué debe hacer el front:** mostrar el nuevo campo si modela la respuesta; no
bloquearse si un cliente viejo lo ignora (es aditivo).

---

## 4. Nuevo: directorio de usuarios

### `GET /api/v1/admin/users` — `admin:users`

Listado paginado y filtrable. Reemplaza la necesidad de consultar SQL para
obtener un `user_id`.

**Query params**

| Parámetro | Valores | Notas |
|---|---|---|
| `account_status` | `active`, `pending_broker_activation` | |
| `role` | `investor`, `broker`, `administrator` | Rol **efectivo** |
| `q` | 1-100 caracteres | Busca en email, nombres y apellidos. `%`, `_` y `\` son literales |
| `broker_requested` | `"true"`, `"false"` | **String**, no booleano (`1`/`yes` dan 422) |
| `kyc_status` | 11 valores en mayúsculas | Ver lista abajo; sensible a mayúsculas |
| `kyc_link_state` | `none`, `unlinked`, `linked` | |
| `limit` | 1-100 | Default `50` |
| `offset` | ≥ 0 | Default `0` |

`kyc_status` válidos: `INACTIVE`, `ONBOARDING`, `SUBMITTED`, `SUBMISSION_FAILED`,
`ACTION_REQUIRED`, `ACCOUNT_UPDATED`, `APPROVAL_PENDING`, `APPROVED`, `REJECTED`,
`ACTIVE`, `ACCOUNT_CLOSED`.

**Respuesta**

```json
{
  "items": [
    {
      "user_id": "uuid",
      "email": "ana@example.com",
      "first_names": "Ana",
      "last_names": "Pérez",
      "phone": null,
      "country": "CO",
      "account_status": "active",
      "is_premium": false,
      "roles": ["investor"],
      "broker_requested": true,
      "registered_at": "2026-01-01T00:00:00+00:00",
      "kyc_link_state": "linked",
      "kyc_alpaca_account_id": "uuid",
      "kyc_status": "SUBMITTED",
      "kyc_status_updated_at": "2026-01-01T00:00:00+00:00",
      "kyc_status_checked_at": "2026-01-01T00:00:00+00:00",
      "kyc_reserved_at": "2026-01-01T00:00:00+00:00",
      "kyc_created_at": "2026-01-01T00:00:00+00:00"
    }
  ],
  "total": 42,
  "limit": 50,
  "offset": 0
}
```

Detalles:

- `total` es el total que cumple los filtros, **independiente** de `limit`/`offset`.
- Orden: `registered_at` descendente; empates por `user_id` ascendente.
- `roles` viene ordenado ascendente y es `[]` para usuarios con
  `pending_broker_activation`.
- `limit` y `offset` se devuelven con los valores aplicados (incluidos defaults).
- `phone` y `country` pueden ser `null`; los campos KYC también según
  `kyc_link_state`.
- `kyc_status` es el **valor almacenado**, no una consulta en vivo a Alpaca.

### `GET /api/v1/admin/users/{user_id}` — `admin:users`

Devuelve exactamente la misma estructura de entrada (`UserDirectoryEntryOut`).
`404 NOT_FOUND` si el UUID no existe; `422` si no es UUID.

### KYC según `kyc_link_state`

| Estado | Qué viene |
|---|---|
| `none` | `kyc_*` todos `null` |
| `unlinked` | `kyc_alpaca_account_id`, `kyc_status`, `*_updated_at`, `*_checked_at` en `null`; `kyc_reserved_at` y `kyc_created_at` con valor |
| `linked` | Todos con el valor almacenado; `kyc_status_checked_at` puede ser `null` si nunca se consultó con éxito |

### Errores

- `401` sin token, **antes** de validar parámetros.
- `403` sin `admin:users`, también antes de validar.
- `422 VALIDATION_ERROR` con `details.errors` nombrando **todos** los parámetros
  inválidos (no solo el primero).
- `503 DATABASE_UNAVAILABLE` sin cuerpo parcial.

**Qué debe hacer el front:** usar este endpoint para el listado y el detalle del
panel; no construir `user_id` desde SQL. Mostrar `kyc_status_checked_at` para que
el admin sepa qué tan fresco es el dato.

---

## 5. Nuevo: reconciliación KYC

`POST /api/v1/admin/kyc/{user_id}/reconcile` — `admin:users`

Sirve para reparar el caso "Alpaca creó la cuenta pero el backend no la registró"
(HTTP 503 con mensaje `KYC completion requires reconciliation` en el flujo normal).

**Body** (opcional):

```json
{ "alpaca_account_id": "uuid-o-null" }
```

- Body ausente, `{}` o `{"alpaca_account_id": null}` → busca por el email
  registrado del usuario.
- `alpaca_account_id` debe ser UUID; otro valor da `422`.

**Respuesta `200`**

```json
{
  "user_id": "uuid",
  "alpaca_account_id": "uuid",
  "status": "SUBMITTED",
  "outcome": "linked"
}
```

`outcome` es `linked` (se vinculó ahora) o `already_linked` (ya estaba vinculado;
la operación es idempotente).

**Errores que el front debe manejar**

| HTTP | `code` | Cuándo |
|---|---|---|
| 404 | `NOT_FOUND` | El `user_id` no existe |
| 404 | `KYC_RECONCILE_NOT_FOUND` | Alpaca no tiene una cuenta que coincida |
| 409 | `KYC_RECONCILE_AMBIGUOUS` | Varias cuentas coinciden; `details.count` trae cuántas. Pedir el `alpaca_account_id` |
| 409 | `KYC_ACCOUNT_EXISTS` | El usuario ya tiene **otra** cuenta vinculada |
| 409 | `ALPACA_ACCOUNT_IN_USE` | Esa cuenta ya pertenece a otro usuario |
| 409 | `KYC_SUBMISSION_IN_PROGRESS` | Hay una reserva de envío de menos de 120 s; reintentar después |
| 422 | `VALIDATION_ERROR` | UUID inválido en path o body |
| 500/502/503 | — | Error de Alpaca o de la base |

**Qué debe hacer el front:** agregar una acción "Reconciliar KYC" en el detalle
del usuario; si llega `KYC_RECONCILE_AMBIGUOUS`, mostrar un campo para pedir el
`alpaca_account_id` y reintentar.

---

## 6. Nuevo: audit log

`GET /api/v1/admin/audit-log` — permiso **`admin:rbac`** (no `admin:users`)

Registro append-only de acciones administrativas. No existe endpoint para
crear, editar ni borrar entradas.

**Query params**

| Parámetro | Valores |
|---|---|
| `action` | Uno de los 10 códigos de abajo |
| `actor_user_id` | UUID |
| `target_type` | `user`, `role` |
| `target_id` | 1-100 caracteres |
| `limit` | 1-100, default 50 |
| `offset` | ≥ 0, default 0 |

Acciones: `administrator_created`, `broker_activated`, `premium_changed`,
`role_assignment_created`, `role_assignment_updated`, `role_assignment_revoked`,
`role_assignment_cancelled`, `role_permission_added`, `role_permission_removed`,
`kyc_reconciled`.

**Respuesta**

```json
{
  "items": [
    {
      "id": "uuid",
      "actor_user_id": "uuid",
      "action": "premium_changed",
      "target_type": "user",
      "target_id": "uuid",
      "payload": { "is_premium": true },
      "occurred_at": "2026-01-01T00:00:00+00:00"
    }
  ],
  "total": 10,
  "limit": 50,
  "offset": 0
}
```

Orden: `occurred_at` descendente; empates por `id` descendente. Filtros exactos y
sensibles a mayúsculas. `payload` depende de la acción (por ejemplo,
`broker_activated` trae `broker_assignment_id` e `investor_assignment_id`;
`role_assignment_updated` trae también los valores previos).

**Qué debe hacer el front:** nueva pantalla de auditoría visible solo para
`admin:rbac`; filtros por acción, actor, tipo y objetivo. No ofrezcas acciones de
escritura.

---

## 7. Códigos de error nuevos

| `code` | HTTP | Significado |
|---|---|---|
| `KYC_RECONCILE_NOT_FOUND` | 404 | No hay cuenta en Alpaca que coincida |
| `KYC_RECONCILE_AMBIGUOUS` | 409 | Varias cuentas coinciden (`details.count`) |
| `KYC_SUBMISSION_IN_PROGRESS` | 409 | Reserva KYC activa; reintentar en >120 s |
| `ALPACA_ACCOUNT_IN_USE` | 409 | La cuenta Alpaca ya está vinculada a otro usuario |

Formato de error sin cambios:

```json
{ "code": "VALIDATION_ERROR", "message": "...", "details": { "errors": [...] } }
```

En validaciones, `details.errors` es una lista de `{field, issue}` y **nombra
todos** los parámetros inválidos del request. Los `field` de query params vienen
como `query.limit`, `query.q`, etc.

---

## 8. Permisos y roles

- Directorio y reconciliación: `admin:users`.
- Audit log: `admin:rbac`.
- Activación de broker: `admin:users` **y** rol efectivo `administrator`.
- Asignación de roles `broker`/`administrator`: `admin:rbac` **y** rol
  `administrator`.
- Tras activar un broker, el usuario tiene `broker` **e** `investor`; no lo trates
  como si solo tuviera `broker`.

---

## 9. Lo que NO cambió

- `GET /users/me` mantiene todos sus campos anteriores; solo se agregó
  `broker_requested` y el estado KYC puede venir de caché.
- `GET /kyc/status` mantiene su contrato (sigue consultando a Alpaca), solo que
  ahora también actualiza el timestamp de caché.
- Los endpoints de RBAC, premium, horarios de mercado, sesiones, preferencias,
  watchlists y market data no cambiaron.
- `contracted_plan` y `associated_broker` siguen en `null`.

---

## 10. Decisiones abiertas que pueden afectar la UI

- **A14**: logout devuelve `503` (no `204`) cuando la base falla, aunque limpie
  cookies. La UI debe tratar el 503 como "sesión local cerrada" igualmente.
- **A10**: promover a un inversionista a broker **no** limpia
  `broker_requested`. Si el admin espera que desaparezca el flag, no ocurrirá.

---

## 11. Checklist de implementación

- [ ] Regenerar tipos/cliente desde `/openapi.json`.
- [ ] Logout: quitar manejo de 401; limpiar sesión local también en 503.
- [ ] Perfil: agregar `broker_requested`.
- [ ] Activación broker: leer `investor_assignment` y reflejar ambos roles.
- [ ] Panel admin: listado con filtros, paginación y `total`.
- [ ] Detalle de usuario admin con campos KYC y `kyc_status_checked_at`.
- [ ] Acción "Reconciliar KYC" con manejo de `KYC_RECONCILE_AMBIGUOUS`.
- [ ] Pantalla de audit log detrás de `admin:rbac`.
- [ ] Manejo de 422 con múltiples errores (`details.errors`).
- [ ] Proxy de `/api/v1/admin/*` si aún no existe.
- [ ] Eliminar consultas SQL/manuales para obtener `user_id`.

---

## Apéndice: ejemplos rápidos

Listar usuarios activos que pidieron ser broker:

```
GET /api/v1/admin/users?account_status=active&broker_requested=true&limit=20&offset=0
```

Usuarios con KYC enviado:

```
GET /api/v1/admin/users?kyc_status=SUBMITTED&kyc_link_state=linked
```

Reconciliar por email:

```
POST /api/v1/admin/kyc/{user_id}/reconcile
Content-Type: application/json
{}
```

Reconciliar con ID explícito:

```
POST /api/v1/admin/kyc/{user_id}/reconcile
Content-Type: application/json
{ "alpaca_account_id": "00000000-0000-0000-0000-000000000000" }
```

Auditoría de activaciones de broker:

```
GET /api/v1/admin/audit-log?action=broker_activated&limit=50
```

## MOD-07 — Administración, comisiones y cumplimiento

Spec vigente: `.kiro/specs/admin-mod-07/`, incluidas las decisiones H1/H3/H7 en
`implementation-decisions.md`. OpenAPI (`/openapi.json`) declara los contratos
de entrada, salida y errores. Todas las rutas siguientes tienen prefijo `/api/v1`.

### Acceso por rol y permiso

| Rol | Capacidades de MOD-07 |
| --- | --- |
| `administrator` | Tarifas, comisiones, mercados, interruptores, auditoría, restricciones, reportes y BI; permisos `admin:fees`, `admin:commissions`, `admin:markets`, `admin:halts`, `admin:audit`, `admin:compliance`, `admin:compliance:read`, `admin:bi` |
| `auditor` | Solo lectura de evidencia, restricciones, señales y reportes guardados: `admin:audit`, `admin:compliance:read` |
| `analyst` | Solo BI agregado: `admin:bi`; no accede a evidencia ni datos individuales |
| `investor` | Cotización y comisiones propias |
| `broker` | Cotización y comisiones firmadas para clientes con vinculación activa |

La gestión de roles, permisos, asignaciones y directorio sigue usando los
endpoints existentes de `identity`. Asignar `auditor` o `analyst` exige un
administrador. No hay registro público de estos roles. Los roles son aditivos:
el administrador debe revisar las demás asignaciones vigentes de cada cuenta.
`PROTECTED_PERMISSION` (409) impide conceder permisos de control a otros roles,
conceder permisos de lectura fuera de la matriz y quitar `admin:rbac` al administrador.

### Rutas

| Método | Ruta | Permiso o rol |
| --- | --- | --- |
| GET | `/admin/fee-schedules` | admin:fees |
| GET, POST | `/admin/fee-schedules/{scope}/versions` | admin:fees |
| POST | `/admin/fee-schedules/{scope}/versions/{version_id}/cancel` | admin:fees |
| GET | `/commissions/quote?symbol&side&qty&price&with_broker` | investor o broker |
| GET | `/commissions?from&to&symbol` | investor |
| GET | `/broker/commissions?from&to&investor_id` | broker |
| GET | `/admin/commissions?from&to&broker_id&investor_id&market` | admin:commissions |
| GET | `/admin/markets` | admin:markets |
| GET | `/admin/markets/{market_code}` | admin:markets |
| GET | `/admin/markets/{market_code}/schedule-changes?from&to` | admin:markets |
| GET, POST | `/admin/trading-halts` | admin:halts |
| POST | `/admin/trading-halts/{halt_id}/release` | admin:halts |
| GET | `/trading-halts/active` | autenticado |
| GET | `/admin/audit-trail?from&to&user_id&source&action&entity_type&entity_id` | admin:audit |
| GET | `/admin/audit-trail/orders/{order_id}` | admin:audit |
| POST | `/admin/compliance/restrictions` | admin:compliance |
| POST | `/admin/compliance/restrictions/{restriction_id}/lift` | admin:compliance |
| GET | `/admin/compliance/restrictions?user_id&status` | admin:compliance:read |
| GET | `/admin/compliance/atypical-operations?from&to&user_id&min_amount` | admin:compliance:read |
| POST | `/admin/compliance/users/{user_id}/audit-reports` | admin:compliance |
| GET | `/admin/compliance/audit-reports/{report_id}` | admin:compliance:read |
| GET | `/admin/compliance/users/{user_id}/audit-reports` | admin:compliance:read |
| GET | `/admin/kpis?from&to&refresh` | admin:bi |

Los listados admiten `cursor` y `page_size` (1–100, por defecto 20; auditoría 50).
El Period obligatorio usa fechas inclusivas `from`/`to` de America/New_York,
máximo 366 días. Los importes, porcentajes, cantidades y precios son cadenas
decimales exactas; el consumidor no debe convertirlos a coma flotante para cálculos.
La escala puede normalizarse: `"1.75"` y `"1.7500"` representan el mismo porcentaje.

### Escrituras críticas y tarifas

Crear/cancelar tarifa, activar/liberar interruptor y restringir/rehabilitar reciben
`reason` (1–500 caracteres) y `totp_code` en JSON. El código no se devuelve,
persiste ni registra. Sin TOTP confirmado: 409 `MFA_ENROLLMENT_REQUIRED`;
sin código: 409 `EXTRA_AUTHORIZATION_REQUIRED`; inválido o reutilizado:
401 `EXTRA_AUTHORIZATION_INVALID`.

Crear tarifa recibe `commission_rate_pct` (0–10, hasta 4 decimales),
`platform_share_pct` (0–100, hasta 2), `expected_latest_version` y
`effective_from` opcional con zona horaria. Scope: `default` o código de mercado.
No se admiten vigencias retroactivas. `FEE_VERSION_CONFLICT` (409) incluye
`latest_version`; el cliente recarga el historial. Solo versiones futuras pueden
cancelarse; de otro modo responde `FEE_VERSION_NOT_CANCELABLE` (409).
La matriz incluye `terms`, la versión `current`, `origin` y versiones `scheduled`.

Los términos quedan fijos al crear la orden y se exponen aditivamente en su
detalle: `fee_version_id`, `commission_rate_pct`, `platform_share_pct`. Cada
ejecución parcial calcula y redondea su comisión half-even; el total es su suma.
Las órdenes anteriores sin evidencia conservan términos nulos. Sus ejecuciones
devuelven `commission_status=historical_terms_unknown`, importes oficiales nulos
y se cuentan en `historical_terms_unknown_count`; `totals.complete=false` y los
indicadores de ingresos muestran `complete=false`. Portfolio mantiene en esos
casos una estimación `commission_source=reference`, nunca `official`.

La cotización es informativa (`binding=false`). El reparto se aplica solo a
ejecuciones con firma de broker. Los totales incluyen todo el Period, no solo
la página visible. Un broker sin vinculación activa al `investor_id` consultado
recibe 404 `CLIENT_NOT_FOUND`; se pierde el acceso al terminar la vinculación.
En el desglose administrativo, `unassigned` representa ejecuciones sin broker.

### Negociación y cambios de horario

`scope` de un interruptor admite `global` o mercado; `starts_at` y `ends_at`
definen su vigencia. Errores: 409 `TRADING_HALT_OVERLAP` o
`TRADING_HALT_NOT_RELEASABLE`. Su consulta pública omite motivos y actores.
La creación/vista previa de órdenes puede responder 503 `TRADING_HALTED` o
403 `ACCOUNT_TRADING_RESTRICTED`; también afectan a la conversión de propuestas.
Con 503 la propuesta permanece aceptada para reintentar; una restricción de
cuenta es un rechazo de negocio. Los envíos pendientes se aplazan sin perder
estado ni reserva, con un solo aviso por causa. Se mantienen las reglas de
expiración y nueva autorización por cambio de precio.

Los horarios se editan con los endpoints actuales de `market_data` (default-schedule
y schedule-overrides). Cada cambio se audita atómicamente y se propaga a órdenes
con reintento idempotente. Se añade el evento de preferencias y notificaciones
`market_schedule_changes`, inicialmente habilitado en `in_app` para cuentas
nuevas y existentes. El historial muestra fecha efectiva, valores anterior/nuevo
y estado del despacho. Las notificaciones de horario son a lo sumo un intento
por destinatario; puede perderse el aviso si el proceso cae después del marcador.

### Cumplimiento, evidencia e indicadores

Una restricción recibe `user_id`, `restriction_type=trading`, `evidence_text`
(hasta 2000 caracteres) y `evidence_refs` (hasta 20 objetos `{source,id}`).
Errores 409: `RESTRICTION_ALREADY_ACTIVE`, `RESTRICTION_NOT_ACTIVE`.
No altera sesiones, roles, billetera ni órdenes enviadas. La detección no bloquea
automáticamente: las decisiones requieren administrador y TOTP.

`atypical-v2` informa reglas `absolute_threshold`, `relative_to_history`,
`order_frequency`, `cancellation_frequency`, `repeated_rejections`, con valores
observados, referencias, versión y configuración. Una señal es evidencia para
revisión humana. Los fallos externos no cuentan como rechazos del usuario.

Generar un reporte recibe `{from,to}`. Se guarda contenido inmutable y
`content_sha256`; recuperarlo no recalcula el contenido. La auditoría reúne
fuentes `admin`, `orders`, `brokers`, `auth` y filtra por actor/afectado/relacionado.
Los triggers protegen la evidencia frente a mutaciones ordinarias; el propietario
del esquema o un superusuario puede deshabilitarlos. Esa limitación también
figura en OpenAPI. El tablero devuelve definiciones, `computed_at`, `as_of`,
`cache_hit` y `stale`; un respaldo vencido se identifica explícitamente.

| Componente de referencia del frontend | Contratos principales |
| --- | --- |
| ExecutiveKpiDashboard | `/admin/kpis` |
| CommissionFeeMatrixEditor | `/admin/fee-schedules`, `/admin/commissions` |
| MarketHoursScheduler | `/admin/markets`, endpoints actuales de horarios, `/admin/trading-halts` |
| AuditTrailViewer | `/admin/audit-trail`, `/admin/compliance/*` |
| UserAccessControlManager | endpoints existentes de identity y `/admin/compliance/restrictions` |

Las migraciones 0010–0012 quedan listas para aplicación manual por el equipo
con Alembic. La implementación no aplica migraciones a Supabase compartido.
