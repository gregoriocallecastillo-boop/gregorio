# Cómo empezar con Nexo

## 1. Crear el administrador

Inicia la aplicación siguiendo el README y ejecuta `docker compose exec web python manage.py bootstrap`. Escribe un nombre de usuario y una contraseña propia de al menos 12 caracteres. No hay una contraseña predeterminada.

## 2. Configurar el negocio

Inicia sesión. En Configuración completa nombre, dirección, identificación, moneda y porcentaje de impuesto. Esos datos se guardarán en las nuevas facturas. Define la moneda antes de registrar existencias.

## 3. Preparar el inventario

Crea almacenes y contactos. Agrega productos con código único, categoría, unidad, precio, mínimo y existencias iniciales. En el detalle del producto puedes subir su foto.

## 4. Registrar una compra

Elige proveedor y almacén, agrega productos, cantidades y costos. Al confirmar aumentan las existencias y se recalcula el costo promedio.

## 5. Vender y facturar

En Ventas selecciona productos, almacén, cliente y fecha de pago. Confirma para descontar el stock y crear una factura. El PDF conserva los datos del cliente, del emisor y de la operación aunque luego edites el catálogo o la configuración.

## 6. Registrar un cobro

En Facturación abre la factura y elige Cobrar. Indica importe recibido, método y referencia. Puedes registrar abonos hasta completar el total. Nexo no procesa cargos bancarios.

## 7. Crear empleados

En Equipo y permisos crea la cuenta con rol Empleado y una contraseña temporal. La persona deberá cambiarla al entrar. Podrá consultar productos/clientes, vender y cobrar sus propias ventas. Los demás módulos están restringidos en el servidor.

## 8. Corregir una operación

Para diferencias de stock, usa un ajuste con motivo. Para devolver una venta completa, primero corrige o registra el reembolso de cualquier cobro asociado y luego registra la devolución; se genera una nota de crédito y se reponen los productos. No se borra el historial.

## 9. Revisar y proteger la información

Consulta Reportes, Bitácora y exportaciones. Realiza copias completas de PostgreSQL con el script incluido. Prueba periódicamente una restauración en una base nueva.

## Si se interrumpe el guardado

Conserva el formulario y actualiza el historial antes de registrar otra operación. El sistema evita duplicar el mismo envío, pero crear una operación nueva después de perder una respuesta puede representar una segunda venta. Revisa primero si ya aparece la factura.
