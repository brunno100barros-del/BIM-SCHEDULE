/* BIM SCHEDULE — módulos funcionais locais, versão 0.5.0-dev
 * Dados e arquivos permanecem no navegador. Não substitui backend multiusuário.
 */
(function () {
  "use strict";

  const EXT_KEY = "bimschedule.extensions.v1";
  const PROJECTS_KEY = "bimschedule.projects.v1";
  const loadJson = (key, fallback) => {
    try { const value = JSON.parse(localStorage.getItem(key)); return value ?? fallback; }
    catch (_) { return fallback; }
  };
  const ext = loadJson(EXT_KEY, {
    calendar: { startDate: "2026-11-02", weekdays: [1,2,3,4,5], holidays: [] },
    resources: [], assignments: [], actualCosts: {}, scenarios: [], versions: [],
    snapshots: [], weather: { latitude: "", longitude: "", rainLimit: 5, result: null },
    projectId: "ADM-001"
  });
  const baseSave = save;
  const baseRender = render;
  const baseParseIfc = parseIfc;
  let projectStore = loadJson(PROJECTS_KEY, []);
  let viewer = null;
  let viewerPromise = null;
  let viewerTimer = null;
  let weatherBusy = false;
  let lastPert = null;

  function persistExt() { localStorage.setItem(EXT_KEY, JSON.stringify(ext)); }
  function currentProject() {
    return projectStore.find(p => p.id === ext.projectId) || null;
  }
  function projectPayload(includeIfcElements) {
    return { id: ext.projectId, name: ext.projectName || "Projeto modelo BIMOFFICE", code: ext.projectCode || "ADM-001",
      savedAt: new Date().toISOString(), activities: state.activities, audit: state.audit, ext: JSON.parse(JSON.stringify(ext)),
      ifc: ifcModel ? { name: ifcModel.name, schema: ifcModel.schema, uploadedAt: ifcModel.uploadedAt,
        mappings: ifcModel.mappings || {}, elements: includeIfcElements ? ifcElements : undefined } : null };
  }
  function persistProject() {
    const payload = projectPayload();
    const index = projectStore.findIndex(p => p.id === payload.id);
    if (index >= 0) projectStore[index] = payload; else projectStore.push(payload);
    localStorage.setItem(PROJECTS_KEY, JSON.stringify(projectStore));
  }
  save = function () { baseSave(); persistExt(); persistProject(); };
  function logEvent(action, detail) {
    if (typeof log === "function") log(action, detail);
    else { state.audit.unshift({ time: new Date().toLocaleString("pt-BR"), action, detail }); save(); }
  }
  function notifyUser(message) { if (typeof notify === "function") notify(message); else alert(message); }
  function downloadText(name, text, type) {
    const url = URL.createObjectURL(new Blob([text], { type: type || "application/octet-stream" }));
    const a = document.createElement("a"); a.href = url; a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  }
  function escHtml(value) { return String(value ?? "").replace(/[&<>"']/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c])); }
  function moneyBR(value) { return Number(value || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 2 }); }
  function isoDate(value) { return new Date(value + "T12:00:00"); }
  function formatDate(value) { return isoDate(value).toLocaleDateString("pt-BR"); }
  function isWorkingDay(date) { return ext.calendar.weekdays.includes(date.getDay()) && !ext.calendar.holidays.includes(date.toISOString().slice(0,10)); }
  function addWorkingDays(start, count) {
    const d = new Date(start.getFullYear(), start.getMonth(), start.getDate(), 12);
    let remaining = Math.max(0, Math.round(Number(count) || 0));
    while (remaining > 0) { d.setDate(d.getDate() + 1); if (isWorkingDay(d)) remaining--; }
    return d;
  }
  function dateForDay(day) {
    const start = isoDate(ext.calendar.startDate || "2026-11-02");
    if (!isWorkingDay(start)) {
      let d = new Date(start); while (!isWorkingDay(d)) d.setDate(d.getDate() + 1);
      return addWorkingDays(d, Math.max(0, Number(day) - 1));
    }
    return addWorkingDays(start, day);
  }
  date = function (day) { return dateForDay(day).toLocaleDateString("pt-BR", { day:"2-digit", month:"short" }).replace(".", ""); };

  function relationsFor(activity) {
    const relations = Array.isArray(activity.relations) ? activity.relations : [];
    if (relations.length) return relations;
    return (activity.preds || []).map(id => ({ predecessorId: Number(id), type: "FS", lag: 0 }));
  }
  function edgeWeight(relation, predecessor, successor) {
    const lag = Number(relation.lag || 0), pd = Number(predecessor.duration || 0), sd = Number(successor.duration || 0);
    switch (String(relation.type || "FS").toUpperCase()) {
      case "SS": return lag;
      case "FF": return pd + lag - sd;
      case "SF": return lag - sd;
      default: return pd + lag;
    }
  }
  function buildNetwork(activities) {
    const byId = new Map(activities.map(a => [Number(a.id), a]));
    const edges = [];
    activities.forEach(successor => relationsFor(successor).forEach(r => {
      const predecessor = byId.get(Number(r.predecessorId ?? r.id));
      if (!predecessor) return;
      const type = String(r.type || r.relation_type || "FS").toUpperCase();
      if (!["FS","SS","FF","SF"].includes(type)) throw new Error("Relação inválida em " + successor.code + ": " + type);
      edges.push({ from: predecessor, to: successor, type, lag: Number(r.lag || 0) });
    }));
    const indegree = new Map(activities.map(a => [Number(a.id), 0]));
    edges.forEach(e => indegree.set(Number(e.to.id), indegree.get(Number(e.to.id)) + 1));
    const queue = activities.filter(a => indegree.get(Number(a.id)) === 0);
    const order = [];
    while (queue.length) {
      const a = queue.shift(); order.push(a);
      edges.filter(e => e.from.id === a.id).forEach(e => {
        const next = Number(e.to.id), value = indegree.get(next) - 1;
        indegree.set(next, value); if (value === 0) queue.push(e.to);
      });
    }
    if (order.length !== activities.length) throw new Error("A rede contém ciclo de precedências. Remova uma relação circular antes de recalcular.");
    return { byId, edges, order };
  }
  function calculateCpm(activities) {
    const { edges, order } = buildNetwork(activities);
    const es = new Map(), ef = new Map();
    order.forEach(a => {
      let start = 0;
      edges.filter(e => e.to.id === a.id).forEach(e => {
        const weight = edgeWeight(e, e.from, e.to);
        start = Math.max(start, (es.get(e.from.id) || 0) + weight);
      });
      es.set(a.id, start); ef.set(a.id, start + Number(a.duration || 0));
    });
    const finish = Math.max(0, ...activities.map(a => ef.get(a.id) || 0));
    const ls = new Map(), lf = new Map();
    [...order].reverse().forEach(a => {
      let latest = finish - Number(a.duration || 0);
      edges.filter(e => e.from.id === a.id).forEach(e => {
        const weight = edgeWeight(e, e.from, e.to);
        latest = Math.min(latest, (ls.get(e.to.id) ?? finish - Number(e.to.duration || 0)) - weight);
      });
      ls.set(a.id, latest); lf.set(a.id, latest + Number(a.duration || 0));
    });
    const results = {};
    activities.forEach(a => {
      const totalFloat = (ls.get(a.id) || 0) - (es.get(a.id) || 0);
      const outgoing = edges.filter(e => e.from.id === a.id);
      const freeFloat = outgoing.length ? Math.min(...outgoing.map(e => (es.get(e.to.id) || 0) - ((es.get(a.id) || 0) + edgeWeight(e, e.from, e.to)))) : finish - (ef.get(a.id) || 0);
      results[a.id] = { es: es.get(a.id), ef: ef.get(a.id), ls: ls.get(a.id), lf: lf.get(a.id), tf: totalFloat,
        ff: freeFloat, critical: Math.abs(totalFloat) < 0.000001 };
      a.start = results[a.id].es; a.critical = results[a.id].critical;
    });
    return { duration: finish, results, edges, order };
  }
  recalc = function () {
    try {
      const result = calculateCpm(state.activities);
      state.activities.forEach(a => {
        const r = result.results[a.id];
        a.start = r.es; a.finish = r.ef; a.ls = r.ls; a.lf = r.lf; a.totalFloat = r.tf; a.freeFloat = r.ff; a.critical = r.critical;
      });
      logEvent("CPM recalculado", "Duração da rede: " + result.duration + " dias úteis; relações FS/SS/FF/SF e lags considerados.");
      persistExt(); baseRender(); notifyUser("CPM recalculado: " + result.duration + " dias úteis.");
    } catch (error) { notifyUser(error.message); }
  };

  function toolbar() {
    const top = document.querySelector(".top");
    if (!top || document.getElementById("schedule-project-tools")) return;
    const tools = top.querySelector(".tools"); if (!tools) return;
    const wrap = document.createElement("div"); wrap.id = "schedule-project-tools"; wrap.className = "project-tools";
    wrap.innerHTML = '<button class="btn" data-project-action="save">Salvar</button><button class="btn" data-project-action="saveas">Salvar como</button><button class="btn" data-project-action="export">Exportar projeto</button><button class="btn" data-project-action="import">Abrir arquivo</button><select id="project-open" title="Abrir projeto local"><option value="">Projetos locais</option></select><button class="btn" data-project-action="delete">Excluir</button><input id="project-file" type="file" accept=".json,application/json" hidden>';
    tools.prepend(wrap);
    refreshProjectSelect();
  }
  function refreshProjectSelect() {
    const select = document.getElementById("project-open"); if (!select) return;
    select.innerHTML = '<option value="">Projetos locais</option>' + projectStore.map(p => '<option value="' + escHtml(p.id) + '" ' + (p.id === ext.projectId ? "selected" : "") + '>' + escHtml(p.code + " · " + p.name) + '</option>').join("");
  }
  function saveAsProject() {
    const name = prompt("Nome do novo projeto:", (ext.projectName || "Projeto") + " — Cópia"); if (!name || !name.trim()) return;
    const code = prompt("Código do novo projeto:", "PRJ-" + Date.now().toString().slice(-6)); if (!code || !code.trim()) return;
    ext.projectId = code.trim(); ext.projectName = name.trim(); ext.projectCode = code.trim();
    persistProject(); persistExt(); refreshProjectSelect(); notifyUser("Cópia local criada. As atividades atuais foram preservadas.");
  }
  function loadProject(id) {
    const p = projectStore.find(x => x.id === id); if (!p) return;
    if (!confirm("Abrir o projeto " + p.name + "? As alterações ainda não salvas do projeto atual serão substituídas.")) return;
    ext.projectId = p.id; ext.projectName = p.name; ext.projectCode = p.code;
    state.activities = JSON.parse(JSON.stringify(p.activities || [])); state.audit = JSON.parse(JSON.stringify(p.audit || []));
    Object.keys(ext).forEach(k => { if (!(k in (p.ext || {}))) delete ext[k]; });
    Object.assign(ext, p.ext || {}); ext.projectId = p.id;
    persistExt(); baseSave(); refreshProjectSelect(); baseRender();
  }
  function exportProject() {
    const payload = projectPayload(true);
    downloadText((payload.code || "BIM-SCHEDULE") + ".json", JSON.stringify(payload, null, 2), "application/json");
    logEvent("Projeto exportado", "Backup JSON gerado no dispositivo.");
  }
  async function importProject(file) {
    try {
      const p = JSON.parse(await file.text());
      if (!p || !Array.isArray(p.activities) || !p.code) throw new Error("Arquivo não reconhecido como projeto BIM SCHEDULE.");
      if (!confirm("Importar " + p.name + " e substituir o projeto atualmente aberto?")) return;
      ext.projectId = p.id || p.code; ext.projectName = p.name || p.code; ext.projectCode = p.code;
      Object.assign(ext, p.ext || {}); ext.projectId = p.id || p.code;
      state.activities = p.activities; state.audit = p.audit || [];
      if (p.ifc && Array.isArray(p.ifc.elements)) {
        ifcElements = p.ifc.elements; ifcModel = { id:"active", name:p.ifc.name, schema:p.ifc.schema, uploadedAt:p.ifc.uploadedAt, elements:ifcElements, mappings:p.ifc.mappings || {} };
      } else if (p.ifc && ifcModel && ifcModel.name === p.ifc.name) {
        ifcModel.mappings = p.ifc.mappings || {};
      } else if (!p.ifc || (ifcModel && ifcModel.name !== p.ifc.name)) {
        ifcModel = null; ifcElements = [];
      }
      if (p.ifc && !p.ifc.elements) notifyUser("Vínculos IFC importados. Reimporte o arquivo IFC original para abrir a geometria e o inventário completo.");
      persistProject(); persistExt(); baseSave(); refreshProjectSelect(); render();
    } catch (error) { notifyUser("Falha ao abrir projeto: " + error.message); }
  }
  document.addEventListener("click", e => {
    const button = e.target.closest("[data-project-action]"); if (!button) return;
    const action = button.dataset.projectAction;
    if (action === "save") { save(); notifyUser("Projeto salvo neste navegador."); }
    if (action === "saveas") saveAsProject();
    if (action === "export") exportProject();
    if (action === "import") document.getElementById("project-file")?.click();
    if (action === "delete") {
      if (!confirm("Excluir o projeto local atual? Esta ação não pode ser desfeita.")) return;
      projectStore = projectStore.filter(p => p.id !== ext.projectId); localStorage.setItem(PROJECTS_KEY, JSON.stringify(projectStore));
      notifyUser("Projeto removido da lista local. O projeto modelo será carregado.");
      ext.projectId = "ADM-001"; ext.projectName = "Edifício Administrativo BIMOFFICE"; ext.projectCode = "ADM-001";
      state.activities = seed.map(a => ({...a})); state.audit = seedAudit.slice(); persistExt(); save(); refreshProjectSelect(); render();
    }
  });
  document.addEventListener("change", e => {
    if (e.target.id === "project-open" && e.target.value) loadProject(e.target.value);
    if (e.target.id === "project-file" && e.target.files?.[0]) importProject(e.target.files[0]);
  });

  function financial() {
    const total = state.activities.reduce((s,a)=>s+Number(a.cost||0),0);
    const earned = state.activities.reduce((s,a)=>s+Number(a.cost||0)*Number(a.progress||0)/100,0);
    const ac = state.activities.reduce((s,a)=>s+Number(ext.actualCosts[a.id] ?? 0),0);
    const pv = state.activities.reduce((s,a)=> {
      const duration = Math.max(1, Number(a.duration||1));
      const elapsed = Math.max(0, Math.min(duration, max() - Number(a.start||0)));
      return s + Number(a.cost||0) * elapsed / duration;
    },0);
    const spi = pv > 0 ? earned/pv : 0, cpi = ac > 0 ? earned/ac : 0;
    const rows = state.activities.map(a => '<tr><td class="code">'+escHtml(a.code)+'</td><td>'+escHtml(a.name)+'</td><td><input type="number" min="0" step="0.01" data-base-cost="'+a.id+'" value="'+Number(a.cost||0)+'"></td><td>'+a.progress+'%</td><td><input type="number" min="0" step="0.01" data-actual-cost="'+a.id+'" value="'+Number(ext.actualCosts[a.id]||0)+'"></td><td>'+moneyBR(Number(a.cost||0)*Number(a.progress||0)/100)+'</td></tr>').join("");
    const ratios = [spi,cpi].map(x=>x.toFixed(2));
    return '<div class="stack"><div class="kpis">'+kpi("ORÇAMENTO BASE",moneyBR(total),"soma do orçamento por atividade","＄")+kpi("VALOR AGREGADO · EV",moneyBR(earned),"custo orçado do trabalho executado","◉")+kpi("CUSTO REAL · AC",moneyBR(ac),"apropriação informada pelo usuário","▤")+kpi("SALDO DO ORÇAMENTO",moneyBR(total-earned),"BAC menos EV","◎")+'</div><div class="g2">'+panel("INDICADORES DE VALOR AGREGADO","CALCULADOS COM OS DADOS INFORMADOS",'<div class="row">PV · Valor planejado<b>'+moneyBR(pv)+'</b></div><div class="row">EV · Valor agregado<b>'+moneyBR(earned)+'</b></div><div class="row">AC · Custo real<b>'+moneyBR(ac)+'</b></div><div class="row">SPI · EV / PV<b>'+ratios[0]+'</b></div><div class="row">CPI · EV / AC<b>'+ratios[1]+'</b></div><div class="row">EAC · Estimativa ao término<b>'+moneyBR(cpi>0?total/cpi:0)+'</b></div>')+panel("CURVA S","ACUMULADO POR DIA DE TRABALHO",'<div class="chart"><svg viewBox="0 0 600 190">'+[35,75,115,155].map(y=>'<line x1="35" x2="580" y1="'+y+'" y2="'+y+'" stroke="var(--line)" stroke-dasharray="3 5"/>').join("")+curvePaths()+'</svg></div><div class="legend"><span>Planejado</span><span>Executado (EV)</span></div>')+'</div>'+panel("ORÇAMENTO E APROPRIAÇÃO POR ATIVIDADE","EDITE OS VALORES PARA ATUALIZAR OS INDICADORES",'<div class="tablewrap"><table class="tbl"><thead><tr><th>CÓDIGO</th><th>ATIVIDADE</th><th>ORÇAMENTO (R$)</th><th>AVANÇO</th><th>CUSTO REAL (R$)</th><th>EV</th></tr></thead><tbody>'+rows+'</tbody></table></div>')+'<div class="note">EV, PV e AC seguem a lógica de valor agregado. PV desta versão é uma aproximação linear por duração; para medição contratual, cadastre a linha de base e distribua o orçamento no tempo.</div></div>';
  }
  function curvePaths() {
    const n = 12, points = [];
    for (let i=0;i<n;i++) {
      const day = max()*i/(n-1);
      const planned = state.activities.reduce((s,a)=>s+Number(a.cost||0)*Math.max(0,Math.min(1,(day-Number(a.start||0))/Math.max(1,a.duration))),0);
      const earned = state.activities.reduce((s,a)=>s+Number(a.cost||0)*Number(a.progress||0)/100*Math.max(0,Math.min(1,(day-Number(a.start||0))/Math.max(1,a.duration))),0);
      points.push({p:planned,e:earned});
    }
    const total = Math.max(1,...points.map(x=>x.p));
    const path = key => points.map((x,i)=>((i?"L":"M")+(35+i*49.5).toFixed(1)+" "+(160-x[key]/total*130).toFixed(1))).join(" ");
    return '<path d="'+path("p")+'" fill="none" stroke="var(--blue)" stroke-width="3"/><path d="'+path("e")+'" fill="none" stroke="var(--a)" stroke-width="3"/>';
  }
  function resources() {
    const resourceOptions = ext.resources.map(r=>'<option value="'+r.id+'">'+escHtml(r.name)+' ('+r.capacity+' un.)</option>').join("");
    const activityOptions = state.activities.map(a=>'<option value="'+a.id+'">'+escHtml(a.code+" — "+a.name)+'</option>').join("");
    const assignments = ext.assignments.map(x=>{
      const r=ext.resources.find(y=>y.id===x.resourceId), a=state.activities.find(y=>y.id===x.activityId);
      return r&&a?'<tr><td>'+escHtml(r.name)+'</td><td>'+escHtml(a.code+" — "+a.name)+'</td><td>'+x.units+'</td><td>'+formatDate(dateForDay(a.start).toISOString().slice(0,10))+' – '+dateForDay(a.start+a.duration).toLocaleDateString("pt-BR")+'</td><td><button class="btn" data-remove-assignment="'+x.id+'">Remover</button></td></tr>':"";
    }).join("");
    const conflicts = [];
    ext.resources.forEach(r=>state.activities.forEach(a=>{
      const total = ext.assignments.filter(x=>x.resourceId===r.id).filter(x=>{
        const other=state.activities.find(y=>y.id===x.activityId); return other&&a.start < other.start+other.duration && other.start < a.start+a.duration;
      }).reduce((s,x)=>s+Number(x.units||0),0);
      if(total>r.capacity) conflicts.push(r.name+" · "+a.code+" ("+total+"/"+r.capacity+")");
    }));
    return '<div class="stack"><div class="toolbar"><div><b>Cadastro e nivelamento de recursos</b><small>Equipes, equipamentos ou frentes de serviço</small></div><span class="pill">'+ext.resources.length+' RECURSOS</span></div><div class="g2">'+panel("NOVO RECURSO","CAPACIDADE E CUSTO",'<form id="resource-form" class="form"><label class="wide">Nome<input name="name" required placeholder="Equipe de montagem metálica"></label><label>Disciplina<select name="discipline"><option>GER</option><option>CIV</option><option>EST</option><option>MET</option><option>SAN</option><option>ELE</option><option>ARQ</option></select></label><label>Capacidade<input name="capacity" type="number" min="0.1" step="0.1" value="1"></label><label>Custo/dia (R$)<input name="cost" type="number" min="0" step="0.01" value="0"></label><button class="btn primary">Cadastrar</button></form>')+panel("ALOCAR RECURSO","VINCULE A UMA ATIVIDADE",'<form id="assignment-form" class="form"><label class="wide">Recurso<select name="resourceId" required>'+resourceOptions+'</select></label><label class="wide">Atividade<select name="activityId" required>'+activityOptions+'</select></label><label>Unidades<input name="units" type="number" min="0.1" step="0.1" value="1"></label><button class="btn primary" '+(!ext.resources.length?'disabled':'')+'>Alocar</button></form>')+'</div>'+panel("RECURSOS CADASTRADOS",ext.resources.length+" ITENS",ext.resources.length?'<div class="tablewrap"><table class="tbl"><thead><tr><th>RECURSO</th><th>DISC.</th><th>CAPACIDADE</th><th>CUSTO/DIA</th><th></th></tr></thead><tbody>'+ext.resources.map(r=>'<tr><td>'+escHtml(r.name)+'</td><td>'+r.discipline+'</td><td>'+r.capacity+'</td><td>'+moneyBR(r.costPerDay)+'</td><td><button class="btn" data-remove-resource="'+r.id+'">Excluir</button></td></tr>').join("")+'</tbody></table></div>':'<div class="note">Nenhum recurso cadastrado. Cadastre equipes, equipamentos ou materiais para começar.</div>')+panel("ALOCAÇÕES",ext.assignments.length+" VÍNCULOS",assignments?'<div class="tablewrap"><table class="tbl"><thead><tr><th>RECURSO</th><th>ATIVIDADE</th><th>UNIDADES</th><th>PERÍODO</th><th></th></tr></thead><tbody>'+assignments+'</tbody></table></div>':'Sem alocações cadastradas.')+(conflicts.length?'<div class="note"><b>Conflito de capacidade:</b> '+conflicts.map(escHtml).join(" · ")+'</div>':'<div class="note">Nenhuma sobrealocação identificada nas atividades e recursos cadastrados.</div>')+'</div>';
  }
  function triangular(min, mode, maxValue) {
    if (maxValue <= min) return min;
    const u=Math.random(), c=(mode-min)/(maxValue-min);
    return u<c ? min+Math.sqrt(u*(maxValue-min)*(mode-min)) : maxValue-Math.sqrt((1-u)*(maxValue-min)*(maxValue-mode));
  }
  function simulatePert(iterations) {
    const network=buildNetwork(state.activities), samples=[];
    for(let k=0;k<iterations;k++) {
      const durations={};
      state.activities.forEach(a=>{
        const o=Math.max(0,Number(a.optimistic ?? Number(a.duration||0)*0.85));
        const m=Math.max(o,Number(a.mostLikely ?? (a.duration||0)));
        const p=Math.max(m,Number(a.pessimistic ?? Number(a.duration||0)*1.25));
        durations[a.id]=triangular(o,m,p);
      });
      const starts={};
      network.order.forEach(a=>{
        let start=0;
        network.edges.filter(e=>e.to.id===a.id).forEach(e=>{
          const pred=state.activities.find(x=>x.id===e.from.id);
          const pseudoPred={...pred,duration:durations[pred.id]},pseudoSucc={...a,duration:durations[a.id]};
          start=Math.max(start,(starts[pred.id]||0)+edgeWeight(e,pseudoPred,pseudoSucc));
        });
        starts[a.id]=start;
      });
      samples.push(Math.max(0,...state.activities.map(a=>(starts[a.id]||0)+durations[a.id])));
    }
    samples.sort((a,b)=>a-b);
    const percentile=p=>samples[Math.min(samples.length-1,Math.floor((samples.length-1)*p))];
    return { samples, p50:percentile(.5), p80:percentile(.8), p90:percentile(.9), mean:samples.reduce((a,b)=>a+b,0)/samples.length };
  }
  function risks() {
    let result=lastPert;
    if(!result) { try { result=simulatePert(1500); lastPert=result; } catch(e) { return '<div class="note">'+escHtml(e.message)+'</div>'; } }
    const deadline=Number(ext.deadline || 0), probability=deadline>0?Math.round(result.samples.filter(x=>x<=deadline).length/result.samples.length*100):null;
    const rows=state.activities.map(a=>'<tr><td class="code">'+escHtml(a.code)+'</td><td>'+escHtml(a.name)+'</td><td><input type="number" min="0" step="0.5" data-pert="'+a.id+'" data-kind="optimistic" value="'+Number(a.optimistic ?? a.duration*.85).toFixed(1)+'"></td><td><input type="number" min="0" step="0.5" data-pert="'+a.id+'" data-kind="likely" value="'+Number(a.mostLikely ?? a.duration).toFixed(1)+'"></td><td><input type="number" min="0" step="0.5" data-pert="'+a.id+'" data-kind="pessimistic" value="'+Number(a.pessimistic ?? a.duration*1.25).toFixed(1)+'"></td></tr>').join("");
    return '<div class="stack"><div class="toolbar"><div><b>PERT e simulação Monte Carlo</b><small>Distribuição triangular por atividade e rede de precedências atual</small></div><button class="btn primary" data-run-pert>Executar 1.500 simulações</button></div><div class="kpis">'+kpi("P50",result.p50.toFixed(1)+" dias","50% de confiança","◷")+kpi("P80",result.p80.toFixed(1)+" dias","80% de confiança","◉")+kpi("P90",result.p90.toFixed(1)+" dias","90% de confiança","⚠")+kpi("MÉDIA",result.mean.toFixed(1)+" dias","prazo médio simulado","▤")+'</div>'+panel("ESTIMATIVAS POR ATIVIDADE","DIAS ÚTEIS",'<div class="tablewrap"><table class="tbl"><thead><tr><th>CÓDIGO</th><th>ATIVIDADE</th><th>OTIMISTA</th><th>MAIS PROVÁVEL</th><th>PESSIMISTA</th></tr></thead><tbody>'+rows+'</tbody></table></div>')+panel("PROBABILIDADE DE CUMPRIR O PRAZO","DEFINA O PRAZO EM DIAS ÚTEIS",'<form id="deadline-form" class="form"><label>Prazo-alvo (dias)<input name="deadline" type="number" min="1" step="1" value="'+(deadline||Math.ceil(result.p80))+'"></label><button class="btn primary">Calcular probabilidade</button><strong>'+(probability===null?"":probability+"% de probabilidade")+'</strong></form>')+'<div class="note">Monte Carlo usa distribuição triangular independente por atividade. Não inclui correlação de riscos, calendários específicos por equipe, clima ou incerteza de produtividade. Resultado é estimativa, não garantia de prazo.</div></div>';
  }
  function audit() {
    return '<div class="stack"><div class="toolbar"><div><b>Histórico e versionamento local</b><small>Snapshots manuais do cronograma, parâmetros e vínculos</small></div><div><button class="btn" data-snapshot>Salvar versão</button><button class="btn" data-export-excel>Exportar Excel</button><button class="btn" data-print-pdf>Imprimir / PDF</button></div></div>'+panel("VERSÕES SALVAS",ext.snapshots.length+" SNAPSHOTS",ext.snapshots.length?ext.snapshots.map((s,i)=>'<div class="row"><span><b>'+escHtml(s.name)+'</b><br>'+escHtml(s.createdAt)+' · '+s.activities.length+' atividades</span><button class="btn" data-restore-snapshot="'+i+'">Restaurar</button></div>').join(""):'Nenhuma versão salva manualmente.')+panel("REGISTRO DE EVENTOS",state.audit.length+" REGISTROS",state.audit.map(a=>'<div class="row">◉　<span><b>'+escHtml(a.action)+'</b><br>'+escHtml(a.detail)+'</span><b>'+escHtml(a.time)+'</b></div>').join(""))+'<div class="note">O histórico e snapshots ficam no navegador atual. Para auditoria corporativa imutável, autenticação e compartilhamento entre usuários, é necessário backend com banco central e controle de acesso.</div></div>';
  }
  function weather() {
    const w=ext.weather;
    const rows=w.result?.daily?.time?.map((d,i)=>'<tr><td>'+formatDate(d)+'</td><td>'+Number(w.result.daily.precipitation_sum?.[i]||0).toFixed(1)+' mm</td><td>'+Number(w.result.daily.precipitation_probability_max?.[i]||0)+'%</td><td>'+Number(w.result.daily.weather_code?.[i]||0)+'</td></tr>').join("")||"";
    return '<div class="stack"><div class="toolbar"><div><b>Clima e impacto no planejamento</b><small>Consulta gratuita ao Open-Meteo, sem chave de API</small></div><span class="pill">PREVISÃO ATÉ 16 DIAS</span></div>'+panel("LOCAL DA OBRA","INFORME AS COORDENADAS DO CANTEIRO",'<form id="weather-form" class="form"><label>Latitude<input name="latitude" type="number" step="0.0001" required value="'+escHtml(w.latitude)+'" placeholder="-8.76"></label><label>Longitude<input name="longitude" type="number" step="0.0001" required value="'+escHtml(w.longitude)+'" placeholder="-63.90"></label><label>Limite de chuva (mm/dia)<input name="rainLimit" type="number" min="0" step="0.5" value="'+w.rainLimit+'"></label><button class="btn primary" '+(weatherBusy?'disabled':'')+'>Consultar previsão</button></form>')+panel("PREVISÃO DIÁRIA","DADOS METEOROLÓGICOS",weatherBusy?"Consultando…":rows?'<div class="tablewrap"><table class="tbl"><thead><tr><th>DATA</th><th>PRECIPITAÇÃO</th><th>PROB. CHUVA</th><th>CÓDIGO</th></tr></thead><tbody>'+rows+'</tbody></table></div>':"Informe as coordenadas e consulte a previsão.")+'<div class="note">A previsão meteorológica não determina automaticamente paralisação. Avalie tipo de serviço, proteção, segurança, condições reais do canteiro e critérios contratuais. A API gratuita tem horizonte limitado e depende de internet.</div></div>';
  }
  function exchange() {
    const payload={format:"bim-schedule-ai-context",version:1,project:projectPayload(),instructions:"Proponha alterações sem inventar dados. Retorne JSON com activities_updates [{id, optimistic, most_likely, pessimistic, risk_note}], risks [{title, probability, impact, mitigation}], assumptions []. Não altere GlobalIds."};
    return '<div class="stack"><div class="toolbar"><div><b>Central de intercâmbio com IA</b><small>Exportar contexto, importar sugestões e aprovar manualmente</small></div><span class="pill">SEM CHAVE / SEM CUSTO DE API</span></div>'+panel("EXPORTAR CONTEXTO","JSON ESTRUTURADO",'<p>Gere um pacote com EAP, atividades, precedências, custos e vínculos IFC. Envie o JSON a uma IA externa e solicite uma análise. O SCHEDULE não envia dados automaticamente.</p><button class="btn primary" data-export-ai>Exportar contexto para IA</button>')+panel("IMPORTAR SUGESTÕES","REVISÃO ANTES DA APLICAÇÃO",'<p>Importe um JSON no formato indicado no contexto exportado. As sugestões serão validadas e exibidas para aprovação manual; nenhum dado será alterado automaticamente.</p><input type="file" id="ai-file" accept=".json,application/json"><button class="btn" data-import-ai>Validar arquivo</button><div id="ai-preview"></div>')+'<div class="note">A integração direta com Gemini/Claude/OpenAI exige credenciais, política de privacidade e controle de custos. Esta implementação oferece intercâmbio estruturado sem armazenar chaves de API.</div></div>';
  }
  function addRelationUI() {
    const options=state.activities.map(a=>'<option value="'+a.id+'">'+escHtml(a.code+" — "+a.name)+'</option>').join("");
    return panel("EDITAR PRECEDÊNCIAS","FS · SS · FF · SF + LAG",'<form id="relation-form" class="form"><label>Predecessora<select name="pred" required>'+options+'</select></label><label>Sucessora<select name="succ" required>'+options+'</select></label><label>Relação<select name="type"><option>FS</option><option>SS</option><option>FF</option><option>SF</option></select></label><label>Lag (dias úteis)<input name="lag" type="number" step="0.5" value="0"></label><button class="btn primary">Adicionar relação</button></form><div class="line"></div>'+state.activities.map(a=>relationsFor(a).map(r=>'<div class="row">'+escHtml(a.code)+' ← '+escHtml(state.activities.find(x=>x.id===Number(r.predecessorId))?.code||r.predecessorId)+' <b>'+escHtml(r.type||"FS")+' '+Number(r.lag||0)+'</b><button class="btn" data-remove-relation="'+a.id+'" data-pred="'+Number(r.predecessorId)+'">Remover</button></div>').join("")).join(""));
  }
  function gantt() {
    let result;
    try { result=calculateCpm(state.activities); } catch(e) { result=null; }
    const scale=Math.max(1,result?.duration||max());
    const rows=state.activities.map(a=>{
      const start=Number(a.start||0), duration=Number(a.duration||0), left=Math.max(0,start/scale*100), width=Math.max(.8,duration/scale*100);
      const color=a.critical?"var(--red)":"var(--blue)";
      return '<div class="gr"><span class="gl"><b>'+escHtml(a.code)+'</b><span>'+escHtml(a.name)+'</span></span><span class="gt"><i class="bar '+(a.critical?"crit":"")+'" style="left:'+left+'%;width:'+Math.min(width,100-left)+'%;background:'+color+'"></i></span></div>';
    }).join("");
    return '<div class="stack"><div class="toolbar"><div><b>Cronograma CPM / Gantt</b><small>Início: '+formatDate(ext.calendar.startDate)+' · calendário de dias úteis</small></div><div><button class="btn" data-calendar>Calendário</button><button class="btn" data-recalc>Recalcular CPM</button><button class="btn primary" data-new>＋ Nova atividade</button></div></div>'+ (showForm?form():"")+panel("GRÁFICO DE GANTT",result?result.duration+" DIAS ÚTEIS":"REDE NÃO CALCULADA",'<div class="legend"><span>■ Caminho crítico</span><span>■ Não crítica</span></div><div class="tablewrap"><div class="gantt">'+rows+'</div></div>')+addRelationUI()+panel("CALENDÁRIO DE TRABALHO","DIAS ÚTEIS, FERIADOS E DATA DE INÍCIO",'<form id="calendar-form" class="form"><label>Início do projeto<input type="date" name="startDate" value="'+ext.calendar.startDate+'"></label><label>Dias úteis (0=dom, 6=sáb)<input name="weekdays" value="'+ext.calendar.weekdays.join(",")+'" placeholder="1,2,3,4,5"></label><label class="wide">Feriados (AAAA-MM-DD, separados por vírgula)<input name="holidays" value="'+ext.calendar.holidays.join(",")+'"></label><button class="btn primary">Salvar calendário</button></form>')+'</div>';
  }
  function ifcPage() {
    const count=ifcElements.length, mapped=ifcModel?.mappings?Object.values(ifcModel.mappings).reduce((s,a)=>s+a.length,0):0;
    const versions=ext.versions;
    return '<div class="stack"><div class="toolbar"><div><b>Modelo IFC e rastreabilidade</b><small>Metadados, GlobalIds, versões e visualização geométrica</small></div><span class="pill">'+(ifcModel?"IFC CARREGADO":"AGUARDANDO IFC")+'</span></div>'+panel("IMPORTAR IFC","IFC2X3 · IFC4 · IFC4X3",'<div class="ifc-drop"><strong>'+(ifcModel?escHtml(ifcModel.name):"Selecione o modelo IFC")+'</strong><small>O arquivo é processado localmente no navegador.</small><div><input id="ifcFile" type="file" accept=".ifc,application/octet-stream"><button class="btn primary" id="ifcLoad" type="button">Processar IFC</button></div><div class="ifc-progress"><i id="ifcProgressBar" style="width:'+ifcPct+'%"></i></div><small id="ifcProgressLabel">'+escHtml(ifcStage)+' · '+ifcPct+'%</small></div>')+(ifcModel?'<div class="kpis">'+kpi("ELEMENTOS",count.toLocaleString("pt-BR"),ifcModel.schema||"Schema não identificado","▧")+kpi("VÍNCULOS",mapped,"GlobalIds associados","↔")+kpi("VERSÕES",versions.length+1,"modelos importados neste navegador","◷")+kpi("DISCIPLINAS",new Set(ifcElements.map(e=>e.discipline)).size,"classificação heurística","◎")+'</div>'+panel("VISUALIZADOR IFC 3D","ORBITAR · ZOOM · SELECIONAR",'<div id="ifc3d" class="ifc-canvas"><div class="note">Carregando visualizador…</div></div>')+panel("INVENTÁRIO E VÍNCULOS","BUSCA POR GLOBALID / TIPO / DISCIPLINA",'<input id="ifcSearch" class="ifc-search" placeholder="Pesquisar elementos IFC"><div class="ifc-actions"><button class="btn" id="ifcSelectVisible">Selecionar visíveis</button><button class="btn" id="ifcClearSelection">Limpar</button><select id="ifcActivity">'+state.activities.map(a=>'<option value="'+a.id+'">'+escHtml(a.code+" — "+a.name)+'</option>').join("")+'</select><button class="btn primary" id="ifcLink">Vincular seleção</button><button class="btn" id="ifcExport">Exportar inventário</button></div><div class="ifc-list">'+ifcElements.filter(e=>!ifcSearch||(e.name+" "+e.guid+" "+e.type+" "+e.discipline).toLowerCase().includes(ifcSearch.toLowerCase())).slice(0,300).map(e=>'<label class="ifc-item"><input type="checkbox" data-ifc-guid="'+escHtml(e.guid)+'" '+(ifcSelected.has(e.guid)?"checked":"")+'><span><b>'+escHtml(e.name)+'</b><small>'+escHtml(e.type)+' · '+escHtml(e.guid)+'</small></span><span class="disc">'+escHtml(e.discipline)+'</span></label>').join("")+'</div>')+panel("COMPARAR VERSÕES IFC","GLOBALIDS ADICIONADOS / REMOVIDOS",'<button class="btn" data-compare-ifc>Comparar com versão anterior</button><div id="ifc-diff"></div>'):'<div class="note">Importe um IFC para indexar GlobalIds e ativar o visualizador geométrico. O arquivo original permanece no armazenamento local do navegador.</div>')+'</div>';
  }
  function bim() {
    return '<div class="stack"><div class="toolbar"><div><b>Simulação BIM 4D</b><small>Elementos reais do IFC vinculados ao cronograma CPM</small></div><span class="pill">'+(ifcModel?"MODELO IFC":"SEM MODELO IFC")+'</span></div>'+(ifcModel?panel("MODELO 3D · ESTADO TEMPORAL","VERDE = CONCLUÍDO · COBRE = EM EXECUÇÃO · CINZA = FUTURO",'<div id="ifc4d" class="ifc-canvas"><div class="note">Carregando geometria IFC…</div></div>'):'<div class="note">Importe um IFC na seção Modelo IFC antes de iniciar a simulação 4D.')+panel("CONTROLE DA SIMULAÇÃO","DIA "+day+" / "+max(),'<div class="sim"><button class="btn" data-4d-restart>↺</button><button class="btn primary" data-4d-play>▶ Reproduzir</button><button class="btn" data-4d-step>›</button><input type="range" min="0" max="'+max()+'" value="'+day+'" id="4d-day"><strong>'+date(day)+'</strong></div><div class="line"></div>'+state.activities.map(a=>'<div class="row">'+escHtml(a.code+" · "+a.name)+'<b>'+a.start+'–'+(a.start+a.duration)+' d</b></div>').join(""))+'<div class="note">A simulação usa GlobalIds associados às atividades. Elementos sem vínculo não recebem estado temporal. O avanço físico continua sendo informado manualmente.</div></div>';
  }

  function render() {
    baseRender();
    toolbar();
    if (page === "ifc" && ifcModel) setTimeout(() => mountIfcViewer("ifc3d", false), 0);
    else if (page === "bim4d" && ifcModel) setTimeout(() => mountIfcViewer("ifc4d", true), 0);
    else disposeViewer();
  }
  window.addEventListener("resize", () => { if (viewer?.renderer && viewer?.container) resizeViewer(); });

  async function loadViewerEngine() {
    if (viewerPromise) return viewerPromise;
    viewerPromise = (async () => {
      const THREE = await import("https://esm.sh/three@0.160.0");
      const mod = await import("https://esm.sh/web-ifc-three@0.0.126/IFCLoader?external=three");
      return { THREE, IFCLoader: mod.IFCLoader };
    })();
    return viewerPromise;
  }
  function disposeViewer() {
    if (!viewer) return;
    try { viewer.controls.dispose(); viewer.renderer.dispose(); viewer.url && URL.revokeObjectURL(viewer.url); }
    catch (_) {}
    viewer.container?.replaceChildren(); viewer = null;
  }
  function resizeViewer() {
    if (!viewer) return;
    const w=Math.max(1,viewer.container.clientWidth), h=Math.max(1,viewer.container.clientHeight);
    viewer.camera.aspect=w/h; viewer.camera.updateProjectionMatrix(); viewer.renderer.setSize(w,h);
  }
  async function mountIfcViewer(containerId, fourD) {
    const container=document.getElementById(containerId); if (!container || !ifcModel?.file) {
      if(container) container.innerHTML='<div class="note">O arquivo IFC original não está disponível nesta sessão. Reimporte o arquivo para visualizar a geometria.</div>';
      return;
    }
    if (viewer?.container===container && viewer.fourD===fourD) { if(fourD) update4D(day); return; }
    disposeViewer();
    container.innerHTML='<div class="viewer-status">Carregando motor geométrico IFC…</div>';
    try {
      const {THREE,IFCLoader}=await loadViewerEngine();
      if (!document.getElementById(containerId)) return;
      const scene=new THREE.Scene(); scene.background=new THREE.Color(0x171a1f);
      const camera=new THREE.PerspectiveCamera(55,container.clientWidth/Math.max(1,container.clientHeight),0.1,100000);
      camera.position.set(15,15,15);
      const renderer=new THREE.WebGLRenderer({antialias:true,alpha:false});
      renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2)); renderer.setSize(container.clientWidth,container.clientHeight);
      container.replaceChildren(renderer.domElement);
      const controlsMod=await import("https://esm.sh/three@0.160.0/examples/jsm/controls/OrbitControls.js");
      const controls=new controlsMod.OrbitControls(camera,renderer.domElement);
      const loader=new IFCLoader();
      loader.ifcManager.setWasmPath("https://cdn.jsdelivr.net/npm/web-ifc@0.0.50/");
      const url=URL.createObjectURL(ifcModel.file);
      const model=await loader.loadAsync(url);
      scene.add(new THREE.AmbientLight(0xffffff,0.75));
      const light=new THREE.DirectionalLight(0xffffff,1.1); light.position.set(10,20,10); scene.add(light);
      scene.add(model);
      const bounds=new THREE.Box3().setFromObject(model), center=bounds.getCenter(new THREE.Vector3()), size=bounds.getSize(new THREE.Vector3()), maxDim=Math.max(size.x,size.y,size.z,1);
      controls?.target.copy(center); camera.position.set(center.x+maxDim*1.4,center.y+maxDim*1.1,center.z+maxDim*1.4); camera.near=Math.max(maxDim/10000,.01); camera.far=maxDim*100; camera.updateProjectionMatrix();
      viewer={THREE,container,scene,camera,renderer,controls,loader,model,url,fourD,frame:0,material:new THREE.MeshStandardMaterial({color:0xde7d43,transparent:true,opacity:.88})};
      const animate=()=>{ if(!viewer || viewer.container!==container) return; viewer.frame=requestAnimationFrame(animate); controls?.update(); renderer.render(scene,camera); };
      animate();
      if(fourD) update4D(day);
      const status=container.querySelector(".viewer-status"); if(status) status.remove();
    } catch(error) {
      container.innerHTML='<div class="note">Não foi possível iniciar o visualizador IFC: '+escHtml(error.message||error)+'. Confira a conexão com a internet e o suporte WebGL do navegador.</div>';
    }
  }
  function update4D(currentDay) {
    if(!viewer || !viewer.fourD) return;
    const manager=viewer.loader.ifcManager, modelID=viewer.model.modelID, THREE=viewer.THREE;
    const groups={done:[],active:[],future:[]};
    const guidToId=new Map(ifcElements.map(e=>[e.guid,e.eid]));
    const mapped=ifcModel?.mappings||{};
    Object.entries(mapped).forEach(([activityId,guids])=>{
      const a=state.activities.find(x=>x.id===Number(activityId)); if(!a) return;
      const bucket=currentDay >= a.start+a.duration ? "done" : currentDay >= a.start ? "active" : "future";
      guids.forEach(g=>{const id=guidToId.get(g);if(id)groups[bucket].push(id)});
    });
    try {
      ["schedule-done","schedule-active","schedule-future"].forEach(id=>manager.removeSubset(modelID,viewer.scene,id));
      const styles=[["done",0x4caf78,"schedule-done"],["active",0xde7d43,"schedule-active"],["future",0x87909b,"schedule-future"]];
      styles.forEach(([key,color,id])=>{
        const ids=Array.from(new Set(groups[key]));
        if(ids.length) manager.createSubset({modelID,ids,scene:viewer.scene,removePrevious:true,customID:id,material:new THREE.MeshStandardMaterial({color,transparent:true,opacity:.92})});
      });
    } catch(error) { console.warn("Falha ao atualizar estado 4D",error); }
  }

  const originalParse = baseParseIfc;
  parseIfc = async function(file) {
    const previousModel = ifcModel;
    const previous = ifcModel && ifcElements.length ? { name:ifcModel.name, schema:ifcModel.schema, guids:ifcElements.map(e=>e.guid), uploadedAt:ifcModel.uploadedAt } : null;
    await originalParse(file);
    if (ifcModel && ifcModel !== previousModel && ifcModel.name === file.name) {
      if(previous) {
        const versionId="version-"+(previous.uploadedAt || Date.now());
        try { await ifcDBPut({id:versionId,name:previous.name,schema:previous.schema,uploadedAt:previous.uploadedAt,guids:previous.guids}); } catch(e) { console.warn("Não foi possível arquivar a versão IFC anterior",e); }
        ext.versions.push({id:versionId,name:previous.name,schema:previous.schema,uploadedAt:previous.uploadedAt,count:previous.guids.length});
      }
      ext.versions=ext.versions.slice(-5);
      persistExt();
    }
  };

  document.addEventListener("submit", async e => {
    const form=e.target;
    if(form.id==="resource-form") {
      e.preventDefault(); const f=new FormData(form);
      ext.resources.push({id:Date.now(),name:String(f.get("name")).trim(),discipline:String(f.get("discipline")),capacity:Number(f.get("capacity")),costPerDay:Number(f.get("cost"))});
      save(); render(); notifyUser("Recurso cadastrado.");
    }
    if(form.id==="assignment-form") {
      e.preventDefault(); const f=new FormData(form);
      ext.assignments.push({id:Date.now(),resourceId:Number(f.get("resourceId")),activityId:Number(f.get("activityId")),units:Number(f.get("units"))});
      save(); render(); notifyUser("Alocação registrada.");
    }
    if(form.id==="calendar-form") {
      e.preventDefault(); const f=new FormData(form);
      const weekdays=String(f.get("weekdays")).split(",").map(Number).filter(n=>Number.isInteger(n)&&n>=0&&n<=6);
      if(!weekdays.length) return notifyUser("Informe ao menos um dia útil válido (0 a 6).");
      ext.calendar.startDate=String(f.get("startDate")); ext.calendar.weekdays=weekdays;
      ext.calendar.holidays=String(f.get("holidays")).split(",").map(x=>x.trim()).filter(x=>/^\d{4}-\d{2}-\d{2}$/.test(x));
      save(); render(); notifyUser("Calendário atualizado. Recalcule o CPM para atualizar as datas.");
    }
    if(form.id==="deadline-form") {
      e.preventDefault(); const f=new FormData(form); ext.deadline=Number(f.get("deadline")); lastPert=simulatePert(1500); save(); render();
    }
    if(form.id==="relation-form") {
      e.preventDefault(); const f=new FormData(form), pred=Number(f.get("pred")), succ=Number(f.get("succ"));
      if(pred===succ) return notifyUser("Uma atividade não pode preceder a si mesma.");
      const a=state.activities.find(x=>x.id===succ); if(!a) return;
      a.relations=relationsFor(a); a.relations.push({predecessorId:pred,type:String(f.get("type")),lag:Number(f.get("lag")||0)});
      a.preds=Array.from(new Set(a.relations.map(x=>x.predecessorId)));
      try { buildNetwork(state.activities); save(); render(); notifyUser("Precedência cadastrada."); }
      catch(error) { a.relations.pop(); a.preds=Array.from(new Set(a.relations.map(x=>x.predecessorId))); notifyUser(error.message); }
    }
    if(form.id==="weather-form") {
      e.preventDefault(); const f=new FormData(form); ext.weather.latitude=String(f.get("latitude")); ext.weather.longitude=String(f.get("longitude")); ext.weather.rainLimit=Number(f.get("rainLimit")); save();
      if(weatherBusy)return; weatherBusy=true; render();
      try {
        const u=new URL("https://api.open-meteo.com/v1/forecast");
        u.search=new URLSearchParams({latitude:ext.weather.latitude,longitude:ext.weather.longitude,daily:"precipitation_sum,precipitation_probability_max,weather_code",forecast_days:"16",timezone:"auto"}).toString();
        const response=await fetch(u); if(!response.ok)throw new Error("Serviço meteorológico retornou "+response.status);
        ext.weather.result=await response.json(); logEvent("Previsão meteorológica consultada","Coordenadas "+ext.weather.latitude+", "+ext.weather.longitude); save();
      } catch(error) { notifyUser("Falha ao consultar clima: "+error.message); }
      finally { weatherBusy=false; render(); }
    }
  });
  document.addEventListener("change", e => {
    const t=e.target;
    if(t.dataset.baseCost) { const a=state.activities.find(x=>x.id===Number(t.dataset.baseCost)); if(a){a.cost=Math.max(0,Number(t.value)||0);save();render();} }
    if(t.dataset.actualCost) { ext.actualCosts[t.dataset.actualCost]=Math.max(0,Number(t.value)||0);save();render(); }
    if(t.dataset.pert) { const a=state.activities.find(x=>x.id===Number(t.dataset.pert)); if(a){a[t.dataset.kind==="optimistic"?"optimistic":t.dataset.kind==="likely"?"mostLikely":"pessimistic"]=Math.max(0,Number(t.value)||0);lastPert=null;save();} }
    if(t.dataset.ifcGuid) { if(t.checked)ifcSelected.add(t.dataset.ifcGuid);else ifcSelected.delete(t.dataset.ifcGuid); }
  });
  document.addEventListener("click", e => {
    const b=e.target.closest("button"); if(!b)return;
    if(b.hasAttribute("data-run-pert")) { try { lastPert=simulatePert(1500); render(); } catch(error){notifyUser(error.message);} }
    if(b.hasAttribute("data-remove-assignment")) { ext.assignments=ext.assignments.filter(x=>x.id!==Number(b.dataset.removeAssignment));save();render(); }
    if(b.hasAttribute("data-remove-resource")) { const id=Number(b.dataset.removeResource);ext.resources=ext.resources.filter(x=>x.id!==id);ext.assignments=ext.assignments.filter(x=>x.resourceId!==id);save();render(); }
    if(b.hasAttribute("data-remove-relation")) { const a=state.activities.find(x=>x.id===Number(b.dataset.removeRelation)); if(a){a.relations=relationsFor(a).filter(r=>Number(r.predecessorId)!==Number(b.dataset.pred));a.preds=a.relations.map(r=>r.predecessorId);save();render();} }
    if(b.hasAttribute("data-calendar")) { page="gantt";render();document.getElementById("calendar-form")?.scrollIntoView({behavior:"smooth"}); }
    if(b.hasAttribute("data-snapshot")) { ext.snapshots.unshift({name:"Versão "+(ext.snapshots.length+1),createdAt:new Date().toLocaleString("pt-BR"),activities:JSON.parse(JSON.stringify(state.activities)),calendar:JSON.parse(JSON.stringify(ext.calendar)),resources:JSON.parse(JSON.stringify(ext.resources)),assignments:JSON.parse(JSON.stringify(ext.assignments))});ext.snapshots=ext.snapshots.slice(0,30);save();render();notifyUser("Snapshot salvo."); }
    if(b.dataset.restoreSnapshot!==undefined) { const s=ext.snapshots[Number(b.dataset.restoreSnapshot)];if(s&&confirm("Restaurar esta versão? As atividades atuais serão substituídas.")){state.activities=JSON.parse(JSON.stringify(s.activities));ext.calendar=s.calendar;ext.resources=s.resources;ext.assignments=s.assignments;save();render();} }
    if(b.hasAttribute("data-export-excel")) exportExcel();
    if(b.hasAttribute("data-print-pdf")) window.print();
    if(b.hasAttribute("data-export-ai")) downloadText("BIM-SCHEDULE-contexto-IA.json",JSON.stringify({format:"bim-schedule-ai-context",version:1,project:projectPayload()},null,2),"application/json");
    if(b.hasAttribute("data-import-ai")) document.getElementById("ai-file")?.click();
    if(b.hasAttribute("data-compare-ifc")) compareIfcVersions();
    if(b.hasAttribute("data-4d-play")) {
      if(viewerTimer){clearInterval(viewerTimer);viewerTimer=null;b.textContent="▶ Reproduzir";}
      else {viewerTimer=setInterval(()=>{if(page!=="bim4d"){clearInterval(viewerTimer);viewerTimer=null;return;}day=day>=max()?0:day+1;const input=document.getElementById("4d-day");if(input)input.value=day;update4D(day);const label=document.querySelector("#view .sim strong");if(label)label.textContent=date(day);},700);b.textContent="Ⅱ Pausar";}
    }
    if(b.hasAttribute("data-4d-restart")) {if(viewerTimer){clearInterval(viewerTimer);viewerTimer=null;}day=0;update4D(day);const input=document.getElementById("4d-day");if(input)input.value=0;const play=document.querySelector("[data-4d-play]");if(play)play.textContent="▶ Reproduzir";}
    if(b.hasAttribute("data-4d-step")) {day=Math.min(max(),day+1);update4D(day);const input=document.getElementById("4d-day");if(input)input.value=day;}
  });
  document.addEventListener("input", e => {
    if(e.target.id==="4d-day"){day=Number(e.target.value);update4D(day);const label=document.querySelector("#view .sim strong");if(label)label.textContent=date(day);}
    if(e.target.id==="ifcSearch"){ifcSearch=e.target.value;}
  });
  document.addEventListener("change", e => {
    if(e.target.id==="ai-file" && e.target.files?.[0]) {
      e.target.files[0].text().then(text=>{
        const data=JSON.parse(text), preview=document.getElementById("ai-preview");
        if(data.format!=="bim-schedule-ai-context" && !Array.isArray(data.activities_updates))throw new Error("Formato de sugestões não reconhecido.");
        const updates=data.activities_updates||[];
        const valid=updates.filter(x=>state.activities.some(a=>a.id===Number(x.id))&&["optimistic","most_likely","pessimistic"].some(k=>x[k]!==undefined));
        window.__bimScheduleAiPending=valid;
        if(preview)preview.innerHTML='<div class="note">'+valid.length+' sugestão(ões) válidas encontradas. <button class="btn primary" data-approve-ai>Aprovar e aplicar</button></div>';
      }).catch(error=>notifyUser("JSON inválido: "+error.message));
    }
  });
  document.addEventListener("click", e=>{
    const b=e.target.closest("[data-approve-ai]"); if(!b)return;
    const updates=window.__bimScheduleAiPending||[];
    updates.forEach(u=>{const a=state.activities.find(x=>x.id===Number(u.id));if(!a)return;if(u.optimistic!==undefined)a.optimistic=Number(u.optimistic);if(u.most_likely!==undefined)a.mostLikely=Number(u.most_likely);if(u.pessimistic!==undefined)a.pessimistic=Number(u.pessimistic);});
    window.__bimScheduleAiPending=[];lastPert=null;logEvent("Sugestões de IA aprovadas",updates.length+" atividade(s) atualizadas após revisão manual.");save();render();
  });
  async function compareIfcVersions() {
    const previous=ext.versions[ext.versions.length-1]; const target=document.getElementById("ifc-diff");
    if(!previous||!ifcModel){if(target)target.textContent="Não há versão anterior para comparar.";return;}
    try {
      const db=await ifcDB();
      const old=await new Promise((resolve,reject)=>{const q=db.transaction("models","readonly").objectStore("models").get(previous.id);q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error);});
      if(!old)throw new Error("Versão anterior não encontrada no IndexedDB.");
      const oldSet=new Set(old.guids||[]), newSet=new Set(ifcElements.map(x=>x.guid));
      const added=[...newSet].filter(x=>!oldSet.has(x)), removed=[...oldSet].filter(x=>!newSet.has(x));
      if(target)target.innerHTML='<div class="row">Elementos adicionados<b>'+added.length+'</b></div><div class="row">Elementos removidos<b>'+removed.length+'</b></div><div class="note">Versão anterior: '+escHtml(previous.name)+' · '+escHtml(previous.schema||"")+'<br>Comparação baseada em GlobalId; não detecta alterações geométricas ou de propriedades quando o GlobalId permanece igual.</div>';
    } catch(error) { if(target)target.textContent="Falha ao comparar versões: "+error.message; }
  }
  function exportExcel() {
    const rows=[["Código","Atividade","Disciplina","Duração (dias úteis)","Início","Término","Avanço (%)","Orçamento (R$)","Custo real (R$)"],...state.activities.map(a=>[a.code,a.name,a.disc,a.duration,a.start,a.start+a.duration,a.progress,a.cost,ext.actualCosts[a.id]||0])];
    const xml='<?xml version="1.0"?><Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"><Worksheet ss:Name="Atividades"><Table>'+rows.map(row=>'<Row>'+row.map(v=>'<Cell><Data ss:Type="'+(typeof v==="number"?"Number":"String")+'">'+escHtml(v)+'</Data></Cell>').join("")+'</Row>').join("")+'</Table></Worksheet></Workbook>';
    downloadText("BIM-SCHEDULE-atividades.xls",xml,"application/vnd.ms-excel");
  }

  // Publica os módulos substitutos para a interface principal (script clássico).
  window.financial=financial; window.resources=resources; window.risks=risks; window.audit=audit;
  window.gantt=gantt; window.ifcPage=ifcPage; window.bim=bim; window.render=render;
  window.recalc=recalc; window.date=date; window.save=save; window.parseIfc=parseIfc;

  // Intercepta os módulos do projeto demonstrativo com cálculos efetivos.
  window.addEventListener("load", () => {
    if (!projectStore.some(p=>p.id===ext.projectId)) persistProject();
    toolbar(); refreshProjectSelect(); render();
  });
  // O script é carregado depois do app original; reapresenta a página com as funções substituídas.
  baseRender();
  toolbar();
})();
