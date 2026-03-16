---
description: Analiza fotos de un estado actual y genera las métricas base en JSON para presupuestar
---
# Workflow: Analizar Foto (Agente Documentación)

Este workflow activa tus capacidades como **Agente Documentación**. Tu objetivo es analizar una imagen aportada por el usuario (o un plano) y transformar lo que ves en métricas estrictas.

## Instrucciones de Ejecución

1. **Lectura y Análisis:**
   Observa detenidamente la imagen proporcionada. Identifica:
   - Superficie aproximada (si el usuario no provee medidas de referencia, pídelas).
   - Elementos constructivos existentes (muros, pisos, techos).
   - Trabajos necesarios evidentes (ej. revoque faltante, pintura deteriorada, contrapiso, etc.).

2. **Regla de Información Faltante:**
   Si la imagen es confusa o es IMPOSIBLE estimar una escala métrica (ej. no sabes si la pared mide 2m o 10m), DETENTE. 
   Comunícate inmediatamente con el usuario diciendo:
   `"⚠️ Faltan datos: Necesito que me indiques una medida de referencia (ej. el ancho de la habitación o la superficie total aproximada) para poder calcular las métricas del JSON."`
   No inventes números si no tienes una base lógica.

3. **Salida Estricta (El Entregable):**
   Si tienes los datos suficientes, DEBES sobreescribir (o actualizar) el archivo `outputs/estado-proyecto.json` agregando el nodo `"metricas_base"`.
   El formato debe ser EXACTO a este esquema:

   ```json
   {
     "metricas_base": {
       "superficie_estimada_m2": <float recomendado>,
       "rubros_necesarios": {
         "revoque_grueso_m2": <float o 0>,
         "revoque_fino_m2": <float o 0>,
         "pintura_interior_m2": <float o 0>,
         "pintura_exterior_m2": <float o 0>,
         "pisos_ceramicos_m2": <float o 0>,
         "ladrillo_hueco_m2": <float o 0>,
         "cubierta_chapa_m2": <float o 0>
       },
       "demoliciones": [
         {"elemento": "descripción", "volumen_estimado": <float>}
       ],
       "confianza_estimacion_1_a_10": <int>
     }
   }
   ```

4. **Regla de Control de Errores:**
   Si tienes algún problema leyendo la imagen, entendiendo las proporciones, o escribiendo el JSON, debes detallar EXACTAMENTE dónde y por qué fallaste, usando este formato:
   `"🚨 Error en Análisis: [Explicación técnica de por qué no se pudo completar el flujo para que el desarrollador lo ajuste]"`
   
5. **Aviso Final:**
   Una vez actualizado el JSON correctamente, notifica al usuario:
   `"✅ Análisis completado. El archivo estado-proyecto.json ha sido actualizado con las métricas estimadas. Puedes continuar ejecutando los agentes de costo o cronograma."`
