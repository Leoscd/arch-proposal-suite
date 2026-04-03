"""
audit_budget.py
─────────────────────────────────────────────────────────────────────────────
Auditor de Desvíos Presupuestarios — Arch Proposal Suite

Compara los gastos reales (tickets/facturas cargados) contra el presupuesto
teórico validado. Genera un reporte JSON de auditoría y una tabla Markdown
con semáforos de alerta.

También incluye lógica de match semanal entre gastos reales y rubros activos
del cronograma, generando reportes de alineamiento por semana.

Uso:
    # Auditoría del período completo
    python audit_budget.py

    # Auditoría de una semana específica
    python audit_budget.py --semana 1

    # Auditoría de un rango de fechas
    python audit_budget.py --desde 2025-04-01 --hasta 2025-04-07

    # Sólo stdout sin guardar archivo
    python audit_budget.py --dry-run

    # Match de gastos vs rubros activos de la semana (genera reporte_match_semana_N.json)
    python audit_budget.py --semana 1
"""

import os
import sys
import json
import argparse
import math
from datetime import datetime, date, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR   = os.path.normpath(os.path.join(BASE_DIR, "..", "outputs"))
ESTADO_PATH   = os.path.normpath(os.path.join(OUTPUTS_DIR, "estado-proyecto.json"))
CRONO_PATH    = os.path.normpath(os.path.join(OUTPUTS_DIR, "cronograma.json"))
CURVA_PATH    = os.path.normpath(os.path.join(OUTPUTS_DIR, "curva_inversion.json"))
RUBROS_PATH   = os.path.normpath(os.path.join(BASE_DIR, "..", "references", "rubros.json"))
AUDIT_DIR     = os.path.join(OUTPUTS_DIR, "auditorias")


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def fmt_ars(valor: float) -> str:
    """Formato moneda ARS con separadores argentinos."""
    return "$ {:,.0f}".format(valor).replace(",", "X").replace(".", ",").replace("X", ".")


def semaforo(desvio_pct: float) -> str:
    """
    Devuelve el semáforo según el desvío porcentual respecto al presupuestado.
    Positivo = gasto real MAYOR que el teórico (mal).
    Negativo = gasto real MENOR que el teórico (bien o retraso).
    """
    if desvio_pct > 15:
        return "🔴 ROJO"
    elif desvio_pct > 5:
        return "🟡 AMARILLO"
    else:
        return "🟢 VERDE"


def _cargar_json(ruta: str) -> dict:
    if not os.path.exists(ruta):
        return {}
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def _semana_de_fecha(fecha_str: str, fecha_inicio_str: str) -> int:
    """Calcula en qué semana de obra cae una fecha dada."""
    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        inicio = datetime.strptime(fecha_inicio_str, "%Y-%m-%d").date()
        return max(1, math.ceil((fecha - inicio).days / 7))
    except Exception:
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# CARGA DE DATOS
# ─────────────────────────────────────────────────────────────────────────────

def cargar_estado() -> tuple[dict, dict, list]:
    """
    Retorna (metadatos, presupuesto_validado, gastos_reales).
    Si presupuesto_validado está vacío, retorna un dict vacío y el auditor
    trabajará sólo con totales globales.
    """
    estado = _cargar_json(ESTADO_PATH)
    metadatos = estado.get("metadatos", {})
    presupuesto = estado.get("presupuesto_validado", {})
    gastos = estado.get("gastos_reales", [])
    return metadatos, presupuesto, gastos


def cargar_cronograma() -> dict:
    return _cargar_json(CRONO_PATH)


# ─────────────────────────────────────────────────────────────────────────────
# FILTRADO DE GASTOS
# ─────────────────────────────────────────────────────────────────────────────

