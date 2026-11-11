# Trazabilidad del alcance activo

> **Reemplazado.** El equipo adoptó `.kiro/specs/identity-market-backend/` como única base de documentación para MOD-01 y MOD-02. Este archivo se conserva solo como referencia histórica; no lo actualices.

## Fuentes conciliadas

Para los dos módulos activos se aplicó esta jerarquía:

1. Decisiones explícitas del equipo: monolito modular hexagonal, Supabase como
   PostgreSQL administrado y alcance activo limitado a MOD-01 y MOD-02.
2. `requerimientos_acciones_ud_v2 (1).pdf`, fechado el 10 de noviembre de 2026,
   como catálogo funcional actualizado.
3. SAD borrador para atributos de calidad y asuntos que el catálogo actualizado
   todavía declara pendientes.

Una decisión técnica no amplía por sí sola el alcance funcional. En particular,
Supabase se usa como base de datos; Supabase Auth, Realtime y Data API quedan fuera
hasta que exista una decisión explícita.

## MOD-01 — Identidad, seguridad y control de acceso

| Requisito | Cobertura en SPEC-0100 | Observación |
|---|---|---|
| RF-01 | Completa en alcance | Incluye términos y preferencia de reporte mensual; la generación del reporte pertenece a MOD-05 |
| RF-02 | Completa en alcance | Se adopta TOTP como segundo factor; el SAD anterior mencionaba correo/celular |
| RF-03 | Parcial por alcance activo | Incluye vigencia y permisos para Inversionista, Comisionista y Administrador; faltan definir Analista de Seguridad y Auditoría y Directivo del negocio |
| RF-06 | Parcial por dependencia | Identidad y estado son propios; plan y comisionista provendrán de MOD-04/MOD-06 |
| RF-07 | Completa para configuración | MOD-01 guarda preferencias; otros módulos producen los eventos y el canal de entrega se integra por puerto |
| RF-08 | Completa para configuración | MOD-05 consumirá las preferencias al existir |
| RF-09 | Completa para configuración | MOD-03 aplicará los controles al existir |
| RFP-01 | Pendiente de aprobación | Datos KYC necesarios para una futura cuenta Alpaca |
| RFP-02 | Incluido por decisión del equipo | Registro diferenciado por rol sin permitir autoasignación privilegiada |
| RFP-03 | Incluido por decisión del equipo | Sesiones, dispositivos y cierre de sesión |
| RFP-08 | Pendiente de aprobación | Intereses, nivel de experiencia y dashboard inicial |

RF-44 no se atribuye a MOD-01: pertenece a MOD-07. Los eventos técnicos de sesión
se conservan por seguridad y observabilidad, pero no equivalen al módulo funcional
de auditoría de operaciones ni pretenden cubrir RNF-05, centrado en las órdenes.

## MOD-02 — Explorador de mercados y cotizaciones

| Requisito | Cobertura en SPEC-0200 | Observación |
|---|---|---|
| RF-24 | Completa en alcance | Catálogo y negociabilidad reportados por Alpaca |
| RF-25 | Completa en alcance | Quote, bid/ask, históricos y profundidad solo cuando el plan la entregue |
| RF-26 | Completa en alcance | Listas observadas y alertas; el acceso premium se valida mediante un puerto hacia MOD-04 |
| RF-27 | Completa en alcance | Calendario, reloj, zona horaria, estado y eventos opcionales de apertura/cierre |
| RF-28 | Completa en alcance | Muestra bolsa y negociabilidad; no compara rutas ni proveedores |

Alpaca es la única integración bursátil aprobada por el catálogo actualizado. El
asunto pendiente no es escoger proveedor, sino seleccionar plan/feed, comprobar
permisos, cobertura, latencia, profundidad y límites.

## Correcciones aplicadas frente a los specs anteriores

- Se retiró RF-44 de Identidad.
- Se incorporaron RF-08 y RF-09 a Identidad.
- Se incorporaron RF-26 y RF-28 a Mercado.
- RF-28 dejó de describir comparación o selección de rutas.
- Se eliminó Alpha Vantage como alternativa de integración.
- Se separó el perfil de riesgo RF-04, que corresponde a MOD-05, de los datos de
  identidad administrados por MOD-01.
- Se retiró la planificación temporal de las especificaciones funcionales por ser
  una decisión de organización interna.
