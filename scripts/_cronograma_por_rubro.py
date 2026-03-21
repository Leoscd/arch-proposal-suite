"""
_cronograma_por_rubro.py
Genera las tareas de cronograma filtrando por rubros seleccionados en sesion_activa.json.
Usado internamente por generate_schedule.py

Solo stdlib Python. Sin dependencias externas.
"""

import json
import unicodedata
from pathlib import Path

# ── Rutas base ────────────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).parent.parent
_SESION_PATH = _BASE_DIR / "outputs" / "sesion_activa.json"
_RUBROS_PATH = _BASE_DIR / "references" / "rubros.json"


# ── Función normalizar (idéntica a verify_scope.py) ───────────────────────────

def normalizar(texto: str) -> str:
    """Convierte a minúsculas y elimina acentos."""
    texto = texto.lower()
    nfkd = unicodedata.normalize("NFD", texto)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


# ── Helpers internos ──────────────────────────────────────────────────────────

def _cargar_rubros(ruta_rubros: Path = _RUBROS_PATH) -> list:
    """Lee rubros.json y devuelve la lista de rubros."""
    if not ruta_rubros.exists():
        print(f"[ERROR] _cronograma_por_rubro: No se encontró {ruta_rubros}")
        return []
    with ruta_rubros.open(encoding="utf-8") as f:
        return json.load(f)


def _cargar_sesion(ruta_sesion: Path = _SESION_PATH) -> dict:
    """
    Lee sesion_activa.json. Si no existe o está vacío, aplica fallback
    a modo obra_completa y emite un warning.
    """
    fallback = {
        "rubros_seleccionados": [],
        "modo_alcance": "obra_completa",
    }

    if not ruta_sesion.exists():
        print("[WARNING] _cronograma_por_rubro: sesion_activa.json no encontrado "
              "— usando modo obra_completa por defecto.")
        return fallback

    with ruta_sesion.open(encoding="utf-8") as f:
        sesion = json.load(f)

    if not sesion.get("rubros_seleccionados") and sesion.get("modo_alcance") != "obra_completa":
        print("[WARNING] _cronograma_por_rubro: sesion_activa.json sin rubros_seleccionados "
              "— usando modo obra_completa por defecto.")
        sesion["modo_alcance"] = "obra_completa"

    return sesion


def _keywords_por_rubro(rubros_ids: list, rubros_data: list) -> dict:
    """
    Construye {rubro_id: [keywords_normalizadas]} para los IDs pedidos.
    Si un ID no se encuentra en rubros_data, se emite warning y se omite.
    """
    ids_disponibles = {r["id"]: r for r in rubros_data}
    resultado = {}

    for rubro_id in rubros_ids:
        if rubro_id not in ids_disponibles:
            print(f"[WARNING] _cronograma_por_rubro: rubro_id '{rubro_id}' "
                  "no encontrado en rubros.json — se omite.")
            continue
        rubro = ids_disponibles[rubro_id]
        keywords = rubro.get("keywords_cronograma", [])
        resultado[rubro_id] = [normalizar(kw) for kw in keywords]

    return resultado


def _nombre_tarea(tarea: dict) -> str:
    """Extrae el nombre de una tarea sea cual sea su clave."""
    return (
        tarea.get("elemento")
        or tarea.get("nombre")
        or tarea.get("tarea")
        or ""
    )


# ── Función pública principal ─────────────────────────────────────────────────

