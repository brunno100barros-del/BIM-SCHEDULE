# Relatório técnico — Etapa 2: reestruturação da arquitetura

| Item | Valor |
|---|---|
| Data | 2026-11-17 |
| Versão | 0.6.0-dev |
| Commit de referência (antes) | `2fb923b02568195f2072d54f52518078655530e4` (`main`) |
| Backup | branch `backup/etapa-02-pre-reestruturacao-2026-11-17` → `2fb923b` (publicada e conferida com `git ls-remote`) |
| Tag de backup | Não criada: o envio de tags é recusado pelo ambiente (HTTP 403). O requisito foi removido por decisão do responsável. |
| Branch de desenvolvimento | `etapa-02/reestruturacao-arquitetura` |

## A. Relatório de alterações

### A.1 Arquivos movidos (sem perda de funcionalidade)

| Antes | Depois | Observação |
|---|---|---|
| `backend/app/api/v1/endpoints/projects.py` | `backend/app/modules/projects/router.py` + `service.py` | Regras (datas, duplicação) extraídas para o serviço |
| `backend/app/schemas/project.py` | `backend/app/modules/projects/schemas.py` | Sem alteração |
| `backend/app/api/v1/endpoints/activities.py` | `backend/app/modules/planning/router.py` + `schemas.py` + `service.py` | Esquemas e orquestração do CPM separados; rotas `/activities` mantidas |
| `backend/app/api/v1/endpoints/ifc.py` | `backend/app/modules/ifc/router.py` + `service.py` + `jobs.py` | Upload agora agenda uma tarefa em processo separado |
| `backend/app/ifc/parser.py` | `backend/app/modules/ifc/parser.py` | Ganhou callbacks opcionais de progresso e cancelamento; a extração é a mesma |
| `frontend/src/LegacyApp.tsx` | `frontend/src/app/AppShell.tsx` | Mesmo layout; recebe status do serviço e o aviso de conexão |
| `frontend/src/App.tsx` | `frontend/src/app/App.tsx` | Sem iframe nem `?connected=1`; verifica o serviço |

### A.2 Arquivos removidos

Nenhum arquivo de funcionalidade foi removido. Os diretórios `backend/app/api/v1/endpoints/`, `backend/app/ifc/` e `backend/app/schemas/` ficaram vazios após as movimentações acima.

### A.3 Arquivos criados

**Backend: núcleo**
- `app/__main__.py`: `python -m app` (serve | prepare | storage-info), porta livre, linha `BIM_SCHEDULE_READY`, `freeze_support`.
- `app/core/storage.py`: pasta de dados e migração validada dos dados legados.
- `app/core/schema_migrations.py`: Alembic na inicialização, com backup do banco.
- `app/core/bootstrap.py` e `app/core/runtime.py`: inicialização e estado do serviço.
- `app/core/errors.py`: envelope de erros padronizado.
- `app/core/security.py`: request id, token local, CORS, TrustedHost.
- `app/core/logging.py`: log rotativo na pasta de dados.

**Backend: tarefas**
- `app/jobs/manager.py`, `worker.py`, `context.py`, `registry.py`, `router.py`, `diagnostic.py`.
- `app/models/job.py` e `migrations/versions/0002_jobs.py` (tabela `jobs` e `ifc_models.job_id`).

**Backend: módulos**
- `modules/system/router.py`: `/system/health` e `/system/status` (inclui capacidades reais).
- `modules/ai/`: `exchange.py`, `service.py`, `router.py`, `providers/{base,ollama,manual}.py`.
- `modules/budget`, `modules/simulation`, `modules/reports`: apenas `__init__.py` com a responsabilidade documentada, marcados **NÃO IMPLEMENTADO**.
- `__init__.py` em todos os pacotes (antes eram pacotes implícitos; necessário para empacotamento).

**Backend: testes**
- `test_jobs.py`, `test_ifc_processing.py`, `test_storage_migration.py`, `test_persistence_restart.py`, `test_errors_security.py`, `test_ai_exchange.py`, `ifc_factory.py`.

**Frontend**
- `src/config/runtime.ts` e `public/runtime-config.js`: configuração em tempo de execução.
- `src/services/apiClient.ts`, `projects.ts`, `planning.ts`, `ifc.ts`, `jobs.ts`, `system.ts`.
- `src/hooks/useBackendStatus.ts`, `useJobProgress.ts`.
- `src/components/feedback/StatusViews.tsx`, `BackendUnavailable.tsx`, `JobProgressCard.tsx`.
- `src/types/api.ts`, `src/vite-env.d.ts`.
- `scripts/build-pages.mjs`: site do GitHub Pages, com a demonstração na raiz.
- Testes: `vitest.config.ts`, `tests/unit/*.test.ts`, `playwright.config.ts`, `tests/e2e/app.spec.ts`, `tests/e2e/fixtures/edificio-teste.ifc` (IFC4 real gerado com IfcOpenShell).
- `package-lock.json`: instalação reproduzível (`npm ci`).

