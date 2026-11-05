<script setup>
/* ============================================================================
   PNL_1.1 — Painel da Operação (opção A: kanban pelas situações da OS)
   ----------------------------------------------------------------------------
   🔵 Escolha dele em 22/10, entre três mockups lado a lado: *"vamos de A
   somente para a Operação por enquanto, mas bem documentado para as demais
   futuramente"*. A opção A é a única em que **mover o card É a ação** — e foi
   esse o motivo que ele deu para o painel existir: *"hoje ainda não usamos a
   situação da OS, por isso o painel e consulta para atualizar a situação no
   painel"*.

   🚨 MOVER AINDA NÃO EXISTE. A rota que escreve `situacaoId` no Harmonit é da
   volta seguinte; enquanto não existir, não há `draggable` nenhum, porque
   oferecer o gesto e não gravar é pior que não ter o gesto. ⚠️ Em 29/10 ele
   mandou TIRAR a frase que explicava isso na tela (*"os comentários tbm devem
   sumir dali"*) -- o comportamento não mudou, só o texto saiu.

   🚨 SÃO 17 COLUNAS, E A ORDEM É A DELE (29/10): *"as situações já estão na
   Ordem"*. A ordem é o fluxo da operação, não alfabética nem por id, e ela
   vive numa tupla só, em `movizap/paineis.py`.

   🚨 COLUNA VAZIA NASCE COLAPSADA, com o contador à vista — são 17 colunas, e
   nenhuma tela mostra 17 sem rolar. É o que o kanban do FPSL já faz com a
   coluna "Pago". ⚠️ Nenhuma é fixa agora: as duas que nunca colapsavam ("Sem
   OS" e "Sem situação") SAÍRAM em 29/10 -- *"qualquer aba fora dessas não deve
   estar no painel"*.

   🚨 A COR NUNCA É O ÚNICO PORTADOR: o estado da solicitação vem escrito na
   etiqueta, e a situação vem escrita no card. É a regra do quadro de demandas
   do FPSL -- *"o estado continua legível pela etiqueta"*.
   ============================================================================ */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api, ErroDeApi } from '../api/cliente.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'
import BalaoDeRecado from '../componentes/BalaoDeRecado.vue'

const router = useRouter()
const quadro = ref(null)
const carregando = ref(true)
const erro = ref('')
const abertas = ref({})


/* 🔵 D9: o interruptor nasce LIGADO -- ver o comentário no `template`. */
const soAbertas = ref(true)

/* Só o dia, sem hora: a data matriz é um corte de calendário. */
/* Só o dia e o mês, para caber no card. ⚠️ O ano entra quando for outro:
   "29/10" num card de 2025 seria ambíguo. */
function dataCurta(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const mesmoAno = d.getFullYear() === new Date().getFullYear()
  return d.toLocaleDateString('pt-BR', mesmoAno
    ? { day: '2-digit', month: '2-digit' }
    : { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function dia(iso) {
  if (!iso) return '—'
  const [a, m, d] = String(iso).split('-')
  return (d && m && a) ? `${d}/${m}/${a}` : iso
}

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    const q = new URLSearchParams({
      so_abertas: soAbertas.value ? '1' : '0',
      ordem: ordem.value,
    })
    if (busca.value.trim()) q.set('busca', busca.value.trim())
    quadro.value = await api.get(`/api/paineis/operacao?${q}`)
    for (const coluna of quadro.value.colunas) {
      /* 🚨 TODA COLUNA NASCE ABERTA, e isto consertou o arrasto -- foi ELE
         quem achou: *"não é necessário ter card para que elas existam... Sem
         as colunas, arrastar o card do 17054 não vai para lugar algum"*.

         A coluna fechada **não tem corpo** (ver o `v-if` do `coluna__corpo`),
         então a única área dela era a tira do título, ~44 px. Com mover no ar,
         uma coluna sem corpo não é um detalhe de espaço: é **um destino que
         não existe**.

         ⚠️ Antes do Bloco D isto era aceitável -- o painel só lia, e colapsar
         a coluna vazia fazia as 17 caberem na tela. Quando mover entrou, a
         mesma linha virou defeito.

         ⚠️ E colapsar CONTINUA existindo, como escolha de quem usa: é o clique
         no título. O que saiu foi o automático por estar vazia.
         🚨 `!== false` para a escolha dela sobreviver ao `carregar()` -- senão
         toda atualização reabriria o que a pessoa fechou. */
      if (abertas.value[coluna.chave] === undefined) {
        abertas.value[coluna.chave] = true
      }
    }
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui ler o painel.'
  } finally {
    carregando.value = false
  }
}

function alternar(coluna) {
  abertas.value[coluna.chave] = !abertas.value[coluna.chave]
}

/* ============================================================================
   O CARD ABERTO — 🔵 *"ao clicar no card nao esta abrindo o proposto no mockup,
   esta direcionando para outra aba"*.
   ----------------------------------------------------------------------------
   🚨 ERA DEFEITO: o clique empurrava `/solicitacoes?solicitacao=<id>`, e desde
   a D8 a maioria dos cards vem do ERP e **nao tem solicitacao** -- `card.id` e
   nulo. Ele clicava e caia noutra tela, com uma consulta vazia.

   ⚠️ O QUE ESTE MODAL MOSTRA E SO O QUE JA EXISTE: a OS que o quadro ja trouxe
   e o log de passagens (`GET .../passagens`, do Bloco D). Os quatro resumos do
   mockup -- descricao, solucao tecnica, dados do chamado e agendamento -- sao
   o **Bloco E** e dependem de ler a OS ao vivo no ERP; o modal DIZ isso em vez
   de mostrar caixa vazia.
   ============================================================================ */
const cardAberto = ref(null)
const passagens = ref([])
const lendoPassagens = ref(false)

/* 🔵 OS QUATRO TEMAS DO MOCKUP — Descrição da OS, Solução técnica, Dados do
   chamado e Agendamento. Ele perguntou *"onde estão os temas do card, após
   clicar?"* e eu os havia deixado para depois, com um texto no modal dizendo
   que faltavam. Dizer o que falta é melhor que caixa vazia -- e não substitui
   o recurso.

   🚨 UMA CHAMADA POR CARD ABERTO: `descricao` e `solucaoTecnica` NÃO estão no
   cache, vêm ao vivo do ERP. Na montagem do quadro seriam 11 chamadas. */
const ficha = ref(null)
const lendoFicha = ref(false)
const erroDaFicha = ref('')
const temaAberto = ref('descricao')

async function abrirCard(card) {
  /* 🔵 De onde o foco veio -- para ele voltar exatamente ali ao fechar. */
  guardarFoco()
  cardAberto.value = card
  focarCaixa(caixaDoCard)
  passagens.value = []
  ficha.value = null
  erroDaFicha.value = ''
  temaAberto.value = 'descricao'
  recado.value = ''
  erroDoRecado.value = ''
  if (!card.numero_ordem) return

  /* O checklist da etapa em que o card ESTÁ. ⚠️ Sem `await`: ele é do nosso
     banco e não pode fazer o card esperar as duas leituras que vão ao ERP. */
  carregarChecklist(card)

  lendoPassagens.value = true
  lendoFicha.value = true
  /* ⚠️ As duas leituras em paralelo: o log é nosso (rápido) e a ficha vai ao
     ERP. Em série, o log esperaria o Harmonit por nada. */
  const log = api.get(
    `/api/paineis/operacao/passagens?numero_os=${card.numero_ordem}`)
    .then((r) => { passagens.value = r.passagens || [] })
    /* ⚠️ Falha ao ler o log NÃO fecha o modal: o resto do card continua
       valendo, e a ausência é dita no próprio modal. */
    .catch(() => { passagens.value = [] })
    .finally(() => { lendoPassagens.value = false })

  const f = api.get(
    `/api/paineis/operacao/ficha?numero_os=${card.numero_ordem}`)
    .then((r) => { ficha.value = r })
    .catch((e) => {
      /* 🚨 FICHA VAZIA SERIA PIOR QUE ERRO: ela é indistinguível de uma OS sem
         dados, e o operador concluiria que não há o que ver. */
      erroDaFicha.value = e instanceof ErroDeApi
        ? e.message : 'Não deu para ler a OS no Harmonit agora.'
    })
    .finally(() => { lendoFicha.value = false })

  await Promise.all([log, f])
}

/* ============================================================================
   BLOCO F, FASE 1 — prioridade (no ERP) e observacao (nossa)
   ----------------------------------------------------------------------------
   🚨 MUDAR A PRIORIDADE ESCREVE A OS INTEIRA no Harmonit, e o plano dele já
   avisava. Por isso a troca pede confirmação do servidor e o card recarrega.

   🚨 A OBSERVAÇÃO NÃO VAI PARA O ERP: 🔵 *"com autor e hora, no MoviZap. Não
   vai para a `solucaoTecnica`"* — aquele campo é da operação técnica, o cliente
   pode lê-lo num relatório, e escrever nele gravaria a OS inteira a cada
   recado. ⚠️ E não se apaga nem se edita: reescrever recado é reescrever a
   história que a operação leu.
   ============================================================================ */
const recado = ref('')
const salvando = ref(false)
const erroDoRecado = ref('')

/* 🚨 A `salvarObservacao` VIVIA AQUI e saiu em 04/11, quando os recados
   ganharam modal próprio (área D). Quem salva agora é a
   `salvarRecadoComAnexo`, que faz o mesmo e ainda sobe o anexo. Deixá-la sem
   chamador seria código morto que parece vivo — a próxima pessoa mexeria nela
   sem efeito nenhum.
   ⚠️ As três regras dela continuam valendo, e estão lá: a lista volta DO
   SERVIDOR (autor e hora são dele), o recado não vai para a OS, e o contador
   do card fechado é recarregado depois. */

async function mudarPrioridade(novaId) {
  const c = cardAberto.value
  if (!c?.numero_ordem) return
  erroDoRecado.value = ''
  salvando.value = true
  try {
    const r = await api.post('/api/paineis/operacao/prioridade', {
      numero_os: c.numero_ordem,
      prioridade_id: novaId,
      /* 🚨 A trava de concorrência, como no mover. */
      prioridade_esperada: ficha.value?.prioridade ?? null,
    })
    if (!r.ok) {
      erroDoRecado.value = r.motivo || 'Não consegui mudar a prioridade.'
    } else if (ficha.value) {
      ficha.value.prioridade = r.para
      /* 🔵 A troca entra como observação do sistema, com autor. */
      ficha.value.observacoes = await api
        .get(`/api/paineis/operacao/ficha?numero_os=${c.numero_ordem}`)
        .then((f) => f.observacoes || [])
        .catch(() => ficha.value.observacoes)
    }
    await carregar()
  } catch (e) {
    erroDoRecado.value = e instanceof ErroDeApi
      ? e.message : 'Não consegui mudar a prioridade.'
  } finally {
    salvando.value = false
  }
}

/* 🔵 O Agendamento *"nasce desabilitado e acende em Serviço Agendado"*. */
const SITUACAO_AGENDADO = 1316

const temas = computed(() => {
  const f = ficha.value
  const c = cardAberto.value
  if (!c) return []
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
      /* 🔵 Acende em "Serviço Agendado", e DIZ por que está apagado. */
      ligado: c.situacao_id === SITUACAO_AGENDADO || !!f?.tem_agendamento,
      resumo: f
        ? (f.tem_agendamento
            ? `${f.agendamentos.length} compromisso(s)`
            : 'só a partir de "Serviço Agendado"')
        : '…',
      agendamentos: f?.agendamentos || [],
      vazio: !!f && !f.tem_agendamento,
    },
  ]
})

function fecharCard() {
  cardAberto.value = null
  passagens.value = []
  devolverFoco()
}

function nomeDaSituacao(sid) {
  const c = (quadro.value?.colunas || []).find((x) => x.situacao_id === sid)
  /* 🚨 Situacao fora das 17 mostra o NUMERO CRU, nunca um rotulo inventado --
     e a regua do grid do FPSL. */
  /* ⚠️ "situação nunca lida" e não só "nunca lida": a pílula do card aparece
     sozinha, e fora de contexto "nunca lida" não diz nunca lida O QUE. A trava
     pegou isto. */
  return c ? c.titulo
           : (sid === null ? 'situação nunca lida' : `situação ${sid}`)
}

function verNaFRM(card) {
  /* A ficha completa do chamado é da `FRM_1.1`. ⚠️ Só existe quando o card
     veio de formulário -- o botão nem aparece nos outros. */
  router.push({ path: '/solicitacoes', query: { solicitacao: card.id } })
}

/* 🚨 O QUE NÃO TEM COLUNA, DITO EM UMA LINHA -- e só quando existe.
   Solicitação sem OS (a escrita no Harmonit falhou) ou com situação fora das
   17 não cabe em coluna nenhuma, e sumir da tela é o defeito que esta casa
   chama de `M12`. Com zero, esta linha não aparece: hoje o painel fica limpo,
   que é o que ele pediu em 29/10. */
