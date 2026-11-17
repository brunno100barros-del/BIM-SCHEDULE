# Plano de implementação até a versão 1.0.0

## Etapa concluída nesta compilação (parcial)

- Fundação CPM/PERT e testes principais.
- Persistência SQLite com chaves estrangeiras.
- Migração inicial Alembic.
- CRUD de projetos, EAP e atividades.
- Precedências FS/SS/FF/SF e cálculo CPM com prazo.
- Gantt gráfico inicial.
- Importação IFC assíncrona básica, estado e progresso por lotes.
- Associação persistente Activity-GlobalId.

## Próximas etapas obrigatórias

1. **Estabilização do núcleo:** cobertura de testes do banco/API, migração de banco legado, auditoria de cascatas, calendários de trabalho, feriados e validação matemática independente.
2. **Planejamento avançado:** edição de relações no Gantt, marcos, restrições de data, calendário, caminho crítico e folgas por calendário.
3. **IFC:** validar IFC2x3 e IFC4 com modelos reais; extração de quantidades, pavimentos, propriedades e materiais; gestão de versões e comparação de GlobalIds.
4. **BIM 4D:** sincronização de atividade/GlobalId/Gantt, estados temporais, player e comparação de cenários.
5. **Recursos:** cadastro de equipes, equipamentos, materiais, produtividade e conflitos de alocação.
6. **PERT e cenários:** estimativas otimista, provável e pessimista, cenários isolados e comparação de prazo.
7. **Financeiro:** orçamento opcional, distribuição temporal, curva S e fluxo de caixa.
8. **Clima:** importação de dados e distinção entre histórico, sazonalidade e previsão.
9. **Central Gemini:** exportação/importação estruturada, validação e aprovação manual.
10. **Auditoria e versionamento:** histórico de versões de cronograma, EAP, parâmetros e modelos IFC.
11. **Exportação e release:** Excel/PDF, build, instalação limpa Windows, testes integrados e pacote 1.0.0.

## Critério de release

A versão 1.0.0 somente será publicada quando o fluxo completo IFC → EAP → atividades → CPM → Gantt → associação IFC → simulação 4D → persistência/reabertura → exportação estiver validado, além dos módulos complementares definidos no escopo do produto.
