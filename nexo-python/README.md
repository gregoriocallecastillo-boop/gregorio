# Nexo · Python + PostgreSQL

Aplicación web de inventario y facturación para pequeños negocios. Servidor Django/Python, base relacional PostgreSQL y una interfaz propia en HTML, CSS y JavaScript que conserva la barra lateral verde oscura, paneles claros y acentos esmeralda de la propuesta visual.

## Desplegar en Render

[Activar Nexo en Render](https://render.com/deploy?repo=https://github.com/gregoriocallecastillo-boop/gregorio/tree/nexo-render)

Elige una contraseña de administrador en `NEXO_BOOTSTRAP_PASSWORD` y aplica el Blueprint.
Usuario inicial: `gregorio`. Ambos recursos usan el plan gratuito. La base de prueba
creada el 7 de septiembre de 2026 vence el 7 de octubre de 2026.
Consulta **docs/RENDER.md** para los pasos de inicio y el negocio de ejemplo.

## Qué incluye

1. Inicio de sesión, cierre de sesión, cambio de contraseña y protección contra intentos repetidos.
2. Resumen del negocio con cifras reales y alertas de reposición.
3. Productos con código único, categoría, unidad, precio, existencia mínima, fecha de vencimiento y foto.
4. Compras con costo promedio ponderado.
5. Ventas con catálogo visual, cantidades fraccionarias y facturación automática.
6. Facturas numeradas, PDF imprimible, impuesto general configurable y vencimiento de pago.
7. Cobros parciales, saldo pendiente y registro de anulaciones/reembolsos ya realizados.
8. Devolución completa de una venta con restitución de existencias y nota de crédito.
9. Movimientos de inventario y ajustes con motivo obligatorio.
10. Varios almacenes y traslados entre ubicaciones.
11. Proveedores y clientes.
12. Reportes de ventas, margen bruto, existencias y cuentas por cobrar.
13. Equipo con acceso de administrador o empleado por negocio.
14. Bitácora de cambios y exportaciones CSV.
15. Negocios separados y configuración del emisor.

Las fotos se validan y convierten a JPEG antes de guardarse en PostgreSQL. No dependen de servicios de imágenes externos.

## Empezar en una computadora

Requisitos: Docker Engine con Docker Compose v2 (o Docker Desktop) y Python 3 para generar la configuración. Para una instalación sin Docker se necesita Python 3.12 y un servidor PostgreSQL compatible con Django 5.2.

Desde la carpeta del proyecto:

```bash
python scripts/configure.py
docker compose up --build -d
docker compose exec web python manage.py bootstrap
```

El último comando solicita el usuario y una contraseña de al menos 12 caracteres, sin imprimirla. No se incluye una cuenta universal ni una contraseña predeterminada.

Abre **http://localhost:8000** en esa computadora. Este domicilio local no se abre desde otro dispositivo. La configuración inicial escucha solo en la computadora local.

Opcional: crear un negocio de ejemplo separado, reemplazando MI_USUARIO por tu usuario real:

```bash
docker compose exec web python manage.py seed_demo --username MI_USUARIO
```

No mezcles datos ficticios con una operación real. El ejemplo tiene nombres y cifras de demostración.

## Para usarlo desde celular y varias computadoras

Desplegar en un servicio que ejecute contenedores/Python y conectar PostgreSQL. El alojamiento del prototipo anterior de Sites no ejecuta este servidor Django. El proyecto incluye Dockerfile y una comprobación `/health/` que valida acceso a la base.

Configuración mínima en el servidor:

- `DATABASE_URL`: conexión privada a PostgreSQL; agregar `sslmode=require` si el proveedor lo requiere.
- `SECRET_KEY`: valor aleatorio largo exclusivo del servidor.
- `DEBUG=0`.
- `ALLOWED_HOSTS`: nombre de dominio exacto, sin protocolo.
- `CSRF_TRUSTED_ORIGINS`: origen HTTPS completo.
- `TIME_ZONE`: zona horaria del negocio/servidor; inicialmente America/Chicago.
- `TRUST_PROXY=1` solo si se controla un proxy que elimine y sobrescriba la cabecera de protocolo.

Configurar HTTPS y copias de seguridad. Crear la primera cuenta con el comando interactivo `bootstrap`. No publicar una contraseña de administrador como variable en el código o en el repositorio. El Dockerfile usa un usuario sin privilegios y Gunicorn; la base no se expone con un puerto público en Compose.

La instalación local usa `DEBUG=1` para HTTP local. **No usar esa configuración en internet.** El inicio aplica migraciones antes de arrancar; para varias réplicas, ejecutar migraciones una sola vez en la etapa de despliegue y arrancar las demás con Gunicorn directamente.

## Pruebas

Con PostgreSQL nativo y la instalación Docker iniciada:

```bash
docker compose exec web python manage.py test core.tests --verbosity 2
```

Django crea una base de pruebas independiente con prefijo `test_`; la cuenta debe tener permiso `CREATEDB` en el entorno de pruebas. No usar credenciales de producción para ese comando.

La entrega incluye pruebas de cantidades, costo promedio, impuestos, idempotencia, permisos, aislamiento entre negocios, pagos parciales, devoluciones, PDF, bloqueo de existencias negativas y una prueba simultánea de dos vendedores.

Consulta **docs/VERIFICACION.md** para distinguir las pruebas ejecutadas en este entorno de las pendientes en el servidor definitivo.

## Copias y recuperación

```bash
python scripts/backup.py
```

Produce una copia completa PostgreSQL en `backups/`, incluyendo usuarios, fotos, movimientos, documentos y permisos. Copia esos archivos a un almacenamiento seguro fuera del servidor y programa el respaldo según el volumen de operaciones.

Para comprobar una copia sin sobrescribir la base activa:

```bash
python scripts/restore.py backups/MI_COPIA.dump nexo_restore_revision
```

Se crea una base **nueva**. Si ese nombre ya existe, el comando falla y no sobrescribe nada. Verifica saldos, usuarios, fotos y facturas antes de cambiar la conexión. Las exportaciones CSV sirven para consulta; no sustituyen la copia completa de PostgreSQL.

## Límites funcionales de esta entrega

- Facturación comercial: sin timbrado, firma ni autorización electrónica de SRI/SAT u otra autoridad. Hay que definir país, régimen e integración antes de afirmar validez fiscal.
- Un impuesto porcentual general por negocio, aplicado a compras y ventas nuevas. No incluye reglas de exenciones, retenciones ni múltiples impuestos por producto.
- Una moneda por negocio; no hace conversión de divisas.
- Los cobros son registros de pagos recibidos. No se cobra una tarjeta ni se realiza un reembolso bancario desde Nexo.
- Devoluciones de ventas completas; no hay devoluciones parciales ni devolución de compras. Las correcciones de cantidades de compras se registran como ajustes con motivo.
- Una fecha de vencimiento por producto, sin lotes/series/recetas. El stock se separa por almacén, con costo promedio global del producto.
- El mínimo se compara con la cantidad total del producto. No hay alertas por almacén ni notificaciones automáticas por correo.
- No incluye contabilidad de doble partida, nómina, caja por turnos, importación masiva ni recuperación de contraseña por correo.
- El administrador inicial puede recuperar una cuenta desde el servidor mediante `python manage.py changepassword USUARIO`.
- Interfaz muestra hasta 250 documentos recientes y 150 eventos. Reportes y CSV usan el historial completo. Períodos de reportes limitados a 366 días por consulta.
- El catálogo se carga completo; orientado a pequeños negocios. No se han medido cargas de cientos de miles de productos ni muchos usuarios simultáneos.
- No se han migrado datos del prototipo anterior ni se ha modificado su enlace.

## Diseño de consistencia y permisos

Las operaciones se validan en Python y se guardan dentro de una transacción. Se bloquea la fila del negocio antes de aplicar movimientos, numerar documentos o registrar cobros; esto serializa operaciones de un negocio y evita pérdidas de actualizaciones. El diseño prioriza consistencia para negocios pequeños frente a la máxima concurrencia por empresa.

Claves de idempotencia evitan duplicados al reenviar exactamente una solicitud. Si se cambia el contenido de una referencia ya usada, se rechaza. Los importes usan Decimal y redondeo comercial; las existencias usan tres decimales y el costo promedio cuatro.

Las existencias negativas y códigos duplicados se rechazan también en PostgreSQL. Facturas, renglones, movimientos y bitácora tienen protección contra modificación/borrado mediante disparadores de base de datos. Las correcciones de ventas se realizan con una operación compensatoria. El documento original y sus datos históricos se mantienen.

## Referencias de implementación

Se adoptaron principios, no se copió código de terceros:

- [InvenTree: arquitectura Python/Django](https://github.com/inventree/InvenTree): separación entre interfaz, reglas del negocio y persistencia.
- [InvenTree: permisos](https://docs.inventree.org/en/1.3.x/settings/permissions/): roles con acceso limitado a funcionalidades.
- [ERPNext: efectos de operaciones en registros](https://docs.frappe.io/erpnext/how-transactions-affect-the-ledger): conservar el historial y registrar correcciones y devoluciones.
- [Django: autenticación](https://docs.djangoproject.com/en/5.2/topics/auth/): contraseñas, sesiones y controles del servidor.
- [Django: transacciones](https://docs.djangoproject.com/en/5.2/topics/db/transactions/): operaciones atómicas.
- [Django: bloqueo de filas](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update): bloqueo para operaciones concurrentes.
- [PGlite Socket](https://pglite.dev/docs/pglite-socket): entorno de integración basado en PostgreSQL compilado a WebAssembly; no equivale a validar concurrencia nativa.

Fuentes consultadas el 7 de septiembre de 2026. Ninguno de estos sistemas ofrece una garantía razonable de ausencia absoluta de errores.

Las fuentes tipográficas DejaVu utilizadas en PDF se distribuyen con su licencia en `core/fonts/LICENSE-DejaVu.txt`.
