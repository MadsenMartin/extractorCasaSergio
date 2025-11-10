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

    prompt = """Analiza las imágenes y extrae TODOS los items del pedido.

IMPORTANTE: Antes de extraer, CUENTA cuántas filas hay en la tabla de items. Luego extrae ESE número exacto de items.

Extrae:
- Número de pedido
- TODOS los items de la tabla con: Código, Artículo, IVA, Pre. Uni., Cantidad, Total
- Totales del documento: Unidades, SubTotal, Iva, Total

Formato JSON:
{
    "pedido_numero": <int>,
    "items": [
        {
            "codigo": "<string>",
            "articulo": "<string>",
            "iva": <float>,
            "pre_uni": <float>,
            "cantidad": <float>,
            "total": <float>
        }
    ],
    "totales_documento": {
        "unidades": <float>,
        "subtotal": <float>,
        "iva_total": <float>,
        "total": <float>
    }
}

REGLAS:
- Punto (.) como separador decimal
- Extrae valores exactos, NO calcules
- Lee TODAS las páginas si hay múltiples imágenes

Responde SOLO JSON."""
    # Construir mensaje con imágenes (sin texto del PDF para reducir confusión)
    user_content = [{"type": "text", "text": prompt}]
    for img_b64 in images_base64:
        user_content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}})

    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": "Sos un asistente de extracción de datos. Tu trabajo es extraer TODOS los items de tablas en imágenes sin saltear ninguno. Analizá cada imagen con cuidado, contá las filas y extraé ese número exacto de items."},
            {"role": "user", "content": user_content}
        ],
        max_completion_tokens=4000
    )

    content = response.choices[0].message.content

    '''# Guardar respuesta raw para debugging
    with open("response_raw.json", "w", encoding="utf-8") as f:
        f.write(content)
    '''

    # Extraer JSON si está envuelto en markdown
    json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', content, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = content

    data = json.loads(json_str)

    '''# Guardar respuesta parseada para debugging
    with open("response_parsed.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(data, indent=2, ensure_ascii=False))
    '''
    
    # VALIDACIONES EN PYTHON (no confiar en GPT)
    items = data["items"]
    totales_doc = data["totales_documento"]

    # Calcular suma de totales de items
    suma_totales = sum(item["total"] for item in items)
    subtotal_doc = totales_doc["subtotal"]

    # Calcular suma de cantidades
    suma_cantidades = sum(item["cantidad"] for item in items)
    unidades_doc = totales_doc["unidades"]

    # Validar
    validacion_ok = True
    validacion = ""

    if abs(suma_totales - subtotal_doc) > 0.01:
        validacion = f"ERROR: Suma totales items ({suma_totales:.2f}) ≠ SubTotal documento ({subtotal_doc:.2f})"
        validacion_ok = False
    else:
        validacion = "OK Totales"

    if abs(suma_cantidades - unidades_doc) > 0.01:
        if validacion_ok:
            validacion = f"ERROR: Suma cantidades ({suma_cantidades}) ≠ Unidades documento ({unidades_doc})"
        else:
            validacion += f" | ERROR: Suma cantidades ({suma_cantidades}) ≠ Unidades ({unidades_doc})"
        validacion_ok = False
    else:
        validacion += " | OK Cantidades"

    # Función para formatear números con coma decimal
    def format_number(num):
        if isinstance(num, (int, float)):
            return str(num).replace('.', ',')
        return num

    # Generar CSV en memoria con UTF-8 encoding correcto
    import codecs
    output = io.StringIO()
    output.write('\ufeff')  # BOM UTF-8
    writer = csv.writer(output, delimiter=';', lineterminator='\n')
    writer.writerow(["Codigo", "Artículo", "Cantidad", "Precio Unitario", "IVA", "Total (neto)", "Validacion"])
    for i, item in enumerate(data["items"]):
        val = validacion if i == 0 else ""
        writer.writerow([
            item["codigo"],
            item["articulo"],
            format_number(item["cantidad"]),
            format_number(item["pre_uni"]),
            format_number(item["iva"]),
            format_number(item["pre_uni"] * item["cantidad"]),
            val
        ])

    # Limpiar archivos temporales
    os.remove("temp.pdf")
    for page_num in range(len(images_base64)):
        try:
            os.remove(f"page{page_num + 1}.png")
        except:
            pass

    return output.getvalue(), data, validacion_ok, suma_totales, subtotal_doc

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
                    st.metric("Items encontrados", len(data["items"]))
                with col3:
                    st.metric("Total documento", f"${data['totales_documento']['total']:,.2f}")

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