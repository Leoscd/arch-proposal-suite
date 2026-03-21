# Plan de Mejoras — Arch Proposal Suite
> Documento de auditoría y seguimiento de tareas pendientes.
> Cada tarea tiene un estado: `[ ]` pendiente · `[x]` completada · `[~]` en progreso · `[!]` bloqueada

---

## FASE 1 — Fundación de Scope
> Objetivo: crear el contrato formal entre lo que el usuario pide y lo que ejecutan los scripts.
> Todas las fases siguientes dependen de esta.

### 1.1 Crear `outputs/sesion_activa.json`
- [x] Definir estructura del archivo
- [x] El orquestador (CLAUDE.md) lo escribe ANTES de llamar cualquier script
- [x] Si no existe, los scripts usan modo `"obra_completa"` como fallback

**Estructura esperada:**
```json
{
  "rubros_seleccionados": ["03_ESTRUCTURAS"],
  "modo_alcance": "rubro_puntual | rubros_multiples | obra_completa",
  "alcance_descripcion": "Solo estructuras resistentes (HA + metálica)",
  "fecha_sesion": "2026-05-01",
  "personal": { "oficiales": 3, "ayudantes": 3 }
}
```

---

### 1.2 Agregar `keywords_cronograma` en `references/rubros.json`
- [x] Agregar campo `keywords_cronograma` a cada rubro del catálogo
- [x] Estas keywords permiten que el verificador de scope identifique a qué rubro pertenece cada tarea

**Ejemplo:**
```json
{
  "id": "03_ESTRUCTURAS",
  "nombre": "Estructuras Resistentes",
  "keywords_cronograma": ["columna", "viga", "losa", "base", "zapata", "encadenado", "estructura metalica", "ipn", "perfil c"]
}
```

---

### 1.3 Crear `scripts/verify_scope.py`
- [x] Lee `sesion_activa.json` (rubros pedidos)
- [x] Lee `outputs/cronograma.json` (tareas generadas)
- [x] Cruza cada tarea del cronograma contra las keywords del rubro seleccionado
- [x] Genera `outputs/auditoria_scope.json` con el resultado

**Estructura de salida:**
```json
{
  "coherente": true,
  "rubros_pedidos": ["03_ESTRUCTURAS"],
  "tareas_fuera_de_scope": [],
  "elementos_sin_tarea": [],
  "warnings": []
}
```

- [x] Agregar en `CLAUDE.md`: después de generar cronograma, siempre ejecutar `verify_scope.py` y mostrar resultado al usuario

---

### 1.4 Actualizar `CLAUDE.md` — flujo de selección de rubros
- [x] Antes de calcular presupuesto o cronograma, el orquestador presenta la lista de rubros de `references/rubros.json`
- [x] Espera selección del usuario (1 rubro, varios, o "toda la obra")
- [x] Escribe la selección en `sesion_activa.json`
- [x] Solo entonces llama al agente correspondiente

---

## FASE 2 — Cronograma por Alcance (bug crítico)
> Problema actual: `cronograma.json` tiene 19 tareas de obra completa aunque se pidió solo estructuras.

### 2.1 Corregir bloque `__main__` de `scripts/generate_schedule.py`
- [x] Leer `outputs/sesion_activa.json` al inicio
- [x] Si `modo_alcance == "rubro_puntual"` → solo incluir tareas del rubro seleccionado
- [x] Si `modo_alcance == "obra_completa"` → incluir todos los rubros como bloques globales (sin desglose interno)
- [x] Si `sesion_activa.json` no existe → comportamiento actual como fallback (con warning en consola)

---

### 2.2 Dos modos de cronograma según alcance

**Modo rubro puntual** → desglose detallado de tareas internas
```
Columnas HA        → 1.3 días → $3.937.456
Bases y Zapatas    → 1.5 días → $6.188.214
Vigas Arriostre    → 1.2 días → $3.418.573
...
```

**Modo obra completa** → rubros como bloques globales
```
03 Estructuras     → 6 días  → $31.492.498
04 Mamposterías    → 8 días  → $XX.XXX.XXX
05 Cubierta        → 4 días  → $XX.XXX.XXX
...
```

- [x] Implementar lógica de modo en `generate_schedule.py`
- [x] Agregar campo `"modo"` en el JSON exportado del cronograma

