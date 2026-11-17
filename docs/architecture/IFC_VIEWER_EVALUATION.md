# Visualizador IFC — avaliação para substituição

Estado: **avaliação**. Nenhuma troca foi feita na Etapa 2. O visualizador atual foi mantido sem mudança funcional. Ele só passou a usar o endereço da API e o token da configuração em tempo de execução e a carregar o WASM por caminho relativo.

## Situação atual

| Item | Situação |
|---|---|
| Biblioteca | `web-ifc-three@0.0.126` (IFCLoader para Three.js) sobre `web-ifc@^0.0.50`, com `three@^0.160` |
| Manutenção | O projeto IFC.js (que publicava `web-ifc-three`) foi descontinuado pelos mantenedores, que passaram a desenvolver o ecossistema **That Open Engine** (`@thatopen/components`, `@thatopen/fragments`), ainda sobre `web-ifc` |
| Dependências | `web-ifc-three@0.0.126` declara *peer dependency* de `three@^0.149`, incompatível com `three@0.160` usado no projeto. A instalação depende de `legacy-peer-deps=true` (`frontend/.npmrc`) |
| Carregamento | Faz o download do IFC inteiro e o processa na thread principal, o que trava a interface em modelos grandes |
| Tamanho do bundle | O build principal tem ~3,4 MB (~590 KB gzip), em grande parte Three.js + web-ifc |
| Validação | Não validado com modelos reais IFC2x3, IFC4 e IFC4x3 de porte |

## Alternativas

1. **That Open Engine** (`@thatopen/components` + `@thatopen/fragments`): sucessor natural. Converte o IFC em *fragments*, um formato otimizado para modelos grandes, com processamento em *worker*. Já traz componentes de seleção, isolamento, cortes e propriedades. Exige reescrever o `IfcViewer` e avaliar a API, que muda com frequência entre versões.
2. **`web-ifc` direto + Three.js próprio:** controle total e menos dependências, porém mais código para manter (geometria, seleção, propriedades).
3. **Geometria pré-processada no backend** (IfcOpenShell → glTF/fragments, em tarefa de segundo plano), com o visualizador carregando o arquivo leve. Aproveita o processamento IFC em processo separado que já foi implementado e evita reprocessar no navegador a cada abertura. Exige armazenar os arquivos derivados.

## Recomendação para a etapa do visualizador / 4D

- Fazer uma prova de conceito curta com a **opção 1**, medindo com modelos reais do usuário: tempo de abertura, memória (RAM e VRAM), fluidez e seleção por GlobalId. Isso é necessário para a simulação 4D, que pinta os elementos pelo estado da atividade.
- Avaliar a **opção 3** em seguida para modelos grandes, porque ela combina com a arquitetura de tarefas já pronta.
- Substituir o `web-ifc-three` só depois que a alternativa passar nessas medições. Até lá, o atual continua funcionando como está.
