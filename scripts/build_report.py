"""
build_report.py
─────────────────────────────────────────────────────────────────────────────
Generador de Reportes HTML — Arch Proposal Suite

Genera un archivo HTML profesional, imprimible en A4, con las secciones
solicitadas (presupuesto, cronograma, cómputo materiales) sin necesidad
de correr todos los agentes.

Uso:
    # Solo presupuesto
    python build_report.py --seccion presupuesto --proyecto "Casa García" --m2 60

    # Solo cronograma
    python build_report.py --seccion cronograma --m2 60 --fecha-inicio 2025-04-01

    # Presupuesto + cronograma
    python build_report.py --seccion presupuesto,cronograma --m2 60 --proyecto "Casa García"

    # Completo
    python build_report.py --completo --m2 60 --proyecto "Casa García"
"""

import os
import sys
import json
import argparse
from datetime import date, datetime

# Asegurar que podemos importar desde el mismo directorio
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from calculate_budget import CalculadoraPresupuesto
from generate_schedule import GeneradorCronograma

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS DE FORMATO
# ─────────────────────────────────────────────────────────────────────────────

def fmt_ars(valor: float) -> str:
    """Formatea un número como moneda ARS con separadores de miles."""
    return "$ {:,.0f}".format(valor).replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_d(valor, dec=2) -> str:
    """Formatea un número decimal."""
    return f"{valor:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ─────────────────────────────────────────────────────────────────────────────
# CARGA DE DATOS
# ─────────────────────────────────────────────────────────────────────────────

def crear_calculadora(m2=60, usar_precios_reales=True) -> CalculadoraPresupuesto:
    """Crea y corre una calculadora de presupuesto con datos básicos de la obra."""
    refs = os.path.normpath(os.path.join(BASE_DIR, "..", "references"))
    rubros  = os.path.join(refs, "rubros.json")
    precios = os.path.join(refs, "precios_materiales.csv") if usar_precios_reales else ""

    calc = CalculadoraPresupuesto(rubros, precios)
    return calc


def calcular_rubros_estandar(calc: CalculadoraPresupuesto, m2: float):
    """
    Calcula un set estándar de rubros basado en los m² totales de la obra.
    Estas proporciones son estimaciones típicas casa en planta baja.
    Pueden refinarse pasando un JSON de rubros personalizado.
    """
    INCL = True
    PCT  = 1.2521

    m_per = m2  # planta baja simple

    # Trabajos iniciales
    calc.calc_replanteo(m_per, INCL, PCT)
    calc.calc_excavacion(m_per * 0.25, mecanica=False)
    calc.calc_cimiento_corrido(m_per * 0.13, INCL, PCT)

    # Estructura (proporciones CIRSOC típicas)
    calc.calc_elemento_ha("Columnas HA",  volumen_m3=m_per*0.05,  kg_acero=m_per*4.7, m2_encofrado=m_per*0.3)
    calc.calc_elemento_ha("Vigas HA",     volumen_m3=m_per*0.04,  kg_acero=m_per*3.5, m2_encofrado=m_per*0.25)
    calc.calc_elemento_ha("Losa Llena",   volumen_m3=m_per*0.067, kg_acero=m_per*5.8, m2_encofrado=m_per, puntales=int(m_per/3))

    # Cerramientos
    calc.calc_ladrillo_hueco(m_per * 2.0, INCL, PCT)  # ~2m² de muro por m² de planta
    calc.calc_capa_aisladora(m_per * 0.7, INCL, PCT)

    # Cubierta
    calc.calc_cubierta_chapa(m_per * 1.1, INCL, PCT)

    # Revoques
    calc.calc_revoque_grueso(m_per * 3.5, espesor_cm=1.5)
    calc.calc_revoque_fino(m_per * 3.5)

    # Pisos
    calc.calc_contrapiso(m_per)
    calc.calc_carpeta(m_per)
    calc.calc_pisos_ceramicos(m_per * 0.9)
    calc.calc_zocalos(m_per * 1.5)

    # Cielorrasos
    calc.calc_cielorraso_aplicado(m_per * 0.85)

    # Instalaciones
    calc.calc_instalacion_electrica(int(m_per * 0.45))
    calc.calc_instalacion_sanitaria(max(4, int(m_per * 0.07)))

    # Pinturas
    calc.calc_pintura_interior(m_per * 5.5)
    calc.calc_pintura_exterior(m_per * 1.5)


