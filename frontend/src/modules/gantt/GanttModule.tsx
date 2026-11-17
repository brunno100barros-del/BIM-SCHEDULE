import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { CalendarDays, Play, Plus, Trash2, Link2, RefreshCw } from 'lucide-react';

interface GanttModuleProps { projectId: number }
interface Activity { id: number; project_id: number; wbs_id?: number | null; name: string; code: string; duration: number; es: number; ef: number; ls: number; lf: number; tf: number; ff: number; is_critical: number }
interface Precedence { id: number; predecessor_id: number; successor_id: number; relation_type: string; lag: number }
interface WbsNode { id: number; code: string; name: string }

export const GanttModule: React.FC<GanttModuleProps> = ({ projectId }) => {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [precs, setPrecs] = useState<Precedence[]>([]);
  const [wbs, setWbs] = useState<WbsNode[]>([]);
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [duration, setDuration] = useState(5);
  const [wbsId, setWbsId] = useState<number | ''>('');
  const [predId, setPredId] = useState<number | ''>('');
  const [succId, setSuccId] = useState<number | ''>('');
  const [relation, setRelation] = useState('FS');
  const [lag, setLag] = useState(0);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchData = async () => {
    setLoading(true); setError('');
    try {
      const [acts, relations, wbsRes] = await Promise.all([
        axios.get(`/api/v1/activities/project/${projectId}`),
        axios.get(`/api/v1/activities/project/${projectId}/precedences`),
        axios.get(`/api/v1/activities/project/${projectId}/wbs`),
      ]);
      setActivities(acts.data); setPrecs(relations.data); setWbs(wbsRes.data);
    } catch (e: any) { setError(e.response?.data?.detail || 'Falha ao carregar o cronograma.'); }
    finally { setLoading(false); }
  };
  useEffect(() => { fetchData(); setSummary(null); }, [projectId]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault(); setError('');
    try {
      await axios.post('/api/v1/activities/', { project_id: projectId, wbs_id: wbsId === '' ? null : Number(wbsId), name, code, duration: Number(duration) });
      setName(''); setCode(''); setSummary(null); await fetchData();
    } catch (e: any) { setError(e.response?.data?.detail || 'Erro ao cadastrar atividade.'); }
  };

  const handleAddPrecedence = async (e: React.FormEvent) => {
    e.preventDefault(); setError('');
    try {
      await axios.post('/api/v1/activities/precedences', { predecessor_id: Number(predId), successor_id: Number(succId), relation_type: relation, lag: Number(lag) });
      setPredId(''); setSuccId(''); setSummary(null); await fetchData();
    } catch (e: any) { setError(e.response?.data?.detail || 'Erro ao cadastrar precedência.'); }
  };

  const handleRunCPM = async () => {
    setError('');
    try {
      const res = await axios.post(`/api/v1/activities/project/${projectId}/calculate-cpm`);
      setSummary(res.data); await fetchData();
    } catch (e: any) { setError(e.response?.data?.detail || 'Erro ao calcular CPM.'); }
  };

  const handleUpdateDuration = async (activity: Activity, nextDuration: number) => {
    if (!Number.isFinite(nextDuration) || nextDuration < 0 || nextDuration === activity.duration) return;
    try { await axios.put(`/api/v1/activities/${activity.id}`, { duration: nextDuration }); setSummary(null); await fetchData(); }
    catch (e: any) { setError(e.response?.data?.detail || 'Falha ao atualizar duração.'); }
  };

  const handleDeleteActivity = async (id: number) => {
    if (!window.confirm('Excluir esta atividade e suas relações de precedência?')) return;
    try { await axios.delete(`/api/v1/activities/${id}`); setSummary(null); await fetchData(); }
    catch (e: any) { setError(e.response?.data?.detail || 'Erro ao excluir atividade.'); }
  };
  const handleDeletePrecedence = async (id: number) => {
    try { await axios.delete(`/api/v1/activities/precedences/${id}`); setSummary(null); await fetchData(); }
    catch (e: any) { setError(e.response?.data?.detail || 'Erro ao excluir precedência.'); }
  };

  const hasSchedule = activities.some(a => a.ef !== 0 || a.lf !== 0 || a.es !== 0 || a.is_critical === 1);
  const maxDay = Math.max(1, ...activities.map(a => Math.max(a.ef || 0, a.duration || 0)));
  const ticks = useMemo(() => Array.from({length: Math.min(10, Math.max(2, Math.ceil(maxDay / 7) + 1))}, (_,i)=>Math.round(i*maxDay/(Math.min(10, Math.max(2, Math.ceil(maxDay / 7) + 1))-1))), [maxDay]);
  const byId = (id: number) => activities.find(a => a.id === id);

  return <div className="p-8 max-w-[1600px] mx-auto space-y-6">
    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
      <div><h2 className="text-2xl font-extrabold text-slate-100 flex items-center gap-3"><CalendarDays className="w-7 h-7 text-blue-500"/>Cronograma e caminho crítico</h2><p className="text-sm text-slate-400 mt-1">Rede de precedências e gráfico temporal calculado pelo motor CPM.</p></div>
      <div className="flex gap-2"><button onClick={fetchData} className="px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-200 text-sm flex items-center gap-2"><RefreshCw className="w-4 h-4"/>Atualizar</button><button onClick={handleRunCPM} className="px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl font-semibold flex items-center gap-2"><Play className="w-4 h-4"/>Calcular CPM</button></div>
    </div>
    {error && <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-sm">{error}</div>}
    {summary && <div className={`p-4 rounded-xl border ${summary.deadline_feasible ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-amber-500/10 border-amber-500/30'}`}><div className="font-semibold text-slate-100">{summary.deadline_feasible ? 'Cálculo concluído' : 'Atenção: prazo contratual incompatível'}</div><p className="text-sm text-slate-300 mt-1">Duração calculada: {summary.duration} dias · Término mais cedo: dia {summary.project_finish}{summary.project_deadline !== null ? ` · Prazo: ${summary.project_deadline} dias · Variação: ${summary.deadline_variance} dias` : ''}</p></div>}
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
      <form onSubmit={handleAdd} className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3 h-fit">
        <h3 className="font-bold text-slate-100">Nova atividade</h3>
        <label className="block text-xs text-slate-400">Código<input required value={code} onChange={e=>setCode(e.target.value)} className="mt-1 w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100" placeholder="EST-001"/></label>
        <label className="block text-xs text-slate-400">Nome<input required value={name} onChange={e=>setName(e.target.value)} className="mt-1 w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100" placeholder="Execução das fundações"/></label>
        <label className="block text-xs text-slate-400">Duração (dias)<input type="number" min="0" step="0.5" required value={duration} onChange={e=>setDuration(Number(e.target.value))} className="mt-1 w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100"/></label>
        <label className="block text-xs text-slate-400">Nó da EAP<select value={wbsId} onChange={e=>setWbsId(e.target.value ? Number(e.target.value) : '')} className="mt-1 w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100"><option value="">Sem vínculo</option>{wbs.map(n=><option key={n.id} value={n.id}>{n.code} — {n.name}</option>)}</select></label>
        <button className="w-full py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-semibold text-sm flex items-center justify-center gap-2"><Plus className="w-4 h-4"/>Adicionar atividade</button>
      </form>
      <form onSubmit={handleAddPrecedence} className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3 h-fit">
        <h3 className="font-bold text-slate-100 flex items-center gap-2"><Link2 className="w-4 h-4 text-blue-400"/>Nova precedência</h3>
        <label className="block text-xs text-slate-400">Predecessora<select required value={predId} onChange={e=>setPredId(e.target.value ? Number(e.target.value) : '')} className="mt-1 w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100"><option value="">Selecione</option>{activities.map(a=><option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}</select></label>
        <label className="block text-xs text-slate-400">Sucessora<select required value={succId} onChange={e=>setSuccId(e.target.value ? Number(e.target.value) : '')} className="mt-1 w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100"><option value="">Selecione</option>{activities.map(a=><option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}</select></label>
        <div className="grid grid-cols-2 gap-2"><label className="block text-xs text-slate-400">Relação<select value={relation} onChange={e=>setRelation(e.target.value)} className="mt-1 w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100"><option>FS</option><option>SS</option><option>FF</option><option>SF</option></select></label><label className="block text-xs text-slate-400">Lag (dias)<input type="number" step="0.5" value={lag} onChange={e=>setLag(Number(e.target.value))} className="mt-1 w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100"/></label></div>
        <button disabled={activities.length < 2} className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white rounded-lg font-semibold text-sm">Adicionar relação</button>
      </form>
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 h-fit"><h3 className="font-bold text-slate-100 mb-3">Relações cadastradas</h3>{precs.length === 0 ? <p className="text-xs text-slate-500">Nenhuma precedência cadastrada.</p> : <div className="space-y-2 max-h-64 overflow-y-auto">{precs.map(p=><div key={p.id} className="flex items-center justify-between gap-2 text-xs bg-slate-800/70 rounded-lg p-2"><span className="text-slate-300 min-w-0 truncate">{byId(p.predecessor_id)?.code || p.predecessor_id} → {byId(p.successor_id)?.code || p.successor_id} <b className="text-blue-300">{p.relation_type}{p.lag ? ` ${p.lag>0?'+':''}${p.lag}` : ''}</b></span><button onClick={()=>handleDeletePrecedence(p.id)} title="Excluir relação" className="text-red-400"><Trash2 className="w-3.5 h-3.5"/></button></div>)}</div>}</div>
    </div>
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 overflow-hidden">
      <div className="flex items-center justify-between mb-4"><div><h3 className="font-bold text-slate-100">Gráfico de Gantt</h3><p className="text-xs text-slate-500 mt-1">Escala relativa em dias a partir do início do projeto.</p></div><div className="flex gap-3 text-[11px] text-slate-400"><span> <i className="inline-block w-3 h-3 rounded-sm bg-blue-500 mr-1"/>Normal</span><span><i className="inline-block w-3 h-3 rounded-sm bg-red-500 mr-1"/>Crítica</span></div></div>
      {loading ? <p className="text-sm text-slate-400 py-8 text-center">Carregando cronograma...</p> : activities.length === 0 ? <p className="text-sm text-slate-400 py-8 text-center">Cadastre atividades para construir o cronograma.</p> : !hasSchedule ? <p className="text-sm text-amber-300 py-8 text-center">As atividades ainda não possuem datas calculadas. Execute o motor CPM para gerar as barras do Gantt.</p> : <div className="overflow-x-auto"><div className="min-w-[850px] relative">
        <div className="grid grid-cols-[260px_1fr] border-b border-slate-700 pb-2 mb-1"><div className="text-xs text-slate-500">Atividade</div><div className="relative h-6">{ticks.map((t,i)=><span key={`${t}-${i}`} className="absolute text-[10px] text-slate-500 -translate-x-1/2" style={{left:`${(t/maxDay)*100}%`}}>D{t}</span>)}</div></div>
        <div className="absolute left-[260px] right-0 top-[29px] pointer-events-none z-10" style={{height:`${activities.length*42}px`}}><svg viewBox={`0 0 1000 ${activities.length*42}`} preserveAspectRatio="none" className="w-full h-full">{precs.map(p=>{const pi=activities.findIndex(a=>a.id===p.predecessor_id);const si=activities.findIndex(a=>a.id===p.successor_id);if(pi<0||si<0)return null;const pred=activities[pi];const succ=activities[si];const x1=Math.max(0,Math.min(1000,(pred.ef/maxDay)*1000));const x2=Math.max(0,Math.min(1000,(succ.es/maxDay)*1000));const y1=pi*42+21;const y2=si*42+21;return <path key={p.id} d={`M ${x1} ${y1} C ${x1+18} ${y1}, ${x2-18} ${y2}, ${x2} ${y2}`} fill="none" stroke="#94a3b8" strokeWidth="1.5" markerEnd="url(#gantt-arrow)"/>})}<defs><marker id="gantt-arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#94a3b8"/></marker></defs></svg></div>
        <div className="relative">{activities.map(a=>{const start=Number(a.es||0); const finish=Number(a.ef||0); const width=Math.max(0.8,((a.duration||0)/maxDay)*100); const left=(start/maxDay)*100; return <div key={a.id} className="grid grid-cols-[260px_1fr] items-center border-b border-slate-800/70 min-h-[42px]"><div className="pr-3 min-w-0"><div className="text-xs font-mono text-blue-400">{a.code}</div><div className="text-xs text-slate-200 truncate" title={a.name}>{a.name}</div></div><div className="relative h-8 bg-slate-800/40 rounded-sm" style={{backgroundImage:'linear-gradient(to right, rgba(148,163,184,.12) 1px, transparent 1px)',backgroundSize:`${100/Math.max(1,ticks.length-1)}% 100%`}}><div title={`${a.name}: ES ${start}, EF ${finish}, duração ${a.duration} dias`} className={`absolute top-1 h-6 rounded-md ${a.is_critical ? 'bg-red-500' : 'bg-blue-500'} shadow-sm`} style={{left:`${Math.max(0,left)}%`,width:`${Math.min(width,100-Math.max(0,left))}%`,minWidth:'4px'}}/><span className="absolute top-1/2 -translate-y-1/2 text-[10px] text-slate-400" style={{left:`${Math.min(99,left+width+0.5)}%`}}> {a.duration}d</span></div></div>})}</div>
      </div></div>}
    </div>
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 overflow-x-auto"><h3 className="font-bold text-slate-100 mb-3">Dados calculados</h3><table className="w-full text-xs min-w-[780px]"><thead><tr className="text-slate-400 border-b border-slate-800"><th className="text-left py-2">Código</th><th className="text-left">Atividade</th><th>Dur.</th><th>ES</th><th>EF</th><th>LS</th><th>LF</th><th>Folga total</th><th>Folga livre</th><th>Crítica</th><th>Ação</th></tr></thead><tbody>{activities.map(a=><tr key={a.id} className="border-b border-slate-800/60 text-slate-300"><td className="py-2 font-mono text-blue-400">{a.code}</td><td className="text-left">{a.name}</td><td className="text-center"><input key={`${a.id}-${a.duration}`} aria-label={`Duração de ${a.code}`} type="number" min="0" step="0.5" defaultValue={a.duration} onBlur={e=>handleUpdateDuration(a,Number(e.target.value))} className="w-14 bg-slate-800 border border-slate-700 rounded px-1 py-1 text-center text-slate-200"/></td><td className="text-center">{a.es}</td><td className="text-center">{a.ef}</td><td className="text-center">{a.ls}</td><td className="text-center">{a.lf}</td><td className="text-center">{a.tf}</td><td className="text-center">{a.ff}</td><td className="text-center">{a.is_critical ? <span className="text-red-400 font-bold">Sim</span> : 'Não'}</td><td className="text-center"><button onClick={()=>handleDeleteActivity(a.id)} className="text-red-400 hover:text-red-300"><Trash2 className="w-4 h-4"/></button></td></tr>)}</tbody></table></div>
  </div>;
};
