# BIM SCHEDULE — versão 0.3.0-dev

Aplicação web independente do ecossistema BIMOFFICE para planejamento de obras e integração inicial com modelos IFC.

> **Estado desta entrega:** versão de desenvolvimento. O núcleo de projetos, EAP, atividades, precedências, cálculo CPM/PERT, gráfico Gantt inicial e importação IFC assíncrona estão em implementação. Não é uma versão 1.0 de produção. Recursos, PERT probabilístico, simulação BIM 4D completa, financeiro, clima, Central Gemini e auditoria/versionamento ainda não estão concluídos.

## Requisitos

- Windows 10/11 (64 bits)
- Python 3.11 ou 3.12 recomendado
- Node.js LTS e npm
- Acesso à internet durante a instalação das dependências

IfcOpenShell depende da disponibilidade de uma distribuição compatível com a versão do Python instalada. Se a instalação dessa dependência falhar, utilize Python 3.11/3.12 e execute novamente `install.bat`.

## Instalação

1. Extraia a pasta do projeto em um diretório com permissão de escrita.
2. Execute `install.bat`.
3. O instalador cria `.venv`, instala dependências, executa as migrações Alembic e valida o build do frontend.
4. Execute `start.bat`.
5. Acesse `http://127.0.0.1:3000`.

## Serviços

- Frontend: `http://127.0.0.1:3000`
- Backend: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

## Banco de dados

O padrão é SQLite em `backend/bim_schedule.db`. Copie `backend/.env.example` para `backend/.env` e ajuste `DATABASE_URL` se necessário. As migrações ficam em `backend/migrations` e são aplicadas com:

```bash
cd backend
python -m alembic upgrade head
```

## Funcionalidades presentes nesta compilação

- Cadastro, edição, exclusão e duplicação básica de projetos.
- Cadastro e edição de atividades.
- Estrutura hierárquica inicial da EAP.
- Relações FS, SS, FF e SF, incluindo lags positivos e negativos.
- Motor CPM com preservação de múltiplas relações entre o mesmo par de atividades, detecção de ciclos e identificação de prazo inviável.
- Gráfico Gantt inicial em escala relativa de dias.
- Upload IFC em tarefa de background, status e progresso de leitura persistidos, extração inicial de GlobalIds, tipos, nomes, conjuntos de propriedades, quantitativos, materiais e pavimento quando disponíveis.
- Associação persistente entre atividade e elemento IFC.

## Limitações conhecidas

- O processamento IFC ocorre em tarefa de background do próprio processo FastAPI; ainda não existe fila distribuída, retomada após queda do processo ou cancelamento de tarefa.
- O progresso IFC é atualizado por lotes e representa avanço da leitura dos produtos, não o progresso interno de cada operação do IfcOpenShell.
- O visualizador usa `web-ifc-three`; That Open Engine ainda não foi migrado.
- A visualização Gantt é temporal e funcional em escala relativa, mas ainda não possui edição por arrastar, conectores de dependências nem calendário de dias úteis.
- A associação GlobalId pode ser cadastrada na tela IFC e consultada pela API; ainda falta a seleção bidirecional sincronizada entre visualizador, atividade e cronograma.
- Os módulos de recursos, cenários PERT, BIM 4D completo, financeiro, clima, Central Gemini e auditoria/versionamento estão desabilitados no menu até sua implementação.
- O build do frontend e a instalação limpa no Windows precisam ser validados em máquina com acesso ao npm registry e às dependências necessárias.

## Testes

Backend:

```bash
cd backend
set PYTHONPATH=.
pytest -q
```

Migrações:

```bash
cd backend
python -m alembic upgrade head
```

Frontend:

```bash
cd frontend
npm install
npm run build
```

Consulte `STATUS.md`, `AUDIT.md`, `IMPLEMENTATION_PLAN.md` e `TEST_REPORT.md` para o estado técnico desta compilação.
