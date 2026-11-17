# BIM SCHEDULE — interface demonstrativa

A aplicação web independente do ecossistema BIMOFFICE abre no Projeto Modelo Edifício Administrativo BIMOFFICE (ADM-001), com identidade visual inspirada no sistema Industrial Precision do COORDIX: IBM Plex, grafite, cobre, linhas técnicas, símbolo vetorial e temas claro/escuro.

## O que é possível testar
- Importar arquivos IFC diretamente no navegador com Web-IFC/WebAssembly (sem upload do arquivo para um servidor), indexar GlobalIds e entidades construtivas, pesquisar elementos e vinculá-los às atividades; o arquivo e o índice ficam no IndexedDB do navegador.
- Exportar inventário IFC em CSV com GlobalIds e atividades vinculadas.
- Navegação por Visão Geral, EAP, Cronograma Gantt, Ambiente BIM 4D esquemático, Custos/Curva S, Recursos, Cenários/Riscos e Histórico.
- Editar avanço e duração de atividades.
- Cadastrar atividades de exemplo e recalcular a sequência FS de referência.
- Filtrar atividades, reproduzir a linha do tempo e exportar CSV.
- Alternar tema claro/escuro.
- Salvar alterações do projeto modelo no localStorage do navegador e restaurar a versão original.

## Limites importantes
Os dados do Projeto Modelo são demonstrativos e locais. Ao importar um IFC real, o SCHEDULE lê metadados/GlobalIds e permite vinculá-los às atividades; a classificação de disciplina é uma sugestão heurística que exige revisão. O painel 3D ainda é esquemático: esta etapa não renderiza a geometria IFC nem executa simulação 4D espacial. Os indicadores financeiros/PERT continuam ilustrativos. A demonstração não representa BIM 4D real, CPM completo ou módulos financeiros validados. A área Ambiente conectado preserva a interface anterior ligada à API para projetos, EAP, Gantt e importação IFC.

## Executar
1. Extraia o projeto.
2. Execute install.bat.
3. Execute start.bat.
4. Acesse http://127.0.0.1:3000.

Frontend: http://127.0.0.1:3000 · Backend: http://127.0.0.1:8000 · Swagger: http://127.0.0.1:8000/docs.

Consulte STATUS.md, AUDIT.md, IMPLEMENTATION_PLAN.md e TEST_REPORT.md para as limitações da versão conectada.
