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
