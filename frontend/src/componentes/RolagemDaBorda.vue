<script setup>
/* ============================================================================
   ROLAGEM PELA BORDA — o mouse sobreposto anda com o quadro (06/11).
   ----------------------------------------------------------------------------
   🔵 Pedido dele: *"sabe quando deixamos o mouse a direita e esquerda sobre
   'botões' e a tela se desloca suavemente para o lado? precisamos disso nos
   paineis"* · *"o mouse ficando parado ou o scrol ficando na tela tbm
   resolve"* · e a decisão: *"pode ligar a rolagem horizontal via mouse
   sobreposto"*.

   ⚠️ **ELE DECIDIU CONTRA A MINHA RECOMENDAÇÃO, e está escrito aqui para não
   ser "corrigido" depois.** Eu propus a faixa só DURANTE O ARRASTE, porque
   faixa sempre ativa cobre a borda do quadro e é um controle invisível. Ele
   mandou ligar no mouse sobreposto. A faixa serve os dois casos.

   🚨 **A PAUSA DE 150ms NÃO É ENFEITE, é o conserto do único risco real.** O
   menu lateral fica à ESQUERDA da área de conteúdo: todo caminho do quadro
   para o menu cruza a faixa esquerda. Sem a pausa, ir ao menu rolaria o quadro
   junto — e a pessoa perderia a coluna que estava olhando sem ter pedido nada.
   ⚠️ E a pausa é exatamente o que ele descreveu: *"o mouse FICANDO PARADO"*.

   🚨 **ARRASTE NÃO EMITE `mouseenter`.** Durante um arraste HTML5 o navegador
   emite `dragover`, não `mousemove` — uma versão que só escutasse o mouse
   funcionaria no uso normal e falharia **exatamente** no caso que mais
   importa: arrastar um card para uma coluna fora da tela, que hoje é
   impossível. Daí os dois caminhos, e a trava que prova o segundo.
   ⚠️ No arraste **não há pausa**: quem está com o card na mão já decidiu.

   ⚠️ **A FAIXA NÃO RECEBE `drop`.** Soltar o card sobre ela tem de devolvê-lo
   para onde estava, não sumir com ele — por isso ela não tem `@drop` e o
   `dragover` chama `preventDefault` só para o navegador não recusar a área.

   🚨 **NÃO EXISTE SE NÃO HÁ PARA ONDE ROLAR**, e cada lado desaparece no seu
   fim: faixa que não anda nada é controle morto (o precedente do
   `ModalAgendar`).
   ============================================================================ */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  rolo: { type: Object, default: null },
  /* Rótulo do que se rola, para quem usa leitor de tela. */
  rotulo: { type: String, default: 'quadro' },
})

/* Uma coluna é o passo do clique: 360px + o `gap`. */
const PASSO = 376
/* A pausa antes de começar a rolar com o ponteiro. Ver o cabeçalho. */
const PAUSA_MS = 150
const LENTO = 240
const RAPIDO = 900
const LARGURA = 48

const esquerda = ref(0)
const visivel = ref(0)
const total = ref(0)
const ativa = ref('')

let quadroDeAnimacao = 0
let relogio = 0
let espera = 0
let direcao = 0
let forca = 1
let observador = null
let roloAtual = null

const menosMovimento = () =>
  typeof window !== 'undefined'
  && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

function medir() {
  const el = props.rolo
  if (!el) {
    total.value = 0
    return
  }
  total.value = el.scrollWidth
  visivel.value = el.clientWidth
  esquerda.value = el.scrollLeft
}

/* Tolerância de 2px: `scrollWidth` e `clientWidth` divergem por arredondamento
   de subpixel em zoom não inteiro, e sem ela a faixa piscaria em 110%. */
const transborda = computed(() => total.value - visivel.value > 2)
const podeEsquerda = computed(() => transborda.value && esquerda.value > 1)
const podeDireita = computed(
  () => transborda.value && esquerda.value < total.value - visivel.value - 1,
)

function parar() {
  cancelAnimationFrame(quadroDeAnimacao)
  clearTimeout(espera)
  quadroDeAnimacao = 0
  espera = 0
  direcao = 0
  ativa.value = ''
}

function passo(agora) {
  const el = props.rolo
  if (!el || !direcao) return
  const dt = relogio ? (agora - relogio) / 1000 : 0
  relogio = agora
  const velocidade = LENTO + (RAPIDO - LENTO) * forca
  el.scrollLeft += direcao * velocidade * dt
  medir()
  const acabou = direcao < 0 ? !podeEsquerda.value : !podeDireita.value
  if (acabou) {
    parar()
    return
  }
  quadroDeAnimacao = requestAnimationFrame(passo)
}

function comecar(lado, pausa) {
  const el = props.rolo
  if (!el) return
  if (lado === 'esquerda' && !podeEsquerda.value) return
  if (lado === 'direita' && !podeDireita.value) return
  if (menosMovimento()) {
    // Rolagem contínua é o que essa preferência existe para evitar: aqui o
    // gesto vira um pulo de coluna, e nada se move sozinho.
    andar(lado === 'direita' ? 1 : -1)
    return
  }
  if (ativa.value === lado && quadroDeAnimacao) return
  clearTimeout(espera)
  ativa.value = lado
  direcao = lado === 'direita' ? 1 : -1
  const arrancar = () => {
    relogio = 0
    quadroDeAnimacao = requestAnimationFrame(passo)
  }
  if (pausa) espera = setTimeout(arrancar, PAUSA_MS)
  else arrancar()
}

