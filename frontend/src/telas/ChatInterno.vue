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
import { corDaInicial, iniciais } from '../util/avatar.js'

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

/* ---- a lista, em duas seções (25/08) -------------------------------------
   🚨 PESSOAS E GRUPOS ESTAVAM MISTURADOS numa coluna só, e embaixo dela havia
   uma FILEIRA DE BOTÕES com o nome de cada atendente. Com 5 pessoas já ficava
   estranho; com 15 seria impraticável. Agora são duas seções e uma busca --
   que é como todo canal interno se organiza, e por isso ninguém precisa
   aprender. */
const filtro = ref('')

function _casa(texto) {
  const alvo = filtro.value.trim().toLowerCase()
  if (!alvo) return true
  return (texto || '').toLowerCase().includes(alvo)
}

const pessoas = computed(
  () => salas.value.filter((s) => s.tipo === 'direta' && _casa(s.com)),
)
const grupos = computed(
  () => salas.value.filter((s) => s.tipo === 'grupo' && _casa(s.nome)),
)

/* Quem ainda não tem conversa aberta comigo: entra na busca, não numa fileira
   permanente de botões. */
const semConversa = computed(() => {
  const jaTem = new Set(salas.value.filter((s) => s.tipo === 'direta')
                                   .map((s) => s.com))
  return contatos.value.filter((c) => !jaTem.has(c.nome) && _casa(c.nome))
})

/* 🚨 `atendente.estado` EXISTE DESDE A MIGRAÇÃO 001 E NENHUMA TELA O USAVA.
   Num canal interno é ele que responde a pergunta que se faz ANTES de
   escrever: adianta chamar agora? */
const ESTADO = {
  disponivel: { rotulo: 'disponível', cor: 'var(--ok)' },
  ausente: { rotulo: 'ausente', cor: 'var(--aviso)' },
  nao_perturbe: { rotulo: 'não perturbe', cor: 'var(--erro)' },
}

function corDoEstado(estado) {
  return (ESTADO[estado] || {}).cor || 'var(--texto-apagado)'
}

function rotuloDoEstado(estado) {
  return (ESTADO[estado] || {}).rotulo || 'sem estado'
}

/* ---- separador de dia ----------------------------------------------------
   Sem ele o fio é um bloco só, e "14:32" não diz se foi hoje ou em julho. */
function _diaDe(iso) {
  return iso ? new Date(iso).toDateString() : ''
}

function comecaODia(m, i) {
  if (i === 0) return true
  return _diaDe(m.criada_em) !== _diaDe(mensagens.value[i - 1].criada_em)
}

function rotuloDoDia(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const hoje = new Date()
  const ontem = new Date()
  ontem.setDate(hoje.getDate() - 1)
  if (d.toDateString() === hoje.toDateString()) return 'Hoje'
  if (d.toDateString() === ontem.toDateString()) return 'Ontem'
  const mesmoAno = d.getFullYear() === hoje.getFullYear()
  return d.toLocaleDateString('pt-BR', mesmoAno
    ? { day: '2-digit', month: 'long' }
    : { day: '2-digit', month: 'long', year: 'numeric' })
}

/* Mensagens seguidas da mesma pessoa viram um bloco: repetir o nome em cada
   balão é o que dá cara de log de sistema. */
function mesmoAutor(m, i) {
  if (i === 0) return false
  const anterior = mensagens.value[i - 1]
  return anterior.autor === m.autor
    && anterior.minha === m.minha
    && !comecaODia(m, i)
}

/* ---- emoji ---------------------------------------------------------------
   🚨 GRADE PRÓPRIA, ZERO DEPENDÊNCIA. Emoji é caractere de texto: biblioteca
   só serve para PROCURAR. `emoji-picker-element` custa ~40 KB e
   `vue3-emoji-picker` ~90 KB -- num bundle de 300 KB, para inserir um
   caractere. Com os que aparecem em atendimento, a grade resolve e serve os
   dois compositores. Se um dia faltar busca por nome, troca-se por uma
   biblioteca sem mexer no resto. */
