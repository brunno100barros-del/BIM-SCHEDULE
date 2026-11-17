# BIM SCHEDULE — interface demonstrativa

A aplicação web independente do ecossistema BIMOFFICE abre no Projeto Modelo Edifício Administrativo BIMOFFICE (ADM-001), com identidade visual inspirada no sistema Industrial Precision do COORDIX: IBM Plex, grafite, cobre, linhas técnicas, símbolo vetorial e temas claro/escuro.

## O que é possível testar
- Navegação por Visão Geral, EAP, Cronograma Gantt, Ambiente BIM 4D esquemático, Custos/Curva S, Recursos, Cenários/Riscos e Histórico.
- Editar avanço e duração de atividades.
- Cadastrar atividades de exemplo e recalcular a sequência FS de referência.
- Filtrar atividades, reproduzir a linha do tempo e exportar CSV.
- Alternar tema claro/escuro.
- Salvar alterações do projeto modelo no localStorage do navegador e restaurar a versão original.

## Limites importantes
Os dados do Projeto Modelo são demonstrativos e locais. Os GlobalIds são fictícios, o desenho 3D é esquemático e os indicadores financeiros/PERT são ilustrativos. A demonstração não representa BIM 4D real, CPM completo ou módulos financeiros validados. A área Ambiente conectado preserva a interface anterior ligada à API para projetos, EAP, Gantt e importação IFC.

## Executar
1. Extraia o projeto.
2. Execute install.bat.
3. Execute start.bat.
4. Acesse http://127.0.0.1:3000.

Frontend: http://127.0.0.1:3000 · Backend: http://127.0.0.1:8000 · Swagger: http://127.0.0.1:8000/docs.

Consulte STATUS.md, AUDIT.md, IMPLEMENTATION_PLAN.md e TEST_REPORT.md para as limitações da versão conectada.
