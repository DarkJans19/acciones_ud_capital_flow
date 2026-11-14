# Contenedorización de MOD-01 y MOD-02

## Requisitos y trazabilidad

Complemento de infraestructura del spec activo: requisitos 17.1 (arranque),
17.3 y 17.8 (configuración), 17.7 (migraciones) y RF-24 a RF-28 (market_data).
No modifica contratos HTTP ni reglas de negocio.

- Ejecutar los módulos existentes con Python 3.12 y dependencias de producción
  de `uv.lock`; fallar si el lock no corresponde a `pyproject.toml`.
- Inyectar configuración por entorno al ejecutar. Excluir secretos, entornos
  locales, pruebas y documentación funcional del contexto de construcción.
- Mantener Supabase PostgreSQL y Alpaca como servicios externos. SMTP y Telegram
  siguen siendo integraciones opcionales configuradas por entorno.
- Ejecutar Alembic explícitamente, separado del inicio de la API; conservar
  `MIGRATION_DATABASE_URL` y `INITIAL_ADMIN_*` para inicializar una base nueva.
- Servir HTTP y WebSocket en el puerto 8000, con un único worker: los jobs de
  alertas/reloj y el registro de suscripciones viven en memoria del proceso.
- Ejecutar como usuario sin privilegios y comprobar `/health`. Esta comprobación
  indica vida del proceso HTTP, no disponibilidad de Supabase o Alpaca.

## Diseño

`Dockerfile` construye el paquete con uv 0.11.15, sin dependencias de desarrollo
y sin instalación editable. La etapa final copia el entorno virtual y Alembic
sobre la misma base Python Debian slim. Uvicorn recibe señales directamente.
`compose.yaml` define `api` y `migrate` (perfil `tools`), sin PostgreSQL local.
Compose >= 2.30 usa `env_file.format: raw` para preservar `$` en hashes Argon2
y otros secretos. El puerto del host se publica solo en loopback por defecto.

## Tareas y verificación

- [x] Añadir imagen multietapa, usuario no root y healthcheck.
- [x] Restringir contexto con `.dockerignore`.
- [x] Añadir Compose y comando manual de migración.
- [x] Documentar configuración, ejecución y límites operativos en README.
- Validar `docker compose config --quiet` y construir la imagen.
- Comprobar importación, Alembic y `/health` con configuración sintética,
  sin ejecutar migraciones contra Supabase ni acceder a proveedores reales.
- Ejecutar ruff, mypy y pytest según AGENTS.md.

## Evidencia de validación (2026-11-12)

- Compose validado usando `--env-file .env.example config --quiet`.
- Imagen construida con éxito: Python 3.12, instalación desde lock sin dev.
- Contenedor aislado con `--network none`, configuración sintética y jobs
  deshabilitados: UID 10001, sin `.env`, Alembic reconoce la revisión
  `0004_assignment_cancellation`, Uvicorn sirve `/health` y `/openapi.json`.
- Ruff y mypy correctos (148 archivos). Pytest local: 174 passed, 18 skipped
  sin `TEST_DATABASE_URL`, 1 failed en la prueba existente
  `test_conversion_preserves_the_instant`: compara el offset de un instante
  convertido con `ZoneInfo.utcoffset()` aplicado a la hora UTC como si fuera
  hora local, lo que difiere en transiciones DST (Asia/Beirut). No se modifica
  esta prueba como parte de la contenedorización.
- No se aplicaron migraciones ni se probaron credenciales de servicios reales.
