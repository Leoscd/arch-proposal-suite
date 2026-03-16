---
name: arch-scheduler
description: Skill de generación de cronograma del Arch Proposal Suite. Calcula el diagrama de Gantt y el camino crítico (CPM) basándose en las métricas del proyecto y los recursos disponibles. Ejecuta generate_schedule.py, guarda cronograma.json y muestra el Gantt en texto. Úsalo cuando el usuario pide el cronograma, las semanas de obra, o necesita saber cuánto tarda el proyecto.
---

# Arch Scheduler — Generador de Cronograma y CPM

Este skill genera el planificación completa de la obra: secuencia de tareas, duración por rubro, diagrama de Gantt y camino crítico.

## Datos que necesitás antes de calcular

Verificá en `./outputs/estado-proyecto.json` si existen estos datos. Los que falten, preguntáselos al usuario:

```
Para generar el cronograma necesito confirmar:
1. ¿Cuántos m² tiene la obra? (cubierta total)
2. ¿Cuántos oficiales trabajarán? [default: 2]
3. ¿Cuántos ayudantes trabajarán? [default: 2]
4. ¿Cuántas horas por jornada? [default: 8]
5. ¿Cuál es la fecha de inicio de obra? (YYYY-MM-DD o "a confirmar")
```

**REGLA:** Si el usuario no provee la cantidad de personal, preguntá obligatoriamente antes de calcular. No asumas valores por defecto sin avisar.

## Ejecución del cálculo

Una vez que tenés todos los datos, ejecutá:

```bash
python3 scripts/generate_schedule.py \
  --m2 {superficie_cubierta_m2} \
  --oficiales {N} \
  --ayudantes {N} \
  --jornada {hs} \
  --fecha-inicio {YYYY-MM-DD}
```

El script genera y guarda automáticamente `./outputs/cronograma.json`.

Si el script falla o no está disponible, calculá el cronograma manualmente usando las duraciones estándar por rubro definidas en `./references/rubros.json`.

## Lógica de cálculo (para modo manual)

Las duraciones se calculan así:

```
Duración (días) = Cantidad de Obra (m² o m³) / (Rendimiento diario × Personal efectivo)
Personal efectivo = oficiales + (ayudantes × 0.6)
```

Rendimientos de referencia por rubro:

| Rubro | Rendimiento | Unidad |
|---|---|---|
| Replanteo/nivelación | 80 m²/día | equipo completo |
| Excavación (manual) | 2.5 m³/día | por ayudante |
| Cimiento ciclópeo | 1.2 m³/día | por oficial |
| Columnas/Vigas HA | 0.8 m³/día | por oficial |
| Losa HA | 0.5 m³/día | por oficial |
| Ladrillo hueco 18cm | 8 m²/día | por oficial |
| Revoque grueso | 12 m²/día | por oficial |
| Revoque fino | 14 m²/día | por oficial |
| Contrapiso | 25 m²/día | equipo |
| Piso cerámico | 8 m²/día | por oficial |
| Pintura interior | 30 m²/día | por oficial |
| Pintura exterior | 25 m²/día | por oficial |

## Secuencia lógica de tareas (predecesores)

```
Replanteo → Excavación → Cimiento
                              ↓
                    Columnas HA → Vigas HA → Losa
                              ↓
                    Ladrillo hueco (paralelo con estructura)
                              ↓
                    Cubierta → Revoque grueso → Revoque fino
                    Contrapiso → Carpeta → Piso cerámico
                    Instalaciones (elec/sanitaria — paralelo con ladrillo)
                              ↓
                    Cielorraso → Pintura interior [CAMINO CRÍTICO TÍPICO]
                              Pintura exterior (paralelo)
```

## Camino Crítico (CPM)

El camino crítico es la cadena de tareas con **holgura = 0 días**. Mostrá al usuario cuáles son y por qué no pueden retrasarse.

## Output al usuario

Mostrá un Gantt simplificado en texto + tabla resumen:

```
📅 CRONOGRAMA — {nombre proyecto}
Inicio: {fecha} | Fin estimado: {fecha} | Duración: {N} días hábiles

GANTT (semanas):
Sem 1    Sem 2    Sem 3    Sem 4    Sem 5    Sem 6
[████]   .        .        .        .        .       Replanteo/Excavación
[████████]        .        .        .        .       Estructura (H°A)
.        [████████████]    .        .        .       Ladrillo/Cubierta
.        .        [████████████]    .        .       Revoques
.        .        .        .  [████████████]         Pisos/Terminaciones
.        .        .        .        .  [████]         ⚠ CRÍTICO: Pintura

🔴 Camino crítico: {lista de tareas críticas}

| Tarea | Días | Inicio | Fin | Holgura |
|---|---|---|---|---|
...

✅ Cronograma guardado en outputs/cronograma.json
```

## Guardado

Siempre actualizá `./outputs/estado-proyecto.json` con:
```json
"cronograma_resumen": {
  "duracion_total_dias": N,
  "fecha_inicio": "YYYY-MM-DD",
  "fecha_fin_estimada": "YYYY-MM-DD",
  "camino_critico": ["tarea1", "tarea2"]
}
```
