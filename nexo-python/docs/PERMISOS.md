# Permisos por negocio

| Función | Administrador | Empleado |
|---|---|---|
| Resumen | Inventario y resultados del negocio | Catálogo y ventas propias |
| Consultar productos y existencias | Sí | Sí |
| Ver costos y valoración | Sí | No |
| Crear/editar/archivar productos y fotos | Sí | No |
| Registrar compras | Sí | No |
| Registrar ventas | Sí | Sí, con precio del catálogo |
| Modificar precio en una venta | Sí en el servidor; la pantalla usa catálogo | No |
| Ver facturas/PDF y cobrar | Todas las del negocio | Solo las de sus ventas |
| Cobros parciales | Sí | Solo sus ventas |
| Anular cobro / registrar reembolso | Sí | No |
| Devolver venta / emitir nota de crédito | Sí | No |
| Ajustes y traslados | Sí | No |
| Kardex y exportación del historial por producto | Sí | No |
| Conteo físico con revisión previa | Sí | No |
| Lista de productos por reponer | Sí | Consulta |
| Almacenes | Administrar | Seleccionar al vender |
| Proveedores | Administrar | No |
| Clientes | Administrar | Consultar y seleccionar |
| Reportes y costos | Sí | No |
| Exportaciones | Sí | No |
| Configuración del negocio | Sí | No |
| Equipo y permisos | Sí | No |
| Bitácora | Sí | No |
| Crear otro negocio | Sí | No |
| Cambiar contraseña propia | Sí | Sí |

Los permisos se verifican en el servidor en cada solicitud. Una persona puede tener roles distintos en negocios diferentes. Desactivar la membresía retira el acceso a ese negocio, aunque su sesión siga abierta. Siempre debe quedar al menos un administrador activo.

Los administradores no se convierten en superusuarios de Django. Su acceso total corresponde a los negocios donde están autorizados, no a los de otras personas.
