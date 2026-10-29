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
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api, ErroDeApi } from '../api/cliente.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'

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
  cardAberto.value = card
  passagens.value = []
  ficha.value = null
  erroDaFicha.value = ''
  temaAberto.value = 'descricao'
  recado.value = ''
  erroDoRecado.value = ''
  if (!card.numero_ordem) return

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

async function salvarObservacao() {
  const c = cardAberto.value
  if (!c?.numero_ordem || !recado.value.trim()) return
  salvando.value = true
  erroDoRecado.value = ''
  try {
    const r = await api.post('/api/paineis/operacao/observacao', {
      numero_os: c.numero_ordem,
      texto: recado.value.trim(),
    })
    /* ⚠️ A lista volta do servidor, não é montada aqui: a hora e o autor são
       dele, e inventá-los na tela criaria duas verdades. */
    if (ficha.value) ficha.value.observacoes = r.observacoes || []
    recado.value = ''
    /* O contador do card fechado também muda. */
    await carregar()
  } catch (e) {
    erroDoRecado.value = e instanceof ErroDeApi
      ? e.message : 'Não consegui salvar a observação.'
  } finally {
    salvando.value = false
  }
}

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

   ⚠️ UMA CAIXA SÓ para os três campos: quem procura tem um número ou um nome na
   mão e não quer decidir em qual caixa ele vai. A tela diz ONDE casou.
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

onMounted(carregar)
</script>

