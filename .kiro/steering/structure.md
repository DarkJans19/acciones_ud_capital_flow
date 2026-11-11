# Estructura y arquitectura

Monolito modular con arquitectura hexagonal. Codigo en `src/acciones_ud/`.

## Capas por modulo de negocio

Cada modulo (`identity`, `market_data`, y los futuros) separa:

- `domain/`: entidades, objetos de valor, reglas puras y puertos de salida (Protocol).
- `application/`: casos de uso, comandos, consultas y DTOs.
- `adapters/inbound/`: entradas HTTP (routers, schemas) y jobs (tareas asyncio).
- `adapters/outbound/`: persistencia (repositorios SQLAlchemy) e integraciones externas (clientes Alpaca).
- `composition.py`: cablea puertos y adaptadores, y expone `register(app)`, `startup(app)`, `shutdown(app)`.

## Regla de dependencias (critica)

- `domain` y `application` NUNCA importan FastAPI, SQLAlchemy, SDKs de proveedores ni infraestructura.
- Las dependencias apuntan hacia adentro mediante interfaces/Protocol.
- Ejemplo: TOTP entra por un puerto; el wrapper de `pyotp` vive en un adaptador de salida.
  Los errores de Alpaca se clasifican en `shared/domain/` para que los casos de uso no importen infraestructura.

## Codigo compartido (`shared/`)

- `shared/domain/`: errores (`AppError`, `ErrorCode`), `Clock`, clasificacion de errores de Alpaca.
- `shared/infrastructure/`: `db.py` (engine, session_factory, unit_of_work), `http_errors.py`,
  `alpaca_http.py`, `cookies.py`, `logging.py`.
- `config/settings.py`: `Settings` (carga `.env`), `require_api_settings`, `InitialAdminSettings`.

## Reglas para modulos nuevos

- Un modulo nuevo se crea solo cuando tiene su propia spec aprobada en `.kiro/specs/`.
- No crear paquetes vacios para capacidades futuras.
- Un modulo que necesite datos de otro (por ejemplo leer preferencias de `identity`) lo hace a traves de un puerto, no importando sus tablas directamente salvo decision explicita.
- `main.py` registra cada modulo llamando su `register`/`startup`/`shutdown`. No hay `composition.py` de nivel superior.

## Pruebas (`tests/`)

- `tests/<modulo>/` con subcarpetas `unit/`, `property/`, `api/`.
- Las pruebas marcadas `db` necesitan `TEST_DATABASE_URL`; sin el se saltan, no fallan.
- Las integraciones con Alpaca usan fakes en memoria que implementan los mismos puertos.