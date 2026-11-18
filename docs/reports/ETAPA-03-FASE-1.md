# Etapa 3 — Fase 1: modelos e revisões IFC, remoção segura e recuperação pendente

| Item | Valor |
|---|---|
| Data | 2026-11-18 |
| Base | `main` em `8a630a4` (Etapa 2 mesclada) |
| Backup | branch `backup/etapa-03-pre-nucleo-bim-2026-11-17` → `8a630a4` |
| Branch | `etapa-03/nucleo-bim` |
| Status | Aguardando revisão. A Fase 2 não foi iniciada. |

## 1. Implementação

### 1.1 Modelos lógicos e revisões
- **`bim_models`** (nova tabela): modelo lógico do projeto, por exemplo "Estrutura Torre A", com nome, disciplina indicada e descrição.
- **`ifc_models`** passa a representar cada **revisão** de um modelo lógico. Campos novos:
  - `bim_model_id`, `revision_number` (1, 2, 3...), `is_current`;
  - `file_size`, `sha256`, `ifc_project_global_id`;
  - `header_json`, com software de autoria, data, autor e organização do cabeçalho STEP;
  - `deleted_at`.
- **Upload:**
  - Sem `bim_model_id`, cria um modelo lógico novo (nome informado ou nome do arquivo). Com `bim_model_id`, registra uma nova revisão daquele modelo.
  - A revisão nova **só passa a vigente quando o processamento termina com sucesso**. Uma revisão que falha não substitui a vigente.
  - O mesmo arquivo (mesmo SHA-256) no mesmo modelo é recusado (409). Em outro modelo do projeto é aceito, com aviso.
- **Sugestão de revisão:** `GET /ifc/model/{id}/revision-candidates` aponta modelos do projeto com o mesmo GlobalId de `IfcProject` (evidência forte) ou o mesmo nome de arquivo (evidência fraca). É só sugestão.
- **Reagrupamento:** `POST /ifc/model/{id}/move-to-bim-model` torna a revisão uma nova revisão de outro modelo. Serve para corrigir importações e para organizar os modelos legados, que a migração separa um por arquivo.
- **Disciplina indicada:** lista fixa nesta fase. Vira tabela configurável na Fase 4.
- **Identidade dos elementos:** continua `(revisão, GlobalId)` com id interno próprio. O teste com GlobalIds idênticos em dois arquivos confirma que elementos e vínculos não se misturam.

### 1.2 Remoção segura
- `DELETE /ifc/model/{id}` remove uma revisão. `DELETE /ifc/bim-models/{id}` remove o modelo lógico e todas as revisões dele.
- **Com vínculos a atividades:** a API devolve 409 informando a quantidade e só prossegue com `confirm_links=true`.
- **Revisão em processamento:** a remoção é recusada.
- **Andamento:**
  - A revisão some das consultas na hora (`deleting`), e a vigente volta para a última revisão concluída.
  - Uma tarefa em segundo plano remove os vínculos e elementos em lotes de 5 000, depois o arquivo, e marca a revisão como `deleted`. O registro fica mantido para auditoria.
- **Interrupção:** se for cancelada ou falhar, a revisão continua oculta, e uma nova solicitação retoma a remoção do ponto em que parou.
- **Arquivo:** só é apagado se estiver dentro da pasta de uploads e não for usado por nenhuma outra revisão.
- **Proteções adicionais:**
  - Não é possível vincular atividades a elementos de revisão removida.
  - **Exclusão de projeto:** recusada enquanto houver tarefa ativa. Agora remove os arquivos IFC do projeto; antes eles ficavam esquecidos no disco. Arquivos de outros projetos ou fora da pasta de uploads não são tocados.

### 1.3 Recuperação pendente nas tarefas
- Novos campos em `jobs`: `recovery_pending`, `recovery_error`, `recovery_attempts` e `recovery_updated_at`.
- **Quando é marcada:** sempre que a rotina de consistência falha. O diagnóstico aparece na tarefa e em `GET /jobs?recovery_pending=true`.
- **Nova tentativa:**
  - automática em cada inicialização do serviço;
  - manual por `POST /jobs/{id}/retry-recovery`.
- **Resultado:** cada tentativa incrementa o contador. Ao dar certo, a marca é retirada.

### 1.4 Migração 0003
- **Somente aditiva:** usa `ALTER TABLE ... ADD COLUMN` e nunca recria tabelas.
- **Por quê:** um teste executado nesta fase mostrou que recriar a tabela pai com `foreign_keys=ON` apaga em cascata todas as linhas filhas.
- **Dados existentes:** cada arquivo IFC vira a revisão 1 de um modelo lógico próprio, com o tamanho do arquivo preenchido. O SHA-256 dos arquivos antigos fica vazio até um reprocessamento.
- **Backup:** o banco é copiado automaticamente antes da migração (Etapa 2).

### 1.5 Defeito da Etapa 2 encontrado e corrigido
`migrations/env.py` executava `PRAGMA foreign_keys=ON` antes de `context.begin_transaction()`. No SQLAlchemy 2 isso abre uma transação implícita, e o Alembic deixa de confirmá-la. **Tudo o que uma migração gravava era desfeito**, inclusive o registro em `alembic_version`.