**CI e documentação**
- `.github/workflows/ci.yml`: backend em Ubuntu e Windows; frontend com unitários, build e e2e.
- `docs/architecture/ARCHITECTURE.md`, `WINDOWS_DESKTOP.md`, `AI_INTEGRATION.md`, `IFC_VIEWER_EVALUATION.md`.
- `docs/reports/LEVANTAMENTO-BRANCHES-FEATURE.md` e este relatório.

### A.4 Arquivos modificados

| Arquivo | Alteração |
|---|---|
| `backend/app/main.py` | `create_app()`; o lifespan executa o bootstrap; sai o `create_all` |
| `backend/app/core/config.py` | Prefixo `BIM_SCHEDULE_`; novas opções; `get_settings()` sob demanda; `DATABASE_URL` antigo aceito |
| `backend/app/core/database.py` | Engine criado na inicialização; SQLite em WAL + `busy_timeout`; engine próprio para processos de tarefa |
| `backend/app/api/v1/api.py` | Inclui `system`, `jobs` e `ai`; prefixos anteriores mantidos |
| `backend/app/models/ifc.py`, `models/__init__.py` | Coluna `job_id`; registro de `JobModel` |
| `backend/migrations/env.py` | Usa a mesma resolução da pasta de dados (evita criar banco vazio ao lado dos dados legados); `render_as_batch` |
| `backend/alembic.ini` | `path_separator = os` (remove aviso de depreciação) |
| `backend/tests/conftest.py` | Pasta de dados temporária e isolada por teste. Os testes antigos `test_api.py` e `test_cpm.py` **não foram alterados**. |
| `backend/tests/test_database.py` | Usa `get_engine()`; novo teste de WAL |
| `frontend/src/modules/*` | Chamadas `axios` diretas trocadas pelos serviços; mensagens de erro padronizadas. Bim3D: progresso do upload, acompanhamento e cancelamento da tarefa IFC. |
| `frontend/src/modules/projects/ProjectList.tsx`, `components/ProjectModal.tsx` | Estado de erro com "tentar novamente"; avisos de sucesso e erro; falhas de excluir e duplicar passam a ser exibidas (antes eram rejeições não tratadas) |
| `frontend/src/components/Sidebar.tsx` | Versão vinda do serviço; módulos de projeto desabilitados sem projeto aberto; link para a demonstração; "Central Gemini AI" → "Central de IA" |
| `frontend/src/modules/bim3d/IfcViewer.tsx` | Aceita cabeçalhos (token); WASM por caminho relativo (`BASE_URL`) |
| `frontend/index.html` | Carrega `runtime-config.js`; remove referência a `/vite.svg`, que não existia |
| `frontend/vite.config.ts` | `base: './'`; destino do proxy configurável; proxy também no `preview` |
| `frontend/package.json` | Versão 0.6.0-dev; scripts `test`, `test:unit`, `test:e2e`, `build:pages` |
| `.github/workflows/deploy-pages.yml` | Publica `pages-dist` (demonstração na raiz) em vez do build React |
| `install.bat`, `start.bat` | `python -m app prepare` e `python -m app --port 8000` |
| `.env.example`, `backend/.env.example` | Variáveis novas documentadas, todas comentadas |
| `.gitignore` | `pages-dist`, relatórios do Playwright |

### A.5 Dependências

| Dependência | Tipo | Justificativa |
|---|---|---|
| `vitest@2.1.9` | dev (frontend) | Autorizada. Testes unitários do cliente da API e da configuração; compatível com Vite 5. |
| `@playwright/test@1.63.0` | dev (frontend) | Autorizada. Testes de ponta a ponta reproduzíveis; o CI instala o Chromium (`npx playwright install --with-deps chromium`). |
| Backend | — | Nenhuma nova. `httpx` (já em `requirements.txt`) passou a ser usado também em tempo de execução, só para consultar o Ollama local. |
| Removidas | — | Nenhuma. |

## B. Arquitetura

Ver [`docs/architecture/ARCHITECTURE.md`](../architecture/ARCHITECTURE.md). Resumo:

