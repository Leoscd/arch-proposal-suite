import json
import os
import math
import csv

# ─────────────────────────────────────────────────────────────────────────────
# TABLA DE PESOS DE HIERRO (kg/ml) - CIRSOC
# ─────────────────────────────────────────────────────────────────────────────
PESO_HIERRO_KG_ML = {
    6: 0.222, 8: 0.395, 10: 0.617, 12: 0.888,
    16: 1.578, 20: 2.466, 25: 3.853
}


class CalculadoraPresupuesto:
    def __init__(self, ruta_rubros, ruta_precios):
        """
        Inicializa la calculadora cargando la base de rubros y la lista de precios.
        Acepta una ruta a un JSON de configuración personalizada para sobrescribir
        incidencias (ej. correcciones ingresadas por el usuario en vivo).
        """
        self.rubros = self._cargar_json(ruta_rubros)
        self.precios = self._cargar_precios(ruta_precios)
        self.resultados = []  # Acumula todos los ítems calculados

        # ─── INCIDENCIAS BASE ─────────────────────────────────────────────
        # Fuente: cuadernillo presupuesto-constructor + CIRSOC + Plasticor
        # Pueden sobreescribirse en tiempo de ejecución vía config_personalizada.json
        self.incidencias = {
            # --- ESTRUCTURAS ---
            "HORMIGON_H21_M3": {
                "cemento_kg": 320 * 1.05, "arena_m3": 0.52 * 1.08,
                "ripio_m3": 0.72 * 1.08, "agua_lt": 190,
                "mo_oficial_hs": 0.8, "mo_ayudante_hs": 4.0
            },
            "ACERO_TORSIONADO": {
                "largo_barra_m": 12.0,      # barras comerciales 12m
                "largo_estribo_m": 6.0,     # estribos comerciales 6m
                "desperdicio": 1.08,
                "mo_oficial_hs_kg": 0.05,   # hs/kg
                "mo_ayudante_hs_kg": 0.05
            },
            "ENCOFRADO_MADERA_M2": {
                "tablas_p2": 4.0, "clavos_kg": 0.15, "alambre_kg": 0.10,
                "mo_oficial_hs": 0.9, "mo_ayudante_hs": 0.9
            },
            # --- CIMIENTOS ---
            "EXCAVACION_M3": {
                "mo_oficial_hs": 0.8, "mo_ayudante_hs": 4.0
            },
            "CIMIENTO_CORRIDO_M3": {     # Piedra + Hormigón pobre H-13
                "cemento_kg": 200 * 1.05, "arena_m3": 0.6 * 1.08,
                "piedra_bola_m3": 0.5 * 1.05,
                "mo_oficial_hs": 1.2, "mo_ayudante_hs": 5.0
            },
            # --- CERRAMIENTOS ---
            "LADRILLO_COMUN_15_M2": {
                "ladrillos_un": 60 * 1.07,          # 60u/m2 + 7% desperdicio
                "bolsas_plasticor": (1 / 3.5) * 1.12,  # 3.5 m2/bolsa + 12%
                "mo_oficial_hs": 0.7, "mo_ayudante_hs": 1.4
            },
            "LADRILLO_HUECO_18_M2": {
                "ladrillos_un": 15 * 1.07,
                "bolsas_plasticor": (1 / 9) * 1.12,    # 9 m2/bolsa junta 1.5cm
                "mo_oficial_hs": 0.5, "mo_ayudante_hs": 1.0
            },
            "STEEL_FRAME_M2": {
                "perfil_pgc_ml": 3.5,           # ml de perfiles C/U por m2
                "placa_roca_yeso_m2": 2.0,      # dos caras
                "aislacion_lana_m2": 1.05,
                "mo_oficial_hs": 0.8, "mo_ayudante_hs": 0.8
            },
            # --- AISLACIONES ---
            "CAPA_AISLADORA_HORIZONTAL_ML": {
                "pintura_asfaltica_kg": 0.3,
                "hidrofugo_lt": 0.15,
                "mo_oficial_hs": 0.15, "mo_ayudante_hs": 0.15
            },
            # --- REVOQUES ---
            "REVOQUE_GRUESO_M2": {
                # espesor 1.5 cm: 4 bolsas Plasticor/m2 | 2.0 cm: 3 bolsas/m2
                "bolsas_plasticor": (1 / 4) * 1.12,    # 1.5 cm por defecto
                "mo_oficial_hs": 0.35, "mo_ayudante_hs": 0.35
            },
            "REVOQUE_FINO_M2": {
                "bolsas_plasticor": (1 / 10) * 1.12,   # 10 m2/bolsa sobre grueso nivelado
                "mo_oficial_hs": 0.25, "mo_ayudante_hs": 0.25
            },
            "AZOTADO_HIDROFUGO_M2": {
                "cemento_kg": 5 * 1.05,
                "hidrofugo_lt": 0.15,
                "mo_oficial_hs": 0.1, "mo_ayudante_hs": 0.1
            },
            # --- CONTRAPISOS ---
            "CONTRAPISO_M3": {  # H° pobre 1:3:3 → 250 kg cem/m3
                "cemento_kg": 250 * 1.05, "arena_m3": 0.45 * 1.08,
                "ripio_m3": 0.65 * 1.08,
                "mo_oficial_hs": 0.6, "mo_ayudante_hs": 2.5
            },
            "CARPETA_NIVELADORA_M2": {
                "bolsas_plasticor": (1 / 5) * 1.12,    # ~5 m2/bolsa-3cm
                "mo_oficial_hs": 0.2, "mo_ayudante_hs": 0.2
            },
            # --- PISOS Y REVESTIMIENTOS ---
            "PISOS_CERAMICOS_M2": {
                "ceramico_m2": 1.0 * 1.12,             # 12% desperdicio corte recto
                "adhesivo_kg": 5.0,                     # ~5 kg/m2
                "pastina_kg": 0.4,
                "mo_oficial_hs": 0.5, "mo_ayudante_hs": 0.5
            },
            "PISOS_CERAMICOS_DIAGONAL_M2": {
                "ceramico_m2": 1.0 * 1.18,             # 18% desperdicio diagonal
                "adhesivo_kg": 5.0, "pastina_kg": 0.4,
                "mo_oficial_hs": 0.7, "mo_ayudante_hs": 0.7
            },
            "ZOCALOS_ML": {
                "zocalo_ml": 1.0 * 1.05,
                "adhesivo_kg": 0.5,
                "mo_oficial_hs": 0.15, "mo_ayudante_hs": 0.10
            },
            # --- CIELORRASOS ---
            "CIELORRASO_APLICADO_M2": {
                "yeso_kg": 4.5,
                "mo_oficial_hs": 0.4, "mo_ayudante_hs": 0.4
            },
            "CIELORRASO_SUSPENDIDO_M2": {
                "placa_durlock_m2": 1.0 * 1.10,
                "perfil_ml": 3.5,
                "tornillos_un": 30,
                "mo_oficial_hs": 0.5, "mo_ayudante_hs": 0.5
            },
            # --- CUBIERTAS ---
            "CUBIERTA_CHAPA_M2": {
                "chapa_m2": 1.0 * 1.10,
                "aislacion_lana_m2": 1.0 * 1.05,
                "mo_oficial_hs": 0.4, "mo_ayudante_hs": 0.4
            },
            "CUBIERTA_MEMBRANA_M2": {
                "membrana_m2": 1.0 * 1.10,
                "imprimacion_lt": 0.2,
                "mo_oficial_hs": 0.3, "mo_ayudante_hs": 0.3
            },
            # --- PINTURAS ---
            "PINTURA_LATEX_INTERIOR_M2": {
                # 2 manos: ~12 m2/lt por mano = 6 m2/lt neto + 5% desperdicio
                "latex_lt": (2 / 12) * 1.05,
                "sellador_lt": (1 / 15) * 1.05,
                "mo_oficial_hs": 0.15, "mo_ayudante_hs": 0.10
            },
            "PINTURA_EXTERIOR_M2": {
                "texturado_lt": (1 / 4) * 1.05,        # ~4 m2/lt texturado grueso
                "mo_oficial_hs": 0.20, "mo_ayudante_hs": 0.15
            },
            # --- INSTALACIONES ---
            "INSTALACION_ELECTRICA_BOCA": {
                "cano_10mm_ml": 3.0, "cable_m": 8.0, "cajas_un": 1.0,
                "mo_oficial_hs": 1.0, "mo_ayudante_hs": 0.5
            },
            "INSTALACION_SANITARIA_BOCA": {
                "cano_75mm_ml": 3.0, "codos_un": 2.0,
                "mo_oficial_hs": 1.5, "mo_ayudante_hs": 1.0
            }
        }

    # ─── HELPERS ─────────────────────────────────────────────────────────────

    def _cargar_json(self, ruta):
        if not ruta or not os.path.exists(ruta):
            return []
        with open(ruta, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _cargar_precios(self, ruta_csv_usuario=None):
        """
        Carga precios en ARS desde el CSV del usuario (merge con defaults).

        Formato mínimo del CSV (dos columnas):
            material,precio_ars
            cemento_kg,380
            acero_12mm_barra,21000

        El archivo puede llamarse:
            references/precios_materiales.csv  ← nombre recomendado
            references/precios.csv

        Los materiales NOT presentes en el CSV usan el valor de referencia.
        """
        # ── Valores de referencia (NOA / Tucumán - Marzo 2025) ─────────────
        defaults = {
            "cemento_kg": 250.0,        "arena_m3": 25000.0,
            "ripio_m3": 28000.0,        "piedra_bola_m3": 22000.0,
            "agua_lt": 10.0,
            "acero_6mm_barra": 4500.0,  "acero_8mm_barra": 7500.0,
            "acero_10mm_barra": 11000.0,"acero_12mm_barra": 18000.0,
            "acero_16mm_barra": 32000.0,
            "madera_p2": 1500.0,        "clavos_kg": 2000.0,
            "alambre_kg": 1800.0,
            "ladrillo_comun_un": 90.0,  "ladrillo_hueco_18_un": 120.0,
            "bolsa_plasticor": 1800.0,
            "ceramico_m2": 5500.0,      "adhesivo_ceramico_kg": 400.0,
            "pastina_kg": 350.0,
            "yeso_kg": 350.0,           "placa_durlock_m2": 3200.0,
            "perfil_durlock_ml": 800.0, "tornillo_un": 15.0,
            "pintura_latex_lt": 2500.0, "sellador_lt": 1800.0,
            "texturado_lt": 3500.0,     "membrana_m2": 4500.0,
            "imprimacion_lt": 2000.0,   "chapa_m2": 3800.0,
            "lana_mineral_m2": 2200.0,
            "cano_electrico_10_ml": 250.0, "cable_ml": 280.0,
            "caja_electrica_un": 600.0,
            "cano_sanitario_75_ml": 1800.0, "codo_sanitario_un": 950.0,
            "pintura_asfaltica_kg": 1200.0, "hidrofugo_lt": 900.0,
            "perfil_pgc_ml": 3500.0,    "zocalo_ml": 1200.0,
            "hora_oficial": 4500.0,     "hora_ayudante": 3500.0,
            "puntal_alquiler_dia": 500.0, "mezcladora_dia": 3000.0,
        }

        # ── Rutas candidatas donde buscar el CSV (de mayor a menor prioridad) ─
        base_dir = os.path.dirname(os.path.abspath(__file__))
        refs_dir = os.path.join(base_dir, "..", "references")
        candidatos = [
            ruta_csv_usuario,
            os.path.join(refs_dir, "precios_materiales.csv"),
            os.path.join(refs_dir, "precios.csv"),
            os.path.join(refs_dir, "lista_precios.csv"),
        ]

        for ruta in filter(None, candidatos):
            ruta = os.path.normpath(ruta)
            if not os.path.exists(ruta):
                continue
            try:
                cargados: int = 0
                with open(ruta, newline='', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    fieldnames = reader.fieldnames or []
                    cols = [c.lower().strip() for c in fieldnames]

                    # Detectar nombres de columna flexibles
                    col_mat  = next((fieldnames[i] for i, c in enumerate(cols)
                                     if c in {"material","item","nombre","clave","descripcion"}), None)
                    col_prec = next((fieldnames[i] for i, c in enumerate(cols)
                                     if c in {"precio_ars","precio","valor","importe","monto"}), None)

                    if not col_mat or not col_prec:
                        print(f"[Precios] Columnas no reconocidas en {ruta}. "
                              f"Usa encabezados: material, precio_ars")
                        continue

                    for row in reader:
                        clave = row[col_mat].strip().lower().replace(" ", "_")
                        raw   = str(row[col_prec]).strip().replace(",", ".").replace(" ", "")
                        try:
                            defaults[clave] = float(raw)
                            cargados += 1  # type: ignore[operator]
                        except ValueError:
                            pass  # Fila sin precio numérico → ignora

                print(f"[Precios] ✓ {cargados} precios cargados desde: {os.path.basename(ruta)}")
                return defaults

            except Exception as e:
                print(f"[Precios] Error leyendo {ruta}: {e}")

        # Si ningún CSV se encontró
        print("[Precios] AVISO: No se encontró lista de precios CSV.")
        print("  → Agrega tu tabla en: references/precios_materiales.csv")
        print("  → Usando valores de referencia NOA/Tucumán.")
        return defaults

    def _calcular_costo_mo(self, hs_oficial, hs_ayudante,
                           incluir_cargas=True, pct_cargas=1.2521):
        costo_base = (hs_oficial * self.precios["hora_oficial"]) + \
                     (hs_ayudante * self.precios["hora_ayudante"])
        return costo_base * (1 + pct_cargas) if incluir_cargas else costo_base

    def _resultado(self, elemento, metricas, mat, mo, equip):
        r = {
            "elemento": elemento,
            "metricas": metricas,
            "subtotales": {
                "materiales": round(mat, 2),
                "mano_obra": round(mo, 2),
                "equipos": round(equip, 2),
                "total": round(mat + mo + equip, 2)
            }
        }
        self.resultados.append(r)
        return r

    # ─── CONVERSIÓN DE ACERO ─────────────────────────────────────────────────

    def barras_a_kg(self, diametro_mm, metros_lineales):
        """Convierte ml de acero a KG usando la tabla CIRSOC."""
        kg_ml = PESO_HIERRO_KG_ML.get(diametro_mm, 0.888)
        return metros_lineales * kg_ml

    def kg_a_barras(self, diametro_mm, kg_total):
        """Calcula cantidad de barras comerciales de 12m a comprar."""
        kg_ml = PESO_HIERRO_KG_ML.get(diametro_mm, 0.888)
        kg_barra = kg_ml * PESO_HIERRO_KG_ML.get(int(diametro_mm), 12) * 12
        # Usamos peso real: kg_barra = peso_por_ml * 12 metros
        kg_barra = PESO_HIERRO_KG_ML.get(diametro_mm, 0.888) * 12
        barras = math.ceil((kg_total * 1.08) / kg_barra)  # 1.08 desperdicio
        llave = f"acero_{diametro_mm}mm_barra"
        precio_barra = self.precios.get(llave, self.precios["acero_12mm_barra"])
        return {"barras_12m": barras, "kg_total": round(kg_total * 1.08, 2),
                "costo_material": round(barras * precio_barra, 2)}

    # ─── MÓDULO 01: TRABAJOS PREPARATORIOS ───────────────────────────────────

    def calc_replanteo(self, m2, incluir_cargas=True, pct_cargas=1.2521):
        mo = self._calcular_costo_mo(0.04 * m2, 0.08 * m2, incluir_cargas, pct_cargas)
        return self._resultado("Nivelación y Replanteo", {"m2": m2}, 0, mo, 0)

    # ─── MÓDULO 02: CIMIENTOS ─────────────────────────────────────────────────

    def calc_excavacion(self, m3, mecanica=False, incluir_cargas=True, pct_cargas=1.2521):
        inc = self.incidencias["EXCAVACION_M3"]
        if mecanica:
            equip = m3 * 15000  # $/m3 alquiler excavadora estimado
            mo = self._calcular_costo_mo(0.1 * m3, 0.3 * m3, incluir_cargas, pct_cargas)
        else:
            equip = 0
            mo = self._calcular_costo_mo(inc["mo_oficial_hs"] * m3, inc["mo_ayudante_hs"] * m3, incluir_cargas, pct_cargas)
        return self._resultado("Excavación", {"m3": m3, "mecanica": mecanica}, 0, mo, equip)

    def calc_cimiento_corrido(self, m3, incluir_cargas=True, pct_cargas=1.2521):
        inc = self.incidencias["CIMIENTO_CORRIDO_M3"]
        mat = (inc["cemento_kg"] * m3 * self.precios["cemento_kg"] +
               inc["arena_m3"] * m3 * self.precios["arena_m3"] +
               inc["piedra_bola_m3"] * m3 * self.precios["piedra_bola_m3"])
        mo = self._calcular_costo_mo(inc["mo_oficial_hs"] * m3, inc["mo_ayudante_hs"] * m3, incluir_cargas, pct_cargas)
        return self._resultado("Cimiento Corrido (Ciclópeo)", {"m3": m3}, mat, mo, 0)

    # ─── MÓDULO 03: ESTRUCTURAS ───────────────────────────────────────────────

    def calc_elemento_ha(self, tipo_elemento, volumen_m3, kg_acero=0,
                         m2_encofrado=0, puntales=0,
                         incluir_cargas=True, pct_cargas=1.2521):
        """Columnas, Vigas, Losas, Encadenados"""
        inc_h = self.incidencias["HORMIGON_H21_M3"]
        inc_e = self.incidencias["ENCOFRADO_MADERA_M2"]
        inc_a = self.incidencias["ACERO_TORSIONADO"]

        # Hormigón
        mat_h = (inc_h["cemento_kg"] * volumen_m3 * self.precios["cemento_kg"] +
                 inc_h["arena_m3"] * volumen_m3 * self.precios["arena_m3"] +
                 inc_h["ripio_m3"] * volumen_m3 * self.precios["ripio_m3"])
        mo_h = self._calcular_costo_mo(inc_h["mo_oficial_hs"] * volumen_m3,
                                       inc_h["mo_ayudante_hs"] * volumen_m3,
                                       incluir_cargas, pct_cargas)
        # Acero
        barras = math.ceil((kg_acero * inc_a["desperdicio"]) /
                           (PESO_HIERRO_KG_ML[12] * 12))
        mat_a = barras * self.precios["acero_12mm_barra"]
        mo_a = self._calcular_costo_mo(inc_a["mo_oficial_hs_kg"] * kg_acero,
                                       inc_a["mo_ayudante_hs_kg"] * kg_acero,
                                       incluir_cargas, pct_cargas)
        # Encofrado
        mat_e = (inc_e["tablas_p2"] * m2_encofrado * self.precios["madera_p2"] +
                 inc_e["clavos_kg"] * m2_encofrado * self.precios["clavos_kg"] +
                 inc_e["alambre_kg"] * m2_encofrado * self.precios["alambre_kg"])
        mo_e = self._calcular_costo_mo(inc_e["mo_oficial_hs"] * m2_encofrado,
                                       inc_e["mo_ayudante_hs"] * m2_encofrado,
                                       incluir_cargas, pct_cargas)
        # Puntales
        equip = puntales * self.precios["puntal_alquiler_dia"] * 15

        mat = mat_h + mat_a + mat_e
        mo = mo_h + mo_a + mo_e
        return self._resultado(tipo_elemento,
                               {"volumen_m3": volumen_m3, "acero_kg": kg_acero,
                                "encofrado_m2": m2_encofrado, "puntales": puntales},
                               mat, mo, equip)

    # ─── MÓDULO 04: CERRAMIENTOS ──────────────────────────────────────────────

    def calc_ladrillo_comun(self, m2, espesor_cm=15, incluir_cargas=True, pct_cargas=1.2521):
        inc = self.incidencias["LADRILLO_COMUN_15_M2"]
        mat = (inc["ladrillos_un"] * m2 * self.precios["ladrillo_comun_un"] +
               inc["bolsas_plasticor"] * m2 * self.precios["bolsa_plasticor"])
        mo = self._calcular_costo_mo(inc["mo_oficial_hs"] * m2, inc["mo_ayudante_hs"] * m2, incluir_cargas, pct_cargas)
        return self._resultado(f"Ladrillo Común {espesor_cm}cm", {"m2": m2}, mat, mo, 0)

    def calc_ladrillo_hueco(self, m2, incluir_cargas=True, pct_cargas=1.2521):
        inc = self.incidencias["LADRILLO_HUECO_18_M2"]
        mat = (inc["ladrillos_un"] * m2 * self.precios["ladrillo_hueco_18_un"] +
               inc["bolsas_plasticor"] * m2 * self.precios["bolsa_plasticor"])
        mo = self._calcular_costo_mo(inc["mo_oficial_hs"] * m2, inc["mo_ayudante_hs"] * m2, incluir_cargas, pct_cargas)
        return self._resultado("Ladrillo Hueco 18cm", {"m2": m2}, mat, mo, 0)

    def calc_steel_frame(self, m2, incluir_cargas=True, pct_cargas=1.2521):
        inc = self.incidencias["STEEL_FRAME_M2"]
        mat = (inc["perfil_pgc_ml"] * m2 * self.precios["perfil_pgc_ml"] +
               inc["placa_roca_yeso_m2"] * m2 * self.precios["placa_durlock_m2"] +
               inc["aislacion_lana_m2"] * m2 * self.precios["lana_mineral_m2"])
        mo = self._calcular_costo_mo(inc["mo_oficial_hs"] * m2, inc["mo_ayudante_hs"] * m2, incluir_cargas, pct_cargas)
        return self._resultado("Steel Frame (Muro Seco)", {"m2": m2}, mat, mo, 0)

    # ─── MÓDULO 05: AISLACIONES ───────────────────────────────────────────────

    def calc_capa_aisladora(self, ml, incluir_cargas=True, pct_cargas=1.2521):
        inc = self.incidencias["CAPA_AISLADORA_HORIZONTAL_ML"]
        mat = (inc["pintura_asfaltica_kg"] * ml * self.precios["pintura_asfaltica_kg"] +
               inc["hidrofugo_lt"] * ml * self.precios["hidrofugo_lt"])
        mo = self._calcular_costo_mo(inc["mo_oficial_hs"] * ml, inc["mo_ayudante_hs"] * ml, incluir_cargas, pct_cargas)
        return self._resultado("Capa Aisladora Horizontal", {"ml": ml}, mat, mo, 0)

    # ─── MÓDULO 06: CUBIERTAS ─────────────────────────────────────────────────

    def calc_cubierta_chapa(self, m2, incluir_cargas=True, pct_cargas=1.2521):
        inc = self.incidencias["CUBIERTA_CHAPA_M2"]
        mat = (inc["chapa_m2"] * m2 * self.precios["chapa_m2"] +
               inc["aislacion_lana_m2"] * m2 * self.precios["lana_mineral_m2"])
        mo = self._calcular_costo_mo(inc["mo_oficial_hs"] * m2, inc["mo_ayudante_hs"] * m2, incluir_cargas, pct_cargas)
        return self._resultado("Cubierta de Chapa + Aislación", {"m2": m2}, mat, mo, 0)

    def calc_cubierta_membrana(self, m2, incluir_cargas=True, pct_cargas=1.2521):
        inc = self.incidencias["CUBIERTA_MEMBRANA_M2"]
        mat = (inc["membrana_m2"] * m2 * self.precios["membrana_m2"] +
               inc["imprimacion_lt"] * m2 * self.precios["imprimacion_lt"])
        mo = self._calcular_costo_mo(inc["mo_oficial_hs"] * m2, inc["mo_ayudante_hs"] * m2, incluir_cargas, pct_cargas)
        return self._resultado("Cubierta Plana (Membrana)", {"m2": m2}, mat, mo, 0)

    # ─── MÓDULO 07: REVOQUES ──────────────────────────────────────────────────

    def calc_revoque_grueso(self, m2, espesor_cm=1.5, incluir_cargas=True, pct_cargas=1.2521):
        # Ajuste de bolsas por espesor: 1.0→6m2, 1.5→4m2, 2.0→3m2, 2.5→2.5m2
        rendimientos = {1.0: 6, 1.5: 4, 2.0: 3, 2.5: 2.5}
        rend = rendimientos.get(espesor_cm, 4)
        bolsas = (m2 / rend) * 1.12
        inc = self.incidencias["REVOQUE_GRUESO_M2"]
        mat = bolsas * self.precios["bolsa_plasticor"]
        mo = self._calcular_costo_mo(inc["mo_oficial_hs"] * m2, inc["mo_ayudante_hs"] * m2, incluir_cargas, pct_cargas)
        return self._resultado(f"Revoque Grueso (e={espesor_cm}cm)",
                               {"m2": m2, "bolsas_plasticor": round(bolsas)}, mat, mo, 0)

    def calc_revoque_fino(self, m2, incluir_cargas=True, pct_cargas=1.2521):
        inc = self.incidencias["REVOQUE_FINO_M2"]
        bolsas = inc["bolsas_plasticor"] * m2
        mat = bolsas * self.precios["bolsa_plasticor"]
        mo = self._calcular_costo_mo(inc["mo_oficial_hs"] * m2, inc["mo_ayudante_hs"] * m2, incluir_cargas, pct_cargas)
        return self._resultado("Revoque Fino", {"m2": m2, "bolsas_plasticor": round(bolsas)}, mat, mo, 0)

    # ─── MÓDULO 08: CONTRAPISOS ───────────────────────────────────────────────

    def calc_contrapiso(self, m2, espesor_m=0.08, incluir_cargas=True, pct_cargas=1.2521):
        m3 = m2 * espesor_m
        inc = self.incidencias["CONTRAPISO_M3"]
        mat = (inc["cemento_kg"] * m3 * self.precios["cemento_kg"] +
               inc["arena_m3"] * m3 * self.precios["arena_m3"] +
               inc["ripio_m3"] * m3 * self.precios["ripio_m3"])
        mo = self._calcular_costo_mo(inc["mo_oficial_hs"] * m3, inc["mo_ayudante_hs"] * m3, incluir_cargas, pct_cargas)
        return self._resultado(f"Contrapiso (e={int(espesor_m*100)}cm)", {"m2": m2, "m3": round(m3, 2)}, mat, mo, 0)

    def calc_carpeta(self, m2, incluir_cargas=True, pct_cargas=1.2521):
        inc = self.incidencias["CARPETA_NIVELADORA_M2"]
        bolsas = inc["bolsas_plasticor"] * m2
        mat = bolsas * self.precios["bolsa_plasticor"]
        mo = self._calcular_costo_mo(inc["mo_oficial_hs"] * m2, inc["mo_ayudante_hs"] * m2, incluir_cargas, pct_cargas)
        return self._resultado("Carpeta Niveladora", {"m2": m2}, mat, mo, 0)

    # ─── MÓDULO 09: PISOS Y REVESTIMIENTOS ───────────────────────────────────

    def calc_pisos_ceramicos(self, m2, diagonal=False, incluir_cargas=True, pct_cargas=1.2521):
        key = "PISOS_CERAMICOS_DIAGONAL_M2" if diagonal else "PISOS_CERAMICOS_M2"
        inc = self.incidencias[key]
        mat = (inc["ceramico_m2"] * m2 * self.precios["ceramico_m2"] +
               inc["adhesivo_kg"] * m2 * self.precios["adhesivo_ceramico_kg"] +
               inc["pastina_kg"] * m2 * self.precios["pastina_kg"])
        mo = self._calcular_costo_mo(inc["mo_oficial_hs"] * m2, inc["mo_ayudante_hs"] * m2, incluir_cargas, pct_cargas)
        tipo = "diagonal" if diagonal else "recto"
        return self._resultado(f"Pisos Cerámicos ({tipo})", {"m2": m2}, mat, mo, 0)

    def calc_zocalos(self, ml, incluir_cargas=True, pct_cargas=1.2521):
        inc = self.incidencias["ZOCALOS_ML"]
        mat = (inc["zocalo_ml"] * ml * self.precios["zocalo_ml"] +
               inc["adhesivo_kg"] * ml * self.precios["adhesivo_ceramico_kg"])
        mo = self._calcular_costo_mo(inc["mo_oficial_hs"] * ml, inc["mo_ayudante_hs"] * ml, incluir_cargas, pct_cargas)
        return self._resultado("Zócalos", {"ml": ml}, mat, mo, 0)

    # ─── MÓDULO 10: CIELORRASOS ───────────────────────────────────────────────

    def calc_cielorraso_aplicado(self, m2, incluir_cargas=True, pct_cargas=1.2521):
        inc = self.incidencias["CIELORRASO_APLICADO_M2"]
        mat = inc["yeso_kg"] * m2 * self.precios["yeso_kg"]
        mo = self._calcular_costo_mo(inc["mo_oficial_hs"] * m2, inc["mo_ayudante_hs"] * m2, incluir_cargas, pct_cargas)
        return self._resultado("Cielorraso Aplicado (Yeso)", {"m2": m2}, mat, mo, 0)

    def calc_cielorraso_suspendido(self, m2, incluir_cargas=True, pct_cargas=1.2521):
        inc = self.incidencias["CIELORRASO_SUSPENDIDO_M2"]
        mat = (inc["placa_durlock_m2"] * m2 * self.precios["placa_durlock_m2"] +
               inc["perfil_ml"] * m2 * self.precios["perfil_durlock_ml"] +
               inc["tornillos_un"] * m2 * self.precios["tornillo_un"])
        mo = self._calcular_costo_mo(inc["mo_oficial_hs"] * m2, inc["mo_ayudante_hs"] * m2, incluir_cargas, pct_cargas)
        return self._resultado("Cielorraso Suspendido (Durlock)", {"m2": m2}, mat, mo, 0)

    # ─── MÓDULO 11: INSTALACIONES ─────────────────────────────────────────────

    def calc_instalacion_electrica(self, bocas, incluir_cargas=True, pct_cargas=1.2521):
        inc = self.incidencias["INSTALACION_ELECTRICA_BOCA"]
        mat = (inc["cano_10mm_ml"] * bocas * self.precios["cano_electrico_10_ml"] +
               inc["cable_m"] * bocas * self.precios["cable_ml"] +
               inc["cajas_un"] * bocas * self.precios["caja_electrica_un"])
        mo = self._calcular_costo_mo(inc["mo_oficial_hs"] * bocas, inc["mo_ayudante_hs"] * bocas, incluir_cargas, pct_cargas)
        return self._resultado("Instalación Eléctrica", {"bocas": bocas}, mat, mo, 0)

    def calc_instalacion_sanitaria(self, bocas, incluir_cargas=True, pct_cargas=1.2521):
        inc = self.incidencias["INSTALACION_SANITARIA_BOCA"]
        mat = (inc["cano_75mm_ml"] * bocas * self.precios["cano_sanitario_75_ml"] +
               inc["codos_un"] * bocas * self.precios["codo_sanitario_un"])
        mo = self._calcular_costo_mo(inc["mo_oficial_hs"] * bocas, inc["mo_ayudante_hs"] * bocas, incluir_cargas, pct_cargas)
        return self._resultado("Instalación Sanitaria", {"bocas": bocas}, mat, mo, 0)

    # ─── MÓDULO 12: PINTURAS ─────────────────────────────────────────────────

    def calc_pintura_interior(self, m2, manos=2, incluir_cargas=True, pct_cargas=1.2521):
        inc = self.incidencias["PINTURA_LATEX_INTERIOR_M2"]
        mat = (inc["latex_lt"] * manos/2 * m2 * self.precios["pintura_latex_lt"] +
               inc["sellador_lt"] * m2 * self.precios["sellador_lt"])
        mo = self._calcular_costo_mo(inc["mo_oficial_hs"] * m2 * manos/2,
                                     inc["mo_ayudante_hs"] * m2 * manos/2, 
                                     incluir_cargas, pct_cargas)
        return self._resultado(f"Pintura Látex Interior ({manos} manos)", {"m2": m2}, mat, mo, 0)

    def calc_pintura_exterior(self, m2, incluir_cargas=True, pct_cargas=1.2521):
        inc = self.incidencias["PINTURA_EXTERIOR_M2"]
        mat = inc["texturado_lt"] * m2 * self.precios["texturado_lt"]
        mo = self._calcular_costo_mo(inc["mo_oficial_hs"] * m2, inc["mo_ayudante_hs"] * m2, incluir_cargas, pct_cargas)
        return self._resultado("Pintura Exterior Texturada", {"m2": m2}, mat, mo, 0)

    # ─── CONSOLIDADO FINAL ────────────────────────────────────────────────────

    def consolidar(self):
        """Suma todos los ítems calculados en el presupuesto global."""
        total_mat = sum(r["subtotales"]["materiales"] for r in self.resultados)
        total_mo = sum(r["subtotales"]["mano_obra"] for r in self.resultados)
        total_equip = sum(r["subtotales"]["equipos"] for r in self.resultados)
        total = total_mat + total_mo + total_equip
        return {
            "items": self.resultados,
            "TOTAL_MATERIALES": round(total_mat, 2),
            "TOTAL_MANO_DE_OBRA": round(total_mo, 2),
            "TOTAL_EQUIPOS": round(total_equip, 2),
            "COSTO_DIRECTO_TOTAL": round(total, 2),
            "nota": "Honorarios profesionales a agregar por separado."
        }

    # ─── EXPORTAR (Tarea 3.3) ────────────────────────────────────────────────

    @staticmethod
    def _nombre_archivo_presupuesto(sesion: dict) -> str:
        """Genera nombre descriptivo del JSON de presupuesto según el scope de sesion."""
        modo = sesion.get("modo_alcance", "obra_completa")
        if modo == "obra_completa":
            return "presupuesto_obra_completa.json"
        rubros = sesion.get("rubros_seleccionados", [])
        if rubros:
            rubros_str = "_".join(r.lower() for r in rubros)
            return f"presupuesto_{rubros_str}.json"
        return "presupuesto.json"

    @staticmethod
    def _actualizar_estado_proyecto_presupuesto(ruta_archivo: str, dir_salida: str):
        """
        Agrega la ruta del archivo de presupuesto exportado a estado-proyecto.json
        bajo archivos_generados.presupuestos y actualiza ultimo_presupuesto.
        """
        estado_path = os.path.join(dir_salida, "estado-proyecto.json")
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

        presupuestos = estado["archivos_generados"].get("presupuestos", [])
        if ruta_archivo not in presupuestos:
            presupuestos.append(ruta_archivo)
        estado["archivos_generados"]["presupuestos"] = presupuestos
        estado["archivos_generados"]["ultimo_presupuesto"] = ruta_archivo

        with open(estado_path, "w", encoding="utf-8") as f:
            json.dump(estado, f, indent=2, ensure_ascii=False)

    def exportar(self, dir_salida: str = None, sesion: dict = None):
        """
        Exporta el presupuesto consolidado en outputs/ como JSON.
        Escribe siempre presupuesto.json (compatibilidad) y además un archivo
        con nombre descriptivo según el scope (Tarea 3.3).

        Args:
            dir_salida: directorio de salida. Si None, usa ../outputs/ relativo al script.
            sesion: dict de sesion_activa.json. Si None, intenta cargarlo automáticamente.
        """
        base = os.path.dirname(os.path.abspath(__file__))
        if dir_salida is None:
            dir_salida = os.path.normpath(os.path.join(base, "..", "outputs"))
        os.makedirs(dir_salida, exist_ok=True)

        # Cargar sesión si no se proveyó
        if sesion is None:
            sesion_path = os.path.normpath(os.path.join(base, "..", "outputs", "sesion_activa.json"))
            if os.path.exists(sesion_path):
                try:
                    with open(sesion_path, encoding="utf-8") as f:
                        sesion = json.load(f)
                except Exception:
                    sesion = {}
            else:
                sesion = {}

        datos = self.consolidar()

        # Archivo original (compatibilidad con generate_schedule.py / cargar_presupuesto())
        ruta_base = os.path.join(dir_salida, "presupuesto.json")
        with open(ruta_base, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
        print(f"[Presupuesto] JSON exportado -> {ruta_base}")

        # Archivo adicional con nombre descriptivo por scope (3.3)
        nombre_descriptivo = self._nombre_archivo_presupuesto(sesion)
        if nombre_descriptivo != "presupuesto.json":
            ruta_descriptiva = os.path.join(dir_salida, nombre_descriptivo)
            with open(ruta_descriptiva, "w", encoding="utf-8") as f:
                json.dump(datos, f, indent=2, ensure_ascii=False)
            print(f"[Presupuesto] JSON (scope)  -> {ruta_descriptiva}")
            self._actualizar_estado_proyecto_presupuesto(ruta_descriptiva, dir_salida)
        else:
            self._actualizar_estado_proyecto_presupuesto(ruta_base, dir_salida)

        return datos


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN DE SELECCIÓN POR RUBROS (Tarea 3.1)
# ─────────────────────────────────────────────────────────────────────────────

def calcular_desde_seleccion(rubros_ids: list,
                             ruta_rubros: str = "../references/rubros.json",
                             ruta_precios: str = "",
                             **kwargs_calc) -> dict:
    """
    Recibe lista de IDs de rubros y ejecuta solo los calc_* correspondientes.
    Devuelve dict con resultados por rubro y un total_ars consolidado.

    Parámetros
    ----------
    rubros_ids  : lista de IDs exactos, p.ej. ["03_ESTRUCTURAS", "04_CERRAMIENTOS"]
    ruta_rubros : ruta al rubros.json (por defecto relativa al script)
    ruta_precios: ruta al CSV de precios (cadena vacía = usar defaults)
    **kwargs_calc: kwargs opcionales para sobreescribir métricas por defecto
                   (ver METRICAS_POR_DEFECTO dentro de esta función)

    Ejemplo
    -------
    resultado = calcular_desde_seleccion(["03_ESTRUCTURAS", "04_CERRAMIENTOS"])
    print(resultado["total_ars"])
    """
    import warnings as _warnings

    # ── Métricas por defecto para cada rubro ─────────────────────────────────
    # Se usan cuando no se pasan valores específicos vía kwargs_calc.
    # Representan una obra residencial de referencia ~60 m2.
    METRICAS_POR_DEFECTO = {
        "01_TRABAJOS_PREPARATORIOS": {"m2": 60},
        "02_CIMIENTOS_Y_FUNDACIONES": {"m3_excavacion": 15, "m3_cimiento": 8},
        "03_ESTRUCTURAS":             {"volumen_m3": 3.0, "kg_acero": 280,
                                       "m2_encofrado": 18},
        "04_CERRAMIENTOS":            {"m2": 120},
        "05_AISLACIONES":             {"ml": 40},
        "06_CUBIERTAS":               {"m2": 65},
        "07_REVOQUES":                {"m2": 200},
        "08_CONTRAPISOS_CARPETAS":    {"m2": 60},
        "09_PISOS":                   {"m2": 55, "ml_zocalos": 80},
        "10_CIELORRASOS":             {"m2": 55},
        "11_INSTALACIONES":           {"bocas_elect": 25, "bocas_sanit": 8},
        "12_CARPINTERIAS":            {},  # sin calc_* implementado aún
        "13_PINTURAS":                {"m2_int": 350, "m2_ext": 80},
        "14_LIMPIEZA":                {},  # sin calc_* implementado aún
    }

    # ── Mapeo explícito rubro_id → función(es) de cálculo ────────────────────
    # Cada entrada es una lista de callables que reciben (calc, metricas).
    # Si un rubro no tiene entrada aquí → warning y se omite.
    def _run_01(calc, m):
        calc.calc_replanteo(m.get("m2", 60))

    def _run_02(calc, m):
        calc.calc_excavacion(m.get("m3_excavacion", 15))
        calc.calc_cimiento_corrido(m.get("m3_cimiento", 8))

    def _run_03(calc, m):
        calc.calc_elemento_ha(
            "Columnas HA",
            volumen_m3=m.get("volumen_m3", 3.0),
            kg_acero=m.get("kg_acero", 280),
            m2_encofrado=m.get("m2_encofrado", 18),
        )

    def _run_04(calc, m):
        calc.calc_ladrillo_hueco(m.get("m2", 120))

    def _run_05(calc, m):
        calc.calc_capa_aisladora(m.get("ml", 40))

    def _run_06(calc, m):
        calc.calc_cubierta_chapa(m.get("m2", 65))

    def _run_07(calc, m):
        calc.calc_revoque_grueso(m.get("m2", 200))
        calc.calc_revoque_fino(m.get("m2", 200))

    def _run_08(calc, m):
        calc.calc_contrapiso(m.get("m2", 60))
        calc.calc_carpeta(m.get("m2", 60))

    def _run_09(calc, m):
        calc.calc_pisos_ceramicos(m.get("m2", 55))
        calc.calc_zocalos(m.get("ml_zocalos", 80))

    def _run_10(calc, m):
        calc.calc_cielorraso_aplicado(m.get("m2", 55))

    def _run_11(calc, m):
        calc.calc_instalacion_electrica(m.get("bocas_elect", 25))
        calc.calc_instalacion_sanitaria(m.get("bocas_sanit", 8))

    def _run_13(calc, m):
        calc.calc_pintura_interior(m.get("m2_int", 350))
        calc.calc_pintura_exterior(m.get("m2_ext", 80))

    MAPEO_RUBROS = {
        "01_TRABAJOS_PREPARATORIOS": _run_01,
        "02_CIMIENTOS_Y_FUNDACIONES": _run_02,
        "03_ESTRUCTURAS":             _run_03,
        "04_CERRAMIENTOS":            _run_04,
        "05_AISLACIONES":             _run_05,
        "06_CUBIERTAS":               _run_06,
        "07_REVOQUES":                _run_07,
        "08_CONTRAPISOS_CARPETAS":    _run_08,
        "09_PISOS":                   _run_09,
        "10_CIELORRASOS":             _run_10,
        "11_INSTALACIONES":           _run_11,
        # 12_CARPINTERIAS — sin calc_* implementado aún
        "13_PINTURAS":                _run_13,
        # 14_LIMPIEZA      — sin calc_* implementado aún
    }

    # ── Ejecutar ──────────────────────────────────────────────────────────────
    resultados_por_rubro: dict = {}
    total_ars: float = 0.0

    for rubro_id in rubros_ids:
        if rubro_id not in MAPEO_RUBROS:
            print(f"[WARNING] calcular_desde_seleccion: rubro '{rubro_id}' "
                  "no tiene función de cálculo mapeada — se omite.")
            continue

        # Instancia calculadora independiente por rubro para aislar resultados
        calc = CalculadoraPresupuesto(ruta_rubros, ruta_precios)

        # Métricas: valores por defecto actualizados con lo que haya en kwargs_calc
        metricas = dict(METRICAS_POR_DEFECTO.get(rubro_id, {}))
        metricas.update(kwargs_calc.get(rubro_id, {}))

        # Ejecutar las funciones del rubro
        MAPEO_RUBROS[rubro_id](calc, metricas)

        resumen_rubro = calc.consolidar()
        subtotal_rubro = resumen_rubro["COSTO_DIRECTO_TOTAL"]

        resultados_por_rubro[rubro_id] = {
            "items": resumen_rubro["items"],
            "subtotal_materiales": resumen_rubro["TOTAL_MATERIALES"],
            "subtotal_mano_obra": resumen_rubro["TOTAL_MANO_DE_OBRA"],
            "subtotal_equipos": resumen_rubro["TOTAL_EQUIPOS"],
            "subtotal_ars": subtotal_rubro,
        }
        total_ars += subtotal_rubro

    return {
        "rubros_calculados": list(resultados_por_rubro.keys()),
        "resultados": resultados_por_rubro,
        "total_ars": round(total_ars, 2),
    }


# ─────────────────────────────────────────────────────────────────────────────
# PRUEBA INTEGRAL: simula una casa simple de 60m2
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    c = CalculadoraPresupuesto("../references/rubros.json", "")
    INCL = True; PCT = 1.2521  # Con cargas sociales estándar

    c.calc_replanteo(60, INCL, PCT)
    c.calc_excavacion(15, mecanica=False)
    c.calc_cimiento_corrido(8, INCL, PCT)
    c.calc_elemento_ha("Columnas HA", volumen_m3=3.0, kg_acero=280, m2_encofrado=18)
    c.calc_elemento_ha("Vigas HA",   volumen_m3=2.5, kg_acero=210, m2_encofrado=15, puntales=12)
    c.calc_elemento_ha("Losa Llena", volumen_m3=4.0, kg_acero=350, m2_encofrado=60, puntales=20)
    c.calc_ladrillo_hueco(120, INCL, PCT)
    c.calc_capa_aisladora(40, INCL, PCT)
    c.calc_cubierta_chapa(65, INCL, PCT)
    c.calc_revoque_grueso(200, espesor_cm=1.5)
    c.calc_revoque_fino(200)
    c.calc_contrapiso(60)
    c.calc_carpeta(60)
    c.calc_pisos_ceramicos(55)
    c.calc_zocalos(80)
    c.calc_cielorraso_aplicado(55)
    c.calc_instalacion_electrica(25)
    c.calc_instalacion_sanitaria(8)
    c.calc_pintura_interior(350)
    c.calc_pintura_exterior(80)

    resumen = c.consolidar()
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
