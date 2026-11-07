# -*- coding: utf-8 -*-
"""Documenta o defeito do `meta.aba` achado por ele (06/11). Idempotente."""
import pathlib
import sys

MARCA = "O `meta.aba` QUE FALTAVA"

TEXTO = """\
### 🚨 06/11, achado POR ELE: as colunas não apareciam — o `meta.aba` QUE FALTAVA

🔵 Ele: *"não estão aparecendo as colunas de 'financeiro' e ' contratual'"*.

**A causa.** O `PainelAba.vue` descobre qual aba carregar em
`rota.meta?.aba || ''` — **não** em `meta.codigo`. As duas rotas que eu escrevi
levavam só `codigo` e `titulo`, porque copiei a forma do `meta` das rotas de
`/config`, que não têm `aba`, em vez das duas do Pós-venda, que têm. Com o campo
ausente, o código ficava **vazio** e a tela pedia `/api/paineis/aba/` sem código
nenhum: nenhuma coluna, e nenhum erro visível.

🚨 **TUDO O MAIS ESTAVA CERTO, e é isso que faz o defeito.** Entrada no registro,
item de menu, rota, permissão, **200** na API quando chamada com o código, as 10
e as 6 colunas no banco, e **2227 testes verdes**. O elo que faltava era o
**quarto**: quem devolve → quem grava → quem lê → **quem diz à tela o que ler**.
A casa já tinha catalogado os três primeiros (`campo novo não entra sozinho`);
este acrescenta o quarto.

**O conserto:** `aba: 'PNL_1.4'` e `aba: 'PNL_1.5'` no `meta`, mais
`largo: true` — que não é enfeite: o Financeiro tem **dez** colunas e sem ele o
quadro ficaria apertado na coluna de conteúdo.

🚨 **A TRAVA NOVA É ESTRUTURAL, e tinha de ser** (`rotas_painel_0611.teste.js`,
6 travas): ela **não cita** `PNL_1.4` nem `PNL_1.5`. Varre o roteador e cobra de
**toda** rota que monta a `PainelAba` quatro coisas — ter `meta.aba`, ter
`meta.aba == meta.codigo` (apontar para outra tela seria pior que tela vazia:
mostraria o conteúdo de um painel na permissão de outro), ter `largo: true`, e
ter `name == meta.codigo`. Assim o próximo painel não pode repetir o
esquecimento. ⚠️ Uma trava que citasse os dois códigos ficaria verde no dia
seguinte e seria inútil. **Reverter o `meta.aba` de uma das duas deixa 3
vermelhas** — forjado e pego.

⚠️ **E a prova não foi o teste:** foi `grep` no **bundle publicado**
(`frontend/dist/assets/index-*.js`), que agora contém `aba:"PNL_1.4"` e
`aba:"PNL_1.5"`. Suíte verde não prova tela (`M9`) — e aqui ela estava verde
enquanto a tela estava vazia.
"""

ALVOS = [
    pathlib.Path("/home/claude/movizap_painel/docs/06_Conteudo_das_Telas.md"),
]
for p in ALVOS:
    t = p.read_text(encoding="utf-8")
    if MARCA in t:
        print(f"  {p.name}: ja aplicado")
        continue
    p.write_text(t.rstrip("\n") + "\n\n" + TEXTO, encoding="utf-8")
    print(f"  {p.name}: ok")

t = ALVOS[0].read_text(encoding="utf-8")
if MARCA not in t:
    sys.exit("grep nao achou a marca depois de escrever")
print("  grep confere:", t.count(MARCA), "ocorrencia(s)")
