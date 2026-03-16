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

def extract_receipt_data(client, image_path):
    """
    Envía la imagen de la factura al LLM de visión para extraer los datos estructurados.
    """
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Analizando imagen con Gemini Vision...")
    
    # Preparamos la imagen
    img = Image.open(image_path)
    
    # Prompt estricto para extraer JSON
    prompt = """
    Eres el Agente de Costos experto en extraer datos contables de tickets y facturas de materiales de construcción.
    Analiza esta factura/ticket y extrae los siguientes datos EXCLUSIVAMENTE en formato JSON válido, sin markdown ni explicaciones adicionales:
    
    {
        "emisor": "Nombre del proveedor o corralón",
        "fecha": "YYYY-MM-DD" (o null si no se encuentra),
        "tiene_iva": true/false (true si detalla IVA o dice Factura A, false si es B/C o Consumidor Final sin detallar),
        "materiales": [
            {
                "nombre": "Descripción del artículo",
                "cantidad": 1.5,
                "unidad": "u, kg, m, m2, m3, lt, bolsa, etc",
                "precio_unitario": 1500.50,
                "subtotal": 2250.75
            }
        ],
        "subtotal_neto": 0.0,
        "total_iva": 0.0,
        "total_factura": 0.0
    }
    
    Reglas:
    - Todos los montos deben ser números flotantes en Pesos Argentinos (ARS), sin símbolo "$" ni comas para miles.
    - Si un material no tiene unidad clara, asigna "un" (unidad).
    - Asegúrate de que la suma de "subtotal" de materiales coincida aprox con el total.
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
        
    md = f"""# Reporte de Ticket Procesado

**Emisor:** {data.get("emisor", "Desconocido")}  
**Fecha de Ticket:** {data.get("fecha", "No detectada")}  
**Condición IVA:** {"Discriminado (A)" if data.get("tiene_iva") else "Consumidor Final (B/C/T)"}  

## Detalle de Materiales Extraídos

| Material | Cantidad | Unidad | P. Unitario | Subtotal |
| :--- | :---: | :---: | :---: | :---: |
"""
    
    for mat in data.get("materiales", []):
        md += f"| {mat.get('nombre')} | {mat.get('cantidad')} | {mat.get('unidad')} | {m(mat.get('precio_unitario', 0))} | **{m(mat.get('subtotal', 0))}** |\n"
        
    md += f"""
---
**Subtotal Neto:** {m(data.get("subtotal_neto", 0))}  
**IVA:** {m(data.get("total_iva", 0))}  
### **TOTAL FACTURA:** {m(data.get("total_factura", 0))}

> *Dato guardado exitosamente en la base de datos del Agente Costos como ID: `{data.get("id")}`*
"""

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
