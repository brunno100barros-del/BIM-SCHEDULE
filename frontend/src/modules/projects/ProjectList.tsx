import React, { useState, useEffect } from 'react';
import { FolderKanban, Plus, Search, Calendar, Building2, MoreVertical, Copy, Edit3, Trash2, ArrowRight } from 'lucide-react';
import { Project } from '../../types/project';
import { projectService } from '../../services/api';
import { ProjectModal } from '../../components/ProjectModal';

interface ProjectListProps {
  onSelectProject: (project: Project) => void;
}

export const ProjectList: React.FC<ProjectListProps> = ({ onSelectProject }) => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [projectToEdit, setProjectToEdit] = useState<Project | null>(null);
  const [actionMenuId, setActionMenuId] = useState<number | null>(null);

  const fetchProjects = async () => {
    try {
      setLoading(true);
      const data = await projectService.getAll();
      setProjects(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchProjects(); }, []);

  const handleSave = async (formData: any) => {
    if (projectToEdit) {
      await projectService.update(projectToEdit.id, formData);
    } else {
      await projectService.create(formData);
    }
    await fetchProjects();
  };

  const handleDelete = async (id: number) => {
    if (window.confirm('Tem certeza que deseja excluir este projeto?')) {
      await projectService.delete(id);
      await fetchProjects();
    }
  };

  const handleDuplicate = async (id: number) => {
    await projectService.duplicate(id);
    await fetchProjects();
  };

  const filtered = projects.filter(p => p.name.toLowerCase().includes(searchQuery.toLowerCase()) || p.code.toLowerCase().includes(searchQuery.toLowerCase()));

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-extrabold text-slate-100 flex items-center space-x-3">
            <FolderKanban className="w-7 h-7 text-blue-500" />
            <span>Gerenciamento de Projetos — BIM SCHEDULE</span>
          </h2>
          <p className="text-sm text-slate-400 mt-1">Selecione um projeto para iniciar o planejamento BIM 4D, cronograma CPM e análise.</p>
        </div>
        <button onClick={() => { setProjectToEdit(null); setIsModalOpen(true); }}
          className="px-5 py-2.5 rounded-xl font-semibold bg-blue-600 hover:bg-blue-500 text-white shadow-lg flex items-center space-x-2">
          <Plus className="w-5 h-5" />
          <span>Novo Projeto</span>
        </button>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex items-center justify-between">
        <div className="relative w-full max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 transform -translate-y-1/2" />
          <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filtrar por nome ou código..."
            className="w-full bg-slate-800 border border-slate-700 rounded-xl pl-10 pr-4 py-2 text-sm text-slate-200" />
        </div>
        <div className="text-xs text-slate-400">Total: <span className="text-slate-100 font-bold">{projects.length}</span></div>
      </div>

      {loading ? (
        <div className="text-center py-20 text-slate-400">Carregando projetos...</div>
      ) : filtered.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center space-y-4">
          <p className="text-slate-400">Nenhum projeto encontrado.</p>
          <button onClick={() => setIsModalOpen(true)} className="px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-semibold">Criar Projeto</button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map(p => (
            <div key={p.id} className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-lg flex flex-col justify-between relative">
              <div>
                <div className="flex items-start justify-between mb-3">
                  <span className="px-2.5 py-1 bg-blue-500/10 border border-blue-500/20 text-blue-400 font-mono text-xs font-bold rounded-lg">{p.code}</span>
                  <div className="relative">
                    <button onClick={() => setActionMenuId(actionMenuId === p.id ? null : p.id)} className="p-1.5 text-slate-400 hover:text-white">
                      <MoreVertical className="w-4 h-4" />
                    </button>
                    {actionMenuId === p.id && (
                      <div className="absolute right-0 mt-2 w-40 bg-slate-800 border border-slate-700 rounded-xl shadow-xl z-30 py-1">
                        <button onClick={() => { setActionMenuId(null); setProjectToEdit(p); setIsModalOpen(true); }}
                          className="w-full text-left px-4 py-2 text-xs text-slate-200 hover:bg-slate-700 flex items-center space-x-2">
                          <Edit3 className="w-3.5 h-3.5 text-blue-400" /><span>Editar</span>
                        </button>
                        <button onClick={() => { setActionMenuId(null); handleDuplicate(p.id); }}
                          className="w-full text-left px-4 py-2 text-xs text-slate-200 hover:bg-slate-700 flex items-center space-x-2">
                          <Copy className="w-3.5 h-3.5 text-emerald-400" /><span>Duplicar</span>
                        </button>
                        <button onClick={() => { setActionMenuId(null); handleDelete(p.id); }}
                          className="w-full text-left px-4 py-2 text-xs text-red-400 hover:bg-red-500/10 flex items-center space-x-2 border-t border-slate-700">
                          <Trash2 className="w-3.5 h-3.5 text-red-400" /><span>Excluir</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
                <h3 className="text-lg font-bold text-slate-100">{p.name}</h3>
                {p.client && <p className="text-xs text-slate-400 flex items-center space-x-1 mt-1"><Building2 className="w-3.5 h-3.5" /><span>{p.client}</span></p>}
                <p className="text-xs text-slate-300 mt-3 line-clamp-2 bg-slate-800/40 p-2.5 rounded-lg">{p.description || 'Sem descrição.'}</p>
              </div>
              <div className="mt-6 pt-4 border-t border-slate-800 flex items-center justify-between">
                <span className="text-[10px] text-slate-500 font-mono">ID: #{p.id}</span>
                <button onClick={() => onSelectProject(p)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-blue-600/20 text-blue-400 hover:bg-blue-600 hover:text-white flex items-center space-x-1.5 transition-all">
                  <span>Abrir Projeto</span><ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      <ProjectModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} onSave={handleSave} projectToEdit={projectToEdit} />
    </div>
  );
};
