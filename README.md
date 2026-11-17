# BIM SCHEDULE — 0.5.0-dev

Aplicação web independente do ecossistema BIMOFFICE para estruturar EAP, planejar atividades, calcular precedências, acompanhar custos e relacionar o cronograma a modelos IFC.

A interface pública utiliza a identidade visual Industrial Precision do COORDIX: IBM Plex, grafite, cobre, linhas técnicas e temas claro/escuro.

## Funcionalidades disponíveis na interface web

- Gestão local de projetos: salvar, salvar como, abrir, excluir e exportar/importar projeto em JSON.
- EAP e cadastro de atividades, com avanço físico e orçamento por atividade.
- Motor CPM no navegador com relações FS, SS, FF e SF, lags positivos/negativos, caminho crítico e detecção de ciclos.
- Calendário de trabalho configurável: data inicial, dias úteis da semana e feriados.
- Gráfico de Gantt recalculado a partir da rede de precedências.
- Importação IFC local com Web-IFC, indexação de entidades/GlobalIds, busca e vínculo de elementos às atividades.
- Visualizador geométrico IFC 3D e simulação temporal 4D por GlobalId, quando o navegador consegue carregar as dependências externas.
- Comparação inicial entre versões IFC por GlobalId adicionado/removido.
- Controle financeiro com orçamento, custo real informado, EV, PV aproximado, AC, SPI, CPI e EAC.
- Cadastro de recursos, alocação às atividades e alerta de sobrealocação por períodos coincidentes.
- PERT com estimativas otimista, mais provável e pessimista e simulação Monte Carlo por distribuição triangular.
- Consulta de previsão meteorológica de até 16 dias pelo Open-Meteo, sem chave de API, mediante coordenadas da obra.
- Intercâmbio estruturado com IA: exportação de contexto e importação de sugestões com aprovação manual.
- Snapshots locais, exportação de planilha compatível com Excel (SpreadsheetML) e impressão para PDF.
- Exportação de inventário IFC em CSV, tema claro/escuro e persistência local.

## Como testar

1. Abra a GitHub Page do repositório.
2. Use o projeto modelo ou crie uma cópia com **Salvar como**.
3. Cadastre/edite atividades e relações no **Cronograma Gantt**.
4. Configure o calendário e clique em **Recalcular CPM**.
5. Importe um IFC em **Modelo IFC**, confira o inventário e vincule GlobalIds às atividades.
6. Abra **Ambiente BIM 4D** e reproduza a linha do tempo.
7. Cadastre recursos, informe custos reais e rode a simulação PERT.
8. Salve snapshots e exporte o projeto JSON para backup.

## Limites técnicos que permanecem

- GitHub Pages é estático. Os projetos, recursos, custos, versões e snapshots são armazenados no navegador/dispositivo atual; não existe sincronização multiusuário nem banco central hospedado.
- A geometria IFC depende de WebGL e do carregamento de Three.js/Web-IFC-Three por CDN. O fluxo ainda precisa de validação ponta a ponta com arquivos IFC2x3, IFC4 e IFC4x3 reais de diferentes autores.
- A comparação de versões identifica inclusão/remoção de GlobalIds; não compara geometria, propriedades ou quantitativos.
- A classificação automática de disciplina é heurística e deve ser revisada.
- O PV financeiro é uma aproximação linear por duração; não substitui linha de base distribuída, medições ou apropriação contábil. AC é informado pelo usuário.
- O Monte Carlo usa distribuições triangulares independentes; não modela correlação, produtividade, clima ou riscos compartilhados.
- A previsão meteorológica cobre somente o horizonte fornecido pelo serviço e não decide paralisações automaticamente.
- A Central de IA faz intercâmbio de JSON; não chama diretamente Gemini, Claude ou OpenAI e não armazena chaves.
- A exportação Excel gera SpreadsheetML compatível com Excel, não um arquivo XLSX nativo. PDF é gerado pelo diálogo de impressão do navegador.
- O backend FastAPI existente oferece projetos, EAP, atividades, CPM e processamento IFC assíncrono local. Ele ainda não está hospedado para a GitHub Page.

## Execução local com backend

1. Extraia o projeto.
2. Execute `install.bat`.
3. Execute `start.bat`.
4. Acesse `http://127.0.0.1:3000`.
5. API: `http://127.0.0.1:8000` · Swagger: `http://127.0.0.1:8000/docs`.

Consulte `STATUS.md`, `AUDIT.md`, `IMPLEMENTATION_PLAN.md` e `TEST_REPORT.md` para a situação de validação.
