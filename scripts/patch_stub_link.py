# -*- coding: utf-8 -*-
"""O `RouterLink` e componente GLOBAL: precisa de stub no `mount` (06/11).

Mockar `vue-router` nao resolve -- o `menu_grupos_2110.teste.js` ja documentava
isso em 21/10 e eu repeti o erro. Sem o stub o Vue monta assim mesmo e so
reclama no stderr, entao o `href` vinha `undefined`.
"""
import pathlib
import sys

P = pathlib.Path("/home/claude/movizap_painel/frontend/src/"
                 "abas_do_painel_0611.teste.js")
t = P.read_text(encoding="utf-8")

if "STUB_LINK" in t:
    sys.exit("ja aplicado")

VELHO = """async function montar(quadro, codigo) {
  estado.quadro = quadro
  estado.rota = { meta: { codigo, aba: codigo }, query: {}, params: {} }
  const tela = mount(PainelAba)
  await flushPromises()
  return tela
}"""
NOVO = """/* ⚠️ O `RouterLink` e componente GLOBAL (registrado pelo plugin do
   vue-router), nao importado: mockar o modulo NAO o resolve. Sem este stub o
   Vue monta assim mesmo, so reclama no stderr, e o `href` vem `undefined` --
   exatamente o que aconteceu na primeira rodada deste arquivo. O
   `menu_grupos_2110.teste.js` ja documentava isto desde 21/10. */
const STUB_LINK = { props: ['to'], template: '<a :href="to"><slot /></a>' }

async function montar(quadro, codigo) {
  estado.quadro = quadro
  estado.rota = { meta: { codigo, aba: codigo }, query: {}, params: {} }
  const tela = mount(PainelAba, {
    global: { stubs: { RouterLink: STUB_LINK } },
  })
  await flushPromises()
  return tela
}"""

if t.count(VELHO) != 1:
    sys.exit(f"ancora apareceu {t.count(VELHO)}x")

P.write_text(t.replace(VELHO, NOVO), encoding="utf-8")
print("abas_do_painel_0611.teste.js: stub do RouterLink")