const fora = computed(() => {
  const f = quadro.value?.fora_do_quadro
  if (!f || (!f.sem_os && !f.situacao_fora && !f.os_falhou
             && !f.sem_tentativa)) return ''
  const partes = []
  /* 🚨 "SEM OS" SÃO TRÊS CASOS, E A TELA CHAMAVA TODOS DE FALHA -- achado por
     ele em 29/10, na tela, minutos depois de o painel subir: a solicitação
     544 nunca teve escrita tentada (é de 13:06, e o Bloco A subiu às 15:30),
     e a frase a acusava de erro do Harmonit.

     ⚠️ A ORDEM É DELIBERADA: o caso benigno primeiro, o que pede ação depois,
     e a sobra no fim. E a sobra EXISTE de propósito -- uma linha preparada e
     nunca tentada não cai em nenhuma das duas contas, e deixá-la desaparecer
     entre as frases seria o mesmo defeito outra vez, mais fundo. */
  if (f.sem_tentativa) {
    /* 🔵 Ele, 29/10, lendo "1 chamado sem OS": *"pq deu erro? o que falta?"*.
       NADA havia falhado -- era o chamado dele, enviado antes de a abertura
       automática existir. A frase contava em vez de identificar, e contagem
       sem número não responde "qual?". */
    /* 🚨 O PLURAL NAO PODE DEPENDER DA LISTA DE NUMEROS, e foi o defeito que
       a trava pegou: a frase dizia "1 chamados" quando o numero do chamado nao
       vinha (acontece acima de 5 itens, ou se o servidor nao mandar a lista).
       Um e singular com lista ou sem. */
    const quais = (f.sem_tentativa_quais || []).join(', ')
    const um = f.sem_tentativa === 1
    partes.push(
      (um ? (quais ? `o chamado ${quais} ainda não tem OS`
                   : '1 chamado ainda sem OS')
          : `${f.sem_tentativa} chamados ainda sem OS`
            + (quais ? ` (${quais})` : ''))
      + (um ? ' (foi enviado' : ', enviados')
      + ' antes de a abertura automática entrar)'.slice(um ? 0 : 1))
  }
  if (f.os_falhou) {
    partes.push(`${f.os_falhou} ${f.os_falhou === 1 ? 'OS não abriu' : 'OS não abriram'}`
      + ` em ${f.os_falhou_chamados} ${f.os_falhou_chamados === 1 ? 'chamado' : 'chamados'}`
      + (f.os_falhou_em ? ` (última tentativa ${quando(f.os_falhou_em)})` : ''))
  }
  const explicados = (f.sem_tentativa || 0) + (f.os_falhou_chamados || 0)
  if (f.sem_os > explicados) {
    partes.push(`${f.sem_os - explicados} sem OS e sem motivo registrado`)
  }
  if (f.situacao_fora) {
    /* 🚨 A SITUAÇÃO VEM DO ERP, e dizer isso é o ponto: a OS está em `0` no
       Harmonit, e `0` não é uma das 17. Não é defeito nosso, e a frase antiga
       ("1 com situação fora das 17") fazia parecer que era. */
    const quais = f.fora_quais || []
    partes.push(quais.length
      ? quais.map((o) => `a OS ${o.numero_os} está em situação `
          + `${o.situacao_id} no Harmonit, que não é uma das 17`).join(' · ')
      : `${f.situacao_fora} com situação fora das 17`
        + (f.situacoes.length ? ` (${f.situacoes.join(', ')})` : ''))
  }
  return partes.join(' · ')
})

