"""
generate_curva_inversion.py
===========================
Lee presupuesto_base.json + cronograma.json y genera curva_inversion.json.

Lógica:
- Mapea cada rubro del presupuesto a la tarea correspondiente en el cronograma
  usando coincidencia de keywords en el nombre del rubro / elemento.
- Distribuye el subtotal_rubro proporcionalmente entre las semanas en que
  esa tarea está activa (por días calendario).
- Produce curva_inversion.json con proyectado semanal y acumulado.

Uso:
    python scripts/generate_curva_inversion.py
"""

import json
import os
from datetime import date, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(ruta: str) -> dict:
    if os.path.exists(ruta):
        with open(ruta, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def m(val: float) -> str:
    """Formateo de moneda ARS."""
    return f"$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def semanas_entre(fecha_inicio_proyecto: date, fecha_inicio_tarea: date, fecha_fin_tarea: date):
    """
    Devuelve lista de (numero_semana, dias_activos_en_esa_semana).
    Semana 1 = días 0-6 desde fecha_inicio_proyecto.
    """
    resultado = []
    dia_inicio_tarea = (fecha_inicio_tarea - fecha_inicio_proyecto).days
    dia_fin_tarea = (fecha_fin_tarea - fecha_inicio_proyecto).days

    semana_inicio = dia_inicio_tarea // 7 + 1
    semana_fin = dia_fin_tarea // 7 + 1

    for s in range(semana_inicio, semana_fin + 1):
        dia_s_inicio = (s - 1) * 7
        dia_s_fin = s * 7 - 1
        solapamiento_inicio = max(dia_inicio_tarea, dia_s_inicio)
        solapamiento_fin = min(dia_fin_tarea, dia_s_fin)
        dias = solapamiento_fin - solapamiento_inicio + 1
        if dias > 0:
            resultado.append((s, dias))

    return resultado


def normalizar_nombre(texto: str) -> str:
    """Convierte a minúsculas sin tildes para comparación."""
    reemplazos = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
        "Á": "a", "É": "e", "Í": "i", "Ó": "o", "Ú": "u",
        "ñ": "n", "Ñ": "n",
    }
    for k, v in reemplazos.items():
        texto = texto.replace(k, v)
    return texto.lower()


# Mapeo de keywords del nombre de rubro del presupuesto → keywords del elemento del cronograma.
# Se busca la primera tarea del cronograma que contenga alguna keyword del valor.
MAPA_RUBROS = {
    "TRABAJOS PREPARATORIOS": ["preparatorio", "preparacion", "limpieza", "replanteo"],
    "MOVIMIENTO DE TIERRA": ["tierra", "excavacion", "movimiento"],
    "CIMIENTOS": ["cimiento", "fundacion"],
    "ESTRUCTURAS": ["estructura", "losa", "columna", "viga"],
    "MAMPOSTERIAS": ["mamposteria", "cerramiento", "ladrillo", "tabique"],
    "REVOQUES": ["revoque"],
    "CONTRAPISOS Y CARPETAS": ["contrapiso", "carpeta"],
    "PISOS": ["piso", "zocalo", "revestimiento"],
    "CUBIERTAS": ["cubierta", "techo"],
    "INSTALACIONES": ["instalacion"],
    "PINTURAS": ["pintura", "tratamiento"],
    "CIELORRASOS": ["cielorraso"],
    "AISLACIONES": ["aislacion"],
}


