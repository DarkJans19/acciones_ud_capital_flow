# SPEC-0100: Identidad, seguridad y control de acceso

> **Reemplazado.** El equipo adoptó `.kiro/specs/identity-market-backend/` como única base de documentación para MOD-01 y MOD-02. Este archivo se conserva solo como referencia histórica; no lo actualices.

## Estado

Reemplazado por `.kiro/specs/identity-market-backend/`.

## Trazabilidad

- Catálogo actualizado: RF-01, RF-02, RF-03 y RF-06 a RF-09.
- RFP incluidos por decisión del equipo: RFP-02 y RFP-03.
- RFP todavía pendientes de aprobación: RFP-01 y RFP-08.
- Calidad del SAD: RNF-04, RNF-08 y RNF-10.
- Casos de uso y escenarios de calidad: pendientes de IDs `CU` y `EC` aprobados.
- Mockups: 01 (Landing), 02 (Login/MFA/Roles) y 09 (Perfil y dispositivos).

RF-44 no forma parte de este módulo. El registro técnico de accesos y sesiones
atiende seguridad y auditabilidad, pero la auditoría funcional de operaciones
pertenece a MOD-07.

## Propósito

Administrar identidades, autenticación con segundo factor, autorización por rol,
perfil de cuenta, sesiones concurrentes y preferencias de usuario. FastAPI es la
autoridad de sesión y permisos; el frontend no decide autorizaciones.

Supabase se usa únicamente como PostgreSQL administrado. La autenticación se
implementa en este módulo mediante sus propios casos de uso; no se adopta Supabase
Auth ni se expone acceso directo del frontend a las tablas.

## Alcance

### Incluido

- RF-01: registro de inversionista con nombres, apellidos, correo, teléfono, país,
  clave, aceptación de términos y preferencia de reporte mensual.
- RF-02: autenticación con correo, clave y TOTP/MFA.
- RF-03: roles, permisos y vigencia de las asignaciones.
- RF-06: consulta de identidad, perfil y estado de cuenta. El plan premium y el
  comisionista se incorporarán mediante contratos con sus módulos propietarios.
- RF-07: preferencias de eventos y canales externos disponibles.
- RF-08: preferencias de visualización del portafolio.
- RF-09: tipo de orden predeterminado, límite diario, umbral elevado y confirmación
  adicional; MOD-03 será responsable de aplicar estos controles.
- RFP-02: registro diferenciado por rol con aprovisionamiento seguro para
  Inversionista, Comisionista y Administrador en el alcance actual.
- RFP-03: sesiones, dispositivos, cierre y revocación.
- Auditoría técnica de registro, acceso, MFA, refresh, cierre y revocación.

### Excluido

- Supabase Auth, Realtime y acceso del navegador mediante Data API.
- Cálculo del perfil de riesgo RF-04 y estadísticas RF-05, propios de MOD-05.
- Generación del reporte mensual; MOD-01 solo guarda la preferencia de RF-01.
- Envío de notificaciones; MOD-01 guarda preferencias y consume un puerto de entrega.
- KYC de RFP-01 e intereses/experiencia de RFP-08 hasta su aprobación.
- Ejecución de órdenes, portafolios, pagos, suscripciones y auditoría RF-44.
- Roles de Analista de Seguridad y Auditoría y Directivo del negocio mientras no
  estén priorizados; por ello RF-03 permanece parcialmente cubierta.

## Actores y reglas de autorización

- El Inversionista puede usar el flujo público aprobado.
- El alcance activo de registro y autorización cubre Inversionista, Comisionista y
  Administrador. Los otros dos roles definidos por el SAD requieren un spec aprobado.
- Un cliente nunca puede autoasignarse como Comisionista o Administrador; esos roles
  requieren invitación, aprovisionamiento o aprobación administrativa.
- Las asignaciones de rol tienen inicio y fin de vigencia cuando corresponda.
- La matriz exacta de permisos debe aprobarse antes de habilitar los endpoints.
- Perfil, preferencias y sesiones se limitan al sujeto autenticado, salvo un caso
  administrativo explícito y auditado.

## Reglas e invariantes de dominio

1. El correo normalizado es único y su verificación se registra explícitamente.
2. Nunca se almacenan contraseñas, JWT, refresh tokens, secretos TOTP ni códigos de
   recuperación en texto plano.
3. Las contraseñas se verifican con Argon2id y parámetros versionados.
4. El secreto TOTP se cifra; los códigos de recuperación se almacenan mediante hash,
   son de un solo uso y su consumo queda auditado.
5. Los refresh tokens rotan. La reutilización de uno revocado aplica la política de
   invalidación de la familia de sesión.
6. Deshabilitar un usuario o revocar una sesión impide nuevos refresh y accesos.
7. La autorización se comprueba en cada caso de uso, no solo en el frontend.
8. Los eventos de seguridad no contienen credenciales, cookies ni secretos.

## Contrato HTTP inicial

