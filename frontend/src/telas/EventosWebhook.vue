<script setup>
/* ============================================================================
   CFG_8.1 — os eventos crus do webhook.
   ----------------------------------------------------------------------------
   🟡 S15/S13, feito em 15/09. A rota `/api/webhook/eventos` existia desde o
   começo e só era alcançável por `curl` -- e foi ela que achou, em 27/08, o
   `listMessage` e o `listResponseMessage` que NENHUMA consulta tinha visto:
   um deles era uma pessoa respondendo a um menu, e o painel tratava como
   ruído.

   🚨 O VALOR AQUI É VER O QUE NÃO SE SABE PROCURAR. Consulta SQL responde
   pergunta que já se sabe fazer; esta tela mostra o que está chegando, e é
   assim que se descobre formato novo antes de ele virar defeito calado.

   ⚠️ O payload cru pode conter binário de mídia (o `base64` do Evolution) e
   é pesado -- por isso ele só é buscado quando a pessoa abre UM evento, nunca
   na lista.
   ============================================================================ */
import { ref, onMounted } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'

const dados = ref(null)
const carregando = ref(true)
const erro = ref('')
const aberto = ref(null)
const payload = ref('')
const carregandoPayload = ref(false)

async function carregar() {
  carregando.value = true
  try {
    dados.value = await api.get('/api/webhook/eventos?limite=50')
    erro.value = ''
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui ler os eventos.'
  } finally {
    carregando.value = false
  }
}

async function abrir(evento) {
  if (aberto.value === evento.id) {
    aberto.value = null
    return
  }
  aberto.value = evento.id
  payload.value = ''
  carregandoPayload.value = true
  try {
    const r = await api.get(`/api/webhook/eventos/${evento.id}`)
    payload.value = JSON.stringify(r.payload ?? r, null, 2)
  } catch (e) {
    payload.value = e instanceof ErroDeApi ? e.message : 'Não consegui ler o corpo.'
  } finally {
    carregandoPayload.value = false
  }
}

function quando(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR')
}

function numero(n) {
  return (n ?? 0).toLocaleString('pt-BR')
}

onMounted(carregar)
</script>

<template>
  <div class="tela">
    <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>

    <section v-if="dados" class="cartao tela__bloco">
      <header class="cartao__cabecalho">
        <span class="linha">
          <i class="bi bi-broadcast" aria-hidden="true"></i>
          O que o WhatsApp mandou
        </span>
        <button class="botao botao--pequeno botao--contorno" type="button"
                :disabled="carregando" @click="carregar">
          <i class="bi bi-arrow-clockwise" aria-hidden="true"></i> Atualizar
        </button>
      </header>

      <div class="cartao__corpo">
        <div class="eventos__numeros">
          <div class="eventos__num">
            <span class="eventos__rotulo">Total</span>
            <strong class="mono">{{ numero(dados.resumo?.total) }}</strong>
          </div>
          <div class="eventos__num">
            <span class="eventos__rotulo">Esperando</span>
            <strong class="mono" :class="{ 'eventos__alerta': dados.resumo?.pendentes }">
              {{ numero(dados.resumo?.pendentes) }}
            </strong>
          </div>
          <div class="eventos__num">
            <span class="eventos__rotulo">Com erro</span>
            <strong class="mono" :class="{ 'eventos__alerta': dados.resumo?.ignorados }">
              {{ numero(dados.resumo?.ignorados) }}
            </strong>
          </div>
          <div class="eventos__num">
            <span class="eventos__rotulo">Último</span>
            <strong class="mono pequeno">{{ quando(dados.resumo?.ultimo) }}</strong>
          </div>
        </div>

        <p class="fraco pequeno">
          Os 50 mais recentes. Clique em um para ver o corpo cru — é ele que
          diz o formato de verdade, e foi assim que apareceram dois tipos de
          mensagem que nenhuma consulta tinha visto.
        </p>
      </div>
    </section>

    <p v-if="carregando" class="linha fraco"><span class="girando"></span> Lendo…</p>

    <section v-else-if="dados" class="cartao tela__bloco">
      <div class="cartao__corpo">
        <div v-if="!dados.eventos?.length" class="vazio">
          <i class="bi bi-inbox vazio__icone" aria-hidden="true"></i>
          <p class="vazio__titulo">Nenhum evento ainda</p>
        </div>

        <div v-else class="tabela--rolavel">
          <table class="tabela">
            <thead>
              <tr>
                <th>Quando</th>
                <th>Evento</th>
                <th>Telefone</th>
                <th>Estado</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <template v-for="e in dados.eventos" :key="e.id">
                <tr>
                  <td class="mono pequeno">{{ quando(e.recebido_em) }}</td>
                  <td><span class="chip">{{ e.evento || '—' }}</span></td>
                  <td class="mono pequeno">{{ e.telefone || '—' }}</td>
                  <td>
                    <span v-if="e.erro" class="chip chip--erro" :title="e.erro">erro</span>
                    <span v-else-if="!e.processado" class="chip chip--aviso">esperando</span>
                    <span v-else class="chip chip--ok">processado</span>
                  </td>
                  <td>
                    <button class="botao botao--pequeno botao--fantasma" type="button"
                            @click="abrir(e)">
                      {{ aberto === e.id ? 'Fechar' : 'Ver corpo' }}
                    </button>
                  </td>
                </tr>
                <tr v-if="aberto === e.id">
                  <td colspan="5">
                    <p v-if="carregandoPayload" class="linha fraco">
                      <span class="girando"></span> Lendo o corpo…
                    </p>
                    <pre v-else class="eventos__payload mono pequeno">{{ payload }}</pre>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.eventos__numeros {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
  gap: var(--e-3);
  margin-bottom: var(--e-3);
}
.eventos__num {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-sm);
}
.eventos__rotulo { font-size: var(--txt-xs); color: var(--texto-apagado); }
.eventos__alerta { color: var(--erro); }

/* 🚨 O corpo cru ROLA DENTRO DA PRÓPRIA CAIXA. Um payload com `base64` de
   mídia tem milhares de linhas: sem teto, ele empurraria a tabela inteira
   para fora da tela e a pessoa perderia a lista de onde clicou. */
.eventos__payload {
  max-height: 22rem;
  overflow: auto;
  margin: 0;
  padding: var(--e-3);
  background: var(--superficie-2);
  border-radius: var(--r-sm);
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