def buscar_tarea(nombre_rubro: str, tareas: list) -> dict | None:
    """
    Busca la tarea del cronograma más relacionada con el nombre del rubro.
    Primero intenta el mapa predefinido; si no, hace match directo por palabras.
    """
    nombre_norm = normalizar_nombre(nombre_rubro)

    # 1. Intentar con el mapa predefinido
    keywords_candidatas = []
    for clave_mapa, keywords in MAPA_RUBROS.items():
        if normalizar_nombre(clave_mapa) in nombre_norm or nombre_norm in normalizar_nombre(clave_mapa):
            keywords_candidatas = keywords
            break

    for tarea in tareas:
        elemento_norm = normalizar_nombre(tarea.get("elemento", ""))
        if keywords_candidatas:
            for kw in keywords_candidatas:
                if kw in elemento_norm:
                    return tarea
        else:
            # Fallback: comparar palabras directamente
            palabras = nombre_norm.split()
            for palabra in palabras:
                if len(palabra) > 4 and palabra in elemento_norm:
                    return tarea

    return None


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def generar_curva_inversion(
    ruta_presupuesto: str,
    ruta_cronograma: str,
    ruta_salida: str,
) -> dict:
    from datetime import datetime

    presupuesto = load_json(ruta_presupuesto)
    cronograma = load_json(ruta_cronograma)

    rubros = presupuesto.get("rubros", [])
    tareas = cronograma.get("tareas", [])
    config = cronograma.get("configuracion", {})

    if not rubros:
        raise ValueError("presupuesto_base.json no contiene rubros.")
    if not tareas:
        raise ValueError("cronograma.json no contiene tareas.")

    # Fecha de inicio del proyecto
    fecha_inicio_str = config.get("fecha_inicio")
    if fecha_inicio_str:
        fecha_inicio_proyecto = date.fromisoformat(fecha_inicio_str)
    else:
        fechas = [date.fromisoformat(t["inicio"]) for t in tareas if t.get("inicio")]
        if not fechas:
            raise ValueError("No se pudo determinar la fecha de inicio del proyecto.")
        fecha_inicio_proyecto = min(fechas)

    # Fecha fin del proyecto
    fechas_fin = [date.fromisoformat(t["fin"]) for t in tareas if t.get("fin")]
    fecha_fin_proyecto = max(fechas_fin)

    # Cantidad total de semanas
    duracion_dias = (fecha_fin_proyecto - fecha_inicio_proyecto).days
    n_semanas = duracion_dias // 7 + 1

    # Inicializar estructura de semanas
    semanas_data = {}
    for s in range(1, n_semanas + 1):
        inicio_s = fecha_inicio_proyecto + timedelta(days=(s - 1) * 7)
        fin_s = fecha_inicio_proyecto + timedelta(days=s * 7 - 1)
        semanas_data[s] = {
            "numero": s,
            "fecha_inicio": inicio_s.isoformat(),
            "fecha_fin": fin_s.isoformat(),
            "rubros_activos": [],
            "proyectado_materiales": 0.0,
            "proyectado_mo": 0.0,
            "proyectado_total": 0.0,
        }

    # Distribuir costos del presupuesto en las semanas del cronograma
    rubros_sin_tarea = []
    for rubro in rubros:
        nombre_rubro = rubro.get("nombre", "")
        subtotal_mat = rubro.get("subtotal_materiales", 0.0)
        subtotal_mo = rubro.get("subtotal_mo", 0.0)
        subtotal_total = rubro.get("subtotal_rubro", 0.0)

        tarea = buscar_tarea(nombre_rubro, tareas)

        if tarea is None:
            rubros_sin_tarea.append(nombre_rubro)
            # Distribuir uniformemente en todas las semanas como fallback
            por_semana_mat = subtotal_mat / n_semanas if n_semanas > 0 else 0
            por_semana_mo = subtotal_mo / n_semanas if n_semanas > 0 else 0
            por_semana_total = subtotal_total / n_semanas if n_semanas > 0 else 0
            for s in semanas_data:
                semanas_data[s]["proyectado_materiales"] += por_semana_mat
                semanas_data[s]["proyectado_mo"] += por_semana_mo
                semanas_data[s]["proyectado_total"] += por_semana_total
                if nombre_rubro not in semanas_data[s]["rubros_activos"]:
                    semanas_data[s]["rubros_activos"].append(nombre_rubro)
            continue

        fecha_inicio_tarea = date.fromisoformat(tarea["inicio"])
        fecha_fin_tarea = date.fromisoformat(tarea["fin"])
        duracion_tarea_dias = (fecha_fin_tarea - fecha_inicio_tarea).days + 1

        distribucion = semanas_entre(fecha_inicio_proyecto, fecha_inicio_tarea, fecha_fin_tarea)

        for (s, dias_activos) in distribucion:
            proporcion = dias_activos / duracion_tarea_dias
            if s not in semanas_data:
                # Semana fuera del rango esperado — ampliar
                inicio_s = fecha_inicio_proyecto + timedelta(days=(s - 1) * 7)
                fin_s = fecha_inicio_proyecto + timedelta(days=s * 7 - 1)
                semanas_data[s] = {
                    "numero": s,
                    "fecha_inicio": inicio_s.isoformat(),
                    "fecha_fin": fin_s.isoformat(),
                    "rubros_activos": [],
                    "proyectado_materiales": 0.0,
                    "proyectado_mo": 0.0,
                    "proyectado_total": 0.0,
                }
            semanas_data[s]["proyectado_materiales"] += subtotal_mat * proporcion
            semanas_data[s]["proyectado_mo"] += subtotal_mo * proporcion
            semanas_data[s]["proyectado_total"] += subtotal_total * proporcion
            if nombre_rubro not in semanas_data[s]["rubros_activos"]:
                semanas_data[s]["rubros_activos"].append(nombre_rubro)

    # Calcular acumulados y porcentajes
    total_presupuesto = presupuesto.get("resumen", {}).get("total_sin_honorarios", 0.0)
    if total_presupuesto == 0:
        total_presupuesto = sum(r.get("subtotal_rubro", 0.0) for r in rubros)

    acumulado = 0.0
    semanas_lista = []
    for s in sorted(semanas_data.keys()):
        entrada = semanas_data[s]
        entrada["proyectado_materiales"] = round(entrada["proyectado_materiales"], 2)
        entrada["proyectado_mo"] = round(entrada["proyectado_mo"], 2)
        entrada["proyectado_total"] = round(entrada["proyectado_total"], 2)
        acumulado += entrada["proyectado_total"]
        entrada["proyectado_acumulado"] = round(acumulado, 2)
        entrada["pct_acumulado"] = round((acumulado / total_presupuesto) * 100, 2) if total_presupuesto > 0 else 0.0
        semanas_lista.append(entrada)

    curva = {
        "fecha_generacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_presupuesto": round(total_presupuesto, 2),
        "n_semanas": len(semanas_lista),
        "fecha_inicio_proyecto": fecha_inicio_proyecto.isoformat(),
        "fecha_fin_proyecto": fecha_fin_proyecto.isoformat(),
        "semanas": semanas_lista,
    }

    # Guardar
    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(curva, f, ensure_ascii=False, indent=2)

    return curva, rubros_sin_tarea


