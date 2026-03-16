---
description: Guía de Diseño y Buenas Prácticas para el Dashboard (Next.js + Tailwind + shadcn/ui)
---

# Guía de Diseño: Dashboard Interactivo

Esta skill define las reglas estrictas de diseño, estructura y estética que los agentes deben seguir al construir o modificar el Dashboard del proyecto.

## 1. Stack Tecnológico Obligatorio
- **Framework:** Next.js (App Router).
- **Estilos:** Tailwind CSS.
- **Componentes UI:** shadcn/ui (para botones, tarjetas, tablas, modales).
- **Gráficos:** Recharts (o similar, compatible con React).
- **Iconos:** Lucide React.

## 2. Estética "Premium" (Mandatorio)
El dashboard no puede verse como un panel de administración genérico ("aburrido"). Debe inspirar confianza y profesionalismo:
- **Modo Oscuro (Dark Mode) por defecto:** Fondos en tonos oscuros elegantes (ej. `bg-slate-950` o `bg-zinc-950`), no negro puro.
- **Glassmorphism:** Uso de tarjetas semi-transparentes con bordes sutiles y desenfoque de fondo (`backdrop-blur-md bg-white/5 border border-white/10`).
- **Paleta de Colores Cuidada:** 
  - Primario: Tonos vibrantes pero profesionales (ej. Emerald para finanzas/éxito, Indigo/Violet para acentos).
  - Estados (Semáforo): Red (alerta/sobrepresupuesto), Yellow (precaución/retraso), Green (saludable/en fecha).
- **Tipografía Moderna:** Usar fuentes limpias como Inter, Roboto u Outfit (configuradas vía Next/Font).
- **Micro-interacciones:** Los botones y tarjetas deben tener efectos `hover` suaves (`transition-all duration-300 hover:scale-[1.02]`).

## 3. Arquitectura y Márgenes (Espaciado)
- **Consistencia en el Padding:** Usar un sistema de grillas espacioso. Las tarjetas deben tener padding holgado (`p-6` o `p-8`).
- **Bordes Redondeados:** Consistentes en toda la UI (`rounded-xl` o `rounded-2xl`).
- **Jerarquía Visual:**
  - `<h1>` para el título principal de la página, text-3xl o 4xl, font-bold.
  - Títulos de tarjetas en text-lg o xl, text-muted-foreground.
  - Números clave (KPIs) en tamaño grande (text-4xl o 5xl) y color destacado.

## 4. Estructura de Datos (Integración JSON)
- Los componentes deben estar preparados para consumir datos estructurados desde `estado-proyecto.json`.
- Separar la lógica de "fetch" de datos de los componentes de presentación (usar Client Components solo cuando haya interactividad o useEffect, preferir Server Components para la carga inicial de datos locales si aplica).

## 5. Vistas Requeridas
1. **Tablero Maestro (Project Manager):** Visión granular. Gráficos de barras (presupuesto vs real), Gantt de progreso, tabla de certificados.
2. **Reporte Ejecutivo (Inversor):** Visión simplificada. Grandes KPIs, semáforo de estado, y la "narrativa" explicativa generada por el Agente Inversor.
