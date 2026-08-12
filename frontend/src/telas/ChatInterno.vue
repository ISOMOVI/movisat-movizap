<script setup>
/* ============================================================================
   ATD_6.1 — Chat interno, entre atendentes
   ----------------------------------------------------------------------------
   🚨 NADA DAQUI SAI PARA O CLIENTE. É outro módulo, outras tabelas, e o
   serviço nem conhece o `evolution`. A cor e o rótulo dizem isso o tempo todo:
   quem se confunde manda para a pessoa errada.

   ⚠️ NÃO SUBSTITUI A NOTA INTERNA. A nota responde "falar sobre ESTA
   conversa" e vive dentro dela; isto responde "falar sobre qualquer coisa".
   ============================================================================ */
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'

const salas = ref([])
const contatos = ref([])
const sala = ref(null)
const mensagens = ref([])
const texto = ref('')
const carregando = ref(true)
const enviando = ref(false)
const erro = ref('')
const abrindo = ref(false)
const baloes = ref(null)
let timer = null

const naoLidasTotal = computed(
  () => salas.value.reduce((s, x) => s + (x.nao_lidas || 0), 0),
)

async function carregar({ silencioso = false } = {}) {
  if (!silencioso) carregando.value = true
  try {
    const r = await api.get('/api/chat/salas')
    salas.value = r.salas || []
    contatos.value = r.contatos || []
    erro.value = ''
  } catch (e) {
    if (!silencioso) {
      erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao ler as conversas.'
    }
  } finally {
    carregando.value = false
  }
}

async function abrir(salaId, { silencioso = false } = {}) {
  try {
    const r = await api.get(`/api/chat/salas/${salaId}`)
    sala.value = salas.value.find((s) => s.id === salaId) || { id: salaId }
    mensagens.value = r.mensagens || []
    if (sala.value.tipo === 'grupo') await carregarMembros(salaId)
    if (!silencioso) {
      mostrandoMembros.value = false
      rolarParaOFim()
    }
    // Abrir zera o não lido desta sala: o servidor já marcou, a lista precisa
    // refletir sem esperar o próximo ciclo.
    await carregar({ silencioso: true })
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao abrir a conversa.'
  }
}

/* ---- grupo ---------------------------------------------------------------
   Sala com nome e vários membros. A sala direta continua sendo o caminho de
   "falar com uma pessoa" -- não vira grupo, porque conversa de dois que passa
   a ser de três é outra conversa. */
const criandoGrupo = ref(false)
const nomeGrupo = ref('')
const escolhidos = ref([])
const membros = ref([])
const mostrandoMembros = ref(false)

const ehGrupo = computed(() => sala.value && sala.value.tipo === 'grupo')
const foraDoGrupo = computed(() => {
  if (!ehGrupo.value) return []
  const dentro = new Set(membros.value.map((m) => m.atendente_id))
  return contatos.value.filter((c) => !dentro.has(c.id))
})

async function criarGrupo() {
  const nome = nomeGrupo.value.trim()
  if (!nome || !escolhidos.value.length || abrindo.value) return
  abrindo.value = true
  erro.value = ''
  try {
    const r = await api.post('/api/chat/grupo',
                             { nome, membros: escolhidos.value })
    recado.value = `Grupo "${r.nome}" criado com ${r.membros} pessoas.`
    criandoGrupo.value = false
    nomeGrupo.value = ''
    escolhidos.value = []
    await carregar({ silencioso: true })
    await abrir(r.sala_id)
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui criar.'
  } finally {
    abrindo.value = false
  }
}

async function carregarMembros(salaId) {
  try {
    const r = await api.get(`/api/chat/salas/${salaId}/membros`)
    membros.value = r.membros || []
  } catch {
    membros.value = []
  }
}

async function adicionar(atendenteId) {
  try {
    const r = await api.post(`/api/chat/salas/${sala.value.id}/membros`,
                             { atendente_id: atendenteId })
    recado.value = `${r.nome} entrou no grupo.`
    await carregarMembros(sala.value.id)
    await carregar({ silencioso: true })
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui adicionar.'
  }
}

