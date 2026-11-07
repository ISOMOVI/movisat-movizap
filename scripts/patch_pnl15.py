# -*- coding: utf-8 -*-
"""A PNL_1.5 (Contratual) no registro e no roteador (06/11). Idempotente."""
import pathlib
import sys

RAIZ = pathlib.Path("/home/claude/movizap_painel")

# ---------------------------------------------------------------- telas.py
P = RAIZ / "movizap/telas.py"
t = P.read_text(encoding="utf-8")
if '"codigo": "PNL_1.5",' in t:
    print("  telas.py: ja aplicado")
else:
    ANCORA = '''    {
        # 🔵 22/10: a tela que recebe o que chega pelos formularios proprios'''
    if t.count(ANCORA) != 1:
        sys.exit(f"telas.py: ancora apareceu {t.count(ANCORA)}x")
    BLOCO = '''    {
        # 🔵 06/11, pedido dele: *"Depois gere a mesmta tela do 'Financeiro'
        # para o 'Contratual'"*, com a lista de colunas colada em seguida.
        #
        # 🚨 DUAS LINHAS DA LISTA DELE NÃO ENTRARAM, e é leitura minha:
        # *"Regras de automação e gatilhos"* e *"pesquisar"* são a moldura da
        # tela de onde ele copiou (o link de automação e a caixa de busca do
        # CRM), não etapas de contrato -- a lista do Financeiro, meia hora
        # antes, vinha com o cabeçalho literal "Colunas" no mesmo lugar.
        # ⚠️ Está escrito nos Próximos Passos como PERGUNTA ABERTA, e o
        # conserto é uma linha da migração 097.
        #
        # 🚨 `owner`, e é a palavra dele: *"eleas ja devem aparecer no menu
        # para owner"*. ⚠️ Com a `CFG_15.1` (de hoje mais cedo), esta tela
        # aparece na aba de permissão **sozinha** -- a lista de concedíveis sai
        # do grupo "Painéis" do registro, não de lista escrita à mão.
        #
        # ⚠️ AS COLUNAS NÃO MORAM AQUI, moram no banco (`pipeline_etapa`,
        # migração 097). Esta entrada é a PORTA: código, rota e quem entra.
        #
        # ⚠️ Código conferido contra `CODIGOS_APOSENTADOS` (só `ATD_4.1`) e
        # contra os códigos em uso: `PNL_1.5` estava livre. O comentário da
        # `PNL_1.1` reservava 1.2/1.3/1.4 para os outros três painéis -- o
        # Pós-venda gastou DUAS (1.2 e 1.3, porque são duas abas), então o
        # Financeiro ficou com 1.4 e o Contratual com 1.5.
        "codigo": "PNL_1.5",
        "titulo": "Contratual",
        "rota": "/paineis/contratual",
        "icone": "bi-file-earmark-text",
        "descricao": "Contratual: de elaborar o contrato aos três desfechos.",
        "grupo": "Painéis",
        "permissao": "owner",
        "fase": 1,
    },
'''
    t = t.replace(ANCORA, BLOCO + ANCORA)
    P.write_text(t, encoding="utf-8")
    print("  telas.py: PNL_1.5 acrescentada")

# ------------------------------------------------------------ router/index.js
P = RAIZ / "frontend/src/router/index.js"
t = P.read_text(encoding="utf-8")
if "'/paineis/contratual'" in t:
    print("  router: ja aplicado")
else:
    ANCORA = "    path: '/paineis/financeiro',"
    if t.count(ANCORA) != 1:
        sys.exit(f"router: ancora apareceu {t.count(ANCORA)}x")
    i = t.index(ANCORA)
    fim = t.index("  },\n", i) + len("  },\n")
    BLOCO = """  {
    // 🔵 06/11, ele: *"gere a mesmta tela do 'Financeiro' para o
    // 'Contratual'"*. Mesma `PainelAba`: as colunas vivem no banco.
    path: '/paineis/contratual',
    name: 'PNL_1.5',
    component: PainelAba,
    meta: { codigo: 'PNL_1.5', titulo: 'Contratual' },
  },
"""
    t = t[:fim] + BLOCO + t[fim:]
    P.write_text(t, encoding="utf-8")
    print("  router: rota /paineis/contratual acrescentada")

print("PNL_1.5: registro + roteador")
