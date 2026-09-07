# Verificación de la interfaz guiada y Kardex

Fecha: 7 de septiembre de 2026 (UTC).

## Versión publicada

- Repositorio: `gregoriocallecastillo-boop/gregorio`, rama `nexo-render`.
- Código de la aplicación: `3ea345d8f25446c885a92e2cf9e2a84424a9ebe2`.
- Render: `nexo-inventario-python`, despliegue `dep-dafkheqd0e5s73cpt6i0`, estado `live`, finalizado a las 23:30 UTC.
- [Demostración pública](https://nexo-inventario-python.onrender.com/demo/), con entrada sin contraseña y datos ficticios separados por visitante.
- Python/Django y PostgreSQL se conservan. Esta actualización no añade migraciones de esquema.

## Pruebas automatizadas

- **65 pruebas aprobadas en PostgreSQL 17 nativo**, incluidas las dos de concurrencia. [Ejecución de GitHub Actions](https://github.com/gregoriocallecastillo-boop/gregorio/actions/runs/34170109882).
- `manage.py check`: sin problemas.
- Comprobaciones de sintaxis de Python y de ambos archivos JavaScript: aprobadas.
- `collectstatic`: recursos recopilados y procesados con WhiteNoise.
- PGlite local: 63 aprobadas y dos de concurrencia omitidas; esas dos sí aprobaron en PostgreSQL nativo.
- La suite comprueba ventas sin stock, atomicidad, costo promedio, traslados, cantidades fraccionarias, impuestos, idempotencia, roles, aislamiento, CSRF, controles de acceso, pagos, devoluciones y restricciones de la base de datos.
- Las nuevas pruebas comprueban saldos del kardex, fechas, paginación, CSV completo, neutralización de fórmulas, permisos, aislamiento de la demo y conteos desactualizados, incluido el caso de movimientos que vuelven a dejar la cantidad original.

## Recorrido del navegador sobre Render

Se utilizó Chrome de escritorio, con ancho de contenido de 1348 píxeles CSS, y exclusivamente un espacio de demostración del navegador de pruebas.

- Entrada pública: muestra 13 módulos y permite entrar como invitado sin credenciales.
- Inicio: botones de tareas, gráfico de ventas y avisos de reposición y cobros; captura revisada visualmente.
- Navegación: se abrieron los 13 módulos, sin alertas de error de la aplicación.
- Venta guiada: un café de $6.50, revisión del descuento de una unidad, confirmación y factura `DEMO-F-00009`.
- Cobro ficticio: registro de $6.50 en efectivo; la factura cambió de pendiente a pagada.
- Inventario y kardex: café de 38 a 37 unidades tras la venta; salida de una unidad y costo promedio histórico de $4.2000.
- Conteo físico: revisión y confirmación de 36 unidades frente a 37 registradas; el ajuste quedó en el kardex con motivo y saldo final de 36.
- Reposición: lista de aceite, galletas y papel con diferencias de 3, 8 y 3 unidades hasta sus mínimos configurados.
- Empleado: cinco módulos visibles. No aparecen alta de productos, conteo, kardex ni costo del producto en su detalle.
- Las capturas de inicio, revisión de venta, menú de módulos y conteo fueron inspeccionadas durante el recorrido.

## Límites y comprobaciones pendientes

- La adaptación móvil está implementada mediante estilos para pantallas de hasta 799 y 390 píxeles, navegación inferior y tablas convertidas en registros. **No se ha verificado en un teléfono Android físico ni con un viewport móvil efectivo en este navegador.**
- La exportación CSV está validada en las pruebas automatizadas. Se pulsó el botón en el navegador publicado, pero el entorno no confirmó el evento de descarga; no se declara verificada de extremo a extremo la descarga del archivo en ese navegador.
- No se usaron credenciales reales ni se modificaron existencias de un negocio real en las pruebas del navegador. Los permisos del backend real se verificaron con las pruebas automatizadas.
- No se realizó en esta actualización una prueba de carga con el catálogo real, restauración de backups, instalación Docker o integración fiscal electrónica.

Este informe distingue las comprobaciones realizadas de las pendientes; no garantiza ausencia absoluta de errores.