/* A força vem da distância até a borda EXTERNA: encostar na beirada é o
   pedido de "mais rápido", e é o gesto que a mão faz naturalmente. */
function calibrar(lado, ev) {
  const caixa = ev.currentTarget?.getBoundingClientRect?.()
  if (!caixa || !caixa.width) {
    forca = 0.5
    return
  }
  const dentro = lado === 'direita'
    ? (ev.clientX - caixa.left) / caixa.width
    : (caixa.right - ev.clientX) / caixa.width
  forca = Math.min(1, Math.max(0, dentro))
}

function noPonteiro(lado, ev) {
  calibrar(lado, ev)
  comecar(lado, true)
}

/* 🚨 O arraste: `dragover` em vez de `mousemove`, e SEM pausa. */
function noArraste(lado, ev) {
  ev.preventDefault()
  calibrar(lado, ev)
  comecar(lado, false)
}

function andar(passos) {
  const el = props.rolo
  if (!el) return
  const curso = el.scrollWidth - el.clientWidth
  el.scrollLeft = Math.max(0, Math.min(curso, el.scrollLeft + passos * PASSO))
  medir()
}

function ligar(el) {
  if (roloAtual === el) return
  desligar()
  roloAtual = el
  if (!el) return
  el.addEventListener('scroll', medir, { passive: true })
  if (typeof ResizeObserver !== 'undefined') {
    observador = new ResizeObserver(medir)
    observador.observe(el)
    if (el.firstElementChild) observador.observe(el.firstElementChild)
  }
  medir()
}

function desligar() {
  parar()
  if (roloAtual) roloAtual.removeEventListener('scroll', medir)
  observador?.disconnect()
  observador = null
  roloAtual = null
}

watch(() => props.rolo, (el) => ligar(el), { immediate: true })
onMounted(() => {
  window.addEventListener('resize', medir)
  ligar(props.rolo)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', medir)
  desligar()
})

defineExpose({ medir, largura: LARGURA })
</script>

<template>
  <!-- ⚠️ `pointer-events: none` no casco e `auto` só nas faixas: fora das duas
       tiras de 48px o quadro continua clicável como sempre. -->
  <div v-if="transborda" class="borda" aria-hidden="false">
    <button
      v-if="podeEsquerda"
      class="borda__faixa borda__faixa--esq"
      :class="{ 'borda__faixa--ativa': ativa === 'esquerda' }"
      type="button"
      :aria-label="`Rolar o ${rotulo} para a esquerda`"
      @pointerenter="noPonteiro('esquerda', $event)"
      @pointermove="noPonteiro('esquerda', $event)"
      @pointerleave="parar"
      @pointerdown.prevent="andar(-1)"
      @dragover="noArraste('esquerda', $event)"
      @dragleave="parar"
      @focus="null"
    >
      <span class="borda__seta" aria-hidden="true">‹</span>
    </button>
    <button
      v-if="podeDireita"
      class="borda__faixa borda__faixa--dir"
      :class="{ 'borda__faixa--ativa': ativa === 'direita' }"
      type="button"
      :aria-label="`Rolar o ${rotulo} para a direita`"
      @pointerenter="noPonteiro('direita', $event)"
      @pointermove="noPonteiro('direita', $event)"
      @pointerleave="parar"
      @pointerdown.prevent="andar(1)"
      @dragover="noArraste('direita', $event)"
      @dragleave="parar"
    >
      <span class="borda__seta" aria-hidden="true">›</span>
    </button>
  </div>
</template>

<style scoped>
.borda {
  position: absolute;
  inset: 0;
  pointer-events: none;
  /* ⚠️ Abaixo da barra de rolagem (3) e muito abaixo de qualquer diálogo: a
     conferência do CSS publicado prende esta ordem. */
  z-index: var(--z-rolagem);
}
.borda__faixa {
  position: absolute;
  inset-block: 0;
  width: 48px;
  margin: 0;
  padding: 0;
  border: 0;
  pointer-events: auto;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  /* 🔵 *"o contorno pode ser bem esmaecido"*: nada de caixa, nada de borda,
     nada de sombra. O contorno é o próprio gradiente morrendo. */
  opacity: 0;
  transition: opacity 120ms ease;
}
.borda__faixa:hover,
.borda__faixa:focus-visible,
.borda__faixa--ativa { opacity: 1; }
.borda__faixa:focus-visible { outline: 2px solid var(--acento); outline-offset: -2px; }
.borda__faixa--esq {
  left: 0;
  cursor: w-resize;
  background: linear-gradient(to right, var(--superficie), transparent);
}
.borda__faixa--dir {
  right: 0;
  cursor: e-resize;
  background: linear-gradient(to left, var(--superficie), transparent);
}
.borda__seta {
  /* A seta acompanha quem rolou para baixo, em vez de ficar no topo de um
     quadro de 3000px de altura. */
  position: sticky;
  top: 40vh;
  font-size: 28px;
  line-height: 1;
  color: var(--texto-fraco);
  user-select: none;
}
/* 🚨 EM TOQUE, NENHUMA DAS DUAS. No celular o dedo já arrasta o quadro, e 96px
   de faixa comeriam justamente a área que serve para arrastar. */
@media (hover: none) {
  .borda { display: none; }
}
</style>
