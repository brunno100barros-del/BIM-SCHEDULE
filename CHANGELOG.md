# Changelog — BIM SCHEDULE

## 0.7.0 — 2026-11-22 (Etapa 4, parte 2: cronograma automático a partir do IFC, sem IA)
- **Quantitativos por elemento** (tarefa `ifc.quantities`, em processo separado, com progresso e cancelamento): por medida, usa Qto do IFC → Pset do autor com medida tipada → geometria (IfcOpenShell, em paralelo) → contagem. Tudo em SI, com a fonte, o método e o valor de origem de cada medida. Exclui aberturas e conjuntos já quantificados pelas peças; as peças de fachada e escada herdam o tipo do conjunto. Peso do aço = volume × 7850, exceto em seções maciças suspeitas.
- **Catálogo de serviços editável por projeto** (18 serviços: tipo IFC + material → serviço, unidade, produtividade, duração padrão e precedências). Produtividades começam vazias (sem índices inventados).
- **Gerador por regras**: EAP nível × serviço (pavimentos do IFC ou faixas de cota quando há um só pavimento), duração = ⌈quantidade ÷ produtividade⌉ ou padrão **provisória**, precedências padrão (mesmo nível, nível anterior), proteção contra ciclos, vínculo automático elemento ↔ atividade e CPM pelo motor existente (inalterado).
- **Tela "Gerar Cronograma"**: quantitativos por modelo, catálogo editável, pré-visualização editável (incluir, nome, duração) e aceite com substituição da geração anterior. Gantt com a etiqueta "provisória"; editar a duração remove a etiqueta.
- Lista de elementos do 3D com "Carregar mais" e filtro (antes limitada a 1000).
- Migração `0004_takeoff_schedule` (somente tabelas novas).
- Testes: backend 109 (9 novos), e2e 9 (1 novo), teste de fumaça do .exe com 11 verificações.

## 0.6.0 desktop — 2026-11-22 (Etapa 4: aplicativo Windows)
- Novo aplicativo desktop Electron (`desktop/`): protocolo `app://bim-schedule`, serviço local iniciado e encerrado pelo app em porta livre, token por sessão, CORS restrito à origem do app, janela única, menus (pasta de dados/logs, tutorial, Swagger) e tela de reinício caso o serviço caia.
- Serviço empacotado com PyInstaller (`bim-schedule-service.exe`), incluindo migrações Alembic e IfcOpenShell; tarefas IFC em processo separado funcionando dentro do executável.
- `build-desktop.bat` gera o app (`desktop\dist\win-unpacked\BIM SCHEDULE.exe`) e cria o atalho na Área de Trabalho.
- Corrigido: `install.bat` encerrava logo após `npm --version` (faltava `call`).
- Corrigido: o visualizador 3D nunca carregava (o WASM copiado era do web-ifc 0.0.50, mas o web-ifc-three usa 0.0.39). Mensagem clara para IFC sem geometria.
- Testes do executável empacotado: `desktop/scripts/smoke-test.cjs` e `viewer-check.cjs`; medição de importação: `ifc_benchmark.py` e `ifc_report.py`.
- `.gitignore`: modelos IFC reais nunca são versionados (só fixtures de teste).
- Tutorial: `docs/TUTORIAL-DESKTOP.md`. Relatório: `docs/reports/ETAPA-04-DESKTOP.md`.

## 0.6.0-dev — 2026-11-17 (Etapa 2: reestruturação da arquitetura)
- Aplicação React única como experiência principal; removidos a alternância `?connected=1` e o iframe. A demonstração estática foi preservada como referência e continua na raiz do GitHub Pages.
- Backend reorganizado em módulos por domínio (`app/modules`), com o motor CPM/PERT inalterado e as rotas `/api/v1` preservadas.
- Tarefas em segundo plano em processo separado (`spawn`), com progresso persistido, cancelamento cooperativo, encerramento forçado após prazo e recuperação de tarefas interrompidas. O processamento IFC passou a usá-las.
- Pasta de dados do usuário (`%LOCALAPPDATA%\BIM-SCHEDULE`) com migração por cópia validada dos dados legados (originais intactos) e backup do banco antes de migrações de esquema.
- Erros padronizados, `X-Request-ID`, logs rotativos, TrustedHost, CORS restrito e token local opcional.
- Configuração em tempo de execução do endereço do serviço (`runtime-config.js`), para o futuro app Windows.
- Preparação para IA: formato de intercâmbio v1, provedores Ollama (somente disponibilidade) e manual por arquivo (Claude), validação de respostas.
- `python -m app` como ponto de entrada do serviço; `install.bat` e `start.bat` atualizados.
- Testes: 62 no backend (Linux e Windows no CI), 12 unitários no frontend (Vitest), 8 de ponta a ponta (Playwright). Novo workflow `ci.yml`.
- Relatório completo: `docs/reports/ETAPA-02.md`.

## 0.3.0-dev — 2026-11-17
- Substituído o motor CPM por cálculo que preserva relações múltiplas entre o mesmo par de atividades.
- Prazo contratual passou a ser tratado como limite rígido, com folga negativa e indicador de inviabilidade.
- Lags negativos limitados pela data de início de referência do projeto.
- Adicionados testes para relações, múltiplas restrições, ciclos e prazo impossível.
- Habilitadas chaves estrangeiras no SQLite.
- Adicionadas migrações Alembic e atualização conservadora do esquema anterior.
- Ampliados os modelos de EAP, atividades e IFC.
- Implementados endpoints CRUD de EAP, atualização de atividades, precedências e vínculo Activity-GlobalId.
- Importação IFC movida para BackgroundTasks, com estado, mensagem e progresso persistidos.
- Criados painel do projeto, módulo EAP e Gantt temporal inicial.
- Módulos ainda não implementados foram desabilitados para não sugerir funcionalidade inexistente.
- Scripts de instalação e inicialização revisados.

## 1.0.0
Ainda não publicada. Será atribuída somente após cumprir e validar os critérios de aceitação da versão 1.0.

## 0.5.0-dev — 2026-11-17
- Adicionados módulos web locais para CPM/Gantt, custos, recursos, PERT/Monte Carlo, clima, intercâmbio JSON com IA e snapshots.
- Adicionada gestão de projetos com salvar, salvar como, abrir, excluir e backup JSON.
- Integrada leitura IFC existente com viewer 3D experimental e simulação 4D por GlobalId.
- Adicionado arquivamento local e comparação inicial de versões IFC por GlobalId.
- Corrigida a rota de renderização do módulo IFC.
- Adicionados testes Node de regressão para relações CPM, folgas, lags, ciclos e smoke checks.
- Alinhadas as dependências Three.js ao peer dependency do web-ifc-three 0.0.126.
- Mantidos como pendentes o backend hospedado, colaboração multiusuário, viewer IFC moderno, XLSX/PDF nativos e validação IFC ponta a ponta.
