# -*- coding: utf-8 -*-
"""O dublê do rolo passa a LIMITAR o `scrollLeft`, como um elemento de verdade.

🚨 O teste "para sozinha ao chegar no fim" reprovou, e a culpa era do DUBLE, nao
do componente: um elemento real limita `scrollLeft` ao intervalo
[0, scrollWidth - clientWidth] silenciosamente, e o meu objeto literal aceitava
qualquer numero. ⚠️ Duble que nao espelha a plataforma faz todos os outros
testes do arquivo medirem uma ficcao -- e foi a licao de `duplo se poe na borda`.
"""
import pathlib
import sys

P = pathlib.Path("/home/claude/movizap_painel/frontend/src/rolagem_0611.teste.js")
t = P.read_text(encoding="utf-8")

if "LIMITA o `scrollLeft`" in t:
    sys.exit("ja aplicado")

VELHO = """function roloFalso({ conteudo = 6500, visivel = 1650, em = 0 } = {}) {
  return {
    scrollWidth: conteudo,
    clientWidth: visivel,
    scrollLeft: em,
    firstElementChild: null,
    addEventListener() {},
    removeEventListener() {},
    getBoundingClientRect: () => ({
      left: 0, right: visivel, width: visivel, top: 0, bottom: 800, height: 800,
    }),
  }
}"""

NOVO = """function roloFalso({ conteudo = 6500, visivel = 1650, em = 0 } = {}) {
  /* 🚨 O DUBLÊ LIMITA o `scrollLeft`, porque elemento de verdade limita. Um
     objeto literal aceitaria `scrollLeft = 99999` e o teste "para no fim"
     mediria um número que o navegador nunca produz. ⚠️ Dublê que não espelha a
     plataforma faz todo o arquivo medir uma ficção -- é a regra de
     `duplo se põe na borda`, e foi este teste que a cobrou. */
  let em_ = em
  const teto = Math.max(0, conteudo - visivel)
  return {
    scrollWidth: conteudo,
    clientWidth: visivel,
    get scrollLeft() { return em_ },
    set scrollLeft(v) { em_ = Math.max(0, Math.min(teto, v)) },
    firstElementChild: null,
    addEventListener() {},
    removeEventListener() {},
    getBoundingClientRect: () => ({
      left: 0, right: visivel, width: visivel, top: 0, bottom: 800, height: 800,
    }),
  }
}"""

if t.count(VELHO) != 1:
    sys.exit(f"ancora apareceu {t.count(VELHO)}x")

P.write_text(t.replace(VELHO, NOVO), encoding="utf-8")
print("rolagem_0611.teste.js: o duble limita o scrollLeft")
