# -*- coding: utf-8 -*-
"""Os dois controles de rolagem entram na ESCALA de z-index da casa (06/11).

🚨 Eu escrevi `z-index: 3` e `z-index: 2` CRUS. A casa tem escala declarada em
`tokens.css` -- `--z-conteudo: 1`, `--z-barra: 50`, `--z-flutuante: 100`,
`--z-modal: 200` -- e numero inventado e exatamente o que a escala existe para
evitar: funciona hoje e nao acompanha uma mudanca futura da escala.

Acrescenta `--z-rolagem: 5` (acima do conteudo, muito abaixo da barra de status
e do modal) e troca os dois numeros crus. ⚠️ Nao e regra de negocio: e a
convencao interna da casa, e usa-la e o conserto.
"""
import pathlib
import sys

RAIZ = pathlib.Path("/home/claude/movizap_painel")

# ------------------------------------------------------------- 1. o token
P = RAIZ / "frontend/src/estilo/tokens.css"
t = P.read_text(encoding="utf-8")
if "--z-rolagem" in t:
    print("  tokens.css: ja aplicado")
else:
    ANCORA = "  --z-barra:    50;"
    if t.count(ANCORA) != 1:
        sys.exit(f"tokens.css: ancora apareceu {t.count(ANCORA)}x")
    NOVO = (
        "  /* 🔵 06/11: os controles de rolagem do quadro (a barra grudada no\n"
        "     alto e as faixas da borda). Acima do conteúdo e MUITO abaixo da\n"
        "     barra de status e do modal: controle de rolagem por cima de um\n"
        "     diálogo é o defeito de camada que a conferência do CSS caça.\n"
        "     ⚠️ A barra usa `calc(var(--z-rolagem) + 1)` para ficar sobre as\n"
        "     faixas -- as duas vivem no mesmo quadro e a ordem entre elas não\n"
        "     pode depender da ordem do template. */\n"
        "  --z-rolagem:   5;\n"
        + ANCORA
    )
    P.write_text(t.replace(ANCORA, NOVO), encoding="utf-8")
    print("  tokens.css: --z-rolagem acrescentado")

# -------------------------------------------------------- 2. os componentes
for arquivo, velho, novo in [
    ("frontend/src/componentes/BarraDeRolagem.vue",
     "  z-index: 3;", "  z-index: calc(var(--z-rolagem) + 1);"),
    ("frontend/src/componentes/RolagemDaBorda.vue",
     "  z-index: 2;", "  z-index: var(--z-rolagem);"),
]:
    P = RAIZ / arquivo
    t = P.read_text(encoding="utf-8")
    if "--z-rolagem" in t:
        print(f"  {P.name}: ja aplicado")
        continue
    if t.count(velho) != 1:
        sys.exit(f"{P.name}: ancora {velho!r} apareceu {t.count(velho)}x")
    P.write_text(t.replace(velho, novo), encoding="utf-8")
    print(f"  {P.name}: usa a escala")

# ------------------------------------------- 3. a 6a conferencia no CSS publicado
P = RAIZ / "frontend/scripts/conferir_css_publicado.mjs"
t = P.read_text(encoding="utf-8")
if "osControlesDeRolagem" in t:
    print("  conferir_css_publicado.mjs: ja aplicado")
    sys.exit(0)

CONF = '''
/* ------------------------------------------------------------------ 6 */
function osControlesDeRolagemFicamNaCamadaCerta(css) {
  /* 🚨 06/11, a camada NOVA. A barra grudada no alto e as faixas da borda
     ficam POR CIMA do quadro -- e camada nova e justamente o tipo de regra que
     some numa cascata sem nenhum teste de tela notar: o jsdom nao pinta.

     ⚠️ E ha um segundo defeito possivel, pior: a faixa esconde-se em
     `@media (hover: none)` para nao comer a area de arrastar no celular. Se
     essa regra ESCAPAR da media query, a faixa desaparece para TODOS -- foi
     exatamente o que um `max-width` global fez com o modal em 05/11. */
  const barra = regra(css, '.barrarolo')
  if (!barra) {
    return falhar('.barrarolo não existe no CSS publicado — a barra de '
                  + 'rolagem do quadro não subiu.')
  }
  if (!/position:\\s*sticky/.test(barra.corpo)) {
    falhar('.barrarolo não é `sticky` — ela voltaria a ficar no pé do quadro, '
           + 'que é a queixa que ela existe para resolver.')
  }
  const zb = prop(barra.corpo, 'z-index') || ''
  if (!zb.includes('--z-rolagem')) {
    falhar('.barrarolo não usa a escala `--z-rolagem` (achei ' + (zb || 'nada')
           + '). Número cru funciona hoje e não acompanha a escala amanhã.')
  }

  const faixa = regra(css, '.borda')
  if (!faixa) {
    return falhar('.borda não existe no CSS publicado — as faixas de rolagem '
                  + 'não subiram.')
  }
  const zf = prop(faixa.corpo, 'z-index') || ''
  if (!zf.includes('--z-rolagem')) {
    falhar('.borda não usa a escala `--z-rolagem` (achei ' + (zf || 'nada') + ').')
  }
  if (!/pointer-events:\\s*none/.test(faixa.corpo)) {
    falhar('.borda não tem `pointer-events: none` — ela cobriria o quadro '
           + 'inteiro e nenhum card seria clicável.')
  }

  /* 🚨 O `display:none` da faixa TEM de estar dentro de `@media (hover: none)`.
     Fora dela, a faixa desaparece para todo mundo. */
  const escondido = [...css.matchAll(/\\.borda(\\[[^\\]]*\\])?\\s*\\{\\s*display:\\s*none/g)]
  for (const m of escondido) {
    const antes = css.slice(0, m.index)
    const abriu = antes.lastIndexOf('@media')
    const fechou = antes.lastIndexOf('}')
    if (!(abriu > fechou)) {
      falhar('`.borda { display: none }` está FORA de uma media query no CSS '
             + 'publicado: as faixas de rolagem ficariam invisíveis para '
             + 'todos, em qualquer tela.')
    }
  }
}
'''

ANCORA = "/* ------------------------------------------------------------------ 5 */"
if t.count(ANCORA) != 1:
    sys.exit(f"conferencia: ancora apareceu {t.count(ANCORA)}x")

# A funcao 6 entra depois da 5; acha o fim da funcao 5 pelo proximo bloco.
i = t.index(ANCORA)
fim = t.index("\n/* ", i + len(ANCORA))
t = t[:fim] + "\n" + CONF + t[fim:]

# E a chamada, na lista de conferencias.
import re  # noqa: E402

m = re.search(r"oDialogoDoChamadoTemTetoProprioENaoEmpata\(css\)", t[fim:])
if not m:
    sys.exit("nao achei a chamada da 5a conferencia")
alvo = "oDialogoDoChamadoTemTetoProprioENaoEmpata(css)"
# A ultima ocorrencia e a chamada (a primeira e a definicao).
pos = t.rfind(alvo)
t = t[:pos + len(alvo)] + "\n  osControlesDeRolagemFicamNaCamadaCerta(css)" + t[pos + len(alvo):]

# O texto do sucesso menciona as conferencias.
t = t.replace("as 5 conferências passaram", "as 6 conferências passaram")
t = t.replace("teto e empilhamento do diálogo do chamado)",
              "teto e empilhamento do diálogo do chamado, camada dos controles "
              "de rolagem)")

P.write_text(t, encoding="utf-8")
print("  conferir_css_publicado.mjs: 6a conferencia")
