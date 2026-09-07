# Verificación de esta entrega

Fecha: 7 de septiembre de 2026.

## Ejecutado

- Instalación de Django 5.2.17, Psycopg 3.3.5, Gunicorn 25.3.0 y demás dependencias declaradas.
- Comprobación de sintaxis de Python y JavaScript.
- `manage.py check`: sin problemas.
- Migraciones aplicadas desde cero sobre PostgreSQL compilado a WebAssembly (PGlite), conectado por Psycopg y el protocolo PostgreSQL. Sin sustitución por SQLite.
- 35 pruebas de integración aprobadas y 1 prueba nativa de concurrencia omitida explícitamente.
- Controles probados: ventas sin stock, rollback completo ante error, costo promedio, transferencias, cantidades fraccionarias, impuestos, reenvíos, roles, aislamiento de negocios, CSRF, bloqueo de intentos de acceso, contraseñas temporales, pagos parciales, exceso de cobro, reversión de pagos, notas de crédito, reportes y restricciones de base de datos.
- Exportación CSV con neutralización de fórmulas, generación de PDF y carga de fotos con validación de permisos, formato y revisión de caché.
- Recursos estáticos recopilados y comprimidos con WhiteNoise.
- Revisión de configuración de producción: ningún error; advertencia opcional sobre HSTS preload. No se ha activado la inscripción en una lista de precarga de navegadores.
- Factura ficticia de 30 renglones generada y sus cuatro páginas revisadas visualmente para comprobar paginación, márgenes y tipografía.

## Pendiente antes de uso comercial

- Ejecutar la suite incluida sobre PostgreSQL **nativo**, especialmente la prueba de dos ventas simultáneas. Las restricciones del entorno impidieron instalar/iniciar el servidor nativo.
- Iniciar y comprobar la instalación Docker en una máquina con Docker disponible. El paquete contiene la configuración, pero Docker no está instalado en este entorno.
- Probar los flujos completos de la interfaz en navegadores de escritorio y Android; no se realizó una prueba de navegador ni se capturaron pantallas de la aplicación ejecutándose.
- Medir carga y tiempo de respuesta con el catálogo y volumen reales del negocio.
- Verificar HTTPS, dominio, secretos, backups, recuperación y entrega de credenciales en el servidor definitivo.
- Definir país y requisitos fiscales. Los PDF son documentos comerciales; no acreditan integración fiscal electrónica.

El código está preparado para PostgreSQL nativo. La prueba de desarrollo con PGlite demuestra funcionamiento de consultas, transacciones, autenticación y lógica de negocio en ese motor; no demuestra el comportamiento multiusuario ni la configuración de un servidor PostgreSQL nativo.

No se garantiza ausencia absoluta de errores. El informe distingue deliberadamente lo probado de lo pendiente.
