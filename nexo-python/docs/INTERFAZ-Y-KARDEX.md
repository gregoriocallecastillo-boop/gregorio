# Nexo: interfaz guiada y kardex

Actualización del 7 de septiembre de 2026.

## Decisión de diseño

Se conserva Python/Django y PostgreSQL y se renueva la interfaz web existente. La combinación aprobada de los modelos 6, 7 y 10 se implementa como inicio por tareas, venta guiada y categorías de herramientas que se reorganizan para celular. No se migra a Flet: las operaciones, sesiones y controles de acceso actuales se reutilizan directamente.

La navegación principal ofrece Inicio, Productos, Vender y Más. En Más, el orden es:

1. Día a día: Resumen, Ventas, Facturación.
2. Productos: Inventario, Compras, Movimientos, Kardex, Almacenes.
3. Tu negocio: Contactos, Reportes, Equipo, Bitácora, Configuración.

El administrador dispone de 13 módulos. El empleado consulta productos y clientes, registra ventas a precio de catálogo y consulta/cobra sus propias facturas. No se amplían sus permisos de compras, ajustes, costos o historiales administrativos.

## Mejoras funcionales

- Venta en tres pasos: selección, revisión explícita del impacto y factura. El pago se registra después de recibir el dinero.
- Existencias disponibles por almacén al seleccionar productos; validación definitiva en el servidor.
- Kardex por producto, almacén y fechas, con apertura, entradas, salidas, cierre, responsable, motivo y costo promedio registrado en cada movimiento.
- Paginación de 50 movimientos, con totales del período completo y exportación CSV de todas sus páginas.
- El costo de cada movimiento conserva su valor histórico. No se presenta como precio de venta ni como un cálculo de valoración contable por almacén.
- Conteo físico guiado: escribir la cantidad contada, revisar la diferencia y confirmar. El servidor compara cantidad y último movimiento con la instantánea revisada. Detecta incluso una venta seguida de devolución que deje la cantidad original. Los reintentos no repiten el ajuste.
- Lista «Qué hace falta», usando mínimos configurados. Las cantidades sugeridas alcanzan ese mínimo; no representan una predicción de demanda ni una compra confirmada.
- Ayuda contextual y glosario cotidiano. Tablas transformadas en registros con etiquetas en pantallas pequeñas, controles táctiles grandes y respeto por la preferencia de movimiento reducido.
- La demostración conserva su aislamiento: todos los cambios siguen almacenándose exclusivamente en el espacio temporal de cada visitante. Los productos de ejemplo incluyen ilustraciones; las fotografías cargadas por cada negocio se mantienen.

## Investigación aplicada

Se consultó documentación oficial, sin copiar código de terceros:

- ERPNext, [Stock Ledger Report](https://docs.frappe.io/erpnext/stock-ledger): consultar movimientos, saldos y referencias por producto y almacén. Se aplica al kardex con apertura del período y exportación completa.
- InvenTree, [Stock Tracking](https://docs.inventree.org/en/1.2.x/stock/tracking/): conservar la trazabilidad de cambios de existencias. Nexo utiliza su historial persistido, sin reescribir movimientos anteriores.
- InvenTree, [Parts / Minimum Stock](https://docs.inventree.org/en/stable/part/): señalar artículos por debajo del mínimo. Se convierte en una lista comprensible de reposición.
- Odoo, [Inventory adjustments](https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/inventory/warehouses_storage/inventory_management/count_products.html): distinguir cantidad registrada y cantidad contada. Se agrega revisión antes de registrar diferencias y comprobación de cambios concurrentes.
- InvenTree, [arquitectura del proyecto](https://github.com/inventree/inventree): ejemplo de un sistema de inventario con backend Python/Django y una interfaz independiente. Renovar la interfaz no exige sustituir PostgreSQL ni las reglas de negocio.

Lotes con múltiples fechas de vencimiento, reservas y predicción de compras requieren reglas y modelos adicionales. No se simulan como funciones disponibles. La fecha de vencimiento actual sigue siendo por producto. La factura sigue siendo un documento comercial, con impuestos configurables; no se agrega una integración fiscal electrónica.

## Validación

La suite incorpora pruebas de saldos, rangos de fechas, traslados, devoluciones, paginación, exportación completa, permisos, aislamiento y conteos desactualizados. La ejecución local encontró 65 pruebas: 63 aprobadas y 2 de concurrencia reservadas para PostgreSQL nativo en GitHub Actions. Los resultados finales de publicación y navegador se registran en el historial de entrega.
