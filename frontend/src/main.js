/* ============================================================================
   Ponto de entrada do painel.
   ----------------------------------------------------------------------------
   A ordem importa: tema antes de tudo (evita piscar), sessão restaurada antes
   de montar (evita o painel aparecer vazio e só depois preencher), e o mount
   só depois do router estar pronto.
   ============================================================================ */
import { createApp } from 'vue'

import './estilo/tokens.css'
import './estilo/base.css'
import './estilo/componentes.css'
/* 🚨 A FONTE ÚNICA DO CSS DOS PAINÉIS (25/11). Vem DEPOIS do
   componentes.css de propósito: ela é a casa das regras de painel, e
   o que estava copiado em quatro `<style scoped>` mora aqui agora. */
import 'bootstrap-icons/font/bootstrap-icons.css'

import App from './App.vue'
import { router } from './router/index.js'
import { restaurar } from './estado/sessao.js'

async function subir() {

  // Token guardado de uma sessão anterior: descobrir quem é ANTES da primeira
  // navegação. Sem isso, a guarda manda para o login quem já estava logado.
  await restaurar()

  const app = createApp(App)
  app.use(router)
  await router.isReady()
  app.mount('#app')
}

subir()