def filtrar_gastos(gastos: list, semana: int = None,
                   desde: str = None, hasta: str = None) -> list:
    """Filtra el array de gastos por semana o rango de fechas."""
    if not gastos:
        return []

    crono = cargar_cronograma()
    fecha_inicio = crono.get("configuracion", {}).get("fecha_inicio", "")

    resultado = []
    for g in gastos:
        fecha_gasto = g.get("fecha", "")

        if semana is not None and fecha_inicio:
            semana_gasto = _semana_de_fecha(fecha_gasto, fecha_inicio)
            if semana_gasto != semana:
                continue

        if desde:
            if fecha_gasto < desde:
                continue

        if hasta:
            if fecha_gasto > hasta:
                continue

        resultado.append(g)

    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# CÁLCULO DE DESVÍOS
# ─────────────────────────────────────────────────────────────────────────────

def calcular_totales(gastos: list) -> dict:
    """Agrupa y suma los gastos reales por proveedor y total global."""
    total_global = 0.0
    por_proveedor = {}

    for g in gastos:
        total = g.get("total_ars", 0.0)
        proveedor = g.get("proveedor", "Sin proveedor")
        total_global += total
        por_proveedor[proveedor] = por_proveedor.get(proveedor, 0.0) + total

    return {
        "total_real_ars": total_global,
        "por_proveedor": por_proveedor,
        "cantidad_tickets": len(gastos),
    }


def calcular_desvios(totales_reales: dict, presupuesto: dict,
                     semana: int = None, crono: dict = None) -> dict:
    """
    Calcula el desvío entre gasto real y presupuesto teórico.
    Si no hay presupuesto_validado, calcula el desvío contra el monto
    teórico semanal prorateado desde el cronograma.
    """
    real = totales_reales["total_real_ars"]

    # ── Calcular presupuesto teórico del período ──────────────────────────────
    teorico = 0.0
    fuente_teorico = "N/A"

    if presupuesto and presupuesto.get("COSTO_DIRECTO_TOTAL"):
        # Hay presupuesto validado — prorratear por semana si aplica
        total_obra = presupuesto["COSTO_DIRECTO_TOTAL"]
        duracion_dias = crono.get("duracion_total_dias", 42) if crono else 42
        semanas_totales = max(1, math.ceil(duracion_dias / 7))

        if semana:
            teorico = total_obra / semanas_totales
            fuente_teorico = f"Prorrateo lineal semana {semana}/{semanas_totales}"
        else:
            teorico = total_obra
            fuente_teorico = "Costo directo total"

    elif crono and semana:
        # Sin presupuesto validado pero con cronograma: no podemos calcular
        fuente_teorico = "Sin presupuesto validado — comparación no disponible"

    # ── Desvío ────────────────────────────────────────────────────────────────
    if teorico > 0:
        desvio_ars = real - teorico
        desvio_pct = (desvio_ars / teorico) * 100
    else:
        desvio_ars = 0.0
        desvio_pct = 0.0

    return {
        "real_ars": real,
        "teorico_ars": teorico,
        "desvio_ars": desvio_ars,
        "desvio_pct": desvio_pct,
        "semaforo": semaforo(desvio_pct),
        "fuente_teorico": fuente_teorico,
    }


# ─────────────────────────────────────────────────────────────────────────────
# GENERACIÓN DE REPORTES
# ─────────────────────────────────────────────────────────────────────────────