# ─────────────────────────────────────────────────────────────────────────────
# RENDERIZADORES DE SECCIÓN
# ─────────────────────────────────────────────────────────────────────────────

# Clasificación de rubros por categoría para agrupar en tablas
CATEGORIAS = {
    "Trabajos Preparatorios":  ["Nivelación", "Replanteo"],
    "Cimientos":               ["Excavación", "Cimiento"],
    "Estructura":              ["Columna", "Viga", "Losa", "Encadenado"],
    "Cerramientos":            ["Ladrillo", "Steel Frame", "Muro"],
    "Cubierta y Aislaciones":  ["Cubierta", "Membrana", "Aislador", "Capa Aisladora"],
    "Revoques y Morteros":     ["Revoque", "Azotado", "Carpeta"],
    "Contrapisos":             ["Contrapiso"],
    "Pisos y Revestimientos":  ["Piso", "Cerámico", "Zócalo"],
    "Cielorrasos":             ["Cielorraso"],
    "Instalaciones":           ["Eléctrica", "Sanitaria"],
    "Pinturas":                ["Pintura"],
}


def categorizar(elemento: str) -> str:
    for cat, keywords in CATEGORIAS.items():
        for kw in keywords:
            if kw.lower() in elemento.lower():
                return cat
    return "Varios"


def render_seccion_presupuesto(resultados: list, resumen: dict, config: dict) -> str:
    """Genera el HTML de la sección Presupuesto."""

    # Agrupar ítems por categoría
    agrupado: dict[str, list] = {}
    for r in resultados:
        cat = categorizar(r["elemento"])
        agrupado.setdefault(cat, []).append(r)

    filas_tabla = ""
    for cat, items in agrupado.items():
        filas_tabla += f"""
        <tr class="categoria-header">
          <td colspan="6">{cat}</td>
        </tr>"""
        subtotal = 0
        for r in items:
            sub = r["subtotales"]
            total_item = sub["total"]
            subtotal += total_item
            metricas_str = ", ".join(f"{k}: {v}" for k, v in r["metricas"].items())
            filas_tabla += f"""
        <tr>
          <td>{r['elemento']}</td>
          <td class="num">{metricas_str}</td>
          <td class="num">{fmt_ars(sub['materiales'])}</td>
          <td class="num">{fmt_ars(sub['mano_obra'])}</td>
          <td class="num">{fmt_ars(sub['equipos'])}</td>
          <td class="num"><strong>{fmt_ars(total_item)}</strong></td>
        </tr>"""
        filas_tabla += f"""
        <tr class="subtotal-row">
          <td colspan="5">Subtotal — {cat}</td>
          <td class="num">{fmt_ars(subtotal)}</td>
        </tr>"""

    total_mat  = resumen["TOTAL_MATERIALES"]
    total_mo   = resumen["TOTAL_MANO_DE_OBRA"]
    total_eq   = resumen["TOTAL_EQUIPOS"]
    total_dir  = resumen["COSTO_DIRECTO_TOTAL"]

    costo_m2 = total_dir / config.get("m2", 1)

    return f"""
<div class="hoja">
  <div class="page-header">
    <div>
      <div class="ph-titulo">PRESUPUESTO DE OBRA</div>
      <div class="ph-proyecto">{config.get('proyecto', '')} — {config.get('localidad', '')}</div>
    </div>
    <div class="ph-logo">APS</div>
  </div>

  <div class="resumen-grid">
    <div class="resumen-card">
      <div class="rc-label">Total Materiales</div>
      <div class="rc-valor">{fmt_ars(total_mat)}</div>
    </div>
    <div class="resumen-card">
      <div class="rc-label">Total Mano de Obra</div>
      <div class="rc-valor">{fmt_ars(total_mo)}</div>
    </div>
    <div class="resumen-card">
      <div class="rc-label">Costo Directo Total</div>
      <div class="rc-valor">{fmt_ars(total_dir)}</div>
    </div>
  </div>

  <h2>Detalle por Rubro</h2>

  <div class="nota-aclaratoria">
    ⚠ Los precios de referencia son en <strong>Pesos Argentinos (ARS)</strong>
    al momento de emisión. Incluye cargas sociales (125,21%) sobre la mano de obra.
    Honorarios profesionales no incluidos.
  </div>

  <table>
    <thead>
      <tr>
        <th>Rubro / Ítem</th>
        <th class="num">Métricas</th>
        <th class="num">Materiales</th>
        <th class="num">Mano de Obra</th>
        <th class="num">Equipos</th>
        <th class="num">Subtotal</th>
      </tr>
    </thead>
    <tbody>
      {filas_tabla}
      <tr class="total-row">
        <td colspan="4"><strong>COSTO DIRECTO TOTAL</strong></td>
        <td class="num" colspan="2"><strong>{fmt_ars(total_dir)}</strong></td>
      </tr>
      <tr>
        <td colspan="4" style="color:#555; font-size:8.5pt;">Costo por m² construido ({config.get('m2', '—')} m²)</td>
        <td class="num" colspan="2"><strong>{fmt_ars(costo_m2)} / m²</strong></td>
      </tr>
    </tbody>
  </table>

  <div class="section-footer">
    Presupuesto paramétrico estimativo — Arch Proposal Suite — {date.today().strftime('%d/%m/%Y')}
  </div>
</div>"""


