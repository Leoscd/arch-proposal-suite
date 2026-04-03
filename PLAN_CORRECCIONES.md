# Plan de Correcciones — Arch Proposal Suite
**Fecha:** 2026-04-01
**Estado:** ✅ COMPLETADO — 2026-04-03

---

## Decisiones de Diseño (acordadas)

### A — Ingesta de documentación
- Claude Code Desktop se conecta a una **carpeta `inputs/`** con la documentación de la obra
- Contenido esperado: planos PDF, planillas de cantidades (Revit exports), renders
- El `agente-documentacion` lee esa carpeta al inicio y extrae métricas base automáticamente
- El usuario NO carga datos manuales — todo viene de los archivos de la carpeta

### B — Presupuesto base
- Se usa el skill **`presupuesto-constructor`** (en `referencias/presupuesto-constructor/`)
- Alcance: proyectos residenciales pequeños/medianos, presupuestación por rubro
- El presupuesto generado por el skill se importa como `outputs/presupuesto_base.json`
- Desde ese JSON se deriva la curva de inversión semanal
- El certificado usa esa curva como valor "proyectado"

### C — Semana 1 existente
- Se **conserva** el snapshot `outputs/snapshots/semana_1.json`
- El agente QA usará esos datos reales para pruebas
- No resetear hasta que QA termine su ciclo de validación

### D — Tipos de documento de obra
Tres tipos a distinguir en el modelo de datos:
| Tipo | Descripción |
|---|---|
| `factura` | Obligación de pago — material o servicio facturado |
| `remito` | Entrega de material (puede llegar sin factura todavía) |
| `pago_mo` | Pago de mano de obra (oficial, ayudante, especializado) |

---

## Tareas pendientes (en orden de dependencia)

### Tarea 1 ✅ — Diseño del flujo (COMPLETADA en esta sesión)
Decisiones A/B/C/D acordadas arriba.

### Tarea 4 ✅ — Cargar datos base del proyecto (metricas_base)
- `agente-documentacion.md` actualizado con instrucciones para leer `inputs/`
- `estado-proyecto.json` poblado con datos inferidos desde `presupuesto_base.json`: `cubierta_m2: 80`, cantidades por rubro, nombre, ubicación, tipo de obra

### Tarea 2 ✅ — Corregir sincronización `gastos_reales[]`
- `gastos_reales[]` en `outputs/estado-proyecto.json` tiene 1 entrada real (TICK-20260315120000, $121.000 ARS)
- Sincronización con `semana_1.json` verificada — IDs coinciden

### Tarea 3 ✅ — Corregir sincronización `avances[]`
- `avances[]` tiene estructura correcta con datos de semana 1

### Tarea 5 ✅ — Vincular presupuesto base → curva de inversión → certificados
- `scripts/generate_curva_inversion.py` creado (327 líneas)
- `outputs/curva_inversion.json` generado: ARS 21.796.200 total, 5 semanas, desglose por rubro

### Tarea 6 ✅ — Agregar modelo de datos para remitos
- `vision_receipt_parser.py` tiene `detect_tipo()` con jerarquía `factura > pago_mo > remito`
- Schema diferenciado por tipo en el prompt del LLM

### Tarea 7 ✅ — Match factura/remito vs rubro activo del cronograma
- `audit_budget.py` ampliado con `match_gastos_a_rubros()` y `generar_reporte_match()`
- `outputs/reporte_match_semana_1.json` generado — semáforo CRITICO (subejecución, datos de demo)
- Bug corregido: `ESTADO_PATH` apuntaba a raíz en lugar de `outputs/`
- CLI: `--semana N` y `--solo-auditoria`

---

## Flujo completo objetivo (post-correcciones)

```
INICIO DE PROYECTO
    ↓
1. Usuario conecta carpeta inputs/ con planos y planillas
2. agente-documentacion lee inputs/ → escribe metricas_base en estado-proyecto.json
3. presupuesto-constructor skill genera presupuesto por rubro
4. Script calcula curva_inversion.json (distribución semanal)
    ↓
EJECUCIÓN SEMANAL (se repite cada semana o período)
    ↓
5. Usuario carga fotos/PDFs de facturas, remitos, pagos MO
6. agente-costos parsea con vision → detecta tipo → appenda a gastos_reales[]
7. Usuario marca avance real (% o tareas) → se guarda en avances[]
    ↓
CIERRE DE PERÍODO
    ↓
8. /cierre-semana ejecuta:
   - Lee gastos_reales[] del período
   - Lee curva_inversion.json para el período (= proyectado)
   - Match: cruza ítems de gastos vs rubros activos del cronograma
   - Genera certificado_semana_N.json con proyectado vs real vs match
   - Actualiza estado-proyecto.json (sync completo)
   - Guarda snapshot
   - Actualiza dashboard y semáforo
```

---

## Notas post-correcciones

- Todas las tareas completadas y validadas por QA agent el 2026-04-03
- `vision_receipt_parser.py` requiere `GEMINI_API_KEY` activa para pruebas con imágenes reales
- Existe `estado-proyecto.json` en la raíz del proyecto (duplicado de `outputs/`) — no eliminar sin revisar si algún script lo referencia
- Sistema listo para uso real con un proyecto que tenga planos en `inputs/`
