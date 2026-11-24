# Evaluación transversal de seguridad y flujos — 2026-11-24

Evaluación, no implementación de nuevas capacidades. No cambia requisitos,
decisiones de negocio, esquemas de producción ni adaptadores de `src/`.

Por solicitud expresa del equipo, el informe y las evidencias de ejecución están
en [`documentation/auditoria-e2e-2026-11-24`](../../../documentation/auditoria-e2e-2026-11-24/README.md).
Este archivo conserva la trazabilidad desde el spec funcional.

## Trazabilidad

| Área | Referencia | Evidencia |
| --- | --- | --- |
| Registro, cookies, login, MFA y sesiones | RF-01/02, RFP-03; requisitos 3, 4, 18 | Suite existente, `tests/security`, HTTPS real |
| Roles efectivos y separación administrativa | RF-03, RNF-04; MOD-07 | Matriz determinista de cinco roles y cuatro estados |
| Información personal y edición | RF-06, RFP-01; requisito 26 | Reproducción del preflight PATCH |
| Catálogo, precios y streaming | RF-24/25/26/27/28 | Pruebas HTTP, frames WebSocket y flujo integrado |
| Órdenes y controles monetarios | MOD-03, RF-30 | Suite de órdenes, idempotencia y preview real |
| Suscripciones y fondos | MOD-04 | Webhook firmado, desbloqueo premium y fondos aislados |
| Portafolio y reportes | MOD-05, RF-41/42 | PostgreSQL real y denegaciones entre propietarios |
| Broker, enlaces y propuestas | MOD-06, RF-13..23 | Suite PostgreSQL y recorrido integrado |
| Tarifas, trazabilidad, compliance y KPI | MOD-07, RF-43..47 | Suite original, matriz exhaustiva y lecturas reales |

## Decisiones no modificadas

- D4 excluye CSRF y validación de Origin/Referer. El informe expone el riesgo
  residual; no lo presenta como un incumplimiento oculto del spec.
- El requisito 18.7 permite regenerar códigos con sesión autenticada. Solicitar
  step-up adicional sería un cambio de seguridad que necesita aprobación.
- Los fallos confirmados tienen regresiones `xfail(strict=True)`, con identificador
  `AUD-*`. Son deuda abierta, no pruebas aprobadas. `--runxfail` los muestra como
  fallos normales.
- No se ejecutan migraciones destructivas sobre `.env`/Supabase. Se usa solamente
  `TEST_DATABASE_URL` desechable para las pruebas que borran el esquema.
