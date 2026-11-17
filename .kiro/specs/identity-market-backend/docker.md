# Docker y Stripe local: MOD-01, MOD-02 y MOD-04

## Requisitos y trazabilidad

Requisitos 17.1, 17.3, 17.7 y 17.8 del spec de identidad y mercados,
RF-24 a RF-28 y RF-10/RF-11 del spec wallet. La API recibe solo sus secretos
necesarios durante la ejecucion; Stripe CLI opera en el host.

## Diseno vigente

Por decision del usuario, API y migraciones vuelven a recibir `.env` mediante
`env_file.format: raw`. Se preservan dolares y no se copia el archivo a la imagen.
Stripe CLI sigue en el host y recibe solamente su clave sandbox y variables del
sistema. No existe servicio Stripe en Compose.

Se utilizan directamente Docker Compose y Stripe CLI, sin scripts intermedios.
El secreto mostrado por el listener local debe configurarse manualmente como
STRIPE_WEBHOOK_SECRET en `.env`; despues se recrea la API. Stripe CLI utiliza
su autenticacion local en la misma cuenta sandbox, sin cargar el `.env` del
backend. Su salida nativa contiene el secreto de firma y no debe publicarse.

El Dockerfile conserva Python 3.12, usuario sin privilegios y healthcheck.
Compose publica la API solo en loopback y mantiene migraciones bajo perfil tools.
Los comandos estan en el README. El entorno de los contenedores backend es
visible a administradores de Docker; no debe publicarse docker inspect ni la
salida completa de docker compose config.

## Verificacion (2026-11-16, America/Bogota)

La configuracion anterior entregaba todo .env a API y Stripe. Se retiraron los
contenedores afectados y se reemplazo por el aislamiento descrito arriba.
No hay evidencia de publicacion externa; no se auditaron todas las capas ni
el historial de imagenes anteriores.

Stripe confirmaba un pago mensual sandbox de 12 USD, pero la base permanecia
pending_checkout e is_premium=false. Se reenviaron los cuatro eventos originales
mediante Stripe CLI: todos recibieron HTTP 200 y la base quedo active,
is_premium=true y pago paid de 12.00 USD. El periodo termina el 16 de diciembre
de 2026 a las 17:45:25 de Bogota, coincidiendo con Stripe. No hubo otro cobro.

El reenvio repetido de Checkout e invoice no duplico eventos ni pagos; el
snapshot antiguo se marco stale. Una peticion sin firma recibio HTTP 400.
API healthy, sin .env dentro del contenedor, sin credenciales de migracion,
administracion inicial o Supabase Data API. Logs revisados sin claves Stripe.

Ruff y mypy correctos (345 archivos). Pytest: 623 passed, 29 skipped por falta
de TEST_DATABASE_URL y una advertencia de dependencia, en Python local 3.13.12.
La recuperacion del pago se verifico adicionalmente contra la base sandbox
configurada. No se aplicaron migraciones.

La evidencia anterior corresponde al aislamiento previo por rol. La configuracion
vigente autoriza `.env` completo para backend y mantiene aislado Stripe CLI.

Se eliminaron el launcher opcional y sus pruebas especificas al simplificar el
flujo a comandos nativos. Se conservan las pruebas de firma, idempotencia y
suscripciones del modulo wallet. Los resultados historicos anteriores no son
un recuento de la suite posterior a esta limpieza.
