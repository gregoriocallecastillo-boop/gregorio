# Demostración pública

Enlace: https://nexo-inventario-python.onrender.com/demo/

El visitante pulsa **Entrar como invitado**. No necesita contraseña ni una cuenta.
La aplicación conserva su interfaz y muestra los 12 módulos. El selector superior
permite probar las vistas de administrador y empleado; **Reiniciar demo** recupera
los datos iniciales, previa confirmación.

## Alcance

- Productos, fotos, contactos y almacenes de ejemplo editables.
- Compras, ventas, ajustes, traslados, cobros parciales, reembolsos y devoluciones.
- Facturas y notas de crédito PDF marcadas como demostración, CSV y reportes.
- Integrantes y permisos ficticios: no se crean cuentas de autenticación reales.
- Un negocio por visitante, 100 operaciones por reinicio, 40 productos,
  20 contactos/almacenes, 12 integrantes, 512 KB por prueba y duración de 24 horas.
- No hay envío de correos, cobro de tarjetas ni emisión fiscal electrónica.

## Aislamiento

`core.demo` guarda exclusivamente una instantánea JSON en `DemoSandbox`, dentro
de PostgreSQL. No escribe en Business, User, Membership, Product ni en las tablas
de operaciones reales. El motor de prueba reproduce los flujos de la interfaz;
el sistema real sigue utilizando sus servicios transaccionales y sus modelos.
Las modificaciones a reglas comerciales deben mantener ambos flujos coherentes.

Cada navegador recibe un token aleatorio de 256 bits en una cookie separada,
HttpOnly, Secure en producción, SameSite=Lax y limitada a `/demo/`. En la base de
datos solo se guarda su SHA-256. El acceso de propietario permanece intacto.
Todas las escrituras requieren CSRF. Los bloqueos de fila evitan perder cambios
simultáneos y las claves de idempotencia evitan duplicar ventas, devoluciones y
cobros al reintentar. Un error revierte por completo la operación.

Se admiten hasta 200 pruebas activas. Un bloqueo transaccional serializa la
admisión y limpia las pruebas vencidas al entrar nuevos visitantes. Al salir de
la demo se elimina esa prueba. Reiniciar solo sustituye su instantánea: nunca
borra historial de un negocio real. Si no hay visitas nuevas, pueden permanecer
instantáneas vencidas hasta la siguiente entrada; ya no son accesibles.

## Verificación

`python manage.py test core.tests` ejecuta las pruebas del sistema y de la demo:
aislamiento, CSRF, preservación de sesión del propietario, permisos directos,
operaciones atómicas, reintentos, PDF, CSV, fotos, impuestos, expiración y ventas
simultáneas en PostgreSQL nativo. El motor PGlite local omite las dos pruebas de
concurrencia, que sí se ejecutan en GitHub Actions con PostgreSQL 17.
