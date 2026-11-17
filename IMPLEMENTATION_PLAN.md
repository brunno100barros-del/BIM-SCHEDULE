# Plano de implementação — BIM SCHEDULE

## Entregue na linha 0.5.0-dev

1. Gestão local de projetos e backup JSON.
2. CPM no navegador com FS/SS/FF/SF, lags, ciclos e caminho crítico.
3. Calendário semanal e feriados.
4. IFC local, inventário GlobalId, vínculo às atividades e CSV.
5. Viewer 3D experimental e simulação 4D por GlobalId.
6. Versionamento inicial por GlobalId.
7. Indicadores EV/PV/AC/SPI/CPI/EAC.
8. Recursos e conflitos básicos de alocação.
9. PERT/Monte Carlo triangular.
10. Consulta meteorológica, intercâmbio JSON com IA, snapshots e exportações.

## Próximas etapas obrigatórias

### A. Validar o fluxo BIM
- Testar amostras IFC2x3, IFC4 e IFC4x3.
- Verificar unidades, coordenadas, geometrias inválidas, modelos federados e arquivos grandes.
- Validar a correspondência dos IDs entre o leitor Web-IFC e o viewer.
- Testar renderização, seleção, isolamento, visibilidade e atualização 4D.
- Substituir a biblioteca antiga web-ifc-three por That Open Components antes de produção.

### B. Validar o planejamento
- Criar bateria de casos CPM com todas as relações, lags, múltiplas predecessoras, restrições de data, ciclos e prazos inviáveis.
- Validar resultados com cálculo independente.
- Implementar calendários por atividade/recurso, exceções e restrições de data.
- Incluir linha de base, comparação planejado x atual e atualização de status-date.

### C. Controle de custos e recursos
- Distribuir orçamento por períodos e curva S.
- Integrar medições e custo real.
- Implementar produtividade, custo unitário, equipes/equipamentos e nivelamento.
- Testar conflitos em períodos e calendários diferentes.

### D. Riscos e clima
- Permitir correlação entre durações e riscos.
- Incluir sensibilidade e distribuição documentada.
- Integrar histórico sazonal e parametrização de impacto climático por serviço.
- Nunca interromper atividades automaticamente sem regra aprovada.

### E. Plataforma corporativa
- Hospedar FastAPI e banco persistente.
- Criar autenticação, autorização, compartilhamento e trilha de auditoria.
- Sincronizar projetos, IFC, versões, recursos e custos.
- Implementar backups, monitoramento, CORS e gestão de segredos.

### F. Entregáveis e release
- Gerar XLSX nativo e PDF técnico paginado.
- Testar build limpo, CI, Chrome/Edge, Windows e telas menores.
- Validar o fluxo IFC → EAP → CPM → Gantt → associação → 4D → salvar/reabrir → exportar.
- Só então avaliar versão 1.0.0.

## Critério para versão 1.0.0

Nenhum módulo deve ser classificado como concluído apenas por existir uma tela ou botão. A liberação exige testes automatizados, testes com arquivos/modelos reais e documentação das limitações residuais.
