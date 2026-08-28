<script setup>
/* ============================================================================
   EML_1.1 — E-mail
   ----------------------------------------------------------------------------
   🚨 NUNCA SE MISTURA COM O WHATSAPP (decisão do usuário em 10/08). Caixa
   própria, marcadores próprios, tela própria. Nada aqui entra na caixa de
   entrada de conversas, e vice-versa.

   Ela mora no MoviZap por dois motivos: atender, e SOMAR CADASTRO -- o
   remetente identifica a empresa, e 788 dos 944 clientes ativos já têm e-mail
   no cadastro. 442 deles não têm WhatsApp alcançável: é aqui que se fala com
   quem o WhatsApp não alcança.

   ⚠️ ELA LÊ E RESPONDE (atualizado em 28/08). O `gmail.send` já está em
   `google_auth.ESCOPO_CAIXA`, e a tela tem Responder, Encaminhar e o atalho
   `r`. Este comentário dizia "em construção... responder exige o escopo
   gmail.send" muito depois de o escopo ter entrado -- e a tela repetia isso
   para o usuário, em texto fixo no cabeçalho.
   ============================================================================ */
import { ref, computed, onMounted, onUnmounted } from 'vue'

import { api, pedirBlob, ErroDeApi } from '../api/cliente.js'
import { corDaInicial as corDe, iniciais as iniciaisDe } from '../util/avatar.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'
import { codigosPermitidos } from '../estado/sessao.js'

const marcadores = ref([])
const mensagens = ref([])
const aberta = ref(null)
const marcadorAtual = ref('INBOX')
const busca = ref('')
const carregando = ref(false)

/* O menu de pastas recolhe, como no Gmail. Fica guardado porque quem recolhe
   quer que continue recolhido amanhã -- e não é preferência que valha uma
   coluna no banco. */
const menuAberto = ref(localStorage.getItem('movizap.email.menu') !== 'fechado')
/* ⚠️ SÓ LEITURA HOJE. O escopo concedido é `gmail.readonly`: escrever exige
   outro consentimento. Os botões aparecem para a tela ser a tela final, e
   dizem por que não funcionam -- em vez de sumirem e a pessoa procurar. */
/* ---- escrever -------------------------------------------------------------
   🚨 UMA MENSAGEM POR VEZ, de propósito. Não existe campo de lista nem rota
   que receba vários destinatários: e-mail enviado não volta, e disparo é
   outro produto -- a mesma regra que já vale no WhatsApp. */
const escrevendo = ref(false)
const rascunho = ref({ para: '', cc: '', cco: '', assunto: '', corpo: '', responder_a: null })
/* Cc e Cco começam escondidos, como no Gmail: a maioria dos e-mails não usa,
   e dois campos vazios a mais atrapalham quem só quer responder. */
const mostrarCopias = ref(false)
const editor = ref(null)
const anexos = ref([])
const subindo = ref(false)