async function sairDoGrupo() {
  if (!confirm('Sair deste grupo? Ele continua para os outros.')) return
  try {
    await api.post(`/api/chat/salas/${sala.value.id}/sair`)
    recado.value = 'Você saiu do grupo.'
    sala.value = null
    mensagens.value = []
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui sair.'
  }
}

const recado = ref('')

async function falarCom(atendenteId) {
  if (abrindo.value) return
  abrindo.value = true
  erro.value = ''
  try {
    const r = await api.post('/api/chat/abrir', { atendente_id: atendenteId })
    await carregar({ silencioso: true })
    await abrir(r.sala_id)
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui abrir.'
  } finally {
    abrindo.value = false
  }
}

async function enviar() {
  const t = texto.value.trim()
  if (!t || enviando.value || !sala.value) return
  enviando.value = true
  erro.value = ''
  try {
    await api.post(`/api/chat/salas/${sala.value.id}/escrever`, { texto: t })
    texto.value = ''
    // 🚨 Relê em vez de empurrar o balão na mão: o que vale é o que o banco
    // gravou, não o que a tela supõe ter acontecido.
    await abrir(sala.value.id)
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui enviar.'
  } finally {
    enviando.value = false
  }
}

/* ⚠️ Só rola sozinho se já estava no fim. Rolar à força enquanto a pessoa lê
   uma mensagem antiga arranca a tela da mão dela a cada 5 segundos. */
function estaNoFim() {
  const el = baloes.value
  if (!el) return true
  return el.scrollHeight - el.scrollTop - el.clientHeight < 80
}

async function rolarParaOFim() {
  await nextTick()
  if (baloes.value) baloes.value.scrollTop = baloes.value.scrollHeight
}

onMounted(async () => {
  await carregar()
  timer = setInterval(async () => {
    const estava = estaNoFim()
    await carregar({ silencioso: true })
    if (sala.value) {
      await abrir(sala.value.id, { silencioso: true })
      if (estava) rolarParaOFim()
    }
  }, 5000)
})

onUnmounted(() => clearInterval(timer))

watch(sala, () => { texto.value = '' })

function hora(iso) {
  return new Date(iso).toLocaleString('pt-BR',
    { dateStyle: 'short', timeStyle: 'short' })
}

