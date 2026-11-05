<script setup>
/* ============================================================================
   Casca do painel.
   ----------------------------------------------------------------------------
   Duas formas: tela pública (login) ocupa tudo; tela de sistema ganha menu,
   conteúdo e barra de status.

   A barra de status fica AQUI, fora do <RouterView>, para valer em toda tela
   sem que nenhuma tela precise lembrar de incluí-la — critério de pronto
   nº 10 ("toda tela mostra a barra com um código válido") não pode depender
   de disciplina de quem escreve a próxima tela.
   ============================================================================ */
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import MenuLateral from './componentes/MenuLateral.vue'
import BarraStatus from './componentes/BarraStatus.vue'
import BarraCelular from './componentes/BarraCelular.vue'
import Notificador from './componentes/Notificador.vue'
import { autenticado } from './estado/sessao.js'

const rota = useRoute()
const roteador = useRouter()
const comCasca = computed(() => autenticado.value && !rota.meta.publica)

/* 🚨 QUEM PERDE A SESSÃO VAI PARA O LOGIN, e não para uma tela morta. O 401
   limpa a sessão em `estado/sessao.js`, a casca desaparece -- e a tela de
   dentro continuava desenhada, sem menu e sem responder, até a pessoa tentar
   navegar. Fica AQUI, na casca, porque é o único lugar que vê as duas coisas:
   se ainda estou autenticado e em que rota estou. */
watch(autenticado, (agora) => {
  if (!agora && !rota.meta.publica) {
    roteador.push({ name: 'login', query: { destino: rota.fullPath } })
  }
})
</script>

<template>
  <div v-if="comCasca" class="painel">
    <!-- 🔵 25/09, celular: abaixo de 860 px o menu lateral e a barra de
         status saem, e a BarraCelular (só os dois chats + Sair) ocupa o
         rodapé. No computador, nada muda. -->
    <MenuLateral class="so-computador" />
    <!-- 🚨 `meta.cheio` (27/08): a Caixa de entrada e um APP DE CONVERSA, nao
         uma pagina com cartoes. Ela precisa da altura toda e sem respiro em
         volta -- foi o que o usuario apontou comparando com o mockup que
         escolheu: "so mudou o fundo... pensei que as dimensoes ficariam igual".

         ⚠️ MARCADO NA ROTA, nao com margem negativa aqui. Margem negativa
         depende do padding do pai continuar exatamente o que e hoje, e quebra
         calada no dia em que ele mudar. -->
    <main class="painel__conteudo"
          :class="{ 'painel__conteudo--cheio': rota.meta.cheio,
                    'painel__conteudo--largo': rota.meta.largo }">
      <RouterView />
    </main>
    <BarraStatus class="so-computador" />
    <BarraCelular />
    <!-- 🔵 24/09: o som e a aba piscando valem em QUALQUER tela, por isso
         moram na casca e não na Caixa de entrada. -->
    <Notificador />
  </div>

  <RouterView v-else />
</template>

<style scoped>
.painel {
  display: grid;
  grid-template-areas:
    "menu conteudo"
    "barra barra";
  grid-template-columns: auto 1fr;
  grid-template-rows: 1fr auto;
  height: 100%;
}

.painel__conteudo {
  grid-area: conteudo;
  min-width: 0;
  overflow: auto;
  padding: var(--e-6) var(--e-7);
}

/* Sem respiro e sem rolagem propria: quem rola e cada coluna da tela. */
.painel__conteudo--cheio { padding: 0; overflow: hidden; }

/* 🔵 05/11: *"em algumas abas, como operacao, existe uma margem entre o grid
   dos cards e o menu, isso e perca de espaco"*.
   🚨 MEDIDO: o padding era `var(--e-6) var(--e-7)` = 30px em cima e **40px de
   cada lado**, em TODAS as telas -- so a Caixa escapava, pelo `cheio: true`.
   Na Operacao isso sao **80px horizontais**, cerca de um terco de uma coluna.
   ⚠️ E NAO USEI O `cheio: true` PARA ISTO, de proposito: ele zera o padding
   **e o `overflow`**, e a Operacao depende da rolagem vertical do casco. O
   `largo` mexe so no lado, e nao toca o comportamento de ninguem.
   O respiro vertical fica: cabecalho colado no topo e pior que 40px perdidos. */
.painel__conteudo--largo { padding-left: var(--e-3); padding-right: var(--e-3); }

@media (max-width: 860px) {
  .painel__conteudo { padding: var(--e-4); }
  /* ⚠️ No celular o padding ja e 16px e nao ha menu do lado: o `largo` nao
     tem o que devolver, e zerar aqui deixaria o card colado na beira. */
  .painel__conteudo--largo { padding-left: var(--e-4); padding-right: var(--e-4); }
  /* Celular: sem coluna de menu; o rodapé é a BarraCelular. */
  .painel {
    grid-template-areas:
      "conteudo"
      "barra";
    grid-template-columns: 1fr;
  }
  .painel__conteudo--cheio { padding: 0; }
}
</style>
