# Etapa 4 — Aplicativo desktop (Electron) e testes com IFCs reais

Branch: `etapa-04/desktop-electron` (a partir de `etapa-03/nucleo-bim` @ 3baea88).
Backup: `backup/etapa-04-pre-desktop-2026-11-22`. Data: 22/11/2026. Ambiente: Windows 10 Pro, Python 3.12.10,
Node 22.23.4, npm 12.2.3.

> Os IFCs usados nos testes são do usuário e **não** estão no repositório. Este relatório usa nomes
> genéricos (Modelo A…K). O relatório detalhado, com nomes, fica apenas na máquina local.

## 1. O que foi feito

| Item | Arquivos |
|---|---|
| Casca Electron conforme `docs/architecture/WINDOWS_DESKTOP.md` (protocolo `app://bim-schedule`, `runtime-config.js` dinâmico, token por sessão, CORS exato, `contextIsolation`/`sandbox`, bloqueio de navegação externa, janela única, encerramento com `taskkill /T`, diálogo de reinício se o serviço cair, menus) | `desktop/main.cjs`, `desktop/package.json` |
| Serviço empacotado (PyInstaller, onedir) com migrações Alembic, IfcOpenShell e todos os módulos de `app/` (as tarefas são importadas dinamicamente) | `desktop/service/bim-schedule-service.spec` |
| Script único de geração + atalho na Área de Trabalho | `build-desktop.bat` |
| Testes do executável empacotado | `desktop/scripts/smoke-test.cjs`, `desktop/scripts/viewer-check.cjs` |
| Medição e análise de IFCs (tempo, memória, extração) | `desktop/scripts/ifc_benchmark.py`, `desktop/scripts/ifc_report.py` |
| Ícone gerado sem dependências | `desktop/scripts/make-icon.py`, `desktop/build/icon.ico` |
| Tutorial | `docs/TUTORIAL-DESKTOP.md` |

Nenhuma alteração em `backend/` (motor CPM/PERT intocado). O CI existente não foi alterado.

## 2. Defeitos encontrados e corrigidos

1. **`install.bat` parava após `npm --version`.** `npm` é `npm.cmd`, e chamar um `.cmd` sem `call` encerra o script em lote. Corrigido com `call node --version` e `call npm --version`.
2. **O visualizador 3D nunca carregava** (`WebAssembly.instantiate(): Import #49 "a" "X": function import requires a callable`). `copy-wasm.js` copiava o `.wasm` do `web-ifc` 0.0.50 (raiz), mas o `IFCLoader` do `web-ifc-three` 0.0.126 usa o próprio `web-ifc` 0.0.39. Agora o script copia o WASM da versão usada pelo carregador. Afetava também a versão web.
3. **IFC sem geometria** gerava `Cannot read properties of undefined (reading 'index')`. Agora a mensagem diz que o arquivo não tem geometria 3D visualizável.
4. **Serviço empacotado sem os módulos de tarefa** (`No module named 'app.modules.ifc.jobs'`). Encontrado pelo teste de fumaça. O `.spec` agora lista os módulos a partir dos arquivos-fonte.
5. O rodapé da barra lateral exibia "Desenvolvimento" fixo. Agora mostra "Aplicativo desktop" no app.

## 3. Resultados dos testes (saídas reais)

| Suíte | Resultado |
|---|---|
| Backend `pytest -q` | **100 passed**, 1 warning (145,7 s) |
| Frontend `vitest` | **12 passed** |
| Frontend `node --test` (motor de cronograma) | **9 passed** |
| Playwright e2e (web) | **8 passed** |
| Teste de fumaça do .exe com IFC real | **8/8**: abre conectado em 2,3 s, cria projeto, processa IFC no processo separado, 3D carregado, CPM = 7 dias, sem erros JS, serviço encerrado ao fechar |
| Teste de fumaça com o IFC sintético da fixture (sem geometria) | 7/8. A falha esperada é o 3D, porque o arquivo não tem geometria. |
| Modo web (`start.bat`) | frontend 200, API via proxy ok. **Nenhuma migração ou backup repetido** na inicialização (correção da Etapa 3 confirmada). |
| Modo desenvolvimento do desktop (`npm start`) | serviço da `.venv` iniciado, interface conectada |

Pacote: `desktop/dist/win-unpacked` com ~510 MB (Electron ~270 MB + serviço ~236 MB).

## 4. IFCs reais (11 arquivos, 8 programas de autoria)

