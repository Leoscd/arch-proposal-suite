import os
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime, date

BASE_DIR = Path(__file__).parent.parent


def actualizar_calendario(semana_numero: int, ruta_certificado: str):
    """Actualiza calendario_certificados.json marcando el certificado como generado."""
    calendario_path = BASE_DIR / "outputs" / "documentacion" / "calendario_certificados.json"
    if not calendario_path.exists():
        return
    with calendario_path.open(encoding="utf-8") as f:
        calendario = json.load(f)
    for semana in calendario.get("semanas", []):
        if semana["numero"] == semana_numero:
            semana["certificado_generado"] = True
            semana["archivo_certificado"] = str(ruta_certificado)
            break
    with calendario_path.open("w", encoding="utf-8") as f:
        json.dump(calendario, f, ensure_ascii=False, indent=2)
    print(f"[Calendario] Semana {semana_numero} marcada como certificada.")

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

def calcular_curva_s(cronograma: dict) -> dict:
    """
    Calcula cuánto presupuesto teórico corresponde a cada semana.
    Itera las tareas del cronograma, identifica en qué semana(s) cae cada una
    por fecha_inicio/fecha_fin, y distribuye el costo_total_ars proporcionalmente.

    Retorna: {"semana_1": monto, "semana_2": monto, ...}
    """
    tareas = cronograma.get("tareas", [])
    if not tareas:
        return {}

    # Determinar fecha inicio del proyecto
    fecha_inicio_str = cronograma.get("configuracion", {}).get("fecha_inicio")
    if fecha_inicio_str:
        fecha_inicio_proyecto = date.fromisoformat(fecha_inicio_str)
    else:
        # Usar la fecha mínima de inicio entre todas las tareas
        fechas = [date.fromisoformat(t["inicio"]) for t in tareas if t.get("inicio")]
        if not fechas:
            return {}
        fecha_inicio_proyecto = min(fechas)

    curva = {}
    for tarea in tareas:
        inicio_str = tarea.get("inicio")
        fin_str = tarea.get("fin")
        costo = tarea.get("costo_total_ars", 0.0)
        if not inicio_str or not fin_str or costo == 0:
            continue

        fecha_inicio_tarea = date.fromisoformat(inicio_str)
        fecha_fin_tarea = date.fromisoformat(fin_str)

        semana_inicio = (fecha_inicio_tarea - fecha_inicio_proyecto).days // 7 + 1
        semana_fin = (fecha_fin_tarea - fecha_inicio_proyecto).days // 7 + 1

        n_semanas = semana_fin - semana_inicio + 1
        costo_por_semana = costo / n_semanas

        for s in range(semana_inicio, semana_fin + 1):
            clave = f"semana_{s}"
            curva[clave] = curva.get(clave, 0.0) + costo_por_semana

    return curva


def leer_curva_inversion(base_dir: Path, semana_objetivo: int):
    """
    Intenta leer curva_inversion.json y devuelve (proyectado_total, proyectado_acumulado, pct_acumulado).
    Si el archivo no existe o la semana no está presente, devuelve (None, None, None).
    """
    ruta_curva = base_dir / "outputs" / "curva_inversion.json"
    if not ruta_curva.exists():
        return None, None, None
    try:
        with ruta_curva.open(encoding="utf-8") as f:
            curva = json.load(f)
        for semana in curva.get("semanas", []):
            if semana.get("numero") == semana_objetivo:
                return (
                    semana.get("proyectado_total", 0.0),
                    semana.get("proyectado_acumulado", 0.0),
                    semana.get("pct_acumulado", 0.0),
                )
    except (json.JSONDecodeError, KeyError):
        pass
    return None, None, None


