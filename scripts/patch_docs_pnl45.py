# -*- coding: utf-8 -*-
"""Documenta a PNL_1.4 (Financeiro) e a PNL_1.5 (Contratual). Idempotente.

🚨 Guard por LINHA NOVA, nunca pela ancora -- a licao dos dois patches de hoje
que disseram "ja aplicado" e nao escreveram nada. E confere com grep no fim.
"""
import pathlib
import sys

DOCS = pathlib.Path("/home/claude/movizap_painel/docs")

def anexar(arquivo, texto):
    p = DOCS / arquivo
    t = p.read_text(encoding="utf-8")
    primeira = texto.strip().splitlines()[0]
    if primeira in t:
        print(f"  {arquivo}: ja aplicado")
        return
    p.write_text(t.rstrip("\n") + "\n\n" + texto, encoding="utf-8")
    print(f"  {arquivo}: ok")


anexar("03_Registro_Telas.md", """\
## 06/11 — `PNL_1.4` Financeiro e `PNL_1.5` Contratual: os quatro painéis existem

🔵 **Pedidos dele, na ordem:** *"do 1"* + a lista de dez colunas, e *"conclua e
exiba o financeiro no paniel para owner"*; depois *"Depois gere a mesmta tela do
'Financeiro' para o 'Contratual'"* + a lista, e *"as regras de criação de cards
em 'financeiro', 'pós-venda' e 'Contratual' ainda ficam em branco mesmo. Mas
eleas ja devem aparecer no menu para owner"*.

| painel | código | rota | colunas | migração |
|---|---|---|---|---|
| Financeiro | `PNL_1.4` | `/paineis/financeiro` | **10** | 096 |
| Contratual | `PNL_1.5` | `/paineis/contratual` | **6** | 097 |

**O vocabulário de `paineis.PAINEIS` declarava quatro desde 22/10, e agora os
quatro têm tela.** ⚠️ `COM_TELA` continua sendo só `("operacao",)`, e é certo:
ele governa o `quadro()`, que fala com o Harmonit. Os três novos passam pelo
`quadro_da_aba`, que não fala com ninguém de fora.

🚨 **UMA ENTRADA POR PAINEL, E NENHUMA COM `aba_de`.** Cada um é um item de menu
próprio. O Pós-venda continua sendo **um** item com duas abas dentro (correção
dele de 05/11) — é o único com `aba_de`.

🚨 **CÓDIGOS:** o comentário da `PNL_1.1` reservava `1.2`, `1.3` e `1.4` para os
outros três painéis desde 22/10. O Pós-venda gastou **duas** (`1.2` e `1.3`,
porque são duas abas), então o Financeiro ficou com `1.4` e o Contratual com
`1.5`. Os dois conferidos contra `CODIGOS_APOSENTADOS` antes de escrever.

🚨 **OS DOIS APARECERAM NA ABA `CFG_15.1` SEM UMA LINHA DE CÓDIGO.** A aba de
permissão nasceu de manhã com três painéis e **não foi tocada** por estas duas
entregas: a lista de concedíveis sai do grupo "Painéis" do REGISTRO. Era o
desenho, e estas são as duas primeiras provas dele. ⚠️ Há trava em cada um dos
dois arquivos de teste — e a do Financeiro teve de ser **consertada**: a primeira
versão fixava a lista inteira de painéis e ficou vermelha quando o Contratual
entrou, meia hora depois. Teste que existe para provar que *"painel novo entra
sozinho"* não pode ser o que obriga a editar teste quando um painel novo entra.
""")

