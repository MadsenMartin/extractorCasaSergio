import fitz  # PyMuPDF
from PIL import Image
import base64
from openai import OpenAI
from dotenv import load_dotenv
import os
def extraer():

    # Abrir el PDF
    doc = fitz.open("5QR248 quinto.pdf")

    # Convertir todas las páginas a imágenes
    images_base64 = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=300)
        pix.save(f"page{page_num + 1}.png")

        with open(f"page{page_num + 1}.png", "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
            images_base64.append(img_b64)

    doc.close()

    load_dotenv()
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Extraer texto directamente del PDF
    doc = fitz.open("5QR248 quinto.pdf")
    texto_completo = ""
    for page_num in range(len(doc)):
        texto_completo += f"\n--- Página {page_num + 1} ---\n"
        texto_completo += doc[page_num].get_text()
    doc.close()

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

    import json
    import re

    content = response.choices[0].message.content
    print(content)

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

    if abs(suma_totales - subtotal) > 0.01:  # Tolerancia para errores de redondeo
        validacion = f"ERROR: Suma={suma_totales} != Subtotal={subtotal}"
        print(f"⚠️ ADVERTENCIA: La suma de totales ({suma_totales}) no coincide con el subtotal ({subtotal})")
    else:
        validacion = "OK"
        print(f"✓ Validación correcta: suma de totales = {suma_totales}")

    # Función para formatear números con coma decimal
    def format_number(num):
        if isinstance(num, (int, float)):
            return str(num).replace('.', ',')
        return num

    # Ejemplo: guardar en CSV
    import csv
    with open("pedido.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(["Codigo", "Descripcion", "Cantidad", "Precio_Unit", "Total", "IVA", "Validacion"])
        for i, item in enumerate(data["items"]):
            # Solo mostrar la validación en la primera fila
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

if __name__ == "__main__":
    extraer()