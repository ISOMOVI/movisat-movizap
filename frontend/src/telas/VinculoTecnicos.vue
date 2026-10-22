<script setup>
/* ============================================================================
   CFG_14.1 — Vínculo dos técnicos. 🟡 Ponta 4 do plano: a rota de pendências
   do vínculo existia e **não tinha tela**.
   ----------------------------------------------------------------------------
   🚨 ESTA TELA NASCEU PARA FECHAR UMA PORTA TRANCADA. A rota
   `/api/tecnicos-harmonit/pendencias` entrou no ar em 21/10 e nenhuma tela a
   chamava: o dado existia, a casa já catalogou esse defeito, e rota sem tela é
   dado que ninguém vê. A alternativa honesta era tirar a rota.

   🚨 SÃO TRÊS BURACOS DIFERENTES, e é por isso que são três listas, e não um
   número só: cada um pede um trabalho de cadastro distinto, e somá-los
   esconderia o que fazer com cada caso. A regra está no `tecnico_vinculo.py`.

   🚨 ESTA TELA NÃO CONSERTA NADA, e diz isso. 🔵 Ele mediu o assunto em 21/10
   e a conclusão foi dele: *"nenhuma regra resolve -- é trabalho de cadastro"*.
   O que ela faz é mostrar o trabalho; quem vincula à mão é a ficha do contato,
   na conversa (o caminho que sustenta a exceção dele, o 6168 → Iago).

   ⚠️ LISTA VAZIA E PONTE FORA DO AR SÃO COISAS DIFERENTES. A varredura lê o
   cadastro pelo FPSL; se ele não responder, a tela diz que não deu para
   consultar -- e não "nenhuma pendência", que faria o cadastro parecer em dia.
   ============================================================================ */
import { computed, onMounted, ref } from 'vue'

import { api } from '../api/cliente.js'

const dados = ref(null)
const carregando = ref(true)
const erro = ref('')

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    dados.value = await api.get('/api/tecnicos-harmonit/pendencias')
  } catch (e) {
    // 🚨 `dados` volta a NULO: a tela não pode desenhar as três listas vazias
    // quando o que houve foi falha de consulta.
    dados.value = null
    erro.value = e?.message || 'Não deu para consultar o cadastro do Harmonit.'
  } finally {
    carregando.value = false
  }
}

const semCadastro = computed(() =>
  dados.value?.tecnicos_sem_cadastro_no_harmonit || [])
const semContato = computed(() =>
  dados.value?.cadastro_sem_contato_no_movizap || [])
const paraMarcar = computed(() => dados.value?.casam_e_nao_sao_do_tipo || [])

onMounted(carregar)
</script>