<template>
  <div class="tela">
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
             quer decidir em qual caixa ele vai. -->
        <label class="painel__busca">
          <span class="so-leitor">Procurar por cliente, número da OS ou placa</span>
          <input type="search" v-model="busca" @input="buscarComCalma"
                 placeholder="cliente, OS ou placa">
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
    <p v-if="carregando" class="apagado">Lendo…</p>

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
            <p v-if="coluna.nota" class="apagado pequeno">{{ coluna.nota }}</p>
            <p v-if="coluna.situacao_id" class="apagado pequeno">
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
                   :style="{ borderLeftColor: corDaEtapa(indice) }"
                   @click="cliqueNoCard(card)">
                <span class="card__topo">
                  <button class="card__os" type="button"
                          @click.stop="cliqueNoCard(card)">OS {{ card.numero_ordem || card.os_id }}</button>
                  <span v-if="ha(card.criada_em)" class="card__ha">
                    {{ ha(card.criada_em) }}
                  </span>
                </span>

                <span v-if="card.cliente" class="card__cliente">{{ card.cliente }}</span>
                <!-- ⚠️ Cliente sem nome é DITO, não deixado em branco: o
                     `harmonit_id` da OS pode não estar no nosso cadastro. Hoje
                     os 9 clientes das OS estão todos lá, e por isso esta linha
                     não aparece -- mas basta uma OS de cliente novo. -->
                <span v-else class="card__cliente card__cliente--sem">
                  cliente {{ card.cliente_id || '?' }}, fora do nosso cadastro
                </span>

                <span v-if="card.tipo_nome" class="card__tipo">{{ card.tipo_nome }}</span>

                <!-- As placas da OS, que só a ponte sabe. -->
                <span v-if="card.placas && card.placas.length" class="card__dado">
                  {{ card.placas.map((p) => p.placa).join(' · ') }}
                </span>

                <span class="card__pistas">
                  <!-- 🔵 O NOME da situação, não o número: *"obviamente deve
                       ser o texto da situacao real"*. 🚨 Eu havia invertido a
                       régua da casa -- o valor cru é a EXCEÇÃO, para a situação
                       que não está nas 17 (como o `0`, que existe em 129 OS), e
                       o `nomeDaSituacao` devolve o cru só nesse caso. -->
                  <span class="pilula">{{ nomeDaSituacao(card.situacao_id) }}</span>

                  <span v-if="card.origem === 'erp'" class="pilula">Harmonit</span>
                  <span v-else-if="card.formulario" class="pilula">{{ card.formulario }}</span>

                  <span v-if="card.estado" class="etiqueta"
                        :class="`etiqueta--${card.estado}`">
                    {{ ROTULO_ESTADO[card.estado] || card.estado }}
                  </span>

                  <span v-if="card.anexos" class="pilula">
                    {{ card.anexos }} anexo(s)
                  </span>

                  <!-- 🔵 *"a prioridade vem escrita porque ela nasce Normal e
                       mudar é exceção, e exceção precisa estar visível sem
                       abrir"*. ⚠️ Nula = a varredura ainda não releu esta OS
                       desde 29/10, e aí a pílula não aparece — em vez de
                       inventar "Normal". -->
                  <span v-if="card.prioridade_nome" class="pilula"
                        :class="{ 'pilula--forte': card.prioridade !== 382 }">
                    {{ card.prioridade_nome }}
                  </span>

                  <!-- 🔵 Bloco F: só o NÚMERO de recados; o texto é no card
                       aberto, senão a coluna cresce sem limite. -->
                  <span v-if="card.observacoes" class="pilula">
                    {{ card.observacoes }} observação(ões)
                  </span>
                </span>

                <!-- 🔵 BLOCO C — OS DOIS TEMPOS. ⚠️ "não medido" quando não há
                     passagem: a `os_passagem` começou em 29/10, e a OS pode
                     estar na etapa desde setembro. -->
                <!-- 🔵 Ele: *"os cards tem informação da data dos prazos da
                     OS, não?"*. 🚨 MEDIDO: a OS do Harmonit tem UM campo de
                     data, `dataPrevisao`, e NÃO existe campo de prazo -- na
                     17055, criada em 29/10, a previsão é 29/10 11:40:19, o
                     mesmo minuto. Então a data entra com o nome que o ERP lhe
                     dá, e chamá-la de "prazo" seria a tela afirmando o que o
                     ERP não diz. 🔵 Isso muda quando a frente do aviso prévio
                     entrar: ela vai mover a previsão em +90 dias. -->
                <span v-if="card.criada_em" class="card__data">
                  prazo {{ dataCurta(card.criada_em) }}
                </span>

                <span class="card__tempos">
                  <template v-if="duracao(card.etapa_desde)">
                    nesta etapa <strong>{{ duracao(card.etapa_desde) }}</strong>
                  </template>
                  <template v-else>
                    nesta etapa <strong>não medido</strong>
                  </template>
                  <template v-if="duracao(card.criada_em)">
                    · total {{ duracao(card.criada_em) }}
                  </template>

                  <!-- 🚨 FINALIZADA É AVISO, não decoração: ela só aparece com
                       o interruptor desligado, e sem esta marca ficaria
                       indistinguível de uma OS viva na mesma coluna. -->
                  <span v-if="card.finalizada" class="card__alerta">finalizada</span>
                </span>

                <!-- ⚠️ Quando este dado foi lido do ERP. A varredura roda a
                     cada 5 min, e a tela não pode deixar supor que é agora. -->
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

      <!-- ================= O CARD ABERTO ================= -->
      <div v-if="cardAberto" class="modal" role="dialog" aria-modal="true"
           :aria-label="`OS ${cardAberto.numero_ordem}`"
           @click.self="fecharCard">
        <div class="modal__caixa">
          <!-- 1. O TOPO: quem é esta OS, e o fechar. -->
          <header class="modal__topo">
            <div class="modal__quem">
              <strong class="modal__os">OS {{ cardAberto.numero_ordem }}</strong>
              <p class="modal__cliente">
                {{ cardAberto.cliente || `cliente ${cardAberto.cliente_id || '?'}, fora do nosso cadastro` }}
              </p>
              <p class="modal__sub">
                {{ cardAberto.tipo_nome || 'tipo não lido' }}
                <template v-if="cardAberto.placas && cardAberto.placas.length">
                  · {{ cardAberto.placas.map((p) => p.placa).join(' · ') }}
                </template>
                · aberta {{ quando(cardAberto.criada_em) }}
              </p>
            </div>
            <button class="modal__fechar" type="button"
                    aria-label="Fechar" @click="fecharCard">✕</button>
          </header>

          <!-- 2. A FAIXA: o que responde "o que está parado e há quanto
               tempo", mais as duas ações de estado. É a hierarquia do mockup —
               esta faixa tem fundo e o resto não. -->
          <div class="modal__faixa">
            <div class="faixa__medida">
              <span class="faixa__rotulo">Etapa agora</span>
              <strong>{{ nomeDaSituacao(cardAberto.situacao_id) }}</strong>
            </div>
            <div class="faixa__medida">
              <span class="faixa__rotulo">Nesta etapa</span>
              <!-- 🔵 Bloco C. ⚠️ "não medido" quando não há passagem: a
                   `os_passagem` começou em 29/10. -->
              <strong>{{ duracao(cardAberto.etapa_desde) || 'não medido' }}</strong>
            </div>
            <div class="faixa__medida">
              <span class="faixa__rotulo">Total da OS</span>
              <strong>{{ duracao(cardAberto.criada_em) || '—' }}</strong>
            </div>
            <div class="faixa__medida">
              <span class="faixa__rotulo">Status no ERP</span>
              <strong>{{ cardAberto.status_str || '—' }}</strong>
            </div>
            <!-- 🚨 "Previsão" é o nome do campo no ERP, e hoje ela É a data de
                 criação -- a ressalva está escrita para ninguém a tomar por
                 prazo de entrega. -->
            <div class="faixa__medida">
              <span class="faixa__rotulo">Previsão de entrega</span>
              <strong>{{ quando(cardAberto.criada_em) }}</strong>
              <span class="faixa__nota">hoje igual à abertura</span>
            </div>

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
          </div>

          <!-- ============ A OBSERVAÇÃO (Bloco F) ============ -->
          <section class="modal__recados">
            <h3>Observação do painel</h3>
            <!-- 🚨 O que esta caixa NÃO é: ela não vai para a OS. Dizer isso
                 evita que alguém escreva aqui pensando que o técnico vai ler. -->
            <p class="apagado pequeno">
              Fica no MoviZap, com autor e hora. <strong>Não vai para a OS</strong>
              do Harmonit, e não se apaga.
            </p>
            <textarea v-model="recado" rows="2" :disabled="salvando"
                      placeholder="o que a operação precisa saber sobre esta OS"
                      aria-label="Escrever observação do painel"></textarea>
            <div class="modal__pe">
              <button class="botao" type="button"
                      :disabled="salvando || !recado.trim()"
                      @click="salvarObservacao">Salvar observação</button>
            </div>
            <p v-if="erroDoRecado" class="aviso aviso--erro" role="alert">
              {{ erroDoRecado }}
            </p>

            <ul v-if="ficha && ficha.observacoes && ficha.observacoes.length"
                class="modal__passagens">
              <li v-for="o in ficha.observacoes" :key="o.id">
                <span class="apagado pequeno">{{ quando(o.em) }}</span>
                <span>{{ o.texto }}</span>
                <span class="pilula">{{ o.quem || 'sem autor' }}</span>
              </li>
            </ul>
            <p v-else-if="ficha" class="apagado pequeno">
              Nenhuma observação ainda.
            </p>
          </section>

          <!-- 🔵 *"deve ter o log de quem faz o que SEMPRE"* -- e aqui ele é
               LIDO. Um log que ninguém consegue ler não cumpre o pedido. -->
          <section class="modal__log">
            <h3>Passagens de etapa</h3>
            <p v-if="lendoPassagens" class="apagado pequeno">Lendo…</p>
            <!-- 🚨 O HARMONIT NÃO REGISTRA SITUAÇÃO na linha do tempo: este log
                 é nosso, e começou a existir em 29/10. Dizer isso é o que
                 impede a tela de parecer que a OS nunca se moveu. -->
            <p v-else-if="!passagens.length" class="apagado pequeno">
              Nenhuma passagem registrada. O Harmonit não guarda a situação na
              linha do tempo — este log é nosso e começou em 29/10, então OS
              movida antes disso não aparece aqui.
            </p>
            <ul v-else class="modal__passagens">
              <li v-for="p in passagens" :key="p.id">
                <span class="apagado pequeno">{{ quando(p.em) }}</span>
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

          <!-- ================= OS QUATRO TEMAS (Bloco E) ================= -->
          <!-- 🔵 Ele: *"onde estão os temas do card, após clicar?"*. São os
               quatro do mockup, e vêm da OS LIDA AO VIVO no ERP -- `descricao`
               e `solucaoTecnica` não existem no cache. -->
          <!-- 3. O CORPO. -->
          <div class="modal__corpo">
          <section class="modal__temas">
            <p v-if="lendoFicha" class="apagado pequeno">Lendo a OS no Harmonit…</p>
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
                <p v-if="t.vazio" class="apagado pequeno">{{ t.resumo }}</p>

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

                <p v-else class="apagado pequeno">{{ t.resumo }}</p>
              </template>
            </div>
          </section>

          </div><!-- /modal__corpo -->

          <!-- 4. O PÉ, com fundo como no mockup. -->
          <footer class="modal__rodape">
            <span class="apagado pequeno">
              Mover de etapa escreve a situação na OS do Harmonit.
            </span>
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
.coluna {
  flex: 0 0 248px;
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-top: 3px solid var(--borda-forte);
  border-radius: var(--r-md);
  transition: box-shadow .15s ease;
}
.coluna:hover { box-shadow: var(--sombra-1); }
/* ⚠️ Coluna sem card fica mais apagada, mas NUNCA escondida: o contador é a
   informação dela. */