| Modelo | Schema | Autoria | Tamanho | Processamento | Pico memória da tarefa | Elementos | 3D no app |
|---|---|---|---|---|---|---|---|
| A | IFC4 | CYPE 3D | 0,2 MB | 2,0 s | 106 MB | 150 | OK |
| B | IFC4 | exportador próprio (plugin) | 0,3 MB | 1,0 s | 106 MB | 12 | **sem geometria legível** |
| C | IFC4 | AltoQi Eberick | 2,2 MB | 1,5 s | 121 MB | 863 | OK |
| D | IFC4 | SteelX | 8,6 MB | 3,5 s | 152 MB | 7.006 | OK |
| E | IFC4 | AltoQi Builder | 14,8 MB | 2,5 s | 171 MB | 1.424 | OK |
| F | IFC4X3 | Revit 2026 | 139,4 MB | 11,6 s | 920 MB | 11.703 | OK (7,1 s) |
| G | IFC4 | SteelX | 9,7 MB | 3,0 s | 157 MB | 5.407 | OK |
| H | IFC2X3 | Advance Steel 2026 | 13,1 MB | 2,0 s | 166 MB | 1.798 | OK |
| I | IFC2X3 | Advance Steel 2026 | 23,1 MB | 2,5 s | 222 MB | 2.655 | OK |
| J | IFC2X3 | Revit 2027 | 32,1 MB | 4,0 s | 284 MB | 3.569 | OK (15,8 s) |
| K | IFC2X3 | TQS 24 | 7,2 MB | 1,5 s | 138 MB | 601 | OK |

Principais conclusões:
- **Nenhum dos 11 arquivos tem `IfcElementQuantity`** (Qto_*/BaseQuantities). Ler Qto do IFC não basta. Os quantitativos precisam vir da **geometria** (calculável em 9 dos 11; 2 a 70 ms por elemento; ~65% de sucesso no Advance Steel IFC2X3), de **Psets do autor** (AltoQi, TQS, Advance Steel) ou de **contagem**.
- Unidades de comprimento em m, cm e mm, conforme o programa. A massa não é definida em Revit nem em Advance Steel. É preciso normalizar para SI com rastreabilidade.
- Pavimentos: bons em Revit, TQS e AltoQi Builder. Eberick exporta subníveis com nomes repetidos. SteelX, Advance Steel, CYPE e o plugin exportam **um único pavimento**, então a EAP por pavimento exige agrupamento por cota ou por conjunto.
- Classificação apenas parcial em Revit (Uniformat). A contagem bruta inclui aberturas, portas de distribuição e duplicidade conjunto/peça (SteelX), que precisam ser filtradas.
- A lista de elementos da tela mostra no máximo 1000 itens.

## 5. Pendências conhecidas

- Instalador NSIS configurado (`npm run dist:installer`), mas não gerado nem testado. Sem assinatura de código (SmartScreen avisa).
- Se o processo do Electron for morto à força (sem passar pelo `before-quit`), o serviço pode ficar órfão até ser encerrado manualmente.
- A memória da janela não volta ao patamar inicial ao trocar de modelo no 3D (~1,7 GB → ~0,95 GB).
- `npm audit` aponta vulnerabilidades em dependências de desenvolvimento (Electron 33 e electron-builder 25). Avaliar a atualização antes de distribuir.

---

# Parte 2 — Cronograma automático a partir do IFC (sem IA)

Implementa os itens (a), (b) e (c) da proposta: quantitativos rastreáveis, gerador por regras e a tela
"Gerar Cronograma". O motor CPM/PERT (`backend/app/engine/cpm_pert.py`) **não foi alterado**.

## 6. O que foi feito

| Item | Arquivos |
|---|---|
| Tabelas novas: `ifc_takeoff_runs`, `ifc_element_takeoff`, `schedule_services`, `schedule_generations` e `schedule_generated_activities`. Migração só aditiva. | `backend/app/models/takeoff.py`, `backend/migrations/versions/0004_takeoff_schedule.py` |
| Extrator de quantitativos. Ordem das fontes: Qto → Pset tipado → geometria → contagem. Resultado em SI, com fonte, método e valor de origem por medida. | `backend/app/modules/takeoff/extractor.py` |
| Tarefa `ifc.quantities` (processo separado, progresso, cancelamento, *abort hook*) | `backend/app/modules/takeoff/jobs.py`, `backend/app/jobs/registry.py` |
| Catálogo padrão de 18 serviços e regras de material (aço/concreto) | `backend/app/modules/takeoff/catalog.py` |
| Gerador: níveis (pavimentos ou faixas de cota), durações, precedências, proteção contra ciclos | `backend/app/modules/takeoff/generator.py` |
| Aplicação: EAP, atividades, precedências, vínculos com elementos, CPM e substituição da geração anterior | `backend/app/modules/takeoff/service.py`, `router.py` |
| Rotas `/api/v1/takeoff/*` e `/api/v1/schedule-generator/*` | `backend/app/api/v1/api.py` |
| Duração editada pelo usuário deixa de ser provisória | `backend/app/modules/planning/router.py` |
| Tela "Gerar Cronograma", etiqueta "provisória" no Gantt, paginação e filtro dos elementos | `frontend/src/modules/generator/`, `services/generator.ts`, `modules/gantt/`, `modules/bim3d/` |
| Validação com os projetos de teste | `desktop/scripts/generator_validation.py` |

