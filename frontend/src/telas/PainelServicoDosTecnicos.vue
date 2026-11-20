<script setup>
/* ============================================================================
   SERVIÇO DOS TÉCNICOS — a aba 2 do Financeiro (PNL_1.6)
   18/11 nasceu · 19/11 recebeu o padrão da aba 1, a ordem da Operação e os
   três serviços que o servidor tinha e a tela não chamava
   ----------------------------------------------------------------------------
   🔵 Pedido dele em 18/11: *"Nova aba2 no painel do Financeiro Movizap:
   'Serviço dos técnicos'"*, com cinco colunas — Movimentação, Preparação,
   Validação, Procfy e Pagamento enviado.

   🔵 Pedido dele em 19/11: *"faltam várias coisas e melhorias de UX/UI
   principalmente em relação a funcionalidade e estilos dos cards -- como a
   aba1 apresenta -- foque na aba 2 e finalize a entrega e serviços dela"* ·
   *"regras de ordenamento tbm da etapa de op faltam aqui"*.

   🚨 TELA PRÓPRIA, E NÃO O `PainelAba.vue`: as cinco colunas **não são etapas
   nossas nem situações do ERP** — são estados do *artefato de pagamento*, que
   vive no FPSL. O `quadro_da_aba` desenharia cinco colunas vazias para sempre.
   ⚠️ Mas o CASCO é o mesmo da aba 1 de propósito, e é isso que mudou em 19/11:
   coluna de 360px com a borda colorida e recolhível, card com sombra e borda
   forte, as duas barras de rolagem, a tira de abas. Ser outra tela não é
   motivo para parecer outro produto.

   🚨 A UNIDADE É O ARTEFATO, e é o que faz as colunas se encaixarem: um serviço
   pago a um técnico numa OS, com **Orçamento · OS · TERMO · valor** — a ordem
   que ele escreveu. O artefato atravessa as cinco colunas; o CARD não: o da
   coluna 1 é permanente por técnico (🔵 decisão dele) e os das outras são
   lotes. É por isso que *"os removidos voltam para o card da primeira
   coluna"* funciona de qualquer etapa.

   ----------------------------------------------------------------------------
   🚨 OS TRÊS SERVIÇOS QUE JÁ EXISTIAM NO SERVIDOR E NINGUÉM ALCANÇAVA

   Das 14 rotas que subiram em 18/11, a tela chamava 11. As três de fora não
   eram enfeite:

   1. **`/comprovante`** — 🔵 *"haverá campo para que em cada 1 dos artefatos de
      pagamento seja inserido anexo que comprove o pagamento. Após o envio do
      anexo, abre o campo que pede o valor"*. 🚨 E sem ele a coluna 3 era um
      beco: o `montar_arquivo` **recusa** lote em que nenhum artefato tem
      comprovante ou dispensa, então o caminho Validação → Procfy não fechava
      por gesto nenhum da tela.
   2. **`/datascope/{id}`** — 🔵 *"fará a validação com o Datascope, trazendo a
      situação que estiver lá"*. A tela só exibia o que a varredura tivesse
      deixado gravado, e não tinha como pedir a leitura.
   3. **`/previa/{lote}`** — 🔵 *"dentro deles um resumo dos artefatos que vão
      para pagamento"*, e é onde o arquivo do Procfy diz **quais colunas saem
      em branco** antes de alguém baixá-lo.

   ⚠️ O que continua FORA, e é decisão dele: a **correção da situação no
   DataScope** (`change_state`). Ela escreve em sistema de terceiro, dispara os
   webhooks deles e manda push ao técnico — e a rota de escrita não existe nem
   no FPSL. Aqui só se LÊ.

   ----------------------------------------------------------------------------
   ⚠️ **COR NUNCA SOZINHA.** Todo estado do semáforo carrega ícone e texto:
   quem não distingue a cor tem de conseguir ler qual é qual.
   ============================================================================ */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api, ErroDeApi } from '../api/cliente.js'
import BarraDeRolagem from '../componentes/BarraDeRolagem.vue'
import RolagemDaBorda from '../componentes/RolagemDaBorda.vue'
import { sessao } from '../estado/sessao.js'

const BASE = '/api/paineis/servico-dos-tecnicos'

const quadro = ref(null)
/* 🚨 `rolo`, e não `quadro`: naquele nome já mora o JSON do painel. Este é o
   elemento com `overflow-x`, que as duas rolagens recebem por `prop` — a mesma
   ligação da Operação desde 06/11 e da aba 1 desde 11/11. */
const rolo = ref(null)
const carregando = ref(false)
const erro = ref('')
const aviso = ref('')
const abertas = ref({})

/* 🚨 A MARCAÇÃO É POR CARD, e isto é conserto de 19/11. Até aqui `marcados`
   era um `Set` só para o quadro inteiro: marcar no card do Franck fazia o
   botão do card do Pedro dizer *"Preparar os marcados (3)"* e mandar os três
   artefatos do Franck junto. O servidor salvava a cara (ele agrupa por
   técnico e gera um lote por pessoa), mas a tela afirmava o que não era.
   ⚠️ A chave é o técnico (`0` para os sem técnico), e não o índice do card. */
const marcados = ref({})

/* 🔵 *"ter o filtro de datas sempre dentro do card coluna 1 (...) por exemplo,
   só quero fechar de 16-18/11/26 filtro isso e flego"*.
   ⚠️ A data é a DO SERVIÇO (a previsão da OS), não a da coleta: é ela que vai
   ao Procfy como competência.
   🚨 E O FILTRO TAMBÉM É POR CARD desde 19/11, pelo mesmo motivo da marcação:
   um `de`/`até` só para a tela aparecia dentro de todos os cards e filtrava
   todos ao mesmo tempo — fechar o período do Franck escondia artefatos do
   Pedro, em dois cards que não têm nada a ver um com o outro. */
const filtros = ref({})

/* O modal de conferir, da coluna 2 — 🔵 *"confirmar 1 a 1 na tela modal"*. */
const conferindo = ref(null)
const devolvendo = ref(null)
const justificativa = ref('')

/* 🔵 19/11: os três modais novos. */
const osAberta = ref(null)
const comprovando = ref(null)
const previa = ref(null)

const TITULOS = {
  movimentacao: 'Movimentação',
  preparacao: 'Preparação',
  validacao: 'Validação',
  procfy: 'Procfy',
  enviado: 'Pagamento enviado',
}

/* 🚨 Ícone e texto por cor, porque cor sozinha não informa. */
const SEMAFORO = {
  verde: { icone: 'bi-check-circle-fill', texto: 'conforme' },
  amarelo: { icone: 'bi-exclamation-circle-fill', texto: 'divergência ou ausência' },
  laranja: { icone: 'bi-arrow-counterclockwise', texto: 'devolvido' },
  vermelho: { icone: 'bi-x-circle-fill', texto: 'a pagar maior que o recibo' },
}

/* 🚨 AS 6 CORES DO CATAVENTO, as mesmas da Operação e da aba 1, ciclando pelas
   cinco colunas. ⚠️ A cor é da COLUNA e nunca do card: o card já está nela, e
   dentro dela todos teriam a mesma cor — a régua de 05/11. */
const CORES = ['#8CC63F', '#FFC20E', '#F07F13', '#1B75BB', '#41BFE8']
const corDaColuna = (i) => CORES[i % CORES.length]

/* ============================================================================
   A BUSCA E A ORDEM — 🔵 19/11: *"regras de ordenamento tbm da etapa de op
   faltam aqui"*.
   ----------------------------------------------------------------------------
   🚨 AQUI QUEM FILTRA É O NAVEGADOR, e na Operação é o servidor. A diferença
   não é descuido: lá o teto é 50 cards por coluna e 600 no quadro, e filtrar
   no navegador esconderia o que o teto já cortou. Aqui o quadro vem INTEIRO
   do FPSL (79 artefatos hoje, 633 OS no universo), então não há nada cortado
   para esconder — e filtrar aqui evita uma ida ao FPSL por tecla.
   ⚠️ No dia em que este quadro ganhar teto, esta decisão tem de virar do
   servidor junto, ou a tela passa a mentir por omissão.

   ⚠️ UMA CAIXA SÓ para os cinco campos, como na Operação: quem procura tem um
   número ou um nome na mão e não quer decidir em qual caixa ele vai. E a tela
   DIZ onde casou — orçamento, OS e termo são três números parecidos no mesmo
   card, e sem isso quem procura `1672` não sabe o que achou.
   ============================================================================ */
const busca = ref('')