function quando(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

/* ============================================================================
   MOVER O CARD — Bloco D. 🔵 Dele: *"O card pode ser por arrastar"*.
   ----------------------------------------------------------------------------
   🚨 A ORDEM É LIVRE: *"que tal de caminho proibido é esse??"*. Não há mapa de
   transições aqui, nem no servidor, nem no Harmonit.

   🚨 A TRAVA DE CONCORRÊNCIA VAI NO PEDIDO: `situacao_esperada` é a situação
   que ESTE card carregava. Se o ERP já estiver em outra, o servidor recusa e a
   tela recarrega -- em vez de escrever por cima do que outra pessoa fez.

   ⚠️ E O CARD VOLTA SOZINHO quando a escrita falha: o movimento na tela é
   otimista (o card pula de coluna na hora), e o `catch` recarrega o quadro.
   Card que fica na coluna nova com a OS na antiga é a tela mentindo.
   ============================================================================ */
/* ---- O checklist da etapa (04/11) ---------------------------------------
   🔵 *"são itens que vão ficar em um botão dentro do card, como mapa para o
   operador saber o que fazer"*, com **modelo fixo + o operador pode
   acrescentar**.

   🚨 NADA DAQUI VAI PARA A OS. Ao sair da etapa, o servidor transforma o
   checklist em OBSERVAÇÃO do card -- decisão dele, porque gravar na
   `solucaoTecnica` exigiria reescrever a OS inteira no Harmonit. */
/* ---- O aviso ao ENTRAR na etapa (Área B, 04/11) -------------------------
   🔵 Palavras dele: *"ao mover 1 ticket para etapa, ele da o aviso e clica
   'Ok', se mover outro card, não há necessidade de avisar por 10min"*.

   Então o aviso é por ETAPA, não por card: confirmado uma vez, aquela etapa
   fica em silêncio por 10 minutos.

   🚨 O AVISO É DEPOIS DO MOVER, NUNCA ANTES. Ele não pode atrasar nem
   bloquear a escrita no ERP -- o arrasto já grava a situação, e um diálogo no
   meio faria o card parecer travado.

   ⚠️ O silêncio vive no `localStorage`, como os grupos do menu. Ele pode vir
   vazio (janela anônima, dados limpos) ou estourar: tudo em `try/catch`, e sem
   ele o aviso só aparece de novo -- nunca quebra o mover. */
/* ---- Os recados em MODAL (área D, 04/11) --------------------------------
   🔵 *"Card OBS anexos, texto, format conve -- exibir em modal"*. A observação
   era uma seção espremida dentro do card aberto; agora tem modal próprio, em
   bolhas, e aceita arquivo. */
const recadosAbertos = ref(false)
const anexoEscolhido = ref(null)
const enviandoRecado = ref(false)

function abrirRecados() {
  guardarFoco()
  recadosAbertos.value = true
  focarCaixa(caixaDosRecados)
}
function fecharRecados() {
  recadosAbertos.value = false
  anexoEscolhido.value = null
  devolverFoco()
}

function escolherAnexo(evento) {
  anexoEscolhido.value = evento.target.files?.[0] || null
}

async function subirAnexo(observacaoId, arquivo) {
  /* ⚠️ `fetch` cru, não `api.post`: arquivo vai por `FormData`, e o navegador
     precisa montar o `Content-Type` com o boundary. Definir o cabeçalho aqui
     quebraria o upload em silêncio — a Caixa já documenta isso. */
  const forma = new FormData()
  forma.append('arquivo', arquivo)
  const r = await fetch(
    `/api/paineis/operacao/observacao/${observacaoId}/anexo`,
    { method: 'POST',
      headers: { Authorization: `Bearer ${localStorage.getItem('movizap.token')}` },
      body: forma })
  const texto = await r.text()
  let corpo = null
  try { corpo = JSON.parse(texto) } catch { corpo = null }
  if (!r.ok) throw new Error((corpo && corpo.detail) || `Falha no anexo (${r.status}).`)
  return corpo
}

async function salvarRecadoComAnexo() {
  if (!cardAberto.value) return
  const texto = recado.value.trim()
  const arquivo = anexoEscolhido.value
  if (!texto && !arquivo) return
  enviandoRecado.value = true
  erroDoRecado.value = ''
  try {
    /* ⚠️ O anexo pende de um recado, então o recado vem primeiro. Sem texto,
       um é inventado com o nome do arquivo: anexo solto não se explica sozinho
       daqui a três meses. */
    const r = await api.post('/api/paineis/operacao/observacao', {
      numero_os: cardAberto.value.numero_ordem,
      texto: texto || `(anexo) ${arquivo.name}`,
    })
    const nova = (r.observacoes || [])[0]
    if (arquivo && nova) await subirAnexo(nova.id, arquivo)
    recado.value = ''
    anexoEscolhido.value = null
    /* 🚨 Relê do servidor — a lista com anexos vem da ficha, nunca remendada
       aqui. */
    await abrirCard(cardAberto.value)
    await carregar()
  } catch (e) {
    erroDoRecado.value = e?.message || 'Não consegui salvar o recado.'
  } finally {
    enviandoRecado.value = false
  }
}

const SILENCIO_MS = 10 * 60 * 1000
const avisoDaEtapa = ref(null)

function chaveDoAviso(situacaoId) {
  return `painel_aviso_etapa_${situacaoId}`
}

function avisoEstaSilenciado(situacaoId) {
  try {
    const quando = Number(localStorage.getItem(chaveDoAviso(situacaoId)) || 0)
    return Number.isFinite(quando) && (Date.now() - quando) < SILENCIO_MS
  } catch {
    return false      // sem localStorage, avisa — é o lado seguro
  }
}

function talvezAvisarDaEtapa(situacaoId) {
  const coluna = (quadro.value?.colunas || []).find(
    (c) => c.situacao_id === situacaoId)
  /* Só avisa onde HÁ checklist: `tem_checklist` vem do servidor por card, e
     aqui basta um card da coluna para saber que a etapa tem lista. */
  const temLista = (coluna?.cards || []).some((c) => c.tem_checklist)
  if (!temLista || avisoEstaSilenciado(situacaoId)) return
  guardarFoco()
  avisoDaEtapa.value = { situacao_id: situacaoId, titulo: coluna?.titulo || '' }
  focarCaixa(caixaDoAviso)
}

function fecharAvisoDaEtapa() {
  const id = avisoDaEtapa.value?.situacao_id
  avisoDaEtapa.value = null
  devolverFoco()
  if (!id) return
  try {
    localStorage.setItem(chaveDoAviso(id), String(Date.now()))
  } catch { /* sem localStorage o aviso volta na próxima — e tudo bem */ }
}

const checklist = ref([])
const carregandoCheck = ref(false)
const erroDoCheck = ref('')
const itemNovo = ref('')

const feitosDoCheck = computed(
  () => checklist.value.filter((i) => i.feito).length)

async function carregarChecklist(card) {
  checklist.value = []
  erroDoCheck.value = ''
  if (!card?.numero_ordem || !card?.situacao_id) return
  carregandoCheck.value = true
  try {
    const r = await api.get('/api/paineis/operacao/checklist'
      + `?numero_os=${card.numero_ordem}&situacao_id=${card.situacao_id}`)
    checklist.value = r.itens || []
  } catch (e) {
    erroDoCheck.value = e?.message || 'Não deu para ler o checklist.'
  } finally {
    carregandoCheck.value = false
  }
}

async function marcarItem(item) {
  erroDoCheck.value = ''
  try {
    /* ⚠️ A lista vem DO SERVIDOR depois de marcar -- nunca se remenda a tela
       com o que ela achava que ia acontecer. É a régua da observação. */
    const r = await api.put(`/api/paineis/operacao/checklist/item/${item.id}`,
                            { feito: !item.feito })
    checklist.value = r.itens || []
    await carregar()          // o selo do card fechado muda junto
  } catch (e) {
    erroDoCheck.value = e?.message || 'Não consegui marcar.'
  }
}

async function acrescentarItem() {
  const texto = itemNovo.value.trim()
  if (!texto || !cardAberto.value) return
  erroDoCheck.value = ''
  try {
    const r = await api.post('/api/paineis/operacao/checklist/item', {
      numero_os: cardAberto.value.numero_ordem,
      situacao_id: cardAberto.value.situacao_id,
      texto,
    })
    checklist.value = r.itens || []
    itemNovo.value = ''
    await carregar()
  } catch (e) {
    erroDoCheck.value = e?.message || 'Não consegui acrescentar.'
  }
}

async function removerItem(item) {
  erroDoCheck.value = ''
  try {
    const r = await api.del(`/api/paineis/operacao/checklist/item/${item.id}`)
    checklist.value = r.itens || []
    await carregar()
  } catch (e) {
    erroDoCheck.value = e?.message || 'Não consegui remover.'
  }
}

const arrastando = ref(null)
const movendo = ref(null)
const erroDeMover = ref('')

/* 🚨 A MARCA DE TEMPO QUE SEPARA CLIQUE DE ARRASTO, e era A causa de o
   arrasto "não funcionar": o `.card__abrir` tem `@click`, e todo arrasto
   começa curto -- o navegador entrega o início como CLIQUE. O modal abria no
   meio do gesto, cobria a tela, e o arrasto morria. Quem arrastava via o card
   abrir e concluía que arrastar não funciona.

   ⚠️ Nenhum teste meu podia pegar: `trigger('dragstart')` e `trigger('click')`
   são eventos separados e sintéticos; a competição entre os dois só existe no
   navegador de verdade. */
let arrastouAgora = 0

const colunaAlvo = ref(null)

function comecarArrasto(card, evento) {
  if (!quadro.value?.pode_mover) return
  arrastando.value = card
  arrastouAgora = Date.now()
  /* ⚠️ `move` e não `copy`: o cursor tem de dizer que isto MOVE. */
  if (evento.dataTransfer) {
    evento.dataTransfer.effectAllowed = 'move'
    /* Alguns navegadores exigem algum dado para iniciar o arrasto. */
    evento.dataTransfer.setData('text/plain', String(card.numero_ordem || ''))
  }
}

function terminarArrasto() {
  arrastando.value = null
  colunaAlvo.value = null
  /* ⚠️ A marca sobrevive ao `dragend` por um instante, porque o clique que o
     navegador gera chega DEPOIS. */
  arrastouAgora = Date.now()
}

/* O clique desiste se um arrasto acabou de acontecer. */
function cliqueNoCard(card) {
  if (Date.now() - arrastouAgora < 400) return
  abrirCard(card)
}

/* 🚨 O RETORNO VISUAL: a coluna acende quando o card passa por cima. Sem isto
   não há como saber se o alvo aceita o solto -- e era justamente a informação
   que faltava para dizer ONDE o gesto quebrava. */
function sobreAColuna(coluna) {
  if (!arrastando.value) return
  colunaAlvo.value = coluna.chave
}

function saiuDaColuna(coluna) {
  if (colunaAlvo.value === coluna.chave) colunaAlvo.value = null
}

async function soltarNaColuna(coluna) {
  const card = arrastando.value
  arrastando.value = null
  colunaAlvo.value = null
  /* ⚠️ Marca o arrasto também no solto: o clique sintético que alguns
     navegadores geram depois do `drop` abriria o card por cima. */
  arrastouAgora = Date.now()
  if (!card || !quadro.value?.pode_mover) return
  /* Soltar na própria coluna não é movimento. */
  if (card.situacao_id === coluna.situacao_id) return
  await mover(card, coluna.situacao_id)
}

async function moverDoModal(paraSituacao) {
  const card = cardAberto.value
  if (!card) return
  await mover(card, paraSituacao)
  /* 🚨 FECHA O MODAL depois de mover: o `carregar()` reconstroi os cards, e o
     `cardAberto` ficaria apontando para um retrato velho -- com a situacao
     antiga escrita na tela. */
  fecharCard()
}

async function mover(card, paraSituacao) {
  erroDeMover.value = ''
  movendo.value = card.numero_ordem
  try {
    const r = await api.post('/api/paineis/operacao/mover', {
      numero_os: card.numero_ordem,
      para_situacao: paraSituacao,
      /* 🚨 A trava de concorrência -- ver o comentário do bloco. */
      situacao_esperada: card.situacao_id,
    })
    if (!r.ok) {
      erroDeMover.value = r.motivo || 'Não consegui mover este card.'
    }
  } catch (e) {
    erroDeMover.value = e instanceof ErroDeApi
      ? e.message : 'Não consegui mover este card.'
  } finally {
    movendo.value = null
    /* Área B: o aviso vem DEPOIS, e só quando a etapa tem checklist. */
    talvezAvisarDaEtapa(paraSituacao)
    /* 🚨 RECARREGA SEMPRE, deu certo ou não: a verdade é o que o ERP
       confirmou, nunca o que a tela achou que ia acontecer. */
    await carregar()
  }
}

/* ============================================================================
   BLOCO C — OS DOIS TEMPOS
   ----------------------------------------------------------------------------
   🔵 *"o card mostra dois tempos: nesta etapa e total da OS"*.

   🚨 O HARMONIT NÃO GUARDA O TEMPO POR ETAPA: a linha do tempo registra só o
   `status`, nunca a situação. Então **o total** sai da data de criação (que é a
   `dataPrevisao`, medido em 12 de 12 OS) e **o tempo nesta etapa** sai da
   última passagem da nossa `os_passagem`, que começou em 29/10.

   ⚠️ SEM PASSAGEM, O CARD DIZ "não medido" — a OS pode estar na etapa desde
   setembro e ninguém sabe. Mostrar "0h" seria afirmar o que ninguém mediu.

   ⚠️ E NÃO HÁ COR POR TEMPO: o mockup mostra laranja "depois do limite", e o
   limite **nunca foi dito**. Escolher um número aqui seria regra imaginária.
   ============================================================================ */
function duracao(iso) {
  if (!iso) return null
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return null
  let seg = Math.max(0, Math.floor((Date.now() - t) / 1000))
  const d = Math.floor(seg / 86400); seg -= d * 86400
  const h = Math.floor(seg / 3600); seg -= h * 3600
  const m = Math.floor(seg / 60)
  if (d) return `${d}d ${h}h`
  if (h) return `${h}h ${m}min`
  return `${m}min`
}

/* ============================================================================
   O FILTRO E A ORDEM — 🔵 *"filtros para os cards, por cliente, OS, placa //
   ordenadores tbm"*.
   ----------------------------------------------------------------------------
   🚨 QUEM FILTRA É O SERVIDOR, e a razão é medida: o teto por coluna é 50 e o
   do quadro é 600. Filtrar no navegador esconderia o que o teto já cortou, e a
   pessoa procuraria uma OS que o servidor nem mandou.

   ⚠️ UMA CAIXA SÓ para os QUATRO campos (o termo entrou em 05/11, área E):
   quem procura tem um número ou um nome na mão e não quer decidir em qual
   caixa ele vai. A tela diz ONDE casou.
   ============================================================================ */
const busca = ref('')
/* 🔵 O PADRAO, por decisao dele: *"o ordenador padrão deve ser por 'Prazo de
   entrega'"*. ⚠️ A ordem desta lista e a ordem do seletor, e o primeiro e o
   padrao -- nao e alfabetica. */
const ordem = ref('prazo')
const ROTULO_ORDEM = {
  prazo: 'prazo de entrega (mais próximo)',
  os_desc: 'OS, da mais nova',
  os_asc: 'OS, da mais antiga',
  parado: 'parado há mais tempo nesta etapa',
  cliente: 'cliente (A-Z)',
}

let relogioDaBusca = null
function buscarComCalma() {
  /* ⚠️ Espera a pessoa parar de digitar: cada tecla seria uma ida ao servidor
     e uma leitura do ERP. */
  clearTimeout(relogioDaBusca)
  relogioDaBusca = setTimeout(carregar, 350)
}

/* 🔵 AS 6 CORES DO CATAVENTO, como código de etapa — do mockup que ele
   aprovou. Ciclam pelas 17 colunas, na ordem do fluxo.

   🚨 A COR NUNCA É O ÚNICO PORTADOR, e é regra desta casa: o nome da etapa e
   o número da situação no Harmonit continuam escritos em cada coluna. Quem não
   distingue as cores perde a decoração, nunca a informação. */
const CORES_DA_ETAPA = [
  '#8CC63F', '#FFC20E', '#F07F13', '#C4203F', '#1B75BB', '#41BFE8',
]

/* ============================================================================
   A EXCECAO DO CARD -- variante C, escolhida por ele em 05/11
   ----------------------------------------------------------------------------
   🔵 *"vamos de C"*, olhando o mockup em que a cor do card fica reservada ao
   que muda o comportamento de quem olha a coluna.

   🚨 O CARD NORMAL NAO TEM COR NENHUMA. Ate 05/11 todo card tinha uma borda
   esquerda de 3px com a cor da etapa -- tirada de `corDaEtapa(indice)`, o
   indice da COLUNA. Mas o card ja esta naquela coluna: dentro dela todos os
   cards tinham a mesma cor, e o acento mais forte do card codificava a unica
   coisa que a posicao ja dizia. A cor da etapa ficou na COLUNA, onde nao se
   repete.

   Sao excecao duas coisas, e as duas mudam o que a pessoa faz:
     1. prioridade diferente de Normal (382) -- dado que ja existe;
     2. parado na etapa alem do limite.

   ⚠️ O LIMITE DE 3 DIAS E SUGESTAO MINHA, NAO NUMERO DELE. Esta escrito em
   `Painel_Operacao_Card_e_Modal_DESIGN.md` como decisao 5, aberta, e ele
   mandou seguir sem responde-la. Trocar o limite e trocar ESTA constante.
   🚨 Teto e regra, e regra e dele: se o numero estiver errado, o erro e meu
   por ter escolhido um.
   ============================================================================ */
const PARADO_DEMAIS_DIAS = 3
const PRIORIDADE_NORMAL = 382

function diasNaEtapa(card) {
  /* ⚠️ `etapa_desde` NULO quer dizer "nao medido" (a `os_passagem` comecou em
     29/10), e nao-medido NUNCA acende alerta: seria afirmar um atraso que
     ninguem mediu. */
  if (!card || !card.etapa_desde) return null
  const t = new Date(card.etapa_desde).getTime()
  if (Number.isNaN(t)) return null
  return (Date.now() - t) / 86400000
}

function paradoDemais(card) {
  const d = diasNaEtapa(card)
  return d !== null && d >= PARADO_DEMAIS_DIAS
}

function prioridadeDeExcecao(card) {
  /* ⚠️ Prioridade NULA = a varredura ainda nao releu esta OS. Nulo nao e
     excecao, e ausencia de medida. */
  return !!(card && card.prioridade) && card.prioridade !== PRIORIDADE_NORMAL
}

function cardEhExcecao(card) {
  return paradoDemais(card) || prioridadeDeExcecao(card)
}

function corDaEtapa(i) {
  return CORES_DA_ETAPA[i % CORES_DA_ETAPA.length]
}

/* "há 2 dias", "hoje" — o que o card do mockup mostra no canto.
   ⚠️ É O TEMPO DESDE A ABERTURA, não o tempo na etapa: o tempo por etapa não
   existe no Harmonit (a linha do tempo registra só o `status`) e é o Bloco C
   desta frente. Escrever "nesta etapa" aqui seria a tela afirmando o que
   ninguém mediu. */
function ha(iso) {
  if (!iso) return ''
  const quandoFoi = new Date(iso)
  if (Number.isNaN(quandoFoi.getTime())) return ''
  const dias = Math.floor((Date.now() - quandoFoi.getTime()) / 86400000)
  if (dias <= 0) return 'hoje'
  if (dias === 1) return 'há 1 dia'
  return `há ${dias} dias`
}

const ROTULO_ESTADO = {
  nova: 'Nova', em_andamento: 'Em andamento', concluida: 'Concluída',
}

/* ============================================================================
   ESC, FOCO E DEVOLUCAO DO FOCO -- o que o `aria-modal` ja prometia
   ----------------------------------------------------------------------------
   🚨 ACHADO EM 05/11, medindo a propria tela: os tres dialogos declaram
   `role="dialog" aria-modal="true"` e nao havia **nenhum** tratamento de
   teclado. `aria-modal="true"` diz ao leitor de tela que o resto da pagina
   esta inerte -- e nao estava: `Escape` nao fechava, o foco nao entrava no
   dialogo, e ao fechar ele ia para o inicio da pagina em vez de voltar ao card.

   ⚠️ A ORDEM DO `Escape` E DELIBERADA: o aviso de etapa primeiro (e o mais
   raso), depois os recados, depois o card. Fechar o card por baixo de um modal
   aberto em cima dele deixaria o de cima orfao.

   ⚠️ E NAO HA TRAVA DE FOCO CIRCULAR: o `Tab` no ultimo elemento sai do
   dialogo. Prender o ciclo exige varrer os focaveis a cada `Tab`, e com tres
   dialogos aninhados e um `<select>` que escreve no ERP o risco de prender o
   foco num dialogo que falhou e maior que o ganho. O que esta resolvido e o
   que se media: entrar, sair pelo teclado, e voltar.
   ============================================================================ */
const caixaDoCard = ref(null)
const caixaDosRecados = ref(null)
const caixaDoAviso = ref(null)

/* 🚨 UMA PILHA, NAO UM SLOT, e a razao e a tela: os recados abrem DE DENTRO
   do card aberto, e o aviso de etapa abre por cima dos dois. Com um slot so,
   abrir os recados sobrescreveria a origem do card -- e fechar o card depois
   devolveria o foco a um botao que ja nao existe no DOM. */
const pilhaDeFoco = []

function aoTeclar(evento) {
  if (evento.key !== 'Escape') return
  if (avisoDaEtapa.value) { fecharAvisoDaEtapa(); return }
  if (recadosAbertos.value) { fecharRecados(); return }
  if (cardAberto.value) { fecharCard() }
}

/* 🚨 `requestAnimationFrame` e nao `nextTick`: o `nextTick` do Vue resolve
   antes de o navegador pintar, e `focus()` num elemento ainda nao pintado nao
   move o foco. */
function focarCaixa(alvoRef) {
  requestAnimationFrame(() => {
    const el = alvoRef && alvoRef.value
    if (el && typeof el.focus === 'function') el.focus()
  })
}

function guardarFoco() {
  pilhaDeFoco.push(document.activeElement)
}

function devolverFoco() {
  const alvo = pilhaDeFoco.pop()
  if (!alvo || typeof alvo.focus !== 'function') return
  /* ⚠️ Se o card saiu do DOM (foi movido de coluna), nao ha onde devolver --
     e ai nao se faz nada, em vez de jogar o foco no `body`. */
  if (!document.body.contains(alvo)) return
  requestAnimationFrame(() => alvo.focus())
}

onMounted(() => {
  carregar()
  window.addEventListener('keydown', aoTeclar)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', aoTeclar)
  clearTimeout(relogioDaBusca)
})
</script>

<template>
  <!-- 🔵 `escala-operacao` sobe as fontes desta tela em +2px, por decisao dele
       em 05/11. A escala vive em `estilo/tokens.css`; aqui nao ha pixel. -->
  <div class="tela escala-operacao">
    <!-- 🔵 *"o cabeçalho esta porco, organize de forma profissional"*.
         🚨 O QUE ESTAVA PORCO: título, botão e quatro controles eram IRMÃOS num
         `space-between`, então o navegador espalhava tudo numa linha sem grupo
         nenhum. Agora são DOIS blocos: a identidade à esquerda e os controles
         à direita, numa fileira própria que quebra junto no celular. -->
    <header class="tela__cabecalho">
      <div class="cabecalho__identidade">
        <h1>Operação</h1>
        <!-- ⚠️ UMA linha de resumo, com o número MEDIDO e desde quando -- como
             no mockup. "O painel está vazio" e "o painel começa em 24/10" são
             respostas diferentes para a mesma tela vazia. -->
        <p v-if="quadro" class="cabecalho__resumo">
          <strong>{{ quadro.total }}</strong>
          {{ quadro.total === 1 ? 'OS' : 'OS' }} nas 17 situações do Harmonit,
          desde {{ dia(quadro.desde) }}
          <template v-if="!quadro.so_abertas"> · incluindo as finalizadas</template>
        </p>
        <AjudaDaTela>
          O card é a <strong>OS</strong>, de qualquer origem — formulário, FPSL,
          painel ou aberta à mão —, em colunas nas
          <strong>17 situações da OS no Harmonit</strong>, na ordem do fluxo da
          operação. Arraste o card para mudar a etapa: isso
          <strong>escreve a situação no Harmonit</strong> e registra quem fez.
        </AjudaDaTela>
      </div>

      <div class="cabecalho__controles">
        <!-- 🔵 *"filtros para os cards, por cliente, OS, placa"* — UMA caixa
             para os três: quem procura tem um número ou um nome na mão e não
             quer decidir em qual caixa ele vai.
             🔵 ÁREA E (05/11): e por TERMO, que é o quarto campo. 🚨 Ele é o
             que mais precisa do *"casou por"* logo abaixo: termo e número de
             OS são os dois números de 4-5 dígitos do card, e sem dizer qual
             casou quem procura `8937` não sabe se achou a OS 8937 ou as 6 OS
             do termo 8937. -->
        <label class="painel__busca">
          <span class="so-leitor">Procurar por cliente, número da OS, placa ou termo</span>
          <input type="search" v-model="busca" @input="buscarComCalma"
                 placeholder="cliente, OS, placa ou termo">
        </label>

        <!-- 🔵 *"ordenadores tbm"*. ⚠️ "parado há mais tempo" usa o Bloco C, e
             card sem passagem registrada vai para o fim — "não medido" não é
             "parado há mais tempo". -->
        <label class="painel__ordem">
          <span class="so-leitor">Ordenar os cards</span>
          <select v-model="ordem" @change="carregar">
            <option v-for="(rot, chave) in ROTULO_ORDEM" :key="chave"
                    :value="chave">{{ rot }}</option>
          </select>
        </label>

        <!-- 🚨 O INTERRUPTOR DAS FINALIZADAS: com ele ligado o Financeiro cai
             de 6 para 2 cards, porque OS financeira nasce `Finalizado`. Sem
             ele, quem procura uma OS finalizada concluiria que ela não
             existe. -->
        <label class="painel__interruptor">
          <input type="checkbox" v-model="soAbertas" @change="carregar">
          <span>só as abertas</span>
        </label>

        <button class="botao botao--contorno" type="button" @click="carregar">
          Atualizar
        </button>
      </div>
    </header>

    <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>
    <!-- 🚨 A RECUSA DE MOVER É DITA, e com `alert`: a escrita no ERP não
         aconteceu, e o card já voltou para o lugar. Falha silenciosa aqui
         faria a pessoa pensar que gravou. -->
    <p v-if="erroDeMover" class="aviso aviso--erro" role="alert">
      {{ erroDeMover }}
    </p>
    <p v-if="carregando" class="nota">Lendo…</p>

    <template v-if="quadro">
      <!-- 🚨 A PONTE CAÍDA É O PRIMEIRO AVISO, acima de todos os outros, e
           com cara de erro: sem ela o quadro mostra só o que o nosso banco
           sabe, e hoje isso são 2 cards em vez de 10. Quadro pequeno sem
           explicação faria o operador concluir que não há trabalho -- e é
           justo nessa hora que há. -->
      <p v-if="quadro && !quadro.ponte_respondeu" class="aviso aviso--erro"
         role="alert">
        <i class="bi bi-plug aviso__icone" aria-hidden="true"></i>
        <span>
          O FPSL não respondeu, então este quadro mostra <strong>só os
          chamados que já têm OS registrada aqui</strong> — as OS abertas
          direto no Harmonit não aparecem agora.
        </span>
      </p>

      <!-- 🚨 CARA DE ATENÇÃO SÓ QUANDO ALGO FALHOU DE VERDADE. Ele leu esta
           linha em 29/10 e perguntou *"pq deu erro?"* -- e nada havia
           falhado: era um chamado aguardando e uma OS que o ERP tem em
           situação 0. O triângulo e o estilo de atenção diziam "problema", e
           a pessoa vai procurar um erro que não existe. Falha de abertura de
           OS é problema; o resto é nota. -->
      <!-- ⚠️ `aviso--fora` existe para quem TESTA poder apontar para ESTA
           linha: a tela tem tres `.aviso` (erro de leitura, ponte caida, e
           esta), e um seletor generico pega a primeira do DOM. -->
      <!-- 🚨 QUADRO FILTRADO QUE NÃO DIZ QUE ESTÁ FILTRADO é a mesma família
           do `M12`: alguém abre o painel, vê 1 card e conclui que a operação
           está vazia. -->
      <p v-if="quadro.busca" class="aviso aviso--nota" role="status">
        <i class="bi bi-funnel aviso__icone" aria-hidden="true"></i>
        <span>
          Mostrando só o que casa com <strong>{{ quadro.busca }}</strong>
          <template v-if="quadro.filtro_casou_por">
            (casou por {{ quadro.filtro_casou_por.join(', ') }})
          </template>
          <template v-else>— <strong>nenhum card casou</strong></template>.
          <button class="painel__limpar" type="button"
                  @click="busca = ''; carregar()">limpar</button>
        </span>
      </p>

      <p v-if="fora" class="aviso aviso--fora"
         :class="quadro.fora_do_quadro.os_falhou ? 'aviso--atencao' : 'aviso--nota'"
         role="status">
        <i class="aviso__icone" aria-hidden="true"
           :class="quadro.fora_do_quadro.os_falhou
                     ? 'bi bi-exclamation-triangle' : 'bi bi-info-circle'"></i>
        <span>{{ fora }} — abra em <strong>Solicitações</strong>.</span>
      </p>

      <!-- 🔵 29/10, ele: *"os comentários tbm devem sumir dali"*. Saíram os
           três textos que ficavam aqui -- o aviso de que mover não existe, a
           lista dos formulários com a contagem de campos, e o cartão de
           "nenhuma solicitação chegou ainda".
           ⚠️ O que saiu é o TEXTO: mover continua não existindo
           (`quadro.pode_mover` segue falso e não há gesto de arrastar), e
           coluna vazia continua colapsada com o contador à vista.
           🚨 E a palavra do atributo de arrastar NÃO SE ESCREVE neste
           comentário: comentário de HTML entra no `html()` renderizado, e a
           trava que garante a ausência do gesto procura exatamente essa
           palavra -- escrevê-la aqui fazia o teste reprovar com a tela
           correta. -->

      <div class="quadro">
        <section
          v-for="(coluna, indice) in quadro.colunas"
          :key="coluna.chave"
          class="coluna"
          :class="{ 'coluna--fechada': !abertas[coluna.chave],
                    'coluna--vazia': !coluna.total,
                    'coluna--alvo': colunaAlvo === coluna.chave }"
          :style="{ borderTopColor: corDaEtapa(indice) }"
          :aria-label="coluna.titulo"
          @dragover.prevent="sobreAColuna(coluna)"
          @dragenter.prevent="sobreAColuna(coluna)"
          @dragleave="saiuDaColuna(coluna)"
          @drop.prevent="soltarNaColuna(coluna)"
        >
          <h2 class="coluna__titulo">
            <!-- ⚠️ Toda coluna colapsa desde 29/10: as duas que eram fixas
                 ("Sem OS" e "Sem situacao") sairam do painel. -->
            <button
              class="coluna__botao"
              type="button"
              :aria-expanded="abertas[coluna.chave] ? 'true' : 'false'"
              @click="alternar(coluna)"
            >
              <span class="coluna__nome">{{ coluna.titulo }}</span>
              <!-- 🚨 CHEIO quando tem card, vazado quando não tem: o quadro
                   tem 17 colunas, e a diferença entre "0" e "3" precisa se ver
                   de longe, sem contar casa por casa. -->
              <span class="coluna__conta"
                    :class="{ 'coluna__conta--zero': !coluna.total }">
                {{ coluna.total }}
              </span>
            </button>
          </h2>

          <div v-if="abertas[coluna.chave]" class="coluna__corpo">
            <p v-if="coluna.nota" class="nota pequeno">{{ coluna.nota }}</p>
            <p v-if="coluna.situacao_id" class="nota pequeno">
              situação {{ coluna.situacao_id }} no Harmonit
            </p>

            <!-- 🚨 A OS VEM NA FRENTE, e isto mudou com a D8: até 29/10 o card
                 começava pelo nome do formulário, e desde que o card é a OS
                 "de qualquer origem" a maioria não tem formulário nenhum --
                 10 de 10 medidos hoje vêm do ERP. O card começava com um
                 campo vazio. -->
            <article v-for="card in coluna.cards"
                     :key="card.numero_ordem || card.id" class="card"
                     :class="{ 'card--movendo': movendo === card.numero_ordem }"
                     :draggable="quadro.pode_mover && !!card.numero_ordem"
                     @dragstart="comecarArrasto(card, $event)"
                     @dragend="terminarArrasto">
              <!-- 🚨 ERA UM `<button>` E ISSO IMPEDIA O ARRASTO: navegador
                   não inicia o arrasto do pai a partir de um elemento
                   interativo -- o `mousedown` morre no botão e o `dragstart`
                   nunca dispara. O `draggable` estava no HTML e o gesto era
                   impossível.
                   ⚠️ O teclado continua alcançando: o NÚMERO DA OS é o botão
                   (alvo pequeno), e o resto do card arrasta. -->
              <div class="card__abrir"
                   :class="{ 'card__abrir--excecao': cardEhExcecao(card) }"
                   @click="cliqueNoCard(card)">

                <!-- LINHA 1 -- O CLIENTE, e nao a OS. 🔵 Variante C, escolhida por
                     ele em 05/11. Isto muda a ordem de 29/10 (*"A OS VEM NA
                     FRENTE"*), e mudou com a palavra dele.
                     🚨 CORTA EM DUAS LINHAS, com o nome inteiro no `title`:
                     medido em 05/11, **11 dos 15** nomes de cliente do quadro
                     passam de 24 caracteres (mediana 28, o maior 56), e numa
                     coluna de 248px com a fonte +2 cabem ~24 por linha. Sem
                     corte, um card comia quatro linhas so de razao social. -->
                <span class="card__linha">
                  <span v-if="card.cliente" class="card__cliente"
                        :title="card.cliente">{{ card.cliente }}</span>
                  <!-- ⚠️ Cliente sem nome e DITO, nao deixado em branco: o
                       `harmonit_id` da OS pode nao estar no nosso cadastro. -->
                  <span v-else class="card__cliente card__cliente--sem">
                    cliente {{ card.cliente_id || '?' }}, fora do nosso cadastro
                  </span>
                  <span v-if="ha(card.criada_em)" class="card__direita">
                    {{ ha(card.criada_em) }}
                  </span>
                </span>

                <!-- LINHA 2 -- os identificadores com que se cruza papel.
                     ⚠️ A OS continua sendo o BOTAO (o alvo de teclado) e o unico
                     em cor de acento; o TERMO e referencia, nao acao. -->
                <!-- LINHA 2 -- 🔵 DUAS FAIXAS VIRARAM UMA em 05/11: com 334px de
                     largura util, os identificadores cabem a esquerda e o tipo
                     com a placa na borda direita. Era o *"mais retangular
                     horizontal do que vertical"* que ele pediu -- o card desce
                     de 5 faixas para 3. -->
                <span class="card__linha">
                  <span class="card__ident">
                    <button class="card__os" type="button"
                            @click.stop="cliqueNoCard(card)">OS {{ card.numero_ordem || card.os_id }}</button>
                    <!-- ⚠️ OS SEM TERMO E 1 DE CADA 7, e a tela nao diz nada: venda,
                         cartao RFID e manutencao nao nascem de termo. -->
                    <span v-if="card.termo" class="card__termo">TERMO {{ card.termo }}</span>
                  </span>
                  <span v-if="card.tipo_nome || (card.placas && card.placas.length)"
                        class="card__direita card__direita--dado">
                    <template v-if="card.tipo_nome">{{ card.tipo_nome }}</template>
                    <template v-if="card.tipo_nome && card.placas && card.placas.length"> &middot; </template>
                    <template v-if="card.placas && card.placas.length">{{ card.placas.map((p) => p.placa).join(' &middot; ') }}</template>
                  </span>
                </span>

                <!-- LINHA 4 -- 🔵 BLOCO C, os dois tempos, agora numa linha com o
                     total alinhado a direita. ⚠️ "nao medido" quando nao ha
                     passagem: a `os_passagem` comecou em 29/10, e a OS pode
                     estar na etapa desde setembro -- mostrar "0h" seria afirmar
                     o que ninguem mediu. -->
                <!-- LINHA 3 -- ⚠️ OS TEMPOS E OS SELOS NA MESMA FAIXA, pelo mesmo
                     motivo: com 334px os dois cabem, e o card deixa de ter uma
                     faixa so para dois numeros curtos. A borda direita continua
                     alinhada com as de cima -- e o realinhamento que ele
                     aprovou em 05/11, com uma faixa menos. -->
                <span class="card__linha card__dado">
                  <span class="card__etapa"
                        :class="{ 'card__etapa--parado': paradoDemais(card) }">
                    nesta etapa
                    <strong>{{ duracao(card.etapa_desde) || 'não medido' }}</strong>
                    <template v-if="duracao(card.criada_em)">
                      &middot; total {{ duracao(card.criada_em) }}
                    </template>
                  </span>
                </span>

                <!-- LINHA 5 -- os selos a esquerda, a data a direita.
                     🚨 SAIRAM DAQUI, em 05/11, duas pilulas que nao informavam:
                     o NOME DA SITUACAO (que e o titulo da coluna em que o card
                     ja esta, e era a pilula mais comprida de todas -- em 248px
                     *"Configurar equipamentos e Sistemas"* ocupava 3 linhas) e
                     *"Harmonit"* (que aparecia em quase todo card, porque a
                     origem ERP e a maioria; o que distingue e ter vindo de
                     FORMULARIO, e so esse caso aparece agora). -->
                <span class="card__linha">
                  <span class="card__pistas">
                    <span v-if="card.origem !== 'erp' && card.formulario"
                          class="pilula pilula--origem">{{ card.formulario }}</span>

                    <span v-if="card.estado" class="etiqueta"
                          :class="`etiqueta--${card.estado}`">
                      {{ ROTULO_ESTADO[card.estado] || card.estado }}
                    </span>

                    <span v-if="card.anexos" class="pilula">
                      {{ card.anexos }} anexo(s)
                    </span>

                    <!-- 🔵 *"a prioridade vem escrita porque ela nasce Normal e
                         mudar e excecao, e excecao precisa estar visivel sem
                         abrir"*. 🚨 E AGORA SO A EXCECAO APARECE: *Normal* em
                         todo card nao distinguia nada e gastava a linha dos
                         selos. Nula tambem nao aparece -- nulo e "a varredura
                         nao releu", nao "sem prioridade". -->
                    <span v-if="prioridadeDeExcecao(card)" class="pilula pilula--alerta">
                      {{ card.prioridade_nome }}
                    </span>

                    <!-- 🔵 04/11: o selo do checklist. ⚠️ `tem_checklist` e
                         `checklist` sao coisas diferentes: a etapa pode TER lista
                         e o card ainda nao a ter aberto. 🚨 Completo fica VERDE,
                         incompleto fica ambar -- a cor acompanha o que FALTA. -->
                    <span v-if="card.checklist" class="pilula"
                          :class="card.checklist.feitos >= card.checklist.total
                                  ? 'pilula--pronto' : 'pilula--alerta'">
                      {{ card.checklist.feitos }} de {{ card.checklist.total }}
                    </span>
                    <span v-else-if="card.tem_checklist" class="pilula">checklist</span>

                    <span v-if="card.observacoes" class="pilula">
                      {{ card.observacoes }} obs
                    </span>

                    <!-- 🚨 FINALIZADA E AVISO, nao decoracao: ela so aparece com
                         o interruptor desligado, e sem esta marca ficaria
                         indistinguivel de uma OS viva na mesma coluna. -->
                    <span v-if="card.finalizada" class="card__alerta">finalizada</span>
                  </span>

                  <!-- 🚨 *"PREVISAO"*, E NAO *"PRAZO"* -- e isto era um defeito meu
                       de 29/10, achado em 05/11: o comentario que acompanhava
                       esta linha dizia, com a medicao, que *"chamar de prazo
                       seria a tela afirmando o que o ERP nao diz"*, e a linha
                       escrevia `prazo`. O modal ja usava *"Previsao de
                       entrega"*, o nome do campo no ERP: as duas telas do mesmo
                       painel se contradiziam.
                       ⚠️ MEDIDO: a OS do Harmonit tem UM campo de data,
                       `dataPrevisao`, e NAO existe campo de prazo -- na 17055,
                       criada em 29/10, a previsao e 29/10 11:40:19, o mesmo
                       minuto. 🔵 Isso muda quando a frente do aviso previo
                       entrar: ela vai mover a previsao em +90 dias. -->
                  <span v-if="card.criada_em" class="card__direita">
                    previsão {{ dataCurta(card.criada_em) }}
                  </span>
                </span>

                <!-- ⚠️ Quando este dado foi lido do ERP. A varredura roda a cada
                     5 min, e a tela nao pode deixar supor que e agora. -->
                <span v-if="card.visto_em" class="card__visto">
                  lido do Harmonit {{ quando(card.visto_em) }}
                </span>
              </div>

              <!-- 🔵 A CAIXA DE SELEÇÃO SAIU DAQUI, a pedido dele: *"pq ela foi
                   substituida por uma caixa de selecao?"*. Ele decidiu
                   arrastar, e enquanto o arrasto estava quebrado a caixa era o
                   único jeito de mover — então ela parecia a substituição.
                   ⚠️ O teclado continua alcançando por outro caminho: o número
                   da OS abre o card (Enter), e o `select` de etapa vive DENTRO
                   do card aberto. -->
            </article>

            <!-- 🚨 O ALVO DA COLUNA VAZIA: é ao mesmo tempo a área de
                 soltar e o convite. Um "Vazia." de uma linha não dava altura
                 para acertar o solto, e era parte do arrasto "não ir a lugar
                 algum". -->
            <p v-if="!coluna.cards.length" class="coluna__alvo-vazio">
              <template v-if="quadro.pode_mover">
                solte um card aqui para mover para esta etapa
              </template>
              <template v-else>sem OS nesta etapa</template>
            </p>
          </div>
        </section>
      </div>

      <!-- ============ OS RECADOS, EM MODAL (Área D) ============ -->
      <div v-if="recadosAbertos && cardAberto" class="modal" role="dialog"
           aria-modal="true" aria-label="Observações do card"
           @click.self="fecharRecados">
        <div ref="caixaDosRecados" tabindex="-1" class="modal__caixa">
          <header class="modal__topo">
            <strong>Observações — OS {{ cardAberto.numero_ordem }}</strong>
            <button class="modal__fechar" type="button" aria-label="Fechar"
                    @click="fecharRecados">✕</button>
          </header>

          <div class="modal__corpo">
            <p class="nota pequeno">
              Ficam no MoviZap, com autor e hora. <strong>Não vão para a OS</strong>
              do Harmonit, e não se apagam.
            </p>

            <ul v-if="ficha && ficha.observacoes && ficha.observacoes.length"
                class="recados">
              <BalaoDeRecado v-for="o in [...ficha.observacoes].reverse()"
                             :key="o.id" :recado="o" :quando="quando" />
            </ul>
            <p v-else class="nota pequeno">Nenhuma observação ainda.</p>
          </div>

          <div class="modal__rodape modal__rodape--escrever">
            <textarea v-model="recado" rows="2" :disabled="enviandoRecado"
                      placeholder="o que a operação precisa saber sobre esta OS"
                      aria-label="Escrever observação"></textarea>
            <div class="linha">
              <!-- ⚠️ A lista branca aparece para quem escolhe: recusar depois
                   de subir desperdiça o tempo de quem opera. -->
              <input type="file" aria-label="Anexar arquivo"
                     accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.doc,.docx,.xls,.xlsx,.csv,.txt"
                     @change="escolherAnexo" />
              <button class="botao botao--primario" type="button"
                      :disabled="enviandoRecado || (!recado.trim() && !anexoEscolhido)"
                      @click="salvarRecadoComAnexo">
                {{ enviandoRecado ? 'Salvando…' : 'Salvar' }}
              </button>
            </div>
            <p class="nota pequeno">
              O arquivo fica no servidor do MoviZap e <strong>não tem
              backup</strong> — não substitui o documento guardado no lugar certo.
            </p>
            <p v-if="erroDoRecado" class="aviso aviso--erro" role="alert">
              {{ erroDoRecado }}
            </p>
          </div>
        </div>
      </div>

      <!-- ============ O AVISO AO ENTRAR NA ETAPA (Área B) ============ -->
    <div v-if="avisoDaEtapa" class="modal" role="dialog" aria-modal="true"
         aria-label="Aviso da etapa">
      <div ref="caixaDoAviso" tabindex="-1" class="modal__caixa modal__caixa--curta">
        <header class="modal__topo">
          <strong>{{ avisoDaEtapa.titulo }}</strong>
        </header>
        <div class="modal__corpo">
          <p>
            Esta etapa tem <strong>checklist</strong>. Ele fica
            <strong>dentro do card</strong> — abra o card para ver o que fazer.
          </p>
          <p class="nota pequeno">
            Não aviso de novo nesta etapa pelos próximos 10 minutos.
          </p>
        </div>
        <div class="modal__rodape">
          <button class="botao botao--primario" type="button"
                  @click="fecharAvisoDaEtapa">Ok</button>
        </div>
      </div>
    </div>

      <!-- ================= O CARD ABERTO ================= -->
      <div v-if="cardAberto" class="modal" role="dialog" aria-modal="true"
           :aria-label="`OS ${cardAberto.numero_ordem}`"
           @click.self="fecharCard">
        <div ref="caixaDoCard" tabindex="-1" class="modal__caixa">
          <!-- ============ 1. O TOPO: quem e esta OS, e o fechar ============
               🔵 05/11, proposta A: o CLIENTE e a primeira coisa, em corpo de
               titulo, e os identificadores descem para a linha de baixo. O
               modal tem 1000px, entao aqui o nome vem INTEIRO -- e e o lugar
               onde ele vem inteiro, porque no card de 248px ele corta em duas
               linhas (11 dos 15 nomes do quadro passam de 24 caracteres). -->
          <header class="modal__topo">
            <div class="modal__quem">
              <h2 class="modal__cliente">
                {{ cardAberto.cliente || `cliente ${cardAberto.cliente_id || '?'}, fora do nosso cadastro` }}
              </h2>
              <p class="modal__ident">
                <strong class="modal__os">OS {{ cardAberto.numero_ordem }}</strong>
                <!-- 🔵 AREA E: o termo tambem no aberto, onde quem vai agir
                     precisa dele para achar o papel. ⚠️ Nulo em 1 de cada 7, e
                     ai nao aparece nada. -->
                <span v-if="cardAberto.termo" class="modal__termo">TERMO {{ cardAberto.termo }}</span>
                <span class="modal__risco" aria-hidden="true"></span>
                <span>{{ cardAberto.tipo_nome || 'tipo não lido' }}</span>
                <template v-if="cardAberto.placas && cardAberto.placas.length">
                  <span class="modal__risco" aria-hidden="true"></span>
                  <span>{{ cardAberto.placas.map((p) => p.placa).join(' · ') }}</span>
                </template>
              </p>
            </div>
            <button class="modal__fechar" type="button"
                    aria-label="Fechar" @click="fecharCard">✕</button>
          </header>

          <!-- ============ 2. A FAIXA: SO LEITURA ============
               🚨 OS DOIS CONTROLES QUE ESCREVEM NO ERP SAIRAM DAQUI em 05/11, e
               foi o defeito de desenho que ele apontou: a faixa punha cinco
               medidas de leitura e dois `<select>` de ESCRITA com o mesmo
               rotulo em caixa-alta e o mesmo peso -- e a frase que avisa da
               escrita estava no PE, a uma tela de distancia dos controles que
               ela descreve. Agora a faixa so informa, e os dois descem para o
               pe, ao lado do aviso.

               ⚠️ E *"Previsao de entrega"* saiu da faixa: ela gastava um slot de
               medida para dizer, numa nota, que a medida nao vale (*"hoje igual
               a abertura"*). No lugar entrou *"Aberta"*, que e o que o dado e.
               🔵 A previsao volta quando a frente do aviso previo a mover em
               +90 dias -- e ai ela sera uma medida de verdade. -->
          <div class="modal__faixa">
            <div class="faixa__medida">
              <span class="faixa__rotulo">Etapa agora</span>
              <strong>{{ nomeDaSituacao(cardAberto.situacao_id) }}</strong>
            </div>
            <div class="faixa__medida">
              <span class="faixa__rotulo">Nesta etapa</span>
              <!-- 🔵 Bloco C. ⚠️ "nao medido" quando nao ha passagem: a
                   `os_passagem` comecou em 29/10. 🔵 E o ambar da variante C
                   aparece aqui tambem, pela mesma regua do card. -->
              <strong :class="{ 'faixa__parado': paradoDemais(cardAberto) }">
                {{ duracao(cardAberto.etapa_desde) || 'não medido' }}
              </strong>
            </div>
            <div class="faixa__medida">
              <span class="faixa__rotulo">Total da OS</span>
              <strong>{{ duracao(cardAberto.criada_em) || '—' }}</strong>
            </div>
            <div class="faixa__medida">
              <span class="faixa__rotulo">Status no ERP</span>
              <strong>{{ cardAberto.status_str || '—' }}</strong>
            </div>
            <div class="faixa__medida">
              <span class="faixa__rotulo">Prioridade</span>
              <!-- ⚠️ LEITURA: quem muda e o `<select>` do pe. O valor vem da
                   ficha lida ao vivo; antes dela chegar, vale o que o card
                   trouxe do cache. -->
              <strong :class="{ 'faixa__parado': prioridadeDeExcecao(cardAberto) }">
                {{ (ficha && ficha.prioridades && ficha.prioridades[ficha.prioridade])
                   || cardAberto.prioridade_nome || '—' }}
              </strong>
            </div>
            <div class="faixa__medida">
              <span class="faixa__rotulo">Aberta</span>
              <strong>{{ quando(cardAberto.criada_em) }}</strong>
            </div>
          </div>

          <!-- ============ 3. O CORPO: duas colunas, UMA rolagem ============
               🚨 TRES COISAS QUE ESTAVAM ERRADAS AQUI, as tres medidas em 05/11:

               1. O checklist, as observacoes e as passagens eram filhos DIRETOS
                  da `.modal__caixa`, que tem `padding: 0` de proposito -- e
                  nenhuma das tres definia padding. O miolo util do modal ficava
                  rente as bordas enquanto o topo, o pe e os temas respiravam.
               2. O teto de rolagem (`max-height: 60vh`) estava no
                  `.modal__corpo`, que continha SO os temas. As tres secoes que
                  crescem de verdade estavam fora dele, sem teto -- o comentario
                  dizia que o teto existia *"para o pe nao fugir da tela"*, e ele
                  guardava justo o bloco de tamanho previsivel.
               3. Duas rolagens empilhadas: a do `.modal` e a do `.modal__corpo`.

               Agora: a caixa tem altura fixa, topo e pe sao `flex: none`, e SO
               este corpo rola. ⚠️ `min-height: 0` e o que faz isso funcionar
               em flex -- sem ele o corpo se recusa a encolher e o pe sai da tela.

               🔵 E duas colunas: a ESQUERDA e o que se FAZ, a DIREITA e o que se
               LE. Empilhadas, as duas metades mais altas do modal somavam; lado
               a lado, a altura cai quase a metade. -->
          <div class="modal__corpo modal__corpo--duas">
            <div class="modal__coluna modal__coluna--fazer">
              <p class="modal__secao">O trabalho</p>
<section v-if="checklist.length || carregandoCheck"
                     class="modal__recados modal__painel">
              <h3>
                Checklist desta etapa
                <span class="pilula">{{ feitosDoCheck }} de {{ checklist.length }}</span>
              </h3>

              <p v-if="carregandoCheck" class="nota pequeno">lendo…</p>

              <ul v-else class="modal__passagens">
                <li v-for="i in checklist" :key="i.id">
                  <label class="check__linha">
                    <input type="checkbox" :checked="i.feito"
                           @change="marcarItem(i)" />
                    <span :class="{ 'check__feito': i.feito }">{{ i.texto }}</span>
                  </label>
                  <span v-if="i.feito" class="nota pequeno">
                    {{ i.feito_por || 'sem autor' }}<span v-if="i.feito_em">, {{ quando(i.feito_em) }}</span>
                  </span>
                  <!-- 🚨 Só o item AVULSO sai. O da lista da etapa se tira no
                       modelo, e a recusa do servidor diz isso por extenso. -->
                  <button v-if="i.avulso" class="botao botao--pequeno botao--fantasma"
                          type="button" title="Remover este item"
                          @click="removerItem(i)">✕</button>
                </li>
              </ul>

              <div class="modal__pe">
                <input v-model="itemNovo" class="campo__entrada"
                       placeholder="+ Adicionar item"
                       aria-label="Acrescentar item ao checklist deste card"
                       @keyup.enter="acrescentarItem" />
                <button class="botao" type="button" :disabled="!itemNovo.trim()"
                        @click="acrescentarItem">Adicionar</button>
              </div>

              <p v-if="erroDoCheck" class="aviso aviso--erro" role="alert">
                {{ erroDoCheck }}
              </p>

              <!-- 🔵 A FRASE DE REGRA E O PE DO PAINEL, e nao a abertura: era o
                   segundo paragrafo do bloco, logo abaixo do titulo, e empurrava
                   o checklist -- a lista e o assunto, a regra e a nota de pe.
                   E o mockup que ele validou a mostrava embaixo. -->
              <p class="modal__painel-pe">
                Ao mover o card, isto vira uma <strong>observação</strong> aqui.
                <strong>Não vai para a OS</strong> do Harmonit.
              </p>
            </section>
<section class="modal__recados modal__painel">
              <h3>
                Observações
                <span class="pilula">{{ ((ficha && ficha.observacoes) || []).length }}</span>
              </h3>
              <div class="modal__pe">
                <button class="botao" type="button" @click="abrirRecados">
                  Abrir observações
                </button>
              </div>
              <p class="modal__painel-pe">
                Com autor e hora, e não se apagam.
                <strong>Não vão para a OS</strong> do Harmonit.
              </p>
            </section>
            </div>

            <div class="modal__coluna modal__coluna--ler">
              <p class="modal__secao">A OS no Harmonit</p>
<section class="modal__temas modal__painel">
              <p v-if="lendoFicha" class="nota pequeno">Lendo a OS no Harmonit…</p>
              <!-- 🚨 ERRO, NÃO FICHA VAZIA: ficha vazia é indistinguível de OS
                   sem dados, e o operador concluiria que não há o que ver. -->
              <p v-else-if="erroDaFicha" class="aviso aviso--erro" role="alert">
                {{ erroDaFicha }}
              </p>

              <div class="temas__abas" role="tablist">
                <button v-for="t in temas" :key="t.chave" type="button"
                        role="tab" class="temas__aba"
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
                  <!-- ⚠️ VAZIO É DITO, não deixado em branco: a solução técnica é
                       nula na maioria das OS, e uma caixa branca parece defeito. -->
                  <p v-if="t.vazio" class="nota pequeno">{{ t.resumo }}</p>

                  <pre v-else-if="t.texto" class="temas__texto">{{ t.texto }}</pre>

                  <!-- os dados do chamado, com RÓTULO e nunca a chave do Bitrix -->
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
            </section>
              <p class="modal__secao">O histórico</p>
<section class="modal__log modal__painel">
              <h3>Passagens de etapa</h3>
              <p v-if="lendoPassagens" class="nota pequeno">Lendo…</p>
              <!-- 🚨 O HARMONIT NÃO REGISTRA SITUAÇÃO na linha do tempo: este log
                   é nosso, e começou a existir em 29/10. Dizer isso é o que
                   impede a tela de parecer que a OS nunca se moveu. -->
              <p v-else-if="!passagens.length" class="nota pequeno">
                Nenhuma passagem registrada. O Harmonit não guarda a situação na
                linha do tempo — este log é nosso e começou em 29/10, então OS
                movida antes disso não aparece aqui.
              </p>
              <ul v-else class="modal__passagens">
                <li v-for="p in passagens" :key="p.id">
                  <span class="nota pequeno">{{ quando(p.em) }}</span>
                  <span>
                    {{ nomeDaSituacao(p.de_situacao) }} →
                    <strong>{{ nomeDaSituacao(p.para_situacao) }}</strong>
                  </span>
                  <span class="pilula">{{ p.quem || 'sem autor' }}</span>
                  <span v-if="!p.ok" class="card__alerta">
                    recusada: {{ p.erro }}
                  </span>
                </li>
              </ul>
            </section>
            </div>
          </div>

          <!-- ============ 4. O PE: onde se AGE ============
               🚨 O AVISO FICA JUNTO DO GESTO QUE ELE DESCREVE. Antes a frase
               vivia aqui e os dois `<select>` viviam na faixa, no alto. E a
               frase estava em `.apagado` (#94A3B8, **2,56:1** sobre branco),
               que e justamente a classe que falha a norma -- o aviso de escrita
               no ERP era o texto menos legivel do modal. -->
          <footer class="modal__rodape">
            <div class="modal__agir">
              <label v-if="quadro.pode_mover && cardAberto.numero_ordem"
                     class="faixa__campo">
                <span class="faixa__rotulo">Mover para</span>
                <select :value="cardAberto.situacao_id"
                        :disabled="movendo === cardAberto.numero_ordem"
                        @change="moverDoModal(Number($event.target.value))">
                  <option v-for="c in quadro.colunas" :key="c.chave"
                          :value="c.situacao_id">{{ c.titulo }}</option>
                </select>
              </label>

              <!-- 🚨 Mudar a prioridade ESCREVE A OS INTEIRA no Harmonit. -->
              <label v-if="ficha && ficha.prioridades" class="faixa__campo">
                <span class="faixa__rotulo">Prioridade</span>
                <select :value="ficha.prioridade" :disabled="salvando"
                        @change="mudarPrioridade(Number($event.target.value))">
                  <option v-for="(rot, id) in ficha.prioridades" :key="id"
                          :value="Number(id)">{{ rot }}</option>
                </select>
              </label>

              <!-- 🚨 A FRASE DIZ O QUE CADA UM ESCREVE, e nao so que escrevem.
                   ⚠️ Eu a havia encurtado para *"Os dois escrevem na OS do
                   Harmonit"* ao mover os controles para ca, e com isso perdi
                   duas informacoes que a frase antiga tinha: que o mover grava
                   **a situacao**, e -- medido no `os_ponte.gravar_prioridade` --
                   que mudar a prioridade reescreve **a OS inteira**, porque a
                   unica rota de escrita do Harmonit e a `SalvarOrdemServico`.
                   Um teste pegou: ele prendia a frase antiga. -->
              <p class="modal__perigo">
                Mover de etapa <strong>escreve a situação na OS do Harmonit</strong>.
                Mudar a prioridade <strong>reescreve a OS inteira</strong>.
              </p>
            </div>

            <div class="modal__acoes">
              <button v-if="cardAberto.id" class="botao botao--contorno"
                      type="button" @click="verNaFRM(cardAberto)">
                Ver o chamado em Solicitações
              </button>
              <button class="botao" type="button" @click="fecharCard">Fechar</button>
            </div>
          </footer>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* 🔵 *"organize de forma profissional"*: DOIS blocos, e cada um com a sua
   fileira. ⚠️ `align-items: flex-end` para o título e os controles ficarem na
   mesma linha de base, que é o que o olho procura. */
.tela__cabecalho {
  display: flex; flex-wrap: wrap;
  align-items: flex-end; justify-content: space-between;
  gap: var(--e-3); margin-bottom: var(--e-4);
}
.cabecalho__identidade { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.cabecalho__resumo { margin: 0; font-size: var(--txt-sm); color: var(--texto-fraco); }
.cabecalho__controles {
  display: flex; flex-wrap: wrap; align-items: center; gap: var(--e-2);
}
.faixa__nota { font-size: var(--txt-xs); color: var(--texto-apagado); }
.card__data { font-size: var(--txt-xs); color: var(--texto-fraco); }
.tela__cabecalho h1 { margin: 0; font-size: var(--txt-xl); }


.quadro { display: flex; gap: var(--e-3); overflow-x: auto; padding-bottom: var(--e-3); align-items: flex-start; }

/* 🔵 A BORDA DE CIMA É A COR DA ETAPA — do mockup. A cor vem do `:style`,
   porque são 17 colunas ciclando 6 cores e isso é dado, não folha de estilo. */
/* 🚨 A COLUNA TEM FUNDO, E O CARD E BRANCO -- e isto era um defeito medido
   em 05/11: a `.coluna` e o `.card__abrir` usavam os DOIS `var(--superficie)`,
   que e `#FFFFFF`. Card branco dentro de coluna branca, e a unica separacao
   era uma borda de 1px no tom mais claro da paleta. 🔵 Ele: *"pode dar uma
   elaborada para evidenciar as limitacoes das caixas, talvez espessura ou
   sombreamento"*. O conserto e nos dois lados: a coluna recua para o fundo da
   pagina, e o card ganha borda mais forte e sombra. */
.coluna {
  /* 🔵 05/11: *"o layout dos cards com a fonte maior nao ficou bom, pode
     deixar um pouco mais retangular horizontal do que vertical, vendo 3
     colunas por scroll esta ok"*.
     🚨 A CONTA DOS 3 POR SCROLL, em tela de 1366px: 1366 - 240 (menu) - 24
     (o padding do `meta.largo`) = 1102, menos dois vaos de 12px = 1078 / 3 =
     **359px**. Com 248px o conteudo util do card era 222px e a ~16px caberiam
     ~24 caracteres por linha -- era isso que o deixava alto e estreito.
     ⚠️ Com 360px o util vai a **334px**, e a mediana dos nomes de cliente do
     quadro (28 caracteres) passa a caber em UMA linha. Os de 42 a 56 ainda
     quebram, e por isso o corte em 2 linhas e o `title` continuam. */
  flex: 0 0 360px;
  background: var(--fundo);
  border: var(--borda-fina) solid var(--borda-forte);
  border-top: 3px solid var(--borda-forte);
  border-radius: var(--r-md);
  box-shadow: var(--sombra-1);
  transition: box-shadow .15s ease;
}
.coluna:hover { box-shadow: var(--sombra-1); }
/* ⚠️ Coluna sem card fica mais apagada, mas NUNCA escondida: o contador é a
   informação dela. */
.coluna--vazia { background: var(--superficie-2); box-shadow: none; }
/* 🚨 O ALVO ACESO: sem retorno visual não há como saber se a coluna aceita o
   solto. ⚠️ E não é só cor -- a borda engrossa, para quem não distingue cor
   também ver. */
.coluna--alvo {
  background: var(--acento-suave, var(--superficie-2));
  outline: 2px dashed var(--acento);
  outline-offset: -2px;
}

.coluna__nome { line-height: 1.3; }

.painel__desde { font-size: var(--txt-xs); color: var(--texto-fraco); }
/* Nota neutra: informa, nao alarma. Ver o comentario no `template`. */
.aviso--nota {
  background: var(--superficie-2);
  border: var(--borda-fina) solid var(--borda);
  color: var(--texto-fraco);
}
.painel__interruptor {
  display: flex; align-items: center; gap: var(--e-1);
  min-height: var(--altura-toque);
  font-size: var(--txt-xs); color: var(--texto-fraco);
  cursor: pointer;
}
/* 🚨 Colapsada fica ESTREITA, não invisível: o contador continua à vista. */
/* ⚠️ A fechada acompanha, mas nao proporcionalmente: ela so mostra o nome
   da etapa e o contador, e 280px ja sobra para o nome mais comprido das 17. */
.coluna--fechada { flex: 0 0 280px; }

.coluna__titulo { margin: 0; font-size: var(--txt-sm); }
.coluna__botao {
  width: 100%;
  min-height: var(--altura-toque);
  display: flex; align-items: center; justify-content: space-between; gap: var(--e-2);
  padding: var(--e-2) var(--e-3);
  border: 0; border-bottom: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md) var(--r-md) 0 0;
  background: var(--superficie-2);
  color: var(--texto);
  font-size: var(--txt-sm); font-weight: var(--peso-forte);
  text-align: left;
  cursor: pointer;
}
.coluna__botao--fixo { cursor: default; }
.coluna--sem-os .coluna__botao { background: var(--acento-suave); color: var(--acento); }
.coluna--sem-situacao .coluna__botao { background: var(--aviso-suave); color: var(--aviso); }
/* Cheio = tem card. Ver o comentário no `template`. */
.coluna__conta {
  background: var(--texto);
  color: var(--superficie);
  border: var(--borda-fina) solid var(--texto);
  border-radius: var(--r-full);
  min-width: 22px;
  padding: 0 var(--e-2);
  font-size: var(--txt-xs);
  font-weight: var(--peso-forte);
  text-align: center;
}
.coluna__conta--zero {
  background: var(--superficie);
  color: var(--texto-apagado);
  border-color: var(--borda-forte);
  font-weight: var(--peso-normal);
}
.coluna__corpo { padding: var(--e-3); display: flex; flex-direction: column; gap: var(--e-2); }
/* 🚨 ALTURA É O QUE FAZ O ALVO EXISTIR. Uma linha de texto não dá onde soltar,
   e era parte de o arrasto "não ir a lugar algum". ⚠️ O tracejado diz, sem
   depender de cor, que ali se pode soltar. */
.coluna__alvo-vazio {
  margin: 0;
  min-height: 72px;
  display: flex; align-items: center; justify-content: center;
  text-align: center;
  padding: var(--e-2);
  border: var(--borda-fina) dashed var(--borda-forte);
  border-radius: var(--r-sm, 6px);
  font-size: var(--txt-xs);
  color: var(--texto-apagado);
}

.card { display: block; }
/* 🔵 O gesto dele. ⚠️ `grab` no card inteiro, e `grabbing` enquanto arrasta. */
.card[draggable="true"] {
  cursor: grab;
  /* 🚨 ESTA LINHA É O QUE FAZ O ARRASTO EXISTIR, e faltava: no Chrome, apertar
     o botão sobre TEXTO SELECIONÁVEL dentro de um `draggable` inicia uma
     SELEÇÃO DE TEXTO, não o arrasto do elemento. O card é todo texto, então
     qualquer ponto onde se tentasse arrastar selecionava palavras.
     ⚠️ E nenhum teste meu pegou: `trigger('dragstart')` é evento sintético --
     prova que o handler está ligado, não que o navegador começa o arrasto. */
  user-select: none;
  -webkit-user-select: none;
}
.card[draggable="true"]:active { cursor: grabbing; }
/* ⚠️ O texto do card volta a ser selecionável DENTRO do card aberto, que é
   onde alguém copia um número de OS. */
.modal__caixa { user-select: text; }
/* Enquanto a escrita no ERP não voltou, o card fica apagado e o select
   desabilitado -- dois cliques seguidos seriam duas escritas. */
.card--movendo { opacity: .55; pointer-events: none; }
.card__mover { display: block; margin-top: var(--e-1); }
.card__mover select {
  width: 100%;
  min-height: var(--altura-toque);
  padding: var(--e-1) var(--e-2);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-sm, 6px);
  background: var(--superficie);
  color: var(--texto-fraco);
  font-size: var(--txt-xs);
}
/* 🚨 O CARD E UMA CAIXA, E AGORA SE VE QUE E. Antes: branco dentro de
   coluna branca, com borda no tom mais claro da paleta -- e por isso ele
   pediu *"evidenciar as limitacoes das caixas, talvez espessura ou
   sombreamento"*. Agora sao tres coisas juntas, e nenhuma delas e cor:
   a coluna recuou para `--fundo`, a borda subiu para `--borda-forte`, e
   entrou `--sombra-1`. ⚠️ A BORDA ESQUERDA DE 3px SAIU do card normal: ela
   trazia a cor da etapa, que e a cor da coluna em que o card ja esta. */
.card__abrir {
  width: 100%;
  min-height: var(--altura-toque);
  display: flex; flex-direction: column; gap: var(--e-2);
  padding: var(--e-3);
  text-align: left;
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda-forte);
  border-radius: var(--r-md);
  box-shadow: var(--sombra-1);
  color: var(--texto);
  cursor: pointer;
}

/* 🔵 A EXCECAO, variante C: a unica cor do card, e ela nunca esta sozinha --
   o tempo da etapa fica ambar e o selo da prioridade vira solido. Quem nao
   distingue a cor le o numero. */
.card__abrir--excecao {
  border-left: 3px solid var(--aviso);
}

/* ⚠️ AS TRES MEDIDAS SECUNDARIAS CAEM NA MESMA BORDA DIREITA ("ha N", "total
   N", "previsao dd/mm"), e e o que ele chamou de realinhar: o olho desce UMA
   coluna em vez de varrer cinco linhas soltas. */
.card__linha {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: var(--e-2); min-width: 0;
}
.card__direita {
  flex: none; white-space: nowrap;
  font-size: var(--txt-xs); color: var(--texto-fraco);
}
/* ⚠️ O tipo e a placa na borda direita podem ser compridos (*"Instalacao
   rastreador"* + 7 placas): aqui a linha PODE cortar, porque o dado inteiro
   esta no card aberto. O que nao pode e empurrar a OS para fora. */
.card__direita--dado {
  min-width: 0; overflow: hidden; text-overflow: ellipsis;
  font-size: var(--txt-sm);
}
.card__ident { display: flex; align-items: baseline; gap: var(--e-2); flex-wrap: wrap; min-width: 0; }
.card__etapa { min-width: 0; }
/* 🚨 `--aviso` (#D97706) da 3,18:1 sobre branco e NAO passa para texto
   pequeno; `--aviso-texto` (#B45309) da 5,02:1. O tom forte fica para a borda,
   texto. */
.card__etapa--parado { color: var(--aviso-texto); font-weight: var(--peso-forte); }

/* 🚨 DUAS LINHAS, e o nome inteiro no `title`: 11 dos 15 nomes do quadro
   passam de 24 caracteres (o maior tem 56). Sem o corte, a razao social comia
   quatro linhas de um card de 248px. */
/* 🔵 O EFEITO QUE ELE PEDIU: o card levanta e ganha sombra na passagem.
   ⚠️ `prefers-reduced-motion` desliga o movimento e mantém a sombra -- quem
   pediu menos movimento no sistema continua vendo que o card responde. */
.card__abrir { transition: box-shadow .15s ease, transform .15s ease, border-color .15s ease; }
.card__abrir:hover {
  background: var(--superficie-2);
  box-shadow: var(--sombra-1);
  transform: translateY(-1px);
}
.card__abrir:active { transform: translateY(0); }
@media (prefers-reduced-motion: reduce) {
  .card__abrir, .coluna { transition: none; }
  .card__abrir:hover { transform: none; }
}

.card__topo { display: flex; align-items: baseline; justify-content: space-between; gap: var(--e-2); }
/* 🚨 O NUMERO DA OS E O BOTAO -- ver o comentario no `template`. Tem cara de
   texto porque o card inteiro ja e clicavel; o que ele garante e o TECLADO. */
.card__os {
  font-size: var(--txt-md);
  font-weight: var(--peso-forte);
  background: none; border: 0; padding: 0;
  color: var(--texto); cursor: pointer; text-align: left;
}
.card__os:focus-visible { outline: 2px solid var(--acento); outline-offset: 2px; }
/* 🔵 ÁREA E — a OS e o termo no mesmo grupo, à esquerda; o "há N dias" fica
   na direita pelo `space-between` do `.card__topo`.
   ⚠️ `min-width: 0` e `flex-wrap`: termo de 5 dígitos em coluna estreita
   quebra para a linha de baixo em vez de empurrar o "há N dias" para fora. */
.card__ident {
  display: flex; align-items: baseline; gap: var(--e-1);
  min-width: 0; flex-wrap: wrap;
}
/* ⚠️ MAIS FRACO QUE O NÚMERO DA OS de propósito: a OS é a identidade com que
   se age (é o botão que abre o card), e o termo é a referência de papel. Os
   dois com o mesmo peso fariam o operador hesitar sobre qual é qual. */
.card__termo { font-size: var(--txt-xs); color: var(--texto-fraco); white-space: nowrap; }

/* 🚨 UMA ROLAGEM, NAO DUAS. Ate 05/11 o `.modal` rolava a pagina inteira
   (`align-items: flex-start` + `overflow-y: auto`) e o `.modal__corpo` rolava
   por dentro: com a roda do mouse sobre o corpo, qual das duas se movia
   dependia de onde o cursor estava. Agora o palco CENTRALIZA e nao rola; quem
   rola e so o corpo. */
.modal {
  position: fixed; inset: 0; z-index: var(--z-modal, 50);
  background: rgba(2, 21, 41, .45);
  display: flex; align-items: center; justify-content: center;
  padding: var(--e-4);
}
/* 🚨 A CAIXA NAO TEM `padding`, e e o que da a hierarquia: cada faixa tem o
   seu, e e isso que faz o topo e o pe terem fundo proprio sem buraco branco nas
   beiradas. Era o que estava feio -- seis secoes soltas com o mesmo peso. */
/* 🚨 ALTURA COM TETO, E O TETO E DA CAIXA -- nao de uma secao de dentro.
   O defeito anterior: `max-height: 60vh` estava no `.modal__corpo`, que
   continha SO a secao dos temas; o checklist, as observacoes e as passagens
   ficavam fora e cresciam sem limite. O comentario dizia que o teto existia
   *"para o pe nao fugir da tela num card com muita observacao"*, e ele
   guardava justo o bloco de tamanho previsivel.
   🔵 1000px (era 820) porque o corpo passou a ter duas colunas. ⚠️ E `100%`
   no `min()` segura a tela estreita. */
.modal__caixa {
  width: min(1000px, 100%);
  max-height: min(900px, 92vh);
  background: var(--superficie);
  /* 🔵 *"evidenciar as limitacoes das caixas, talvez espessura ou
     sombreamento"*: a borda sobe de `--borda` para um tom mais forte e a
     sombra e a de elevacao. */
  border: var(--borda-fina) solid var(--texto-apagado);
  border-radius: var(--r-md);
  box-shadow: var(--sombra-2);
  overflow: hidden;
  display: flex; flex-direction: column;
}
/* ⚠️ O `tabindex="-1"` existe para o foco PODER entrar na caixa ao abrir; ele
   nao deve desenhar um anel quando o foco chega por programa. */
.modal__caixa:focus { outline: none; }
.modal__caixa:focus-visible { outline: 2px solid var(--acento); outline-offset: -2px; }

/* 1. o topo */
/* 🚨 AS TRES FAIXAS DA CAIXA (topo, faixa, pe) TEM BORDA DE 2px, e e o que
   as separa do miolo: com 1px no tom claro, as sete secoes do modal tinham
   todas o mesmo limite e a caixa parecia uma lista. */
.modal__topo {
  flex: none;
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: var(--e-3);
  padding: var(--e-4) var(--e-5);
  border-bottom: 2px solid var(--borda-forte);
}
.modal__quem { min-width: 0; display: flex; flex-direction: column; gap: var(--e-1); }
/* 🔵 O CLIENTE E O TITULO DO MODAL, e vem INTEIRO: e o unico lugar com
   largura para os nomes de 56 caracteres que a base tem. */
.modal__cliente {
  margin: 0; font-size: var(--txt-xl); font-weight: var(--peso-forte);
  line-height: 1.25; letter-spacing: -0.01em;
}
.modal__ident {
  margin: 0; display: flex; align-items: baseline; flex-wrap: wrap;
  gap: var(--e-2);
  font-size: var(--txt-sm); color: var(--texto-fraco);
}
.modal__os { font-size: var(--txt-md); color: var(--acento); }
.modal__termo { color: var(--texto-fraco); }
/* O risco vertical que separa os identificadores -- decoracao, e por isso
   `aria-hidden` no markup. */
.modal__risco {
  width: 1px; height: 13px; background: var(--borda-forte); display: inline-block;
}
.modal__fechar {
  flex: none;
  min-width: var(--altura-toque); min-height: var(--altura-toque);
  border: var(--borda-fina) solid var(--borda); border-radius: var(--r-sm, 6px);
  background: var(--superficie); color: var(--texto); cursor: pointer;
}
.modal__fechar:hover { background: var(--superficie-2); }

/* 2. a faixa das medidas -- a unica com fundo no meio da caixa, de proposito */
.modal__faixa {
  flex: none;
  display: flex; flex-wrap: wrap; gap: var(--e-6);
  align-items: flex-end;
  padding: var(--e-3) var(--e-5);
  background: var(--superficie-2);
  border-bottom: 2px solid var(--borda-forte);
}
/* 🚨 `--aviso` (#D97706) da 3,18:1 sobre o fundo claro e nao passa em texto;
   #B45309 da 5,02:1. */
.faixa__parado { color: var(--aviso-texto); }
.faixa__medida, .faixa__campo { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.faixa__rotulo {
  font-size: var(--txt-xs); color: var(--texto-fraco);
  text-transform: uppercase; letter-spacing: .06em;
}
.faixa__medida strong { font-size: var(--txt-md); }
.faixa__campo select {
  min-height: var(--altura-toque);
  padding: var(--e-1) var(--e-2);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-sm, 6px);
  background: var(--superficie); color: var(--texto); font-size: var(--txt-sm);
}

/* 3. o corpo */
/* 🚨 O UNICO QUE ROLA, e o `min-height: 0` e o que faz isso funcionar:
   sem ele um filho de flex se recusa a encolher abaixo do conteudo, o corpo
   empurra a caixa, e o pe sai da tela -- que era o sintoma que o
   `max-height: 60vh` tentava remediar no lugar errado. */
.modal__corpo {
  flex-grow: 1; min-height: 0; overflow-y: auto;
  padding: var(--e-5);
  background: var(--fundo);
  display: flex; flex-direction: column; gap: var(--e-4);
}
/* 🔵 DUAS COLUNAS: a esquerda e o que se FAZ, a direita e o que se LE.
   ⚠️ `flex-wrap` com base de 320px: em tela estreita elas EMPILHAM, e o
   modal continua usavel -- nao ha largura minima que force rolagem lateral. */
.modal__corpo--duas {
  flex-direction: row; flex-wrap: wrap; align-items: flex-start;
  gap: var(--e-5);
}
.modal__coluna {
  min-width: 0; display: flex; flex-direction: column; gap: var(--e-3);
}
.modal__coluna--fazer { flex: 3 1 320px; }
.modal__coluna--ler { flex: 2 1 280px; }

/* O rotulo que agrupa os paineis de uma coluna. */
.modal__secao {
  margin: 0; font-size: var(--txt-xs); font-weight: var(--peso-forte);
  letter-spacing: .08em; text-transform: uppercase; color: var(--texto-fraco);
}

/* 🚨 CADA BLOCO E UM PAINEL COM BORDA, e isto conserta de uma vez os dois
   defeitos do miolo: o padding (as tres secoes eram filhas diretas da caixa,
   que tem `padding: 0`, e nenhuma definia o seu -- o miolo util ficava rente
   as bordas) e a hierarquia (o proprio CSS admitia por escrito que eram
   *"seis secoes soltas com o mesmo peso"*).
   🔵 *"espessura ou sombreamento"*: borda forte + sombra de 1px, e o
   cabecalho do painel com fundo. */
/* 🚨 AS REGRAS DO PAINEL VIVEM NO FIM DESTE BLOCO, e nao aqui, porque as
   regras antigas de `.modal__recados`/`.modal__log`/`.modal__temas` estao mais
   abaixo com a MESMA especificidade -- e a que vem depois ganha. Escritas aqui,
   o cabecalho do painel caia para `--txt-sm` e o `gap` voltava a `--e-2`.
   Procure por `.modal__painel` no fim da folha de estilo. */

/* 4. o pe */
.modal__rodape {
  flex: none;
  display: flex; flex-wrap: wrap; gap: var(--e-4);
  align-items: flex-end; justify-content: space-between;
  padding: var(--e-4) var(--e-5);
  background: var(--superficie-2);
  border-top: 2px solid var(--borda-forte);
}
/* 🔵 ONDE SE AGE: os dois controles que escrevem no ERP e o aviso que os
   descreve, no MESMO bloco. Antes a frase estava aqui e os controles la em
   cima, na faixa das medidas. */
.modal__agir {
  display: flex; flex-wrap: wrap; align-items: flex-end; gap: var(--e-4);
  min-width: 0;
}
/* 🚨 O AVISO DE ESCRITA SAIU DE `.apagado`: #94A3B8 da **2,56:1** sobre
   branco, e a norma pede 4,5:1 -- o texto menos legivel do modal era
   justamente o que avisa que o gesto chega ao ERP. #B45309 da 5,02:1. */
.modal__perigo {
  margin: 0 0 var(--e-2); max-width: 30ch;
  font-size: var(--txt-sm); color: var(--aviso-texto); line-height: 1.45;
}
.modal__acoes { display: flex; gap: var(--e-2); flex-wrap: wrap; }
.painel__busca input, .painel__ordem select {
  min-height: var(--altura-toque);
  padding: var(--e-1) var(--e-2);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-sm, 6px);
  background: var(--superficie); color: var(--texto);
  font-size: var(--txt-sm);
}
.painel__busca input { min-width: 180px; }
.painel__limpar {
  border: 0; background: none; padding: 0 0 0 var(--e-1);
  color: var(--acento); cursor: pointer; font: inherit;
  text-decoration: underline;
}
.card__tempos { font-size: var(--txt-xs); color: var(--texto-fraco); }
/* ⚠️ Prioridade diferente de Normal fica MARCADA: é exceção, e exceção precisa
   ser vista sem abrir. 🚨 E não só por cor -- o nome está escrito. */