- **Efeito na `main`:** a cada inicialização o serviço migrava de novo e criava um **novo backup**. Também não havia como aplicar migrações de dados, como o preenchimento da 0003.
- **Correção:** remover o comando. As migrações passam a rodar sem `foreign_keys`, como o Alembic recomenda para SQLite.
- **Por que os testes da Etapa 2 não pegaram:** eles iniciavam o serviço só uma vez por banco, e a migração 0001 cria as tabelas a partir dos modelos atuais.
- **Agora:** os testes de migração partem do **esquema real** da `main` (`tests/fixtures_schema_main_8a630a4.sql`, gerado executando o código daquele commit). Eles cobrem `alembic_version` vazio (instalações da Etapa 2) e marcado `0001` (instalações anteriores).

## 2. Arquivos

**Criados**
- `backend/app/modules/ifc/revisions.py`
- `backend/migrations/versions/0003_bim_models.py`
- `backend/tests/test_bim_models.py`
- `backend/tests/test_migration_0003.py`
- `backend/tests/fixtures_schema_main_8a630a4.sql`
- este relatório

**Modificados**

| Arquivo | Mudança |
|---|---|
| `backend/app/models/ifc.py` | `BimModel` e campos das revisões |
| `backend/app/models/job.py` | Campos de recuperação |
| `backend/app/models/__init__.py` | Registro de `BimModel` |
| `backend/app/jobs/manager.py` | Recuperação pendente e nova tentativa |
| `backend/app/jobs/router.py` | `retry-recovery`; filtro `recovery_pending` |
| `backend/app/jobs/registry.py` | Tipo `ifc.delete_revision` |
| `backend/app/jobs/diagnostic.py` | Falha temporária controlada para testes |
| `backend/app/modules/ifc/router.py` | Upload com modelo/revisão; rotas de modelos, candidatos, reagrupamento e remoção |
| `backend/app/modules/ifc/jobs.py` | Revisão vigente após sucesso; tarefa de remoção |
| `backend/app/modules/ifc/parser.py` | GlobalId do `IfcProject` e cabeçalho |
| `backend/app/modules/planning/router.py` | Recusa vínculo com revisão removida |
| `backend/app/modules/projects/router.py`, `service.py` | Exclusão de projeto com arquivos e verificação de tarefas |
| `backend/migrations/env.py` | Correção do defeito acima |
| `backend/tests/test_jobs_consistency.py` | Testes de recuperação pendente |
| `backend/tests/test_storage_migration.py` | Revisão mais recente lida do Alembic, sem valor fixo |

Frontend, motor CPM/PERT e IA: **sem alteração**.

## 3. Testes

| Conjunto | Resultado local |
|---|---|
| Backend (pytest) | **100/100** (eram 79) |
| Vitest | 12/12 |
| Motor da demonstração | 9/9 |
| Build de produção | OK |
| Playwright (serviço real + interface) | 8/8 |
| CI (Ubuntu, Windows, frontend) | Ver seção 5 |

Testes novos (21):
- **Modelos e revisões (7):** metadados, vigência só após sucesso, duplicata, entradas inválidas, GlobalIds repetidos entre arquivos, candidatos e reagrupamento, edição.
- **Remoção (7):** preserva outras revisões, arquivos, vínculos e projetos; remove o modelo lógico; recusa em processamento; remoção cancelada fica oculta e é retomada; vínculo com revisão removida recusado; exclusão de projeto remove só os arquivos dele; recusa com tarefa ativa.
- **Migração (4):** esquema real com `alembic_version` vazio e com `0001` (registro por registro iguais, `integrity_check`, `foreign_key_check`, hashes dos arquivos, backup); reinício sem nova migração; banco novo marcado e sem nova migração.
- **Recuperação pendente (3):** marcação e nova tentativa via API; nova tentativa automática na inicialização; operação sem efeito em tarefa sem pendência.
- **Contraprova:** com o `env.py` anterior, os 4 testes de migração falham.

## 4. Limitações
- A interface ainda não mostra modelos lógicos e revisões, nem os botões de remover e reagrupar. A API está pronta; a interface entra na Fase 5, conforme o plano.
- O SHA-256 dos arquivos importados antes da Etapa 3 fica vazio até um reprocessamento (Fase 2).
- A comparação de revisões continua só por GlobalId. A comparação sem depender exclusivamente do GlobalId, com as categorias novo, removido, mantido, modificado e sem correspondência confiável, está planejada para a Fase 3, quando houver propriedades e quantitativos para comparar.
- Bancos criados do zero recebem as chaves estrangeiras declaradas nos modelos. Bancos migrados recebem `bim_model_id` com `REFERENCES` via `ADD COLUMN`. A integridade dos demais campos novos é garantida pela aplicação.
- Arquivos IFC usados nesta fase são gerados pelo IfcOpenShell. Os arquivos públicos da buildingSMART e do IfcOpenShell, com verificação de licença, entram na Fase 2, junto com a extração.

## 5. CI
Aguardando a execução do commit desta fase.
