---
name: memoria_reciente
description: Actividad de la semana actual — se archiva cada viernes
type: project
ttl: weekly
capa: caliente
---

# Memoria Reciente — Semana activa

> Esta capa se resetea cada viernes. El contenido se resume en `semana_anterior.md` antes de archivar.

## Semana del 2026-03-17 al 2026-03-21

### Sesión 2026-03-21 — Plan de Mejoras v2 completado (73 tareas)

**Decisiones clave:**
- Sistema de memoria en 3 capas implementado: caliente (semanal) / media (2 semanas) / fría (historial/ → GitHub los viernes)
- `sesion_activa.json` como contrato de scope entre orquestador y scripts
- `verify_scope.py`: audita coherencia cronograma vs rubros seleccionados usando normalización NFD
- Bug crítico cronograma resuelto: generate_schedule.py generaba 19 tareas para todos los rubros aunque solo se seleccionara uno. Fix: modos `rubro_puntual` (4 tareas) vs `obra_completa` (11 bloques)

**Archivos creados/modificados:**
- `scripts/generate_schedule.py`: refactor completo con lectura de sesion_activa.json
- `scripts/calculate_budget.py`: método `calcular_desde_seleccion(rubros_ids)`
- `scripts/_cronograma_por_rubro.py`: nuevo módulo de filtrado por keywords
- `scripts/generate_computo.py`: genera computo_materiales.json
- `scripts/generate_calendario.py`: curva S real con 5 semanas, $23.4M ARS total
- `scripts/generate_certificate.py`: eliminado mock $1.5M, curva S dinámica
- `scripts/server.py`: Flask puerto 8080, 8 endpoints, CORS habilitado
- `outputs/dashboard_inversor.html` (29KB): solo lectura, curva S canvas nativo
- `outputs/dashboard_arquitecto.html` (56KB): 9 secciones, formularios POST
- `install.sh`: one-liner clone + install + launch, compatible macOS/Linux/WSL
- `requirements.txt`: flask>=2.3.0, Pillow>=10.0.0

**Estado del sistema:** Listo para uso real. Server en localhost:8080.

**Pendientes detectados en prueba (ver revision.md):**
1. CRÍTICO: `scrollTo(id)` choca con `window.scrollTo` nativo — fix: renombrar a `navegarA(id)` en dashboard_arquitecto.html línea 1171 + nav-items 807-832
2. Cronograma: ajustes visuales a definir con el usuario
3. Curva S: ajustes visuales a definir con el usuario
4. Fase 8 pendiente: carga de tickets por foto (Python + Anthropic vision API)
