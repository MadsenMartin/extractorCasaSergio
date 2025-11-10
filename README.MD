# Extractor de artículos de pedidos de Casa Sergio con IA

![Imágen de muestra de la aplicación](./imagenes/captura.png)

Este proyecto es una aplicación web que usa inteligencia artificial para extraer artículos de pedidos en formato PDF de Casa Sergio (proveedor). La aplicación permite a los usuarios cargar archivos PDF y obtener una lista estructurada de los artículos pedidos, facilitando la gestión y análisis de los datos.  
Su finalidad es el control de lo pedido vs lo que cargan ellos en el sistema (Lo que van a cobrar), o en el caso de que se trate de un pedido a restar de un acopio, obtener los datos necesarios para hacer el desacopio.

## Uso

1. Cloná este repositorio en tu máquina local.
2. Navegá al directorio del proyecto.
3. Asegurate de tener Docker y Docker Compose instalados.
4. Editá el archivo `docker-compose.yml` para incluir tus variables de entorno (clave de API de OpenAI y contraseña de la aplicación)
5. Corré el container con `docker-compose up --build`
6. Accedé a la aplicación en tu navegador web en `http://localhost:8501`.