import React from 'react';
import { getRuntimeConfig } from '../config/runtime';
import { LayoutDashboard, Box, Network, CalendarDays, Users, GitBranch, Activity, DollarSign, CloudSun, Cpu, ShieldCheck, FolderKanban, ExternalLink } from 'lucide-react';

interface SidebarProps {
  currentModule: string;
  onSelectModule: (module: string) => void;
  activeProjectName?: string;
  version?: string;
  hasActiveProject?: boolean;
}

interface MenuItem { id: string; label: string; icon: React.ElementType; available: boolean; needsProject?: boolean }

const MENU: MenuItem[] = [
  { id: 'projects', label: 'Projetos', icon: FolderKanban, available: true },
  { id: 'dashboard', label: 'Visão Geral', icon: LayoutDashboard, available: true, needsProject: true },
  { id: 'bim3d', label: 'Modelos IFC & 3D', icon: Box, available: true, needsProject: true },
  { id: 'wbs', label: 'EAP & Atividades', icon: Network, available: true, needsProject: true },
  { id: 'gantt', label: 'Gráfico de Gantt & CPM', icon: CalendarDays, available: true, needsProject: true },
  { id: 'resources', label: 'Equipes & Recursos', icon: Users, available: false },
  { id: 'scenarios', label: 'Cenários PERT', icon: GitBranch, available: false },
  { id: 'sim4d', label: 'Simulação BIM 4D', icon: Activity, available: false },
  { id: 'financial', label: 'Orçamento & Curva S', icon: DollarSign, available: false },
  { id: 'climate', label: 'Análise Climática', icon: CloudSun, available: false },
  { id: 'intelligence', label: 'Central de IA', icon: Cpu, available: false },
  { id: 'audit', label: 'Versionamento & Auditoria', icon: ShieldCheck, available: false },
];

export const Sidebar: React.FC<SidebarProps> = ({ currentModule, onSelectModule, activeProjectName, version, hasActiveProject = true }) => (
  <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col h-screen sticky top-0 shrink-0">
    <div className="p-5 border-b border-slate-800 flex items-center space-x-3">
      <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center font-bold text-white shadow-lg shadow-blue-500/30">BS</div>
      <div><h1 className="font-bold text-slate-100 tracking-wide text-lg">BIM SCHEDULE</h1><p className="text-xs text-slate-400">Ecossistema BIMOFFICE</p></div>
    </div>
    {activeProjectName && (
      <div className="mx-3 mt-3 p-2.5 bg-slate-800/80 border border-slate-700/60 rounded-lg">
        <p className="text-[10px] uppercase font-semibold text-blue-400 tracking-wider">Projeto Ativo</p>
        <p className="text-xs font-medium text-slate-200 truncate mt-0.5" title={activeProjectName}>{activeProjectName}</p>
      </div>
    )}
    <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
      {MENU.map((item) => {
        const Icon = item.icon;
        const active = currentModule === item.id;
        const blockedByProject = item.available && item.needsProject && !hasActiveProject;
        const enabled = item.available && !blockedByProject;
        const title = !item.available ? 'Módulo ainda não implementado' : blockedByProject ? 'Abra um projeto primeiro' : '';
        return (
          <button key={item.id} disabled={!enabled} title={title} onClick={() => onSelectModule(item.id)}
            className={`w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${active ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20' : enabled ? 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60' : 'text-slate-600 cursor-not-allowed opacity-60'}`}>
            <Icon className={`w-5 h-5 ${active ? 'text-white' : 'text-slate-500'}`} />
            <span className="truncate flex-1 text-left">{item.label}</span>
            {!item.available && <span className="text-[9px] uppercase tracking-wide">breve</span>}
          </button>
        );
      })}
    </nav>
    <div className="p-4 border-t border-slate-800 space-y-2 text-center">
      <a href="./demo.html" target="_blank" rel="noopener" className="text-[11px] text-slate-400 hover:text-slate-200 inline-flex items-center gap-1">
        <ExternalLink className="w-3 h-3" />Demonstração (dados fictícios)
      </a>
      <div><span className="text-[10px] text-slate-500 font-mono">v{version ?? '—'} · {getRuntimeConfig().mode === 'desktop' ? 'Aplicativo desktop' : 'Desenvolvimento'}</span></div>
    </div>
  </aside>
);
