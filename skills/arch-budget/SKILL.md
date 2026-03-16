---
name: arch-budget
description: Skill ejecutora de cálculos de presupuesto por rubros, estructurada para ser utilizada por el agente-presupuestos dentro del Arch Proposal Suite.
---

# Arch Budget Calculator (Cálculo de Presupuestos por Rubros)

Esta herramienta (Skill) se encarga de ejecutar la matemática dura del presupuesto de obra. Se basa en las métricas extraídas por el `agente-documentacion` y en la base de precios del `agente-costos`.

## Flujo Lógico y Eficiencia Condicional
La presupuestación se organiza estrictamente por **Rubros de Construcción**. 
**Regla de Eficiencia:** SOLO se calcularán los rubros de los cuales el usuario o el `agente-documentacion` haya provisto métricas. Si el usuario solo envía datos de "Estructuras" (ej. metros cúbicos de hormigón), el cálculo ignorará los demás rubros.

### Lista Base de Rubros (Estructura de Presupuesto)
1. Trabajos Preparatorios (Limpieza, Replanteo, Excavaciones)
2. Estructuras (Hormigón Armado, Metálicas, Maderas) - *Unidad típica: m³ (Hormigón), kg (Acero)*
3. Mamposterías (Ladrillo hueco, común, cerramientos) - *Unidad típica: m²*
4. Revoques (Grueso, Fino, Exterior, Interior) - *Unidad típica: m²*
5. Contrapisos y Carpetas - *Unidad típica: m², m³*
6. Pisos y Revestimientos - *Unidad típica: m²*
7. Cubiertas y Techos - *Unidad típica: m²*
8. Instalaciones (Sanitaria, Eléctrica, Gas) - *Unidad típica: Boca, ml, Global*
9. Pintura y Terminaciones - *Unidad típica: m², ml*

## Metodología de Cómputo de Materiales
El cómputo de materiales surge de multiplicar la **Cantidad de Obra (Métrica base)** por la **Incidencia del Material por Unidad de Medida**.

### 1. Extracción de Métricas Relativas
Lee el archivo `estado-proyecto.json` (bloque `"metricas_base"` generado por el `agente-documentacion`).

### 2. Aplicación de Incidencias
Aplica las incidencias estándar para cada material según la unidad del rubro. 
*(Nota: Si el usuario provisto un cuadernillo o parámetros custom, estos tienen prioridad).*

**Ejemplo - Factor de Incidencia (Orientativo):**
* **Hormigón H-21 (por m³):** Cemento (320 kg), Arena (0.52 m³), Ripio (0.72 m³), Agua (190 L). Desperdicios: H° Elaborado (x1.05), Arena/Ripio (x1.08), Acero en barras (x1.08).
* **Mampostería (por m² - Ladrillo común 15cm):** Ladrillos (60 U), Mortero Plasticor (se asumen ~3.5 m²/bolsa dependiendo de junta). Desperdicio: Ladrillos (x1.07), Mortero (x1.12).
* **Revoque Fino (por m²):** Plasticor ~7m²/bolsa sobre mampostería.

### 3. Asignación de Costos Unitarios
Busca en la base local (o pide al agente que navegue a internet si falta un precio en ARS en la provincia/región).
* Fórmula: `Costo Material = Cantidad Total del Material x Precio Unitario ARS`

### 4. Cálculo de Mano de Obra (MO)
El costo de MO usa las horas de rendimiento multiplicadas por la tarifa por hora de los oficiales y ayudantes.
* `Costo MO = (Horas Oficial x Tarifa Oficial) + (Horas Ayudante x Tarifa Ayudante)`
* Agregar Cargas Sociales (Preguntar al usuario si no lo proporcionó, referencia histórica ~120-125%).

## Output: Matriz de Resultados
Al terminar, este skill debe retornar la tabla estructurada por Rubros procesados con el formato:
`ITEM | RUBRO | CANTIDAD | UNIDAD | SUBTOTAL MATERIALES | SUBTOTAL MANO DE OBRA | SUBTOTAL EQUIPOS | TOTAL ITEM`

Generando al final:
- Total Materiales
- Total Mano de Obra (Cargas Soc. incluidas)
- Total Equipos
- Total Costo Directo.