# ---------------------------------------------------------------------------
# Main — resumen impreso
# ---------------------------------------------------------------------------

def main():
    base_dir = str(BASE_DIR)
    out_dir = os.path.join(base_dir, "outputs")

    ruta_presupuesto = os.path.join(out_dir, "presupuesto_base.json")
    ruta_cronograma = os.path.join(out_dir, "cronograma.json")
    ruta_salida = os.path.join(out_dir, "curva_inversion.json")

    print("=" * 60)
    print("  GENERADOR DE CURVA DE INVERSION")
    print("=" * 60)

    # Validaciones previas
    for ruta, nombre in [(ruta_presupuesto, "presupuesto_base.json"), (ruta_cronograma, "cronograma.json")]:
        if not os.path.exists(ruta):
            print(f"[ERROR] No se encontró: {ruta}")
            print(f"        Asegurate de que '{nombre}' exista en outputs/")
            return

    try:
        curva, rubros_sin_tarea = generar_curva_inversion(ruta_presupuesto, ruta_cronograma, ruta_salida)
    except Exception as e:
        print(f"[ERROR] {e}")
        return

    print(f"\n  Proyecto       : {date.fromisoformat(curva['fecha_inicio_proyecto']).strftime('%d/%m/%Y')} "
          f"— {date.fromisoformat(curva['fecha_fin_proyecto']).strftime('%d/%m/%Y')}")
    print(f"  Semanas totales: {curva['n_semanas']}")
    print(f"  Presupuesto    : {m(curva['total_presupuesto'])}")

    if rubros_sin_tarea:
        print(f"\n  [WARN] Rubros sin tarea en cronograma (distribuidos uniformemente):")
        for r in rubros_sin_tarea:
            print(f"         - {r}")

    print(f"\n  {'SEMANA':<8} {'INICIO':<13} {'FIN':<13} {'PROYECTADO':>18} {'ACUMULADO':>18} {'%':>7}")
    print("  " + "-" * 80)
    for s in curva["semanas"]:
        print(
            f"  {s['numero']:<8} "
            f"{s['fecha_inicio']:<13} "
            f"{s['fecha_fin']:<13} "
            f"{m(s['proyectado_total']):>18} "
            f"{m(s['proyectado_acumulado']):>18} "
            f"{s['pct_acumulado']:>6.1f}%"
        )

    print(f"\n  [OK] curva_inversion.json guardada en: {ruta_salida}")
    print("=" * 60)


if __name__ == "__main__":
    main()
