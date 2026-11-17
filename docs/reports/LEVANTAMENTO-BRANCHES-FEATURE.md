# Levantamento das branches `feature/*` fora da `main`

Data: 2026-11-17 · Referência: `main` em `2fb923b02568195f2072d54f52518078655530e4`.

Levantamento **somente documental**. Nenhuma branch foi alterada, mesclada ou aproveitada por cherry-pick. Todas foram preservadas.

Método: `git log origin/main..origin/<branch>` (commits que não estão na `main`), `git diff origin/main origin/<branch>` (diferença de conteúdo entre as pontas) e comparação das funções JavaScript da demonstração.

## Resumo

| Branch | Ponta | Commits fora da `main` | Diferença de conteúdo em relação à `main` | Conclusão |
|---|---|---|---|---|
| `feature/bim-schedule-reimplementation` | `aad7764` | 39 | **Nenhuma** (árvore idêntica à `main`) | Conteúdo **já incorporado** à `main`, provavelmente por *squash* no commit `2fb923b`. Nada a aproveitar. |
| `feature/complete-bim-schedule` | `a2c5ae7` | 13 | Versão alternativa e **mais antiga** da demonstração (`schedule-enhancements.js` com 575 linhas, contra 776 na `main`) e documentação "0.5.0-dev" | Nenhuma função exclusiva: todas as funções desta versão existem na `main`, que tem 6 a mais (`applyExt`, `calculateEarnedValue`, `deleteCurrentProject`, `ifcDBDeleteById`, `ifcDBGetById`, `restoreProjectIfc`). Pode haver diferenças de implementação dentro de funções de mesmo nome (PERT, ciclo de vida do viewer, reprodução 4D), a serem revisadas se houver interesse. |
| `feature/ifc-browser-schedule-engine` | `a807267` | 9 | Estado anterior da `main` (sem `schedule-enhancements.js` e testes) | Superada. A importação IFC no navegador e a rastreabilidade por GlobalId já estão na `main` (commit `47c5a47`). |
| `feature/github-pages-demo` | `bcbd0e2` | 6 | Estado anterior | Superada. O workflow do Pages já está na `main` (PR #2, commit `0a27054`). |
| `feature/coordix-industrial-workspace` | `e337274` | 1 | Estado anterior | Superada. A identidade "Coordix/Industrial Precision" já está na `main` (commit `1cccca5`). |

## Detalhes por branch

### `feature/bim-schedule-reimplementation` (PR #4)

Os 39 commits cobrem módulos da demonstração (CPM no navegador, custos e EV/PV/AC, recursos, PERT/Monte Carlo, clima via Open-Meteo, intercâmbio JSON com IA, snapshots), correções de reset e isolamento de IFC entre projetos locais, testes `schedule-engine.test.mjs` e documentação. A comparação de conteúdo com a `main` é vazia: tudo isso já está na `main`.

### `feature/complete-bim-schedule`

Principais commits:
- "Add functional planning, control and analysis modules"
- "Harden PERT simulation, viewer lifecycle and 4D playback"
- "Persist project backups efficiently and archive IFC versions"
- "Correct project switching and IFC version capture"
- "Document BIM Schedule 0.5 development scope and limitations"

Para avaliar no futuro: comparar, função a função, `simulatePert` (PERT/Monte Carlo), o ciclo de vida do visualizador (`loadViewerEngine`, `mountIfcViewer`, `disposeViewer`) e a reprodução 4D (`update4D`) com a versão da `main`, antes da etapa do visualizador e da simulação 4D. Os módulos são da **demonstração estática**: aproveitá-los na aplicação React exige reimplementação sobre o backend e o motor de engenharia, não cópia.

### `feature/ifc-browser-schedule-engine` (PR #3), `feature/github-pages-demo`, `feature/coordix-industrial-workspace` (PR #1)

São etapas intermediárias cujo resultado já foi incorporado à `main`. As diferenças de conteúdo são só remoções, porque essas branches não têm o que foi acrescentado depois.

## Situação dos Pull Requests (consultada no GitHub)

| PR | Branch | Estado |
|---|---|---|
| #1 | `feature/coordix-industrial-workspace` | Mesclado e fechado |
| #2 | `feature/github-pages-demo` | Mesclado e fechado |
| #3 | `feature/ifc-browser-schedule-engine` | Mesclado e fechado |
| #4 | `feature/bim-schedule-reimplementation` | Mesclado e fechado (squash → `2fb923b`) |
| — | `feature/complete-bim-schedule` | Sem PR. Conteúdo nunca mesclado, porém sem funções exclusivas em relação à `main` |

As branches continuam no repositório. Removê-las é uma decisão sua e não foi tomada nesta etapa.
