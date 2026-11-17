# Status de desenvolvimento — BIM SCHEDULE 0.5.0-dev

Atualizado em 2026-11-17.

## Implementado na interface web (armazenamento local)

- [x] Identidade visual Industrial Precision, tipografia IBM Plex e temas claro/escuro.
- [x] Projeto modelo, EAP, Gantt, IFC, BIM 4D, custos, recursos, riscos e histórico.
- [x] Gestão local de projetos: salvar, salvar como, abrir, excluir e importar/exportar JSON.
- [x] Motor CPM no navegador com FS/SS/FF/SF, lags, detecção de ciclos, folgas e caminho crítico.
- [x] Calendário de dias úteis configurável e feriados.
- [x] Orçamento por atividade, custo real informado e indicadores EV/PV/AC/SPI/CPI/EAC.
- [x] Cadastro de recursos, alocações e alerta de sobrecarga em períodos coincidentes.
- [x] PERT triangular e Monte Carlo com percentis P50/P80/P90.
- [x] Snapshots locais do cronograma e parâmetros.
- [x] Intercâmbio estruturado de contexto/sugestões com IA, com aprovação manual.
- [x] Consulta de previsão meteorológica via Open-Meteo (até 16 dias).
- [x] Exportação SpreadsheetML compatível com Excel e impressão para PDF.
- [x] Importação IFC local, indexação de GlobalIds, busca, vínculo às atividades e inventário CSV.
- [x] Arquivamento local de GlobalIds de versões anteriores e comparação de inclusões/remoções.

## Implementação inicial — requer validação de campo

- [~] Visualizador geométrico IFC 3D via Three.js/Web-IFC-Three carregado por CDN.
- [~] Simulação BIM 4D com estados temporais dos elementos associados por GlobalId.
- [~] Comparação de versões IFC limitada a GlobalIds; sem diff de geometria, propriedades e quantitativos.
- [~] CPM no navegador com calendário semanal/feriados; ainda não contempla calendários independentes por recurso, restrições avançadas de data e exceções específicas.
- [~] Financeiro: PV linear aproximado; não há linha de base distribuída no tempo nem integração com medições.
- [~] Recursos: alocação e conflitos básicos; sem nivelamento automático, produtividade ou custos indiretos.
- [~] PERT/Monte Carlo: distribuições triangulares independentes; sem correlação ou análise quantitativa completa de riscos.
- [~] Clima: previsão de curto prazo; sem histórico sazonal integrado ao cálculo de prazo.
- [~] Central IA: intercâmbio JSON; não há integração direta com Gemini/Claude/OpenAI.
- [~] Auditoria: snapshots e histórico locais; não é trilha imutável de auditoria corporativa.

## Backend e publicação

- [x] Backend FastAPI com projetos, EAP, atividades, precedências, CPM e upload IFC assíncrono inicial.
- [x] Banco SQLite local, estrutura Alembic e testes existentes do núcleo.
- [ ] Backend hospedado e conectado à GitHub Page.
- [ ] Autenticação, permissões, banco compartilhado e colaboração multiusuário.
- [ ] Persistência central de recursos, custos, cenários, versões e auditoria.
- [ ] Teste ponta a ponta de IFC2x3/IFC4/IFC4x3 e visualização 4D com modelos reais.
- [ ] Build Vite/npm validado após as novas alterações.
- [ ] Testes manuais em Chrome/Edge, telas menores e Windows.
- [ ] Exportação XLSX nativa e PDF paginado com relatório técnico.

## Aviso de uso

A versão continua classificada como `0.5.0-dev`. Os módulos novos estão implementados em modo local e não devem ser tratados como sistema corporativo multiusuário ou ferramenta de medição contratual validada até a conclusão dos testes e da hospedagem do backend.
