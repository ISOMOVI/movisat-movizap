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
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api, pedirBlob, ErroDeApi } from '../api/cliente.js'
import { marcar, partir } from '../util/destaque.js'

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
const enviando = ref(false)

/* ---- buscar DENTRO da conversa (ATD_1.2) --------------------------------
   Pergunta diferente da busca da lista: lá é "com quem eu falei", aqui é
   "onde ele disse isso". Por isso são dois campos e não um.

   ⚠️ RODA NO NAVEGADOR, sem rota nova: as mensagens já estão carregadas em
   `aberta.mensagens`. Uma rota faria o servidor reler o que a tela já tem.

   🚨 SÓ ACHA O QUE FOI CARREGADO. O backend manda no máximo
   `teto_mensagens` e avisa em `truncada`. Numa conversa truncada, "não
   encontrado" seria mentira -- a tela precisa dizer que está vendo um pedaço.
   Nenhuma conversa passou do teto ainda (a maior tem 130 de 1.000). */
const buscaNaConversa = ref('')
const achadoAtual = ref(0)

const achadosNaConversa = computed(() => {
  const alvo = buscaNaConversa.value.trim().toLowerCase()
  if (!alvo || !aberta.value) return []
  return aberta.value.mensagens
    .filter((m) => (m.conteudo || '').toLowerCase().includes(alvo))
    .map((m) => m.id)
})

const idAchado = computed(() => achadosNaConversa.value[achadoAtual.value] ?? null)

function casaNaConversa(m) {
  const alvo = buscaNaConversa.value.trim().toLowerCase()
  return Boolean(alvo && (m.conteudo || '').toLowerCase().includes(alvo))
}

function irParaAchado(passo) {
  const total = achadosNaConversa.value.length
  if (!total) return
  // Dá a volta nas duas direções: no último, "próximo" volta ao primeiro.
  achadoAtual.value = (achadoAtual.value + passo + total) % total
  rolarAteAchado()
}

async function rolarAteAchado() {
  await nextTick()
  const alvo = idAchado.value
  if (!alvo || !baloes.value) return
  const el = baloes.value.querySelector(`[data-mensagem="${alvo}"]`)
  if (el) el.scrollIntoView({ block: 'center', behavior: 'smooth' })
}

/* ⚠️ Zera ao trocar o termo: sem isto, apagar uma letra deixa o contador em
   "7/2" e o próximo clique pula para um índice que não existe mais. */
watch(buscaNaConversa, () => {
  achadoAtual.value = 0
  if (achadosNaConversa.value.length) rolarAteAchado()
})

/* Participantes — quem mais está acompanhando esta conversa.
   🚨 Convidar NÃO dá acesso: qualquer atendente com ATD_1.2 já abre qualquer
   conversa. O convite faz ela APARECER NA LISTA de quem foi chamado. */
const acompanham = ref([])
const convidaveis = ref([])
const souDono = ref(false)
const souParticipante = ref(false)
/* Vários de uma vez (12/08): era um <select> de um só, e chamar três pessoas
   custava três idas ao painel. */
const convidados = ref([])
const mexendo = ref(false)

/* ---- confirmação --------------------------------------------------------
   Uma caixa só, alimentada por quem chama. `acao` é a função que roda no
   "confirmar"; enquanto ninguém aperta, nada acontece.

   ⚠️ NÃO CONFIRMAR O QUE SE DESFAZ SOZINHO. Encerrar, devolver e sair mudam
   quem responde pelo cliente e nenhum tem "desfazer" -- por isso estes três
   perguntam. Transferir e convidar abrem painel próprio, onde a escolha já é
   deliberada; pedir confirmação ali seria um clique a mais por nada. */
const confirmacao = ref(null)

/* ⚠️ FECHAR LIMPA O QUE FOI DIGITADO. Sem isto, quem abre "encerrar", escolhe
   uma classificação, desiste e depois encerra OUTRA conversa leva a escolha
   antiga junto -- e o histórico grava um rótulo que ninguém escolheu ali. */
function abrirPainel(qual) {
  painelAcao.value = painelAcao.value === qual ? '' : qual
  if (!painelAcao.value) limparPaineis()
}

function fecharPainel() {
  painelAcao.value = ''
  limparPaineis()
}

function limparPaineis() {
  convidados.value = []
  timeEscolhido.value = ''
  motivo.value = ''
  classificacaoEscolhida.value = ''
  comentario.value = ''
}

function perguntar(titulo, texto, rotulo, acao, perigo = false) {
  confirmacao.value = { titulo, texto, rotulo, acao, perigo }
}

async function confirmar() {
  const c = confirmacao.value
  if (!c || mexendo.value) return
  confirmacao.value = null
  await c.acao()
}

async function carregarParticipantes(id) {
  try {
    const r = await api.get(`/api/conversas/${id}/participantes`)
    acompanham.value = r.participantes || []
    convidaveis.value = r.convidaveis || []
    souDono.value = Boolean(r.sou_dono)
    souParticipante.value = Boolean(r.sou_participante)
  } catch {
    // A conversa abre mesmo se isto falhar: participante é informação a mais,
    // não pré-requisito para atender.
    acompanham.value = []
    convidaveis.value = []
  }
}

/* 🚨 UM CONVITE POR CHAMADA, DE PROPÓSITO. A rota `/convidar` é atômica por
   pessoa; mandar a lista inteira de uma vez faria três convites virarem uma
   transação só, e um nome inválido derrubaria os outros dois. Aqui cada um vai
   sozinho e o resultado é contado -- o parcial é dito, não escondido.

   ⚠️ NÃO SE ANUNCIA SUCESSO SEM CONTAR: "3 chamados" quando dois falharam é
   exatamente o tipo de tela que mente. */
async function convidar() {
  if (!convidados.value.length || mexendo.value) return
  mexendo.value = true
  erro.value = ''
  const nomeDe = (id) => {
    const a = convidaveis.value.find((x) => String(x.id) === String(id))
    return a ? a.nome : `#${id}`
  }
  const entraram = []
  const falharam = []
  for (const id of convidados.value) {
    try {
      const r = await api.post(`/api/conversas/${aberta.value.id}/convidar`,
                               { atendente_id: Number(id) })
      entraram.push(r.nome || nomeDe(id))
    } catch (e) {
      falharam.push(`${nomeDe(id)} (${e instanceof ErroDeApi ? e.message : 'falhou'})`)
    }
  }
  if (entraram.length) {
    recado.value = entraram.length === 1
      ? `${entraram[0]} foi chamado para a conversa.`
      : `${entraram.length} pessoas foram chamadas: ${entraram.join(', ')}.`
  }
  if (falharam.length) erro.value = `Não entrou: ${falharam.join(' · ')}`
  convidados.value = []
  painelAcao.value = ''
  await carregarParticipantes(aberta.value.id)
  mexendo.value = false
}

