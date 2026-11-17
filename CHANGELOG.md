# Changelog — BIM SCHEDULE

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
