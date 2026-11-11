# Constitución de Acciones UD

## 1. Fidelidad al dominio

Las reglas de negocio se expresan en el dominio o en casos de uso, no en
routers, modelos ORM ni proveedores externos. El catálogo unificado actualizado
es la fuente funcional principal y el SAD complementa atributos de calidad y
decisiones abiertas. Los asuntos pendientes se documentan antes de implementarse.

## 2. Dependencias hacia adentro

Los módulos internos dependen de abstracciones propias. FastAPI, SQLAlchemy,
Supabase PostgreSQL, Stripe y Alpaca son decisiones de infraestructura que se
mantienen detrás de adaptadores. Elegir Supabase como base de datos no autoriza
por sí mismo el uso de Supabase Auth, Realtime ni Data API.

## 3. Seguridad y trazabilidad

El acceso se diseña con mínimo privilegio, separación por rol, protección de
secretos y auditoría de eventos relevantes. Nunca se registran contraseñas,
tokens ni datos sensibles en logs.

## 4. Contratos verificables

Cada spec debe definir alcance, actores, escenarios, errores y criterios de
aceptación. Los contratos HTTP y eventos se versionan deliberadamente y las
pruebas deben cubrir el comportamiento observable.

## 5. Monolito modular como arquitectura objetivo

La solución se diseña, implementa y despliega como un único monolito modular con
arquitectura hexagonal. Los límites entre módulos existen para proteger reglas de
negocio, contratos y mantenibilidad dentro del monolito; no se diseñan como paso
previo a extraer microservicios. La división en servicios independientes no forma
parte del alcance ni de la evolución prevista del proyecto.

## 6. Calidad operativa

Los cambios deben mantener tipado, validación, observabilidad, migraciones
reproducibles y pruebas automatizadas. Los fallos no se silencian ni se
convierten en respuestas exitosas.
