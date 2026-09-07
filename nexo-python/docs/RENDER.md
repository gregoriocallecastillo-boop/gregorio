# Abrir Nexo desde el teléfono

El código está en `nexo-python/` dentro de la rama `nexo-render`. El archivo
`render.yaml` de la raíz define el servidor Python y su PostgreSQL privado.
Reutiliza la base `nexo-demo-postgres` creada en Ohio. Ambos planes son gratuitos.

1. Abre el enlace de despliegue de Render para la rama `nexo-render`.
2. Conecta GitHub con Render si lo solicita y revisa el workspace.
3. En `NEXO_BOOTSTRAP_PASSWORD`, elige una contraseña larga y única
   (12 caracteres como mínimo; evita palabras comunes y tu nombre de usuario).
4. Pulsa **Deploy Blueprint** o **Apply** y espera a que el servicio esté **Live**.
5. Abre la dirección `onrender.com` que muestre Render. Usuario: `gregorio`.
   Contraseña: la que elegiste en el paso 3.
6. En el selector superior elige **Mercado Central · Ejemplo** para ver productos,
   compras, una venta, una factura y un pago parcial de demostración.

Después de comprobar el acceso, elimina `NEXO_BOOTSTRAP_PASSWORD` de las variables
de Render. El inicio detecta cuentas existentes y nunca reinicia sus contraseñas.
Las credenciales no se incluyen en GitHub ni se imprimen en los registros.

Los datos de ejemplo están separados de **Mi negocio**, que empieza vacío.
La primera creación se ejecuta en una transacción y con un bloqueo de PostgreSQL
para evitar administradores duplicados durante arranques simultáneos.

El servidor gratuito puede tardar en responder después de estar inactivo.
La base gratuita creada el 7 de septiembre de 2026 vence el **7 de octubre de 2026**.
Este despliegue sirve para probar; el plan y los respaldos para una operación real
deben definirse antes de guardar información comercial.

Referencias: https://render.com/docs/deploy-django,
https://render.com/docs/free, https://render.com/docs/infrastructure-as-code.
