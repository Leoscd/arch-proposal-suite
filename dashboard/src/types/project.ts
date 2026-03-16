export interface ProjectMetadata {
  proyecto_nombre: string;
  fecha_inicio_obra: string;
  personal_sugerido: {
    oficiales: number;
    ayudantes: number;
  };
}

export interface BaseMetrics {
  superficies: {
    cubierta_m2: number;
    semicubierta_m2: number;
    descubierta_m2: number;
  };
  cantidades_estimadas_por_foto_o_plano: Record<string, number>;
}

export interface RealExpense {
  item: string;
  monto: number;
  fecha: string;
  categoria: string;
}

export interface EstadoProyecto {
  metadatos: ProjectMetadata;
  metricas_base: BaseMetrics;
  presupuesto_validado: Record<string, any>;
  gastos_reales: RealExpense[];
  auditorias_completadas: string[];
}
