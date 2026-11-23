# BIM SCHEDULE — Tutorial do aplicativo desktop (Windows)

Versão 0.7.0 (Etapa 4: app desktop + cronograma automático a partir do IFC). O aplicativo abre como um programa normal do Windows: **não precisa de terminal,
navegador nem `start.bat`**. O serviço local (Python/IfcOpenShell) é iniciado e encerrado pelo próprio app.

---

## 1. Abrir o programa

**Jeito mais rápido:** clique duas vezes no atalho **BIM SCHEDULE** na Área de Trabalho.

Se o atalho não existir, abra diretamente:
```
Documentos\GitHub\BIM-SCHEDULE\desktop\dist\win-unpacked\BIM SCHEDULE.exe
```

O que acontece:
1. Aparece a tela azul-escura "Iniciando o serviço local…" (2 a 5 segundos).
2. Abre a tela **Gerenciamento de Projetos**.
3. No rodapé da barra lateral aparece `v0.6.0-dev · Aplicativo desktop`. Isso confirma que você está no app
   desktop conectado ao serviço.

> Na primeira execução, o Windows SmartScreen ou o antivírus pode avisar que o programa não é assinado.
> Clique em **Mais informações → Executar assim mesmo**. O executável foi gerado no seu próprio PC.

Só pode haver **uma janela** do app aberta. Clicar no atalho de novo traz a janela existente para a frente.

---

## 2. Onde ficam os seus dados

