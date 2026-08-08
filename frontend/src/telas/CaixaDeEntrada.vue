<script setup>
/* ============================================================================
   ATD_1.1 — Caixa de entrada  ·  ATD_1.2 — Conversa
   ----------------------------------------------------------------------------
   Um componente serve as duas rotas: a conversa abre AO LADO da lista, como o
   06_Conteudo_das_Telas desenha. `/atendimento/:id` só entra já com uma
   selecionada.

   🚨 O QUE ESTA TELA NÃO FAZ, E PRECISA DIZER: não envia mensagem. `evolution.py`
   não tem rota de envio — Fase 1 é receber. O campo de resposta aparece
   desabilitado com o motivo à vista, pela mesma regra do "Esqueci minha senha":
   controle que existe e explica por que não funciona é honesto; controle que
   some muda a tela debaixo de quem usa.

   🚨 "NÃO IDENTIFICADO" É CASO NORMAL, NÃO EXCEÇÃO. Medido em 07/08: dos 9
   números que trocaram mensagem, 1 estava no cadastro. A lista mostra o
   telefone quando não há contato, e a ficha explica QUAL é o caso — não é
   cliente, ou o número responde por vários cadastros. As duas situações pedem
   ações diferentes de quem atende.
   ============================================================================ */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api, ErroDeApi } from '../api/cliente.js'

const route = useRoute()
const router = useRouter()

const lista = ref([])
const resumo = ref(null)
const aberta = ref(null)
const carregando = ref(true)
const erro = ref('')
const recado = ref('')
const filtro = ref('todas')
const busca = ref('')

/* Enquanto a IA não existe, transferir é a TRIAGEM feita por gente. */
const times = ref([])
const classificacoes = ref([])
const painelAcao = ref('')        // '' | 'transferir' | 'encerrar'
const timeEscolhido = ref('')
const motivo = ref('')
const classificacaoEscolhida = ref('')
const comentario = ref('')

const resposta = ref('')
const modoNota = ref(false)
const enviando = ref(false)

let timer = null

const FILTROS = [
  { valor: 'todas', rotulo: 'Todas' },
  { valor: 'sem_dono', rotulo: 'Sem dono' },
  { valor: 'minhas', rotulo: 'Minhas' },
]

function parametros() {
  const p = new URLSearchParams()
  if (filtro.value === 'sem_dono') p.set('sem_dono', 'true')
  if (filtro.value === 'minhas') p.set('minhas', 'true')
  if (busca.value.trim()) p.set('busca', busca.value.trim())
  return p.toString()
}

async function carregar({ silencioso = false } = {}) {
  if (!silencioso) carregando.value = true
  try {
    const [conversas, r] = await Promise.all([
      api.get(`/api/conversas?${parametros()}`),
      api.get('/api/conversas/resumo'),
    ])
    lista.value = conversas
    resumo.value = r
    erro.value = ''
  } catch (e) {
    if (!silencioso) erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao ler as conversas.'
  } finally {
    carregando.value = false
  }
}

async function abrir(id) {
  try {
    aberta.value = await api.get(`/api/conversas/${id}`)
    recado.value = ''
    if (route.params.id !== String(id)) {
      router.replace({ path: `/atendimento/${id}` })
    }
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao abrir a conversa.'
  }
}

async function assumir() {
  try {
    await api.post(`/api/conversas/${aberta.value.id}/assumir`)
    recado.value = 'Conversa assumida.'
    await Promise.all([abrir(aberta.value.id), carregar({ silencioso: true })])
  } catch (e) {
    // 🚨 409 aqui é o caso projetado: outra pessoa clicou primeiro.
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui assumir.'
  }
}

const exigeComentario = computed(() => {
  const c = classificacoes.value.find((x) => String(x.id) === String(classificacaoEscolhida.value))
  return Boolean(c && c.exige_comentario)
})

async function enviar() {
  const texto = resposta.value.trim()
  if (!texto || enviando.value) return
  enviando.value = true
  erro.value = ''
  recado.value = ''
  const caminho = modoNota.value ? 'nota' : 'responder'
  try {
    await api.post(`/api/conversas/${aberta.value.id}/${caminho}`, { texto })
    resposta.value = ''
    // 🚨 Recarrega a conversa em vez de empurrar o balão na mão: o que vale é
    // o que o banco gravou, não o que a tela supõe ter acontecido.
    await Promise.all([abrir(aberta.value.id), carregar({ silencioso: true })])
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui enviar.'
  } finally {
    enviando.value = false
  }
}

