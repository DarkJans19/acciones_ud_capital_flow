# 5. MOD-04: fondos virtuales y suscripciones

[Índice](README.md) · [Anterior](04-ordenes.md) · [Siguiente](06-portafolio.md)

**Paquete:** `src/acciones_ud/wallet/`.  
**Trazabilidad:** RF-10..12, RF-36..40, RFP-11;
[requisitos](../wallet-mod-04/requirements.md), [diseño](../wallet-mod-04/design.md).

## 5.1 Dos circuitos económicos separados

Wallet reúne dos capacidades con proveedores diferentes:

| Circuito | Proveedor | Qué representa |
| --- | --- | --- |
| Saldos, ACH y movimientos bursátiles | Alpaca sandbox | Fondos virtuales de la cuenta de inversión |
| Plan mensual/anual y pagos | Stripe test | Suscripción premium de la plataforma |

Pagar premium no deposita buying power en Alpaca. Un depósito virtual tampoco
contrata una suscripción. No existe cambio de divisas ni liquidación de
comisiones oficiales a través de estos endpoints.

## 5.2 Consulta de saldos

`WalletService` exige cuenta enlazada y consulta trading account de Alpaca.
Devuelve moneda, efectivo, efectivo retirable, buying power, equity, valor de
portafolio y valor de posiciones largas.

Estos campos **no son intercambiables**: para retirar se comprueba
`cash_withdrawable`, no cash ni buying power. Para una compra se utiliza buying
power mediante el puerto que consume orders.

Los valores se mantienen como cadenas decimales sin convertir a float ni
redondear la respuesta original. Si falla el proveedor o se agota el presupuesto,
la consulta de saldos puede devolver `unavailable=true` e importes nulos; no
pone saldos a cero.

Actualizar el estado local de cuenta tras una lectura es un efecto secundario
best-effort: un fallo al guardarlo no descarta el saldo externo recién leído.
Esto no se generaliza a escrituras financieras, que sí necesitan persistencia.

## 5.3 Relaciones bancarias de prueba

`FundingService.create_bank_relationship` exige cuenta activa y valida:

- Titular no vacío de hasta 200 caracteres.
- Tipo `CHECKING` o `SAVINGS`.
- Número de cuenta de 4..17 dígitos.
- Routing number de nueve dígitos.

Envía esos datos a Alpaca y guarda identificador externo, propietario, tipo,
últimos cuatro dígitos y estado. No almacena el número completo en la tabla.
Listar puede refrescar estados del proveedor; el detalle local no constituye
por sí mismo una nueva aprobación bancaria.

Al consultar una relación ajena devuelve 404 igual que una inexistente. Al usar
una en un depósito/retiro, si no es propia o no está `APPROVED`, devuelve 409
`BANK_RELATIONSHIP_NOT_USABLE`.

**Por qué cambia el error:** una consulta de recurso expresa existencia/propiedad;
una operación expresa si un medio de financiación es utilizable, sin revelar
quién es dueño de una relación ajena.

## 5.4 Depósitos y retiros

La entrada contiene `bank_relationship_id`, `amount` como string y moneda `USD`.
Se exige importe finito con hasta dos decimales, al menos USD 1,00 y como máximo
`WALLET_MAX_TRANSFER_AMOUNT`, por defecto 50 000,00.

```text
INCOMING = depósito
OUTGOING = retiro
```

El flujo:

1. Valida importe, moneda, dirección e `Idempotency-Key`.
2. Bloquea usuario, verifica clave previa, cuenta y relación bancaria.
3. Reserva la clave como `in_progress` y confirma.
4. En retiro, lee cash_withdrawable y rechaza si es insuficiente.
5. Solicita transferencia a Alpaca.
6. Guarda transferencia y completa la clave en otra transacción.

La clave tiene espacio por usuario y digest canónico de dirección, relación,
importe y moneda. Una repetición completada con mismo cuerpo devuelve la
transferencia original; cuerpo distinto o intento todavía en progreso da 409.

**Diferencia con órdenes:** no se dispone aquí del mismo mecanismo automático de
recuperación por client order ID. Ante fallo externo ambiguo se conserva
`in_progress` para no crear otra transferencia con un reintento ciego.
Un rechazo explícito o ciertos errores anteriores al POST liberan la clave.

Si Alpaca creó la transferencia y el proceso cayó antes de persistirla, puede
faltar localmente mientras la clave sigue bloqueada. Se requiere investigación
operativa; borrar la reserva sin verificar el proveedor podría duplicar el
movimiento.

Las respuestas incluyen aviso de sandbox: no representan dinero real.

## 5.5 Reconciliación de transferencias y actividades

`TransferReconciler` corre normalmente cada 60 s. Agrupa cuentas, consulta
transferencias y aplica una actualización solo si:

- El estado almacenado no es terminal.
- `updated_at` externo es estrictamente posterior al conocido.

Los terminales incluyen COMPLETE, CANCELED, RETURNED y REJECTED. No se valida una
máquina rígida de todos los pasos intermedios; se respeta el estado que reporta
Alpaca con el guard temporal.

**Limitación intencional:** COMPLETE se considera terminal, por lo que un RETURNED
posterior no revierte ese registro. Es un límite del alcance sandbox, no un
modelo completo de devoluciones bancarias reales.

El reconciliador consume actividades con cursor por cuenta y deduplica avisos
mediante `wallet_balance_notifications`:

- Transferencia que llegó a COMPLETE, incluso si se guardó así inicialmente.
- Actividad FILL nueva.

El primer cursor de actividades parte del momento inicial para no enviar una
oleada de avisos de operaciones antiguas. La API de actividades y el historial
local de transferencias son vistas diferentes.