/* ⚠️ A ordem desta lista é a ordem do seletor, e o primeiro é o padrão — não é
   alfabética. 🟡 O PADRÃO É SUGESTÃO MINHA, não decisão dele: na Operação ele
   escolheu *"prazo de entrega (mais próximo)"*, e o equivalente honesto aqui é
   o serviço mais antigo primeiro — é o que está há mais tempo sem pagar. */
const ordem = ref('data_asc')
const ROTULO_ORDEM = {
  data_asc: 'serviço mais antigo primeiro',
  data_desc: 'serviço mais recente primeiro',
  os_desc: 'OS, da mais nova',
  os_asc: 'OS, da mais antiga',
  valor_desc: 'maior valor primeiro',
  cliente: 'cliente (A-Z)',
}

/* 🟡 E a ordem dos CARDS, que na Operação não existe porque lá o card é uma OS
   e aqui é uma pessoa. O padrão continua sendo o de 18/11 (quem tem mais
   artefatos primeiro), para a tela não mudar de cara sem ele pedir. */
const ordemDosCards = ref('artefatos')
const ROTULO_ORDEM_CARDS = {
  artefatos: 'card com mais artefatos primeiro',
  valor: 'card com maior valor primeiro',
  tecnico: 'técnico (A-Z)',
}

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    quadro.value = await api.get(BASE)
    for (const coluna of quadro.value.colunas || []) {
      if (abertas.value[coluna.chave] === undefined) {
        abertas.value[coluna.chave] = true
      }
    }
  } catch (e) {
    /* 🚨 QUADRO VAZIO NUNCA: vazio silencioso faria concluir que não há
       pagamento a preparar, justo quando há. */
    erro.value = e instanceof ErroDeApi ? e.message
      : 'Não consegui ler o quadro de pagamentos.'
  } finally {
    carregando.value = false
  }
}

/* 🔵 A TIRA DE ABAS — a mesma da aba 1, e sem ela a `PNL_1.6` era um beco: ela
   não aparece no menu por desenho (`aba_de: PNL_1.4`), então quem entrava só
   voltava pelo botão do navegador.
   ⚠️ DUAS FONTES, cada uma com o que é dela: o SERVIDOR diz quais abas são
   deste painel e como se chamam; o `sessao.telas` dá a ROTA e, de graça, a
   permissão — aba que a pessoa não alcança não está nessa lista e cai fora
   sem segunda régua. */
const abasVisiveis = computed(() => {
  const doPainel = quadro.value?.abas || []
  const porCodigo = new Map((sessao.telas || []).map((t) => [t.codigo, t]))
  return doPainel
    .filter((a) => porCodigo.has(a.codigo_tela))
    .map((a) => ({ codigo: a.codigo_tela, titulo: a.titulo,
                   rota: porCodigo.get(a.codigo_tela).rota }))
})

const codigoDesta = 'PNL_1.6'

/* 🚨 O `h1` É O NOME DO PAINEL, e não o da aba — a mesma régua da aba 1
   (11/11, dele: *"deve condizer com o tipo da Aba"*). ⚠️ Aqui ele NÃO pode
   sair de `rota.meta.titulo`: no roteador esta entrada se chama *"Serviço dos
   técnicos"*, que é o nome da ABA, e ele já aparece na tira logo abaixo —
   usá-lo no `h1` diria duas vezes a mesma coisa e deixaria o painel sem nome.
   ⚠️ E não sai do servidor porque o `painel_aba` guarda a chave (`financeiro`)
   e o título de cada ABA, não o nome do painel. */
const tituloDoPainel = 'Financeiro'

/* ---------------------------------------------------------------- as datas */

function isoDaData(bruto) {
  /* ⚠️ A `data_previsao` do cache vem `dd/mm/aaaa HH:MM:SS` — o JavaScript não
     sabe ler isso (`new Date(...)` = Invalid Date), e foi essa armadilha que
     deixou o "há 2 dias" sumido em 10 de 10 cards em 05/11. */
  if (!bruto) return ''
  const m = String(bruto).match(/^(\d{2})\/(\d{2})\/(\d{4})/)
  if (m) return `${m[3]}-${m[2]}-${m[1]}`
  const iso = String(bruto).match(/^(\d{4})-(\d{2})-(\d{2})/)
  return iso ? iso[0] : ''
}

function dataCurta(bruto) {
  const iso = isoDaData(bruto)
  if (!iso) return 'sem data'
  const [a, m, d] = iso.split('-')
  return `${d}/${m}/${a.slice(2)}`
}

/* 🚨 LER NÃO ESCREVE, e esta é a armadilha desta tela: `filtroDo` e
   `marcadosDo` são chamados DENTRO do template, e criar a entrada que falta
   ali seria escrever num `ref` durante o desenho — o Vue reage, redesenha,
   escreve de novo, e a tela entra em laço. Os dois leem com um valor vazio
   constante; quem cria a entrada é o GESTO (`definirFiltro`, `alternar`).
   ⚠️ `Object.freeze` para que ninguém escreva no vazio por engano e o
   compartilhe entre todos os cards. */
const FILTRO_VAZIO = Object.freeze({ de: '', ate: '' })
const MARCADOS_VAZIO = Object.freeze([])

function filtroDo(card) {
  return filtros.value[card.tecnico_id || 0] || FILTRO_VAZIO
}

function definirFiltro(card, campo, valor) {
  const chave = card.tecnico_id || 0
  const atual = filtros.value[chave] || FILTRO_VAZIO
  filtros.value = { ...filtros.value,
                    [chave]: { ...atual, [campo]: valor } }
}

function limparFiltro(card) {
  filtros.value = { ...filtros.value,
                    [card.tecnico_id || 0]: { de: '', ate: '' } }
}

/* 🚨 19/11, DEFEITO ACHADO POR ELE USANDO A TELA: *"ao usa o filtro de data na
   aba2 os cards somem"*. A causa é o `<input type="date">`, não a comparação.

   📏 Medido: o campo dispara `input` a CADA dígito do ano, então digitar 2026
   produz a sequência `0002-11-19`, `0020-...`, `0202-...`, `2026-...`. Com
   `até = 0002-11-19` **todo** artefato é maior que o limite e cai fora: o card
   esvazia na cara de quem está digitando.

   🚨 Duas travas, e as duas são necessárias:
   1. o evento passou a ser `change` (só valor COMMITADO) -- no template;
   2. este guarda: limite com ano implausível é limite que NÃO EXISTE. Sem ele,
      colar uma data torta ou um teclado que comita cedo repete o sintoma. */
function limiteValido(iso) {
  return /^\d{4}-\d{2}-\d{2}$/.test(iso) && iso.slice(0, 4) >= '1900'
}

function dentroDoFiltro(card, artefato) {
  const f = filtroDo(card)
  const de = limiteValido(f.de) ? f.de : ''
  const ate = limiteValido(f.ate) ? f.ate : ''
  if (!de && !ate) return true
  const iso = isoDaData(artefato.data_os)
  /* ⚠️ ARTEFATO SEM DATA FICA DE FORA de um filtro de período, e isso é
     deliberado: ele não está "dentro", e deixá-lo passar faria o total do
     período somar um serviço que ninguém sabe de quando é. */
  if (!iso) return false
  if (de && iso < de) return false
  if (ate && iso > ate) return false
  return true
}

/* ----------------------------------------------------------- busca e ordem */

function casouPor(a) {
  const t = busca.value.trim().toLowerCase()
  if (!t) return ''
  if (String(a.numero_os || '').toLowerCase().includes(t)) return 'OS'
  if (String(a.orcamento_numero || '').toLowerCase().includes(t)) return 'orçamento'
  if (String(a.termo || '').toLowerCase().includes(t)) return 'termo'
  if (String(a.cliente || '').toLowerCase().includes(t)) return 'cliente'
  if (String(a.tecnico_nome || '').toLowerCase().includes(t)) return 'técnico'
  if (String(a.tipo_nome || '').toLowerCase().includes(t)) return 'tipo da OS'
  return ''
}

function casa(a) {
  return !busca.value.trim() || !!casouPor(a)
}

function valorDe(a) {
  return (Number(a.valor_pagamento) || 0) + (Number(a.valor_km) || 0)
}

