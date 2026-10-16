"""Bloco 12 na tela: "visto por" na nota interna (15/10).

🔵 *"um icone que ao clicar mostra que ja leu aquela nota, junto ao carimbo de
data e hora, bem pequeno mesmo"*.

🚨 O ROTULO E "VISTO POR", NUNCA "LEU". A tela sabe que a nota ESTEVE NA TELA
de alguem; nao sabe que a pessoa leu. Esta e a ressalva que nao se contorna.

Uso: ./venv/bin/python scripts/patch_bloco12_frontend.py [--conferir]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ALVO = RAIZ / "frontend" / "src" / "telas" / "CaixaDeEntrada.vue"
SO_CONFERIR = "--conferir" in sys.argv

PASSOS: list[tuple[str, str, str]] = []


def passo(nome, velho, novo):
    PASSOS.append((nome, velho, novo))


passo("script: o estado e o observador de notas",
      """const ICONE_EVENTO = {""",
      """/* ---- "VISTO POR" NA NOTA (Bloco 12, 15/10) -------------------------------
   🔵 *"um icone que ao clicar mostra que ja leu aquela nota, junto ao carimbo
   de data e hora, bem pequeno mesmo"*.

   🚨 MARCA QUANDO A NOTA APARECE NA TELA, não quando a conversa abre. Abrir
   uma conversa de 200 mensagens e não rolar até o fim não é ver a nota que
   está lá atrás -- carimbar isso seria inventar o dado. Daí o
   `IntersectionObserver`: ele é a única coisa que sabe o que está visível.

   🚨 E O RÓTULO É "VISTO POR", NUNCA "LEU": o sistema sabe que a nota esteve
   na tela, não que a pessoa leu. Dizer "leu" vira prova de algo que não se
   mediu, e alguém cobra com base nisso.

   ⚠️ EM LOTE, com espera: rolar a conversa passa por dezenas de notas, e uma
   requisição por nota seria uma rajada. Junta e manda uma vez. */
const vistoAberto = ref(null)
const notasParaMarcar = new Set()
let observadorDeNotas = null
let timerDeNotas = null

function alternarVisto(id) {
  vistoAberto.value = vistoAberto.value === id ? null : id
}

async function mandarNotasVistas() {
  timerDeNotas = null
  const ids = [...notasParaMarcar]
  notasParaMarcar.clear()
  if (!ids.length || !aberta.value) return
  try {
    await api.post(`/api/conversas/${aberta.value.id}/notas/vistas`, { ids })
  } catch {
    /* ⚠️ Falhar aqui não pode virar erro na tela: a pessoa está LENDO, e não
       pediu nada. O carimbo se perde e a nota será marcada na próxima vez em
       que aparecer. */
  }
}

function olharAsNotas() {
  pararDeOlharAsNotas()
  if (typeof IntersectionObserver === 'undefined') return
  observadorDeNotas = new IntersectionObserver((entradas) => {
    for (const e of entradas) {
      if (!e.isIntersecting) continue
      const id = Number(e.target.dataset.nota)
      if (id) notasParaMarcar.add(id)
      // Uma vez visto, não precisa ser observado de novo.
      observadorDeNotas.unobserve(e.target)
    }
    if (notasParaMarcar.size && !timerDeNotas) {
      timerDeNotas = setTimeout(mandarNotasVistas, 1200)
    }
  }, { threshold: 0.6 })
  nextTick(() => {
    document.querySelectorAll('[data-nota]').forEach((el) => {
      observadorDeNotas?.observe(el)
    })
  })
}

function pararDeOlharAsNotas() {
  observadorDeNotas?.disconnect()
  observadorDeNotas = null
  if (timerDeNotas) {
    clearTimeout(timerDeNotas)
    timerDeNotas = null
  }
  // O que já estava visto vai agora: fechar a conversa não apaga o fato.
  if (notasParaMarcar.size) mandarNotasVistas()
}

const ICONE_EVENTO = {""")

passo("template: o ícone ao lado da hora, e o popover",
      """                <span v-if="TIQUE[m.entrega]"
                      class="balao__tique"
                      :class="{ 'balao__lida': m.entrega === 'lida' }"
                      :title="m.entrega">{{ TIQUE[m.entrega] }}</span>
                <span v-else-if="m.entrega"> · {{ m.entrega }}</span>
              </p>""",
      """                <span v-if="TIQUE[m.entrega]"
                      class="balao__tique"
                      :class="{ 'balao__lida': m.entrega === 'lida' }"
                      :title="m.entrega">{{ TIQUE[m.entrega] }}</span>
                <span v-else-if="m.entrega"> · {{ m.entrega }}</span>

                <!-- 🔵 15/10, Bloco 12: "visto por", junto ao carimbo, bem
                     pequeno -- do tamanho que ele pediu.
                     🚨 O OLHO NÃO DIZ "LIDA". Ele diz quantas pessoas tiveram
                     a nota na tela, e o popover diz quem e quando. -->
                <button v-if="m.tipo === 'nota'" type="button" class="balao__visto"
                        :aria-expanded="vistoAberto === m.id"
                        title="quem teve esta nota na tela"
                        @click.stop="alternarVisto(m.id)">
                  · <i class="bi"
                       :class="m.vistos && m.vistos.length ? 'bi-eye-fill' : 'bi-eye'"
                       aria-hidden="true"></i>
                  <template v-if="m.vistos && m.vistos.length">{{ m.vistos.length }}</template>
                </button>
              </p>

              <!-- O popover do "visto por". Fora do rodapé porque pode ter
                   várias linhas, e o rodapé é de uma. -->
              <p v-if="m.tipo === 'nota' && vistoAberto === m.id"
                 class="balao__vistos pequeno">
                <!-- 🚨 "NÃO HAVIA REGISTRO" NÃO É "NINGUÉM VIU". Nota anterior
                     ao início do registro não pode aparecer como não vista por
                     ninguém: seria uma afirmação falsa sobre o passado.
                     ⚠️ Sem data escrita aqui: a data mora no backend
                     (`LEITURA_DE_NOTA_DESDE`), e repeti-la na tela criaria uma
                     segunda verdade para divergir no dia em que ela mudar. -->
                <template v-if="!m.leitura_rastreada">
                  Sem registro: esta nota é anterior ao dia em que o MoviZap
                  passou a anotar quem vê.
                </template>
                <template v-else-if="!m.vistos || !m.vistos.length">
                  Ninguém teve esta nota na tela ainda.
                </template>
                <template v-else>
                  <strong>Visto por</strong>
                  <span v-for="v in m.vistos" :key="v.atendente_id"
                        class="balao__visto-quem">
                    {{ v.nome }} <span class="apagado">{{ hora(v.visto_em) }}</span>
                  </span>
                </template>
              </p>""")

passo("template: a nota ganha a marca que o observador procura",
      """              :data-mensagem="m.id"
              @click="tocarBalao(m, $event)"
            >""",
      """              :data-mensagem="m.id"
              :data-nota="m.tipo === 'nota' && m.leitura_rastreada ? m.id : null"
              @click="tocarBalao(m, $event)"
            >""")

passo("abrir(): o observador é da conversa aberta",
      """    rolarParaOFim()
    recado.value = ''""",
      """    rolarParaOFim()
    // 🔵 15/10, Bloco 12: quem olha as notas é remontado por conversa -- os
    // elementos são outros, e o que estava pendente vai antes de trocar.
    vistoAberto.value = null
    olharAsNotas()
    recado.value = ''""")

passo("script: nota nova (do refresh de 8s) também passa a ser olhada",
      """function pararDeOlharAsNotas() {""",
      """/* ⚠️ O refresh de 8s e o "carregar anteriores" trazem nota nova, e elemento
   novo não nasce observado. Sem este `watch`, nota que chegasse depois da
   abertura nunca seria marcada -- e o recurso pareceria funcionar, porque as
   antigas aparecem certas. */
watch(() => aberta.value?.mensagens?.length, () => {
  if (aberta.value) olharAsNotas()
})

function pararDeOlharAsNotas() {""")

passo("onUnmounted: solta o observador",
      """  guardarRascunho()
  soltarPlayerLigacao()""",
      """  guardarRascunho()
  soltarPlayerLigacao()
  pararDeOlharAsNotas()""")

passo("estilo: o olho e o popover",
      """.evento__hora { margin-left: auto; flex: none; font-size: var(--txt-xs); }""",
      """.evento__hora { margin-left: auto; flex: none; font-size: var(--txt-xs); }

/* 🔵 15/10, Bloco 12 — "visto por" na nota. `bem pequeno mesmo`, no tamanho do
   carimbo, e com alvo de toque decente mesmo sendo pequeno de desenho. */
.balao__visto {
  appearance: none;
  border: 0;
  background: none;
  padding: 0 2px;
  margin: 0;
  font: inherit;
  color: inherit;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.balao__visto:hover { color: var(--texto-fraco); }
.balao__vistos {
  display: flex;
  flex-direction: column;
  gap: 1px;
  margin: var(--e-1) 0 0;
  padding: var(--e-2);
  border-radius: var(--r-sm);
  background: var(--superficie-2);
  color: var(--texto-fraco);
}
.balao__visto-quem { display: flex; gap: var(--e-2); justify-content: space-between; }""")


def aplicar():
    texto = ALVO.read_text(encoding="utf-8")
    feitos, pulados = [], []
    for nome, velho, novo in PASSOS:
        if novo in texto:
            pulados.append(nome)
            continue
        n = texto.count(velho)
        if n != 1:
            raise SystemExit(f"ANCORA {n}x em '{nome}': {velho[:70]!r}")
        texto = texto.replace(velho, novo, 1)
        feitos.append(nome)
    if not SO_CONFERIR and feitos:
        ALVO.write_text(texto, encoding="utf-8")
    for n in feitos:
        print(f"  {'conferido' if SO_CONFERIR else 'aplicado'}: {n}")
    for n in pulados:
        print(f"  ja aplicado: {n}")


aplicar()