.coluna--vazia { background: var(--superficie-2); }
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
.coluna--fechada { flex: 0 0 210px; }

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
.card__abrir {
  width: 100%;
  min-height: var(--altura-toque);
  display: flex; flex-direction: column; gap: 2px;
  padding: var(--e-3);
  text-align: left;
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-left: 3px solid var(--acento);
  border-radius: var(--r-md);
  color: var(--texto);
  cursor: pointer;
}
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

.modal {
  position: fixed; inset: 0; z-index: 50;
  background: rgba(2, 21, 41, .45);
  display: flex; align-items: flex-start; justify-content: center;
  padding: var(--e-4); overflow-y: auto;
}
/* 🚨 A CAIXA NAO TEM `padding`, e e o que da a hierarquia: cada faixa tem o
   seu, e e isso que faz o topo e o pe terem fundo proprio sem buraco branco nas
   beiradas. Era o que estava feio -- seis secoes soltas com o mesmo peso. */
.modal__caixa {
  width: min(820px, 100%);
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda-forte);
  border-radius: var(--r-md);
  box-shadow: var(--sombra-2);
  overflow: hidden;
  display: flex; flex-direction: column;
}

/* 1. o topo */
.modal__topo {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: var(--e-3);
  padding: var(--e-3) var(--e-4);
  border-bottom: var(--borda-fina) solid var(--borda);
}
.modal__quem { min-width: 0; }
.modal__os { font-size: var(--txt-lg, 18px); }
.modal__cliente { margin: 2px 0 0; font-size: var(--txt-md); font-weight: var(--peso-forte); }
.modal__sub { margin: 2px 0 0; font-size: var(--txt-xs); color: var(--texto-fraco); }
.modal__fechar {
  flex: none;
  min-width: var(--altura-toque); min-height: var(--altura-toque);
  border: var(--borda-fina) solid var(--borda); border-radius: var(--r-sm, 6px);
  background: var(--superficie); color: var(--texto); cursor: pointer;
}
.modal__fechar:hover { background: var(--superficie-2); }

