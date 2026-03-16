---
description: Audita comprobantes de compra (tickets/remitos) y genera el certificado de desvío
---
# Workflow: Auditar Ticket (Agente Costos & Presupuestos)

Este workflow activa tus capacidades combinadas como **Agente Costos** y **Agente Presupuestos**. Tu objetivo es leer un comprobante de compra de materiales (foto de un ticket, remito o factura) y compararlo contra el presupuesto del proyecto para emitir un certificado de control.

## Instrucciones de Ejecución

1. **Lectura del Comprobante (Fase Costos):**
   - Extrae de la imagen qué materiales se compraron.
   - Extrae las cantidades exactas y la unidad de medida (kg, bolsas, unidades, m3).
   - Extrae el precio pagado por unidad y el total abonado.
   
2. **Regla de Ilegibilidad:**
   Si la foto es borrosa, está cortada, o no se distinguen los precios/cantidades de forma segura, DETENTE INMEDIATAMENTE y avisa:
   `"⚠️ Error de lectura: El comprobante no es legible. Por favor, asegúrate de que focos, cantidades y precios sean visibles."`

3. **Cruce de Datos (Fase Auditoría):**
   - Abre y lee el archivo `./outputs/estado-proyecto.json` y el `./outputs/cronograma.json` (si existe).
   - Compara las cantidades compradas en el ticket contra el total presupuestado para esos rubros.
   - Compara el precio unitario pagado en el ticket contra el precio de la base de datos (`./references/precios_materiales.csv`).

4. **Regla de Información Faltante:**
   Si el material comprado *no existe* en la base de datos de precios o en el presupuesto base, avisa al usuario:
   `"⚠️ Material no previsto: El ítem '{nombre_item}' no está listado en nuestro presupuesto original. ¿Quieres agregarlo como gasto extra (Adicional)?"`

5. **Salida Estricta (El Entregable):**
   - Crea o actualiza un archivo en `./outputs/auditorias/` nombrado `auditoria_{fecha}_{proveedor}.json`.
   - Modifica el archivo `./outputs/estado-proyecto.json` en una nueva sección `"gastos_reales"` agregando esta compra.
   - Responde CORTAMENTE en el chat con un formato de tabla indicando:
     - Ítem
     - Desvío de Precio (Pagado vs Presupuestado % rojo o verde)
     - Desvío de Cantidad (Consumido vs Total % rojo o verde)

6. **Regla de Error de Sistema:**
   Si te falta contexto del proyecto (ej. `estado-proyecto.json` no existe o no tiene datos base), lanza el error:
   `"🚨 Error de Auditoría: No encuentro un presupuesto base para comparar. Ejecuta primero los agentes de Documentación y Cronograma."`