async function anexar(evento) {
  const arquivos = Array.from(evento.target.files || [])
  subindo.value = true
  for (const f of arquivos) {
    const dados = new FormData()
    dados.append('arquivo', f)
    try {
      /* Sobe direto por fetch: `api.post` manda JSON, e FormData precisa que
         o navegador monte o `boundary` sozinho -- definir Content-Type à mão
         quebra o upload de um jeito que só aparece no servidor. */
      const r = await fetch('/api/email/anexo', {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('movizap.token')}` },
        body: dados,
      })
      if (!r.ok) throw new Error()
      anexos.value.push(await r.json())
    } catch {
      erro.value = `Não consegui subir ${f.name}.`
    }
  }
  subindo.value = false
  evento.target.value = ''
}

function tirarAnexo(id) {
  anexos.value = anexos.value.filter((a) => a.id !== id)
}

function tamanho(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

/* ⚠️ `execCommand` está marcado como obsoleto há anos, mas funciona em todos
   os navegadores atuais e não tem substituto padronizado -- o `Editing API`
   nunca saiu do papel. A alternativa seria uma biblioteca de editor, que
   sozinha pesa mais que todo o nosso bundle. Quando quebrar, troca-se. */
function formatar(comando, valor = null) {
  document.execCommand(comando, false, valor)
  editor.value?.focus()
}

function inserirLink() {
  const url = prompt('Endereço do link:')
  if (url) formatar('createLink', url)
}

/* O que vai no envio: HTML do editor + versão em texto, na mesma mensagem.
   Quem lê sem HTML recebe o texto; ninguém recebe tag crua. */
function corpoDoEditor() {
  const el = editor.value
  if (!el) return { html: '', texto: rascunho.value.corpo || '' }
  return { html: el.innerHTML, texto: el.innerText }
}

const FERRAMENTAS = [
  { i: 'bi-type-bold', c: 'bold', t: 'Negrito' },
  { i: 'bi-type-italic', c: 'italic', t: 'Itálico' },
  { i: 'bi-type-underline', c: 'underline', t: 'Sublinhado' },
  { sep: true },
  { i: 'bi-list-ul', c: 'insertUnorderedList', t: 'Lista' },
  { i: 'bi-list-ol', c: 'insertOrderedList', t: 'Lista numerada' },
  { sep: true },
  { i: 'bi-text-left', c: 'justifyLeft', t: 'Alinhar à esquerda' },
  { i: 'bi-text-center', c: 'justifyCenter', t: 'Centralizar' },
  { i: 'bi-text-right', c: 'justifyRight', t: 'Alinhar à direita' },
  { sep: true },
  { i: 'bi-quote', c: 'formatBlock', v: 'blockquote', t: 'Citação' },
  { i: 'bi-eraser', c: 'removeFormat', t: 'Limpar formatação' },
]
const enviando = ref(false)

function novaMensagem() {
  rascunho.value = { para: '', cc: '', cco: '', assunto: '', corpo: '', responder_a: null }
  mostrarCopias.value = false
  escrevendo.value = true
}

function responder(encaminhar = false) {
  if (!aberta.value) return
  const a = aberta.value
  mostrarCopias.value = false
  rascunho.value = {
    cc: '', cco: '',
    para: encaminhar ? '' : (a.remetente || ''),
    assunto: (encaminhar ? 'Enc: ' : 'Re: ') + (a.assunto || '').replace(/^(Re|Enc):\s*/i, ''),
    corpo: `\n\n--- Em ${new Date(a.enviado_em).toLocaleString('pt-BR')}, ${a.remetente} escreveu:\n${a.texto || ''}`,
    // Só a resposta encaixa na conversa existente; encaminhar abre fio novo.
    responder_a: encaminhar ? null : a.id,
  }
  escrevendo.value = true
}

async function mandar() {
  enviando.value = true
  erro.value = ''
  try {
    const c = corpoDoEditor()
    await api.post('/api/email/enviar',
                   { ...rascunho.value, corpo: c.texto, html: c.html,
                     conta_id: contaAtual.value,
                     anexos: anexos.value.map((a) => a.id) })
    anexos.value = []
    recado.value = 'Enviado.'
    escrevendo.value = false
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui enviar.'
  } finally {
    enviando.value = false
  }
}

/* ---- vincular ao cadastro -------------------------------------------------
   🚨 É O OBJETIVO: o e-mail existir aqui para SOMAR CADASTRO. Sem isto o
   painel identifica só quem casa sozinho e o resto morre como mensagem. */
const buscaEmpresa = ref('')
const achados = ref([])

async function procurarEmpresa() {
  if (buscaEmpresa.value.trim().length < 2) { achados.value = []; return }
  try {
    const r = await api.get(
      `/api/conversas/buscar-empresa?termo=${encodeURIComponent(buscaEmpresa.value)}`)
    achados.value = r.itens || []
  } catch { achados.value = [] }
}

async function vincular(clienteId) {
  try {
    const r = await api.post(`/api/email/mensagens/${aberta.value.id}/vincular`,
                             { cliente_id: clienteId })
    recado.value = `Vinculado a ${r.cliente} — ${r.mensagens} mensagem(ns) deste remetente.`
    buscaEmpresa.value = ''
    achados.value = []
    await abrir(aberta.value.id)
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui vincular.'
  }
}

/* ---- assinatura ----------------------------------------------------------
   🚨 A IMAGEM VOLTOU PARA A TELA EM 27/08. Ele perguntou onde ela tinha ido
   parar; o backend estava inteiro desde a migração 017 -- a rota de subir, a
   de tirar, a pasta por atendente e o `enviar._assinatura()` que embute o
   arquivo por CID. **Faltava só o controle aqui**, e sem ele o recurso existia
   e ninguém podia usar.

   ⚠️ A IMAGEM NÃO SUBSTITUI O HTML: o e-mail sai com os dois. O HTML é o texto
   (nome, cargo, telefone); a imagem é o logo. */
const assinatura = ref('')
const editandoAssinatura = ref(false)
const temImagem = ref(false)
const imagemNome = ref('')

async function carregarAssinatura() {
  try {
    const r = await api.get('/api/eu/assinatura')
    assinatura.value = r.html || ''
    temImagem.value = Boolean(r.tem_imagem)
    imagemNome.value = r.imagem_nome || ''
  } catch {}
}
async function salvarAssinatura() {
  await api.put('/api/eu/assinatura', { html: assinatura.value })
  editandoAssinatura.value = false
  recado.value = 'Assinatura salva.'
}

/* ⚠️ NÃO passa pelo `api.post`, que serializa JSON. Arquivo vai por `FormData`,
   e aí o navegador monta o `Content-Type` com o boundary sozinho -- definir o
   cabeçalho na mão quebra o upload em silêncio, com o servidor recebendo corpo
   vazio. Mesma armadilha do anexo da conversa. */
async function subirImagem(evento) {
  const arquivo = evento.target.files && evento.target.files[0]
  evento.target.value = ''            // deixa reenviar o mesmo arquivo
  if (!arquivo) return
  erro.value = ''
  const corpo = new FormData()
  corpo.append('arquivo', arquivo)
  try {
    /* Mesmo caminho do anexo, logo acima: `fetch` direto para o navegador
       montar o `boundary`. */
    const r = await fetch('/api/eu/assinatura/imagem', {
      method: 'POST',
      headers: { Authorization: `Bearer ${localStorage.getItem('movizap.token')}` },
      body: corpo,
    })
    if (!r.ok) {
      /* O backend recusa com motivo (não é imagem, passa de 2 MB, conta sem
         linha em `atendente`) -- mostrar "não consegui" perderia o porquê. */
      const detalhe = await r.json().catch(() => ({}))
      throw new ErroDeApi(detalhe.detail || 'O servidor recusou a imagem.', r.status, '')
    }
    /* 🚨 RELÊ EM VEZ DE CONFIAR NO 200. O backend confere o disco antes de
       dizer que a imagem existe -- é ele quem sabe se ela vale. */
    await carregarAssinatura()
    recado.value = 'Imagem da assinatura salva.'
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui subir a imagem.'
  }
}

async function tirarImagem() {
  if (!confirm('Tirar a imagem da assinatura?\n\nO texto continua como está.')) return
  try {
    await api.del('/api/eu/assinatura/imagem')
    await carregarAssinatura()
    recado.value = 'Imagem removida.'
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui tirar a imagem.'
  }
}

function alternarMenu() {
  menuAberto.value = !menuAberto.value
  localStorage.setItem('movizap.email.menu', menuAberto.value ? 'aberto' : 'fechado')
}
const erro = ref('')
const recado = ref('')

/* ---- anexo recebido ------------------------------------------------------
   Os bytes ficam no Google e são buscados no clique. Ver `gmail.anexo`.

   ⚠️ NÃO DÁ PARA USAR <a href="/api/...">: o token vive no cabeçalho
   Authorization e o navegador não manda cabeçalho em navegação -- o download
   voltaria 401 e o atendente veria uma página de erro sem explicação. Por isso
   o binário vem por `pedirBlob` e vira object URL. É a mesma razão pela qual a
   mídia do WhatsApp não usa <img src>. */
const baixando = ref(null)

// `tamanho()` já existe acima, usada pelo anexo de RASCUNHO. Reaproveitada.

async function baixarAnexo(indice, anexo) {
  if (baixando.value !== null) return
  baixando.value = indice
  erro.value = ''
  try {
    const blob = await pedirBlob(
      `/api/email/mensagens/${aberta.value.id}/anexo/${indice}`)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = anexo.nome || `anexo-${indice}`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui baixar.'
  } finally {
    baixando.value = null
  }
}

/* 🚨 A API do Gmail devolve identificador interno: `INBOX`, `CATEGORY_UPDATES`,
   `UNREAD`. Ninguém que abre uma caixa de e-mail deveria descobrir que existe
   uma API por trás -- aqui eles viram nome de gente. */
const NOMES = {
  INBOX: 'Caixa de entrada',
  SENT: 'Enviados',
  STARRED: 'Com estrela',
  IMPORTANT: 'Importantes',
  UNREAD: 'Não lidas',
}

/* Lixo, rascunho e as CATEGORIAS internas do Gmail não aparecem: são
   classificação automática dele, não organização de quem atende.

   🚨 AS ESTRELAS COLORIDAS TAMBÉM SAEM (27/08). O Gmail tem 12 marcadores de
   estrela — `YELLOW_STAR`, `RED_STAR`, `BLUE_INFO`… — e todos significam a
   MESMA lista que o `STARRED` já mostra como "Com estrela". Ele viu o
   `YELLOW_STAR` cru na tela e pediu o nome legível; mas dois itens chamados
   "Com estrela" seriam pior que um id feio. Fica o `STARRED`, que é o que o
   Gmail chama de "Com estrela" na barra lateral dele. */
const ESTRELAS_DO_GMAIL = [
  'YELLOW_STAR', 'ORANGE_STAR', 'RED_STAR', 'PURPLE_STAR', 'BLUE_STAR',
  'GREEN_STAR', 'YELLOW_BANG', 'ORANGE_GUILLEMET', 'RED_BANG',
  'PURPLE_QUESTION', 'BLUE_INFO', 'GREEN_CHECK',
]
const ESCONDIDOS = ['SPAM', 'TRASH', 'CHAT', 'DRAFT', ...ESTRELAS_DO_GMAIL]

function rotulo(m) {
  return NOMES[m.id_externo] || m.nome
}

const visiveis = computed(() =>
  marcadores.value
    .filter((m) => !ESCONDIDOS.includes(m.id_externo))
    .filter((m) => !m.id_externo.startsWith('CATEGORY_'))
    .sort((a, b) => {
      // Caixa de entrada e Enviados primeiro; os seus marcadores depois.
      const ordem = ['INBOX', 'SENT', 'STARRED', 'IMPORTANT', 'UNREAD']
      const ia = ordem.indexOf(a.id_externo)
      const ib = ordem.indexOf(b.id_externo)
      if (ia !== ib) return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib)
      return rotulo(a).localeCompare(rotulo(b))
    }),
)

/* 🚨 AS DUAS FUNÇÕES SAÍRAM DAQUI EM 25/08. Viviam neste arquivo, e quando a
   caixa de entrada precisou do mesmo avatar, copiar teria criado duas versões
   da mesma regra. Agora vivem em `util/avatar.js` e recebem o NOME, não a
   mensagem -- assim servem contato, atendente e remetente sem saber o que
   cada tela chama de quê. */
function iniciais(m) {
  return iniciaisDe(m.remetente_nome || m.remetente)
}

function corDaInicial(m) {
  return corDe(m.remetente || m.remetente_nome)
}

/* ---- as caixas de quem está logado --------------------------------------
   🚨 QUEM NÃO CONECTOU CAIXA NENHUMA PRECISA SABER DISSO. Desde a migração
   030 a tela só mostra as caixas de quem entrou -- antes mostrava a do owner
   para qualquer um. Sem esta verificação, a pessoa nova abriria uma tela
   silenciosamente vazia e concluiria que o e-mail está quebrado. */
const caixas = ref([])

/* ---- seleção e estrela (25/08) -------------------------------------------
   Pedido do usuário: *"o recurso de 'estrela' do gmail não poderíamos ter?
   selecionar, botão de leitura de e-mails, etc"*. Nada disto pediu
   consentimento novo -- o escopo já é `gmail.modify`. */
/* ---- qual caixa está em uso (25/08) --------------------------------------
   🚨 A CAIXA ATIVA PRECISA SER ÓBVIA, e foi o que o usuário pediu com todas
   as letras: *"só precisa ficar evidente qual é a que estão usando"*. Cada
   atendente vê as caixas que ELE conectou (migração 030) -- a dele e, por
   exemplo, o `sac@` numa segunda aba.

   ⚠️ `conta_id` vai em TODA leitura e no envio. O backend recusa envio sem
   caixa escolhida quando há mais de uma: "pega a primeira" era o defeito que
   mandaria o e-mail pelo endereço errado, calado. */
const contaAtual = ref(null)

const caixaAtiva = computed(
  () => caixas.value.find((c) => c.id === contaAtual.value) || null,
)

/* A cor é derivada do endereço: a mesma caixa tem a mesma faixa todo dia, e é
   ela que o olho usa para saber onde está antes de ler o endereço. */
function corDaCaixa(conta) {
  return corDe(conta.endereco)
}

async function trocarCaixa(id) {
  if (contaAtual.value === id) return
  contaAtual.value = id
  localStorage.setItem('movizap.email.caixa', String(id))
  aberta.value = null
  marcadas.value = []
  marcadorAtual.value = 'INBOX'
  await carregarMarcadores()
  await carregar()
}

const marcadas = ref([])
const aplicandoLote = ref(false)

function alternarMarcada(id) {
  marcadas.value = marcadas.value.includes(id)
    ? marcadas.value.filter((m) => m !== id)
    : [...marcadas.value, id]
}

const todasMarcadas = computed(
  () => mensagens.value.length > 0
    && mensagens.value.every((m) => marcadas.value.includes(m.id)),
)

function alternarTodas() {
  marcadas.value = todasMarcadas.value ? [] : mensagens.value.map((m) => m.id)
}

async function alternarEstrela(m) {
  /* ⚠️ Vira na tela ANTES da resposta: estrela é clique de meio segundo, e
     esperar o Gmail para o ícone mudar faz a pessoa clicar de novo. Se falhar,
     desfaz e diz. */
  const antes = m.estrela
  m.estrela = !antes
  try {
    await api.post(`/api/email/mensagens/${m.id}/estrela?ligada=${!antes}`)

    /* 🚨 DENTRO DE "COM ESTRELA", TIRAR A ESTRELA TIRA DA LISTA (27/08).
       Ele viu e apontou: *"tirar estrela não removeu ele da lista"*. A lista
       é o marcador aberto; uma mensagem sem estrela dentro de "Com estrela"
       é uma mensagem que não pertence mais àquela lista, e deixá-la ali é a
       tela contradizendo o próprio título.

       ⚠️ SÓ NESTA LISTA. Na caixa de entrada, tirar a estrela não muda nada
       sobre estar na caixa -- remover ali faria a mensagem sumir por um
       motivo que não tem nada a ver com o lugar onde ela está. */
    if (marcadorAtual.value === 'STARRED' && !m.estrela) {
      mensagens.value = mensagens.value.filter((x) => x.id !== m.id)
      marcadas.value = marcadas.value.filter((id) => id !== m.id)
      // A que estava aberta saiu junto: mostrá-la sem estar na lista deixaria
      // a leitura apontando para algo que a coluna já não tem.
      if (aberta.value && aberta.value.id === m.id) aberta.value = null
    }
  } catch (e) {
    m.estrela = antes
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui mexer na estrela.'
  }
}

async function lote(acao) {
  if (!marcadas.value.length) return
  aplicandoLote.value = true
  erro.value = ''
  try {
    const r = await api.post('/api/email/lote',
                             { ids: marcadas.value, acao })
    recado.value = r.falhas
      ? `${r.feitas} de ${r.pedidas} — ${r.falhas} não deu.`
      : `${r.feitas} mensagem(ns).`
    marcadas.value = []
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui aplicar.'
  } finally {
    aplicandoLote.value = false
  }
}

async function carregarCaixas() {
  try {
    caixas.value = (await api.get('/api/email/caixas')).caixas || []
    /* ⚠️ Guarda qual estava aberta: quem trabalha no `sac@` o dia inteiro não
       quer voltar para a caixa pessoal a cada F5. Se a caixa guardada sumiu
       (foi desconectada), cai na primeira em vez de ficar em nenhuma. */
    const guardada = Number(localStorage.getItem('movizap.email.caixa') || 0)
    const existe = caixas.value.some((c) => c.id === guardada)
    contaAtual.value = existe ? guardada : (caixas.value[0]?.id ?? null)
  } catch {
    caixas.value = []
    contaAtual.value = null
  }
}

async function carregarMarcadores() {
  try {
    const q = contaAtual.value ? `?conta_id=${contaAtual.value}` : ''
    marcadores.value = (await api.get(`/api/email/marcadores${q}`)).marcadores || []
  } catch {
    marcadores.value = []
  }
}

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    const q = new URLSearchParams({ marcador: marcadorAtual.value, busca: busca.value })
    if (contaAtual.value) q.set('conta_id', String(contaAtual.value))
    mensagens.value = (await api.get(`/api/email/mensagens?${q}`)).mensagens || []
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui ler a caixa.'
  } finally {
    carregando.value = false
  }
}

/* ---- o fio da conversa (25/08) -------------------------------------------
   🚨 `thread_externa` É COLUNA DESDE A MIGRAÇÃO 014 E NUNCA FOI USADA. Uma
   troca de seis e-mails virava seis linhas idênticas na lista, sem ninguém
   saber que eram a mesma conversa -- e responder a mensagem errada de um fio
   é como se perde contexto com o cliente. */
const fio = ref([])

async function carregarFio() {
  if (!aberta.value?.thread_externa) { fio.value = []; return }
  try {
    const r = await api.get(
      `/api/email/fio?thread=${encodeURIComponent(aberta.value.thread_externa)}`)
    fio.value = r.mensagens || []
  } catch { fio.value = [] }
}

/* ---- ações da mensagem aberta -------------------------------------------- */
async function marcarNaoLida(m) {
  try {
    await api.post(`/api/email/mensagens/${m.id}/nao-lida`, {})
    const naLista = mensagens.value.find((x) => x.id === m.id)
    if (naLista) naLista.lida = false
    recado.value = 'Marcada como não lida.'
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui marcar.'
  }
}

async function arquivarAberta() {
  if (!aberta.value) return
  const id = aberta.value.id
  try {
    await api.post('/api/email/lote', { ids: [id], acao: 'arquivar' })
    aberta.value = null
    await carregar()
    recado.value = 'Arquivada — saiu da caixa aqui e no Gmail.'
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui arquivar.'
  }
}

/* ---- atalhos de teclado --------------------------------------------------
   🚨 CAIXA DE E-MAIL SEM ATALHO OBRIGA O MOUSE PARA TUDO, e quem passa o dia
   nela sente isso em toda mensagem. São os mesmos do Gmail: quem vem de lá
   não reaprende.

   ⚠️ NUNCA DENTRO DE CAMPO DE TEXTO. Sem esta guarda, escrever "responder"
   num e-mail dispararia `r`, `e`, `s`... e a pessoa perderia o que digitou. */
function atalho(evento) {
  const alvo = evento.target
  const digitando = alvo?.isContentEditable
    || ['INPUT', 'TEXTAREA', 'SELECT'].includes(alvo?.tagName)
  if (digitando || evento.ctrlKey || evento.metaKey || evento.altKey) return
  if (escrevendo.value) return

  const ordem = mensagens.value
  const atual = ordem.findIndex((m) => aberta.value && m.id === aberta.value.id)

  if (evento.key === 'j' || evento.key === 'k') {
    evento.preventDefault()
    const passo = evento.key === 'j' ? 1 : -1
    const proximo = ordem[Math.min(Math.max(atual + passo, 0), ordem.length - 1)]
    if (proximo) abrir(proximo.id)
    return
  }
  if (!aberta.value) return
  if (evento.key === 'r') { evento.preventDefault(); responder(false) }
  if (evento.key === 'e') { evento.preventDefault(); arquivarAberta() }
  if (evento.key === 'u') { evento.preventDefault(); marcarNaoLida(aberta.value) }
  if (evento.key === 's') {
    evento.preventDefault()
    const naLista = mensagens.value.find((m) => m.id === aberta.value.id)
    if (naLista) alternarEstrela(naLista)
  }
}

async function abrir(id) {
  try {
    aberta.value = await api.get(`/api/email/mensagens/${id}`)
    carregarFio()
    /* Marca lida no Gmail, não só aqui. Falha em silêncio: não conseguir
       marcar não pode impedir a pessoa de LER a mensagem. */
    const naLista = mensagens.value.find((m) => m.id === id)
    if (naLista && !naLista.lida) {
      naLista.lida = true
      api.post(`/api/email/mensagens/${id}/lida`, {}).catch(() => {})
    }
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui abrir.'
  }
}

async function buscarNovos() {
  recado.value = 'buscando no Gmail…'
  try {
    const r = await api.post('/api/email/ler', {})
    recado.value = `${r.novas} nova(s), ${r.repetidas} já tínhamos.`
    await carregar()
  } catch (e) {
    recado.value = ''
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao buscar.'
  }
}

function trocar(id) {
  marcadorAtual.value = id
  aberta.value = null
  carregar()
}

function quando(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const hoje = new Date().toDateString() === d.toDateString()
  return hoje
    ? d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
}

const podeConectarCaixa = computed(() => codigosPermitidos.value.has('CFG_1.1'))
const conectando = ref(false)

/* ⚠️ Navega na MESMA aba, de propósito: o Google devolve para o nosso callback,
   e uma aba nova deixaria a original mostrando "nenhuma caixa" para sempre. */
async function conectarCaixa() {
  conectando.value = true
  try {
    const r = await api.get('/api/email/autorizar')
    window.location.href = r.url
  } catch (e) {
    conectando.value = false
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui abrir o Google.'
  }
}

onMounted(async () => {
  document.addEventListener('keydown', atalho)
  await carregarCaixas()
  await carregarMarcadores()
  await carregar()
  await carregarAssinatura()
})

onUnmounted(() => document.removeEventListener('keydown', atalho))
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1 class="tela__titulo">E-mail</h1>
        <!-- 🚨 A FRASE QUE ESTAVA AQUI ERA FALSA, não só comprida (28/08).
             Ela dizia "Por enquanto dá para ler e consultar. Responder pela
             tela vem em breve" -- e esta tela tem Responder, Encaminhar,
             atalho `r` e a rota /api/email/enviar no ar. O texto era verdade
             quando foi escrito e ninguém voltou para matá-lo quando o
             responder ficou pronto.

             ⚠️ A TRAVA QUE ISSO DEIXA: entrega de função nova inclui varrer o
             que a tela diz sobre si mesma. Tela que anuncia "vem em breve"
             ou recebe o recurso, ou perde a frase -- nunca as duas coisas
             convivendo, porque aí a tela mente sobre a própria capacidade. -->
        <AjudaDaTela>
          As caixas conectadas, com o cliente já vinculado na linha. Dá para
          ler, responder, encaminhar e arquivar sem sair daqui.
        </AjudaDaTela>
      </div>
      <div class="linha">
        <input v-model="busca" class="campo__entrada" type="search"
               placeholder="Buscar por assunto ou remetente" @keyup.enter="carregar" />
        <button class="botao botao--pequeno botao--contorno" type="button" @click="buscarNovos">
          <i class="bi bi-arrow-clockwise" aria-hidden="true"></i> Atualizar
        </button>
      </div>
    </header>

    <!-- 🚨 SEM CAIXA, A TELA EXPLICA em vez de ficar vazia. É o estado de
         quem entra no painel pela primeira vez: a caixa é de quem a conecta
         (migração 030), e conectar é ação do owner na CFG_1.1. -->
    <div v-if="!caixas.length" class="vazio">
      <i class="bi bi-envelope-x vazio__icone" aria-hidden="true"></i>
      <p class="vazio__titulo">Nenhuma caixa conectada à sua conta</p>
      <p>Peça ao administrador para conectar a sua caixa.</p>
      <!-- 🚨 O BOTÃO QUE FALTAVA (28/08). A rota existia com zero chamadores,
           e a única caixa da base foi conectada na mão. Só aparece para quem
           tem CFG_1.1, que é a permissão que a rota exige: mostrar para os
           outros seria oferecer um 403. -->
      <button v-if="podeConectarCaixa" class="botao botao--primario"
              type="button" :disabled="conectando" @click="conectarCaixa">
        <span v-if="conectando" class="girando"></span>
        <i v-else class="bi bi-google" aria-hidden="true"></i>
        Conectar minha caixa
      </button>
    </div>

    <p v-if="erro" class="aviso aviso--erro">{{ erro }}</p>
    <p v-if="recado" class="apagado pequeno">{{ recado }}</p>

    <!-- 🚨 ABAS DE CAIXA, como pasta de planilha (pedido do usuário em 25/08).
         O endereço INTEIRO fica visível na ativa -- abreviar "sac@..." é
         exatamente onde alguém responde pela caixa errada. A faixa de cor é
         derivada do endereço: a mesma caixa tem a mesma cor todo dia, e é ela
         que o olho usa antes de ler. -->
    <div v-if="caixas.length" class="caixas" role="tablist">
      <button
        v-for="cx in caixas"
        :key="cx.id"
        class="caixas__aba"
        :class="{ 'caixas__aba--ativa': cx.id === contaAtual }"
        type="button"
        role="tab"
        :aria-selected="cx.id === contaAtual"
        @click="trocarCaixa(cx.id)"
      >
        <span class="caixas__cor" :style="{ background: corDaCaixa(cx) }"
              aria-hidden="true"></span>
        {{ cx.endereco }}
      </button>
    </div>

    <!-- barra de orientação: onde estou, quantas há, e o que dá para fazer -->
    <div class="email__barra">
      <div class="linha">
        <button class="botao botao--pequeno botao--fantasma" type="button"
                :aria-expanded="menuAberto" title="Mostrar ou esconder as pastas"
                @click="alternarMenu">
          <i class="bi bi-list" aria-hidden="true"></i>
        </button>
        <strong>{{ NOMES[marcadorAtual] || marcadorAtual || 'Todas' }}</strong>
        <span class="apagado pequeno">{{ mensagens.length }} mensagens</span>
      </div>

      <div class="linha email__acoes">
        <button class="botao botao--pequeno botao--acento" type="button" @click="novaMensagem">
          <i class="bi bi-pencil-square" aria-hidden="true"></i> Nova mensagem
        </button>
        <span class="email__separador" aria-hidden="true"></span>
        <button class="botao botao--pequeno botao--fantasma" type="button"
                :disabled="!aberta"
                :title="aberta ? 'Responder (r)' : 'Abra uma mensagem primeiro'"
                @click="responder(false)">
          <i class="bi bi-reply" aria-hidden="true"></i> Responder
        </button>
        <button class="botao botao--pequeno botao--fantasma" type="button"
                :disabled="!aberta"
                :title="aberta ? 'Encaminhar' : 'Abra uma mensagem primeiro'"
                @click="responder(true)">
          <i class="bi bi-arrow-right" aria-hidden="true"></i> Encaminhar
        </button>
        <span class="email__separador" aria-hidden="true"></span>
        <button class="botao botao--pequeno botao--fantasma" type="button"
                title="Sua assinatura, usada nos e-mails que você enviar"
                @click="editandoAssinatura = !editandoAssinatura">
          <i class="bi bi-vector-pen" aria-hidden="true"></i> Assinatura
        </button>
      </div>
    </div>

    <!-- assinatura: HTML colado da que a pessoa já usa -->
    <section v-if="editandoAssinatura" class="cartao email__painel">
      <h2 class="inicio__titulo">Sua assinatura</h2>
      <!-- ⚠️ O que sobra é a única parte acionável: a do Gmail não vale aqui.
           "Cole o HTML da que você já usa" o campo vazio já pede. -->
      <p class="apagado pequeno">A assinatura do Gmail não vale nesta tela.</p>
      <textarea v-model="assinatura" class="campo__entrada email__area" rows="6"
                placeholder="<div>Seu nome<br>Movisat</div>"></textarea>
      <div v-if="assinatura" class="email__previa" v-html="assinatura"></div>

      <!-- 🚨 A IMAGEM VOLTOU PARA A TELA (27/08). Ele perguntou: *"assinatura
           por upload de imagem oculto? onde foi parar"*. O backend estava
           inteiro — a rota, a pasta, e o `enviar._assinatura()` que embute a
           imagem por CID no e-mail. **Faltava só o controle aqui.**

           ⚠️ A IMAGEM NÃO SUBSTITUI O HTML: o e-mail sai com os dois, e é por
           isso que os dois ficam no mesmo painel. O HTML é o texto (nome,
           cargo, telefone); a imagem é o logo. -->
      <div class="email__assinatura-imagem">
        <p class="campo__rotulo">Imagem (logo)</p>
        <!-- ⚠️ MOSTRA O NOME, NÃO A IMAGEM. Não existe rota que devolva o
             arquivo, e inventar uma só para a prévia seria escopo que ninguém
             pediu. O nome + "ativa" responde o que a pessoa precisa saber:
             tem imagem, e qual é. -->
        <div v-if="temImagem" class="linha">
          <span class="chip chip--ok">
            <i class="bi bi-image" aria-hidden="true"></i> {{ imagemNome }}
          </span>
          <button class="botao botao--pequeno botao--fantasma" type="button"
                  @click="tirarImagem">
            <i class="bi bi-x-circle" aria-hidden="true"></i> Tirar
          </button>
        </div>
        <p v-else class="apagado pequeno">Nenhuma imagem — o e-mail sai só com o texto.</p>
        <label class="botao botao--pequeno botao--contorno">
          <i class="bi bi-upload" aria-hidden="true"></i>
          {{ temImagem ? 'Trocar imagem' : 'Enviar imagem' }}
          <input type="file" accept="image/png,image/jpeg" hidden
                 @change="subirImagem" />
        </label>
        <span class="apagado pequeno">PNG ou JPG, até 2 MB.</span>
      </div>

      <div class="linha">
        <button class="botao botao--pequeno botao--acento" type="button" @click="salvarAssinatura">
          Salvar
        </button>
        <button class="botao botao--pequeno botao--fantasma" type="button"
                @click="editandoAssinatura = false">Fechar</button>
      </div>
    </section>

    <!-- escrever: UMA mensagem, nunca lista -->
    <section v-if="escrevendo" class="cartao email__painel">
      <h2 class="inicio__titulo">
        {{ rascunho.responder_a ? 'Responder' : 'Nova mensagem' }}
      </h2>
      <div class="campo email__para">
        <span class="campo__rotulo">Para</span>
        <div class="linha">
          <input v-model="rascunho.para" class="campo__entrada" type="email"
                 placeholder="alguem@empresa.com.br" />
          <button class="email__quadrado" type="button"
                  :class="{ 'email__quadrado--ligado': mostrarCopias }"
                  title="Cópia e cópia oculta"
                  @click="mostrarCopias = !mostrarCopias">Cc</button>
        </div>
      </div>

      <template v-if="mostrarCopias">
        <label class="campo">
          <span class="campo__rotulo">Cc <span class="apagado">— todos veem quem recebeu</span></span>
          <input v-model="rascunho.cc" class="campo__entrada" type="text"
                 placeholder="separe por vírgula" />
        </label>
        <label class="campo">
          <span class="campo__rotulo">Cco <span class="apagado">— ninguém vê quem recebeu</span></span>
          <input v-model="rascunho.cco" class="campo__entrada" type="text"
                 placeholder="separe por vírgula" />
        </label>
      </template>

      <label class="campo">
        <span class="campo__rotulo">Assunto</span>
        <input v-model="rascunho.assunto" class="campo__entrada" type="text" />
      </label>
      <div class="campo">
        <span class="campo__rotulo">Mensagem</span>
        <!-- 🚨 DE QUAL CAIXA ESTÁ SAINDO. Campo fixo, não editável: com duas
             caixas conectadas, escrever sem ver o remetente é como o
             destinatário acaba respondendo para o endereço errado. -->
        <p v-if="caixaAtiva" class="email__de-fixo pequeno">
          <span class="apagado">De:</span>
          <span class="caixas__cor" :style="{ background: corDaCaixa(caixaAtiva) }"
                aria-hidden="true"></span>
          <strong>{{ caixaAtiva.endereco }}</strong>
        </p>

        <div class="email__ferramentas">
          <template v-for="(f, i) in FERRAMENTAS" :key="i">
            <span v-if="f.sep" class="email__separador" aria-hidden="true"></span>
            <button v-else class="email__quadrado" type="button" :title="f.t"
                    @mousedown.prevent="formatar(f.c, f.v)">
              <i class="bi" :class="f.i" aria-hidden="true"></i>
            </button>
          </template>
          <select class="email__tamanho" title="Tamanho"
                  @change="formatar('fontSize', $event.target.value)">
            <option value="">Tamanho</option>
            <option value="2">Pequeno</option>
            <option value="3">Normal</option>
            <option value="5">Grande</option>
          </select>
          <button class="email__quadrado" type="button" title="Inserir link"
                  @mousedown.prevent="inserirLink">
            <i class="bi bi-link-45deg" aria-hidden="true"></i>
          </button>
        </div>
        <div ref="editor" class="email__editor" contenteditable="true"
             v-html="rascunho.corpo.replace(/\n/g, '<br>')"></div>
      </div>
      <!-- ⚠️ "Um destinatário por vez" é limite e fica; o resto o compositor
           já mostra no campo "De:". -->
      <p class="apagado pequeno">Um destinatário por vez.</p>
      <div class="linha linha--quebra email__anexos">
        <label class="botao botao--pequeno botao--contorno">
          <i class="bi bi-paperclip" aria-hidden="true"></i>
          {{ subindo ? 'subindo…' : 'Anexar' }}
          <input type="file" multiple hidden @change="anexar" />
        </label>
        <span v-for="a in anexos" :key="a.id" class="chip">
          {{ a.nome }} <span class="apagado">{{ tamanho(a.tamanho) }}</span>
          <button class="email__tirar" type="button" title="Remover"
                  @click="tirarAnexo(a.id)">×</button>
        </span>
      </div>

      <div class="linha">
        <button class="botao botao--acento" type="button" :disabled="enviando" @click="mandar">
          <i class="bi bi-send" aria-hidden="true"></i>
          {{ enviando ? 'enviando…' : 'Enviar' }}
        </button>
        <button class="botao botao--fantasma" type="button" @click="escrevendo = false">
          Cancelar
        </button>
      </div>
    </section>

    <div class="email" :class="{ 'email--sem-menu': !menuAberto }">
      <!-- marcadores: a navegação, como no Gmail -->
      <nav v-show="menuAberto" class="cartao email__lado">
        <button
          v-for="m in visiveis"
          :key="m.id"
          class="email__marcador"
          :class="{ 'email__marcador--ativo': marcadorAtual === m.id_externo }"
          type="button"
          @click="trocar(m.id_externo)"
        >
          <span>{{ rotulo(m) }}</span>
          <span v-if="m.quantidade" class="apagado pequeno">{{ m.quantidade }}</span>
        </button>
        <p v-if="!visiveis.length" class="apagado pequeno">
          Clique em <strong>Atualizar</strong> para trazer suas pastas.
        </p>
      </nav>

      <!-- lista -->
      <div class="cartao email__lista">
        <!-- 🚨 A BARRA SÓ EXISTE COM ALGO MARCADO. Barra de ação permanente
             numa caixa de 336 mensagens é convite para clique errado, e
             ocupa a altura que a lista precisa. -->
        <div v-if="marcadas.length" class="email__lote">
          <strong class="pequeno">{{ marcadas.length }} selecionada(s)</strong>
          <span class="espaco"></span>
          <button class="botao botao--pequeno botao--fantasma" type="button"
                  :disabled="aplicandoLote" title="Marcar como lida"
                  @click="lote('lida')">
            <i class="bi bi-envelope-open" aria-hidden="true"></i>
          </button>
          <button class="botao botao--pequeno botao--fantasma" type="button"
                  :disabled="aplicandoLote" title="Marcar como não lida"
                  @click="lote('nao_lida')">
            <i class="bi bi-envelope" aria-hidden="true"></i>
          </button>
          <button class="botao botao--pequeno botao--fantasma" type="button"
                  :disabled="aplicandoLote" title="Marcar com estrela"
                  @click="lote('estrela')">
            <i class="bi bi-star" aria-hidden="true"></i>
          </button>
          <button class="botao botao--pequeno botao--fantasma" type="button"
                  :disabled="aplicandoLote" title="Arquivar"
                  @click="lote('arquivar')">
            <i class="bi bi-archive" aria-hidden="true"></i>
          </button>
          <button class="botao botao--pequeno botao--fantasma" type="button"
                  @click="marcadas = []">
            limpar
          </button>
        </div>

        <label v-if="mensagens.length" class="email__todas pequeno">
          <input type="checkbox" :checked="todasMarcadas" @change="alternarTodas" />
          <span>selecionar tudo</span>
        </label>

        <p v-if="carregando" class="apagado pequeno">carregando…</p>
        <div v-else-if="!mensagens.length" class="email__vazio">
          <i class="bi bi-inbox" aria-hidden="true"></i>
          <p>Nenhuma mensagem por aqui.</p>
          <p class="apagado pequeno">Clique em <strong>Atualizar</strong> para buscar as novas.</p>
        </div>
        <!-- 🚨 DUAS ALTURAS DE INFORMAÇÃO, NÃO UMA FILA. A linha antiga punha
             remetente, assunto, cliente, clipe e hora lado a lado, todos com
             o mesmo peso -- e numa caixa de 336 mensagens isso obriga a LER
             cada linha inteira para achar qualquer coisa. Remetente e hora em
             cima, assunto embaixo: o olho varre a primeira coluna e só desce
             onde interessa. -->
        <div
          v-for="m in mensagens"
          :key="m.id"
          class="email__item"
          :class="{ 'email__item--aberta': aberta && aberta.id === m.id,
                    'email__item--nova': !m.lida }"
        >
          <input
            class="email__marca"
            type="checkbox"
            :checked="marcadas.includes(m.id)"
            :aria-label="`Selecionar: ${m.assunto || 'sem assunto'}`"
            @change="alternarMarcada(m.id)"
          />

          <!-- ⚠️ A estrela é botão PRÓPRIO, fora do que abre a mensagem:
               estrelar sem abrir é metade do uso dela. -->
          <button
            class="email__estrela"
            :class="{ 'email__estrela--ligada': m.estrela }"
            type="button"
            :title="m.estrela ? 'Tirar a estrela' : 'Marcar com estrela'"
            :aria-label="m.estrela ? 'Tirar a estrela' : 'Marcar com estrela'"
            @click.stop="alternarEstrela(m)"
          >
            <i class="bi" :class="m.estrela ? 'bi-star-fill' : 'bi-star'"></i>
          </button>

          <button class="email__abrir" type="button" @click="abrir(m.id)">
            <span class="email__linha1">
              <span class="email__inicial"
                    :style="{ background: corDaInicial(m) }" aria-hidden="true">
                {{ iniciais(m) }}
              </span>
              <span class="email__de">{{ m.remetente_nome || m.remetente }}</span>
              <i v-if="m.tem_anexo" class="bi bi-paperclip apagado" aria-hidden="true"></i>
              <span class="apagado pequeno email__quando">{{ quando(m.enviado_em) }}</span>
            </span>
            <span class="email__linha2">
              <span class="email__assunto">{{ m.assunto || '(sem assunto)' }}</span>
              <!-- 🚨 O CHIP DO CLIENTE É O QUE ESTA CAIXA TEM E O GMAIL NÃO.
                   Ficava só dentro da mensagem aberta; na lista, é ele que
                   transforma "um e-mail" em "um e-mail da Pastelaria". -->
              <span v-if="m.cliente_nome" class="chip chip--pequeno email__cliente">
                {{ m.cliente_nome }}
              </span>
            </span>
          </button>
        </div>
      </div>

      <!-- leitura -->
      <div class="cartao email__leitura">
        <div v-if="!aberta" class="email__vazio">
          <i class="bi bi-envelope-open" aria-hidden="true"></i>
          <p>Escolha uma mensagem para ler</p>
        </div>
        <template v-else>
          <!-- 🚨 CABEÇALHO FIXO. Numa mensagem longa, rolar fazia sumir de
               QUEM ela é -- e responder sem ver o remetente é como se
               responde para a pessoa errada. -->
          <header class="email__cabecalho">
            <div class="email__cabecalho-topo">
              <h2 class="email__titulo">{{ aberta.assunto || '(sem assunto)' }}</h2>
              <div class="linha">
                <button class="botao botao--pequeno botao--contorno" type="button"
                        title="Responder (r)" @click="responder(false)">
                  <i class="bi bi-reply" aria-hidden="true"></i> Responder
                </button>
                <button class="botao botao--pequeno botao--fantasma botao--icone"
                        type="button" title="Marcar como não lida (u)"
                        aria-label="Marcar como não lida"
                        @click="marcarNaoLida(aberta)">
                  <i class="bi bi-envelope" aria-hidden="true"></i>
                </button>
                <!-- Arquivar tira a mensagem da vista: ação sobre o registro,
                     e pela régua de 28/08 ela tem palavra. O envelope de
                     "não lida" fica só ícone -- é convenção de caixa de
                     correio e o atalho `u` está no ícone de ajuda. -->
                <button class="botao botao--pequeno botao--fantasma"
                        type="button" title="Arquivar (e)"
                        @click="arquivarAberta">
                  <i class="bi bi-archive" aria-hidden="true"></i>
                  Arquivar
                </button>
              </div>
            </div>
            <p class="apagado pequeno mono">
              {{ aberta.remetente }} ·
              {{ new Date(aberta.enviado_em).toLocaleString('pt-BR') }}
            </p>
          </header>

          <!-- a mesma faixa da ficha do WhatsApp: quem é, ou como vincular -->
          <p v-if="aberta.cliente_nome" class="chip chip--acento">
            <i class="bi bi-building" aria-hidden="true"></i> {{ aberta.cliente_nome }}
          </p>
          <div v-if="aberta.bitrix" class="gaveta__bitrix">
            <strong class="pequeno">Aparece no Bitrix</strong>
            <span v-if="aberta.bitrix.nome">{{ aberta.bitrix.nome }}</span>
            <span v-if="aberta.bitrix.empresa" class="apagado pequeno">{{ aberta.bitrix.empresa }}</span>
            <span v-if="aberta.bitrix.tipo" class="chip">{{ aberta.bitrix.tipo }}</span>
            <span class="apagado pequeno">Sistema antigo — <strong>não é vínculo</strong>.</span>
          </div>

          <div v-if="!aberta.cliente_nome" class="email__vincular">
            <!-- O campo de busca logo abaixo já diz o que fazer; a frase só
                 repetia o estado que o bloco inteiro anuncia. -->
            <p class="apagado pequeno">Remetente sem cliente vinculado.</p>
            <input v-model="buscaEmpresa" class="campo__entrada" type="search"
                   placeholder="Buscar empresa por nome ou CNPJ"
                   @input="procurarEmpresa" />
            <ul v-if="achados.length" class="gaveta__lista">
              <li v-for="c in achados" :key="c.id">
                <button class="botao botao--pequeno botao--contorno gaveta__achado"
                        type="button" @click="vincular(c.id)">
                  <span>{{ c.nome }}</span>
                  <span class="apagado pequeno mono">{{ c.documento }}</span>
                </button>
              </li>
            </ul>
          </div>

          <!-- 🚨 ATÉ 12/08 ISTO ERA SÓ UM SELO. A tela dizia "tem anexo" e
               não deixava abrir: 48 dos 226 e-mails, e quem precisava do
               boleto ia no Gmail. Os bytes continuam no Google -- guardá-los
               custaria ~360 MB/ano para duplicar o que já está lá --, mas
               agora o clique busca na hora. -->
          <div v-if="aberta.anexos && aberta.anexos.length"
               class="linha linha--quebra pequeno">
            <button
              v-for="(a, i) in aberta.anexos"
              :key="a.nome + i"
              class="botao botao--pequeno botao--contorno"
              type="button"
              :disabled="baixando === i"
              :title="a.id_externo
                ? `Baixar ${a.nome}`
                : 'Anexo sem id no Gmail — abra pelo Gmail'"
              @click="baixarAnexo(i, a)"
            >
              <span v-if="baixando === i" class="girando"></span>
              <i v-else class="bi bi-paperclip" aria-hidden="true"></i>
              {{ a.nome }}
              <span v-if="a.tamanho" class="apagado">{{ tamanho(a.tamanho) }}</span>
            </button>
          </div>

          <pre class="email__corpo">{{ aberta.texto || '(sem texto legível)' }}</pre>

          <!-- 🚨 O FIO. `thread_externa` é coluna desde a migração 014 e nunca
               foi usada: cada mensagem aparecia solta, e uma troca de seis
               e-mails virava seis linhas idênticas na lista, sem ninguém saber
               que eram a mesma conversa. -->
          <section v-if="fio.length > 1" class="email__fio">
            <h3 class="email__subtitulo">
              Nesta conversa ({{ fio.length }} mensagens)
            </h3>
            <button
              v-for="f in fio"
              :key="f.id"
              class="email__fio-item"
              :class="{ 'email__fio-item--atual': f.id === aberta.id }"
              type="button"
              @click="abrir(f.id)"
            >
              <span class="email__fio-de">{{ f.remetente_nome || f.remetente }}</span>
              <span class="apagado pequeno">{{ quando(f.enviado_em) }}</span>
            </button>
          </section>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* A barra fica GRUDADA acima das colunas, com respiro embaixo: sem a margem
   o botão de recolher parecia flutuando solto sobre a lista. */
.email__barra {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--e-2);
  padding: var(--e-2) var(--e-3);
  margin-bottom: var(--e-3);
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-lg);
  box-shadow: var(--sombra-1);
}
.email__acoes { flex-wrap: wrap; gap: var(--e-1); }
.email__separador {
  width: 1px; height: 20px;
  background: var(--borda);
  margin: 0 var(--e-1);
}
/* Desabilitado tem que PARECER desabilitado, senão vira clique frustrado. */
.email__acoes .botao:disabled { opacity: .45; cursor: not-allowed; }

/* 🚨 AS TRES AREAS DIVIDEM A MESMA ALTURA e rolam por dentro. Antes cada
   cartao terminava onde o conteudo dele acabava, e o desalinhamento aparecia
   de cara -- lista curta ao lado de leitura longa. */
.email {
  display: grid;
  grid-template-columns: 190px minmax(280px, 360px) 1fr;
  gap: var(--e-3);
  align-items: stretch;
  height: calc(100vh - 250px);   /* desconta cabeçalho + barra de ações */
  min-height: 420px;
}
.email--sem-menu { grid-template-columns: minmax(280px, 360px) 1fr; }

/* Abaixo de 1100px o painel ja tem o menu lateral dele: dois menus lado a
   lado espremem a leitura. A lista some e fica só o que se está lendo. */
@media (max-width: 1100px) {
  .email { grid-template-columns: minmax(260px, 320px) 1fr; }
  .email__lado { display: none; }
}
@media (max-width: 760px) {
  .email { grid-template-columns: 1fr; height: auto; }
  .email__lista, .email__leitura { max-height: 60vh; }
}

.email__lado { padding: var(--e-2); display: flex; flex-direction: column; gap: 2px; }

.email__inicial {
  width: 26px; height: 26px; flex: none;
  display: grid; place-items: center;
  border-radius: var(--r-full);
  color: #fff; font-size: var(--txt-sm); font-weight: 600;
}
.email__de {
  width: 150px; flex: none;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.email__assunto {
  flex: 1; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  color: var(--texto-fraco);
}
.email__cliente { flex: none; max-width: 130px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.email__quando { flex: none; width: 46px; text-align: right; font-variant-numeric: tabular-nums; }

/* Não lida em negrito e com barra: é o que a pessoa procura ao abrir. */
.email__item--nova { border-left: 3px solid var(--acento); }
.email__item--nova .email__de { font-weight: 700; }

/* Botão quadrado: ocupa o mínimo. Espaço de tela é caro, e formatação é
   coisa que se reconhece pelo ícone, não pelo rótulo. */
.email__quadrado {
  width: 30px; height: 30px; flex: none;
  display: grid; place-items: center;
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-sm);
  background: var(--superficie);
  color: var(--texto-fraco);
  cursor: pointer;
  font-size: var(--txt-sm);
  font-family: var(--fonte);
}
.email__quadrado:hover { background: var(--superficie-2); color: var(--texto); }
.email__quadrado--ligado { background: var(--acento-suave); color: var(--acento); border-color: var(--acento-borda); }

.email__ferramentas {
  display: flex; flex-wrap: wrap; align-items: center; gap: 2px;
  padding: var(--e-1);
  border: var(--borda-fina) solid var(--borda);
  border-bottom: none;
  border-radius: var(--r-sm) var(--r-sm) 0 0;
  background: var(--superficie-2);
}
.email__tamanho {
  height: 30px; border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-sm); background: var(--superficie);
  font-size: var(--txt-sm); font-family: var(--fonte); color: var(--texto-fraco);
}

.email__editor {
  min-height: 190px; max-height: 40vh; overflow-y: auto;
  padding: var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-radius: 0 0 var(--r-sm) var(--r-sm);
  background: var(--superficie);
  font-size: var(--txt-md);
  line-height: 1.55;
}
.email__editor:focus { outline: none; box-shadow: var(--foco); }
.email__editor blockquote {
  margin: 0 0 0 var(--e-2); padding-left: var(--e-2);
  border-left: 3px solid var(--borda-forte); color: var(--texto-fraco);
}
.email__para .linha { gap: var(--e-1); }
.email__para .campo__entrada { flex: 1; }

.email__anexos { gap: var(--e-2); align-items: center; }
.email__tirar {
  border: none; background: transparent; cursor: pointer;
  color: var(--texto-fraco); font-size: var(--txt-md); line-height: 1;
  padding: 0 0 0 4px;
}
.email__tirar:hover { color: var(--erro); }

.email__painel { padding: var(--e-4); margin-bottom: var(--e-3); display: flex; flex-direction: column; gap: var(--e-2); }
.email__area { font-family: var(--fonte-mono); font-size: var(--txt-sm); resize: vertical; }
.email__previa {
  border: var(--borda-fina) dashed var(--borda-forte);
  border-radius: var(--r-sm);
  padding: var(--e-2);
  background: var(--superficie-2);
}
.gaveta__bitrix {
  display: flex; flex-direction: column; gap: 2px;
  padding: var(--e-2); margin: var(--e-2) 0;
  border-left: 3px solid var(--aviso);
  background: var(--aviso-suave);
  border-radius: var(--r-sm);
}
.email__vincular { display: flex; flex-direction: column; gap: var(--e-2); margin: var(--e-2) 0; }
.gaveta__lista { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--e-1); max-height: 200px; overflow-y: auto; }
.gaveta__achado { width: 100%; display: flex; justify-content: space-between; gap: var(--e-2); text-align: left; }

.email__vazio {
  display: flex; flex-direction: column; align-items: center; gap: var(--e-1);
  padding: var(--e-6) var(--e-3); text-align: center; color: var(--texto-apagado);
}
.email__vazio i { font-size: 30px; opacity: .5; }
.email__vazio p { margin: 0; }
.email__marcador {
  display: flex;
  justify-content: space-between;
  gap: var(--e-2);
  padding: var(--e-2);
  border: none;
  background: transparent;
  border-radius: var(--r-sm);
  cursor: pointer;
  text-align: left;
  font-family: var(--fonte);
  font-size: var(--txt-sm);
  color: var(--texto);
}
.email__marcador:hover { background: var(--superficie-2); }
.email__marcador--ativo { background: var(--acento-suave); color: var(--acento); font-weight: 600; }

.email__lista {
  padding: var(--e-2);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-height: 0;   /* sem isto o filho de grid não encolhe e a rolagem não nasce */
}
.email__item {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  min-width: 0;
  padding: var(--e-2);
  border: none;
  border-bottom: var(--borda-fina) solid var(--borda);
  /* 🚨 A BARRA DE NÃO LIDA. 3px à esquerda em vez de negrito no texto inteiro:
     negrito muda a largura das palavras e faz a lista "tremer" conforme as
     mensagens são abertas. A barra não mexe em nada. */
  border-left: 3px solid transparent;
  background: transparent;
  text-align: left;
  font-family: var(--fonte);
}
.email__item:hover { background: var(--superficie-2); }
.email__item--aberta { background: var(--acento-suave); }
.email__item--nova { border-left-color: var(--acento); background: var(--superficie); }
.email__item--nova .email__de { font-weight: var(--peso-forte); color: var(--texto); }

/* O que abre a mensagem é só o miolo: caixa de seleção e estrela ficam de
   fora, senão marcar uma mensagem a abriria junto. */
.email__abrir {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  border: 0;
  background: none;
  padding: 0;
  cursor: pointer;
  text-align: left;
  font-family: var(--fonte);
}
.email__linha1 { display: flex; align-items: center; gap: var(--e-2); min-width: 0; }
.email__linha2 { display: flex; align-items: center; gap: var(--e-2); min-width: 0; }

.email__de {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--texto-fraco);
}
.email__quando { flex: none; white-space: nowrap; }
.email__assunto {
  flex: 1 1 auto;
  min-width: 0;
  font-size: var(--txt-sm);
  color: var(--texto-fraco);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.email__cliente { flex: none; }

.email__marca { flex: none; }
.email__estrela {
  flex: none;
  border: 0;
  background: none;
  padding: 2px;
  cursor: pointer;
  color: var(--texto-apagado);
  line-height: 1;
}
.email__estrela:hover { color: var(--aviso); }
.email__estrela--ligada { color: var(--aviso); }

/* ---- abas de caixa ------------------------------------------------------
   Pasta de planilha: a ativa "sai" da linha, as outras ficam recuadas. */
.caixas {
  display: flex;
  gap: 2px;
  align-items: flex-end;
  margin-bottom: -1px;
  overflow-x: auto;
}
.caixas__aba {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  flex: none;
  padding: var(--e-2) var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-bottom: none;
  border-radius: var(--r-md) var(--r-md) 0 0;
  background: var(--superficie-2);
  color: var(--texto-fraco);
  font-family: var(--fonte);
  font-size: var(--txt-sm);
  cursor: pointer;
  white-space: nowrap;
}
.caixas__aba:hover { color: var(--texto); }
.caixas__aba--ativa {
  background: var(--superficie);
  color: var(--texto);
  font-weight: var(--peso-forte);
  /* +1px de altura e fundo igual ao painel: é o que faz a aba parecer
     CONTINUAR na área de leitura, em vez de flutuar acima dela. */
  padding-top: calc(var(--e-2) + 2px);
}
.caixas__aba:focus-visible { outline: none; box-shadow: var(--foco); }
.caixas__cor {
  width: 8px;
  height: 8px;
  border-radius: var(--r-full);
  flex: none;
}

.email__de-fixo {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  padding: var(--e-2) 0;
  border-bottom: var(--borda-fina) solid var(--borda);
  margin-bottom: var(--e-2);
}

.email__lote {
  display: flex;
  align-items: center;
  gap: var(--e-1);
  padding: var(--e-2);
  background: var(--acento-suave);
  border-bottom: var(--borda-fina) solid var(--acento-borda);
  position: sticky;
  top: 0;
  z-index: var(--z-conteudo);
}
.email__todas {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  padding: var(--e-1) var(--e-2);
  color: var(--texto-fraco);
}

.email__leitura { padding: 0; overflow-y: auto; min-height: 0; }

/* Cabeçalho fixo: numa mensagem longa, rolar fazia sumir de quem ela é. */
.email__cabecalho {
  position: sticky;
  top: 0;
  z-index: var(--z-conteudo);
  padding: var(--e-4);
  background: var(--superficie);
  border-bottom: var(--borda-fina) solid var(--borda);
}
.email__cabecalho-topo {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--e-3);
}
.email__leitura > *:not(.email__cabecalho) { padding-left: var(--e-4); padding-right: var(--e-4); }

.email__subtitulo {
  font-size: var(--txt-sm);
  text-transform: uppercase;
  letter-spacing: .06em;
  color: var(--texto-apagado);
  margin: var(--e-4) 0 var(--e-2);
}
.email__fio { padding-bottom: var(--e-4); }
.email__fio-item {
  display: flex;
  justify-content: space-between;
  gap: var(--e-2);
  width: 100%;
  padding: var(--e-2);
  border: 0;
  border-bottom: var(--borda-fina) solid var(--borda);
  background: none;
  cursor: pointer;
  text-align: left;
  font-family: var(--fonte);
  font-size: var(--txt-sm);
}
.email__fio-item:hover { background: var(--superficie-2); }
.email__fio-item--atual {
  background: var(--acento-suave);
  border-left: 3px solid var(--acento);
}
.email__fio-de { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.email__lado { overflow-y: auto; min-height: 0; }
.email__titulo { font-size: var(--txt-lg); margin: 0 0 var(--e-1); }
/* Largura de leitura confortável. Texto esticado até a borda de uma tela
   larga cansa: o olho perde a linha na volta. */
.email__corpo {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-family: var(--fonte);
  font-size: var(--txt-md);
  line-height: 1.55;
  /* ⚠️ O token `--largura-texto` existia desde o primeiro dia e não era
     usado: havia um `65ch` escrito à mão aqui. Texto esticado até a borda de
     uma tela larga cansa -- o olho perde a linha na volta. */
  max-width: var(--largura-texto);
  margin-top: var(--e-3);
  padding-bottom: var(--e-4);
}
</style>
