import React, { useState, useEffect } from 'react';
import { Upload, Box, RefreshCw, ListFilter } from 'lucide-react';
import axios from 'axios';
import { IfcViewer } from './IfcViewer';

interface Bim3DModuleProps {
  projectId: number;
}

export const Bim3DModule: React.FC<Bim3DModuleProps> = ({ projectId }) => {
  const [models, setModels] = useState<any[]>([]);
  const [elements, setElements] = useState<any[]>([]);
  const [activeModelId, setActiveModelId] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);
  const [loadingEls, setLoadingEls] = useState(false);

  const fetchModels = async () => {
    try {
      const res = await axios.get(`/api/v1/ifc/project/${projectId}/models`);
      setModels(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchElements = async (modelId: number) => {
    try {
      setLoadingEls(true);
      const res = await axios.get(`/api/v1/ifc/model/${modelId}/elements`);
      setElements(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingEls(false);
    }
  };

  useEffect(() => {
    fetchModels();
  }, [projectId]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      setUploading(true);
      await axios.post(`/api/v1/ifc/project/${projectId}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      await fetchModels();
    } catch (err) {
      alert('Erro ao fazer upload do IFC.');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const selectModel = (id: number) => {
    setActiveModelId(id);
    fetchElements(id);
  };

  return (
    <div className="flex h-[calc(100vh-140px)] gap-6 p-4">
      <div className="w-80 flex flex-col gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-md">
          <h3 className="font-bold text-slate-100 flex items-center gap-2 mb-4">
            <Box className="w-5 h-5 text-blue-400" />
            Modelos IFC Importados
          </h3>
          
          <label className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg cursor-pointer transition-colors text-sm font-semibold mb-4">
            <Upload className="w-4 h-4" />
            {uploading ? 'Processando IFC...' : 'Importar IFC'}
            <input type="file" accept=".ifc" className="hidden" onChange={handleFileUpload} disabled={uploading} />
          </label>

          <div className="space-y-2 max-h-[30vh] overflow-y-auto pr-1">
            {models.length === 0 ? (
              <p className="text-xs text-slate-500 text-center py-4">Nenhum modelo importado.</p>
            ) : (
              models.map(m => (
                <button
                  key={m.id}
                  onClick={() => selectModel(m.id)}
                  className={`w-full text-left p-3 rounded-lg border text-sm transition-all ${
                    activeModelId === m.id 
                    ? 'bg-blue-600/20 border-blue-500 text-blue-400' 
                    : 'bg-slate-800 border-slate-700 text-slate-300 hover:border-slate-600'
                  }`}
                >
                  <p className="font-semibold truncate" title={m.filename}>{m.filename}</p>
                  <p className="text-[10px] mt-1 opacity-70">ID: {m.id} • Rev: {m.version}</p>
                </button>
              ))
            )}
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-md flex-1 flex flex-col min-h-0">
          <h3 className="font-bold text-slate-100 flex items-center gap-2 mb-3 text-sm">
            <ListFilter className="w-4 h-4 text-emerald-400" />
            Elementos Extraídos ({elements.length})
          </h3>
          <div className="flex-1 overflow-y-auto pr-1">
            {loadingEls ? (
              <div className="text-center py-4 text-xs text-slate-400 flex items-center justify-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin" /> Carregando...
              </div>
            ) : elements.length === 0 ? (
              <p className="text-xs text-slate-500 text-center py-4">Selecione um modelo.</p>
            ) : (
              <div className="space-y-1.5">
                {elements.slice(0, 100).map(el => (
                  <div key={el.id} className="p-2 bg-slate-800 rounded-md border border-slate-700/50">
                    <p className="text-xs font-semibold text-slate-200 truncate">{el.name}</p>
                    <div className="flex justify-between mt-1">
                      <span className="text-[10px] text-blue-400 bg-blue-400/10 px-1.5 py-0.5 rounded">{el.ifc_type}</span>
                      <span className="text-[10px] text-slate-500 font-mono" title={el.global_id}>{el.global_id.substring(0, 8)}...</span>
                    </div>
                  </div>
                ))}
                {elements.length > 100 && (
                  <p className="text-[10px] text-center text-slate-500 pt-2">Mostrando 100 de {elements.length}</p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="flex-1">
        <IfcViewer ifcUrl={activeModelId ? `/api/v1/ifc/model/${activeModelId}/download` : null} />
      </div>
    </div>
  );
};
