---
name: arch
description: Skill principal del Arch Proposal Suite. Orquesta el flujo completo de generación de una propuesta de obra: inicializa el proyecto, guía al usuario por los 5 agentes en secuencia y entrega el reporte final. Invocar con /arch proposal [nombre del proyecto].
---

# Arch Proposal — Orquestador de Flujo Completo

Este skill es el punto de entrada para generar una propuesta integral de obra. Al invocarlo, el sistema inicializa el proyecto y coordina los 5 agentes en la secuencia correcta.

## Paso 0 — Inicialización del Proyecto

Extraé el nombre del proyecto del argumento del comando (ej. `/arch proposal Casa García` → nombre = "Casa García").

Luego preguntá al usuario los datos base si no los proporcionó:
```
Para iniciar la propuesta de "Casa García" necesito los datos básicos:
1. ¿Cuál es la localidad/provincia de la obra? (ej. Tucumán, NOA)
2. ¿Cuál es la superficie estimada en m²? (o subí un plano/foto para que la calcule)
3. ¿Cuál es el nombre del comitente/propietario?
4. ¿Tenés fecha estimada de inicio de obra?
5. ¿Cuántos oficiales y ayudantes disponés?
```

Con esos datos, actualizá `./estado-proyecto.json` en el bloque `"metadatos"`:
```json
{
  "metadatos": {
    "proyecto_nombre": "[nombre]",
    "localidad": "[localidad]",
    "comitente": "[nombre propietario]",
    "fecha_inicio_obra": "[YYYY-MM-DD o null]",
    "personal_sugerido": {
      "oficiales": [N],
      "ayudantes": [N]
    }
  }
}
```

## Paso 1 — Documentación (agente-documentacion)

Informá al usuario:
`"📐 PASO 1/5 — Analizando documentación del proyecto..."`

- Si el usuario subió imágenes o PDFs: invocá el agente-documentacion para que extraiga métricas.
- Si sólo declaró m²: inyectá las métricas base manualmente en `estado-proyecto.json` con los valores declarados.
- Usá el workflow `analizar_foto.md` si hay imágenes.

Confirmá al finalizar: `"✅ Métricas base registradas. Superficie: {m2} m²"`

## Paso 2 — Costos (agente-costos)

Informá: `"💰 PASO 2/5 — Cargando base de precios..."`

- Verificá que existe `./references/precios_materiales.csv`. Si no, avisá que los precios serán paramétricos.
- Si el usuario tiene tickets o facturas disponibles, ofrecé cargarlos ahora: *"¿Tenés algún comprobante de compra ya realizada para incorporar al proyecto?"*
- Si no: continuá con precios de referencia de la base local.

## Paso 3 — Cronograma (agente-cronograma)

Informá: `"📅 PASO 3/5 — Generando cronograma y camino crítico..."`

- Verificá que tenés: m² de la obra y cantidad de personal.
- Ejecutá: `python3 scripts/generate_schedule.py` con los parámetros disponibles.
- Si el script falla: generá el cronograma manualmente con las tareas estándar del sistema.
- Mostrá al usuario un resumen: fecha de inicio → fecha fin estimada → tarea crítica.

## Paso 4 — Presupuesto (agente-presupuestos)

Informá: `"📊 PASO 4/5 — Calculando presupuesto de obra..."`

**REGLA OBLIGATORIA:** Antes de calcular, preguntá:
*"¿Incluyo Cargas Sociales en la Mano de Obra? (estándar: 125% — o indicame un porcentaje personalizado)"*

- Ejecutá: `python3 scripts/build_report.py --completo --m2 {m2} --proyecto "{nombre}" --localidad "{localidad}"`
- Mostrá el resumen: Total Materiales / Total MO / Costo Directo Total / Costo por m².

## Paso 5 — Presentación (agente-inversor)

Informá: `"🎯 PASO 5/5 — Preparando presentación para el cliente..."`

- Generá el resumen ejecutivo con los datos consolidados.
- Preguntá: *"¿Publico la landing del proyecto ahora o guardás como borrador?"*
- Si confirma publicar: ejecutá `python3 scripts/build_landing.py`.

## Cierre del Flujo

Al finalizar los 5 pasos, mostrá el dashboard de entregables:

```
✅ PROPUESTA COMPLETA — {nombre del proyecto}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 Reporte A4:      outputs/reporte_{fecha}.html
📅 Cronograma:      outputs/cronograma.json
💰 Presupuesto:     Costo directo $ {total ARS}
🏗️  Duración:        {N} días hábiles
📁 Estado guardado: outputs/estado-proyecto.json
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Próximo paso: /cierre-semana (cada viernes para auditar el avance)
```
