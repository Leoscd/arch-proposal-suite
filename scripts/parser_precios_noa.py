"""
parser_precios_noa.py
─────────────────────────────────────────────────────────────────────────────
Convierte el archivo preciosNOA.csv (formato Arq. & Const. / Metaltec)
al formato plano que espera calculate_budget.py:
    material,precio_ars
    cemento_kg,380
    ...

El script genera el archivo references/precios_materiales.csv listo para usar.
Uso:
    python parser_precios_noa.py
    python parser_precios_noa.py --origen ruta/precios.csv --destino ruta/salida.csv
"""

import csv
import os
import argparse
import re

# ─────────────────────────────────────────────────────────────────────────────
# TABLA DE MAPEO: Descripción NOA → Clave interna de la calculadora
#
# Estructura: "fragmento a buscar en Descripción (lowercase)" → {
#     "clave": "clave_interna",
#     "divisor": (opcional) divisor para normalizar la unidad base
#     "descripcion": "descripción amigable del mapeo"
# }
# ─────────────────────────────────────────────────────────────────────────────
MAPEOS = [
    # ACERO (barras por unidad de 12m) ↓
    {"buscar": r"torsion.*\b6\s*mm",            "excluir": "tns",  "clave": "acero_6mm_barra",   "div": 1},
    {"buscar": r"torsion.*\b8\s*mm",            "excluir": "tns",  "clave": "acero_8mm_barra",   "div": 1},
    {"buscar": r"torsion.*\b10\s*mm",           "excluir": "tns",  "clave": "acero_10mm_barra",  "div": 1},
    {"buscar": r"torsion.*\b12\s*mm",           "excluir": "tns",  "clave": "acero_12mm_barra",  "div": 1},
    {"buscar": r"torsion.*\b16\s*mm",           "excluir": "tns",  "clave": "acero_16mm_barra",  "div": 1},
    {"buscar": r"torsion.*\b20\s*mm",           "excluir": "tns",  "clave": "acero_20mm_barra",  "div": 1},

    # CEMENTO → precio por bolsa de 50kg → ÷ 50 = por kg
    {"buscar": r"loma negra.*50\s*kg",          "excluir": None,   "clave": "cemento_kg",        "div": 50, "nota": "Loma Negra 50kg"},
    {"buscar": r"holcim.*50\s*kg",              "excluir": None,   "clave": "cemento_kg_holcim", "div": 50},

    # ÁRIDOS
    {"buscar": r"arena mediana.*m3",            "excluir": None,   "clave": "arena_m3",          "div": 1},
    {"buscar": r"arena fina.*m3",               "excluir": None,   "clave": "arena_fina_m3",     "div": 1},
    {"buscar": r"ripio 1:3.*m3",                "excluir": None,   "clave": "ripio_m3",          "div": 1},
    {"buscar": r"ripio bruto.*m3",              "excluir": None,   "clave": "ripio_bruto_m3",    "div": 1},

    # ALAMBRE → precio por kg
    {"buscar": r"recocido 16.*50\s*kg",         "excluir": None,   "clave": "alambre_kg",        "div": 50, "nota": "ARS/kg (÷50)"},
    {"buscar": r"galvanizado 1,?63\s*mm",       "excluir": None,   "clave": "alambre_galv_kg",   "div": 1},

    # CLAVOS → precio por kg
    {"buscar": r"punta paris.*30\s*kg",         "excluir": None,   "clave": "clavos_kg",         "div": 30, "nota": "ARS/kg (÷30)"},

    # LADRILLOS
    {"buscar": r"ladrillo com[uú]n.*mil",       "excluir": None,   "clave": "ladrillo_comun_un", "div": 1000, "nota": "ARS/un (÷1000)"},
    {"buscar": r"ladrillo hueco.*18.*18|para tabique.*18.*18", "excluir": None, "clave": "ladrillo_hueco_18_un", "div": 1},

    # REVOQUES Y MORTEROS (bolsa 25-30 kg ≈ bolsa Plasticor)
    {"buscar": r"parex duo.*25\s*kg",           "excluir": None, "clave": "bolsa_plasticor", "div": 1, "nota": "Parex Duo 25kg como proxy Plasticor"},
    {"buscar": r"stuko fino.*interior.*25\s*kg", "excluir": None, "clave": "stuko_interior_bolsa25", "div": 1},
    {"buscar": r"stuko fino.*exterior.*25\s*kg", "excluir": None, "clave": "stuko_exterior_bolsa25", "div": 1},

    # HORMIGÓN ELABORADO
    {"buscar": r"h\s*17.*m3",                   "excluir": None,   "clave": "hormigon_h17_m3",   "div": 1},
    {"buscar": r"h\s*30.*m3",                   "excluir": None,   "clave": "hormigon_h30_m3",   "div": 1},

    # DURLOCK / CONSTRUCCIÓN EN SECO
    {"buscar": r"placa (durlock|yeso).*12,?5\s*mm", "excluir": "verde", "clave": "placa_durlock_m2", "div": 2.88, "nota": "÷ 2.88m2 por placa"},
    {"buscar": r"placa (durlock|yeso).*9,?5\s*mm",  "excluir": None,    "clave": "placa_durlock_95_m2", "div": 2.88},

    # PINTURAS (Látex interior por litro)
    {"buscar": r"l[aá]tex.*interior.*20\s*l",   "excluir": None, "clave": "pintura_latex_lt",  "div": 20, "nota": "ARS/lt (÷20)"},
    {"buscar": r"l[aá]tex.*exterior.*20\s*l",   "excluir": None, "clave": "pintura_latex_ext_lt", "div": 20},
    {"buscar": r"fijador.*20\s*l",              "excluir": None, "clave": "sellador_lt",       "div": 20},

    # CHAPAS
    {"buscar": r"chapa trap.*c.?\s*25",         "excluir": None,   "clave": "chapa_ml",          "div": 1},
    {"buscar": r"chapa acan.*c.?\s*25",         "excluir": None,   "clave": "chapa_acan_ml",     "div": 1},

    # HIDROFUGO
    {"buscar": r"hidrofugo.*4",                 "excluir": None,  "clave": "hidrofugo_lt",      "div": 4, "nota": "ARS/lt (÷4) Asume balde de 4kg/lt"},

    # CERÁMICOS Y PISOS
    {"buscar": r"cer[aá]micos.*m2",             "excluir": None, "clave": "ceramico_m2",         "div": 1},
    {"buscar": r"porc[e|a]ll?anato.*m2",        "excluir": None, "clave": "porcelanato_m2",      "div": 1},

    # ADHESIVO Y PASTINA
    {"buscar": r"pegamento.*30\s*kg",           "excluir": None, "clave": "adhesivo_ceramico_kg", "div": 30, "nota": "ARS/kg (÷30)"},
    {"buscar": r"pastina.*blanca",              "excluir": None, "clave": "pastina_kg",           "div": 1},

    # VIDRIOS
    {"buscar": r"(cristal|critsal|vidrio).*4\s*mm",     "excluir": None, "clave": "vidrio_4mm_m2",        "div": 1},
    {"buscar": r"(cristal|critsal|vidrio).*6\s*mm",     "excluir": None, "clave": "vidrio_6mm_m2",        "div": 1},

    # YESO
    {"buscar": r"yeso.*40\s*kg",                "excluir": None, "clave": "yeso_kg",              "div": 40, "nota": "ARS/kg (÷40)"},

    # AISLANTES
    {"buscar": r"isolant.*10\s*mm",             "excluir": None, "clave": "lana_mineral_m2",      "div": 20, "nota": "Proxy lana mineral ARS/m2 (÷20)"},

    # MALLAS SIMA
    {"buscar": r"malla r\s*131",                "excluir": None, "clave": "malla_r131_un",        "div": 1},
    {"buscar": r"malla q\s*131",                "excluir": None, "clave": "malla_q131_un",        "div": 1},

    # MEMBRANA
    {"buscar": r"membrana.*10\s*m2",            "excluir": None, "clave": "membrana_m2",          "div": 10, "nota": "ARS/m2 (÷10)"},
    {"buscar": r"pintura asf[aá]ltica",         "excluir": None, "clave": "pintura_asfaltica_lt", "div": 18},

    # CARPINTERÍA (Aberturas)
    {"buscar": r"puerta.*0,?90\s*x\s*2,?05",    "excluir": None, "clave": "puerta_alum_90x205_un",  "div": 1},
    {"buscar": r"ventana.*0,?90\s*x\s*1,?20",   "excluir": None, "clave": "ventana_alum_90x120_un", "div": 1},

    # VIGUETAS PRETENSADAS
    {"buscar": r"vigueta.*4,?00",               "excluir": None, "clave": "vigueta_4m_un",  "div": 1},
    {"buscar": r"vigueta.*4,?80",               "excluir": None, "clave": "vigueta_48m_un", "div": 1},
    {"buscar": r"vigueta.*5,?00",               "excluir": None, "clave": "vigueta_5m_un",  "div": 1},

    # BLOQUES
    {"buscar": r"bloque.*13\s*x",               "excluir": None, "clave": "bloque_13_un", "div": 1},
    {"buscar": r"bloque.*19\s*x",               "excluir": None, "clave": "bloque_19_un", "div": 1},
    {"buscar": r"bovedilla.*10\s*x",            "excluir": None, "clave": "bovedilla_10_un", "div": 1},
    {"buscar": r"bovedilla.*12\s*x",            "excluir": None, "clave": "bovedilla_12_un", "div": 1},

    # TEJAS
    {"buscar": r"teja colonial",                "excluir": None, "clave": "teja_colonial_un",  "div": 1},
    {"buscar": r"teja francesa",                "excluir": None, "clave": "teja_francesa_un",  "div": 1},
]


