import React, { useState, useEffect } from 'react';
import { 
  FolderKanban, 
  Plus, 
  Search, 
  Calendar, 
  Building2, 
  MoreVertical, 
  Copy, 
  Edit3, 
  Trash2, 
  ArrowRight,
  Clock,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
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
      console.error('Erro ao buscar projetos:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleSaveProject = async (formData: any) => {
    if (projectToEdit) {
      await projectService.update(projectToEdit.id, formData);
    } else {
      await projectService.create(formData);
    }
    await fetchProjects();
  };

  const handleDelete = async (id: number) => {
    if (window.confirm('Tem certeza que deseja excluir este projeto? Esta ação não pode ser desfeita.')) {
      try {
        await projectService.delete(id);
        await fetchProjects();
      } catch (err) {
        alert('Erro ao excluir projeto.');
      }
    }
  };

  const handleDuplicate = async (id: number) => {
    try {
      await projectService.duplicate(id);
      await fetchProjects();
    } catch (err) {
      alert('Erro ao duplicar projeto.');
    }
  };

  const filteredProjects = projects.filter(p => 
    p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (p.client && p.client.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-extrabold text-slate-100 flex items-center space-x-3">
            <FolderKanban className="w-7 h-7 text-blue-500" />
            <span>Gerenciamento de Projetos</span>
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Selecione um projeto para iniciar o planejamento BIM 4D, cronograma CPM e análise orçamentária.
          </p>
        </div>
        <button
          onClick={() => {
            setProjectToEdit(null);
            setIsModalOpen(true);
          }}
          className="px-5 py-2.5 rounded-xl font-semibold bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/30 flex items-center space-x-2 transition-all transform hover:-translate-y-0.5"
        >
          <Plus className="w-5 h-5" />
          <span>Novo Projeto</span>
        </button>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex items-center justify-between shadow-sm">
        <div className="relative w-full max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 transform -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filtrar por nome, código ou cliente..."
            className="w-full bg-slate-800/80 border border-slate-700/80 rounded-xl pl-10 pr-4 py-2 text-sm text-slate-200 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="text-xs text-slate-400 font-medium">
          Total: <span className="text-slate-100 font-bold">{projects.length}</span> projetos cadastrados
        </div>
      </div>

      {loading ? (
        <div className="text-center py-20">
          <div className="inline-block w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-sm text-slate-400 mt-3">Carregando projetos...</p>
        </div>
      ) : filteredProjects.length === 0 ? (
        <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-12 text-center space-y-4">
          <div className="w-16 h-16 rounded-full bg-slate-800 flex items-center justify-center mx-auto text-slate-500">
            <FolderKanban className="w-8 h-8" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-200">Nenhum projeto encontrado</h3>
            <p className="text-sm text-slate-400 max-w-sm mx-auto mt-1">
              {searchQuery ? 'Tente ajustar sua busca ou limpar o filtro.' : 'Comece criando seu primeiro projeto de engenharia civil BIM.'}
            </p>
          </div>
          {!searchQuery && (
            <button
              onClick={() => {
                setProjectToEdit(null);
                setIsModalOpen(true);
              }}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl text-sm transition-all"
            >
              Criar Primeiro Projeto
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredProjects.map((project) => (
            <div
              key={project.id}
              className="bg-slate-900 border border-slate-800 rounded-2xl p-6 hover:border-slate-700 transition-all shadow-lg flex flex-col justify-between group relative"
            >
              <div>
                <div className="flex items-start justify-between mb-3">
                  <span className="px-2.5 py-1 bg-blue-500/10 border border-blue-500/20 text-blue-400 font-mono text-xs font-bold rounded-lg">
                    {project.code}
                  </span>
                  <div className="flex items-center space-x-2">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold flex items-center space-x-1 ${
                      project.status === 'Concluído' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                      project.status === 'Em Andamento' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                      'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                    }`}>
                      {project.status === 'Concluído' && <CheckCircle2 className="w-3 h-3 mr-0.5" />}
                      {project.status === 'Em Andamento' && <Clock className="w-3 h-3 mr-0.5" />}
                      {project.status === 'Planejamento' && <AlertCircle className="w-3 h-3 mr-0.5" />}
                      <span>{project.status}</span>
                    </span>

                    <div className="relative">
                      <button
                        onClick={() => setActionMenuId(actionMenuId === project.id ? null : project.id)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                      >
                        <MoreVertical className="w-4 h-4" />
                      </button>

                      {actionMenuId === project.id && (
                        <div className="absolute right-0 mt-2 w-48 bg-slate-800 border border-slate-700 rounded-xl shadow-xl z-30 py-1 overflow-hidden animate-in fade-in duration-150">
                          <button
                            onClick={() => {
                              setActionMenuId(null);
                              setProjectToEdit(project);
                              setIsModalOpen(true);
                            }}
                            className="w-full text-left px-4 py-2 text-xs text-slate-200 hover:bg-slate-700 flex items-center space-x-2"
                          >
                            <Edit3 className="w-3.5 h-3.5 text-blue-400" />
                            <span>Editar Projeto</span>
                          </button>
                          <button
                            onClick={() => {
                              setActionMenuId(null);
                              handleDuplicate(project.id);
                            }}
                            className="w-full text-left px-4 py-2 text-xs text-slate-200 hover:bg-slate-700 flex items-center space-x-2"
                          >
                            <Copy className="w-3.5 h-3.5 text-emerald-400" />
                            <span>Duplicar Projeto</span>
                          </button>
                          <button
                            onClick={() => {
                              setActionMenuId(null);
                              handleDelete(project.id);
                            }}
                            className="w-full text-left px-4 py-2 text-xs text-red-400 hover:bg-red-500/10 flex items-center space-x-2 border-t border-slate-700"
                          >
                            <Trash2 className="w-3.5 h-3.5 text-red-400" />
                            <span>Excluir Projeto</span>
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <h3 className="text-lg font-bold text-slate-100 group-hover:text-blue-400 transition-colors">
                  {project.name}
                </h3>

                {project.client && (
                  <p className="text-xs text-slate-400 flex items-center space-x-1.5 mt-1">
                    <Building2 className="w-3.5 h-3.5 text-slate-500" />
                    <span>{project.client}</span>
                  </p>
                )}

                <p className="text-xs text-slate-300 mt-3 line-clamp-2 bg-slate-800/40 p-2.5 rounded-lg border border-slate-800">
                  {project.description || 'Sem descrição cadastrada.'}
                </p>

                <div className="mt-4 space-y-1.5 text-[11px] text-slate-400 border-t border-slate-800 pt-3">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center space-x-1">
                      <Calendar className="w-3.5 h-3.5 text-slate-500" />
                      <span>Início:</span>
                    </span>
                    <span className="font-medium text-slate-200">{project.start_date || 'Não definido'}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="flex items-center space-x-1">
                      <Calendar className="w-3.5 h-3.5 text-slate-500" />
                      <span>Término:</span>
                    </span>
                    <span className="font-medium text-slate-200">{project.end_date || 'Não definido'}</span>
                  </div>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-slate-800 flex items-center justify-between">
                <span className="text-[10px] text-slate-500 font-mono">
                  ID: #{project.id}
                </span>
                <button
                  onClick={() => onSelectProject(project)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-blue-600/20 text-blue-400 hover:bg-blue-600 hover:text-white flex items-center space-x-1.5 transition-all"
                >
                  <span>Abrir Projeto</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <ProjectModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSave={handleSaveProject}
        projectToEdit={projectToEdit}
      />
    </div>
  );
};
