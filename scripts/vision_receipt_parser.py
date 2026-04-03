import os
import json
import base64
import argparse
from datetime import datetime
from PIL import Image

# Use the official google-genai SDK
from google import genai
from google.genai import types

def setup_client():
    """Inicializa el cliente de Gemini usando la variable de entorno GEMINI_API_KEY"""
    if "GEMINI_API_KEY" not in os.environ:
        raise ValueError("Falta la variable de entorno GEMINI_API_KEY")
    return genai.Client()

# Palabras clave para detección de tipo de comprobante
_KEYWORDS_FACTURA = {"FACTURA", "FCA", "FCB", "FC A", "FC B", "CUIT"}
_KEYWORDS_REMITO  = {"REMITO", "REM."}
_KEYWORDS_PAGO_MO = {"RECIBO", "JORNAL", "CUADRILLA", "OFICIAL", "AYUDANTE"}
_KEYWORDS_IVA     = {"IVA", "TOTAL"}

def detect_tipo(text: str) -> str:
    """
    Detecta el tipo de comprobante a partir del texto OCR o del JSON extraído.
    Jerarquía: factura > pago_mo > remito. Default: 'factura'.
    """
    upper = text.upper()
    if any(kw in upper for kw in _KEYWORDS_FACTURA):
        return "factura"
    if any(kw in upper for kw in _KEYWORDS_PAGO_MO):
        return "pago_mo"
    if any(kw in upper for kw in _KEYWORDS_REMITO):
        has_iva = any(kw in upper for kw in _KEYWORDS_IVA)
        if not has_iva:
            return "remito"
    return "factura"

def extract_receipt_data(client, image_path):
    """
    Envía la imagen de la factura al LLM de visión para extraer los datos estructurados.
    """
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Analizando imagen con Gemini Vision...")
    
    # Preparamos la imagen
    img = Image.open(image_path)
    
    # Prompt con detección de tipo y schema unificado
    prompt = """
    Eres el Agente de Costos experto en extraer datos contables de comprobantes de obra.
    Primero identifica el TIPO de comprobante:
    - Si contiene "FACTURA", "FCA", "FCB", "FC A", "FC B" o "CUIT" → tipo = "factura"
    - Si contiene "REMITO" o "REM." sin mencionar IVA ni total → tipo = "remito"
    - Si contiene "RECIBO", "JORNAL", "CUADRILLA", "OFICIAL" o "AYUDANTE" → tipo = "pago_mo"
    - Si no podés determinarlo → tipo = "factura"
    Jerarquía si hay señales mixtas: factura > pago_mo > remito.

    Devolvé EXCLUSIVAMENTE JSON válido sin markdown según el tipo detectado:

    Para tipo "factura":
    {
        "tipo": "factura",
        "emisor": "Nombre del proveedor",
        "cuit": "XX-XXXXXXXX-X o null",
        "numero_factura": "0001-00012345 o null",
        "fecha": "YYYY-MM-DD o null",
        "tiene_iva": true,
        "items": [{"descripcion": "...", "cantidad": 1.0, "unidad": "u", "precio_unit": 0.0, "subtotal": 0.0}],
        "subtotal_neto": 0.0,
        "total_iva": 0.0,
        "total_ars": 0.0,
        "precio_pendiente": false
    }

    Para tipo "remito":
    {
        "tipo": "remito",
        "proveedor": "Nombre del proveedor",
        "numero_remito": "...",
        "fecha": "YYYY-MM-DD o null",
        "tiene_iva": false,
        "items": [{"descripcion": "...", "cantidad": 1.0, "unidad": "u", "precio_unit": 0.0, "subtotal": 0.0}],
        "total_ars": 0.0,
        "precio_pendiente": true
    }

    Para tipo "pago_mo":
    {
        "tipo": "pago_mo",
        "trabajador": "Nombre completo o cuadrilla",
        "categoria": "Oficial / Ayudante / Medio Oficial",
        "periodo": "YYYY-MM-DD / YYYY-MM-DD",
        "horas": 0.0,
        "jornales": 0.0,
        "importe": 0.0,
        "total_ars": 0.0,
        "tiene_iva": false,
        "precio_pendiente": false
    }

    Reglas generales:
    - Todos los montos en Pesos Argentinos (ARS), sin símbolo "$" ni comas para miles.
    - Si un material no tiene unidad clara, asignar "un".
    - Para remitos sin precios: total_ars = 0.0 y precio_pendiente = true.
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, img],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        
        # Validar y parsear JSON
        data = json.loads(response.text)
        return data
        
    except Exception as e:
        print(f"Error procesando imagen: {e}")
        return None

def save_to_db(data, db_path):
    """Guarda o actualiza el registro en la base de datos de gastos (JSON)"""
    # Cargar existente o crear nuevo
    if os.path.exists(db_path):
        with open(db_path, 'r', encoding='utf-8') as f:
            try:
                db = json.load(f)
            except json.JSONDecodeError:
                db = {"gastos": []}
    else:
        db = {"gastos": []}
        
    # Asignar un ID único basado en timestamp
    gasto_id = f"TICK-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    data["id"] = gasto_id
    data["fecha_carga"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # Compatibilidad: documentos sin campo 'tipo' se tratan como factura
    if "tipo" not in data:
        data["tipo"] = "factura"

    db["gastos"].append(data)
    
    # Guardar
    with open(db_path, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=4, ensure_ascii=False)
        
    return gasto_id

def generate_markdown_report(data, image_filename, report_path):
    """Genera un reporte estético en Markdown para el usuario"""
    
    # Formateo de moneda
    def m(val):
        return f"$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
    tipo = data.get("tipo", "factura")
    tipo_label = {"factura": "Factura", "remito": "Remito", "pago_mo": "Pago Mano de Obra"}.get(tipo, tipo)
    emisor = data.get("emisor") or data.get("proveedor") or data.get("trabajador", "Desconocido")
    pendiente_str = "Sí — factura por recibir" if data.get("precio_pendiente") else "No"

    md = f"""# Reporte de Ticket Procesado

