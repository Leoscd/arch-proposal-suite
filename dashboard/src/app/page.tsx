import { 
  Card, 
  CardContent, 
  CardDescription, 
  CardHeader, 
  CardTitle 
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { getProjectData } from "@/lib/data-service";
import { 
  BarChart3, 
  Calendar, 
  CreditCard, 
  LayoutDashboard, 
  TrendingUp, 
  Users,
  AlertTriangle,
  CheckCircle2
} from "lucide-react";

export default async function DashboardPage() {
  const data = await getProjectData();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 p-6 lg:p-10 space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-blue-400 to-emerald-400 bg-clip-text text-transparent">
            {data.metadatos.proyecto_nombre}
          </h1>
          <p className="text-slate-400 mt-1">Monitoreo Maestro de Obra</p>
        </div>
        <div className="flex gap-3">
          <Badge variant="outline" className="px-4 py-1 text-sm bg-white/5 border-white/10 backdrop-blur-sm">
            Estado: <span className="text-emerald-400 ml-1 font-semibold italic">En curso</span>
          </Badge>
          <div className="p-2 rounded-full bg-white/5 border border-white/10">
            <Calendar className="w-5 h-5 text-blue-400" />
          </div>
        </div>
      </div>

      {/* Main Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatsCard 
          title="Presupuesto" 
          value="$--" 
          description="Total Estimado" 
          icon={<BarChart3 className="w-5 h-5 text-blue-400" />}
          trend="+0%"
        />
        <StatsCard 
          title="Gastos Reales" 
          value={`$${data.gastos_reales.reduce((acc, curr) => acc + curr.monto, 0).toLocaleString()}`} 
          description="Hoy" 
          icon={<CreditCard className="w-5 h-5 text-emerald-400" />}
          trend="En fecha"
        />
        <StatsCard 
          title="Avance Obra" 
          value="15%" 
          description="Semana 1" 
          icon={<TrendingUp className="w-5 h-5 text-indigo-400" />}
          trend="+15%"
        />
        <StatsCard 
          title="Personal" 
          value={`${data.metadatos.personal_sugerido.oficiales + data.metadatos.personal_sugerido.ayudantes}`} 
          description="In situ" 
          icon={<Users className="w-5 h-5 text-amber-400" />}
          trend="Completo"
        />
      </div>

      {/* Tabs for different perspectives */}
      <Tabs defaultValue="master" className="w-full space-y-6">
        <TabsList className="bg-white/5 border border-white/10 p-1">
          <TabsTrigger value="master" className="data-[state=active]:bg-blue-600 data-[state=active]:text-white transition-all">
            <LayoutDashboard className="w-4 h-4 mr-2" />
            Tablero Maestro
          </TabsTrigger>
          <TabsTrigger value="investor" className="data-[state=active]:bg-emerald-600 data-[state=active]:text-white transition-all">
            <TrendingUp className="w-4 h-4 mr-2" />
            Vista Inversor
          </TabsTrigger>
        </TabsList>

        <TabsContent value="master" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card className="bg-white/5 border-white/10 backdrop-blur-md">
              <CardHeader>
                <CardTitle className="text-slate-100 flex items-center">
                  Cómputo de Superficies
                </CardTitle>
                <CardDescription className="text-slate-400">Distribución de m2 según planos</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <ProgressItem label="Cubierta" value={data.metricas_base.superficies.cubierta_m2} color="bg-blue-500" />
                  <ProgressItem label="Semicubierta" value={data.metricas_base.superficies.semicubierta_m2} color="bg-indigo-500" />
                  <ProgressItem label="Descubierta" value={data.metricas_base.superficies.descubierta_m2} color="bg-emerald-500" />
                </div>
              </CardContent>
            </Card>

            <Card className="bg-white/5 border-white/10 backdrop-blur-md">
              <CardHeader>
                <CardTitle className="text-slate-100">Certificaciones Emitidas</CardTitle>
              </CardHeader>
              <CardContent className="flex items-center justify-center p-12 italic text-slate-500">
                Aún no hay certificaciones para este proyecto.
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="investor" className="space-y-6">
          <Card className="bg-gradient-to-br from-emerald-900/40 to-slate-900/60 border-white/10 backdrop-blur-xl border-emerald-500/20 shadow-2xl shadow-emerald-950/20">
            <CardHeader>
              <div className="flex items-center gap-3">
                <CheckCircle2 className="w-8 h-8 text-emerald-400" />
                <div>
                  <CardTitle className="text-2xl text-slate-100">Estado Ejecutivo</CardTitle>
                  <CardDescription className="text-emerald-300">Resumen exclusivo para el inversor</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="p-4 bg-emerald-500/10 rounded-lg border border-emerald-500/20">
                <p className="text-lg leading-relaxed text-slate-200">
                  La obra se encuentra en su fase inicial con un despliegue de personal acorde a lo planificado. 
                  Los gastos operativos de la primera semana se mantienen dentro de los márgenes previstos.
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="p-4 bg-white/5 rounded-xl border border-white/10">
                  <p className="text-sm text-slate-400">Eficiencia de Capital</p>
                  <p className="text-2xl font-bold text-emerald-400">Excelente</p>
                </div>
                <div className="p-4 bg-white/5 rounded-xl border border-white/10">
                  <p className="text-sm text-slate-400">Ahorros Detectados</p>
                  <p className="text-2xl font-bold text-blue-400">--</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function StatsCard({ title, value, description, icon, trend }: { title: string, value: string, description: string, icon: React.ReactNode, trend: string }) {
  return (
    <Card className="bg-white/5 border-white/10 backdrop-blur-md hover:border-white/20 transition-all">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-slate-400">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold text-slate-100">{value}</div>
        <div className="flex items-center justify-between mt-1">
          <p className="text-xs text-slate-500">{description}</p>
          <span className="text-xs font-medium text-emerald-400">{trend}</span>
        </div>
      </CardContent>
    </Card>
  );
}

function ProgressItem({ label, value, color }: { label: string, value: number, color: string }) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm">
        <span className="text-slate-300">{label}</span>
        <span className="text-slate-100 font-medium">{value} m2</span>
      </div>
      <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${Math.min(value, 100)}%` }}></div>
      </div>
    </div>
  );
}
