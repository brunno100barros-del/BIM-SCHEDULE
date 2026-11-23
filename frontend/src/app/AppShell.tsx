import React, { useEffect, useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { Sidebar } from '../components/Sidebar';
import { Navbar } from '../components/Navbar';
import { ProjectList } from '../modules/projects/ProjectList';
import { Bim3DModule } from '../modules/bim3d/Bim3DModule';
import { GanttModule } from '../modules/gantt/GanttModule';
import { WbsModule } from '../modules/wbs/WbsModule';
import { DashboardModule } from '../modules/dashboard/DashboardModule';
import { GeneratorModule } from '../modules/generator/GeneratorModule';
import { Project } from '../types/project';
import { SystemStatus } from '../types/api';

interface Props {
  status: SystemStatus | null;
  banner?: React.ReactNode;
}

/** Estrutura da aplicação conectada: barra lateral, barra superior e módulo ativo. */
export function AppShell({ status, banner }: Props) {
  const [darkMode, setDarkMode] = useState<boolean>(true);
  const [currentModule, setCurrentModule] = useState<string>('projects');
  const [activeProject, setActiveProject] = useState<Project | null>(null);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode);
  }, [darkMode]);

  const backToProjects = () => { setActiveProject(null); setCurrentModule('projects'); };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar currentModule={currentModule} onSelectModule={setCurrentModule} activeProjectName={activeProject?.name}
        version={status?.version} hasActiveProject={!!activeProject} />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Navbar darkMode={darkMode} onToggleDarkMode={() => setDarkMode(!darkMode)} activeProjectName={activeProject?.name} />
        {banner}
        <main className="flex-1 overflow-y-auto bg-slate-950">
          {currentModule === 'projects' && (
            <ProjectList onSelectProject={(p) => { setActiveProject(p); setCurrentModule('dashboard'); }} />
          )}
          {currentModule !== 'projects' && activeProject && (
            <>
              <div className="px-8 pt-5">
                <button onClick={backToProjects} className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-white text-xs flex items-center gap-2">
                  <ArrowLeft className="w-4 h-4" />Voltar aos projetos
                </button>
              </div>
              {currentModule === 'dashboard' && <DashboardModule projectId={activeProject.id} projectName={activeProject.name} />}
              {currentModule === 'bim3d' && <Bim3DModule projectId={activeProject.id} />}
              {currentModule === 'generator' && <GeneratorModule projectId={activeProject.id} onOpenGantt={() => setCurrentModule('gantt')} />}
              {currentModule === 'wbs' && <WbsModule projectId={activeProject.id} />}
              {currentModule === 'gantt' && <GanttModule projectId={activeProject.id} />}
            </>
          )}
        </main>
      </div>
    </div>
  );
}

export default AppShell;
