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
import argparse
import unicodedata
from datetime import date, timedelta


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
# CLASE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

class GeneradorCronograma:

    def __init__(self,
                 resultados: list,
                 personal_oficial: int = 2,
                 personal_ayudante: int = 2,
                 fecha_inicio: str = None,
                 jornada_hs: float = 8.0):
        """
        Args:
            resultados: lista de dicts generada por CalculadoraPresupuesto.consolidar()["items"]
            personal_oficial: cantidad de oficiales disponibles
            personal_ayudante: cantidad de ayudantes disponibles
            fecha_inicio: 'YYYY-MM-DD' | None (usa hoy)
            jornada_hs: horas de trabajo por día (default: 8)
        """
        self.resultados = resultados
        self.pof = max(1, personal_oficial)
        self.pay = max(1, personal_ayudante)
        self.jornada = jornada_hs
        self.fecha_inicio = date.fromisoformat(fecha_inicio) if fecha_inicio else date.today()
        self.tareas: list[dict] = []     # Cronograma calculado

    # ─── PASO 1: CONSTRUIR LA LISTA DE TAREAS ────────────────────────────────

    def _construir_tareas(self):
        """Convierte los resultados del presupuesto en tareas del cronograma."""
        self.tareas = []
        for r in self.resultados:
            elemento = r["elemento"]
            # Extraer horas MO sumando oficial + ayudante desde el nombre del elemento
            # Las horas totales las reconstruimos desde el costo de MO del resultado
            # (alternativa más robusta: las guardamos en resultados extendidos)
            hs_oficial   = r.get("hs_oficial", 0)
            hs_ayudante  = r.get("hs_ayudante", 0)

            # Si el resultado no tiene las horas guardadas (compatibilidad con
            # versiones anteriores de calculate_budget.py), estimamos desde el costo:
            if hs_oficial == 0 and hs_ayudante == 0:
                costo_mo = r["subtotales"]["mano_obra"]
                # Estimación: distribución 50/50 entre oficial y ayudante
                # y calculamos hacia atrás desde el costo (sin cargas: ÷ 2.2521)
                precio_blend = (4500 + 3500) / 2   # Promedio oficial+ayudante
                total_hs = (costo_mo / 2.2521) / precio_blend if precio_blend > 0 else 0
                hs_oficial  = total_hs / 2
                hs_ayudante = total_hs / 2

            # Calcular duración en días hábiles
            # Bottleneck: el factor limitante entre los dos tipos de personal
            if hs_oficial > 0 and self.pof > 0:
                dias_por_oficial = hs_oficial / (self.pof * self.jornada)
            else:
                dias_por_oficial = 0
            if hs_ayudante > 0 and self.pay > 0:
                dias_por_ayudante = hs_ayudante / (self.pay * self.jornada)
            else:
                dias_por_ayudante = 0

            duracion = max(1.0, dias_por_oficial, dias_por_ayudante)

            self.tareas.append({
                "id":           elemento,
                "elemento":     elemento,
                "metricas":     r.get("metricas", {}),
                "hs_oficial":   round(hs_oficial, 2),
                "hs_ayudante":  round(hs_ayudante, 2),
                "duracion_dias": round(duracion, 1),
                "predecesores": resolver_predecesores(elemento),
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
        # Índice para buscar tareas por id
        por_id = {t["id"]: t for t in self.tareas}

        # Resolvemos el grafo con un enfoque iterativo
        resuelta = {t["id"]: False for t in self.tareas}
        max_iter = len(self.tareas) * 2

        for _ in range(max_iter):
            for tarea in self.tareas:
                if resuelta[tarea["id"]]:
                    continue

                # Buscar las tareas predecesoras (por fragmento de nombre, sin acentos)
                predec_tareas = []
                for pred_kw in tarea["predecesores"]:
                    for t in self.tareas:
                        if pred_kw in no_accent(t["id"]) and t["id"] != tarea["id"]:
                            predec_tareas.append(t)
                            break

                # Esperar a que todos los predecesores estén resueltos
                if any(not resuelta[p["id"]] for p in predec_tareas):
                    continue

                if predec_tareas:
                    # Empieza cuando termina el último predecesor
                    fin_max = max(p["fin_temprano"] for p in predec_tareas)
                    tarea["inicio_temprano"] = siguiente_dia_habil(fin_max)
                else:
                    tarea["inicio_temprano"] = self.fecha_inicio

                tarea["fin_temprano"] = agregar_dias_habiles(
                    tarea["inicio_temprano"],
                    int(tarea["duracion_dias"])
                )
                resuelta[tarea["id"]] = True

        # Para las no resueltas (tareas huérfanas o con deps rotas): desde inicio
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

        # ── Construir mapa de sucesores (inverso del mapa de predecesores) ──
        # Para cada tarea A, sucesores[A.id] = lista de tareas B donde A es predecesora de B
        sucesores_de = {t["id"]: [] for t in self.tareas}
        for tarea in self.tareas:
            for pred_kw in tarea["predecesores"]:
                # Buscar la primera tarea cuyo id contenga la palabra clave (sin acentos)
                for candidata in self.tareas:
                    if pred_kw in no_accent(candidata["id"]) and candidata["id"] != tarea["id"]:
                        sucesores_de[candidata["id"]].append(tarea)
                        break  # Un match por keyword es suficiente

        # Inicializar: todos los nodos parten con fin_tardio = fecha_fin_proyecto
        for tarea in self.tareas:
            tarea["fin_tardio"]    = fecha_fin_proyecto
            tarea["inicio_tardio"] = agregar_dias_habiles(
                fecha_fin_proyecto, -int(tarea["duracion_dias"])
            )

        # Iteración hacia atrás propagando restricciones
        for _ in range(len(self.tareas) * 3):
            cambio = False
            for tarea in reversed(self.tareas):
                sucesores = sucesores_de[tarea["id"]]
                if not sucesores:
                    continue  # Nodo hoja → mantiene la fecha_fin_proyecto

                # fin_tardio de A = mínimo de los inicio_tardio de sus sucesores
                mejor_fin = min(s["inicio_tardio"] for s in sucesores)
                if mejor_fin < tarea["fin_tardio"]:
                    tarea["fin_tardio"]    = mejor_fin
                    tarea["inicio_tardio"] = agregar_dias_habiles(
                        mejor_fin, -int(tarea["duracion_dias"])
                    )
                    cambio = True

            if not cambio:
                break   # Convergió

        # Calcular holgura y marcar camino crítico
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
        print(f"  Personal: {self.pof} oficiales / {self.pay} ayudantes  |  "
              f"Jornada: {self.jornada}hs  |  Inicio: {self.fecha_inicio}")
        print(linea)
        print(f"  {'TAREA':<40} {'DÍAS':>5} {'INICIO':>12} {'FIN':>12} {'HOLGURA':>8} {'CRÍTICA':>8}")
        print(linea)
        for t in self.tareas:
            critica_mark = "⚠ SÍ" if t["critica"] else "  no"
            print(f"  {t['elemento']:<40} {t['duracion_dias']:>5.1f} "
                  f"{str(t['inicio_temprano']):>12} {str(t['fin_temprano']):>12} "
                  f"{t['holgura']:>8} {critica_mark:>8}")
        print(linea)
        print(f"  DURACIÓN TOTAL DEL PROYECTO: {self.duracion_total()} días hábiles  |  "
              f"Fin estimado: {max(t['fin_temprano'] for t in self.tareas)}")
        print(linea)

        criticas = [t["elemento"] for t in self.tareas if t["critica"]]
        if criticas:
            print(f"\n  ⚠  CAMINO CRÍTICO:")
            for c in criticas:
                print(f"       → {c}")
        print()

    # ─── EXPORTAR ─────────────────────────────────────────────────────────────

    def exportar(self, dir_salida: str = None):
        """Exporta cronograma.json y cronograma.csv en outputs/."""
        base = os.path.dirname(os.path.abspath(__file__))
        if dir_salida is None:
            dir_salida = os.path.normpath(os.path.join(base, "..", "outputs"))
        os.makedirs(dir_salida, exist_ok=True)

        # ── JSON ──────────────────────────────────────────────────
        datos_json = {
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
        ruta_json = os.path.join(dir_salida, "cronograma.json")
        with open(ruta_json, "w", encoding="utf-8") as f:
            json.dump(datos_json, f, indent=2, ensure_ascii=False)
        print(f"[Cronograma] ✓ JSON exportado → {ruta_json}")

        # ── CSV (formato Gantt básico) ─────────────────────────────
        ruta_csv = os.path.join(dir_salida, "cronograma.csv")
        with open(ruta_csv, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Tarea", "Duración (días hábiles)",
                "Inicio temprano", "Fin temprano",
                "Inicio tardío", "Fin tardío",
                "Holgura (días)", "¿Crítica?",
                "Predecesores"
            ])
            for t in self.tareas:
                writer.writerow([
                    t["elemento"],
                    t["duracion_dias"],
                    str(t["inicio_temprano"]),
                    str(t["fin_temprano"]),
                    str(t["inicio_tardio"]),
                    str(t["fin_tardio"]),
                    t["holgura"],
                    "SÍ" if t["critica"] else "no",
                    " | ".join(t["predecesores"]) if t["predecesores"] else "—"
                ])
        print(f"[Cronograma] ✓ CSV  exportado → {ruta_csv}")


# ─────────────────────────────────────────────────────────────────────────────
# EJECUCIÓN INDEPENDIENTE — Usa el mismo ejemplo de casa 60m2
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Genera el cronograma de obra a partir del presupuesto calculado."
    )
    parser.add_argument("--personal-oficial",  type=int,   default=2,
                        help="Cantidad de oficiales disponibles (default: 2)")
    parser.add_argument("--personal-ayudante", type=int,   default=2,
                        help="Cantidad de ayudantes disponibles (default: 2)")
    parser.add_argument("--fecha-inicio",      type=str,   default=None,
                        help="Fecha de inicio de obra YYYY-MM-DD (default: hoy)")
    parser.add_argument("--jornada",           type=float, default=8.0,
                        help="Horas de trabajo por día (default: 8)")
    parser.add_argument("--sin-exportar",      action="store_true",
                        help="No guardar archivos, solo mostrar en consola")
    args = parser.parse_args()

    # ── Correr el mismo ejemplo de casa de 60m2 del calculate_budget ──────────
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
        personal_oficial=args.personal_oficial,
        personal_ayudante=args.personal_ayudante,
        fecha_inicio=args.fecha_inicio,
        jornada_hs=args.jornada
    )
    gen.calcular()
    gen.resumen_consola()

    if not args.sin_exportar:
        gen.exportar()