| Método y ruta | Resultado esperado |
|---|---|
| `POST /api/v1/auth/register` | Registra una identidad permitida; `201` |
| `POST /api/v1/auth/login` | Valida credenciales e inicia desafío MFA |
| `POST /api/v1/auth/mfa/verify` | Completa el desafío y crea la sesión |
| `POST /api/v1/auth/refresh` | Rota la sesión mediante cookie segura |
| `POST /api/v1/auth/logout` | Revoca la sesión actual; `204` |
| `GET /api/v1/users/me` | Devuelve identidad, perfil, estado y capacidades |
| `PUT /api/v1/users/preferences/channels` | Sustituye eventos y canales seleccionados |
| `PUT /api/v1/users/preferences/portfolio` | Sustituye preferencias de visualización |
| `PUT /api/v1/users/preferences/orders` | Sustituye controles personales de órdenes |
| `GET /api/v1/users/me/sessions` | Lista sesiones/dispositivos propios |
| `DELETE /api/v1/users/me/sessions/{session_id}` | Revoca una sesión propia; `204` |
| `PUT /api/v1/admin/users/{user_id}/roles` | Administra asignaciones con vigencia |

Los errores usarán un contrato versionado compatible con
`application/problem+json`. Las mutaciones autenticadas mediante cookies requieren
protección CSRF y validación de `Origin`.

## Modelo relacional propuesto (3FN)

Las tablas se alojarán en Supabase PostgreSQL y se versionarán con Alembic:

- `users`: correo normalizado, hash de contraseña, estado y marcas de tiempo.
- `user_profiles`: nombres, apellidos, teléfono y país.
- `roles`, `permissions`, `role_permissions` y `user_roles`: catálogo, permisos,
  asignaciones y vigencias.
- `mfa_credentials` y `mfa_recovery_codes`: secreto cifrado y códigos hasheados.
- `sessions`: familia, hash del refresh token, expiración, revocación y dispositivo.
- `session_audit`: usuario, sesión, evento, IP tratada según política, `user_agent`,
  instante, resultado y correlación.
- `notification_preferences`: usuario, evento, canal y estado.
- `portfolio_view_preferences`: tipo de vista, orden y umbral de ocultamiento.
- `order_control_preferences`: tipo predeterminado, límite diario, umbral elevado y
  confirmación adicional.
- `report_preferences`: habilitación del reporte mensual solicitada en RF-01.

Las relaciones usarán claves foráneas, restricciones de unicidad e índices
justificados. Las migraciones usarán preferiblemente la conexión directa de
Supabase, o Session pooler si el entorno solo dispone de IPv4. La aplicación usará
la conexión directa o Session pooler apropiada para su despliegue persistente.

## Seguridad de Supabase

- La cadena PostgreSQL y sus credenciales solo existen en el backend y en secretos
  de despliegue; nunca se entregan a Next.js.
- Las tablas de aplicación no se exponen mediante Data API sin una decisión y
  políticas RLS revisadas.
- Elegir Supabase no reemplaza las comprobaciones de autorización de los casos de uso.

## Estrategia de pruebas

- Unitarias: estados, roles, preferencias, MFA, rotación, revocación y permisos.
- Integración: Supabase/PostgreSQL, restricciones y migraciones ida/vuelta.
- Contrato: OpenAPI, cookies, códigos HTTP y `application/problem+json`.
- Seguridad: escalamiento de rol, reutilización de sesión, fuerza bruta, CSRF,
  enumeración de cuentas y filtrado de secretos.
- E2E: registro permitido, login+MFA, refresh, preferencias y revocación de sesión.

## Criterios de aceptación

- [ ] Ningún flujo público crea roles privilegiados sin autorización del servidor.
- [ ] Credenciales y tokens no aparecen en texto plano, respuestas JSON ni logs.
- [ ] Las cookies finales tienen atributos de seguridad aprobados.
- [ ] El backend rechaza operaciones no autorizadas aunque se manipule el frontend.
- [ ] MFA, recuperación y revocación cubren éxito, error y replay.
- [ ] RF-08 y RF-09 persisten preferencias sin ejecutar lógica de otros módulos.
- [ ] La documentación de RF-03 identifica explícitamente los roles aún no cubiertos.
- [ ] Las migraciones construyen el esquema en un proyecto Supabase vacío.
- [ ] OpenAPI genera tipos reproducibles para el frontend.
- [ ] Ruff, Mypy y Pytest finalizan correctamente.

## Decisiones pendientes

- Aprobación de RFP-01 (KYC) y RFP-08 (intereses/experiencia/dashboard).
- Flujo de alta y verificación de Comisionistas y Administradores.
- Matriz de permisos y posible incorporación de los otros roles del SAD.
- Política de contraseña, bloqueo, recuperación y verificación de correo.
- Recuperación MFA, obligatoriedad por rol y nombre del emisor TOTP.
- Algoritmo y rotación de claves JWT; duración y máximo de sesiones.
- Estrategia CSRF y atributos de cookies según el gateway.
- Retención de auditoría técnica y tratamiento de IP/dispositivo.
- Estrategia de schemas/RLS en Supabase si alguna tabla llegara a exponerse.
