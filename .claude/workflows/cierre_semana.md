---
description: Workflow orquestado de Cierre de Semana. Consolida el avance real, genera el certificado de obra, actualiza el Dashboard y guarda el snapshot de estado para que la próxima sesión arranque con contexto completo.
---

# Workflow: Cierre de Semana (Director de Obra)

Este workflow es el **ritual de fin de semana** del Arch Proposal Suite. Lo ejecuta el Orquestador cuando el usuario escribe `/cierre-semana` o lo solicita explícitamente. Coordina a todos los agentes en secuencia y cierra el ciclo semanal.

---

## FASE 0 — Orientación (¿En qué semana estamos?)

Antes de hacer nada, el sistema DEBE calcular el número de semana actual del proyecto:

1. Lee `./outputs/cronograma.json` → campo `configuracion.fecha_inicio`.
2. Calcula `SEMANA_ACTUAL = ceil((fecha_hoy - fecha_inicio).days / 7)`.
3. Verifica si ya existe el archivo `./outputs/snapshots/semana_{N}.json`. Si existe, significa que el cierre de esa semana ya fue ejecutado. Avisa al usuario:
   `"⚠️ El cierre de la Semana {N} ya fue generado el {fecha}. ¿Deseas regenerarlo o ejecutar el cierre de la Semana {N+1}?"`

---

## FASE 1 — Auditoría de Gastos Reales (Agente Costos)

**Objetivo:** Asegurarse de que todos los tickets de la semana estén registrados antes de cerrar.

1. Lee el array `"gastos_reales"` en `./outputs/estado-proyecto.json`.
2. Filtra los gastos de los últimos 7 días (semana en curso).
3. Calcula:
   - `total_gastado_semana` = suma de `total_ars` de los gastos filtrados
   - `total_gastado_acumulado` = suma histórica de todos los gastos
4. Avisa al usuario con un resumen rápido:
   ```
   📋 Tickets registrados esta semana: {N}
   💰 Gasto real semana: $ {total_gastado_semana}
   💰 Gasto acumulado total: $ {total_gastado_acumulado}
   ```
5. Pregunta: *"¿Hay algún ticket pendiente de cargar antes de cerrar la semana?"*
   - Si el usuario dice Sí: espera, ejecuta el workflow `auditar_ticket.md` y luego retorna a esta Fase.
   - Si el usuario dice No: continúa a FASE 2.

---

## FASE 2 — Avance del Cronograma (Agente Cronograma)

**Objetivo:** Calcular qué porcentaje del cronograma está completado según el plan vs. la realidad.

1. Lee `./outputs/cronograma.json`.
2. Identifica las tareas cuya fecha `fin` ya pasó (tareas que DEBERÍAN estar terminadas).
3. Pregunta al usuario cuáles de esas tareas están **realmente terminadas** (puede ser voz/texto libre o una lista de checkbox).
   - *"Según el cronograma, esta semana debían completarse: {lista de tareas}. ¿Confirmas cuáles están 100% terminadas?"*
4. Calcula:
   - `avance_programado_%` = (tareas planificadas completadas / total tareas) * 100
   - `avance_real_%` = (tareas realmente completadas / total tareas) * 100
   - `desvio_tiempo_dias` = diferencia entre fecha fin planificada y fecha actual
5. Guarda el resultado en memoria temporal para las fases siguientes.

---

## FASE 3 — Generación del Certificado de Obra (Agente Presupuestos)

**Objetivo:** Emitir el documento oficial de la semana.

1. Compila los datos de FASE 1 y FASE 2.
2. Lee el presupuesto teórico desde `./outputs/estado-proyecto.json` (campo `presupuesto_validado`).
3. Calcula la inversión teórica programada para la semana según el cronograma (prorrateo por % de avance planificado).
4. Genera el archivo `./outputs/certificado_semana_{N}.md` con este formato EXACTO:

```markdown
# Certificado de Obra - SEMANA {N}
*Generado el: {fecha_hora}*

## Curva de Inversión y Auditoría

| Métrica | Monto ARS |
| :--- | :--- |
| **Inversión Teórica Programada:** | $ {teorico} |
| **Inversión Real Ejecutada:** | $ {real} |
| **Desvío del Período:** | $ {desvio} |
| **Estado:** | {emoji + estado + porcentaje} |

---

## Avance de Obra

| Indicador | Valor |
| :--- | :--- |
| **Avance Programado:** | {avance_prog}% |
| **Avance Real:** | {avance_real}% |
| **Desvío de Tiempo:** | {desvio_tiempo} días |
| **Semáforo:** | {VERDE / AMARILLO / ROJO} |

---

## Tareas Completadas esta Semana
{lista de tareas terminadas}

## Tareas para la Próxima Semana
{lista de tareas planificadas para Semana N+1 según cronograma}

---

## Resumen de Tickets Ingresados (Gastos Reales)
{tabla de tickets de la semana con detalle de materiales}

---
*Reporte emitido Automáticamente por el **Agente Audítor (Presupuestos)** de Arch Proposal Suite.*
```

