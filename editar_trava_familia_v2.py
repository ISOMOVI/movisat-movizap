# -*- coding: utf-8 -*-
"""A 12ª conferência, v2: medir no FONTE dos painéis — e a 8ª, cuja premissa
a fonte única venceu. 25/11.

🚨 **POR QUE A v1 DA 12ª NÃO SERVIU, e é medição, não opinião:** ela contava
corpos no CSS publicado, e `.tela__cabecalho` existe em **16 outras telas**
(Histórico, Solicitações, Atendentes, Canais, …), `.painel` no `App.vue` e na
Caixa, `.coluna` na Caixa e no Chat interno. Esses nomes são da CASA, não do
painel: contar tudo junto reprovava 9 classes por um defeito que não existe.

A v2 mede o que importa e sem ambiguidade: **nenhum arquivo de painel declara
regra da família** — a casa delas é `estilo/painel.css`. É a forma da 11ª
conferência, que lê o template para medir a cadeia.

E a **8ª** (*"toda variante de pílula tem a pílula base no mesmo escopo"*)
tinha uma premissa que esta mudança venceu: a base era scoped por componente,
e agora é global sob `.escala-operacao`. Ela passa a aceitar a base global —
o risco que ela guardava (*"selo com cor e sem forma"*) continua guardado, pela
base global mais a 12ª.
"""
import pathlib
import re
import shutil
import sys
from datetime import datetime

ALVO = pathlib.Path("/home/claude/movizap_painel/frontend/scripts/"
                    "conferir_css_publicado.mjs")

NOVA_12 = r"""/* ------------------------------------------------------------------ 12 */
function aFamiliaDoPainelTemUmaCasaSO() {
  /* 🚨 O DEFEITO, medido em 25/11: `.card__abrir` declarado em **4** arquivos
     com **3 corpos diferentes**, `.pilula` em 7, `.coluna` em 5 — e o CSS
     global declarando nenhum. Na tela: `gap` e-1 numa aba e e-2 na outra,
     borda fina numa e forte na outra, sombra só numa, cabeçalho centrado aqui
     e `flex-end` lá. Ele viu como *"as fontes estão erradas entre as abas"*, e
     nenhuma das 11 conferências via: cada regra, isolada, estava válida.

     🚨 **MEDE NO FONTE, E SÓ DOS ARQUIVOS DE PAINEL.** Contar corpos no CSS
     publicado não serve: `.tela__cabecalho` existe em **16 outras telas**,
     `.painel` no `App.vue`, `.coluna` na Caixa e no Chat interno — nomes da
     casa, não do painel. O que não pode existir é a CÓPIA dentro de um
     arquivo de painel, porque é ela que diverge da fonte única.

     ⚠️ Variante (`--algo`) e `:hover` ficam fora: variante de uma tela só é
     desenho, e é por isso que elas continuam scoped. */
  const CASA = 'src/estilo/painel.css'
  const PAINEIS = [
    'src/telas/PainelAba.vue',
    'src/telas/PainelOperacao.vue',
    'src/telas/PainelServicoDosTecnicos.vue',
    'src/componentes/CorpoDoCard.vue',
  ]
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

  const base = join(process.cwd(), '..')
  const casa = join(base, CASA)
  if (!existsSync(casa)) {
    falhar(`não achei ${CASA} — a fonte única do CSS dos painéis sumiu, e sem `
           + 'ela cada tela volta a ter a sua cópia.')
    return
  }
  const fonteDaCasa = readFileSync(casa, 'utf8')

  const copias = []
  const semCasa = []
  for (const arquivo of PAINEIS) {
    const caminho = join(base, arquivo)
    if (!existsSync(caminho)) {
      falhar(`não achei ${arquivo} para conferir a família do painel.`)
      continue
    }
    const texto = readFileSync(caminho, 'utf8')
    const estilo = texto.match(/<style[^>]*>([\s\S]*)<\/style>/)
    if (!estilo) continue
    const semComentario = estilo[1].replace(/\/\*[\s\S]*?\*\//g, '')
    for (const nome of FAMILIA) {
      const re = new RegExp(`(^|\\})\\s*\\.${nome}\\s*(,[^{]*)?\\{`, 'm')
      if (re.test(semComentario)) {
        copias.push(`${nome} em ${arquivo.split('/').pop()}`)
      }
    }
  }
  /* E a cadeia: o que os painéis usam tem de estar na casa. */
  for (const nome of FAMILIA) {
    if (!new RegExp(`\\.${nome}[\\s,{]`).test(fonteDaCasa)) semCasa.push(nome)
  }

  if (copias.length) {
    falhar(`${copias.length} regra(s) da família do painel declarada(s) DENTRO `
           + `de um arquivo de painel: ${copias.join(' · ')}. A casa delas é `
           + `${CASA} — duas casas divergem, e foi assim que as abas ficaram `
           + 'com fontes e proporções diferentes.')
  }
  if (semCasa.length > 8) {
    falhar(`${semCasa.length} classes da família não estão em ${CASA} `
           + `(${semCasa.slice(0, 6).join(', ')}…) — a fonte única está `
           + 'incompleta, e o que falta volta a ser copiado.')
  }
}

const css = cssPublicado()"""

