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
function dia(iso) {
  if (!iso) return '—'
  const [a, m, d] = String(iso).split('-')
  return (d && m && a) ? `${d}/${m}/${a}` : iso
}

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    quadro.value = await api.get(
      `/api/paineis/operacao?so_abertas=${soAbertas.value ? 1 : 0}`)
    for (const coluna of quadro.value.colunas) {
      /* Vazia nasce fechada; com card, aberta. ⚠️ Nenhuma é fixa desde
         29/10 -- as duas que não eram situação saíram do painel. */
      abertas.value[coluna.chave] = coluna.total > 0
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

function comecarArrasto(card, evento) {
  if (!quadro.value?.pode_mover) return
  arrastando.value = card
  /* ⚠️ `move` e não `copy`: o cursor tem de dizer que isto MOVE. */
  if (evento.dataTransfer) {
    evento.dataTransfer.effectAllowed = 'move'
    /* Alguns navegadores exigem algum dado para iniciar o arrasto. */
    evento.dataTransfer.setData('text/plain', String(card.numero_ordem || ''))
  }
}

function terminarArrasto() {
  arrastando.value = null
}

async function soltarNaColuna(coluna) {
  const card = arrastando.value
  arrastando.value = null
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
    <header class="tela__cabecalho">
      <div>
        <h1>Operação</h1>
        <AjudaDaTela>
          As solicitações dos formulários da <strong>Operação</strong> (Suporte,
          Demonstração, Teste gratuito e Credenciamento técnico), em colunas
          nas <strong>17 situações da OS no Harmonit</strong>, na ordem do
          fluxo da operação. A OS nasce junto com o chamado, na primeira
          situação.
        </AjudaDaTela>
      </div>
      <button class="botao botao--contorno" type="button" @click="carregar">Atualizar</button>

        <!-- 🔵 D9 dele: a data matriz. A tela DIZ desde quando está montando,
             porque "o painel está vazio" e "o painel começa em 24/10" são
             respostas diferentes para a mesma tela vazia.
             ⚠️ Mudar a data é do OWNER (a rota recusa com 403), e por isso
             aqui ela é só TEXTO -- botão que o servidor recusa é pior que
             botão nenhum. -->
        <span v-if="quadro" class="painel__desde">
          desde {{ dia(quadro.desde) }}
        </span>

        <!-- 🚨 O INTERRUPTOR DAS FINALIZADAS, e o motivo de ele existir é
             medido: com ele ligado o Financeiro cai de 6 para 2 cards, porque
             OS financeira nasce `Finalizado`. Sem o interruptor, quem procura
             uma OS finalizada concluiria que ela não existe. -->
        <label class="painel__interruptor">
          <input type="checkbox" v-model="soAbertas" @change="carregar">
          <span>só as abertas</span>
        </label>
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
                    'coluna--vazia': !coluna.total }"
          :style="{ borderTopColor: corDaEtapa(indice) }"
          :aria-label="coluna.titulo"
          @dragover.prevent
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
                   @click="abrirCard(card)">
                <span class="card__topo">
                  <button class="card__os" type="button"
                          @click.stop="abrirCard(card)">OS {{ card.numero_ordem || card.os_id }}</button>
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

            <p v-if="!coluna.cards.length" class="apagado pequeno">Vazia.</p>
          </div>
        </section>
      </div>

      <!-- ================= O CARD ABERTO ================= -->
      <div v-if="cardAberto" class="modal" role="dialog" aria-modal="true"
           :aria-label="`OS ${cardAberto.numero_ordem}`"
           @click.self="fecharCard">
        <div class="modal__caixa">
          <header class="modal__topo">
            <div>
              <strong class="modal__os">OS {{ cardAberto.numero_ordem }}</strong>
              <p class="modal__cliente">
                {{ cardAberto.cliente || `cliente ${cardAberto.cliente_id || '?'}, fora do nosso cadastro` }}
              </p>
            </div>
            <button class="botao botao--contorno" type="button"
                    aria-label="Fechar" @click="fecharCard">✕</button>
          </header>

          <dl class="modal__dados">
            <div>
              <dt>Etapa agora</dt>
              <dd>{{ nomeDaSituacao(cardAberto.situacao_id) }}</dd>
            </div>
            <div>
              <dt>Tipo</dt>
              <dd>{{ cardAberto.tipo_nome || '—' }}</dd>
            </div>
            <div>
              <dt>Status no ERP</dt>
              <dd>{{ cardAberto.status_str || '—' }}</dd>
            </div>
            <div>
              <dt>Aberta</dt>
              <dd>{{ quando(cardAberto.criada_em) }}</dd>
            </div>
            <div v-if="cardAberto.placas && cardAberto.placas.length">
              <dt>Placas</dt>
              <dd>{{ cardAberto.placas.map((p) => p.placa).join(' · ') }}</dd>
            </div>
            <div v-if="cardAberto.tecnicos && cardAberto.tecnicos.length">
              <dt>Técnico</dt>
              <dd>
                {{ cardAberto.tecnicos.map((t) => t.nome || `usuário ${t.usuario_id}`).join(' · ') }}
              </dd>
            </div>
          </dl>

          <!-- mover, do próprio modal -->
          <div v-if="quadro.pode_mover && cardAberto.numero_ordem"
               class="modal__mover">
            <label>
              <span>Mover para</span>
              <select :value="cardAberto.situacao_id"
                      :disabled="movendo === cardAberto.numero_ordem"
                      @change="moverDoModal(Number($event.target.value))">
                <option v-for="c in quadro.colunas" :key="c.chave"
                        :value="c.situacao_id">{{ c.titulo }}</option>
              </select>
            </label>
          </div>

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

          <footer class="modal__pe">
            <button v-if="cardAberto.id" class="botao botao--contorno"
                    type="button" @click="verNaFRM(cardAberto)">
              Ver o chamado em Solicitações
            </button>
            <button class="botao" type="button" @click="fecharCard">Fechar</button>
          </footer>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.tela__cabecalho { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--e-3); margin-bottom: var(--e-4); }
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
.modal__caixa {
  width: min(760px, 100%);
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda-forte);
  border-radius: var(--r-md);
  box-shadow: var(--sombra-2);
  padding: var(--e-4);
  display: flex; flex-direction: column; gap: var(--e-3);
}
.modal__topo { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--e-3); }
.modal__os { font-size: var(--txt-lg, 18px); }
.modal__cliente { margin: 2px 0 0; font-size: var(--txt-sm); color: var(--texto-fraco); }
.modal__dados { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: var(--e-3); margin: 0; }
.modal__dados dt { font-size: var(--txt-xs); color: var(--texto-fraco); text-transform: uppercase; letter-spacing: .04em; }
.modal__dados dd { margin: 2px 0 0; font-size: var(--txt-sm); }
.modal__mover select {
  min-height: var(--altura-toque); margin-left: var(--e-2);
  padding: var(--e-1) var(--e-2);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-sm, 6px);
  background: var(--superficie); color: var(--texto);
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