**Tipo de Comprobante:** {tipo_label}
**Emisor:** {emisor}
**Fecha de Ticket:** {data.get("fecha", "No detectada")}
**Condición IVA:** {"Discriminado (A)" if data.get("tiene_iva") else "No aplica / Consumidor Final"}
**Precio Pendiente:** {pendiente_str}

"""

    if tipo == "pago_mo":
        md += f"""## Detalle de Mano de Obra

| Trabajador | Categoría | Período | Horas | Jornales | Importe |
| :--- | :--- | :--- | :---: | :---: | :---: |
| {data.get('trabajador','—')} | {data.get('categoria','—')} | {data.get('periodo','—')} | {data.get('horas',0)} | {data.get('jornales',0)} | **{m(data.get('total_ars',0))}** |

"""
    else:
        md += """## Detalle de Ítems

| Ítem | Cantidad | Unidad | P. Unitario | Subtotal |
| :--- | :---: | :---: | :---: | :---: |
"""
        # Soporta tanto "items" (schema nuevo) como "materiales" (legacy)
        for mat in data.get("items", data.get("materiales", [])):
            nombre = mat.get("descripcion", mat.get("nombre", ""))
            precio = mat.get("precio_unit", mat.get("precio_unitario", 0))
            md += f"| {nombre} | {mat.get('cantidad')} | {mat.get('unidad')} | {m(precio)} | **{m(mat.get('subtotal', 0))}** |\n"

        total_ars = data.get("total_ars", data.get("total_factura", 0))
        md += f"""
---
**Subtotal Neto:** {m(data.get("subtotal_neto", 0))}
**IVA:** {m(data.get("total_iva", 0))}
### **TOTAL:** {m(total_ars)}

"""

    md += f"> *Dato guardado exitosamente como ID: `{data.get('id')}`*\n"

    # Modo append o crear nuevo (separador si ya existe)
    mode = 'a' if os.path.exists(report_path) else 'w'
    with open(report_path, mode, encoding='utf-8') as f:
        if mode == 'a':
            f.write("\n\n---\n\n")
        f.write(md)

def main():
    parser = argparse.ArgumentParser(description="Extrae datos de tickets usando Vision AI")
    parser.add_argument("image_path", help="Ruta a la imagen del ticket/factura")
    args = parser.parse_args()

    image_path = args.image_path
    
    if not os.path.exists(image_path):
        print(f"Error: La imagen '{image_path}' no existe.")
        return

    # Rutas absolutas/relativas del output
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(base_dir, "outputs")
    db_path = os.path.join(out_dir, "gastos_ejecutados.json")
    report_path = os.path.join(out_dir, "reporte_tickets.md")
    
    os.makedirs(out_dir, exist_ok=True)

    try:
        client = setup_client()
        
        datos = extract_receipt_data(client, image_path)
        
        if datos:
            # 1. Guardar en JSON (Base de Datos de Costos)
            gasto_id = save_to_db(datos, db_path)
            print(f"✓ Datos extraídos y guardados en DB ({gasto_id})")
            
            # 2. Generar reporte estético para el humano
            generate_markdown_report(datos, os.path.basename(image_path), report_path)
            print(f"✓ Reporte visual actualizado en {report_path}")
            
    except Exception as e:
        print(f"Error crítico en la ejecución: {e}")

if __name__ == "__main__":
    main()