def render_seccion_cronograma(tareas: list, meta: dict, config: dict) -> str:
    """Genera el HTML de la sección Cronograma con Gantt visual."""

    if not tareas:
        return ""

    # Calcular duración total para escalar las barras
    fecha_inicio_proy = min(t["inicio_temprano"] for t in tareas)
    fecha_fin_proy    = max(t["fin_temprano"]    for t in tareas)
    duracion_total_dias = (fecha_fin_proy - fecha_inicio_proy).days or 1

    # Generar semanas para el header del Gantt
    from datetime import timedelta
    semanas = []
    s = fecha_inicio_proy
    while s <= fecha_fin_proy:
        semanas.append(s.strftime("S%d/%m"))
        s += timedelta(days=7)

    semanas_html = "".join(f'<div class="gantt-week">{sw}</div>' for sw in semanas)

    # Generar filas del Gantt
    filas_gantt = ""
    for t in tareas:
        offset_dias = (t["inicio_temprano"] - fecha_inicio_proy).days
        dur_dias    = (t["fin_temprano"] - t["inicio_temprano"]).days or 1

        left_pct  = (offset_dias  / duracion_total_dias) * 100
        width_pct = (dur_dias     / duracion_total_dias) * 100

        critica_cls = "critica" if t["critica"] else ""
        nombre = t["id"][:38]

        filas_gantt += f"""
        <div class="gantt-row">
          <div class="gantt-label" title="{t['id']}">{nombre}</div>
          <div class="gantt-track">
            <div class="gantt-bar {critica_cls}"
                 style="left:{left_pct:.1f}%;width:{max(width_pct,1):.1f}%"
                 title="{t['id']}: {t['inicio_temprano']} → {t['fin_temprano']} ({dur_dias}d)"
            >{dur_dias}d</div>
          </div>
        </div>"""

    camino_str = " → ".join(meta.get("camino_critico", [])) or "—"

    return f"""
<div class="hoja">
  <div class="page-header">
    <div>
      <div class="ph-titulo">CRONOGRAMA DE OBRA</div>
      <div class="ph-proyecto">{config.get('proyecto', '')} — {config.get('localidad', '')}</div>
    </div>
    <div class="ph-logo">APS</div>
  </div>

  <div class="resumen-grid">
    <div class="resumen-card">
      <div class="rc-label">Inicio de obra</div>
      <div class="rc-valor">{fecha_inicio_proy.strftime('%d/%m/%Y')}</div>
    </div>
    <div class="resumen-card">
      <div class="rc-label">Fin estimado</div>
      <div class="rc-valor">{fecha_fin_proy.strftime('%d/%m/%Y')}</div>
    </div>
    <div class="resumen-card">
      <div class="rc-label">Duración total</div>
      <div class="rc-valor">{meta.get('duracion_total_dias', '—')} días hábiles</div>
    </div>
  </div>

  <div class="nota-aclaratoria">
    Personal: {config.get('personal_oficial', 2)} oficial(es) / {config.get('personal_ayudante', 2)} ayudante(s)
    &emsp;|&emsp; Jornada: {config.get('jornada', 8)} hs/día
    &emsp;|&emsp; Camino crítico: <strong>{camino_str}</strong>
  </div>

  <h2>Diagrama de Gantt</h2>

  <div class="gantt-wrapper">
    <div class="gantt-header">
      {semanas_html}
    </div>
    {filas_gantt}
  </div>

  <div class="gantt-legend">
    <div class="gantt-legend-item">
      <div class="gantt-legend-box" style="background:#2d6a9f"></div>
      Tarea normal
    </div>
    <div class="gantt-legend-item">
      <div class="gantt-legend-box" style="background:#c0392b"></div>
      Tarea crítica (no puede retrasarse)
    </div>
  </div>

  <h2 style="margin-top:20px">Detalle de Tareas</h2>
  <table>
    <thead>
      <tr>
        <th>Tarea</th>
        <th class="num">Días</th>
        <th class="num">Inicio</th>
        <th class="num">Fin</th>
        <th class="num">Holgura</th>
        <th class="num">Crítica</th>
      </tr>
    </thead>
    <tbody>
      {"".join(f'''
      <tr>
        <td>{t["id"]}</td>
        <td class="num">{t["duracion_dias"]}</td>
        <td class="num">{t["inicio_temprano"].strftime("%d/%m/%y")}</td>
        <td class="num">{t["fin_temprano"].strftime("%d/%m/%y")}</td>
        <td class="num">{t["holgura"]} d</td>
        <td class="num" style="color:{"#c0392b" if t["critica"] else "#27ae60"}">
          {"⚠ SÍ" if t["critica"] else "no"}
        </td>
      </tr>''' for t in tareas)}
    </tbody>
  </table>

  <div class="section-footer">
    Cronograma estimativo — Arch Proposal Suite — {date.today().strftime('%d/%m/%Y')}
  </div>
</div>"""


