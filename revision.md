# Revisión — Arch Proposal Suite
> Pendientes detectados en prueba del 2026-03-21. Retomar mañana.

---

## 1. Bug navegación dashboard arquitecto — CRÍTICO

**Problema:** Los botones del sidebar izquierdo no navegan a la sección correcta.

**Causa identificada:** La función custom `scrollTo(id)` del JS choca con la función nativa del browser `window.scrollTo(x, y)`. El `event.currentTarget` tampoco está garantizado dentro de un `onclick` inline.

**Fix:** Renombrar a `navegarA(id)` en todo el archivo y actualizar los `onclick` del sidebar.

**Archivo:** `outputs/dashboard_arquitecto.html` — línea 1171 (función) + líneas 807-832 (nav-items)

---

## 2. Ajustes pendientes en el cronograma — A DEFINIR

El usuario quiere ver cambios en la visualización del cronograma.

**Preguntar mañana:**
- ¿Qué información falta o sobra en la tabla actual?
- ¿Se quiere un Gantt visual (barras) o la tabla actual está bien?
- ¿Se muestran bien las fechas de inicio/fin por tarea?
- ¿El camino crítico está resaltado claramente?

---

## 3. Ajustes pendientes en la curva S — A DEFINIR

El usuario quiere cambios en el gráfico de curva de inversión.

**Preguntar mañana:**
- ¿Qué falta en el gráfico actual (canvas)?
- ¿Se quiere línea acumulada o por semana?
- ¿Agregar etiquetas de monto en cada punto?
- ¿Mostrar la línea real (gastos) aunque sea en 0?

---

## 4. Carga de tickets por foto — Fase 8 (pendiente diseñar)

**Situación actual:** El formulario de carga de tickets es 100% manual (usuario tipea emisor, fecha, materiales, monto).

**Lo que se quiere:** Subir foto del ticket → el sistema extrae los datos automáticamente → el usuario confirma.

**Cómo se haría:**
- Script Python que recibe la imagen y llama a la API de Anthropic con visión
- El script extrae: emisor, fecha, ítems, precios
- El dashboard pre-completa el formulario con esos datos para confirmación

**Pendiente:** Definir si la foto se sube desde el dashboard (endpoint en server.py) o directo desde Claude Code adjuntando la imagen.

---

## 5. Para arrancar mañana

```bash
# 1. Levantar el sistema
cd arch-proposal-suite && bash install.sh

# 2. Abrir dashboard en browser
http://localhost:8080/static/dashboard_arquitecto.html

# 3. Empezar por fix de navegación (item 1 arriba)
```

**Repo:** https://github.com/Leoscd/arch-proposal-suite
**Estado del plan:** `mejoras.md` — 73/73 tareas completadas ✓