async function transferir() {
  try {
    await api.post(`/api/conversas/${aberta.value.id}/transferir`, {
      time_id: Number(timeEscolhido.value) || null,
      observacao: motivo.value || null,
    })
    recado.value = 'Transferida — a conversa foi para a fila desse time.'
    painelAcao.value = ''
    timeEscolhido.value = ''
    motivo.value = ''
    await Promise.all([abrir(aberta.value.id), carregar({ silencioso: true })])
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui transferir.'
  }
}

async function devolver() {
  try {
    await api.post(`/api/conversas/${aberta.value.id}/devolver`)
    recado.value = 'Devolvida para a fila.'
    await Promise.all([abrir(aberta.value.id), carregar({ silencioso: true })])
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui devolver.'
  }
}

async function encerrar() {
  try {
    await api.post(`/api/conversas/${aberta.value.id}/encerrar`, {
      classificacao_id: Number(classificacaoEscolhida.value),
      comentario: comentario.value || null,
    })
    recado.value = 'Encerrada. Ela passa a aparecer no Histórico.'
    painelAcao.value = ''
    classificacaoEscolhida.value = ''
    comentario.value = ''
    await Promise.all([abrir(aberta.value.id), carregar({ silencioso: true })])
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui encerrar.'
  }
}

onMounted(async () => {
  await carregar()
  try {
    ;[times.value, classificacoes.value] = await Promise.all([
      api.get('/api/times'),
      api.get('/api/classificacoes'),
    ])
  } catch {
    // sem estes a tela ainda mostra conversa; só as ações ficam sem opção
  }
  if (route.params.id) await abrir(route.params.id)
  // A fila é consumida a cada 5s no servidor; a tela reflete isso sem F5.
  timer = setInterval(() => carregar({ silencioso: true }), 8000)
})

onUnmounted(() => clearInterval(timer))

watch(filtro, () => carregar())

const filaParada = computed(
  () => resumo.value && resumo.value.eventos_pendentes > 50,
)

function quem(c) {
  return c.contato_nome || c.telefone_e164
}

function quando(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const agora = new Date()
  const min = Math.round((agora - d) / 60000)
  if (min < 1) return 'agora'
  if (min < 60) return `${min} min`
  if (min < 60 * 24) return `${Math.round(min / 60)} h`
  return d.toLocaleDateString('pt-BR')
}

