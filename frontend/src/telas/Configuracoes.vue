<script setup>
/* ============================================================================
   CFG_0.1 — Configurações. A casca com abas.
   ----------------------------------------------------------------------------
   Pedido do usuário em 27/08: *"precisamos ter uma aba para as configurações e
   os acionadores dos interruptores devem ficar lá"*.

   🚨 ESTA TELA NÃO REESCREVE NENHUMA DAS SEIS. Ela monta os componentes que já
   existem, cada um continuando no seu arquivo, com seu código e sua rota. É o
   que faz link antigo continuar abrindo e o `teste_router.py` continuar
   comparando registro contra roteador do mesmo jeito.

   🚨 A CASCA NÃO TEM `<h1>` PRÓPRIO, DE PROPÓSITO. Cada tela filha já traz o
   seu cabeçalho e o seu chip de código; um segundo `<h1>` aqui daria dois
   títulos na mesma página. Quem diz onde você está é a barra de abas.

   ⚠️ QUEM SOME DO MENU É QUEM TEM `aba_de`, e isso é decidido no REGISTRO do
   backend (`movizap/telas.py`), não aqui. Esta tela nem sabe quais telas
   existem: ela lê a mesma lista que o menu lê.

   🚨 A ESCADA DA IA FICA NO TOPO DA ABA DA IA. Era o pedido de fundo: os três
   interruptores viviam em três telas diferentes e o usuário não achou nenhum.
   ============================================================================ */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { sessao } from '../estado/sessao.js'
import EscadaIa from '../componentes/EscadaIa.vue'

import Canais from './Canais.vue'
import IaPrompt from './IaPrompt.vue'
import Sincronizacao from './Sincronizacao.vue'
import Classificacoes from './Classificacoes.vue'
import Automacao from './Automacao.vue'
import RegistroDeTelas from './RegistroDeTelas.vue'

const route = useRoute()
const router = useRouter()

/* A ordem é a ordem de uso, não a ordem do código: a IA primeiro, porque é o
   que está sendo montado agora e é onde moram os interruptores. */
const COMPONENTE = {
  'CFG_2.1': IaPrompt,
  'CFG_1.1': Canais,
  'CFG_5.1': Automacao,
  'CFG_4.1': Classificacoes,
  'CFG_3.1': Sincronizacao,
  'CFG_9.1': RegistroDeTelas,
}
const ORDEM = ['CFG_2.1', 'CFG_1.1', 'CFG_5.1', 'CFG_4.1', 'CFG_3.1', 'CFG_9.1']

/* Título curto para a aba. O do registro é bom para o menu e comprido para uma
   barra de abas ("IA — prompt" vira só "IA", porque a escada mora aqui). */
const ROTULO = {
  'CFG_2.1': 'IA',
  'CFG_1.1': 'Canais',
  'CFG_5.1': 'Automação',
  'CFG_4.1': 'Classificações',
  'CFG_3.1': 'Sincronização',
  'CFG_9.1': 'Telas',
}

/* 🚨 SÓ AS ABAS QUE ESTE USUÁRIO ENXERGA. A permissão continua sendo por tela,
   como sempre foi -- a casca não concede nada. Se um dia uma das seis for
   liberada para um perfil que não vê as outras, ele vê uma aba só. */
const abas = computed(() =>
  ORDEM
    .filter((codigo) => sessao.telas.some((t) => t.codigo === codigo))
    .map((codigo) => ({ codigo, rotulo: ROTULO[codigo] })),
)

const ativa = ref(null)

/* A rota manda: `/config/canais` abre na aba de Canais. É isso que faz link
   antigo, favorito e histórico do navegador continuarem funcionando. */
function daRota() {
  const codigo = route.meta?.codigo
  if (codigo && codigo !== 'CFG_0.1' && COMPONENTE[codigo]) return codigo
  return abas.value[0]?.codigo || null
}

watch(() => route.fullPath, () => { ativa.value = daRota() }, { immediate: true })

const componenteAtivo = computed(() => COMPONENTE[ativa.value] || null)

/* Trocar de aba TROCA A ROTA. Sem isso o endereço mentiria sobre onde o
   usuário está, e recarregar a página o jogaria para outro lugar. */
function abrir(codigo) {
  const tela = sessao.telas.find((t) => t.codigo === codigo)
  if (tela && tela.rota !== route.path) router.push(tela.rota)
  else ativa.value = codigo
}
</script>

<template>
  <div class="config">
    <nav class="config__abas" aria-label="Configurações">
      <button v-for="aba in abas" :key="aba.codigo"
              class="config__aba"
              :class="{ 'config__aba--ativa': aba.codigo === ativa }"
              type="button"
              :aria-current="aba.codigo === ativa ? 'page' : undefined"
              :title="aba.codigo"
              @click="abrir(aba.codigo)">
        {{ aba.rotulo }}
      </button>
    </nav>

    <p v-if="!abas.length" class="aviso aviso--info">
      <i class="bi bi-info-circle aviso__icone" aria-hidden="true"></i>
      <span>Nenhuma configuração liberada para esta conta.</span>
    </p>

    <div class="config__conteudo">
      <!-- A escada vem ANTES do conteúdo da aba da IA: é o que o usuário
           precisa ver primeiro, e o que ele não achava. -->
      <EscadaIa v-if="ativa === 'CFG_2.1'" @ir-para="abrir" />

      <component :is="componenteAtivo" v-if="componenteAtivo" :key="ativa" />
    </div>
  </div>
</template>

<style scoped>
.config { display: flex; flex-direction: column; min-height: 0; }

.config__abas {
  display: flex;
  flex-wrap: wrap;
  gap: var(--e-1);
  padding-bottom: var(--e-3);
  margin-bottom: var(--e-4);
  border-bottom: var(--borda-fina) solid var(--borda);
}

.config__aba {
  min-height: var(--altura-toque);
  padding: 0 var(--e-4);
  border: var(--borda-fina) solid transparent;
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--texto-fraco);
  font-family: inherit;
  font-size: var(--txt-md);
  font-weight: var(--peso-medio);
  cursor: pointer;
  transition: background var(--tempo-rapido) var(--curva),
              color var(--tempo-rapido) var(--curva);
}
.config__aba:hover { background: var(--superficie-2); color: var(--texto); }
.config__aba--ativa {
  background: var(--acento);
  border-color: var(--acento);
  color: #fff;
}
.config__aba:focus-visible { outline: 2px solid var(--foco); outline-offset: 2px; }

.config__conteudo { min-height: 0; }
</style>