---

### 2.3 Agregar campo `"alcance"` en el JSON exportado del cronograma
- [x] El archivo `cronograma.json` debe registrar siempre qué se incluyó

**Estructura a agregar:**
```json
{
  "alcance": {
    "rubros_incluidos": ["03_ESTRUCTURAS"],
    "modo": "rubro_puntual",
    "descripcion": "Solo estructuras resistentes"
  },
  ...
}
```

---

### 2.4 Agregar `costo_total_ars` en cada tarea del cronograma
- [x] Cuando se genera el cronograma junto con el presupuesto, enlazar cada tarea con su costo
- [x] El enlace se hace por nombre de elemento (matching fuzzy o por ID de rubro)
- [x] Si no hay presupuesto calculado para esa tarea, el campo queda en `null`

**Ejemplo en cada tarea:**
```json
{
  "elemento": "Columnas HA (66 un. / 132.45 ml)",
  "duracion_dias": 1.3,
  "costo_total_ars": 3937456.88,
  "metricas": { "volumen_m3": 5.83, "acero_kg": 700 },
  ...
}
```

---

## FASE 3 — Selección de Rubros Interactiva
> Objetivo: que el usuario elija qué rubros calcular antes de ejecutar cualquier script.

### 3.1 Agregar método `calcular_desde_seleccion()` en `scripts/calculate_budget.py`
- [x] Recibe lista de IDs de rubros (ej. `["03_ESTRUCTURAS", "04_MAMPOSTERIA"]`)
- [x] Mapeo explícito entre ID de rubro y función de cálculo correspondiente
- [x] Llama internamente solo a los `calc_*` relevantes

---

### 3.2 Crear `scripts/_cronograma_por_rubro.py`
- [x] Análogo al existente `_calc_estructuras.py` pero para el cronograma
- [x] Lee `sesion_activa.json` para saber qué rubros incluir
- [x] Genera solo las tareas correspondientes

---

### 3.3 Convención de nombres de archivos por alcance
- [x] Cada presupuesto genera un archivo con nombre descriptivo:
  - `presupuesto_03_estructuras.json`
  - `presupuesto_04_mamposteria.json`
  - `presupuesto_obra_completa.json`
- [x] Nunca sobreescribir — siempre versionar o nombrar por rubro
- [x] Actualizar referencias en `estado-proyecto.json` cuando se genera un nuevo presupuesto

---

## FASE 4 — Cómputo de Materiales
> Objetivo: mostrar cantidades físicas de cada elemento para auditoría y corrección.

### 4.1 Generar `outputs/documentacion/computo_materiales.json`
- [x] Extraer las cantidades de `presupuesto_[rubro].json` → campo `metricas` de cada ítem
- [x] Agregar cantidades de `estado-proyecto.json` → campo `cantidades_de_plano`
- [x] Consolidar en un único archivo de cómputo

**Estructura esperada:**
```json
{
  "rubro": "03_ESTRUCTURAS",
  "elementos": [
    {
      "nombre": "Bases y Zapatas HA",
      "unidades": 35,
      "volumen_m3": 13.48,
      "acero_kg": 1078,
      "encofrado_m2": 0,
      "puntales": 0,
      "costo_total_ars": 6188214.02
    },
    {
      "nombre": "Columnas HA",
      "unidades": 66,
      "longitud_ml": 132.45,
      "volumen_m3": 5.83,
      "acero_kg": 700,
      "encofrado_m2": 29,
      "puntales": 0,
      "costo_total_ars": 3937456.88
    }
  ],
  "estructura_metalica": {
    "perfiles_c_100x50x15_ml": 236.04,
    "ipn_120_ml": 38.69,
    "ipn_160_ml": 9.62,
    "ipn_240_ml": 11.74,
    "ipn_280_ml": 8.05
  },
  "totales": {
    "hormigon_m3": 35.01,
    "acero_total_kg": 3148,
    "costo_total_ars": 31492498
  }
}
```

---

### 4.2 Agregar sección "Cómputo" en el dashboard del arquitecto
- [ ] Tabla expandible por elemento con todas las cantidades físicas
- [ ] Columnas: elemento, unidades, volumen/longitud/m2, acero kg, costo unitario, costo total
- [ ] Botón "Corregir cantidad" que abre un campo editable → recalcula el costo en tiempo real
- [ ] Exportar cómputo como HTML imprimible

