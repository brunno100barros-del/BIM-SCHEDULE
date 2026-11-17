import React, { useEffect, useState } from 'react';
import { planningService } from '../../services/planning';
import { ifcService } from '../../services/ifc';
import { getErrorMessage } from '../../services/apiClient';
import { Activity, Box, CalendarDays, FolderTree, AlertTriangle } from 'lucide-react';
interface Props { projectId: number; projectName: string }
export const DashboardModule: React.FC<Props> = ({ projectId, projectName }) => {
  const [data, setData] = useState({ activities: 0, wbs: 0, models: 0, processing: 0 });
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([planningService.listActivities(projectId, controller.signal), planningService.listWbs(projectId, controller.signal), ifcService.listModels(projectId, controller.signal)]).then(([a,w,m]) => setData({ activities:a.length, wbs:w.length, models:m.length, processing:m.filter((x)=>['queued','processing'].includes(x.status)).length })).catch((e:unknown)=>{ if (!controller.signal.aborted) setError(getErrorMessage(e, 'Não foi possível carregar o resumo do projeto.')); });
    return () => controller.abort();
  }, [projectId]);
  const cards = [{label:'Atividades',value:data.activities,icon:Activity,color:'text-blue-400'},{label:'Níveis da EAP',value:data.wbs,icon:FolderTree,color:'text-violet-400'},{label:'Modelos IFC',value:data.models,icon:Box,color:'text-emerald-400'},{label:'Processamentos IFC',value:data.processing,icon:CalendarDays,color:'text-amber-400'}];
  return <div className="p-8 max-w-7xl mx-auto space-y-6"><div><p className="text-xs uppercase tracking-wider text-blue-400 font-semibold">Painel do projeto</p><h2 className="text-2xl font-extrabold text-slate-100 mt-1">{projectName}</h2><p className="text-sm text-slate-400 mt-1">Resumo dos dados atualmente persistidos no BIM SCHEDULE.</p></div>{error && <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-sm">{error}</div>}<div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">{cards.map(c=>{const Icon=c.icon;return <div key={c.label} className="bg-slate-900 border border-slate-800 rounded-2xl p-5"><div className="flex items-center justify-between"><span className="text-sm text-slate-400">{c.label}</span><Icon className={`w-5 h-5 ${c.color}`}/></div><div className="text-3xl font-bold text-slate-100 mt-3">{c.value}</div></div>})}</div><div className="bg-slate-900 border border-amber-500/20 rounded-2xl p-5"><div className="flex items-center gap-2 text-amber-300 font-semibold"><AlertTriangle className="w-5 h-5"/>Estado de desenvolvimento</div><p className="text-sm text-slate-300 mt-2">Esta compilação é uma versão de desenvolvimento. O núcleo de projetos, EAP, atividades, CPM e importação inicial IFC está em implementação. Recursos, cenários, financeiro, clima, Central Gemini, auditoria e simulação BIM 4D ainda não estão liberados como funcionalidades concluídas.</p></div></div>;
};