def generate_weekly_certificate(semana_objetivo, ruta_gastos, ruta_presupuesto, ruta_cronograma, ruta_salida):
    """
    Genera el cruce entre los gastos reales y el presupuesto teórico.
    Lee gastos_reales[] desde estado-proyecto.json (fuente única de verdad).
    """
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Generando Certificado para la Semana {semana_objetivo}...")

    # 1. Cargar Datos — leer de estado-proyecto.json (fuente única de verdad)
    estado = load_json(ruta_gastos)
    todos_los_gastos = estado.get("gastos_reales", [])

    # Filtrar gastos que pertenecen a la semana objetivo
    gastos_db = [g for g in todos_los_gastos if g.get("semana") == semana_objetivo]
    # Fallback: si ningún gasto tiene campo "semana", tomar todos (compatibilidad)
    if not gastos_db and todos_los_gastos:
        gastos_db = todos_los_gastos

    # Determinar presupuesto teórico semanal:
    # Primero intentar desde curva_inversion.json (basada en presupuesto_base.json real).
    # Si no existe, usar calcular_curva_s() sobre el cronograma como fallback.
    proyectado_curva, proyectado_acumulado, pct_acumulado_curva = leer_curva_inversion(BASE_DIR, semana_objetivo)

    if proyectado_curva is not None:
        presupuesto_teorico_semanal = proyectado_curva
        fuente_proyectado = "curva_inversion.json"
        print(f"[Curva] Usando curva_inversion.json — semana {semana_objetivo}: {m(presupuesto_teorico_semanal)}")
    else:
        cronograma = load_json(ruta_cronograma)
        curva_s = calcular_curva_s(cronograma)
        clave_semana = f"semana_{semana_objetivo}"
        presupuesto_teorico_semanal = curva_s.get(clave_semana, 0.0)
        proyectado_acumulado = None
        pct_acumulado_curva = None
        fuente_proyectado = "curva_s (fallback desde cronograma)"
        print(f"[Curva] curva_inversion.json no encontrada — usando calcular_curva_s() como fallback.")

    # 2. Gastos del período ya filtrados por semana arriba
    gastos_periodo = gastos_db

    # 3. Matemática de Auditoría
    total_materiales = sum(g.get("subtotal_neto", 0) for g in gastos_periodo)
    total_iva = sum(g.get("total_iva", 0) for g in gastos_periodo)
    total_real = sum(g.get("total_ars", g.get("total_factura", 0)) for g in gastos_periodo)
    
    desvio = presupuesto_teorico_semanal - total_real
    estado_desvio = "<span style='color: #10B981; font-weight: bold;'>BAJO PRESUPUESTO</span>" if desvio >= 0 else "<span style='color: #EF4444; font-weight: bold;'>SOBREPRESUPUESTO</span>"
    pct_consumido = (total_real / presupuesto_teorico_semanal) * 100 if presupuesto_teorico_semanal > 0 else 0
    
    # Fila opcional % acumulado de la curva de inversión
    fila_pct_acumulado = ""
    if pct_acumulado_curva is not None and proyectado_acumulado is not None:
        fila_pct_acumulado = (
            f"| **Inversión Acumulada Proyectada:** | {m(proyectado_acumulado)} |\n"
            f"| **% Avance Acumulado (curva):** | {pct_acumulado_curva:.1f}% del presupuesto total |\n"
        )

    # 4. Generar Reporte Markdown Estético
    md = f"""# Certificado de Obra - SEMANA {semana_objetivo}
*Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*Fuente del proyectado: {fuente_proyectado}*

## Curva de Inversión y Auditoría

| Métrica | Monto ARS |
| :--- | :--- |
| **Inversión Teórica Programada:** | {m(presupuesto_teorico_semanal)} |
| **Inversión Real Ejecutada:** | {m(total_real)} |
| **Desvío del Período:** | {m(abs(desvio))} |
| **Estado:** | {estado_desvio} ({pct_consumido:.1f}% de lo proyectado) |
{fila_pct_acumulado}

---

## Resumen de Tickets Ingresados (Gastos Reales)

"""
    
    if not gastos_periodo:
        md += "> *No se han registrado facturas ni movimientos en este período.*\n\n"
    else:
        for idx, gasto in enumerate(gastos_periodo, 1):
            proveedor = gasto.get("proveedor", gasto.get("emisor", "Proveedor"))
            tipo = gasto.get("tipo", "factura").upper()
            total = gasto.get("total_ars", gasto.get("total_factura", 0))
            md += f"### {idx}. {proveedor} `[{tipo}]`\n"
            md += f"- **ID Ticket:** `{gasto.get('id', 'N/A')}`\n"
            md += f"- **Fecha:** {gasto.get('fecha', 'N/A')}\n"
            md += f"- **Total:** **{m(total)}**\n\n"

            # Tabla desplegable (detalles)
            md += "<details><summary>👉 Ver detalle de materiales</summary>\n\n"
            md += "| Ítem | Cantidad | Unidad | P.Unit | Subtotal |\n"
            md += "| :--- | :---: | :---: | :---: | :---: |\n"
            # Soporta tanto "items" (schema nuevo) como "materiales" (schema legacy)
            for mat in gasto.get("items", gasto.get("materiales", [])):
                nombre = mat.get("descripcion", mat.get("nombre", ""))
                precio = mat.get("precio_unit", mat.get("precio_unitario", 0))
                md += f"| {nombre} | {mat.get('cantidad')} | {mat.get('unidad')} | {m(precio)} | *{m(mat.get('subtotal',0))}* |\n"
            md += "\n</details>\n\n<br>\n"
            
    md += """
---
*Reporte emitido Automáticamente por el **Agente Audítor (Presupuestos)** de Arch Proposal Suite.*
"""

    # Guardar archivo
    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
    with open(ruta_salida, 'w', encoding='utf-8') as f:
        f.write(md)

    # Snapshot: copiar a outputs/documentacion/certificados/certificado_semana_N.html
    certs_dir = BASE_DIR / "outputs" / "documentacion" / "certificados"
    certs_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = certs_dir / f"certificado_semana_{semana_objetivo}.html"
    shutil.copy2(ruta_salida, snapshot_path)
    print(f"[Snapshot] Certificado copiado en: {snapshot_path}")

    # Actualizar calendario_certificados.json
    actualizar_calendario(semana_objetivo, str(snapshot_path))

def main():
    parser = argparse.ArgumentParser(description="Genera el Certificado de Obra cruzando costos y cronograma")
    parser.add_argument("--semana", type=int, default=1, help="Número de semana a certificar")
    args = parser.parse_args()

    # Rutas
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(base_dir, "outputs")
    
    # Fuente única de verdad: estado-proyecto.json (gastos_reales[])
    ruta_gastos = os.path.join(out_dir, "estado-proyecto.json")
    ruta_presu = os.path.join(out_dir, "presupuesto_referencia.json")
    ruta_crono = os.path.join(out_dir, "cronograma.json")

    ruta_salida = os.path.join(out_dir, "documentacion", "certificados", f"certificado_semana_{args.semana}.md")
    
    try:
        generate_weekly_certificate(args.semana, ruta_gastos, ruta_presu, ruta_crono, ruta_salida)
        print(f"✓ Certificado Semanal generado exitosamente en: {ruta_salida}")
    except Exception as e:
        print(f"Error generando certificado: {e}")

if __name__ == "__main__":
    main()