.pilula--forte {
  border-color: var(--aviso, var(--borda-forte));
  color: var(--texto); font-weight: var(--peso-forte);
}
/* 🚨 OS TRES SELOS COM SIGNIFICADO, e cada um tem FUNDO alem da cor: num
   card de 248px com cinco selos possiveis, borda sozinha nao distingue nada a
   um metro de distancia.
   ⚠️ E os dois que alertam diferem em LUMINOSIDADE, nao so em matiz -- ambar
   e verde, nunca vermelho e verde. */
.pilula--alerta {
  color: var(--aviso-texto); background: var(--aviso-suave);
  border-color: var(--aviso); font-weight: var(--peso-forte);
}
.pilula--pronto {
  color: var(--ok-texto); background: var(--ok-suave);
  border-color: var(--ok); font-weight: var(--peso-forte);
}
.pilula--origem {
  color: var(--acento-hover); background: var(--acento-suave);
  border-color: var(--acento-borda);
}
.recados { list-style: none; margin: 0; padding: 0; }
.modal__rodape--escrever { display: grid; gap: var(--e-2); }

/* O diálogo do aviso de etapa é curto: uma frase e o Ok. */
.modal__caixa--curta { max-width: 26rem; }

.check__linha {
  display: flex;
  align-items: flex-start;
  gap: var(--e-2);
  cursor: pointer;
}
.check__linha input { margin: 0; flex: none; }
/* ⚠️ Riscado E esmaecido: cor sozinha não é portador de informação. */
.check__feito { text-decoration: line-through; opacity: .6; }

