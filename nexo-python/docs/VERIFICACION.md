# Verificación de esta entrega

Fecha: 7 de septiembre de 2026.

## Ejecutado

- Instalación de Django 5.2.17, Psycopg 3.3.5, Gunicorn 25.3.0 y demás dependencias declaradas.
- Comprobación de sintaxis de Python y JavaScript.
- `manage.py check`: sin problemas.
- Migraciones aplicadas desde cero sobre PostgreSQL compilado a WebAssembly (PGlite), conectado por Psycopg y el protocolo PostgreSQL. Sin sustitución por SQLite.
- 38 pruebas aprobadas sobre PostgreSQL 17 nativo en GitHub Actions, incluida la prueba de dos vendedores simultáneos. Ejecución: https://github.com/gregoriocallecastillo-boop/gregorio/actions/runs/34092375040.
- También se ejecutaron 37 pruebas en PGlite; allí se omitió una prueba de concurrencia por las limitaciones del motor embebido.
- Inicialización única del administrador desde un secreto privado de Render: creación, contraseña fuerte, datos de ejemplo separados y reintentos que no reinician cuentas existentes.
- Blueprint render.yaml validado contra el esquema oficial de Render.
- Controles probados: ventas sin stock, rollback completo ante error, costo promedio, transferencias, cantidades fraccionarias, impuestos, reenvíos, roles, aislamiento de negocios, CSRF, bloqueo de intentos de acceso, contraseñas temporales, pagos parciales, exceso de cobro, reversión de pagos, notas de crédito, reportes y restricciones de base de datos.
- Exportación CSV con neutralización de fórmulas, generación de PDF y carga de fotos con validación de permisos, formato y revisión de caché.
- Recursos estáticos recopilados y comprimidos con WhiteNoise.
- Revisión de configuración de producción: ningún error; advertencia opcional sobre HSTS preload. No se ha activado la inscripción en una lista de precarga de navegadores.
- Factura ficticia de 30 renglones generada y sus cuatro páginas revisadas visualmente para comprobar paginación, márgenes y tipografía.

## Pendiente antes de uso comercial

- Activar el Blueprint de Render y comprobar la conexión a la base ya creada, el login y la comprobación de salud del despliegue definitivo.
- Iniciar y comprobar la instalación Docker en una máquina con Docker disponible. El paquete contiene la configuración, pero Docker no está instalado en este entorno.
- Probar los flujos completos de la interfaz en navegadores de escritorio y Android; no se realizó una prueba de navegador ni se capturaron pantallas de la aplicación ejecutándose.
- Medir carga y tiempo de respuesta con el catálogo y volumen reales del negocio.
- Verificar HTTPS, dominio, secretos, backups, recuperación y entrega de credenciales en el servidor definitivo.
- Definir país y requisitos fiscales. Los PDF son documentos comerciales; no acreditan integración fiscal electrónica.

Las pruebas con PostgreSQL 17 nativo verificaron las reglas de negocio y el bloqueo concurrente de existencias. La conexión privada y el despliegue concreto en Render siguen pendientes de activación. La revisión visual del PDF no sustituye la comprobación de la interfaz en un teléfono.

No se garantiza ausencia absoluta de errores. El informe distingue deliberadamente lo probado de lo pendiente.
