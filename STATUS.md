# Status de desenvolvimento — BIM SCHEDULE · interface demonstrativa

Atualizado em 2026-11-17.

## Interface demonstrativa
- [x] Interface de entrada inspirada no sistema Industrial Precision do COORDIX.
- [x] Tipografia IBM Plex, paleta grafite/cobre e linhas técnicas.
- [x] Símbolo vetorial COORDIX integrado como referência visual do ecossistema.
- [x] Temas claro e escuro com preferência local.
- [x] Projeto modelo carregado por padrão.
- [x] Visão geral, EAP, Gantt, BIM 4D esquemático, custos, recursos, riscos e histórico.
- [x] Edição local de avanço/duração, cadastro de atividade e recálculo simplificado FS.
- [x] Linha do tempo com reprodução, seleção de atividades, exportação CSV e persistência local.
- [x] Preservação do ambiente conectado anterior em Ambiente conectado.

## Motor IFC no navegador — implementação inicial
- [x] Importação IFC local com Web-IFC 0.0.78 / WebAssembly, sem envio do arquivo para backend.
- [x] Indexação de entidades construtivas, nomes e GlobalIds.
- [x] Sugestão heurística de disciplina e busca no inventário.
- [x] Associação de GlobalIds reais às atividades e persistência local via IndexedDB.
- [x] Exportação do inventário IFC e vínculos em CSV.
- [ ] Visualizador geométrico IFC 3D no SCHEDULE.
- [ ] Simulação BIM 4D real, destacando no modelo os elementos vinculados conforme o avanço do cronograma.
- [ ] CPM completo conectado à interface pública e persistência compartilhada multiusuário.

## Limites da demonstração
- Dados do projeto modelo não são gravados no banco do backend.
- O modelo 3D exibido ainda é esquemático. O motor IFC lê metadados e GlobalIds, mas ainda não renderiza geometria no SCHEDULE.
- Simulação temporal não constitui BIM 4D real.
- Curva S, indicadores financeiros, recursos e cenários são ilustrativos.
- Recálculo demonstrativo simplificado, não substitui o motor CPM conectado FS/SS/FF/SF com lags.
- Histórico local não é auditoria completa.

## Ambiente conectado
Permanecem disponíveis os módulos anteriores de projetos, EAP, atividades, CPM/Gantt inicial e importação IFC assíncrona, com limitações descritas em AUDIT.md, IMPLEMENTATION_PLAN.md e TEST_REPORT.md.

## Validações pendentes
- Instalação limpa e build npm em ambiente com acesso ao registry.
- Teste responsivo em desktop, notebook e celular.
- Teste manual do ambiente conectado com backend ativo.
- Teste ponta a ponta de importação IFC real e persistência.
