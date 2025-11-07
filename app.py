import streamlit as st
import fitz  # PyMuPDF
import base64
from openai import OpenAI
from dotenv import load_dotenv
import os
import json
import re
import csv
import io

def extraer_pdf(pdf_file):
    """Extrae datos del PDF subido y retorna el CSV generado"""

    # Guardar temporalmente el PDF
    with open("temp.pdf", "wb") as f:
        f.write(pdf_file.getbuffer())

    # Abrir el PDF
    doc = fitz.open("temp.pdf")

    # Convertir todas las páginas a imágenes
    images_base64 = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=300)
        pix.save(f"page{page_num + 1}.png")

        with open(f"page{page_num + 1}.png", "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
            images_base64.append(img_b64)

    # Extraer texto directamente del PDF
    texto_completo = ""
    for page_num in range(len(doc)):
        texto_completo += f"\n--- Página {page_num + 1} ---\n"
        texto_completo += doc[page_num].get_text()

    # Cerrar el documento antes de intentar eliminar el archivo
    doc.close()

    load_dotenv()
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = f"""
    Extrae TODOS los items del pedido de TODAS las {len(images_base64)} página(s). Los números DEBEN coincidir EXACTAMENTE con los del texto.

    TEXTO DEL PDF:
    {texto_completo}

    INSTRUCCIONES:
    1. Mira las imágenes Y el texto para identificar TODOS los items de TODAS las páginas
    2. Extrae TODOS los items de la tabla (filas con Código, Artículo, IVA, Pre. Uni., Cantidad, Total)
    3. Busca al final:
       - "SubTotal:" = suma de todos los totales
       - "Iva:" = IVA total
       - "Total:" = total final

    Devuelve JSON:
    {{
    "pedido_numero": string,
    "items": [
        {{"codigo": string, "descripcion": string, "cantidad": float, "precio_unit": float, "total": float, "iva": float}}
    ],
    "subtotal": float,
    "iva_total": float,
    "total": float
    }}
    """

    # Construir mensaje con texto + imágenes
    user_content = [{"type": "text", "text": prompt}]
    for img_b64 in images_base64:
        user_content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}})

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Sos un asistente que extrae datos estructurados de PDFs de múltiples páginas. Usa el texto Y las imágenes para no perder ningún item."},
            {"role": "user", "content": user_content}
        ],
        max_tokens=4000
    )

    content = response.choices[0].message.content

    # Extraer JSON si está envuelto en markdown
    json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', content, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = content

    data = json.loads(json_str)

    # Verificar que la suma de totales = subtotal
    suma_totales = sum(item["total"] for item in data["items"])
    subtotal = data["subtotal"]

    if abs(suma_totales - subtotal) > 0.01:
        validacion = f"ERROR: Suma={suma_totales} != Subtotal={subtotal}"
        validacion_ok = False
    else:
        validacion = "OK"
        validacion_ok = True

    # Función para formatear números con coma decimal
    def format_number(num):
        if isinstance(num, (int, float)):
            return str(num).replace('.', ',')
        return num

    # Generar CSV en memoria
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["Codigo", "Descripcion", "Cantidad", "Precio_Unit", "Total", "IVA", "Validacion"])
    for i, item in enumerate(data["items"]):
        val = validacion if i == 0 else ""
        writer.writerow([
            item["codigo"],
            item["descripcion"],
            format_number(item["cantidad"]),
            format_number(item["precio_unit"]),
            format_number(item["total"]),
            format_number(item["iva"]),
            val
        ])

    # Limpiar archivos temporales
    os.remove("temp.pdf")
    for page_num in range(len(images_base64)):
        try:
            os.remove(f"page{page_num + 1}.png")
        except:
            pass

    return output.getvalue(), data, validacion_ok, suma_totales, subtotal

# Interfaz de Streamlit
st.set_page_config(page_title="Extractor de pedidos Casa Sergio", page_icon="📄")

# Autenticación
load_dotenv()
PASSWORD = os.getenv("APP_PASSWORD", "admin123")  # Contraseña por defecto si no está en .env

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 Acceso restringido")
    password = st.text_input("Ingresa la contraseña", type="password")
    if st.button("Ingresar"):
        if password == PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ Contraseña incorrecta")
    st.stop()

st.title("📄 Pedidos Casa Sergio")

# Subir archivo
uploaded_file = st.file_uploader("Selecciona un PDF", type=['pdf'])

if uploaded_file is not None:
    st.success(f"Archivo cargado: {uploaded_file.name}")

    if st.button("🚀 Extraer datos", type="primary"):
        with st.spinner("Procesando PDF..."):
            try:
                csv_content, data, validacion_ok, suma, subtotal = extraer_pdf(uploaded_file)

                # Mostrar resultados
                st.success("✅ Extracción completada")

                # Información del pedido
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Pedido N°", data.get("pedido_numero", "N/A"))
                with col2:
                    st.metric("Total items", len(data["items"]))
                with col3:
                    st.metric("Total", f"${data['total']:,.2f}")

                # Validación
                if validacion_ok:
                    st.success(f"✓ Validación OK: Suma de totales = ${suma:,.2f}")
                else:
                    st.error(f"⚠️ Suma de totales (${suma:,.2f}) ≠ Subtotal (${subtotal:,.2f})")

                # Mostrar datos
                st.subheader("Items extraídos")
                st.dataframe(data["items"], use_container_width=True)

                # Botón de descarga
                st.download_button(
                    label="📥 Descargar CSV",
                    data=csv_content,
                    file_name=f"pedido_{data.get('pedido_numero', 'extraido')}.csv",
                    mime="text/csv"
                )

            except Exception as e:
                st.error(f"❌ Error al procesar el PDF: {str(e)}")
                st.exception(e)