const EMOJIS = [
  { grupo: 'Rosto', itens: ['😀', '😄', '😁', '😊', '🙂', '😉', '😍', '🤔',
    '😅', '😂', '🥲', '😴', '😐', '🙄', '😕', '😞', '😢', '😭', '😤', '😡',
    '🤯', '😱', '🤗', '🤝'] },
  { grupo: 'Gesto', itens: ['👍', '👎', '👌', '✌️', '🙏', '👏', '💪', '🫡',
    '👋', '🤞', '☝️', '✍️'] },
  { grupo: 'Trabalho', itens: ['✅', '❌', '⚠️', '❗', '❓', '📌', '📎', '📅',
    '⏰', '📞', '📱', '💻', '📧', '🧾', '💰', '📊', '🔧', '🚗', '🛠️', '🔑'] },
  { grupo: 'Sinal', itens: ['🔴', '🟠', '🟡', '🟢', '🔵', '⚫', '⚪', '🔥',
    '⭐', '💡', '🎯', '🚨'] },
]
const emojiAberto = ref(false)

function porEmoji(e) {
  texto.value = (texto.value || '') + e
}

function fecharEmojiSeForaDele(evento) {
  if (!emojiAberto.value) return
  if (!evento.target.closest('.emoji')) emojiAberto.value = false
}

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
  document.addEventListener('click', fecharEmojiSeForaDele)
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

