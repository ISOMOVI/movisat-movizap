<script setup>
/* ============================================================================
   CFG_7.1 — Geral. Os interruptores do SISTEMA.
   ----------------------------------------------------------------------------
   Pedido dele em 27/08: *"os acionadores dos interruptores devem ficar lá"*. Em
   28/08 ele mandou conferir se todos tinham chegado — e dois não tinham:

     🔴 `jornada_ativa` acionava em ATENDENTES (CAD_2.1), tela de cadastro.
        É interruptor do sistema: muda como a fila distribui. Estava escondido
        onde ninguém procura configuração -- o mesmo padrão que motivou a
        escada da IA.

     🔴 `avaliacao_ativa` não tinha acionador em tela NENHUMA. A chave existe no
        banco, com descrição, e não havia como ligá-la pelo painel.

   🚨 A LEITURA CONTINUA EM ATENDENTES, SÓ A CHAVE MUDOU DE LUGAR. Aquela tela
   precisa do estado para marcar quem está fora do horário; o que saiu de lá foi
   o BOTÃO. Interruptor tem um lugar só; estado se lê onde faz falta.

   ⚠️ `avaliacao_ativa` aparece TRAVADA, com o motivo escrito -- é a regra que
   ele aprovou na escada da IA: nada some, e o que não dá para usar diz o que
   falta. Ligar um interruptor cujo comportamento não existe seria pior que
   escondê-lo.
   ============================================================================ */
import { ref, onMounted } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'

const carregando = ref(true)
const salvando = ref(false)
const erro = ref('')
const recado = ref('')
const jornadaAtiva = ref(false)

async function carregar() {
  carregando.value = true
  try {
    jornadaAtiva.value = (await api.get('/api/config/jornada')).jornada_ativa
    erro.value = ''
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui ler.'
  } finally {
    carregando.value = false
  }
}

async function alternarJornada() {
  salvando.value = true
  recado.value = ''
  try {
    const r = await api.put('/api/config/jornada', { ligada: !jornadaAtiva.value })
    jornadaAtiva.value = r.jornada_ativa
    recado.value = jornadaAtiva.value
      ? 'Jornada ligada: a fila passa a avisar quem está fora do horário.'
      : 'Jornada desligada: a escala continua gravada e não afeta a fila.'
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui mudar.'
  } finally {
    salvando.value = false
  }
}

onMounted(carregar)
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Geral</h1>
        <AjudaDaTela>
          Os interruptores que valem para o painel inteiro. Os que são por
          canal, por tipo ou por pessoa ficam nas abas deles.
        </AjudaDaTela>
      </div>
    </header>

    <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>
    <p v-if="recado" class="aviso aviso--ok" role="status">{{ recado }}</p>
    <p v-if="carregando" class="linha fraco"><span class="girando"></span> Lendo…</p>

    <section class="cartao tela__bloco">
      <div class="cartao__corpo pilha">
        <label class="interruptor">
          <input type="checkbox" :checked="jornadaAtiva" :disabled="salvando"
                 @change="alternarJornada" />
          <span><strong>Usar a jornada dos atendentes na fila</strong></span>
        </label>
        <p class="apagado pequeno">
          Desligada, a escala fica gravada e não afeta a fila. Monta-se com
          calma; ligar é ato separado.
        </p>
        <p class="apagado pequeno">
          A escala de cada pessoa se monta em <strong>Atendentes</strong>.
        </p>
      </div>
    </section>

    <!-- ⚠️ TRAVADO, NÃO ESCONDIDO. A chave `avaliacao_ativa` existe no banco
         desde o começo e não tinha acionador em tela nenhuma: ficava invisível.
         Aparecer cinza, dizendo o que falta, é a regra que ele aprovou. -->
    <section class="cartao tela__bloco">
      <div class="cartao__corpo pilha">
        <label class="interruptor interruptor--travado">
          <input type="checkbox" disabled
                 title="A avaliação ainda não existe no atendimento" />
          <span><strong>Pedir nota de 1 a 5 ao encerrar a conversa</strong></span>
        </label>
        <p class="aviso aviso--atencao">
          <i class="bi bi-hourglass-split aviso__icone" aria-hidden="true"></i>
          <span>
            A avaliação ainda não existe no atendimento — ligar aqui não faria
            nada. O interruptor aparece para você saber que ele existe.
          </span>
        </p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.interruptor { display: flex; align-items: center; gap: var(--e-3); cursor: pointer; }
.interruptor input { width: 18px; height: 18px; accent-color: var(--acento); }
.interruptor--travado { cursor: not-allowed; color: var(--texto-apagado); }
</style>
