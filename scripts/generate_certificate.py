import os
import json
import argparse
from datetime import datetime

def load_json(ruta):
    """Carga segura de JSON"""
    if os.path.exists(ruta):
        with open(ruta, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def m(val):
    """Formateo de moneda ARS"""
    return f"$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def generate_weekly_certificate(semana_objetivo, ruta_gastos, ruta_presupuesto, ruta_cronograma, ruta_salida):
    """
    Genera el cruce entre los gastos reales y el presupuesto teórico.
    """
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Generando Certificado para la Semana {semana_objetivo}...")
    
    # 1. Cargar Datos
    gastos_db = load_json(ruta_gastos).get("gastos", [])
    
    # MOCK: Como calcular_budget.py y generate_schedule.py aún no escupen el JSON consolidado final,
    # simularemos un presupuesto semanal teórico para efectos de la demostración arquitectónica.
    # En producción real, esto leerá los diccionarios reales de esos scripts.
    presupuesto_teorico_semanal = 1500000.00  # 1.5M ARS teóricos esperados para una semana promedio
    
    # 2. Filtrar Gastos (Acá en prod filtraríamos por fecha coincidente con la "Semana X")
    # Para la demo, tomaremos todos los tickets ingresados como parte de este periodo.
    gastos_periodo = gastos_db
    
    # 3. Matemática de Auditoría
    total_materiales = sum(g.get("subtotal_neto", 0) for g in gastos_periodo)
    total_iva = sum(g.get("total_iva", 0) for g in gastos_periodo)
    total_real = sum(g.get("total_factura", 0) for g in gastos_periodo)
    
    desvio = presupuesto_teorico_semanal - total_real
    estado_desvio = "<span style='color: #10B981; font-weight: bold;'>BAJO PRESUPUESTO</span>" if desvio >= 0 else "<span style='color: #EF4444; font-weight: bold;'>SOBREPRESUPUESTO</span>"
    pct_consumido = (total_real / presupuesto_teorico_semanal) * 100 if presupuesto_teorico_semanal > 0 else 0
    
    # 4. Generar Reporte Markdown Estético
    md = f"""# Certificado de Obra - SEMANA {semana_objetivo}
*Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*

## Curva de Inversión y Auditoría

| Métrica | Monto ARS |
| :--- | :--- |
| **Inversión Teórica Programada:** | {m(presupuesto_teorico_semanal)} |
| **Inversión Real Ejecutada:** | {m(total_real)} |
| **Desvío del Período:** | {m(abs(desvio))} |
| **Estado:** | {estado_desvio} ({pct_consumido:.1f}% de lo proyectado) |

---

## Resumen de Tickets Ingresados (Gastos Reales)

"""
    
    if not gastos_periodo:
        md += "> *No se han registrado facturas ni movimientos en este período.*\n\n"
    else:
        for idx, gasto in enumerate(gastos_periodo, 1):
            md += f"### {idx}. {gasto.get('emisor', 'Proveedor')} \n"
            md += f"- **ID Ticket:** `{gasto.get('id', 'N/A')}`\n"
            md += f"- **Fecha:** {gasto.get('fecha', 'N/A')}\n"
            md += f"- **Total Facturado:** **{m(gasto.get('total_factura', 0))}**\n\n"
            
            # Tabla desplegable (detalles)
            md += "<details><summary>👉 Ver detalle de materiales facturados</summary>\n\n"
            md += "| Ítem | Cantidad | Unidad | P.Unit | Subtotal |\n"
            md += "| :--- | :---: | :---: | :---: | :---: |\n"
            for mat in gasto.get("materiales", []):
                md += f"| {mat.get('nombre')} | {mat.get('cantidad')} | {mat.get('unidad')} | {m(mat.get('precio_unitario',0))} | *{m(mat.get('subtotal',0))}* |\n"
            md += "\n</details>\n\n<br>\n"
            
    md += """
---
*Reporte emitido Automáticamente por el **Agente Audítor (Presupuestos)** de Arch Proposal Suite.*
"""

    # Guardar archivo
    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
    with open(ruta_salida, 'w', encoding='utf-8') as f:
        f.write(md)

def main():
    parser = argparse.ArgumentParser(description="Genera el Certificado de Obra cruzando costos y cronograma")
    parser.add_argument("--semana", type=int, default=1, help="Número de semana a certificar")
    args = parser.parse_args()

    # Rutas
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(base_dir, "outputs")
    
    ruta_gastos = os.path.join(out_dir, "gastos_ejecutados.json")
    # Los siguientes no existen aún realmente, es la interfaz para el futuro
    ruta_presu = os.path.join(out_dir, "presupuesto_referencia.json")
    ruta_crono = os.path.join(out_dir, "cronograma.json")
    
    ruta_salida = os.path.join(out_dir, f"certificado_semana_{args.semana}.md")
    
    try:
        generate_weekly_certificate(args.semana, ruta_gastos, ruta_presu, ruta_crono, ruta_salida)
        print(f"✓ Certificado Semanal generado exitosamente en: {ruta_salida}")
    except Exception as e:
        print(f"Error generando certificado: {e}")

if __name__ == "__main__":
    main()
