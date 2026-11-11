# SPEC-0001: Fundación backend hexagonal

## Estado

Implementado

## Trazabilidad

- SAD: RNF-06 (interoperabilidad) y RNF-10 (mantenibilidad).
- No implementa requisitos funcionales de negocio.

## Contexto y alcance

Se establece la base ejecutable del backend: API FastAPI, configuración
externalizada, persistencia Supabase PostgreSQL preparada y límites modulares para
implementar las capacidades aprobadas.

Quedan fuera de este spec la autenticación real, MFA, órdenes, pagos,
cotizaciones, notificaciones y reglas de cumplimiento.

## Actores y precondiciones

- Equipo de desarrollo mantiene el código y ejecuta las validaciones.
- El proceso puede arrancar sin conexión a Supabase para consultar `/health`.
- Los adaptadores de datos requieren una `DATABASE_URL` válida cuando se usen.

## Contrato y escenarios

### Escenario principal

`GET /health` devuelve `200` y `{"status": "ok"}`.

### Errores y límites

- La configuración inválida debe fallar al iniciar, no generar una respuesta
  de éxito falsa.
- Los módulos de negocio no deben importar detalles de infraestructura.

## Criterios de aceptación

- [x] Existe un layout `src` con módulos de negocio separados.
- [x] El alcance inicial se limita a `identity` y `market_data`.
- [x] La aplicación expone `GET /health`.
- [x] SQLAlchemy async y Alembic están configurados para Supabase PostgreSQL.
- [x] Las reglas hexagonales y el flujo SDD están documentados.
- [x] Existe una prueba automatizada del endpoint de salud.

## Decisiones pendientes

- Plan, feed, permisos y límites de Alpaca Market Data para NYSE y NASDAQ.
- Detalle de roles, MFA, sesiones y conservación de auditoría.
- Estrategia de despliegue y observabilidad de producción.
