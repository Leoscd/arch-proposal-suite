"""
build_landing.py
─────────────────────────────────────────────────────────────────────────────
Genera la landing page del cliente reemplazando placeholders en la template.

Uso:
    python3 scripts/build_landing.py
    python3 scripts/build_landing.py --resumen "Texto personalizado del ejecutivo"
    python3 scripts/build_landing.py --salida outputs/landing/mi_proyecto.html
    python3 scripts/build_landing.py --estudio "Estudio Pérez Arquitectos"
"""

import os
import sys
import json
import glob
import argparse
from datetime import date, datetime

# ─────────────────────────────────────────────────────────────────────────────
# RUTAS BASE
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR      = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT    = os.path.dirname(SCRIPT_DIR)

ESTADO_JSON     = os.path.join(PROJECT_ROOT, "estado-proyecto.json")
CRONOGRAMA_JSON = os.path.join(PROJECT_ROOT, "outputs", "cronograma.json")
SNAPSHOTS_DIR   = os.path.join(PROJECT_ROOT, "outputs", "snapshots")
TEMPLATE_HTML   = os.path.join(PROJECT_ROOT, "templates", "landing", "index.html")
DEFAULT_SALIDA  = os.path.join(PROJECT_ROOT, "outputs", "landing", "index.html")

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS DE FORMATO
# ─────────────────────────────────────────────────────────────────────────────

