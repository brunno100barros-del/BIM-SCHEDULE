# Status técnico — BIM SCHEDULE 0.5.0-dev

Atualizado em 17/11/2026. Esta é uma versão de desenvolvimento, não uma liberação de produção.

## Implementado na interface web local

- [x] Identidade visual e navegação por módulos.
- [x] Gestão de projetos no navegador: salvar, salvar como, abrir, excluir, importar e exportar JSON.
- [x] EAP e cadastro/edição de atividades.
- [x] CPM com FS, SS, FF, SF, lags, caminho crítico, folgas, ciclos e validações básicas.
- [x] Calendário semanal configurável, feriados e data-base.
- [x] Gantt recalculado pela rede CPM.
- [x] Importação IFC local, indexação de GlobalIds, busca, seleção e vínculos às atividades.
- [x] Persistência do arquivo e índice IFC no IndexedDB por projeto.
- [x] Inventário IFC CSV.
- [x] Viewer geométrico IFC 3D experimental.
- [x] Simulação 4D temporal por atividade/GlobalId.
- [x] Arquivamento de GlobalIds de versões anteriores e comparação de inclusões/remoções.
- [x] Controle financeiro EV/PV/AC/SPI/CPI/EAC com data de status editável e PV linear aproximado.
- [x] Cadastro de recursos, alocações e alertas básicos de sobrealocação.
- [x] PERT e Monte Carlo triangular.
- [x] Consulta meteorológica Open-Meteo.
- [x] Intercâmbio JSON com IA externa e aprovação manual.
- [x] Snapshots e histórico local, incluindo custos, calendário, recursos e vínculos IFC.
- [x] Exportação SpreadsheetML e impressão para PDF.
- [x] Testes de regressão CPM e smoke checks da integração de módulos adicionados ao CI.

## Parcial / experimental

- [~] Viewer IFC 3D: depende de CDN/WebGL e de biblioteca antiga; sem validação de compatibilidade com todos os modelos.
- [~] BIM 4D: coloração por GlobalId; sem seleção bidirecional, isolamento avançado e diff geométrico.
- [~] CPM: dias de trabalho relativos e calendário básico; sem calendário individual por recurso e restrições avançadas.
- [~] Financeiro: PV linear aproximado; sem baseline temporal detalhada, medições e fluxo de caixa.
- [~] Recursos: conflitos básicos; sem nivelamento automático.
- [~] Monte Carlo: triangulares independentes; sem correlação e análise quantitativa abrangente.
- [~] Clima: previsão curta; sem histórico sazonal e sem paralisação automática.
- [~] IA: intercâmbio JSON; sem integração direta com provedor.
- [~] Versionamento: comparação de GlobalIds; sem comparação geométrica/propriedades.
- [~] Exportação: SpreadsheetML .xls e PDF via impressão; sem XLSX nativo e PDF paginado próprio.

## Não implementado / depende de infraestrutura

- [ ] API FastAPI hospedada e conectada à página pública.
- [ ] Login, permissões, banco central, colaboração e sincronização multiusuário.
- [ ] Auditoria corporativa imutável.
- [ ] Teste ponta a ponta com arquivos IFC2x3, IFC4 e IFC4x3 de diferentes autores.
- [ ] Teste de desempenho e memória com modelos de grande porte.
- [ ] Viewer moderno baseado em That Open Components.
- [ ] Integração direta opcional com Gemini/Claude/OpenAI via backend seguro.
- [ ] Nivelamento automático de recursos e custos por produtividade.
- [ ] Linha de base financeira distribuída, medições e fluxo de caixa.
- [ ] Exportação XLSX nativa e PDF técnico paginado.
- [ ] Validação manual em Chrome/Edge, Windows e telas menores.

## Regra de uso

Não usar os resultados do viewer, Monte Carlo ou indicadores financeiros como medição contratual ou decisão de engenharia sem validação independente. A versão deve permanecer identificada como `0.5.0-dev`.
