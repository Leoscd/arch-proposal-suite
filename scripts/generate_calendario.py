#!/usr/bin/env python3
"""
generate_calendario.py — Genera el calendario de certificados semanales.
Lee cronograma.json y calcula las fechas y montos teóricos de cada semana
usando la curva S del proyecto.
"""

import json
import sys
from datetime import datetime, date, timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
RUTA_CRONOGRAMA = BASE_DIR / "outputs" / "cronograma.json"
RUTA_SALIDA = BASE_DIR / "outputs" / "documentacion" / "calendario_certificados.json"


def load_json(ruta: Path) -> dict:
    """Carga segura de JSON."""
    if ruta.exists():
        with open(ruta, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


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


def obtener_tareas_activas_semana(tareas: list, fecha_inicio_proyecto: date, numero_semana: int) -> list:
    """
    Retorna los nombres de tareas que están activas durante una semana dada.
    Una tarea está activa si su rango de fechas se superpone con la semana.
    """
    fecha_inicio_semana = fecha_inicio_proyecto + timedelta(weeks=numero_semana - 1)
    fecha_fin_semana = fecha_inicio_semana + timedelta(days=6)

    activas = []
    for tarea in tareas:
        inicio_str = tarea.get("inicio")
        fin_str = tarea.get("fin")
        if not inicio_str or not fin_str:
            continue
        fecha_inicio_tarea = date.fromisoformat(inicio_str)
        fecha_fin_tarea = date.fromisoformat(fin_str)

        # Superposición: inicio_tarea <= fin_semana AND fin_tarea >= inicio_semana
        if fecha_inicio_tarea <= fecha_fin_semana and fecha_fin_tarea >= fecha_inicio_semana:
            nombre = tarea.get("elemento", "Tarea sin nombre")
            activas.append(nombre)

    return activas


def generar_calendario(cronograma: dict) -> dict:
    """
    Genera la estructura completa del calendario de certificados.
    """
    curva_s = calcular_curva_s(cronograma)
    if not curva_s:
        print("[ERROR] No se pudo calcular la curva S. Verifique que cronograma.json contiene tareas.", file=sys.stderr)
        sys.exit(1)

    # Fecha inicio del proyecto
    fecha_inicio_str = cronograma.get("configuracion", {}).get("fecha_inicio")
    if fecha_inicio_str:
        fecha_inicio_proyecto = date.fromisoformat(fecha_inicio_str)
    else:
        tareas = cronograma.get("tareas", [])
        fechas = [date.fromisoformat(t["inicio"]) for t in tareas if t.get("inicio")]
        fecha_inicio_proyecto = min(fechas)

    tareas = cronograma.get("tareas", [])
    rubros_incluidos = cronograma.get("alcance", {}).get("rubros_incluidos", [])

    # Ordenar semanas numéricamente
    numeros_semana = sorted(
        int(clave.split("_")[1]) for clave in curva_s.keys()
    )
    total_semanas = max(numeros_semana)

    semanas = []
    for n in numeros_semana:
        fecha_inicio_semana = fecha_inicio_proyecto + timedelta(weeks=n - 1)
        fecha_fin_semana = fecha_inicio_semana + timedelta(days=6)
        presupuesto = curva_s.get(f"semana_{n}", 0.0)
        tareas_activas = obtener_tareas_activas_semana(tareas, fecha_inicio_proyecto, n)

        semanas.append({
            "numero": n,
            "fecha_inicio": fecha_inicio_semana.isoformat(),
            "fecha_fin": fecha_fin_semana.isoformat(),
            "presupuesto_teorico_ars": round(presupuesto, 2),
            "tareas_activas": tareas_activas,
            "certificado_generado": False,
            "archivo_certificado": None,
        })

    calendario = {
        "generado": datetime.now().isoformat(),
        "rubros_incluidos": rubros_incluidos,
        "total_semanas": total_semanas,
        "fecha_inicio_proyecto": fecha_inicio_proyecto.isoformat(),
        "semanas": semanas,
    }

    return calendario


def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Cargando cronograma desde: {RUTA_CRONOGRAMA}")
    cronograma = load_json(RUTA_CRONOGRAMA)

    if not cronograma:
        print(f"[ERROR] No se encontró o está vacío: {RUTA_CRONOGRAMA}", file=sys.stderr)
        sys.exit(1)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Calculando curva S y generando calendario...")
    calendario = generar_calendario(cronograma)

    RUTA_SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(RUTA_SALIDA, "w", encoding="utf-8") as f:
        json.dump(calendario, f, ensure_ascii=False, indent=2)

    total = calendario["total_semanas"]
    presupuesto_total = sum(s["presupuesto_teorico_ars"] for s in calendario["semanas"])
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Calendario generado exitosamente.")
    print(f"  Semanas planificadas : {total}")
    print(f"  Presupuesto total    : $ {presupuesto_total:,.2f} ARS")
    print(f"  Archivo de salida    : {RUTA_SALIDA}")


if __name__ == "__main__":
    main()
