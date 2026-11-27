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
import { baixarArquivo } from '../util/baixar.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'
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
/* O anexo do comprovante (25/11): subindo e o motivo da recusa, que vem do
   servidor — quem sabe a lista de extensões e o teto é ele. */
const subindoAnexo = ref(false)
const erroDoAnexo = ref('')
/* ⚠️ `ref` de template declarada aqui, e não `$refs` no clique: em
   `<script setup>` o `$refs` não é exposto, e o botão abriria o seletor de
   arquivo **nunca** — falha calada, que nenhuma trava de atributo pegaria. */
const inputDoAnexo = ref(null)
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

/* ==========================================================================
   O CARD ABERTO — 🔵 dele, 23/11
   ==========================================================================
   🔵 *"o card fechado só com resumo, dados e botões só no card aberto"*.

   🚨 **É O PADRÃO DA CASA, e não invenção desta tela.** A aba 1
   (`PainelAba.vue`) e a Operação (`PainelOperacao.vue`) já abrem o card num
   diálogo desde 05/11; esta tela era a única em que o card trazia tudo dentro
   de um `<div class="card__abrir">` que nunca abria nada. Medido em 23/11: a
   coluna 1 empilhava nome, valores, dois campos de data, a lista inteira de
   artefatos com caixas de marcação e três botões — num card que fica ao lado
   de outros quatro numa coluna estreita.

   ⚠️ **A COLUNA ENTRA NO ESTADO, não só o card.** Os botões do diálogo mudam
   por coluna (Preparar na 1, Conferir na 2, Montar arquivo na 3, Baixar na 4),
   e o card sozinho não sabe de qual coluna veio. */
const cardAberto = ref(null)
const colunaAberta = ref('')
const focoAnterior = ref(null)

function abrirCardDoTecnico(card, coluna) {
  /* 🔵 De onde o foco veio -- para ele voltar exatamente ali ao fechar. É a
     mesma régua do `PainelOperacao.abrirCard`. */
  focoAnterior.value = document.activeElement
  cardAberto.value = card
  colunaAberta.value = coluna.chave
}

function fecharCardDoTecnico() {
  cardAberto.value = null
  colunaAberta.value = ''
  const alvo = focoAnterior.value
  focoAnterior.value = null
  if (alvo && typeof alvo.focus === 'function') alvo.focus()
}

/* 🚨 O RESUMO DO SEMÁFORO DO CARD, para o card FECHADO. O pior semáforo manda:
   um artefato vermelho num card de dez não pode ficar escondido atrás de nove
   verdes, porque vermelho é justamente o que faz alguém abrir o card.
   ⚠️ Ícone E texto, nunca a cor sozinha — é a régua desta tela desde 19/11. */
const PIOR_PRIMEIRO = ['vermelho', 'amarelo', 'laranja', 'verde']

