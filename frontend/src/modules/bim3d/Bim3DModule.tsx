import React, { useState, useEffect, useCallback } from 'react';
import { Upload, Box, RefreshCw, ListFilter, Link2, CheckCircle2, AlertCircle } from 'lucide-react';
import axios from 'axios';
import { IfcViewer } from './IfcViewer';

interface Props { projectId: number }
interface IfcModel { id:number; filename:string; status:string; progress:number; processing_message?:string; error_message?:string; element_count:number; schema_name?:string; version:number }
interface IfcElement { id:number; global_id:string; name:string; ifc_type:string; description?:string }
interface Activity { id:number; code:string; name:string }

export const Bim3DModule: React.FC<Props> = ({ projectId }) => {
  const [models, setModels] = useState<IfcModel[]>([]);
  const [elements, setElements] = useState<IfcElement[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [activeModelId, setActiveModelId] = useState<number | null>(null);
  const [selectedElementId, setSelectedElementId] = useState<number | ''>('');
  const [selectedActivityId, setSelectedActivityId] = useState<number | ''>('');
  const [uploading, setUploading] = useState(false);
  const [loadingEls, setLoadingEls] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const fetchModels = useCallback(async () => {
    try {
      const res = await axios.get(`/api/v1/ifc/project/${projectId}/models`);
      setModels(res.data);
      setActiveModelId(current => current ?? (res.data[0]?.id ?? null));
    } catch (e:any) { setError(e.response?.data?.detail || 'Falha ao carregar modelos IFC.'); }
  }, [projectId]);

  const fetchActivities = useCallback(async () => {
    try { const res = await axios.get(`/api/v1/activities/project/${projectId}`); setActivities(res.data); }
    catch (e:any) { setError(e.response?.data?.detail || 'Falha ao carregar atividades.'); }
  }, [projectId]);

  const fetchElements = useCallback(async (modelId:number) => {
    try { setLoadingEls(true); const res = await axios.get(`/api/v1/ifc/model/${modelId}/elements?limit=1000`); setElements(res.data); }
    catch (e:any) { setError(e.response?.data?.detail || 'Falha ao carregar elementos IFC.'); }
    finally { setLoadingEls(false); }
  }, []);

  useEffect(() => { fetchModels(); fetchActivities(); }, [fetchModels, fetchActivities]);
  useEffect(() => {
    if (activeModelId) fetchElements(activeModelId); else setElements([]);
  }, [activeModelId, fetchElements]);
  useEffect(() => {
    const hasPending = models.some(m => ['queued','processing'].includes(m.status));
    if (!hasPending) return;
    const timer = window.setInterval(fetchModels, 2000);
    return () => window.clearInterval(timer);
  }, [models, fetchModels]);

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;
    setError(''); setNotice('');
    try {
      setUploading(true);
      let lastId: number | null = null;
      for (const file of files) {
        const form = new FormData(); form.append('file', file);
        const response = await axios.post(`/api/v1/ifc/project/${projectId}/upload`, form);
        lastId = response.data.id;
      }
      setNotice(`${files.length} arquivo(s) recebido(s). Processamento iniciado.`);
      await fetchModels(); if (lastId) setActiveModelId(lastId);
    } catch (e:any) { setError(e.response?.data?.detail || 'Falha no envio de um dos arquivos IFC.'); }
    finally { setUploading(false); event.target.value=''; }
  };

  const linkElement = async () => {
    if (selectedActivityId === '' || selectedElementId === '') return;
    try {
      await axios.post(`/api/v1/activities/${selectedActivityId}/ifc-elements`, { ifc_element_id:Number(selectedElementId) });
      setNotice('Elemento IFC associado à atividade.'); setError('');
    } catch (e:any) { setError(e.response?.data?.detail || 'Não foi possível associar o elemento.'); }
  };

  const activeModel = models.find(m=>m.id===activeModelId);
  return <div className="flex min-h-[calc(100vh-150px)] gap-5 p-5">
    <div className="w-[350px] shrink-0 flex flex-col gap-4">
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <div className="flex items-center justify-between mb-4"><h3 className="font-bold text-slate-100 flex items-center gap-2"><Box className="w-5 h-5 text-blue-400"/>Modelos IFC</h3><button onClick={fetchModels} className="text-slate-400 hover:text-white" title="Atualizar"><RefreshCw className="w-4 h-4"/></button></div>
        <label className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg cursor-pointer text-sm font-semibold mb-4"><Upload className="w-4 h-4"/>{uploading?'Enviando arquivo…':'Importar IFC'}<input type="file" accept=".ifc" multiple className="hidden" onChange={handleUpload} disabled={uploading}/></label>
        <div className="space-y-2 max-h-[34vh] overflow-y-auto">{models.map(model=><button key={model.id} onClick={()=>setActiveModelId(model.id)} className={`w-full text-left p-3 rounded-lg border text-sm ${activeModelId===model.id?'bg-blue-600/20 border-blue-500 text-blue-300':'bg-slate-800 border-slate-700 text-slate-300'}`}><div className="flex items-center justify-between gap-2"><p className="font-semibold truncate">{model.filename}</p><span className="text-[10px] text-slate-500">v{model.version}</span></div><div className="mt-2 flex items-center justify-between text-[10px]"><span>{model.status==='completed'?'Concluído':model.status==='failed'?'Falhou':model.status==='queued'?'Na fila':'Processando'}</span><span>{model.progress||0}%</span></div><div className="mt-1 h-1.5 rounded-full bg-slate-700 overflow-hidden"><div className={`h-full ${model.status==='failed'?'bg-red-500':'bg-blue-500'}`} style={{width:`${model.progress||0}%`}}/></div><p className="mt-1 text-[10px] text-slate-500 truncate">{model.processing_message || model.error_message || `${model.element_count||0} elementos`}</p></button>)}</div>
      </div>
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex-1 flex flex-col min-h-[250px]">
        <h3 className="font-bold text-slate-100 flex items-center gap-2 mb-3 text-sm"><ListFilter className="w-4 h-4 text-emerald-400"/>Elementos ({elements.length})</h3>
        <div className="flex-1 overflow-y-auto space-y-1.5 max-h-[35vh]">{loadingEls?<div className="text-xs text-center text-slate-400">Carregando elementos…</div>:elements.map(el=><button key={el.id} onClick={()=>setSelectedElementId(el.id)} className={`w-full text-left p-2 rounded-md border text-xs ${selectedElementId===el.id?'bg-blue-600/20 border-blue-500':'bg-slate-800 border-slate-700'}`}><p className="font-semibold text-slate-200 truncate">{el.name}</p><div className="flex justify-between mt-1 gap-2"><span className="text-blue-400 truncate">{el.ifc_type}</span><span className="text-slate-500 font-mono">{el.global_id.slice(0,8)}</span></div></button>)}</div>
        <div className="pt-3 mt-3 border-t border-slate-800 space-y-2"><label className="block text-[11px] text-slate-400">Associar elemento selecionado à atividade<select value={selectedActivityId} onChange={e=>setSelectedActivityId(e.target.value?Number(e.target.value):'')} className="mt-1 w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-2 text-xs text-slate-100"><option value="">Selecione uma atividade</option>{activities.map(a=><option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}</select></label><button onClick={linkElement} disabled={selectedElementId===''||selectedActivityId===''} className="w-full py-2 rounded-lg bg-indigo-600 disabled:opacity-40 text-white text-xs font-semibold flex items-center justify-center gap-2"><Link2 className="w-3.5 h-3.5"/>Vincular GlobalId</button></div>
      </div>
    </div>
    <div className="flex-1 min-w-0 flex flex-col gap-2">{error&&<div className="p-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex gap-2"><AlertCircle className="w-4 h-4 shrink-0"/>{error}</div>}{notice&&<div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex gap-2"><CheckCircle2 className="w-4 h-4 shrink-0"/>{notice}</div>}{activeModel&&<div className="text-xs text-slate-400">{activeModel.filename} · {activeModel.schema_name||'Schema IFC não identificado'} · {activeModel.element_count||0} elementos</div>}<div className="flex-1 min-h-[500px]"><IfcViewer ifcUrl={activeModelId?`/api/v1/ifc/model/${activeModelId}/download`:null}/></div></div>
  </div>;
};
