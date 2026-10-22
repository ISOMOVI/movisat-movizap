<script setup>
/* ============================================================================
   O modal do botão Agendar — três abas. 🔵 Pedido dele de 19/10.
   ----------------------------------------------------------------------------
   🔵 Fluxo real, nas palavras dele: *"o operador pede dados ao cliente via
   chat, confirma com o tecnico e dai envia o orçamento para ele; ele
   validando, vai clicar no agendamento tecnico e depois no do cliente para
   confirmar"*. Por isso a ordem é **Orçamento → Agendar → Confirmar**.

   🚨 A ABA QUE ABRE DEPENDE DO CONTATO. Conversa de técnico vê Orçamento e
   Agendar; conversa de cliente vê Confirmar. Conversa sem contato não some
   com o botão: ela **explica por que não dá**, que é a diferença entre uma
   tela que ensina e uma que esconde.

   🚨 AS DUAS CONFIRMAÇÕES SAEM PRÉ-ESCRITAS, E QUEM ENVIA É O ATENDENTE
   (decisão 6 dele). Este modal escreve no compositor e sai da frente -- não
   manda nada sozinho.
   ============================================================================ */
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { api } from '../api/cliente.js'
import { agrupar, dataBr, horaBr, textosDoGrupo } from '../util/mensagem_agendamento.js'

const props = defineProps({
  conversaId: { type: Number, required: true },
  relacao: { type: String, default: '' },
  contatoNome: { type: String, default: '' },
  // Só existe em conversa de CLIENTE: em conversa de técnico o
  // `contato.cliente_id` é NULL por desenho (decisão dele de 07/10).
  clienteHarmonitId: { type: String, default: '' },
  clienteNome: { type: String, default: '' },
})
const emit = defineEmits(['fechar', 'inserir'])

const router = useRouter()

/* ---- A TRAVA DO MODAL (🔵 pedido dele, 21/10) ------------------------------
   *"coloque trava nesse modal, se clicar fora dele no movizap ele aparece
   aviso de 'cancelar' ou 'continuar'"*.

   🚨 O MOTIVO E O TRABALHO PERDIDO. Este modal guarda orcamento em
   digitacao, OS marcadas, data, endereco -- e um clique no fundo apagava tudo
   sem perguntar. Era o unico caminho de saida acidental: o X e o Enter sao
   deliberados.

   ⚠️ "Continuar" NAO E "salvar": e voltar ao modal. Quem fecha perde o que
   nao gravou, e o aviso diz isso -- botao que promete o que nao cumpre e o
   defeito do "Nao perturbe". */
function tentarFechar() {
  if (!window.confirm('Fechar o agendamento?\n\nO que não foi gravado se '
                      + 'perde: orçamento em digitação, OS marcadas, data e '
                      + 'endereço.\n\nOK cancela o agendamento. Cancelar '
                      + 'continua aqui.')) return
  emit('fechar')
}

const ehTecnico = computed(() => props.relacao === 'tecnico')
const ehCliente = computed(() => props.relacao === 'cliente')

const abas = computed(() => {
  if (ehTecnico.value) return [
    { id: 'orcamento', rotulo: 'Orçamento' },
    { id: 'agendar', rotulo: 'Agendar' },
  ]
  if (ehCliente.value) return [{ id: 'confirmar', rotulo: 'Confirmar' }]
  return []
})
const aba = ref('')
watch(abas, (lista) => { if (!aba.value && lista.length) aba.value = lista[0].id },
      { immediate: true })

const erro = ref('')
const ocupado = ref(false)

/* ---------------------------------------------------------------- Orçamento */
const catalogo = ref([])
const proximoNumero = ref(null)
const linhas = ref([])
const osDoOrcamento = ref('')
const orcamentoEmitido = ref(null)

function linhaNova() {
  const padrao = catalogo.value[0] || { servico: '', unidade: 'un' }
  return { servico: padrao.servico, preco_unit: '', quantidade: '1',
           unidade: padrao.unidade }
}

function trocarServico(linha) {
  const achado = catalogo.value.find((c) => c.servico === linha.servico)
  // A unidade acompanha o serviço: deslocamento é km, e é isso que faz o PDF
  // imprimir "77,7 km" em vez de "77.7 un".
  if (achado) linha.unidade = achado.unidade
}

const totalCentavos = computed(() => linhas.value.reduce((soma, l) => {
  const preco = Math.round((Number(String(l.preco_unit).replace(',', '.')) || 0) * 100)
  const qtd = Number(String(l.quantidade).replace(',', '.')) || 0
  return soma + Math.round(preco * qtd)
}, 0))

function emReais(centavos) {
  return (centavos / 100).toLocaleString('pt-BR', { minimumFractionDigits: 2 })
}

const podeEmitir = computed(() =>
  linhas.value.length > 0 &&
  linhas.value.every((l) => l.servico && Number(String(l.preco_unit).replace(',', '.')) > 0
                            && Number(String(l.quantidade).replace(',', '.')) > 0))

async function emitirOrcamento() {
  ocupado.value = true
  erro.value = ''
  try {
    const ordens = osDoOrcamento.value
      .split(/[\s,;]+/).map((n) => Number(n)).filter((n) => Number.isInteger(n) && n > 0)
    orcamentoEmitido.value = await api.post(
      `/api/conversas/${props.conversaId}/orcamento`,
      { ordens, itens: linhas.value.map((l) => ({ ...l })) })
    proximoNumero.value = orcamentoEmitido.value.numero + 1
  } catch (e) {
    erro.value = e?.message || 'Não deu para emitir o orçamento.'
  } finally {
    ocupado.value = false
  }
}

async function reenviarOrcamento() {
  if (!orcamentoEmitido.value) return
  ocupado.value = true
  erro.value = ''
  try {
    const r = await api.post(
      `/api/conversas/${props.conversaId}/orcamento/${orcamentoEmitido.value.id}/reenviar`)
    // Relê o resultado do envio em vez de assumir que foi: a confirmação é o
    // estado, nunca o fato de o botão ter sido clicado.
    orcamentoEmitido.value = { ...orcamentoEmitido.value, enviado: r.enviado }
  } catch (e) {
    erro.value = e?.message || 'Não deu para reenviar.'
  } finally {
    ocupado.value = false
  }
}

/* ------------------------------------------------------------------ Agendar */
const passo = ref(1)
const quando = ref('')

