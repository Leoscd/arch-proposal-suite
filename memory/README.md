# Sistema de Memoria — Arch Proposal Suite

Memoria estratificada en 3 capas. Solo la capa caliente está siempre en contexto.

## Capas

| Capa | Archivo | TTL | En contexto |
|---|---|---|---|
| Caliente | `memoria_reciente.md` | 1 semana | Siempre |
| Media | `semana_anterior.md` | 2 semanas | Si es relevante |
| Fría | `historial/semana_YYYY-MM-DD.md` | hasta 4 semanas | Solo si se pide |

## Proceso del viernes (cierre semanal)

1. Leer `memoria_reciente.md` → extraer resumen ≤15 líneas
2. Mover `semana_anterior.md` → `historial/semana_YYYY-MM-DD.md`
3. Escribir resumen en nuevo `semana_anterior.md`
4. Resetear `memoria_reciente.md` vacío
5. `git add memory/historial/` → `git commit` → `git push`

## Reglas de expiración

- Archivos en `historial/` con más de 28 días → se pushean a GitHub y se eliminan localmente
- El historial en GitHub es la fuente de verdad para reconstrucción
- `sesion_activa.json` (en outputs/) dura solo la sesión — no es memoria

## Reconstrucción

Si necesitás acceder a una semana archivada:
- Si está en `historial/`: Claude la lee directamente
- Si solo está en GitHub: `git pull` trae el archivo
- Si el usuario la sube manualmente: Claude la procesa y reconstruye el contexto
