# -*- coding: utf-8 -*-
"""A 12ª CONFERÊNCIA: a família do painel não pode ter duas casas — 25/11.

🔵 Ele: *"as fontes ainda estão erradas entre as abas"* · *"porque não está
fazendo corretamente?"*

🚨 A causa era `card__abrir` declarado em 4 arquivos com 3 corpos. A fonte única
(`estilo/painel.css`) conserta HOJE; esta conferência é o que impede a cópia de
voltar amanhã — e falha o **build**, não um teste que alguém pode não rodar.
"""
import pathlib
import shutil
import sys
from datetime import datetime

ALVO = pathlib.Path("/home/claude/movizap_painel/frontend/scripts/"
                    "conferir_css_publicado.mjs")

FUNCAO = r"""/* ------------------------------------------------------------------ 12 */
function aFamiliaDoPainelTemUmaCasaSO(css) {
  /* 🚨 O DEFEITO, medido em 25/11: `.card__abrir` estava declarado em **4**
     arquivos com **3 corpos diferentes**, `.pilula` em 7, `.coluna` em 5 — e o
     CSS global declarava nenhum. Resultado na tela: a mesma classe com `gap`
     e-1 numa aba e e-2 na outra, borda fina numa e forte na outra, sombra só
     numa. Ele viu isso como *"as fontes estão erradas entre as abas"*, e
     nenhuma das 11 conferências anteriores olhava para isso: cada regra,
     isolada, estava válida.

     ⚠️ O que se mede é **duas CASAS com corpos DIFERENTES**, não duas
     ocorrências: `.painel__topo, .tela__cabecalho { … }` é uma regra com dois
     nomes, e isso é exatamente o que se quer.

     ⚠️ E `:hover`, `--variante` e qualquer coisa dentro de `@media` ficam
     fora: a variante é de UMA tela por desenho, e o `@media` existe para
     declarar outro corpo. */
  const FAMILIA = [
    'painel', 'painel__topo', 'painel__identidade', 'painel__titulo',
    'painel__medidas', 'painel__casco', 'painel__quadro',
    'tela__cabecalho', 'cabecalho__identidade', 'cabecalho__controles',
    'card', 'card__abrir', 'card__linha', 'card__cliente', 'card__direita',
    'card__dado', 'card__ident', 'card__os', 'card__termo', 'card__resumo',
    'card__rodape', 'card__acoes',
    'coluna', 'coluna__titulo', 'coluna__botao', 'coluna__nome',
    'coluna__conta', 'coluna__corpo',
    'abas', 'abas__item', 'controles', 'controles__busca', 'controles__ordem',
    'pilula', 'selo',
    'acoes', 'acoes__grupo', 'acoes__titulo', 'acoes__grade',
    'acao', 'acao__nome', 'acao__nota',
  ]

  /* Varre as regras de 1º nível, pulando o conteúdo de `@media` e afins. */
  const casas = new Map()
  let i = 0
  while (i < css.length) {
    const abre = css.indexOf('{', i)
    if (abre < 0) break
    const sel = css.slice(i, abre).trim()
    let nivel = 1
    let k = abre + 1
    while (k < css.length && nivel) {
      if (css[k] === '{') nivel += 1
      else if (css[k] === '}') nivel -= 1
      k += 1
    }
    const corpo = css.slice(abre + 1, k - 1)
    i = k
    if (sel.startsWith('@')) continue
    for (const bruto of sel.split(',')) {
      const um = bruto.trim()
      /* o último seletor simples, sem o `[data-v-...]` do `scoped` */
      const m = um.match(/\.([a-zA-Z0-9_-]+)(\[data-v-[0-9a-f]+\])?$/)
      if (!m) continue
      const nome = m[1]
      if (!FAMILIA.includes(nome)) continue
      const normal = corpo.replace(/\s+/g, ' ').trim()
      if (!casas.has(nome)) casas.set(nome, new Set())
      casas.get(nome).add(normal)
    }
  }

  const duplas = [...casas.entries()].filter(([, corpos]) => corpos.size > 1)
  if (duplas.length) {
    falhar(`${duplas.length} classe(s) da família do painel com MAIS DE UM `
           + `corpo no CSS publicado: `
           + duplas.map(([n, c]) => `${n} (${c.size} corpos)`).join(' · ')
           + '. A casa delas é `estilo/painel.css` — duas casas divergem, e foi '
           + 'assim que as abas ficaram com fontes e proporções diferentes.')
  }
}

const css = cssPublicado()"""

CHAMADA_DE = """  todaVarianteDeBotaoUsadaTemRegra(css)
}"""
CHAMADA_PARA = """  todaVarianteDeBotaoUsadaTemRegra(css)
  aFamiliaDoPainelTemUmaCasaSO(css)
}"""

TEXTO_DE = ("console.log('CSS publicado: as 11 conferências passaram (teto "
            "do diálogo, '")
TEXTO_PARA = ("console.log('CSS publicado: as 12 conferências passaram (teto "
              "do diálogo, '")

FIM_DE = """            + 'toda variante de botão usada com regra no CSS)')"""
FIM_PARA = """            + 'toda variante de botão usada com regra no CSS, '
            + 'família do painel com uma casa só)')"""

T = [("a 12a conferencia", "const css = cssPublicado()", FUNCAO),
     ("a chamada dela", CHAMADA_DE, CHAMADA_PARA),
     ("o texto do verde", TEXTO_DE, TEXTO_PARA),
     ("o fim do texto", FIM_DE, FIM_PARA)]


def main() -> int:
    texto = ALVO.read_text(encoding="utf-8")
    for rotulo, de, _p in T:
        if texto.count(de) != 1:
            print(f"ABORTADO em '{rotulo}': {texto.count(de)} ocorrencias.",
                  file=sys.stderr)
            return 1
    novo = texto
    for _r, de, para in T:
        novo = novo.replace(de, para, 1)
    marca = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    shutil.copy2(ALVO, ALVO.with_suffix(ALVO.suffix + f".bak_{marca}_familia"))
    ALVO.write_text(novo, encoding="utf-8")
    print(f"linhas {len(texto.splitlines())} -> {len(novo.splitlines())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
