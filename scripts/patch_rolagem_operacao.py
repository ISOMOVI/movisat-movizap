# -*- coding: utf-8 -*-
"""Liga a barra no alto e a rolagem pela borda no painel da Operacao (06/11).

🔵 Ele: *"Ok go"* (a barra) e *"pode ligar a rolagem horizontal via mouse
sobreposto"* (a faixa).

Idempotente, com guard pela marca NOVA, e confere com grep no fim.
"""
import pathlib
import sys

P = pathlib.Path("/home/claude/movizap_painel/frontend/src/telas/PainelOperacao.vue")
t = P.read_text(encoding="utf-8")

if "BarraDeRolagem" in t:
    sys.exit("ja aplicado")

# ---------------------------------------------------------------- 1. imports
ANCORA_IMP = "import DialogoDeChamado from '../componentes/DialogoDeChamado.vue'"
if t.count(ANCORA_IMP) != 1:
    sys.exit(f"import: ancora apareceu {t.count(ANCORA_IMP)}x")
t = t.replace(
    ANCORA_IMP,
    ANCORA_IMP + "\n"
    "import BarraDeRolagem from '../componentes/BarraDeRolagem.vue'\n"
    "import RolagemDaBorda from '../componentes/RolagemDaBorda.vue'",
)

# ------------------------------------------------- 2. a referencia para o rolo
ANCORA_REF = "const arrastando = ref(null)"
if t.count(ANCORA_REF) != 1:
    sys.exit(f"ref: ancora apareceu {t.count(ANCORA_REF)}x")
t = t.replace(
    ANCORA_REF,
    "/* 🔵 06/11: o elemento do quadro, que os dois controles de rolagem\n"
    "   precisam. ⚠️ Vem por `ref` do template e NAO por `querySelector`: o\n"
    "   quadro nasce dentro de um `v-if`, e um seletor rodaria antes de ele\n"
    "   existir. */\n"
    "const rolo = ref(null)\n"
    + ANCORA_REF,
)

# --------------------------------------------- 3. o casco, a barra e as faixas
ANTIGO = '''      <div class="quadro">'''
NOVO = '''      <!-- 🔵 06/11, ele: *"precisamos disso nos paineis, pois o scroll ficou
           la embaixo"* · *"Ok go"* · *"pode ligar a rolagem horizontal via
           mouse sobreposto"*.

           🚨 O CASCO existe para as faixas terem onde se pendurar: elas sao
           `position: absolute` sobre a area visivel, e sem um ancestral
           `relative` se penduraim no casco do painel inteiro.

           ⚠️ A BARRA FICA FORA DO CASCO, e e de proposito: ela e `sticky` em
           relacao ao `.painel__conteudo` (que tem `overflow: auto`), e um
           ancestral `relative` com altura do quadro nao muda isso -- mas
           deixa-la DENTRO do casco a poria por baixo das faixas na mesma
           camada. Fora, a ordem fica explicita. -->
      <BarraDeRolagem :rolo="rolo" rotulo="quadro da Operação" />

      <div class="quadro__casco">
        <RolagemDaBorda :rolo="rolo" rotulo="quadro" />
        <div ref="rolo" class="quadro">'''
if t.count(ANTIGO) != 1:
    sys.exit(f"quadro: ancora apareceu {t.count(ANTIGO)}x")
t = t.replace(ANTIGO, NOVO)

# O `</div>` que fecha o `.quadro` precisa de um a mais para o casco. A
# estrutura: `<div class="quadro">` ... `</div>` e logo depois vem o fim do
# `v-if`. Acha o fechamento pela indentacao do bloco seguinte.
ANCORA_FIM = """        </section>
      </div>

      <!-- ============ O CHAMADO ABERTO (05/11) ============"""
if t.count(ANCORA_FIM) != 1:
    # Tenta achar o que vem depois do quadro para dar erro util.
    i = t.index('<div ref="rolo" class="quadro">')
    print("--- trecho depois do quadro, para achar o fechamento ---")
    print(t[i:i + 2000][-600:])
    sys.exit(f"fim do quadro: ancora apareceu {t.count(ANCORA_FIM)}x")
# ⚠️ So ACRESCENTA o fechamento do casco: as 250 linhas de dentro do quadro
# NAO sao reindentadas. Reindentar geraria um diff enorme por nada -- e diff
# grande e onde um erro de verdade se esconde.
t = t.replace(ANCORA_FIM, """        </section>
        </div>
      </div>

      <!-- ============ O CHAMADO ABERTO (05/11) ============""")

# ------------------------------------------------------------------- 4. o CSS
ANCORA_CSS = ".quadro { display: flex;"
if t.count(ANCORA_CSS) != 1:
    sys.exit(f"css: ancora apareceu {t.count(ANCORA_CSS)}x")
t = t.replace(
    ANCORA_CSS,
    "/* 🔵 06/11: o casco das faixas de rolagem. `relative` e tudo o que ele\n"
    "   faz -- as faixas se penduram nele, e o quadro continua sendo o unico\n"
    "   com `overflow-x`. */\n"
    ".quadro__casco { position: relative; }\n"
    + ANCORA_CSS,
)

P.write_text(t, encoding="utf-8")
print("PainelOperacao.vue: barra + faixas ligadas")

t = P.read_text(encoding="utf-8")
print("conferindo com grep:")
for p in ("BarraDeRolagem", "RolagemDaBorda", 'ref="rolo"',
          "quadro__casco", "const rolo = ref(null)"):
    print(f"  {p}: {t.count(p)}")