---

## FASE 5 — Calendario de Certificados Semanales
> Objetivo: calcular cuánto presupuesto teórico corresponde a cada semana y generar los certificados correctamente.

### 5.1 Corregir `scripts/generate_certificate.py`
- [x] Eliminar el mock hardcodeado de `presupuesto_teorico_semanal = 1500000.00`
- [x] Implementar `calcular_curva_s(cronograma, presupuesto)`:
  - Itera las tareas del cronograma
  - Calcula en qué semana(s) cae cada tarea por fecha de inicio/fin
  - Distribuye el `costo_total_ars` de cada tarea proporcionalmente entre las semanas que ocupa
  - Resultado: `{ "semana_1": monto, "semana_2": monto, ... }`

---

### 5.2 Crear `outputs/documentacion/calendario_certificados.json`
- [x] Se genera automáticamente al finalizar el cronograma
- [x] Una entrada por semana con: fechas, presupuesto teórico, tareas activas, estado del certificado

**Estructura:**
```json
{
  "rubros_incluidos": ["03_ESTRUCTURAS"],
  "total_semanas": 2,
  "semanas": [
    {
      "numero": 1,
      "fecha_inicio": "2026-05-01",
      "fecha_fin": "2026-05-07",
      "presupuesto_teorico_ars": 18500000,
      "tareas_activas": ["Bases y Zapatas HA", "Columnas HA"],
      "certificado_generado": false,
      "archivo_certificado": null
    },
    {
      "numero": 2,
      "fecha_inicio": "2026-05-08",
      "fecha_fin": "2026-05-14",
      "presupuesto_teorico_ars": 12992498,
      "tareas_activas": ["Vigas HA", "Estructura Metálica"],
      "certificado_generado": false,
      "archivo_certificado": null
    }
  ]
}
```

---

### 5.3 Actualizar workflow `cierre_semana.md`
- [x] Leer `calendario_certificados.json` para identificar la semana vigente por fecha actual
- [x] Usar el `presupuesto_teorico_ars` de esa semana (no el mock)
- [ ] Al generar el certificado, actualizar `certificado_generado: true` y `archivo_certificado` con la ruta
- [ ] Guardar snapshot en `outputs/documentacion/certificados/certificado_semana_N.html`

---

## FASE 6 — Servidor Local y Dashboards
> Objetivo: dos dashboards servidos por un servidor Python local dentro de Claude Code.

### 6.1 Crear `scripts/server.py`
- [x] Framework: Flask o FastAPI (~120 líneas)
- [x] Sirve los archivos HTML estáticos
- [x] Expone endpoints REST que leen/escriben los JSON del proyecto

**Endpoints mínimos:**
```
GET  /api/estado           → estado-proyecto.json
GET  /api/presupuesto      → outputs/presupuesto_*.json
GET  /api/cronograma       → outputs/cronograma.json
GET  /api/calendario       → outputs/documentacion/calendario_certificados.json
GET  /api/certificados     → lista outputs/documentacion/certificados/
GET  /api/computo          → outputs/documentacion/computo_materiales.json

POST /api/gasto            → agrega gasto a gastos_reales en estado-proyecto.json
POST /api/avance           → registra avance semanal
```

- [ ] Al recibir POST, escribir nota en `memory/project_arch_proposal.md` con fecha y descripción del evento (para que Claude lo vea en la próxima sesión)

---

### 6.2 Configurar `launch.json`
- [x] Agregar entrada `"servidor-obra"` que ejecute `python scripts/server.py`
- [x] Puerto: 8080

---

### 6.3 Crear `outputs/dashboard_inversor.html`

**Vista para el cliente/financiador — solo lectura:**
- [x] Barra de progreso general: `XX% ejecutado`
- [x] Semáforo financiero: verde / amarillo / rojo según gastos vs presupuesto
- [x] Tabla de certificados semanales: número, período, monto certificado, estado
- [x] Gráfico curva S: planificado (línea azul) vs real (línea verde)
- [x] Resumen de gastos: total presupuestado vs total ejecutado vs diferencia
- [x] Sin botones de carga — solo lectura
- [x] Lenguaje financiero, sin tecnicismos de obra

---

### 6.4 Crear `outputs/dashboard_arquitecto.html`