**Regla de Semáforo:**
- VERDE: avance_real >= avance_programado Y gasto_real <= gasto_teorico * 1.05
- AMARILLO: avance_real >= avance_programado * 0.85 O gasto_real <= gasto_teorico * 1.15
- ROJO: cualquier otra condición

---

## FASE 4 — Snapshot de Estado (Sistema)

**Objetivo:** Persistir el estado completo de la semana cerrada como archivo de registro histórico.

1. Crea la carpeta `./outputs/snapshots/` si no existe.
2. Genera `./outputs/snapshots/semana_{N}.json` con este schema:

```json
{
  "semana": N,
  "fecha_cierre": "YYYY-MM-DD",
  "resumen_financiero": {
    "gastado_semana_ars": 0.0,
    "gastado_acumulado_ars": 0.0,
    "presupuestado_semana_ars": 0.0,
    "desvio_financiero_pct": 0.0
  },
  "resumen_tiempo": {
    "avance_programado_pct": 0.0,
    "avance_real_pct": 0.0,
    "desvio_dias": 0
  },
  "semaforo": "VERDE | AMARILLO | ROJO",
  "tareas_completadas": [],
  "tareas_proxima_semana": [],
  "tickets_semana": [],
  "notas_director": ""
}
```

3. Actualiza `./outputs/estado-proyecto.json` con los datos del cierre:
   - Agrega un registro al array `"avances"`:
     ```json
     {
       "semana": N,
       "avance_programado_pct": valor_de_fase_2,
       "avance_real_pct": valor_de_fase_2,
       "tareas_completadas": lista_confirmada_por_usuario,
       "fecha_cierre": "YYYY-MM-DD"
     }
     ```
   - Actualiza `"semaforo"` con el valor calculado en FASE 3 (verde/amarillo/rojo).
   - Actualiza `"metadatos.ultima_actualizacion"` con la fecha de hoy.
   - **IMPORTANTE:** NO borrar ni sobreescribir `"gastos_reales"` — ese array es acumulativo y solo crece.

---

## FASE 5 — Actualización del Dashboard (Agente Inversor)

**Objetivo:** Publicar o preparar la actualización para el cliente.

1. Verifica la configuración del modo de publicación en `estado-proyecto.json`.
2. Si está en **Modo Automático**: actualiza el Dashboard inmediatamente.
3. Si está en **Modo Manual** (default): presenta el borrador y pregunta:
   *"¿Publico esta actualización en el Dashboard del cliente ahora, o la guardo como borrador?"*
4. Si tiene integración Notion activa, actualiza la página del proyecto con el resumen ejecutivo.

---

## FASE 6 — Actualización de Memoria del Sistema

**Objetivo:** Guardar el contexto clave para que la próxima sesión de Claude Code arranque con contexto completo.

Al finalizar, el sistema DEBE emitir el siguiente bloque de memoria para ser guardado:

```
MEMORIA SEMANAL A GUARDAR:
- Proyecto activo: {nombre_proyecto}
- Semana completada: {N}
- Último certificado: ./outputs/certificado_semana_{N}.md
- Estado financiero: {VERDE/AMARILLO/ROJO} ({desvio}% del presupuesto)
- Avance real: {avance_real}%
- Próxima semana planificada: {tareas_proxima_semana}
- Alertas pendientes: {lista o "Ninguna"}
```

---

## Resumen del Flujo

```
/cierre-semana
    │
    ├─ FASE 0: ¿Qué semana es?
    ├─ FASE 1: Auditoría de tickets (Agente Costos)
    │           └─ ¿Tickets pendientes? → loop hasta confirmación
    ├─ FASE 2: Avance cronograma (Agente Cronograma)
    │           └─ Confirmar tareas terminadas con el usuario
    ├─ FASE 3: Generar certificado_semana_N.md (Agente Presupuestos)
    ├─ FASE 4: Guardar snapshot en outputs/snapshots/semana_N.json
    ├─ FASE 5: Dashboard update (Agente Inversor)
    │           └─ Automático o manual según configuración
    └─ FASE 6: Actualizar memoria del sistema
```

## Paso Final — Archivar memoria semanal

Al completar el cierre, ejecutar el proceso de rotación de memoria:

1. **Leer** `memory/memoria_reciente.md` → extraer resumen ≤15 líneas de lo más importante de la semana (decisiones, cambios, bugs resueltos, correcciones permanentes)

2. **Mover** `memory/semana_anterior.md` → `memory/historial/semana_YYYY-MM-DD.md` (usar fecha del viernes)

3. **Escribir** el resumen extraído en nuevo `memory/semana_anterior.md`

4. **Resetear** `memory/memoria_reciente.md` con plantilla vacía para la semana siguiente

5. **Commitear y pushear** el historial a GitHub:
   ```
   git add memory/historial/semana_YYYY-MM-DD.md
   git commit -m "historial: cierre semana YYYY-MM-DD"
   git push origin main
   ```

6. **Limpiar historial local** — si hay archivos en `memory/historial/` con más de 28 días:
   - Ya están en GitHub → eliminar la copia local
   - Esto mantiene el repo local liviano

> El historial completo siempre vive en GitHub: https://github.com/Leoscd/arch-proposal-suite
> Para acceder a una semana archivada: `git pull` o el usuario sube el archivo manualmente.
