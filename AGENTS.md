# Acciones UD Backend

## Propósito

Este repositorio contiene el backend de Acciones UD, una plataforma para
consultar información bursátil, gestionar portafolios y tramitar operaciones
con controles de seguridad, trazabilidad e integración con proveedores
externos. El catálogo unificado `requerimientos_acciones_ud_v2 (1).pdf` es la
fuente funcional principal; el SAD complementa atributos de calidad y decisiones
abiertas. Ningún asunto pendiente debe convertirse en un supuesto silencioso.

## Arquitectura

La aplicación inicia como un monolito modular con arquitectura hexagonal.
Cada módulo de negocio separa:

- `domain`: entidades, objetos de valor, reglas y puertos de salida.
- `application`: casos de uso, comandos, consultas y DTOs.
- `adapters/inbound`: entradas HTTP y otros controladores.
- `adapters/outbound`: persistencia e integraciones externas.

El dominio y la aplicación no deben importar FastAPI, SQLAlchemy, SDKs de
proveedores ni detalles de infraestructura. Las dependencias apuntan hacia
adentro mediante interfaces/Protocol. Los adaptadores se conectan en
`composition.py` o en la capa de configuración.

## Alcance funcional activo

En la fase actual solo se desarrollan estos módulos:

- `identity`: identidad, perfiles, autenticación, MFA, roles, sesiones y
  preferencias de usuario. Cubre RF-01 a RF-03 y RF-06 a RF-09, además de los
  RFP aprobados expresamente para registro por rol y gestión de sesiones.
- `market_data`: mercados, calendarios, instrumentos, búsqueda, cotizaciones e
  históricos, listas observadas y alertas. Cubre RF-24 a RF-28.

No se deben crear paquetes vacíos para capacidades futuras. Órdenes,
portafolios, fondos, comisionistas, suscripciones, notificaciones y analítica se
incorporarán únicamente cuando exista un spec aprobado para su módulo.

## Convenciones de desarrollo

- Python 3.12+, tipado explícito y módulos pequeños.
- Dependencias y comandos se gestionan con `uv`.
- Supabase PostgreSQL es la base de datos administrada. SQLAlchemy 2.x async +
  `asyncpg` y Alembic son los componentes de persistencia y migración. Esta
  decisión no implica usar Supabase Auth, Realtime o Data API.
- Pydantic se usa para contratos de entrada/salida y configuración; no sustituye
  las entidades del dominio.
- Los errores deben ser explícitos y traducirse en la frontera HTTP.
- Las credenciales y secretos solo se obtienen desde variables de entorno.
- Cada funcionalidad nueva debe iniciar o actualizar un spec en `specs/` y
  mantener trazabilidad al SAD mediante IDs `RF`, `RNF`, `CU` o `EC`.

## Validación

Ejecutar:

```powershell
uv run ruff check .
uv run mypy src
uv run pytest
```

Para levantar la API localmente:

```powershell
uv run uvicorn acciones_ud.main:app --reload
```

`DATABASE_URL` debe usar la conexión de aplicación de Supabase y
`MIGRATION_DATABASE_URL` una conexión separada para Alembic, preferiblemente
directa o Session pooler cuando el entorno solo tenga IPv4. Con `asyncpg`, el
parámetro de URL es `ssl=require`, no `sslmode=require`. El endpoint de salud no
requiere una conexión activa.