# A 8ª: a base da pílula agora pode ser global.
OITAVA_DE = """    if (!escoposComBase.has(escopo)) {
      falhar(`o escopo data-v-${escopo} declara uma VARIANTE de .pilula e não `
             + 'declara a base — o selo fica com cor e sem forma. A `.pilula` é '
             + 'scoped por componente: cada tela que a usa declara a sua.');
    }"""

OITAVA_PARA = """    /* 🚨 25/11: A PREMISSA DESTA CONFERÊNCIA MUDOU, e quem a mudou fui eu.
       A `.pilula` era scoped por componente -- cada tela declarava a sua, e foi
       por isso que esta trava nasceu em 12/11. Agora a base dos PAINÉIS mora
       em `estilo/painel.css`, sob `.escala-operacao`: variante sem base local
       deixou de ser defeito quando a base global existe.
       ⚠️ O risco que ela guardava continua guardado -- pela base global e pela
       12ª conferência, que proíbe a cópia voltar para dentro das telas. */
    if (!escoposComBase.has(escopo) && !temBaseGlobalDaPilula(css)) {
      falhar(`o escopo data-v-${escopo} declara uma VARIANTE de .pilula e não `
             + 'declara a base, e não há base global em `estilo/painel.css` — '
             + 'o selo fica com cor e sem forma.');
    }"""

AJUDANTE = """function temBaseGlobalDaPilula(css) {
  /* A base global do painel: `.escala-operacao .pilula { … }`. */
  return /\\.escala-operacao\\s+\\.pilula\\s*[,{]/.test(css)
}

/* ------------------------------------------------------------------ 9 */"""

CHAMADA_DE = """  todaVarianteDeBotaoUsadaTemRegra(css)
  aFamiliaDoPainelTemUmaCasaSO(css)
}"""
CHAMADA_PARA = """  todaVarianteDeBotaoUsadaTemRegra(css)
  aFamiliaDoPainelTemUmaCasaSO()
}"""

T = [("a 12a conferencia v2",
      re.compile(r"/\* -+ 12 \*/.*?const css = cssPublicado\(\)", re.S),
      NOVA_12),
     ("a 8a aceitando base global", OITAVA_DE, OITAVA_PARA),
     ("o ajudante da base global", "/* ------------------------------------------------------------------ 9 */",
      AJUDANTE),
     ("a chamada da 12a", CHAMADA_DE, CHAMADA_PARA)]


def main() -> int:
    texto = ALVO.read_text(encoding="utf-8")
    novo = texto
    for rotulo, de, para in T:
        if isinstance(de, re.Pattern):
            achados = de.findall(novo)
            if len(achados) != 1:
                print(f"ABORTADO em '{rotulo}': {len(achados)} casamentos.",
                      file=sys.stderr)
                return 1
            novo = de.sub(lambda _m: para, novo, count=1)
            continue
        if novo.count(de) != 1:
            print(f"ABORTADO em '{rotulo}': {novo.count(de)} ocorrencias.",
                  file=sys.stderr)
            return 1
        novo = novo.replace(de, para, 1)

    marca = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    shutil.copy2(ALVO, ALVO.with_suffix(ALVO.suffix + f".bak_{marca}_familia_v2"))
    ALVO.write_text(novo, encoding="utf-8")
    print(f"linhas {len(texto.splitlines())} -> {len(novo.splitlines())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