def limpiar_precio(raw):
    """Convierte '32.524,05' → 32524.05"""
    return float(raw.strip().replace(".", "").replace(",", "."))


def parsear_csv_noa(ruta_origen, ruta_destino):
    encontrados = {}
    no_encontrados = []

    # Detect delimiter
    with open(ruta_origen, "r", encoding="utf-8-sig") as f:
        first_line = f.readline()
        delimiter = ";" if ";" in first_line else ","

    with open(ruta_origen, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=delimiter)
        filas = list(reader)

    print(f"[Parser NOA] {len(filas)} filas leídas de {os.path.basename(ruta_origen)}")

    for fila in filas:
        if len(fila) < 3:
            continue
            
        # Compatibilidad: si tiene 5 o más columnas asume formato viejo (descripción en col 4, precio en col 5)
        # Si tiene 3 columnas asume formato nuevo ("Categoría", "Descripción", "Precio")
        if len(fila) >= 5:
            descripcion = fila[3].lower().strip()
            precio_raw = fila[4].strip()
            desc_original = fila[3]
        else:
            descripcion = fila[1].lower().strip()
            precio_raw = fila[2].strip()
            desc_original = fila[1]

        if not precio_raw or precio_raw == "0,00" or precio_raw.lower() == "precio":
            continue

        for mapeo in MAPEOS:
            patron_buscar = str(mapeo["buscar"])
            excluir = str(mapeo.get("excluir") or "")

            if re.search(patron_buscar, descripcion, re.IGNORECASE):
                if excluir and re.search(excluir, descripcion, re.IGNORECASE):
                    continue  # Tiene palabra excluída → saltear
                clave = mapeo["clave"]
                divisor = mapeo.get("div", 1)
                nota = mapeo.get("nota", "")
                try:
                    precio_unitario = limpiar_precio(precio_raw) / divisor
                    if clave not in encontrados:  # Solo el primer match
                        encontrados[clave] = {"precio": precio_unitario, "descripcion": desc_original, "nota": nota}
                except ValueError:
                    pass

    # Detectar claves no encontradas
    claves_buscadas = {m["clave"] for m in MAPEOS}
    no_encontrados = sorted(claves_buscadas - set(encontrados.keys()))

    # Escribir CSV de salida
    with open(ruta_destino, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["material", "precio_ars", "fuente", "nota"])
        for clave, datos in sorted(encontrados.items()):
            writer.writerow([
                clave,
                round(datos["precio"], 2),
                datos["descripcion"][:80],
                datos["nota"]
            ])

    print(f"\n[Parser NOA] ✓ {len(encontrados)} precios mapeados → {os.path.basename(ruta_destino)}")
    if no_encontrados:
        print(f"[Parser NOA] ⚠ {len(no_encontrados)} claves SIN precio en el CSV:")
        for c in no_encontrados:
            print(f"   - {c}")

    return encontrados, no_encontrados


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parsea preciosNOA.csv al formato de la calculadora")
    parser.add_argument("--origen",  default=None, help="Ruta al preciosNOA.csv")
    parser.add_argument("--destino", default=None, help="Ruta de salida precios_materiales.csv")
    args = parser.parse_args()

    base = os.path.dirname(os.path.abspath(__file__))
    refs = os.path.join(base, "..", "references")

    ruta_in  = args.origen  or os.path.normpath(os.path.join(
        base, "..", "..", "referencias", "presupuesto-constructor", "references", "preciosNOA.csv"
    ))
    ruta_out = args.destino or os.path.normpath(os.path.join(refs, "precios_materiales.csv"))

    if not os.path.exists(ruta_in):
        print(f"[Error] No se encontró el archivo de origen: {ruta_in}")
        exit(1)

    parsear_csv_noa(ruta_in, ruta_out)
    print(f"\n→ Ahora ejecuta calculate_budget.py para usar los precios reales.")
