import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Calculator, CheckCircle2, ChevronDown, ChevronRight, Layers, ListChecks, Play, RefreshCw, RotateCcw, Wand2 } from 'lucide-react';
import {
  ActivityOverride, ApplyResult, generatorService, LevelMode, Proposal, ScheduleService, TakeoffModel,
} from '../../services/generator';
import { jobService } from '../../services/jobs';
import { getErrorMessage } from '../../services/apiClient';
import { Notice } from '../../components/feedback/StatusViews';
import { Job } from '../../types/api';

interface Props { projectId: number; onOpenGantt?: () => void }

const TAKEOFF_LABEL: Record<string, string> = {
  none: 'Não calculado', queued: 'Na fila', processing: 'Calculando', completed: 'Concluído', failed: 'Falhou', cancelled: 'Cancelado',
};
const fmt = (v: number, digits = 2) => v.toLocaleString('pt-BR', { maximumFractionDigits: digits, minimumFractionDigits: 0 });
const card = 'bg-slate-900 border border-slate-800 rounded-xl p-5';
const input = 'bg-slate-800 border border-slate-700 rounded-md px-2 py-1 text-xs text-slate-100 w-full';

/**
 * Gerar cronograma a partir do IFC, por regras (sem IA):
 * 1) quantitativos por elemento; 2) catálogo de serviços e produtividades; 3) pré-visualização editável;
 * 4) aceitar → EAP, atividades, precedências, vínculos com elementos e CPM.
 */
