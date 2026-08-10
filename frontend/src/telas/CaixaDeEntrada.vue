<script setup>
/* ============================================================================
   ATD_1.1 — Caixa de entrada  ·  ATD_1.2 — Conversa
   ----------------------------------------------------------------------------
   Um componente serve as duas rotas: a conversa abre AO LADO da lista, como o
   06_Conteudo_das_Telas desenha. `/atendimento/:id` só entra já com uma
   selecionada.

   🚨 A MÍDIA VEM DO WEBHOOK, NÃO DE DOWNLOAD. O Evolution entrega o binário
   em `base64` dentro do próprio evento; o backend só o move para o disco. Aqui
   ele é buscado por `pedirBlob` porque o token vive no cabeçalho e <img src>
   não carrega cabeçalho — apontar o `src` para a rota daria 401 mudo.

   🚨 "NÃO IDENTIFICADO" É CASO NORMAL, NÃO EXCEÇÃO. Medido em 07/08: dos 9
   números que trocaram mensagem, 1 estava no cadastro. A lista mostra o
   telefone quando não há contato, e a ficha explica QUAL é o caso — não é
   cliente, ou o número responde por vários cadastros. As duas situações pedem
   ações diferentes de quem atende.
   ============================================================================ */
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api, pedirBlob, ErroDeApi } from '../api/cliente.js'

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
    // Solta o que a conversa anterior segurava ANTES de trocar: o object URL
    // da foto de outro cliente não tem por que continuar vivo.
    soltarMidias()
    gaveta.value = false
    empresas.value = []
    empresasAbertas.value = false
    buscaCliente.value = ''
    achadosCliente.value = []
    aberta.value = await api.get(`/api/conversas/${id}`)
    carregarMidiasDaConversa(aberta.value)
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

/* Quem está falando, na ordem do WhatsApp: o apelido que a pessoa escolheu,
   depois o nome do cadastro, e o número só quando não há nem um nem outro.

   🚨 O apelido vem PRIMEIRO de propósito. 35 das 37 conversas não têm vínculo
   com o cadastro -- com `contato_nome` na frente, a tela mostrava número cru
   quase sempre, num painel em que o nome da pessoa já tinha chegado. */