/* 2. a faixa das medidas -- a unica com fundo no meio da caixa, de proposito */
.modal__faixa {
  display: flex; flex-wrap: wrap; gap: var(--e-4);
  align-items: flex-end;
  padding: var(--e-3) var(--e-4);
  background: var(--superficie-2);
  border-bottom: var(--borda-fina) solid var(--borda);
}
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
.modal__corpo {
  padding: var(--e-4);
  display: flex; flex-direction: column; gap: var(--e-4);
  /* ⚠️ A caixa inteira rola na pagina; o corpo tem teto para o pe nao fugir
     da tela num card com muita observacao. */
  max-height: 60vh; overflow-y: auto;
}

/* 4. o pe */
.modal__rodape {
  display: flex; flex-wrap: wrap; gap: var(--e-3);
  align-items: center; justify-content: space-between;
  padding: var(--e-3) var(--e-4);
  background: var(--superficie-2);
  border-top: var(--borda-fina) solid var(--borda);
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
/* ⚠️ A caixa agora rola no `modal__corpo`, então o modal alinha ao topo e
   a sombra do mockup fica visível na beirada. */
.modal { align-items: flex-start; padding: var(--e-4) var(--e-3); }
.card__ha { font-size: var(--txt-xs); color: var(--texto-fraco); }
.card__cliente { font-size: var(--txt-sm); font-weight: var(--peso-forte); }
.card__cliente--sem { font-weight: var(--peso-normal); color: var(--texto-fraco); font-style: italic; }
.card__tipo { font-size: var(--txt-xs); color: var(--texto-fraco); }
.card__dado {
  align-self: flex-start;
  font-size: var(--txt-xs);
  background: var(--superficie-3, var(--superficie-2));
  border-radius: var(--r-sm, 6px);
  padding: 2px var(--e-1);
}
.card__pistas { display: flex; flex-wrap: wrap; gap: var(--e-1); align-items: center; margin-top: var(--e-1); }
.card__visto { font-size: var(--txt-xs); color: var(--texto-apagado); }
/* 🚨 Aviso, não decoração: ver o comentário no `template`. */
.card__alerta { font-size: var(--txt-xs); color: var(--erro); font-weight: var(--peso-forte); }

.pilula {
  font-size: var(--txt-xs);
  color: var(--texto-fraco);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-full);
  padding: 0 var(--e-2);
}

.etiqueta { padding: 0 var(--e-2); border-radius: var(--r-full); font-size: var(--txt-xs); border: var(--borda-fina) solid var(--borda); }
.etiqueta--nova { background: var(--acento-suave); border-color: var(--acento-borda); color: var(--acento); }
.etiqueta--em_andamento { background: var(--aviso-suave); border-color: var(--aviso); color: var(--aviso); }
.etiqueta--concluida { background: var(--ok-suave); border-color: var(--ok-borda); color: var(--ok); }
</style>
