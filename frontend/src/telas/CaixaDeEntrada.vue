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
import { codigosPermitidos } from '../estado/sessao.js'
import { marcar, partir } from '../util/destaque.js'
import { corDaInicial, iniciais } from '../util/avatar.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'

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
// '' | 'transferir' | 'convidar' | 'encerrar' | 'vincular'
const painelAcao = ref('')
const timeEscolhido = ref('')
const motivo = ref('')
const classificacaoEscolhida = ref('')
const comentario = ref('')

const resposta = ref('')
const enviando = ref(false)

/* ---- responder citando (aprovado em 12/08, feito em 25/08) ---------------
   🚨 RECEBÍAMOS A CITAÇÃO E NÃO SABÍAMOS ENVIAR. O balão já desenha
   `citada_conteudo` desde sempre -- só o caminho de volta faltava. Citar é
   campo do `sendText` (`quoted`), não rota própria: foi por isso que não deu
   para provar sondando rotas. */
const citando = ref(null)

function citar(m) {
  citando.value = m
  /* Foco no campo: citar e não poder escrever em seguida obriga a um clique
     que não existe no WhatsApp. */
  nextTick(() => document.querySelector('.compositor textarea')?.focus())
}

/* ---- reagir com emoji ----------------------------------------------------
   ⚠️ Seis emojis, não a grade inteira: reação é resposta de UM clique. Quem
   quer escrever escreve. São os mesmos seis do WhatsApp, e por isso ninguém
   precisa aprender. */
const REACOES = ['👍', '❤️', '😂', '😮', '😢', '🙏']
const reagindoEm = ref(null)

/* 🚨 `m.reacoes` É LISTA DESDE 26/08, e não mais um emoji só. O cliente passou
   a reagir também, e 40% das reações são em GRUPO: com um campo só, o último
   que reagisse apagaria os outros em silêncio. Cada item é
   `{emoji, n, nosso}` — o `nosso` é o que deixa o botão aceso. */
function nossaReacao(m) {
  return (m.reacoes || []).find((r) => r.nosso)?.emoji || null
}

async function reagir(m, emoji) {
  reagindoEm.value = null
  /* Vira na tela antes da resposta: reação é clique de meio segundo. Se
     falhar, desfaz e diz. */
  const antes = m.reacoes ? [...m.reacoes] : []
  const atual = nossaReacao(m)
  const novo = atual === emoji ? '' : emoji

  /* O eco otimista mexe só NA NOSSA parte da lista: tirar a linha inteira
     apagaria da tela a reação de outra pessoa, que não mudou. */
  const outros = antes.map((r) => ({ ...r, n: r.nosso ? r.n - 1 : r.n }))
    .filter((r) => r.n > 0)
    .map((r) => ({ ...r, nosso: false }))
  if (novo) {
    const igual = outros.find((r) => r.emoji === novo)
    if (igual) { igual.n += 1; igual.nosso = true }
    else outros.push({ emoji: novo, n: 1, nosso: true })
  }
  m.reacoes = outros

  try {
    await api.post(`/api/conversas/${aberta.value.id}/reagir`, {
      mensagem_id: m.id,
      emoji: novo,
    })
  } catch (e) {
    m.reacoes = antes
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui reagir.'
  }
}

/* ---- mídia em tela cheia -------------------------------------------------
   🚨 A FOTO ABRIA DO TAMANHO DO BALÃO. Print de erro e foto de avaria são
   exatamente o que precisa de zoom, e eram justamente o que não dava para
   ver. */
const emTelaCheia = ref(null)

/* ---- gravar áudio --------------------------------------------------------
   🚨 `sendWhatsAppAudio`, não anexo: pela rota de voz a mensagem chega com
   onda e tocar-seguido; por `sendMedia`, chega como arquivo para baixar. */
const gravando = ref(false)
const segundosGravados = ref(0)
let gravador = null
let pedacos = []
let relogioGravacao = null

