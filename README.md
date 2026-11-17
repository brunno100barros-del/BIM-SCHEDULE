# BIM SCHEDULE — planejamento e controle BIM

Aplicação web do ecossistema BIMOFFICE para organizar EAP, atividades, precedências, cronograma, custos, recursos e vínculos com modelos IFC. A interface segue a identidade Industrial Precision do COORDIX.

## O que está implementado na versão de desenvolvimento

### Projeto e planejamento
- Criar cópia, salvar, abrir, excluir, importar e exportar projetos JSON no navegador.
- Gerenciar atividades, duração, avanço, orçamento e precedências.
- Motor CPM no navegador com relações FS, SS, FF e SF, lags positivos/negativos, caminho crítico, folgas e validação de ciclos.
- Calendário de trabalho configurável com dias da semana, feriados e data-base.
- Cronograma Gantt recalculado a partir da rede de precedências.

### BIM e IFC
- Importação de IFC local pelo Web-IFC, com indexação de entidades, nomes e GlobalIds.
- Busca, seleção e associação de GlobalIds a atividades.
- Inventário e associações exportáveis em CSV.
- Armazenamento do arquivo IFC no IndexedDB do navegador, separado dos dados leves do projeto.
- Visualizador geométrico IFC 3D experimental e simulação 4D por atividade/GlobalId.
- Arquivamento de versões e comparação inicial de GlobalIds adicionados/removidos.

### Controle e análise
- Custos por atividade, custo real informado, EV, PV linear aproximado calculado por data de status, AC, SPI, CPI e EAC.
- Cadastro de recursos, alocação às atividades e alerta básico de sobrealocação.
- Estimativas otimista, mais provável e pessimista; PERT e Monte Carlo com distribuição triangular.
- Consulta de previsão meteorológica pelo Open-Meteo, sem chave de API.
- Intercâmbio de contexto/sugestões em JSON com IA externa e aprovação manual.
- Histórico e snapshots locais, incluindo dados financeiros, calendário, recursos e vínculos IFC.
- Exportação SpreadsheetML compatível com Excel e impressão do navegador para PDF.

## Como testar online

1. Abra a GitHub Page: https://brunno100barros-del.github.io/BIM-SCHEDULE/
2. Na barra superior, use **Salvar como** para criar uma cópia do projeto modelo.
3. Em **Cronograma Gantt**, altere atividades e cadastre relações FS/SS/FF/SF; clique em **Recalcular CPM**.
4. Em **Modelo IFC**, selecione um arquivo IFC e clique em **Processar IFC**. Aguarde a barra de progresso e confira o inventário.
5. Selecione elementos e vincule-os a atividades; depois confira a simulação em **Ambiente BIM 4D**.
6. Informe custos reais em **Custos e Curva S**, cadastre recursos e rode o cenário PERT.
7. Salve o projeto e exporte o JSON para backup.

A página online só será atualizada depois que as alterações forem integradas à branch `main` e o workflow de GitHub Pages concluir o deploy.

## Limitações que não devem ser confundidas com funcionalidades prontas

- **Armazenamento:** projetos, IFC, recursos, custos e snapshots ficam no navegador/dispositivo atual. Não há sincronização multiusuário, login ou banco central hospedado.
- **Backend:** a API FastAPI existente é executada localmente. A GitHub Page é estática e ainda não está conectada a uma API hospedada.
- **Visualizador IFC:** o viewer usa `web-ifc-three` 0.0.126, uma biblioteca antiga/depreciada. O carregamento 3D é experimental e precisa de validação com modelos reais IFC2x3, IFC4 e IFC4x3, além de modelos grandes. O leitor de metadados e o viewer geométrico são fluxos diferentes.
- **BIM 4D:** a cor temporal depende de GlobalIds associados às atividades. Não há ainda seleção bidirecional completa, isolamento avançado, diff geométrico ou quantitativos por fase.
- **CPM:** o motor calcula a rede em dias de trabalho relativos; o calendário converte posições em datas. Ainda faltam calendários por recurso, restrições avançadas e testes independentes de todos os casos especiais.
- **Custos:** PV é aproximado por distribuição linear do orçamento ao longo da duração. AC é informado pelo usuário. Não substitui medição, apropriação contábil, orçamento distribuído ou fluxo de caixa.
- **Recursos:** existe cadastro, alocação e alerta de conflitos básicos. Não há nivelamento automático, produtividade ou composição detalhada de custos.
- **Riscos:** Monte Carlo usa distribuições triangulares independentes. Não há correlação entre riscos nem modelo de produtividade/clima.
- **Clima:** previsão de curto prazo, não série histórica sazonal nem decisão automática de paralisação.
- **IA:** não existe chamada direta a Gemini, Claude ou OpenAI. O módulo exporta contexto JSON e importa sugestões para revisão manual, sem chave de API.
- **Exportação:** a planilha é SpreadsheetML com extensão .xls, não XLSX nativo. PDF usa o diálogo de impressão do navegador.
- **Auditoria:** histórico e snapshots são locais e editáveis, não trilha imutável corporativa.

## Execução local

1. Extraia o repositório.
2. Execute `install.bat`.
3. Execute `start.bat`.
4. Acesse `http://127.0.0.1:3000`.
5. API local: `http://127.0.0.1:8000`; documentação: `http://127.0.0.1:8000/docs`.

Consulte `STATUS.md`, `IMPLEMENTATION_PLAN.md`, `AUDIT.md` e `TEST_REPORT.md` antes de usar em um projeto real.
