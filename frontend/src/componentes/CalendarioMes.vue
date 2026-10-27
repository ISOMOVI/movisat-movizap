<script setup>
/* ============================================================================
   A grade de um mês — UM calendário, duas telas.
   ----------------------------------------------------------------------------
   🚨 ESTE ARQUIVO EXISTE PORQUE O MESMO CALENDÁRIO ESTAVA ESCRITO DUAS VEZES.
   Até 26/10 a grade do mês vivia copiada em `componentes/ModalAgendar.vue`
   (linhas 787-815) e em `telas/Agendamentos.vue` (381-408): a mesma conta dos
   vazios antes do dia 1, o mesmo `andarMes`, o mesmo `rotuloDoMes`, e o CSS
   quase igual -- com medidas diferentes (34px de coluna ali, 36px aqui) por
   nenhuma razão. Dois lugares para o mesmo defeito, e foi o que aconteceu: o
   toque de 44px entrou num e não no outro.

   🚨 O QUE ESTE COMPONENTE NÃO FAZ: ele não escolhe hora, não carrega nada e
   não sabe o que é um agendamento. Ele mostra um mês e avisa qual dia foi
   clicado. Quem decide o que isso significa é a tela:
     · no `ModalAgendar`, escolher o dia preenche o `quando` (preservando a
       hora já escolhida);
     · na `ATD_7.1`, escolher o dia move a âncora do carrossel e recarrega.

   ⚠️ O SELO DE "TEM SERVIÇO" CONTINUA FORA DAQUI, de propósito (era a
   justificativa escrita na `ATD_7.1`): o que está carregado é a semana da
   âncora, então o mês saberia de uns dias e não de outros -- e um mês com
   pontos em três dias afirmaria que nos outros não há nada. Tela que mente é
   defeito. Quem precisa dizer isso usa o slot `nota`.

   ⚠️ O CURSOR DO MÊS NÃO SEGUE O `selecionado`, e isso é o comportamento de
   antes, preservado de propósito: nas duas telas o mês abria no mês de hoje e
   só andava pelas setas. Fazê-lo pular junto seria mudança de comportamento
   escondida dentro de uma extração.
   ============================================================================ */
import { computed, ref } from 'vue'

const props = defineProps({
  /* O dia em destaque, em `AAAA-MM-DD`. */
  selecionado: { type: String, default: '' },
  /* Em que mês a grade abre. Vazio = o mês de hoje. */
  mesDe: { type: String, default: '' },
  /* Marcar os dias já passados. ⚠️ MARCAR NÃO É BARRAR: remarcar serviço que
     já aconteceu é caso real, e quem avisa é a tela, pelo slot `nota`. */
  marcarPassado: { type: Boolean, default: false },
})
const emit = defineEmits(['escolher'])

const SEMANA = ['D', 'S', 'T', 'Q', 'Q', 'S', 'S']

function iso(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
         + `-${String(d.getDate()).padStart(2, '0')}`
}

/* Meio-dia, sempre: `new Date(ano, mes, 1)` à meia-noite mais horário de verão
   dá o dia anterior em alguns fusos, e o mês nasceria deslocado. */
function primeiroDoMes(d) {
  return new Date(d.getFullYear(), d.getMonth(), 1, 12, 0, 0)
}

const hojeIso = iso(new Date())
const mesCursor = ref(primeiroDoMes(
  props.mesDe ? new Date(`${props.mesDe}T12:00:00`) : new Date()))

const rotuloDoMes = computed(() =>
  mesCursor.value.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' }))

const diasDoMes = computed(() => {
  const base = mesCursor.value
  const primeiro = primeiroDoMes(base)
  const lista = []
  // Os vazios antes do dia 1, para o dia cair na coluna do seu dia da semana.
  for (let i = 0; i < primeiro.getDay(); i += 1) lista.push(null)
  const d = new Date(primeiro)
  while (d.getMonth() === base.getMonth()) {
    const dia = iso(d)
    lista.push({ iso: dia, dia: d.getDate(), hoje: dia === hojeIso,
                 passado: dia < hojeIso })
    d.setDate(d.getDate() + 1)
  }
  return lista
})

function andarMes(passo) {
  const d = new Date(mesCursor.value)
  d.setMonth(d.getMonth() + passo)
  mesCursor.value = new Date(d.getFullYear(), d.getMonth(), 1, 12, 0, 0)
}

defineExpose({ andarMes })
</script>

<template>
  <div class="cal">
    <header class="cal__topo">
      <button class="botao botao--fantasma" type="button"
              aria-label="Mês anterior" @click="andarMes(-1)">
        <i class="bi bi-chevron-left" aria-hidden="true"></i>
      </button>
      <strong class="cal__rotulo">{{ rotuloDoMes }}</strong>
      <button class="botao botao--fantasma" type="button"
              aria-label="Mês seguinte" @click="andarMes(1)">
        <i class="bi bi-chevron-right" aria-hidden="true"></i>
      </button>
    </header>

    <div class="cal__grade">
      <span v-for="(s, i) in SEMANA" :key="`s${i}`" class="cal__semana">{{ s }}</span>
      <template v-for="(d, i) in diasDoMes" :key="d ? d.iso : `v${i}`">
        <span v-if="!d" class="cal__vago"></span>
        <button
          v-else
          type="button"
          class="cal__dia"
          :class="{ 'cal__dia--ativo': d.iso === selecionado,
                    'cal__dia--hoje': d.hoje,
                    'cal__dia--passado': marcarPassado && d.passado }"
          :aria-current="d.iso === selecionado ? 'date' : undefined"
          @click="emit('escolher', d.iso)"
        >{{ d.dia }}</button>
      </template>
    </div>

    <!-- O que a tela precisa dizer sobre o próprio mês. Fica aqui para o aviso
         ficar junto da grade de que ele fala. -->
    <slot name="nota" />
  </div>
</template>

<style scoped>
.cal { display: flex; flex-direction: column; gap: var(--e-2); }

.cal__topo {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--e-2);
}
.cal__rotulo { text-transform: capitalize; }

/* 🚨 44px NÃO É ESTÉTICA (`docs/02_Padrao_Visual` §3), e isto é tela que se usa
   no celular. As duas cópias antigas tinham 34px e 36px de coluna com 30px de
   altura -- abaixo do alvo de toque, e cada uma com um número diferente. */
.cal__grade {
  display: grid;
  grid-template-columns: repeat(7, minmax(var(--altura-toque), 1fr));
  gap: 3px;
}
.cal__semana { text-align: center; font-size: var(--txt-xs); color: var(--texto-fraco); }
.cal__vago { display: block; }

.cal__dia {
  min-height: var(--altura-toque);
  border: var(--borda-fina) solid transparent;
  border-radius: var(--r-sm);
  background: var(--superficie-2);
  color: inherit;
  cursor: pointer;
}
.cal__dia--hoje { border-color: var(--acento); }
.cal__dia--ativo { background: var(--acento); color: #fff; }
/* Apagado, não riscado nem desabilitado: dia passado se agenda. */
.cal__dia--passado { color: var(--texto-fraco); }
</style>