/* 🚨 SÓ QUEM ESTÁ NA CONVERSA AGE NELA. Até 12/08 qualquer atendente com a
   tela `ATD_1.2` encerrava, transferia e devolvia conversa alheia -- o
   `souDono || souParticipante` governava só o botão *Sair*. O usuário achou
   saindo de uma conversa e reabrindo pelo painel.

   ⚠️ Esconder o botão NÃO é a trava: a rota recusa com 409. Isto aqui é para
   a tela não oferecer o que vai ser negado. */
const posso = computed(() => souDono.value || souParticipante.value)

async function entrarNaConversa() {
  mexendo.value = true
  try {
    const r = await api.post(`/api/conversas/${aberta.value.id}/entrar`)
    recado.value = r.papel === 'dono'
      ? 'Você já responde por esta conversa.'
      : 'Você entrou — agora pode responder e agir nela.'
    await Promise.all([abrir(aberta.value.id), carregar({ silencioso: true })])
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui entrar.'
  } finally {
    mexendo.value = false
  }
}

async function sairDaConversa() {
  mexendo.value = true
  try {
    const r = await api.post(`/api/conversas/${aberta.value.id}/sair`)
    recado.value = r.para_fila
      ? 'Você saiu e a conversa voltou para a fila.'
      : (r.novo_dono_nome
          ? `Você saiu; ${r.novo_dono_nome} passou a responder pela conversa.`
          : 'Você saiu da conversa.')
    await Promise.all([abrir(aberta.value.id), carregar({ silencioso: true })])
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui sair.'
  } finally {
    mexendo.value = false
  }
}

async function removerParticipante(id) {
  mexendo.value = true
  try {
    await api.post(`/api/conversas/${aberta.value.id}/remover/${id}`)
    await carregarParticipantes(aberta.value.id)
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui remover.'
  } finally {
    mexendo.value = false
  }
}

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

/* ⚠️ O GIRANDO SÓ APARECE DEPOIS DE 3 SEGUNDOS. Busca rápida — que é o caso
   normal, medido entre 5 e 30 ms — não pode piscar um indicador: pisca-pisca a
   cada tecla cansa mais do que espera nenhuma. Passando de 3 s, o silêncio é
   que vira problema: sem sinal, a pessoa acha que a tela travou e digita de
   novo. Decisão do usuário em 12/08. */
const DEMORA_ATE_AVISAR_MS = 3000
const buscaDemorada = ref(false)
let avisoDemora = null

async function carregar({ silencioso = false } = {}) {
  if (!silencioso) carregando.value = true
  clearTimeout(avisoDemora)
  avisoDemora = setTimeout(() => { buscaDemorada.value = true }, DEMORA_ATE_AVISAR_MS)
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
    // 🚨 Apagar o aviso no `finally`, nunca no caminho de sucesso: busca que
    // FALHA depois de 4 s deixaria o girando na tela para sempre.
    clearTimeout(avisoDemora)
    buscaDemorada.value = false
    carregando.value = false
  }
}

async function abrir(id) {
  try {
    // Solta o que a conversa anterior segurava ANTES de trocar: o object URL
    // da foto de outro cliente não tem por que continuar vivo.
    soltarMidias()
    // ⚠️ Modal aberto para a conversa anterior não pode sobreviver à troca:
    // ele confirmaria sobre a conversa nova com o texto da velha.
    painelAcao.value = ''
    confirmacao.value = null
    limparPaineis()
    // A busca é DESTA conversa: carregá-la em outra mostraria contador e
    // marcações de um termo que ninguém procurou aqui.
    buscaNaConversa.value = ''
    achadoAtual.value = 0
    gaveta.value = false
    empresas.value = []
    empresasAbertas.value = false
    buscaCliente.value = ''
    achadosCliente.value = []
    aberta.value = await api.get(`/api/conversas/${id}`)
    carregarParticipantes(id)
    carregarMidiasDaConversa(aberta.value)
    rolarParaOFim()
    recado.value = ''
    if (route.params.id !== String(id)) {
      router.replace({ path: `/atendimento/${id}` })
    }
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao abrir a conversa.'
  }
}

/* Assumir serve os dois casos: conversa na fila e conversa ENCERRADA.
   Encerrada, assumir REABRE -- antes de 12/08 encerrar era porta só de ida e o
   único jeito de voltar a falar era o cliente escrever primeiro. */
async function assumir(id = null) {
  const alvo = id || aberta.value.id
  try {
    const r = await api.post(`/api/conversas/${alvo}/assumir`)
    recado.value = r.reaberta
      ? 'Conversa reaberta — você passou a responder por ela.'
      : 'Conversa assumida.'
    await Promise.all([abrir(alvo), carregar({ silencioso: true })])
  } catch (e) {
    // 🚨 409 aqui é o caso projetado: outra pessoa clicou primeiro, ou este
    // número já tem outra conversa aberta e é nela que a resposta chega.
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui assumir.'
  }
}

/* Pela lista: sem dono assume direto; encerrada abre a conversa ANTES de
   perguntar, para quem vai reabrir ver do que se trata em vez de confirmar às
   cegas a partir de uma linha de lista. */
async function assumirDaLista(c) {
  if (c.estado !== 'resolvida') {
    await assumir(c.id)
    return
  }
  await abrir(c.id)
  if (aberta.value && aberta.value.estado === 'resolvida') pedirParaAssumir()
}

function pedirParaAssumir() {
  if (aberta.value.estado === 'resolvida') {
    perguntar(
      'Reabrir esta conversa?',
      'Ela sai do Histórico, volta para a caixa de entrada e você passa a '
        + 'responder por ela. O tempo de atendimento é recontado no próximo '
        + 'encerramento.',
      'Reabrir e assumir',
      () => assumir(),
    )
    return
  }
  assumir()
}

const exigeComentario = computed(() => {
  const c = classificacoes.value.find((x) => String(x.id) === String(classificacaoEscolhida.value))
  return Boolean(c && c.exige_comentario)
})

/* O destino vem do BOTÃO clicado, não de um estado guardado. Era `modoNota`,
   um seletor invisível que o usuário não conseguia entender -- e com razão. */
