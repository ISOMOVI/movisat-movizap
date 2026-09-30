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
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api, pedirBlob, ErroDeApi } from '../api/cliente.js'
import { corDaInicial, iniciais } from '../util/avatar.js'
import { partesDoTexto } from '../util/mencao.js'
import { corDoEstado, rotuloDoEstado } from '../util/estado.js'
import BotaoMensagensRapidas from '../componentes/BotaoMensagensRapidas.vue'

const salas = ref([])
const contatos = ref([])
const sala = ref(null)
const route = useRoute()
const router = useRouter()

/* 🔵 25/09, celular: sem a lista ao lado, o "Voltar" do cabeçalho (ou o do
   aparelho, que tira o `?sala=` da URL) fecha a sala e mostra a lista. */
function fecharSala() {
  sala.value = null
  mensagens.value = []
}
function voltarParaLista() {
  if (route.query.sala) router.push({ path: '/chat' })
  else fecharSala()
}
watch(() => route.query.sala, (s) => {
  if (s && String(sala.value?.id) !== String(s)) abrir(Number(s))
  if (!s && sala.value) fecharSala()
})
const mensagens = ref([])
const texto = ref('')
const carregando = ref(true)
const enviando = ref(false)
const erro = ref('')
const abrindo = ref(false)
const baloes = ref(null)
let timer = null

/* 🔵 25/09: editar (15 min) e apagar (48 h) a própria mensagem, como na Caixa. */
const JANELA_EDITAR_MIN = 15
const JANELA_APAGAR_MIN = 48 * 60
const editando = ref(null)   // { id, texto }
const salvandoEdicao = ref(false)

// Quais mensagens editadas estão com o texto ANTERIOR aberto. Mesmo padrão
// da Caixa: por id, só nesta sessão, sem guardar em lugar nenhum.
const originalAberto = ref(new Set())
function alternarOriginal(id) {
  const s = new Set(originalAberto.value)
  s.has(id) ? s.delete(id) : s.add(id)
  originalAberto.value = s
}

/* 🔵 25/09 (item G): tiques de envio/leitura, igual à Caixa. Só 2 estados --
   não há "entregue" aqui, é tudo local (sem gateway externo). Em grupo, por
   decisão dele, "lida" só quando TODOS os outros membros leram (o backend já
   calcula isso em `m.lida`, agregando o `lido_ate` de todo mundo). */
const TIQUE_CHAT = { enviada: '✓', lida: '✓✓' }

/* ---- responder citando (29/09) --------------------------------------------
   🔵 Pedido dele: "no chat interno também", igual ao gesto da Caixa. Aqui não
   existe `evolution` nem `stanzaId` -- citar é só um FK para outra
   `chat_mensagem` da MESMA sala, conferido no backend (`chat._conferir_citada`).
*/
const citando = ref(null)
function citar(m) {
  citando.value = m
  nextTick(() => campoTexto.value?.focus())
}

/* Clicar na citação dentro do balão rola até a mensagem original e a destaca
   por um instante. Sem paginação aqui (a sala já carrega até 500 mensagens
   de uma vez, ver `abrir`), então basta achar o elemento na tela -- se a
   citação for mais antiga que a janela carregada, o clique não acha nada e
   não faz nada, mesmo silêncio que a Caixa já tem para o caso equivalente. */
const balaoRealcado = ref(null)
function irParaMensagem(id) {
  if (!id || !baloes.value) return
  const el = baloes.value.querySelector(`[data-mensagem="${id}"]`)
  if (!el) return
  el.scrollIntoView({ block: 'center', behavior: 'smooth' })
  balaoRealcado.value = id
  setTimeout(() => {
    if (balaoRealcado.value === id) balaoRealcado.value = null
  }, 2000)
}

/* Mesmo destaque, para abrir imagem/vídeo em tela cheia (como na Caixa). */
const emTelaCheia = ref(null)

/* ---- anexo (22/09) --------------------------------------------------------
   🔵 Pedido dele: *"sobre envio de anexos no chat interno, igual no aberto"*,
   com o áudio junto e teto de 25 MB, decididos por ele no mesmo dia.

   🚨 NADA DAQUI SAI PARA O CLIENTE, como o resto desta tela. A rota é
   `/api/chat/salas/{id}/arquivo`, que grava e serve -- o módulo `chat` do
   backend não importa o `evolution`.

   ⚠️ O TETO TAMBÉM MORA AQUI, e não é duplicação preguiçosa: subir 40 MB
   para levar 413 no fim é desperdício do tempo de quem está atendendo. O
   servidor continua sendo quem decide. */
const TETO_ARQUIVO_MB = 25
/* 🔵 25/09: até 10 anexos por envio, texto só na primeira mensagem -- igual
   à Caixa de entrada. */
const TETO_ANEXOS = 10
const arquivos = ref([])   // File[], até TETO_ANEXOS
const enviandoArquivo = ref(false)

/* 🚨 A IMAGEM NÃO PODE IR POR `<img src="/api/...">`: a tag não manda o
   cabeçalho `Authorization` e a rota exige sessão -- armadilha já registrada
   neste projeto. Busca com token, vira object URL, e as URLs são REVOGADAS ao
   sair da tela, senão cada visita vaza um pedaço de memória. */
const midias = reactive({})

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
   escrever: adianta chamar agora? A régua (cores e rótulos) mora em
   `util/estado.js` desde 23/09 -- a Caixa de entrada usa a mesma. */

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

async function abrir(salaId, { silencioso = false, recarregarLista = true } = {}) {
  try {
    const r = await api.get(`/api/chat/salas/${salaId}`)
    sala.value = salas.value.find((s) => s.id === salaId) || { id: salaId }
    mensagens.value = r.mensagens || []
    // ⚠️ Cada anexo é buscado UMA vez: o `carregarMidia` marca "em andamento"
    // antes de ir, então o laço de 5 s não rebaixa o que já está na mão.
    for (const m of mensagens.value) carregarMidia(m)
    // 🚨 O `else` NÃO É ENFEITE (22/09). Sem ele, `membros` guardava o último
    // GRUPO aberto para sempre: quem saísse de um grupo para uma conversa de
    // dois e digitasse `@` recebia a lista do grupo -- gente que não está
    // nesta sala e que o backend recusa pelo nome. A régua da tela tem de ser
    // a mesma da rota, que é o que o comentário do `chamaveis` promete.
    if (sala.value.tipo === 'grupo') await carregarMembros(salaId)
    else membros.value = []
    if (!silencioso) {
      mostrandoMembros.value = false
      rolarParaOFim()
      /* 🔵 25/09, celular: a sala aberta vai para a URL (`/chat?sala=11`).
         Da lista para a sala é `push`, para o "voltar" do aparelho trazer a
         lista de volta; entre salas, `replace`. O ciclo de 5 s é silencioso
         e NÃO passa por aqui -- não mexe no histórico. */
      if (String(route.query.sala || '') !== String(salaId)) {
        const destino = { path: '/chat', query: { sala: String(salaId) } }
        if (route.query.sala) router.replace(destino)
        else router.push(destino)
      }
    }
    // Abrir zera o não lido desta sala: o servidor já marcou, a lista precisa
    // refletir sem esperar o próximo ciclo.
    // ⚠️ O CICLO DE 5 s PEDE `recarregarLista: false` (23/09): ele mesmo busca
    // a lista logo depois, e buscar aqui também fazia a lista ir DUAS vezes a
    // cada volta -- 3 requisições por ciclo numa conversa direta, 4 num grupo.
    if (recarregarLista) await carregar({ silencioso: true })
  } catch (e) {
    // 🚨 CICLO DE FUNDO NÃO PINTA ERRO (22/09). O `catch` escrevia na faixa
    // vermelha mesmo no ciclo silencioso: um soluço de rede de um segundo
    // deixava "Falha ao abrir a conversa" na tela de quem não clicou em nada.
    // É o mesmo critério que o `carregar()` aqui em cima já usa -- este foi o
    // que ficou de fora.
    if (!silencioso) {
      erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao abrir a conversa.'
    }
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
    // A URL sai da sala junto: recarregar a página não pode reabrir o que saiu.
    if (route.query.sala) router.replace({ path: '/chat' })
    fecharSala()
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui sair.'
  }
}