def render_seccion_computo(resultados: list, precios: dict, config: dict) -> str:
    """Genera el HTML del cómputo de materiales (listado de insumos)."""

    # Acumular materiales de todos los resultados
    materiales: dict[str, dict] = {}

    UNIDADES = {
        "cemento_kg": "kg", "arena_m3": "m³", "ripio_m3": "m³",
        "ladrillo_comun_un": "un", "ladrillo_hueco_18_un": "un",
        "bolsa_plasticor": "bolsa", "ceramico_m2": "m²",
        "adhesivo_ceramico_kg": "kg", "yeso_kg": "kg",
        "placa_durlock_m2": "m²", "pintura_latex_lt": "lt",
        "sellador_lt": "lt", "chapa_ml": "ml", "lana_mineral_m2": "m²",
        "acero_12mm_barra": "barra", "madera_p2": "p²",
        "clavos_kg": "kg", "alambre_kg": "kg",
    }

    # Recalcular insumos desde las incidencias usando los resultados del presupuesto
    filas = ""
    total_materiales = 0

    for r in resultados:
        mat = r["subtotales"]["materiales"]
        total_materiales += mat
        filas += f"""
      <tr>
        <td>{r["elemento"]}</td>
        <td class="num">{", ".join(f"{k}: {v}" for k, v in r["metricas"].items())}</td>
        <td class="num">{fmt_ars(mat)}</td>
      </tr>"""

    return f"""
<div class="hoja">
  <div class="page-header">
    <div>
      <div class="ph-titulo">CÓMPUTO DE MATERIALES</div>
      <div class="ph-proyecto">{config.get('proyecto', '')} — {config.get('localidad', '')}</div>
    </div>
    <div class="ph-logo">APS</div>
  </div>

  <div class="nota-aclaratoria">
    Estimación de insumos por ítem. Los precios unitarios corresponden a la
    base de datos de precios <em>{config.get('fuente_precios', 'referencias NOA/Tucumán')}</em>.
  </div>

  <h2>Costo de materiales por rubro</h2>

  <table>
    <thead>
      <tr>
        <th>Rubro</th>
        <th class="num">Magnitud</th>
        <th class="num">Costo Materiales</th>
      </tr>
    </thead>
    <tbody>
      {filas}
      <tr class="total-row">
        <td colspan="2"><strong>TOTAL MATERIALES</strong></td>
        <td class="num"><strong>{fmt_ars(total_materiales)}</strong></td>
      </tr>
    </tbody>
  </table>

  <div class="section-footer">
    Cómputo estimativo — Arch Proposal Suite — {date.today().strftime('%d/%m/%Y')}
  </div>
</div>"""