const ocupado = computed(() => enviando.value || enviandoArquivo.value)
const temAlgoParaEnviar = computed(
  () => Boolean(arquivo.value) || Boolean(resposta.value.trim()),
)

async function enviar(interna = false) {
  const texto = resposta.value.trim()
  if (!texto || ocupado.value) return
  enviando.value = true
  erro.value = ''
  recado.value = ''
  const caminho = interna ? 'nota' : 'responder'
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

/* ---- envio de arquivo ----------------------------------------------------
   🚨 O DESTINATÁRIO NÃO É ESCOLHIDO AQUI. A rota tira o número da conversa;
   o formulário manda só o arquivo e a legenda.

   ⚠️ NÃO passa pelo `api.post`, que serializa JSON. Arquivo vai por
   `FormData`, e nesse caso o navegador precisa montar o `Content-Type` com o
   boundary sozinho -- definir o cabeçalho na mão quebra o upload em silêncio,
   com o servidor recebendo corpo vazio. */
/* 25 MB é decisão do usuário (12/08). Eu tinha posto 16 por conta própria, e
   teto é decisão dele -- regra que ele já tinha dado no dia anterior. */
const TETO_ARQUIVO_MB = 25
const arquivo = ref(null)
const enviandoArquivo = ref(false)

function escolherArquivo(evento) {
  const f = evento.target.files?.[0] || null
  erro.value = ''
  if (f && f.size > TETO_ARQUIVO_MB * 1024 * 1024) {
    // Barra aqui também, além do servidor: subir 40 MB para levar 413 no fim
    // é desperdício de tempo de quem está atendendo.
    erro.value = `O arquivo tem ${(f.size / 1024 / 1024).toFixed(1)} MB e o `
      + `teto é ${TETO_ARQUIVO_MB} MB.`
    evento.target.value = ''
    arquivo.value = null
    return
  }
  arquivo.value = f
}

function limparArquivo() {
  arquivo.value = null
  const campo = document.getElementById('campo-arquivo')
  if (campo) campo.value = ''
}

async function enviarArquivo(interna = false) {
  if (!arquivo.value || ocupado.value) return
  enviandoArquivo.value = true
  erro.value = ''
  recado.value = ''
  try {
    const forma = new FormData()
    forma.append('arquivo', arquivo.value)
    forma.append('legenda', resposta.value.trim())
    // Anexo vale nos dois destinos: como nota, o arquivo é guardado na
    // conversa e não sai para o cliente.
    forma.append('interna', interna ? 'true' : 'false')
    const r = await fetch(`/api/conversas/${aberta.value.id}/arquivo`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${localStorage.getItem('movizap.token')}` },
      body: forma,
    })
    // 🚨 Não confiar no código: ler o corpo e decidir por ele.
    const texto = await r.text()
    let corpo = null
    try { corpo = JSON.parse(texto) } catch { corpo = null }
    if (!r.ok) {
      throw new Error((corpo && corpo.detail) || `Falha ao enviar (${r.status}).`)
    }
    limparArquivo()
    resposta.value = ''
    recado.value = 'Arquivo enviado.'
    await Promise.all([abrir(aberta.value.id), carregar({ silencioso: true })])
  } catch (e) {
    erro.value = e.message || 'Não consegui enviar o arquivo.'
  } finally {
    enviandoArquivo.value = false
  }
}

function tamanhoDoArquivo(f) {
  if (!f) return ''
  return f.size < 1024 * 1024
    ? `${Math.round(f.size / 1024)} KB`
    : `${(f.size / 1024 / 1024).toFixed(1)} MB`
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

function pedirParaDevolver() {
  perguntar(
    'Devolver à fila?',
    `A conversa fica sem dono e volta para a fila, onde qualquer atendente pode `
      + `assumir. Você deixa de ser responsável por ela. O cliente não é avisado.`,
    'Devolver à fila',
    devolver,
  )
}

function pedirParaSair() {
  /* ⚠️ O texto muda conforme o papel, porque a consequência muda: dono que sai
     PASSA A POSSE (ou joga na fila); participante que sai só deixa de ver. */
  const texto = souDono.value
    ? (acompanham.value.length
        ? 'Você é quem responde por ela. Ao sair, a posse passa para quem está '
          + 'acompanhando há mais tempo.'
        : 'Você é quem responde por ela e não há mais ninguém acompanhando — '
          + 'ao sair, a conversa volta para a fila.')
    : 'Ela deixa de aparecer na sua lista. Quem responde pela conversa não muda.'
  perguntar('Sair da conversa?', texto, 'Sair da conversa', sairDaConversa)
}

async function encerrar() {
  try {
    await api.post(`/api/conversas/${aberta.value.id}/encerrar`, {
      // 🚨 `Number('')` é 0, e 0 não é "sem classificação" -- é um id que
      // não existe. Classificar virou opcional em 11/08, então o que vai é
      // null quando ninguém escolheu.
      classificacao_id: classificacaoEscolhida.value
        ? Number(classificacaoEscolhida.value)
        : null,
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
  // ⚠️ Grupo tem nome próprio e não tem telefone. Sem este primeiro caso, a
  // linha do grupo cairia no `telefone_e164`, que é NULO, e a lista mostraria
  // vazio.
  if (c.tipo === 'grupo') return c.grupo_nome || 'Grupo sem nome'
  return c.nome_whatsapp || c.contato_nome || c.telefone_e164
}

const ehGrupo = computed(() => Boolean(aberta.value && aberta.value.tipo === 'grupo'))

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

/* `partir` e `marcar` mudaram para `util/destaque.js` em 12/08 — funções puras
   dentro de um `.vue` são inalcançáveis por teste, e elas sustentam o destaque
   da busca inclusive na parte de segurança. Ver `destaque.teste.js`. */

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

/* Que tipo de mídia é esta mensagem, para decidir se mostra foto, áudio ou só
   o link de baixar.

   🚨 NÃO DÁ PARA OLHAR SÓ `m.tipo`. Nota com anexo tem `tipo = 'nota'` -- o
   CHECK `ck_nota_e_interna` do banco exige isso --, então uma foto anexada a
   uma nota apareceria como "arquivo genérico" e nunca como imagem. Quem sabe
   o que é o arquivo é o MIME dele. */
const FAMILIA = { image: 'imagem', audio: 'audio', video: 'video' }

function tipoDaMidia(m) {
  if (!m.midia_id) return m.tipo
  if (m.tipo === 'nota' || m.tipo === 'documento') {
    return FAMILIA[(m.midia_mime || '').split('/')[0]] || 'documento'
  }
  return m.tipo
}

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
const baloes = ref(null)

/* 🚨 A CONVERSA ABRE NA MENSAGEM MAIS RECENTE. Abrir no topo obriga o
   atendente a rolar até o fim toda vez para achar o que a pessoa acabou de
   dizer -- e em conversa longa isso é o primeiro gesto, sempre.

   ⚠️ `nextTick` é obrigatório: sem ele a rolagem acontece antes de os balões
   existirem no DOM, e não faz nada -- em silêncio. */
async function rolarParaOFim() {
  await nextTick()
  if (baloes.value) baloes.value.scrollTop = baloes.value.scrollHeight
}

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
    if (m.midia_id && MOSTRAM_SOZINHAS.includes(tipoDaMidia(m))) carregarMidia(m)
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
          <label class="campo campo--busca">
            <span class="so-leitor">Buscar conversa</span>
            <div class="busca">
              <input
                v-model="busca"
                class="campo__entrada"
                type="search"
                placeholder="nome, telefone ou o que foi dito"
                @keyup.enter="carregar()"
              />
              <button
                class="botao botao--primario botao--icone"
                type="button"
                title="Buscar conversa"
                aria-label="Buscar conversa"
                @click="carregar()"
              >
                <i class="bi bi-search" aria-hidden="true"></i>
              </button>
            </div>
            <span class="campo__ajuda">
              Procura no nome do WhatsApp, no cadastro, no telefone
              (<strong>pedaço serve</strong>: <code>6168</code>) e no texto das
              mensagens, inclusive das notas internas.
            </span>
            <!-- ⚠️ Só depois de 3 s. Antes disso, o normal é responder em
                 milissegundos e piscar seria pior que ficar quieto. -->
            <span v-if="buscaDemorada" class="linha pequeno fraco">
              <span class="girando"></span> Procurando… a base está grande, isso
              pode levar alguns segundos.
            </span>
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
          <!-- 🚨 O "Assumir" é IRMÃO do botão da conversa, não filho: botão
               dentro de botão é HTML inválido, e o navegador desfaz o
               aninhamento sozinho -- o clique de dentro passa a abrir a
               conversa em vez de assumir, sem erro nenhum aparecer. -->
          <li v-for="c in lista" :key="c.id" class="conversas__item">
            <button
              class="conversa"
              :class="{ 'conversa--aberta': aberta && aberta.id === c.id }"
              type="button"
              @click="abrir(c.id)"
            >
              <div class="conversa__topo">
                <strong class="conversa__quem">
                  <!-- Grupo e conversa direta na MESMA lista, como no
                       WhatsApp. O ícone é o que distingue. -->
                  <i v-if="c.tipo === 'grupo'" class="bi bi-people" aria-hidden="true"></i>
                  {{ quem(c) }}
                </strong>
                <span class="apagado pequeno">{{ quando(c.ultima_atividade_em) }}</span>
              </div>
              <!-- ⚠️ Fui CHAMADO para esta, não sou o dono. Sem a marca, ela
                   fica igual às minhas na lista — e só o dono responde por ela. -->
              <p v-if="c.acompanho" class="conversa__marca pequeno">
                <i class="bi bi-people" aria-hidden="true"></i>
                acompanhando<span v-if="c.atendente_nome"> · {{ c.atendente_nome }} responde</span>
              </p>
              <!-- 🚨 CASOU PELO TEXTO: MOSTRAR O TEXTO. Sem isto a conversa
                   entra na lista sem nada visível batendo com o que foi
                   digitado, e quem buscou conclui que a busca está quebrada.
                   O backend só manda `trecho` quando o nome NÃO explica o
                   acerto -- se o nome já bate, a prévia normal continua. -->
              <p v-if="c.trecho" class="conversa__previa conversa__previa--achado pequeno">
                <i class="bi bi-search" aria-hidden="true"></i>
                <span v-for="(p, i) in partir(c.trecho, busca)" :key="i"
                      :class="{ 'achado': p.casa }">{{ p.texto }}</span>
              </p>
              <p v-else class="conversa__previa apagado pequeno">
                <i v-if="ICONE[c.ultimo_tipo]" class="bi" :class="ICONE[c.ultimo_tipo]" aria-hidden="true"></i>
                <span v-if="c.ultima_direcao === 'saida'" class="fraco">você: </span>
                {{ c.ultima_mensagem || '(sem texto)' }}
              </p>
              <div class="linha pequeno">
                <!-- "não identificado" fala do CADASTRO, não do nome: ter apelido
                     do WhatsApp não quer dizer que se saiba de qual cliente é. -->
                <span v-if="!c.contato_nome" class="chip chip--aviso">não identificado</span>
                <span v-if="c.cliente_nome" class="chip">{{ c.cliente_nome }}</span>
                <span v-if="c.estado === 'resolvida'" class="chip chip--ok">encerrada</span>
                <span v-if="c.atendente_nome" class="chip chip--acento">{{ c.atendente_nome }}</span>
                <span v-else class="chip">sem dono</span>
              </div>
            </button>

            <!-- Sem dono, ou encerrada: dá para pegar daqui, sem abrir antes.
                 Encerrada, assumir REABRE -- por isso o rótulo muda. -->
            <button
              v-if="!c.atendente_id || c.estado === 'resolvida'"
              class="botao botao--pequeno botao--primario conversas__assumir"
              type="button"
              :title="c.estado === 'resolvida'
                ? 'Reabrir esta conversa e passar a responder por ela'
                : 'Assumir esta conversa'"
              @click="assumirDaLista(c)"
            >
              <i class="bi" :class="c.estado === 'resolvida' ? 'bi-arrow-counterclockwise' : 'bi-hand-index-thumb'" aria-hidden="true"></i>
              {{ c.estado === 'resolvida' ? 'Reabrir' : 'Assumir' }}
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
              <strong>
                <i v-if="ehGrupo" class="bi bi-people" aria-hidden="true"></i>
                {{ quem(aberta) }}
              </strong>
              <!-- 🚨 GRUPO NÃO TEM FICHA. A gaveta mostra UM cliente, e num
                   grupo há vários ou nenhum -- abri-la ali mostraria a ficha
                   de quem, exatamente? -->
              <button
                v-if="!ehGrupo"
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
            <!-- Encerrada TEM dono (quem fechou), então o `!atendente_id` de
                 antes escondia o botão justo onde ele é mais necessário. -->
            <button
              v-if="!aberta.atendente_id || aberta.estado === 'resolvida'"
              class="botao botao--pequeno botao--primario"
              type="button"
              @click="pedirParaAssumir"
            >
              <i class="bi" :class="aberta.estado === 'resolvida' ? 'bi-arrow-counterclockwise' : 'bi-hand-index-thumb'" aria-hidden="true"></i>
              {{ aberta.estado === 'resolvida' ? 'Reabrir e assumir' : 'Assumir' }}
            </button>
            <span v-else class="chip chip--acento">{{ aberta.atendente_nome }}</span>
          </header>

          <!-- ⚠️ Só aparece quando há alguém: linha vazia em toda conversa
               seria ruído numa tela que já é densa. -->
          <p v-if="acompanham.length" class="conversa__acompanham pequeno">
            <i class="bi bi-people" aria-hidden="true"></i>
            <span class="apagado">acompanhando:</span>
            <span v-for="p in acompanham" :key="p.atendente_id" class="chip chip--pequeno">
              {{ p.nome }}
              <button
                v-if="souDono"
                class="chip__x"
                type="button"
                :disabled="mexendo"
                :title="`tirar ${p.nome} da conversa`"
                @click="removerParticipante(p.atendente_id)"
              >×</button>
            </span>
          </p>

          <!-- ══ BARRA DE AÇÕES ══════════════════════════════════════════
               Fica no TOPO, logo abaixo de quem responde pela conversa
               (pedido do usuário em 12/08): é ali que se olha para saber de
               quem é a conversa, e é ali que se decide o que fazer com ela.
               Antes estava lá embaixo, depois de todos os balões.

               🚨 ÍCONE SEM NOME É ADIVINHAÇÃO: os quatro carregam `title` e
               `aria-label`. "Devolver à fila" e "Sair da conversa" fazem
               coisas diferentes e têm setas parecidas. *Encerrar* mantém o
               texto — é o fim do atendimento, e é o único que não deve
               depender de reconhecer desenho. -->
          <div v-if="aberta.estado !== 'resolvida'" class="acoes cartao__corpo">
            <!-- DE FORA: só dá para ler. A rota recusa com 409 de qualquer
                 jeito; aqui a tela para de oferecer o que seria negado. -->
            <div v-if="!posso" class="linha linha--quebra">
              <span class="chip chip--aviso">
                <i class="bi bi-eye" aria-hidden="true"></i> só leitura
              </span>
              <span class="apagado pequeno">
                Você não está nesta conversa.
              </span>
              <span class="espaco"></span>
              <button
                v-if="aberta.atendente_id"
                class="botao botao--pequeno botao--primario"
                type="button"
                :disabled="mexendo"
                @click="entrarNaConversa"
              >
                <i class="bi bi-box-arrow-in-right" aria-hidden="true"></i> Entrar
              </button>
            </div>

            <div v-else class="linha linha--quebra">
              <button
                class="botao botao--pequeno botao--contorno botao--icone"
                type="button"
                title="Transferir para outro time"
                aria-label="Transferir para outro time"
                @click="abrirPainel('transferir')"
              >
                <i class="bi bi-arrow-left-right" aria-hidden="true"></i>
              </button>
              <button
                class="botao botao--pequeno botao--contorno botao--icone"
                type="button"
                title="Convidar atendentes para esta conversa"
                aria-label="Convidar atendentes para esta conversa"
                @click="abrirPainel('convidar')"
              >
                <i class="bi bi-person-plus" aria-hidden="true"></i>
              </button>
              <button
                v-if="aberta.atendente_id"
                class="botao botao--pequeno botao--contorno botao--icone"
                type="button"
                title="Devolver à fila — a conversa fica sem dono"
                aria-label="Devolver à fila"
                @click="pedirParaDevolver"
              >
                <i class="bi bi-arrow-return-left" aria-hidden="true"></i>
              </button>
              <button
                class="botao botao--pequeno botao--contorno botao--icone"
                type="button"
                :disabled="mexendo"
                title="Sair da conversa — ela some da sua lista"
                aria-label="Sair da conversa"
                @click="pedirParaSair"
              >
                <i class="bi bi-box-arrow-left" aria-hidden="true"></i>
              </button>
              <span class="espaco"></span>
              <button
                class="botao botao--pequeno botao--contorno"
                type="button"
                @click="abrirPainel('encerrar')"
              >
                <i class="bi bi-check2-square" aria-hidden="true"></i> Encerrar
              </button>
            </div>
          </div>

          <p v-if="!aberta.contato_id && !ehGrupo" class="aviso aviso--atencao">
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
          <aside v-if="gaveta && !ehGrupo" class="gaveta">
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

              <!-- 🚨 SELO AMARELO: informação sem afirmação. Diz que a pessoa
                   aparece no Bitrix, sem dizer que ela é cliente. -->
              <div v-if="aberta.bitrix" class="gaveta__bitrix">
                <strong class="pequeno">Aparece no Bitrix</strong>
                <span v-if="aberta.bitrix.nome">{{ aberta.bitrix.nome }}</span>
                <span v-if="aberta.bitrix.empresa" class="apagado pequeno">
                  {{ aberta.bitrix.empresa }}
                </span>
                <span class="linha pequeno">
                  <span v-if="aberta.bitrix.tipo" class="chip">{{ aberta.bitrix.tipo }}</span>
                  <span v-if="aberta.bitrix.cargo" class="apagado">{{ aberta.bitrix.cargo }}</span>
                </span>
                <span class="apagado pequeno">
                  Sistema antigo — <strong>não é vínculo</strong>. Confirme abaixo
                  se for a mesma empresa.
                </span>
              </div>
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

          <!-- BUSCAR NA CONVERSA — outra pergunta que a busca da lista:
               lá é "com quem eu falei", aqui é "onde ele disse isso". -->
          <div class="buscaconversa">
            <div class="busca">
              <input
                v-model="buscaNaConversa"
                class="campo__entrada"
                type="search"
                placeholder="Buscar na conversa"
                aria-label="Buscar na conversa"
                @keyup.enter="irParaAchado(1)"
              />
              <template v-if="buscaNaConversa.trim()">
                <span class="pequeno fraco buscaconversa__conta">
                  {{ achadosNaConversa.length
                     ? `${achadoAtual + 1}/${achadosNaConversa.length}`
                     : '0' }}
                </span>
                <button
                  class="botao botao--pequeno botao--contorno botao--icone"
                  type="button"
                  :disabled="!achadosNaConversa.length"
                  title="Ocorrência anterior"
                  aria-label="Ocorrência anterior"
                  @click="irParaAchado(-1)"
                >
                  <i class="bi bi-chevron-up" aria-hidden="true"></i>
                </button>
                <button
                  class="botao botao--pequeno botao--contorno botao--icone"
                  type="button"
                  :disabled="!achadosNaConversa.length"
                  title="Próxima ocorrência"
                  aria-label="Próxima ocorrência"
                  @click="irParaAchado(1)"
                >
                  <i class="bi bi-chevron-down" aria-hidden="true"></i>
                </button>
              </template>
            </div>
            <!-- 🚨 "Não encontrado" numa conversa truncada seria MENTIRA: a
                 busca só vê o que foi carregado. Nenhuma conversa passou do
                 teto ainda, mas o aviso nasce junto com a busca. -->
            <p v-if="aberta.truncada" class="chip chip--aviso pequeno">
              Mostrando as {{ aberta.teto_mensagens }} mensagens mais recentes —
              a busca não alcança o que está antes disso.
            </p>
            <p v-else-if="buscaNaConversa.trim() && !achadosNaConversa.length"
               class="apagado pequeno">
              Nada com esse termo nesta conversa.
            </p>
          </div>

          <div ref="baloes" class="baloes">
            <div
              v-for="m in aberta.mensagens"
              :key="m.id"
              class="balao"
              :class="[`balao--${m.direcao}`, {
                'balao--casa': casaNaConversa(m),
                'balao--atual': m.id === idAchado,
              }]"
              :data-mensagem="m.id"
            >
              <!-- A mensagem que esta está respondendo. Sem isto, uma foto
                   seguida de "esse aqui" fica ininteligível. -->
              <p v-if="m.citada_id" class="balao__citada pequeno">
                <i class="bi bi-reply" aria-hidden="true"></i>
                <span class="fraco">{{ m.citada_autor === 'cliente' ? 'cliente' : 'nós' }}:</span>
                {{ m.citada_conteudo || `(${m.citada_tipo})` }}
              </p>

              <img
                v-if="m.midia_id && ['imagem', 'figurinha'].includes(tipoDaMidia(m)) && midias[m.midia_id]"
                :src="midias[m.midia_id]"
                class="balao__imagem"
                :alt="m.conteudo || 'imagem da conversa'"
              />
              <audio
                v-else-if="m.midia_id && tipoDaMidia(m) === 'audio' && midias[m.midia_id]"
                :src="midias[m.midia_id]"
                controls
                class="balao__audio"
              ></audio>
              <video
                v-else-if="m.midia_id && tipoDaMidia(m) === 'video' && midias[m.midia_id]"
                :src="midias[m.midia_id]"
                controls
                class="balao__imagem"
              ></video>

              <p v-if="m.tipo !== 'texto' && (m.midia_id || m.tipo !== 'nota')"
                 class="balao__tipo pequeno">
                <i class="bi" :class="ICONE[tipoDaMidia(m)] || 'bi-paperclip'" aria-hidden="true"></i>
                {{ m.midia_nome || tipoDaMidia(m) }}
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
              <!-- 🚨 NOTA SEM AUTOR NÃO SERVE PARA CONSULTAR DEPOIS. O nome já
                   vinha da API (`mensagens()` faz o JOIN em atendente desde
                   sempre) e a tela simplesmente não o imprimia: meses depois,
                   "cliente pediu desconto" não dizia quem tinha escrito. -->
              <!-- 🚨 EM GRUPO, QUEM FALOU NÃO É A CONVERSA. Sem esta linha o
                   histórico de um grupo de quinze vira monólogo de autor
                   desconhecido. Só na ENTRADA: o que sai é nosso. -->
              <p v-if="ehGrupo && m.direcao === 'entrada' && m.remetente_nome"
                 class="balao__autor pequeno">
                <i class="bi bi-person" aria-hidden="true"></i>
                {{ m.remetente_nome }}
              </p>
              <p v-if="m.tipo === 'nota'" class="balao__autor pequeno">
                <i class="bi bi-sticky" aria-hidden="true"></i>
                Nota de <strong>{{ m.atendente_nome || 'autor não registrado' }}</strong>
              </p>
              <!-- Pedaços, não `v-html`: o texto é do cliente. -->
              <p v-if="m.conteudo" class="balao__texto">
                <span v-for="(p, i) in marcar(m.conteudo, buscaNaConversa)" :key="i"
                      :class="{ 'achado': p.casa }">{{ p.texto }}</span>
              </p>
              <p v-else class="balao__texto fraco">(sem texto)</p>
              <p class="balao__rodape apagado pequeno">
                {{ hora(m.criada_em) }}
                <!-- Só na saída: quem respondeu pelo painel. O eco do WhatsApp
                     chega sem atendente, e aí não há nome a mostrar. -->
                <span v-if="m.direcao === 'saida' && m.atendente_nome">
                  · {{ m.atendente_nome }}
                </span>
                <span v-if="m.entrega"> · {{ m.entrega }}</span>
              </p>
            </div>
          </div>

          <div v-if="aberta.estado === 'resolvida'" class="cartao__corpo pilha">
            <p class="aviso aviso--ok">
              <i class="bi bi-check-circle aviso__icone" aria-hidden="true"></i>
              <span>
                Conversa encerrada. Ela está no Histórico (ATD_5.1).
                <strong>Para voltar a responder, reabra.</strong>
              </span>
            </p>
            <!-- 🚨 SEM ISTO, ENCERRAR ERA PORTA SÓ DE IDA. O `responder` recusa
                 conversa resolvida, e a tela escondia a barra inteira: só o
                 cliente escrevendo de novo trazia a conversa de volta. -->
            <button class="botao botao--primario" type="button" @click="pedirParaAssumir">
              <i class="bi bi-arrow-counterclockwise" aria-hidden="true"></i>
              Reabrir e assumir
            </button>
          </div>

          <!-- DE FORA: nem o campo aparece. Poder escrever sem estar na
               conversa é o mesmo furo da barra de ações. -->
          <p v-else-if="!posso" class="cartao__corpo apagado pequeno">
            <i class="bi bi-lock" aria-hidden="true"></i>
            Entre na conversa para responder ou anotar.
          </p>

          <div v-else class="cartao__corpo pilha">
            <!-- 🚨 NÃO EXISTE MAIS SELETOR DE MODO. Havia um par
                 "Para o cliente | Nota interna" que só trocava um estado
                 invisível: clicar no lado que já estava ativo não fazia nada,
                 e o usuário perguntou duas vezes para que servia. Estado que
                 não se vê é o que confunde. Agora o destino é o BOTÃO: um
                 campo, duas ações, e o que se clica é o que acontece. -->
            <label class="campo">
              <span class="so-leitor">Mensagem</span>
              <textarea
                v-model="resposta"
                class="campo__entrada"
                rows="3"
                maxlength="4000"
                placeholder="Escreva e escolha abaixo: enviar ao cliente ou guardar como nota"
                @keydown.ctrl.enter.prevent="enviar"
              ></textarea>
            </label>

            <!-- ANEXO nos DOIS modos (decisão do usuário, 12/08). No modo
                 nota o arquivo é guardado na conversa e NÃO sai para o
                 cliente -- é o print do erro, o PDF que chegou por outro
                 canal, o comprovante que se quer deixar registrado. -->
            <div v-if="arquivo" class="anexo">
              <i class="bi bi-paperclip" aria-hidden="true"></i>
              <span class="anexo__nome">{{ arquivo.name }}</span>
              <span class="apagado pequeno">{{ tamanhoDoArquivo(arquivo) }}</span>
              <button
                class="botao botao--pequeno botao--fantasma"
                type="button"
                title="Tirar o anexo"
                @click="limparArquivo"
              >×</button>
            </div>

            <div class="linha linha--quebra">
              <label class="botao botao--contorno botao--icone" title="Anexar arquivo">
                <i class="bi bi-paperclip" aria-hidden="true"></i>
                <span class="so-leitor">Anexar arquivo</span>
                <input
                  id="campo-arquivo"
                  class="so-leitor"
                  type="file"
                  @change="escolherArquivo"
                />
              </label>

              <!-- O DESTINO É O BOTÃO. Verde é WhatsApp em toda a casa;
                   amarelo é nota. A cor diz para onde vai antes do clique. -->
              <button
                class="botao botao--primario"
                type="button"
                :disabled="ocupado || !temAlgoParaEnviar"
                @click="arquivo ? enviarArquivo(false) : enviar(false)"
              >
                <span v-if="ocupado" class="girando"></span>
                <i v-else class="bi bi-whatsapp" aria-hidden="true"></i>
                {{ arquivo ? 'Enviar arquivo ao cliente' : 'Enviar ao cliente' }}
              </button>

              <button
                class="botao botao--nota"
                type="button"
                :disabled="ocupado || !temAlgoParaEnviar"
                @click="arquivo ? enviarArquivo(true) : enviar(true)"
              >
                <i class="bi bi-sticky" aria-hidden="true"></i>
                {{ arquivo ? 'Guardar como nota' : 'Salvar nota' }}
              </button>

              <span class="apagado pequeno">
                <template v-if="arquivo">
                  O texto acima vai junto com o arquivo.
                </template>
                <template v-else>
                  Ctrl+Enter envia ao cliente. Arquivo até {{ TETO_ARQUIVO_MB }} MB.
                </template>
              </span>
            </div>
          </div>
        </template>
      </section>
    </div>

    <!-- ================================================================ MODAIS
         Ficam fora das colunas de propósito: `position: fixed` dentro de um
         container que rola acompanha a rolagem e a caixa some da vista. -->

    <!-- CONVIDAR — vários de uma vez, por caixa de seleção -->
    <div v-if="painelAcao === 'convidar' && aberta" class="modal" @click.self="fecharPainel">
      <div class="modal__caixa" role="dialog" aria-modal="true" aria-label="Convidar atendentes">
        <p class="modal__titulo">Convidar para esta conversa</p>
        <p class="modal__texto pequeno">
          Marque quantos precisar. Quem for chamado passa a ver esta conversa na
          lista dele e responde normalmente.
          <strong>Quem responde pela conversa continua sendo
          {{ aberta.atendente_nome || 'ninguém — está na fila' }}.</strong>
        </p>

        <div v-if="convidaveis.length" class="modal__opcoes">
          <label v-for="a in convidaveis" :key="a.id" class="modal__opcao">
            <input v-model="convidados" type="checkbox" :value="a.id" />
            <span>{{ a.nome }}</span>
          </label>
        </div>
        <p v-else class="apagado pequeno">Todo mundo já está nesta conversa.</p>

        <div class="modal__acoes">
          <button class="botao botao--contorno" type="button" @click="fecharPainel">
            Cancelar
          </button>
          <button
            class="botao botao--primario"
            type="button"
            :disabled="!convidados.length || mexendo"
            @click="convidar"
          >
            <span v-if="mexendo" class="girando"></span>
            {{ convidados.length > 1 ? `Convidar ${convidados.length}` : 'Convidar' }}
          </button>
        </div>
      </div>
    </div>

    <!-- TRANSFERIR -->
    <div v-if="painelAcao === 'transferir' && aberta" class="modal" @click.self="fecharPainel">
      <div class="modal__caixa" role="dialog" aria-modal="true" aria-label="Transferir conversa">
        <p class="modal__titulo">Transferir para outro time</p>
        <p class="modal__texto pequeno">
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
            O que já foi conversado. Quem assume não deve precisar ler tudo de novo.
          </span>
        </label>
        <div class="modal__acoes">
          <button class="botao botao--contorno" type="button" @click="fecharPainel">
            Cancelar
          </button>
          <button class="botao botao--primario" type="button" :disabled="!timeEscolhido" @click="transferir">
            Transferir
          </button>
        </div>
      </div>
    </div>

    <!-- ENCERRAR — caixa de confirmação. A classificação vem NO FIM e é
         opcional desde 11/08: ninguém pediu a lista, e o analytics que a
         justificava é Fase 3. -->
    <div v-if="painelAcao === 'encerrar' && aberta" class="modal" @click.self="fecharPainel">
      <div class="modal__caixa" role="dialog" aria-modal="true" aria-label="Encerrar conversa">
        <p class="modal__titulo">Encerrar esta conversa?</p>
        <p class="modal__texto">
          Ela sai da caixa de entrada e passa para o Histórico. O cliente
          <strong>não</strong> é avisado. Se ele escrever de novo, uma conversa
          nova é aberta — e você pode reabrir esta a qualquer momento.
        </p>

        <details class="encerrar__extra">
          <summary class="pequeno">Classificar (opcional)</summary>
          <label class="campo">
            <span class="campo__rotulo">Classificação</span>
            <select v-model="classificacaoEscolhida" class="campo__entrada">
              <option value="">não classificar</option>
              <option v-for="c in classificacoes" :key="c.id" :value="c.id">{{ c.nome }}</option>
            </select>
            <span class="campo__ajuda">
              Deixou de ser obrigatória em 11/08. Encerrar sem classificar é o
              caminho normal.
            </span>
          </label>
          <label v-if="exigeComentario" class="campo">
            <span class="campo__rotulo">Comentário — obrigatório nesta</span>
            <textarea v-model="comentario" class="campo__entrada" rows="2" maxlength="2000"></textarea>
            <span class="campo__ajuda">
              Sem isto, "Outro" vira o vale-tudo onde metade das conversas acaba.
            </span>
          </label>
        </details>

        <div class="modal__acoes">
          <button class="botao botao--contorno" type="button" @click="fecharPainel">
            Cancelar
          </button>
          <button
            class="botao botao--primario"
            type="button"
            :disabled="exigeComentario && !comentario.trim()"
            @click="encerrar"
          >
            Encerrar conversa
          </button>
        </div>
      </div>
    </div>

    <!-- CONFIRMAÇÃO genérica — devolver, sair, reabrir -->
    <div v-if="confirmacao" class="modal" @click.self="confirmacao = null">
      <div class="modal__caixa" role="dialog" aria-modal="true" :aria-label="confirmacao.titulo">
        <p class="modal__titulo">{{ confirmacao.titulo }}</p>
        <p class="modal__texto">{{ confirmacao.texto }}</p>
        <div class="modal__acoes">
          <button class="botao botao--contorno" type="button" @click="confirmacao = null">
            Cancelar
          </button>
          <button
            class="botao"
            :class="confirmacao.perigo ? 'botao--perigo' : 'botao--primario'"
            type="button"
            :disabled="mexendo"
            @click="confirmar"
          >
            {{ confirmacao.rotulo }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* A ficha é uma faixa dentro da conversa, não uma tela: some ao trocar de
   conversa e não tem rota. É o equivalente a clicar no contato no WhatsApp. */
.gaveta {
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
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
.gaveta__bitrix {
  display: flex; flex-direction: column; gap: 2px;
  padding: var(--e-2);
  border-left: 3px solid var(--aviso);
  background: var(--aviso-suave);
  border-radius: var(--r-sm);
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
  border-radius: var(--r-sm);
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
  border-radius: var(--r-md);
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
  border-radius: var(--r-sm);
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

/* O "Assumir" fica ao lado do botão da conversa, não dentro dele — o item é
   quem vira a linha, e a borda de topo passou para cá porque agora são dois
   elementos irmãos dividindo a mesma linha. */
.conversas__item {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  padding-right: var(--e-3);
  border-top: 1px solid var(--borda, rgba(128, 128, 128, .25));
}
.conversas__item:hover { background: rgba(128, 128, 128, .08); }
.conversas__assumir { flex: none; }

.conversa {
  display: block;
  flex: 1 1 auto;
  min-width: 0;
  text-align: left;
  background: none;
  border: 0;
  padding: var(--e-3);
  cursor: pointer;
}
.conversa:hover { background: rgba(128, 128, 128, .08); }
.conversa--aberta { background: rgba(128, 128, 128, .14); }

.conversa__topo { display: flex; justify-content: space-between; gap: var(--e-2); }
.conversa__acompanham {
  display: flex; align-items: center; gap: var(--e-1);
  flex-wrap: wrap; padding: 0 var(--e-3) var(--e-2);
}
.chip--pequeno { font-size: var(--txt-sm); padding: 2px var(--e-1); }
.conversa__marca { color: var(--acento); display: flex; gap: 4px; align-items: center; }
.chip__x {
  background: none; border: 0; cursor: pointer; padding: 0 0 0 4px;
  color: inherit; opacity: .6; font-size: 1em; line-height: 1;
}
.chip__x:hover { opacity: 1; }
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

/* Quem escreveu a nota. Fora do itálico do balão interno: é etiqueta, não
   parte do texto que a pessoa digitou. */
.balao__autor {
  display: flex;
  align-items: center;
  gap: 4px;
  margin: 0 0 var(--e-1);
  font-style: normal;
  color: var(--texto-fraco);
}

.linha--quebra { flex-wrap: wrap; gap: var(--e-2); }

/* ---- busca --------------------------------------------------------------- */
.busca { display: flex; align-items: center; gap: var(--e-2); }
.busca .campo__entrada { flex: 1 1 auto; min-width: 0; }
.campo--busca { margin-bottom: var(--e-2); }

.buscaconversa {
  display: flex;
  flex-direction: column;
  gap: var(--e-1);
  padding: var(--e-2) var(--e-4);
  border-bottom: 1px solid var(--borda, rgba(128, 128, 128, .25));
}
.buscaconversa__conta { flex: none; min-width: 3.2em; text-align: right; }

/* O anexo escolhido, antes de ir. Sem esta faixa, o único sinal de que há
   arquivo seria o botão mudar de rótulo. */
.anexo {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  padding: var(--e-2) var(--e-3);
  border: 1px dashed var(--borda-forte, var(--borda));
  border-radius: var(--r-sm);
  background: var(--superficie-2);
}
.anexo__nome { overflow-wrap: anywhere; font-weight: var(--peso-medio); }

/* O botão de nota é amarelo porque a nota é amarela em toda a tela. A cor diz
   para onde vai a mensagem ANTES do clique — que é justamente o que o seletor
   de modo, sendo estado invisível, não conseguia dizer. */
.botao--nota {
  background: rgba(255, 193, 7, .85);
  color: #241c00;
  border-color: rgba(255, 193, 7, .85);
}
.botao--nota:hover:not(:disabled) { background: rgba(255, 193, 7, 1); }

/* O termo achado. Amarelo é a convenção de "achado" em toda parte, e é o
   mesmo amarelo que a nota interna já usa nesta tela. */
.achado {
  background: rgba(255, 193, 7, .45);
  border-radius: 3px;
  font-weight: var(--peso-forte);
}
.conversa__previa--achado { color: var(--texto-fraco); }

/* A mensagem em que a busca está parada AGORA, distinta das outras que também
   casaram: sem isso, num balão longo, não se sabe qual das 17 é a "3". */
.balao--casa { outline: 1px solid rgba(255, 193, 7, .5); }
.balao--atual { outline: 2px solid var(--acento); }

.acoes { border-top: 1px solid var(--borda, rgba(128, 128, 128, .25)); }

textarea.campo__entrada { resize: vertical; }
.campo--nota { background: rgba(255, 193, 7, .10); }

/* Classificar ficou no fim e fechado: é opcional desde 11/08, e caixa aberta
   por padrão lê como campo que falta preencher. */
.encerrar__extra { margin-top: var(--e-2); }
.encerrar__extra summary { cursor: pointer; color: var(--texto-fraco); }
.encerrar__extra > .campo { margin-top: var(--e-3); }
</style>