function ordenarArtefatos(lista) {
  const l = [...lista]
  /* ⚠️ SEM DATA VAI PARA O FIM nos dois sentidos: "não medido" não é "o mais
     antigo" nem "o mais novo" — é a mesma régua do *"parado há mais tempo"* da
     Operação, que manda card sem passagem para o fim. */
  const data = (a) => isoDaData(a.data_os) || ''
  switch (ordem.value) {
    case 'data_asc':
      return l.sort((x, y) => (data(x) || '9999').localeCompare(data(y) || '9999'))
    case 'data_desc':
      return l.sort((x, y) => (data(y) || '0000').localeCompare(data(x) || '0000'))
    case 'os_desc':
      return l.sort((x, y) => (y.numero_os || 0) - (x.numero_os || 0))
    case 'os_asc':
      return l.sort((x, y) => (x.numero_os || 0) - (y.numero_os || 0))
    case 'valor_desc':
      return l.sort((x, y) => valorDe(y) - valorDe(x))
    case 'cliente':
      return l.sort((x, y) => String(x.cliente || 'zzz')
        .localeCompare(String(y.cliente || 'zzz'), 'pt-BR'))
    default:
      return l
  }
}

function artefatosVisiveis(card) {
  return ordenarArtefatos(
    (card.artefatos || []).filter((a) => dentroDoFiltro(card, a) && casa(a)))
}

/* ⚠️ Nas colunas 2 a 5 não há filtro de período: o lote já foi fechado, e
   peneirá-lo por data esconderia parte de um pagamento que vai sair inteiro. */
function artefatosDoLote(card) {
  return ordenarArtefatos((card.artefatos || []).filter(casa))
}

function ordenarCards(cards, visiveis) {
  const l = [...cards]
  switch (ordemDosCards.value) {
    case 'valor':
      return l.sort((x, y) => totalDe(y, visiveis) - totalDe(x, visiveis))
    case 'tecnico':
      return l.sort((x, y) => String(x.tecnico_nome || 'zzz')
        .localeCompare(String(y.tecnico_nome || 'zzz'), 'pt-BR'))
    default:
      return l.sort((x, y) => visiveis(y).length - visiveis(x).length)
  }
}

function cardsDa(coluna) {
  const visiveis = coluna.chave === 'movimentacao'
    ? artefatosVisiveis : artefatosDoLote
  /* 🚨 CARD QUE FICOU SEM NENHUM ARTEFATO SOME DA BUSCA, mas não do quadro
     quando não há busca: card de técnico vazio é informação (ele não tem nada
     a pagar), card de técnico escondido pelo filtro é ruído. */
  const lista = busca.value.trim()
    ? (coluna.cards || []).filter((c) => visiveis(c).length)
    : (coluna.cards || [])
  return ordenarCards(lista, visiveis)
}

/* ------------------------------------------------------------- os totais */

function moeda(v) {
  return (Number(v) || 0).toLocaleString('pt-BR',
    { style: 'currency', currency: 'BRL' })
}

function totalDe(card, visiveis) {
  const lista = (visiveis || artefatosVisiveis)(card)
  return lista.reduce((s, a) => s + valorDe(a), 0)
}

function somaDe(card, campo, visiveis) {
  const lista = (visiveis || artefatosVisiveis)(card)
  return lista.reduce((s, a) => s + (Number(a[campo]) || 0), 0)
}

const artefatosNoQuadro = computed(() => quadro.value?.artefatos ?? 0)

const totalAPagar = computed(() => {
  let soma = 0
  for (const coluna of quadro.value?.colunas || []) {
    const visiveis = coluna.chave === 'movimentacao'
      ? artefatosVisiveis : artefatosDoLote
    for (const card of coluna.cards || []) soma += totalDe(card, visiveis)
  }
  return soma
})

/* -------------------------------------------------------- a marcação */

function marcadosDo(card) {
  return marcados.value[card.tecnico_id || 0] || MARCADOS_VAZIO
}

function estaMarcado(card, id) {
  return marcadosDo(card).includes(id)
}

function alternar(card, id) {
  const chave = card.tecnico_id || 0
  const atuais = marcadosDo(card)
  const novos = atuais.includes(id)
    ? atuais.filter((x) => x !== id)
    : [...atuais, id]
  marcados.value = { ...marcados.value, [chave]: novos }
}

function marcarTodosDoCard(card) {
  const chave = card.tecnico_id || 0
  /* ⚠️ "Todos" é "todos os que estão À VISTA": marcar o que o filtro de
     período escondeu prepararia pagamento de um mês que ninguém pediu. */
  marcados.value = { ...marcados.value,
                     [chave]: artefatosVisiveis(card).map((a) => a.id) }
}

function limparMarcados(card) {
  marcados.value = { ...marcados.value, [card.tecnico_id || 0]: [] }
}

/* ------------------------------------------------------------ as chamadas */

async function chamar(caminho, corpo, metodo = 'post') {
  erro.value = ''
  aviso.value = ''
  try {
    const r = metodo === 'get'
      ? await api.get(BASE + caminho)
      : await api.post(BASE + caminho, corpo || {})
    /* 🚨 RECUSA É RESPOSTA, não exceção: o motivo vem por extenso e aparece na
       tela. 🔵 *"os motivos de recusa deve aparecer descritos ao inves de erro
       generico, para que me tragam o problema ja cientes"*. */
    if (r && r.ok === false) {
      erro.value = r.motivo || 'A ação foi recusada e não veio o motivo.'
      return null
    }
    return r
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui completar.'
    return null
  }
}

async function varrer() {
  const r = await chamar('/varrer')
  if (r) {
    aviso.value = `Varredura: ${r.novos} artefato(s) novo(s), `
      + `${r.ja_existiam} que já existiam, ${r.sem_tecnico} sem técnico.`
    await carregar()
  }
}

async function preparar(card) {
  const ids = marcadosDo(card)
  if (!ids.length) return
  const r = await chamar('/preparar', { artefatos: ids })
  if (!r) return
  limparMarcados(card)
  if (r.recusados && r.recusados.length) {
    /* ⚠️ O QUE FICOU DE FORA É DITO, não descartado em silêncio: são os sem
       técnico, e eles existem para o dinheiro não sair de vista. */
    aviso.value = `${r.preparados} preparado(s). Ficaram de fora: `
      + r.recusados.map((x) => `OS ${x.numero_os} (${x.porque})`).join('; ')
  } else {
    aviso.value = `${r.preparados} artefato(s) em preparação.`
  }
  await carregar()
}

async function abrirConferencia(card) {
  const linhas = []
  for (const a of card.artefatos || []) {
    const r = await chamar(`/conferir/${a.id}`)
    if (r) linhas.push({ ...a, ...r })
  }
  conferindo.value = { card, linhas }
}

async function ciente(linha) {
  if (await chamar(`/ciente/${linha.id}`)) {
    linha.ciente_em = new Date().toISOString()
  }
}

function pedirDevolucao(linha) {
  devolvendo.value = linha
  justificativa.value = ''
}

async function devolver() {
  const alvo = devolvendo.value
  if (!alvo) return
  const r = await chamar('/devolver', {
    artefato_id: alvo.id, justificativa: justificativa.value,
  })
  if (r) {
    devolvendo.value = null
    conferindo.value = null
    aviso.value = `OS ${alvo.numero_os} voltou para a Movimentação.`
    await carregar()
  }
}

async function auditar(card) {
  const r = await chamar(`/auditar/${card.lote_id}`)
  if (r) {
    conferindo.value = null
    aviso.value = `${r.avancaram} avançaram; ${r.ficaram} ficaram sem ciente.`
    await carregar()
  }
}

async function revalidar(card) {
  const r = await chamar(`/revalidar/${card.lote_id}`)
  if (r) {
    aviso.value = `${r.revalidados} artefato(s) relidos.`
    await carregar()
  }
}

/* 🔵 19/11 — O SERVIÇO 2 QUE NINGUÉM ALCANÇAVA: *"fará a validação com o
   Datascope, trazendo a situação que estiver lá"*.
   ⚠️ SÓ LEITURA. A correção da situação lá (`change_state`) não entra: ela
   escreve em sistema de terceiro, dispara os webhooks deles e manda push ao
   técnico — e a rota de escrita não existe nem no FPSL. */
async function lerDataScope(card) {
  let lidos = 0
  let sem = 0
  for (const a of card.artefatos || []) {
    const r = await chamar(`/datascope/${a.id}`)
    if (!r) return
    if (r.form_state) lidos += 1
    else sem += 1
  }
  aviso.value = `DataScope lido: ${lidos} com registro, ${sem} `
    + 'sem registro para a OS.'
  await carregar()
}

