# Extractor de artículos de pedidos de Casa Sergio con IA

![Imágen de muestra de la aplicación](./imagenes/captura.png)

Este proyecto es una aplicación web que usa inteligencia artificial para extraer artículos de pedidos en formato PDF de Casa Sergio (proveedor). La aplicación permite a los usuarios cargar archivos PDF y obtener una lista estructurada de los artículos pedidos, facilitando la gestión y análisis de los datos.  
Su finalidad es el control de lo pedido vs lo que cargan ellos en el sistema (Lo que van a cobrar), o en el caso de que se trate de un pedido a restar de un acopio, obtener los datos necesarios para hacer el desacopio.

## Uso

1. Cloná este repositorio en tu máquina local.
2. Instalá los requisitos con `pip install -r requirements.txt`.
3. Configurá tu clave de API de OpenAI en un archivo `.env` (podés usar `.env.example` como plantilla).
4. Ejecutá la aplicación en un puerto específico con `streamlit run app.py --server.port 8501 --server.address 0.0.0.0`.