function quando(iso) {
  if (!iso) return ''
  const min = Math.round((new Date() - new Date(iso)) / 60000)
  if (min < 1) return 'agora'
  if (min < 60) return `${min} min`
  if (min < 60 * 24) return `${Math.round(min / 60)} h`
  return new Date(iso).toLocaleDateString('pt-BR')
}
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Chat interno</h1>
        <p class="fraco pequeno">
          Conversa entre atendentes. <strong>Não sai para o cliente</strong> —
          para falar com ele, use o Atendimento.
        </p>
      </div>
      <span v-if="naoLidasTotal" class="chip chip--acento">
        {{ naoLidasTotal }} não lida{{ naoLidasTotal > 1 ? 's' : '' }}
      </span>
    </header>

    <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>
    <p v-if="recado" class="aviso aviso--ok" role="status">{{ recado }}</p>

    <div class="colunas">
      <!-- ─────────────────────────────────────────────── quem -->
      <section class="cartao coluna">
        <header class="cartao__cabecalho"><strong>Conversas</strong></header>

        <p v-if="carregando" class="linha fraco cartao__corpo">
          <span class="girando"></span> Lendo…
        </p>

        <ul v-else-if="salas.length" class="salas">
          <li v-for="s in salas" :key="s.id">
            <button
              class="sala"
              :class="{ 'sala--aberta': sala && sala.id === s.id }"
              type="button"
              @click="abrir(s.id)"
            >
              <div class="sala__topo">
                <strong>
                  <i v-if="s.tipo === 'grupo'" class="bi bi-people" aria-hidden="true"></i>
                  {{ s.com || s.nome || 'conversa' }}
                </strong>
                <span class="apagado pequeno">{{ quando(s.ultima_em) }}</span>
              </div>
              <p v-if="s.tipo === 'grupo'" class="apagado pequeno sala__previa">
                {{ s.qtd_membros }} pessoas
              </p>
              <p class="apagado pequeno sala__previa">
                <span v-if="s.ultimo_autor" class="fraco">{{ s.ultimo_autor }}: </span>
                {{ s.ultima_mensagem || '(sem mensagem ainda)' }}
              </p>
              <span v-if="s.nao_lidas" class="chip chip--acento chip--pequeno">
                {{ s.nao_lidas }}
              </span>
            </button>
          </li>
        </ul>

        <div v-else class="vazio">
          <i class="bi bi-chat-left-dots vazio__icone" aria-hidden="true"></i>
          <p class="vazio__titulo">Nenhuma conversa ainda</p>
          <p>Escolha alguém abaixo para começar.</p>
        </div>

        <div class="cartao__corpo pilha">
          <p class="campo__rotulo">Falar com</p>
          <div class="linha linha--quebra">
            <button
              v-for="c in contatos"
              :key="c.id"
              class="botao botao--pequeno botao--contorno"
              type="button"
              :disabled="abrindo"
              @click="falarCom(c.id)"
            >
              <i class="bi bi-person" aria-hidden="true"></i> {{ c.nome }}
            </button>
          </div>
          <p v-if="!contatos.length" class="apagado pequeno">
            Não há outro atendente ativo com e-mail cadastrado.
          </p>

          <button
            v-if="contatos.length && !criandoGrupo"
            class="botao botao--pequeno botao--contorno"
            type="button"
            @click="criandoGrupo = true"
          >
            <i class="bi bi-people" aria-hidden="true"></i> Criar grupo
          </button>

          <div v-if="criandoGrupo" class="pilha grupo__novo">
            <label class="campo">
              <span class="campo__rotulo">Nome do grupo</span>
              <input v-model="nomeGrupo" class="campo__entrada" maxlength="60"
                     placeholder="Plantão do fim de semana" />
            </label>
            <p class="campo__rotulo">Quem entra</p>
            <label v-for="c in contatos" :key="c.id" class="grupo__opcao">
              <input v-model="escolhidos" type="checkbox" :value="c.id" />
              <span>{{ c.nome }}</span>
            </label>
            <p class="apagado pequeno">Você entra automaticamente.</p>
            <div class="linha linha--quebra">
              <button class="botao botao--pequeno botao--contorno" type="button"
                      @click="criandoGrupo = false; escolhidos = []">
                Cancelar
              </button>
              <button
                class="botao botao--pequeno botao--primario"
                type="button"
                :disabled="!nomeGrupo.trim() || !escolhidos.length || abrindo"
                @click="criarGrupo"
              >
                Criar
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- ─────────────────────────────────────────── a conversa -->
      <section class="cartao coluna coluna--larga">
        <div v-if="!sala" class="vazio">
          <i class="bi bi-chat-text vazio__icone" aria-hidden="true"></i>
          <p class="vazio__titulo">Escolha uma conversa</p>
        </div>

        <template v-else>
          <header class="cartao__cabecalho">
            <strong>
              <i v-if="ehGrupo" class="bi bi-people" aria-hidden="true"></i>
              {{ sala.com || sala.nome || 'Conversa' }}
            </strong>
            <span class="chip chip--aviso">
              <i class="bi bi-lock" aria-hidden="true"></i> interno
            </span>
            <span class="espaco"></span>
            <template v-if="ehGrupo">
              <button class="botao botao--pequeno botao--fantasma" type="button"
                      @click="mostrandoMembros = !mostrandoMembros">
                {{ membros.length }} pessoas
              </button>
              <button class="botao botao--pequeno botao--fantasma" type="button"
                      title="Sair do grupo" @click="sairDoGrupo">
                <i class="bi bi-box-arrow-left" aria-hidden="true"></i>
              </button>
            </template>
          </header>

          <div v-if="ehGrupo && mostrandoMembros" class="cartao__corpo pilha grupo__novo">
            <p class="campo__rotulo">No grupo</p>
            <div class="linha linha--quebra">
              <span v-for="m in membros" :key="m.atendente_id" class="chip">
                {{ m.nome }}
              </span>
            </div>
            <template v-if="foraDoGrupo.length">
              <p class="campo__rotulo">Chamar para o grupo</p>
              <div class="linha linha--quebra">
                <button
                  v-for="c in foraDoGrupo"
                  :key="c.id"
                  class="botao botao--pequeno botao--contorno"
                  type="button"
                  @click="adicionar(c.id)"
                >
                  <i class="bi bi-person-plus" aria-hidden="true"></i> {{ c.nome }}
                </button>
              </div>
            </template>
            <p v-else class="apagado pequeno">Todo mundo já está no grupo.</p>
          </div>

          <div ref="baloes" class="baloes">
            <p v-if="!mensagens.length" class="apagado pequeno cartao__corpo">
              Nenhuma mensagem ainda. Escreva a primeira.
            </p>
            <div
              v-for="m in mensagens"
              :key="m.id"
              class="balao"
              :class="m.minha ? 'balao--minha' : 'balao--dele'"
            >
              <p v-if="!m.minha" class="balao__autor pequeno">{{ m.autor }}</p>
              <p class="balao__texto">{{ m.texto }}</p>
              <p class="balao__rodape apagado pequeno">{{ hora(m.criada_em) }}</p>
            </div>
          </div>

          <div class="cartao__corpo pilha">
            <label class="campo">
              <span class="so-leitor">Mensagem</span>
              <textarea
                v-model="texto"
                class="campo__entrada"
                rows="2"
                maxlength="4000"
                placeholder="Escreva e aperte Ctrl+Enter"
                @keydown.ctrl.enter.prevent="enviar"
              ></textarea>
            </label>
            <div class="linha">
              <button
                class="botao botao--primario"
                type="button"
                :disabled="enviando || !texto.trim()"
                @click="enviar"
              >
                <span v-if="enviando" class="girando"></span>
                {{ enviando ? 'Enviando…' : 'Enviar' }}
              </button>
              <span class="apagado pequeno">
                🚨 Isto <strong>não</strong> chega ao cliente.
              </span>
            </div>
          </div>
        </template>
      </section>
    </div>
  </div>
