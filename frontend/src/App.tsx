import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { Navbar } from './components/Navbar';
import { ProjectList } from './modules/projects/ProjectList';
import { Project } from './types/project';
import { Bim3DModule } from './modules/bim3d/Bim3DModule';
import { 
  ArrowLeft,
  Layers
} from 'lucide-react';

export function App() {
  const [darkMode, setDarkMode] = useState<boolean>(true);
  const [currentModule, setCurrentModule] = useState<string>('projects');
  const [activeProject, setActiveProject] = useState<Project | null>(null);

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [darkMode]);

  const handleSelectProject = (project: Project) => {
    setActiveProject(project);
    setCurrentModule('dashboard');
  };

  const handleBackToProjects = () => {
    setActiveProject(null);
    setCurrentModule('projects');
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar 
        currentModule={currentModule} 
        onSelectModule={(mod) => {
          if (mod === 'projects') {
            setActiveProject(null);
          }
          setCurrentModule(mod);
        }}
        activeProjectName={activeProject?.name}
      />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Navbar 
          darkMode={darkMode} 
          onToggleDarkMode={() => setDarkMode(!darkMode)}
          activeProjectName={activeProject?.name}
        />

        <main className="flex-1 overflow-y-auto bg-slate-950">
          {currentModule === 'projects' && (
            <ProjectList onSelectProject={handleSelectProject} />
          )}

          {currentModule !== 'projects' && (
            <div className="p-8 max-w-7xl mx-auto space-y-6 h-full flex flex-col">
              <div className="flex items-center justify-between pb-4 border-b border-slate-800 flex-shrink-0">
                <div className="flex items-center space-x-3">
                  <button
                    onClick={handleBackToProjects}
                    className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-white transition-colors"
                    title="Voltar para Lista de Projetos"
                  >
                    <ArrowLeft className="w-4 h-4" />
                  </button>
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-mono text-blue-400 font-bold">{activeProject?.code || 'PRJ-001'}</span>
                      <span className="text-slate-600">•</span>
                      <span className="text-xs text-slate-400">{activeProject?.client || 'Cliente não informado'}</span>
                    </div>
                    <h2 className="text-2xl font-extrabold text-slate-100 mt-0.5">
                      {activeProject?.name || 'Projeto Selecionado'}
                    </h2>
                  </div>
                </div>

                <div className="flex items-center space-x-3">
                  <span className="px-3 py-1 rounded-xl bg-blue-600/10 border border-blue-600/20 text-blue-400 text-xs font-semibold">
                    {activeProject?.status || 'Planejamento'}
                  </span>
                </div>
              </div>

              {currentModule === 'bim3d' && activeProject ? (
                <div className="flex-1 min-h-0"><Bim3DModule projectId={activeProject.id} /></div>
              ) : (
                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center space-y-4 shadow-xl">
                  <div className="w-16 h-16 rounded-2xl bg-blue-600/20 text-blue-400 flex items-center justify-center mx-auto shadow-inner">
                    <Layers className="w-8 h-8" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-slate-100 capitalize">
                      Módulo: {currentModule}
                    </h3>
                    <p className="text-sm text-slate-400 max-w-md mx-auto mt-2">
                      Este módulo está estruturado na arquitetura do BIM SCHEDULE e será implementado nas próximas fases do ecossistema BIMOFFICE.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