/* 🔵 19/11 — O SERVIÇO 1 QUE NINGUÉM ALCANÇAVA, e o que destravava a coluna 3:
   *"haverá campo para que em cada 1 dos artefatos de pagamento seja inserido
   anexo que comprove o pagamento. Após o envio do anexo, abre o campo que pede
   o valor inserido no documento"*.

   🚨 SEM ESTE GESTO A COLUNA 3 ERA UM BECO: o `montar_arquivo` recusa o lote
   em que nenhum artefato tem comprovante nem dispensa, e nada na tela
   registrava um dos dois.

   ⚠️ O COMPROVANTE É UMA REFERÊNCIA DE TEXTO, não um arquivo subido: o campo
   do FPSL é `comprovante_arquivo TEXT`, e não existe rota de upload nesta
   frente. 🔴 Subir o PDF de verdade é a próxima peça e precisa da palavra dele
   (dono do arquivo, quem pode baixar, e uma migração para guardá-lo). */
function abrirComprovante(artefato) {
  comprovando.value = {
    artefato,
    arquivo: artefato.comprovante_arquivo || '',
    valor: artefato.valor_do_comprovante ?? null,
    dispensa: artefato.comprovante_dispensa || '',
  }
}

const comprovantePodeSalvar = computed(() => {
  const c = comprovando.value
  if (!c) return false
  /* 🚨 UM DOS DOIS É OBRIGATÓRIO — a mesma regra do servidor, dita aqui para
     a pessoa não descobrir na recusa. */
  return !!(String(c.arquivo || '').trim() || String(c.dispensa || '').trim())
})

async function salvarComprovante() {
  const c = comprovando.value
  if (!c) return
  const valor = c.valor === '' || c.valor === null || c.valor === undefined
    ? null : Number(c.valor)
  const r = await chamar('/comprovante', {
    artefato_id: c.artefato.id,
    arquivo: String(c.arquivo || '').trim() || null,
    valor,
    dispensa: String(c.dispensa || '').trim() || null,
  })
  if (r) {
    comprovando.value = null
    const s = SEMAFORO[r.semaforo]
    aviso.value = `OS ${c.artefato.numero_os}: comprovante registrado`
      + (s ? ` — ${s.texto}.` : '.')
    await carregar()
  }
}

/* 🔵 19/11 — O SERVIÇO 3 QUE NINGUÉM ALCANÇAVA: *"dentro deles um resumo dos
   artefatos que vão para pagamento"*. 🚨 E é aqui que o arquivo do Procfy diz
   QUAIS COLUNAS SAEM EM BRANCO, antes de alguém baixá-lo e descobrir na
   recusa da importação. ⚠️ Ver a prévia não move card. */
async function verPrevia(card) {
  const r = await chamar(`/previa/${card.lote_id}`, null, 'get')
  if (r) previa.value = { card, ...r }
}

async function montarArquivo(card) {
  const r = await chamar(`/montar-arquivo/${card.lote_id}`)
  if (r) {
    previa.value = null
    aviso.value = `Arquivo montado: ${r.avancaram} artefato(s)`
      + (r.ficaram ? `, ${r.ficaram} ficaram sem comprovante.` : '.')
    await carregar()
  }
}

function baixar(card) {
  /* ⚠️ `window.open` e não `fetch`: o navegador é quem salva o arquivo, e o
     cabeçalho `Content-Disposition` é o que dá o nome. */
  window.open(`${BASE}/arquivo/${card.lote_id}`, '_blank')
}

async function enviar(card) {
  const r = await chamar(`/enviar/${card.lote_id}`)
  if (r) {
    aviso.value = 'Lote marcado como pagamento enviado.'
    await carregar()
  }
}

/* 🔵 19/11 — A OS NO HARMONIT, a caixa que a aba 1 ganhou no mesmo dia.
   🚨 O NÚMERO SAI DO ARTEFATO: a rota é `/os/{artefato_id}` e não aceita
   `numero_os` de fora — quem alcança a PNL_1.6 lê só as OS do quadro dela. */
const temaAberto = ref('descricao')

async function abrirOs(artefato) {
  osAberta.value = { artefato, ficha: null, lendo: true, erro: '' }
  temaAberto.value = 'descricao'
  try {
    const ficha = await api.get(`${BASE}/os/${artefato.id}`)
    if (osAberta.value) {
      osAberta.value.ficha = ficha
      osAberta.value.lendo = false
    }
  } catch (e) {
    if (osAberta.value) {
      /* 🚨 ERRO, NÃO CAIXA VAZIA: ficha vazia é indistinguível de OS sem
         dados, e quem lê concluiria que não há o que ver. */
      osAberta.value.erro = e instanceof ErroDeApi
        ? e.message : 'Não deu para ler a OS no Harmonit agora.'
      osAberta.value.lendo = false
    }
  }
}

/* 🚨 OS MESMOS QUATRO TEMAS DA OPERAÇÃO E DA ABA 1, na mesma ordem e com os
   mesmos títulos. ⚠️ VAZIO É DITO, nunca deixado em branco: caixa branca
   parece defeito. */
const temas = computed(() => {
  const f = osAberta.value?.ficha
  return [
    {
      chave: 'descricao',
      titulo: 'Descrição da OS',
      resumo: f ? (f.descricao || 'sem descrição escrita') : '…',
      texto: f?.descricao || null,
      vazio: !!f && !f.descricao,
      ligado: true,
    },
    {
      chave: 'solucao',
      titulo: 'Solução técnica',
      resumo: f ? (f.solucao_tecnica || 'sem solução técnica escrita') : '…',
      texto: f?.solucao_tecnica || null,
      vazio: !!f && !f.solucao_tecnica,
      ligado: true,
    },
    {
      chave: 'chamado',
      titulo: 'Dados do chamado',
      resumo: f
        ? (f.chamado
            ? `${f.chamado.formulario} · ${f.chamado.respostas.length} campos`
              + (f.chamado.anexos ? ` · ${f.chamado.anexos} anexo(s)` : '')
            : 'esta OS não veio de formulário')
        : '…',
      respostas: f?.chamado?.respostas || [],
      vazio: !!f && !f.chamado,
      ligado: true,
    },
    {
      chave: 'agendamento',
      titulo: 'Agendamento',
      ligado: !!f?.tem_agendamento,
      resumo: f
        ? (f.tem_agendamento
            ? `${f.agendamentos.length} compromisso(s)`
            : 'nenhum compromisso nesta OS')
        : '…',
      agendamentos: f?.agendamentos || [],
      vazio: !!f && !f.tem_agendamento,
    },
  ]
})

function alternarColuna(coluna) {
  abertas.value[coluna.chave] = !abertas.value[coluna.chave]
}

/* ⚠️ A ORDEM DO `Escape` É DELIBERADA: fecha o modal mais de cima primeiro, e
   não todos de uma vez — fechar a pilha inteira perderia o que a pessoa
   estava fazendo embaixo. */
function aoTeclar(evento) {
  if (evento.key !== 'Escape') return
  if (devolvendo.value) { devolvendo.value = null; return }
  if (comprovando.value) { comprovando.value = null; return }
  if (previa.value) { previa.value = null; return }
  if (osAberta.value) { osAberta.value = null; return }
  if (conferindo.value) conferindo.value = null
}

onMounted(() => {
  window.addEventListener('keydown', aoTeclar)
  carregar()
})
onBeforeUnmount(() => window.removeEventListener('keydown', aoTeclar))
</script>

