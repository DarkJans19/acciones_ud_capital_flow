# Producto: Acciones UD (backend)

Plataforma para consultar informacion bursatil, gestionar portafolios y tramitar
operaciones con seguridad y trazabilidad. Solo backend: el frontend lo desarrolla
otro equipo y consume el contrato OpenAPI (`/openapi.json`, `/docs`).

## Fuente de requisitos

- Catalogo funcional principal: `requerimientos_acciones_ud_v2 (1).pdf` (RF-01 a RF-47, RFP-01 a RFP-13).
- Specs del equipo: `.kiro/specs/` es la unica base de documentacion. La carpeta `specs/` quedo reemplazada.
- Ningun asunto pendiente se vuelve supuesto silencioso: se documenta como decision o assumption.

## Integraciones

- Alpaca es la unica integracion bursatil (Broker API + Market Data API), en sandbox.
- Supabase se usa solo como PostgreSQL administrado. No se usa Supabase Auth, Realtime ni Data API.
- Stripe (cuando aplique a su modulo) solo en sandbox para suscripciones premium.

## Modulos de desarrollo (MOD-01 a MOD-08)

- MOD-01 identity: identidad, auth, MFA, roles, sesiones, preferencias. Implementado.
- MOD-02 market_data: mercados, instrumentos, cotizaciones, historicos, watchlists, alertas. Pendiente.
- MOD-03 ordenes, MOD-04 fondos/billetera, MOD-05 portafolio, MOD-06 comisionistas,
  MOD-07 administracion/auditoria, MOD-08 movil. Se incorporan cuando tengan su propia spec aprobada.

## Regla de specs (importante)

- Una spec por modulo de desarrollo. No agrupar varios modulos en una sola spec.
- La primera spec (identity-market-backend) junto MOD-01 y MOD-02 por historia; no repetir ese patron.
- Nombrar cada spec por su modulo, por ejemplo `orders-mod-03`, `wallet-mod-04`.