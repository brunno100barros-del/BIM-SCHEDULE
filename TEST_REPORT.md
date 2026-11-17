# Relatório de testes — BIM SCHEDULE 0.3.0-dev

Data: 2026-11-17.

## Testes executados

| Verificação | Resultado |
|---|---|
| Testes unitários CPM/PERT | 13 cenários aprovados |
| Testes API de projetos, EAP, atividades e precedências | 6 cenários aprovados |
| Teste de configuração de chaves estrangeiras SQLite | 1 aprovado |
| Total da suíte pytest | 20 aprovados |
| `python -m compileall` no backend | Aprovado |
| `alembic upgrade head` em banco SQLite limpo | Aprovado |
| Migração simulada de esquema legado, preservando registros | Aprovado |
| Transpilação sintática TypeScript/TSX | 13 arquivos, zero diagnósticos de sintaxe |
| `npm install` | Não concluído: registry npm inacessível por DNS até o limite de tempo |
| `npm run build` | Não executado; dependências não foram instaladas |
| Teste IFC ponta a ponta | Não executado; IfcOpenShell ausente no ambiente |
| Scripts BAT em Windows | Não executados neste ambiente |

## Cenários CPM cobertos

- FS, SS, FF e SF.
- Lag positivo e negativo.
- Múltiplas relações entre o mesmo par de atividades.
- Prazo contratual impossível e folga negativa.
- Ciclos.
- Identificadores e tipos de relação inválidos.
- Exemplo de controle A (3 dias) → B (4 dias), FS + 1: ES(B)=4 e EF(B)=8.

## Observações

A transpilação sintática de TypeScript não substitui o `tsc` completo nem o build Vite. A execução dos testes backend não comprova o funcionamento do frontend no navegador. A migração em banco limpo e em um esquema legado sintético foi validada. Antes de atualizar uma instalação real em uso, ainda é necessário testar com uma cópia do banco de dados dessa instalação.
