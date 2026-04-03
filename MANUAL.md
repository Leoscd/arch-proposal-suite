# Manual de Usuario — Arch Proposal Suite

## ¿Qué es este sistema?

El Arch Proposal Suite es un equipo de asistentes de IA que trabajan juntos para gestionar el presupuesto y la ejecución de una obra. Resuelve un problema concreto: saber en todo momento cuánto se gastó, cuánto se debería haber gastado, y si la obra va encaminada o desviada — sin tener que armar planillas a mano.

---

## Los 5 asistentes

| Asistente | Qué hace |
|---|---|
| **Documentación** | Lee los planos y extrae los metros cuadrados y cantidades base de la obra |
| **Costos** | Procesa fotos de facturas, remitos y recibos de mano de obra para registrar lo gastado |
| **Cronograma** | Genera el diagrama de Gantt y calcula el camino crítico según el personal disponible |
| **Presupuestos** | Audita los desvíos entre lo planificado y lo real; busca precios en internet si la base local está incompleta |
| **Inversor** | Publica el resumen del proyecto para el cliente en una landing o en Notion |

---

## Flujo para un proyecto nuevo

### Paso 1 — Conectar los planos
Copiar los archivos de la obra en la carpeta `inputs/`:
- Planos en PDF (AutoCAD o Revit)
- Planillas de cómputo exportadas
- Fotos de obra o renders (opcional)

El asistente de Documentación lee esa carpeta automáticamente y extrae los metros cuadrados cubiertos, semicubiertos y descubiertos, junto con las cantidades estimadas de cada rubro (excavación, cimientos, mampostería, etc.).

### Paso 2 — Generar el presupuesto
Escribir al sistema: `"generá el presupuesto"`. El asistente de Presupuestos tomará las métricas del Paso 1 y armará el presupuesto por rubro, guardándolo en `outputs/presupuesto_base.json`.

### Paso 3 — Generar el cronograma
Escribir: `"generá el cronograma"`. El sistema preguntará la cantidad de personal disponible (cantidad de oficiales y ayudantes). Con eso, el asistente de Cronograma arma el Gantt con fechas de inicio y fin por rubro.

### Paso 4 — Generar la curva de inversión
Desde la terminal, correr:
```
python3 scripts/generate_curva_inversion.py
```
Esto cruza el presupuesto con el cronograma y calcula cuánto dinero se debería gastar cada semana. El resultado queda en `outputs/curva_inversion.json` y es la referencia que se usa en cada cierre semanal.

---

## Flujo semanal

### Cargar gastos de la semana
Cada vez que llegue una factura, remito o se pague la cuadrilla, informárselo al asistente de Costos con la foto o el archivo:

> *"Cargá esta factura: [adjuntar imagen o PDF]"*

El sistema detecta automáticamente el tipo de documento (ver sección Tipos de documento), extrae los datos y los registra.

### Cerrar la semana
Al finalizar cada semana de obra, escribir `/cierre-semana`. El sistema ejecutará los siguientes pasos en orden:

1. Muestra todos los tickets cargados en la semana y pregunta si falta alguno
2. Pide confirmar qué tareas del cronograma quedaron realmente terminadas
3. Genera el certificado de obra de la semana (`outputs/certificado_semana_N.md`)
4. Guarda el estado de la semana como registro histórico en `outputs/snapshots/`
5. Actualiza el semáforo del proyecto
6. Pregunta si publicar la actualización en el Dashboard del cliente

### Interpretar el reporte de match (semáforo)
Después del cierre, el sistema compara lo que se gastó contra lo que el presupuesto preveía para esa semana, rubro por rubro. El semáforo resume esa comparación (ver sección El semáforo).

---

## Comandos de consola

| Comando | Para qué sirve |
|---|---|
| `python3 scripts/generate_curva_inversion.py` | Recalcula la distribución semanal del presupuesto (correr cada vez que cambie el cronograma o el presupuesto) |
| `python3 scripts/audit_budget.py --semana 1` | Genera el reporte de match de la Semana 1: cuánto se gastó vs. cuánto estaba previsto, por rubro |
| `python3 scripts/audit_budget.py --semana 1 --solo-auditoria` | Muestra solo el desvío global sin detalle de match por rubro |
| `python3 scripts/verify_scope.py` | Verifica que el cronograma cubra todos los rubros del presupuesto |

---

## Tipos de documento

El sistema distingue tres tipos de comprobante. Clasificarlos bien es importante para que el match semanal sea correcto.

| Tipo | Descripción | Ejemplo concreto |
|---|---|---|
| **Factura** | Obligación de pago por material o servicio, con número de comprobante y CUIT del proveedor | Factura del corralón por 10 bolsas de cemento y 2 barras de hierro 12mm |
| **Remito** | Entrega de material sin precio confirmado todavía — la factura llega después | Remito de entrega de arena gruesa; el precio se factura a fin de mes |
| **Pago MO** | Pago de mano de obra: oficial, ayudante, medio oficial o cuadrilla completa | Recibo de jornal semanal del oficial García y sus dos ayudantes |

Si el comprobante no tiene precio (remito sin valores), el sistema lo marca como `precio_pendiente` y no lo suma al gasto real hasta que llegue la factura correspondiente.

---

## El semáforo

El semáforo resume la salud financiera del período de un vistazo.

| Color | Condición | Qué hacer |
|---|---|---|
| **Verde** | Avance real >= avance planificado Y gasto real <= presupuestado + 5% | Continuar normalmente |
| **Alerta (amarillo)** | Avance real >= 85% del planificado O gasto real entre 5% y 15% por encima del presupuestado | Revisar qué rubro está consumiendo más; ajustar en la semana siguiente |
| **Crítico (rojo)** | Avance por debajo del 85% planificado O gasto real más de 15% por encima del presupuestado | Detener compras no urgentes; reunión de revisión del presupuesto; identificar el rubro desviado en el reporte de match |

Un semáforo **crítico por subejecución** (gasto muy por debajo de lo proyectado) puede indicar que la obra está atrasada o que faltan tickets por cargar — no necesariamente es una buena noticia.

---

## Dónde están los archivos

| Archivo | Qué contiene |
|---|---|
| `outputs/estado-proyecto.json` | Estado completo del proyecto: métricas base, gastos reales cargados, avance por semana y semáforo |
| `outputs/presupuesto_base.json` | Presupuesto por rubro generado al inicio del proyecto |
| `outputs/cronograma.json` | Cronograma con fechas de inicio y fin por tarea |
| `outputs/curva_inversion.json` | Distribución semanal del presupuesto (lo que se debería gastar cada semana) |
| `outputs/certificado_semana_N.md` | Certificado de obra de la Semana N con proyectado vs. real |
| `outputs/reporte_match_semana_N.json` | Detalle del match entre gastos reales y rubros activos de la Semana N |
| `outputs/snapshots/semana_N.json` | Registro histórico de cada semana cerrada |
| `inputs/` | Carpeta de entrada: planos, PDFs, fotos. No se modifica nunca |