anexar("06_Conteudo_das_Telas.md", """\
## 06/11 — `PNL_1.4` Financeiro

🔵 **As dez colunas, na ordem dele** (*"do 1"*, e a lista sob o cabeçalho
"Colunas"):

`Nova solicitação` · `Contratos assinados` · `Contrato vinculado no financeiro`
· `Aguardando prazo` · `Aguardando Datascope` · `Em tratativa` · `Aguardando
terceiros` · `INADIMPLENTES` · **`Atendimento feito`** · **`Não atendido`**

🚨 **UMA ABA, E NÃO QUATRO.** O Pós-venda tem duas porque ele escreveu **duas**
listas de colunas. Aqui a lista é **uma**. ⚠️ O que havia antes sobre "abas do
financeiro" era o exemplo de permissão que ele mesmo marcou como *"Apenas
exemplo"*, e a lista do §2.1 do `MoviZap_Formularios_PLANO.md` (`Financeiro ·
Pagamento técnicos · Administrativo · Fornecedores`), que é de **formulários**,
não de etapas. Repartir dez colunas entre quatro abas inventadas seria escopo
meu. Aba nova é uma linha na migração e uma no `telas.py`.

🚨 **"INADIMPLENTES" ENTROU SEM A AUTOMAÇÃO.** Ele escreveu *"INADIMPLENTES
(Automação move para pipeline Cobrança)"* — o parêntese é **comportamento
futuro**, não parte do nome. E não dá para construí-lo hoje: o painel "Cobrança"
**não existe**, nem como tela nem no vocabulário (`painel_aba_painel_conhecido`
aceita só `operacao`, `pos_venda`, `contratual`, `financeiro`). Automação que
move card para pipeline inexistente não é automação, é perda de card. 🔴 Fica
como decisão dele. ⚠️ Há trava provando que **não há `Cobrança` em painel
nenhum**, para o dia em que alguém "lembrar" de ligar isso.

🚨 **DOIS FINS, e não um.** "Atendimento feito" e "Não atendido" são os dois;
marcar só a última diria que chegar em "Atendimento feito" não é terminar.
⚠️ `final` segue sendo só o fato no banco — nada na tela depende dele ainda.

## 06/11 — `PNL_1.5` Contratual

🔵 **As seis colunas, na ordem dele** (*"gere a mesmta tela do 'Financeiro' para
o 'Contratual' - seguindo o seguindo modelo para colunas"*):

`Elaborar contrato` · `Aguardando pendencias` · `Aguardando assinatura` ·
**`Assinado`** · **`Não assinado`** · **`Desistiu de cancelar`**

🚨 **DUAS LINHAS DA LISTA DELE NÃO ENTRARAM, E ISSO É LEITURA MINHA.** A lista
colada começava com *"Regras de automação e gatilhos"* e *"pesquisar"*. Li as
duas como a **moldura da tela de onde ele copiou** — o link de automação do CRM e
a caixa de busca —, por três razões: na lista do Financeiro, meia hora antes, a
linha equivalente era o cabeçalho literal **"Colunas"**; *"pesquisar"* vem em
minúscula no meio de títulos capitalizados; e as seis restantes formam um fluxo
fechado de contrato. 🔴 **Se eu errei, o conserto é uma linha da migração 097** —
e está nos Próximos Passos como **pergunta aberta**, não como fato. Há trava
provando que nenhuma coluna se chama "pesquisar" nem contém "gatilho", e é ela
que fica vermelha quando alguém corrigir a leitura.

🚨 **TRÊS FINS:** Assinado, Não assinado e Desistiu de cancelar.

⚠️ **A GRAFIA É A DELE:** "pendencias" sem acento, e "Desistiu de cancelar"
inteiro. Corrigir ortografia de rótulo ditado é renomear a coluna dele sem pedir
— e o rótulo é o que o operador procura com os olhos. Há trava para isso.

🔴 **OS TRÊS NASCEM VAZIOS, e é decisão dele:** *"as regras de criação de cards em
'financeiro', 'pós-venda' e 'Contratual' ainda ficam em branco mesmo"*. A
`PainelAba` escreve **"Nenhum card nesta aba ainda."** — quadro vazio que não diz
por que está vazio é `M12`.
""")

anexar("02_Modelo_Dados.md", """\
## Os quatro painéis em `painel_aba` (migrações 092 · 094 · 096 · 097)

| painel | `codigo_tela` | título da aba | etapas | migração |
|---|---|---|---|---|
| `operacao` | `PNL_1.1` | Operação | **1** (`Chamados`) | 092 |
| `pos_venda` | `PNL_1.2` | Treinamentos | 4 | 094 |
| `pos_venda` | `PNL_1.3` | Pós-venda | 4 | 094 |
| `financeiro` | `PNL_1.4` | Financeiro | **10** | 096 |
| `contratual` | `PNL_1.5` | Contratual | **6** | 097 |

🚨 **`painel_aba.painel` TEM VOCABULÁRIO FECHADO** (`painel_aba_painel_conhecido`):
`operacao`, `pos_venda`, `contratual`, `financeiro`. Painel novo — "Cobrança", por
exemplo, que a anotação dele sobre INADIMPLENTES menciona — precisa de migração
que **amplie o CHECK** antes de qualquer aba. É a armadilha que a casa já
catalogou em `contato.relacao`: código recusando valor que o banco aceita, ou o
contrário.

⚠️ **A `PNL_1.1` tem UMA etapa só**, e não dezessete: as 17 colunas da Operação
são **situações da OS do Harmonit**, calculadas em `paineis.quadro()`. A única
etapa nossa dela é a `Chamados`. As dos outros três são **todas** nossas, e
vivem aqui.

⚠️ **Etapa é única DENTRO da aba, não no sistema:** "Solicitação" aparece nas
duas abas do Pós-venda, e "Assinado" (contratual) e "Contratos assinados"
(financeiro) são colunas diferentes de painéis diferentes.

**Cards hoje: 1 no total** (um chamado na `Chamados` da Operação). Os quatro
painéis novos estão **vazios por decisão dele** — a origem dos cards segue em
aberto (*"as regras de criação de cards (...) ainda ficam em branco mesmo"*).
""")

print("\nconferindo com grep:")
t3 = (DOCS / "03_Registro_Telas.md").read_text(encoding="utf-8")
t6 = (DOCS / "06_Conteudo_das_Telas.md").read_text(encoding="utf-8")
t2 = (DOCS / "02_Modelo_Dados.md").read_text(encoding="utf-8")
for codigo in ("PNL_1.4", "PNL_1.5"):
    print(f"  {codigo}: docs/03={t3.count(codigo)} docs/06={t6.count(codigo)} "
          f"docs/02={t2.count(codigo)}")
for icone in ("bi-cash-coin", "bi-file-earmark-text"):
    print(f"  {icone}: docs/03={t3.count(icone)}")