<template>
  <section class="painel escala-operacao">
    <header class="painel__topo">
      <h1 class="painel__titulo">{{ tituloDoPainel }}</h1>
      <div class="painel__medidas">
        <span class="pilula">
          {{ artefatosNoQuadro }}
          {{ artefatosNoQuadro === 1 ? 'artefato' : 'artefatos' }}
        </span>
        <span class="pilula pilula--valor">{{ moeda(totalAPagar) }}</span>
        <button class="botao botao--contorno" type="button"
                :disabled="carregando" @click="carregar">
          <i class="bi bi-arrow-clockwise" aria-hidden="true"></i>
          Atualizar
        </button>
        <button class="botao" type="button" @click="varrer">
          <i class="bi bi-arrow-repeat" aria-hidden="true"></i>
          Buscar serviços
        </button>
      </div>
    </header>

    <!-- 🔵 A TIRA DE ABAS, igual à da aba 1. ⚠️ Com uma aba só a barra não
         aparece: uma aba sozinha não é escolha. -->
    <nav v-if="abasVisiveis.length > 1" class="abas"
         :aria-label="`Abas de ${tituloDoPainel}`">
      <RouterLink v-for="a in abasVisiveis" :key="a.codigo" :to="a.rota"
                  class="abas__item"
                  :class="{ 'abas__item--atual': a.codigo === codigoDesta }"
                  :aria-current="a.codigo === codigoDesta ? 'page' : undefined">
        {{ a.titulo }}
      </RouterLink>
    </nav>

    <!-- 🔵 *"regras de ordenamento tbm da etapa de op faltam aqui"*. -->
    <div class="controles">
      <label class="controles__busca">
        <span class="so-leitor">
          Procurar por cliente, número da OS, termo, orçamento ou técnico
        </span>
        <input v-model="busca" type="search"
               placeholder="cliente, OS, termo, orçamento ou técnico" />
      </label>

      <label class="controles__ordem">
        <span class="so-leitor">Ordenar os artefatos dentro do card</span>
        <select v-model="ordem">
          <option v-for="(rot, chave) in ROTULO_ORDEM" :key="chave"
                  :value="chave">{{ rot }}</option>
        </select>
      </label>

      <label class="controles__ordem">
        <span class="so-leitor">Ordenar os cards</span>
        <select v-model="ordemDosCards">
          <option v-for="(rot, chave) in ROTULO_ORDEM_CARDS" :key="chave"
                  :value="chave">{{ rot }}</option>
        </select>
      </label>
    </div>

    <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>
    <p v-if="aviso" class="aviso" role="status">{{ aviso }}</p>
    <p v-if="carregando && !quadro" class="nota">Abrindo…</p>

    <BarraDeRolagem v-if="quadro" :rolo="rolo"
                    rotulo="quadro de Serviço dos técnicos" />

    <div v-if="quadro" class="painel__casco">
      <RolagemDaBorda :rolo="rolo" rotulo="quadro" />
      <div ref="rolo" class="painel__quadro">
        <div v-for="(coluna, indice) in quadro.colunas" :key="coluna.chave"
             class="coluna" :class="{ 'coluna--vazia': !coluna.total }"
             :style="{ borderTopColor: corDaColuna(indice) }"
             :aria-label="TITULOS[coluna.chave] || coluna.chave">
          <h2 class="coluna__titulo">
            <button class="coluna__botao" type="button"
                    :aria-expanded="abertas[coluna.chave] ? 'true' : 'false'"
                    @click="alternarColuna(coluna)">
              <span class="coluna__nome">
                {{ TITULOS[coluna.chave] || coluna.chave }}
              </span>
              <span class="coluna__conta"
                    :class="{ 'coluna__conta--zero': !coluna.total }">
                {{ coluna.total }}
              </span>
            </button>
          </h2>

          <div v-if="abertas[coluna.chave]" class="coluna__corpo">
            <!-- ================= COLUNA 1 — Movimentação ================= -->
            <template v-if="coluna.chave === 'movimentacao'">
              <article v-for="card in cardsDa(coluna)"
                       :key="card.tecnico_id || 0" class="card">
                <div class="card__abrir"
                     :class="{ 'card__abrir--sem-tecnico': !card.pode_preparar }">
                  <span class="card__linha">
                    <span class="card__cliente"
                          :title="card.tecnico_nome || ''">
                      {{ card.tecnico_nome || 'técnico ' + card.tecnico_id }}
                    </span>
                    <span class="card__direita">
                      {{ artefatosVisiveis(card).length }} de
                      {{ (card.artefatos || []).length }}
                    </span>
                  </span>

                  <span class="card__linha card__dado">
                    <span>
                      a pagar <strong>{{ moeda(totalDe(card)) }}</strong>
                      &middot; serviço
                      {{ moeda(somaDe(card, 'valor_pagamento')) }}
                      &middot; km {{ moeda(somaDe(card, 'valor_km')) }}
                    </span>
                  </span>

                  <!-- 🔵 O FILTRO DE DATAS DENTRO DO CARD: *"só quero fechar
                       de 16-18/11/26 filtro isso e flego"*. ⚠️ A data é a do
                       SERVIÇO, e o filtro é DESTE card. -->
                  <!-- ⚠️ `:value` + `@input`, e NÃO `v-model`: o alvo seria
                       `filtroDo(card).de`, e `v-model` exige uma expressão de
                       membro simples — chamada de função no caminho é erro de
                       compilação do template. -->
                  <div class="card__filtro">
                    <label>de
                      <input type="date" :value="filtroDo(card).de"
                             @change="definirFiltro(card, 'de', $event.target.value)" />
                    </label>
                    <label>até
                      <input type="date" :value="filtroDo(card).ate"
                             @change="definirFiltro(card, 'ate', $event.target.value)" />
                    </label>
                    <button v-if="filtroDo(card).de || filtroDo(card).ate"
                            class="botao botao--fraco" type="button"
                            @click="limparFiltro(card)">
                      limpar
                    </button>
                  </div>

                  <ul class="artefatos">
                    <li v-for="a in artefatosVisiveis(card)" :key="a.id"
                        class="artefato">
                      <label class="artefato__marca">
                        <input type="checkbox"
                               :checked="estaMarcado(card, a.id)"
                               :disabled="!card.pode_preparar"
                               @change="alternar(card, a.id)" />
                        <!-- 🔵 A ordem é a dele: Orçamento — OS — TERMO. -->
                        <span v-if="a.orcamento_numero"
                              class="artefato__orcamento">
                          Orç {{ a.orcamento_numero }}
                        </span>
                        <span v-else
                              class="artefato__orcamento artefato__orcamento--sem">
                          <i class="bi bi-exclamation-circle" aria-hidden="true"></i>
                          sem orçamento
                        </span>
                        <button class="artefato__os" type="button"
                                @click.stop.prevent="abrirOs(a)">
                          OS {{ a.numero_os }}
                        </button>
                        <span v-if="a.termo" class="artefato__termo">
                          TERMO {{ a.termo }}
                        </span>
                        <span class="artefato__valor">
                          {{ moeda(valorDe(a)) }}
                        </span>
                      </label>

                      <!-- 🔵 19/11: os dados da OS, *"como a aba1 apresenta"*.
                           ⚠️ Cliente sem nome é DITO, não deixado em branco —
                           a frase é a mesma do card da aba 1. -->
                      <p class="artefato__os-dados">
                        <span v-if="a.cliente" class="artefato__cliente"
                              :title="a.cliente">{{ a.cliente }}</span>
                        <span v-else class="artefato__cliente artefato__cliente--sem">
                          cliente {{ a.cliente_id || '?' }}, fora do nosso cadastro
                        </span>
                        <span v-if="a.tipo_nome">&middot; {{ a.tipo_nome }}</span>
                        <span>&middot; serviço {{ dataCurta(a.data_os) }}</span>
                        <span v-if="a.status_str">&middot; {{ a.status_str }}</span>
                      </p>

                      <p v-if="casouPor(a)" class="artefato__casou">
                        casou por {{ casouPor(a) }}
                      </p>

                      <!-- 🔵 O devolvido é LARANJA e a justificativa fica à
                           vista: laranja sem motivo é cor sem informação. -->
                      <p v-if="a.semaforo === 'laranja'" class="artefato__devolvido">
                        <i class="bi bi-arrow-counterclockwise" aria-hidden="true"></i>
                        devolvido: {{ a.justificativa }}
                      </p>
                    </li>
                  </ul>

                  <p v-if="!artefatosVisiveis(card).length" class="nota pequeno">
                    Nenhum artefato à vista com este filtro.
                  </p>

                  <!-- 🚨 O card dos SEM TÉCNICO não prepara, e DIZ por quê:
                       sem técnico não há a quem pagar. Ele existe para o
                       dinheiro não sair de vista. -->
                  <p v-if="!card.pode_preparar" class="card__trava">
                    <i class="bi bi-info-circle" aria-hidden="true"></i>
                    Estas OS têm valor de pagamento e nenhum técnico
                    identificado na linha. Não há a quem pagar até alguém
                    vincular o técnico na OS.
                  </p>
                  <div v-else class="card__acoes">
                    <button class="botao botao--fraco" type="button"
                            @click="marcarTodosDoCard(card)">
                      Marcar todos
                    </button>
                    <button v-if="marcadosDo(card).length"
                            class="botao botao--fraco" type="button"
                            @click="limparMarcados(card)">
                      Limpar
                    </button>
                    <button class="botao" type="button"
                            :disabled="!marcadosDo(card).length"
                            @click="preparar(card)">
                      Preparar os marcados ({{ marcadosDo(card).length }})
                    </button>
                  </div>
                </div>
              </article>
            </template>

            <!-- ============ COLUNAS 2 a 5 — os lotes por técnico ========= -->
            <template v-else>
              <article v-for="card in cardsDa(coluna)" :key="card.lote_id"
                       class="card">
                <div class="card__abrir">
                  <span class="card__linha">
                    <span class="card__cliente" :title="card.tecnico_nome || ''">
                      {{ card.tecnico_nome || 'técnico ' + card.tecnico_id }}
                    </span>
                    <span class="card__direita">
                      lote {{ card.lote_id }}
                    </span>
                  </span>

                  <span class="card__linha card__dado">
                    <span>
                      {{ artefatosDoLote(card).length }} artefato(s) &middot;
                      <strong>
                        {{ moeda(totalDe(card, artefatosDoLote)) }}
                      </strong>
                    </span>
                  </span>

                  <ul class="artefatos">
                    <li v-for="a in artefatosDoLote(card)" :key="a.id"
                        class="artefato">
                      <span class="artefato__marca">
                        <button class="artefato__os" type="button"
                                @click.stop.prevent="abrirOs(a)">
                          OS {{ a.numero_os }}
                        </button>
                        <span v-if="a.termo" class="artefato__termo">
                          TERMO {{ a.termo }}
                        </span>
                        <span class="artefato__valor">
                          {{ moeda(valorDe(a)) }}
                        </span>
                      </span>

                      <p class="artefato__os-dados">
                        <span v-if="a.cliente" class="artefato__cliente"
                              :title="a.cliente">{{ a.cliente }}</span>
                        <span v-else class="artefato__cliente artefato__cliente--sem">
                          cliente {{ a.cliente_id || '?' }}, fora do nosso cadastro
                        </span>
                        <span>&middot; serviço {{ dataCurta(a.data_os) }}</span>
                      </p>

                      <p class="artefato__selos">
                        <!-- 🚨 Ícone E texto: cor sozinha não é portadora. -->
                        <span v-if="a.semaforo" class="selo"
                              :class="'selo--' + a.semaforo">
                          <i :class="'bi ' + SEMAFORO[a.semaforo].icone"
                             aria-hidden="true"></i>
                          {{ SEMAFORO[a.semaforo].texto }}
                        </span>
                        <span v-if="a.datascope_form_state" class="selo">
                          DataScope: {{ a.datascope_form_state }}
                        </span>
                        <span v-if="a.comprovante_arquivo" class="selo selo--verde">
                          <i class="bi bi-paperclip" aria-hidden="true"></i>
                          comprovante
                          <template v-if="a.valor_do_comprovante != null">
                            {{ moeda(a.valor_do_comprovante) }}
                          </template>
                        </span>
                        <span v-else-if="a.comprovante_dispensa" class="selo selo--amarelo">
                          <i class="bi bi-chat-left-text" aria-hidden="true"></i>
                          dispensado: {{ a.comprovante_dispensa }}
                        </span>

                        <!-- 🔵 19/11: o comprovante, que a tela não tinha.
                             🚨 Só na Validação: depois do arquivo montado,
                             mexer no recibo mudaria o que já foi para o
                             Procfy. -->
                        <button v-if="coluna.chave === 'validacao'"
                                class="botao botao--fraco botao--mini"
                                type="button" @click="abrirComprovante(a)">
                          {{ a.comprovante_arquivo || a.comprovante_dispensa
                             ? 'Trocar comprovante' : 'Comprovante' }}
                        </button>
                      </p>
                    </li>
                  </ul>

                  <div class="card__acoes">
                    <!-- 🔵 *"todos os cards tem botão de 'atualizar'"*. -->
                    <button class="botao botao--fraco" type="button"
                            @click="revalidar(card)">Atualizar</button>

                    <button v-if="coluna.chave === 'preparacao'" class="botao"
                            type="button" @click="abrirConferencia(card)">
                      Conferir e auditar
                    </button>

                    <template v-if="coluna.chave === 'validacao'">
                      <button class="botao botao--fraco" type="button"
                              @click="lerDataScope(card)">
                        Ler DataScope
                      </button>
                      <button class="botao botao--fraco" type="button"
                              @click="verPrevia(card)">
                        Ver prévia
                      </button>
                      <button class="botao" type="button"
                              @click="montarArquivo(card)">
                        Montar arquivo
                      </button>
                    </template>

                    <template v-if="coluna.chave === 'procfy'">
                      <button class="botao botao--fraco" type="button"
                              @click="verPrevia(card)">Ver prévia</button>
                      <button class="botao" type="button" @click="baixar(card)">
                        Baixar o arquivo
                      </button>
                      <button class="botao botao--fraco" type="button"
                              @click="enviar(card)">Marcar como enviado</button>
                    </template>
                  </div>
                </div>
              </article>
            </template>

            <p v-if="!cardsDa(coluna).length" class="nota pequeno">
              {{ busca.trim() ? 'Nenhum card casa com a busca.' : 'Vazia.' }}
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- 🔵 O MODAL DE CONFERIR, da coluna 2: *"exibir para o operador
         confirmar 1 a 1 na tela modal que abrir"*. -->
    <div v-if="conferindo" class="modal" role="dialog" aria-modal="true">
      <div class="modal__caixa">
        <h2>Conferir a situação, uma a uma</h2>
        <ul class="conferencia">
          <li v-for="l in conferindo.linhas" :key="l.id">
            <button class="artefato__os" type="button" @click="abrirOs(l)">
              OS {{ l.numero_os }}
            </button>
            <span class="selo" :class="l.libera ? 'selo--verde' : 'selo--amarelo'">
              <i :class="'bi ' + (l.libera ? 'bi-check-circle-fill'
                                           : 'bi-exclamation-circle-fill')"
                 aria-hidden="true"></i>
              {{ l.motivo }}
            </span>
            <span v-if="l.etapa_nossa" class="selo">
              está em Serviço Realizado (etapa nossa)
            </span>
            <button v-if="!l.ciente_em" class="botao botao--fraco" type="button"
                    @click="ciente(l)">Ciente</button>
            <span v-else class="selo selo--verde">
              <i class="bi bi-check2" aria-hidden="true"></i> ciente
            </span>
            <button class="botao botao--fraco" type="button"
                    @click="pedirDevolucao(l)">Remover</button>
          </li>
        </ul>
        <div class="modal__acoes">
          <button class="botao botao--fraco" type="button"
                  @click="conferindo = null">Fechar</button>
          <!-- 🔵 *"irá mover o card somente com os cientes de situação e não
               negados para a próxima coluna"*. -->
          <button class="botao" type="button"
                  @click="auditar(conferindo.card)">Auditar</button>
        </div>
      </div>
    </div>

    <!-- 🔵 *"abrindo um campo de justificativa com campo de texto pequeno"*. -->
    <div v-if="devolvendo" class="modal" role="dialog" aria-modal="true">
      <div class="modal__caixa modal__caixa--curta">
        <h2>Por que está removendo?</h2>
        <p class="nota pequeno">
          A OS {{ devolvendo.numero_os }} volta para a Movimentação em laranja,
          com esta justificativa à vista.
        </p>
        <input v-model="justificativa" class="campo" maxlength="400"
               placeholder="ex.: OS ainda em Agendar serviço" />
        <div class="modal__acoes">
          <button class="botao botao--fraco" type="button"
                  @click="devolvendo = null">Cancelar</button>
          <button class="botao" type="button" :disabled="!justificativa.trim()"
                  @click="devolver">Remover</button>
        </div>
      </div>
    </div>

    <!-- 🔵 19/11 — O COMPROVANTE: *"haverá campo para que em cada 1 dos
         artefatos de pagamento seja inserido anexo que comprove o pagamento.
         Após o envio do anexo, abre o campo que pede o valor"*. -->
    <div v-if="comprovando" class="modal" role="dialog" aria-modal="true">
      <div class="modal__caixa modal__caixa--curta">
        <h2>Comprovante da OS {{ comprovando.artefato.numero_os }}</h2>
        <p class="nota pequeno">
          A pagar {{ moeda(valorDe(comprovando.artefato)) }} —
          serviço {{ moeda(comprovando.artefato.valor_pagamento) }} e km
          {{ moeda(comprovando.artefato.valor_km) }}.
        </p>

        <label class="campo__rotulo">
          Comprovante (link ou nome do arquivo)
          <input v-model="comprovando.arquivo" class="campo" maxlength="400"
                 placeholder="ex.: recibo_franck_1811.pdf" />
        </label>

        <!-- 🔵 *"Após o envio do anexo, abre o campo que pede o valor inserido
             no documento"* — o campo do valor só existe quando há comprovante:
             valor sem documento não tem o que conferir. -->
        <label v-if="comprovando.arquivo.trim()" class="campo__rotulo">
          Valor que está no documento
          <input v-model="comprovando.valor" class="campo" type="number"
                 step="0.01" min="0" placeholder="0,00" />
        </label>

        <!-- 🔵 *"avança com os que tiveram ou arquivo enviado ou justificativa
             escrita na tela de envio de anexo (pode não ter)"*. -->
        <label class="campo__rotulo">
          Ou a justificativa de quem não tem comprovante
          <input v-model="comprovando.dispensa" class="campo" maxlength="400"
                 placeholder="ex.: pago em dinheiro, sem recibo" />
        </label>

        <p class="nota pequeno">
          🚨 Sem comprovante e sem justificativa não há o que registrar — e o
          artefato fica parado na Validação quando o arquivo for montado.
        </p>

        <div class="modal__acoes">
          <button class="botao botao--fraco" type="button"
                  @click="comprovando = null">Cancelar</button>
          <button class="botao" type="button" :disabled="!comprovantePodeSalvar"
                  @click="salvarComprovante">Salvar</button>
        </div>
      </div>
    </div>

    <!-- 🔵 19/11 — A PRÉVIA: *"dentro deles um resumo dos artefatos que vão
         para pagamento"*. 🚨 E é onde as colunas em branco do Procfy são
         ditas ANTES de alguém baixar o arquivo. -->
    <div v-if="previa" class="modal" role="dialog" aria-modal="true">
      <div class="modal__caixa">
        <h2>O que vai para o Procfy — {{ previa.tecnico }}</h2>
        <p class="nota pequeno">
          {{ previa.artefatos }} artefato(s) &middot;
          <strong>{{ moeda(previa.total) }}</strong>
        </p>

        <p v-if="previa.aviso" class="aviso" role="status">
          <i class="bi bi-exclamation-triangle" aria-hidden="true"></i>
          {{ previa.aviso }}
        </p>

        <div class="previa__rolo">
          <table class="previa">
            <thead>
              <tr>
                <th>OS / descrição</th>
                <th>competência</th>
                <th>valor</th>
                <th>documento</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(l, i) in previa.linhas" :key="i">
                <td>{{ l['Descrição'] }}</td>
                <td>{{ l['Data de competência'] }}</td>
                <td>{{ l['Valor'] }}</td>
                <td>{{ l['Observações'] }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="modal__acoes">
          <button class="botao botao--fraco" type="button"
                  @click="previa = null">Fechar</button>
          <button v-if="previa.card && previa.card.coluna === 'validacao'"
                  class="botao" type="button"
                  @click="montarArquivo(previa.card)">Montar arquivo</button>
        </div>
      </div>
    </div>

    <!-- 🔵 19/11 — A OS NO HARMONIT, os quatro temas da Operação. -->
    <div v-if="osAberta" class="modal" role="dialog" aria-modal="true">
      <div class="modal__caixa">
        <h2>OS {{ osAberta.artefato.numero_os }} no Harmonit</h2>

        <p v-if="osAberta.lendo" class="nota pequeno">
          Lendo a OS no Harmonit…
        </p>
        <p v-else-if="osAberta.erro" class="aviso aviso--erro" role="alert">
          {{ osAberta.erro }}
        </p>

        <div class="temas__abas" role="tablist">
          <button v-for="t in temas" :key="t.chave" type="button" role="tab"
                  class="temas__aba"
                  :class="{ 'temas__aba--ativa': temaAberto === t.chave,
                            'temas__aba--apagada': !t.ligado }"
                  :aria-selected="temaAberto === t.chave"
                  :disabled="!t.ligado"
                  @click="temaAberto = t.chave">
            <strong>{{ t.titulo }}</strong>
            <span class="temas__resumo">{{ t.resumo }}</span>
          </button>
        </div>

        <div v-for="t in temas" :key="`c-${t.chave}`" class="temas__corpo">
          <template v-if="temaAberto === t.chave">
            <p v-if="t.vazio" class="nota pequeno">{{ t.resumo }}</p>
            <pre v-else-if="t.texto" class="temas__texto">{{ t.texto }}</pre>
            <dl v-else-if="t.respostas && t.respostas.length"
                class="temas__respostas">
              <template v-for="r in t.respostas" :key="r.nome">
                <dt>{{ r.rotulo }}</dt>
                <dd>{{ Array.isArray(r.valor) ? r.valor.join(' · ') : r.valor }}</dd>
              </template>
            </dl>
            <ul v-else-if="t.agendamentos && t.agendamentos.length"
                class="temas__respostas">
              <li v-for="a in t.agendamentos" :key="a.agendamento_id">
                {{ a.nome || `usuário ${a.usuario_id}` }} —
                compromisso {{ a.agendamento_id }}
              </li>
            </ul>
            <p v-else class="nota pequeno">{{ t.resumo }}</p>
          </template>
        </div>

        <div class="modal__acoes">
          <button class="botao botao--fraco" type="button"
                  @click="osAberta = null">Fechar</button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
