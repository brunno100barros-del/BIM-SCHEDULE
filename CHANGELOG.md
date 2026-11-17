# Changelog — BIM SCHEDULE

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