def generar_tabla_markdown(gastos: list, totales: dict, desvios: dict,
                           semana: int = None) -> str:
    """Genera la tabla Markdown del reporte de auditoría."""

    periodo = f"Semana {semana}" if semana else "Período completo"
    hoy = date.today().strftime("%d/%m/%Y")

    lineas = [
        f"## Auditoría de Gastos — {periodo} | {hoy}",
        "",
        "### Resumen Ejecutivo",
        "",
        f"| Métrica | Valor |",
        f"| :--- | :--- |",
        f"| **Gasto Real** | {fmt_ars(desvios['real_ars'])} |",
        f"| **Presupuesto Teórico** | {fmt_ars(desvios['teorico_ars']) if desvios['teorico_ars'] else 'Sin presupuesto validado'} |",
        f"| **Desvío** | {fmt_ars(desvios['desvio_ars'])} ({desvios['desvio_pct']:.1f}%) |",
        f"| **Estado** | {desvios['semaforo']} |",
        f"| **Tickets procesados** | {totales['cantidad_tickets']} |",
        "",
        "### Detalle por Ticket",
        "",
        "| # | Fecha | Proveedor | Total ARS |",
        "| :---: | :--- | :--- | :--- |",
    ]

    for i, g in enumerate(gastos, 1):
        lineas.append(
            f"| {i} | {g.get('fecha', '—')} | {g.get('proveedor', '—')} "
            f"| {fmt_ars(g.get('total_ars', 0))} |"
        )

    if totales["por_proveedor"]:
        lineas += [
            "",
            "### Acumulado por Proveedor",
            "",
            "| Proveedor | Total ARS |",
            "| :--- | :--- |",
        ]
        for prov, monto in sorted(totales["por_proveedor"].items(),
                                  key=lambda x: x[1], reverse=True):
            lineas.append(f"| {prov} | {fmt_ars(monto)} |")

    lineas += [
        "",
        "---",
        f"*Reporte generado por audit_budget.py — Arch Proposal Suite*",
    ]

    return "\n".join(lineas)