function quem(c) {
  return c.nome_whatsapp || c.contato_nome || c.telefone_e164
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

/* ---- mídia --------------------------------------------------------------
   O que aparece dentro do balão (imagem, figurinha, áudio, vídeo) é buscado
   sob demanda e guardado aqui pelo id da mídia. Documento não é pré-carregado:
   nada ganha em baixar um PDF que ninguém abriu.

   ⚠️ Os object URLs são liberados ao trocar de conversa. Sem isso o navegador
   segura o binário de toda conversa já aberta -- num painel que fica aberto o
   dia inteiro, isso vira centenas de MB. */
const midias = reactive({})
const MOSTRAM_SOZINHAS = ['imagem', 'figurinha', 'audio', 'video']

function tamanhoLegivel(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

async function carregarMidia(m) {
  if (!m.midia_id || midias[m.midia_id] !== undefined) return
  midias[m.midia_id] = ''   // marca "em andamento": evita buscar duas vezes
  try {
    const blob = await pedirBlob(`/api/midia/${m.midia_id}/ver`)
    midias[m.midia_id] = URL.createObjectURL(blob)
  } catch {
    // Falhar aqui não pode derrubar a conversa: o balão mostra o botão de
    // baixar e o texto, que é o que importa.
    midias[m.midia_id] = null
  }
}

function soltarMidias() {
  for (const [id, url] of Object.entries(midias)) {
    if (url) URL.revokeObjectURL(url)
    delete midias[id]
  }
}

async function baixarMidia(m) {
  const blob = await pedirBlob(`/api/midia/${m.midia_id}`)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = m.midia_nome || `midia-${m.midia_id}`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

/* ---- gaveta do contato ---------------------------------------------------
   Abre por botão, como clicar no contato no WhatsApp. Quando há vínculo mostra
   a empresa; quando não há -- que é o caso de 35 das 41 conversas -- mostra a
   busca para vincular à mão.

   🚨 A busca é o produto aqui, não um detalhe. 51% dos clientes ativos estão
   fora do alcance por cadastro incompleto; cada vínculo feito nesta gaveta é
   um telefone que passa a existir, digitado por quem está falando com a
   pessoa. */
const gaveta = ref(false)

/* As empresas que o telefone alcança -- o grupo da pessoa.

   🚨 Número em vários cadastros NÃO é ambiguidade: são grupos empresariais
   com o mesmo responsável. A identidade é da PESSOA; as empresas são consulta
   rápida, atrás de um botão, com CNPJ para conferir. */
const empresas = ref([])
const empresasAbertas = ref(false)
const buscandoEmpresas = ref(false)

async function verEmpresas() {
  empresasAbertas.value = !empresasAbertas.value
  if (!empresasAbertas.value || empresas.value.length) return
  buscandoEmpresas.value = true
  try {
    const r = await api.get(`/api/conversas/${aberta.value.id}/empresas`)
    empresas.value = r.empresas || []
  } catch {
    empresas.value = []
  } finally {
    buscandoEmpresas.value = false
  }
}
const buscaCliente = ref('')
const achadosCliente = ref([])
const buscando = ref(false)
const vinculando = ref(false)

async function procurarCliente() {
  const termo = buscaCliente.value.trim()
  if (termo.length < 2) {
    achadosCliente.value = []
    return
  }
  buscando.value = true
  try {
    const r = await api.get(`/api/conversas/buscar-empresa?termo=${encodeURIComponent(termo)}`)
    achadosCliente.value = r.itens || r.lista || []
  } catch {
    achadosCliente.value = []
  } finally {
    buscando.value = false
  }
}

async function vincularA(clienteId) {
  vinculando.value = true
  try {
    await api.post(`/api/conversas/${aberta.value.id}/vincular`, { cliente_id: clienteId })
    // Relê do servidor em vez de remendar a tela: o vínculo pode ter criado
    // contato novo, e o que vale é o que o banco diz.
    await abrir(aberta.value.id)
    await carregar({ silencioso: true })
    recado.value = 'Número vinculado ao cadastro.'
    buscaCliente.value = ''
    achadosCliente.value = []
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao vincular.'
  } finally {
    vinculando.value = false
  }
}

async function desvincular() {
  try {
    await api.post(`/api/conversas/${aberta.value.id}/desvincular`)
    await abrir(aberta.value.id)
    await carregar({ silencioso: true })
    recado.value = 'Vínculo desfeito. O telefone continua no cadastro.'
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao desvincular.'
  }
}

function documentoLegivel(d) {
  if (!d) return ''
  const s = String(d)
  if (s.length === 14) return s.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, '$1.$2.$3/$4-$5')
  if (s.length === 11) return s.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4')
  return s
}

function carregarMidiasDaConversa(c) {
  if (!c || !c.mensagens) return
  for (const m of c.mensagens) {
    if (m.midia_id && MOSTRAM_SOZINHAS.includes(m.tipo)) carregarMidia(m)
  }
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
                <!-- "não identificado" fala do CADASTRO, não do nome: ter apelido
                     do WhatsApp não quer dizer que se saiba de qual cliente é. -->
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
              <strong>{{ aberta.nome_whatsapp || aberta.contato_nome || aberta.telefone_e164 }}</strong>
              <button
                class="botao botao--pequeno botao--fantasma"
                type="button"
                :aria-expanded="gaveta"
                @click="gaveta = !gaveta"
              >
                <i class="bi bi-person-lines-fill" aria-hidden="true"></i>
                {{ gaveta ? 'Fechar ficha' : 'Ver ficha' }}
              </button>
              <p class="apagado pequeno mono">
                {{ aberta.telefone_e164 }}
                <span v-if="aberta.nome_whatsapp && aberta.contato_nome">
                  · cadastro: {{ aberta.contato_nome }}
                </span>
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

          <!-- ================= GAVETA DO CONTATO ================= -->
          <aside v-if="gaveta" class="gaveta">
            <p class="gaveta__topo">
              <strong>{{ aberta.nome_whatsapp || 'Sem nome no WhatsApp' }}</strong>
              <span class="apagado pequeno mono">{{ aberta.telefone_e164 }}</span>
            </p>

            <!-- Empresas do grupo desta pessoa. Consulta, não escolha: o
                 número identifica quem fala, não a empresa do assunto. -->
            <button
              class="botao botao--pequeno botao--contorno"
              type="button"
              :aria-expanded="empresasAbertas"
              @click="verEmpresas"
            >
              <i class="bi bi-buildings" aria-hidden="true"></i>
              {{ empresasAbertas ? 'Ocultar empresas' : 'Empresas vinculadas' }}
            </button>

            <div v-if="empresasAbertas" class="gaveta__bloco">
              <p v-if="buscandoEmpresas" class="apagado pequeno">consultando…</p>
              <p v-else-if="!empresas.length" class="apagado pequeno">
                Este número não está em nenhum cadastro.
              </p>
              <ul v-else class="gaveta__lista">
                <li v-for="e in empresas" :key="e.id" class="gaveta__empresa">
                  <strong>{{ e.nome }}</strong>
                  <span v-if="!e.ativo" class="chip chip--erro">inativa</span>
                  <span class="apagado pequeno mono">{{ documentoLegivel(e.documento) || 'sem CNPJ' }}</span>
                  <span class="apagado pequeno">contato: {{ e.contato_nome }}</span>
                </li>
              </ul>
              <p v-if="empresas.length > 1" class="apagado pequeno">
                {{ empresas.length }} empresas do mesmo responsável. A conversa
                fica na pessoa; a empresa se escolhe quando o assunto exigir.
              </p>
            </div>

            <!-- COM vínculo: os dados da empresa -->
            <template v-if="aberta.empresa && aberta.empresa.cliente">
              <dl class="gaveta__dados">
                <dt>Empresa</dt>
                <dd>
                  {{ aberta.empresa.cliente.nome }}
                  <span v-if="!aberta.empresa.cliente.ativo" class="chip chip--erro">inativo</span>
                </dd>
                <template v-if="aberta.empresa.cliente.nome_fantasia">
                  <dt>Nome fantasia</dt>
                  <dd>{{ aberta.empresa.cliente.nome_fantasia }}</dd>
                </template>
                <template v-if="aberta.empresa.cliente.documento">
                  <dt>CNPJ/CPF</dt>
                  <dd class="mono">{{ documentoLegivel(aberta.empresa.cliente.documento) }}</dd>
                </template>
                <template v-if="aberta.empresa.cliente.email">
                  <dt>E-mail</dt>
                  <dd>{{ aberta.empresa.cliente.email }}</dd>
                </template>
                <!-- ⚠️ NÃO mostrar `contato.papeis` aqui. Os papéis existem no
                     banco desde a migração 001, vieram do modelo do ERP e não
                     acionam nada; anunciá-los na ficha promete recurso que não
                     existe, sobre um eixo que não é do atendimento. -->
                <dt>Contato</dt>
                <dd>{{ aberta.empresa.contato.nome }}</dd>
                <template v-if="aberta.empresa.contato.email">
                  <dt>E-mail do contato</dt>
                  <dd>{{ aberta.empresa.contato.email }}</dd>
                </template>
              </dl>
              <button class="botao botao--pequeno botao--fantasma" type="button" @click="desvincular">
                <i class="bi bi-x-circle" aria-hidden="true"></i> Desvincular
              </button>
            </template>

            <!-- SEM vínculo: o caso comum. Buscar e vincular. -->
            <template v-else>
              <p class="chip chip--aviso">Não está no cadastro</p>
              <p class="apagado pequeno">
                Procure a empresa e vincule este número. O telefone entra no
                cadastro marcado como vindo do atendimento.
              </p>

              <!-- Candidatos que o próprio sistema já achou pelo telefone -->
              <div v-if="aberta.candidatos && aberta.candidatos.length" class="gaveta__bloco">
                <p class="pequeno fraco">Este número responde por mais de um cadastro:</p>
                <button
                  v-for="c in aberta.candidatos"
                  :key="c.id"
                  class="botao botao--pequeno botao--contorno gaveta__achado"
                  type="button"
                  :disabled="vinculando"
                  @click="vincularA(c.cliente_id || c.id)"
                >
                  {{ c.nome }}
                </button>
              </div>

              <label class="campo">
                <span class="campo__rotulo">Buscar empresa</span>
                <input
                  v-model="buscaCliente"
                  class="campo__entrada"
                  type="search"
                  placeholder="nome, CNPJ ou CPF"
                  @input="procurarCliente"
                />
              </label>

              <p v-if="buscando" class="apagado pequeno">procurando…</p>
              <ul v-else-if="achadosCliente.length" class="gaveta__lista">
                <li v-for="c in achadosCliente" :key="c.id">
                  <button
                    class="botao botao--pequeno botao--contorno gaveta__achado"
                    type="button"
                    :disabled="vinculando"
                    @click="vincularA(c.id)"
                  >
                    <span>{{ c.nome }}</span>
                    <span class="apagado pequeno mono">{{ documentoLegivel(c.documento) }}</span>
                  </button>
                </li>
              </ul>
              <p v-else-if="buscaCliente.length >= 2" class="apagado pequeno">
                Nenhuma empresa com esse termo.
              </p>
            </template>
          </aside>

          <div class="baloes">
            <div
              v-for="m in aberta.mensagens"
              :key="m.id"
              class="balao"
              :class="`balao--${m.direcao}`"
            >
              <!-- A mensagem que esta está respondendo. Sem isto, uma foto
                   seguida de "esse aqui" fica ininteligível. -->
              <p v-if="m.citada_id" class="balao__citada pequeno">
                <i class="bi bi-reply" aria-hidden="true"></i>
                <span class="fraco">{{ m.citada_autor === 'cliente' ? 'cliente' : 'nós' }}:</span>
                {{ m.citada_conteudo || `(${m.citada_tipo})` }}
              </p>

              <img
                v-if="m.midia_id && ['imagem', 'figurinha'].includes(m.tipo) && midias[m.midia_id]"
                :src="midias[m.midia_id]"
                class="balao__imagem"
                :alt="m.conteudo || 'imagem enviada pelo cliente'"
              />
              <audio
                v-else-if="m.midia_id && m.tipo === 'audio' && midias[m.midia_id]"
                :src="midias[m.midia_id]"
                controls
                class="balao__audio"
              ></audio>
              <video
                v-else-if="m.midia_id && m.tipo === 'video' && midias[m.midia_id]"
                :src="midias[m.midia_id]"
                controls
                class="balao__imagem"
              ></video>

              <p v-if="m.tipo !== 'texto'" class="balao__tipo pequeno">
                <i class="bi" :class="ICONE[m.tipo] || 'bi-paperclip'" aria-hidden="true"></i>
                {{ m.midia_nome || m.tipo }}
                <span v-if="m.midia_tamanho" class="fraco">· {{ tamanhoLegivel(m.midia_tamanho) }}</span>
                <button
                  v-if="m.midia_id"
                  class="botao botao--pequeno botao--fantasma"
                  type="button"
                  @click="baixarMidia(m)"
                >
                  <i class="bi bi-download" aria-hidden="true"></i> Baixar
                </button>
                <span v-else class="fraco">— sem arquivo guardado</span>
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
/* A ficha é uma faixa dentro da conversa, não uma tela: some ao trocar de
   conversa e não tem rota. É o equivalente a clicar no contato no WhatsApp. */
.gaveta {
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--raio-2);
  background: var(--superficie-2);
  padding: var(--e-3);
  margin-bottom: var(--e-3);
  display: flex;
  flex-direction: column;
  gap: var(--e-2);
}
.gaveta__topo {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.gaveta__dados {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: var(--e-1) var(--e-3);
  margin: 0;
}
.gaveta__dados dt {
  color: var(--texto-fraco);
  font-size: var(--txt-sm);
}
.gaveta__dados dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.gaveta__bloco {
  display: flex;
  flex-direction: column;
  gap: var(--e-1);
}
.gaveta__lista {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--e-1);
  max-height: 240px;
  overflow-y: auto;
}
.gaveta__empresa {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--e-2);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--raio-1);
  background: var(--superficie);
}
.gaveta__achado {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--e-2);
  text-align: left;
}
/* A imagem ocupa a largura do balão, com teto de altura: foto de celular em
   pé tem 4000px e empurraria a conversa inteira para fora da tela. */
.balao__imagem {
  display: block;
  max-width: 100%;
  max-height: 320px;
  width: auto;
  border-radius: var(--raio-2);
  margin-bottom: var(--e-2);
  background: var(--superficie-2);
}
.balao__audio {
  width: 100%;
  max-width: 320px;
  margin-bottom: var(--e-2);
}
/* A citação é uma faixa presa à esquerda, como no WhatsApp: precisa parecer
   subordinada à mensagem, não outra mensagem. */
.balao__citada {
  border-left: 3px solid var(--acento-borda);
  padding: var(--e-1) var(--e-2);
  margin-bottom: var(--e-2);
  background: var(--superficie-2);
  border-radius: var(--raio-1);
  color: var(--texto-fraco);
  overflow-wrap: anywhere;
}
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