.modal__recados { display: flex; flex-direction: column; gap: var(--e-2); }
.modal__recados h3 { margin: 0; font-size: var(--txt-sm); }
.modal__recados textarea {
  width: 100%; box-sizing: border-box; padding: var(--e-2);
  border: var(--borda-fina) solid var(--borda); border-radius: var(--r-sm, 6px);
  font: inherit; font-size: var(--txt-sm); resize: vertical;
}
.modal__log h3 { margin: 0 0 var(--e-2); font-size: var(--txt-sm); }
.modal__passagens { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--e-2); }
.modal__passagens li { display: flex; flex-wrap: wrap; gap: var(--e-2); align-items: center; font-size: var(--txt-sm); }
.modal__temas { display: flex; flex-direction: column; gap: var(--e-2); }
.temas__abas { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: var(--e-2); }
.temas__aba {
  text-align: left; min-height: 56px; padding: var(--e-2) var(--e-3);
  border: var(--borda-fina) solid var(--borda); border-radius: var(--r-sm, 6px);
  background: var(--superficie); color: var(--texto); cursor: pointer;
  display: flex; flex-direction: column; gap: 2px;
  transition: border-color .15s ease, box-shadow .15s ease;
}
.temas__aba:hover:not(:disabled) { box-shadow: var(--sombra-1); }
.temas__aba--ativa { border-color: var(--acento); box-shadow: var(--sombra-1); }
/* 🔵 Apagada = "só a partir de Serviço Agendado", e o resumo diz isso. */
.temas__aba--apagada { border-style: dashed; opacity: .65; cursor: not-allowed; }
.temas__resumo { font-size: var(--txt-xs); color: var(--texto-fraco); }
.temas__corpo:empty { display: none; }
.temas__texto {
  margin: 0; white-space: pre-wrap; word-break: break-word;
  font-family: inherit; font-size: var(--txt-sm);
  background: var(--superficie-2); border-radius: var(--r-sm, 6px);
  padding: var(--e-3); max-height: 240px; overflow-y: auto;
}
.temas__respostas { margin: 0; font-size: var(--txt-sm); max-height: 240px; overflow-y: auto; }
.temas__respostas dt { font-size: var(--txt-xs); color: var(--texto-fraco); margin-top: var(--e-2); }
.temas__respostas dd { margin: 0; }
.modal__pe { display: flex; gap: var(--e-2); justify-content: flex-end; flex-wrap: wrap; }

