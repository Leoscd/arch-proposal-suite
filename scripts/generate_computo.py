#!/usr/bin/env python3
"""
generate_computo.py — Genera el cómputo de materiales consolidado.
Lee cronograma.json y presupuesto.json (si existe), extrae métricas físicas
por elemento, y produce outputs/documentacion/computo_materiales.json
"""

import json
from datetime import datetime, timezone
from pathlib import Path

# ─── Rutas ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
CRONOGRAMA_PATH  = BASE_DIR / "outputs" / "cronograma.json"
PRESUPUESTO_PATH = BASE_DIR / "outputs" / "presupuesto.json"
OUTPUT_DIR       = BASE_DIR / "outputs" / "documentacion"
OUTPUT_PATH      = OUTPUT_DIR / "computo_materiales.json"

# Mapeo de campos de métricas del cronograma a campos del cómputo.
# Clave  → nombre interno en metricas{}
# Valor  → nombre canónico en el JSON de salida
METRIC_MAP = {
    "volumen_m3":    "volumen_m3",
    "hormigon_m3":   "volumen_m3",      # alias usado en algunos rubros
    "acero_kg":      "acero_kg",
    "acero_total_kg":"acero_kg",        # alias
    "encofrado_m2":  "encofrado_m2",
    "longitud_ml":   "longitud_ml",
    "unidades":      "unidades",
    "area_m2":       "area_m2",
    "superficie_m2": "area_m2",         # alias
}

# Campos canónicos de métricas presentes en cada elemento de salida
METRIC_FIELDS = ["volumen_m3", "acero_kg", "encofrado_m2",
                 "longitud_ml", "area_m2", "unidades"]


def _cargar_json(path: Path) -> dict | list | None:
    """Carga un JSON desde disco; devuelve None si no existe."""
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _extraer_metricas(raw: dict) -> dict:
    """
    Convierte el dict `metricas` crudo del cronograma al formato canónico.
    Campos no presentes quedan en None.
    """
    out = {field: None for field in METRIC_FIELDS}
    if not raw:
        return out
    for src_key, canonical in METRIC_MAP.items():
        val = raw.get(src_key)
        if val is not None:
            out[canonical] = val
    return out


def _nombre_desde_elemento(elemento: str) -> str:
    """
    Extrae el nombre legible del campo 'elemento' del cronograma.
    Formato: "ID — Nombre Largo" → "Nombre Largo"
    """
    if " — " in elemento:
        return elemento.split(" — ", 1)[1].strip()
    if " - " in elemento:
        return elemento.split(" - ", 1)[1].strip()
    return elemento.strip()


def _rubro_desde_cronograma(cronograma: dict) -> str:
    """Determina el identificador de rubro a partir del alcance del cronograma."""
    alcance = cronograma.get("alcance", {})
    modo = alcance.get("modo", "")
    rubros = alcance.get("rubros_incluidos", [])
    if modo == "obra_completa" or rubros == ["TODOS"]:
        return "OBRA_COMPLETA"
    if len(rubros) == 1:
        return rubros[0]
    if rubros:
        return ", ".join(rubros)
    return "OBRA_COMPLETA"


def main() -> None:
    # ── 1. Cargar datos ───────────────────────────────────────────────────────
    cronograma = _cargar_json(CRONOGRAMA_PATH)
    if cronograma is None:
        print(f"[ERROR] No se encontró {CRONOGRAMA_PATH}")
        raise SystemExit(1)

    presupuesto = _cargar_json(PRESUPUESTO_PATH)
    if presupuesto is None:
        print(f"[WARN]  {PRESUPUESTO_PATH} no existe — se usarán costos del cronograma.")

    # Índice de costos por nombre de elemento (desde presupuesto si existe)
    costo_por_nombre: dict[str, float] = {}
    if isinstance(presupuesto, dict):
        for elem in presupuesto.get("elementos", []):
            nombre = elem.get("nombre", "")
            costo = elem.get("costo_total_ars")
            if nombre and costo is not None:
                costo_por_nombre[nombre] = float(costo)

    # ── 2. Construir lista de elementos ───────────────────────────────────────
    rubro = _rubro_desde_cronograma(cronograma)
    tareas = cronograma.get("tareas", [])
    elementos = []

    for tarea in tareas:
        nombre = _nombre_desde_elemento(tarea.get("elemento", ""))
        duracion = tarea.get("duracion_dias")
        # Costo: priorizar presupuesto.json; fallback a cronograma
        costo = costo_por_nombre.get(nombre, tarea.get("costo_total_ars"))

        metricas_raw = tarea.get("metricas", {})
        metricas = _extraer_metricas(metricas_raw)

        elementos.append({
            "nombre":         nombre,
            "duracion_dias":  duracion,
            "costo_total_ars": costo,
            "metricas":       metricas,
        })

    # ── 3. Calcular totales ───────────────────────────────────────────────────
    def _sum_field(field: str) -> float:
        """Suma un campo de métricas a través de todos los elementos (ignora None)."""
        return sum(
            e["metricas"][field]
            for e in elementos
            if e["metricas"].get(field) is not None
        )

    totales = {
        "costo_total_ars":    sum(
            e["costo_total_ars"] for e in elementos
            if e["costo_total_ars"] is not None
        ),
        "duracion_total_dias": sum(
            e["duracion_dias"] for e in elementos
            if e["duracion_dias"] is not None
        ),
        "hormigon_m3":        _sum_field("volumen_m3"),
        "acero_total_kg":     _sum_field("acero_kg"),
        "encofrado_m2":       _sum_field("encofrado_m2"),
        "longitud_total_ml":  _sum_field("longitud_ml"),
        "area_total_m2":      _sum_field("area_m2"),
    }

    # Redondear totales a 2 decimales
    totales = {k: round(v, 2) for k, v in totales.items()}

    # ── 4. Armar documento de salida ──────────────────────────────────────────
    computo = {
        "generado": datetime.now(tz=timezone.utc).isoformat(),
        "rubro":    rubro,
        "elementos": elementos,
        "totales":   totales,
    }

    # ── 5. Escribir output ────────────────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(computo, f, ensure_ascii=False, indent=2)

    print(f"[OK]    Generado → {OUTPUT_PATH}")
    print(f"        Rubro   : {rubro}")
    print(f"        Elementos: {len(elementos)}")
    print(f"        Totales  : {json.dumps(totales, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