Decisões:
- **Sem índices inventados.** As produtividades começam vazias. Sem produtividade, a duração é a padrão do
  serviço e fica marcada como provisória, com o motivo.
- **Pset só com medida tipada** (IfcLengthMeasure, IfcAreaMeasure, IfcVolumeMeasure, IfcMassMeasure). Valores
  `IfcReal` são ignorados, porque a unidade seria suposição.
- **Área geométrica:** volume ÷ espessura nos elementos delgados (exata em paredes e lajes extrudadas); nos demais,
  metade da área superficial. **Comprimento:** maior dimensão da caixa local.
- **Peso do aço:** volume × 7850 kg/m³, mas não quando volume ÷ comprimento > 0,06 m². Nos testes, vigas TQS
  com material "ASTM A36" e seção maciça de 0,17 m² teriam gerado 16 t de aço fictício.
- **Conjuntos:** conjuntos com peças (`IfcElementAssembly`, `IfcCurtainWall`, `IfcStair`…) não são somados; as
  peças são. Assim se evita a contagem dupla que o SteelX gerava. As peças de fachada e escada herdam o tipo do
  conjunto para as regras.

## 7. Testes (saídas reais)

| Suíte | Resultado |
|---|---|
| Backend `pytest -q` | **109 passed** (100 anteriores + 9 novos) |
| Frontend `vitest` / `node --test` | **12 passed** / **9 passed** |
| Playwright e2e | **9 passed** (novo: quantitativos → prévia → edição → aceite → Gantt com "provisória") |
| Fumaça do .exe empacotado (IFC real de 2,2 MB e de 32 MB) | **11/11**, incluindo quantitativos, geração e Gantt |
| Visualizador 3D nos 11 IFCs reais | 10/11. O modelo B não tem geometria, como já registrado na parte 1. |

## 8. Validação com os 11 IFCs reais (serviço empacotado)

| Modelo | Quantitativos | Elementos com geometria | Níveis (modo) | Atividades criadas | Precedências | Vínculos | CPM |
|---|---|---|---|---|---|---|---|
| A (CYPE) | 2,1 s | 146/146 | 2 (faixas) | 2 | 1 | 146 | 10 d |
| B (plugin) | 1,1 s | 0/9 | 1 (faixas) | 1 | 0 | 9 | 5 d |
| C+D+E+F (multidisciplinar) | 2,7 + 21,5 + 6,6 + 81,2 s | 15.865/15.875 | 14 (pavimentos) | 63 | 112 | 14.713 | 160 d |
| G (SteelX) | 10,8 s | 2648/2648 | 3 (faixas) | 4 | 3 | 2.648 | 15 d |
| H (Advance Steel) | 8,4 s | 474/649 | 4 (faixas) | 7 | 6 | 649 | 20 d |
| I (Advance Steel) | 13,2 s | 968/1394 | 4 (faixas) | 7 | 6 | 1.390 | 20 d |
| J (Revit) | 20,7 s | 2908/2908 | 6 (pavimentos) | 41 | 51 | 2.499 | 50 d |
| K (TQS) | 3,7 s | 594/594 | 5 (pavimentos) | 14 | 21 | 594 | 65 d |

Todas as durações ficaram provisórias (catálogo sem produtividade). Exemplos de quantidades:
- Eberick: fundações 93,5 m³; pilares 29,0 m³ e vigas 24,9 m³ no nível de fundação.
- AltoQi Builder: 1.085 m de tubulação no térreo. O comprimento veio do Pset do autor, convertido de cm para m.
- Revit (J): alvenaria de ~1.300 m² por pavimento.

Limitações observadas:
- **Projeto com vários modelos em modo "pavimentos":** os nomes de pavimento de cada programa não coincidem
  ("TÉRREO", "Nível 1", "Default Storey"), então surgem 14 níveis intercalados por cota. Para modelos de
  programas diferentes, o modo "faixas de cota" dá uma EAP mais coerente. Está documentado no tutorial.
- **Advance Steel IFC2X3:** ~30% dos elementos (sobretudo fixadores) sem geometria legível. A ligação é medida por
  contagem, sem perda. Os perfis sem geometria ficam sem peso, e a cobertura parcial é sinalizada.
- **Revit:** "Lajes e pisos" inclui pisos de acabamento modelados como `IfcSlab` (11.820 m² no nível 1 do ARQ).
  O usuário pode separar ajustando os tipos e as regras no catálogo.
- O CPM mede as folgas até o prazo contratual do projeto. Com a data final padrão da tela (+365 dias), o
  cronograma gerado pode não ter atividades críticas. A tela explica isso.
