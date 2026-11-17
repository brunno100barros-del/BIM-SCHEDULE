import React, { useEffect, useMemo, useState } from 'react';
import { planningService } from '../../services/planning';
import { getErrorMessage } from '../../services/apiClient';
import { FolderTree, Plus, Trash2, RefreshCw, Pencil, ArrowUp, ArrowDown } from 'lucide-react';

interface Props { projectId: number }
interface WbsNode { id: number; project_id: number; name: string; code: string; description?: string | null; parent_id?: number | null; sort_order: number }
interface Activity { id: number; project_id: number; wbs_id?: number | null; name: string; code: string; duration: number; status: string }

export const WbsModule: React.FC<Props> = ({ projectId }) => {
  const [nodes, setNodes] = useState<WbsNode[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [parentId, setParentId] = useState<number | ''>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true); setError('');
    try {
      const [wbs, acts] = await Promise.all([
        planningService.listWbs(projectId),
        planningService.listActivities(projectId),
      ]);
      setNodes(wbs); setActivities(acts);
    } catch (e: any) { setError(getErrorMessage(e, 'Não foi possível carregar a EAP.')); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [projectId]);

  const orderedNodes = useMemo(() => {
    const result: Array<WbsNode & { level: number }> = [];
    const visit = (parent: number | null, level: number) => {
      nodes.filter(n => (n.parent_id ?? null) === parent).sort((a,b) => a.sort_order - b.sort_order || a.id - b.id).forEach(n => {
        result.push({ ...n, level }); visit(n.id, level + 1);
      });
    };
    visit(null, 0);
    // Evita esconder nós órfãos caso uma base antiga contenha referências inconsistentes.
    nodes.filter(n => !result.some(r => r.id === n.id)).forEach(n => result.push({ ...n, level: 0 }));
    return result;
  }, [nodes]);

  const editNode = async (node: WbsNode) => {
    const nextName = window.prompt('Nome do item da EAP:', node.name);
    if (nextName === null || !nextName.trim()) return;
    const nextCode = window.prompt('Código do item da EAP:', node.code);
    if (nextCode === null || !nextCode.trim()) return;
    try { await planningService.updateWbs(node.id, { name: nextName.trim(), code: nextCode.trim() }); await load(); }
    catch (e: any) { setError(getErrorMessage(e, 'Falha ao editar item da EAP.')); }
  };
  const moveNode = async (node: WbsNode, direction: number) => {
    const siblings = nodes.filter(n => (n.parent_id ?? null) === (node.parent_id ?? null)).sort((a,b)=>a.sort_order-b.sort_order || a.id-b.id);
    const index = siblings.findIndex(n=>n.id===node.id); const target = siblings[index + direction];
    if (!target) return;
    const reordered = [...siblings];
    [reordered[index], reordered[index + direction]] = [reordered[index + direction], reordered[index]];
    try {
      await Promise.all(reordered.map((item, position) => planningService.updateWbs(item.id, { sort_order: position })));
      await load();
    } catch (e: any) { setError(getErrorMessage(e, 'Falha ao reordenar EAP.')); }
  };
  const deleteNode = async (node: WbsNode) => {
    if (!window.confirm(`Excluir ${node.code} — ${node.name}? Os níveis filhos também serão excluídos e as atividades ficarão sem vínculo com este nó.`)) return;
    try { await planningService.deleteWbs(node.id); await load(); }
    catch (e: any) { setError(getErrorMessage(e, 'Falha ao excluir item da EAP.')); }
  };

  const createNode = async (e: React.FormEvent) => {
    e.preventDefault(); setError('');
    try {
      await planningService.createWbs({ project_id: projectId, name, code, parent_id: parentId === '' ? null : Number(parentId) });
      setName(''); setCode(''); setParentId(''); await load();
    } catch (e: any) { setError(getErrorMessage(e, 'Falha ao criar item da EAP.')); }
  };

  return <div className="p-8 max-w-7xl mx-auto space-y-6">
    <div className="flex items-center justify-between gap-4">
      <div><h2 className="text-2xl font-extrabold text-slate-100 flex items-center gap-3"><FolderTree className="w-7 h-7 text-blue-500"/>EAP e atividades</h2><p className="text-sm text-slate-400 mt-1">Estrutura hierárquica persistida e vinculada ao projeto.</p></div>
      <button onClick={load} className="px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-200 text-sm flex gap-2 items-center"><RefreshCw className="w-4 h-4"/>Atualizar</button>
    </div>
    {error && <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-sm">{error}</div>}
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
      <form onSubmit={createNode} className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3 h-fit">
        <h3 className="font-bold text-slate-100">Novo nível da EAP</h3>
        <label className="block text-xs text-slate-400">Código<input required value={code} onChange={e=>setCode(e.target.value)} className="mt-1 w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100" placeholder="1.1"/></label>
        <label className="block text-xs text-slate-400">Nome<input required value={name} onChange={e=>setName(e.target.value)} className="mt-1 w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100" placeholder="Fundações"/></label>
        <label className="block text-xs text-slate-400">Nível superior<select value={parentId} onChange={e=>setParentId(e.target.value ? Number(e.target.value) : '')} className="mt-1 w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100"><option value="">Raiz</option>{orderedNodes.map(n=><option key={n.id} value={n.id}>{n.code} — {n.name}</option>)}</select></label>
        <button className="w-full py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold flex items-center justify-center gap-2"><Plus className="w-4 h-4"/>Adicionar à EAP</button>
      </form>
      <div className="xl:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-5">
        <div className="flex items-center justify-between mb-4"><h3 className="font-bold text-slate-100">Estrutura analítica do projeto</h3><span className="text-xs text-slate-400">{nodes.length} níveis · {activities.length} atividades</span></div>
        {loading ? <p className="text-slate-400 text-sm py-8 text-center">Carregando...</p> : orderedNodes.length === 0 ? <p className="text-slate-400 text-sm py-8 text-center">Nenhum nível cadastrado. Crie a estrutura inicial ao lado.</p> : <div className="space-y-1">{orderedNodes.map(n=><div key={n.id} className="flex items-center justify-between gap-3 py-2 px-3 rounded-lg bg-slate-800/60 border border-slate-700/60" style={{marginLeft: `${Math.min(n.level,5)*18}px`}}><div className="min-w-0"><span className="text-xs font-mono text-blue-400 mr-3">{n.code}</span><span className="text-sm text-slate-100 font-medium">{n.name}</span></div><div className="flex items-center gap-2 shrink-0"><span className="text-[11px] text-slate-500">{activities.filter(a=>a.wbs_id===n.id).length} atividades</span><button onClick={()=>moveNode(n,-1)} title="Mover para cima" className="text-slate-500 hover:text-slate-200"><ArrowUp className="w-3.5 h-3.5"/></button><button onClick={()=>moveNode(n,1)} title="Mover para baixo" className="text-slate-500 hover:text-slate-200"><ArrowDown className="w-3.5 h-3.5"/></button><button onClick={()=>editNode(n)} title="Editar" className="text-blue-400"><Pencil className="w-3.5 h-3.5"/></button><button onClick={()=>deleteNode(n)} title="Excluir" className="text-red-400"><Trash2 className="w-3.5 h-3.5"/></button></div></div>)}</div>}
      </div>
    </div>
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
      <h3 className="font-bold text-slate-100 mb-3">Atividades vinculadas</h3>
      {activities.length === 0 ? <p className="text-sm text-slate-400">Ainda não há atividades. Cadastre-as no módulo de Gantt/CPM.</p> : <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-xs text-slate-400 border-b border-slate-800"><th className="text-left py-2">Código</th><th className="text-left">Atividade</th><th className="text-left">EAP</th><th className="text-right">Duração</th><th className="text-right">Status</th></tr></thead><tbody>{activities.map(a=><tr key={a.id} className="border-b border-slate-800/60"><td className="py-2 font-mono text-blue-400">{a.code}</td><td className="text-slate-200">{a.name}</td><td className="text-slate-400">{nodes.find(n=>n.id===a.wbs_id)?.code || '—'}</td><td className="text-right text-slate-300">{a.duration} d</td><td className="text-right text-slate-400">{a.status}</td></tr>)}</tbody></table></div>}
    </div>
  </div>;
};