async function comecarGravacao() {
  try {
    const trilha = await navigator.mediaDevices.getUserMedia({ audio: true })
    pedacos = []
    gravador = new MediaRecorder(trilha)
    gravador.ondataavailable = (e) => { if (e.data.size) pedacos.push(e.data) }
    gravador.onstop = () => {
      /* ⚠️ Solta o microfone SEMPRE. Sem isto o navegador fica com a luz de
         gravação acesa depois de enviar, e a pessoa acha que o painel está
         ouvindo. */
      trilha.getTracks().forEach((t) => t.stop())
    }
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
  pedacos = []
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

  const blob = new Blob(pedacos, { type: 'audio/ogg; codecs=opus' })
  gravador = null
  pedacos = []
  if (!blob.size) return

  enviando.value = true
  try {
    const dados = new FormData()
    dados.append('arquivo', blob, 'audio.ogg')
    const r = await fetch(`/api/conversas/${aberta.value.id}/audio`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${localStorage.getItem('movizap.token')}` },
      body: dados,
    })
    if (!r.ok) throw new Error((await r.json()).detail || 'falhou')
    await Promise.all([abrir(aberta.value.id), carregar({ silencioso: true })])
  } catch (e) {
    erro.value = e.message || 'Não consegui enviar o áudio.'
  } finally {
    enviando.value = false
  }
}

/* ---- o TIPO da pessoa, na própria ficha -----------------------------------
   🚨 A FAIXA MOSTRAVA A EMPRESA E NÃO MOSTRAVA O TIPO. Apontado por ele em
   26/08. Até 25/08 o tipo era só uma etiqueta de cadastro e a falta passava;
   desde então ele decide se a **saudação automática** dispara, e desde 26/08
   se a **IA** atende — quem está falando com a pessoa é quem sabe o que ela
   é, e mandá-lo a outra tela para marcar isso é o caminho que ninguém faz.

   ⚠️ A LISTA É CÓPIA DO CHECK DO BANCO (`contato_relacao_check`, migração
   031), igual à da tela de Contatos. Divergir aqui daria 400 na cara do
   atendente com o valor que a própria tela ofereceu.

   ⚠️ QUEM NÃO TEM `CAD_1.2` VÊ, MAS NÃO TROCA. A rota exige essa permissão, e
   oferecer um seletor que responde 403 é pior que mostrar o valor: o
   frontend desenha, não decide. */
const RELACOES = [
  ['cliente', 'Cliente'], ['fornecedor', 'Fornecedor'], ['parceiro', 'Parceiro'],
  ['tecnico', 'Técnico'], ['lead', 'Lead'], ['colaborador', 'Colaborador'],
  ['teste', 'Teste'], ['sem_identificacao', 'Sem identificação'],
]
const NOME_RELACAO = Object.fromEntries(RELACOES)

/* ⚠️ `sem_identificacao` fica de fora da ESCOLHA (28/08): ele é o valor de
   nascimento do contato (migração 031), não uma marcação de ninguém. Continua
   em `RELACOES` porque é valor válido do banco e precisa ter nome legível. */
const RELACOES_ESCOLHIVEIS = RELACOES.filter(([v]) => v !== 'sem_identificacao')

const podeTrocarTipo = computed(() => codigosPermitidos.value.has('CAD_1.2'))

/* 🚨 MARCAR O TIPO DE DENTRO DA CONVERSA É ATD_1.2, NÃO CAD_1.2. O perfil
   `atendimento` não tem CAD_1.2 desde 10/08 -- exigir a permissão do cadastro
   esconderia o seletor justamente de quem está falando com a pessoa. A rota
   nova checa ATD_1.2, e a tela segue a rota. */
const podeMarcarTipo = computed(() => codigosPermitidos.value.has('ATD_1.2'))
const tipoSalvo = ref(false)

/* 🚨 O TIPO NÃO DEPENDE MAIS DE EMPRESA VINCULADA (28/08). Pedido dele:
   *"o tipo… não precisa depender de empresa vinculada para ter o campo"*.

   Antes esta função desistia sem `empresa.contato`, e a ficha só mostrava o
   chip "Sem cadastro" -- em 61% das conversas. O tipo mora em `contato`, então
   escolher CRIA o contato (sem empresa, `origem='movizap'`), pela rota
   `PUT /api/conversas/{id}/tipo`.

   ⚠️ RELÊ DO SERVIDOR EM VEZ DE REMENDAR A TELA. Criar contato muda `empresa`,
   `candidatos`, `bitrix` e o rótulo do botão da ficha de uma vez -- remendar
   quatro campos à mão é onde a tela começa a divergir do banco. Mesma decisão
   do `vincularA`. */
const tipoSemCadastro = ref('')

async function trocarTipo(nova) {
  const contato = aberta.value?.empresa?.contato
  if (!nova || (contato && nova === contato.relacao)) return
  tipoSalvo.value = false
  const antes = contato ? contato.relacao : null
  if (contato) contato.relacao = nova
  try {
    const r = await api.put(`/api/conversas/${aberta.value.id}/tipo`,
                            { relacao: nova })
    tipoSalvo.value = true
    /* 🚨 A AUTOMAÇÃO MUDA NA HORA, e a tela avisa em vez de deixar descobrir
       pelo comportamento: sem cadastro a pessoa seguia a linha `sem_cadastro`
       da CFG_5.1; com o tipo marcado ela passa a seguir a do tipo. */
    if (r.criou_contato) {
      recado.value = `Cadastro criado e marcado como ${NOME_RELACAO[nova] || nova}. `
        + 'A automação por tipo passa a valer para esta pessoa.'
      tipoSemCadastro.value = ''
      await abrir(aberta.value.id)
      await carregar({ silencioso: true })
    }
  } catch (e) {
    if (contato) contato.relacao = antes
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui marcar o tipo.'
  }
}

/* ---- encaminhar ----------------------------------------------------------
   Entrou em 25/08, quando a regra de "não é caixa de disparo" caiu. Cinco
   destinos por vez, que é o limite do próprio WhatsApp. */
const encaminhando = ref(null)
const destinosEscolhidos = ref([])

function abrirEncaminhar(m) {
  encaminhando.value = m
  destinosEscolhidos.value = []
}

async function confirmarEncaminhar() {
  if (!destinosEscolhidos.value.length) return
  try {
    const r = await api.post('/api/conversas/encaminhar', {
      mensagem_id: encaminhando.value.id,
      conversas: destinosEscolhidos.value,
    })
    /* 🚨 A FALHA DIZ O MOTIVO, não só o número. "1 não deu" manda o atendente
       adivinhar; com arquivo, o motivo costuma ser o teto de 25 MB, e é isso
       que ele precisa ler para saber que não foi o número que está errado. */
    recado.value = r.falhas.length
      ? `Encaminhada para ${r.enviadas}; ${r.falhas.length} não deu — `
        + r.falhas.map((f) => f.motivo).filter(Boolean).join(' · ')
      : `Encaminhada para ${r.enviadas} conversa(s).`
    encaminhando.value = null
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui encaminhar.'
  }
}

/* ---- buscar DENTRO da conversa (ATD_1.2) --------------------------------
   Pergunta diferente da busca da lista: lá é "com quem eu falei", aqui é
   "onde ele disse isso". Por isso são dois campos e não um.

   🚨 SUBIU PARA O SERVIDOR EM 25/08, junto com a paginação. Ela rodava aqui
   no navegador, sobre `aberta.mensagens` -- e isso estava CERTO enquanto a
   conversa inteira vinha de uma vez. No momento em que a tela passou a abrir
   com 60 mensagens, a mesma busca passaria a responder "nada com esse termo"
   sobre mensagem que existe três telas acima. É por isso que paginar e mover
   a busca são um item só.

   ⚠️ O servidor devolve as POSIÇÕES (ids). Se o acerto está fora da janela
   carregada, a tela carrega para trás até alcançá-lo -- ver `irParaAchado`. */
const buscaNaConversa = ref('')
const achadoAtual = ref(0)
const achadosNaConversa = ref([])

/* A busca abre por botão (27/08): ela é ação eventual e ocupava uma faixa fixa
   na altura mais disputada da tela. */
const buscaAberta = ref(false)
const campoBuscaConversa = ref(null)

function alternarBusca() {
  if (buscaAberta.value) { fecharBusca(); return }
  buscaAberta.value = true
  // Abrir e ter de clicar no campo seria um clique a mais para nada.
  nextTick(() => campoBuscaConversa.value && campoBuscaConversa.value.focus())
}

/* ⚠️ FECHAR LIMPA O TERMO, e isso não é zelo: com o termo guardado, os balões
   continuariam marcados e o contador sumiria junto com o campo — um filtro
   ativo sem nada na tela dizendo que existe. */
function fecharBusca() {
  buscaAberta.value = false
  buscaNaConversa.value = ''
  achadosNaConversa.value = []
  achadoAtual.value = 0
}
const buscandoNaConversa = ref(false)
/* ⚠️ O servidor devolve no máximo 200 acertos. Termo largo numa conversa
   longa encosta nisso, e encostar calado é a mentira por omissão que o teto
   de 1.000 mensagens fazia. */
const achadosLimitados = ref(false)

const idAchado = computed(() => achadosNaConversa.value[achadoAtual.value] ?? null)

function casaNaConversa(m) {
  return achadosNaConversa.value.includes(m.id)
}

async function buscarNaConversa() {
  const alvo = buscaNaConversa.value.trim()
  achadoAtual.value = 0
  if (!alvo || !aberta.value) {
    achadosNaConversa.value = []
    achadosLimitados.value = false
    return
  }
  buscandoNaConversa.value = true
  try {
    const r = await api.get(
      `/api/conversas/${aberta.value.id}/buscar?termo=${encodeURIComponent(alvo)}`)
    achadosNaConversa.value = (r.achados || []).map((a) => a.id)
    achadosLimitados.value = Boolean(r.limitado)
    if (achadosNaConversa.value.length) await irParaAchado(0)
  } catch {
    achadosNaConversa.value = []
  } finally {
    buscandoNaConversa.value = false
  }
}

async function irParaAchado(passo) {
  const total = achadosNaConversa.value.length
  if (!total) return
  // Dá a volta nas duas direções: no último, "próximo" volta ao primeiro.
  achadoAtual.value = (achadoAtual.value + passo + total) % total
  await rolarAteAchado()
}

async function rolarAteAchado() {
  await nextTick()
  const alvo = idAchado.value
  if (!alvo || !baloes.value) return

  /* 🚨 O ACERTO PODE ESTAR ACIMA DO QUE ESTÁ CARREGADO. Sem isto, a busca
     acharia (o servidor vê a conversa inteira) e a tela não teria para onde
     rolar -- o contador diria "3/7" e nada se mexeria, que é pior do que não
     achar. Carrega para trás até o balão existir, com um limite de voltas
     para nunca virar laço infinito numa conversa gigante. */
  let voltas = 0
  while (!baloes.value.querySelector(`[data-mensagem="${alvo}"]`)
         && aberta.value?.tem_anteriores && voltas < 25) {
    await carregarAnteriores()
    await nextTick()
    voltas += 1
  }

  const el = baloes.value.querySelector(`[data-mensagem="${alvo}"]`)
  if (el) el.scrollIntoView({ block: 'center', behavior: 'smooth' })
}

/* ⚠️ Espera a digitação parar: uma rota por tecla faria uma consulta ao banco
   a cada letra. 300 ms é o intervalo em que a pessoa ainda não percebeu que
   esperou. */
let debounceBuscaConversa = null
watch(buscaNaConversa, () => {
  clearTimeout(debounceBuscaConversa)
  debounceBuscaConversa = setTimeout(buscarNaConversa, 300)
})

/* ---- carregar mensagens anteriores --------------------------------------
   🚨 A tela abre com 60 e sobe de 200 em 200 (decisão do usuário, 25/08). O
   teto de 1.000 saiu: a maior conversa da base já tinha 776, e teto que se
   encosta silencia mensagem antiga. */
const carregandoAnteriores = ref(false)

async function carregarAnteriores() {
  if (!aberta.value || carregandoAnteriores.value) return
  if (!aberta.value.mensagens.length) return
  carregandoAnteriores.value = true
  const topo = aberta.value.mensagens[0].id
  /* ⚠️ Guarda a altura ANTES de prepender: sem isto a lista salta e a pessoa
     perde o lugar onde estava lendo -- o conteúdo novo entra por cima e
     empurra tudo para baixo. */
  const alturaAntes = baloes.value ? baloes.value.scrollHeight : 0
  try {
    const r = await api.get(
      `/api/conversas/${aberta.value.id}/mensagens?antes_de=${topo}`)
    aberta.value.mensagens = [...(r.mensagens || []), ...aberta.value.mensagens]
    aberta.value.tem_anteriores = Boolean(r.tem_anteriores)
    await nextTick()
    if (baloes.value) {
      baloes.value.scrollTop = baloes.value.scrollHeight - alturaAntes
    }
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui carregar.'
  } finally {
    carregandoAnteriores.value = false
  }
}

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
  /* ⚠️ O termo do vínculo entra aqui pela mesma razão dos outros (28/08):
     quem procura "Velasco", desiste e abre o vínculo de OUTRA conversa
     encontraria a lista da anterior já montada -- e um clique ali vincularia
     a empresa certa ao telefone errado. */
  buscaCliente.value = ''
  achadosCliente.value = []
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

/* ---- filtro por tipo de cadastro (pedido do usuário em 25/08) -----------
   🚨 "SEM CADASTRO" E "SEM IDENTIFICAÇÃO" SÃO COISAS DIFERENTES, e a ordem
   aqui reflete isso: `sem_cadastro` é a conversa que não tem contato nenhum
   na base (211 de 332, 64%); `sem_identificacao` é o flag da ficha de um
   contato que existe. Os dois ficam lado a lado de propósito -- juntá-los
   esconderia o caso majoritário. */
const TIPOS = [
  { valor: 'sem_cadastro', rotulo: 'Sem cadastro' },
  { valor: 'cliente', rotulo: 'Cliente' },
  { valor: 'fornecedor', rotulo: 'Fornecedor' },
  { valor: 'tecnico', rotulo: 'Técnico' },
  { valor: 'teste', rotulo: 'Teste' },
  { valor: 'sem_identificacao', rotulo: 'Sem identificação' },
]
const tiposMarcados = ref([])
const filtroAberto = ref(false)

/* ⚠️ FECHA AO CLICAR FORA. Popover que só fecha no próprio botão fica aberto
   por cima da lista enquanto a pessoa tenta clicar numa conversa -- e ela
   clica duas vezes achando que a tela travou. */
function fecharFiltroSeForaDele(evento) {
  if (!filtroAberto.value) return
  if (!evento.target.closest('.filtro')) filtroAberto.value = false
}

function alternarTipo(valor) {
  tiposMarcados.value = tiposMarcados.value.includes(valor)
    ? tiposMarcados.value.filter((t) => t !== valor)
    : [...tiposMarcados.value, valor]
  carregar()
}

function parametros() {
  const p = new URLSearchParams()
  if (filtro.value === 'sem_dono') p.set('sem_dono', 'true')
  if (filtro.value === 'minhas') p.set('minhas', 'true')
  if (busca.value.trim()) p.set('busca', busca.value.trim())
  if (tiposMarcados.value.length) p.set('relacoes', tiposMarcados.value.join(','))
  return p.toString()
}

/* ---- o botão `+`: falar primeiro com quem ainda não escreveu ------------
   🚨 Até 25/08 não havia caminho de saída: conversa só nascia quando CHEGAVA
   mensagem. Este painel é o único lugar do painel onde se escolhe para quem
   mandar. */
const novaAberta = ref(false)
const novoNumero = ref('')
const novoTexto = ref('')
const enviandoNova = ref(false)
const erroNova = ref('')
const semWhatsapp = ref(false)

function abrirNova() {
  novaAberta.value = true
  novoNumero.value = ''
  novoTexto.value = ''
  erroNova.value = ''
  semWhatsapp.value = false
}

async function enviarNova() {
  enviandoNova.value = true
  erroNova.value = ''
  semWhatsapp.value = false
  try {
    const r = await api.post('/api/conversas/nova', {
      numero: novoNumero.value,
      texto: novoTexto.value,
    })
    novaAberta.value = false
    /* O recado diz o que aconteceu com a IDENTIFICAÇÃO, porque é o que
       diferencia este caminho: mandar para número desconhecido é normal. */
    recado.value = r.identificada
      ? `Enviado. Já vinculei a ${r.cliente_nome || r.contato_nome}.`
      : (r.nasceu
          ? 'Enviado. Este número não está no cadastro — dá para vincular pela ficha.'
          : 'Enviado na conversa que já estava aberta com este número.')
    await carregar()
    await abrir(r.conversa_id)
  } catch (e) {
    /* O backend devolve o corpo inteiro no 409: `sem_whatsapp` distingue "o
       número não existe no WhatsApp" de "falhou por outro motivo", e as duas
       pedem reação diferente de quem está na tela. */
    const detalhe = e instanceof ErroDeApi ? e.detalhe : null
    semWhatsapp.value = Boolean(detalhe && detalhe.sem_whatsapp)
    erroNova.value = (detalhe && detalhe.motivo)
      || (e instanceof ErroDeApi ? e.message : 'Não consegui enviar.')
  } finally {
    enviandoNova.value = false
  }
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
    // 🚨 PELA MESMA RAZÃO, A MENÇÃO NÃO ATRAVESSA A TROCA. Um chamado montado
    // no grupo A seguiria para o grupo B — e lá o JID nem existe. A lista de
    // quem dá para chamar também é da conversa, e é remontada sob demanda.
    mencionados.value = []
    listaArroba.value = []
    chamaveis.value = []
    chamaveisDaConversa = null
    // A busca é DESTA conversa: carregá-la em outra mostraria contador e
    // marcações de um termo que ninguém procurou aqui.
    // ⚠️ E o CAMPO fecha junto (27/08): deixá-lo aberto na conversa nova
    // devolveria a faixa de altura que o botão existe para não gastar.
    fecharBusca()
    /* ⚠️ A citação é DESTA conversa. Sem limpar, a barra continuava apontando
       para uma mensagem da conversa anterior: o backend recusa ("só dá para
       citar mensagem desta conversa"), mas a tela mentia até a pessoa
       tentar. */
    citando.value = null
    // ⚠️ Os ACHADOS também. Antes de 25/08 eles eram `computed` e sumiam
    // sozinhos com o termo; agora são estado, e estado não se limpa sozinho --
    // sobrariam marcações de balão de outra conversa.
    achadosNaConversa.value = []
    achadosLimitados.value = false
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
    /* ⚠️ Só vai quem AINDA está escrito: apagar o "@Fulano" à mão tem de
       desfazer a menção, senão a pessoa é chamada sem aparecer nada.
       ⚠️ Nota interna não chama ninguém: ela nunca vai ao WhatsApp. */
    const vivos = interna ? []
      : mencionados.value.filter((p) => texto.includes('@' + p.nome))
    await api.post(`/api/conversas/${aberta.value.id}/${caminho}`, {
      texto,
      /* ⚠️ Nota interna não cita: ela nunca foi ao WhatsApp, e o backend
         recusaria a chave. */
      citando_id: interna ? null : (citando.value?.id ?? null),
      mencionados: vivos.map((p) => p.jid),
    })
    resposta.value = ''
    citando.value = null
    mencionados.value = []
    listaArroba.value = []
    // 🚨 Recarrega a conversa em vez de empurrar o balão na mão: o que vale é
    // o que o banco gravou, não o que a tela supõe ter acontecido.
    await Promise.all([abrir(aberta.value.id), carregar({ silencioso: true })])
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui enviar.'
  } finally {
    enviando.value = false
  }
}

/* ---- chamar alguém com @, só em grupo (27/08) ----------------------------
   Pedido do usuário: *"interessante e pode ser, tanto no interno quanto no do
   whatsa"*.

   🚨 SÓ EM GRUPO, e não é escolha de tela: fora dele o WhatsApp IGNORA
   `mentioned`. Oferecer o `@` numa conversa direta seria prometer o que o
   outro lado não faz — o backend também não repassa.

   🚨 A LISTA VEM DO EVOLUTION, ao vivo, e é pedida quando alguém digita `@` —
   nunca por mensagem. É a única fonte que liga o `@lid` do participante a um
   telefone: desde que o WhatsApp passou a usar LID nos grupos, TODOS os
   remetentes que gravamos estão nesse formato. */
const campoResposta = ref(null)
const mencionados = ref([])
const listaArroba = ref([])
const arrobaEscolhido = ref(0)
const chamaveis = ref([])
let chamaveisDaConversa = null   // de qual conversa a lista carregada é
let inicioDaArroba = -1

async function carregarChamaveis() {
  const id = aberta.value?.id
  if (!id || !ehGrupo.value) { chamaveis.value = []; return }
  if (chamaveisDaConversa === id) return
  try {
    const r = await api.get(`/api/conversas/${id}/quem-chamar`)
    chamaveis.value = r.participantes || []
    chamaveisDaConversa = id
  } catch {
    // Não pode derrubar a conversa: sem a lista, escreve-se normalmente.
    chamaveis.value = []
  }
}

async function olharArroba(evento) {
  if (!ehGrupo.value) { listaArroba.value = []; return }
  const campo = evento.target
  const ate = campo.value.slice(0, campo.selectionStart)
  const at = ate.lastIndexOf('@')
  // ⚠️ `@` colado em palavra não abre a lista: "email@movisat" não é menção.
  const antes = at > 0 ? ate[at - 1] : ' '
  if (at === -1 || !/\s/.test(antes)) { listaArroba.value = []; return }
  const termo = ate.slice(at + 1)
  if (/\s{2,}|\n/.test(termo)) { listaArroba.value = []; return }

  await carregarChamaveis()
  inicioDaArroba = at
  const busca = termo.trim().toLowerCase()
  listaArroba.value = chamaveis.value
    .filter((p) => !mencionados.value.some((m) => m.jid === p.jid))
    .filter((p) => !busca || (p.nome || '').toLowerCase().includes(busca))
    .slice(0, 8)
  arrobaEscolhido.value = 0
}

/* ⚠️ Só rouba as setas quando a lista está aberta. Sem isto, subir e descer no
   texto deixaria de funcionar em toda conversa de grupo. */
function andarNaLista(passo, evento) {
  if (!listaArroba.value.length) return
  evento.preventDefault()
  const n = listaArroba.value.length
  arrobaEscolhido.value = (arrobaEscolhido.value + passo + n) % n
}

/* Enter escolhe da lista quando ela está aberta. Fora disso NÃO envia: aqui a
   mensagem vai para o cliente e não volta, e o envio é `Ctrl+Enter` desde
   sempre — a fricção se paga. */
function enterNoCompositor(evento) {
  if (!listaArroba.value.length) return
  evento.preventDefault()
  escolherArroba(listaArroba.value[arrobaEscolhido.value])
}

function escolherArroba(pessoa) {
  if (!pessoa) return
  const campo = campoResposta.value
  const fim = campo ? campo.selectionStart : resposta.value.length
  if (inicioDaArroba >= 0) {
    resposta.value = resposta.value.slice(0, inicioDaArroba)
      + '@' + pessoa.nome + ' ' + resposta.value.slice(fim)
  }
  if (!mencionados.value.some((m) => m.jid === pessoa.jid)) {
    mencionados.value.push(pessoa)
  }
  listaArroba.value = []
  inicioDaArroba = -1
  nextTick(() => campo && campo.focus())
}

function tirarMencionado(jid) {
  mencionados.value = mencionados.value.filter((m) => m.jid !== jid)
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

/* ---- colar print (Ctrl+V) ------------------------------------------------
   🚨 O CAMINHO MAIS CURTO PARA MANDAR UM PRINT. Sem isto, quem tira print
   precisa salvar em arquivo, achar a pasta e anexar -- três passos para o que
   o WhatsApp resolve com um. */
function colar(evento) {
  const itens = Array.from(evento.clipboardData?.items || [])
  const imagem = itens.find((i) => i.type.startsWith('image/'))
  if (!imagem) return          // colar texto continua sendo colar texto
  const arq = imagem.getAsFile()
  if (!arq) return
  evento.preventDefault()
  /* Nome com hora: "image.png" três vezes na conversa não distingue nada. */
  const carimbo = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
  arquivo.value = new File([arq], `print-${carimbo}.png`, { type: arq.type })
}

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

/* CONCLUIR ATENDIMENTO — era "Encerrar" até 25/08.
   ⚠️ A rota continua `/encerrar`: rótulo é da tela, e trocar o caminho
   derrubaria quem estivesse com o painel aberto no meio do deploy. */
async function encerrar() {
  try {
    const r = await api.post(`/api/conversas/${aberta.value.id}/encerrar`, {
      // 🚨 `Number('')` é 0, e 0 não é "sem classificação" -- é um id que
      // não existe. Classificar virou opcional em 11/08, então o que vai é
      // null quando ninguém escolheu.
      classificacao_id: classificacaoEscolhida.value
        ? Number(classificacaoEscolhida.value)
        : null,
      comentario: comentario.value || null,
    })
    // O recado diz o que MUDOU, não que "deu certo": a conversa saiu da sua
    // lista e voltou para "sem dono", e isso surpreende quem não esperava.
    recado.value = r.participantes_saidos
      ? `Atendimento concluído. A conversa voltou para "sem dono" e saiu da `
        + `lista de ${r.participantes_saidos} pessoa(s) que acompanhavam.`
      : 'Atendimento concluído. A conversa voltou para "sem dono" e está no Histórico.'
    painelAcao.value = ''
    classificacaoEscolhida.value = ''
    comentario.value = ''
    await Promise.all([abrir(aberta.value.id), carregar({ silencioso: true })])
  } catch (e) {
    erro.value = e instanceof ErroDeApi
      ? e.message
      : 'Não consegui concluir o atendimento.'
  }
}

/* 🚨 ATALHOS (28/08). O E-mail tinha 6 teclas e as ensinava no ícone de
   ajuda; esta tela, que é a mais usada, tinha ZERO.

   ⚠️ NUNCA DENTRO DE CAMPO DE TEXTO — mesma guarda do E-mail. Sem ela,
   escrever "javali" para o cliente pularia de conversa no meio da palavra.
   `Ctrl`/`Cmd`/`Alt` também saem: são atalhos do navegador.

   ⚠️ Nenhuma tecla DESTRÓI. `c` abre o modal de concluir, não conclui — a
   confirmação continua sendo o que decide. */

/* 🚨 OS ATALHOS SÓ EXISTEM SE A PESSOA OS LIGOU (28/08). Ele pediu a tela de
   Configurações com o interruptor DESLIGADO -- e desligado é o padrão do
   banco, não uma opção que eu escolhi aqui.

   ⚠️ Começa FALSO e só vira verdadeiro quando `/api/eu/atalhos` responder:
   entre montar a tela e a resposta chegar, nenhuma tecla age. Se a chamada
   falhar, continua falso -- o lado seguro é o teclado inerte. */
const atalhosLigados = ref(false)
const atalhosTeclas = ref({})

function tecla(acao) {
  return atalhosTeclas.value[acao]
}

async function carregarAtalhos() {
  try {
    const r = await api.get('/api/eu/atalhos')
    atalhosTeclas.value = r.teclas || {}
    atalhosLigados.value = Boolean(r.ligados)
  } catch {
    atalhosLigados.value = false
  }
}

function atalho(evento) {
  const alvo = evento.target
  const digitando = alvo?.isContentEditable
    || ['INPUT', 'TEXTAREA', 'SELECT'].includes(alvo?.tagName)
  if (!atalhosLigados.value) return
  if (digitando || evento.ctrlKey || evento.metaKey || evento.altKey) return
  if (painelAcao.value || confirmacao.value || novaAberta.value) return

  if (evento.key === tecla('buscar')) {
    evento.preventDefault()
    document.querySelector('.campo--busca input')?.focus()
    return
  }
  if (evento.key === tecla('proxima') || evento.key === tecla('anterior')) {
    evento.preventDefault()
    const ordem = lista.value
    const atual = ordem.findIndex((c) => aberta.value && c.id === aberta.value.id)
    const passo = evento.key === tecla('proxima') ? 1 : -1
    const proximo = ordem[Math.min(Math.max(atual + passo, 0), ordem.length - 1)]
    if (proximo && (!aberta.value || proximo.id !== aberta.value.id)) abrir(proximo.id)
    return
  }
  if (!aberta.value) return
  if (evento.key === tecla('assumir') && (!aberta.value.atendente_id
      || aberta.value.estado === 'resolvida')) {
    evento.preventDefault()
    pedirParaAssumir()
  }
  if (evento.key === tecla('concluir') && aberta.value.estado !== 'resolvida') {
    evento.preventDefault()
    abrirPainel('encerrar')
  }
}

onMounted(async () => {
  document.addEventListener('keydown', atalho)
  document.addEventListener('click', fecharFiltroSeForaDele)
  /* 🚨 O FILTRO VEM DA URL QUANDO A TELA INICIAL MANDA. Os cartões da INI_1.1
     apontam para `/atendimento?minhas=1` e `?sem_dono=1`: sem ler a query, o
     clique cairia na lista inteira e o número da tela inicial não bateria com
     o que aparece aqui -- que é a forma mais rápida de a pessoa parar de
     confiar nos dois. */
  if (route.query.minhas) filtro.value = 'minhas'
  else if (route.query.sem_dono) filtro.value = 'sem_dono'

  /* 🚨 VEM DA FICHA DO CLIENTE. O botão "Conversar" da CAD_1.1 manda o número
     para cá: se já existe conversa aberta com ele, abre; senão, abre o painel
     do `+` já preenchido. Sem isto, o botão levaria à caixa de entrada
     genérica e a pessoa teria de procurar o número que acabou de clicar. */
  const numeroPedido = route.query.numero
  if (numeroPedido) {
    busca.value = String(numeroPedido)
  }
  carregarAtalhos()
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
  else if (numeroPedido) {
    /* A busca já rodou com o número: se achou exatamente uma, abre; se não
       achou nenhuma, oferece começar a conversa com ele. */
    if (lista.value.length === 1) await abrir(lista.value[0].id)
    else if (!lista.value.length) {
      abrirNova()
      novoNumero.value = String(numeroPedido)
    }
  }
  // A fila é consumida a cada 5s no servidor; a tela reflete isso sem F5.
  timer = setInterval(() => carregar({ silencioso: true }), 8000)
})

onUnmounted(() => {
  clearInterval(timer)
  document.removeEventListener('keydown', atalho)
  document.removeEventListener('click', fecharFiltroSeForaDele)
  /* 🚨 O MICROFONE TEM DE SER SOLTO AO SAIR (achado na auditoria de 25/08).
     Eu tratei disso no `onstop` do gravador e esqueci a saída pela porta:
     trocar de tela no meio de uma gravação deixava a trilha aberta e a luz
     vermelha do navegador acesa, com a pessoa achando que o painel continua
     ouvindo. É pior que o defeito original, porque não há nem o botão de
     cancelar à vista. */
  cancelarGravacao()
})

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

/* ---- separador de dia ---------------------------------------------------
   🚨 SEM ISTO O FIO É UM BLOCO SÓ. Uma conversa de meses desenhava mensagem
   atrás de mensagem sem nenhuma marca de tempo além da hora -- e "14:32" não
   diz se foi hoje ou em julho. É a primeira coisa que falta quando se compara
   com o WhatsApp lado a lado. */
function _diaDe(iso) {
  return iso ? new Date(iso).toDateString() : ''
}

function comecaODia(m, i) {
  if (!aberta.value) return false
  if (i === 0) return true
  return _diaDe(m.criada_em) !== _diaDe(aberta.value.mensagens[i - 1].criada_em)
}

function rotuloDoDia(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const hoje = new Date()
  const ontem = new Date()
  ontem.setDate(hoje.getDate() - 1)
  if (d.toDateString() === hoje.toDateString()) return 'Hoje'
  if (d.toDateString() === ontem.toDateString()) return 'Ontem'
  /* Menos de um ano: dia e mês bastam. Mais que isso, o ano importa. */
  const mesmoAno = d.getFullYear() === hoje.getFullYear()
  return d.toLocaleDateString('pt-BR', mesmoAno
    ? { day: '2-digit', month: 'long' }
    : { day: '2-digit', month: 'long', year: 'numeric' })
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

/* O estado de entrega, no símbolo que quem atende já lê sem pensar (27/08).
   🚨 SÓ OS ESTADOS QUE TÊM TIQUE. `pendente` e `falhou` continuam saindo por
   extenso: um relógio e um "x" pequenininho no canto seriam justamente os dois
   casos em que a pessoa PRECISA parar e ler. */
const TIQUE = { enviada: '✓', entregue: '✓✓', lida: '✓✓' }

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
    /* 🚨 O MODAL FECHA NO SUCESSO, NÃO NO CLIQUE (28/08). Fechar antes da
       resposta deixaria a falha sem lugar para aparecer: o `erro` do catch
       renderiza na tela de trás, e quem clicou já teria perdido a lista de
       onde escolher de novo. */
    await api.post(`/api/conversas/${aberta.value.id}/vincular`, { cliente_id: clienteId })
    painelAcao.value = ''
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
  <div class="tela tela--conversa">
    <!-- 🚨 O CABEÇALHO DE PÁGINA SAIU EM 27/08. Ele comia uma faixa da altura
         para repetir o nome da tela que o menu já diz, e era o que mais
         afastava a tela do desenho escolhido. O título e os dois números
         passaram para o topo da coluna da lista, onde ficam ao lado do que
         contam.

         ⚠️ OS DOIS NÚMEROS FICARAM. Eles são a decisão de 25/08 -- quantas
         esperam e quantas não têm dono é o que decide trabalho. -->

    <p v-if="filaParada" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>
        <strong>{{ resumo.eventos_pendentes }} eventos esperando processamento.</strong>
        A fila pode ter parado.
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
        <header class="cartao__cabecalho lista__topo">
          <!-- O título e os dois números, que antes ficavam numa faixa acima
               da tela inteira. Aqui eles ficam ao lado do que contam. -->
          <div class="lista__titulo">
            <h1>Caixa de entrada</h1>
            <AjudaDaTela titulo="O que esta tela faz e o que a busca alcança">
              As conversas do WhatsApp, suas e da fila. A busca procura no nome
              do WhatsApp, no cadastro, no telefone (pedaço serve:
              <code>6168</code>) e no texto das mensagens, inclusive das notas
              internas.
              <br /><br />
              <strong>Atalhos:</strong>
              <code>j</code> e <code>k</code> passam de conversa ·
              <code>/</code> vai para a busca ·
              <code>a</code> assume ·
              <code>c</code> abre o concluir.
            </AjudaDaTela>
            <div v-if="resumo" class="lista__placar">
              <span>{{ resumo.conversas }} abertas</span>
              <span v-if="resumo.sem_dono" class="lista__pede">
                · {{ resumo.sem_dono }} sem dono
              </span>
            </div>
          </div>

          <div class="linha linha--quebra">
            <!-- ⚠️ CONTROLE SEGMENTADO, não três botões soltos. Três botões
                 com cores diferentes leem como três ações; segmentado lê como
                 UMA escolha entre três -- que é o que é. -->
            <div class="abas" role="tablist">
              <button
                v-for="f in FILTROS"
                :key="f.valor"
                class="abas__aba"
                :class="{ 'abas__aba--ativa': filtro === f.valor }"
                type="button"
                role="tab"
                :aria-selected="filtro === f.valor"
                @click="filtro = f.valor"
              >
                {{ f.rotulo }}
              </button>
            </div>

            <!-- 🚨 O `+` FICA LOGO DEPOIS DE "MINHAS", como o usuário pediu
                 em 25/08. É o único lugar do painel onde se escolhe para quem
                 mandar: em todo o resto o destino sai da conversa. -->
            <button
              class="botao botao--pequeno botao--primario botao--icone"
              type="button"
              title="Nova mensagem para um número"
              aria-label="Nova mensagem para um número"
              @click="abrirNova"
            >
              <i class="bi bi-plus-lg" aria-hidden="true"></i>
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
              <!-- 🚨 O FILTRO MORA NO CAMPO DE BUSCA, não numa fileira de
                   chips acima da lista. Buscar e filtrar são a MESMA
                   pergunta ("quais conversas eu quero ver"), e separá-los em
                   dois lugares fazia a coluna virar uma parede de botões
                   antes de qualquer conversa aparecer. -->
              <div class="filtro">
                <button
                  class="botao botao--contorno botao--icone"
                  type="button"
                  :class="{ 'botao--filtrando': tiposMarcados.length }"
                  :aria-expanded="filtroAberto"
                  title="Filtrar por tipo de cadastro"
                  aria-label="Filtrar por tipo de cadastro"
                  @click.prevent="filtroAberto = !filtroAberto"
                >
                  <i class="bi bi-funnel" aria-hidden="true"></i>
                  <span v-if="tiposMarcados.length" class="filtro__conta">
                    {{ tiposMarcados.length }}
                  </span>
                </button>

                <div v-if="filtroAberto" class="filtro__caixa">
                  <p class="filtro__titulo">Tipo de cadastro</p>
                  <label v-for="t in TIPOS" :key="t.valor" class="filtro__linha">
                    <input
                      type="checkbox"
                      :checked="tiposMarcados.includes(t.valor)"
                      @change="alternarTipo(t.valor)"
                    />
                    <span>{{ t.rotulo }}</span>
                  </label>
                  <button
                    v-if="tiposMarcados.length"
                    class="botao botao--pequeno botao--fantasma filtro__limpar"
                    type="button"
                    @click.prevent="tiposMarcados = []; carregar()"
                  >
                    limpar filtro
                  </button>
                </div>
              </div>

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

            <!-- O que está filtrado aparece EMBAIXO do campo, em texto: o
                 ícone diz que há filtro, esta linha diz qual. -->
            <span v-if="tiposMarcados.length" class="filtro__resumo pequeno">
              <i class="bi bi-funnel-fill" aria-hidden="true"></i>
              {{ TIPOS.filter((t) => tiposMarcados.includes(t.valor))
                      .map((t) => t.rotulo).join(' · ') }}
            </span>
            <!-- 🚨 A EXPLICAÇÃO DA BUSCA SUBIU PARA O ÍCONE DE AJUDA (28/08).
                 Ela era uma faixa fixa embaixo do campo, na coluna de 348px:
                 três linhas de altura permanente numa coluna cujo produto é
                 quantas conversas cabem à vista.

                 🚨 ERA A METADE QUE FALTOU DE 27/08. O pedido dele -- *"as
                 abas tem textos explicativos... transforme em balões ícones
                 apenas"* -- alcançava 15 telas; eu varri por FORMA DE
                 MARCAÇÃO (`<h1>` + `<p class="apagado pequeno">`) e entreguei
                 13. Esta ficou de fora porque o texto não estava no cabeçalho,
                 e o do E-mail porque o `<h1>` de lá tem `class`. Medir a forma
                 do código em vez do alcance do pedido é o M7 outra vez. -->
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
              :class="{
                'conversa--aberta': aberta && aberta.id === c.id,
                'conversa--grupo': c.tipo === 'grupo',
              }"
              type="button"
              @click="abrir(c.id)"
            >
              <!-- 🚨 AVATAR COM INICIAL, NÃO ÍCONE GENÉRICO. A lista é lida
                   de relance, dezenas de vezes por dia: cor estável derivada
                   do nome distingue a conversa antes de a pessoa ler. Grupo
                   troca a inicial pelo ícone de pessoas -- ali a inicial de
                   um nome de grupo não identifica ninguém. -->
              <span
                class="conversa__avatar"
                :style="{ background: c.tipo === 'grupo' ? null : corDaInicial(quem(c)) }"
                :class="{ 'conversa__avatar--grupo': c.tipo === 'grupo' }"
                aria-hidden="true"
              >
                <i v-if="c.tipo === 'grupo'" class="bi bi-people"></i>
                <template v-else>{{ iniciais(quem(c)) }}</template>
              </span>

              <span class="conversa__corpo">
              <div class="conversa__topo">
                <strong class="conversa__quem">{{ quem(c) }}</strong>
                <span class="apagado pequeno conversa__hora">
                  {{ quando(c.ultima_atividade_em) }}
                </span>
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
              <!-- 🚨 UMA LINHA DE MARCAS, NÃO CINCO CHIPS. Antes toda
                   conversa carregava até cinco chips do mesmo peso -- e
                   "sem dono" aparecia em TODAS as 336, virando ruído puro. O
                   que fica é o que diferencia esta conversa das outras: quem
                   responde (quando há), a empresa (quando se sabe) e o
                   estado excepcional. -->
              <div class="conversa__marcas pequeno">
                <span v-if="!c.contato_nome" class="chip chip--aviso chip--pequeno">
                  sem cadastro
                </span>
                <span v-else-if="c.cliente_nome" class="chip chip--pequeno">
                  {{ c.cliente_nome }}
                </span>
                <span v-if="c.estado === 'resolvida'" class="chip chip--ok chip--pequeno">
                  concluída
                </span>
                <span v-if="c.atendente_nome" class="chip chip--acento chip--pequeno">
                  {{ c.atendente_nome }}
                </span>
              </div>
              </span>
            </button>

            <!-- Sem dono, ou encerrada: dá para pegar daqui, sem abrir antes.
                 Encerrada, assumir REABRE -- por isso o rótulo muda. -->
            <button
              v-if="!c.atendente_id || c.estado === 'resolvida'"
              class="botao botao--pequeno botao--primario conversas__assumir"
              type="button"
              :title="c.estado === 'resolvida'
                ? 'Reabrir este atendimento e passar a responder por ele'
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
              <!-- 🚨 O BOTÃO DIZ DE QUEM É A FICHA, e muda de cara quando não
                   há ficha. Era um botão fantasma com "Ver ficha", do mesmo
                   peso de tudo na barra. Medido em 28/08: 231 das 381
                   conversas (61%) não têm cadastro -- então a falta de
                   cadastro é o estado mais COMUM, e é o convite para
                   resolver, não um detalhe. Por isso ele é contorno âmbar
                   quando falta, e contorno normal com o nome dentro quando
                   existe. -->
              <button
                v-if="!ehGrupo"
                class="botao botao--pequeno"
                :class="aberta.contato_id ? 'botao--contorno' : 'botao--faltando'"
                type="button"
                :aria-expanded="gaveta"
                @click="gaveta = !gaveta"
              >
                <i class="bi" :class="aberta.contato_id
                     ? 'bi-person-lines-fill' : 'bi-person-exclamation'"
                   aria-hidden="true"></i>
                <!-- 🚨 A PALAVRA "FICHA" ABRE TODOS OS CASOS (28/08). Pedido
                     dele: *"não vejo mais a ficha nas conversas"* -- e a ficha
                     estava lá o tempo todo. O rótulo "Sem ficha — vincular",
                     que eu escrevi em 25/08 (48bdfd4), lê como AUSÊNCIA e não
                     como porta, e ele cai em 231 das 381 conversas (61%,
                     medido em 28/08): o estado mais comum da tela anunciava
                     que a função não existia.

                     ⚠️ O que distingue os dois casos continua sendo o CONTORNO
                     âmbar e o ícone, não a palavra. Cor diz estado; a palavra
                     diz que coisa é. -->
                <template v-if="gaveta">Fechar ficha</template>
                <template v-else-if="aberta.empresa && aberta.empresa.cliente">
                  Ficha · {{ aberta.empresa.cliente.nome }}
                </template>
                <template v-else-if="aberta.contato_nome">
                  Ficha · {{ aberta.contato_nome }}
                </template>
                <template v-else>Ficha · vincular</template>
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
              <!-- 🚨 O QUE ABRE A BUSCA (27/08). Fica na fileira das ações da
                   conversa porque é isso que ela é: uma ação eventual. Antes
                   era uma faixa fixa comendo altura em toda conversa.
                   ⚠️ Fica ACESO enquanto a busca está aberta -- botão que
                   alterna e não mostra em que estado está é adivinhação. -->
              <button
                class="botao botao--pequeno botao--icone"
                :class="buscaAberta ? 'botao--primario' : 'botao--contorno'"
                type="button"
                :title="buscaAberta ? 'Fechar a busca' : 'Buscar nesta conversa'"
                :aria-label="buscaAberta ? 'Fechar a busca' : 'Buscar nesta conversa'"
                :aria-pressed="buscaAberta"
                @click="alternarBusca"
              >
                <i class="bi bi-search" aria-hidden="true"></i>
              </button>
              <!-- 🚨 AÇÃO SOBRE A CONVERSA TEM PALAVRA (28/08). Esta fileira
                   tinha CINCO botões só de ícone e UM com texto -- e o único
                   legível era "Concluir atendimento", o que encerra. Tudo que
                   é rotina e reversível era adivinhação.

                   🚨 O PAR PERIGOSO ERA ESTE: "devolver à fila" e "sair da
                   conversa" são duas setas apontando para a ESQUERDA, lado a
                   lado (`arrow-return-left` e `box-arrow-left`), e fazem
                   coisas diferentes -- uma larga a conversa para a fila, a
                   outra tira você dela. Só o balão do navegador distinguia as
                   duas, e ele não existe em toque.

                   ⚠️ A RÉGUA, para as telas seguintes: fica só ícone o que é
                   convenção do gênero E mora colado ao campo que serve (lupa,
                   funil, clipe, microfone, emoji, X). Ganha palavra o que age
                   sobre a conversa. O texto longo continua no `title`. -->
              <button
                class="botao botao--pequeno botao--contorno"
                type="button"
                title="Transferir para outro time"
                @click="abrirPainel('transferir')"
              >
                <i class="bi bi-arrow-left-right" aria-hidden="true"></i>
                Transferir
              </button>
              <button
                class="botao botao--pequeno botao--contorno"
                type="button"
                title="Convidar atendentes para esta conversa"
                @click="abrirPainel('convidar')"
              >
                <i class="bi bi-person-plus" aria-hidden="true"></i>
                Convidar
              </button>
              <button
                v-if="aberta.atendente_id"
                class="botao botao--pequeno botao--contorno"
                type="button"
                title="A conversa fica sem dono e volta para a fila"
                @click="pedirParaDevolver"
              >
                <i class="bi bi-arrow-return-left" aria-hidden="true"></i>
                Devolver à fila
              </button>
              <button
                class="botao botao--pequeno botao--contorno"
                type="button"
                :disabled="mexendo"
                title="A conversa some da sua lista"
                @click="pedirParaSair"
              >
                <i class="bi bi-box-arrow-left" aria-hidden="true"></i>
                Sair
              </button>
              <span class="espaco"></span>
              <button
                class="botao botao--pequeno botao--contorno"
                type="button"
                @click="abrirPainel('encerrar')"
              >
                <i class="bi bi-check2-square" aria-hidden="true"></i>
                Concluir atendimento
              </button>
            </div>
          </div>

          <!-- 🚨 A FAIXA DE AVISO SAIU (28/08). Ela aparecia em 61% das
               conversas — faixa larga, quatro linhas, dizendo o que o botão
               da ficha logo acima já diz em âmbar e por escrito: não há
               cadastro. Dois lugares para o mesmo estado, e o segundo era o
               que gastava altura.

               ⚠️ O ÚNICO FATO QUE ELA CARREGAVA E O BOTÃO NÃO — o número
               responder por vários cadastros — ficou na gaveta, em uma linha.
               Ele cortou o padrão inteiro: *"elas ajudaram nas etapas de
               lógica, mas agora em teste sujam a tela"*. -->

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
                {{ empresas.length }} empresas do mesmo responsável.
              </p>
            </div>

            <!-- 🚨 TRÊS ESTADOS, NÃO DOIS (28/08). Havia "com empresa" e "sem
                 nada". Desde que o tipo pode ser marcado sem vincular empresa,
                 existe o do meio -- cadastro sem empresa -- e sem este ramo a
                 gaveta continuaria dizendo "Sem cadastro" logo depois de a
                 pessoa ter criado um. A tela negaria o que ela acabou de
                 fazer. Achado na validação, antes de escrever. -->
            <p v-if="aberta.empresa && aberta.empresa.contato && !aberta.empresa.cliente"
               class="chip chip--aviso">Cadastro sem empresa</p>

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

                <!-- 🚨 O TIPO DECIDE SE A AUTOMAÇÃO E A IA ATENDEM ESTA
                     PESSOA (CFG_5.1). Fica na ficha porque quem fala com ela
                     é quem sabe o que ela é. -->
                <dt>Tipo</dt>
                <dd>
                  <!-- ⚠️ Mesma classe da ficha do contato (CAD_1.2): o tipo é
                       um campo só e tem de ter uma cara só. -->
                  <select
                    v-if="podeTrocarTipo"
                    :value="aberta.empresa.contato.relacao"
                    class="campo__entrada campo__entrada--compacto"
                    @change="trocarTipo($event.target.value)"
                  >
                    <option v-for="[valor, rotulo] in RELACOES" :key="valor" :value="valor">
                      {{ rotulo }}
                    </option>
                  </select>
                  <span v-else class="chip">
                    {{ NOME_RELACAO[aberta.empresa.contato.relacao]
                       || aberta.empresa.contato.relacao }}
                  </span>
                  <span v-if="tipoSalvo" class="chip chip--ok">gravado</span>
                </dd>
              </dl>
              <button class="botao botao--pequeno botao--fantasma" type="button" @click="desvincular">
                <i class="bi bi-x-circle" aria-hidden="true"></i> Desvincular
              </button>
            </template>

            <!-- SEM EMPRESA: o caso comum. Marcar o tipo e/ou vincular. -->
            <template v-else>
              <p v-if="!aberta.contato_id" class="chip chip--aviso">
                Não está no cadastro
              </p>

              <!-- 🚨 O TIPO APARECE MESMO SEM CADASTRO (27/08). Ele apontou
                   que a lista "não aparece na Ficha do contato" -- e não
                   aparecia mesmo: o Tipo é coluna de CONTATO, e **63% das
                   conversas abertas não têm contato** (234 de 374, medido).

                   Só que a pessoa TEM um tipo: a automação e a IA já a tratam
                   como `sem_cadastro`, e esse é o tipo que decide se elas
                   respondem. Esconder isso deixava a ficha muda justamente no
                   caso mais comum.

                   ⚠️ É A REGRA QUE VOCÊ APROVOU NA ESCADA DA IA: nada some;
                   o que não dá para mudar aparece dizendo o que falta para
                   destravar. Trocar exige vincular, porque é no contato que o
                   tipo mora -- criar contato a partir daqui é decisão sua, e
                   não a tomei.

                   🚨 "SEM CADASTRO" NÃO ESTÁ EM `RELACOES` DE PROPÓSITO, e
                   não é esquecimento: `contato.relacao` tem 8 valores no CHECK
                   do banco, e este não é um deles. Ele é chave da
                   `relacao_automacao` -- a linha que decide o que fazer com
                   quem NÃO tem contato. Pôr no seletor faria a tela oferecer
                   um valor que o banco recusa. -->
              <!-- 🚨 O SELETOR APARECE SEM CADASTRO (28/08), e escolher CRIA
                   o contato. Antes aqui havia um chip morto dizendo "Sem
                   cadastro" -- estado, sem saída. O tipo mora em `contato`, e
                   o que faltava não era o campo: era o registro.

                   ⚠️ `sem_identificacao` NÃO entra na lista: é o valor com que
                   o contato NASCE (migração 031), não uma escolha. Oferecê-lo
                   seria convidar a marcar "não sei" de propósito. -->
              <dl class="gaveta__dados">
                <dt>Tipo</dt>
                <dd>
                  <select
                    v-if="podeMarcarTipo"
                    v-model="tipoSemCadastro"
                    class="campo__entrada campo__entrada--compacto"
                    @change="trocarTipo(tipoSemCadastro)"
                  >
                    <option value="">sem cadastro</option>
                    <option v-for="[valor, rotulo] in RELACOES_ESCOLHIVEIS"
                            :key="valor" :value="valor">{{ rotulo }}</option>
                  </select>
                  <span v-else class="chip">Sem cadastro</span>
                </dd>
              </dl>

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
                <span class="apagado pequeno">Sistema antigo — não é vínculo.</span>
              </div>
              <!-- 🚨 A ESCOLHA DA EMPRESA SAIU DAQUI E VIROU MODAL (28/08).
                   Pedido dele: *"ao selecionar algumas empresas pelo campo de
                   busca, na ficha, para vínculo, não está exibindo claramente,
                   verifique o uso de uma caixa modal, acaba sendo uma saída
                   para não ficar espremendo as coisas"*.

                   Ele estava certo, e dá para medir: a gaveta tem teto de
                   `42vh` e já carregava, ACIMA da lista, o nome, o telefone,
                   o botão de empresas, o Tipo, o selo do Bitrix, um parágrafo,
                   o bloco de candidatos e o campo de busca. Os 10 resultados
                   que o backend devolve (teto da rota) caíam no que sobrasse
                   -- perto de 180px numa janela de 900px, com uma SEGUNDA
                   barra de rolagem dentro da primeira.

                   ⚠️ A gaveta fica com o que é ESTADO (quem é, que tipo é, o
                   que o Bitrix acha); o modal fica com o que é ESCOLHA. Era a
                   mistura dos dois no mesmo teto que espremia. -->
              <button
                class="botao botao--pequeno botao--primario"
                type="button"
                @click="abrirPainel('vincular')"
              >
                <i class="bi bi-link-45deg" aria-hidden="true"></i>
                Vincular a uma empresa
              </button>
              <!-- O único fato que a faixa de aviso carregava e o botão da
                   ficha não carrega. Uma linha, sem a lição. -->
              <p v-if="aberta.candidatos && aberta.candidatos.length"
                 class="apagado pequeno">
                Responde por {{ aberta.candidatos.length }} cadastros.
              </p>
            </template>
          </aside>

          <!-- BUSCAR NA CONVERSA — outra pergunta que a busca da lista:
               lá é "com quem eu falei", aqui é "onde ele disse isso". -->
          <!-- 🚨 A BUSCA SÓ APARECE QUANDO SE PEDE (27/08, pedido dele: *"o
               campo de busca na conversa, pode abrir de um botão, pois ocupa
               muito espaço"*). Ela é uma ação eventual ocupando uma faixa fixa
               na altura mais disputada da tela — e altura, aqui, é conversa
               visível.

               ⚠️ FECHAR LIMPA O TERMO. Deixar o termo guardado esconderia um
               filtro ativo: os balões continuariam marcados e o contador
               sumiria, sem nada dizendo por quê. -->
          <div v-if="buscaAberta" class="buscaconversa">
            <div class="busca">
              <input
                v-model="buscaNaConversa"
                class="campo__entrada"
                type="search"
                placeholder="Buscar na conversa"
                ref="campoBuscaConversa"
                aria-label="Buscar na conversa"
                @keyup.enter="irParaAchado(1)"
                @keydown.esc="fecharBusca"
                :disabled="!aberta"
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
              <button
                class="botao botao--pequeno botao--fantasma botao--icone"
                type="button"
                title="Fechar a busca"
                aria-label="Fechar a busca"
                @click="fecharBusca"
              >
                <i class="bi bi-x-lg" aria-hidden="true"></i>
              </button>
            </div>
            <!-- ⚠️ O AVISO DE "TRUNCADA" SAIU. Ele existia porque a busca só
                 via o que estava carregado; agora ela roda no servidor e
                 alcança a conversa inteira, então "nada com esse termo" é
                 verdade quando aparece. -->
            <p v-if="buscandoNaConversa" class="linha pequeno fraco">
              <span class="girando"></span> procurando…
            </p>
            <p v-else-if="achadosLimitados" class="chip chip--aviso pequeno">
              Mostrando os primeiros {{ achadosNaConversa.length }} acertos —
              use um termo mais específico.
            </p>
            <p v-else-if="buscaNaConversa.trim() && !achadosNaConversa.length"
               class="apagado pequeno">
              Nada com esse termo nesta conversa.
            </p>
          </div>

          <div ref="baloes" class="baloes">
            <!-- 🚨 O TOPO DA CONVERSA. A tela abre com as 60 mais recentes e
                 sobe de 200 em 200: o teto de 1.000 saiu quando a maior
                 conversa da base chegou a 776. -->
            <div v-if="aberta.tem_anteriores" class="anteriores">
              <button
                class="botao botao--pequeno botao--contorno"
                type="button"
                :disabled="carregandoAnteriores"
                @click="carregarAnteriores"
              >
                <span v-if="carregandoAnteriores" class="girando"></span>
                <i v-else class="bi bi-arrow-up" aria-hidden="true"></i>
                Carregar {{ aberta.janela }} anteriores
              </button>
            </div>
            <template v-for="(m, i) in aberta.mensagens" :key="m.id">
            <p v-if="comecaODia(m, i)" class="diario">
              <span class="diario__marca">{{ rotuloDoDia(m.criada_em) }}</span>
            </p>
            <div
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

              <!-- 🚨 CLICAR ABRE EM TELA CHEIA. A foto abria do tamanho do
                   balão, e print de erro e foto de avaria são exatamente o
                   que precisa de zoom. -->
              <img
                v-if="m.midia_id && ['imagem', 'figurinha'].includes(tipoDaMidia(m)) && midias[m.midia_id]"
                :src="midias[m.midia_id]"
                class="balao__imagem balao__imagem--clicavel"
                :alt="m.conteudo || 'imagem da conversa'"
                @click="emTelaCheia = midias[m.midia_id]"
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
              <!-- Veio de outra conversa: o histórico precisa dizer isso.
                   Seis meses depois ninguém sabe se a frase foi escrita para
                   este cliente ou repassada. -->
              <p v-if="m.encaminhada_de" class="balao__marca pequeno">
                <i class="bi bi-arrow-right" aria-hidden="true"></i> encaminhada
              </p>

              <p class="balao__rodape apagado pequeno">
                {{ hora(m.criada_em) }}
                <!-- Só na saída: quem respondeu pelo painel. O eco do WhatsApp
                     chega sem atendente, e aí não há nome a mostrar. -->
                <span v-if="m.direcao === 'saida' && m.atendente_nome">
                  · {{ m.atendente_nome }}
                </span>
                <!-- 🚨 O TIQUE, não a palavra (27/08). "enviada / entregue /
                     lida" é vocabulário nosso, do CHECK do banco; quem atende
                     lê ✓ e ✓✓ sem pensar. O segundo tique fica AZUL só quando
                     foi lida -- é a única diferença entre entregue e lida, e é
                     a que o atendente procura.
                     ⚠️ `title` mantém a palavra, para quem passar o mouse e
                     para leitor de tela: o símbolo não pode ser a única
                     fonte. -->
                <span v-if="TIQUE[m.entrega]"
                      class="balao__tique"
                      :class="{ 'balao__lida': m.entrega === 'lida' }"
                      :title="m.entrega">{{ TIQUE[m.entrega] }}</span>
                <span v-else-if="m.entrega"> · {{ m.entrega }}</span>
              </p>

              <!-- A reação fica PENDURADA no canto do balão, como no
                   WhatsApp: dentro dele, viraria mais uma linha de texto.
                   ⚠️ A CONTA SÓ APARECE A PARTIR DE DOIS. Num grupo, "👍 3"
                   é informação; numa conversa direta, "👍 1" é ruído em todo
                   balão. -->
              <span v-if="(m.reacoes || []).length" class="balao__reacao">
                <span v-for="r in m.reacoes" :key="r.emoji"
                      class="balao__reacao-item"
                      :class="{ 'balao__reacao-item--nosso': r.nosso }"
                      :title="r.nosso ? 'inclui a sua reação' : ''">
                  {{ r.emoji }}<em v-if="r.n > 1">{{ r.n }}</em>
                </span>
              </span>

              <!-- ⚠️ AS AÇÕES APARECEM NO HOVER, não sempre. Três botões fixos
                   em cada balão transformam o fio numa grade de botões, e o
                   que se lê é a conversa. -->
              <div v-if="posso && m.tipo !== 'nota'" class="balao__acoes">
                <button class="balao__acao" type="button" title="Responder citando"
                        aria-label="Responder citando" @click="citar(m)">
                  <i class="bi bi-reply" aria-hidden="true"></i>
                </button>
                <button class="balao__acao" type="button" title="Reagir"
                        aria-label="Reagir"
                        @click="reagindoEm = reagindoEm === m.id ? null : m.id">
                  <i class="bi bi-emoji-smile" aria-hidden="true"></i>
                </button>
                <button v-if="m.conteudo && !m.midia_id" class="balao__acao"
                        type="button" title="Encaminhar" aria-label="Encaminhar"
                        @click="abrirEncaminhar(m)">
                  <i class="bi bi-arrow-right" aria-hidden="true"></i>
                </button>

                <div v-if="reagindoEm === m.id" class="reacoes">
                  <!-- ⚠️ A NOSSA FICA MARCADA NO SELETOR TAMBÉM: clicar nela
                       de novo é o que TIRA a reação, e sem a marca o gesto
                       parece não fazer nada. -->
                  <button v-for="e in REACOES" :key="e" class="reacoes__item"
                          :class="{ 'reacoes__item--nosso': nossaReacao(m) === e }"
                          type="button" @click="reagir(m, e)">{{ e }}</button>
                </div>
              </div>
            </div>
            </template>
          </div>

          <div v-if="aberta.estado === 'resolvida'" class="cartao__corpo pilha">
            <p class="aviso aviso--ok">
              <i class="bi bi-check-circle aviso__icone" aria-hidden="true"></i>
              <span>
                Atendimento concluído. A conversa está no Histórico e sem dono.
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

          <div v-else class="cartao__corpo pilha rodape-conversa">
            <!-- 🚨 NÃO EXISTE MAIS SELETOR DE MODO. Havia um par
                 "Para o cliente | Nota interna" que só trocava um estado
                 invisível: clicar no lado que já estava ativo não fazia nada,
                 e o usuário perguntou duas vezes para que servia. Estado que
                 não se vê é o que confunde. Agora o destino é o BOTÃO: um
                 campo, duas ações, e o que se clica é o que acontece. -->
            <!-- A mensagem que está sendo citada, com um X para desistir. -->
            <div v-if="citando" class="citando">
              <i class="bi bi-reply" aria-hidden="true"></i>
              <span class="citando__texto">
                {{ citando.conteudo || `(${citando.tipo})` }}
              </span>
              <button class="botao botao--pequeno botao--fantasma" type="button"
                      title="Não citar" @click="citando = null">×</button>
            </div>

            <label class="campo compositor">
              <span class="so-leitor">Mensagem</span>
              <textarea
                ref="campoResposta"
                v-model="resposta"
                class="campo__entrada"
                rows="3"
                :placeholder="ehGrupo
                  ? 'Escreva — @ chama alguém do grupo'
                  : 'Escreva e escolha abaixo: enviar ao cliente ou guardar como nota'"
                maxlength="4000"
                @input="olharArroba"
                @keydown.ctrl.enter.prevent="enviar"
                @keydown.enter.exact="enterNoCompositor"
                @keydown.down="andarNaLista(1, $event)"
                @keydown.up="andarNaLista(-1, $event)"
                @keydown.esc="listaArroba = []"
                @paste="colar"
              ></textarea>

              <!-- A lista sobe: o compositor mora no rodapé da conversa. -->
              <ul v-if="listaArroba.length" class="arroba" role="listbox">
                <li v-for="(p, i) in listaArroba" :key="p.jid">
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

            <!-- 🚨 QUEM VAI SER CHAMADO APARECE ANTES DE ENVIAR, e o aviso diz
                 que isso só vale em grupo — a tela não pode prometer o que o
                 WhatsApp ignora fora dele. -->
            <p v-if="mencionados.length" class="linha pequeno fraco chamados">
              <i class="bi bi-at" aria-hidden="true"></i>
              <span>chamando no grupo</span>
              <button v-for="p in mencionados" :key="p.jid"
                      class="chamados__chip" type="button"
                      :title="`não chamar ${p.nome}`"
                      @click="tirarMencionado(p.jid)">
                {{ p.nome }} <i class="bi bi-x" aria-hidden="true"></i>
              </button>
            </p>

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
              <!-- 🚨 GRAVAR ÁUDIO: o que o atendente mais usa no celular.
                   Enquanto grava, os outros botões dão lugar ao contador --
                   gravando, a única decisão é enviar ou desistir. -->
              <template v-if="gravando">
                <span class="gravando">
                  <span class="gravando__ponto" aria-hidden="true"></span>
                  gravando {{ Math.floor(segundosGravados / 60) }}:{{
                    String(segundosGravados % 60).padStart(2, '0') }}
                </span>
                <button class="botao botao--pequeno botao--fantasma" type="button"
                        @click="cancelarGravacao">Cancelar</button>
                <button class="botao botao--primario" type="button"
                        :disabled="enviando" @click="enviarGravacao">
                  <i class="bi bi-send" aria-hidden="true"></i> Enviar áudio
                </button>
              </template>

              <button v-else class="botao botao--contorno botao--icone"
                      type="button" title="Gravar áudio" aria-label="Gravar áudio"
                      @click="comecarGravacao">
                <i class="bi bi-mic" aria-hidden="true"></i>
              </button>

              <label v-if="!gravando" class="botao botao--contorno botao--icone" title="Anexar arquivo">
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
                :title="temAlgoParaEnviar ? '' : 'Escreva algo ou anexe um arquivo'"
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
                :title="temAlgoParaEnviar ? '' : 'Escreva algo ou anexe um arquivo'"
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
                  Ctrl+Enter envia. Até {{ TETO_ARQUIVO_MB }} MB.
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

    <!-- TELA CHEIA — clique em qualquer lugar fecha, como em toda galeria. -->
    <div v-if="emTelaCheia" class="cheia" @click="emTelaCheia = null">
      <img :src="emTelaCheia" class="cheia__img" alt="imagem da conversa" />
      <button class="cheia__fechar" type="button" aria-label="Fechar">
        <i class="bi bi-x-lg" aria-hidden="true"></i>
      </button>
    </div>

    <!-- ENCAMINHAR — lista de conversas com caixas de seleção, como o
         WhatsApp faz. Cinco por vez, que é o limite do próprio aplicativo. -->
    <div v-if="encaminhando" class="modal" @click.self="encaminhando = null">
      <div class="modal__caixa" role="dialog" aria-modal="true" aria-label="Encaminhar">
        <p class="modal__titulo">Encaminhar para</p>
        <p class="modal__texto pequeno">
          A mensagem chega como <strong>mensagem nova</strong>, marcada como
          encaminhada — não como citação.
          <!-- ⚠️ O ARQUIVO PASSOU A IR JUNTO EM 26/08. Dizer isso aqui evita
               a dúvida de quem lembra que antes só ia o texto — e avisa do
               teto ANTES do clique, não depois da falha. -->
          <template v-if="encaminhando.midia_id">
            <br />O <strong>arquivo vai junto</strong>. Acima de 25 MB o
            WhatsApp recusa.
          </template>
        </p>

        <div class="modal__opcoes">
          <label v-for="c in lista.filter((x) => x.id !== aberta.id
                                                 && x.estado !== 'resolvida')"
                 :key="c.id" class="modal__opcao">
            <input v-model="destinosEscolhidos" type="checkbox" :value="c.id"
                   :disabled="destinosEscolhidos.length >= 5
                              && !destinosEscolhidos.includes(c.id)" />
            <span>{{ quem(c) }}</span>
          </label>
        </div>

        <p class="apagado pequeno">
          {{ destinosEscolhidos.length }} de 5 escolhidos.
        </p>

        <div class="modal__acoes">
          <button class="botao botao--contorno" type="button"
                  @click="encaminhando = null">Cancelar</button>
          <button class="botao botao--primario" type="button"
                  :disabled="!destinosEscolhidos.length"
                  :title="destinosEscolhidos.length ? '' : 'Marque ao menos uma conversa de destino'"
                  @click="confirmarEncaminhar">
            Encaminhar
          </button>
        </div>
      </div>
    </div>

    <!-- NOVA MENSAGEM — o `+`. Um destinatário: este painel responde
         "falar com esta pessoa". -->
    <div v-if="novaAberta" class="modal" @click.self="novaAberta = false">
      <div class="modal__caixa" role="dialog" aria-modal="true" aria-label="Nova mensagem">
        <p class="modal__titulo">Nova mensagem</p>
        <p class="modal__texto pequeno">
          Para um número que ainda não escreveu.
        </p>

        <label class="campo">
          <span class="campo__rotulo">Número</span>
          <input
            v-model="novoNumero"
            class="campo__entrada"
            type="tel"
            placeholder="(18) 99811-6168"
            autocomplete="off"
          />
          <span class="campo__ajuda">Com DDD. Pode colar como estiver.</span>
        </label>

        <label class="campo">
          <span class="campo__rotulo">Mensagem</span>
          <textarea
            v-model="novoTexto"
            class="campo__entrada"
            rows="3"
            maxlength="4000"
          ></textarea>
        </label>

        <!-- 🚨 A RECUSA POR FALTA DE WHATSAPP TEM CARA PRÓPRIA. É a diferença
             entre "erra o número" e "o sistema falhou", e a reação de quem
             está na tela é outra em cada caso. -->
        <p v-if="semWhatsapp" class="aviso aviso--atencao">
          <i class="bi bi-whatsapp aviso__icone" aria-hidden="true"></i>
          <span>{{ erroNova }}</span>
        </p>
        <p v-else-if="erroNova" class="aviso aviso--erro">
          <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
          <span>{{ erroNova }}</span>
        </p>

        <div class="modal__acoes">
          <button class="botao botao--contorno" type="button" @click="novaAberta = false">
            Cancelar
          </button>
          <button
            class="botao botao--primario"
            type="button"
            :disabled="enviandoNova || !novoNumero.trim() || !novoTexto.trim()"
            :title="!novoNumero.trim() ? 'Informe o número, com DDD'
              : !novoTexto.trim() ? 'Escreva a mensagem' : ''"
            @click="enviarNova"
          >
            <span v-if="enviandoNova" class="girando"></span>
            <i v-else class="bi bi-whatsapp" aria-hidden="true"></i>
            Enviar
          </button>
        </div>
      </div>
    </div>

    <!-- CONVIDAR — vários de uma vez, por caixa de seleção -->
    <div v-if="painelAcao === 'convidar' && aberta" class="modal" @click.self="fecharPainel">
      <div class="modal__caixa" role="dialog" aria-modal="true" aria-label="Convidar atendentes">
        <p class="modal__titulo">Convidar para esta conversa</p>
        <p class="modal__texto pequeno">
          Quem for chamado passa a ver esta conversa e responde por ela.
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
            :title="convidados.length ? '' : 'Marque quem você quer chamar'"
            @click="convidar"
          >
            <span v-if="mexendo" class="girando"></span>
            {{ convidados.length > 1 ? `Convidar ${convidados.length}` : 'Convidar' }}
          </button>
        </div>
      </div>
    </div>

    <!-- VINCULAR A UMA EMPRESA — a escolha que morava espremida na gaveta -->
    <div v-if="painelAcao === 'vincular' && aberta" class="modal" @click.self="fecharPainel">
      <div class="modal__caixa modal__caixa--larga" role="dialog" aria-modal="true"
           aria-label="Vincular a uma empresa">
        <p class="modal__titulo">Vincular a uma empresa</p>
        <!-- ⚠️ SÓ O FATO: de quem é o número. A explicação de que o telefone
             entra no cadastro como vindo do atendimento era aula, e ele
             cortou (28/08): *"muito textinho no modal"*. -->
        <p class="modal__texto pequeno">
          <strong class="mono">{{ aberta.telefone_e164 }}</strong>
          <span v-if="aberta.nome_whatsapp"> · {{ aberta.nome_whatsapp }}</span>
        </p>

        <!-- Candidatos que o próprio sistema já achou pelo telefone. Ficam
             ANTES da busca: quando existem, quase sempre a resposta está
             entre eles, e digitar seria trabalho à toa. -->
        <div v-if="aberta.candidatos && aberta.candidatos.length" class="vincular__bloco">
          <p class="campo__rotulo">Este número já responde por</p>
          <div class="modal__opcoes">
            <button
              v-for="c in aberta.candidatos"
              :key="c.id"
              class="vincular__item"
              type="button"
              :disabled="vinculando"
              @click="vincularA(c.cliente_id || c.id)"
            >
              <span>{{ c.nome }}</span>
            </button>
          </div>
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

        <p v-if="buscando" class="linha apagado pequeno">
          <span class="girando"></span> procurando…
        </p>
        <!-- ⚠️ O TETO DA ROTA APARECE NA TELA. `/api/conversas/buscar-empresa`
             devolve no máximo 10, e teto que ninguém vê não é limite: é dado
             sumindo. É a mesma regra dos 200 acertos da busca na conversa. -->
        <template v-else-if="achadosCliente.length">
          <div class="modal__opcoes">
            <button
              v-for="c in achadosCliente"
              :key="c.id"
              class="vincular__item"
              type="button"
              :disabled="vinculando"
              @click="vincularA(c.id)"
            >
              <span class="vincular__nome">{{ c.nome }}</span>
              <span class="apagado pequeno mono">
                {{ documentoLegivel(c.documento) || 'sem CNPJ' }}
              </span>
            </button>
          </div>
          <p v-if="achadosCliente.length >= 10" class="apagado pequeno">
            Mostrando as 10 primeiras. Refine o termo se a sua não estiver aqui.
          </p>
        </template>
        <p v-else-if="buscaCliente.trim().length >= 2" class="apagado pequeno">
          Nenhuma empresa com esse termo.
        </p>
        <!-- ⚠️ O estado de "ainda não dá para buscar" não precisa de frase: o
             campo vazio já diz. A explicação de POR QUE são 2 letras era aula
             sobre a regra, não instrução de uso. -->

        <div class="modal__acoes">
          <button class="botao botao--contorno" type="button" @click="fecharPainel">
            Cancelar
          </button>
        </div>
      </div>
    </div>

    <!-- TRANSFERIR -->
    <div v-if="painelAcao === 'transferir' && aberta" class="modal" @click.self="fecharPainel">
      <div class="modal__caixa" role="dialog" aria-modal="true" aria-label="Transferir conversa">
        <p class="modal__titulo">Transferir para outro time</p>
        <!-- ⚠️ A consequência fica (transferir tira o dono, e isso não se
             desfaz); a aula sobre triagem e IA saiu. -->
        <p class="modal__texto pequeno">
          Transferir tira o dono: a conversa volta a ser do time.
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
          <button class="botao botao--primario" type="button"
                  :disabled="!timeEscolhido"
                  :title="timeEscolhido ? '' : 'Escolha o time de destino'"
                  @click="transferir">
            Transferir
          </button>
        </div>
      </div>
    </div>

    <!-- ENCERRAR — caixa de confirmação. A classificação vem NO FIM e é
         opcional desde 11/08: ninguém pediu a lista, e o analytics que a
         justificava é Fase 3. -->
    <div v-if="painelAcao === 'encerrar' && aberta" class="modal" @click.self="fecharPainel">
      <div class="modal__caixa" role="dialog" aria-modal="true" aria-label="Concluir atendimento">
        <p class="modal__titulo">Concluir este atendimento?</p>
        <p class="modal__texto">
          A conversa passa para o Histórico e <strong>volta para "sem
          dono"</strong>. O cliente <strong>não</strong> é avisado, e você
          pode reabrir esta a qualquer momento.
        </p>
        <!-- ⚠️ Concluir vale mesmo com gente dentro: concluir é conclusão.
             Quem quer só se retirar usa "Sair da conversa", que é outra ação
             e continua existindo. -->
        <p v-if="acompanham.length" class="modal__texto pequeno">
          <strong>{{ acompanham.length }} pessoa(s) acompanham</strong> esta
          conversa. Concluir tira todo mundo — inclusive elas.
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
              Concluir sem classificar é o caminho normal.
            </span>
          </label>
          <label v-if="exigeComentario" class="campo">
            <span class="campo__rotulo">Comentário — obrigatório nesta</span>
            <textarea v-model="comentario" class="campo__entrada" rows="2" maxlength="2000"></textarea>
            <span class="campo__ajuda">
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
            :title="exigeComentario && !comentario.trim()
              ? 'Esta classificação exige um comentário dizendo o que foi' : ''"
            @click="encerrar"
          >
            Concluir atendimento
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
  /* ⚠️ A COLUNA PASSOU A TER ALTURA, então a ficha também precisa saber
     encolher: aberta numa pessoa com muitas empresas, ela empurraria o fio e
     o compositor para fora do cartão -- e `.coluna { overflow: hidden }`
     cortaria em silêncio, sem barra para rolar. */
  flex: 0 1 auto;
  max-height: 45%;
  overflow-y: auto;
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
/* O seletor de tipo na ficha: largura de conteúdo, não de formulário. Um
   `<select>` de 100% ao lado de "Empresa" e "CNPJ" desequilibra a lista. */
/* ⚠️ O teto de 12rem saiu junto com o de 14rem da CAD_1.2: quem dimensiona
   agora é `--compacto`, e teto por tela devolveria a divergência. */

/* `.gaveta__tipo-ajuda` saiu: as duas frases que ela formatava eram as
   explicações do tipo que ele mandou tirar em 28/08. Regra sem elemento é
   peso morto que a próxima pessoa tenta entender. */


/* ---- modal de vínculo (28/08) --------------------------------------------
   🚨 MAIS LARGO QUE OS OUTROS, DE PROPÓSITO. `.modal__caixa` é 420px, que
   serve para escolher entre nomes de atendente; razão social com CNPJ ao lado
   quebra em duas linhas nessa largura e a lista vira parede. */
.modal__caixa--larga { max-width: 560px; }

.vincular__bloco { margin-bottom: var(--e-4); }

/* A linha da empresa: nome à esquerda, documento à direita, e o alvo de
   clique ocupando a linha inteira -- não só o texto. */
.vincular__item {
  width: 100%;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--e-3);
  padding: var(--e-2) var(--e-3);
  border: 0;
  border-radius: var(--r-sm);
  background: none;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.vincular__item:hover:not(:disabled) { background: var(--superficie-2); }
.vincular__item:focus-visible { outline: none; box-shadow: var(--foco); }
.vincular__item:disabled { opacity: .55; cursor: default; }
/* ⚠️ `min-width: 0` no nome: sem ele, razão social longa empurra o documento
   para fora da caixa em vez de quebrar. */
.vincular__nome { min-width: 0; }

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

/* ============================================================================
   OS CINCO DEFEITOS QUE A AUDITORIA DE 27/08 ACHOU
   ----------------------------------------------------------------------------
   Ele viu antes de mim: *"visualmente já vejo erros de scroll, alinhamento e
   etc"*. Eu tinha rodado suíte e build -- e nenhum dos dois vê layout. É a
   regra que este projeto já tinha escrita: placar verde não prova que a tela
   abre.

   1. 🚨 A ALTURA NÃO CHEGAVA. `.painel` pedia `height: 100%` e o pai `.tela`
      não tinha altura nenhuma -- em CSS, `height: 100%` sobre pai `auto`
      resolve para `auto`. A tela inteira voltava a crescer com o conteúdo, e
      daí o scroll errado: rolava a PÁGINA em vez de rolar o fio.
   2. `max-width: 1280px` deixava uma faixa vazia em monitor largo, num
      desenho que ocupa a tela toda.
   3. `.cartao__cabecalho` mantinha o raio dos cantos de cima, agora que o
      cartão perdeu o dele -- 12px de curva contra uma borda reta.
   4. e mantinha o fundo cinza, num desenho em que a barra do topo é branca.
   5. os avisos ficavam entre a tela e o painel, sem nenhum respiro lateral:
      colavam na borda da janela.
   ========================================================================== */
.tela--conversa {
  max-width: none;
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* Os avisos são raros e ficam ACIMA das colunas. Sem margem própria eles
   colariam na borda, agora que a página não tem mais padding. */
.tela--conversa > .aviso {
  flex: none;
  margin: var(--e-3) var(--e-4) 0;
}

/* A barra do topo de cada coluna deixa de ser "cabeçalho de cartão": sem raio,
   fundo branco, e a linha de baixo é quem separa. */
.tela--conversa .cartao__cabecalho {
  border-radius: 0;
  background: var(--superficie);
}

.tela__cabecalho {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--e-4);
  flex-wrap: wrap;
  margin-bottom: var(--e-4);
}
.tela__cabecalho p { max-width: var(--largura-texto); margin-top: var(--e-1); }

/* ============================================================================
   A TELA É UM APP DE CONVERSA, NÃO UMA PÁGINA COM CARTÕES (27/08).
   ----------------------------------------------------------------------------
   🚨 Foi o que ele apontou comparando com o mockup que escolheu: *"não ficou
   igual ao modelo, só mudou o fundo, pensei que as dimensões e etc ficariam
   igual"*. Ele estava certo -- eu tinha trocado a pele do balão e deixado a
   estrutura como estava.

   O que muda: as duas colunas COLAM (sem `gap`), ocupam a ALTURA TODA, e
   deixam de ser cartões flutuando com raio e sombra. O respiro da página é
   anulado pelo `meta.cheio` da rota, no App.

   ⚠️ SÓ ESTA TELA. As outras continuam sendo páginas com cartões, e o
   `.painel` daqui é `scoped`. ============================================= */
.painel {
  display: grid;
  grid-template-columns: 348px 1fr;
  /* ⚠️ `flex: 1 1 auto` + `min-height: 0`, NÃO `height: 100%`. O pai é um
     flex-column, e é ele quem distribui a altura; `height: 100%` num filho de
     flex briga com a distribuição e foi metade do defeito de scroll. */
  flex: 1 1 auto;
  min-height: 0;
  gap: 0;
  align-items: stretch;
}
@media (max-width: 1100px) { .painel { grid-template-columns: 300px 1fr; } }
@media (max-width: 860px)  { .painel { grid-template-columns: 1fr; } }

/* As colunas perdem a casca de cartão: sem raio, sem sombra, divididas por
   uma linha de 1px -- é o que faz a tela parecer contínua. */
.painel > .cartao {
  border-radius: 0;
  border: 0;
  box-shadow: none;
  padding: 0;
  min-height: 0;
}
.painel > .cartao + .cartao { border-left: var(--borda-fina) solid var(--borda); }

.coluna {
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--superficie);
}

/* ---- o topo da coluna da lista (27/08) --------------------------------- */
.lista__topo {
  flex: none;
  display: block;
  padding: var(--e-4) var(--e-4) var(--e-3);
  border-bottom: var(--borda-fina) solid var(--borda);
}
/* ⚠️ O ÍCONE DE AJUDA AO LADO DO TÍTULO (28/08). A regra global que faz isso
   nas outras 13 telas mira `.tela__cabecalho > div:first-child`, e este
   cabeçalho é `.cartao__cabecalho` -- não é a mesma casa. Sem esta regra o
   ícone cai embaixo do `<h1>`, que foi exatamente o defeito que a regra
   global nasceu para consertar. */
.lista__titulo {
  margin-bottom: var(--e-3);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--e-2);
  min-width: 0;
}
.lista__titulo h1 {
  margin: 0;
  font-size: var(--txt-lg);
  font-weight: var(--peso-forte);
  letter-spacing: -.01em;
}
/* ⚠️ Os dois números viraram uma linha de apoio, não dois cartões: eles
   informam, e o que decide a atenção é a lista abaixo. */
.lista__placar {
  /* Linha inteira: o placar é apoio do título, não vizinho dele. */
  flex-basis: 100%;
  margin-top: 2px;
  font-size: var(--txt-sm);
  color: var(--texto-apagado);
}
.lista__pede { color: var(--aviso); font-weight: var(--peso-medio); }

/* ⚠️ A BUSCA NÃO ESTÁ DENTRO DO TOPO -- ela é o `.cartao__corpo` seguinte, e
   uma regra `.lista__topo .busca` não pegaria nada. A auditoria pegou; o
   ajuste vai onde ela de fato mora, e o padding de baixo é menor porque a
   lista começa logo abaixo. */
.coluna > .cartao__corpo { padding: var(--e-3) var(--e-4); }

/* 🚨 A COLUNA DA CONVERSA VIRA UMA PILHA COM ALTURA, e o fio ocupa o que
   sobra. Apontado por ele em 26/08: o fio tinha `max-height: 52vh` fixo, então
   metade da tela ficava vazia embaixo enquanto a conversa rolava numa
   janelinha. Altura fixa em `vh` é chute sobre o monitor de quem usa.

   ⚠️ `max-height`, NÃO `height`: conversa curta continua sendo um cartão
   curto, sem um vão cinza embaixo. O `calc` desconta o cabeçalho da tela e as
   margens; o `min` impede que num monitor muito alto o fio fique maior do que
   se lê de uma vez. */
/* ⚠️ O `max-height` em `vh` SAIU. Ele existia porque a tela era uma página que
   rolava; agora a coluna ocupa exatamente a altura disponível e quem rola é o
   fio, por dentro. Altura em `vh` era chute sobre o monitor de quem usa. */
.coluna--larga {
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--fundo);
}

/* A mesma regra da outra coluna: ninguém cresce, exceto a lista. Aqui os
   filhos são o topo, a busca, e então a lista (ou "carregando", ou o vazio). */
.coluna > * { flex: none; }
.coluna > .conversas,
.coluna > .vazio { flex: 1 1 auto; min-height: 0; }

/* Pelo mesmo motivo, a lista rola inteira em vez de parar em 60vh. */
.conversas {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
}

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

/* 🚨 A MARGEM CARREGA UM SIGNIFICADO SÓ: conversa direta × grupo.
   É o fichário que o usuário pediu em 25/08 -- "para sabermos qual é".
   Duas leituras na mesma faixa é a faixa não querer dizer nada, e por isso
   "não identificado" e "concluída" continuam como CHIP, não como cor de
   borda. Os tokens são os do sistema: nenhum valor de cor escrito aqui. */
.conversa {
  display: flex;
  align-items: flex-start;
  gap: var(--e-3);
  flex: 1 1 auto;
  min-width: 0;
  text-align: left;
  background: none;
  border: 0;
  border-left: 4px solid var(--acento);
  padding: var(--e-3);
  cursor: pointer;
  font-family: var(--fonte);
}
.conversa--grupo { border-left-color: var(--ok); }

/* `min-width: 0` é o que permite o texto TRUNCAR dentro do flex: sem ele o
   item cresce e a hora sai da coluna. */
.conversa__corpo { flex: 1 1 auto; min-width: 0; display: block; }

/* ⚠️ 44px, não 36 (27/08). É o mesmo número do alvo de toque (`--altura-toque`)
   e o que dá presença à lista sem trocar a densidade: a linha já tinha essa
   altura por causa das duas linhas de texto. */
.conversa__avatar {
  flex: none;
  width: var(--altura-toque);
  height: var(--altura-toque);
  border-radius: var(--r-full);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: var(--txt-sm);
  font-weight: var(--peso-forte);
  letter-spacing: .02em;
}
.conversa__avatar--grupo {
  background: var(--superficie-3);
  color: var(--texto-fraco);
}

.conversa__hora { flex: none; white-space: nowrap; }

/* 🚨 UMA LINHA SÓ, COM RETICÊNCIAS. A prévia com duas linhas fazia o item
   pular de altura conforme o texto -- e uma lista que muda de ritmo é mais
   difícil de varrer do que uma lista densa. */
.conversa__quem,
.conversa__previa {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conversa__marcas {
  display: flex;
  gap: var(--e-1);
  flex-wrap: wrap;
  margin-top: 2px;
}
.conversa__marcas:empty { display: none; }
.conversa:hover { background: rgba(128, 128, 128, .08); }
.conversa--aberta { background: rgba(128, 128, 128, .14); }

/* ---- filtro dentro do campo de busca ------------------------------------
   O popover ancora no botão do funil. `position: relative` no pai é o que
   segura o `absolute` do painel; sem ele, ele iria para o canto da tela. */
.filtro { position: relative; flex: none; }

.botao--filtrando {
  border-color: var(--acento);
  color: var(--acento);
  background: var(--acento-suave);
}

/* O contador no canto do funil: diz QUE há filtro sem abrir o painel. */
.filtro__conta {
  position: absolute;
  top: -6px;
  right: -6px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: var(--r-full);
  background: var(--acento);
  color: var(--acento-texto);
  font-size: var(--txt-xs);
  line-height: 16px;
  text-align: center;
}

.filtro__caixa {
  position: absolute;
  top: calc(100% + var(--e-1));
  right: 0;
  z-index: var(--z-flutuante);
  min-width: 220px;
  padding: var(--e-3);
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-lg);
  box-shadow: var(--sombra-2);
}
.filtro__titulo {
  margin: 0 0 var(--e-2);
  font-size: var(--txt-sm);
  font-weight: var(--peso-forte);
  color: var(--texto-fraco);
}
.filtro__linha {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  padding: var(--e-1) 0;
  cursor: pointer;
}
.filtro__limpar { margin-top: var(--e-2); padding-left: 0; }
.filtro__resumo {
  display: inline-flex;
  align-items: center;
  gap: var(--e-1);
  color: var(--acento);
}

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
  /* 🚨 A MESMA MARGEM LATERAL DO COMPOSITOR. O fio usava `--e-3` e o campo de
     escrever vive dentro de `.cartao__corpo`, que usa `--e-4`: 4px de
     diferença de cada lado, e o campo aparecia mais estreito que as mensagens.
     Apontado por ele em 26/08. Alinhar é usar o mesmo token, não somar um
     ajuste -- valor escolhido a olho volta a desalinhar na próxima mudança. */
  /* ⚠️ MARGEM LATERAL MAIOR QUE A VERTICAL (27/08, do mockup escolhido). O
     balão tem no máximo 66% da largura; sem margem generosa nas laterais ele
     encosta na borda e a conversa perde o ar que o desenho tem. */
  padding: var(--e-4) var(--e-7);
  /* Ocupa o que sobra da coluna em vez de um `vh` fixo. `min-height: 0` é o
     que permite o filho de um flex ENCOLHER e rolar; sem ele o fio empurra o
     compositor para fora da tela em conversa longa. */
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  /* Balão já quebra palavra; barra horizontal aqui só apareceria por acidente
     de conteúdo largo, e rolar a conversa de lado não serve para nada. */
  overflow-x: hidden;

  /* 🚨 O PAPEL DA CONVERSA (27/08, escolha dele entre cinco desenhos). A
     textura é o que o olho reconhece antes de ler: quem atende passa o dia no
     WhatsApp, e a semelhança vale treinamento.

     ⚠️ PADRÃO EM SVG EMBUTIDO, não arquivo: sem requisição, sem asset para
     versionar, e some junto com o CSS se um dia isto mudar. */
  background-color: var(--conversa-fundo);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='52' height='52' viewBox='0 0 52 52'%3E%3Cg fill='%23000' fill-opacity='.028'%3E%3Ccircle cx='9' cy='9' r='1.6'/%3E%3Ccircle cx='35' cy='22' r='1.2'/%3E%3Ccircle cx='20' cy='40' r='1.4'/%3E%3Ccircle cx='45' cy='47' r='1'/%3E%3C/g%3E%3C/svg%3E");
  gap: 3px;
}

/* ---- o balão ------------------------------------------------------------
   🚨 ELE TINHA ESCAPADO DO SISTEMA, e é a peça mais vista do painel: usava
   `var(--raio, 12px)` -- token que NUNCA EXISTIU, então caía no valor de
   emergência -- e três `rgba()` escritos à mão, fora da paleta. Agora cada
   valor é token, e o token está documentado no `tokens.css`. */
.balao {
  position: relative;
  max-width: min(66%, 520px);
  padding: 7px 11px 6px;
  border-radius: var(--conversa-raio);
  background: var(--conversa-balao);
  box-shadow: var(--sombra-1);
  line-height: 1.5;
}

/* 🚨 O BICO. É o detalhe que faz a tela ser reconhecida de longe, e ele é
   feito com borda -- nenhuma imagem, nenhum pseudo-elemento posicionado a
   olho. O canto do lado do bico perde o raio: é o que encaixa os dois. */
.balao--entrada { align-self: flex-start; border-top-left-radius: 0; }
.balao--entrada::before {
  content: "";
  position: absolute;
  left: calc(var(--conversa-bico) * -1);
  top: 0;
  border: var(--conversa-bico) solid transparent;
  border-left: 0;
  border-right-color: var(--conversa-balao);
  border-top-color: var(--conversa-balao);
}

.balao--saida {
  align-self: flex-end;
  background: var(--conversa-saida);
  border-top-right-radius: 0;
}
.balao--saida::before {
  content: "";
  position: absolute;
  right: calc(var(--conversa-bico) * -1);
  top: 0;
  border: var(--conversa-bico) solid transparent;
  border-right: 0;
  border-left-color: var(--conversa-saida);
  border-top-color: var(--conversa-saida);
}

/* ⚠️ A NOTA INTERNA NÃO TEM BICO, e isso é significado: ela não veio de
   ninguém e não vai para o cliente. Fica centrada, em papel próprio. */
.balao--interna {
  align-self: center;
  max-width: min(70%, 460px);
  background: var(--conversa-nota);
  color: var(--conversa-nota-texto);
  text-align: center;
  font-size: var(--txt-sm);
  font-style: normal;
}
.balao--interna::before { display: none; }

.balao__texto { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.balao__tipo { margin: 0 0 var(--e-1); }

/* ⚠️ HORA À DIREITA, sempre -- inclusive no balão de entrada. É onde o olho
   já procura, e alinhar à esquerda faria a hora competir com o texto. */
.balao__rodape {
  margin: 2px 0 0;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
/* O segundo tique só existe quando a mensagem foi lida. */
.balao__tique { margin-left: 3px; letter-spacing: -2px; }
.balao__lida { color: var(--conversa-lida); font-weight: var(--peso-forte); }

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

/* ---- placar do cabeçalho -------------------------------------------------
   Número grande + rótulo pequeno: dois números com hierarquia leem-se de
   relance; quatro chips iguais obrigam a ler todos. */
.placar { display: flex; gap: var(--e-5); }
.placar__item { display: flex; flex-direction: column; line-height: 1.1; }
.placar__numero { font-size: var(--txt-xl); color: var(--texto); }
.placar__rotulo { font-size: var(--txt-sm); color: var(--texto-fraco); }
/* O que pede trabalho ganha cor. O resto fica neutro -- se tudo grita,
   nada grita. */
.placar__item--pede .placar__numero { color: var(--aviso); }

/* ---- controle segmentado -------------------------------------------------
   Uma escolha entre três, e não três ações. */
.abas {
  display: inline-flex;
  padding: 2px;
  background: var(--superficie-2);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-full);
}
.abas__aba {
  border: 0;
  background: none;
  padding: 5px var(--e-3);
  border-radius: var(--r-full);
  font-family: var(--fonte);
  font-size: var(--txt-sm);
  color: var(--texto-fraco);
  cursor: pointer;
}
.abas__aba:hover { color: var(--texto); }
.abas__aba--ativa {
  background: var(--superficie);
  color: var(--texto);
  font-weight: var(--peso-forte);
  box-shadow: var(--sombra-1);
}
.abas__aba:focus-visible { outline: none; box-shadow: var(--foco); }

.anteriores { display: flex; justify-content: center; padding: var(--e-2) 0; }

/* ---- chamar alguém com @, só em grupo (27/08) --------------------------- */
/* `position: relative` porque a lista do `@` se ancora no compositor. */
/* 🚨 A FAIXA CINZA ATRÁS DO COMPOSITOR. É ela que faz o campo branco virar
   uma ilha; sem o contraste, o compositor se dissolvia no fim do fio. */
/* 🚨 QUEM CRESCE É SÓ O FIO. A coluna da conversa tem NOVE filhos diretos --
   barra do topo, acompanham, ações, aviso de ficha, gaveta, busca, fio e as
   três formas do rodapé. Num flex-column sem regra, vários deles crescem ou
   encolhem juntos, e foi isso que jogou a rolagem para o lugar errado.

   A regra é uma só e vale para todos: ninguém cresce, exceto o fio. */
.coluna--larga > * { flex: none; }
.coluna--larga > .baloes { flex: 1 1 auto; min-height: 0; }
/* Sem conversa escolhida, o vazio ocupa a coluna em vez de virar uma tira. */
.coluna--larga > .vazio {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

/* ⚠️ A GAVETA ROLA POR DENTRO. Ela é a ficha do cliente e pode ser mais alta
   que a tela; sem teto próprio, empurrava o fio e o compositor para fora. */
.coluna--larga > .gaveta { max-height: 42vh; overflow-y: auto; }

/* ⚠️ O `padding` SUBSTITUI o do `.cartao__corpo`, não soma com ele -- a
   auditoria pegou os dois empilhados, e o compositor ficava afundado.

   A faixa cinza vale para as TRÊS formas do rodapé (compositor, conversa
   resolvida, sem permissão): a barra de baixo não pode mudar de cor conforme
   o estado da conversa. */
.rodape-conversa,
.coluna--larga > .cartao__corpo.pilha,
.coluna--larga > p.cartao__corpo {
  background: var(--superficie-2);
  border-top: var(--borda-fina) solid var(--borda);
  padding: var(--e-3) var(--e-4) var(--e-4);
  margin: 0;
}

/* ---- o compositor (27/08) -----------------------------------------------
   🚨 O CAMPO É UMA ILHA BRANCA SOBRE FUNDO CINZA, e isso é a coisa que mais
   separa "campo de formulário" de "lugar de escrever mensagem". O fio tem
   papel próprio; sem o contraste aqui, o compositor sumia dentro do cartão. */
.compositor {
  position: relative;
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  /* 🚨 14px, não 8: no desenho escolhido o campo é uma ILHA arredondada sobre
     a faixa cinza, e é o raio que faz ela parecer lugar de escrever mensagem
     em vez de campo de formulário. */
  border-radius: 14px;
  transition: border-color var(--tempo) var(--curva),
              box-shadow var(--tempo) var(--curva);
}
.compositor:focus-within {
  border-color: var(--acento-borda);
  box-shadow: 0 0 0 3px var(--acento-suave);
}
/* O `.campo__entrada` de dentro perde a própria borda: quem desenha a caixa
   agora é o compositor inteiro, senão ficam duas molduras concêntricas. */
.compositor .campo__entrada {
  border: 0;
  background: none;
  box-shadow: none;
}
.compositor .campo__entrada:focus { box-shadow: none; outline: 0; }

/* A lista SOBE: o compositor mora no rodapé da conversa, e abaixo dele a
   lista sairia da tela. */
.arroba {
  position: absolute;
  bottom: calc(100% + var(--e-1));
  left: 0;
  z-index: var(--z-flutuante);
  min-width: 220px;
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

/* ---- ações do balão -----------------------------------------------------
   Aparecem no hover: três botões fixos em cada balão transformam o fio numa
   grade de botões, e o que se lê é a conversa. */
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
  /* 🚨 `opacity`, NÃO `display: none` (27/08). Medido: com `display:none` o
     bloco sai do fluxo de foco, então `:focus-within` NUNCA dispara -- a linha
     existia e era código morto, e reagir, citar e encaminhar eram
     inalcançáveis por teclado.

     ⚠️ `pointer-events` acompanha a opacidade: invisível não pode continuar
     clicável por acidente, senão vira alvo fantasma sobre o balão. */
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

.reacoes {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  display: flex;
  gap: 2px;
  padding: var(--e-1);
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-full);
  box-shadow: var(--sombra-2);
  z-index: var(--z-flutuante);
}
.reacoes__item {
  border: 0;
  background: none;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  padding: 3px;
  border-radius: var(--r-full);
}
.reacoes__item:hover { background: var(--superficie-2); transform: scale(1.15); }
.reacoes__item--nosso { background: var(--superficie-2); outline: 2px solid var(--acento); }

/* A reação pendurada no canto: dentro do balão viraria mais uma linha. */
.balao__reacao {
  position: absolute;
  bottom: -10px;
  left: var(--e-3);
  display: flex;
  gap: 3px;
  line-height: 1.4;
}
.balao__reacao-item {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 1px 5px;
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-full);
  font-size: var(--txt-sm);
}
/* A nossa fica marcada: sem isso, num balão com três reações ninguém sabe
   qual foi a sua — e clicar de novo tiraria a de outra pessoa na cabeça de
   quem clica. */
.balao__reacao-item--nosso { border-color: var(--acento); }
.balao__reacao-item em {
  font-style: normal;
  font-size: var(--txt-xs);
  color: var(--texto-apagado);
}
.balao__marca { color: var(--texto-apagado); display: flex; gap: 4px; align-items: center; }

.balao__imagem--clicavel { cursor: zoom-in; }

/* ---- citar --------------------------------------------------------------- */
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

/* ---- gravação ------------------------------------------------------------ */
.gravando {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  color: var(--erro);
  font-size: var(--txt-sm);
  font-variant-numeric: tabular-nums;
}
.gravando__ponto {
  width: 9px;
  height: 9px;
  border-radius: var(--r-full);
  background: var(--erro);
  animation: pulsa 1.2s infinite;
}
@keyframes pulsa { 50% { opacity: .25; } }

/* ---- tela cheia ---------------------------------------------------------- */
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

/* Separador de dia: linha fina atravessando, com o rótulo no meio. É o padrão
   que todo mensageiro usa, e por isso ninguém precisa aprender. */
.diario {
  display: flex;
  align-items: center;
  gap: var(--e-3);
  margin: var(--e-4) 0 var(--e-2);
  color: var(--texto-apagado);
  font-size: var(--txt-sm);
}
.diario::before,
.diario::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--borda);
}
.diario__marca { flex: none; text-transform: lowercase; }

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
/* ⚠️ `--aviso-borda`, nao um ambar escrito a mao: a trava de estilo
   pegou este aqui em 27/08, junto com as tres cores do balao. */
.balao--casa { outline: 1px solid var(--aviso-borda); }
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