- **Backend modular:** `core` (configuração, armazenamento, banco, erros, segurança, logs), `engine` (CPM/PERT puro, inalterado), `jobs` (processos separados) e `modules/*` por domínio.
- **Comunicação:** HTTP/JSON em `/api/v1`, com envelope de erro padronizado, `X-Request-ID`, `202 + job_id` para tarefas, consulta de progresso e cancelamento.
- **Tarefas:** um processo `spawn` por tarefa, com estado no SQLite, cancelamento cooperativo, encerramento forçado após o prazo, `abort_hook` de consistência e recuperação de tarefas interrompidas.
- **Dados:** `%LOCALAPPDATA%\BIM-SCHEDULE`, com migração por cópia validada e backup antes de cada migração de esquema.
- **Web:** o GitHub Pages publica só a demonstração. A Web local usa Vite + serviço local. A Web com backend remoto está preparada (endereço configurável), mas não implementada.
- **Windows:** recomendação de Electron + PyInstaller, com o serviço iniciado sem terminal (detalhes em [`WINDOWS_DESKTOP.md`](../architecture/WINDOWS_DESKTOP.md)).
- **IA:** formato de intercâmbio v1, provedores intercambiáveis e validação sem aplicação (detalhes em [`AI_INTEGRATION.md`](../architecture/AI_INTEGRATION.md)).

## C. Testes

Todos os testes abaixo foram **executados**. Os resultados são os observados.

### C.1 Testes obrigatórios da etapa

| # | Teste exigido | Como foi verificado | Resultado |
|---|---|---|---|
| 1 | Inicialização do frontend | Playwright sobe `vite` e abre a aplicação principal (sem iframe) | Aprovado |
| 2 | Inicialização do backend | `python -m app` como processo real (`test_persistence_restart.py`) e pelo Playwright | Aprovado |
| 3 | Comunicação frontend/backend | e2e: versão lida de `/system/status`, CRUD, CPM, upload IFC | Aprovado |
| 4 | Criação de projeto | e2e pela interface + pytest pela API | Aprovado |
| 5 | Persistência no banco | e2e consulta a API diretamente após criar pela interface | Aprovado |
| 6 | Recuperação após reiniciar o backend | pytest: inicia `python -m app`, cria projeto e atividade, encerra, reinicia e confere | Aprovado |
| 7 | Backend indisponível | e2e: `runtime-config` apontando para porta sem serviço (conexão recusada real) mostra a tela de orientação, sem dados simulados | Aprovado |
| 8 | Erros de requisição | pytest (404, 409, 422, 500, Host inválido, token) + Vitest (rede, 502 do proxy, timeout, cancelamento, envelope) + e2e (código duplicado; requisição sem conexão) | Aprovado |
| 9 | Testes existentes do CPM/PERT | `test_cpm.py` e `test_api.py` **sem alteração** | Aprovado |
| 10 | Build de produção do frontend | `tsc && vite build` | Aprovado |

### C.2 Resultados por conjunto

| Conjunto | Ambiente | Resultado |
|---|---|---|
| Backend (pytest) | Linux, Python 3.13 (local) | **65 aprovados** (após a revisão; eram 62) |
| Backend (pytest) | GitHub Actions `ubuntu-latest`, Python 3.12 | Aguardando a execução do CI desta revisão (antes: 62/62) |
| Backend (pytest) | GitHub Actions `windows-latest`, Python 3.12.10 | Aguardando a execução do CI desta revisão (antes: 62/62) |
| Frontend unitários (Vitest) | local e CI | **12 aprovados** |
| Motor da demonstração (node:test) | local e CI | **9 aprovados** |
| Ponta a ponta (Playwright, Chromium) | local e CI | **8 aprovados** |
| Type check + build de produção | local e CI | Aprovado |
| `npm ci` a partir do lockfile | local e CI | Aprovado |