El marcador del aviso se confirma antes de notificar: evita duplicados por
repetición, pero una caída puede perder el aviso. Es una estrategia **como máximo
una vez**, no entrega garantizada.

## 5.6 Planes y Checkout

`domain/subscriptions.py` define planes de prueba:

| Plan | Precio mostrado | Intervalo |
| --- | --- | --- |
| `monthly` | USD 12,00 | Mes |
| `annual` | USD 120,00 | Año |

Los IDs de Price llegan del entorno. La configuración debe apuntar a productos
Stripe coherentes con esos precios; mostrar un catálogo local no modifica la
cuenta Stripe.

`SubscriptionService.start_checkout` verifica que no haya suscripción actual
active/trialing/past_due, crea sesión Checkout y guarda `pending_checkout`.
Devuelve ID y URL para redirigir al usuario. El navegador nunca entrega tarjeta
al backend de Acciones UD.

**La URL de éxito no concede premium.** La activación depende del webhook
verificado. Un usuario puede visitar una URL manualmente; eso no prueba un pago.

La cancelación solicita `cancel_at_period_end=true` y conserva motivo/fecha.
No convierte de inmediato una suscripción activa en cancelada; el webhook
posterior refleja el estado autoritativo.

**Excepción arquitectónica real:** las llamadas a Stripe de crear Checkout y
cancelar se ejecutan dentro de la unidad de trabajo con lock de usuario.
Serializa la secuencia, pero prolonga la transacción durante I/O externo. No debe
describirse el repositorio como si absolutamente toda llamada externa ocurriera
fuera de transacciones. Además, `pending_checkout` no forma parte de `CURRENT`:
el lock no implica que nunca puedan existir varios checkouts pendientes.

## 5.7 Webhook Stripe: autenticidad y aplicación

`POST /api/v1/webhooks/stripe` no exige cookies de usuario; exige firma externa.
Recibe cuerpo **crudo** antes de parsear JSON.

1. Verifica `Stripe-Signature` con HMAC-SHA256 sobre `timestamp + "." + body`.
2. Usa comparación de tiempo constante y tolerancia de 300 s.
3. Reserva el `event_id` mediante inserción idempotente.
4. Aplica suscripción, pago e `is_premium` en la misma transacción.
5. Responde 200 en duplicados sin repetir efectos.

Una firma inválida produce 400 sin modificar estado. Si la transacción falla,
registro y efectos revierten; Stripe puede reintentar. No se debe responder
éxito tras perder cambios que todavía debían aplicarse.

Eventos atendidos:

```text
checkout.session.completed
customer.subscription.created
customer.subscription.updated
customer.subscription.deleted
invoice.paid
invoice.payment_failed
```

El cliente fija `Stripe-Version: 2024-06-20`; el parser además tolera estructuras
modernas observadas en sandbox, con periodos en `items.data[0]` y referencia de
suscripción de factura en `parent.subscription_details`.

Si Checkout solo trae el ID de suscripción, el handler consulta a Stripe para
obtener el estado autoritativo. Esa lectura también ocurre dentro de la unidad
de trabajo del webhook: puede prolongar el lock de usuario; si falla, no debe
confundirse con un evento completamente aplicado. El evento y sus efectos
locales siguen sujetos a rollback.

## 5.8 Asociación, desorden y cambios de premium

La firma demuestra procedencia, pero no a qué usuario local debe aplicarse:
también se exige asociación con la suscripción/Checkout almacenado.
Cuando eventos iniciales se adelantan al checkout completado, la metadata
firmada solo permite enlazar si hay exactamente un checkout pendiente del usuario.
Eventos no asociados se registran sin cambiar premium.

Se conserva `stripe_event_created_at`; un evento anterior al aplicado no hace
retroceder la suscripción.

| Estado de suscripción | Efecto sobre `is_premium` |
| --- | --- |
| `active`, `trialing` | Habilitar |
| `canceled`, `unpaid`, `incomplete_expired` | Deshabilitar |
| Otros, incluido `past_due` | Conservar valor previo |

El handler aplica el efecto cuando cambia el estado de la suscripción; no
reescribe incondicionalmente el flag en cada evento recibido.

El pago se identifica por factura. Si una factura fallida se paga después, se
actualiza el mismo Payment; un fallo retrasado no revierte un pago confirmado.
El lector `contracted_plan_reader` permite a identity mostrar el plan sin importar
Stripe desde su aplicación.

Existe además gestión administrativa del flag premium en identity; por eso
`is_premium` no debe asumirse siempre como deducción de una sola fila Stripe.

## 5.9 Implementación y pruebas

| Componente | Función |
| --- | --- |
| `application/wallet_service.py` | Saldos, moneda y actividades |
| `application/funding_service.py` | Banco, depósitos y retiros |
| `application/transfer_reconciler.py` | Estados externos y avisos deduplicados |
| `application/subscription_service.py` | Planes, Checkout, cancelación y pagos |
| `application/stripe_webhook_service.py` | Firma, asociación y efectos idempotentes |
| `adapters/outbound/persistence/unit_of_work.py` | Repositorios y transacciones tipadas |
| `adapters/outbound/stripe/stripe_client.py` | REST con HTTPX, sin SDK Stripe |

Se eligió HTTPX para compartir estrategia con Alpaca, controlar el contrato
enviado y probar respuestas sin red. El costo es mantener parseo y compatibilidad
de versiones explícitamente.

Las pruebas de `tests/wallet/property/` cubren importes, retiro, idempotencia,
estados y firma. `unit/test_modern_stripe_events.py`, `test_invoice_lifecycle.py`
y `test_reconciler.py` cubren escenarios no felices concretos.
