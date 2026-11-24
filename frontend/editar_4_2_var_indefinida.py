# -*- coding: utf-8 -*-
"""Tarefa 4.2 (G3) — a conferência de CSS passa a REPROVAR `var()` indefinida.

🚨 O DEFEITO QUE ISTO FECHA, e ele já aconteceu: `var(--nao-existe)` é
DESCARTADA EM SILÊNCIO pelo navegador -- a declaração inteira desaparece, sem
erro no console, sem aviso no build. Foi assim que seis variáveis mortas
sobreviveram, e as 9 conferências de hoje não veem isso: todas olham regras
específicas que já quebraram, nenhuma olha a cadeia token -> uso.

⚠️ FALLBACK NÃO ENTRA: `var(--fundo-2, #fff)` tem segundo argumento, então nada
é descartado -- medido em 23/11, é exatamente o caso do `IaPrompt.vue:440`, e
reprovar ali seria a trava errada.

⚠️ E A DECLARAÇÃO VALE DE QUALQUER LUGAR, não só do `:root`: token declarado
dentro de `.escala-operacao` ou de um `@media` de tema é legítimo. O que a
trava mede é EXISTIR, não onde mora -- quem mede onde mora é a conferência 3.
"""
import pathlib

p = pathlib.Path("scripts/conferir_css_publicado.mjs")
bruto = p.read_bytes()
CRLF = b"\r\n" in bruto
t = bruto.decode("utf-8").replace("\r\n", "\n")


def troca(velho, novo, rotulo):
    global t
    assert velho in t, "NAO ACHOU (%s)" % rotulo
    assert t.count(velho) == 1, "AMBIGUO %dx (%s)" % (t.count(velho), rotulo)
    t = t.replace(velho, novo, 1)
    print("  ok:", rotulo)


# ------------------------------------------------------------------ a função
troca('''const css = cssPublicado()''',
      '''/* ------------------------------------------------------------------ 10 */
function todoVarUsadoExiste(css) {
  /* 🚨 O DEFEITO: `var(--nao-existe)` é DESCARTADA EM SILÊNCIO -- a declaração
     inteira desaparece, sem erro no console e sem aviso no build. Nenhuma das
     nove conferências acima vê isso: todas olham uma regra que já quebrou, e
     esta olha a CADEIA (o token existe? quem o usa o encontra?).

     ⚠️ FALLBACK FICA DE FORA, e não é indulgência: `var(--x, #fff)` não
     descarta nada. Medido em 23/11 -- é o caso do `IaPrompt.vue:440`, e
     reprovar ali seria a trava errada, do tipo que faz a casa afrouxar a
     trava em vez de consertar o código.

     ⚠️ DECLARADA EM QUALQUER LUGAR CONTA: `:root`, `[data-theme]`, um
     `@media`, ou uma classe de escala. O que se mede é EXISTIR; onde mora é
     assunto da conferência 3. */
  const declaradas = new Set(
    [...css.matchAll(/(--[a-zA-Z0-9_-]+)\\s*:/g)].map((m) => m[1]))
  /* `var(` até a vírgula ou o fecha-parêntese: o que vier depois é fallback. */
  const usadas = new Map()
  for (const m of css.matchAll(/var\\(\\s*(--[a-zA-Z0-9_-]+)\\s*([,)])/g)) {
    const nome = m[1]
    const temFallback = m[2] === ','
    if (temFallback) continue
    if (!usadas.has(nome)) usadas.set(nome, 0)
    usadas.set(nome, usadas.get(nome) + 1)
  }
  const orfas = [...usadas.keys()].filter((n) => !declaradas.has(n)).sort()
  if (orfas.length) {
    falhar(`${orfas.length} var() SEM declaração e SEM fallback: `
           + orfas.map((n) => `${n} (${usadas.get(n)}x)`).join(', ')
           + '. O navegador descarta a declaração inteira em silêncio — '
           + 'declare o token, ou dê um fallback se a ausência for esperada.')
  }
}

const css = cssPublicado()''',
      "1. a conferencia 10")

# ------------------------------------------------------------------ o runner
troca('''  aBarraDeEtapasRolaENaoQuebra(css)
}''',
      '''  aBarraDeEtapasRolaENaoQuebra(css)
  todoVarUsadoExiste(css)
}''',
      "2. entra no runner")

troca('''console.log('CSS publicado: as 9 conferências passaram (teto do diálogo, '
            + 'ordem da cascata, tokens no :root, empilhamento dos diálogos, '
            + 'teto e empilhamento do diálogo do chamado, camada dos controles '
            + 'de rolagem, forma do aviso da etapa, lista de etapas com largura estável, '
            + 'pílula com base no mesmo '
            + 'escopo)')''',
      '''console.log('CSS publicado: as 10 conferências passaram (teto do diálogo, '
            + 'ordem da cascata, tokens no :root, empilhamento dos diálogos, '
            + 'teto e empilhamento do diálogo do chamado, camada dos controles '
            + 'de rolagem, forma do aviso da etapa, lista de etapas com largura estável, '
            + 'pílula com base no mesmo '
            + 'escopo, todo var() com token declarado)')''',
      "3. a frase final diz 10")

saida = t.replace("\n", "\r\n") if CRLF else t
p.write_bytes(saida.encode("utf-8"))
print("gravado:", p, len(saida), "bytes")