export const GeneratorModule: React.FC<Props> = ({ projectId, onOpenGantt }) => {
  const [models, setModels] = useState<TakeoffModel[]>([]);
  const [jobs, setJobs] = useState<Record<string, Job>>({});
  const [selected, setSelected] = useState<number[]>([]);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [details, setDetails] = useState<Record<number, TakeoffModel>>({});
  const [services, setServices] = useState<ScheduleService[]>([]);
  const [showServices, setShowServices] = useState(false);
  const [levelMode, setLevelMode] = useState<LevelMode>('auto');
  const [bandHeight, setBandHeight] = useState(3);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [overrides, setOverrides] = useState<Record<string, ActivityOverride>>({});
  const [replacePrevious, setReplacePrevious] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [result, setResult] = useState<ApplyResult | null>(null);

  const loadModels = useCallback(async () => {
    try {
      const data = await generatorService.projectModels(projectId);
      setModels(data);
      setSelected((cur) => (cur.length ? cur.filter((id) => data.some((m) => m.model_id === id))
        : data.filter((m) => m.is_current).map((m) => m.model_id)));
      const active = data.filter((m) => (m.status === 'queued' || m.status === 'processing') && m.job_id);
      const fetched = await Promise.all(active.map((m) => jobService.get(m.job_id as string).catch(() => null)));
      setJobs(Object.fromEntries(fetched.filter(Boolean).map((j) => [(j as Job).id, j as Job])));
    } catch (e) { setError(getErrorMessage(e, 'Falha ao carregar os modelos IFC.')); }
  }, [projectId]);

  const loadServices = useCallback(async () => {
    try { setServices(await generatorService.listServices(projectId)); }
    catch (e) { setError(getErrorMessage(e, 'Falha ao carregar o catálogo de serviços.')); }
  }, [projectId]);

  useEffect(() => { loadModels(); loadServices(); }, [loadModels, loadServices]);
  const anyRunning = models.some((m) => m.status === 'queued' || m.status === 'processing');
  useEffect(() => {
    if (!anyRunning) return;
    const t = window.setInterval(loadModels, 1500);
    return () => window.clearInterval(t);
  }, [anyRunning, loadModels]);

  const toggleExpand = async (modelId: number) => {
    if (expanded === modelId) { setExpanded(null); return; }
    setExpanded(modelId);
    try { const d = await generatorService.modelTakeoff(modelId); setDetails((cur) => ({ ...cur, [modelId]: d })); }
    catch (e) { setError(getErrorMessage(e)); }
  };

  const startTakeoff = async (ids: number[]) => {
    setError(''); setNotice('');
    try {
      for (const id of ids) await generatorService.startTakeoff(id);
      setNotice(`Cálculo de quantitativos iniciado para ${ids.length} modelo(s). Ele roda em segundo plano.`);
      setProposal(null);
      await loadModels();
    } catch (e) { setError(getErrorMessage(e, 'Não foi possível iniciar o cálculo.')); }
  };

  const saveService = async (svc: ScheduleService, patch: Partial<ScheduleService> & { clear_productivity?: boolean }) => {
    try {
      const updated = await generatorService.updateService(svc.id, patch);
      setServices((cur) => cur.map((s) => (s.id === updated.id ? updated : s)));
      setProposal(null);
    } catch (e) { setError(getErrorMessage(e, 'Não foi possível salvar o serviço.')); }
  };

  const resetServices = async () => {
    if (!window.confirm('Restaurar o catálogo padrão? As produtividades cadastradas neste projeto serão apagadas.')) return;
    try { setServices(await generatorService.resetServices(projectId)); setProposal(null); }
    catch (e) { setError(getErrorMessage(e)); }
  };

  const readyIds = selected.filter((id) => models.find((m) => m.model_id === id)?.status === 'completed');
  const pendingSelected = selected.filter((id) => models.find((m) => m.model_id === id)?.status !== 'completed');

  const runPreview = async () => {
    setError(''); setNotice(''); setResult(null);
    setBusy('preview');
    try {
      setProposal(await generatorService.preview(projectId, { model_ids: readyIds, level_mode: levelMode, band_height_m: bandHeight }));
      setOverrides({});
    } catch (e) { setError(getErrorMessage(e, 'Falha ao gerar a pré-visualização.')); }
    finally { setBusy(null); }
  };

  const setOverride = (key: string, patch: Partial<ActivityOverride>) =>
    setOverrides((cur) => ({ ...cur, [key]: { ...cur[key], key, ...patch } }));

  const activities = useMemo(() => (proposal?.activities ?? []).map((a) => {
    const o = overrides[a.key] ?? {};
    const duration = o.duration ?? a.duration;
    return { ...a, include: o.include ?? a.include, name: o.name ?? a.name, duration,
      provisional: a.provisional && (o.duration === undefined || o.duration === a.duration) };
  }), [proposal, overrides]);
  const included = activities.filter((a) => a.include);

  const apply = async () => {
    if (!proposal) return;
    setError(''); setNotice(''); setBusy('apply');
    try {
      const res = await generatorService.apply(projectId, {
        model_ids: readyIds, level_mode: levelMode, band_height_m: bandHeight, replace_previous: replacePrevious, run_cpm: true,
        overrides: Object.values(overrides),
      });
      setResult(res);
      setNotice(`Cronograma criado: ${res.activities} atividades, ${res.precedences} precedências e ${res.element_links} vínculos com elementos.`);
    } catch (e) { setError(getErrorMessage(e, 'Falha ao criar o cronograma.')); }
    finally { setBusy(null); }
  };

  const byLevel = useMemo(() => {
    const groups = new Map<string, typeof activities>();
    for (const a of activities) groups.set(a.level_name, [...(groups.get(a.level_name) ?? []), a]);
    return Array.from(groups.entries());
  }, [activities]);

  return (
    <div className="p-8 space-y-5 max-w-[1400px]">
      <div>
        <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2"><Wand2 className="w-5 h-5 text-violet-400" />Gerar cronograma a partir do IFC</h2>
        <p className="text-xs text-slate-400 mt-1 max-w-3xl">
          Por regras, sem IA: EAP por nível (pavimento ou faixa de cota) × serviço. Quantidades em SI com a fonte de cada medida
          (Qto do IFC, Pset do autor, geometria ou contagem). Duração = quantidade ÷ produtividade; sem produtividade cadastrada,
          a duração padrão é usada e a atividade fica marcada como <span className="text-amber-300 font-semibold">provisória</span>.
        </p>
      </div>
      {error && <Notice tone="error" onDismiss={() => setError('')}>{error}</Notice>}
      {notice && <Notice tone="success" onDismiss={() => setNotice('')}>{notice}</Notice>}

      {/* 1. Modelos e quantitativos */}
      <section className={card}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-bold text-slate-100 flex items-center gap-2 text-sm"><Calculator className="w-4 h-4 text-blue-400" />1. Modelos e quantitativos</h3>
          <div className="flex gap-2">
            <button onClick={loadModels} className="px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-xs text-slate-300 flex items-center gap-1"><RefreshCw className="w-3.5 h-3.5" />Atualizar</button>
            <button disabled={!selected.length || anyRunning} onClick={() => startTakeoff(selected)}
              className="px-3 py-1.5 rounded-lg bg-blue-600 disabled:opacity-40 text-white text-xs font-semibold flex items-center gap-1">
              <Calculator className="w-3.5 h-3.5" />Calcular quantitativos dos selecionados
            </button>
          </div>
        </div>
        {models.length === 0 && <p className="text-xs text-slate-400">Nenhum modelo IFC processado neste projeto. Importe em <b>Modelos IFC & 3D</b>.</p>}
        <div className="space-y-2">
          {models.map((m) => {
            const job = m.job_id ? jobs[m.job_id] : undefined;
            const s = m.summary;
            return (
              <div key={m.model_id} className="rounded-lg border border-slate-700 bg-slate-800">
                <div className="flex items-center gap-3 p-3 text-xs">
                  <input type="checkbox" aria-label={`Selecionar ${m.filename}`} checked={selected.includes(m.model_id)}
                    onChange={(e) => setSelected((cur) => e.target.checked ? [...cur, m.model_id] : cur.filter((id) => id !== m.model_id))} />
                  <button onClick={() => toggleExpand(m.model_id)} className="text-slate-400" aria-label="Detalhes">
                    {expanded === m.model_id ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                  </button>
                  <span className="font-semibold text-slate-200 flex-1 truncate">{m.filename}{!m.is_current && <span className="ml-2 text-[10px] text-slate-500">(revisão anterior)</span>}</span>
                  <span className="text-slate-500">{m.element_count} produtos IFC</span>
                  <span data-testid={`takeoff-status-${m.model_id}`} className={`px-2 py-0.5 rounded-full text-[11px] ${m.status === 'completed' ? 'bg-emerald-500/15 text-emerald-300' : m.status === 'failed' ? 'bg-red-500/15 text-red-300' : 'bg-slate-800 text-slate-300'}`}>
                    {TAKEOFF_LABEL[m.status] ?? m.status}{job && !job.is_terminal ? ` ${job.progress}%` : ''}
                  </span>
                  <button disabled={m.status === 'queued' || m.status === 'processing'} onClick={() => startTakeoff([m.model_id])}
                    className="px-2 py-1 rounded-md bg-slate-800 border border-slate-700 disabled:opacity-40 text-slate-200">
                    {m.status === 'completed' ? 'Recalcular' : 'Calcular'}
                  </button>
                </div>
                {job && !job.is_terminal && <div className="px-3 pb-3"><div className="h-1.5 rounded-full bg-slate-800 overflow-hidden"><div className="h-full bg-blue-500" style={{ width: `${job.progress}%` }} /></div><p className="text-[10px] text-slate-500 mt-1">{job.message}</p></div>}
                {m.status === 'failed' && m.error_message && <p className="px-3 pb-3 text-[11px] text-red-300">{m.error_message}</p>}
                {s && <p className="px-3 pb-2 text-[11px] text-slate-400">
                  {s.included} elementos quantificados ({s.excluded} excluídos: aberturas/conjuntos) · geometria em {s.with_geometry} de {s.geometry_attempted} ·
                  unidades do arquivo: comprimento {s.units.length}, área {s.units.area}, volume {s.units.volume}
                </p>}
                {expanded === m.model_id && details[m.model_id]?.totals && (
                  <div className="px-3 pb-3 overflow-x-auto">
                    <table className="w-full text-[11px]">
                      <thead className="text-slate-500"><tr><th className="text-left py-1">Tipo IFC</th><th className="text-right">Qtd</th><th className="text-right">Volume (m³)</th><th className="text-right">Área (m²)</th><th className="text-right">Compr. (m)</th><th className="text-right">Peso (kg)</th><th className="text-right">Com geometria</th></tr></thead>
                      <tbody className="text-slate-300">
                        {Object.entries(details[m.model_id].totals!.by_type).map(([t, v]) => (
                          <tr key={t} className="border-t border-slate-800"><td className="py-1">{t}</td><td className="text-right">{v.count}</td><td className="text-right">{fmt(v.volume_m3)}</td><td className="text-right">{fmt(v.area_m2)}</td><td className="text-right">{fmt(v.length_m)}</td><td className="text-right">{fmt(v.weight_kg, 0)}</td><td className="text-right">{v.with_geometry}</td></tr>
                        ))}
                      </tbody>
                    </table>
                    {s?.sources_by_measure && <p className="mt-2 text-[10px] text-slate-500">Fontes: {Object.entries(s.sources_by_measure).map(([k, v]) => `${k}: ${Object.entries(v).map(([src, n]) => `${src} ${n}`).join(', ')}`).join(' · ')}</p>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* 2. Serviços */}
      <section className={card}>
        <div className="flex items-center justify-between">
          <button onClick={() => setShowServices(!showServices)} className="font-bold text-slate-100 flex items-center gap-2 text-sm">
            {showServices ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}<ListChecks className="w-4 h-4 text-emerald-400" />2. Serviços, regras e produtividades
            <span className="text-[11px] font-normal text-slate-400">({services.filter((s) => s.productivity_per_day).length} de {services.length} com produtividade)</span>
          </button>
          {showServices && <button onClick={resetServices} className="px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-xs text-slate-300 flex items-center gap-1"><RotateCcw className="w-3.5 h-3.5" />Restaurar padrão</button>}
        </div>
        {showServices && (
          <div className="mt-3 overflow-x-auto">
            <p className="text-[11px] text-slate-400 mb-2">Produtividade = quantidade executada por dia, na unidade do serviço. Deixe vazio quando não houver índice confiável: a duração padrão será usada como provisória.</p>
            <table className="w-full text-[11px]">
              <thead className="text-slate-500"><tr>
                <th className="text-left py-1">Ativo</th><th className="text-left">Código</th><th className="text-left">Serviço</th><th className="text-left">Tipos IFC</th>
                <th className="text-left">Unid.</th><th className="text-left w-28">Produtividade / dia</th><th className="text-left w-24">Duração padrão (d)</th><th className="text-left">Predecessores</th><th className="text-left">Incluir</th>
              </tr></thead>
              <tbody className="text-slate-300">
                {services.map((s) => (
                  <tr key={s.id} className="border-t border-slate-800 align-top">
                    <td className="py-1.5"><input type="checkbox" checked={s.is_active} onChange={(e) => saveService(s, { is_active: e.target.checked })} /></td>
                    <td className="font-mono">{s.code}</td>
                    <td><input className={input} defaultValue={s.name} onBlur={(e) => e.target.value !== s.name && e.target.value.trim() && saveService(s, { name: e.target.value })} /></td>
                    <td className="max-w-[260px]"><input className={input} title={s.ifc_types} defaultValue={s.ifc_types} onBlur={(e) => e.target.value !== s.ifc_types && saveService(s, { ifc_types: e.target.value })} />{s.material_class && <span className="text-[10px] text-slate-500">material: {s.material_class === 'steel' ? 'aço' : 'não aço'}</span>}</td>
                    <td>{s.unit}</td>
                    <td><input aria-label={`Produtividade ${s.code}`} type="number" min={0} step="any" className={input} defaultValue={s.productivity_per_day ?? ''} placeholder="sem índice"
                      onBlur={(e) => {
                        const v = e.target.value.trim();
                        if (!v && s.productivity_per_day != null) saveService(s, { clear_productivity: true });
                        else if (v && Number(v) > 0 && Number(v) !== s.productivity_per_day) saveService(s, { productivity_per_day: Number(v) });
                      }} /></td>
                    <td><input type="number" min={0} step="any" className={input} defaultValue={s.default_duration_days}
                      onBlur={(e) => Number(e.target.value) !== s.default_duration_days && Number(e.target.value) >= 0 && saveService(s, { default_duration_days: Number(e.target.value) })} /></td>
                    <td><input className={input} defaultValue={s.predecessors ?? ''} onBlur={(e) => e.target.value !== (s.predecessors ?? '') && saveService(s, { predecessors: e.target.value })} /></td>
                    <td><input type="checkbox" checked={s.include_by_default} onChange={(e) => saveService(s, { include_by_default: e.target.checked })} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* 3. Pré-visualização */}
      <section className={card}>
        <div className="flex flex-wrap items-end gap-3 mb-3">
          <h3 className="font-bold text-slate-100 flex items-center gap-2 text-sm mr-auto"><Layers className="w-4 h-4 text-violet-400" />3. Pré-visualizar e revisar</h3>
          <label className="text-[11px] text-slate-400">Níveis
            <select value={levelMode} onChange={(e) => setLevelMode(e.target.value as LevelMode)} className={`${input} mt-1 w-56`}>
              <option value="auto">Automático (pavimentos; faixas se houver só um)</option>
              <option value="storey">Pavimentos do IFC</option>
              <option value="elevation">Faixas de cota</option>
            </select>
          </label>
          <label className="text-[11px] text-slate-400">Altura da faixa (m)
            <input type="number" min={0.5} step={0.5} value={bandHeight} onChange={(e) => setBandHeight(Number(e.target.value) || 3)} className={`${input} mt-1 w-24`} />
          </label>
          <button disabled={!readyIds.length || busy !== null} onClick={runPreview}
            className="px-4 py-2 rounded-lg bg-violet-600 disabled:opacity-40 text-white text-xs font-semibold flex items-center gap-1.5">
            <Play className="w-3.5 h-3.5" />{busy === 'preview' ? 'Gerando…' : 'Pré-visualizar cronograma'}
          </button>
        </div>
        {pendingSelected.length > 0 && <p className="text-[11px] text-amber-300 mb-2">{pendingSelected.length} modelo(s) selecionado(s) sem quantitativos calculados ficarão de fora.</p>}
        {proposal && (
          <>
            <div className="flex flex-wrap gap-4 text-xs text-slate-300 mb-3">
              <span>Níveis: <b>{proposal.levels.length}</b> ({proposal.level_mode === 'storey' ? 'pavimentos' : 'faixas de cota'})</span>
              <span>Atividades: <b>{included.length}</b> de {activities.length}</span>
              <span>Provisórias: <b className="text-amber-300">{included.filter((a) => a.provisional).length}</b></span>
              <span>Precedências: <b>{proposal.precedences.length}</b></span>
              <span>Elementos: <b>{proposal.stats.elements}</b></span>
            </div>
            {Object.keys(proposal.unmapped).length > 0 && <p className="text-[11px] text-slate-400 mb-2">Tipos sem serviço: {Object.entries(proposal.unmapped).map(([t, n]) => `${t} (${n})`).join(', ')}</p>}
            {proposal.warnings.map((w) => <p key={w} className="text-[11px] text-amber-300">{w}</p>)}
            <div className="overflow-x-auto max-h-[60vh] overflow-y-auto border border-slate-800 rounded-lg">
              <table className="w-full text-[11px]">
                <thead className="text-slate-500 sticky top-0 bg-slate-900"><tr>
                  <th className="p-2 text-left">Incluir</th><th className="text-left">Código</th><th className="text-left">Atividade</th><th className="text-right">Quantidade</th>
                  <th className="text-right">Cobertura</th><th className="text-right">Prod./dia</th><th className="text-left w-24 pl-2">Duração (d)</th><th className="text-right">Elementos</th><th className="text-left pl-2">Situação</th>
                </tr></thead>
                <tbody className="text-slate-300">
                  {byLevel.map(([level, acts]) => (
                    <React.Fragment key={level}>
                      <tr className="bg-slate-800/60"><td colSpan={9} className="p-2 font-semibold text-slate-200">{level}</td></tr>
                      {acts.map((a) => (
                        <tr key={a.key} className={`border-t border-slate-800 ${a.include ? '' : 'opacity-50'}`} data-testid={`proposal-${a.code}`}>
                          <td className="p-2"><input type="checkbox" aria-label={`Incluir ${a.code}`} checked={a.include} onChange={(e) => setOverride(a.key, { include: e.target.checked })} /></td>
                          <td className="font-mono">{a.code}</td>
                          <td className="min-w-[260px] pr-2"><input className={input} value={a.name} onChange={(e) => setOverride(a.key, { name: e.target.value })} /></td>
                          <td className="text-right whitespace-nowrap">{fmt(a.quantity)} {a.unit}</td>
                          <td className="text-right">{a.quantity_basis === 'count' ? '—' : `${Math.round(a.coverage * 100)}%`}</td>
                          <td className="text-right">{a.productivity ?? '—'}</td>
                          <td className="pl-2"><input aria-label={`Duração ${a.code}`} type="number" min={0} step="any" className={input} value={a.duration} onChange={(e) => setOverride(a.key, { duration: Number(e.target.value) })} /></td>
                          <td className="text-right">{a.element_count}</td>
                          <td className="pl-2">{a.provisional
                            ? <span title={a.provisional_reason ?? ''} className="px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300">provisória</span>
                            : <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300">calculada</span>}
                            {a.provisional && <span className="ml-1 text-[10px] text-slate-500">{a.provisional_reason}</span>}</td>
                        </tr>
                      ))}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex flex-wrap items-center gap-4 mt-4">
              <label className="text-xs text-slate-300 flex items-center gap-2"><input type="checkbox" checked={replacePrevious} onChange={(e) => setReplacePrevious(e.target.checked)} />Substituir o cronograma gerado anteriormente (atividades criadas à mão não são tocadas)</label>
              <button disabled={!included.length || busy !== null} onClick={apply}
                className="ml-auto px-4 py-2 rounded-lg bg-emerald-600 disabled:opacity-40 text-white text-xs font-semibold flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4" />{busy === 'apply' ? 'Criando…' : `Aceitar e criar cronograma (${included.length} atividades)`}
              </button>
            </div>
          </>
        )}
        {result && (
          <div className="mt-4 p-4 rounded-lg border border-emerald-700 bg-emerald-500/10 text-xs text-emerald-200 space-y-1" data-testid="generator-result">
            <p className="font-semibold">Geração {result.number} criada.</p>
            <p>{result.activities} atividades ({result.provisional} provisórias), {result.precedences} precedências, {result.element_links} vínculos com elementos IFC
              {result.removed_previous ? `; ${result.removed_previous} atividades da geração anterior removidas` : ''}.</p>
            {result.cpm?.status === 'success' && <p>CPM calculado: duração total <b>{fmt(result.cpm.duration ?? 0, 1)} dias</b>, {result.cpm.critical_activities} atividades críticas.</p>}
            {result.cpm?.status === 'success' && result.cpm.project_deadline != null && (
              <p className={result.cpm.deadline_feasible ? 'text-emerald-200/80' : 'text-red-300'}>
                Prazo contratual do projeto: {fmt(result.cpm.project_deadline, 0)} dias. {result.cpm.deadline_feasible
                  ? 'As folgas são medidas até esse prazo; por isso pode não haver atividades críticas quando ele é maior que a duração calculada.'
                  : 'A duração calculada ultrapassa o prazo contratual.'}
              </p>)}
            {result.cpm?.status === 'error' && <p className="text-red-300">CPM não calculado: {result.cpm.message}</p>}
            {onOpenGantt && <button onClick={onOpenGantt} className="mt-2 px-3 py-1.5 rounded-lg bg-emerald-600 text-white font-semibold">Abrir Gráfico de Gantt</button>}
          </div>
        )}
      </section>
    </div>
  );
};

export default GeneratorModule;