| O quê | Onde |
|---|---|
| Banco de dados (projetos, atividades, elementos IFC) | `%LOCALAPPDATA%\BIM-SCHEDULE\bim_schedule.db` |
| Arquivos IFC importados (cópias) | `%LOCALAPPDATA%\BIM-SCHEDULE\uploads\` |
| Backups automáticos antes de migrações | `%LOCALAPPDATA%\BIM-SCHEDULE\backups\` |
| Logs | `%LOCALAPPDATA%\BIM-SCHEDULE\logs\` (`desktop-service.log` é o do app) |

Atalhos no menu: **Arquivo → Abrir pasta de dados** e **Arquivo → Abrir pasta de logs**.
O app desktop e a versão web (`start.bat`) usam **a mesma pasta de dados**, então os projetos aparecem nos dois.
**Não abra os dois ao mesmo tempo.**

---

## 3. Roteiro de teste (15 minutos)

### 3.1 Projetos de teste já criados
Já existem 8 projetos com código `TST-…`, criados nos testes com os seus IFCs:
`TST-ESAP` (multidisciplinar: ARQ, EST, HID e estrutura metálica), `TST-SENAC`, `TST-XIMENES`, `TST-LEONE`,
`TST-MODEL-RJ`, `TST-ESTMET-RJ`, `TST-VOLUM` e `TST-PORTAL`. Todos já têm **quantitativos calculados** e um
**cronograma gerado** (veja o Gantt). Comece pelo `TST-SENAC` (Revit, 6 pavimentos) ou pelo `TST-ESAP`.
Você pode abri-los direto, gerar de novo ou apagá-los.

### 3.2 Criar um projeto
1. Na tela **Projetos**, clique em **Novo Projeto**.
2. Preencha **Nome do Projeto** e **Código** (único). Os demais campos são opcionais.
3. Clique em **Salvar Projeto**. Aparece "Projeto XXX criado e salvo." e o cartão do projeto.
4. Clique em **Abrir Projeto**.

### 3.3 Importar um IFC
1. No menu lateral, abra **Modelos IFC & 3D**.
2. Clique em **Importar IFC** e escolha um ou mais arquivos `.ifc`.
3. O cartão **Processamento IFC** mostra o progresso. O processamento roda em segundo plano, e você pode
   continuar usando o app. Tempos medidos: de 1 a 4 s para arquivos até 32 MB e ~12 s para 139 MB.
4. Ao concluir: "Processamento IFC concluído." e a lista **Elementos (N)**.
5. Para **cancelar** um processamento longo, use **Cancelar** no cartão do modelo.

### 3.4 Visualizador 3D
1. Clique no cartão de um modelo concluído. O visualizador mostra "Carregando geometria IFC…".
2. **Mouse:** botão esquerdo gira, botão direito desloca e a roda aproxima.
3. Se o arquivo não tiver geometria 3D, aparece a mensagem "Este arquivo IFC não contém geometria 3D
   visualizável". Os elementos e as propriedades continuam importados.

### 3.5 Gerar o cronograma automaticamente a partir do IFC (novo)
No menu lateral, abra **Gerar Cronograma**. São três passos na mesma tela:

1. **Modelos e quantitativos.** Marque os modelos (os vigentes já vêm marcados) e clique em
   **Calcular quantitativos dos selecionados**. O cálculo roda em segundo plano, com progresso por modelo.
   Tempos medidos com os seus arquivos: de 2 a 21 s na maioria; ~80 s no ARQ de 139 MB. A seta ao lado do nome
   mostra os totais por tipo IFC (quantidade, m³, m², m, kg) e a **fonte** de cada medida:
   - `ifc_qto`: quantitativos do próprio IFC (Qto_*/BaseQuantities). Nenhum dos seus arquivos tem.
   - `author_pset`: propriedade do programa de autoria com unidade definida (ex.: comprimento de tubos do AltoQi).
   - `geometry`: calculada pela geometria do elemento.
   - `count`: 1 por elemento.

   Todas as quantidades ficam em **m, m², m³ e kg**, convertidas da unidade do arquivo (cm e mm inclusive).
2. **Serviços, regras e produtividades** (clique para abrir). Esta tabela diz qual tipo IFC vira qual serviço,
   a unidade, a **produtividade por dia**, a duração padrão e os predecessores. As produtividades começam
   **vazias**: o programa não inventa índices. Preencha as que você tem (ex.: alvenaria em m²/dia). A alteração
   é salva ao sair do campo. **Restaurar padrão** volta ao catálogo inicial.
3. **Pré-visualizar e revisar.** Escolha os **níveis**:
   - *Automático*: usa os pavimentos do IFC; quando o modelo tem um só pavimento (Advance Steel, SteelX, CYPE),
     usa faixas de cota.
   - *Pavimentos do IFC*.
   - *Faixas de cota*, com a altura da faixa em metros.

   Clique em **Pré-visualizar cronograma**. A tabela mostra, por nível, cada atividade com quantidade, cobertura
   (% dos elementos com medida), produtividade, duração e situação. A situação é **calculada** (quantidade ÷
   produtividade) ou **provisória**, com o motivo: sem produtividade, sem quantidade ou quantidade parcial.
   Você pode desmarcar atividades, renomear e mudar durações. Uma duração digitada deixa de ser provisória.
   "Outros elementos (a classificar)" vem desmarcado.
4. Clique em **Aceitar e criar cronograma**. O app cria a EAP (geração → níveis), as atividades (código `G1-…`),
   as precedências padrão e os vínculos de cada atividade com os seus elementos IFC, e calcula o CPM.
   Com **Substituir o cronograma gerado anteriormente** marcado, a geração anterior é removida. Atividades criadas
   à mão nunca são tocadas.
5. Clique em **Abrir Gráfico de Gantt**. As atividades com duração provisória aparecem com a etiqueta
   **provisória**. Ao editar a duração no Gantt, a etiqueta some.

> **Prazo contratual.** Um projeto criado pela tela recebe, por padrão, data final = início + 365 dias. O CPM
> mede as folgas até esse prazo, então um cronograma bem mais curto pode aparecer **sem atividades críticas**.
> Para ver o caminho crítico do próprio cronograma, apague ou ajuste a data final do projeto.

### 3.6 EAP e atividades
1. **EAP & Atividades**: monte a estrutura analítica e as atividades.
2. Para vincular um elemento IFC a uma atividade: em **Modelos IFC & 3D**, selecione o elemento na lista,
   escolha a atividade em "Associar elemento selecionado à atividade" e clique em **Vincular GlobalId**.

### 3.7 Cronograma manual (CPM)
1. **Gráfico de Gantt & CPM** → **Nova atividade**: código (ex.: `A-01`), nome e duração em dias → **Adicionar atividade**.
2. **Nova precedência**: escolha a predecessora e a sucessora → **Adicionar relação**.
3. Clique em **Calcular CPM**. O motor do serviço calcula datas, folgas e caminho crítico
   (exemplo: A-01 com 3 dias → A-02 com 4 dias = "Duração calculada: 7 dias").

---

## 4. Menus do aplicativo

| Menu | Item | Para quê |
|---|---|---|
| Arquivo | Recarregar (F5) | Recarrega a interface (não reinicia o serviço). |
| Arquivo | Abrir pasta de dados / de logs | Abre a pasta no Explorer. |
| Exibir | Zoom, tela cheia, ferramentas do desenvolvedor (Ctrl+Shift+I) | Ajustes e diagnóstico. |
| Ajuda | Tutorial de uso | Abre este arquivo. |
| Ajuda | Documentação da API (Swagger) | Abre a API local no navegador (útil para testes avançados). |
| Ajuda | Sobre | Versão, pasta de dados e endereço do serviço. |

---

## 5. Problemas comuns

| Sintoma | O que fazer |
|---|---|
| "Falha ao iniciar" ao abrir | Leia `%LOCALAPPDATA%\BIM-SCHEDULE\logs\desktop-service.log`. Confira se outra janela do app ou o `start.bat` não está aberto. |
| "O serviço local foi encerrado inesperadamente" | Clique em **Reiniciar serviço**. Se repetir, envie o log acima. |
| IFC fica em "Aguardando processamento" | Só um IFC é processado por vez. Aguarde a fila. |
| A lista mostra "1000 de N" elementos | Use **Carregar mais 1000** no fim da lista ou o campo de filtro (nome, tipo ou GlobalId). |
| Muitas atividades "provisórias" | Normal enquanto não houver produtividade cadastrada: preencha em **Gerar Cronograma → 2. Serviços**. |
| Quantidade "0" ou cobertura baixa | O elemento não tem geometria legível nem Pset com unidade. A duração fica provisória. Confira a exportação do IFC. |
| Antivírus bloqueia `bim-schedule-service.exe` | Libere a pasta `desktop\dist\win-unpacked` (executável não assinado). |

---

## 6. Para quem desenvolve

| Tarefa | Comando (na raiz do repositório) |
|---|---|
| Instalar o ambiente | `install.bat` |
| Versão web (navegador) | `start.bat` → http://127.0.0.1:3000 |
| **Gerar o app desktop** (frontend + serviço PyInstaller + Electron + atalho) | `build-desktop.bat` |
| Rodar o desktop sem empacotar (usa a `.venv`) | `cd desktop` → `npm start` (exige `frontend\dist`, gerado por `npm run build`) |
| Teste de fumaça do .exe empacotado (pasta de dados temporária) | `cd desktop` → `node scripts\smoke-test.cjs [arquivo.ifc]` |
| Conferir o 3D de todos os projetos `TST-` | `cd desktop` → `node scripts\viewer-check.cjs` |
| Validar quantitativos + gerador nos projetos `TST-` | `.venv\Scripts\python.exe desktop\scripts\generator_validation.py --out resultado.json --apply` |
| Medir importação de IFCs (tempo e memória) | `.venv\Scripts\python.exe desktop\scripts\ifc_benchmark.py --plan plano.json --out resultado.json` |

Arquitetura: `docs/architecture/WINDOWS_DESKTOP.md`. Relatório da etapa: `docs/reports/ETAPA-04-DESKTOP.md`.
