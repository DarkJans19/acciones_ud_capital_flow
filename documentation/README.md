# Documentación de Acciones UD Capital Flow

## Guía completa del programa

La **[guía del sistema](../.kiro/specs/guia-del-sistema/README.md)** explica el
funcionamiento real del backend, sus siete módulos, arquitectura, tecnologías,
reglas de negocio, integraciones, decisiones y límites.

El contenido explicativo se conserva en `.kiro/specs/`, la base documental del
equipo. Esta página permite acceder a él desde `documentation/` sin mantener dos
copias que puedan divergir.

| Lectura | Contenido |
| --- | --- |
| [Visión general y arquitectura](../.kiro/specs/guia-del-sistema/01-arquitectura.md) | Qué resuelve el programa, capas, dependencias, arranque y tecnologías |
| [Identidad y seguridad](../.kiro/specs/guia-del-sistema/02-identidad.md) | Registro, MFA, sesiones, roles, perfil, preferencias y KYC |
| [Mercado](../.kiro/specs/guia-del-sistema/03-mercado.md) | Catálogo, cotizaciones, históricos, calendario, alertas y streaming |
| [Órdenes](../.kiro/specs/guia-del-sistema/04-ordenes.md) | Validación, reservas, revisión, envío, reconciliación y cancelación |
| [Fondos y suscripciones](../.kiro/specs/guia-del-sistema/05-fondos-suscripciones.md) | Saldos, ACH de prueba, Stripe, pagos y premium |
| [Portafolio](../.kiro/specs/guia-del-sistema/06-portafolio.md) | Posiciones, resultados, estadísticas, riesgo y reportes |
| [Comisionistas](../.kiro/specs/guia-del-sistema/07-comisionistas.md) | Vínculos, consentimientos, propuestas, mensajes y reputación |
| [Administración](../.kiro/specs/guia-del-sistema/08-administracion.md) | Tarifas, comisiones, controles, auditoría, compliance y KPI |
| [Estrategias transversales](../.kiro/specs/guia-del-sistema/09-estrategias-datos.md) | Persistencia, concurrencia, idempotencia, precisión, errores y decisiones |
| [Operación y pruebas](../.kiro/specs/guia-del-sistema/10-operacion-pruebas.md) | Configuración, ejecución, Docker, migraciones, validación y diagnóstico |
| [API y recorridos completos](../.kiro/specs/guia-del-sistema/11-api-flujos.md) | Inventario de operaciones, contratos e integración entre módulos |

## Evidencias existentes

- [Auditoría transversal del 24/11/2026](auditoria-e2e-2026-11-24/README.md):
  resultados y defectos abiertos; no equivale a certificación de producción.
- [E2E de administración](mod-07/E2E_MODULO_07.md): pruebas específicas de MOD-07.

Las evidencias describen una ejecución concreta. Los requisitos y decisiones
funcionales se consultan en los specs enlazados desde la guía.
