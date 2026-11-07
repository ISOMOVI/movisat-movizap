# -*- coding: utf-8 -*-
"""As duas rotas novas sem `meta.aba`: era por isso que as colunas nao apareciam.

🚨 DEFEITO MEU. O `PainelAba.vue` descobre qual aba carregar em
`rota.meta?.aba || ''` -- nao em `meta.codigo`. As duas rotas que eu escrevi
levavam so `codigo`, entao `codigo` ficava VAZIO e a tela pedia
`/api/paineis/aba/` sem codigo nenhum: menu certo, rota certa, permissao certa,
e nenhuma coluna. ⚠️ Copiei a forma do `meta` das rotas de CONFIG, que nao tem
`aba`, em vez das duas do Pos-venda, que tem.

⚠️ `largo: true` entra junto, e nao e enfeite: e o que da ao quadro a largura
cheia, como no Pos-venda e na Operacao. Sem ele o kanban de DEZ colunas ficaria
apertado na coluna de conteudo.
"""
import pathlib
import sys

P = pathlib.Path("/home/claude/movizap_painel/frontend/src/router/index.js")
t = P.read_text(encoding="utf-8")

PARES = [
    ("    meta: { codigo: 'PNL_1.4', titulo: 'Financeiro' },",
     "    meta: { codigo: 'PNL_1.4', aba: 'PNL_1.4',\n"
     "            titulo: 'Financeiro', largo: true },"),
    ("    meta: { codigo: 'PNL_1.5', titulo: 'Contratual' },",
     "    meta: { codigo: 'PNL_1.5', aba: 'PNL_1.5',\n"
     "            titulo: 'Contratual', largo: true },"),
]

feitos = 0
for velho, novo in PARES:
    if novo.splitlines()[0] in t:
        print("  ja la:", novo.splitlines()[0].strip()[:40])
        continue
    if t.count(velho) != 1:
        sys.exit(f"ancora apareceu {t.count(velho)}x: {velho[:50]}")
    t = t.replace(velho, novo)
    feitos += 1

P.write_text(t, encoding="utf-8")
print(f"router: {feitos} meta(s) corrigida(s)")

t = P.read_text(encoding="utf-8")
print("conferindo com grep:")
for c in ("PNL_1.2", "PNL_1.3", "PNL_1.4", "PNL_1.5"):
    print(f"  aba: '{c}' ->", t.count(f"aba: '{c}'"))
