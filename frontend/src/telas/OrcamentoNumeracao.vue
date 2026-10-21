<script setup>
/* ============================================================================
   CFG_13.1 — a numeração do orçamento. 🔵 Decisão 9 dele (19/10): numeração
   própria do MoviZap, com aba de configuração **exclusiva do owner**.
   ----------------------------------------------------------------------------
   🚨 A TELA AVISA, EM TEXTO, o que o número faz. O sistema de orçamento atual
   segue existindo FORA desta VPS, e baixar o próximo número pode fazer este
   painel emitir um documento com número já usado lá. Interruptor que não diz
   a consequência é o mesmo defeito do "Não perturbe" que não perturbava.
   ============================================================================ */
import { onMounted, ref } from 'vue'

import { api } from '../api/cliente.js'

const proximo = ref(null)
const digitado = ref('')
const carregando = ref(true)
const salvando = ref(false)
const erro = ref('')
const salvo = ref(false)

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    const r = await api.get('/api/config/orcamento-numero')
    proximo.value = r.proximo_numero
    digitado.value = String(r.proximo_numero)
  } catch (e) {
    erro.value = e?.message || 'Não deu para ler a numeração.'
  } finally {
    carregando.value = false
  }
}

async function salvar() {
  const numero = Number(digitado.value)
  if (!Number.isInteger(numero) || numero < 1) {
    erro.value = 'O número tem de ser inteiro e começar em 1.'
    return
  }
  salvando.value = true
  erro.value = ''
  salvo.value = false
  try {
    const r = await api.put('/api/config/orcamento-numero', { proximo_numero: numero })
    // Relê o que o servidor gravou, em vez de confiar no que mandei: a
    // confirmação é o estado, nunca o retorno do comando.
    proximo.value = r.proximo_numero
    digitado.value = String(r.proximo_numero)
    salvo.value = true
  } catch (e) {
    erro.value = e?.message || 'Não deu para gravar.'
  } finally {
    salvando.value = false
  }
}

onMounted(carregar)
</script>

<template>
  <section class="orcnum">
    <h2 class="orcnum__titulo">Numeração do orçamento</h2>
    <p class="orcnum__texto">
      É o número que o <b>próximo</b> orçamento emitido por este painel vai
      receber. Ele sobe sozinho a cada documento gerado.
    </p>

    <p class="aviso aviso--atencao">
      Mudar este número pode fazer o painel <b>repetir um documento já
      emitido</b> pelo sistema de orçamento atual, que segue existindo fora
      daqui. O número só é gasto quando o PDF é gerado — abrir e fechar o
      modal não consome numeração.
    </p>

    <p v-if="carregando" class="orcnum__texto">Lendo…</p>

    <div v-else class="orcnum__campo">
      <label for="orcnum-proximo">Próximo número</label>
      <input
        id="orcnum-proximo"
        v-model="digitado"
        type="number"
        min="1"
        step="1"
        inputmode="numeric"
        class="campo__entrada"
      />
      <button class="botao" type="button" :disabled="salvando" @click="salvar">
        {{ salvando ? 'Gravando…' : 'Gravar' }}
      </button>
    </div>

    <p v-if="erro" class="aviso aviso--erro">{{ erro }}</p>
    <p v-else-if="salvo" class="aviso aviso--ok">
      Gravado. O próximo orçamento sai com o número {{ proximo }}.
    </p>
  </section>
</template>

<style scoped>
.orcnum { display: flex; flex-direction: column; gap: var(--e-3); max-width: 640px; }
.orcnum__titulo { margin: 0; font-size: var(--txt-lg); }
.orcnum__texto { margin: 0; color: var(--texto-fraco); font-size: var(--txt-sm); }
.orcnum__campo { display: flex; align-items: flex-end; gap: var(--e-3); flex-wrap: wrap; }
.orcnum__campo label {
  display: flex;
  flex-direction: column;
  gap: var(--e-1);
  font-size: var(--txt-sm);
  font-weight: var(--peso-forte);
}
/* 16px: abaixo disso o iOS dá zoom ao focar o campo (padrão dos quatro painéis). */
.orcnum__campo .campo__entrada { width: 180px; font-size: 16px; }
</style>
