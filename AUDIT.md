# Auditoria técnica — ZIP de origem `BIM-SCHEDULE-v1.0.0(2).zip`

## Escopo da auditoria

Inspeção estática dos arquivos entregues, execução dos testes Python existentes e novos testes de unidade/API após as alterações desta compilação. A instalação do frontend e o processamento real de IFC não puderam ser validados neste ambiente.

## Situação encontrada no pacote de origem

- Backend FastAPI e modelos SQLAlchemy iniciais estavam presentes.
- Endpoints disponíveis apenas para projetos, atividades/precedências e upload IFC.
- O motor CPM corrigia a soma indevida de EF no forward pass, mas ainda usava `DiGraph`, sobrescrevendo relações múltiplas.
- O prazo informado era descartado quando menor que o prazo calculado.
- O endpoint CPM não encaminhava o prazo do projeto.
- Upload e leitura IFC ocorriam sincronamente na requisição HTTP.
- O endpoint IFC informava sucesso mesmo quando o parser retornava falha.
- O parser extraía somente identificador, nome, tipo e descrição.
- Não existia associação persistente entre atividades e elementos IFC.
- A tela chamada Gantt era uma tabela, não uma linha temporal gráfica.
- A EAP não possuía endpoints de gerenciamento.
- A maioria dos itens do menu eram telas genéricas sem implementação.
- O README e CHANGELOG classificavam o pacote como produção v1.0.0 sem evidências de validação suficientes.

## Alterações aplicadas nesta compilação

- Reescrito o motor CPM para preservar todas as restrições, detectar ciclos e reportar inviabilidade de prazo por folga negativa.
- Acrescentados testes para relações, múltiplas relações, lags negativos, ciclos e prazo impossível.
- Ativado `PRAGMA foreign_keys=ON` no SQLite e incluído teste automatizado.
- Adicionada estrutura inicial de migrações Alembic.
- Ampliados modelos de EAP, atividades e IFC.
- Implementados endpoints de CRUD de EAP, atualização de atividades, precedências, vínculo/desvínculo Activity-IFC e comparação inicial de conjuntos de GlobalIds entre versões processadas.
- Melhorada a validação de projeto e duplicação de estrutura de EAP/atividades/precedências.
- Upload IFC passou a tarefa de background, com estado, progresso por lotes e mensagens de erro persistidas.
- Criados painel do projeto, módulo de EAP e Gantt temporal inicial com conectores de precedência.
- Melhorado o ciclo de vida do visualizador IFC.
- Módulos ainda não implementados foram desabilitados no menu e declarados como pendentes.
- Scripts Windows e documentação foram revisados.

## Limitações que permanecem

- Não há fila distribuída nem recuperação de processamento IFC após queda do processo.
- IfcOpenShell não estava instalado neste ambiente; não foi executado teste IFC ponta a ponta.
- That Open Engine ainda não foi adotado; o viewer segue com `web-ifc-three`.
- O Gantt não tem calendário de dias úteis, edição por arrastar ou edição completa de relações na própria linha temporal.
- A seleção do GlobalId ainda não é sincronizada bidirecionalmente com a geometria do visualizador.
- Recursos, cenários PERT, BIM 4D completo, financeiro, clima, Central Gemini e auditoria/versionamento não estão implementados.
- O frontend não teve build validado: `npm install` excedeu o tempo limite porque o registry npm não estava acessível por falha de DNS.
- Os scripts `.bat` não foram executados em Windows.

## Classificação

Esta compilação é `0.3.0-dev`. Não deve ser apresentada como versão 1.0.0 de produção.


## Complemento da auditoria — interface 0.5.0-dev

A linha anterior deste documento registra a auditoria da compilação 0.3.0-dev e não descreve o estado atual desta branch.

### Implementações adicionadas na branch de reimplementação

- Módulos web de CPM/Gantt, financeiro, recursos, PERT/Monte Carlo, clima, intercâmbio JSON com IA e snapshots locais.
- Gestão de projetos no navegador, com arquivos JSON e IndexedDB separado para modelos IFC.
- Correção do vínculo da navegação IFC ao renderer da página.
- Viewer 3D experimental e simulação temporal 4D por GlobalId.
- Testes de regressão para o motor CPM do navegador e smoke checks de integração.
- Ajuste da dependência Three.js para a faixa compatível com `web-ifc-three@0.0.126`.

### Riscos e limites mantidos

- A implementação de viewer usa `web-ifc-three@0.0.126`, biblioteca antiga/depreciada; deve ser substituída por That Open Components antes de produção.
- A versão 3D depende de CDN, WebGL e compatibilidade real entre o parser de metadados e o carregador geométrico.
- Os testes adicionados cobrem o motor CPM e integração estática, não comprovam abertura de arquivos IFC reais.
- Os módulos financeiros, recursos, PERT, clima e IA possuem as aproximações descritas em `STATUS.md`.
- GitHub Pages continua estático; backend não está hospedado e não há sincronização multiusuário.

### Critério de validação desta branch

O resultado de build, testes Node e workflow deve ser consultado no GitHub Actions. A validação geométrica IFC e a execução manual permanecem pendentes mesmo se o CI passar.
