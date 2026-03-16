import fs from 'fs/promises';
import path from 'path';
import { EstadoProyecto } from '@/types/project';

const PROJECT_ROOT = path.join(process.cwd(), '..');
const DATA_FILE = path.join(PROJECT_ROOT, 'estado-proyecto.json');

export async function getProjectData(): Promise<EstadoProyecto> {
  try {
    const content = await fs.readFile(DATA_FILE, 'utf-8');
    return JSON.parse(content);
  } catch (error) {
    console.error('Error reading project data:', error);
    // Return a default structure if reading fails
    return {
      metadatos: {
        proyecto_nombre: "Error al cargar datos",
        fecha_inicio_obra: "N/A",
        personal_sugerido: { oficiales: 0, ayudantes: 0 }
      },
      metricas_base: {
        superficies: { cubierta_m2: 0, semicubierta_m2: 0, descubierta_m2: 0 },
        cantidades_estimadas_por_foto_o_plano: {}
      },
      presupuesto_validado: {},
      gastos_reales: [],
      auditorias_completadas: []
    };
  }
}
