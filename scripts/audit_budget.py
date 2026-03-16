"""
audit_budget.py
─────────────────────────────────────────────────────────────────────────────
Auditor de Desvíos Presupuestarios — Arch Proposal Suite

Compara los gastos reales (tickets/facturas cargados) contra el presupuesto
teórico validado. Genera un reporte JSON de auditoría y una tabla Markdown
con semáforos de alerta.

Uso:
    # Auditoría del período completo
    python audit_budget.py

    # Auditoría de una semana específica
    python audit_budget.py --semana 1

    # Auditoría de un rango de fechas
    python audit_budget.py --desde 2025-04-01 --hasta 2025-04-07

    # Sólo stdout sin guardar archivo
    python audit_budget.py --dry-run
"""

import os
import sys
import json
import argparse
import math
from datetime import datetime, date, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR  = os.path.normpath(os.path.join(BASE_DIR, "..", "outputs"))
ESTADO_PATH  = os.path.normpath(os.path.join(BASE_DIR, "..", "estado-proyecto.json"))
CRONO_PATH   = os.path.normpath(os.path.join(OUTPUTS_DIR, "cronograma.json"))
AUDIT_DIR    = os.path.join(OUTPUTS_DIR, "auditorias")


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

    args = p.parse_args()
    auditar(
        semana=args.semana,
        desde=args.desde,
        hasta=args.hasta,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