/* 🚨 QUATRO VARIÁVEIS QUE NÃO EXISTEM, E QUE ESTE ARQUIVO USAVA ATÉ 19/11.
   📏 Medido: `--sucesso`, `--perigo`, `--r-2` e `--r-3` não estão definidos em
   `estilo/*.css` nem em lugar nenhum do frontend. Declaração com `var()` que
   não resolve é DESCARTADA EM SILÊNCIO pelo navegador — então o selo verde
   ficava sem verde, o vermelho sem vermelho e os cantos sem raio, sem um erro
   no console. ⚠️ E o jsdom não faz layout: nenhuma suíte de tela veria.
   Os nomes certos, do `tokens.css`: `--ok` (#16A34A), `--erro` (#DC2626),
   `--r-md` e `--r-lg` (8px). É a lição do `conferir_css_publicado.mjs`.
   🚨 O MESMO DEFEITO ESTÁ NO `CorpoDoCard.vue`, que desenha o card da aba 1 e
   o da Operação — lá apaga o verde do checklist completo e o VERMELHO do
   *"atrasado"*. Vai num patch próprio.

   🚨 O CASCO É O DA ABA 1, e isto é o pedido de 19/11: *"como a aba1
   apresenta"*. As medidas são as que ele aprovou na Operação em 05/11
   (*"vendo 3 colunas por scroll esta ok"*), e repeti-las aqui não é
   duplicação à toa: as classes vivem em `<style scoped>` por componente, e
   foi a lição do `max-width` de 05/11 e da `.pilula` de 12/11 — nome de
   classe de outra tela não alcança esta. */
