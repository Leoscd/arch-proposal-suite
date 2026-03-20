#!/usr/bin/env python3
"""
verify_scope.py — Verifica coherencia entre el scope pedido y el cronograma generado.
Cruza cada tarea del cronograma contra las keywords del rubro seleccionado.
Genera outputs/auditoria_scope.json con el resultado.
"""

import json
import unicodedata
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

SESION_PATH = BASE_DIR / "outputs" / "sesion_activa.json"
CRONOGRAMA_PATH = BASE_DIR / "outputs" / "cronograma.json"
RUBROS_PATH = BASE_DIR / "references" / "rubros.json"
AUDITORIA_PATH = BASE_DIR / "outputs" / "auditoria_scope.json"


def normalizar(texto: str) -> str:
    """Convierte a minúsculas y elimina acentos."""
    texto = texto.lower()
    nfkd = unicodedata.normalize("NFD", texto)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def cargar_archivos():
    """Lee los tres archivos necesarios y los devuelve como objetos Python."""
    # sesion_activa.json — si no existe, no es un error; usamos defaults
    if not SESION_PATH.exists():
        print(f"[WARNING] No se encontró sesion_activa.json — se usará modo obra_completa por defecto.")
        sesion = {
            "rubros_seleccionados": [],
            "modo_alcance": "obra_completa",
            "alcance_descripcion": "",
            "fecha_sesion": "",
            "personal": {"oficiales": 0, "ayudantes": 0},
        }
    else:
        with SESION_PATH.open(encoding="utf-8") as f:
            sesion = json.load(f)

    # cronograma.json — si no existe, sí es un error
    if not CRONOGRAMA_PATH.exists():
        print(f"[ERROR] No se encontró cronograma.json en {CRONOGRAMA_PATH}")
        sys.exit(1)

    with CRONOGRAMA_PATH.open(encoding="utf-8") as f:
        cronograma = json.load(f)

    # rubros.json
    with RUBROS_PATH.open(encoding="utf-8") as f:
        rubros_data = json.load(f)

    return sesion, cronograma, rubros_data


def obtener_keywords_rubros_seleccionados(sesion: dict, rubros_data: list) -> dict:
    """
    Devuelve dict {rubro_id: [keywords...]} solo para los rubros
    presentes en sesion["rubros_seleccionados"].
    """
    rubros_sel = sesion.get("rubros_seleccionados", [])
    result = {}
    for rubro in rubros_data:
        rubro_id = rubro.get("id", "")
        if rubro_id in rubros_sel:
            keywords = rubro.get("keywords_cronograma", [])
            result[rubro_id] = keywords
    return result


def cruzar_tareas(tareas: list, keywords_por_rubro: dict) -> list:
    """
    Para cada tarea del cronograma verifica si alguna keyword de algún rubro
    seleccionado aparece en el nombre normalizado de la tarea.
    Devuelve lista de tareas fuera de scope.
    """
    fuera_de_scope = []

    for tarea in tareas:
        # El campo nombre puede ser "elemento", "nombre" o "tarea"
        nombre_tarea = (
            tarea.get("elemento")
            or tarea.get("nombre")
            or tarea.get("tarea")
            or ""
        )
        nombre_norm = normalizar(nombre_tarea)

        match_encontrado = False
        for rubro_id, keywords in keywords_por_rubro.items():
            for kw in keywords:
                if normalizar(kw) in nombre_norm:
                    match_encontrado = True
                    break
            if match_encontrado:
                break

        if not match_encontrado:
            fuera_de_scope.append({
                "elemento": nombre_tarea,
                "accion_sugerida": "Verificar si corresponde al scope",
            })

    return fuera_de_scope


