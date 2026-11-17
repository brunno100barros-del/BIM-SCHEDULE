# Plano de implementação — BIM SCHEDULE

## Versão 0.5.0-dev — funcionalidades adicionadas

- Gestão local de projetos e intercâmbio JSON.
- CPM no navegador com relações FS/SS/FF/SF, lags, detecção de ciclos e caminho crítico.
- Calendário semanal configurável, feriados e data de início.
- Financeiro por atividade com EV/PV/AC e indicadores de valor agregado.
- Cadastro de recursos, alocações e alertas básicos de sobrecarga.
- PERT triangular e Monte Carlo.
- Snapshots locais e histórico.
- Consulta meteorológica de curto prazo.
- Intercâmbio estruturado com IA com aprovação manual.
- Visualizador IFC 3D e sobreposição temporal 4D por GlobalId.
- Comparação inicial de versões IFC e exportação compatível com Excel/PDF.

## Próximas etapas obrigatórias para produção

1. **Validação do motor:** testes matemáticos independentes do CPM do navegador e backend; restrições de data, calendários por recurso, feriados locais e exceções.
2. **IFC:** ensaios com amostras IFC2x3, IFC4 e IFC4x3; modelos grandes; propriedades, quantidades, pavimentos, materiais e tratamento de geometrias inválidas.
3. **BIM 4D:** seleção bidirecional, ocultação/isolamento de elementos, filtros por disciplina, comparação temporal e desempenho em modelos extensos.
4. **Recursos:** produtividade, custos de equipe/equipamento/material, histogramas, nivelamento automático e resolução de conflitos.
5. **Riscos:** correlação entre riscos, calendário climático histórico, produtividade, análise de sensibilidade e validação estatística.
6. **Financeiro:** linha de base temporal, orçamento distribuído, medições, fluxo de caixa e curva S validada.
7. **Clima:** histórico sazonal e impacto parametrizado por tipo de serviço, sem paralisação automática.
8. **Central IA:** integração opcional com provedor, gerenciamento seguro de credenciais, consentimento, limites de uso e aprovação manual.
9. **Auditoria:** backend central, autenticação, trilha imutável, versões de cronograma/EAP/IFC e comparação detalhada.
10. **Hospedagem:** publicar API e banco persistente; conectar frontend público com CORS, autenticação, backups e monitoramento.
11. **Exportação:** XLSX nativo, PDF paginado, relatórios de caminho crítico e pacote de entrega.
12. **Release:** instalação limpa, testes integrados, teste Windows, acessibilidade e validação de desempenho.

## Critério de release 1.0.0

A versão 1.0.0 somente será liberada após validar o fluxo IFC → EAP → atividades → CPM → Gantt → associação IFC → simulação 4D → persistência/reabertura → exportação, além dos módulos complementares e do backend hospedado com dados compartilhados.