def guardar_auditoria(payload: dict, semana: int = None) -> str:
    """Guarda el JSON de auditoría y devuelve la ruta del archivo."""
    os.makedirs(AUDIT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sufijo = f"semana_{semana}_" if semana else ""
    nombre = f"auditoria_{sufijo}{timestamp}.json"
    ruta = os.path.join(AUDIT_DIR, nombre)

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return ruta


# ─────────────────────────────────────────────────────────────────────────────
# ORQUESTADOR
# ─────────────────────────────────────────────────────────────────────────────

def auditar(semana: int = None, desde: str = None,
            hasta: str = None, dry_run: bool = False) -> dict:
    """
    Función principal. Orquesta carga → filtrado → cálculo → reporte.
    Retorna el payload completo de auditoría.
    """
    # Cargar datos
    metadatos, presupuesto, gastos_todos = cargar_estado()
    crono = cargar_cronograma()

    proyecto = metadatos.get("proyecto_nombre", "Sin definir")

    # Filtrar gastos según el período pedido
    gastos = filtrar_gastos(gastos_todos, semana=semana, desde=desde, hasta=hasta)

    if not gastos:
        print(f"[AuditBudget] ⚠ No se encontraron gastos para el período solicitado.")
        print(f"  Total de gastos registrados en el sistema: {len(gastos_todos)}")
        return {}

    # Calcular
    totales  = calcular_totales(gastos)
    desvios  = calcular_desvios(totales, presupuesto, semana=semana, crono=crono)

    # Tabla Markdown (siempre a stdout)
    tabla_md = generar_tabla_markdown(gastos, totales, desvios, semana)
    print(tabla_md)

    # Payload JSON para guardar
    payload = {
        "proyecto": proyecto,
        "periodo": {"semana": semana, "desde": desde, "hasta": hasta},
        "generado_en": datetime.now().isoformat(),
        "resumen": desvios,
        "totales": totales,
        "gastos_detalle": gastos,
    }

    # Guardar archivo (salvo dry_run)
    if not dry_run:
        ruta_guardado = guardar_auditoria(payload, semana)
        print(f"\n[AuditBudget] ✅ Auditoría guardada → {ruta_guardado}")
    else:
        print("\n[AuditBudget] ℹ Modo dry-run: no se guardó ningún archivo.")

    return payload


# ─────────────────────────────────────────────────────────────────────────────
# MATCH GASTOS ↔ RUBROS ACTIVOS (TAREA 7)
# ─────────────────────────────────────────────────────────────────────────────

def _cargar_rubros() -> list:
    """Carga references/rubros.json con la definición de rubros y sus keywords."""
    if not os.path.exists(RUBROS_PATH):
        print(f"[MatchSemana] ADVERTENCIA: No se encontró rubros.json en {RUBROS_PATH}")
        return []
    with open(RUBROS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _cargar_curva() -> dict:
    """Carga outputs/curva_inversion.json."""
    return _cargar_json(CURVA_PATH)


def _rubros_activos_semana(semana_num: int, curva: dict) -> list:
    """
    Devuelve la lista de nombres de rubros activos para la semana indicada,
    según curva_inversion.json (campo 'rubros_activos' de cada semana).
    """
    for sem in curva.get("semanas", []):
        if sem.get("numero") == semana_num:
            return sem.get("rubros_activos", [])
    return []


def _proyectado_semana(semana_num: int, curva: dict) -> dict:
    """
    Devuelve los totales proyectados de la semana (materiales, mo, total).
    """
    for sem in curva.get("semanas", []):
        if sem.get("numero") == semana_num:
            return {
                "materiales": sem.get("proyectado_materiales", 0.0),
                "mo":         sem.get("proyectado_mo", 0.0),
                "total":      sem.get("proyectado_total", 0.0),
            }
    return {"materiales": 0.0, "mo": 0.0, "total": 0.0}


def _rubro_id_a_nombre(rubro_id: str) -> str:
    """
    Convierte el ID de un rubro (ej. '03_ESTRUCTURAS') en su nombre clave
    normalizado para comparar con los nombres de rubros_activos en curva.
    Ej: '03_ESTRUCTURAS' → 'ESTRUCTURAS'
         '02_CIMIENTOS_Y_FUNDACIONES' → 'CIMIENTOS'  (usa primer token post-prefijo)
    """
    # Quitar prefijo numérico y tomar tokens del ID
    partes = rubro_id.split("_")
    # El primer token es el número (ej. '03'), el resto forman el nombre
    nombre_tokens = partes[1:] if partes and partes[0].isdigit() else partes
    # Normalizar: si contiene 'CIMIENTOS' → 'CIMIENTOS', 'ESTRUCTURAS' → 'ESTRUCTURAS', etc.
    nombre_upper = "_".join(nombre_tokens).upper()
    # Mapeo manual de IDs compuestos a nombres usados en curva_inversion
    mapeo = {
        "TRABAJOS_PREPARATORIOS": "TRABAJOS PREPARATORIOS",
        "CIMIENTOS_Y_FUNDACIONES": "CIMIENTOS",
        "ESTRUCTURAS": "ESTRUCTURAS",
        "CERRAMIENTOS": "MAMPOSTERÍAS",   # cerramientos = mamposterías en curva
        "AISLACIONES": "AISLACIONES",
        "CUBIERTAS": "CUBIERTAS",
        "REVOQUES": "REVOQUES",
        "CONTRAPISOS_CARPETAS": "CONTRAPISOS",
        "PISOS": "PISOS",
        "CIELORRASOS": "CIELORRASOS",
        "INSTALACIONES": "INSTALACIONES",
        "CARPINTERIAS": "CARPINTERÍAS",
        "PINTURAS": "PINTURAS",
        "LIMPIEZA": "LIMPIEZA",
    }
    resultado = mapeo.get(nombre_upper, nombre_upper.replace("_", " "))
    return resultado


def _asignar_rubro_a_gasto(gasto: dict, rubros_def: list, rubros_activos_nombres: list) -> str | None:
    """
    Intenta asignar un gasto a un rubro activo analizando las descripciones
    de sus items contra los keywords de cada rubro en rubros.json.

    Usa dos fuentes de keywords:
      1. keywords_cronograma del rubro
      2. Nombres de items del rubro (para capturar materiales como cemento, hierro)
    También incluye keywords genéricos de materiales de construcción por rubro.

    Retorna el nombre del rubro activo asignado (como aparece en rubros_activos),
    o None si no se puede asignar a ningún rubro activo.
    """
    # Keywords adicionales de materiales por rubro (complementan rubros.json)
    KEYWORDS_MATERIALES = {
        "ESTRUCTURAS":          ["cemento", "hierro", "acero", "armadura", "encofrado",
                                 "hormigon", "hormigón", "losa", "viga", "columna",
                                 "barra", "malla", "alambre", "puntal"],
        "CIMIENTOS":            ["cemento", "hormigon", "hormigón", "excavacion",
                                 "excavación", "piedra", "arena", "cascote"],
        "MAMPOSTERÍAS":         ["ladrillo", "bloque", "mortero", "cal", "cemento",
                                 "junta", "tabique"],
        "REVOQUES":             ["revoque", "cal", "cemento", "arena", "yeso",
                                 "plastificante", "jaharro"],
        "TRABAJOS PREPARATORIOS": ["limpieza", "replanteo", "nivelacion", "cerco",
                                   "obrador", "material"],
        "MOVIMIENTO DE TIERRA": ["excavacion", "excavación", "relleno", "suelo",
                                 "tierra", "retiro"],
        "INSTALACIONES":        ["caño", "cañeria", "cañería", "plomeria", "plomería",
                                 "electrica", "eléctrica", "cable", "termotanque",
                                 "sanitaria"],
        "PINTURAS":             ["pintura", "latex", "látex", "esmalte", "barniz",
                                 "sellador", "rodillo"],
        "PISOS":                ["ceramica", "cerámica", "porcelanato", "piso",
                                 "revestimiento", "pegamento"],
        "CIELORRASOS":          ["yeso", "durlock", "placa", "cielorraso", "cieloraso"],
        "AISLACIONES":          ["hidrofugo", "hidrófugo", "aislante", "barrera",
                                 "impermeabilizante", "membrana"],
    }

    # Texto de búsqueda: descripción de cada item + nombre del proveedor
    textos = [gasto.get("proveedor", "").lower()]
    for item in gasto.get("items", []):
        textos.append(item.get("descripcion", "").lower())
    texto_completo = " ".join(textos)

    # Para cada rubro, contar cuántos keywords coinciden
    mejor_rubro = None
    mejor_puntaje = 0

    for rubro_def in rubros_def:
        rubro_id = rubro_def.get("id", "")
        nombre_curva = _rubro_id_a_nombre(rubro_id)

        # Solo considerar rubros activos en la semana
        if nombre_curva not in rubros_activos_nombres:
            continue

        # Fuente 1: keywords_cronograma del rubro
        keywords_crono = rubro_def.get("keywords_cronograma", [])
        puntaje = sum(1 for kw in keywords_crono if kw.lower() in texto_completo)

        # Fuente 2: keywords de materiales adicionales
        kw_mat = KEYWORDS_MATERIALES.get(nombre_curva, [])
        puntaje += sum(1 for kw in kw_mat if kw.lower() in texto_completo)

        # Fuente 3: nombres de items del rubro (peso menor: 0.5 por coincidencia)
        items_rubro = rubro_def.get("items", [])
        for item_rubro in items_rubro:
            nombre_item = item_rubro.get("nombre", "").lower()
            # Buscar palabras clave del nombre del item en el texto del gasto
            palabras = [w for w in nombre_item.split() if len(w) > 3]
            puntaje += sum(0.5 for w in palabras if w in texto_completo)

        if puntaje > mejor_puntaje:
            mejor_puntaje = puntaje
            mejor_rubro = nombre_curva

    return mejor_rubro if mejor_puntaje > 0 else None


def _proyectado_por_rubro(semana_num: int, rubros_activos: list,
                           cronograma: dict, curva: dict) -> dict:
    """
    Calcula el monto proyectado por cada rubro activo en la semana.

    Estrategia: proratea el proyectado_total de la semana entre los rubros
    activos de esa semana, en proporción al costo_total_ars de cada tarea
    en el cronograma.

    Rubros de la curva que no tienen tarea directa en el cronograma se
    resuelven con el mapeo de aliases (ej. MOVIMIENTO DE TIERRA → CIMIENTOS).

    Retorna: {nombre_rubro: monto_proyectado_ars}
    """
    proyectado_semana = _proyectado_semana(semana_num, curva)
    total_sem = proyectado_semana["total"]

    # Aliases: nombres usados en curva_inversion que no tienen tarea propia
    # en cronograma pero comparten costo con otro rubro
    ALIAS_RUBRO = {
        "MOVIMIENTO DE TIERRA": "CIMIENTOS",
    }

    # Obtener costo total de cada tarea del cronograma y su nombre en curva
    costo_por_nombre = {}
    for tarea in cronograma.get("tareas", []):
        elemento = tarea.get("elemento", "")
        # Extraer ID: primer token antes de " — "
        id_parte = elemento.split(" — ")[0].strip()
        nombre_curva = _rubro_id_a_nombre(id_parte)
        costo = tarea.get("costo_total_ars", 0.0)
        costo_por_nombre[nombre_curva] = costo_por_nombre.get(nombre_curva, 0.0) + costo

    # Resolver aliases para rubros activos sin costo directo
    costos_activos = {}
    for r in rubros_activos:
        costo_directo = costo_por_nombre.get(r, 0.0)
        if costo_directo == 0.0 and r in ALIAS_RUBRO:
            costo_directo = costo_por_nombre.get(ALIAS_RUBRO[r], 0.0)
        costos_activos[r] = costo_directo

    total_costo_activos = sum(costos_activos.values())

    if total_costo_activos <= 0:
        # Sin información de costos: distribuir igualmente
        n = len(rubros_activos) if rubros_activos else 1
        return {r: total_sem / n for r in rubros_activos}

    return {
        r: (costos_activos[r] / total_costo_activos) * total_sem
        for r in rubros_activos
    }


def _estado_desvio(desvio_pct: float) -> str:
    """
    Semáforo de estado para el match semanal por rubro.
      ok       : desvío ≤ 10 %  (positivo = sobreejecutado, negativo = subejecución)
      alerta   : 10 % < |desvío| ≤ 25 %
      critico  : |desvío| > 25 %
    """
    abs_d = abs(desvio_pct)
    if abs_d <= 10:
        return "ok"
    elif abs_d <= 25:
        return "alerta"
    else:
        return "critico"


def _semaforo_general(resultados_rubros: list) -> str:
    """
    Determina el semáforo general de la semana en base a los estados por rubro.
    Si al menos uno es 'critico' → 'critico'
    Si al menos uno es 'alerta'  → 'alerta'
    Todos 'ok'                   → 'ok'
    """
    estados = [r["estado"] for r in resultados_rubros]
    if "critico" in estados:
        return "critico"
    if "alerta" in estados:
        return "alerta"
    return "ok"


def match_gastos_a_rubros(semana_num: int, gastos: list,
                           cronograma: dict, curva: dict) -> dict:
    """
    Función principal de match para la Tarea 7.

    Parámetros
    ----------
    semana_num  : número de semana de obra (1-based)
    gastos      : lista de gastos_reales filtrados para esa semana
    cronograma  : dict cargado de outputs/cronograma.json
    curva       : dict cargado de outputs/curva_inversion.json

    Retorna
    -------
    dict con:
      - semana           : int
      - rubros_activos   : list[str]
      - por_rubro        : list[dict]  — proyectado/real/desvío/estado por rubro
      - gastos_sin_rubro : list[dict]  — gastos que no pudieron asignarse
      - semaforo_general : str  (ok / alerta / critico)
      - totales_semana   : dict
    """
    rubros_def = _cargar_rubros()
    rubros_activos = _rubros_activos_semana(semana_num, curva)

    if not rubros_activos:
        print(f"[MatchSemana] ADVERTENCIA: No se encontraron rubros activos para la semana {semana_num}.")

    # Proyectado por rubro
    proy_por_rubro = _proyectado_por_rubro(semana_num, rubros_activos, cronograma, curva)

    # Asignar cada gasto a un rubro activo
    real_por_rubro = {r: 0.0 for r in rubros_activos}
    gastos_sin_rubro = []
    gastos_asignados = []

    for gasto in gastos:
        rubro_asignado = _asignar_rubro_a_gasto(gasto, rubros_def, rubros_activos)
        if rubro_asignado:
            real_por_rubro[rubro_asignado] = real_por_rubro.get(rubro_asignado, 0.0) + gasto.get("total_ars", 0.0)
            gastos_asignados.append({
                "id":       gasto.get("id"),
                "proveedor": gasto.get("proveedor"),
                "fecha":    gasto.get("fecha"),
                "total_ars": gasto.get("total_ars", 0.0),
                "tipo":     gasto.get("tipo"),
                "rubro_asignado": rubro_asignado,
            })
        else:
            gastos_sin_rubro.append({
                "id":       gasto.get("id"),
                "proveedor": gasto.get("proveedor"),
                "fecha":    gasto.get("fecha"),
                "total_ars": gasto.get("total_ars", 0.0),
                "tipo":     gasto.get("tipo"),
                "motivo_no_asignado": "Sin keywords coincidentes con rubros activos",
            })

    # Construir resultados por rubro
    por_rubro = []
    for rubro in rubros_activos:
        proyectado = proy_por_rubro.get(rubro, 0.0)
        real       = real_por_rubro.get(rubro, 0.0)
        desvio_ars = real - proyectado
        desvio_pct = (desvio_ars / proyectado * 100) if proyectado > 0 else 0.0
        estado     = _estado_desvio(desvio_pct)

        por_rubro.append({
            "rubro":          rubro,
            "proyectado_ars": round(proyectado, 2),
            "real_ars":       round(real, 2),
            "desvio_ars":     round(desvio_ars, 2),
            "desvio_pct":     round(desvio_pct, 2),
            "estado":         estado,
        })

    semaforo_gen = _semaforo_general(por_rubro)

    # Totales de la semana
    total_proyectado = sum(r["proyectado_ars"] for r in por_rubro)
    total_real       = sum(r["real_ars"] for r in por_rubro)
    total_sin_rubro  = sum(g["total_ars"] for g in gastos_sin_rubro)

    return {
        "semana":           semana_num,
        "rubros_activos":   rubros_activos,
        "por_rubro":        por_rubro,
        "gastos_asignados": gastos_asignados,
        "gastos_sin_rubro": gastos_sin_rubro,
        "semaforo_general": semaforo_gen,
        "totales_semana": {
            "proyectado_total_ars": round(total_proyectado, 2),
            "real_asignado_ars":    round(total_real, 2),
            "real_sin_rubro_ars":   round(total_sin_rubro, 2),
            "real_total_ars":       round(total_real + total_sin_rubro, 2),
            "desvio_ars":           round((total_real + total_sin_rubro) - total_proyectado, 2),
            "desvio_pct":           round(
                ((total_real + total_sin_rubro) - total_proyectado) / total_proyectado * 100
                if total_proyectado > 0 else 0.0,
                2
            ),
        },
    }


def generar_reporte_match(semana_num: int) -> dict:
    """
    Orquesta la generación del reporte de match para la semana indicada:
      1. Carga cronograma, curva e estado-proyecto
      2. Filtra gastos de esa semana
      3. Ejecuta match_gastos_a_rubros
      4. Guarda outputs/reporte_match_semana_{N}.json
      5. Imprime resumen en consola

    Retorna el payload del reporte.
    """
    print(f"\n[MatchSemana] === Reporte de Match — Semana {semana_num} ===")

    # Cargar datos
    cronograma = _cargar_json(CRONO_PATH)
    curva      = _cargar_curva()
    estado     = _cargar_json(os.path.normpath(os.path.join(BASE_DIR, "..", "outputs", "estado-proyecto.json")))

    # Fallback: estado-proyecto puede vivir un nivel arriba de outputs/
    if not estado:
        estado = _cargar_json(ESTADO_PATH)

    gastos_todos = estado.get("gastos_reales", [])

    if not cronograma:
        print(f"[MatchSemana] ERROR: No se pudo leer cronograma.json en {CRONO_PATH}")
        return {}
    if not curva:
        print(f"[MatchSemana] ERROR: No se pudo leer curva_inversion.json en {CURVA_PATH}")
        return {}

    # Filtrar gastos para la semana solicitada
    # Prioridad: campo 'semana' explícito en el gasto; fallback: calcular por fecha
    fecha_inicio = cronograma.get("configuracion", {}).get("fecha_inicio", "")
    gastos_semana = []
    for g in gastos_todos:
        semana_gasto = g.get("semana")
        if semana_gasto is None and fecha_inicio and g.get("fecha"):
            semana_gasto = _semana_de_fecha(g["fecha"], fecha_inicio)
        if semana_gasto == semana_num:
            gastos_semana.append(g)

    print(f"  Gastos encontrados para la semana {semana_num}: {len(gastos_semana)}")

    # Ejecutar match
    resultado = match_gastos_a_rubros(semana_num, gastos_semana, cronograma, curva)

    # Construir payload completo
    payload = {
        "generado_en":    datetime.now().isoformat(),
        "semana":         semana_num,
        "semaforo_general": resultado["semaforo_general"],
        "rubros_activos": resultado["rubros_activos"],
        "por_rubro":      resultado["por_rubro"],
        "gastos_asignados": resultado["gastos_asignados"],
        "gastos_sin_rubro": resultado["gastos_sin_rubro"],
        "totales_semana": resultado["totales_semana"],
    }

    # Guardar JSON
    nombre_archivo = f"reporte_match_semana_{semana_num}.json"
    ruta_salida    = os.path.join(OUTPUTS_DIR, nombre_archivo)
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Imprimir resumen en consola
    print(f"\n  Rubros activos ({len(resultado['rubros_activos'])}):")
    for r in resultado["por_rubro"]:
        signo = "+" if r["desvio_ars"] >= 0 else ""
        print(
            f"    [{r['estado'].upper():7}] {r['rubro']:30} "
            f"Proy: {fmt_ars(r['proyectado_ars']):>18}  "
            f"Real: {fmt_ars(r['real_ars']):>18}  "
            f"Desvio: {signo}{fmt_ars(r['desvio_ars'])} ({signo}{r['desvio_pct']:.1f}%)"
        )

    tots = resultado["totales_semana"]
    print(f"\n  Gastos sin rubro asignado: {len(resultado['gastos_sin_rubro'])}")
    if resultado["gastos_sin_rubro"]:
        for g in resultado["gastos_sin_rubro"]:
            print(f"    - {g['proveedor']} | {fmt_ars(g['total_ars'])} | {g['motivo_no_asignado']}")

    print(f"\n  Totales de la semana:")
    print(f"    Proyectado total : {fmt_ars(tots['proyectado_total_ars'])}")
    print(f"    Real total       : {fmt_ars(tots['real_total_ars'])}")
    print(f"    Desvío           : {fmt_ars(tots['desvio_ars'])} ({tots['desvio_pct']:+.1f}%)")

    semaforo_iconos = {"ok": "VERDE", "alerta": "AMARILLO", "critico": "ROJO"}
    print(f"\n  Semaforo general de la semana: {semaforo_iconos.get(resultado['semaforo_general'], resultado['semaforo_general']).upper()}")
    print(f"\n[MatchSemana] Reporte guardado → {ruta_salida}\n")

    return payload


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="Auditor de desvíos presupuestarios — Arch Proposal Suite."
    )
    p.add_argument("--semana",   type=int,  default=None,
                   help="Número de semana de obra a auditar (ej. 1)")
    p.add_argument("--desde",    type=str,  default=None,
                   help="Fecha de inicio del período (YYYY-MM-DD)")
    p.add_argument("--hasta",    type=str,  default=None,
                   help="Fecha de fin del período (YYYY-MM-DD)")
    p.add_argument("--dry-run",  action="store_true",
                   help="Muestra el reporte pero no guarda el archivo JSON")
    p.add_argument("--solo-auditoria", action="store_true",
                   help="Ejecuta solo la auditoría clásica sin generar reporte de match")

    args = p.parse_args()

    semana = args.semana if args.semana is not None else 1

    # Siempre generar el reporte de match cuando se especifica --semana
    # (o con la semana default = 1)
    if not args.solo_auditoria:
        generar_reporte_match(semana)

    # Auditoría clásica: solo si se pasó --semana, --desde, --hasta o --solo-auditoria
    if args.solo_auditoria or args.desde or args.hasta or args.semana is not None:
        auditar(
            semana=args.semana,
            desde=args.desde,
            hasta=args.hasta,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