onUnmounted(() => {
  clearInterval(timer)
  document.removeEventListener('click', fecharEmojiSeForaDele)
})

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
        <!-- 🚨 UM AVISO, NÃO TRÊS. "Não chega ao cliente" aparecia no
             cabeçalho da tela, no chip da conversa e embaixo do botão de
             enviar. Repetir três vezes na mesma tela não avisa mais: avisa
             menos, porque vira decoração que o olho pula. Fica o chip, que é
             o que está à vista NA HORA de escrever. -->
        <p class="fraco pequeno">Conversa entre atendentes.</p>
      </div>
      <span v-if="naoLidasTotal" class="chip chip--acento">
        {{ naoLidasTotal }} não lida{{ naoLidasTotal > 1 ? 's' : '' }}
      </span>
    </header>

    <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>
    <p v-if="recado" class="aviso aviso--ok" role="status">{{ recado }}</p>

    <div class="colunas">
      <!-- ─────────────────────────────────────────── pessoas e grupos -->
      <section class="cartao coluna">
        <div class="cartao__corpo ci__topo">
          <!-- 🚨 UMA BUSCA NO LUGAR DA FILEIRA DE BOTÕES. Havia um botão por
               atendente embaixo da lista: com 5 já ficava estranho, com 15
               seria impraticável. Buscar serve para achar conversa E para
               começar uma nova, que é a mesma intenção. -->
          <label class="busca">
            <span class="so-leitor">Buscar pessoa ou grupo</span>
            <input
              v-model="filtro"
              class="campo__entrada"
              type="search"
              placeholder="Buscar pessoa ou grupo…"
            />
          </label>
          <button
            class="botao botao--pequeno botao--contorno botao--icone"
            type="button"
            title="Criar grupo"
            aria-label="Criar grupo"
            @click="criandoGrupo = !criandoGrupo"
          >
            <i class="bi bi-people" aria-hidden="true"></i>
          </button>
        </div>

        <div v-if="criandoGrupo" class="cartao__corpo pilha grupo__novo">
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

        <p v-if="carregando" class="linha fraco cartao__corpo">
          <span class="girando"></span> Lendo…
        </p>

        <div v-else class="ci__lista">
          <template v-if="pessoas.length">
            <p class="ci__secao">Pessoas</p>
            <button
              v-for="sl in pessoas"
              :key="sl.id"
              class="ci__sala"
              :class="{ 'ci__sala--aberta': sala && sala.id === sl.id }"
              type="button"
              @click="abrir(sl.id)"
            >
              <span class="ci__avatar" :style="{ background: corDaInicial(sl.com) }"
                    aria-hidden="true">
                {{ iniciais(sl.com) }}
                <span class="ci__estado"
                      :style="{ background: corDoEstado(sl.com_estado) }"
                      :title="rotuloDoEstado(sl.com_estado)"></span>
              </span>
              <span class="ci__corpo">
                <span class="ci__topo1">
                  <strong class="ci__nome">{{ sl.com }}</strong>
                  <span class="apagado pequeno">{{ quando(sl.ultima_em) }}</span>
                </span>
                <span class="ci__previa pequeno apagado">
                  <span v-if="sl.ultimo_autor" class="fraco">{{ sl.ultimo_autor }}: </span>
                  {{ sl.ultima_mensagem || 'sem mensagem ainda' }}
                </span>
              </span>
              <span v-if="sl.nao_lidas" class="ci__badge">{{ sl.nao_lidas }}</span>
            </button>
          </template>

          <template v-if="grupos.length">
            <p class="ci__secao">Grupos</p>
            <button
              v-for="sl in grupos"
              :key="sl.id"
              class="ci__sala"
              :class="{ 'ci__sala--aberta': sala && sala.id === sl.id }"
              type="button"
              @click="abrir(sl.id)"
            >
              <span class="ci__avatar ci__avatar--grupo" aria-hidden="true">
                <i class="bi bi-people"></i>
              </span>
              <span class="ci__corpo">
                <span class="ci__topo1">
                  <strong class="ci__nome">{{ sl.nome }}</strong>
                  <span class="apagado pequeno">{{ quando(sl.ultima_em) }}</span>
                </span>
                <span class="ci__previa pequeno apagado">
                  <span v-if="sl.ultimo_autor" class="fraco">{{ sl.ultimo_autor }}: </span>
                  {{ sl.ultima_mensagem || `${sl.qtd_membros} pessoas` }}
                </span>
              </span>
              <span v-if="sl.nao_lidas" class="ci__badge">{{ sl.nao_lidas }}</span>
            </button>
          </template>

          <!-- ⚠️ Quem ainda não tem conversa aparece SÓ quando se procura ou
               quando não há conversa nenhuma: lista permanente de "todos os
               atendentes" é o que enchia a coluna antes. -->
          <template v-if="semConversa.length && (filtro.trim() || !salas.length)">
            <p class="ci__secao">Começar conversa</p>
            <button
              v-for="c in semConversa"
              :key="c.id"
              class="ci__sala"
              type="button"
              :disabled="abrindo"
              @click="falarCom(c.id)"
            >
              <span class="ci__avatar" :style="{ background: corDaInicial(c.nome) }"
                    aria-hidden="true">
                {{ iniciais(c.nome) }}
                <span class="ci__estado" :style="{ background: corDoEstado(c.estado) }"
                      :title="rotuloDoEstado(c.estado)"></span>
              </span>
              <span class="ci__corpo">
                <span class="ci__nome">{{ c.nome }}</span>
                <span class="ci__previa pequeno apagado">
                  {{ rotuloDoEstado(c.estado) }}
                </span>
              </span>
            </button>
          </template>

          <div v-if="!salas.length && !semConversa.length" class="vazio">
            <i class="bi bi-chat-left-dots vazio__icone" aria-hidden="true"></i>
            <p class="vazio__titulo">Nenhuma conversa ainda</p>
            <p>Não há outro atendente ativo com e-mail cadastrado.</p>
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
            <template v-for="(m, i) in mensagens" :key="m.id">
              <p v-if="comecaODia(m, i)" class="diario">
                <span class="diario__marca">{{ rotuloDoDia(m.criada_em) }}</span>
              </p>
              <!-- ⚠️ Mensagens seguidas da mesma pessoa viram um bloco:
                   repetir o nome em cada balão é o que dá cara de log. -->
              <div
                class="balao"
                :class="[m.minha ? 'balao--minha' : 'balao--dele',
                         { 'balao--seguida': mesmoAutor(m, i) }]"
              >
                <p v-if="!m.minha && !mesmoAutor(m, i)" class="balao__autor pequeno">
                  {{ m.autor }}
                </p>
                <p class="balao__texto">{{ m.texto }}</p>
                <p class="balao__rodape apagado pequeno">{{ hora(m.criada_em) }}</p>
              </div>
            </template>
          </div>

          <div class="cartao__corpo pilha">
            <label class="campo">
              <span class="so-leitor">Mensagem</span>
              <!-- 🚨 ENTER ENVIA, Shift+Enter quebra linha. `Ctrl+Enter` é o
                   que se usa na CAIXA DE ENTRADA, onde a mensagem vai para o
                   cliente e não volta. Aqui é conversa de equipe: a fricção
                   não se paga, e ela aparecia em toda mensagem. -->
              <textarea
                v-model="texto"
                class="campo__entrada"
                rows="2"
                maxlength="4000"
                placeholder="Escreva e aperte Enter"
                @keydown.enter.exact.prevent="enviar"
              ></textarea>
            </label>
            <div class="linha">
              <!-- Grade própria de emoji: ~4 KB e nenhuma dependência. -->
              <div class="emoji">
                <button
                  class="botao botao--contorno botao--icone"
                  type="button"
                  title="Emoji"
                  aria-label="Emoji"
                  :aria-expanded="emojiAberto"
                  @click.prevent="emojiAberto = !emojiAberto"
                >
                  <i class="bi bi-emoji-smile" aria-hidden="true"></i>
                </button>
                <div v-if="emojiAberto" class="emoji__caixa">
                  <div v-for="g in EMOJIS" :key="g.grupo" class="emoji__grupo">
                    <p class="emoji__titulo">{{ g.grupo }}</p>
                    <div class="emoji__grade">
                      <button
                        v-for="e in g.itens"
                        :key="e"
                        class="emoji__item"
                        type="button"
                        @click.prevent="porEmoji(e)"
                      >{{ e }}</button>
                    </div>
                  </div>
                </div>
              </div>

              <button
                class="botao botao--primario"
                type="button"
                :disabled="enviando || !texto.trim()"
                @click="enviar"
              >
                <span v-if="enviando" class="girando"></span>
                {{ enviando ? 'Enviando…' : 'Enviar' }}
              </button>
              <span class="apagado pequeno">Enter envia · Shift+Enter quebra linha</span>
            </div>
          </div>
        </template>
      </section>
    </div>
  </div>