function semaforoResumo(card, visiveis) {
  const lista = (visiveis || artefatosVisiveis)(card)
  for (const cor of PIOR_PRIMEIRO) {
    if (lista.some((a) => a.semaforo === cor)) return cor
  }
  return ''
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
    /* 🚨 **O CARD ABERTO TEM DE SER REAPONTADO**, e esta é a mesma armadilha
       que a `PainelAba.vue` já documentava: sem isto o diálogo seguiria
       mostrando o retrato de ANTES da recarga -- a lista velha de artefatos,
       o valor velho, o semáforo velho -- justamente depois de um "Preparar"
       ou um "Atualizar", que é quando o dado mudou.
       ⚠️ E card que saiu do quadro (foi todo para a coluna seguinte) fecha o
       diálogo, em vez de ficar aberto sobre o que não existe mais. */
    if (cardAberto.value) {
      const col = (quadro.value.colunas || [])
        .find((c) => c.chave === colunaAberta.value)
      const chave = colunaAberta.value === 'movimentacao'
        ? 'tecnico_id' : 'lote_id'
      const alvo = cardAberto.value[chave]
      const vivo = (col?.cards || []).find((c) => c[chave] === alvo)
      if (vivo) cardAberto.value = vivo
      else fecharCardDoTecnico()
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

/* ==========================================================================
   O CORTE DE DATA DA ABA 2 — 🔵 D6 e D7 dele, 23/11
   ==========================================================================
   🔵 *"use 16/11/2026 de inicio para o financeiro, não mexa na data do OP"*, e
   os anteriores se **escondem, não se apagam**.

   🚨 **A TELA TEM DE DIZER O CORTE, e isto é uma saída deliberada do padrão da
   Operação.** Medido em 23/11: a `PainelOperacao.vue` **não mostra nem deixa
   mudar** a data dela — a `.painel__desde` existe no CSS dela e **nenhum
   template a usa**, é regra morta. Copiar isso aqui seria copiar o defeito:
   📏 o corte de 16/11 leva a contagem de **79 artefatos para 2**, e número que
   cai 97% sem explicação é a tela mentindo por omissão (`M12`). Foi assim que
   o "sumiço" de 19/11 pareceu defeito quando era filtro.

   ⚠️ **A DATA NÃO SE MUDA PELA TELA**, e aí sim o padrão da Operação vale: ela
   é do owner e se muda pela rota (`PUT /api/paineis/servico-dos-tecnicos/desde`,
   403 para quem não é owner). Pôr um campo aqui o daria às três pessoas que
   têm a `PNL_1.6`. */
const desdeDoQuadro = computed(() => quadro.value?.desde || '')
const escondidosPelaData = computed(
  () => Number(quadro.value?.escondidos_pela_data) || 0)

/* 🚨 QUANDO O QUADRO FOI VARRIDO — `M12`, e é o par da linha do corte.
   Dizer "a partir de 16/11" sem dizer **quando se olhou** deixa um quadro de
   seis dias atrás com a mesma cara de um varrido hoje, agora que a varredura
   é cron das 05:10. O carimbo vem do `config` do FPSL, em ISO/UTC.
   ⚠️ **Carimbo torto ou ausente não inventa hora**: devolve vazio e a tela
   simplesmente não escreve a parte da hora — a mesma régua do `desde`, que
   cai no padrão em vez de esvaziar a aba. */
const varridoEm = computed(() => {
  const bruto = quadro.value?.varrido_em
  if (!bruto) return ''
  const d = new Date(String(bruto))
  if (Number.isNaN(d.getTime())) return ''
  const hora = `${String(d.getHours()).padStart(2, '0')}:`
    + `${String(d.getMinutes()).padStart(2, '0')}`
  const hoje = new Date()
  const mesmoDia = d.getDate() === hoje.getDate()
    && d.getMonth() === hoje.getMonth()
    && d.getFullYear() === hoje.getFullYear()
  if (mesmoDia) return `hoje às ${hora}`
  const dia = `${String(d.getDate()).padStart(2, '0')}/`
    + `${String(d.getMonth() + 1).padStart(2, '0')}`
  return `em ${dia} às ${hora}`
})

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

/* 🔵 25/11 — os nomes provisórios de um card, sem repetir.
   📏 Vem do NOSSO agendamento (o backend põe `tecnico_provisorio` em cada
   artefato que tem). ⚠️ `Set` porque o mesmo técnico pode ter várias OS no
   card, e repetir o nome cinco vezes não informa mais que uma. */
function provisoriosDe(card) {
  const nomes = new Set()
  for (const a of card.artefatos || []) {
    if (a.tecnico_provisorio) nomes.add(a.tecnico_provisorio)
  }
  return [...nomes]
}

/* 🔵 25/11 (passo 4b) — as cinco colunas de cadastro do arquivo do Procfy.
   ⚠️ Os NOMES são os da planilha dele, não os das chaves do `/config`: quem lê
   vai preencher no Excel, e lá a coluna se chama "Categoria". */
const CHAVES_DO_PROCFY = ['procfy_categoria', 'procfy_conta_bancaria',
                          'procfy_modo_pagamento', 'procfy_centro_de_custo',
                          'procfy_tags']
const COLUNA_DO_PROCFY = {
  procfy_categoria: 'Categoria',
  procfy_conta_bancaria: 'Contas bancárias',
  procfy_modo_pagamento: 'Modo de pagamento',
  procfy_centro_de_custo: 'Centro de Custo',
  procfy_tags: 'Tags (Por Marcação)',
}
const configProcfy = ref(Object.fromEntries(
  CHAVES_DO_PROCFY.map((c) => [c, ''])))
const salvandoProcfy = ref(false)
const salvoProcfy = ref(false)
const erroProcfy = ref('')
const procfyVazias = computed(() =>
  CHAVES_DO_PROCFY.filter((c) => !(configProcfy.value[c] || '').trim()))

async function lerConfigProcfy() {
  try {
    const r = await api.get('/api/paineis/servico-dos-tecnicos/config-procfy')
    for (const c of CHAVES_DO_PROCFY) configProcfy.value[c] = r[c] || ''
  } catch (e) {
    /* ⚠️ Não derruba a tela: o quadro é o que importa, e as colunas são
       cadastro. Mas o erro aparece, porque campo vazio por falha de leitura
       pareceria campo nunca preenchido. */
    erroProcfy.value = 'Não consegui ler as colunas do Procfy.'
  }
}

async function salvarConfigProcfy() {
  if (salvandoProcfy.value) return
  salvandoProcfy.value = true
  erroProcfy.value = ''
  salvoProcfy.value = false
  try {
    const corpo = {}
    for (const c of CHAVES_DO_PROCFY) corpo[c] = configProcfy.value[c] || ''
    const r = await api.put(
      '/api/paineis/servico-dos-tecnicos/config-procfy', corpo)
    for (const c of CHAVES_DO_PROCFY) configProcfy.value[c] = r[c] || ''
    salvoProcfy.value = true
  } catch (e) {
    erroProcfy.value = e instanceof ErroDeApi
      ? e.message : 'Não consegui salvar as colunas do Procfy.'
  } finally {
    salvandoProcfy.value = false
  }
}

/* 🔵 25/11 (passo 5) — A CORRECAO DA SITUACAO NO DATASCOPE.
   🚨 A chamada ESCREVE EM SISTEMA DE TERCEIRO: dispara os webhooks deles e
   manda PUSH para o tecnico que enviou a resposta. Esta medido e documentado.
   Por isso nada aqui acontece num clique so -- e por isso o interruptor nasce
   desligado e vive nesta tela, nao no `/config`. */
const escritaDatascope = ref(null)
const dsArtefato = ref(null)
const dsFazendo = ref(false)
const dsErro = ref('')
const dsFeito = ref('')

async function lerEscritaDatascope() {
  try {
    const r = await api.get(
      '/api/paineis/servico-dos-tecnicos/datascope-escrita')
    escritaDatascope.value = !!r.ligada
  } catch (e) {
    /* ⚠️ `null` e diferente de `false`: nao medido nao e desligado, e a modal
       diz qual dos dois e. */
    escritaDatascope.value = null
  }
}

async function ligarEscritaDatascope() {
  dsErro.value = ''
  try {
    const r = await api.put(
      '/api/paineis/servico-dos-tecnicos/datascope-escrita', { ligada: true })
    escritaDatascope.value = !!r.ligada
  } catch (e) {
    dsErro.value = e instanceof ErroDeApi
      ? e.message : 'Não consegui ligar a escrita no DataScope.'
  }
}

/* 🚨 O clique ABRE A MODAL, nunca escreve. */
function abrirDatascope(a) {
  dsArtefato.value = a
  dsErro.value = ''
  dsFeito.value = ''
}

function fecharDatascope() {
  dsArtefato.value = null
}

async function confirmarDatascope() {
  if (!dsArtefato.value || dsFazendo.value) return
  dsFazendo.value = true
  dsErro.value = ''
  try {
    const r = await api.post(
      `/api/paineis/servico-dos-tecnicos/datascope-aprovar/${dsArtefato.value.id}`)
    dsFeito.value = r && r.ja_estava
      ? 'já estava aprovado no DataScope'
      : 'situação corrigida no DataScope'
    await carregar()
  } catch (e) {
    dsErro.value = e instanceof ErroDeApi
      ? e.message : 'Não consegui corrigir a situação no DataScope.'
  } finally {
    dsFazendo.value = false
  }
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

/* 🔵 Tarefa 2.4: *"Excluir o card inteiro devolvendo tudo à coluna 1, com
   justificativa única"*.
   🚨 REUSA O MESMO DIÁLOGO da devolução de um item -- `devolvendoLote` só diz
   que o alvo é o lote. Um segundo diálogo com o mesmo texto divergiria do
   primeiro na primeira palavra que ele mudasse. */
const devolvendoLote = ref(null)

function pedirExclusaoDoCard(card) {
  devolvendoLote.value = card
  justificativa.value = ''
}

/* 🔵 Tarefa 2.5: *"Reabrir na coluna 5 e gerar o arquivo de novo"*.
   ⚠️ SEM DIÁLOGO DE JUSTIFICATIVA, e é de propósito: nada é devolvido nem
   desfeito -- o lote volta para a Validação com a conferência intacta. Pedir
   motivo aqui trataria reabrir como erro, e reabrir é trabalho. */
async function reabrirLote(card) {
  const r = await chamar(`/reabrir/${card.lote_id}`)
  if (r) {
    fecharCardDoTecnico()
    aviso.value = r.ok
      ? `Lote ${card.lote_id} voltou para a Validação: gere o arquivo de novo.`
      : (r.motivo || 'não deu para reabrir')
    await carregar()
  }
}

async function devolverLote() {
  const alvo = devolvendoLote.value
  if (!alvo) return
  const r = await chamar('/devolver-lote', {
    lote_id: alvo.lote_id, justificativa: justificativa.value,
  })
  if (r) {
    devolvendoLote.value = null
    /* ⚠️ Fecha o card aberto: ele acabou de ficar sem item nenhum, e deixá-lo
       aberto mostraria uma lista vazia sem dizer por quê. */
    fecharCardDoTecnico()
    aviso.value = r.ok
      ? `${r.devolvidos} item(ns) voltaram para a Movimentação.`
      : (r.motivo || 'nada foi devolvido')
    await carregar()
  }
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

   🔵 25/11: O ANEXO DE VERDADE EXISTE. O arquivo vai para o **MoviZap**
   (`pagamento_comprovante_arquivo`, migração 119, pasta
   `/home/claude/movizap_pagamento_comprovantes`) e o FPSL guarda só a
   referência `anexo:<id>` no `comprovante_arquivo TEXT` que já existe — sem
   migração daquele lado e **sem bytes atravessando a ponte**, que é JSON
   servidor-a-servidor. O campo de texto continua aceitando o que se digita:
   quem já registrou um nome à mão não perde o que escreveu.
   🔵 24/11: **anexo completo, não só PDF** — a lista é a da observação da
   Operação. */
function abrirComprovante(artefato) {
  comprovando.value = {
    artefato,
    arquivo: artefato.comprovante_arquivo || '',
    valor: artefato.valor_do_comprovante ?? null,
    dispensa: artefato.comprovante_dispensa || '',
    /* O que o quadro já sabe do arquivo (nome e tamanho), para o link de
       download aparecer sem uma segunda consulta. */
    anexo: artefato.comprovante_anexo || null,
  }
  erroDoAnexo.value = ''
}

/* 🚨 `fetch` cru, não `api.post`: arquivo vai por `FormData` e o navegador
   precisa montar o `Content-Type` com o boundary. Definir o cabeçalho aqui
   quebraria o upload **em silêncio** — a Caixa e a Operação já documentam
   isso, e é o mesmo molde delas. */
async function subirComprovante(evento) {
  const arquivo = evento?.target?.files?.[0]
  if (evento?.target) evento.target.value = ''
  const c = comprovando.value
  if (!arquivo || !c) return
  subindoAnexo.value = true
  erroDoAnexo.value = ''
  try {
    const forma = new FormData()
    forma.append('arquivo', arquivo)
    const r = await fetch(`${BASE}/anexo/${c.artefato.id}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${localStorage.getItem('movizap.token')}` },
      body: forma,
    })
    const texto = await r.text()
    let corpo = null
    try { corpo = JSON.parse(texto) } catch { corpo = null }
    /* 🚨 A RECUSA É RESPOSTA, e com a FRASE do servidor: *"os motivos de
       recusa devem aparecer descritos ao invés de erro genérico"*. É o
       servidor que sabe quais extensões aceita e qual é o teto. */
    if (!r.ok) throw new Error((corpo && corpo.detail)
                               || `Falha no anexo (${r.status}).`)
    /* 🔵 *"Após o envio do anexo, abre o campo que pede o valor"* — é esta
       linha que abre: o campo do valor existe quando há `arquivo`. */
    c.arquivo = corpo.referencia
    c.anexo = { id: corpo.id, nome_original: corpo.nome_original,
                bytes: corpo.bytes }
  } catch (e) {
    erroDoAnexo.value = e.message || 'Falha no anexo.'
  } finally {
    subindoAnexo.value = false
  }
}

/* 🚨 26/11: ERA `window.open`, E O COMENTÁRIO ANTIGO ESTAVA ERRADO. Ele dizia
   que *"o navegador é quem salva, e o `Content-Disposition` é o que dá o nome
   original"* -- verdade para rota aberta, e esta é `requer_tela("PNL_1.6")`.
   `window.open` não manda `Authorization`, então o `Content-Disposition` nunca
   chegava: medido no log, **2 cliques e 2 × 401**. É a mesma causa do anexo das
   Solicitações, achada na mesma varredura. Ver `util/baixar.js`. */
async function baixarComprovante(anexoId, nome) {
  erroDoAnexo.value = ''
  try {
    await baixarArquivo(`${BASE}/anexo/${anexoId}`, nome || `comprovante-${anexoId}`)
  } catch (e) {
    erroDoAnexo.value = e?.message || 'Não consegui baixar o comprovante.'
  }
}

function tamanhoCurto(bytes) {
  const n = Number(bytes) || 0
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
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
  /* 🔴 ESTA ROTA TAMBÉM VOLTA 401, E ISTO AQUI AINDA NÃO É O CONSERTO.
     `window.open` não manda `Authorization`, e a rota é
     `requer_tela("PNL_1.6")` -- lido na definição em 26/11, na varredura que
     achou o anexo das Solicitações (4 × 401) e o comprovante (2 × 401). Este
     caminho nunca foi clicado, então não há 401 no log: a falta de evidência
     é de USO, não de defeito.

     ⚠️ POR QUE NÃO CONSERTEI JUNTO: o nome do arquivo é `procfy_<técnico>.xlsx`
     e o saneamento dele é REGRA DO SERVIDOR (25/11). Baixar por blob obriga a
     tela a dizer o nome, e recriar a regra aqui seria a mesma divergência que
     este dia inteiro veio corrigir. São duas saídas, e a escolha é dele:
     (a) `pedirArquivo` nova no `api/cliente.js`, que lê o nome do
         `Content-Disposition` e o devolve junto do blob -- o nome continua
         vindo do servidor;
     (b) a tela nomeia, e aí o nome do arquivo deixa de ser o que o Procfy
         recebe hoje.
     Enquanto não decidir, fica como está: quebrado e DITO, não quebrado e
     calado. */
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
  if (conferindo.value) { conferindo.value = null; return }
  /* ⚠️ O card aberto é o de BAIXO da pilha: os cinco modais acima nascem de
     dentro dele, e fechá-lo primeiro tiraria o chão deles. */
  if (cardAberto.value) fecharCardDoTecnico()
}

onMounted(() => {
  window.addEventListener('keydown', aoTeclar)
  carregar()
  /* ⚠️ Em paralelo, e nao dentro do `carregar`: leitura de cadastro nao
     pode atrasar o quadro, que e o que a pessoa veio ver. */
  lerConfigProcfy()
  /* ⚠️ Lido na abertura: a modal precisa saber se oferece
     corrigir ou ligar, e descobrir isso no clique faria a modal
     piscar de um estado para o outro. */
  lerEscritaDatascope()
})
onBeforeUnmount(() => window.removeEventListener('keydown', aoTeclar))
</script>

<template>
  <section class="painel escala-operacao">
    <!-- 🔵 25/11: O TOPO NO PADRÃO DA OPERAÇÃO, e é o pedido dele de 05/11
         (*"o cabeçalho esta porco, organize de forma profissional"*): a
         IDENTIDADE à esquerda (o que é a tela) e os CONTROLES à direita (o que
         se faz com ela), em dois blocos que quebram juntos no celular.
         🔵 *"faltam recursos no topo da aba1 também"* — a mesma mudança chega
         ao `PainelAba.vue`, que serve os quatro painéis de aba. -->
    <header class="painel__topo">
      <div class="painel__identidade">
        <h1 class="painel__titulo">{{ tituloDoPainel }}</h1>
        <!-- 🚨 O TEXTO NÃO SE PERDE, ELE SE RECOLHE: o balão abre no hover
             **e** no foco, então quem usa teclado também o lê. -->
        <AjudaDaTela>
          Fecha o pagamento dos técnicos: a varredura das <strong>05:10</strong>
          traz a OS com valor de serviço ou km, o card anda pelas cinco colunas
          e o arquivo do Procfy sai da Validação.
          <strong>Só aparece serviço de {{ dataCurta(desdeDoQuadro) }} em
          diante</strong>, e o que é anterior segue no banco.
        </AjudaDaTela>
      </div>
      <div class="painel__medidas">
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
    <!-- ⚠️ A busca e os dois ordenadores subiram para o topo (25/11). Esta
         linha ficou com o que é ESTADO do quadro, não controle: o corte de
         data e a hora da varredura. -->
    <div class="controles">
      <!-- 🔵 D6/D7, 23/11: o corte de data, DITO. 🚨 Não é enfeite: sem esta
           linha a aba abriria com 2 cards onde havia 79 e ninguém saberia por
           quê. ⚠️ E diz que eles **continuam no banco**, porque "escondido" e
           "apagado" são coisas diferentes e a decisão dele foi esconder. -->
      <p v-if="desdeDoQuadro" class="painel__desde">
        <i class="bi bi-calendar-range" aria-hidden="true"></i>
        serviço a partir de <strong>{{ dataCurta(desdeDoQuadro) }}</strong>
        <template v-if="escondidosPelaData">
          &middot; {{ escondidosPelaData }}
          {{ escondidosPelaData === 1 ? 'artefato anterior' : 'artefatos anteriores' }}
          fora de vista (seguem no banco)
        </template>
        <!-- 🚨 `M12`: o quadro diz QUANDO olhou. A varredura roda às 05:10 e,
             sem esta parte, quadro de seis dias atrás tem cara de quadro de
             hoje. ⚠️ Só aparece quando há carimbo — nunca varrido não é erro. -->
        <template v-if="varridoEm">
          &middot; varrido {{ varridoEm }}
        </template>
      </p>
    </div>

    <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>
    <p v-if="aviso" class="aviso" role="status">{{ aviso }}</p>
    <p v-if="carregando && !quadro" class="nota">Abrindo…</p>

    <BarraDeRolagem v-if="quadro" :rolo="rolo"
                    rotulo="quadro de Serviço dos técnicos" />

    <!-- 🔵 25/11 (passo 4b) — AS CINCO COLUNAS DE CADASTRO DO ARQUIVO.
         📏 O defeito que isto conserta: as cinco chaves eram LIDAS pelo gerador
         do arquivo e NENHUMA rota as escrevia -- ninguém conseguia preenchê-las,
         nem o owner, e o arquivo saía com as cinco colunas em branco sem
         caminho para mudar isso.
         🔵 Preencher é OPCIONAL (decisão dele de 18/11: *"pode gerar com elas
         em branco nesse momento"*), e a frase diz o que acontece quando ficam
         vazias -- sugerir obrigatoriedade seria a tela mentindo. -->
    <details v-if="quadro" class="procfy">
      <summary class="procfy__abrir">
        <i class="bi bi-table" aria-hidden="true"></i>
        Colunas do Procfy
        <span v-if="procfyVazias.length" class="selo selo--amarelo">
          {{ procfyVazias.length }} em branco
        </span>
        <span v-else class="selo selo--verde">as cinco preenchidas</span>
      </summary>
      <p class="nota pequeno">
        Estas cinco colunas do arquivo saem destes campos. O arquivo é gerado
        mesmo com elas <strong>em branco</strong> — quem importa preenche na
        planilha.
      </p>
      <div class="procfy__grade">
        <label v-for="c in CHAVES_DO_PROCFY" :key="c" class="procfy__campo">
          <span class="procfy__rotulo">{{ COLUNA_DO_PROCFY[c] }}</span>
          <input v-model="configProcfy[c]" type="text" maxlength="200"
                 :class="'campo campo--' + c.replace(/_/g, '-')"
                 :disabled="salvandoProcfy" />
        </label>
      </div>
      <div class="procfy__agir">
        <button class="botao botao--contorno" type="button"
                :disabled="salvandoProcfy" @click="salvarConfigProcfy">
          <i class="bi bi-check2" aria-hidden="true"></i>
          Salvar as colunas
        </button>
        <span v-if="erroProcfy" class="nota pequeno erro">{{ erroProcfy }}</span>
        <span v-else-if="salvoProcfy" class="nota pequeno">salvo</span>
      </div>
    </details>

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
              <!-- 🔵 23/11, dele: *"o card fechado só com resumo, dados e
                   botões só no card aberto"*. 🚨 `<button>` e não `<div>`: o
                   card agora ABRE, e o que abre tem de chegar pelo teclado --
                   um `div` com `@click` é invisível para quem usa Tab, e a
                   tela estaria trancada para quem não usa mouse. -->
              <article v-for="card in cardsDa(coluna)"
                       :key="card.tecnico_id || 0" class="card">
                <button class="card__abrir card__abrir--botao" type="button"
                        :class="{ 'card__abrir--sem-tecnico': !card.pode_preparar }"
                        @click="abrirCardDoTecnico(card, coluna)">
                  <span class="card__linha">
                    <span class="card__tecnico"
                          :title="card.tecnico_nome || ''">
                      {{ card.tecnico_nome || 'técnico ' + card.tecnico_id }}
                    </span>
                    <span class="card__direita">
                      {{ artefatosVisiveis(card).length }} de
                      {{ (card.artefatos || []).length }}
                    </span>
                  </span>

                  <!-- 🔵 25/11: QUEM FOI, no card fechado. O título do card é
                       FIXO ("não cadastrados no Harmonit"); o nome de quem
                       atendeu vem do NOSSO agendamento e aparece aqui, porque
                       *"o card já direciona"* só funciona se der para ver sem
                       abrir. ⚠️ Vários num card fixo: a lista é separada por
                       vírgula, e por isso não vai no título. -->
                  <span v-if="provisoriosDe(card).length"
                        class="card__linha card__dado">
                    <span class="selo selo--amarelo" :title="provisoriosDe(card).join(', ')">
                      <i class="bi bi-person-exclamation" aria-hidden="true"></i>
                      provisório: {{ provisoriosDe(card).join(', ') }}
                    </span>
                  </span>

                  <span class="card__linha card__dado">
                    <span>a pagar <strong>{{ moeda(totalDe(card)) }}</strong></span>
                    <!-- 🚨 O PIOR SEMÁFORO no card fechado: vermelho escondido
                         atrás de nove verdes é justamente o que faria ninguém
                         abrir o card. Ícone E texto, nunca a cor sozinha. -->
                    <span v-if="semaforoResumo(card)" class="selo"
                          :class="'selo--' + semaforoResumo(card)">
                      <i :class="'bi ' + SEMAFORO[semaforoResumo(card)].icone"
                         aria-hidden="true"></i>
                      {{ SEMAFORO[semaforoResumo(card)].texto }}
                    </span>
                  </span>

                  <!-- ⚠️ O filtro ATIVO é dito no card fechado, senão a
                       contagem "4 de 39" pareceria perda de dado. -->
                  <span v-if="filtroDo(card).de || filtroDo(card).ate"
                        class="card__linha card__dado">
                    <span class="card__filtrado">
                      <i class="bi bi-funnel-fill" aria-hidden="true"></i>
                      filtrado por data
                    </span>
                  </span>

                  <!-- 🚨 A trava dos SEM TÉCNICO fica no card FECHADO: ela é o
                       motivo de o dinheiro estar parado, e esconder isso atrás
                       de um clique deixaria o valor sem explicação à vista. -->
                  <span v-if="!card.pode_preparar" class="card__trava">
                    <i class="bi bi-info-circle" aria-hidden="true"></i>
                    Sem técnico identificado: não há a quem pagar.
                  </span>
                </button>
              </article>
            </template>

            <!-- ============ COLUNAS 2 a 5 — os lotes por técnico ========= -->
            <template v-else>
              <article v-for="card in cardsDa(coluna)" :key="card.lote_id"
                       class="card">
                <button class="card__abrir card__abrir--botao" type="button"
                        @click="abrirCardDoTecnico(card, coluna)">
                  <span class="card__linha">
                    <span class="card__tecnico" :title="card.tecnico_nome || ''">
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
                    <span v-if="semaforoResumo(card, artefatosDoLote)" class="selo"
                          :class="'selo--' + semaforoResumo(card, artefatosDoLote)">
                      <i :class="'bi ' + SEMAFORO[semaforoResumo(card, artefatosDoLote)].icone"
                         aria-hidden="true"></i>
                      {{ SEMAFORO[semaforoResumo(card, artefatosDoLote)].texto }}
                    </span>
                  </span>
                </button>
              </article>
            </template>

            <p v-if="!cardsDa(coluna).length" class="nota pequeno">
              {{ busca.trim() ? 'Nenhum card casa com a busca.' : 'Vazia.' }}
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- 🔵 O CARD ABERTO, 23/11: *"dados e botões só no card aberto"*.
         🚨 PRIMEIRO NA ORDEM dos diálogos de propósito: os cinco de baixo
         nascem DE DENTRO deste, e no DOM eles têm de ficar DEPOIS para
         empilhar por cima sem depender de `z-index` -- é a mesma régua de
         empilhamento que a conferência de CSS publicado já guarda. -->
    <div v-if="cardAberto" class="modal" role="dialog" aria-modal="true"
         :aria-label="'Card de ' + (cardAberto.tecnico_nome || 'técnico')">
      <div class="modal__caixa">
        <h3 class="modal__titulo">
          {{ cardAberto.tecnico_nome || 'técnico ' + cardAberto.tecnico_id }}
          <span v-if="colunaAberta !== 'movimentacao'" class="apagado">
            &middot; lote {{ cardAberto.lote_id }}
          </span>
        </h3>

        <!-- ================= COLUNA 1 — Movimentação ================= -->
        <template v-if="colunaAberta === 'movimentacao'">
          <!-- 🔵 25/11: O RESUMO EM MEDIDAS, e não numa frase corrida. Três
               números no meio de uma linha de texto obrigam a LER para achar o
               que importa; em medidas, o olho vai direto. É a mesma forma das
               pílulas do topo da tela. -->
          <div class="medidas">
            <span class="medida">
              <span class="medida__rotulo">a pagar</span>
              <strong class="medida__valor">{{ moeda(totalDe(cardAberto)) }}</strong>
            </span>
            <span class="medida">
              <span class="medida__rotulo">serviço</span>
              <span class="medida__valor">
                {{ moeda(somaDe(cardAberto, 'valor_pagamento')) }}
              </span>
            </span>
            <span class="medida">
              <span class="medida__rotulo">km</span>
              <span class="medida__valor">
                {{ moeda(somaDe(cardAberto, 'valor_km')) }}
              </span>
            </span>
            <span class="medida">
              <span class="medida__rotulo">artefatos</span>
              <span class="medida__valor">
                {{ artefatosVisiveis(cardAberto).length }} de
                {{ (cardAberto.artefatos || []).length }}
              </span>
            </span>
          </div>

                  <!-- 🔵 O FILTRO DE DATAS DENTRO DO CARD: *"só quero fechar
                       de 16-18/11/26 filtro isso e flego"*. ⚠️ A data é a do
                       SERVIÇO, e o filtro é DESTE card. -->
                  <!-- ⚠️ `:value` + `@input`, e NÃO `v-model`: o alvo seria
                       `filtroDo(cardAberto).de`, e `v-model` exige uma expressão de
                       membro simples — chamada de função no caminho é erro de
                       compilação do template. -->
          <!-- 🔵 25/11: o filtro em QUADRO, com título. Dois `<input
               type="date">` soltos numa linha não diziam de que data eram --
               e é a do SERVIÇO, não a do card. -->
          <div class="acoes">
            <div class="acoes__grupo">
              <p class="acoes__titulo">Filtrar pela data do serviço</p>
              <div class="card__filtro">
                <label class="campo__rotulo campo__rotulo--lado">
                  de
                  <input class="campo" type="date"
                         :value="filtroDo(cardAberto).de"
                         @change="definirFiltro(cardAberto, 'de', $event.target.value)" />
                </label>
                <label class="campo__rotulo campo__rotulo--lado">
                  até
                  <input class="campo" type="date"
                         :value="filtroDo(cardAberto).ate"
                         @change="definirFiltro(cardAberto, 'ate', $event.target.value)" />
                </label>
                <button v-if="filtroDo(cardAberto).de || filtroDo(cardAberto).ate"
                        class="botao botao--fantasma" type="button"
                        @click="limparFiltro(cardAberto)">
                  <i class="bi bi-x-lg" aria-hidden="true"></i>
                  Limpar o filtro
                </button>
              </div>
            </div>
          </div>

                  <ul class="artefatos">
                    <!-- 🔵 25/11 (A23): O ARTEFATO É UM CARD INTERNO, no
                         vocabulário do `CorpoDoCard` -- o modelo da aba 1, que
                         agora mora na fonte única. Antes eram cinco campos
                         numa `<label>` e três parágrafos soltos, tudo no mesmo
                         peso. ⚠️ A `<label>` em volta FICA: é ela que faz
                         clicar no texto marcar o item. -->
                    <li v-for="a in artefatosVisiveis(cardAberto)" :key="a.id"
                        class="artefato"
                        :class="{ 'artefato--marcado': estaMarcado(cardAberto, a.id) }">
                      <label class="artefato__marca">
                        <input type="checkbox"
                               :checked="estaMarcado(cardAberto, a.id)"
                               :disabled="!cardAberto.pode_preparar"
                               @change="alternar(cardAberto, a.id)" />
                        <span class="artefato__corpo">
                          <!-- LINHA 1 — os identificadores e o VALOR à direita.
                               🔵 A ordem é a dele: Orçamento — OS — TERMO. -->
                          <span class="card__linha">
                            <span class="card__ident">
                              <!-- 🔵 25/11 (passo 4a) — O VÍNCULO DEMONSTRADO.
                                   Ele: *"orçamento não é impedimento é apenas
                                   vínculo demonstrado para operador auditar em
                                   tela"*. Auditar é COMPARAR, então o TOTAL do
                                   orçamento vem junto do número: só o número
                                   obrigaria a abrir outra tela para saber
                                   quanto era. -->
                              <span v-if="a.orcamento_numero"
                                    class="artefato__orcamento"
                                    :title="a.orcamento_total != null
                                            ? 'orçamento de ' + moeda(a.orcamento_total)
                                            : 'orçamento sem total medido'">
                                Orç {{ a.orcamento_numero }}
                                <template v-if="a.orcamento_total != null">
                                  ({{ moeda(a.orcamento_total) }})
                                </template>
                              </span>
                              <!-- 🚨 SEM ÍCONE DE ALERTA (25/11): o orçamento
                                   NÃO impede o pagamento, por decisão dele, e
                                   alarme para algo que não impede é a tela
                                   exagerando a gravidade (`M12`). O texto fica,
                                   porque a ausência continua sendo informação. -->
                              <span v-else
                                    class="artefato__orcamento artefato__orcamento--sem">
                                sem orçamento
                              </span>
                              <button class="card__os" type="button"
                                      @click.stop.prevent="abrirOs(a)">
                                OS {{ a.numero_os }}
                              </button>
                              <span v-if="a.termo" class="card__termo">
                                TERMO {{ a.termo }}
                              </span>
                            </span>
                            <span class="card__direita card__direita--dado">
                              <strong>{{ moeda(valorDe(a)) }}</strong>
                            </span>
                          </span>

                          <!-- LINHA 2 — de quem é e quando foi.
                               ⚠️ Cliente sem nome é DITO, não deixado em
                               branco — a frase é a do card da aba 1. -->
                          <span class="card__linha card__dado">
                            <span v-if="a.cliente" class="card__cliente"
                                  :title="a.cliente">{{ a.cliente }}</span>
                            <span v-else class="card__cliente card__cliente--sem">
                              cliente {{ a.cliente_id || '?' }}, fora do nosso cadastro
                            </span>
                            <span class="card__direita">
                              <template v-if="a.tipo_nome">{{ a.tipo_nome }} &middot; </template>
                              serviço {{ dataCurta(a.data_os) }}
                            </span>
                          </span>

                          <!-- LINHA 3 — os selos, e só quando há o que dizer. -->
                          <span v-if="a.status_str || casouPor(a)
                                      || a.tecnico_provisorio
                                      || a.semaforo === 'laranja'"
                                class="artefato__selos">
                            <!-- 🔵 25/11: o provisório TAMBÉM por artefato, porque
                                 o card fixo junta vários e a correção é de UMA
                                 OS por vez. ⚠️ Amarelo, não verde: identificado
                                 não é resolvido. -->
                            <span v-if="a.tecnico_provisorio"
                                  class="selo selo--amarelo">
                              <i class="bi bi-person-exclamation" aria-hidden="true"></i>
                              provisório: {{ a.tecnico_provisorio }}
                            </span>
                            <span v-if="a.status_str" class="selo">
                              {{ a.status_str }}
                            </span>
                            <span v-if="casouPor(a)" class="selo">
                              casou por {{ casouPor(a) }}
                            </span>
                            <!-- 🔵 O devolvido é LARANJA e a justificativa fica
                                 à vista: laranja sem motivo é cor sem
                                 informação. -->
                            <span v-if="a.semaforo === 'laranja'"
                                  class="selo selo--laranja">
                              <i class="bi bi-arrow-counterclockwise" aria-hidden="true"></i>
                              devolvido: {{ a.justificativa }}
                            </span>
                          </span>
                        </span>
                      </label>
                    </li>
                  </ul>

                  <p v-if="!artefatosVisiveis(cardAberto).length" class="nota pequeno">
                    Nenhum artefato à vista com este filtro.
                  </p>

                  <!-- 🚨 O card dos SEM TÉCNICO não prepara, e DIZ por quê:
                       sem técnico não há a quem pagar. Ele existe para o
                       dinheiro não sair de vista. -->
                  <!-- 🚨 A frase INTEIRA fica aqui dentro; o card fechado
                       leva só a versão curta. Dizer POR QUE o dinheiro está
                       parado é o recado, e ele não cabe no resumo. -->
                  <p v-if="!cardAberto.pode_preparar" class="card__trava">
                    <i class="bi bi-info-circle" aria-hidden="true"></i>
                    Estas OS têm valor de pagamento e nenhum técnico
                    identificado na linha. Não há a quem pagar até alguém
                    vincular o técnico na OS.
                  </p>
                  <!-- 🔵 Os botões, que é o que ele pediu para sair do card
                       fechado. 🚨 `v-if` próprio e não `v-else` da trava acima:
                       o par `v-if`/`v-else` existia porque os dois moravam no
                       mesmo card; aqui a trava é uma frase e o bloco de ações é
                       outro, e amarrá-los faria um sumir com o outro. -->
                  <!-- 🔵 25/11: OS QUADROS DE AÇÃO. Cinco botões de larguras
                       diferentes numa fileira que quebrava onde dava, e sem
                       dizer o que fazem, foi o que ele chamou de *"terrível"*.
                       Agora: grade de larguras IGUAIS, cada ação com uma linha
                       dizendo o que faz, e separadas por quadro. 🚨 O
                       agrupamento não é enfeite: "Excluir o card" e
                       "Atualizar" lado a lado, do mesmo tamanho, é como se
                       clica no errado. -->
                  <div v-if="cardAberto.pode_preparar" class="acoes">
                    <div class="acoes__grupo">
                      <p class="acoes__titulo">Escolher o que vai pagar</p>
                      <div class="acoes__grade">
                        <button class="acao" type="button"
                                @click="marcarTodosDoCard(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-check2-all" aria-hidden="true"></i>
                            Marcar todos
                          </span>
                          <span class="acao__nota">
                            Marca os {{ artefatosVisiveis(cardAberto).length }}
                            artefato(s) à vista — o filtro acima manda.
                          </span>
                        </button>
                        <button v-if="marcadosDo(cardAberto).length"
                                class="acao" type="button"
                                @click="limparMarcados(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-x-lg" aria-hidden="true"></i>
                            Limpar a marcação
                          </span>
                          <span class="acao__nota">
                            Desmarca os {{ marcadosDo(cardAberto).length }}
                            marcados. Não mexe em artefato nenhum.
                          </span>
                        </button>
                      </div>
                    </div>
                    <div class="acoes__grupo">
                      <p class="acoes__titulo">Fechar o pagamento</p>
                      <div class="acoes__grade">
                        <button class="acao acao--principal" type="button"
                                :disabled="!marcadosDo(cardAberto).length"
                                @click="preparar(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-box-arrow-right" aria-hidden="true"></i>
                            Preparar os marcados
                            ({{ marcadosDo(cardAberto).length }})
                          </span>
                          <span class="acao__nota">
                            Cria o card do técnico na Preparação com os
                            marcados. O que ficar sem marca permanece aqui.
                          </span>
                        </button>
                      </div>
                    </div>
                  </div>

                  <!-- 🚨 O RODAPÉ NUMA FAIXA SÓ, e o `Fechar` mora DENTRO deste
                       braço: era ele que caía numa segunda faixa abaixo das
                       ações, com peso de ação principal. ⚠️ Está nos DOIS
                       braços do diálogo de propósito, e há trava medindo isso
                       (`aba2_rodape_2511.teste.js`) — braço sem `Fechar` é
                       diálogo sem porta de saída. -->
                  <div class="card__rodape">
                    <span class="nota pequeno">
                      <i class="bi bi-info-circle" aria-hidden="true"></i>
                      Só os artefatos marcados vão para a Preparação.
                    </span>
                    <div class="modal__acoes">
                      <button class="botao botao--fantasma" type="button"
                              @click="fecharCardDoTecnico">Fechar</button>
                    </div>
                  </div>
        </template>

        <!-- ============ COLUNAS 2 a 5 — os lotes por técnico ========= -->
        <template v-else>

                  <ul class="artefatos">
                    <li v-for="a in artefatosDoLote(cardAberto)" :key="a.id"
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
                        <button v-if="colunaAberta === 'validacao'"
                                class="botao botao--contorno"
                                type="button" @click="abrirComprovante(a)">
                          <i class="bi bi-paperclip" aria-hidden="true"></i>
                          {{ a.comprovante_arquivo || a.comprovante_dispensa
                             ? 'Trocar comprovante' : 'Comprovante' }}
                        </button>

                        <!-- 🔵 25/11 (passo 5) — A CORREÇÃO DA SITUAÇÃO NO
                             DATASCOPE. 🚨 Só na Validação, pela mesma razão do
                             comprovante ao lado: *"tem como base as etapas de
                             validação que permitem o card do pagamento técnico
                             avançar"*.
                             ⚠️ O clique ABRE MODAL, nunca escreve: a chamada
                             dispara os webhooks deles e manda push para o
                             técnico. -->
                        <button v-if="colunaAberta === 'validacao'"
                                class="botao botao--fantasma"
                                type="button" @click="abrirDatascope(a)">
                          <i class="bi bi-pencil-square" aria-hidden="true"></i>
                          Corrigir situação no DataScope
                        </button>

                        <!-- 🔵 Tarefa 2.3: remover o item com justificativa
                             nas colunas 3, 4 e 5. 📏 Medido em 23/11: o
                             serviço já aceitava de qualquer coluna que não
                             seja a 1, e o botão existia só no diálogo de
                             conferência, que abre da coluna 2.
                             🚨 MESMO GESTO, não um segundo caminho: chama o
                             `pedirDevolucao` que a conferência usa, e a regra
                             dele ("sempre para a coluna 1") fica num lugar
                             só. -->
                        <button v-if="colunaAberta !== 'movimentacao'"
                                class="botao botao--contorno"
                                type="button" @click="pedirDevolucao(a)">
                          <i class="bi bi-x-circle" aria-hidden="true"></i>
                          Remover
                        </button>
                      </p>
                    </li>
                  </ul>

                  <!-- 🔵 25/11: OS QUADROS DE AÇÃO (ver o braço da
                       Movimentação). Os grupos são três: o que só LÊ, o que
                       FECHA dinheiro e o que DESFAZ. -->
                  <div class="acoes">
                    <div class="acoes__grupo">
                      <p class="acoes__titulo">Conferir — nada se move</p>
                      <div class="acoes__grade">
                        <!-- 🔵 *"todos os cards tem botão de 'atualizar'"*. -->
                        <button class="acao" type="button"
                                @click="revalidar(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-arrow-clockwise" aria-hidden="true"></i>
                            Atualizar
                          </span>
                          <span class="acao__nota">
                            Roda as verificações deste card de novo, para
                            ajuste feito depois que ele nasceu. Não move nada.
                          </span>
                        </button>
                        <button v-if="colunaAberta === 'validacao'"
                                class="acao" type="button"
                                @click="lerDataScope(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-clipboard-data" aria-hidden="true"></i>
                            Ler DataScope
                          </span>
                          <span class="acao__nota">
                            Busca o formulário do técnico e marca o que ele
                            respondeu. Só leitura.
                          </span>
                        </button>
                        <button v-if="colunaAberta === 'validacao'
                                      || colunaAberta === 'procfy'"
                                class="acao" type="button"
                                @click="verPrevia(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-eye" aria-hidden="true"></i>
                            Ver prévia
                          </span>
                          <span class="acao__nota">
                            Mostra o que vai para o Procfy e quais colunas
                            saem em branco, antes de baixar o arquivo.
                          </span>
                        </button>
                      </div>
                    </div>

                    <div v-if="colunaAberta !== 'movimentacao'" class="acoes__grupo">
                      <p class="acoes__titulo">Fechar o pagamento</p>
                      <div class="acoes__grade">
                        <button v-if="colunaAberta === 'preparacao'"
                                class="acao acao--principal" type="button"
                                @click="abrirConferencia(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-list-check" aria-hidden="true"></i>
                            Conferir e auditar
                          </span>
                          <span class="acao__nota">
                            Abre a conferência um a um e leva para a Validação
                            só os cientes que não foram negados.
                          </span>
                        </button>
                        <button v-if="colunaAberta === 'validacao'"
                                class="acao acao--principal" type="button"
                                @click="montarArquivo(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-file-earmark-spreadsheet"
                               aria-hidden="true"></i>
                            Montar arquivo
                          </span>
                          <span class="acao__nota">
                            Fecha o lote e gera a planilha do Procfy. Artefato
                            sem comprovante nem dispensa fica para trás.
                          </span>
                        </button>
                        <button v-if="colunaAberta === 'procfy'"
                                class="acao acao--principal" type="button"
                                @click="baixar(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-download" aria-hidden="true"></i>
                            Baixar o arquivo
                          </span>
                          <span class="acao__nota">
                            Salva a planilha para importar no Procfy. Pode
                            baixar quantas vezes precisar.
                          </span>
                        </button>
                        <button v-if="colunaAberta === 'procfy'"
                                class="acao" type="button"
                                @click="enviar(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-send-check" aria-hidden="true"></i>
                            Marcar como enviado
                          </span>
                          <span class="acao__nota">
                            Move o card para a última coluna. Diz que o
                            pagamento saiu — não envia nada por si.
                          </span>
                        </button>
                        <button v-if="colunaAberta === 'enviado'"
                                class="acao" type="button"
                                @click="reabrirLote(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-arrow-counterclockwise"
                               aria-hidden="true"></i>
                            Reabrir para gerar de novo
                          </span>
                          <span class="acao__nota">
                            Devolve o lote à Validação, onde o "Montar
                            arquivo" serve outra vez.
                          </span>
                        </button>
                      </div>
                    </div>

                    <!-- 🔵 Tarefa 2.4: excluir o card inteiro. Vale de
                         qualquer coluna de lote (2 a 5) -- na coluna 1 o card
                         é o técnico, permanente, e não há lote para excluir.
                         🚨 Fica em QUADRO PRÓPRIO, longe do "Atualizar": era
                         vizinho dele, do mesmo tamanho e da mesma cor. -->
                    <div v-if="colunaAberta !== 'movimentacao'" class="acoes__grupo">
                      <p class="acoes__titulo">Desfazer</p>
                      <div class="acoes__grade">
                        <button class="acao acao--perigo" type="button"
                                @click="pedirExclusaoDoCard(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-trash" aria-hidden="true"></i>
                            Excluir o card
                          </span>
                          <span class="acao__nota">
                            Devolve todos os artefatos à Movimentação, com uma
                            justificativa única. Pede confirmação.
                          </span>
                        </button>
                      </div>
                    </div>
                  </div>

                  <!-- 🚨 O MESMO RODAPÉ DO OUTRO BRAÇO. Ver o comentário de lá:
                       o `Fechar` mora dentro dos dois, e há trava medindo. -->
                  <div class="card__rodape">
                    <span class="nota pequeno">
                      <i class="bi bi-info-circle" aria-hidden="true"></i>
                      O arquivo do Procfy só sai com comprovante ou dispensa em
                      cada artefato.
                    </span>
                    <div class="modal__acoes">
                      <button class="botao botao--fantasma" type="button"
                              @click="fecharCardDoTecnico">Fechar</button>
                    </div>
                  </div>
        </template>
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
            <button v-if="!l.ciente_em" class="botao botao--contorno" type="button"
                    @click="ciente(l)">
              <i class="bi bi-check2" aria-hidden="true"></i>
              Ciente
            </button>
            <span v-else class="selo selo--verde">
              <i class="bi bi-check2" aria-hidden="true"></i> ciente
            </span>
            <button class="botao botao--contorno" type="button"
                    @click="pedirDevolucao(l)">
              <i class="bi bi-x-circle" aria-hidden="true"></i>
              Remover
            </button>
          </li>
        </ul>
        <div class="modal__acoes">
          <button class="botao botao--fantasma" type="button"
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
        <!-- 🚨 A CONSEQUÊNCIA, QUANDO HÁ UMA: na coluna 4 o arquivo do Procfy
             já foi montado com este item dentro, e na 5 ele já foi enviado.
             Remover sem dizer isso faria a tela esconder o que muda -- e é
             justamente aqui que a pessoa decide. -->
        <!-- ⚠️ `nota pequeno` e `selo--laranja`, que EXISTEM neste arquivo:
             em 23/11 eu ia escrever `nota--aviso`, que não existe em nenhum
             CSS -- a armadilha da `.pilula`, classe sem estilo que nenhum
             teste pega porque o jsdom não faz layout. -->
        <p v-if="colunaAberta === 'procfy' || colunaAberta === 'enviado'"
           class="nota pequeno">
          <span class="selo selo--laranja">atenção</span>
          {{ colunaAberta === 'enviado'
             ? 'Atenção: o arquivo deste lote já foi marcado como enviado. '
               + 'Remover aqui não desfaz o envio — o acerto é no Procfy.'
             : 'Atenção: o arquivo deste lote já foi montado com este item '
               + 'dentro. Depois de remover, monte o arquivo de novo.' }}
        </p>
        <input v-model="justificativa" class="campo" maxlength="400"
               placeholder="ex.: OS ainda em Agendar serviço" />
        <div class="modal__acoes">
          <button class="botao botao--fantasma" type="button"
                  @click="devolvendo = null">Cancelar</button>
          <button class="botao" type="button" :disabled="!justificativa.trim()"
                  @click="devolver">Remover</button>
        </div>
      </div>
    </div>

    <!-- 🔵 Tarefa 2.4: a justificativa ÚNICA do card inteiro. -->
    <div v-if="devolvendoLote" class="modal" role="dialog" aria-modal="true">
      <div class="modal__caixa modal__caixa--curta">
        <h2>Excluir o card inteiro?</h2>
        <p class="nota pequeno">
          Todos os itens deste lote voltam para a Movimentação em laranja, com
          esta mesma justificativa à vista.
        </p>
        <!-- 🚨 O NÚMERO À VISTA: "todos os itens" sem dizer quantos deixaria a
             pessoa decidir no escuro. -->
        <p class="nota pequeno">
          <span class="selo selo--laranja">atenção</span>
          {{ (devolvendoLote.artefatos || []).length }} item(ns) ·
          {{ colunaAberta === 'enviado'
             ? 'o arquivo deste lote já foi marcado como enviado, e remover '
               + 'aqui não desfaz o envio — o acerto é no Procfy.'
             : (colunaAberta === 'procfy'
                ? 'o arquivo deste lote já foi montado; depois de excluir, '
                  + 'monte o arquivo de novo.'
                : 'o lote sai do quadro.') }}
        </p>
        <input v-model="justificativa" class="campo" maxlength="400"
               placeholder="ex.: lote montado com o técnico errado" />
        <div class="modal__acoes">
          <button class="botao botao--fantasma" type="button"
                  @click="devolvendoLote = null">Cancelar</button>
          <button class="botao" type="button" :disabled="!justificativa.trim()"
                  @click="devolverLote">Excluir o card</button>
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

        <!-- 🔵 25/11 — O ANEXO DE VERDADE: *"o anexo é do MoviZap, no padrão
             da observação da Operação"*, e **anexo completo, não só PDF**.
             🚨 O `<input type="file">` fica escondido e quem aparece é o
             botão: input de arquivo cru não aceita estilo e cada navegador
             desenha o seu. É o molde da Operação e da Caixa. -->
        <!-- 🔵 25/11: o anexo vira QUADRO, no mesmo padrão das ações do
             card, e os passos ficam numerados — o campo do valor continua
             nascendo só depois do documento. -->
        <div class="acoes">
          <div class="acoes__grupo">
            <p class="acoes__titulo">1. O documento</p>
            <div class="acoes__grade">
              <input ref="inputDoAnexo" class="comprovante__arquivo" type="file"
                     @change="subirComprovante" />
              <button class="acao" type="button"
                      :class="{ 'acao--principal': !comprovando.anexo }"
                      :disabled="subindoAnexo"
                      @click="inputDoAnexo?.click()">
                <span class="acao__nome">
                  <i class="bi bi-paperclip" aria-hidden="true"></i>
                  {{ subindoAnexo ? 'Enviando…'
                     : comprovando.anexo ? 'Trocar o arquivo'
                     : 'Anexar comprovante' }}
                </span>
                <span class="acao__nota">
                  <template v-if="comprovando.anexo">
                    <strong>{{ comprovando.anexo.nome_original }}</strong>
                    &middot; {{ tamanhoCurto(comprovando.anexo.bytes) }}
                  </template>
                  <template v-else>
                    PDF, imagem, planilha ou documento, até 10 MB.
                  </template>
                </span>
              </button>
            </div>
            <!-- ⚠️ O link de baixar fica FORA do quadro: dentro dele, clicar
                 no link abriria também o seletor de arquivo do botão. -->
            <p v-if="comprovando.anexo" class="nota pequeno">
              <a href="#" @click.prevent="baixarComprovante(comprovando.anexo.id,
                                              comprovando.anexo.nome_original)">
                <i class="bi bi-file-earmark-arrow-down" aria-hidden="true"></i>
                baixar {{ comprovando.anexo.nome_original }}
              </a>
            </p>
          </div>
        </div>

        <!-- 🚨 A FRASE DO SERVIDOR, não um erro genérico: é ele quem sabe
             quais extensões aceita e qual é o teto. -->
        <p v-if="erroDoAnexo" class="aviso aviso--erro" role="alert">
          {{ erroDoAnexo }}
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
          2. Valor que está no documento
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

        <div class="card__rodape">
          <span class="nota pequeno">
            <i class="bi bi-info-circle" aria-hidden="true"></i>
            Sem comprovante e sem justificativa não há o que registrar — e o
            artefato fica parado na Validação quando o arquivo for montado.
          </span>
          <div class="modal__acoes">
            <button class="botao botao--fantasma" type="button"
                    @click="comprovando = null">Cancelar</button>
            <button class="botao" type="button" :disabled="!comprovantePodeSalvar"
                    @click="salvarComprovante">Salvar</button>
          </div>
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
          <button class="botao botao--fantasma" type="button"
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
                <template v-if="a.janela">{{ a.janela }} · </template>compromisso {{ a.agendamento_id }}
              </li>
            </ul>
            <p v-else class="nota pequeno">{{ t.resumo }}</p>
          </template>
        </div>

        <div class="modal__acoes">
          <button class="botao botao--fantasma" type="button"
                  @click="osAberta = null">Fechar</button>
        </div>
      </div>
    </div>
    <!-- 🔵 25/11 (passo 5) — A MODAL ANTES DE ESCREVER, decisao dele de 18/11.
         🚨 Ela DIZ o que vai acontecer do outro lado, em texto: a chamada
         dispara os webhooks do DataScope e manda PUSH para o tecnico que
         enviou a resposta. Confirmar sem saber disso seria a tela escondendo a
         consequencia. -->
    <div v-if="dsArtefato" class="modal" @click.self="fecharDatascope">
      <section class="modal__caixa modal__caixa--curta">
        <h2>Corrigir a situação no DataScope</h2>
        <p>
          A OS <strong>{{ dsArtefato.numero_os }}</strong> passa para
          <strong>Aprovado análise técnica</strong> no DataScope.
          <template v-if="dsArtefato.datascope_form_state">
            Hoje ela está como
            <strong>{{ dsArtefato.datascope_form_state }}</strong>.
          </template>
        </p>
        <p class="nota">
          Isto escreve no sistema deles: dispara os <strong>webhooks</strong> do
          DataScope e manda <strong>push para o técnico</strong> que enviou a
          resposta. Não volta para o estado vazio.
        </p>

        <p v-if="escritaDatascope === false" class="nota">
          A escrita no DataScope está <strong>desligada</strong> nesta tela.
        </p>
        <p v-else-if="escritaDatascope === null" class="nota">
          Não consegui medir se a escrita está ligada.
        </p>

        <p v-if="dsErro" class="nota erro">{{ dsErro }}</p>
        <p v-else-if="dsFeito" class="nota">{{ dsFeito }}</p>

        <div class="modal__rodape">
          <div class="modal__agir">
            <button v-if="escritaDatascope !== true" class="botao"
                    type="button" @click="ligarEscritaDatascope">
              <i class="bi bi-unlock" aria-hidden="true"></i>
              Ligar a escrita
            </button>
            <button v-else class="botao botao--perigo" type="button"
                    :disabled="dsFazendo" @click="confirmarDatascope">
              <i class="bi bi-pencil-square" aria-hidden="true"></i>
              Corrigir situação
            </button>
          </div>
          <div class="modal__acoes">
            <button class="botao botao--fantasma" type="button"
                    @click="fecharDatascope">Fechar</button>
          </div>
        </div>
      </section>
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
/* 🔵 25/11 — a IDENTIDADE da tela: título e ajuda juntos, como na Operação.
   ⚠️ Nome próprio nesta tela: `cabecalho__identidade` é `scoped` dentro do
   `PainelOperacao.vue`, e copiar o nome de lá daria marcação SEM ESTILO --
   a armadilha da `.pilula` de 12/11. */
.painel__identidade {
  display: flex; align-items: center; gap: var(--e-2); min-width: 0;
}

/* 🔵 25/11, dele: *"o nome do tecnico pode ter o mesmo destaque que os cards
   do OP com o Termo"*. No card do técnico o nome é o IDENTIFICADOR -- é por
   ele que se cruza com a planilha do Procfy -- então ganha o tratamento que a
   OS e o TERMO têm lá: acento e peso forte, no mesmo tamanho.
   ⚠️ Herda a quebra em 2 linhas do `card__cliente`, que é de onde ele saiu. */
.card__tecnico {
  font-weight: var(--peso-forte); font-size: var(--txt-sm);
  color: var(--acento);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 🔵 25/11 — OS QUADROS DE AÇÃO, e o rodapé numa faixa só.
   🚨 O que eles consertam: cinco botões de larguras diferentes, sem dizer o
   que fazem, com "Excluir o card" vizinho de "Atualizar". A grade dá largura
   IGUAL e quebra previsível; a nota diz o efeito antes do clique; o grupo
   separa o que lê, o que fecha dinheiro e o que desfaz. */
.acoes { display: flex; flex-direction: column; gap: var(--e-3);
         margin-top: var(--e-3); }
.acoes__grupo { margin: 0; }
.acoes__titulo {
  margin: 0 0 var(--e-2); font-size: var(--txt-xs); color: var(--texto-fraco);
  text-transform: uppercase; letter-spacing: .04em;
  font-weight: var(--peso-forte);
}
.acoes__grade {
  display: grid; gap: var(--e-2);
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}
.acao {
  display: flex; flex-direction: column; gap: 2px; text-align: left;
  padding: var(--e-2) var(--e-3); cursor: pointer; font: inherit;
  background: var(--superficie); color: var(--texto);
  border: var(--borda-fina) solid var(--borda-forte);
  border-radius: var(--r-md);
  transition: border-color var(--tempo-rapido) var(--curva),
              box-shadow var(--tempo-rapido) var(--curva);
}
.acao:hover { border-color: var(--acento); box-shadow: var(--sombra-1); }
.acao:focus-visible { outline: none; box-shadow: var(--foco); }
/* ⚠️ Desabilitado DIZ que está desabilitado: sem isto o quadro cinza continua
   com cara de clicável e a pessoa clica três vezes achando que travou. */
.acao:disabled { opacity: .55; cursor: not-allowed; box-shadow: none;
                 border-color: var(--borda); }
.acao__nome {
  display: flex; align-items: center; gap: var(--e-2);
  font-weight: var(--peso-forte); font-size: var(--txt-sm);
}
.acao__nota {
  font-size: var(--txt-xs); color: var(--texto-fraco);
  line-height: var(--entrelinha);
}
.acao--principal { border-color: var(--acento); background: var(--acento-suave); }
.acao--perigo:hover { border-color: var(--erro); }

/* A faixa única do rodapé: a regra à esquerda, o `Fechar` à direita.
   ⚠️ `.modal__acoes` já existe nesta folha e põe os botões à direita. */
.card__rodape {
  display: flex; flex-wrap: wrap; gap: var(--e-2);
  align-items: center; justify-content: space-between;
  margin-top: var(--e-3); padding-top: var(--e-3);
  border-top: var(--borda-fina) solid var(--borda);
}
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
/* ⚠️ `flex-basis: 100%` para a linha do corte cair SOZINHA abaixo dos três
   controles, em vez de disputar espaço com eles e virar uma frase apertada
   entre dois `<select>`. O `.controles` é `flex` com `wrap`. */
.painel__desde {
  flex-basis: 100%; margin: 0;
  display: flex; align-items: center; gap: var(--e-1); flex-wrap: wrap;
  font-size: var(--txt-xs); color: var(--texto-fraco);
}

/* O anexo do comprovante (25/11). ⚠️ O `<input type="file">` é escondido por
   CSS e não por `v-if`: ele tem de existir no DOM para o clique no botão
   alcançá-lo. `display: none` serve — o elemento continua clicável por
   programa, e é assim na Operação e na Caixa. */
/* 🔵 25/11 (passo 4b) — o quadro das colunas do Procfy, fechado por padrão:
   é cadastro que se preenche uma vez, e aberto roubaria a primeira tela de quem
   veio ver o quadro. */
.procfy {
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md); padding: var(--e-2) var(--e-3);
  background: var(--superficie);
}
.procfy__abrir {
  display: flex; align-items: center; gap: var(--e-2);
  cursor: pointer; font-weight: var(--peso-forte);
}
.procfy__grade {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--e-2); margin: var(--e-2) 0;
}
.procfy__campo { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.procfy__rotulo {
  font-size: var(--txt-xs); color: var(--texto-fraco);
  text-transform: uppercase; letter-spacing: .04em;
}
.procfy__agir { display: flex; align-items: center; gap: var(--e-2); }
.erro { color: var(--erro); }

.comprovante__anexo { display: flex; flex-direction: column; gap: var(--e-1);
                      margin-bottom: var(--e-2); }
.comprovante__arquivo { display: none; }

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
/* 🚨 25/11: era `--aviso` (âmbar de alerta). O orçamento não impede nada, e
   cor de alarme numa informação neutra faz o operador procurar problema onde
   não há. Fica no tom de apoio, como os vizinhos. */
.artefato__orcamento--sem { color: var(--texto-fraco); font-style: italic; }
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
/* 🚨 O CARD FECHADO VIROU `<button>` (23/11), e `<button>` traz consigo o
   `background`, a `border`, o `text-align: center`, o `font` do agente e o
   `cursor` padrão do navegador. Sem este bloco o card perderia a cara que
   tinha e ficaria centralizado, com fonte de sistema -- e nenhum teste de
   jsdom veria, porque o jsdom não faz layout. */
.card__abrir--botao {
  width: 100%; text-align: left; font: inherit; color: inherit;
  background: none; border: 0; padding: 0; margin: 0; cursor: pointer;
}
/* 🚨 **NÃO SE DECLARA `:focus-visible` AQUI.** O `estilo/base.css:55` já o faz
   para TODO elemento focável, com `outline: none` e `box-shadow: var(--foco)`.
   ⚠️ Eu havia escrito um `outline` próprio aqui, com um token que **não
   existe** (medido em 23/11 no CSS publicado: ele não está no `:root`). Só não
   virou regra descartada porque eu pusera um fallback — mas o efeito seria
   pior que o do token: uma especificidade maior que a do `base.css` daria a
   ESTE botão um anel de foco diferente do de todo o resto do sistema. */
/* ⚠️ A trava e o selo dentro de um `<button>` precisam ser `inline-flex` por
   conta própria: o `<span>` herdaria o `text-align` e o alinhamento do botão. */
.card__filtrado {
  display: inline-flex; align-items: center; gap: var(--e-1);
  font-size: var(--txt-xs); color: var(--texto-fraco);
}
.modal__titulo { margin: 0; font-size: var(--txt-lg); }
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

/* 🔵 25/11 — AS REGRAS QUE NASCERAM DEPOIS DA FONTE ÚNICA e voltaram com ela.
   ⚠️ Elas ficam NO FIM do bloco de propósito: `.artefato__marca` também existe
   acima, com o corpo de uma linha só, e o que vale é o último. */

/* 🔵 25/11 (A23) — o artefato como card interno.
   ⚠️ `align-items: flex-start`: a caixinha alinha com a PRIMEIRA linha do
   corpo, não no meio do bloco de três linhas. */
.artefato__marca {
  display: flex; align-items: flex-start; gap: var(--e-2);
  width: 100%; cursor: pointer;
}
.artefato__marca input[type="checkbox"] { margin-top: 3px; flex: none; }
/* `min-width: 0` para o nome do cliente poder encurtar em vez de empurrar o
   valor para fora do card -- a armadilha clássica do flex. */
.artefato__corpo {
  display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1 1 auto;
}
/* 🚨 O MARCADO SE VÊ, e não só pela caixinha: numa lista de 39 itens, a
   marcação de um checkbox sozinho se perde. */
.artefato--marcado {
  border-color: var(--acento);
  background: var(--acento-suave);
}

/* 🔵 25/11 — AS MEDIDAS DO CARD ABERTO: três números que eram uma frase.
   ⚠️ Rótulo em cima, valor embaixo: o valor é o que se procura. */
.medidas {
  display: flex; flex-wrap: wrap; gap: var(--e-3);
  padding: var(--e-2) var(--e-3);
  background: var(--superficie-2);
  border-radius: var(--r-md);
}
.medida { display: flex; flex-direction: column; min-width: 0; }
.medida__rotulo {
  font-size: var(--txt-xs); color: var(--texto-fraco);
  text-transform: uppercase; letter-spacing: .04em;
}
.medida__valor { font-size: var(--txt-sm); font-weight: var(--peso-forte); }

/* O rótulo do campo de data fica ao LADO, não em cima: numa linha de filtro,
   "de" e "até" em cima de cada campo dobram a altura da faixa. */
.campo__rotulo--lado {
  display: flex; align-items: center; gap: var(--e-1);
  font-size: var(--txt-xs); color: var(--texto-fraco);
}
.campo__rotulo--lado .campo { width: auto; }

/* 🔵 25/11 — O VOCABULÁRIO DO CARD que o artefato (A23) usa, com os corpos da
   `PainelOperacao.vue` (o modelo que ele validou). ⚠️ É cópia de CSS, e a
   dívida está declarada no `conferir_css_publicado.mjs`: a casa comum só volta
   com a palavra dele e com uma forma de medir layout antes de publicar. */
.card__ident {
  display: flex; align-items: baseline; gap: var(--e-1);
  min-width: 0; flex-wrap: wrap;
}
.card__os {
  font-size: var(--txt-md);
  font-weight: var(--peso-forte);
  background: none; border: 0; padding: 0;
  color: var(--texto); cursor: pointer; text-align: left;
}
.card__os:focus-visible { outline: 2px solid var(--acento); outline-offset: 2px; }
/* ⚠️ MAIS FRACO QUE O NÚMERO DA OS de propósito: a OS é a identidade. */
.card__termo { font-size: var(--txt-xs); color: var(--texto-fraco); white-space: nowrap; }
.card__direita--dado {
  min-width: 0; overflow: hidden; text-overflow: ellipsis;
  font-size: var(--txt-sm);
}
/* ⚠️ Cliente sem cadastro não é apoio, é uma FALTA: âmbar legível, não cinza. */
.card__cliente--sem {
  font-size: var(--txt-sm);
  font-weight: var(--peso-normal);
  color: var(--aviso-texto); font-style: italic;
}
</style>
