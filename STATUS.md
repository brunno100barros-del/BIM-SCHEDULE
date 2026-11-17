# Status de desenvolvimento — BIM SCHEDULE 0.3.0-dev

Atualizado em 2026-11-17.

## Implementado nesta compilação

- [x] Motor CPM preservando múltiplas relações entre o mesmo par.
- [x] Tratamento de FS, SS, FF e SF.
- [x] Lags positivos e negativos com início de projeto como limite inferior.
- [x] Detecção de ciclos e precedências inválidas.
- [x] Prazo contratual rígido e identificação de folga negativa.
- [x] SQLite com chaves estrangeiras ativadas.
- [x] Migração Alembic inicial e atualização conservadora do esquema anterior.
- [x] CRUD de projetos e duplicação de EAP/atividades/precedências.
- [x] CRUD inicial de EAP.
- [x] Cadastro, edição e exclusão de atividades.
- [x] Cadastro e exclusão de precedências.
- [x] Associação e desassociação Activity-IFC no backend.
- [x] Upload IFC assíncrono básico com status e progresso por lotes.
- [x] Extração inicial de GlobalIds, tipos, nomes, descrição e psets quando disponíveis.
- [x] Painel de projeto.
- [x] Interface de EAP.
- [x] Gantt temporal inicial com conectores de dependência.
- [x] Menu não anuncia módulos pendentes como funcionais.

## Parcial

- [ ] Gantt: sem edição por arrastar, calendário útil e marcos.
- [ ] IFC: sem extração completa de quantitativos, materiais e pavimentos.
- [ ] Viewer: sem sincronização visual bidirecional de seleção de GlobalIds.
- [ ] IFC: progresso por lotes, não progresso detalhado de cada etapa interna do parser.
- [ ] Duplicação de projeto: duplica EAP, atividades e precedências; não duplica arquivos IFC.
- [ ] Visualizador: permanece em web-ifc-three, não That Open Engine.

## Ainda não implementado

- [ ] Recursos, equipes e equipamentos.
- [ ] Cenários PERT probabilísticos.
- [ ] Simulação BIM 4D completa.
- [ ] Orçamento, cronograma físico-financeiro, curva S e fluxo de caixa.
- [ ] Análise climática.
- [ ] Central Gemini com pacote manual estruturado.
- [ ] Auditoria e versionamento completo.
- [ ] Exportação Excel/PDF.
- [ ] Instalação e execução validadas em Windows.

## Bloqueios de validação

- O ambiente não possui IfcOpenShell instalado.
- O registry npm não respondeu por erro de DNS; o build do frontend não pôde ser executado.
- Não há ambiente Windows disponível para executar os arquivos BAT.