</template>

<style scoped>
/* ---- coluna de pessoas e grupos ----------------------------------------- */
.ci__topo { display: flex; gap: var(--e-2); align-items: center; }
.ci__topo .busca { flex: 1 1 auto; }
.ci__lista { overflow-y: auto; min-height: 0; }

.ci__secao {
  margin: var(--e-3) 0 var(--e-1);
  padding: 0 var(--e-3);
  font-size: var(--txt-xs);
  text-transform: uppercase;
  letter-spacing: .06em;
  color: var(--texto-apagado);
}

.ci__sala {
  display: flex;
  align-items: center;
  gap: var(--e-3);
  width: 100%;
  padding: var(--e-2) var(--e-3);
  border: 0;
  background: none;
  text-align: left;
  cursor: pointer;
  font-family: var(--fonte);
}
.ci__sala:hover { background: var(--superficie-2); }
.ci__sala--aberta { background: var(--acento-suave); }

.ci__avatar {
  position: relative;
  flex: none;
  width: 36px;
  height: 36px;
  border-radius: var(--r-full);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: var(--txt-sm);
  font-weight: var(--peso-forte);
}
.ci__avatar--grupo { background: var(--superficie-3); color: var(--texto-fraco); }

/* O ponto de estado fica NO avatar, não numa coluna à parte: é sobre aquela
   pessoa, e ler os dois juntos é uma olhada só. */
.ci__estado {
  position: absolute;
  right: -1px;
  bottom: -1px;
  width: 11px;
  height: 11px;
  border-radius: var(--r-full);
  border: 2px solid var(--superficie);
}

.ci__corpo { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; }
.ci__topo1 { display: flex; justify-content: space-between; gap: var(--e-2); }
.ci__nome, .ci__previa {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ci__badge {
  flex: none;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: var(--r-full);
  background: var(--acento);
  color: var(--acento-texto);
  font-size: var(--txt-xs);
  line-height: 20px;
  text-align: center;
}

/* ---- separador de dia --------------------------------------------------- */
.diario {
  display: flex;
  align-items: center;
  gap: var(--e-3);
  margin: var(--e-4) 0 var(--e-2);
  color: var(--texto-apagado);
  font-size: var(--txt-sm);
}
.diario::before, .diario::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--borda);
}

/* Balão que continua o anterior: cola no de cima e perde o canto, como em
   qualquer mensageiro. */
.balao--seguida { margin-top: 2px; }

/* ---- emoji -------------------------------------------------------------- */
.emoji { position: relative; }
.emoji__caixa {
  position: absolute;
  bottom: calc(100% + var(--e-1));
  left: 0;
  z-index: var(--z-flutuante);
  width: 280px;
  max-height: 260px;
  overflow-y: auto;
  padding: var(--e-3);
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-lg);
  box-shadow: var(--sombra-2);
}
.emoji__titulo {
  margin: 0 0 var(--e-1);
  font-size: var(--txt-xs);
  text-transform: uppercase;
  letter-spacing: .06em;
  color: var(--texto-apagado);
}
.emoji__grupo + .emoji__grupo { margin-top: var(--e-3); }
.emoji__grade { display: flex; flex-wrap: wrap; gap: 2px; }
.emoji__item {
  border: 0;
  background: none;
  cursor: pointer;
  font-size: 20px;
  line-height: 1;
  padding: 4px;
  border-radius: var(--r-sm);
}
.emoji__item:hover { background: var(--superficie-2); }

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