function hora(iso) {
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

const ICONE = {
  imagem: 'bi-image', audio: 'bi-mic', video: 'bi-camera-video',
  documento: 'bi-file-earmark', figurinha: 'bi-emoji-smile',
  localizacao: 'bi-geo-alt', contato: 'bi-person-vcard',
}
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Caixa de entrada</h1>
        <p class="fraco pequeno">
          O que chegou pelo WhatsApp. A conversa abre ao lado.
        </p>
      </div>
      <div v-if="resumo" class="linha">
        <span class="chip">{{ resumo.conversas }} conversas</span>
        <span class="chip chip--aviso">{{ resumo.sem_dono }} sem dono</span>
        <span class="chip">{{ resumo.mensagens }} mensagens</span>
        <!-- Ignorado é NÚMERO, não problema: informativo e grupo são descarte
             de propósito. Ficava no contador de erro até 07/08. -->
        <span
          v-if="resumo.eventos_ignorados"
          class="chip"
          title="Eventos descartados de propósito: canal informativo e grupo. Não é falha."
        >{{ resumo.eventos_ignorados }} ignorados</span>
      </div>
    </header>

    <p v-if="filaParada" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>
        <strong>{{ resumo.eventos_pendentes }} eventos esperando processamento.</strong>
        A fila pode ter parado — mensagem chegando e não virando conversa parece
        "nenhuma mensagem nova", que é o pior jeito de falhar.
      </span>
    </p>
    <p v-else-if="resumo && resumo.eventos_com_erro" class="aviso aviso--atencao" role="status">
      <i class="bi bi-exclamation-triangle aviso__icone" aria-hidden="true"></i>
      <span>{{ resumo.eventos_com_erro }} evento(s) com erro de interpretação — o payload cru está guardado e dá para reprocessar.</span>
    </p>

    <p v-if="erro" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>{{ erro }}</span>
    </p>
    <p v-if="recado" class="aviso aviso--ok" role="status">
      <i class="bi bi-check-circle aviso__icone" aria-hidden="true"></i>
      <span>{{ recado }}</span>
    </p>

    <div class="painel">
      <!-- ---------------------------------------------------------- LISTA -->
      <section class="cartao coluna">
        <header class="cartao__cabecalho">
          <div class="linha linha--quebra">
            <button
              v-for="f in FILTROS"
              :key="f.valor"
              class="botao botao--pequeno"
              :class="filtro === f.valor ? 'botao--primario' : 'botao--fantasma'"
              type="button"
              @click="filtro = f.valor"
            >
              {{ f.rotulo }}
            </button>
          </div>
        </header>

        <div class="cartao__corpo">
          <label class="campo">
            <span class="so-leitor">Buscar</span>
            <input
              v-model="busca"
              class="campo__entrada"
              type="search"
              placeholder="nome ou telefone"
              @keyup.enter="carregar()"
            />
            <span class="campo__ajuda">Telefone em qualquer grafia encontra o mesmo número.</span>
          </label>
        </div>

        <p v-if="carregando" class="linha fraco cartao__corpo">
          <span class="girando"></span> Lendo…
        </p>

        <div v-else-if="!lista.length" class="vazio">
          <i class="bi bi-chat-dots vazio__icone" aria-hidden="true"></i>
          <p class="vazio__titulo">Nenhuma conversa</p>
          <p>Assim que alguém escrever, ela aparece aqui sozinha.</p>
        </div>

        <ul v-else class="conversas">
          <li v-for="c in lista" :key="c.id">
            <button
              class="conversa"
              :class="{ 'conversa--aberta': aberta && aberta.id === c.id }"
              type="button"
              @click="abrir(c.id)"
            >
              <div class="conversa__topo">
                <strong class="conversa__quem">{{ quem(c) }}</strong>
                <span class="apagado pequeno">{{ quando(c.ultima_atividade_em) }}</span>
              </div>
              <p class="conversa__previa apagado pequeno">
                <i v-if="ICONE[c.ultimo_tipo]" class="bi" :class="ICONE[c.ultimo_tipo]" aria-hidden="true"></i>
                <span v-if="c.ultima_direcao === 'saida'" class="fraco">você: </span>
                {{ c.ultima_mensagem || '(sem texto)' }}
              </p>
              <div class="linha pequeno">
                <span v-if="!c.contato_nome" class="chip chip--aviso">não identificado</span>
                <span v-if="c.cliente_nome" class="chip">{{ c.cliente_nome }}</span>
                <span v-if="c.atendente_nome" class="chip chip--acento">{{ c.atendente_nome }}</span>
                <span v-else class="chip">sem dono</span>
              </div>
            </button>
          </li>
        </ul>
      </section>

      <!-- ------------------------------------------------------- CONVERSA -->
      <section class="cartao coluna coluna--larga">
        <div v-if="!aberta" class="vazio">
          <i class="bi bi-chat-text vazio__icone" aria-hidden="true"></i>
          <p class="vazio__titulo">Escolha uma conversa</p>
          <p>A ficha do cliente entra aqui na ATD_2.1, consultando o FPSL.</p>
        </div>

        <template v-else>
          <header class="cartao__cabecalho">
            <div>
              <strong>{{ aberta.contato_nome || aberta.telefone_e164 }}</strong>
              <p class="apagado pequeno mono">
                {{ aberta.telefone_e164 }}
                <span v-if="aberta.canal_nome"> · {{ aberta.canal_nome }}</span>
                · {{ aberta.estado }}
              </p>
            </div>
            <button
              v-if="!aberta.atendente_id"
              class="botao botao--pequeno botao--primario"
              type="button"
              @click="assumir"
            >
              Assumir
            </button>
            <span v-else class="chip chip--acento">{{ aberta.atendente_nome }}</span>
          </header>

          <p v-if="!aberta.contato_id" class="aviso aviso--atencao">
            <i class="bi bi-person-exclamation aviso__icone" aria-hidden="true"></i>
            <span v-if="aberta.candidatos.length">
              <strong>Número compartilhado:</strong> responde por
              {{ aberta.candidatos.length }} cadastros
              ({{ aberta.candidatos.map((c) => c.nome).join(', ') }}).
              Não vinculei a nenhum — chutar produziria ficha errada.
            </span>
            <span v-else>
              <strong>Não identificado:</strong> este número não está no cadastro
              do Harmonit. Pode não ser cliente, ou o telefone dele estar
              desatualizado lá.
            </span>
          </p>

          <div class="baloes">
            <div
              v-for="m in aberta.mensagens"
              :key="m.id"
              class="balao"
              :class="`balao--${m.direcao}`"
            >
              <p v-if="m.tipo !== 'texto'" class="balao__tipo pequeno">
                <i class="bi" :class="ICONE[m.tipo] || 'bi-paperclip'" aria-hidden="true"></i>
                {{ m.tipo }}
                <span class="fraco">— mídia não é baixada na Fase 1</span>
              </p>
              <p v-if="m.conteudo" class="balao__texto">{{ m.conteudo }}</p>
              <p v-else class="balao__texto fraco">(sem texto)</p>
              <p class="balao__rodape apagado pequeno">
                {{ hora(m.criada_em) }}
                <span v-if="m.entrega"> · {{ m.entrega }}</span>
              </p>
            </div>
          </div>

          <div v-if="aberta.estado !== 'resolvida'" class="acoes cartao__corpo">
            <div class="linha linha--quebra">
              <button
                class="botao botao--pequeno botao--contorno"
                type="button"
                @click="painelAcao = painelAcao === 'transferir' ? '' : 'transferir'"
              >
                <i class="bi bi-arrow-left-right" aria-hidden="true"></i> Transferir
              </button>
              <button
                v-if="aberta.atendente_id"
                class="botao botao--pequeno botao--fantasma"
                type="button"
                @click="devolver"
              >
                Devolver à fila
              </button>
              <button
                class="botao botao--pequeno botao--contorno"
                type="button"
                @click="painelAcao = painelAcao === 'encerrar' ? '' : 'encerrar'"
              >
                <i class="bi bi-check2-square" aria-hidden="true"></i> Encerrar
              </button>
            </div>

            <div v-if="painelAcao === 'transferir'" class="pilha acoes__painel">
              <p class="campo__ajuda">
                🚨 Enquanto a IA está desligada, <strong>isto é a triagem</strong>:
                você lê e decide o destino. Transferir para time tira o dono — a
                conversa volta a ser responsabilidade coletiva.
              </p>
              <label class="campo">
                <span class="campo__rotulo">Time</span>
                <select v-model="timeEscolhido" class="campo__entrada">
                  <option value="">escolha…</option>
                  <option v-for="t in times" :key="t.id" :value="t.id">
                    {{ t.nome }}{{ t.qtd_membros ? '' : ' — sem ninguém dentro!' }}
                  </option>
                </select>
                <span class="campo__ajuda">
                  Time sem membro aceita a transferência, mas ninguém recebe.
                </span>
              </label>
              <label class="campo">
                <span class="campo__rotulo">Resumo para quem vai receber</span>
                <input v-model="motivo" class="campo__entrada" maxlength="2000" />
                <span class="campo__ajuda">
                  O que já foi conversado. Quem assume não deve precisar ler
                  tudo de novo.
                </span>
              </label>
              <button class="botao botao--primario" type="button" :disabled="!timeEscolhido" @click="transferir">
                Transferir
              </button>
            </div>

            <div v-if="painelAcao === 'encerrar'" class="pilha acoes__painel">
              <label class="campo">
                <span class="campo__rotulo">Classificação</span>
                <select v-model="classificacaoEscolhida" class="campo__entrada">
                  <option value="">escolha…</option>
                  <option v-for="c in classificacoes" :key="c.id" :value="c.id">{{ c.nome }}</option>
                </select>
                <span class="campo__ajuda">
                  Obrigatória: é ela que responde depois "no que gastamos
                  atendimento".
                </span>
              </label>
              <label v-if="exigeComentario" class="campo">
                <span class="campo__rotulo">Comentário — obrigatório nesta</span>
                <textarea v-model="comentario" class="campo__entrada" rows="2" maxlength="2000"></textarea>
                <span class="campo__ajuda">
                  Sem isto, "Outro" vira o vale-tudo onde metade das conversas
                  acaba e o analytics morre.
                </span>
              </label>
              <button
                class="botao botao--primario"
                type="button"
                :disabled="!classificacaoEscolhida || (exigeComentario && !comentario.trim())"
                @click="encerrar"
              >
                Encerrar conversa
              </button>
            </div>
          </div>

          <p v-else class="aviso aviso--ok">
            <i class="bi bi-check-circle aviso__icone" aria-hidden="true"></i>
            <span>Conversa encerrada. Ela está no Histórico (ATD_5.1).</span>
          </p>

          <div v-if="aberta.estado !== 'resolvida'" class="cartao__corpo pilha">
            <div class="linha linha--quebra">
              <button
                class="botao botao--pequeno"
                :class="modoNota ? 'botao--fantasma' : 'botao--primario'"
                type="button"
                @click="modoNota = false"
              >
                Responder o cliente
              </button>
              <button
                class="botao botao--pequeno"
                :class="modoNota ? 'botao--primario' : 'botao--fantasma'"
                type="button"
                @click="modoNota = true"
              >
                <i class="bi bi-sticky" aria-hidden="true"></i> Nota interna
              </button>
            </div>

            <label class="campo">
              <span class="so-leitor">{{ modoNota ? 'Nota interna' : 'Resposta' }}</span>
              <textarea
                v-model="resposta"
                class="campo__entrada"
                :class="{ 'campo--nota': modoNota }"
                rows="3"
                maxlength="4000"
                :placeholder="modoNota
                  ? 'Fica na conversa e NUNCA vai para o cliente'
                  : 'Escreva e aperte Ctrl+Enter para enviar'"
                @keydown.ctrl.enter.prevent="enviar"
              ></textarea>
              <span class="campo__ajuda">
                <template v-if="modoNota">
                  🚨 Nota interna não sai para o cliente — o banco amarra os dois
                  campos para ela não vazar como mensagem.
                </template>
                <template v-else>
                  Vai pelo WhatsApp, para <strong>{{ aberta.telefone_e164 }}</strong>.
                  Não dá para escolher outro destinatário: o número sai da
                  conversa.
                </template>
              </span>
            </label>

            <div class="linha linha--quebra">
              <button
                class="botao botao--primario"
                type="button"
                :disabled="enviando || !resposta.trim()"
                @click="enviar"
              >
                <span v-if="enviando" class="girando"></span>
                {{ enviando ? 'Enviando…' : (modoNota ? 'Salvar nota' : 'Enviar') }}
              </button>
              <span class="apagado pequeno">
                ⚠️ Envio de arquivo entra na Fase 2. Recebimento já funciona.
              </span>
            </div>
          </div>
        </template>
      </section>
    </div>
  </div>
</template>

<style scoped>
.tela { max-width: 1280px; }

.tela__cabecalho {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--e-4);
  flex-wrap: wrap;
  margin-bottom: var(--e-4);
}
.tela__cabecalho p { max-width: var(--largura-texto); margin-top: var(--e-1); }

