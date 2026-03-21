"""
generate_schedule.py
─────────────────────────────────────────────────────────────────────────────
Generador de Cronograma de Obra — Arch Proposal Suite
Recibe los resultados de CalculadoraPresupuesto y genera:
  - Un cronograma ordenado con fechas de inicio/fin
  - El camino crítico (CPM) del proyecto
  - Exporta: outputs/cronograma.json  y  outputs/cronograma.csv

Uso independiente:
    python generate_schedule.py --personal-oficial 2 --personal-ayudante 2
                                --fecha-inicio 2025-04-01 --jornada 8

Uso integrado (desde otro script):
    from generate_schedule import GeneradorCronograma
    gen = GeneradorCronograma(resultados=calc.resultados, ...)
    gen.calcular()
    gen.exportar()
"""

import json
import os
import csv
import glob
import argparse
import unicodedata
from datetime import date, timedelta
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# RUTAS BASE
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent.parent
SESION_PATH = BASE_DIR / "outputs" / "sesion_activa.json"
RUBROS_PATH = BASE_DIR / "references" / "rubros.json"


# ─────────────────────────────────────────────────────────────────────────────
# 2.1 — CARGA DE SESIÓN
# ─────────────────────────────────────────────────────────────────────────────

def cargar_sesion():
    """Lee sesion_activa.json. Si no existe, retorna defaults de obra_completa."""
    if not SESION_PATH.exists():
        print("[WARNING] sesion_activa.json no encontrado — usando modo obra_completa por defecto")
        return {
            "rubros_seleccionados": [],
            "modo_alcance": "obra_completa",
            "alcance_descripcion": "",
            "personal": {"oficiales": 3, "ayudantes": 3},
        }
    with SESION_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def cargar_rubros():
    """Lee references/rubros.json."""
    with RUBROS_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def no_accent(text: str) -> str:
    """Elimina acentos y convierte a minúsculas para comparación robusta."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', text.lower())
        if unicodedata.category(c) != 'Mn'
    )

# ─────────────────────────────────────────────────────────────────────────────
# TABLA DE DEPENDENCIAS
# Define el orden lógico de ejecución de los rubros de construcción.
# Clave: fragmento de texto que debe estar en el nombre del elemento.
# Valor: lista de fragmentos de texto de predecesores.
# ─────────────────────────────────────────────────────────────────────────────
DEPENDENCIAS_CLAVE = {
    # Trabajos preparatorios — sin predecesores
    "replanteo":              [],
    "nivelacion":             [],
    # Excavación requiere replanteo
    "excavacion":             ["replanteo"],
    # Cimientos requieren excavación
    "cimiento":               ["excavacion"],
    # Estructura requiere cimientos
    "columna":                ["cimiento"],
    "viga":                   ["columna"],
    "losa":                   ["viga"],
    "encadenado":             ["cimiento"],
    # Cerramientos requieren estructura
    "ladrillo":               ["columna", "viga"],
    "steel frame":            ["columna"],
    "muro":                   ["columna"],
    # Cubierta requiere estructura y cerramiento
    "cubierta":               ["losa", "ladrillo", "steel frame"],
    "membrana":               ["losa"],
    # Aislaciones dependen de cubierta / cerramiento
    "capa aisladora":         ["cimiento", "ladrillo"],
    "aislacion":              ["cubierta"],
    # Revoques requieren cerramiento y cubierta
    "revoque grueso":         ["ladrillo", "steel frame", "cubierta"],
    "azotado":                ["ladrillo"],
    "revoque fino":           ["revoque grueso"],
    # Contrapisos y carpetas requieren estructura y cerramiento
    "contrapiso":             ["cimiento", "ladrillo"],
    "carpeta":                ["contrapiso"],
    # Pisos, cielorrasos e instalaciones requieren contrapiso/revoque
    "pisos":                  ["carpeta", "revoque grueso"],
    "ceramico":               ["carpeta", "revoque grueso"],
    "zocalo":                 ["pisos", "ceramico"],
    "cielorraso":             ["revoque fino"],
    "instalacion electrica":  ["ladrillo", "steel frame"],
    "instalacion sanitaria":  ["ladrillo", "contrapiso"],
    # Pinturas van al final
    "pintura":                ["revoque fino", "cielorraso"],
}

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def siguiente_dia_habil(desde: date) -> date:
    """Avanza al próximo día hábil (Lunes–Viernes)."""
    dia = desde + timedelta(days=1)
    while dia.weekday() >= 5:   # 5=Sábado, 6=Domingo
        dia += timedelta(days=1)
    return dia


def agregar_dias_habiles(desde: date, n_dias: int) -> date:
    """Suma (o resta si n_dias < 0) n días hábiles a una fecha."""
    if n_dias == 0:
        return desde
    actual = desde
    contados = 0
    step = 1 if n_dias > 0 else -1
    target = abs(int(n_dias))
    while contados < target:
        actual += timedelta(days=step)
        if actual.weekday() < 5:
            contados += 1
    return actual


def resolver_predecesores(nombre: str) -> list:
    """Devuelve las claves de predecesores para un nombre de elemento dado."""
    nombre_norm = no_accent(nombre)
    for palabra_clave, predec in DEPENDENCIAS_CLAVE.items():
        if palabra_clave in nombre_norm:
            return predec
    return []   # Sin predecesores conocidos → puede empezar desde el inicio


# ─────────────────────────────────────────────────────────────────────────────
# 2.4 — CARGA DE PRESUPUESTO (para enlazar costo_total_ars por tarea)
# ─────────────────────────────────────────────────────────────────────────────

def cargar_presupuesto():
    """
    Busca el primer archivo outputs/presupuesto_*.json o presupuesto.json.
    Devuelve un dict {nombre_normalizado: costo_total_ars} o {} si no existe.
    """
    outputs_dir = BASE_DIR / "outputs"
    candidatos = list(outputs_dir.glob("presupuesto_*.json")) + list(outputs_dir.glob("presupuesto.json"))

    if not candidatos:
        return {}

    ruta = candidatos[0]
    try:
        with ruta.open(encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}

    # El presupuesto puede tener estructura {"items": [...]} o ser una lista directa
    items = data if isinstance(data, list) else data.get("items", [])

    tabla = {}
    for item in items:
        nombre = item.get("elemento") or item.get("nombre") or ""
        costo = item.get("costo_total") or item.get("total_ars") or item.get("subtotales", {}).get("total")
        if nombre and costo is not None:
            tabla[no_accent(nombre)] = float(costo)

    return tabla


def buscar_costo(nombre_elemento: str, tabla_presupuesto: dict):
    """
    Busca el costo de un elemento en la tabla de presupuesto usando matching
    normalizado. Retorna el valor float o None si no hay match.
    """
    if not tabla_presupuesto:
        return None
    nombre_norm = no_accent(nombre_elemento)
    # Búsqueda exacta primero
    if nombre_norm in tabla_presupuesto:
        return tabla_presupuesto[nombre_norm]
    # Búsqueda parcial: el nombre del elemento está contenido en la clave
    for clave, costo in tabla_presupuesto.items():
        if nombre_norm in clave or clave in nombre_norm:
            return costo
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 2.2 — FILTRADO POR RUBRO
# ─────────────────────────────────────────────────────────────────────────────

def obtener_keywords_rubro(rubro_id: str, rubros_data: list) -> list:
    """Retorna la lista de keywords_cronograma del rubro indicado."""
    for rubro in rubros_data:
        if rubro.get("id") == rubro_id:
            return rubro.get("keywords_cronograma", [])
    return []


def tarea_pertenece_a_rubros(nombre_elemento: str, rubros_ids: list, rubros_data: list) -> bool:
    """
    Retorna True si el nombre del elemento hace match con alguna keyword
    de alguno de los rubros indicados.
    """
    nombre_norm = no_accent(nombre_elemento)
    for rubro_id in rubros_ids:
        keywords = obtener_keywords_rubro(rubro_id, rubros_data)
        for kw in keywords:
            if no_accent(kw) in nombre_norm:
                return True
    return False


def filtrar_resultados_por_rubro(resultados: list, rubros_ids: list, rubros_data: list) -> list:
    """
    Modo rubro_puntual: retorna solo los resultados cuyo elemento
    corresponde a uno de los rubros seleccionados.
    """
    filtrados = []
    for r in resultados:
        nombre = r.get("elemento", "")
        if tarea_pertenece_a_rubros(nombre, rubros_ids, rubros_data):
            filtrados.append(r)
    return filtrados


def agrupar_resultados_por_rubro(resultados: list, rubros_data: list) -> list:
    """
    Modo obra_completa: agrupa los resultados por rubro y genera un resultado
    resumido por rubro (un bloque con duración y costo total del rubro).
    """
    # Asignar cada resultado a su rubro
    grupos = {}     # rubro_id -> {"nombre": ..., "items": [...]}
    sin_rubro = []

    for r in resultados:
        nombre = r.get("elemento", "")
        asignado = False
        for rubro in rubros_data:
            rubro_id = rubro.get("id", "")
            keywords = rubro.get("keywords_cronograma", [])
            for kw in keywords:
                if no_accent(kw) in no_accent(nombre):
                    if rubro_id not in grupos:
                        grupos[rubro_id] = {"nombre": rubro.get("nombre", rubro_id), "items": []}
                    grupos[rubro_id]["items"].append(r)
                    asignado = True
                    break
            if asignado:
                break
        if not asignado:
            sin_rubro.append(r)

    # Construir resultados agrupados: un item por rubro
    agrupados = []
    for rubro_id, grupo in grupos.items():
        items = grupo["items"]
        total_hs_oficial  = sum(i.get("hs_oficial", 0) for i in items)
        total_hs_ayudante = sum(i.get("hs_ayudante", 0) for i in items)
        costo_total = sum(
            i.get("subtotales", {}).get("total", 0) for i in items
        )

        # Reconstruir horas si no vienen explícitas
        if total_hs_oficial == 0 and total_hs_ayudante == 0:
            precio_blend = (4500 + 3500) / 2
            for i in items:
                costo_mo = i.get("subtotales", {}).get("mano_obra", 0)
                total_hs = (costo_mo / 2.2521) / precio_blend if precio_blend > 0 else 0
                total_hs_oficial  += total_hs / 2
                total_hs_ayudante += total_hs / 2

        agrupados.append({
            "elemento":    f"{rubro_id} — {grupo['nombre']}",
            "rubro_id":    rubro_id,
            "hs_oficial":  round(total_hs_oficial, 2),
            "hs_ayudante": round(total_hs_ayudante, 2),
            "costo_total_ars": round(costo_total, 2) if costo_total else None,
            "metricas":    {"items_agrupados": len(items)},
            "subtotales":  {"total": costo_total, "mano_obra": 0},
        })

    # Agregar elementos sin rubro asignado (como items individuales)
    for r in sin_rubro:
        agrupados.append(r)

    return agrupados


# ─────────────────────────────────────────────────────────────────────────────
# CLASE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

class GeneradorCronograma:

    def __init__(self,
                 resultados: list,
                 personal_oficial: int = 2,
                 personal_ayudante: int = 2,
                 fecha_inicio: str = None,
                 jornada_hs: float = 8.0,
                 sesion: dict = None,
                 rubros_data: list = None):
        """
        Args:
            resultados: lista de dicts generada por CalculadoraPresupuesto.consolidar()["items"]
            personal_oficial: cantidad de oficiales disponibles
            personal_ayudante: cantidad de ayudantes disponibles
            fecha_inicio: 'YYYY-MM-DD' | None (usa hoy)
            jornada_hs: horas de trabajo por día (default: 8)
            sesion: dict de sesion_activa.json (si None, se carga automáticamente)
            rubros_data: lista de rubros.json (si None, se carga automáticamente)
        """
        self.resultados_originales = resultados
        self.pof = max(1, personal_oficial)
        self.pay = max(1, personal_ayudante)
        self.jornada = jornada_hs
        self.fecha_inicio = date.fromisoformat(fecha_inicio) if fecha_inicio else date.today()
        self.tareas: list[dict] = []     # Cronograma calculado

        # Sesión y rubros
        self.sesion = sesion if sesion is not None else cargar_sesion()
        self.rubros_data = rubros_data if rubros_data is not None else cargar_rubros()

        # Presupuesto para enlazar costos (2.4)
        self.tabla_presupuesto = cargar_presupuesto()

        # Determinar modo
        self.modo_alcance = self.sesion.get("modo_alcance", "obra_completa")
        self.rubros_seleccionados = self.sesion.get("rubros_seleccionados", [])

    # ─── PASO 1: CONSTRUIR LA LISTA DE TAREAS ────────────────────────────────

    def _preparar_resultados(self) -> list:
        """
        2.2 — Aplica el filtrado / agrupamiento según el modo de alcance.
        Retorna la lista de resultados a usar para construir las tareas.
        """
        if self.modo_alcance == "rubro_puntual" and self.rubros_seleccionados:
            filtrados = filtrar_resultados_por_rubro(
                self.resultados_originales,
                self.rubros_seleccionados,
                self.rubros_data
            )
            if not filtrados:
                print(f"[WARNING] No se encontraron tareas para los rubros: {self.rubros_seleccionados}")
                print("          Revise las keywords en references/rubros.json.")
            return filtrados

        elif self.modo_alcance == "obra_completa":
            return agrupar_resultados_por_rubro(
                self.resultados_originales,
                self.rubros_data
            )

        else:
            # rubros_multiples u otro: filtrar por todos los rubros seleccionados
            return filtrar_resultados_por_rubro(
                self.resultados_originales,
                self.rubros_seleccionados,
                self.rubros_data
            )

    def _construir_tareas(self):
        """Convierte los resultados del presupuesto en tareas del cronograma."""
        resultados_a_usar = self._preparar_resultados()
        self.tareas = []

        for r in resultados_a_usar:
            elemento = r["elemento"]
            hs_oficial   = r.get("hs_oficial", 0)
            hs_ayudante  = r.get("hs_ayudante", 0)

            # Si el resultado no tiene las horas guardadas (compatibilidad con
            # versiones anteriores de calculate_budget.py), estimamos desde el costo:
            if hs_oficial == 0 and hs_ayudante == 0:
                costo_mo = r.get("subtotales", {}).get("mano_obra", 0)
                # Estimación: distribución 50/50 entre oficial y ayudante
                precio_blend = (4500 + 3500) / 2
                total_hs = (costo_mo / 2.2521) / precio_blend if precio_blend > 0 else 0
                hs_oficial  = total_hs / 2
                hs_ayudante = total_hs / 2

            # Calcular duración en días hábiles
            if hs_oficial > 0 and self.pof > 0:
                dias_por_oficial = hs_oficial / (self.pof * self.jornada)
            else:
                dias_por_oficial = 0
            if hs_ayudante > 0 and self.pay > 0:
                dias_por_ayudante = hs_ayudante / (self.pay * self.jornada)
            else:
                dias_por_ayudante = 0

            duracion = max(1.0, dias_por_oficial, dias_por_ayudante)

            # 2.4 — Buscar costo_total_ars en el presupuesto exportado
            # Para modo obra_completa el costo ya viene en el resultado agrupado
            costo_ars = r.get("costo_total_ars")
            if costo_ars is None:
                costo_ars = buscar_costo(elemento, self.tabla_presupuesto)
                # Fallback: usar subtotales.total si está disponible
                if costo_ars is None:
                    total_sub = r.get("subtotales", {}).get("total")
                    if total_sub:
                        costo_ars = round(float(total_sub), 2)

            self.tareas.append({
                "id":              elemento,
                "elemento":        elemento,
                "metricas":        r.get("metricas", {}),
                "hs_oficial":      round(hs_oficial, 2),
                "hs_ayudante":     round(hs_ayudante, 2),
                "duracion_dias":   round(duracion, 1),
                "costo_total_ars": costo_ars,
                "predecesores":    resolver_predecesores(elemento),
                # Campos CPM (se rellenan en calcular())
                "inicio_temprano": None,
                "fin_temprano":    None,
                "inicio_tardio":   None,
                "fin_tardio":      None,
                "holgura":         None,
                "critica":         False,
            })

    # ─── PASO 2: CPM — FORWARD PASS (inicio / fin tempranos) ─────────────────

    def _forward_pass(self):
        """Calcula el inicio y fin más temprano de cada tarea."""
        por_id = {t["id"]: t for t in self.tareas}

        resuelta = {t["id"]: False for t in self.tareas}
        max_iter = len(self.tareas) * 2

        for _ in range(max_iter):
            for tarea in self.tareas:
                if resuelta[tarea["id"]]:
                    continue

                predec_tareas = []
                for pred_kw in tarea["predecesores"]:
                    for t in self.tareas:
                        if pred_kw in no_accent(t["id"]) and t["id"] != tarea["id"]:
                            predec_tareas.append(t)
                            break

                if any(not resuelta[p["id"]] for p in predec_tareas):
                    continue

                if predec_tareas:
                    fin_max = max(p["fin_temprano"] for p in predec_tareas)
                    tarea["inicio_temprano"] = siguiente_dia_habil(fin_max)
                else:
                    tarea["inicio_temprano"] = self.fecha_inicio

                tarea["fin_temprano"] = agregar_dias_habiles(
                    tarea["inicio_temprano"],
                    int(tarea["duracion_dias"])
                )
                resuelta[tarea["id"]] = True

        for tarea in self.tareas:
            if tarea["inicio_temprano"] is None:
                tarea["inicio_temprano"] = self.fecha_inicio
                tarea["fin_temprano"] = agregar_dias_habiles(
                    self.fecha_inicio,
                    int(tarea["duracion_dias"])
                )

    # ─── PASO 3: CPM — BACKWARD PASS (inicio / fin tardíos + holgura) ────────

    def _backward_pass(self):
        """Calcula el inicio / fin tardío y la holgura de cada tarea."""
        fecha_fin_proyecto = max(t["fin_temprano"] for t in self.tareas)

        sucesores_de = {t["id"]: [] for t in self.tareas}
        for tarea in self.tareas:
            for pred_kw in tarea["predecesores"]:
                for candidata in self.tareas:
                    if pred_kw in no_accent(candidata["id"]) and candidata["id"] != tarea["id"]:
                        sucesores_de[candidata["id"]].append(tarea)
                        break

        for tarea in self.tareas:
            tarea["fin_tardio"]    = fecha_fin_proyecto
            tarea["inicio_tardio"] = agregar_dias_habiles(
                fecha_fin_proyecto, -int(tarea["duracion_dias"])
            )

        for _ in range(len(self.tareas) * 3):
            cambio = False
            for tarea in reversed(self.tareas):
                sucesores = sucesores_de[tarea["id"]]
                if not sucesores:
                    continue

                mejor_fin = min(s["inicio_tardio"] for s in sucesores)
                if mejor_fin < tarea["fin_tardio"]:
                    tarea["fin_tardio"]    = mejor_fin
                    tarea["inicio_tardio"] = agregar_dias_habiles(
                        mejor_fin, -int(tarea["duracion_dias"])
                    )
                    cambio = True

            if not cambio:
                break

        for tarea in self.tareas:
            hol_dias = (tarea["inicio_tardio"] - tarea["inicio_temprano"]).days
            tarea["holgura"] = max(0, hol_dias)
            tarea["critica"] = tarea["holgura"] == 0

    # ─── API PRINCIPAL ────────────────────────────────────────────────────────

    def calcular(self):
        """Ejecuta todo el pipeline de cálculo del cronograma."""
        self._construir_tareas()
        self._forward_pass()
        self._backward_pass()
        return self

    def duracion_total(self) -> int:
        """Retorna la duración total del proyecto en días hábiles."""
        if not self.tareas:
            return 0
        fin = max(t["fin_temprano"] for t in self.tareas)
        dias = 0
        actual = self.fecha_inicio
        while actual < fin:
            actual += timedelta(days=1)
            if actual.weekday() < 5:
                dias += 1
        return dias

    def resumen_consola(self):
        """Imprime el cronograma en la consola como tabla ASCII."""
        linea = "─" * 100
        print(f"\n{'CRONOGRAMA DE OBRA':^100}")
        print(f"{'Arch Proposal Suite':^100}")
        print(linea)
        print(f"  Modo: {self.modo_alcance}  |  Personal: {self.pof} oficiales / {self.pay} ayudantes  |  "
              f"Jornada: {self.jornada}hs  |  Inicio: {self.fecha_inicio}")
        print(linea)
        print(f"  {'TAREA':<40} {'DÍAS':>5} {'INICIO':>12} {'FIN':>12} {'HOLGURA':>8} {'CRÍTICA':>8}")
        print(linea)
        for t in self.tareas:
            critica_mark = "SI" if t["critica"] else "no"
            print(f"  {t['elemento']:<40} {t['duracion_dias']:>5.1f} "
                  f"{str(t['inicio_temprano']):>12} {str(t['fin_temprano']):>12} "
                  f"{t['holgura']:>8} {critica_mark:>8}")
        print(linea)
        print(f"  DURACION TOTAL DEL PROYECTO: {self.duracion_total()} dias habiles  |  "
              f"Fin estimado: {max(t['fin_temprano'] for t in self.tareas)}")
        print(linea)

        criticas = [t["elemento"] for t in self.tareas if t["critica"]]
        if criticas:
            print(f"\n  CAMINO CRITICO:")
            for c in criticas:
                print(f"       -> {c}")
        print()

    # ─── EXPORTAR ─────────────────────────────────────────────────────────────

    def _construir_alcance(self) -> dict:
        """
        2.3 — Construye el campo "alcance" para el JSON exportado.
        """
        rubros_ids = self.rubros_seleccionados if self.rubros_seleccionados else []

        # Descripción legible de los rubros incluidos
        nombres_rubros = []
        for rubro_id in rubros_ids:
            for rubro in self.rubros_data:
                if rubro.get("id") == rubro_id:
                    nombres_rubros.append(rubro.get("nombre", rubro_id))
                    break

        descripcion = self.sesion.get("alcance_descripcion", "")
        if not descripcion:
            if self.modo_alcance == "obra_completa":
                descripcion = "Todos los rubros de la obra"
            elif nombres_rubros:
                descripcion = "Solo " + ", ".join(nombres_rubros)
            else:
                descripcion = self.modo_alcance

        return {
            "rubros_incluidos": rubros_ids if rubros_ids else ["TODOS"],
            "modo": self.modo_alcance,
            "descripcion": descripcion,
        }

    def _nombre_archivo_cronograma(self) -> str:
        """Genera nombre descriptivo según el scope de la sesión."""
        if self.modo_alcance == "obra_completa":
            return "cronograma_obra_completa.json"
        elif self.modo_alcance in ("rubro_puntual", "rubros_multiples"):
            rubros = "_".join(r.lower() for r in self.rubros_seleccionados)
            return f"cronograma_{rubros}.json"
        return "cronograma.json"

    def _actualizar_estado_proyecto(self, ruta_archivo: str, dir_salida: str):
        """
        Agrega la ruta del archivo exportado a estado-proyecto.json
        bajo archivos_generados.cronogramas y actualiza ultimo_cronograma.
        """
        estado_path = os.path.normpath(os.path.join(dir_salida, "estado-proyecto.json"))
        if not os.path.exists(estado_path):
            estado = {}
        else:
            try:
                with open(estado_path, encoding="utf-8") as f:
                    estado = json.load(f)
            except Exception:
                estado = {}

        if "archivos_generados" not in estado:
            estado["archivos_generados"] = {
                "cronogramas": [],
                "presupuestos": [],
                "ultimo_cronograma": None,
                "ultimo_presupuesto": None,
            }

        cronogramas = estado["archivos_generados"].get("cronogramas", [])
        if ruta_archivo not in cronogramas:
            cronogramas.append(ruta_archivo)
        estado["archivos_generados"]["cronogramas"] = cronogramas
        estado["archivos_generados"]["ultimo_cronograma"] = ruta_archivo

        with open(estado_path, "w", encoding="utf-8") as f:
            json.dump(estado, f, indent=2, ensure_ascii=False)

    def exportar(self, dir_salida: str = None):
        """Exporta cronograma.json y cronograma.csv en outputs/.
        Adicionalmente exporta un archivo con nombre descriptivo según el scope.
        """
        base = os.path.dirname(os.path.abspath(__file__))
        if dir_salida is None:
            dir_salida = os.path.normpath(os.path.join(base, "..", "outputs"))
        os.makedirs(dir_salida, exist_ok=True)

        # ── JSON ──────────────────────────────────────────────────
        datos_json = {
            # 2.3 — campo alcance al nivel raíz
            "alcance": self._construir_alcance(),
            "configuracion": {
                "fecha_inicio":       str(self.fecha_inicio),
                "personal_oficial":   self.pof,
                "personal_ayudante":  self.pay,
                "jornada_hs":         self.jornada,
            },
            "duracion_total_dias": self.duracion_total(),
            "fecha_fin_estimada":  str(max(t["fin_temprano"] for t in self.tareas)),
            "camino_critico": [t["elemento"] for t in self.tareas if t["critica"]],
            "tareas": [
                {
                    "elemento":         t["elemento"],
                    "duracion_dias":    t["duracion_dias"],
                    # 2.4 — costo_total_ars por tarea
                    "costo_total_ars":  t["costo_total_ars"],
                    "inicio":           str(t["inicio_temprano"]),
                    "fin":              str(t["fin_temprano"]),
                    "inicio_tardio":    str(t["inicio_tardio"]),
                    "fin_tardio":       str(t["fin_tardio"]),
                    "holgura_dias":     t["holgura"],
                    "critica":          t["critica"],
                    "predecesores":     t["predecesores"],
                    "metricas":         t["metricas"],
                }
                for t in self.tareas
            ]
        }
        # Archivo original (compatibilidad con verify_scope.py, build_landing.py, audit_budget.py)
        ruta_json = os.path.join(dir_salida, "cronograma.json")
        with open(ruta_json, "w", encoding="utf-8") as f:
            json.dump(datos_json, f, indent=2, ensure_ascii=False)
        print(f"[Cronograma] JSON exportado -> {ruta_json}")

        # Archivo adicional con nombre descriptivo por scope (3.3)
        nombre_descriptivo = self._nombre_archivo_cronograma()
        if nombre_descriptivo != "cronograma.json":
            ruta_descriptiva = os.path.join(dir_salida, nombre_descriptivo)
            with open(ruta_descriptiva, "w", encoding="utf-8") as f:
                json.dump(datos_json, f, indent=2, ensure_ascii=False)
            print(f"[Cronograma] JSON (scope)  -> {ruta_descriptiva}")
            self._actualizar_estado_proyecto(ruta_descriptiva, dir_salida)
        else:
            self._actualizar_estado_proyecto(ruta_json, dir_salida)

        # ── CSV (formato Gantt básico) ─────────────────────────────
        ruta_csv = os.path.join(dir_salida, "cronograma.csv")
        with open(ruta_csv, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Tarea", "Duración (días hábiles)", "Costo Total ARS",
                "Inicio temprano", "Fin temprano",
                "Inicio tardío", "Fin tardío",
                "Holgura (días)", "Crítica?",
                "Predecesores"
            ])
            for t in self.tareas:
                writer.writerow([
                    t["elemento"],
                    t["duracion_dias"],
                    t["costo_total_ars"] if t["costo_total_ars"] is not None else "",
                    str(t["inicio_temprano"]),
                    str(t["fin_temprano"]),
                    str(t["inicio_tardio"]),
                    str(t["fin_tardio"]),
                    t["holgura"],
                    "SI" if t["critica"] else "no",
                    " | ".join(t["predecesores"]) if t["predecesores"] else "—"
                ])
        print(f"[Cronograma] CSV  exportado -> {ruta_csv}")


# ─────────────────────────────────────────────────────────────────────────────
# EJECUCIÓN INDEPENDIENTE
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Genera el cronograma de obra a partir del presupuesto calculado."
    )
    parser.add_argument("--personal-oficial",  type=int,   default=None,
                        help="Cantidad de oficiales disponibles")
    parser.add_argument("--personal-ayudante", type=int,   default=None,
                        help="Cantidad de ayudantes disponibles")
    parser.add_argument("--fecha-inicio",      type=str,   default=None,
                        help="Fecha de inicio de obra YYYY-MM-DD (default: hoy)")
    parser.add_argument("--jornada",           type=float, default=8.0,
                        help="Horas de trabajo por día (default: 8)")
    parser.add_argument("--sin-exportar",      action="store_true",
                        help="No guardar archivos, solo mostrar en consola")
    args = parser.parse_args()

    # 2.1 — Leer sesion_activa.json al inicio
    sesion = cargar_sesion()
    rubros_data = cargar_rubros()

    modo = sesion.get("modo_alcance", "obra_completa")
    rubros_sel = sesion.get("rubros_seleccionados", [])

    print(f"[Cronograma] Modo alcance: {modo}")
    if rubros_sel:
        print(f"[Cronograma] Rubros seleccionados: {rubros_sel}")

    # Personal: args > sesion > defaults
    personal = sesion.get("personal", {})
    pof = args.personal_oficial  if args.personal_oficial  is not None else personal.get("oficiales",  3)
    pay = args.personal_ayudante if args.personal_ayudante is not None else personal.get("ayudantes",  3)
    pof = max(1, pof)
    pay = max(1, pay)

    # ── Correr el ejemplo de casa de 60m2 del calculate_budget ──────────
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from calculate_budget import CalculadoraPresupuesto

    base_dir = os.path.dirname(os.path.abspath(__file__))
    ruta_rubros  = os.path.normpath(os.path.join(base_dir, "..", "references", "rubros.json"))
    ruta_precios = os.path.normpath(os.path.join(base_dir, "..", "references", "precios_materiales.csv"))

    calc = CalculadoraPresupuesto(ruta_rubros, ruta_precios)
    INCL = True; PCT = 1.2521

    # Datos de ejemplo: casa simple de 60m2
    calc.calc_replanteo(60, INCL, PCT)
    calc.calc_excavacion(15, mecanica=False)
    calc.calc_cimiento_corrido(8, INCL, PCT)
    calc.calc_elemento_ha("Columnas HA", volumen_m3=3.0, kg_acero=280, m2_encofrado=18)
    calc.calc_elemento_ha("Vigas HA",    volumen_m3=2.5, kg_acero=210, m2_encofrado=15, puntales=12)
    calc.calc_elemento_ha("Losa Llena",  volumen_m3=4.0, kg_acero=350, m2_encofrado=60, puntales=20)
    calc.calc_ladrillo_hueco(120, INCL, PCT)
    calc.calc_capa_aisladora(40, INCL, PCT)
    calc.calc_cubierta_chapa(65, INCL, PCT)
    calc.calc_revoque_grueso(200, espesor_cm=1.5)
    calc.calc_revoque_fino(200)
    calc.calc_contrapiso(60)
    calc.calc_carpeta(60)
    calc.calc_pisos_ceramicos(55)
    calc.calc_zocalos(80)
    calc.calc_cielorraso_aplicado(55)
    calc.calc_instalacion_electrica(25)
    calc.calc_instalacion_sanitaria(8)
    calc.calc_pintura_interior(350)
    calc.calc_pintura_exterior(80)

    # ── Generar el cronograma ──────────────────────────────────────────────────
    gen = GeneradorCronograma(
        resultados=calc.resultados,
        personal_oficial=pof,
        personal_ayudante=pay,
        fecha_inicio=args.fecha_inicio,
        jornada_hs=args.jornada,
        sesion=sesion,
        rubros_data=rubros_data,
    )
    gen.calcular()
    gen.resumen_consola()

    if not args.sin_exportar:
        gen.exportar()