/* ---- O CALENDARIO SEMPRE ABERTO (🔵 pedido dele, 21/10) -------------------
   *"o botao do calendario pode ficar um pouco mais perto ou ja aparecer em
   aberto mesmo, ficar sempre aberto"*.

   🚨 POR QUE NAO FOI O `showPicker()` DO NAVEGADOR: ele depende de cada
   navegador e **fecha sozinho** ao clicar fora -- "sempre aberto" nao se
   sustentaria. Este calendario e desenhado aqui, entao esta sempre visivel
   porque e parte da tela, e nao um popup emprestado.

   O `input datetime-local` fica, escondido do olho mas presente: e ele que
   carrega o `quando`, e e por ele que teste e teclado continuam funcionando.

   ⚠️ PASSO DE 30 MINUTOS, das 7h as 19h -- escolha minha, declarada: ele
   nao vetou quando propus. Horario fora disso ainda entra, pelo campo. */
const HORA_DE = 7
const HORA_ATE = 19
const PASSO_MIN = 30

function _iso(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const hojeIso = _iso(new Date())
const mesCursor = ref(new Date(new Date().getFullYear(), new Date().getMonth(), 1, 12))

const diaEscolhido = computed(() => (quando.value || '').slice(0, 10))
const horaEscolhida = computed(() => (quando.value || '').slice(11, 16))

const rotuloDoMes = computed(() =>
  mesCursor.value.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' }))

const diasDoMes = computed(() => {
  const base = mesCursor.value
  const primeiro = new Date(base.getFullYear(), base.getMonth(), 1, 12)
  const lista = []
  for (let i = 0; i < primeiro.getDay(); i += 1) lista.push(null)
  const d = new Date(primeiro)
  while (d.getMonth() === base.getMonth()) {
    const iso = _iso(d)
    lista.push({ iso, dia: d.getDate(), hoje: iso === hojeIso, passado: iso < hojeIso })
    d.setDate(d.getDate() + 1)
  }
  return lista
})

const horarios = computed(() => {
  const lista = []
  for (let h = HORA_DE; h <= HORA_ATE; h += 1) {
    for (let m = 0; m < 60; m += PASSO_MIN) {
      if (h === HORA_ATE && m > 0) break
      lista.push(`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`)
    }
  }
  return lista
})

function andarMes(passoMes) {
  const d = new Date(mesCursor.value)
  d.setMonth(d.getMonth() + passoMes)
  mesCursor.value = new Date(d.getFullYear(), d.getMonth(), 1, 12)
}

/* ⚠️ Dia e hora se escolhem SEPARADO, e por isso cada um preserva o outro:
   trocar o dia depois de escolher a hora nao pode apagar a hora. Sem hora
   ainda, o dia nasce com a primeira do expediente -- e `quando` nunca fica
   meio preenchido, que e o que o `Continuar` mede. */
function escolherDia(d) {
  quando.value = `${d.iso}T${horaEscolhida.value || String(HORA_DE).padStart(2, '0') + ':00'}`
}

function escolherHora(h) {
  quando.value = `${diaEscolhido.value || hojeIso}T${h}`
}
const clientes = ref([])
const buscaCliente = ref('')
const clienteEscolhido = ref(null)
const osDoCliente = ref([])
const jaAgendadas = ref([])
const osEscolhidas = ref([])
const endereco = ref('')
const agendado = ref(null)

/* ---- O ENDERECO EM CAMPOS SEPARADOS (🔵 pedido dele, 21/10) --------------
   *"a tela 3 precisa ter o campo com os dados de endereço separados, para
   enviar sem erros no harmonit... sem os campos, podem inserir de qqer jeito"*.

   🚨 OS SETE CAMPOS SAO OS DO HARMONIT, um a um -- a OS guarda `cep`,
   `endereco`(rua), `numero`, `bairro`, `cidade`, `uf` e `complemento`. O unico
   nome diferente e `logradouro`, que la e `endereco`: aqui esse nome ja era da
   linha montada que sai na mensagem.

   🚨 PRE-PREENCHE COM O ENDERECO DA PROPRIA OS. Endereco vindo da fonte e
   melhor que endereco digitado -- e foi medido que ele existe: das 30 OS
   amostradas em 21/10, 23 tem rua. ⚠️ As outras 7 nao tem nada, e e para
   essas que existe o caminho do CEP.

   ⚠️ TUDO CONTINUA EDITAVEL depois do preenchimento (*"ela ainda edita se
   precisar"*): endereco de servico tem excecao -- condominio, zona rural, rua
   renomeada -- e quem decide e quem atende. */
const LIMITES = { cep: 8, logradouro: 80, numero: 10, bairro: 60, cidade: 50,
                  uf: 2, complemento: 40 }

function enderecoVazio() {
  return { cep: '', logradouro: '', numero: '', bairro: '', cidade: '', uf: '',
           complemento: '' }
}

const campos = ref(enderecoVazio())
const enderecoDaOs = ref(null)
const cepEstado = ref('')   // '', 'buscando', 'achado', 'nao-existe', 'caiu'

const temRua = computed(() => !!campos.value.logradouro.trim())

/* A linha como ela vai sair na mensagem -- a mesma regra do backend.
   🚨 Mostrada na tela de proposito: o operador ve o que o CLIENTE vai ler,
   antes de gravar. */
const linhaDoEndereco = computed(() => {
  const e = campos.value
  const primeiro = [e.logradouro.trim(), e.numero.trim()].filter(Boolean).join(', ')
  const local = [e.cidade.trim(), e.uf.trim()].filter(Boolean).join(' - ')
  return [primeiro, e.bairro.trim(), e.complemento.trim(), local,
          e.cep.trim() ? `CEP ${e.cep.trim()}` : ''].filter(Boolean).join(' · ')
})

async function carregarEnderecoDaOs() {
  const primeira = osEscolhidas.value[0]
  if (!primeira) return
  try {
    const r = await api.get(
      `/api/agendamento/os/${primeira.numero_os}/endereco`)
    enderecoDaOs.value = r
    if (!r.tem_endereco) return
    // ⚠️ So preenche o que esta VAZIO: se o operador ja digitou, o cadastro
    // da OS nao passa por cima -- ele veio depois na tela, nao antes.
    const vindo = r.endereco || {}
    const mapa = { cep: vindo.cep, logradouro: vindo.endereco,
                   numero: vindo.numero, bairro: vindo.bairro,
                   cidade: vindo.cidade, uf: vindo.uf,
                   complemento: vindo.complemento }
    for (const [k, v] of Object.entries(mapa)) {
      if (v && !campos.value[k]) campos.value[k] = String(v)
    }
  } catch (e) {
    // 🚨 Nao e erro de tela: o compromisso pode ser agendado com endereco
    // digitado. A tela diz que nao conseguiu ler o da OS.
    enderecoDaOs.value = { erro: e?.message || 'não deu para ler o endereço da OS' }
  }
}

async function buscarCep() {
  const limpo = campos.value.cep.replace(/\D/g, '')
  if (limpo.length !== 8) { cepEstado.value = 'curto'; return }
  cepEstado.value = 'buscando'
  try {
    const r = await api.get(`/api/cep/${limpo}`)
    if (!r.achado) { cepEstado.value = 'nao-existe'; return }
    campos.value.cep = r.cep
    // ⚠️ O CEP preenche rua, bairro, cidade e UF -- e NUNCA o numero, que
    // ele nao sabe. Numero vem do operador, sempre.
    campos.value.logradouro = r.logradouro || campos.value.logradouro
    campos.value.bairro = r.bairro || campos.value.bairro
    campos.value.cidade = r.cidade || campos.value.cidade
    campos.value.uf = r.uf || campos.value.uf
    cepEstado.value = 'achado'
  } catch (e) {
    // 🚨 "Nao deu para consultar" NAO e "CEP errado", e a tela diz qual dos
    // dois foi: o contrario faria o operador apagar um CEP certo.
    cepEstado.value = 'caiu'
    erro.value = e?.message || 'Não deu para consultar o CEP agora.'
  }
}

const clientesFiltrados = computed(() => {
  const termo = buscaCliente.value.trim().toUpperCase()
  const lista = clientes.value.filter((c) => !c.sem_cadastro)
  if (!termo) return lista.slice(0, 40)
  return lista.filter((c) => (c.nome || '').toUpperCase().includes(termo)).slice(0, 40)
})

async function carregarClientes() {
  ocupado.value = true
  erro.value = ''
  try {
    const r = await api.get('/api/agendamento/clientes')
    clientes.value = r.clientes || []
  } catch (e) {
    // 🚨 Lista vazia e ponte fora do ar são coisas diferentes, e a tela diz
    // qual é o caso: o contrário faria agendar por cima de serviço existente.
    erro.value = e?.message || 'Não deu para consultar as OS no FPSL.'
    clientes.value = []
  } finally {
    ocupado.value = false
  }
}

async function escolherCliente(c) {
  clienteEscolhido.value = c
  osEscolhidas.value = []
  ocupado.value = true
  erro.value = ''
  try {
    const r = await api.get(`/api/agendamento/clientes/${c.harmonit_id}/os`)
    osDoCliente.value = r.os || []
    jaAgendadas.value = r.ja_agendadas || []
    const sugestao = await api.get(
      `/api/agendamento/endereco-sugerido/${c.harmonit_id}`)
    // Sugestão, não preenchimento automático: 🔵 decisão 11 dele é que o
    // operador DIGITA. Endereço herdado em silêncio manda técnico ao lugar
    // errado.
    if (sugestao.endereco && !endereco.value) endereco.value = sugestao.endereco
  } catch (e) {
    erro.value = e?.message || 'Não deu para consultar as OS deste cliente.'
    osDoCliente.value = []
  } finally {
    ocupado.value = false
  }
}

/* A cor do selo do tipo. ⚠️ Mapa FECHADO, com os 5 nomes que o Harmonit
   devolve (medidos em 21/10): tipo que nao estiver aqui cai no neutro, em vez
   de a tela inventar cor para um nome que ela nao conhece. */
const CLASSE_DO_TIPO = {
  'Contrato': 'agm__tipo--contrato',
  'Solicitação de Cliente': 'agm__tipo--solicitacao',
  'Ordem de Serviço': 'agm__tipo--ordem',
  'Demanda Interna': 'agm__tipo--interna',
  'Teste ou Treinamento': 'agm__tipo--teste',
}

function seloDoTipo(nome) {
  return CLASSE_DO_TIPO[nome] || 'agm__tipo--sem-nome'
}

function placasDaOs(os) {
  if (!os.veiculos || !os.veiculos.length) return 'sem placa registrada'
  return os.veiculos.map((v) => v.placa).join(', ')
}

function alternarOs(os) {
  if (jaAgendadas.value.includes(os.numero_os)) return
  const i = osEscolhidas.value.findIndex((o) => o.numero_os === os.numero_os)
  if (i >= 0) osEscolhidas.value.splice(i, 1)
  else osEscolhidas.value.push({
    numero_os: os.numero_os,
    placa: (os.veiculos && os.veiculos[0] && os.veiculos[0].placa) || null,
    // Ponta 1: o nome do tipo vai GRAVADO no compromisso (retrato, como a
    // placa), para o cabeçalho da mensagem. ⚠️ Nulo é o caso comum -- 173 das
    // 547 OS têm tipo fora da lista do Harmonit -- e o cabeçalho omite o
    // segmento nesse caso, em vez de imprimir número ou rótulo inventado.
    tipo_nome: os.tipo_nome || null,
  })
}

const osMarcada = (os) => osEscolhidas.value.some((o) => o.numero_os === os.numero_os)

const podeAgendar = computed(() =>
  !!quando.value && !!clienteEscolhido.value && osEscolhidas.value.length > 0)

async function gravarAgendamento() {
  ocupado.value = true
  erro.value = ''
  try {
    agendado.value = await api.post('/api/agendamentos', {
      conversa_id: props.conversaId,
      cliente_harmonit_id: clienteEscolhido.value.harmonit_id,
      cliente_nome: clienteEscolhido.value.nome,
      inicio: new Date(quando.value).toISOString(),
      endereco: linhaDoEndereco.value || endereco.value.trim() || null,
      endereco_campos: { ...campos.value },
      ordens: osEscolhidas.value,
      orcamento_id: orcamentoEmitido.value ? orcamentoEmitido.value.id : null,
    })
    passo.value = 4
  } catch (e) {
    erro.value = e?.message || 'Não deu para gravar o agendamento.'
  } finally {
    ocupado.value = false
  }
}

/* ---------------------------------------------------------------- Confirmar */
const aguardando = ref([])
const marcados = ref([])
const responsavel = ref('')

async function carregarAguardando() {
  if (!props.clienteHarmonitId) return
  ocupado.value = true
  erro.value = ''
  try {
    const r = await api.get(`/api/agendamento/aguardando/${props.clienteHarmonitId}`)
    aguardando.value = r.agendamentos || []
  } catch (e) {
    erro.value = e?.message || 'Não deu para ler o que espera confirmação.'
  } finally {
    ocupado.value = false
  }
}

function alternarMarcado(a) {
  const i = marcados.value.indexOf(a.id)
  if (i >= 0) marcados.value.splice(i, 1)
  else marcados.value.push(a.id)
}

/* 🚨 A MONTAGEM DAS DUAS MENSAGENS MORA EM `util/mensagem_agendamento.js`, e
   não aqui: desde 21/10 a `ATD_7.1` também as monta ("Reenviar confirmação",
   ponta 2 do plano), e a mesma mensagem escrita em dois lugares viraria duas
   mensagens diferentes no primeiro ajuste de campo. A do cliente é a única que
   sai para fora da casa. */
function textos(grupo) {
  return textosDoGrupo(grupo, { responsavelPadrao: responsavel.value })
}

const mensagens = ref([])

/* ---- F5: ENVIAR AO CLIENTE, E ABRIR NO TECNICO (🔵 21/10) ----------------
   *"os botões de cada texto podem ser: 'Enviar ao cliente' e do outro 'Abrir
   na conversa do tecnico', então envia o primeiro e o modal persiste, como
   orçamento faz, dai operador decide clicar no outro ou não, não sendo
   obrigatório"*.

   🚨 O MODAL PERSISTE DEPOIS DE ENVIAR, como o orcamento: fechar sozinho
   levaria embora o texto do tecnico, que e o segundo passo opcional.

   ⚠️ A DECISAO 6 DELE CONTINUA VALENDO -- *"quem envia e o atendente"*: o
   botao e um clique dele, e o que desapareceu foi o desvio pelo compositor.

   🚨 ENVIAR E A CONVERSA ABERTA, e so ela: a rota `/responder` exige estar
   na conversa, e a do tecnico e outra. Por isso o segundo botao ABRE em vez de
   enviar -- prometer envio ali seria botao que nao cumpre. */
async function enviarAoCliente(m) {
  m.enviando = true
  m.erroEnvio = ''
  try {
    await api.post(`/api/conversas/${props.conversaId}/responder`,
                   { texto: m.doCliente })
    m.enviado = true
  } catch (e) {
    m.erroEnvio = e?.message || 'Não deu para enviar.'
  } finally {
    m.enviando = false
  }
}

function abrirNoTecnico(m) {
  if (!m.conversaDoTecnico) return
  /* 🚨 O caminho e o RASCUNHO POR CONVERSA (Bloco 7, 15/10): a Caixa semeia
     o compositor com `movizap.rascunho.<id>` ao abrir a conversa. ⚠️ Nao
     sobrescreve texto nao enviado de ninguem sem perguntar. */
  const chave = `movizap.rascunho.${m.conversaDoTecnico}`
  try {
    const havia = localStorage.getItem(chave)
    if (havia && havia.trim() && havia !== m.doTecnico
        && !window.confirm('A conversa do técnico já tem texto não enviado no '
                           + 'compositor. Substituir?')) return
    localStorage.setItem(chave, m.doTecnico)
  } catch { /* sem storage: abre de todo jeito, o texto esta na tela */ }
  emit('fechar')
  router.push(`/atendimento/${m.conversaDoTecnico}`)
}

async function confirmar() {
  if (!responsavel.value.trim()) {
    erro.value = 'Diga quem acompanha o técnico — é campo das duas mensagens.'
    return
  }
  ocupado.value = true
  erro.value = ''
  try {
    const confirmados = []
    for (const id of marcados.value) {
      confirmados.push(await api.post(`/api/agendamentos/${id}/confirmar`,
                                      { responsavel_cliente: responsavel.value.trim() }))
    }
    /* ⚠️ Cada mensagem ganha estado PROPRIO de envio: sao varias quando ha
       horarios diferentes, e um estado compartilhado marcaria todas como
       enviadas no primeiro clique. E `conversaDoTecnico` sai do compromisso --
       a conversa de ORIGEM e a do tecnico (decisao dele de 07/10). */
    mensagens.value = agrupar(confirmados).map((grupo) => ({
      ...textos(grupo),
      conversaDoTecnico: grupo[0]?.conversa_id || null,
      enviando: false,
      enviado: false,
      erroEnvio: '',
    }))
  } catch (e) {
    erro.value = e?.message || 'Não deu para confirmar.'
  } finally {
    ocupado.value = false
  }
}

function usar(texto) {
  emit('inserir', texto)
  emit('fechar')
}

onMounted(() => {
  if (ehTecnico.value) {
    api.get('/api/orcamento/catalogo').then((r) => {
      catalogo.value = r.catalogo || []
      proximoNumero.value = r.proximo_numero
      if (!linhas.value.length) linhas.value = [linhaNova()]
    }).catch((e) => { erro.value = e?.message || 'Não deu para ler o catálogo.' })
    carregarClientes()
  }
  if (ehCliente.value) carregarAguardando()
})
</script>

<template>
  <div class="agm__fundo" @click.self="tentarFechar">
    <section class="agm" role="dialog" aria-label="Agendar serviço">
      <header class="agm__topo">
        <h2 class="agm__titulo">Agendar serviço</h2>
        <button class="botao botao--fantasma botao--icone" type="button"
                aria-label="Fechar" @click="tentarFechar">
          <i class="bi bi-x-lg" aria-hidden="true"></i>
        </button>
      </header>

      <!-- 🚨 Sem contato o botão EXPLICA, em vez de sumir. -->
      <p v-if="!abas.length" class="aviso aviso--info">
        Esta conversa não tem contato marcado como <b>técnico</b> nem como
        <b>cliente</b>. Marque o tipo do contato na ficha ao lado: o orçamento
        sai no nome do técnico, e a confirmação é do cliente.
      </p>

      <template v-else>
        <nav class="agm__abas">
          <button v-for="a in abas" :key="a.id" type="button"
                  class="agm__aba" :class="{ 'agm__aba--ativa': aba === a.id }"
                  @click="aba = a.id">{{ a.rotulo }}</button>
        </nav>

        <p v-if="erro" class="aviso aviso--erro">{{ erro }}</p>

        <!-- ------------------------------------------------- aba Orçamento -->
        <div v-if="aba === 'orcamento'" class="agm__corpo">
          <!-- 🚨 EMITIDO E NÃO ENVIADO É UM TERCEIRO CASO, e precisa de
               nome próprio: o documento existe, o número já foi gasto, e só o
               envio falhou. Em 21/10 isso apareceu como "erro ao gerar PDF",
               que era falso nas três palavras. -->
          <template v-if="orcamentoEmitido">
            <!-- 🚨 A CADEIA v-if/v-else NÃO PODE SER CORTADA AO MEIO. Pôr um
                 <p> entre o `v-if` e o `v-else` fez os dois avisos saírem
                 juntos: "o PDF foi" e "o PDF não chegou", na mesma tela.
                 Achado por teste. -->
            <p v-if="orcamentoEmitido.enviado && orcamentoEmitido.enviado.ok"
               class="aviso aviso--ok">
              Orçamento <b>nº {{ orcamentoEmitido.numero }}</b> emitido —
              R$ {{ emReais(orcamentoEmitido.total_centavos) }}. O PDF foi para
              a conversa.
            </p>
            <p v-else class="aviso aviso--atencao">
              Orçamento <b>nº {{ orcamentoEmitido.numero }}</b> foi gerado —
              R$ {{ emReais(orcamentoEmitido.total_centavos) }} —, mas
              <b>o PDF não chegou à conversa</b>:
              {{ (orcamentoEmitido.enviado && orcamentoEmitido.enviado.motivo)
                 || 'o envio não respondeu' }}.
              O número já foi usado, então reenvie este mesmo documento em vez
              de emitir outro.
            </p>

            <!-- 🔵 21/10, decisão dele: o documento leva o nome do CADASTRO DO
                 HARMONIT, achado pelo telefone do contato. A tela diz qual
                 nome saiu — descobrir isso abrindo o PDF seria tarde. -->
            <p v-if="orcamentoEmitido.tecnico_do_harmonit
                     && orcamentoEmitido.tecnico_do_harmonit.achado"
               class="agm__dica">
              Saiu em nome de <b>{{ orcamentoEmitido.tecnico_nome }}</b>, como
              está no cadastro do Harmonit.
            </p>
            <p v-else-if="orcamentoEmitido.tecnico_nome" class="aviso aviso--atencao">
              Não achei este técnico no cadastro do Harmonit pelo telefone do
              contato, então o documento saiu com o nome daqui:
              <b>{{ orcamentoEmitido.tecnico_nome }}</b>.
            </p>

            <div v-if="!(orcamentoEmitido.enviado && orcamentoEmitido.enviado.ok)"
                 class="agm__acoes">
              <button class="botao botao--primario" type="button"
                      :disabled="ocupado" @click="reenviarOrcamento">
                {{ ocupado ? 'Reenviando…' : 'Reenviar o PDF' }}
              </button>
            </div>
          </template>

          <template v-else>
            <p class="agm__dica">
              Próximo número: <b>{{ proximoNumero ?? '—' }}</b>. O número só é
              gasto quando o PDF é gerado.
            </p>

            <label class="agm__campo">
              <span>OS deste orçamento (números, separados por vírgula)</span>
              <input v-model="osDoOrcamento" class="campo__entrada"
                     placeholder="17015, 17016" />
            </label>

            <table class="tabela agm__itens">
              <thead>
                <tr><th>Serviço</th><th>Preço unit.</th><th>Qtde.</th><th>Un.</th><th>Valor</th><th></th></tr>
              </thead>
              <tbody>
                <tr v-for="(l, i) in linhas" :key="i">
                  <td>
                    <select v-model="l.servico" class="campo__entrada"
                            @change="trocarServico(l)">
                      <option v-for="c in catalogo" :key="c.servico" :value="c.servico">
                        {{ c.servico }}
                      </option>
                    </select>
                  </td>
                  <td><input v-model="l.preco_unit" class="campo__entrada agm__num"
                             inputmode="decimal" placeholder="0,00" /></td>
                  <td><input v-model="l.quantidade" class="campo__entrada agm__num"
                             inputmode="decimal" /></td>
                  <td>{{ l.unidade }}</td>
                  <td>
                    R$ {{ emReais(Math.round(
                      (Number(String(l.preco_unit).replace(',', '.')) || 0) * 100
                      * (Number(String(l.quantidade).replace(',', '.')) || 0))) }}
                  </td>
                  <td>
                    <button class="botao botao--fantasma botao--icone" type="button"
                            aria-label="Tirar linha" @click="linhas.splice(i, 1)">
                      <i class="bi bi-trash" aria-hidden="true"></i>
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>

            <div class="agm__linha">
              <button class="botao botao--contorno" type="button"
                      @click="linhas.push(linhaNova())">Mais uma linha</button>
              <b class="agm__total">Total: R$ {{ emReais(totalCentavos) }}</b>
            </div>

            <div class="agm__acoes">
              <button class="botao botao--primario" type="button"
                      :disabled="ocupado || !podeEmitir" @click="emitirOrcamento">
                {{ ocupado ? 'Gerando…' : 'Gerar e anexar o PDF' }}
              </button>
            </div>
          </template>
        </div>

        <!-- --------------------------------------------------- aba Agendar -->
        <div v-else-if="aba === 'agendar'" class="agm__corpo">
          <template v-if="agendado">
            <p class="aviso aviso--ok">
              Agendado para <b>{{ dataBr(agendado.inicio) }} às {{ horaBr(agendado.inicio) }}</b>,
              esperando a confirmação do cliente. Abra a conversa do cliente para
              confirmar e enviar os avisos.
            </p>
            <!-- 🚨 A ESCRITA NO HARMONIT TEM VOZ PRÓPRIA. Ela pode falhar sem
                 derrubar o compromisso (o dono é o MoviZap), e calar a recusa
                 faria o operador achar que a OS foi agendada lá também. -->
            <p v-if="agendado.harmonit && agendado.harmonit.ligado
                     && agendado.harmonit.quantas_foram"
               class="aviso aviso--ok">
              A OS também foi agendada no Harmonit.
            </p>
            <p v-else-if="agendado.harmonit && agendado.harmonit.erro"
               class="aviso aviso--atencao">
              O compromisso vale aqui, mas <b>não foi agendado no Harmonit</b>:
              {{ agendado.harmonit.erro }}
            </p>
          </template>

          <template v-else>
            <ol class="agm__passos">
              <li :class="{ 'agm__passo--ativo': passo === 1 }">1. Data e hora</li>
              <li :class="{ 'agm__passo--ativo': passo === 2 }">2. Cliente e OS</li>
              <li :class="{ 'agm__passo--ativo': passo === 3 }">3. Resumo e endereço</li>
            </ol>

            <div v-if="passo === 1">
              <!-- 🔵 Sempre aberto: e parte da tela, nao um popup. -->
              <div class="agm__quando">
                <div class="agm__cal">
                  <header class="agm__cal-topo">
                    <button class="botao botao--fantasma" type="button"
                            aria-label="Mês anterior" @click="andarMes(-1)">
                      <i class="bi bi-chevron-left" aria-hidden="true"></i>
                    </button>
                    <strong class="agm__cal-mes">{{ rotuloDoMes }}</strong>
                    <button class="botao botao--fantasma" type="button"
                            aria-label="Mês seguinte" @click="andarMes(1)">
                      <i class="bi bi-chevron-right" aria-hidden="true"></i>
                    </button>
                  </header>
                  <div class="agm__cal-grade">
                    <span v-for="(s, i) in ['D', 'S', 'T', 'Q', 'Q', 'S', 'S']"
                          :key="`s${i}`" class="agm__cal-semana">{{ s }}</span>
                    <template v-for="(d, i) in diasDoMes" :key="d ? d.iso : `v${i}`">
                      <span v-if="!d" class="agm__cal-vago"></span>
                      <button v-else type="button" class="agm__cal-dia"
                              :class="{ 'agm__cal-dia--ativo': d.iso === diaEscolhido,
                                        'agm__cal-dia--hoje': d.hoje,
                                        'agm__cal-dia--passado': d.passado }"
                              @click="escolherDia(d)">{{ d.dia }}</button>
                    </template>
                  </div>
                  <!-- ⚠️ Dia passado NAO e proibido: remarcar servico que ja
                       aconteceu e caso real. A tela avisa, nao barra. -->
                  <p v-if="diaEscolhido && diaEscolhido < hojeIso"
                     class="aviso aviso--atencao agm__cal-nota">
                    Este dia já passou. Dá para agendar, mas confira.
                  </p>
                </div>
                <div class="agm__horas">
                  <span class="agm__horas-rotulo">Horário</span>
                  <div class="agm__horas-grade">
                    <button v-for="h in horarios" :key="h" type="button"
                            class="agm__hora"
                            :class="{ 'agm__hora--ativo': h === horaEscolhida }"
                            @click="escolherHora(h)">{{ h }}</button>
                  </div>
                </div>
              </div>
              <label class="agm__campo">
                <span>Ou digite dia e hora (aceita fora do expediente)</span>
                <input v-model="quando" type="datetime-local" class="campo__entrada" />
              </label>
              <div class="agm__acoes">
                <button class="botao botao--primario" type="button"
                        :disabled="!quando" @click="passo = 2">Continuar</button>
              </div>
            </div>

            <div v-else-if="passo === 2">
              <p class="agm__dica">
                Só clientes com <b>OS em aberto nos últimos 6 meses</b>.
              </p>
              <label class="agm__campo">
                <span>Cliente</span>
                <input v-model="buscaCliente" class="campo__entrada"
                       placeholder="Buscar pelo nome" />
              </label>

              <ul v-if="!clienteEscolhido" class="agm__lista">
                <li v-for="c in clientesFiltrados" :key="c.harmonit_id">
                  <button type="button" class="agm__item" @click="escolherCliente(c)">
                    <span>{{ c.nome }}</span>
                    <small>{{ c.quantas_os }} OS</small>
                  </button>
                </li>
                <li v-if="!clientesFiltrados.length && !ocupado" class="agm__vazio">
                  Nenhum cliente com OS em aberto bate com esta busca.
                </li>
              </ul>

              <template v-else>
                <p class="agm__dica">
                  <b>{{ clienteEscolhido.nome }}</b>
                  <button class="botao botao--fantasma" type="button"
                          @click="clienteEscolhido = null">trocar</button>
                </p>
                <ul class="agm__lista">
                  <li v-for="os in osDoCliente" :key="os.numero_os">
                    <button type="button" class="agm__item"
                            :class="{ 'agm__item--marcado': osMarcada(os),
                                      'agm__item--preso': jaAgendadas.includes(os.numero_os) }"
                            :disabled="jaAgendadas.includes(os.numero_os)"
                            @click="alternarOs(os)">
                      <span class="agm__item-linha">
                        <!-- 🔵 21/10: *"o tipo da OS pode ter mais destaque"*. O
                             tipo e o que o CLIENTE le no cabecalho da mensagem,
                             entao ganha o mesmo peso do numero da OS -- selo
                             com cor por tipo, e nao linha miuda cinza.
                             ⚠️ Sem nome, o selo fica neutro e DIZ que nao ha
                             nome, em vez de desaparecer. -->
                        <span class="agm__tipo" :class="seloDoTipo(os.tipo_nome)">
                          {{ os.tipo_nome || 'tipo sem nome no Harmonit' }}
                        </span>
                        <b>OS {{ os.numero_os }}</b>
                        <span class="agm__fraco">{{ placasDaOs(os) }}</span>
                      </span>
                      <small>
                        {{ os.sem_situacao ? 'sem situação' : os.status_str }}
                        <template v-if="jaAgendadas.includes(os.numero_os)">
                          · já agendada
                        </template>
                      </small>
                    </button>
                  </li>
                  <li v-if="!osDoCliente.length && !ocupado" class="agm__vazio">
                    Este cliente não tem OS em aberto no período.
                  </li>
                </ul>
              </template>

              <div class="agm__acoes">
                <button class="botao botao--contorno" type="button" @click="passo = 1">Voltar</button>
                <button class="botao botao--primario" type="button"
                        :disabled="!osEscolhidas.length"
                        @click="passo = 3; carregarEnderecoDaOs()">Continuar</button>
              </div>
            </div>

            <div v-else-if="passo === 3">
              <p class="agm__dica">
                <b>{{ clienteEscolhido?.nome }}</b> ·
                {{ osEscolhidas.length }} OS ·
                {{ quando ? `${dataBr(quando)} às ${horaBr(quando)}` : '' }} ·
                técnico {{ contatoNome || '—' }}
              </p>
              <!-- 🔵 Campos separados, com os nomes do Harmonit. -->
              <div class="agm__endereco">
                <label class="agm__campo agm__campo--cep">
                  <span>CEP</span>
                  <span class="agm__cep-linha">
                    <input v-model="campos.cep" class="campo__entrada"
                           :maxlength="LIMITES.cep" inputmode="numeric"
                           placeholder="19013180" @keyup.enter="buscarCep" />
                    <button class="botao botao--contorno" type="button"
                            :disabled="cepEstado === 'buscando'" @click="buscarCep">
                      {{ cepEstado === 'buscando' ? 'Buscando…' : 'Buscar' }}
                    </button>
                  </span>
                </label>
                <label class="agm__campo agm__campo--rua">
                  <span>Rua <small>{{ campos.logradouro.length }}/{{ LIMITES.logradouro }}</small></span>
                  <input v-model="campos.logradouro" class="campo__entrada"
                         :maxlength="LIMITES.logradouro" />
                </label>
                <label class="agm__campo agm__campo--num">
                  <span>Número</span>
                  <input v-model="campos.numero" class="campo__entrada"
                         :maxlength="LIMITES.numero" />
                </label>
                <label class="agm__campo">
                  <span>Bairro <small>{{ campos.bairro.length }}/{{ LIMITES.bairro }}</small></span>
                  <input v-model="campos.bairro" class="campo__entrada"
                         :maxlength="LIMITES.bairro" />
                </label>
                <label class="agm__campo">
                  <span>Cidade <small>{{ campos.cidade.length }}/{{ LIMITES.cidade }}</small></span>
                  <input v-model="campos.cidade" class="campo__entrada"
                         :maxlength="LIMITES.cidade" />
                </label>
                <label class="agm__campo agm__campo--uf">
                  <span>UF</span>
                  <input v-model="campos.uf" class="campo__entrada"
                         :maxlength="LIMITES.uf" />
                </label>
                <label class="agm__campo">
                  <span>Complemento <small>{{ campos.complemento.length }}/{{ LIMITES.complemento }}</small></span>
                  <input v-model="campos.complemento" class="campo__entrada"
                         :maxlength="LIMITES.complemento" />
                </label>
              </div>

              <!-- 🚨 Os tres estados da consulta de CEP, separados: "nao
                   existe" e "nao deu para perguntar" nao sao a mesma coisa. -->
              <p v-if="cepEstado === 'curto'" class="aviso aviso--atencao">
                O CEP tem 8 dígitos.
              </p>
              <p v-else-if="cepEstado === 'nao-existe'" class="aviso aviso--atencao">
                Este CEP não existe na base dos Correios. Confira, ou preencha os
                campos à mão.
              </p>
              <p v-else-if="cepEstado === 'caiu'" class="aviso aviso--erro">
                Não deu para consultar o CEP agora — isto <b>não</b> quer dizer que
                ele está errado. Preencha à mão, ou tente de novo.
              </p>

              <p v-if="enderecoDaOs && enderecoDaOs.tem_endereco === false"
                 class="aviso aviso--info">
                Esta OS <b>não tem endereço</b> no Harmonit. O que você preencher
                aqui vai gravado nela.
              </p>
              <p v-else-if="enderecoDaOs && enderecoDaOs.erro" class="aviso aviso--atencao">
                Não deu para ler o endereço desta OS ({{ enderecoDaOs.erro }}). Dá
                para agendar: o endereço daqui é que vale.
              </p>

              <p v-if="!temRua" class="aviso aviso--atencao">
                Sem a rua, o endereço <b>não</b> vai para a OS do Harmonit — o
                compromisso vale aqui, mas lá fica como está.
              </p>
              <p v-if="linhaDoEndereco" class="agm__dica">
                O cliente vai ler: <b>{{ linhaDoEndereco }}</b>
              </p>
              <p v-if="orcamentoEmitido" class="agm__dica">
                Orçamento nº {{ orcamentoEmitido.numero }} vai junto.
              </p>
              <div class="agm__acoes">
                <button class="botao botao--contorno" type="button" @click="passo = 2">Voltar</button>
                <button class="botao botao--primario" type="button"
                        :disabled="ocupado || !podeAgendar" @click="gravarAgendamento">
                  {{ ocupado ? 'Gravando…' : 'Agendar' }}
                </button>
              </div>
            </div>
          </template>
        </div>

        <!-- ------------------------------------------------- aba Confirmar -->
        <div v-else-if="aba === 'confirmar'" class="agm__corpo">
          <p v-if="!clienteHarmonitId" class="aviso aviso--info">
            Esta conversa não está ligada a um cliente com cadastro no Harmonit,
            então não há agendamento para confirmar aqui.
          </p>

          <template v-else-if="!mensagens.length">
            <p class="agm__dica">Marque o que o cliente confirmou:</p>
            <ul class="agm__lista">
              <li v-for="a in aguardando" :key="a.id">
                <button type="button" class="agm__item"
                        :class="{ 'agm__item--marcado': marcados.includes(a.id) }"
                        @click="alternarMarcado(a)">
                  <span>
                    {{ dataBr(a.inicio) }} às {{ horaBr(a.inicio) }} —
                    OS {{ (a.ordens || []).map((o) => o.numero_os).join(', ') }}
                  </span>
                  <small>{{ a.tecnico_nome || 'sem técnico' }}</small>
                </button>
              </li>
              <li v-if="!aguardando.length && !ocupado" class="agm__vazio">
                Nada esperando confirmação para este cliente.
              </li>
            </ul>

            <label class="agm__campo">
              <span>Quem acompanha o técnico</span>
              <input v-model="responsavel" class="campo__entrada"
                     placeholder="Nome de quem recebe o técnico" />
            </label>

            <div class="agm__acoes">
              <button class="botao botao--primario" type="button"
                      :disabled="ocupado || !marcados.length" @click="confirmar">
                {{ ocupado ? 'Confirmando…' : 'Confirmar e escrever os avisos' }}
              </button>
            </div>
          </template>

          <template v-else>
            <p class="aviso aviso--ok">
              Confirmado. Os avisos abaixo ficam <b>prontos para você revisar e
              enviar</b> — nada sai daqui sozinho.
            </p>
            <div v-for="(m, i) in mensagens" :key="i" class="agm__mensagem">
              <h3>Para o cliente</h3>
              <!-- 🔵 21/10: *"ao invés de editar na caixa de mensagem, pode
                   editar ali no modal mesmo"*. -->
              <textarea v-model="m.doCliente" class="campo__entrada agm__texto"
                        rows="8"></textarea>
              <div class="agm__acoes">
                <button class="botao botao--primario" type="button"
                        :disabled="m.enviando || m.enviado"
                        @click="enviarAoCliente(m)">
                  {{ m.enviado ? 'Enviado' : (m.enviando ? 'Enviando…' : 'Enviar ao cliente') }}
                </button>
                <button class="botao botao--contorno" type="button"
                        @click="usar(m.doCliente)">Escrever no compositor</button>
              </div>
              <p v-if="m.enviado" class="agm__dica">
                Foi para esta conversa. 🔵 O do técnico é opcional: clique ao
                lado só se quiser.
              </p>
              <p v-if="m.erroEnvio" class="aviso aviso--erro">{{ m.erroEnvio }}</p>

              <h3>Para o técnico</h3>
              <textarea v-model="m.doTecnico" class="campo__entrada agm__texto"
                        rows="9"></textarea>
              <div class="agm__acoes">
                <!-- 🚨 ABRE, NAO ENVIA: a conversa do tecnico e outra, e a rota
                     de envio exige estar nela. O texto vai no compositor. -->
                <button class="botao botao--contorno" type="button"
                        :disabled="!m.conversaDoTecnico"
                        @click="abrirNoTecnico(m)">Abrir na conversa do técnico</button>
                <span v-if="!m.conversaDoTecnico" class="agm__fraco">
                  este compromisso não guarda a conversa de origem
                </span>
              </div>
            </div>
          </template>
        </div>
      </template>
    </section>
  </div>
