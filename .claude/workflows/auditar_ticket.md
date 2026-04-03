---
description: Audita comprobantes de obra (facturas, remitos, pagos de mano de obra) y registra el gasto en estado-proyecto.json
---
# Workflow: Auditar Ticket (Agente Costos & Presupuestos)

Este workflow activa tus capacidades combinadas como **Agente Costos** y **Agente Presupuestos**. Tu objetivo es leer un comprobante de obra (foto de ticket, factura, remito o recibo de mano de obra), identificar su tipo, extraer los datos y registrarlos con el campo `tipo` correcto en `gastos_reales[]`.

---

## Paso 1 — Identificar el Tipo de Comprobante

Antes de extraer cualquier dato, determina el tipo analizando el texto visible en la imagen:

| Señales en el documento | Tipo asignado |
|---|---|
| Contiene "FACTURA", "FCB", "FCA", "FC A", "FC B", "CUIT" | `factura` |
| Contiene "REMITO", "REM." y **no** menciona IVA ni total | `remito` |
| Contiene "RECIBO", "JORNAL", "CUADRILLA", "OFICIAL", "AYUDANTE" | `pago_mo` |
| No se puede determinar con certeza | `factura` (default) |

> Si el comprobante muestra señales de más de un tipo, prevalece: `factura` > `pago_mo` > `remito`.

---

## Paso 2 — Regla de Ilegibilidad

Si la foto es borrosa, está cortada, o no se distinguen datos clave de forma segura, DETENTE INMEDIATAMENTE y avisa:

`"⚠️ Error de lectura: El comprobante no es legible. Por favor, asegúrate de que foco, cantidades y precios sean visibles."`

---

## Paso 3 — Extracción de Datos Según Tipo

### Si tipo = `factura`
Extrae:
- `emisor`: nombre del proveedor o corralón
- `cuit`: número de CUIT del emisor (formato XX-XXXXXXXX-X)
- `numero_factura`: número completo del comprobante (ej. "0001-00012345")
- `fecha`: fecha del comprobante (YYYY-MM-DD)
- `tiene_iva`: `true` si discrimina IVA (Factura A), `false` si es B/C/Ticket
- `items`: lista de ítems con `descripcion`, `cantidad`, `unidad`, `precio_unit`, `subtotal`
- `subtotal_neto`: monto antes de IVA
- `total_iva`: monto de IVA (0.0 si no aplica)
- `total_ars`: monto total del comprobante en ARS
- `precio_pendiente`: siempre `false`

### Si tipo = `remito`
Extrae:
- `proveedor`: nombre del proveedor
- `numero_remito`: número del remito
- `fecha`: fecha del remito (YYYY-MM-DD)
- `items`: lista de ítems con `descripcion`, `cantidad`, `unidad`. Precio puede ser 0 si no figura.
- `total_ars`: monto total si figura; si no figura, usar `0.0`
- `precio_pendiente`: `true` si no hay precios en el documento, `false` si están presentes
- `tiene_iva`: siempre `false` (los remitos no son comprobantes fiscales)

> Los remitos registran **entrega de material**, no obligación de pago. El precio puede llegar con la factura posterior.

### Si tipo = `pago_mo` (mano de obra)
Extrae:
- `trabajador`: nombre completo del trabajador o cuadrilla
- `categoria`: categoría laboral (ej. "Oficial", "Ayudante", "Medio Oficial")
- `periodo`: período trabajado (ej. "2026-03-01 / 2026-03-15")
- `horas`: cantidad de horas trabajadas (usar 0 si se trabaja por jornales)
- `jornales`: cantidad de jornales (usar 0 si se trabaja por horas)
- `importe`: importe total en ARS
- `total_ars`: igual a `importe`
- `tiene_iva`: siempre `false`
- `precio_pendiente`: siempre `false`

---

## Paso 4 — Regla de Información Faltante

Si el material o ítem comprado *no existe* en la base de datos de precios (`./references/precios_materiales.csv`) ni en el presupuesto base, avisa:

`"⚠️ Material no previsto: El ítem '{nombre_item}' no está listado en nuestro presupuesto original. ¿Quieres agregarlo como gasto extra (Adicional)?"`

---

## Paso 5 — Cruce contra Presupuesto (solo para `factura` y `pago_mo`)

- Lee `./outputs/estado-proyecto.json` y `./outputs/cronograma.json`.
- Compara cantidades compradas contra el total presupuestado para esos rubros.
- Compara precio unitario pagado contra la base de precios (`./references/precios_materiales.csv`).

> Para `remito` con `precio_pendiente: true`: omitir el cruce de precios. Solo registrar el movimiento de materiales.

---

## Paso 6 — Escribir en `gastos_reales[]` de `estado-proyecto.json`

Agregar el comprobante al array `gastos_reales` de `./outputs/estado-proyecto.json` con el schema unificado:

```json
{
  "id": "TICK-YYYYMMDDHHMMSS",
  "tipo": "factura | remito | pago_mo",
  "proveedor": "nombre del emisor",
  "fecha": "YYYY-MM-DD",
  "fecha_carga": "YYYY-MM-DD HH:MM:SS",
  "tiene_iva": true,
  "items": [
    {"descripcion": "...", "cantidad": 0, "unidad": "bolsa", "precio_unit": 0.0, "subtotal": 0.0}
  ],
  "subtotal_neto": 0.0,
  "total_iva": 0.0,
  "total_ars": 0.0,
  "precio_pendiente": false,
  "semana": 1
}
```

El campo `semana` se calcula comparando la `fecha` del ticket contra `cronograma.json.configuracion.fecha_inicio`. Los documentos sin campo `tipo` se tratan como `"factura"` para compatibilidad.

---

## Paso 7 — Archivos de Salida

1. Crear o actualizar `./outputs/auditorias/auditoria_{fecha}_{proveedor}.json` con el detalle completo.
2. Modificar `./outputs/estado-proyecto.json` agregando el gasto a `gastos_reales[]`.
3. Responder en el chat con tabla según tipo:

**Para `factura`:**
| Ítem | Precio Pagado | Precio Presup. | Desvío % | Cant. Consumida | Cant. Presup. | Desvío % |
|---|---|---|---|---|---|---|

**Para `remito`:**
| Ítem | Cantidad Recibida | Unidad | Precio | Estado |
|---|---|---|---|---|
Indicar "Sin precio — pendiente de factura" si `precio_pendiente: true`.

**Para `pago_mo`:**
| Trabajador | Categoría | Período | Horas/Jornales | Importe |
|---|---|---|---|---|

---

## Paso 8 — Regla de Error de Sistema

Si falta contexto del proyecto (`estado-proyecto.json` no existe o no tiene datos base), lanzar:

`"🚨 Error de Auditoría: No encuentro un presupuesto base para comparar. Ejecuta primero los agentes de Documentación y Cronograma."`
