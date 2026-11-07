# -*- coding: utf-8 -*-
"""Documenta a CFG_15.1 e a tabela `tela_concedida` (06/11). Idempotente.

Os tres lugares que a suite cobra: docs/03 (registro + icone + a entrega),
docs/06 (conteudo da tela) e docs/02 (modelo de dados).
"""
import pathlib
import sys

DOCS = pathlib.Path("/home/claude/movizap_painel/docs")


def trocar(caminho, antiga, nova, rotulo):
    p = DOCS / caminho
    t = p.read_text(encoding="utf-8")
    if nova.strip().splitlines()[0] in t:
        print(f"  {rotulo}: ja aplicado")
        return
    if t.count(antiga) != 1:
        sys.exit(f"{rotulo}: ancora apareceu {t.count(antiga)}x")
    p.write_text(t.replace(antiga, nova), encoding="utf-8")
    print(f"  {rotulo}: ok")


def anexar(caminho, texto, rotulo):
    p = DOCS / caminho
    t = p.read_text(encoding="utf-8")
    if texto.strip().splitlines()[0] in t:
        print(f"  {rotulo}: ja aplicado")
        return
    p.write_text(t.rstrip("\n") + "\n\n" + texto, encoding="utf-8")
    print(f"  {rotulo}: ok")


# ---------------------------------------------------------------------------
# docs/03 — a linha da tabela do registro
# ---------------------------------------------------------------------------
trocar(
    "03_Registro_Telas.md",
    "| `CFG_14.1` | Vínculo dos técnicos | `/config/vinculo-tecnicos` | `owner` | 1 |\n",
    "| `CFG_14.1` | Vínculo dos técnicos | `/config/vinculo-tecnicos` | `owner` | 1 |\n"
    "| `CFG_15.1` | Permissão dos painéis | `/config/permissao-paineis` | `owner` | 1 |\n",
    "docs/03 tabela",
)

# ---------------------------------------------------------------------------
# docs/03 — a linha do ícone
# ---------------------------------------------------------------------------
trocar(
    "03_Registro_Telas.md",
    "| `CFG_14.1` Vínculo dos técnicos | `bi-person-vcard` | aba |\n",
    "| `CFG_14.1` Vínculo dos técnicos | `bi-person-vcard` | aba |\n"
    "| `CFG_15.1` Permissão dos painéis | `bi-shield-lock` | aba |\n",
    "docs/03 ícone",
)