</template>

<style scoped>
.colunas { display: flex; gap: var(--e-4); align-items: flex-start; }
.coluna { flex: 1 1 300px; min-width: 0; }
.coluna--larga { flex: 2 1 520px; }

.salas { list-style: none; margin: 0; padding: 0; max-height: 45vh; overflow-y: auto; }
.sala {
  display: block;
  width: 100%;
  text-align: left;
  background: none;
  border: 0;
  border-top: 1px solid var(--borda, rgba(128, 128, 128, .25));
  padding: var(--e-3);
  cursor: pointer;
}
.sala:hover { background: rgba(128, 128, 128, .08); }
.sala--aberta { background: rgba(128, 128, 128, .14); }
.sala__topo { display: flex; justify-content: space-between; gap: var(--e-2); }
.sala__previa {
  margin: 2px 0 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.baloes {
  display: flex;
  flex-direction: column;
  gap: var(--e-2);
  padding: var(--e-4);
  max-height: 52vh;
  overflow-y: auto;
}
.balao {
  max-width: 72%;
  padding: var(--e-2) var(--e-3);
  border-radius: var(--r-md);
  background: var(--superficie-2);
}
/* ⚠️ Verde é a cor do WhatsApp nesta casa, e o chat interno NÃO é WhatsApp.
   Usar o acento do painel é o que impede a confusão de "mandei para quem?". */
.balao--minha { align-self: flex-end; background: var(--acento-suave); }
.balao--dele { align-self: flex-start; }
.balao__autor { margin: 0 0 2px; color: var(--texto-fraco); font-weight: var(--peso-forte); }
.balao__texto { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.balao__rodape { margin: var(--e-1) 0 0; }

.chip--pequeno { font-size: var(--txt-xs); padding: 1px 6px; }

.grupo__novo {
  padding: var(--e-3);
  border: 1px dashed var(--borda-forte, var(--borda));
  border-radius: var(--r-sm);
  background: var(--superficie-2);
}
.grupo__opcao {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  padding: 3px 0;
  cursor: pointer;
}
.grupo__opcao input { width: 17px; height: 17px; accent-color: var(--acento); }
.linha--quebra { flex-wrap: wrap; gap: var(--e-2); }
textarea.campo__entrada { resize: vertical; }
</style>
