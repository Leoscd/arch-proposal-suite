---
name: arch-vision
description: Skill de visión del Arch Proposal Suite. Analiza imágenes de fotos de obra, planos en PDF o bocetos y extrae métricas constructivas (m², m³, rubros necesarios). Inyecta los resultados en estado-proyecto.json. Úsalo cuando el usuario comparte una imagen antes de presupuestar. Wrappea el workflow analizar_foto.md con validaciones adicionales.
---

# Arch Vision — Análisis Visual de Obra

Este skill activa la capacidad de visión para extraer métricas constructivas de imágenes o documentos. Es el primer paso técnico de cualquier propuesta.

## Qué acepta

- **PDF de Revit:** exportación con tablas de cómputo, cuadro de superficies, planillas de aberturas → fuente más confiable, datos exactos
- **PDF de AutoCAD:** planta acotada, cortes, cartel del plano → cotas explícitas en el dibujo
- **Fotos de obra:** estado actual, terreno, estructura existente → requiere referencia métrica
- **Bocetos con cotas:** esquemas dibujados a mano con dimensiones anotadas
- **Vistas múltiples:** podés recibir varios archivos en una sola invocación

## Protocolo de análisis

### 1. Recepción y clasificación del input

Al recibir un archivo, primero clasificá de qué tipo es para saber cómo procesarlo:

**PDF de Revit** → datos exactos, no necesitás estimar nada:
- Buscá la tabla "Cómputo de Materiales" o "Material Takeoff"
- Buscá el "Cuadro de Superficies" o "Room Schedule"
- Buscá la "Planilla de Aberturas"
- Transcribí los valores directamente — Revit ya hizo el cálculo

**PDF de AutoCAD** → cotas explícitas en el dibujo:
- Leé las dimensiones anotadas en planta (largo × ancho de cada local)
- Calculá m² sumando cada ambiente
- Leé el cartel del plano: nombre, escala, fecha
- Si hay escala gráfica visible, úsala como referencia

**Foto de obra o plano fotografiado** → estimación visual:
- Requiere referencia métrica del usuario (ver regla estricta abajo)

**REGLA ESTRICTA — solo para fotos:** Si es una foto sin referencia métrica clara, SIEMPRE preguntá:
```
⚠️ Necesito una referencia de escala para calcular los metros.
Por favor indicame una de estas:
  a) ¿Cuánto mide el frente del terreno/lote?
  b) ¿Cuánto mide aproximadamente la pared más larga visible?
  c) ¿Cuántos m² tiene la planta total (aproximado)?
```
Esta regla NO aplica a PDFs — ellos tienen sus propias cotas y datos.

### 2. Extracción de métricas

Con la referencia disponible, estimá y documentá:

| Rubro | Qué buscar en la imagen |
|---|---|
| `cubierta_m2` | Superficie de techo/losa visible |
| `muro_ladrillo_m2` | Paredes sin terminar, ladrillo a la vista |
| `revoque_grueso_m2` | Paredes con revoque aplicado o necesario |
| `revoque_fino_m2` | Paredes que necesitan terminación |
| `contrapiso_carpeta_m2` | Pisos sin revestir, tierra apisonada |
| `piso_ceramico_m2` | Superficie a revestir con piso |
| `pintura_interior_m2` | Superficies pintadas o a pintar |
| `excavacion_m3` | Tierra removida o a excavar (estimación) |
| `cimiento_m3` | Fundaciones visibles o necesarias |

**Confianza:** Asigná un score de 1 a 10 según qué tan segura es tu estimación.

### 3. Inyección en estado-proyecto.json

Actualizá el archivo `./estado-proyecto.json` con el bloque exacto:

```json
"metricas_base": {
  "superficies": {
    "cubierta_m2": 0.0,
    "semicubierta_m2": 0.0,
    "descubierta_m2": 0.0
  },
  "cantidades_estimadas_por_foto_o_plano": {
    "excavacion_m3": 0.0,
    "cimiento_m3": 0.0,
    "columna_viga_losa_m3": 0.0,
    "muro_ladrillo_m2": 0.0,
    "contrapiso_carpeta_m2": 0.0,
    "revoque_grueso_m2": 0.0,
    "revoque_fino_m2": 0.0,
    "cubierta_chapa_m2": 0.0,
    "piso_ceramico_m2": 0.0,
    "pintura_interior_m2": 0.0
  },
  "fuente": "foto | plano | declarado",
  "confianza_estimacion_1_a_10": 0,
  "notas_vision": "descripción de lo observado"
}
```

Solo completá con valores > 0 los rubros que veas claramente necesarios.

### 4. Resumen visual al usuario

Después de escribir el JSON, mostrá una tabla compacta:

```
✅ Análisis de imagen completado

| Rubro | Cantidad | Confianza |
|---|---|---|
| Muro ladrillo | 80 m² | Alta |
| Revoque grueso | 80 m² | Alta |
| Piso cerámico | 60 m² | Media |
| ... | ... | ... |

Superficie cubierta estimada: 65 m²
Confianza general: 7/10

Los datos fueron inyectados en estado-proyecto.json.
¿Continúo con el cálculo del presupuesto y cronograma?
```

## Casos de error

| Situación | Respuesta |
|---|---|
| Imagen borrosa / ilegible | `"⚠️ La imagen no es suficientemente clara. Por favor subí una foto con mejor iluminación o más cerca."` |
| No hay imagen adjunta | `"ℹ️ No recibí ninguna imagen. Subí una foto o plano para continuar, o declarame los m² directamente."` |
| Plano en escala sin referencia conocida | Pedir la escala gráfica o una medida de referencia |
| Múltiples imágenes contradictorias | Pedir al usuario que aclare cuál es la situación actual real |
