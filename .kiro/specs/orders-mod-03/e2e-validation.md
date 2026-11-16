# Diagnóstico y validación E2E de MOD-03 y MOD-04

Fecha: 2026-11-15. Entorno real de la aplicación: Supabase configurado, Alpaca
Broker sandbox y Stripe test. Usuario utilizado: investor.ti@accionesud.com.
No se registraron usuarios nuevos ni se consumieron códigos de recuperación.

## Resultado y alcance de la validación

**La causa de DATABASE_UNAVAILABLE en suscripciones está corregida y las
migraciones están aplicadas. El E2E financiero completo NO está aprobado.**

| Área | Resultado real |
| --- | --- |
| Login + TOTP dinámico | 200 + 200; usuario existente autenticado |
| Renovación de sesión | 200; cookies rotadas |
| Logout / token revocado | 204 y luego 401 usando la sesión cerrada |
| Sin sesión / solo Bearer | 401, conforme al contrato actual de cookies |
| Supabase | Revisión 0007; 19 tablas presentes y RLS habilitado |
| Preferencias | 40 filas del inversionista: 10 eventos × 4 canales |
| Planes Stripe | Claves válidas; precios activos test: USD 12/mes y USD 120/año |
| Checkout mensual | 201; completado mediante Chrome con tarjeta de prueba; Stripe confirma paid |
| Suscripción y factura | active, pago USD 12 paid, un único registro por factura |
| Cancelación de suscripción | 200; cancel_at_period_end=true en Stripe y Supabase |
| Webhook con firma ausente | 400 WEBHOOK_SIGNATURE_INVALID |
| Eventos reales de Stripe | Cinco eventos aplicados mediante reproducción local firmada; duplicados sin segundo pago |
| Entrega automática de webhooks | Pendiente: GET /v1/webhook_endpoints devolvió lista vacía |
| Relación ACH | 201, luego APPROVED; concordancia entre API y Supabase |
| Depósito USD 1000 | 201; QUEUED → SENT_TO_CLEARING, confirmado directamente en Alpaca |
| Idempotencia de depósito | Repetición: mismo ID; cambio de importe: 409 |
| Saldo Alpaca | 200, unavailable=false, cash/buying_power/cash_withdrawable=0 |
| Retiro USD 1 | 422 INSUFFICIENT_FUNDS; no se creó transferencia |
| Órdenes: listado / preview | 200; próxima apertura 2026-11-16 09:30 America/New_York |
| Órdenes: creación y reintento | 502 por presupuesto de 5 s; no se persistió orden ni reserva |
| Orden inexistente: detalle/cancelación/reautorización/reenvío/reanudación | 404 ORDER_NOT_FOUND |
| Cola de comisionista con investor | 403 FORBIDDEN |
| Compra, ejecución FILL y cancelación de orden real | Pendientes; no se afirma éxito |

El usuario ya tenía is_premium=true antes del checkout. Se verificó su
conservación y contracted_plan=monthly, sin atribuir ese flag inicial al pago.

La API de pruebas se levantó en http://127.0.0.1:8765 con la configuración real.
Los comandos siguientes usan el puerto habitual 8000 para tu propia ejecución.

## 1. Causa raíz y correcciones

### 1.1 Esquema sin desplegar

La base respondía y estaba en 0005_identity_admin_gaps. SELECT sobre subscriptions
fallaba con ProgrammingError / SQLSTATE **42P01**, tabla inexistente.
El manejador compartido convertía todos esos errores a DATABASE_UNAVAILABLE y
descartaba su causa sin registrarla.

Se ejecutó Alembic upgrade head. El primer intento reveló un segundo fallo:
SQLSTATE **23514**, violación de
notification_preferences_event_type_check. El CHECK original admitía siete
tipos; los seeds nuevos intentaban insertar balance_changes y posteriormente
order_executions/order_updates.

Se corrigieron y aplicaron 0006_wallet_schema y 0007_orders_schema. Cada revisión
amplía el CHECK antes de su seed; el downgrade borra sus eventos antes de
restaurar el vocabulario anterior. No se utilizó create_all, stamp ni un reset.

También se corrigió 0002_initial_admin: importaba default_preferences del código
actual, por lo que una instalación nueva intentaba sembrar diez eventos sobre
el esquema histórico de siete. Ahora usa un snapshot de los siete originales.
Esta corrección no vuelve a crear ni modifica al administrador existente.