def detectar_elementos_sin_tarea(keywords_por_rubro: dict, tareas: list) -> list:
    """
    Para cada keyword de los rubros seleccionados, verifica si al menos una
    tarea del cronograma la incluye. Reporta solo las primeras 5 keywords de
    cada rubro que no tengan match.
    """
    # Pre-normalizar nombres de tareas
    nombres_norm = []
    for tarea in tareas:
        nombre = (
            tarea.get("elemento")
            or tarea.get("nombre")
            or tarea.get("tarea")
            or ""
        )
        nombres_norm.append(normalizar(nombre))

    elementos_sin_tarea = []

    for rubro_id, keywords in keywords_por_rubro.items():
        sin_match_en_rubro = 0
        vistas = set()  # deduplicar keywords normalizadas
        for kw in keywords:
            kw_norm = normalizar(kw)
            if kw_norm in vistas:
                continue
            vistas.add(kw_norm)
            tiene_match = any(kw_norm in nombre for nombre in nombres_norm)
            if not tiene_match:
                # Solo reportar las primeras 5 por rubro para no saturar
                if sin_match_en_rubro < 5:
                    elementos_sin_tarea.append({
                        "keyword": kw,
                        "rubro": rubro_id,
                        "accion_sugerida": "Considerar agregar tarea",
                    })
                sin_match_en_rubro += 1

    return elementos_sin_tarea


def main():
    sesion, cronograma, rubros_data = cargar_archivos()

    modo_alcance = sesion.get("modo_alcance", "obra_completa")
    rubros_pedidos = sesion.get("rubros_seleccionados", [])

    # Si es obra_completa no tiene sentido auditar por rubro
    if modo_alcance == "obra_completa":
        print("[INFO] modo_alcance = obra_completa — no se genera auditoría de scope por rubros.")
        print("       Todos los rubros están incluidos; la auditoría de scope no aplica.")
        sys.exit(0)

    keywords_por_rubro = obtener_keywords_rubros_seleccionados(sesion, rubros_data)

    warnings = []
    if not rubros_pedidos:
        warnings.append("No hay rubros seleccionados en sesion_activa.json.")

    rubros_sin_keywords = [r for r in rubros_pedidos if r not in keywords_por_rubro]
    for r in rubros_sin_keywords:
        warnings.append(f"El rubro '{r}' no se encontró en rubros.json y fue ignorado.")

    tareas = cronograma.get("tareas", [])

    tareas_fuera_de_scope = cruzar_tareas(tareas, keywords_por_rubro)
    elementos_sin_tarea = detectar_elementos_sin_tarea(keywords_por_rubro, tareas)

    coherente = len(tareas_fuera_de_scope) == 0

    resultado = {
        "coherente": coherente,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "rubros_pedidos": rubros_pedidos,
        "modo_alcance": modo_alcance,
        "tareas_fuera_de_scope": tareas_fuera_de_scope,
        "elementos_sin_tarea": elementos_sin_tarea,
        "warnings": warnings,
    }

    # Guardar JSON de auditoría
    with AUDITORIA_PATH.open("w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    # Imprimir resumen en consola
    print("=" * 60)
    print("  AUDITORIA DE SCOPE — verify_scope.py")
    print("=" * 60)
    print(f"  Modo alcance  : {modo_alcance}")
    print(f"  Rubros pedidos: {', '.join(rubros_pedidos) if rubros_pedidos else '(ninguno)'}")
    print(f"  Coherente     : {'SI' if coherente else 'NO'}")
    print("-" * 60)

    if tareas_fuera_de_scope:
        print(f"  Tareas FUERA de scope ({len(tareas_fuera_de_scope)}):")
        for t in tareas_fuera_de_scope:
            print(f"    - {t['elemento']}")
    else:
        print("  Tareas fuera de scope: ninguna.")

    print()

    if elementos_sin_tarea:
        print(f"  Keywords sin tarea asociada ({len(elementos_sin_tarea)}):")
        for e in elementos_sin_tarea:
            print(f"    - [{e['rubro']}] keyword '{e['keyword']}'")
    else:
        print("  Keywords sin tarea asociada: ninguna.")

    if warnings:
        print()
        print("  Warnings:")
        for w in warnings:
            print(f"    * {w}")

    print("=" * 60)
    print(f"  Resultado guardado en: outputs/auditoria_scope.json")
    print("=" * 60)

    # Código de salida
    if tareas_fuera_de_scope:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
