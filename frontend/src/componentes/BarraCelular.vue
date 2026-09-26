<script setup>
/* ============================================================================
   Barra de baixo do CELULAR (🔵 25/09).
   ----------------------------------------------------------------------------
   *"verifique a compatibilidade do movizap somente para chat interno e externo
   via navegador mobile, os mesmos recursos, porém somente os chats"*.

   Abaixo de 860 px o menu lateral some (ele comia 62 dos 390 px) e esta barra
   ocupa o rodapé, com SÓ os dois chats e o Sair. As outras telas continuam
   existindo no computador; no celular, "somente os chats" é decisão dele.

   ⚠️ Os selos repetem os do menu lateral: Caixa = minhas não lidas (o mesmo
   número da aba Minhas, que o Notificador já mantém); Chat = não lidas do chat
   interno. O chat só é consultado quando a barra está À VISTA -- no
   computador o menu lateral já faz essa consulta, e duas seria desperdício.
   ============================================================================ */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api } from '../api/cliente.js'
import { notificacoes } from '../estado/notificacoes.js'
import { sessao, sair } from '../estado/sessao.js'

const rota = useRoute()
const router = useRouter()

const temCaixa = computed(() => sessao.telas.some((t) => t.codigo === 'ATD_1.1'))
const temChat = computed(() => sessao.telas.some((t) => t.codigo === 'ATD_6.1'))
const naCaixa = computed(() => rota.path.startsWith('/atendimento'))
const noChat = computed(() => rota.path.startsWith('/chat'))

const naoLidasChat = ref(0)
const mencoes = ref(0)
const celular = window.matchMedia ? window.matchMedia('(max-width: 860px)') : { matches: false }
let relogio = null

async function atualizar() {
  if (!celular.matches || !temChat.value) return
  try {
    const [r, m] = await Promise.all([api.get('/api/chat/nao-lidas'), api.get('/api/chat/mencoes')])
    naoLidasChat.value = r.nao_lidas || 0
    mencoes.value = (m || []).reduce((soma, s) => soma + Number(s.quantas || 0), 0)
  } catch {
    // selo é conveniência: falha aqui não pode virar erro na tela
  }
}
onMounted(() => { atualizar(); relogio = setInterval(atualizar, 15000) })
onUnmounted(() => clearInterval(relogio))

function selo(n) { return n > 99 ? '99+' : String(n) }

function encerrar() {
  // Um toque errado no rodapé não pode derrubar a sessão sem perguntar.
  if (!window.confirm('Sair do MoviZap neste aparelho?')) return
  sair()
  router.push({ name: 'login' })
}
</script>

<template>
  <nav class="barra-celular so-celular" aria-label="Navegação do celular">
    <RouterLink v-if="temCaixa" to="/atendimento" class="barra-celular__item"
                :class="{ 'barra-celular__item--aqui': naCaixa }">
      <span class="barra-celular__icone">
        <i class="bi bi-chat-dots" aria-hidden="true"></i>
        <span v-if="notificacoes.abas.minhas" class="barra-celular__selo">
          {{ selo(notificacoes.abas.minhas) }}
        </span>
      </span>
      Caixa de entrada
    </RouterLink>
    <RouterLink v-if="temChat" to="/chat" class="barra-celular__item"
                :class="{ 'barra-celular__item--aqui': noChat }">
      <span class="barra-celular__icone">
        <i class="bi bi-chat-square-text" aria-hidden="true"></i>
        <span v-if="naoLidasChat" class="barra-celular__selo"
              :class="{ 'barra-celular__selo--mencao': mencoes }">
          {{ selo(naoLidasChat) }}
        </span>
      </span>
      Chat interno
    </RouterLink>
    <button class="barra-celular__item" type="button" @click="encerrar">
      <span class="barra-celular__icone"><i class="bi bi-box-arrow-left" aria-hidden="true"></i></span>
      Sair
    </button>
  </nav>
</template>

<style scoped>
.barra-celular {
  grid-area: barra;
  justify-content: space-around;
  align-items: stretch;
  gap: var(--e-1);
  padding: var(--e-1) var(--e-2);
  /* O traço da tela sem botão do iPhone não pode cobrir os ícones. */
  padding-bottom: calc(var(--e-1) + env(safe-area-inset-bottom, 0px));
  background: var(--superficie);
  border-top: var(--borda-fina) solid var(--borda);
}
.barra-celular__item {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-height: 52px;
  border: 0;
  border-radius: var(--r-md);
  background: none;
  color: var(--texto-fraco);
  font-family: inherit;
  font-size: var(--txt-xs);
  text-decoration: none;
  cursor: pointer;
}
/* ⚠️ `--acento`, NÃO `--acento-texto`: este é o branco de texto POR CIMA do
   acento, e sobre o `--acento-suave` o item ativo ficaria invisível. */
.barra-celular__item--aqui { color: var(--acento); background: var(--acento-suave); }
.barra-celular__icone { position: relative; font-size: 22px; line-height: 1; }
.barra-celular__selo {
  position: absolute;
  top: -6px;
  right: -14px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: var(--r-full);
  background: var(--acento);
  color: #fff;
  font-size: 11px;
  font-weight: var(--peso-forte);
  line-height: 18px;
  text-align: center;
}
.barra-celular__selo--mencao { background: var(--aviso); }
</style>
