"""A 11a CONFERENCIA DO CSS PUBLICADO: `botao--*` usada sem regra (25/11).

🚨 O DEFEITO QUE ELA IMPEDE: `botao--fraco` foi usada 19 vezes numa tela e
NAO EXISTIA em CSS nenhum. Os 19 renderizaram como `.botao` base, com cara de
primario -- e isso passou por 3.898 testes verdes e pelas 10 conferencias de
CSS, porque classe inexistente nao da erro: o navegador simplesmente ignora.

⚠️ As 10 conferencias olham o CSS. Esta olha a CADEIA, como a do `var()`: a
classe usada no TEMPLATE tem regra no CSS que o navegador recebe?
"""
import pathlib
import shutil
import sys
from datetime import datetime

ALVO = pathlib.Path("/home/claude/movizap_painel/frontend/scripts/"
                    "conferir_css_publicado.mjs")

IMPORT_DE = ("import { readFileSync, readdirSync, existsSync } "
             "from 'node:fs'\nimport { join } from 'node:path'\n")
IMPORT_PARA = ("import { readFileSync, readdirSync, existsSync, statSync } "
               "from 'node:fs'\nimport { join } from 'node:path'\n")

FUNCAO_DE = """const css = cssPublicado()
if (!erros.length) {"""

FUNCAO_PARA = """/* ------------------------------------------------------------------ 11 */
function todaVarianteDeBotaoUsadaTemRegra(css) {
  /* 🚨 O DEFEITO, medido em 25/11: `botao--fraco` usada **19 vezes** na aba 2
     do Financeiro e declarada em lugar nenhum -- nem no `componentes.css`, nem
     no `<style scoped>` da tela. Classe que não existe **não dá erro**: o
     navegador ignora e o botão renderiza como `.botao` base, com cara de
     primário. Uma tela com 19 primários não diz qual é a ação principal.

     ⚠️ É a mesma forma da conferência 10: o que se mede é a CADEIA (a classe
     usada no template encontra regra no CSS publicado?), não uma regra que já
     quebrou. A suíte não alcança isto -- o jsdom não aplica folha de estilo.

     ⚠️ SÓ O QUE ESTÁ EM `class=`/`:class=` conta. Varrer o arquivo inteiro
     pegaria o nome escrito em COMENTÁRIO (este projeto documenta defeito no
     comentário, inclusive o `botao--fraco` que acabou de sair) e a trava
     reprovaria por causa de um texto. */
  const raiz = join(process.cwd(), 'src')
  const vues = []
  const andar = (pasta) => {
    for (const nome of readdirSync(pasta)) {
      const caminho = join(pasta, nome)
      if (statSync(caminho).isDirectory()) andar(caminho)
      else if (nome.endsWith('.vue')) vues.push(caminho)
    }
  }
  if (!existsSync(raiz)) {
    falhar(`não achei ${raiz} para conferir as variantes de botão.`)
    return
  }
  andar(raiz)

  const usadas = new Map()
  for (const caminho of vues) {
    const texto = readFileSync(caminho, 'utf8')
    for (const atr of texto.matchAll(/:?class="([^"]*)"/g)) {
      for (const m of atr[1].matchAll(/botao--[a-z0-9-]+/g)) {
        if (!usadas.has(m[0])) usadas.set(m[0], new Set())
        usadas.get(m[0]).add(caminho.split('src').pop())
      }
    }
  }
  /* Declarada em QUALQUER lugar do CSS publicado conta -- global ou scoped
     (`.botao--x[data-v-...]`). O que se mede é existir. */
  const declaradas = new Set(
    [...css.matchAll(/\\.(botao--[a-z0-9-]+)/g)].map((m) => m[1]))
  const orfas = [...usadas.keys()].filter((n) => !declaradas.has(n)).sort()
  if (orfas.length) {
    falhar(`${orfas.length} variante(s) de botão usada(s) em template SEM `
           + `regra no CSS publicado: `
           + orfas.map((n) => `${n} (${[...usadas.get(n)].join(', ')})`)
             .join(' · ')
           + '. O navegador ignora a classe e o botão sai como `.botao` base — '
           + 'use uma variante que existe em estilo/componentes.css, ou '
           + 'declare a regra.')
  }
}

const css = cssPublicado()
if (!erros.length) {"""

CHAMADA_DE = """  todoVarUsadoExiste(css)
}"""
CHAMADA_PARA = """  todoVarUsadoExiste(css)
  todaVarianteDeBotaoUsadaTemRegra(css)
}"""

TEXTO_DE = ("console.log('CSS publicado: as 10 conferências passaram (teto do "
            "diálogo, '")
TEXTO_PARA = ("console.log('CSS publicado: as 11 conferências passaram (teto "
              "do diálogo, '")

FIM_DE = """            + 'pílula com base no mesmo '
            + 'escopo, todo var() com token declarado)')"""
FIM_PARA = """            + 'pílula com base no mesmo '
            + 'escopo, todo var() com token declarado, '
            + 'toda variante de botão usada com regra no CSS)')"""

T = [("o import do statSync", IMPORT_DE, IMPORT_PARA),
     ("a 11a conferencia", FUNCAO_DE, FUNCAO_PARA),
     ("a chamada dela", CHAMADA_DE, CHAMADA_PARA),
     ("o texto do verde", TEXTO_DE, TEXTO_PARA),
     ("o fim do texto do verde", FIM_DE, FIM_PARA)]


def main() -> int:
    texto = ALVO.read_text(encoding="utf-8")
    for rotulo, de, _para in T:
        if texto.count(de) != 1:
            print(f"ABORTADO em '{rotulo}': ancora aparece "
                  f"{texto.count(de)} vezes. Nada gravado.", file=sys.stderr)
            return 1
    novo = texto
    for _r, de, para in T:
        novo = novo.replace(de, para, 1)
    marca = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    shutil.copy2(ALVO, ALVO.with_suffix(ALVO.suffix + f".bak_{marca}_trava_botao"))
    ALVO.write_text(novo, encoding="utf-8")
    print(f"linhas: {len(texto.splitlines())} -> {len(novo.splitlines())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