def fmt_ars(valor: float) -> str:
    """Formatea un número como moneda ARS con separadores de miles (estilo argentino)."""
    return "$ {:,.0f}".format(valor).replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_fecha(fecha_str: str) -> str:
    """Convierte 'YYYY-MM-DD' a 'DD/MM/YYYY' para lectura humana."""
    try:
        dt = datetime.strptime(fecha_str, "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return fecha_str


# ─────────────────────────────────────────────────────────────────────────────
# LOGICA DE SEMAFORO
# ─────────────────────────────────────────────────────────────────────────────

SEMAFORO_MAP = {
    "VERDE": {
        "color":       "#10B981",
        "texto":       "EN PRESUPUESTO",
        "descripcion": "El proyecto avanza dentro del presupuesto y cronograma planificados.",
    },
    "AMARILLO": {
        "color":       "#F59E0B",
        "texto":       "ATENCION",
        "descripcion": "El proyecto presenta desvios menores que requieren seguimiento.",
    },
    "ROJO": {
        "color":       "#EF4444",
        "texto":       "ALERTA",
        "descripcion": "El proyecto presenta desvios significativos. Se requiere revision inmediata.",
    },
}


def resolver_semaforo(clave: str) -> dict:
    """Devuelve color, texto y descripcion para la clave de semaforo dada."""
    clave_norm = clave.strip().upper()
    return SEMAFORO_MAP.get(clave_norm, SEMAFORO_MAP["VERDE"])


# ─────────────────────────────────────────────────────────────────────────────
# CARGA DE DATOS
# ─────────────────────────────────────────────────────────────────────────────

def cargar_estado() -> dict:
    """Carga estado-proyecto.json. Devuelve dict vacio si no existe."""
    if not os.path.isfile(ESTADO_JSON):
        print(f"  [!]  No se encontro {ESTADO_JSON}. Usando valores por defecto.")
        return {}
    with open(ESTADO_JSON, encoding="utf-8") as f:
        return json.load(f)


def cargar_cronograma() -> dict:
    """Carga outputs/cronograma.json. Devuelve dict vacio si no existe."""
    if not os.path.isfile(CRONOGRAMA_JSON):
        print(f"  [!]  No se encontro {CRONOGRAMA_JSON}. Usando valores por defecto.")
        return {}
    with open(CRONOGRAMA_JSON, encoding="utf-8") as f:
        return json.load(f)


def cargar_snapshot_mas_reciente() -> dict:
    """
    Busca todos los archivos semana_*.json en outputs/snapshots/ y devuelve
    el contenido del mas reciente (mayor numero de semana). Devuelve {} si no hay ninguno.
    """
    patron = os.path.join(SNAPSHOTS_DIR, "semana_*.json")
    archivos = glob.glob(patron)
    if not archivos:
        print("  [!]  No se encontraron snapshots. Semaforo: VERDE por defecto.")
        return {}

    def _num_semana(path: str) -> int:
        base  = os.path.basename(path)       # semana_3.json
        stem  = os.path.splitext(base)[0]    # semana_3
        partes = stem.split("_")
        try:
            return int(partes[-1])
        except (ValueError, IndexError):
            return 0

    archivos.sort(key=_num_semana)
    ultimo = archivos[-1]

    with open(ultimo, encoding="utf-8") as f:
        data = json.load(f)

    print(f"  [ok] Snapshot mas reciente: {os.path.basename(ultimo)}")
    return data


# ─────────────────────────────────────────────────────────────────────────────
# CALCULOS
# ─────────────────────────────────────────────────────────────────────────────

def calcular_gasto_ejecutado(estado: dict, snapshot: dict) -> float:
    """
    Calcula el gasto ejecutado acumulado.
    Prioridad 1: resumen_financiero.gastado_acumulado_ars del snapshot.
    Prioridad 2: suma de total_ars de gastos_reales en estado-proyecto.json.
    """
    resumen = snapshot.get("resumen_financiero", {})
    if "gastado_acumulado_ars" in resumen:
        return float(resumen["gastado_acumulado_ars"])

    gastos = estado.get("gastos_reales", [])
    if gastos:
        return sum(float(g.get("total_ars", 0)) for g in gastos)

    return 0.0


def calcular_presupuesto_total(estado: dict) -> float:
    """
    Extrae el presupuesto total validado.
    Busca 'total_ars' o suma todos los valores numericos del dict presupuesto_validado.
    """
    pv = estado.get("presupuesto_validado", {})
    if not pv:
        return 0.0
    if "total_ars" in pv:
        return float(pv["total_ars"])
    total = 0.0
    for v in pv.values():
        if isinstance(v, (int, float)):
            total += float(v)
    return total


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Genera la landing page del cliente para Arch Proposal Suite.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--resumen",
        type=str,
        default=None,
        help="Texto del resumen ejecutivo (HTML permitido). Si no se indica, se genera automaticamente.",
    )
    parser.add_argument(
        "--salida",
        type=str,
        default=DEFAULT_SALIDA,
        help=f"Ruta de salida del HTML generado (default: outputs/landing/index.html)",
    )
    parser.add_argument(
        "--estudio",
        type=str,
        default=None,
        help="Nombre del estudio de arquitectura (sobreescribe el valor del JSON).",
    )
    args = parser.parse_args()

    print("\n-- Arch Proposal Suite - build_landing.py --")

    # ── 1. Cargar datos ──────────────────────────────────────────────────────
    estado     = cargar_estado()
    cronograma = cargar_cronograma()
    snapshot   = cargar_snapshot_mas_reciente()

    # ── 2. Extraer metadatos ─────────────────────────────────────────────────
    metadatos = estado.get("metadatos", {})

    proyecto_nombre    = metadatos.get("proyecto_nombre", "Proyecto sin nombre")
    proyecto_localidad = metadatos.get(
        "localidad", metadatos.get("proyecto_localidad", "—")
    )
    comitente = metadatos.get("comitente", metadatos.get("cliente", "—"))

    estudio_nombre = (
        args.estudio
        or metadatos.get("estudio_nombre", metadatos.get("estudio", "Arch Proposal Suite"))
    )

    # ── 3. Finanzas ──────────────────────────────────────────────────────────
    presupuesto_total = calcular_presupuesto_total(estado)
    gasto_ejecutado   = calcular_gasto_ejecutado(estado, snapshot)

    # ── 4. Cronograma ────────────────────────────────────────────────────────
    fecha_fin_raw  = cronograma.get("fecha_fin_estimada", "")
    fecha_fin      = fmt_fecha(fecha_fin_raw) if fecha_fin_raw else "—"
    camino_critico = cronograma.get("camino_critico", [])
    camino_critico_str = ", ".join(camino_critico) if camino_critico else "No determinado"

    # ── 5. Snapshot: semaforo y avance ───────────────────────────────────────
    semaforo_clave = snapshot.get("semaforo", "VERDE")
    semaforo_data  = resolver_semaforo(semaforo_clave)

    resumen_tiempo  = snapshot.get("resumen_tiempo", {})
    avance_real_pct = float(resumen_tiempo.get("avance_real_pct", 0.0))

    # ── 6. Resumen ejecutivo ─────────────────────────────────────────────────
    if args.resumen:
        resumen_ejecutivo = "<p>" + args.resumen + "</p>"
    else:
        notas = snapshot.get("notas_director", "")
        parrafo_notas = (
            "<p><strong>Notas del director:</strong> " + notas + "</p>"
            if notas else ""
        )

        if presupuesto_total > 0:
            pct_gasto = (gasto_ejecutado / presupuesto_total) * 100
            linea_financiera = (
                "Se ha ejecutado el <strong>" + f"{pct_gasto:.1f}%" + "</strong> del presupuesto total "
                "(" + fmt_ars(gasto_ejecutado) + " de " + fmt_ars(presupuesto_total) + ")."
            )
        else:
            linea_financiera = (
                "Gasto ejecutado: <strong>" + fmt_ars(gasto_ejecutado) + "</strong>."
                if gasto_ejecutado else "Sin datos financieros cargados aun."
            )

        linea_cronograma = (
            "Avance de obra: <strong>" + f"{avance_real_pct:.1f}%" + "</strong>. "
            "Fecha fin estimada: <strong>" + fecha_fin + "</strong>."
        )

        resumen_ejecutivo = (
            "<p>El proyecto <strong>" + proyecto_nombre + "</strong> se encuentra en estado "
            "<strong style='color:" + semaforo_data["color"] + "'>" + semaforo_data["texto"] + "</strong>. "
            + semaforo_data["descripcion"] + "</p>"
            "<p>" + linea_financiera + " " + linea_cronograma + "</p>"
            + parrafo_notas
        )

    # ── 7. Fecha de emision ──────────────────────────────────────────────────
    fecha_emision = date.today().strftime("%d/%m/%Y")

    # ── 8. Leer template ─────────────────────────────────────────────────────
    if not os.path.isfile(TEMPLATE_HTML):
        print("\n[ERROR] No se encontro la template en:", TEMPLATE_HTML)
        sys.exit(1)

    with open(TEMPLATE_HTML, encoding="utf-8") as f:
        html = f.read()

    # ── 9. Reemplazar placeholders ───────────────────────────────────────────
    reemplazos = {
        "{{ESTUDIO_NOMBRE}}":        estudio_nombre,
        "{{PROYECTO_NOMBRE}}":       proyecto_nombre,
        "{{PROYECTO_LOCALIDAD}}":    proyecto_localidad,
        "{{COMITENTE}}":             comitente,
        "{{TOTAL_PRESUPUESTO_ARS}}": fmt_ars(presupuesto_total) if presupuesto_total else "—",
        "{{GASTO_EJECUTADO_ARS}}":   fmt_ars(gasto_ejecutado) if gasto_ejecutado else "—",
        "{{AVANCE_REAL_PCT}}":       f"{avance_real_pct:.1f}",
        "{{FECHA_FIN_ESTIMADA}}":    fecha_fin,
        "{{SEMAFORO_COLOR}}":        semaforo_data["color"],
        "{{SEMAFORO_TEXTO}}":        semaforo_data["texto"],
        "{{SEMAFORO_DESCRIPCION}}":  semaforo_data["descripcion"],
        "{{RESUMEN_EJECUTIVO}}":     resumen_ejecutivo,
        "{{FECHA_EMISION}}":         fecha_emision,
        "{{CAMINO_CRITICO}}":        camino_critico_str,
    }

    for placeholder, valor in reemplazos.items():
        html = html.replace(placeholder, str(valor))

    # ── 10. Escribir salida ───────────────────────────────────────────────────
    salida_path = args.salida
    salida_dir  = os.path.dirname(os.path.abspath(salida_path))
    os.makedirs(salida_dir, exist_ok=True)

    with open(salida_path, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(salida_path) / 1024
    print(f"\n[OK] Landing generada -> {salida_path}  ({size_kb:.1f} KB)")
    print(f"[ok] Semaforo: {semaforo_clave} | Avance: {avance_real_pct:.1f}% | Fin estimado: {fecha_fin}")
    print("-----------------------------------------------------------\n")


if __name__ == "__main__":
    main()