.painel { display: flex; flex-direction: column; gap: var(--e-4); }
.painel__topo {
  display: flex; flex-wrap: wrap; gap: var(--e-3);
  align-items: center; justify-content: space-between;
}
.painel__titulo { margin: 0; font-size: var(--txt-lg); }
.painel__medidas { display: flex; align-items: center; gap: var(--e-2); flex-wrap: wrap; }

/* 🚨 `relative` É A CONDIÇÃO da faixa de rolagem da borda: ela é
   `position: absolute` e, sem um ancestral posicionado, ancoraria no elemento
   que rola — e andaria junto com o conteúdo em vez de ficar parada na borda. */
.painel__casco { position: relative; }

.abas {
  display: flex; gap: var(--e-1); flex-wrap: wrap;
  border-bottom: var(--borda-fina) solid var(--borda);
}
.abas__item {
  padding: var(--e-2) var(--e-3);
  border-bottom: 3px solid transparent;
  color: var(--texto-fraco); text-decoration: none;
  font-size: var(--txt-sm); font-weight: var(--peso-forte);
}
.abas__item:hover { color: var(--texto); background: var(--superficie-2); }
.abas__item--atual { color: var(--texto); border-bottom-color: var(--acento); }

.controles {
  display: flex; flex-wrap: wrap; gap: var(--e-2); align-items: center;
}
.controles__busca input, .controles__ordem select {
  padding: var(--e-2); border-radius: var(--r-md);
  border: var(--borda-fina) solid var(--borda-forte);
  background: var(--superficie); color: var(--texto);
  /* ⚠️ 16px nos campos: abaixo disso o iOS dá zoom ao focar. */
  font-size: 16px;
}
.controles__busca input { min-width: 260px; }