# ─────────────────────────────────────────────────────────────────────────────
# ENSAMBLADO FINAL DEL HTML
# ─────────────────────────────────────────────────────────────────────────────

def cargar_template() -> str:
    ruta = os.path.normpath(os.path.join(
        BASE_DIR, "..", "templates", "landing", "reporte.html.template"
    ))
    with open(ruta, encoding="utf-8") as f:
        return f.read()


def render_reporte(config: dict, secciones: set) -> str:
    """Ensambla el HTML final según las secciones solicitadas."""

    m2 = config.get("m2", 60)

    # ── Siempre necesitamos el presupuesto como base (para cronograma también) ──
    calc = crear_calculadora(m2, usar_precios_reales=True)
    calcular_rubros_estandar(calc, m2)
    resumen = calc.consolidar()

    # ── Renderizar secciones ──────────────────────────────────────────────────
    html_presupuesto = ""
    html_cronograma  = ""
    html_computo     = ""

    if "presupuesto" in secciones:
        html_presupuesto = render_seccion_presupuesto(resumen["items"], resumen, config)

    if "cronograma" in secciones:
        gen = GeneradorCronograma(
            resultados=calc.resultados,
            personal_oficial=config.get("personal_oficial", 2),
            personal_ayudante=config.get("personal_ayudante", 2),
            fecha_inicio=config.get("fecha_inicio"),
            jornada_hs=config.get("jornada", 8),
        )
        gen.calcular()
        tareas_con_dates = gen.tareas
        meta_crono = {
            "duracion_total_dias": gen.duracion_total(),
            "camino_critico": [t["id"] for t in gen.tareas if t["critica"]],
        }
        html_cronograma = render_seccion_cronograma(tareas_con_dates, meta_crono, config)

        # Exportar también el JSON/CSV del cronograma
        gen.exportar()

    if "computo" in secciones:
        html_computo = render_seccion_computo(resumen["items"], calc.precios, config)

    # ── Carátula extra meta ───────────────────────────────────────────────────
    caratula_extra = ""
    if "cronograma" in secciones:
        caratula_extra += f"""
        <div class="meta-item">
          <span class="label">Inicio programado de obra</span>
          <span class="valor">{config.get('fecha_inicio', 'A confirmar')}</span>
        </div>"""

    if "presupuesto" in secciones:
        costo_m2 = resumen["COSTO_DIRECTO_TOTAL"] / m2
        caratula_extra += f"""
        <div class="meta-item">
          <span class="label">Costo directo estimado</span>
          <span class="valor">{fmt_ars(resumen['COSTO_DIRECTO_TOTAL'])}</span>
        </div>
        <div class="meta-item">
          <span class="label">Costo por m²</span>
          <span class="valor">{fmt_ars(costo_m2)} / m²</span>
        </div>"""

    tipo_doc_parts = []
    if "presupuesto" in secciones: tipo_doc_parts.append("Presupuesto")
    if "cronograma"  in secciones: tipo_doc_parts.append("Cronograma")
    if "computo"     in secciones: tipo_doc_parts.append("Cómputo de Materiales")
    tipo_doc = " + ".join(tipo_doc_parts)

    # ── Sustituir placeholders en la plantilla ────────────────────────────────
    template = cargar_template()

    sustituciones = {
        "{{TITULO_REPORTE}}":        f"{tipo_doc} — {config.get('proyecto', 'Proyecto')}",
        "{{ESTUDIO_NOMBRE}}":        config.get("estudio", "Estudio de Arquitectura"),
        "{{ESTUDIO_SUBTITULO}}":     config.get("estudio_sub", "Arquitectura + Construcción"),
        "{{TIPO_DOCUMENTO}}":        tipo_doc,
        "{{PROYECTO_NOMBRE}}":       config.get("proyecto", "Nombre del Proyecto"),
        "{{PROYECTO_UBICACION}}":    config.get("localidad", ""),
        "{{COMITENTE}}":             config.get("comitente", "—"),
        "{{SUPERFICIE}}":            str(m2),
        "{{FECHA_EMISION}}":         date.today().strftime("%d de %B de %Y"),
        "{{REF_EXPEDIENTE}}":        config.get("expediente") or f"APS-{datetime.now().strftime('%Y%m%d')}",
        "{{CARATULA_EXTRA_META}}":   caratula_extra,
        "{{SECCION_PRESUPUESTO}}":   html_presupuesto,
        "{{SECCION_CRONOGRAMA}}":    html_cronograma,
        "{{SECCION_COMPUTO}}":       html_computo,
    }

    # Asegurar que ningún valor sea None (causaría error en replace())
    sustituciones = {k: (v if v is not None else "") for k, v in sustituciones.items()}


    for placeholder, valor in sustituciones.items():
        template = template.replace(placeholder, valor)

    return template


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="Genera un reporte HTML A4 para el Arch Proposal Suite."
    )

    # Secciones
    p.add_argument("--seccion", default="presupuesto",
                   help="Secciones a incluir: presupuesto,cronograma,computo (separadas por coma)")
    p.add_argument("--completo", action="store_true",
                   help="Genera todas las secciones")

    # Datos del proyecto
    p.add_argument("--proyecto",  default="Proyecto",  help="Nombre del proyecto")
    p.add_argument("--localidad", default="Tucumán, Argentina", help="Localidad de la obra")
    p.add_argument("--comitente", default="—",         help="Nombre del propietario/comitente")
    p.add_argument("--m2",        type=float, default=60, help="Superficie total en m²")
    p.add_argument("--estudio",   default="Estudio de Arquitectura", help="Nombre del estudio profesional")
    p.add_argument("--estudio-sub", default="Arquitectura + Construcción")
    p.add_argument("--expediente", default=None, help="Referencia de expediente")
    p.add_argument("--fuente-precios", default="Lista NOA — Metaltec")

    # Cronograma
    p.add_argument("--fecha-inicio", default=None, help="YYYY-MM-DD")
    p.add_argument("--personal-oficial",  type=int, default=2)
    p.add_argument("--personal-ayudante", type=int, default=2)
    p.add_argument("--jornada", type=float, default=8.0)

    # Salida
    p.add_argument("--salida", default=None, help="Ruta del HTML de salida")

    args = p.parse_args()

    # Determinar secciones
    if args.completo:
        secciones = {"presupuesto", "cronograma", "computo"}
    else:
        secciones = {s.strip().lower() for s in args.seccion.split(",")}

    config = {
        "m2":               args.m2,
        "proyecto":         args.proyecto,
        "localidad":        args.localidad,
        "comitente":        args.comitente,
        "estudio":          args.estudio,
        "estudio_sub":      args.estudio_sub,
        "expediente":       args.expediente,
        "fuente_precios":   args.fuente_precios,
        "fecha_inicio":     args.fecha_inicio,
        "personal_oficial": args.personal_oficial,
        "personal_ayudante":args.personal_ayudante,
        "jornada":          args.jornada,
    }

    print(f"[ReporteHTM] Generando secciones: {', '.join(secciones)}")
    html = render_reporte(config, secciones)

    # Guardar
    outputs_dir = os.path.normpath(os.path.join(BASE_DIR, "..", "outputs"))
    os.makedirs(outputs_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    nombre_archivo = args.salida or os.path.join(
        outputs_dir, f"reporte_{timestamp}.html"
    )

    with open(nombre_archivo, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[ReporteHTML] ✓ Reporte generado → {nombre_archivo}")
    print(f"  → Abrí el archivo en tu navegador y usá Ctrl+P para imprimir en A4 / guardar como PDF.")

    return nombre_archivo


if __name__ == "__main__":
    main()