/* ==========================================================================
   O PAINEL DO MODAL -- as tres faixas do mockup que ele validou
   --------------------------------------------------------------------------
   🚨 ESTE BLOCO TEM DE VIR DEPOIS de `.modal__recados`, `.modal__log` e
   `.modal__temas`: as tres tem a mesma especificidade que ele, e na primeira
   tentativa eu as escrevi DEPOIS das minhas -- o cabecalho do painel caiu para
   `--txt-sm`, o `gap` voltou a `--e-2`, e o painel ficou uma caixa de padding
   unico em vez das tres faixas. Foi o que ele viu: *"o layout do card apos o
   clique esta errado"*.

   🔵 *"espessura ou sombreamento"*: borda forte, sombra de 1px, e o cabecalho
   com fundo proprio -- e e a faixa que da a hierarquia, nao o tamanho da fonte.
   ========================================================================== */
.modal__painel {
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda-forte);
  border-radius: var(--r-md);
  box-shadow: var(--sombra-1);
  /* ⚠️ PADDING ZERO: cada faixa tem o seu, e e isso que faz o cabecalho e o pe
     terem fundo proprio sem buraco branco nas beiradas -- a mesma regua da
     `.modal__caixa`. */
  padding: 0;
  gap: 0;
  overflow: hidden;
}