### 1.2 Diagnóstico seguro

| Causa | HTTP | Código |
| --- | --- | --- |
| Conexión, DNS, timeout o indisponibilidad | 503 | DATABASE_UNAVAILABLE |
| SQLSTATE clase 42: tabla/columna/query | 500 | DATABASE_SCHEMA_ERROR |
| SQLSTATE 42501 o clase 28 | 500 | DATABASE_PERMISSION_ERROR |
| SQLSTATE clase 23: restricciones | 409 | DATABASE_INTEGRITY_ERROR |
| SQLSTATE clase 22: representación de datos | 500 | DATABASE_DATA_ERROR |

Se registra categoría, SQLSTATE y tipo de excepción; el middleware incorpora
request_id. No se imprime SQL, parámetros, texto del driver, contraseñas, TOTP
ni claves. OpenAPI declara 409/500 junto a los fallos de persistencia.
Logout elimina cookies también ante las nuevas categorías de fallo.

Se observaron fallos intermitentes getaddrinfo (11001) al abrir conexiones nuevas
a Supabase. Los reintentos de lectura funcionaron. Eso es distinto del esquema
faltante: si vuelve a ocurrir, corresponde a DATABASE_UNAVAILABLE y debe
investigarse la resolución DNS/red del entorno; no está certificado como resuelto.

### 1.3 Eventos actuales de Stripe

Los eventos reales del pago usan API 2026-10-28.endive. Desde Basil, Stripe mueve:

- El período de suscripción a items.data[0].current_period_start/end.
- La referencia de suscripción de facturas a parent.subscription_details.subscription.

El receptor admite ambas formas y mantiene compatibilidad con 2024-06-20,
firma obligatoria e idempotencia por event_id. El producto admite un solo ítem
de suscripción, mensual o anual. Las peticiones salientes siguen fijadas a
2024-06-20.