Composição dos 65 testes do backend: 20 anteriores (CPM, API, banco) e 45 novos (42 da entrega inicial e 3 da revisão do PR #5).
- **Tarefas:** progresso; API responsiva durante a tarefa; cancelamento cooperativo; encerramento forçado de tarefa que não responde; falha; morte do processo; cancelamento na fila; desligamento do serviço; recuperação de tarefas interrompidas.
- **IFC real:** processamento completo, cancelamento sem dados parciais, arquivo corrompido, validações, limite de tamanho, confinamento do arquivo em `uploads/`.
- **Preservação de dados:** leitura no modo legado; migração validada com hashes intactos e reinício sem nova migração; falha de migração mantendo o local legado; cópia divergente rejeitada; URL explícita; atualização de esquema com backup.
- **Erros e segurança:** envelopes de erro, Host inválido, token, CORS, capacidades reais.
- **IA:** pacote de pedido, validação, formato antigo da demonstração, provedores sem rede externa.

### C.3 Problemas encontrados e corrigidos durante a etapa

- `index.html` referenciava `/vite.svg`, um arquivo inexistente: removido.
- `ProjectList` só registrava erros no console. Exclusão e duplicação geravam rejeições não tratadas. Corrigido.
- Os módulos de projeto na barra lateral abriam uma tela vazia sem projeto selecionado: agora ficam desabilitados.
- O visualizador IFC usava `setWasmPath('/')`, que falha em subpastas e sob outro protocolo: agora é relativo.

### C.4 Revisão do PR #5 — correções solicitadas

**1. Falha ao iniciar o processo da tarefa** (`backend/app/jobs/manager.py`)

- **Problema:** em `_run()`, se `process.start()` lançasse exceção, o fluxo saía antes de `_finalize()`, e a tarefa ficava indefinidamente com status `running`.
- **Correção:** a criação do `Process` e o `start()` ficam em um bloco protegido. Em caso de falha, o novo `_fail_to_start()`:
  - registra a tarefa como `failed`, com a mensagem "Falhou ao iniciar";
  - grava um erro compreensível com o tipo e o texto da exceção e uma orientação;
  - limpa o `pid`, grava `finished_at` e libera a referência ao processo;
  - executa o `abort_hook` do tipo de tarefa. No IFC, o modelo passa a `failed`, sem elementos parciais.
  - O supervisor retorna normalmente e continua atendendo a fila.
- **Testes novos** (`backend/tests/test_jobs.py`), simulando `OSError` em `Process.start()`:
  - `test_process_start_failure_marks_job_failed_and_supervisor_continues`: tarefa `failed` com mensagem e erro, `pid` nulo, nenhum processo ativo, e a tarefa seguinte é concluída.
  - `test_process_start_failure_runs_abort_hook_for_ifc`: envio de IFC real com falha de inicialização deixa o modelo `failed`, com o `job_id` na mensagem e sem elementos; um novo envio é processado normalmente.
  - Contraprova: os dois testes falham com o `manager.py` anterior (a tarefa permanecia `running`).
- **Ajuste após o CI da revisão:** a primeira versão da correção marcava a tarefa como `failed` *antes* de executar o `abort_hook`. O CI no Ubuntu (execução 44173320438) flagrou a janela em que a tarefa já aparecia encerrada e o modelo IFC ainda estava `queued`. Agora a ordem é: `abort_hook` → tarefa `failed` → liberação da referência ao processo. Quando um cliente vê a tarefa encerrada, os dados já estão consistentes. O teste do IFC passou a tornar a rotina de consistência propositalmente lenta (0,5 s), o que torna a verificação determinística: ele falha com a ordem anterior e passa com a nova.

**2. Electron e CORS** (`docs/architecture/WINDOWS_DESKTOP.md`, seção 3.1, e `ARCHITECTURE.md`)

- **Problema:** a proposta usava `BrowserWindow.loadFile()`. Uma página `file://` envia `Origin: null`, que o serviço não autoriza e não deve autorizar.
- **Solução documentada:** a interface é carregada pelo protocolo privilegiado `app://bim-schedule` (*standard* + *secure*), com `protocol.handle` servindo `dist/` com proteção contra caminhos fora da pasta e tipos MIME corretos (`application/wasm`). O handler gera `runtime-config.js` com o endereço e o token da sessão. O Electron inicia o serviço com `BIM_SCHEDULE_CORS_ORIGINS=["app://bim-schedule"]`, uma única origem exata. `webSecurity`, `contextIsolation` e `sandbox` permanecem ativos, e `null` e `*` nunca são liberados.
- **Alternativas avaliadas e registradas:** servidor HTTP local do Electron e o próprio FastAPI servindo a interface.
- **Teste novo** (`backend/tests/test_errors_security.py::test_cors_accepts_desktop_protocol_origin_only_when_configured`): com a configuração do app Windows, o *preflight* com `X-BIM-Schedule-Token` e o GET a partir de `app://bim-schedule` são aceitos. As origens `null`, `app://outro-app` e `http://127.0.0.1:3000` são recusadas. Na configuração padrão, nem `app://` nem `null` são aceitas.
- **Código do backend:** sem alteração, porque o CORS já compara origens exatas e aceita a lista por variável de ambiente. Só comentários do frontend que citavam `file://` ou preload foram atualizados: `vite.config.ts`, `IfcViewer.tsx`, `config/runtime.ts`, `public/runtime-config.js`.
- **Pendente** (etapa de distribuição): implementar e testar o handler do protocolo e a casca Electron com o app empacotado.

### C.5 Problemas encontrados e **não** corrigidos (fora do escopo; não introduzidos nesta etapa)

1. **Erros de JavaScript na demonstração estática** (`demo.html` / `schedule-enhancements.js`, idênticos aos da `main`): `weather is not defined` e `Maximum call stack size exceeded` ao carregar. Reproduzidos com os arquivos da `main` sem modificação. A demonstração continua sendo publicada como estava.
2. **Tema escuro:** o botão aplica a classe `dark` em `<html>`, mas `index.css` verifica `body:not(.dark)`. Na prática a aplicação sempre exibe o tema claro remapeado. O comportamento foi preservado para não alterar a identidade visual.
3. **Pacote JS principal com ~3,4 MB** (aviso do Vite), devido a Three.js e web-ifc. A divisão de código fica para a etapa do visualizador.

## D. Limitações conhecidas

- O processamento IFC foi validado com modelos IFC4 gerados pelo IfcOpenShell (até 3 000 paredes), **não** com modelos reais de projeto (IFC2x3/IFC4x3, grandes).
- O cancelamento cooperativo do IFC ocorre entre elementos. Durante `ifcopenshell.open()` de arquivos muito grandes, a tarefa só para pelo encerramento forçado (após `JOB_CANCEL_GRACE_SECONDS`), que remove os dados parciais pelo `abort_hook`.
- Concorrência padrão de **1** tarefa simultânea; as demais aguardam na fila.
- A migração de dados foi testada com dados criados no esquema anterior (revisão 0001) em ambiente de teste. **Não** foi executada sobre uma instalação real do usuário. Como os originais nunca são alterados, recomenda-se ainda assim manter uma cópia manual de `backend\bim_schedule.db` e `backend\uploads` antes de atualizar.
- O aplicativo Windows, o instalador e o funcionamento offline **não** foram implementados nem testados.
- IA: somente estrutura. Não há planejamento inteligente, aplicação de propostas ou tela de IA no frontend.
- Orçamento, simulação 4D no backend e relatórios: apenas reservados.
- O visualizador IFC continua com `web-ifc-three@0.0.126` (avaliação em `IFC_VIEWER_EVALUATION.md`).
- Os módulos da demonstração (custos, recursos, PERT/Monte Carlo, clima, 4D) continuam **apenas** na demonstração estática, com dados locais do navegador. Eles não fazem parte da aplicação principal.

## E. Próxima etapa

**Ficou preparado**
- Estrutura modular para desenvolver orçamento, simulação 4D, relatórios e IA sem mexer no motor.
- Tarefas em segundo plano reutilizáveis: basta registrar um novo tipo em `app/jobs/registry.py`.
- Contrato de IA v1, com validação e JSON Schema.
- Serviço pronto para ser iniciado por uma casca desktop (porta livre, sinal de pronto, token, pasta de dados).
- Frontend com cliente único, estados padronizados e configuração em tempo de execução.

**Ainda não implementado**
- Importador de orçamento; base de produtividade; geração de cronograma por IA; integração real com o Ollama; aplicação de propostas; simulação 4D definitiva; relatórios XLSX/PDF; app Windows e instalador; edição Web com backend remoto (autenticação e banco multiusuário).

**Dependências para a Etapa 3**
- Definir o escopo da Etapa 3 (sugestões: importação de orçamento e/ou visualizador IFC moderno e 4D).
- Disponibilizar modelos IFC reais e planilhas de orçamento reais para validação.
- Decidir sobre a correção dos erros da demonstração estática e do tema escuro.
- Opcional: trocar a branch padrão do repositório para `main` (hoje é `claude/amazing-newton-016hgd`).

**Riscos técnicos identificados**

| Risco | Mitigação prevista |
|---|---|
| Modelos IFC grandes consumindo muita RAM no processo de tarefa | Limite de 1 tarefa simultânea; medir com modelos reais; considerar geometria pré-processada |
| `web-ifc-three` descontinuado e com conflito de *peer dependency* | Prova de conceito com That Open Engine antes da etapa 4D |
| Empacotamento PyInstaller com IfcOpenShell e `spawn` | Testar cedo; `freeze_support` já presente; incluir `migrations/` como dados |
| SQLite com gravações concorrentes (API + tarefa) | WAL + `busy_timeout`; progresso com frequência limitada |
| Dependências do backend sem versão fixa (`>=`) | Avaliar fixação (lockfile pip) antes da distribuição Windows |
| Qualidade e consistência das respostas da IA | Contrato estrito, validação, e o motor sempre recalcula |