.painel {
  display: grid;
  grid-template-columns: minmax(280px, 360px) 1fr;
  gap: var(--e-4);
  align-items: start;
}
@media (max-width: 860px) {
  .painel { grid-template-columns: 1fr; }
}

.coluna { overflow: hidden; }

.conversas { list-style: none; margin: 0; padding: 0; max-height: 60vh; overflow-y: auto; }

.conversa {
  display: block;
  width: 100%;
  text-align: left;
  background: none;
  border: 0;
  border-top: 1px solid var(--borda, rgba(128, 128, 128, .25));
  padding: var(--e-3);
  cursor: pointer;
}
.conversa:hover { background: rgba(128, 128, 128, .08); }
.conversa--aberta { background: rgba(128, 128, 128, .14); }

.conversa__topo { display: flex; justify-content: space-between; gap: var(--e-2); }
.conversa__quem { overflow-wrap: anywhere; }
.conversa__previa {
  margin: var(--e-1) 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.baloes {
  display: flex;
  flex-direction: column;
  gap: var(--e-2);
  padding: var(--e-3);
  max-height: 52vh;
  overflow-y: auto;
}

.balao {
  max-width: 78%;
  padding: var(--e-2) var(--e-3);
  border-radius: var(--raio, 12px);
  background: rgba(128, 128, 128, .12);
}
.balao--saida { align-self: flex-end; background: rgba(37, 211, 102, .16); }
.balao--interna { align-self: center; background: rgba(255, 193, 7, .16); font-style: italic; }

.balao__texto { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.balao__tipo { margin: 0 0 var(--e-1); }
.balao__rodape { margin: var(--e-1) 0 0; }

.linha--quebra { flex-wrap: wrap; gap: var(--e-2); }

.acoes { border-top: 1px solid var(--borda, rgba(128, 128, 128, .25)); }

textarea.campo__entrada { resize: vertical; }
.campo--nota { background: rgba(255, 193, 7, .10); }
.acoes__painel { margin-top: var(--e-3); }
</style>
