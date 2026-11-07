# -*- coding: utf-8 -*-
"""A PNL_1.4 (Financeiro) no registro e no roteador (06/11). Idempotente.

Guard: a linha que SERIA acrescentada, nunca a ancora -- a licao dos dois
patches de hoje que disseram "ja aplicado" e nao escreveram nada.
"""
import pathlib
import sys

RAIZ = pathlib.Path("/home/claude/movizap_painel")

# ---------------------------------------------------------------- telas.py
P = RAIZ / "movizap/telas.py"
t = P.read_text(encoding="utf-8")
NOVA_ENTRADA = '''        "codigo": "PNL_1.4",'''
if NOVA_ENTRADA in t:
    print("  telas.py: ja aplicado")
else:
    ANCORA = '''    {
        # 🔵 22/10: a tela que recebe o que chega pelos formularios proprios'''
    if t.count(ANCORA) != 1:
        sys.exit(f"telas.py: ancora apareceu {t.count(ANCORA)}x")
    BLOCO = '''    {
        # 🔵 06/11, pedido dele: *"do 1"* -- as colunas do Financeiro, que era
        # a pendência de 05/11 -- seguido da lista das dez e de *"conclua e
        # exiba o financeiro no paniel para owner"*.
        #
        # 🚨 UMA ENTRADA, E NÃO QUATRO. O Pós-venda tem duas porque ele
        # escreveu DUAS listas de colunas; aqui a lista é uma, sob o título
        # "Colunas". ⚠️ O que havia sobre "abas do financeiro" era o exemplo de
        # permissão que ele marcou como *"Apenas exemplo"*, e a lista do §2.1 do
        # `MoviZap_Formularios_PLANO.md`, que é de FORMULÁRIOS, não de etapas.
        # Repartir dez colunas entre quatro abas inventadas seria escopo meu.
        #
        # 🚨 `owner`, E É A PALAVRA DELE: *"exiba o financeiro no paniel para
        # owner"*. ⚠️ E agora isso tem consequência nova: a aba `CFG_15.1`
        # (06/11) concede o grupo "Painéis", e a lista de concedíveis sai do
        # REGISTRO -- então esta tela aparece lá para ele marcar **sozinha**,
        # sem uma linha de código a mais. Era o desenho; esta entrada é a
        # primeira prova dele.
        #
        # ⚠️ AS COLUNAS NÃO MORAM AQUI, moram no banco (`pipeline_etapa`,
        # migração 096). Esta entrada é a PORTA: código, rota e quem entra.
        #
        # ⚠️ Código conferido contra `CODIGOS_APOSENTADOS` (só `ATD_4.1`) e
        # contra os códigos em uso: `PNL_1.4` estava livre, e era o reservado
        # pelo comentário da `PNL_1.1` desde 22/10.
        "codigo": "PNL_1.4",
        "titulo": "Financeiro",
        "rota": "/paineis/financeiro",
        "icone": "bi-cash-coin",
        "descricao": "Financeiro: da solicitação ao atendimento, em dez etapas nossas.",
        "grupo": "Painéis",
        "permissao": "owner",
        "fase": 1,
    },
'''
    t = t.replace(ANCORA, BLOCO + ANCORA)
    P.write_text(t, encoding="utf-8")
    print("  telas.py: PNL_1.4 acrescentada")

# ------------------------------------------------------------ router/index.js
P = RAIZ / "frontend/src/router/index.js"
t = P.read_text(encoding="utf-8")
if "'/paineis/financeiro'" in t:
    print("  router: ja aplicado")
else:
    ANCORA = """    path: '/paineis/pos-venda/realizado',"""
    if t.count(ANCORA) != 1:
        sys.exit(f"router: ancora apareceu {t.count(ANCORA)}x")
    # Acha o fim do objeto de rota da PNL_1.3 para inserir depois dele.
    i = t.index(ANCORA)
    fim = t.index("  },\n", i) + len("  },\n")
    BLOCO = """  {
    // 🔵 06/11, ele: *"conclua e exiba o financeiro no paniel para owner"*.
    // 🚨 MESMA `PainelAba` das abas do Pós-venda: as colunas vivem no banco
    // (`pipeline_etapa`), não no código -- uma tela por painel seria copiar o
    // mesmo kanban quatro vezes.
    path: '/paineis/financeiro',
    name: 'PNL_1.4',
    component: PainelAba,
    meta: { codigo: 'PNL_1.4', titulo: 'Financeiro' },
  },
"""
    t = t[:fim] + BLOCO + t[fim:]
    P.write_text(t, encoding="utf-8")
    print("  router: rota /paineis/financeiro acrescentada")

print("PNL_1.4: registro + roteador")
