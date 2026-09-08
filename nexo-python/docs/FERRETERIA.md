# Demostración de ferretería

Entrada pública: `/demo/ferreteria/`. La tienda anterior sigue disponible en `/demo/`.

La ferretería ofrece los mismos 13 módulos, con una entrada de invitado propia, ocho productos fotografiados, dos almacenes y contactos ficticios. Las existencias, precios, compras, ventas, facturas y movimientos son datos de ejemplo. Los productos incluyen martillo, cinta métrica, atornillador inalámbrico, alicate, destornillador, llave ajustable, tornillo para madera y gafas de seguridad.

Cada visitante tiene un espacio temporal independiente. La ferretería utiliza una cookie HttpOnly distinta, restringida a `/demo/ferreteria/`, y las API comprueban que el perfil de la cookie coincida con el de la ruta. Reiniciar o cerrar la ferretería no borra la prueba de la tienda ni la de otro visitante. Las operaciones siguen confinadas a DemoSandbox, sin modificar negocios, usuarios, productos o documentos reales.

El botón para probar la ferretería aparece en la entrada de la tienda y en Mi cuenta. No se añade una cuenta real ni se necesita contraseña. El administrador y el empleado conservan los mismos permisos de la aplicación.

## Fotografías

Se incluyen miniaturas de fotografías reales de Wikimedia Commons, revisadas visualmente. No se generaron imágenes con IA. Se sirven desde los recursos estáticos de Nexo para evitar que cada visita dependa de un servidor de fotografías externo.

Las fuentes, autores y licencias están en [CREDITS.json](../core/static/core/hardware/CREDITS.json). También aparecen en la entrada de la ferretería y en el detalle de cada producto. Las fotografías CC BY-SA conservan su licencia, independientemente de la licencia del código. La fotografía del martillo de Evan-Amos es de dominio público. Las marcas visibles pertenecen a sus titulares; esta es una demostración ficticia y no afirma afiliación o patrocinio.

Si el invitado carga otra fotografía, se muestra esa imagen en su espacio temporal y dejan de mostrarse los créditos de la fotografía de ejemplo para ese producto.

## Comprobaciones

Las pruebas de `test_hardware_demo.py` verifican catálogo y archivos JPEG, prefijo de las API, separación entre perfiles y visitantes, reinicio, cierre, rechazo de cookies de otro perfil, CSRF, permisos del empleado, venta, cobro, factura PDF y conciliación del Kardex para cada producto y almacén.

## Resultado de la publicación · 8 de septiembre de 2026 UTC

- Código publicado: `95ee9eadfb2593e8fdffccfb464e2249ff961f8b`.
- Las **70 pruebas aprobaron en PostgreSQL 17 nativo**: [GitHub Actions](https://github.com/gregoriocallecastillo-boop/gregorio/actions/runs/34171971449). En PGlite aprobaron 68 y se omitieron las dos de concurrencia que sí aprobaron en PostgreSQL nativo.
- Render confirmó el despliegue `dep-dafl1kgn74is73agjmp0` como `live` a las 00:04 UTC.
- [Entrada pública verificada](https://nexo-inventario-python.onrender.com/demo/ferreteria/).
- En Chrome se verificaron la entrada de invitado, las ocho fotografías cargadas, el catálogo, una venta de un martillo por $12.90, la factura `DEMO-F-00008` y la disminución de 39 a 38 unidades en el Kardex. No se registraron errores de JavaScript de la aplicación durante ese recorrido.
- Se verificó el detalle del producto en la vista de empleado: fotografía, precio y existencias, con atribución de la foto y sin costo promedio ni controles administrativos. La tienda original mantuvo su propio negocio al recargar otra pestaña.
- La revisión visual se realizó en Chrome de escritorio. Los estilos móviles están implementados, pero no se verificó esta entrega en un teléfono físico.
