# Arch Proposal Suite

Sistema multi-agente para la gestión integral de proyectos de arquitectura y obra. Corre dentro de **Claude Code Desktop** y coordina 5 agentes especializados que van desde el análisis de planos hasta la presentación al cliente.

---

## Requisitos

| Herramienta | Versión mínima | Para qué |
|---|---|---|
| [Claude Code](https://claude.ai/code) | Última | Runtime del sistema |
| Python | 3.10+ | Scripts de cálculo |
| Git | Cualquiera | Control de versiones |
| GitHub CLI (`gh`) | Opcional | Publicar en GitHub Pages |

---

## Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/Leoscd/arch-proposal-suite.git
cd arch-proposal-suite

# 2. Abrir en Claude Code Desktop
claude .
```

Eso es todo. No hay dependencias externas que instalar — los scripts usan únicamente la librería estándar de Python.

---

## Cómo usar el sistema

### Empezar un proyecto nuevo

Escribí en el chat de Claude Code:

```
/arch proposal Casa García
```

El sistema te guía paso a paso por 5 etapas:

```
PASO 1 — Documentación   →  Analizá planos o fotos de la obra
PASO 2 — Costos          →  Cargá tickets y facturas de materiales
PASO 3 — Cronograma      →  Generá el Gantt con camino crítico
PASO 4 — Presupuesto     →  Calculá el costo directo total
PASO 5 — Presentación    →  Publicá la landing para el cliente
```

Al terminar tenés:
- `outputs/reporte_{fecha}.html` — Presupuesto + Cronograma imprimible en A4
- `outputs/cronograma.json` — Datos del Gantt
- `estado-proyecto.json` — Estado completo del proyecto

---

### Analizar un plano o foto

**PDF de Revit o AutoCAD** — arrastralo al chat y escribí:

```
Analizá este plano y extraé las métricas
```

**Foto de la obra** — adjuntala al chat y escribí:

```
Analizá esta foto — el frente del lote mide 10 metros
```

> Para fotos necesitás dar una referencia métrica.
> Para PDFs de Revit/AutoCAD el sistema lee las cotas directamente.

---

### Cargar un ticket o factura

Adjuntá la foto del ticket y escribí:

```
Auditá este ticket
```

El sistema extrae los ítems, compara contra el presupuesto y muestra el desvío en 🟢 verde / 🟡 amarillo / 🔴 rojo.

---

### Cierre semanal — cada viernes

```
/cierre-semana
```

Ejecuta el ritual completo de fin de semana:

1. Consolida todos los tickets de la semana
2. Confirma el avance real del cronograma con vos
3. Genera `outputs/certificado_semana_N.md` con semáforo financiero
4. Guarda el snapshot en `outputs/snapshots/semana_N.json`
5. Actualiza la landing del cliente
6. Ofrece publicar en GitHub Pages

---

### Publicar el dashboard al cliente

Después del cierre semanal, si aprobás publicar:

```
/deploy-github
```

El sistema verifica que tenés todo configurado (GitHub CLI, autenticación, repo, GitHub Pages) y publica la landing en:

```
https://Leoscd.github.io/arch-proposal-suite
```

El cliente accede desde cualquier dispositivo, sin login.

---

## Estructura del proyecto

```
arch-proposal-suite/
│
├── .claude/
│   ├── agents/          # Los 5 agentes de dominio
│   │   ├── agente-documentacion.md
│   │   ├── agente-costos.md
│   │   ├── agente-cronograma.md
│   │   ├── agente-presupuestos.md
│   │   └── agente-inversor.md
│   └── workflows/       # Flujos de trabajo orquestados
│       ├── analizar_foto.md
│       ├── auditar_ticket.md
│       ├── cierre_semana.md
│       └── dashboard_ui_guidelines.md
│
├── skills/              # Comandos invocables con /nombre
│   ├── arch/            →  /arch proposal [nombre]
│   ├── arch-vision/     →  análisis de planos y fotos
│   ├── arch-scheduler/  →  generación de cronograma
│   ├── arch-budget/     →  cálculo de presupuesto por rubros
│   └── deploy-github/   →  publicar en GitHub Pages
│
├── scripts/             # Scripts Python (corren solos o via agentes)
│   ├── calculate_budget.py   — motor de cálculo por rubros
│   ├── generate_schedule.py  — Gantt + CPM
│   ├── build_report.py       — reporte HTML A4
│   ├── audit_budget.py       — desvíos real vs presupuestado
│   ├── build_landing.py      — landing del cliente
│   ├── generate_certificate.py
│   ├── vision_receipt_parser.py
│   └── parser_precios_noa.py
│
├── dashboard/           # Dashboard interactivo (Next.js + Tailwind)
├── templates/           # Plantillas HTML (reporte A4 + landing cliente)
├── references/          # Base de precios NOA + rubros de construcción
│
├── outputs/             # Todo lo que genera el sistema
│   ├── cronograma.json
│   ├── snapshots/       # Un snapshot por semana cerrada
│   ├── auditorias/      # Reportes de desvío por ticket
│   └── landing/         # Landing del cliente (generada, no commitear)
│
├── inputs/              # Acá subís tus planos, fotos y tickets
├── estado-proyecto.json # Fuente única de verdad del proyecto activo
└── CLAUDE.md            # Instrucciones del orquestador principal
```

> **Importante:** nunca modifiques archivos dentro de `inputs/` manualmente.
> Subí los archivos ahí y dejá que los agentes los procesen.

---

## Scripts independientes (sin Claude Code)

Los scripts funcionan solos desde la terminal:

```bash
# Presupuesto completo para 80 m²
python3 scripts/build_report.py --completo --m2 80 --proyecto "Casa García" --localidad "Tucumán"

# Solo cronograma con fecha de inicio
python3 scripts/build_report.py --seccion cronograma --m2 80 --fecha-inicio 2025-06-01

# Auditar gastos de la semana 1
python3 scripts/audit_budget.py --semana 1

# Auditar por rango de fechas
python3 scripts/audit_budget.py --desde 2025-04-01 --hasta 2025-04-07

# Compilar landing del cliente
python3 scripts/build_landing.py --estudio "Estudio García" --resumen "El proyecto avanza en tiempo y forma."
```

---

## Flujo completo de un proyecto

```
1. Recibís el encargo del cliente
         ↓
2. Subís el plano PDF a inputs/
         ↓
3. /arch proposal "Nombre del proyecto"
         ↓
4. Claude analiza, presupuesta y cronograma
         ↓
5. Cada compra de materiales → auditás el ticket
         ↓
6. Cada viernes → /cierre-semana
         ↓
7. Aprobás la publicación
         ↓
8. El cliente ve el dashboard actualizado en su URL
```

---

## Moneda y región

- Todos los precios en **Pesos Argentinos (ARS)**
- Base de precios: región **NOA — Noroeste Argentino**
- Si un insumo está en USD, el sistema busca la cotización del día

---

## Soporte

Desarrollado con [Claude Code](https://claude.ai/code).
Issues y sugerencias: [github.com/Leoscd/arch-proposal-suite/issues](https://github.com/Leoscd/arch-proposal-suite/issues)