# ---------------------------------------------------------------------------
# docs/03 — a entrega
# ---------------------------------------------------------------------------
anexar("03_Registro_Telas.md", """\
## 06/11 — `CFG_15.1`, e a PRIMEIRA permissão que não é por perfil

🔵 **Pedido dele:** *"em configuração, crie uma aba de permissão para os
paineis, ali vou definir quem pode ver o que e por aba tbm, como notará que o
pós venda ja possui abas"*.

| o quê | onde |
|---|---|
| a aba | `CFG_15.1`, `aba_de: CFG_0.1`, **só owner**, entre Sincronização e Vínculo |
| a tabela | `tela_concedida` (migração 095) — uma linha por pessoa e tela |
| a regra | `telas.pode_acessar` passa a honrar a concessão **antes** de recusar tela `owner` |
| a identidade | `auth.buscar_usuario` traz `telas_concedidas`, lido **a cada requisição** |
| as rotas | `GET` e `PUT /api/config/permissao-paineis` |

🚨 **ATÉ 06/11 A PERMISSÃO DO MOVIZAP ERA SÓ POR PERFIL**, e perfil não sabe
dizer *"esta pessoa, esta aba"*. `atendente.perfil` dá um conjunto de nomes
(`PERFIS`), cada tela declara **um** desses nomes, e `pode_acessar` recusava
toda tela `owner` a todo não-owner. As três telas de painel são `owner` — então
**não existia caminho de concessão nenhum**. Medido em 06/11: só o Iago (121)
alcançava qualquer painel, e a `atendente_time_permissao` estava **vazia**.

🚨 **A CONCESSÃO VENCE O `permissao: owner` DA TELA.** É a linha mais
importante da entrega; sem ela a aba gravaria sem efeito. ⚠️ **A tela não é
rebaixada:** continua `owner` no registro, e quem não tem linha em
`tela_concedida` continua barrado. O que existe é uma lista de exceções
**nomeadas**, cada uma com quem concedeu e quando. Rebaixar a tela para
`equipe` seria outra coisa inteiramente: abriria o painel para todo admin de
uma vez, sem ninguém marcar nada.

🚨 **SÓ O GRUPO "PAINÉIS" É CONCEDÍVEL, e a trava é no backend.** A lista sai do
REGISTRO (`grupo == "Painéis"`), não de uma lista escrita à mão: painel novo
entra sozinho — é o que o **Financeiro** vai precisar quando as colunas dele
chegarem. ⚠️ E a `CFG_15.1` **não pode conceder a si mesma**: ela é do grupo
"Configuração". Ninguém se concede a própria chave, nem concede `CFG_1.1` (os
canais do WhatsApp) por descuido.

⚠️ **FORA DO TOKEN DE PROPÓSITO.** Com a lista no JWT, revogar um painel só
valeria no próximo login — e o token do MoviZap vale até a virada do dia.
Permissão que demora um dia para sair não é permissão.

⚠️ **O OWNER APARECE NA GRADE, marcado e sem caixa:** tirá-lo faria a grade
parecer incompleta; deixá-lo marcável ofereceria um gesto sem efeito (o
precedente é o `ModalAgendar`).

### 🚨 A PORTA TRANCADA, que deixou de ser hipótese no mesmo dia

Até 06/11 o `MenuLateral` pulava **toda** tela com `aba_de`. Isso bastava porque
toda aba vinha acompanhada da mãe: a casca `/config` é `atendimento`, então quem
tem `CFG_1.1` tem a `CFG_0.1` junto. Com esta aba deixou de ser verdade —
conceder **só** a `PNL_1.3` dava uma pessoa com tela, com rota e com permissão e
**sem nenhum item de menu**, porque o item é da `PNL_1.2`. O 403 nunca
apareceria: a tela simplesmente não existiria para ela.

🔵 Decisão dele: *"4 ok"*. A condição virou **"a mãe chegou?"**: aba com a mãe
presente continua escondida (as quinze `CFG_*`), aba órfã desenha o próprio
item, com o título e a rota dela. ⚠️ A regra antiga não foi afrouxada, foi
**condicionada** — e uma fixture do `menu_grupos_2110.teste.js` que tinha uma
aba órfã (situação que o sistema não produz) foi corrigida, e não o código.
""", "docs/03 entrega")