def filtrar_tareas_por_rubro(tareas: list, rubros_ids: list,
                             ruta_rubros: str = None,
                             ruta_sesion: str = None) -> list:
    """
    Filtra la lista de tareas del cronograma dejando solo las que corresponden
    a alguno de los rubros pedidos.

    Parámetros
    ----------
    tareas      : lista completa de tareas (dicts con clave "elemento", "nombre"
                  o "tarea")
    rubros_ids  : lista de IDs de rubro, p.ej. ["03_ESTRUCTURAS", "04_CERRAMIENTOS"].
                  Si está vacía se devuelven todas las tareas (modo obra_completa).
    ruta_rubros : ruta alternativa a rubros.json (opcional, usa default si None)
    ruta_sesion : ruta alternativa a sesion_activa.json (no usada aquí directamente,
                  pero disponible para futuros callers que quieran pasar la sesión
                  como path)

    Retorna
    -------
    Lista de tareas filtradas. Cada tarea mantiene su estructura original
    con el campo adicional "_rubro_match" indicando el rubro que la capturó.

    Comportamiento
    --------------
    - Si rubros_ids está vacío → se retornan todas las tareas sin modificar
      (modo obra_completa).
    - Si una tarea tiene keyword de más de un rubro, se asocia al primero
      que hizo match (orden de rubros_ids).
    - Si ninguna keyword matchea la tarea, se excluye del resultado.
    """
    # Modo obra_completa: sin filtro
    if not rubros_ids:
        print("[INFO] _cronograma_por_rubro: rubros_ids vacío — "
              "se devuelven todas las tareas (modo obra_completa).")
        return list(tareas)

    # Cargar rubros.json
    _ruta_rubros = Path(ruta_rubros) if ruta_rubros else _RUBROS_PATH
    rubros_data = _cargar_rubros(_ruta_rubros)

    if not rubros_data:
        print("[ERROR] _cronograma_por_rubro: rubros_data vacío — "
              "se devuelven todas las tareas como fallback.")
        return list(tareas)

    # Construir índice de keywords por rubro
    kw_por_rubro = _keywords_por_rubro(rubros_ids, rubros_data)

    if not kw_por_rubro:
        print("[WARNING] _cronograma_por_rubro: ningún rubro_id válido en rubros_ids "
              "— se devuelve lista vacía.")
        return []

    # Filtrar tareas
    tareas_filtradas = []

    for tarea in tareas:
        nombre_norm = normalizar(_nombre_tarea(tarea))
        rubro_match = None

        for rubro_id, keywords in kw_por_rubro.items():
            for kw in keywords:
                if kw in nombre_norm:
                    rubro_match = rubro_id
                    break
            if rubro_match:
                break

        if rubro_match:
            tarea_out = dict(tarea)
            tarea_out["_rubro_match"] = rubro_match
            tareas_filtradas.append(tarea_out)

    print(f"[INFO] _cronograma_por_rubro: {len(tareas_filtradas)} tareas "
          f"seleccionadas de {len(tareas)} totales "
          f"(rubros: {', '.join(kw_por_rubro.keys())})")

    return tareas_filtradas


# ── Función de conveniencia: leer rubros desde sesion_activa y filtrar ────────

def filtrar_tareas_desde_sesion(tareas: list,
                                ruta_sesion: str = None,
                                ruta_rubros: str = None) -> list:
    """
    Variante de filtrar_tareas_por_rubro que lee los rubros_ids directamente
    desde sesion_activa.json en lugar de recibirlos como parámetro.

    Útil para llamarlo desde generate_schedule.py sin tener que leer la sesión
    en el caller.

    Parámetros
    ----------
    tareas      : lista completa de tareas del cronograma
    ruta_sesion : ruta alternativa a sesion_activa.json (usa default si None)
    ruta_rubros : ruta alternativa a rubros.json (usa default si None)

    Retorna
    -------
    Lista de tareas filtradas (o todas si modo_alcance == "obra_completa").
    """
    _ruta_sesion = Path(ruta_sesion) if ruta_sesion else _SESION_PATH
    sesion = _cargar_sesion(_ruta_sesion)

    modo_alcance = sesion.get("modo_alcance", "obra_completa")
    rubros_ids = sesion.get("rubros_seleccionados", [])

    if modo_alcance == "obra_completa" or not rubros_ids:
        print("[INFO] _cronograma_por_rubro: modo_alcance=obra_completa — "
              "se devuelven todas las tareas sin filtrar.")
        return list(tareas)

    return filtrar_tareas_por_rubro(tareas, rubros_ids, ruta_rubros=ruta_rubros)


# ── Bloque de prueba standalone ───────────────────────────────────────────────

if __name__ == "__main__":
    # Tareas de ejemplo para probar el filtro
    TAREAS_EJEMPLO = [
        {"nombre": "Excavación manual para cimientos"},
        {"nombre": "Columnas de Hormigón Armado"},
        {"nombre": "Muro de ladrillo hueco 18cm"},
        {"nombre": "Cubierta de chapa trapezoidal"},
        {"nombre": "Pintura látex interior 2 manos"},
        {"nombre": "Instalación eléctrica: bocas de luz"},
        {"nombre": "Limpieza final de obra"},
        {"nombre": "Revoque grueso interior"},
        {"nombre": "Carpeta niveladora"},
        {"nombre": "Pisos cerámicos 45x45"},
    ]

    print("=== Prueba filtrar_tareas_por_rubro ===")
    resultado = filtrar_tareas_por_rubro(
        TAREAS_EJEMPLO,
        ["03_ESTRUCTURAS", "04_CERRAMIENTOS", "07_REVOQUES"]
    )
    for t in resultado:
        print(f"  [{t['_rubro_match']}] {t.get('nombre', t.get('elemento', ''))}")

    print()
    print("=== Prueba con rubros_ids vacío (obra_completa) ===")
    resultado_completo = filtrar_tareas_por_rubro(TAREAS_EJEMPLO, [])
    print(f"  Tareas devueltas: {len(resultado_completo)} (esperado: {len(TAREAS_EJEMPLO)})")