/* A FAIXA DE CIMA. O `h3` ja envolve o titulo e a pilula no markup, entao ele
   e a faixa -- nao precisou de `<div>` novo. */
.modal__painel > h3 {
  display: flex; align-items: center; justify-content: space-between;
  gap: var(--e-2);
  margin: 0;
  padding: var(--e-3) var(--e-4);
  background: var(--superficie-2);
  border-bottom: var(--borda-fina) solid var(--borda-forte);
  font-size: var(--txt-md);
}

/* O MIOLO: tudo o que nao e faixa ganha o respiro lateral.
   🚨 O ESPACO VERTICAL VEM POR VIZINHANCA, E NAO POR TIPO. A primeira versao
   usava `:first-of-type`, que casa o primeiro de CADA tipo de elemento -- num
   painel com `<p>`, `<ul>` e `<div>` isso dava respiro de topo em tres filhos
   ou em nenhum, dependendo de quais `v-if` estivessem ligados naquele card.
   `h3 + *` e `* + *` nao dependem do tipo nem de quantos existem. */
.modal__painel > :not(h3):not(.modal__painel-pe) {
  margin-left: var(--e-4);
  margin-right: var(--e-4);
}
/* o que vem logo depois da faixa de cima */
.modal__painel > h3 + :not(.modal__painel-pe) { margin-top: var(--e-3); }
/* o espaco ENTRE os blocos do miolo */
.modal__painel > :not(h3) + :not(h3):not(.modal__painel-pe) { margin-top: var(--e-3); }
/* ⚠️ E o respiro de baixo so quando nao ha faixa de pe: com ela, o pe encosta
   na borda de proposito -- e faixa, nao conteudo. */