</template>

<style scoped>
.agm__fundo {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--e-3);
  background: rgba(15, 23, 42, .55);
}
.agm {
  display: flex;
  flex-direction: column;
  gap: var(--e-3);
  width: min(760px, 100%);
  max-height: 90vh;
  overflow-y: auto;
  padding: var(--e-4);
  border-radius: var(--r-lg);
  background: var(--superficie);
  color: var(--texto);
}
.agm__topo { display: flex; align-items: center; justify-content: space-between; }

/* O calendario sempre aberto (F3) */
.agm__quando { display: flex; gap: var(--e-3); flex-wrap: wrap; align-items: flex-start; }
.agm__cal { display: flex; flex-direction: column; gap: var(--e-2); }
.agm__cal-topo { display: flex; align-items: center; justify-content: space-between; gap: var(--e-2); }
.agm__cal-mes { text-transform: capitalize; }
.agm__cal-grade { display: grid; grid-template-columns: repeat(7, 34px); gap: 3px; }
.agm__cal-semana { text-align: center; font-size: var(--txt-xs); color: var(--texto-fraco); }
.agm__cal-vago { display: block; }
.agm__cal-dia {
  height: 30px;
  border: var(--borda-fina) solid transparent;
  border-radius: var(--r-sm);
  background: var(--superficie-2);
  color: inherit;
  cursor: pointer;
}
.agm__cal-dia--hoje { border-color: var(--acento); }
.agm__cal-dia--ativo { background: var(--acento); color: #fff; }
.agm__cal-dia--passado { color: var(--texto-fraco); }
.agm__cal-nota { margin: 0; max-width: 30ch; }
.agm__horas { display: flex; flex-direction: column; gap: var(--e-1); }
.agm__horas-rotulo { font-size: var(--txt-xs); text-transform: uppercase; color: var(--texto-fraco); }
.agm__horas-grade {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 3px;
  max-height: 232px;
  overflow-y: auto;
}
.agm__hora {
  padding: 4px 8px;
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-sm);
  background: var(--superficie-2);
  color: inherit;
  font-size: var(--txt-sm);
  cursor: pointer;
}
.agm__hora--ativo { background: var(--acento); color: #fff; border-color: var(--acento); }

/* O selo do tipo da OS (F2) */
.agm__item-linha { display: flex; align-items: center; gap: var(--e-2); flex-wrap: wrap; }
.agm__fraco { color: var(--texto-fraco); }
.agm__tipo {
  padding: 1px 8px;
  border-radius: 999px;
  font-size: var(--txt-xs);
  font-weight: var(--peso-forte);
  text-transform: uppercase;
  letter-spacing: .02em;
  color: #fff;
  white-space: nowrap;
}
.agm__tipo--contrato { background: #2563eb; }
.agm__tipo--solicitacao { background: #7c3aed; }
.agm__tipo--ordem { background: #0f766e; }
.agm__tipo--interna { background: #b45309; }
.agm__tipo--teste { background: #be123c; }
/* ⚠️ Sem nome: cinza e com borda, para nao parecer um tipo a mais. */
.agm__tipo--sem-nome {
  background: transparent;
  border: var(--borda-fina) solid var(--borda);
  color: var(--texto-fraco);
  text-transform: none;
}
.agm__titulo { margin: 0; font-size: var(--txt-lg); }
.agm__abas { display: flex; gap: var(--e-2); border-bottom: var(--borda-fina) solid var(--borda); }
.agm__aba {
  padding: var(--e-2) var(--e-3);
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--texto-fraco);
  font-size: var(--txt-sm);
  font-weight: var(--peso-forte);
  cursor: pointer;
}
.agm__aba--ativa { color: var(--acento); border-bottom-color: var(--acento); }
.agm__corpo { display: flex; flex-direction: column; gap: var(--e-3); }
.agm__campo { display: flex; flex-direction: column; gap: var(--e-1); font-size: var(--txt-sm); }
/* 16px: abaixo disso o iOS dá zoom ao focar (padrão dos quatro painéis). */
.agm__campo .campo__entrada { font-size: 16px; }
.agm__num { width: 110px; font-size: 16px; }
.agm__dica { margin: 0; color: var(--texto-fraco); font-size: var(--txt-sm); }
.agm__linha { display: flex; align-items: center; justify-content: space-between; gap: var(--e-3); }
.agm__total { font-size: var(--txt-md); }
.agm__acoes { display: flex; gap: var(--e-2); justify-content: flex-end; flex-wrap: wrap; }
.agm__passos { display: flex; gap: var(--e-3); margin: 0; padding: 0; list-style: none; font-size: var(--txt-sm); color: var(--texto-fraco); }
.agm__passo--ativo { color: var(--acento); font-weight: var(--peso-forte); }
.agm__lista { list-style: none; margin: 0; padding: 0; max-height: 280px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; }
.agm__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--e-2);
  width: 100%;
  padding: var(--e-2) var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-sm);
  background: var(--superficie-2);
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.agm__item--marcado { border-color: var(--acento); background: var(--acento-suave, var(--superficie-3)); }
.agm__item--preso { opacity: .55; cursor: not-allowed; }
.agm__item small { color: var(--texto-fraco); }
.agm__vazio { padding: var(--e-3); color: var(--texto-fraco); font-size: var(--txt-sm); }
.agm__endereco { display: grid; grid-template-columns: repeat(2, minmax(160px, 1fr)); gap: var(--e-2); }
.agm__endereco .agm__campo span small { color: var(--texto-fraco); font-weight: 400; }
.agm__campo--rua { grid-column: span 2; }
.agm__cep-linha { display: flex; gap: var(--e-1); }
.agm__texto { width: 100%; font-family: inherit; font-size: var(--txt-sm); }
.agm__mensagem { display: flex; flex-direction: column; gap: var(--e-2); }
.agm__mensagem h3 { margin: 0; font-size: var(--txt-sm); }
.agm__mensagem pre {
  margin: 0;
  padding: var(--e-3);
  border-radius: var(--r-sm);
  background: var(--superficie-2);
  font-family: inherit;
  font-size: var(--txt-sm);
  white-space: pre-wrap;
}
</style>