# ---------------------------------------------------------------------------
# docs/06 — o conteúdo da tela
# ---------------------------------------------------------------------------
anexar("06_Conteudo_das_Telas.md", """\
## 06/11 — `CFG_15.1` Permissão dos painéis

🔵 **Pedido dele:** *"em configuração, crie uma aba de permissão para os
paineis, ali vou definir quem pode ver o que e por aba tbm, como notará que o
pós venda ja possui abas"*.

**Uma grade.** Linhas = atendentes **ativos**; colunas = as telas do grupo
"Painéis", na ordem do registro. Uma caixa por cruzamento.

| coluna | de onde vem o nome |
|---|---|
| Operação | `PNL_1.1` |
| Treinamentos | `PNL_1.2` — **do banco** (`painel_aba.titulo`) |
| Pós-venda | `PNL_1.3` — **do banco**, e a coluna entra **recuada** (`aba_de`) |

🚨 **AS DUAS COLUNAS DO PÓS-VENDA TERIAM O MESMO NOME SEM O BANCO.** No
registro, `PNL_1.2` e `PNL_1.3` se chamam as duas "Pós-venda" (correção dele de
05/11: o item de menu é o do painel). O nome que as distingue mora em
`painel_aba.titulo` — e sem ele marcar uma das duas seria chute. É o detalhe
que ele antecipou: *"como notará que o pós venda ja possui abas"*.

🚨 **MARCAR NÃO GRAVA.** Marcar é dar acesso a dado de cliente; gravar no clique
transformaria um toque errado em concessão silenciosa. A linha alterada fica
destacada, com **Gravar** e **desfazer**, e o rodapé conta quantas linhas estão
pendentes.

⚠️ **A TELA REDESENHA DO QUE O SERVIDOR DEVOLVEU.** O `PUT` responde com a grade
**relida**, e não com um `ok`. Tela que confia no próprio palpite é como `M12`
começa.

⚠️ **SEM PARÁGRAFO DIDÁTICO** (decisão dele, 30/10: *"atrapalha o
profissionalismo"*). O que a tela escreve é ESTADO: o perfil de cada pessoa, o
código de cada coluna, **quem concedeu e em que dia** cada marca, e quantas
linhas faltam gravar.

🔴 **O que esta aba NÃO faz:** não cria conta, não muda perfil, não concede
nenhuma tela fora dos painéis, e não concede a si mesma.
""", "docs/06 conteúdo")

# ---------------------------------------------------------------------------
# docs/02 — o modelo de dados
# ---------------------------------------------------------------------------
anexar("02_Modelo_Dados.md", """\
## `tela_concedida` — a permissão que não é por perfil (migração 095, 06/11)

```
tela_concedida
  id             bigserial PK
  atendente_id   bigint NOT NULL -> atendente(id) ON DELETE CASCADE
  codigo_tela    varchar(16) NOT NULL        -- código do `movizap/telas.py`
  concedida_por  bigint -> atendente(id) ON DELETE SET NULL
  concedida_em   timestamptz NOT NULL DEFAULT now()
  UNIQUE (atendente_id, codigo_tela)
```

🔵 Nasceu do pedido dele de 06/11: *"em configuração, crie uma aba de permissão
para os paineis, ali vou definir quem pode ver o que e por aba tbm"*.

🚨 **É A LISTA DE EXCEÇÕES NOMEADAS DA PERMISSÃO.** Até 06/11 quem decidia
acesso era só `atendente.perfil` → `telas.PERFIS`. Cada linha aqui diz *"esta
pessoa alcança esta tela"*, e `telas.pode_acessar` a honra **antes** de recusar
tela `owner`. ⚠️ A tela continua `owner` no registro — isto não a rebaixa.

🚨 **SEM FK EM `codigo_tela`, de propósito:** o catálogo de telas é o CÓDIGO
(`movizap/telas.py`), não uma tabela — a mesma razão de `painel_aba.codigo_tela`
não ter. Quem limita o que pode ser gravado é a rota, que só aceita código do
grupo "Painéis".

🚨 **A UNIQUE É A TRAVA DA TELA.** Sem ela, conceder duas vezes daria duas
linhas e revogar apagaria uma só: a pessoa continuaria vendo o painel e a tela
de permissão diria "não concedido" — `M12`, e sobre quem vê o quê.

⚠️ **AS DUAS FK SÃO DIFERENTES DE PROPÓSITO.** `atendente_id` cai em **CASCADE**
(a concessão não tem sentido sem quem a recebeu); `concedida_por` cai em **SET
NULL** (apagar quem concedeu não tira o acesso de quem recebeu, só o autor).

⚠️ **LIDA A CADA REQUISIÇÃO** por `auth.buscar_usuario`, e **não** guardada no
token: revogar vale no próximo clique da pessoa, não no próximo login dela. A
leitura degrada para vazio se a tabela não responder — a pessoa perde o painel
concedido e continua entrando, que é o lado certo de falhar.

**Hoje:** 0 linhas. Quem concede é ele, na aba `CFG_15.1`. A migração não
concede nada a ninguém.
""", "docs/02 modelo")

print("documentação da CFG_15.1: feita")