**Vista operativa para el director de obra — lectura + carga:**
- [x] Todo lo del dashboard inversor, más:
- [x] Panel de tareas de la semana activa con estado (pendiente / en curso / terminado)
- [x] Botón "Registrar avance" → formulario que hace POST a `/api/avance`
- [x] Botón "Cargar ticket/factura" → formulario que hace POST a `/api/gasto`
- [x] Tabla de tickets cargados con emisor, fecha, materiales, monto
- [x] Sección cómputo de materiales con cantidades verificables (FASE 4)
- [x] Alertas: tareas con holgura cero, materiales sin precio, desvíos > 10%
- [x] Botón "Generar certificado semana N" → llama al agente o script

---

## FASE 7 — Estructura de Carpetas Final
> Reorganizar outputs para que toda la documentación técnica quede ordenada.

### 7.1 Nueva estructura de `outputs/` ✓
```
outputs/
├── documentacion/
│   ├── computo_materiales.json
│   ├── computo_materiales.html        ← versión imprimible
│   ├── presupuesto_03_estructuras.json
│   ├── presupuesto_obra_completa.json
│   ├── cronograma_03_estructuras.json
│   ├── cronograma_obra_completa.json
│   ├── curva_inversion.json
│   ├── curva_inversion.html           ← gráfico standalone
│   └── certificados/
│       ├── certificado_semana_1.html
│       ├── certificado_semana_2.html
│       └── ...
├── calendario_certificados.json
├── sesion_activa.json
├── auditoria_scope.json
├── estado-proyecto.json
├── dashboard_arquitecto.html
├── dashboard_inversor.html
└── snapshots/
    ├── semana_1.json
    └── semana_2.json
```

- [x] Actualizar todas las referencias de rutas en los scripts Python
- [x] Actualizar `CLAUDE.md` con las nuevas rutas
- [x] Agregar `.gitignore` entries para `sesion_activa.json` (es temporal, no debe commitearse)

---

## Dependencias entre fases

```
FASE 1  ←── base de todo
  ↓
FASE 2  ←── requiere sesion_activa.json (Fase 1)
  ↓
FASE 3  ←── requiere sesion_activa.json (Fase 1)
FASE 4  ←── puede hacerse en paralelo con Fase 2 y 3
  ↓
FASE 5  ←── requiere cronograma con costos por tarea (Fase 2.4)
  ↓
FASE 6  ←── requiere documentos generados (Fases 4 y 5)
FASE 7  ←── puede hacerse en cualquier momento (reorganización)
```

---

## Archivos clave a modificar

| Archivo | Qué cambia | Fase |
|---|---|---|
| `CLAUDE.md` | Flujo de selección de rubros + regla de verify_scope | 1.4 |
| `references/rubros.json` | Agregar campo `keywords_cronograma` | 1.2 |
| `scripts/generate_schedule.py` | Leer `sesion_activa.json`, agregar `alcance` y `costo_total_ars` | 2.1 / 2.3 / 2.4 |
| `scripts/calculate_budget.py` | Agregar `calcular_desde_seleccion()` | 3.1 |
| `scripts/generate_certificate.py` | Eliminar mock, implementar curva S real | 5.1 |
| `.claude/workflows/cierre_semana.md` | Leer calendario real en vez de mock | 5.3 |

**Archivos nuevos a crear:**

| Archivo | Descripción | Fase |
|---|---|---|
| `outputs/sesion_activa.json` | Contrato scope entre agente y scripts | 1.1 |
| `scripts/verify_scope.py` | Verifica coherencia cronograma vs scope | 1.3 |
| `scripts/_cronograma_por_rubro.py` | Cronograma filtrado por rubro | 3.2 |
| `scripts/server.py` | Servidor Flask/FastAPI local | 6.1 |
| `outputs/documentacion/computo_materiales.json` | Cómputo con cantidades físicas | 4.1 |
| `outputs/documentacion/calendario_certificados.json` | Calendario de certificados semanales | 5.2 |
| `outputs/dashboard_inversor.html` | Dashboard cliente (solo lectura) | 6.3 |
| `outputs/dashboard_arquitecto.html` | Dashboard director de obra (lectura + carga) | 6.4 |

---

*Generado el 2026-03-16 — Arch Proposal Suite v2 Planning*