.painel__quadro {
  display: flex; gap: var(--e-3);
  overflow-x: auto; padding-bottom: var(--e-2);
  align-items: flex-start;
}
.coluna {
  flex: 0 0 360px;
  background: var(--fundo);
  border: var(--borda-fina) solid var(--borda);
  border-top: 3px solid var(--borda-forte);
  border-radius: var(--r-md);
  padding: var(--e-3);
}
.coluna--vazia { opacity: .8; }
.coluna__titulo { margin: 0; font-size: var(--txt-sm); }
.coluna__botao {
  width: 100%; display: flex; align-items: center;
  justify-content: space-between; gap: var(--e-2);
  border: 0; background: transparent; cursor: pointer;
  font: inherit; color: var(--texto); padding: 0 0 var(--e-2);
  text-align: left;
}
.coluna__nome { font-weight: var(--peso-forte); }
.coluna__conta {
  flex: 0 0 auto; min-width: 22px; text-align: center;
  padding: 0 var(--e-1); border-radius: var(--r-full);
  background: var(--acento); color: #FFFFFF;
  font-size: var(--txt-xs); font-weight: var(--peso-forte);
}
.coluna__conta--zero {
  background: transparent; color: var(--texto-fraco);
  border: var(--borda-fina) solid var(--borda-forte);
}
.coluna__corpo { display: flex; flex-direction: column; gap: var(--e-2); }

/* 🚨 A COLUNA RECUA E O CARD É BRANCO, com sombra e borda forte: os dois eram
   `--superficie` na Operação até 05/11, e 1px no tom mais claro da paleta era
   a única separação — era isso que fazia as caixas não terem limite. */
.card { border-radius: var(--r-md); }
.card__abrir {
  display: flex; flex-direction: column; gap: var(--e-2);
  width: 100%; padding: var(--e-2) var(--e-3);
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda-forte);
  border-left: 3px solid transparent;
  border-radius: var(--r-md);
  box-shadow: var(--sombra-1);
  text-align: left;
}
.card__abrir:hover { box-shadow: var(--sombra-2); }

/* 🚨 O CARD DOS SEM TÉCNICO É VISIVELMENTE OUTRO, e nunca só pela cor: a
   frase que explica por que ele não prepara está dentro dele. */
.card__abrir--sem-tecnico { border-left-color: var(--aviso); }

.card__linha {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: var(--e-2); width: 100%;
}
.card__cliente {
  font-weight: var(--peso-forte); font-size: var(--txt-sm);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.card__direita {
  flex: none; font-size: var(--txt-xs); color: var(--texto-fraco);
  white-space: nowrap;
}
.card__dado { font-size: var(--txt-xs); color: var(--texto-fraco); }
.card__filtro {
  display: flex; gap: var(--e-2); font-size: var(--txt-xs);
  align-items: center; flex-wrap: wrap;
}
.card__filtro input { font-size: 16px; }
.card__trava {
  margin: 0; font-size: var(--txt-xs); color: var(--texto-fraco);
  display: flex; gap: var(--e-1);
}
.card__acoes { display: flex; flex-wrap: wrap; gap: var(--e-2); }

.artefatos {
  list-style: none; margin: 0; padding: 0;
  display: flex; flex-direction: column; gap: var(--e-2);
}
.artefato {
  display: flex; flex-direction: column; gap: 2px;
  font-size: var(--txt-xs);
  padding-bottom: var(--e-1);
  border-bottom: var(--borda-fina) solid var(--borda);
}
.artefato:last-child { border-bottom: 0; padding-bottom: 0; }
.artefato__marca {
  display: flex; flex-wrap: wrap; align-items: center;
  gap: var(--e-1); cursor: pointer;
}
/* ⚠️ A OS é o BOTÃO e o único em cor de acento, como no card da aba 1: o
   termo e o orçamento são referência, não ação. */
.artefato__os {
  padding: 0; border: 0; background: none; cursor: pointer;
  font-family: inherit; color: var(--acento);
  font-weight: var(--peso-forte); font-size: var(--txt-xs);
}
.artefato__os:hover { text-decoration: underline; }
.artefato__termo, .artefato__orcamento { color: var(--texto-fraco); }
.artefato__orcamento--sem { color: var(--aviso); }
.artefato__valor { margin-left: auto; font-weight: var(--peso-forte); }
.artefato__os-dados {
  margin: 0; color: var(--texto-fraco);
  display: flex; flex-wrap: wrap; gap: var(--e-1);
}
.artefato__cliente {
  font-weight: var(--peso-forte); color: var(--texto);
  max-width: 100%; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap;
}
.artefato__cliente--sem { font-weight: var(--peso-normal); color: var(--texto-fraco); }
.artefato__casou { margin: 0; color: var(--texto-fraco); font-style: italic; }
.artefato__selos { margin: 0; display: flex; flex-wrap: wrap; gap: var(--e-1);
                   align-items: center; }
.artefato__devolvido {
  margin: 0; color: var(--aviso); display: flex; gap: var(--e-1);
}

/* 🚨 CLASSE PRÓPRIA, NUNCA `.pilula` emprestada: ela é `scoped` por
   componente e não existe em `estilo/*.css` — o selo nasceria sem estilo, e o
   jsdom, que não faz layout, não pegaria. É a lição de 05–11/11. */
.selo {
  display: inline-flex; align-items: center; gap: var(--e-1);
  padding: 1px var(--e-2);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-full);
  font-size: var(--txt-xs); color: var(--texto-fraco);
}
.selo--verde { border-color: var(--ok); color: var(--ok); }
.selo--amarelo { border-color: var(--aviso); color: var(--aviso); }
.selo--laranja { border-color: var(--aviso); color: var(--aviso); }
.selo--vermelho { border-color: var(--erro); color: var(--erro); }

/* ⚠️ A `.pilula` do cabeçalho é DESTE componente, pelo mesmo motivo. */
.pilula {
  display: inline-flex; align-items: center; gap: var(--e-1);
  padding: 1px var(--e-2); border-radius: var(--r-full);
  background: var(--superficie-2); color: var(--texto-fraco);
  font-size: var(--txt-xs); font-weight: var(--peso-forte);
}
.pilula--valor { color: var(--texto); }

.botao--mini { font-size: var(--txt-xs); padding: 1px var(--e-2); }

.modal {
  position: fixed; inset: 0; display: grid; place-items: center;
  background: rgba(0, 0, 0, .45); z-index: var(--z-modal, 50);
}
.modal__caixa {
  width: min(760px, 92vw); max-height: 86vh; overflow: auto;
  padding: var(--e-4); border-radius: var(--r-lg);
  background: var(--superficie); display: flex; flex-direction: column;
  gap: var(--e-3);
}
.modal__caixa--curta { width: min(460px, 92vw); }
.modal__acoes { display: flex; justify-content: flex-end; gap: var(--e-2); }
.campo__rotulo {
  display: flex; flex-direction: column; gap: var(--e-1);
  font-size: var(--txt-xs); color: var(--texto-fraco);
}
.campo__rotulo .campo { font-size: 16px; }

.conferencia {
  list-style: none; margin: 0; padding: 0;
  display: flex; flex-direction: column; gap: var(--e-2);
}
.conferencia li {
  display: flex; flex-wrap: wrap; align-items: center;
  gap: var(--e-2); font-size: var(--txt-xs);
}

.previa__rolo { overflow: auto; max-height: 46vh; }
.previa { width: 100%; border-collapse: collapse; font-size: var(--txt-xs); }
.previa th, .previa td {
  text-align: left; padding: var(--e-1) var(--e-2);
  border-bottom: var(--borda-fina) solid var(--borda);
}
.previa th { color: var(--texto-fraco); font-weight: var(--peso-forte); }

/* ⚠️ OS TEMAS SÃO REDECLARADOS AQUI, como no `DialogoDeChamado` em 19/11: os
   da Operação vivem no `<style scoped>` daquela tela e não alcançam esta. */
.temas__abas { display: flex; flex-wrap: wrap; gap: var(--e-1); }
.temas__aba {
  display: flex; flex-direction: column; gap: 2px; text-align: left;
  padding: var(--e-2) var(--e-3);
  border: var(--borda-fina) solid var(--borda-forte);
  border-radius: var(--r-md);
  background: var(--superficie); color: var(--texto);
  cursor: pointer; font: inherit;
}
.temas__aba--ativa { border-color: var(--acento); }
.temas__aba--apagada { opacity: .55; cursor: not-allowed; }
.temas__resumo { font-size: var(--txt-xs); color: var(--texto-fraco); }
.temas__corpo { font-size: var(--txt-sm); }
.temas__texto {
  white-space: pre-wrap; word-break: break-word; margin: 0;
  font: inherit; color: var(--texto);
}
.temas__respostas { margin: 0; }
.temas__respostas dt { font-weight: var(--peso-forte); }
.temas__respostas dd { margin: 0 0 var(--e-2); color: var(--texto-fraco); }

.nota { color: var(--texto-fraco); }
.pequeno { font-size: var(--txt-xs); }
</style>