/* 🚨 "EXCLUIR CONVERSA" TIRA DA MINHA LISTA, e a confirmação diz as duas
   coisas que a pessoa precisa saber antes de clicar: o outro continua com
   tudo, e ela volta se alguém escrever. É o comportamento do WhatsApp, que é
   a referência que ele escolheu para esta tela.

   ⚠️ Apagar de verdade levaria junto o histórico de quem não pediu nada, e
   conversa interna é prova de combinado: quem disse o quê sobre um
   atendimento. */
async function esconderConversa() {
  const quem = sala.value?.com || sala.value?.nome || 'esta conversa'
  const aviso = `Tirar "${quem}" da sua lista?\n\n`
    + 'A conversa continua inteira para a outra pessoa — isto não apaga nada.\n\n'
    + 'Ela volta para a sua lista assim que alguém escrever de novo.'
  if (!confirm(aviso)) return
  try {
    await api.post(`/api/chat/salas/${sala.value.id}/esconder`)
    recado.value = 'Conversa fora da sua lista. Ela volta se alguém escrever.'
    // A URL sai da sala junto: recarregar a página não pode reabrir o que saiu.
    if (route.query.sala) router.replace({ path: '/chat' })
    fecharSala()
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui esconder.'
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

/* ---- chamar alguém com @ (27/08) -----------------------------------------
   🚨 QUEM RESOLVE O `@` É QUEM ESCREVE, na hora de escolher na lista — não um
   regex lendo o texto depois. Regex teria de adivinhar onde o nome termina
   ("Suporte Erika" tem espaço), casar apelido e desempatar homônimo, e erraria
   em silêncio nos três casos. A tela manda os IDS; o backend confere que cada
   um é membro da sala e recusa dizendo o nome de quem não está.

   ⚠️ O TEXTO NÃO GANHA MARCAÇÃO EMBUTIDA. Guardar `@[12:Erika]` tornaria o
   histórico ilegível fora desta tela — e o texto do chat é lido em log e em
   busca. O que se guarda é o texto como a pessoa escreveu, e a lista à parte. */
const campoTexto = ref(null)

/* 🔵 25/09 (Plano 3): no Chat interno, *"Minhas notas e Formulários"*. Entra
   no cursor; o que já estava escrito fica. */
function inserirNoTexto(trecho) {
  const el = campoTexto.value
  const atual = texto.value || ''
  const ini = el?.selectionStart ?? atual.length
  const fim = el?.selectionEnd ?? atual.length
  texto.value = atual.slice(0, ini) + trecho + atual.slice(fim)
  nextTick(() => {
    el?.focus()
    el?.setSelectionRange(ini + trecho.length, ini + trecho.length)
  })
}
const mencionados = ref([])      // [{id, nome}] já escolhidos
const listaArroba = ref([])      // o que a lista está oferecendo agora
const arrobaEscolhido = ref(0)
let inicioDaArroba = -1          // onde o `@` desta busca começou

/* Só quem está NESTA sala pode ser chamado — a mesma régua do backend, para a
   tela não oferecer o que a rota vai recusar.

   ⚠️ `sou_eu` VEM DO BACKEND, não de comparar ids aqui. Chamar a si mesmo não
   quebra nada (o backend já não conta como não lida), mas aparecer na própria
   lista é ruído. */
const chamaveis = computed(() =>
  (membros.value || []).filter((m) => !m.sou_eu)
    .map((m) => ({ id: m.atendente_id, nome: m.nome })))

function olharArroba(evento) {
  const campo = evento.target
  const ate = campo.value.slice(0, campo.selectionStart)
  const at = ate.lastIndexOf('@')
  // ⚠️ `@` colado em palavra não abre a lista: "email@movisat" não é menção.
  const antes = at > 0 ? ate[at - 1] : ' '
  if (at === -1 || !/\s/.test(antes)) {
    listaArroba.value = []
    return
  }
  const termo = ate.slice(at + 1)
  if (/\s{2,}|\n/.test(termo)) { listaArroba.value = []; return }
  inicioDaArroba = at
  const busca = termo.trim().toLowerCase()
  listaArroba.value = chamaveis.value
    .filter((p) => !mencionados.value.some((m) => m.id === p.id))
    .filter((p) => !busca || p.nome.toLowerCase().includes(busca))
    .slice(0, 8)
  arrobaEscolhido.value = 0
}

function andarNaLista(passo) {
  if (!listaArroba.value.length) return
  const n = listaArroba.value.length
  arrobaEscolhido.value = (arrobaEscolhido.value + passo + n) % n
}

/* Enter escolhe da lista quando ela está aberta; senão envia. Sem isto, quem
   digitasse `@a` e apertasse Enter mandaria a mensagem pela metade. */
function enterNoCampo(evento) {
  if (listaArroba.value.length) {
    evento.preventDefault()
    escolherArroba(listaArroba.value[arrobaEscolhido.value])
    return
  }
  // 🟢 Agora obedece à preferência (22/09). O `.prevent` saiu do template e
  // veio para cá: desligado, Enter tem de QUEBRAR LINHA, e um `prevent` fixo
  // engolia a quebra sem enviar nada -- tecla que não faz nada é pior que
  // tecla que faz outra coisa. É a mesma forma do `enterNoCompositor` da
  // Caixa de entrada.
  if (enterEnvia.value) {
    evento.preventDefault()
    enviar()
  }
}

function escolherArroba(pessoa) {
  if (!pessoa) return
  const campo = campoTexto.value
  const fim = campo ? campo.selectionStart : texto.value.length
  const at = inicioDaArroba
  if (at >= 0) {
    texto.value = texto.value.slice(0, at) + '@' + pessoa.nome + ' '
      + texto.value.slice(fim)
  }
  if (!mencionados.value.some((m) => m.id === pessoa.id)) {
    mencionados.value.push(pessoa)
  }
  listaArroba.value = []
  inicioDaArroba = -1
  nextTick(() => campo && campo.focus())
}

function tirarMencionado(id) {
  mencionados.value = mencionados.value.filter((m) => m.id !== id)
}

/* `partesDoTexto` vem de `util/mencao.js` (23/09): a MESMA função que o
   `mencao.teste.js` testa. Antes o teste defendia uma cópia. */

const FAMILIA = { image: 'imagem', audio: 'audio', video: 'video' }

function tipoDaMidia(m) {
  return FAMILIA[(m.midia_mime || '').split('/')[0]] || 'documento'
}

function tamanhoLegivel(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

async function carregarMidia(m) {
  if (!m.midia_id || midias[m.midia_id] !== undefined) return
  midias[m.midia_id] = ''   // "em andamento": o laço de 5 s não busca de novo
  try {
    const blob = await pedirBlob(`/api/midia/${m.midia_id}/ver`)
    midias[m.midia_id] = URL.createObjectURL(blob)
  } catch {
    // Falhar aqui não derruba a conversa: sobra o botão de baixar e o texto.
    midias[m.midia_id] = null
  }
}

function soltarMidias() {
  for (const [id, url] of Object.entries(midias)) {
    if (url) URL.revokeObjectURL(url)
    delete midias[id]
  }
}

/* 🚨 BAIXAR TAMBÉM PASSA PELO TOKEN. Um `<a href="/api/midia/...">` comum
   não manda o cabeçalho `Authorization` e a rota responde 401 -- a pessoa
   veria "não autorizado" ao clicar em baixar, dentro de uma tela onde ela
   está autenticada. Busca com token e entrega o arquivo por um link
   temporário, que some em seguida. */
async function baixar(m) {
  try {
    const blob = await pedirBlob(`/api/midia/${m.midia_id}`)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = m.midia_nome || 'arquivo'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch {
    erro.value = 'Não consegui baixar o arquivo.'
  }
}

/* 🚨 O CAMINHO MAIS CURTO PARA MANDAR UM PRINT. Sem isto, quem tira print
   precisa salvar em arquivo, achar a pasta e anexar -- três passos para o que
   o WhatsApp resolve com um. É o mesmo atalho da Caixa de entrada. */
function colar(evento) {
  const itens = Array.from(evento.clipboardData?.items || [])
  const imagem = itens.find((i) => i.type.startsWith('image/'))
  if (!imagem) return          // colar texto continua sendo colar texto
  const arq = imagem.getAsFile()
  if (!arq) return
  if (arquivos.value.length >= TETO_ANEXOS) {
    erro.value = `Já tem ${TETO_ANEXOS} arquivos — o máximo por envio.`
    return
  }
  evento.preventDefault()
  const carimbo = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
  arquivos.value = [...arquivos.value,
    new File([arq], `print-${carimbo}.png`, { type: arq.type })]
}

/* 🔵 25/09: até 10 anexos por envio -- mudança só de frontend, o backend já
   trata cada `POST .../arquivo` como independente. */
function escolherArquivo(evento) {
  const novos = Array.from(evento.target.files || [])
  erro.value = ''
  const cabem = TETO_ANEXOS - arquivos.value.length
  if (novos.length > cabem) {
    erro.value = cabem > 0
      ? `Dá para mandar no máximo ${TETO_ANEXOS} arquivos por envio — cabem mais ${cabem}.`
      : `Já tem ${TETO_ANEXOS} arquivos — o máximo por envio.`
  }
  const aceitos = []
  for (const f of novos.slice(0, Math.max(cabem, 0))) {
    if (f.size > TETO_ARQUIVO_MB * 1024 * 1024) {
      // 🚨 SEM O NOME DO ARQUIVO: ele não deve aparecer na tela para um
      // arquivo que foi recusado e não entrou.
      erro.value = `O arquivo tem ${(f.size / 1024 / 1024).toFixed(1)} MB e o `
        + `teto é ${TETO_ARQUIVO_MB} MB.`
      continue
    }
    aceitos.push(f)
  }
  arquivos.value = [...arquivos.value, ...aceitos]
  evento.target.value = ''
}

function limparArquivo(indice) {
  arquivos.value = arquivos.value.filter((_, i) => i !== indice)
}

function limparArquivos() {
  arquivos.value = []
  const campo = document.getElementById('chat-campo-arquivo')
  if (campo) campo.value = ''
}

/* ⚠️ NÃO passa pelo `api.post`, que serializa JSON. Arquivo vai por
   `FormData`, e aí o navegador monta o `Content-Type` com o boundary sozinho
   -- definir o cabeçalho na mão quebra o upload EM SILÊNCIO, com o servidor
   recebendo corpo vazio. */
async function subirArquivo(blob, nome, legenda) {
  const dados = new FormData()
  dados.append('arquivo', blob, nome)
  dados.append('legenda', legenda)
  const vivos = mencionados.value.filter((p) => texto.value.includes('@' + p.nome))
  dados.append('mencionados', vivos.map((p) => p.id).join(','))
  const r = await fetch(`/api/chat/salas/${sala.value.id}/arquivo`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${localStorage.getItem('movizap.token')}` },
    body: dados,
  })
  if (!r.ok) {
    let motivo = 'Não consegui enviar o arquivo.'
    try { motivo = (await r.json()).detail || motivo } catch { /* corpo não-JSON */ }
    throw new Error(motivo)
  }
}

async function enviarArquivo() {
  if (!arquivos.value.length || enviando.value || !sala.value) return
  enviandoArquivo.value = true
  erro.value = ''
  const total = arquivos.value.length
  let enviados = 0
  try {
    // Sequencial, texto só no primeiro -- mesmo padrão da Caixa de entrada.
    for (const arq of arquivos.value) {
      await subirArquivo(arq, arq.name, enviados === 0 ? texto.value.trim() : '')
      enviados++
    }
    texto.value = ''
    mencionados.value = []
    listaArroba.value = []
    limparArquivos()
    await abrir(sala.value.id)
  } catch (e) {
    // 🔵 28/09: se um do meio falhar, PARA e mostra quantos já foram --
    // mesma decisão da Caixa, documentada no plano.
    arquivos.value = arquivos.value.slice(enviados)
    erro.value = (enviados > 0
        ? `${enviados} de ${total} enviados; parei no que falhou: `
        : '') + (e.message || 'Não consegui enviar o arquivo.')
    if (enviados > 0) {
      texto.value = ''
      await abrir(sala.value.id)
    }
  } finally {
    enviandoArquivo.value = false
  }
}

/* ---- gravar voz ----------------------------------------------------------
   🚨 SOLTAR O MICROFONE É PARTE DA FUNÇÃO, não um detalhe. Na Caixa de
   entrada isso já foi defeito: a trilha ficava aberta e a luz de gravação
   acesa depois de sair da tela, com a pessoa achando que o painel continuava
   ouvindo. Aqui ele é solto no `onstop`, no cancelar E na saída da tela. */
const gravando = ref(false)
const segundosGravados = ref(0)
let gravador = null
let pedacosAudio = []
let relogioGravacao = null

async function comecarGravacao() {
  try {
    const trilha = await navigator.mediaDevices.getUserMedia({ audio: true })
    pedacosAudio = []
    gravador = new MediaRecorder(trilha)
    gravador.ondataavailable = (e) => { if (e.data.size) pedacosAudio.push(e.data) }
    gravador.onstop = () => trilha.getTracks().forEach((t) => t.stop())
    gravador.start()
    gravando.value = true
    segundosGravados.value = 0
    relogioGravacao = setInterval(() => { segundosGravados.value += 1 }, 1000)
  } catch {
    erro.value = 'Não consegui usar o microfone. Verifique a permissão do navegador.'
  }
}

function pararRelogio() {
  clearInterval(relogioGravacao)
  gravando.value = false
}

/* Cancelar existe porque gravar sem poder desistir faz a pessoa não gravar. */
function cancelarGravacao() {
  if (!gravador) return
  gravador.onstop = null
  gravador.stream?.getTracks().forEach((t) => t.stop())
  gravador.stop()
  gravador = null
  pedacosAudio = []
  pararRelogio()
}

async function enviarGravacao() {
  if (!gravador) return
  const pronto = new Promise((resolve) => {
    const antes = gravador.onstop
    gravador.onstop = (e) => { antes?.(e); resolve() }
  })
  gravador.stop()
  await pronto
  pararRelogio()

  /* 🔵 25/09, celular: o iPhone grava MP4/AAC. Com rótulo "ogg", quem abre
     no computador recebe um arquivo que diz ser uma coisa e é outra. Só o
     caso do iPhone muda; o resto continua como sempre foi. */
  const doIphone = (gravador.mimeType || '').includes('mp4')
  const blob = new Blob(pedacosAudio, { type: doIphone ? 'audio/mp4' : 'audio/ogg; codecs=opus' })
  gravador = null
  pedacosAudio = []
  if (!blob.size) return

  enviandoArquivo.value = true
  erro.value = ''
  try {
    const carimbo = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
    await subirArquivo(blob, `voz-${carimbo}.${doIphone ? 'm4a' : 'ogg'}`, texto.value.trim())
    texto.value = ''
    mencionados.value = []
    await abrir(sala.value.id)
  } catch (e) {
    erro.value = e.message || 'Não consegui enviar o áudio.'
  } finally {
    enviandoArquivo.value = false
  }
}

function minutos(s) {
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

async function enviar() {
  // Com arquivo escolhido, Enter manda O ARQUIVO com o texto de legenda --
  // senão a legenda iria numa mensagem e o arquivo em outra.
  if (arquivos.value.length) return enviarArquivo()
  const t = texto.value.trim()
  if (!t || enviando.value || !sala.value) return
  enviando.value = true
  erro.value = ''
  try {
    // ⚠️ Só vai quem AINDA está escrito no texto: apagar o "@Fulano" à mão
    // tem de desfazer a menção, senão a pessoa é chamada sem aparecer nada.
    const vivos = mencionados.value.filter((p) => t.includes('@' + p.nome))
    await api.post(`/api/chat/salas/${sala.value.id}/escrever`,
                   { texto: t, mencionados: vivos.map((p) => p.id),
                     citando_id: citando.value?.id ?? null })
    texto.value = ''
    mencionados.value = []
    listaArroba.value = []
    citando.value = null
    // 🚨 Relê em vez de empurrar o balão na mão: o que vale é o que o banco
    // gravou, não o que a tela supõe ter acontecido.
    await abrir(sala.value.id)
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui enviar.'
  } finally {
    enviando.value = false
  }
}

/* ---- editar/apagar a própria mensagem (25/09, item B) --------------------
   🔵 Pedido dele: "editar (15 min) e apagar (48 h) a própria mensagem, como
   na Caixa". Mesma janela, mesmo padrão -- só que aqui é tudo local, sem
   chamada ao WhatsApp: a rota já cuida disso, a tela só confere de novo para
   não oferecer um botão que o servidor vai recusar. */
function idadeMin(m) {
  return (Date.now() - new Date(m.criada_em).getTime()) / 60000
}
function podeEditarChat(m) {
  return m.minha && !m.apagada_em && idadeMin(m) <= JANELA_EDITAR_MIN
}
function podeApagarChat(m) {
  return m.minha && !m.apagada_em && idadeMin(m) <= JANELA_APAGAR_MIN
}
function abrirEdicaoChat(m) {
  editando.value = { id: m.id, texto: m.texto || '' }
}
async function salvarEdicaoChat() {
  const e = editando.value
  if (!e || !e.texto.trim() || salvandoEdicao.value || !sala.value) return
  salvandoEdicao.value = true
  erro.value = ''
  try {
    await api.post(`/api/chat/salas/${sala.value.id}/mensagens/${e.id}/editar`,
                   { texto: e.texto })
    editando.value = null
    await abrir(sala.value.id)
  } catch (x) {
    erro.value = x instanceof ErroDeApi ? x.message : 'Não consegui editar.'
  } finally {
    salvandoEdicao.value = false
  }
}
async function apagarMensagemChat(m) {
  if (!confirm('Apagar esta mensagem? Ela some para todos na sala, mas continua registrada, marcada como apagada.')) return
  try {
    await api.post(`/api/chat/salas/${sala.value.id}/mensagens/${m.id}/apagar`)
    await abrir(sala.value.id)
  } catch (x) {
    erro.value = x instanceof ErroDeApi ? x.message : 'Não consegui apagar.'
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

/* 🟢 A PREFERÊNCIA VALE AQUI TAMBÉM (22/09). A tecla estava FIXA no template:
   o chat mandava com Enter sempre, sem nunca ler `/api/eu/atalhos`. O
   checkbox de "Minha conta" diz *"como você envia"* -- e para esta tela ele
   era uma frase sem efeito.

   ⚠️ Falhou a leitura, fica DESLIGADO: `Ctrl+Enter` continua enviando e
   Enter quebra linha. Perder a tecla é chato; mandar sem querer, não. */
const enterEnvia = ref(false)

async function carregarPreferencia() {
  try {
    const r = await api.get('/api/eu/atalhos')
    enterEnvia.value = Boolean(r.enviar_com_enter)
  } catch {
    enterEnvia.value = false
  }
}

onMounted(async () => {
  document.addEventListener('click', fecharEmojiSeForaDele)
  await carregarPreferencia()
  await carregar()
  // Entrou direto por `/chat?sala=11` (ou recarregou a página com a sala aberta).
  if (route.query.sala) await abrir(Number(route.query.sala))
  /* 🚨 UMA BUSCA DA LISTA POR VOLTA (23/09). Antes: lista, sala, e a lista de
     NOVO no fim do `abrir`. Agora a sala vem PRIMEIRO -- é ela que marca a
     leitura -- e a lista depois, uma vez, já com o não lido zerado. A ordem
     importa: lista antes da sala mostraria por 5 s um não lido que já foi lido. */
  timer = setInterval(async () => {
    const estava = estaNoFim()
    if (sala.value) {
      await abrir(sala.value.id, { silencioso: true, recarregarLista: false })
      if (estava) rolarParaOFim()
    }
    await carregar({ silencioso: true })
  }, 5000)
})

onUnmounted(() => {
  clearInterval(timer)
  document.removeEventListener('click', fecharEmojiSeForaDele)
  // 🚨 A SAÍDA PELA PORTA TAMBÉM CONTA. Trocar de tela no meio de uma
  // gravação deixaria a trilha aberta e a luz vermelha do navegador acesa,
  // sem nem o botão de cancelar à vista — defeito que a Caixa de entrada já
  // teve, achado na auditoria de 25/08.
  cancelarGravacao()
  soltarMidias()
})

/* 🚨 COMPARA O `id`, NUNCA O OBJETO (22/09) -- e este é o defeito que chegou
   ao usuário: *"alguns usuários não conseguem escrever, fica apagando sozinho
   a mensagem antes de enviar"*.

   A intenção continua a mesma e é certa: trocou de conversa, limpa o
   rascunho, senão você manda para a Erika o que escreveu para o João. O que
   estava errado era o CRITÉRIO. `watch(sala, ...)` compara identidade de
   objeto, e o ciclo de 5 segundos reconstrói `salas` com objetos novos a cada
   resposta do servidor -- então `abrir()` reapontava `sala` para um objeto
   diferente da MESMA conversa, o watcher entendia "trocou" e apagava o que a
   pessoa estava escrevendo. A cada 5 segundos, para todo mundo. Quem não
   percebia era só quem terminava de escrever antes do próximo ciclo.

   ⚠️ `mencionados` e `listaArroba` entram junto: só `texto` era limpo, e os
   chips de menção da conversa anterior sobreviviam à troca real de sala. */
watch(() => sala.value?.id, (novo, velho) => {
  if (novo === velho) return
  texto.value = ''
  mencionados.value = []
  listaArroba.value = []
  // O anexo escolhido e ainda não enviado é rascunho como o texto: ele era
  // para AQUELA conversa. E a gravação em curso para junto.
  limparArquivos()
  cancelarGravacao()
  // A citação também era desta sala -- citar em outra citaria mensagem que
  // o backend recusa (`chat._conferir_citada`), e o balão ficaria pendurado
  // no compositor sem explicação.
  citando.value = null
})

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
  <div class="tela" :class="{ 'tela--com-sala': sala }">
    <!-- 🚨 A BARRA ALTA (27/08, pedido dele: *"design replicado de caixa de
         entrada do zap, porém com barra alta evidente para distinção"*).

         O pedido é de DESENHO e a razão é de RISCO: quanto mais esta tela se
         parecer com a caixa de entrada, mais fácil fica escrever para o
         colega achando que é o cliente -- ou o contrário. A semelhança é o
         que ele quer, e a barra é o que a torna segura.

         ⚠️ ELA É A PRIMEIRA COISA DA TELA, atravessa a largura toda e não
         rola junto: um aviso que sai de vista com a rolagem avisa só quem já
         sabia. E é a ÚNICA repetição permitida deste recado -- ele já esteve
         em três lugares ao mesmo tempo, e três avisos iguais viram
         decoração que o olho pula. -->
    <p class="barra-interna" role="note">
      <i class="bi bi-shield-lock-fill" aria-hidden="true"></i>
      <strong>Conversa interna.</strong>
      <span>Nada aqui chega ao cliente — para falar com ele, use a Caixa de entrada.</span>
    </p>

    <header class="tela__cabecalho">
      <div>
        <h1>Chat interno</h1>
      </div>
      <span v-if="naoLidasTotal" class="chip chip--acento">
        {{ naoLidasTotal }} não lida{{ naoLidasTotal > 1 ? 's' : '' }}
      </span>
    </header>

    <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>
    <p v-if="recado" class="aviso aviso--ok" role="status">{{ recado }}</p>

    <div class="colunas" :class="{ 'colunas--com-sala': sala }">
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
          <!-- 🚨 O TEXTO VOLTOU (28/08). Ele perguntou *"o botão de + não tem
               opção para criar o grupo"* e depois *"não tínhamos uma demanda
               de criar o grupo que havia sido entregue?"* -- tínhamos: a
               demanda é dele (*"podemos criar grupos com os temas"*, 25/08) e
               a função foi entregue em 12/08, com o texto "Criar grupo" na
               tela. Em 25/08, refazendo o chat, EU tirei a palavra e deixei
               só o ícone: a função continuou inteira e ficou inachável.

               ⚠️ `title` não é rótulo. O balão do navegador demora cerca de
               um segundo e não existe em toque -- quem não passa o mouse
               nunca descobre o que o quadrado faz. -->
          <button
            class="botao botao--pequeno botao--contorno"
            type="button"
            title="Criar um grupo do chat interno"
            @click="criandoGrupo = !criandoGrupo"
          >
            <i class="bi bi-people" aria-hidden="true"></i>
            Criar grupo
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
            <!-- 🔵 25/09, celular: sem a lista ao lado, o caminho de volta é este
                 botão (e o "voltar" do aparelho). Some no computador. -->
            <button class="botao botao--fantasma botao--icone so-celular" type="button"
                    aria-label="Voltar para a lista de conversas" @click="voltarParaLista">
              <i class="bi bi-arrow-left" aria-hidden="true"></i>
            </button>
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
            <!-- 🚨 "EXCLUIR" AQUI TIRA DA MINHA LISTA, e o rótulo diz isso.
                 Chamar de "excluir conversa" sem mais nada faria parecer que
                 apaga para os dois -- e conversa interna é prova de
                 combinado: quem disse o quê sobre um atendimento. -->
            <button class="botao botao--pequeno botao--fantasma" type="button"
                    title="Tirar esta conversa da minha lista"
                    aria-label="Tirar esta conversa da minha lista"
                    @click="esconderConversa">
              <i class="bi bi-trash3" aria-hidden="true"></i>
            </button>
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
                         { 'balao--seguida': mesmoAutor(m, i),
                           'balao--realcado': m.id === balaoRealcado }]"
                :data-mensagem="m.id"
              >
                <p v-if="!m.minha && !mesmoAutor(m, i)" class="balao__autor pequeno">
                  {{ m.autor }}
                </p>
                <!-- A mensagem que esta está respondendo (29/09). Clicar rola
                     até ela e a destaca -- mesmo gesto da Caixa de entrada. -->
                <p v-if="m.citada_id" class="balao__citada pequeno"
                   @click="irParaMensagem(m.citada_id)">
                  <i class="bi bi-reply" aria-hidden="true"></i>
                  <span class="fraco">{{ m.citada_autor || '(apagada)' }}:</span>
                  {{ m.citada_texto
                     || (m.citada_midia_mime
                         ? `(${tipoDaMidia({ midia_mime: m.citada_midia_mime })})`
                         : '(mensagem)') }}
                </p>
                <!-- 🚨 O DESTAQUE VEM DE `mencionados`, NÃO DE PROCURAR "@" NO
                     TEXTO. Quem foi chamado está gravado; caçar arroba no texto
                     acenderia "@10h" e "email@movisat" como se fossem gente. -->
                <!-- 🚨 O ANEXO (22/09). Imagem e áudio aparecem DENTRO do
                     balão; o resto vira uma linha com nome, tamanho e o botão
                     de baixar. Quem decide o que é o arquivo é o MIME, nunca
                     a extensão do nome, que qualquer um renomeia. -->
                <!-- 🔵 25/09: apagada por quem escreveu -- mesmo padrão da
                     Caixa, atrás de um clique, nunca destruída. -->
                <template v-if="!m.apagada_em || originalAberto.has(m.id)">
                  <template v-if="m.midia_id">
                    <!-- 🚨 CLICAR ABRE EM TELA CHEIA (29/09), igual à Caixa:
                         imagem dentro do balão só "aparecia", sem jeito de
                         ampliar -- pedido dele. -->
                    <img
                      v-if="tipoDaMidia(m) === 'imagem' && midias[m.midia_id]"
                      :src="midias[m.midia_id]"
                      class="balao__imagem balao__imagem--clicavel"
                      :alt="m.midia_nome || 'Imagem enviada'"
                      @click="emTelaCheia = midias[m.midia_id]"
                    />
                    <audio
                      v-else-if="tipoDaMidia(m) === 'audio' && midias[m.midia_id]"
                      :src="midias[m.midia_id]" controls class="balao__audio"
                    ></audio>
                    <video
                      v-else-if="tipoDaMidia(m) === 'video' && midias[m.midia_id]"
                      :src="midias[m.midia_id]" controls class="balao__imagem"
                    ></video>
                    <!-- ⚠️ `midias[id] === ''` é "buscando"; `null` é "não deu".
                         Nos dois casos sobra esta linha, que é a que sempre
                         funciona -- anexo que não abre ainda pode ser baixado. -->
                    <a
                      v-if="tipoDaMidia(m) === 'documento' || midias[m.midia_id] === null"
                      class="balao__arquivo"
                      :href="`/api/midia/${m.midia_id}`"
                      @click.prevent="baixar(m)"
                    >
                      <i class="bi bi-paperclip" aria-hidden="true"></i>
                      <span>{{ m.midia_nome || 'arquivo' }}</span>
                      <span class="apagado pequeno">{{ tamanhoLegivel(m.midia_tamanho) }}</span>
                    </a>
                  </template>
                  <p v-if="m.texto" class="balao__texto">
                    <template v-for="(p, k) in partesDoTexto(m)" :key="k">
                      <mark v-if="p.mencao" class="mencao"
                            :class="{ 'mencao--eu': p.eu }">{{ p.texto }}</mark>
                      <template v-else>{{ p.texto }}</template>
                    </template>
                  </p>
                </template>
                <p v-if="m.apagada_em && !originalAberto.has(m.id)"
                   class="balao__texto balao__apagada">
                  <i class="bi bi-slash-circle" aria-hidden="true"></i>
                  mensagem apagada
                  <button v-if="m.texto || m.midia_id" type="button" class="balao__revelar"
                          @click="alternarOriginal(m.id)">ver o que dizia</button>
                </p>
                <p v-if="m.apagada_em && originalAberto.has(m.id)"
                   class="balao__marca pequeno">
                  <i class="bi bi-slash-circle" aria-hidden="true"></i>
                  apagada ·
                  <button type="button" class="balao__revelar"
                          @click="alternarOriginal(m.id)">esconder</button>
                </p>
                <p v-if="m.editada_em && m.conteudo_original && originalAberto.has(m.id)"
                   class="balao__original pequeno">
                  antes: {{ m.conteudo_original }}
                </p>
                <p class="balao__rodape apagado pequeno">
                  {{ hora(m.criada_em) }}
                  <button v-if="m.editada_em" type="button" class="balao__editada"
                          :aria-expanded="originalAberto.has(m.id)"
                          :title="m.conteudo_original ? 'ver o texto anterior' : ''"
                          @click="alternarOriginal(m.id)">
                    · editada
                  </button>
                  <span v-if="m.minha && !m.apagada_em && TIQUE_CHAT[m.lida ? 'lida' : 'enviada']"
                        class="balao__tique"
                        :class="{ 'balao__lida': m.lida }"
                        :title="m.lida ? 'lida' : 'enviada'">{{ TIQUE_CHAT[m.lida ? 'lida' : 'enviada'] }}</span>
                </p>

                <!-- 🔵 25/09: editar (15 min) / apagar (48 h) a própria
                     mensagem, só na minha e dentro da janela -- igual à
                     Caixa, sem chamar o WhatsApp (é tudo local).
                     🔵 29/09: citar vale em qualquer mensagem não apagada,
                     de qualquer autor -- não depende de editar/apagar. -->
                <div v-if="!m.apagada_em || podeEditarChat(m) || podeApagarChat(m)"
                     class="balao__acoes">
                  <button v-if="!m.apagada_em" class="balao__acao" type="button"
                          title="Responder citando"
                          aria-label="Responder citando" @click="citar(m)">
                    <i class="bi bi-reply" aria-hidden="true"></i>
                  </button>
                  <button v-if="podeEditarChat(m)" class="balao__acao" type="button"
                          title="Editar (até 15 minutos depois de enviar)"
                          aria-label="Editar mensagem" @click="abrirEdicaoChat(m)">
                    <i class="bi bi-pencil" aria-hidden="true"></i>
                  </button>
                  <button v-if="podeApagarChat(m)" class="balao__acao" type="button"
                          title="Apagar"
                          aria-label="Apagar mensagem" @click="apagarMensagemChat(m)">
                    <i class="bi bi-trash" aria-hidden="true"></i>
                  </button>
                </div>
              </div>
            </template>
          </div>

          <div class="cartao__corpo pilha">
            <!-- A mensagem que está sendo citada, com um X para desistir
                 (29/09, mesmo padrão da Caixa). -->
            <div v-if="citando" class="citando">
              <i class="bi bi-reply" aria-hidden="true"></i>
              <span class="citando__texto">
                {{ citando.texto || (citando.midia_id
                    ? `(${tipoDaMidia(citando)})` : '(mensagem)') }}
              </span>
              <button class="botao botao--pequeno botao--fantasma" type="button"
                      title="Não citar" @click="citando = null">×</button>
            </div>

            <!-- `position: relative` porque a lista do `@` se ancora aqui. -->
            <label class="campo campo--arroba">
              <span class="so-leitor">Mensagem</span>
              <!-- 🚨 QUEM DECIDE É A PREFERÊNCIA (22/09), não esta tela.
                   Ligada: Enter envia e Shift+Enter quebra linha. Desligada:
                   Enter quebra linha e `Ctrl+Enter` envia -- o mesmo par da
                   Caixa de entrada. Antes o Enter estava FIXO aqui, e o
                   checkbox de "Minha conta" não mandava em nada.

                   ⚠️ `Ctrl+Enter` vale nos DOIS casos: sem ele, quem
                   desligasse a preferência ficaria sem nenhuma tecla para
                   enviar.

                   ⚠️ O PLACEHOLDER SEGUE A PREFERÊNCIA. Ele dizia "aperte
                   Enter" para todo mundo; desligada, seria a tela prometendo
                   o que a tecla não faz. -->
              <textarea
                ref="campoTexto"
                v-model="texto"
                class="campo__entrada"
                rows="2"
                maxlength="4000"
                :placeholder="enterEnvia
                  ? 'Escreva e aperte Enter — @ chama alguém'
                  : 'Escreva e aperte Ctrl+Enter — @ chama alguém'"
                @input="olharArroba"
                @paste="colar"
                @keydown.ctrl.enter.prevent="enviar"
                @keydown.enter.exact="enterNoCampo"
                @keydown.down.prevent="andarNaLista(1)"
                @keydown.up.prevent="andarNaLista(-1)"
                @keydown.esc="listaArroba = []"
              ></textarea>

              <!-- ⚠️ A LISTA APARECE ACIMA DO CAMPO, não abaixo: abaixo ela
                   ficaria fora da tela quando o compositor está no rodapé. -->
              <ul v-if="listaArroba.length" class="arroba" role="listbox">
                <li v-for="(p, i) in listaArroba" :key="p.id">
                  <button type="button"
                          class="arroba__item"
                          :class="{ 'arroba__item--aqui': i === arrobaEscolhido }"
                          :aria-selected="i === arrobaEscolhido"
                          @mousedown.prevent="escolherArroba(p)">
                    {{ p.nome }}
                  </button>
                </li>
              </ul>
            </label>

            <!-- 🚨 QUEM VAI SER CHAMADO APARECE ANTES DE ENVIAR. Sem isto a
                 pessoa só descobre que chamou alguém depois de mandar. -->
            <p v-if="mencionados.length" class="linha pequeno fraco chamados">
              <i class="bi bi-at" aria-hidden="true"></i>
              <span>chamando</span>
              <button v-for="p in mencionados" :key="p.id"
                      class="chamados__chip" type="button"
                      :title="`não chamar ${p.nome}`"
                      @click="tirarMencionado(p.id)">
                {{ p.nome }} <i class="bi bi-x" aria-hidden="true"></i>
              </button>
            </p>
            <!-- 🚨 O ANEXO ESCOLHIDO APARECE ANTES DE IR (22/09). Sem esta
                 linha, quem cola um print não vê nada acontecer e cola de
                 novo — e manda dois.
                 🔵 25/09: até 10 por envio, cada um vira um balão. -->
            <p v-for="(a, i) in arquivos" :key="i" class="linha pequeno anexo-escolhido">
              <i class="bi bi-paperclip" aria-hidden="true"></i>
              <span>{{ a.name }}</span>
              <span class="apagado">{{ tamanhoLegivel(a.size) }}</span>
              <button class="botao botao--pequeno botao--contorno" type="button"
                      title="Tirar este anexo" @click="limparArquivo(i)">
                Tirar
              </button>
            </p>
            <p v-if="arquivos.length > 1" class="linha pequeno apagado">
              O texto vai só no primeiro.
              <button class="botao botao--pequeno botao--contorno" type="button"
                      @click="limparArquivos">Tirar todos</button>
            </p>

            <!-- 🚨 A GRAVAÇÃO TEM SAÍDA. Gravar sem poder desistir faz a
                 pessoa não gravar; o tempo à vista evita o áudio de 4
                 minutos que ninguém ouve. -->
            <p v-if="gravando" class="linha pequeno gravando">
              <span class="gravando__ponto" aria-hidden="true"></span>
              <span>Gravando {{ minutos(segundosGravados) }}</span>
              <button class="botao botao--pequeno botao--contorno" type="button"
                      @click="cancelarGravacao">Cancelar</button>
              <button class="botao botao--pequeno botao--primario" type="button"
                      :disabled="enviandoArquivo" @click="enviarGravacao">
                Enviar áudio
              </button>
            </p>

            <div class="linha ci__envio">
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

              <BotaoMensagensRapidas onde="interno" @inserir="inserirNoTexto" />

              <!-- 🚨 BOTÃO COM RÓTULO, não só ícone. `title` não é rótulo: o
                   balão do navegador demora cerca de um segundo e não existe
                   em toque. Foi esse o erro de 25/08 que escondeu o "Criar
                   grupo" desta mesma tela. -->
              <label class="botao botao--contorno" :class="{ 'botao--ocupado': enviandoArquivo }"
                     :title="`Anexar (até ${TETO_ANEXOS})`">
                <i class="bi bi-paperclip" aria-hidden="true"></i>
                Anexar
                <input
                  id="chat-campo-arquivo"
                  class="so-leitor"
                  type="file"
                  multiple
                  :disabled="enviandoArquivo || gravando"
                  @change="escolherArquivo"
                />
              </label>

              <button
                v-if="!gravando"
                class="botao botao--contorno"
                type="button"
                :disabled="enviandoArquivo"
                @click="comecarGravacao"
              >
                <i class="bi bi-mic" aria-hidden="true"></i>
                Gravar
              </button>

              <button
                class="botao botao--primario"
                type="button"
                :disabled="enviando || enviandoArquivo || (!texto.trim() && !arquivos.length)"
                @click="enviar"
              >
                <span v-if="enviando || enviandoArquivo" class="girando"></span>
                {{ enviando || enviandoArquivo ? 'Enviando…' : 'Enviar' }}
              </button>
              <!-- ⚠️ A DICA SEGUE A PREFERÊNCIA (22/09). Ela dizia "Enter
                   envia" para todo mundo; com a preferência desligada, a tela
                   estaria prometendo o que a tecla não faz. -->
              <span class="apagado pequeno">
                {{ enterEnvia
                  ? 'Enter envia · Shift+Enter quebra linha'
                  : 'Ctrl+Enter envia · Enter quebra linha' }}
              </span>
            </div>
          </div>
        </template>
      </section>
    </div>

    <!-- 🔵 25/09: EDITAR A MINHA MENSAGEM (até 15 min). Classes `.modal`
         globais, definidas em `estilo/componentes.css` -- mesma UI da Caixa. -->
    <div v-if="editando" class="modal" @click.self="editando = null">
      <div class="modal__caixa" role="dialog" aria-modal="true" aria-label="Editar mensagem">
        <p class="modal__titulo">Editar mensagem</p>
        <p class="modal__texto pequeno">
          Dá para editar por {{ JANELA_EDITAR_MIN }} minutos depois de enviar.
        </p>
        <textarea v-model="editando.texto" class="campo__entrada" rows="4"
                  maxlength="4000"></textarea>
        <div class="modal__acoes">
          <button class="botao botao--contorno" type="button" @click="editando = null">
            Cancelar
          </button>
          <button class="botao botao--primario" type="button"
                  :disabled="!editando.texto.trim() || salvandoEdicao"
                  @click="salvarEdicaoChat">
            <span v-if="salvandoEdicao" class="girando"></span>
            Salvar
          </button>
        </div>
      </div>
    </div>

    <!-- TELA CHEIA (29/09) — clique em qualquer lugar fecha, mesmo padrão da
         Caixa de entrada. -->
    <div v-if="emTelaCheia" class="cheia" @click="emTelaCheia = null">
      <img :src="emTelaCheia" class="cheia__img" alt="imagem da conversa" />
      <button class="cheia__fechar" type="button" aria-label="Fechar">
        <i class="bi bi-x-lg" aria-hidden="true"></i>
      </button>
    </div>
  </div>
</template>

<style scoped>
/* ---- a barra alta de distinção (27/08) ----------------------------------
   🚨 O PEDIDO É DE DESENHO E A RAZÃO É DE RISCO. Ele mandou esta tela se
   parecer com a caixa de entrada do WhatsApp -- e quanto mais parecida, mais
   fácil escrever para o colega achando que é o cliente. A barra é o que torna
   a semelhança segura.

   ⚠️ ÂMBAR, NÃO VERMELHO. Vermelho é erro, e não há erro nenhum aqui: é
   contexto. Vermelho para o que é normal treina a equipe a ignorar vermelho.

   ⚠️ ALTA E LARGA de propósito: ela é a primeira coisa da tela, atravessa a
   largura toda e não rola junto -- aviso que sai de vista com a rolagem avisa
   só quem já sabia. */
.barra-interna {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--e-2);
  margin: 0 0 var(--e-4);
  padding: var(--e-3) var(--e-4);
  background: var(--aviso-suave);
  border: var(--borda-fina) solid var(--aviso-borda);
  /* A faixa grossa à esquerda é o que se enxerga pelo canto do olho, antes
     mesmo de ler. */
  border-left: 4px solid var(--aviso);
  border-radius: var(--r-md);
  color: var(--aviso);
  font-size: var(--txt-md);
}
.barra-interna strong { font-weight: var(--peso-forte); }
.barra-interna span { color: var(--texto-fraco); }
.barra-interna .bi { font-size: 16px; }

/* ---- coluna de pessoas e grupos ----------------------------------------- */
/* ⚠️ `flex-wrap` desde 28/08: o botão de criar grupo voltou a ter texto, e
   sem quebra ele espremia a busca até o placeholder sumir na coluna estreita.
   Quebrar é o certo -- os dois continuam inteiros, um em cada linha. */
.ci__topo { display: flex; gap: var(--e-2); align-items: center; flex-wrap: wrap; }
.ci__topo .busca { flex: 1 1 12rem; }
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

/* ══ CELULAR (🔵 25/09) ═════════════════════════════════════════════════
   *"os mesmos recursos, porém somente os chats"*. A 390 px as duas colunas
   ficavam lado a lado com 103 e 177 px, sem nome nas conversas (medido na
   prévia de 25/09). Agora é UMA COISA POR VEZ: sem sala, a lista; com sala,
   só ela, ocupando a altura toda, e o "Voltar" (ou o do aparelho) traz a
   lista de volta.
   ⚠️ A BARRA "Conversa interna." FICA, também no celular: é ela que impede
   escrever para o colega achando que é o cliente (27/08). Só fica mais baixa.
   ⚠️ Nada daqui vale acima de 860 px: o computador fica como estava. */
@media (max-width: 860px) {
  .tela { display: flex; flex-direction: column; height: 100%; min-height: 0; }
  .tela > .colunas { flex: 1 1 auto; min-height: 0; }
  .colunas { flex-direction: column; align-items: stretch; gap: 0; }
  .colunas--com-sala > .coluna:not(.coluna--larga) { display: none; }
  .colunas:not(.colunas--com-sala) > .coluna--larga { display: none; }
  .coluna { flex: 1 1 auto; }
  .tela--com-sala .tela__cabecalho { display: none; }
  .barra-interna { padding-top: var(--e-2); padding-bottom: var(--e-2); }

  /* Com a sala aberta, as mensagens ficam com toda a altura que sobra e o
     campo de escrever fica sempre no rodapé. */
  .coluna--larga { display: flex; flex-direction: column; min-height: 0; }
  .coluna--larga > * { flex: none; }
  .coluna--larga > .baloes { flex: 1 1 auto; min-height: 0; max-height: none; }
  .salas { max-height: none; }
  /* A fileira de envio (emoji, rápidas, Anexar, Gravar, Enviar) quebra
     linha: numa só, o Enviar saía da tela (medido na prévia de 25/09). */
  .ci__envio { flex-wrap: wrap; }

  /* Alvos de toque: nada abaixo de 44 px. */
  .coluna .botao--icone,
  .coluna .botao--pequeno,
  .coluna :deep(.mr__botao) { min-height: 44px; min-width: 44px; }
  .coluna .botao { min-height: 44px; }
}

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
/* 🔵 25/09 (item G): visual igual ao da Caixa de entrada, pedido dele --
   "ajustar o painel interno visualmente igual ao do externo e as
   confirmações de envio e leitura tbm". Isto substitui a cor de acento
   genérica que havia antes (a nota de 22/09 dizia que verde era "cor do
   WhatsApp, e o chat interno não é WhatsApp" -- decisão anterior, revista
   agora por pedido dele, posterior e explícito). Mesmos tokens `--conversa-*`
   da Caixa, definidos em `estilo/tokens.css`. */
.balao {
  position: relative;
  max-width: min(72%, 520px);
  padding: 7px 11px 6px;
  border-radius: var(--conversa-raio);
  background: var(--conversa-balao);
  box-shadow: var(--sombra-1);
  line-height: 1.5;
}
.balao--dele {
  align-self: flex-start;
  border-top-left-radius: 0;
}
.balao--dele::before {
  content: "";
  position: absolute;
  left: calc(var(--conversa-bico) * -1);
  top: 0;
  border: var(--conversa-bico) solid transparent;
  border-left: 0;
  border-right-color: var(--conversa-balao);
  border-top-color: var(--conversa-balao);
}
.balao--minha {
  align-self: flex-end;
  background: var(--conversa-saida);
  border-top-right-radius: 0;
}
.balao--minha::before {
  content: "";
  position: absolute;
  right: calc(var(--conversa-bico) * -1);
  top: 0;
  border: var(--conversa-bico) solid transparent;
  border-right: 0;
  border-left-color: var(--conversa-saida);
  border-top-color: var(--conversa-saida);
}
.balao__rodape {
  margin: 2px 0 0;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.balao__tique { margin-left: 3px; letter-spacing: -2px; }
.balao__lida { color: var(--conversa-lida); font-weight: var(--peso-forte); }
.balao__editada {
  background: none;
  border: 0;
  padding: 0;
  margin-left: 3px;
  font: inherit;
  color: inherit;
  cursor: pointer;
  text-decoration: underline dotted;
}
.balao__editada:hover { text-decoration: underline; }
.balao__apagada {
  color: var(--texto-apagado);
  font-style: italic;
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.balao__revelar {
  background: none;
  border: 0;
  padding: 0;
  font: inherit;
  color: inherit;
  cursor: pointer;
  text-decoration: underline dotted;
  text-underline-offset: 2px;
}
.balao__revelar:hover { text-decoration: underline; }
.balao__marca { color: var(--texto-apagado); display: flex; gap: 4px; align-items: center; }
.balao__original {
  margin-top: var(--e-1);
  padding-left: var(--e-2);
  border-left: 2px solid var(--borda);
  color: var(--texto-apagado);
  white-space: pre-wrap;
}
.balao__acoes {
  position: absolute;
  top: -11px;
  right: var(--e-2);
  display: flex;
  gap: 2px;
  padding: 2px;
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-full);
  box-shadow: var(--sombra-2);
  opacity: 0;
  pointer-events: none;
  transform: translateY(3px);
  transition: opacity var(--tempo) var(--curva),
              transform var(--tempo) var(--curva);
}
.balao:hover .balao__acoes,
.balao:focus-within .balao__acoes {
  opacity: 1;
  pointer-events: auto;
  transform: none;
}
.balao__acao {
  border: 0;
  background: none;
  cursor: pointer;
  padding: 3px 6px;
  border-radius: var(--r-full);
  color: var(--texto-fraco);
  line-height: 1;
}
.balao__acao:hover { background: var(--superficie-2); color: var(--texto); }

/* ---- responder citando (29/09), mesmo padrão da Caixa de entrada -------- */
.balao__citada {
  border-left: 3px solid var(--acento-borda);
  padding: var(--e-1) var(--e-2);
  margin-bottom: var(--e-2);
  background: var(--superficie-2);
  border-radius: var(--r-sm);
  color: var(--texto-fraco);
  overflow-wrap: anywhere;
  cursor: pointer;
}
.balao--realcado { outline: 2px solid var(--acento); }
.citando {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  padding: var(--e-2);
  border-left: 3px solid var(--acento);
  background: var(--acento-suave);
  border-radius: var(--r-sm);
}
.citando__texto {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--txt-sm);
  color: var(--texto-fraco);
}

/* ---- imagem em tela cheia (29/09), mesmo padrão da Caixa de entrada ----- */
.balao__imagem--clicavel { cursor: zoom-in; }
.cheia {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  background: rgba(0, 0, 0, .85);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: zoom-out;
}
.cheia__img { max-width: 92vw; max-height: 92vh; object-fit: contain; }
.cheia__fechar {
  position: absolute;
  top: var(--e-4);
  right: var(--e-4);
  border: 0;
  background: rgba(255, 255, 255, .15);
  color: #fff;
  width: 40px;
  height: 40px;
  border-radius: var(--r-full);
  cursor: pointer;
}

/* ---- chamar alguém com @ (27/08) ----------------------------------------
   ⚠️ Duas intensidades, e a diferença é de significado, não de gosto: a
   menção a OUTRA pessoa é informação ("chamaram a Erika"); a menção a MIM é
   chamado ("preciso responder"). Se as duas tivessem o mesmo peso, a segunda
   se perderia no meio da primeira. */
.mencao {
  background: none;
  color: var(--acento);
  font-weight: var(--peso-medio);
  border-radius: var(--r-sm);
  padding: 0 2px;
}
.mencao--eu {
  background: var(--acento-suave);
  color: var(--acento-texto);
  font-weight: var(--peso-forte);
}

.campo--arroba { position: relative; }

/* A lista do `@` sobe acima do campo: abaixo ela sairia da tela, porque o
   compositor mora no rodapé. */
.arroba {
  position: absolute;
  bottom: calc(100% + var(--e-1));
  left: 0;
  z-index: var(--z-flutuante);
  min-width: 200px;
  max-height: 220px;
  overflow-y: auto;
  margin: 0;
  padding: var(--e-1);
  list-style: none;
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
  box-shadow: var(--sombra-2);
}
.arroba__item {
  display: block;
  width: 100%;
  min-height: var(--altura-toque);
  padding: 0 var(--e-3);
  border: 0;
  border-radius: var(--r-sm);
  background: none;
  color: var(--texto);
  font-family: inherit;
  font-size: var(--txt-md);
  text-align: left;
  cursor: pointer;
}
.arroba__item:hover,
.arroba__item--aqui { background: var(--acento-suave); color: var(--acento-texto); }

.chamados { flex-wrap: wrap; gap: var(--e-1); margin: 0; }
.chamados__chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px var(--e-2);
  border: var(--borda-fina) solid var(--acento-borda);
  border-radius: var(--r-full);
  background: var(--acento-suave);
  color: var(--acento-texto);
  font-family: inherit;
  font-size: var(--txt-sm);
  cursor: pointer;
}

.balao__autor { margin: 0 0 2px; color: var(--texto-fraco); font-weight: var(--peso-forte); }
.balao__texto { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }

/* ---- anexo (22/09) --------------------------------------------------------
   ⚠️ `max-width: 100%` e `height: auto` juntos: sem os dois, um print de
   3000 px de largura estoura o balão e empurra a conversa inteira para o
   lado. Os tokens são os mesmos do resto da tela -- token inventado cai no
   valor de emergência em silêncio, e isso já aconteceu aqui. */
.balao__imagem {
  display: block;
  max-width: 100%;
  height: auto;
  border-radius: var(--r-md);
  margin-bottom: var(--e-1);
}

.balao__audio { display: block; width: 100%; margin-bottom: var(--e-1); }

.balao__arquivo {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  padding: var(--e-2);
  margin-bottom: var(--e-1);
  border: var(--borda-fina);
  border-radius: var(--r-sm);
  text-decoration: none;
  color: inherit;
  /* O nome longo encolhe em vez de esticar o balão. */
  overflow-wrap: anywhere;
}

.anexo-escolhido { align-items: center; gap: var(--e-2); margin: 0 0 var(--e-2); }

.gravando { align-items: center; gap: var(--e-2); margin: 0 0 var(--e-2); }

/* O ponto vermelho é o que diz "está ligado" sem depender de ler o texto. */
.gravando__ponto {
  width: 10px;
  height: 10px;
  border-radius: var(--r-full);
  background: var(--erro);
}

.botao--ocupado { opacity: 0.6; pointer-events: none; }

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