.modal__painel > :not(.modal__painel-pe):last-child { margin-bottom: var(--e-4); }

/* A FAIXA DE BAIXO: a frase de regra, que antes abria o bloco e empurrava o
   assunto para baixo.
   🚨 E ela NAO usa `.nota`: o texto que diz *"nao vai para a OS do Harmonit"*
   e o que impede alguem de escrever pensando que o tecnico vai ler, e tem de
   ser legivel -- `--texto-fraco` da 4,76:1. */
.modal__painel-pe {
  margin: 0;
  padding: var(--e-3) var(--e-4);
  background: var(--fundo);
  border-top: var(--borda-fina) solid var(--borda-forte);
  font-size: var(--txt-sm);
  color: var(--texto-fraco);
}
.modal__painel-pe strong { color: var(--texto); }
/* ⚠️ A caixa agora rola no `modal__corpo`, então o modal alinha ao topo e
   a sombra do mockup fica visível na beirada. */
/* 🚨 A REGRA QUE ALINHAVA O MODAL AO TOPO SAIU EM 05/11. Ela existia porque
   a caixa nao tinha teto de altura e precisava crescer para baixo, deixando a
   pagina rolar. Agora a caixa tem `max-height` e so o corpo rola, entao o
   dialogo e centralizado e o pe esta sempre visivel.
   ⚠️ O que fica e so o respiro lateral em tela estreita. */
.modal { padding: var(--e-4) var(--e-3); }
.card__ha { font-size: var(--txt-xs); color: var(--texto-fraco); }
/* 🔵 O CLIENTE E A PRIMEIRA LINHA e o maior texto do card (variante C):
   e por ele que a operacao pensa, e os identificadores vem depois.
   🚨 CORTA EM DUAS LINHAS: medido em 05/11, **11 dos 15** nomes do quadro
   passam de 24 caracteres (mediana 28, o maior 56 -- *"TGS RIO ALUGUEL DE
   CACAMBAS E RECICLAGEM DE ENTULHO LTDA"*). O nome inteiro fica no `title` e
   no modal, que tem 1000px para ele. */
.card__cliente {
  font-size: var(--txt-md);
  font-weight: var(--peso-forte);
  line-height: 1.3;
  min-width: 0;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.card__cliente--sem {
  font-size: var(--txt-sm);
  font-weight: var(--peso-normal);
  /* ⚠️ Isto nao e apoio, e uma falta de cadastro: fica em ambar legivel, nao
     em cinza de rodape. */
  color: var(--aviso-texto); font-style: italic;
  -webkit-line-clamp: 3;
}
.card__tipo { font-size: var(--txt-xs); color: var(--texto-fraco); }
/* ⚠️ ERA UMA CAIXINHA CINZA, e virou texto: com a caixa, as linhas do tipo
   e dos tempos competiam com os SELOS, que sao as caixinhas de verdade do
   card. Dois niveis de caixa num card de 248px nao tem como se distinguir. */
.card__dado {
  font-size: var(--txt-sm);
  color: var(--texto-fraco);
  min-width: 0;
}
.card__pistas { display: flex; flex-wrap: wrap; gap: var(--e-1); align-items: center; margin-top: var(--e-1); }
/* 🚨 SAIU DE `--texto-apagado`: #94A3B8 sobre branco da **2,56:1**, e a
   norma pede 4,5:1 para texto pequeno. `--texto-fraco` da 4,76:1. */
.card__visto { font-size: var(--txt-xs); color: var(--texto-fraco); }
/* 🚨 Aviso, não decoração: ver o comentário no `template`. */
.card__alerta { font-size: var(--txt-xs); color: var(--erro); font-weight: var(--peso-forte); }

/* 🚨 A `.nota` SUBSTITUI A `.apagado` NESTA TELA, e e conserto de norma, nao
   de gosto: a `.apagado` global usa `--texto-apagado` (#94A3B8), que sobre
   branco da **2,56:1** -- a norma pede 4,5:1 para texto pequeno, e a classe
   carregava justamente as frases de REGRA do modal (*"Nao vai para a OS do
   Harmonit"*, *"Mover de etapa escreve a situacao na OS"*), o autor e a hora
   de cada item marcado, e os *"sem solucao tecnica escrita"*. `--texto-fraco`
   (#64748B) da **4,76:1** e e o tom que a `.pilula` ja usava.
   ⚠️ O TOKEN GLOBAL NAO FOI TOCADO: mexer nele mudaria ~30 telas que
   ninguem auditou, e isso e decisao dele -- esta escrito como a decisao 7 do
   `Painel_Operacao_Card_e_Modal_DESIGN.md`. */
.nota { color: var(--texto-fraco); }

.pilula {
  font-size: var(--txt-xs);
  color: var(--texto-fraco);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-full);
  padding: 0 var(--e-2);
}

.etiqueta { padding: 0 var(--e-2); border-radius: var(--r-full); font-size: var(--txt-xs); border: var(--borda-fina) solid var(--borda); }
.etiqueta--nova { background: var(--acento-suave); border-color: var(--acento-borda); color: var(--acento); }
/* 🚨 OS DOIS TONS FORTES NAO PASSAVAM EM TEXTO PEQUENO: `--aviso` (#D97706)
   da 3,18:1 e `--ok` (#16A34A) da 2,78:1 sobre os respectivos fundos claros.
   Os tons escuros da mesma familia passam, e a cor de borda continua a de
   antes -- entao a aparencia muda pouco e a leitura muda muito. */
.etiqueta--em_andamento { background: var(--aviso-suave); border-color: var(--aviso); color: var(--aviso-texto); }
.etiqueta--concluida { background: var(--ok-suave); border-color: var(--ok-borda); color: var(--ok-texto); }
</style>
