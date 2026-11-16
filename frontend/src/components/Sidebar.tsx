import React from 'react';
import { 
  LayoutDashboard, 
  Box, 
  Network, 
  CalendarDays, 
  Users, 
  GitBranch, 
  Activity, 
  DollarSign, 
  CloudSun, 
  Cpu, 
  ShieldCheck, 
  Settings,
  FolderKanban
} from 'lucide-react';

interface SidebarProps {
  currentModule: string;
  onSelectModule: (module: string) => void;
  activeProjectName?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentModule, onSelectModule, activeProjectName }) => {
  const menuItems = [
    { id: 'projects', label: 'Projetos', icon: FolderKanban },
    { id: 'dashboard', label: 'Visão Geral', icon: LayoutDashboard },
    { id: 'bim3d', label: 'Modelos IFC & 3D', icon: Box },
    { id: 'wbs', label: 'EAP & Atividades', icon: Network },
    { id: 'gantt', label: 'Gráfico de Gantt & CPM', icon: CalendarDays },
    { id: 'resources', label: 'Equipes & Recursos', icon: Users },
    { id: 'scenarios', label: 'Cenários PERT', icon: GitBranch },
    { id: 'sim4d', label: 'Simulação BIM 4D', icon: Activity },
    { id: 'financial', label: 'Orçamento & Curva S', icon: DollarSign },
    { id: 'climate', label: 'Análise Climática', icon: CloudSun },
    { id: 'intelligence', label: 'Central Gemini AI', icon: Cpu },
    { id: 'audit', label: 'Versionamento & Auditoria', icon: ShieldCheck },
  ];

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col h-screen sticky top-0">
      <div className="p-5 border-b border-slate-800 flex items-center space-x-3">
        <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center font-bold text-white shadow-lg shadow-blue-500/30">
          BS
        </div>
        <div>
          <h1 className="font-bold text-slate-100 tracking-wide text-lg">BIM SCHEDULE</h1>
          <p className="text-xs text-slate-400">Ecossistema BIMOFFICE</p>
        </div>
      </div>

      {activeProjectName && (
        <div className="mx-3 mt-3 p-2.5 bg-slate-800/80 border border-slate-700/60 rounded-lg">
          <p className="text-[10px] uppercase font-semibold text-blue-400 tracking-wider">Projeto Ativo</p>
          <p className="text-xs font-medium text-slate-200 truncate mt-0.5" title={activeProjectName}>
            {activeProjectName}
          </p>
        </div>
      )}

      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentModule === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectModule(item.id)}
              className={`w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                isActive
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20'
                  : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
              }`}
            >
              <Icon className={`w-5 h-5 ${isActive ? 'text-white' : 'text-slate-400'}`} />
              <span className="truncate">{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="p-4 border-t border-slate-800">
        <button 
          onClick={() => onSelectModule('settings')}
          className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
            currentModule === 'settings' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800'
          }`}
        >
          <Settings className="w-5 h-5" />
          <span>Configurações</span>
        </button>
        <div className="mt-3 text-center">
          <span className="text-[10px] text-slate-500 font-mono">v0.2.0-alpha • Fase 2</span>
        </div>
      </div>
    </aside>
  );
};