<template>
  <section class="vtc">
    <header class="vtc__topo">
      <h2 class="vtc__titulo">Vínculo dos técnicos com o cadastro do Harmonit</h2>
      <button class="botao botao--fantasma" type="button" :disabled="carregando"
              @click="carregar">
        {{ carregando ? 'Consultando…' : 'Reconsultar' }}
      </button>
    </header>

    <p class="aviso aviso--info vtc__nota">
      O vínculo é o que faz o compromisso do agendamento chegar ao técnico
      certo na OS do Harmonit. A varredura roda <b>1×/dia</b> e casa pelo
      telefone — o e-mail do técnico no cadastro do Harmonit é o número dele.
      Vínculo gravado à mão <b>ganha do telefone</b> e a varredura não encosta
      mais nele.
    </p>
    <p class="vtc__nota vtc__nota--fraca">
      Esta tela <b>mostra</b> o que falta; ela não conserta nada. Quem vincula à
      mão é a ficha do contato, dentro da conversa.
    </p>

    <p v-if="erro" class="aviso aviso--erro">{{ erro }}</p>
    <p v-if="carregando" class="vtc__vazio">Consultando o cadastro…</p>

    <template v-else-if="dados">
      <article class="vtc__bloco">
        <h3 class="vtc__bloco-titulo">
          Técnicos daqui sem cadastro no Harmonit
          <span class="vtc__conta">{{ semCadastro.length }}</span>
        </h3>
        <p class="vtc__bloco-nota">
          O contato está marcado como técnico aqui, e nenhum cadastro do
          Harmonit tem este número no e-mail. Enquanto estiver assim, o
          agendamento deste técnico <b>não</b> vai para a OS por telefone — só
          por vínculo à mão.
        </p>
        <ul v-if="semCadastro.length" class="vtc__lista">
          <li v-for="c in semCadastro" :key="c.contato_id">
            <b>{{ c.nome || 'sem nome' }}</b>
            <span class="vtc__fraco">{{ c.e164 }}</span>
          </li>
        </ul>
        <p v-else class="vtc__vazio">Nenhum.</p>
      </article>

      <article class="vtc__bloco">
        <h3 class="vtc__bloco-titulo">
          Cadastros do Harmonit sem contato aqui
          <span class="vtc__conta">{{ semContato.length }}</span>
        </h3>
        <p class="vtc__bloco-nota">
          O técnico existe no Harmonit e nenhum contato deste painel casa com
          ele. Normalmente é número que mudou, ou técnico que nunca escreveu
          para cá.
        </p>
        <ul v-if="semContato.length" class="vtc__lista">
          <li v-for="t in semContato" :key="t.tecnico_id">
            <b>{{ t.nome }}</b>
            <span class="vtc__fraco">{{ t.email || 'sem e-mail no cadastro' }}</span>
          </li>
        </ul>
        <p v-else class="vtc__vazio">Nenhum.</p>
      </article>

      <article class="vtc__bloco">
        <h3 class="vtc__bloco-titulo">
          Casam pelo telefone e ainda não são do tipo técnico
          <span class="vtc__conta">{{ paraMarcar.length }}</span>
        </h3>
        <p class="vtc__bloco-nota">
          O número casa com um cadastro de técnico, mas o contato está com
          outro tipo aqui. 🚨 A varredura <b>não muda o tipo do contato</b> —
          marcar é decisão de quem atende, na ficha da conversa.
        </p>
        <ul v-if="paraMarcar.length" class="vtc__lista">
          <li v-for="c in paraMarcar" :key="c.contato_id">
            <b>{{ c.nome || 'sem nome' }}</b>
            <span class="vtc__fraco">
              está como {{ c.relacao || 'sem tipo' }} · casa com {{ c.tecnico }}
            </span>
          </li>
        </ul>
        <p v-else class="vtc__vazio">Nenhum.</p>
      </article>
    </template>
  </section>
</template>

<style scoped>
.vtc { display: flex; flex-direction: column; gap: var(--e-3); }
.vtc__topo { display: flex; align-items: center; justify-content: space-between; gap: var(--e-3); flex-wrap: wrap; }
.vtc__titulo { margin: 0; font-size: var(--txt-md); }
.vtc__nota { margin: 0; max-width: 72ch; }
.vtc__nota--fraca { color: var(--texto-fraco); font-size: var(--txt-sm); }
.vtc__bloco {
  display: flex;
  flex-direction: column;
  gap: var(--e-2);
  padding: var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
  background: var(--superficie-2);
}
.vtc__bloco-titulo { display: flex; align-items: center; gap: var(--e-2); margin: 0; font-size: var(--txt-sm); }
.vtc__conta {
  padding: 0 8px;
  border-radius: 999px;
  background: var(--acento);
  color: #fff;
  font-size: var(--txt-xs);
}
.vtc__bloco-nota { margin: 0; max-width: 72ch; color: var(--texto-fraco); font-size: var(--txt-sm); }
.vtc__lista { display: flex; flex-direction: column; gap: 4px; margin: 0; padding: 0; list-style: none; }
.vtc__lista li { display: flex; gap: var(--e-2); flex-wrap: wrap; font-size: var(--txt-sm); }
.vtc__fraco { color: var(--texto-fraco); }
.vtc__vazio { margin: 0; color: var(--texto-fraco); font-size: var(--txt-sm); }
</style>
