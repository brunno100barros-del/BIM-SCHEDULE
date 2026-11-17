# Relatório de testes — BIM SCHEDULE 0.5.0-dev

## Testes adicionados nesta alteração

O comando `npm run test:schedule` executa testes Node nativos sobre as funções CPM efetivamente usadas pela interface e verifica os vínculos entre os módulos e a página demonstrativa.

**9 testes automatizados** cobrem os seguintes casos:
- Sequência FS e caminho crítico.
- PV/EV/AC/SPI/CPI/EAC com data de status e encerramento do cronograma.
- Atividades paralelas e folga total.
- Relações SS, FF e SF.
- Relações múltiplas entre o mesmo par de atividades.
- Lag negativo.
- Rejeição de ciclos, predecessoras inexistentes e durações inválidas.
- Smoke check da página IFC, navegação de Clima/IA, data de status financeiro e vínculos de renderização.

## CI

O workflow `.github/workflows/validate-demo.yml` foi ampliado para:
1. Extrair e verificar a sintaxe do JavaScript inline.
2. Verificar a sintaxe de `schedule-enhancements.js`.
3. Instalar dependências do frontend.
4. Executar `npm run test:schedule`.
5. Executar `npm run build`.

**Status dos resultados:** aguardando execução do GitHub Actions para esta branch. Não considerar os testes aprovados até o workflow terminar em verde.

## Testes ainda pendentes

- Importar e abrir IFC2x3, IFC4 e IFC4x3 reais no navegador.
- Validar visualização 3D e simulação 4D em Chrome/Edge com WebGL.
- Testar modelo de grande porte e medir consumo de memória.
- Testar persistência IndexedDB após fechar/reabrir o navegador e alternar projetos.
- Testar clima em rede real.
- Testar Windows e instalação limpa do backend.
- Validar cálculos CPM, PERT e financeiro com casos de obra independentes.

## Observação

Testes sintáticos e testes de funções não comprovam a compatibilidade geométrica com todos os arquivos IFC. O viewer continua experimental até a validação ponta a ponta.