Referencias oficiales:
[períodos por ítem](https://docs.stripe.com/changelog/basil/2025-03-31/deprecate-subscription-current-period-start-and-end),
[referencias parent de facturas](https://docs.stripe.com/changelog/basil/2025-03-31/adds-new-parent-field-to-invoicing-objects).

## 2. Estado persistido y referencias para dashboards

| Recurso | Identificador |
| --- | --- |
| Usuario local existente | c0674321-9a64-4f13-9070-e57dfb35b4e8 |
| Cuenta Alpaca sandbox | 9257e7d9-e70b-4898-a034-d3347e3b6ba3 |
| Banco local | 9798164c-cc5f-4806-9caf-4e441c7c1138 |
| Relación Alpaca | c5f5d43a-d950-4a74-bd1e-e4ccb59d538b |
| Depósito local | 056e9243-bac1-4726-a89c-8a8d0823d349 |
| Transferencia Alpaca | fb2ce7be-13c6-4ced-ab07-0f063200d819 |
| Suscripción local | c615b56a-3441-4d78-934c-d58205b0f4bd |
| Suscripción Stripe | sub_1UcBst06EEigZaInjAzAkvw3 |
| Factura Stripe | in_1UcBsu06EEigZaIn5S6df4VJ |
| Pago local | 4e577ceb-de38-4d55-bb05-cd1672b3c095 |

Stripe confirma suscripción active, cancel_at_period_end=true y factura paid,
1200 centavos USD. El período es del 2026-11-15 22:26:51 UTC al
2026-12-15 22:26:51 UTC. No se programarán renovaciones mediante esta suscripción
de prueba. Premium se conserva durante el período; su futura baja automática
depende de configurar la recepción de webhooks.

En el Broker Dashboard selecciona sandbox y la cuenta Alpaca de esta tabla.
Comprueba la relación bancaria y la transferencia por sus IDs externos.
El backend y el proveedor coincidían en SENT_TO_CLEARING, amount=1000.
No se encontró duplicado del depósito. No hay orden que buscar en Alpaca:
la creación HTTP no llegó a persistirla ni enviarla.

Las aserciones de solo lectura sobre Supabase y proveedores se incluyen en
e2e-database-evidence.json. Las respuestas HTTP con secretos redactados están
en e2e-http-evidence.json. e2e-stripe-replay-evidence.json identifica expresamente
el transporte controlado de eventos reales.

## 3. Guía reproducible en PowerShell

Ejecuta desde la raíz del repositorio. Usa **curl.exe**, no el alias curl de
Windows PowerShell. Los JSON se escriben sin BOM para evitar problemas de
comillas entre versiones de PowerShell.

### 3.1 Preparar y levantar la API

Las variables existentes se leen desde .env; el entorno del proceso tiene
prioridad. No copies claves de proveedores al frontend ni al reporte.

~~~powershell
uv run alembic current
uv run alembic upgrade head
uv run alembic current
uv run uvicorn acciones_ud.main:app --host 127.0.0.1 --port 8000
~~~

Esperado: revisión 0007_orders_schema y arranque sin errores de configuración.
Las migraciones ya están aplicadas en la base revisada; upgrade head será un
no-op si sigue apuntando a esa misma base.

En otra terminal:

~~~powershell
$base = "http://127.0.0.1:8000/api/v1"
$qaDir = Join-Path (Get-Location) ".cache/manual-e2e"
New-Item -ItemType Directory -Force -Path $qaDir | Out-Null

function New-JsonBody([string]$name, $body) {
    $file = Join-Path $qaDir ($name + ".json")
    [IO.File]::WriteAllText($file, ($body | ConvertTo-Json -Depth 12), [Text.UTF8Encoding]::new($false))
    return $file
}
~~~

La API autentica por **Cookie: access_token=JWT**, no por Authorization: Bearer.
Se probó Bearer solo y devuelve 401. No se añadió otro mecanismo de autenticación.
Estos comandos envían la cookie explícitamente para probar por HTTP local; para
navegador o producción usa HTTPS, pues las cookies son Secure y HttpOnly.

### 3.2 Login

Introduce la contraseña de prueba proporcionada mediante el prompt, sin guardarla
en este documento:

~~~powershell
$securePassword = Read-Host "Password de investor.ti@accionesud.com" -AsSecureString
$env:E2E_PASSWORD = [Net.NetworkCredential]::new("", $securePassword).Password
$loginFile = New-JsonBody "login" @{ email = "investor.ti@accionesud.com"; password = $env:E2E_PASSWORD }
curl.exe -sS -X POST "$base/auth/login" -H "Content-Type: application/json" --data-binary "@$loginFile" -o "$qaDir/login.response.json" -w "HTTP %{http_code}"
$login = Get-Content "$qaDir/login.response.json" -Raw | ConvertFrom-Json
~~~

Esperado 200:

~~~json
{
  "mfa_token": "TOKEN_DE_DESAFIO_DEVUELTO_POR_LA_API",
  "mfa_expires_at": "FECHA_ISO",
  "totp_enrollment": null
}
~~~

Todavía no existe una sesión autenticada completa.

### 3.3 TOTP dinámico y sesión

Introduce el secreto TOTP facilitado en el prompt. No hace falta utilizar
recovery codes ni volver a enrolar al usuario.

~~~powershell
$secureTotp = Read-Host "Secreto TOTP existente" -AsSecureString
$env:E2E_TOTP_SECRET = [Net.NetworkCredential]::new("", $secureTotp).Password
$code = uv run python -c "import os,pyotp; print(pyotp.TOTP(os.environ['E2E_TOTP_SECRET']).now())"
$mfaFile = New-JsonBody "mfa" @{ mfa_token = $login.mfa_token; code = $code.Trim() }
curl.exe -sS -X POST "$base/auth/mfa/verify" -H "Content-Type: application/json" --data-binary "@$mfaFile" -c "$qaDir/cookies.txt" -o "$qaDir/mfa.response.json" -w "HTTP %{http_code}"
$accessToken = ((Get-Content "$qaDir/cookies.txt" | Where-Object { $_ -match "\saccess_token\s" }) -split "\s+")[-1]
$refreshToken = ((Get-Content "$qaDir/cookies.txt" | Where-Object { $_ -match "\srefresh_token\s" }) -split "\s+")[-1]
$auth = "Cookie: access_token=$accessToken"
~~~

Esperado 200; el JSON contiene el usuario. Los JWT están en Set-Cookie, no en
el cuerpo de respuesta. Conserva los archivos solo durante esta prueba local.

Si se acaba de utilizar el mismo TOTP en otro login, espera al siguiente
intervalo del autenticador antes de repetirlo: existe protección contra replay.

### 3.4 Verificar identidad y cuenta de inversión

~~~powershell
curl.exe -sS "$base/users/me" -H "$auth" -w " HTTP %{http_code}"
curl.exe -sS "$base/kyc/status" -H "$auth" -w " HTTP %{http_code}"
~~~

Esperado: ambos 200, rol investor, MFA enrolado y cuenta ACTIVE/can_trade=true.
No llames a registro ni vuelvas a abrir una cuenta KYC.

### 3.5 Suscripciones: consulta y planes

~~~powershell
curl.exe -sS "$base/subscriptions/me" -H "$auth" -w " HTTP %{http_code}"
curl.exe -sS "$base/subscriptions/plans" -H "$auth" -w " HTTP %{http_code}"
~~~

Esperado: 200. Extracto válido de la consulta actual:

~~~json
{
  "subscription": {
    "id": "c615b56a-3441-4d78-934c-d58205b0f4bd",
    "plan": "monthly",
    "status": "active",
    "cancel_at_period_end": true
  },
  "next_charge_at": null
}
~~~

El cuerpo real incluye también períodos, plan, motivo y último pago.
Planes:

~~~json
[
  {"code":"monthly","price":"12.00","currency":"USD","interval":"month"},
  {"code":"annual","price":"120.00","currency":"USD","interval":"year"}
]
~~~

### 3.6 Checkout

~~~powershell
$checkoutFile = New-JsonBody "checkout" @{ plan = "monthly" }
curl.exe -sS -X POST "$base/subscriptions/checkout" -H "$auth" -H "Content-Type: application/json" --data-binary "@$checkoutFile" -w " HTTP %{http_code}"
~~~

**Con el estado actual de este investor, lo correcto es 409**:

~~~json
{"code":"SUBSCRIPTION_ALREADY_ACTIVE","message":"Subscription is already active.","details":null}
~~~

En el E2E, antes de contratar, esta llamada devolvió 201 con
checkout_session_id y url. Se abrió esa URL en Chrome, se eligió USD y tarjeta,
y se completó con 4242 4242 4242 4242, vencimiento 12/34 y CVC de prueba.
[Tarjetas oficiales de prueba](https://docs.stripe.com/testing).

La URL de éxito apunta al frontend local de puerto 3000. Como no había frontend
arrancado, el navegador mostró conexión rechazada tras pagar. La API de Stripe
confirmó status=complete y payment_status=paid; ese fallo de redirección no
revirtió el pago.

No cambies a mano la fila local a canceled para permitir otro checkout: la
suscripción externa seguiría activa y se perdería la coherencia.

### 3.7 Pagos y cancelación al final del período

~~~powershell
curl.exe -sS "$base/subscriptions/me/payments" -H "$auth" -w " HTTP %{http_code}"
curl.exe -sS "$base/subscriptions/me/payments/4e577ceb-de38-4d55-bb05-cd1672b3c095" -H "$auth" -w " HTTP %{http_code}"
$cancelFile = New-JsonBody "cancel-subscription" @{ reason = "Prueba sandbox de cancelacion al finalizar periodo" }
curl.exe -sS -X POST "$base/subscriptions/me/cancel" -H "$auth" -H "Content-Type: application/json" --data-binary "@$cancelFile" -w " HTTP %{http_code}"
~~~

Esperado: 200, pago amount=12.00/currency=USD/result=paid y
cancel_at_period_end=true. No significa cancelación inmediata ni devolución
del importe. El E2E ya dejó programada esta cancelación.

### 3.8 Webhooks: configurar entrega automática

La clave secreta de API no configura webhooks. La consulta a Stripe devolvió
cero endpoints registrados.

Para probar localmente con la **CLI oficial de Stripe**, inicia un listener
antes de generar eventos:

~~~powershell
stripe login
stripe listen --forward-to http://127.0.0.1:8000/api/v1/webhooks/stripe
~~~

Copia el whsec del listener a STRIPE_WEBHOOK_SECRET del proceso/.env usado por
la API y reiníciala. No mezcles el secreto del listener con el de otro endpoint.
Para despliegue estable registra la URL pública HTTPS de ese entorno y usa el
secreto de ese endpoint. Suscribe checkout.session.completed,
customer.subscription.created/updated/deleted, invoice.paid e invoice.payment_failed.

No copies un encabezado Stripe-Signature antiguo: la firma incluye un timestamp
y se comprueba una ventana temporal de 300 segundos.

En esta sesión se recuperaron cinco eventos **reales** de Stripe test y se
reprodujeron en el receptor local con una firma HMAC generada controladamente
con el secreto configurado. Se verificaron respuesta 200, persistencia y
duplicados. Esto valida el receptor y los efectos, **no prueba entrega
automática Stripe → servidor**. No se inventaron estados de factura o de
suscripción ni se actualizaron sus tablas manualmente.

[Webhooks de Stripe](https://docs.stripe.com/webhooks).

### 3.9 MOD-03: previsualización y creación de orden

Este paso requiere fondos disponibles; el depósito preparado en MOD-04 aún no
se había liquidado. Puedes consultar/previsualizar ahora; el camino positivo
requiere resolver fondeo y el presupuesto de respuesta indicado más abajo.

~~~powershell
curl.exe -sS "$base/markets/clock" -H "$auth" -w " HTTP %{http_code}"
$orderFile = New-JsonBody "order" @{ symbol = "AAPL"; side = "buy"; qty = "1"; type = "market"; order_class = "simple"; time_in_force = "day"; schedule_if_closed = $true; confirmed = $true }
curl.exe -sS -X POST "$base/orders/preview" -H "$auth" -H "Content-Type: application/json" --data-binary "@$orderFile" -w " HTTP %{http_code}"
$orderKey = "manual-order-" + (Get-Date -Format "yyyyMMddHHmmss")
curl.exe -sS -X POST "$base/orders" -H "$auth" -H "Content-Type: application/json" -H "Idempotency-Key: $orderKey" --data-binary "@$orderFile" -w " HTTP %{http_code}"
curl.exe -sS "$base/orders" -H "$auth" -w " HTTP %{http_code}"
~~~

Preview observado: 200, reference_price=356.4, estimated_amount=363.53,
reference_commission=7.13, available_buying_power=0, market_open=false y
scheduled_for=2026-11-16T09:30:00-05:00. Son valores de esa consulta, no precios
que deban repetirse.

La creación observada y su reintento con la misma clave dieron **502**:

~~~json
{
  "code":"ALPACA_UNAVAILABLE",
  "message":"Order response deadline exceeded; retry with the same Idempotency-Key.",
  "details":null
}
~~~

El presupuesto HTTP vigente es 5 s. Un perfil real de preview tardó 12.874 s:
cuenta 2.734, activo 2.275, cotización 2.834, controles 0.989, sesión 1.791,
próxima sesión 1.139, poder de compra 0.100 y trabajo restante de persistencia.
No se aumentó el plazo ni se falseó el mercado para presentar un resultado verde.

Una vez resueltos fondos y latencia, el resultado positivo esperado es 201 con
id, estado y reserva. En mercado cerrado sería PENDING con scheduled_for y sin
alpaca_order_id. No se ha verificado ese resultado en esta sesión.

Siempre reintenta con la **misma** clave después de un timeout y consulta el
listado; no asumas que un timeout implica ausencia de una operación.
La auditoría de esta sesión comprobó cero órdenes y cero reservas del usuario.

### 3.10 MOD-03: consultas y acciones sobre una orden existente

Solo después de obtener un ID real:

~~~powershell
$orderId = "UUID_DEVUELTO_POR_CREACION"
curl.exe -sS "$base/orders/$orderId" -H "$auth" -w " HTTP %{http_code}"
$cancelOrderFile = New-JsonBody "cancel-order" @{ reason = "input_error"; confirmed = $true }
curl.exe -sS -X POST "$base/orders/$orderId/cancel" -H "$auth" -H "Content-Type: application/json" --data-binary "@$cancelOrderFile" -w " HTTP %{http_code}"
~~~

Esperado condicional: 200 y reserva released para cancelación local; 202 si
debe esperar confirmación de Alpaca. Una ejecución podría ganar la carrera
contra una cancelación externa. Para ejecución completa, el modelo local usa
EXECUTING con fully_filled=true.

Estas acciones dependen del estado:

~~~powershell
$reauthFile = New-JsonBody "reauthorize" @{ decision = "accept" }
curl.exe -sS -X POST "$base/orders/$orderId/reauthorization" -H "$auth" -H "Content-Type: application/json" --data-binary "@$reauthFile" -w " HTTP %{http_code}"
$resubmitFile = New-JsonBody "resubmit" @{ qty = "1" }
curl.exe -sS -X POST "$base/orders/$orderId/resubmit" -H "$auth" -H "Content-Type: application/json" --data-binary "@$resubmitFile" -w " HTTP %{http_code}"
curl.exe -sS -X POST "$base/orders/$orderId/resume" -H "$auth" -w " HTTP %{http_code}"
curl.exe -sS "$base/broker/order-reviews" -H "$auth" -w " HTTP %{http_code}"
~~~

Reautorización requiere HELD y solicitud vigente; reenvío, devolución por
comisionista; reanudación, revisión por cambio de calendario. Fuera de esas
precondiciones se espera 409. Los recursos inexistentes dieron 404 en todas
las acciones probadas. El investor obtuvo 403 al consultar la cola de broker.

No se puede aprobar como broker usando este investor ni hay vinculación de
MOD-06 configurada. No se cambiaron sus roles para simular ese caso.

### 3.11 MOD-04: consultar banco, saldos, monedas y movimientos

~~~powershell
$bankId = "9798164c-cc5f-4806-9caf-4e441c7c1138"
$depositId = "056e9243-bac1-4726-a89c-8a8d0823d349"
curl.exe -sS "$base/wallet/balances" -H "$auth" -w " HTTP %{http_code}"
curl.exe -sS "$base/wallet/currencies" -H "$auth" -w " HTTP %{http_code}"
curl.exe -sS "$base/wallet/bank-relationships" -H "$auth" -w " HTTP %{http_code}"
curl.exe -sS "$base/wallet/bank-relationships/$bankId" -H "$auth" -w " HTTP %{http_code}"
curl.exe -sS "$base/wallet/transfers" -H "$auth" -w " HTTP %{http_code}"
curl.exe -sS "$base/wallet/transfers/$depositId" -H "$auth" -w " HTTP %{http_code}"
curl.exe -sS "$base/wallet/activities?types=FILL" -H "$auth" -w " HTTP %{http_code}"
~~~

Esperado: 200; banco APPROVED, depósito con estado almacenado y monedas USD /
conversion_supported=false. Consultar el **listado** de bancos refresca estados
desde Alpaca; el detalle consulta el registro local.

El banco de esta sesión se creó con este cuerpo sandbox:

~~~json
{
  "account_owner_name":"Prueba Ti",
  "bank_account_type":"CHECKING",
  "bank_account_number":"123456789",
  "bank_routing_number":"121000358"
}
~~~

El endpoint es POST /wallet/bank-relationships. Para reproducir la creación:

~~~powershell
$bankFile = New-JsonBody "bank" @{ account_owner_name = "Prueba Ti"; bank_account_type = "CHECKING"; bank_account_number = "123456789"; bank_routing_number = "121000358" }
curl.exe -sS -X POST "$base/wallet/bank-relationships" -H "$auth" -H "Content-Type: application/json" --data-binary "@$bankFile" -w " HTTP %{http_code}"
~~~

No necesitas repetirlo: ya existe un banco aprobado. El proveedor puede
rechazar otra relación activa. El resultado original fue 201; la persistencia
local conserva solo últimos cuatro dígitos y referencia externa.

### 3.12 MOD-04: depósito idempotente

Para comprobar el depósito existente **sin crear otro**, reutiliza su clave y
cuerpo exactos:

~~~powershell
$depositFile = New-JsonBody "deposit" @{ bank_relationship_id = $bankId; amount = "1000.00"; currency = "USD" }
curl.exe -sS -X POST "$base/wallet/deposits" -H "$auth" -H "Content-Type: application/json" -H "Idempotency-Key: e2e-20261115-deposit-001" --data-binary "@$depositFile" -w " HTTP %{http_code}"
~~~

Esperado: 201, mismo id 056e9243-bac1-4726-a89c-8a8d0823d349 y misma referencia
Alpaca. La clave en estado completed significa que la solicitud se registró;
**no significa que Alpaca haya liquidado el depósito**.

Para probar conflicto sin mover más fondos:

~~~powershell
$conflictFile = New-JsonBody "deposit-conflict" @{ bank_relationship_id = $bankId; amount = "1001.00"; currency = "USD" }
curl.exe -sS -X POST "$base/wallet/deposits" -H "$auth" -H "Content-Type: application/json" -H "Idempotency-Key: e2e-20261115-deposit-001" --data-binary "@$conflictFile" -w " HTTP %{http_code}"
~~~

Esperado 409:

~~~json
{"code":"IDEMPOTENCY_CONFLICT","message":"Idempotency conflict.","details":{"reason":"body_mismatch"}}
~~~

### 3.13 MOD-04: retiro

~~~powershell
$withdrawFile = New-JsonBody "withdraw" @{ bank_relationship_id = $bankId; amount = "1.00"; currency = "USD" }
$withdrawKey = "manual-withdraw-" + (Get-Date -Format "yyyyMMddHHmmss")
curl.exe -sS -X POST "$base/wallet/withdrawals" -H "$auth" -H "Content-Type: application/json" -H "Idempotency-Key: $withdrawKey" --data-binary "@$withdrawFile" -w " HTTP %{http_code}"
~~~

Con saldo retirable cero se observó 422:

~~~json
{"code":"INSUFFICIENT_FUNDS","message":"Insufficient withdrawable funds.","details":{"cash_withdrawable":"0"}}
~~~

Con fondos retirables suficientes, se espera 201 y una transferencia OUTGOING,
pero ese camino positivo no se pudo validar. No uses cash o buying_power como
sustituto de cash_withdrawable.

### 3.14 Controles y notificaciones

~~~powershell
curl.exe -sS "$base/users/preferences/orders" -H "$auth" -w " HTTP %{http_code}"
$controlsFile = New-JsonBody "controls" @{ default_order_type = "market"; daily_order_limit = 50; high_order_threshold_usd = "10000.00"; extra_confirmation = $true }
curl.exe -sS -X PUT "$base/users/preferences/orders" -H "$auth" -H "Content-Type: application/json" --data-binary "@$controlsFile" -w " HTTP %{http_code}"
curl.exe -sS "$base/users/preferences/channels" -H "$auth" -w " HTTP %{http_code}"
curl.exe -sS "$base/notifications" -H "$auth" -w " HTTP %{http_code}"
~~~

El PUT mantuvo los controles anteriores y respondió 200. Las nuevas preferencias
in_app están habilitadas. No se espera aviso de depósito completado mientras
permanezca SENT_TO_CLEARING.

### 3.15 Renovar sesión y salir

Si el access token expira durante las pruebas:

~~~powershell
curl.exe -sS -X POST "$base/auth/refresh" -H "Cookie: refresh_token=$refreshToken" -c "$qaDir/cookies.txt" -w " HTTP %{http_code}"
$accessToken = ((Get-Content "$qaDir/cookies.txt" | Where-Object { $_ -match "\saccess_token\s" }) -split "\s+")[-1]
$refreshToken = ((Get-Content "$qaDir/cookies.txt" | Where-Object { $_ -match "\srefresh_token\s" }) -split "\s+")[-1]
$auth = "Cookie: access_token=$accessToken"
~~~

Esperado: 200 y nuevas expiraciones. Para cerrar esta sesión:

~~~powershell
curl.exe -sS -X POST "$base/auth/logout" -H "Cookie: access_token=$accessToken; refresh_token=$refreshToken" -w " HTTP %{http_code}"
Remove-Item Env:E2E_PASSWORD,Env:E2E_TOTP_SECRET -ErrorAction SilentlyContinue
Get-ChildItem -LiteralPath $qaDir -File | Remove-Item
~~~

Esperado: 204 sin cuerpo y cookies borradas. Después, usar ese access token debe
devolver 401 porque su sesión fue revocada.

## 4. Comprobaciones SQL reproducibles en Supabase

Ejecuta en SQL Editor con permisos administrativos de lectura. No cambies
estados, saldos o flags para forzar el éxito.

~~~sql
select version_num from alembic_version;

select event_type, count(*) as channels
from notification_preferences
where user_id = 'c0674321-9a64-4f13-9070-e57dfb35b4e8'
group by event_type order by event_type;

select id, alpaca_relationship_id, account_last4, status
from wallet_bank_relationships
where user_id = 'c0674321-9a64-4f13-9070-e57dfb35b4e8';

select id, alpaca_transfer_id, amount, currency, direction, status
from wallet_transfers
where user_id = 'c0674321-9a64-4f13-9070-e57dfb35b4e8';

select state, transfer_id
from wallet_idempotency_keys
where user_id = 'c0674321-9a64-4f13-9070-e57dfb35b4e8';

select id, stripe_subscription_id, plan, status,
       current_period_start, current_period_end, cancel_at_period_end
from subscriptions
where user_id = 'c0674321-9a64-4f13-9070-e57dfb35b4e8';

select stripe_invoice_id, count(*) as records, sum(amount) as amount
from subscription_payments
where user_id = 'c0674321-9a64-4f13-9070-e57dfb35b4e8'
group by stripe_invoice_id;

select id, status, alpaca_order_id, filled_qty, fully_filled
from orders
where user_id = 'c0674321-9a64-4f13-9070-e57dfb35b4e8';

select order_id, status, amount
from order_reservations
where user_id = 'c0674321-9a64-4f13-9070-e57dfb35b4e8';
~~~

Resultados auditados: 10 eventos × 4 canales, 1 banco, 1 transferencia USD 1000,
1 clave completed, 1 suscripción active con cancelación programada, 1 factura
paid USD 12, 5 eventos Stripe únicos, 0 órdenes y 0 reservas.

## 5. Validación automática y archivos

~~~powershell
uv --cache-dir .cache/uv run --no-sync ruff check .
uv --cache-dir .cache/uv run --no-sync mypy src
uv --cache-dir .cache/uv run --no-sync pytest -q
uv --cache-dir .cache/uv run --no-sync python -m compileall -q src migrations
uv --cache-dir .cache/uv build --offline --out-dir dist
~~~

Resultado: Ruff correcto, Mypy correcto (240 archivos), **467 passed,
20 skipped**, compilación y wheel/sdist correctos. Persiste el aviso previo
de Starlette/httpx. Las 20 omitidas requieren TEST_DATABASE_URL desechable.
No se apuntó la suite destructiva de migraciones a la base compartida.

Se validó también la sintaxis de los 21 bloques PowerShell de esta guía: cero
errores de análisis. Se conservaron 64 solicitudes HTTP redactadas y se revisó
que los entregables no incluyan claves reales, JWT, contraseña ni secreto TOTP.

Cambios de producción:

- migrations/versions/0002_initial_admin.py: snapshot del bootstrap.
- migrations/versions/0006_wallet_schema.py y 0007_orders_schema.py: CHECK y seeds.
- shared/domain/errors.py y shared/infrastructure/db.py: categorías y log seguro.
- shared/infrastructure/http_errors.py: contrato de errores.
- identity/adapters/inbound/http/routers/sessions.py: limpieza de cookies.
- wallet/application/stripe_webhook_service.py: compatibilidad de snapshots Stripe.

Pruebas nuevas: test_database_error_classification.py,
test_bootstrap_vocabulary.py y test_modern_stripe_events.py.
Se actualizaron las pruebas de migraciones, contrato OpenAPI y rollback de FK
para reflejar el código DATABASE_INTEGRITY_ERROR.

Requisitos/diseños/tasks de ambos specs documentan la estabilización y dejan
pendientes explícitos los casos externos y de rendimiento sin verificar.

## 6. Pendientes para aprobar el E2E completo

1. Registrar/configurar entrega automática de Stripe con el secreto correcto.
   La futura expiración de premium depende de esos eventos.
2. Resolver con Alpaca el depósito SENT_TO_CLEARING; se comprobó directamente
   en el proveedor, no es una discrepancia de la tabla local. La cuenta tenía
   allow_instant_ach=false. No se atribuye una causa definitiva a ese flag.
3. Resolver la latencia de validación/BD respecto al presupuesto HTTP de 5 s.
   No se ha corregido ni certificado ese requisito de rendimiento.
4. Con fondos disponibles, validar creación, reserva, cancelación local y luego
   envío/ejecución FILL durante una sesión de mercado.
5. Probar retiro positivo y notificaciones de saldo tras liquidación.
6. Validar revisión real por broker cuando exista la vinculación de MOD-06.
7. Investigar los fallos DNS intermitentes si se reproducen en el entorno habitual.

La documentación de Alpaca describe fondeo sandbox inmediato, pero la respuesta
real de esta cuenta permaneció en SENT_TO_CLEARING con saldo cero; el reporte
conserva esa evidencia y no da por cumplida la liquidación:
[Transfer API](https://docs.alpaca.markets/us/reference/createtransferforaccount).

