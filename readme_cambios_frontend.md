# Cambios del backend que afectan al frontend — módulo Identity

Alcance: PR #1 (`feat/identity-admin-gaps`), mergeado en `main` como `16ed495`.
Cubre las brechas de `readme_agregar.md` (tareas 22-30) más el cambio de logout.

Todo está bajo el prefijo `/api/v1`. El contrato completo y actualizado está en
`/openapi.json` y `/docs`.

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
