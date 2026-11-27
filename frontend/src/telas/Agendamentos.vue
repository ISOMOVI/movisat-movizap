<script setup>
/* ============================================================================
   ATD_7.1 — Agendamentos. 🔵 Decisão 14 dele (19/10): é TELA, em Atendimento,
   **aberta a todo atendente**.
   ----------------------------------------------------------------------------
   🚨 ESTA TELA DIZ A COBERTURA DELA. Só aparece aqui o que foi agendado pelo
   MoviZap — serviço combinado por fora, ou marcado direto no Harmonit, não
   existe nesta lista. Mesma régua da faixa da aba Ligações: ausência não pode
   parecer "não tem".

   🚨 NÃO É O `agenda.py` DA TELA INÍCIO. Aquele é a agenda do Google e o topo
   dele diz, desde que nasceu, que não é um calendário — virar calendário faria
   a Início deixar de ser "o que precisa de você". O calendário é aqui.
   ----------------------------------------------------------------------------
   26/11 — A TABELA DE 10 COLUNAS VIROU CARTÃO POR COMPROMISSO. 🔵 Escolha dele
   entre três mockups. O que mudou e por quê:

   · a célula de "Ações" tinha 4 botões e ia receber o 5º ("Ir para o card").
     Numa tabela de 10 colunas isso empurrava tudo para fora da tela em
     qualquer monitor de 1366, e em celular era inutilizável.
   · **cartão fechado = o que decide** (hora, cliente, estado, o selo do
     Harmonit, `NOVO`/`Visto`); **aberto = o detalhe e as 5 ações**.
   · o painel de reenvio, que nascia no PÉ DA TABELA, passa a abrir DENTRO do
     cartão clicado — antes ele aparecia longe da linha que o gerou.

   🚨 NENHUMA REGRA DE NEGÓCIO MUDOU NESTA VOLTA. Cancelar continua exigindo
   motivo, reagendar continua mandando ISO, reenviar continua não enviando, e o
   agrupamento dos irmãos é o mesmo. O que mudou é a forma.
   ============================================================================ */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api } from '../api/cliente.js'
import { codigosPermitidos } from '../estado/sessao.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'
import CalendarioMes from '../componentes/CalendarioMes.vue'
import { agrupar, chaveDoGrupo, dataBr, textosDoGrupo } from '../util/mensagem_agendamento.js'

const router = useRouter()

const agendamentos = ref([])
const carregando = ref(true)
const erro = ref('')
const acaoErro = ref('')

/* O carrossel: ontem, hoje e os 5 próximos — os 7 dias que ele pediu. */
const DIAS_ANTES = 1
const DIAS_DEPOIS = 5

function iso(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const hoje = new Date()
const ancora = ref(iso(hoje))
const selecionado = ref(iso(hoje))

const dias = computed(() => {
  const base = new Date(`${ancora.value}T12:00:00`)
  const lista = []
  for (let i = -DIAS_ANTES; i <= DIAS_DEPOIS; i += 1) {
    const d = new Date(base)
    d.setDate(base.getDate() + i)
    lista.push({
      iso: iso(d),
      dia: d.getDate(),
      mes: d.toLocaleDateString('pt-BR', { month: 'short' }).replace('.', ''),
      semana: d.toLocaleDateString('pt-BR', { weekday: 'short' }).replace('.', ''),
      hoje: iso(d) === iso(hoje),
    })
  }
  return lista
})

const doDia = computed(() =>
  agendamentos.value.filter((a) => (a.inicio || '').slice(0, 10) === selecionado.value))

/* Quantos por dia, para o carrossel marcar os dias com serviço — um ponto no
   dia vazio e um no dia cheio seria a mesma tela para casos diferentes. */
const porDia = computed(() => {
  const conta = {}
  for (const a of agendamentos.value) {
    if (a.estado === 'cancelado') continue
    const d = (a.inicio || '').slice(0, 10)
    conta[d] = (conta[d] || 0) + 1
  }
  return conta
})

const ROTULO_ESTADO = {
  rascunho: 'Rascunho',
  aguardando: 'Aguardando confirmação',
  confirmado: 'Confirmado',
  cancelado: 'Cancelado',
}

function hora(valor) {
  if (!valor) return '—'
  return new Date(valor).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

function placas(a) {
  const comPlaca = (a.ordens || []).filter((o) => o.placa).map((o) => o.placa)
  // ⚠️ Só 236 das 572 OS têm oficina, e é dela que sai a placa. Dizer o
  // porquê é diferente de desenhar uma coluna em branco.
  if (!comPlaca.length) return 'sem placa registrada'
  return comPlaca.join(', ')
}

function ordens(a) {
  return (a.ordens || []).map((o) => o.numero_os).join(', ') || '—'
}

async function carregar() {
  carregando.value = true
  erro.value = ''
  const base = new Date(`${ancora.value}T12:00:00`)
  const de = new Date(base)
  de.setDate(base.getDate() - DIAS_ANTES)
  const ate = new Date(base)
  ate.setDate(base.getDate() + DIAS_DEPOIS)
  try {
    const r = await api.get(`/api/agendamentos?de=${iso(de)}&ate=${iso(ate)}`)
    agendamentos.value = r.agendamentos || []
  } catch (e) {
    erro.value = e?.message || 'Não deu para carregar os agendamentos.'
    agendamentos.value = []
  } finally {
    carregando.value = false
  }
}

function andar(passo) {
  const base = new Date(`${ancora.value}T12:00:00`)
  base.setDate(base.getDate() + passo)
  ancora.value = iso(base)
  selecionado.value = iso(base)
  carregar()
}

function irParaHoje() {
  ancora.value = iso(hoje)
  selecionado.value = iso(hoje)
  carregar()
}

/* ---- O CARTÃO QUE ABRE (26/11) -------------------------------------------
   ⚠️ UM CONJUNTO, e não um id só: dois compromissos da mesma hora são
   irmãos e quem confere um costuma conferir o outro. Fechar o anterior ao
   abrir o seguinte faria a pessoa perder o que acabou de ler. */
const abertos = ref(new Set())

function estaAberto(a) {
  return abertos.value.has(a.id)
}

function alternarCartao(a) {
  const novo = new Set(abertos.value)
  if (novo.has(a.id)) {
    novo.delete(a.id)
  } else {
    novo.add(a.id)
    /* 🔵 Decisão dele: abrir o cartão JÁ MARCA como visto *"e avisa que
       confirmou também"*. Por isso a marca automática sai daqui, e não de um
       `watch`: o gesto é o clique. */
    marcarVisto(a, { automatico: true })
  }
  abertos.value = novo
  // Reenvio aberto de um cartão que fechou não pode ficar na tela.
  if (!novo.has(a.id) && reenvio.value?.agendamento?.id === a.id) {
    reenvio.value = null
  }
}

/* ---- O SELO "VISTO" (26/11, migração 121) --------------------------------
   🔵 Pedido dele: *"pode ter um flag de 'Visto' para que o usuário saiba o que
   já viu e o que não, pois podem aparecer agendamentos no dia mesmo"*. E 🔵 a
   escolha do lugar foi dele: **no banco, por pessoa** — e não no navegador,
   que é por máquina e faria o selo mentir no celular.

   🚨 `NOVO` É A AUSÊNCIA DE `visto_em`, não "criado hoje". Quem nunca abriu
   não viu, e é só isso que a tela afirma. */
const marcandoVisto = ref(null)
/* Quem o SISTEMA acabou de marcar, para o cartão poder dizer que marcou. ⚠️
   Vive só nesta visita: recarregar a tela não repete o aviso, porque ele não
   é sobre o compromisso, é sobre o que acabou de acontecer na mão da pessoa. */
const avisadosAgora = ref(new Set())

function naoVistos(lista) {
  return lista.filter((a) => !a.visto_em).length
}

async function marcarVisto(a, { automatico = false } = {}) {
  /* ⚠️ Já visto não se remarca: o POST é idempotente do lado de lá, mas um
     pedido por abertura de cartão enche o log sem mudar nada. */
  if (a.visto_em) return
  marcandoVisto.value = a.id
  acaoErro.value = ''
  try {
    const r = await api.post(`/api/agendamentos/${a.id}/visto`, { automatico })
    a.visto_em = r.visto_em
    a.visto_automatico = r.visto_automatico
    if (automatico) {
      const novo = new Set(avisadosAgora.value)
      novo.add(a.id)
      avisadosAgora.value = novo
    }
  } catch (e) {
    /* 🚨 SELO QUE MENTE É PIOR QUE SELO QUE FALTA. Falhou, não marca nada na
       tela e a frase aparece — e não há `visto_em` local inventado. */
    acaoErro.value = e?.message || 'Não deu para marcar como visto.'
  } finally {
    marcandoVisto.value = null
  }
}

async function desmarcarVisto(a) {
  marcandoVisto.value = a.id
  acaoErro.value = ''
  try {
    await api.del(`/api/agendamentos/${a.id}/visto`)
    a.visto_em = null
    a.visto_automatico = false
    const novo = new Set(avisadosAgora.value)
    novo.delete(a.id)
    avisadosAgora.value = novo
  } catch (e) {
    acaoErro.value = e?.message || 'Não deu para desfazer.'
  } finally {
    marcandoVisto.value = null
  }
}

/* ---- "IR PARA O CARD" (26/11) --------------------------------------------
   🔵 Ele: *"leva para a coluna do clicado em outra aba, só isso, bem simples
   mesmo, já atende"*.

   🚨 ÂNCORA, E NUNCA `window.open` — a lição está no `ModalKm` e no
   `DialogoDeChamado`: *"bloqueador de pop-up come `window.open` sem aviso, e
   aí o clique não faria nada e pareceria defeito"*. A navegação nativa de um
   `<a target="_blank">` nunca é bloqueada, e `rel="noopener"` evita que a aba
   do painel ganhe `window.opener` e possa navegar esta.

   🚨 E O BOTÃO SEGUE A REGRA DA `CFG_15.1`, não uma regra minha: ele só é
   desenhado para quem tem a `PNL_1.1` concedida (medido em 26/11: 8 dos 9
   ativos). 🔵 Ele: *"PNL_1.1 tem tela de permissões nas configurações já
   pronta, deve seguir a regra dela mesmo"*. Desenhar para todos levaria quem
   não tem a uma aba de "Sem permissão", que é tela prometendo o que não
   entrega. */
const SITUACAO_AGENDADO = 1316
const podeVerOQuadro = computed(() => codigosPermitidos.value.has('PNL_1.1'))

function ordensDoCartao(a) {
  return (a.ordens || []).map((o) => o.numero_os).filter(Boolean).join(',')
}

function linkDoCard(a) {
  /* ⚠️ TODAS as OS do compromisso vão na URL, não só a primeira: é o que
     deixa o quadro dizer, do outro lado, que uma delas não está na coluna
     esperada. Um compromisso cobre várias OS; o card de lá é por OS. */
  return `/paineis/operacao?situacao=${SITUACAO_AGENDADO}&os=${ordensDoCartao(a)}`
}

/* ---- As duas ações que PERGUNTAM (26/10) -----------------------------------
   🚨 SAÍRAM OS DOIS `window.prompt`. Além de não nomear botão, o `prompt` não
   valida enquanto se digita: data errada só virava erro depois de o diálogo
   fechar, com o que a pessoa escreveu já perdido. E pedir data por texto
   (`AAAA-MM-DD HH:MM`) numa tela que tem calendário é oferecer o caminho pior
   -- em celular, um teclado cego por cima da tela.

   ⚠️ A REGRA NÃO MUDOU: cancelar exige motivo (o backend grava em
   `motivo_cancelamento`) e reagendar manda ISO. Mudou como se pergunta.

   🚨 E DESDE 18/11 AS DUAS CHEGAM AO HARMONIT (migração 112): cancelar apaga
   lá a linha que NÓS criamos, e reagendar leva a data nova. O gesto daqui tem
   consequência no ERP -- é por isso que os dois modais mostram cliente, data e
   hora antes de confirmar. */
const acao = ref(null)        // { tipo: 'cancelar' | 'reagendar', agendamento }
const motivoDigitado = ref('')
const quandoDigitado = ref('')
const salvandoAcao = ref(false)

function pedirCancelar(a) {
  motivoDigitado.value = ''
  acaoErro.value = ''
  acao.value = { tipo: 'cancelar', agendamento: a }
}

function pedirReagendar(a) {
  /* O `datetime-local` quer `AAAA-MM-DDTHH:MM`, que é exatamente o que o ISO
     do compromisso já traz nos 16 primeiros caracteres. */
  quandoDigitado.value = (a.inicio || '').slice(0, 16)
  acaoErro.value = ''
  acao.value = { tipo: 'reagendar', agendamento: a }
}

function fecharAcao() {
  if (salvandoAcao.value) return
  acao.value = null
}

const podeConfirmarAcao = computed(() => {
  if (!acao.value) return false
  if (acao.value.tipo === 'cancelar') return !!motivoDigitado.value.trim()
  if (acao.value.tipo === 'rascunho') return true
  return !!quandoDigitado.value && !Number.isNaN(Date.parse(quandoDigitado.value))
})

async function confirmarAcao() {
  if (!acao.value || !podeConfirmarAcao.value) return
  /* O terceiro tipo não fala com o servidor: é decisão de navegador. */
  if (acao.value.tipo === 'rascunho') return substituirRascunho()
  const { tipo, agendamento } = acao.value
  salvandoAcao.value = true
  acaoErro.value = ''
  try {
    if (tipo === 'cancelar') {
      await api.post(`/api/agendamentos/${agendamento.id}/cancelar`,
                     { motivo: motivoDigitado.value.trim() })
    } else {
      await api.post(`/api/agendamentos/${agendamento.id}/reagendar`,
                     { inicio: new Date(quandoDigitado.value).toISOString() })
    }
    acao.value = null
    await carregar()
  } catch (e) {
    /* ⚠️ O modal FICA ABERTO no erro: fechar jogaria fora o que foi digitado,
       que é o defeito do `prompt` que esta volta veio consertar. */
    acaoErro.value = e?.message
      || (tipo === 'cancelar' ? 'Não deu para cancelar.' : 'Não deu para reagendar.')
  } finally {
    salvandoAcao.value = false
  }
}

/* ---- MÊS NAVEGÁVEL AO LADO (ponta 3 do plano, §8) ------------------------
   O carrossel entrega semana anterior / hoje / próxima; faltava o mês ao lado,
   para pular para um dia distante sem andar de sete em sete.

   ⚠️ O MÊS É UM ATALHO DE NAVEGAÇÃO, NÃO UMA SEGUNDA LISTA. Escolher um dia
   nele move a âncora do carrossel e recarrega os 7 dias -- quem manda no que
   a tela mostra continua sendo o carrossel. Duas listas de agendamento na
   mesma tela seriam duas respostas para a mesma pergunta.

   🚨 O SELO DE "TEM SERVIÇO" NÃO APARECE NO MÊS, de propósito: o que está
   carregado é a semana da âncora, então o mês saberia de uns dias e não de
   outros -- e um mês com pontos em três dias afirmaria que nos outros não há
   nada. Tela que mente é defeito. */
const mesAberto = ref(false)

/* 🚨 26/10: a grade do mês saiu daqui para `componentes/CalendarioMes.vue` --
   ela era a MESMA do `ModalAgendar`, copiada, com 36px de coluna contra 34px
   lá. O que fica aqui é o que é desta tela: o que escolher um dia significa. */
function escolherDoMes(diaIso) {
  ancora.value = diaIso
  selecionado.value = diaIso
  mesAberto.value = false
  carregar()
}

/* ---- REENVIAR CONFIRMAÇÃO (ponta 2 do plano, §8) -------------------------
   A quarta ação do cartão. Entregaram-se três em 21/10 (Reagendar, Cancelar,
   Abrir conversa) e esta ficou faltando.

   🚨 NÃO ENVIA NADA. Decisão 6 dele, ao pé da letra: as duas confirmações
   saem pré-escritas e **quem envia é o atendente**. Aqui ela mostra os dois
   textos para copiar e oferece abrir a conversa com o texto no compositor.

   🚨 MONTA COM A MESMA REGRA DE AGRUPAMENTO (mesma data e hora => uma
   mensagem só, placas e OS somadas), e por isso junta os compromissos IRMÃOS:
   o mesmo cliente, na mesma hora, menos os cancelados. Reenviar só o cartão
   clicado mandaria ao cliente um texto diferente do que ele recebeu.

   ⚠️ COMPROMISSO AINDA `aguardando` NÃO TEM RESPONSÁVEL: o texto sai com o
   campo vazio, e a tela diz por quê em vez de deixar o operador descobrir. */
const reenvio = ref(null)
const copiado = ref('')

function irmaosDe(a) {
  const chave = chaveDoGrupo(a)
  return agendamentos.value.filter(
    (x) => x.estado !== 'cancelado'
      && x.cliente_harmonit_id === a.cliente_harmonit_id
      && chaveDoGrupo(x) === chave)
}

function reenviarConfirmacao(a) {
  const grupo = irmaosDe(a)
  // `irmaosDe` exclui cancelado, e a ação não aparece em cartão cancelado --
  // mas se por algum caminho chegar aqui vazia, usa o próprio compromisso em
  // vez de montar mensagem de lista vazia.
  const [primeiro] = agrupar(grupo.length ? grupo : [a])
  reenvio.value = {
    agendamento: a,
    ...textosDoGrupo(primeiro, {}),
  }
  copiado.value = ''
}

async function copiar(qual, texto) {
  try {
    await navigator.clipboard.writeText(texto)
    copiado.value = qual
  } catch {
    // 🚨 A ÁREA DE TRANSFERÊNCIA FALHA SEM AVISO em contexto não seguro e
    // quando a aba não tem o foco. O texto está na tela, selecionável: o que
    // não pode é a tela afirmar que copiou sem ter copiado.
    copiado.value = ''
    acaoErro.value = 'Não deu para copiar — selecione o texto e copie à mão.'
  }
}

/* Abre a conversa com o texto JÁ no compositor.

   🚨 O CAMINHO É O RASCUNHO POR CONVERSA (Bloco 7, 15/10): a Caixa semeia o
   compositor com `localStorage['movizap.rascunho.<id>']` ao abrir a conversa.
   Escrever aqui é usar o mecanismo que já existe, em vez de inventar um
   segundo caminho de "texto pendente".

   ⚠️ NÃO SOBRESCREVE RASCUNHO SEM AVISAR: se já havia texto guardado naquela
   conversa, pergunta. Perder meia frase digitada pelo colega é o defeito que
   o Bloco 7 nasceu para corrigir. */
function abrirConversaComTexto(a, texto) {
  if (!a.conversa_id) return
  const chave = `movizap.rascunho.${a.conversa_id}`
  try {
    const havia = localStorage.getItem(chave)
    if (havia && havia.trim() && havia !== texto) {
      /* 🚨 26/10: ERA UM `window.confirm`. Além de não nomear botão, ele não
         mostrava o texto em jogo -- a pergunta é "substituir o que o colega
         digitou?" e a pessoa decidia às cegas. O modal mostra o começo do que
         seria perdido. */
      acao.value = { tipo: 'rascunho', agendamento: a, texto, chave, havia }
      return
    }
    localStorage.setItem(chave, texto)
  } catch {
    // Sem storage (janela privada, dados bloqueados): abre a conversa de todo
    // jeito e diz que o texto não foi semeado -- o texto continua na tela.
    acaoErro.value = 'Abri a conversa, mas não deu para deixar o texto no '
      + 'compositor neste navegador. Copie o texto acima.'
  }
  reenvio.value = null
  router.push(`/atendimento/${a.conversa_id}`)
}

/* A segunda metade do fluxo acima: a pessoa viu o que seria perdido e disse
   para substituir. ⚠️ A gravação continua dentro de `try`: o motivo de haver
   `catch` ali (janela privada, storage bloqueado) não desaparece porque a
   pergunta mudou de forma. */
function substituirRascunho() {
  const { agendamento, texto, chave } = acao.value
  try {
    localStorage.setItem(chave, texto)
  } catch {
    acaoErro.value = 'Abri a conversa, mas não deu para deixar o texto no '
      + 'compositor neste navegador. Copie o texto acima.'
  }
  acao.value = null
  reenvio.value = null
  router.push(`/atendimento/${agendamento.conversa_id}`)
}

function abrirConversa(a) {
  if (!a.conversa_id) return
  router.push(`/atendimento/${a.conversa_id}`)
}

onMounted(carregar)
</script>

<template>
  <section class="agd">
    <!-- 🚨 CABEÇALHO NO PADRÃO DA CASA (`G2`, 26/11): `tela__cabecalho`, `h1`,
         ajuda e o chip do código, como a `CAD_1.2` e as outras 27. Esta tela
         era uma das 14 sem `AjudaDaTela` nenhuma.
         ⚠️ E A FAIXA DE COBERTURA VIROU A AJUDA, não some: era um `aviso--info`
         ocupando uma linha inteira todo dia para dizer uma coisa que se aprende
         uma vez. O texto é o MESMO -- quem precisa, passa o mouse. -->
    <header class="tela__cabecalho">
      <div>
        <h1>Agendamentos</h1>
        <AjudaDaTela>
          Aparece aqui o que foi agendado <b>por este painel</b>. Serviço
          combinado por fora, ou marcado direto no Harmonit, não entra nesta
          lista.
        </AjudaDaTela>
      </div>
      <span class="chip chip--codigo chip--acento">ATD_7.1</span>
    </header>

    <div class="agd__navegacao">
      <button class="botao botao--fantasma" type="button" @click="andar(-7)">
        <i class="bi bi-chevron-left" aria-hidden="true"></i> Semana anterior
      </button>
      <button class="botao botao--fantasma" type="button" @click="irParaHoje">Hoje</button>
      <button class="botao botao--fantasma" type="button" @click="andar(7)">
        Próxima semana <i class="bi bi-chevron-right" aria-hidden="true"></i>
      </button>
      <!-- Ponta 3: o mês ao lado, para pular para um dia distante sem andar
           de sete em sete. Atalho de navegação, não uma segunda lista. -->
      <button class="botao botao--fantasma" type="button"
              :aria-expanded="mesAberto ? 'true' : 'false'"
              @click="mesAberto = !mesAberto">
        <i class="bi bi-calendar3" aria-hidden="true"></i> Mês
      </button>
    </div>

    <nav class="agd__carrossel" aria-label="Dias">
      <button
        v-for="d in dias"
        :key="d.iso"
        type="button"
        class="agd__dia"
        :class="{ 'agd__dia--ativo': d.iso === selecionado, 'agd__dia--hoje': d.hoje }"
        @click="selecionado = d.iso"
      >
        <span class="agd__dia-semana">{{ d.semana }}</span>
        <span class="agd__dia-numero">{{ d.dia }}</span>
        <span class="agd__dia-mes">{{ d.mes }}</span>
        <span v-if="porDia[d.iso]" class="agd__dia-selo">{{ porDia[d.iso] }}</span>
      </button>
    </nav>

    <div v-if="mesAberto" class="agd__mes">
      <CalendarioMes :selecionado="selecionado" @escolher="escolherDoMes">
        <!-- 🚨 Dizer isto evita que a ausência de marca pareça ausência de
             serviço: o que está carregado é a semana da âncora. -->
        <template #nota>
          <p class="agd__mes-nota">
            Escolher um dia move a semana do carrossel. As marcas de serviço
            ficam no carrossel, que é o que está carregado.
          </p>
        </template>
      </CalendarioMes>
    </div>

    <p v-if="erro" class="aviso aviso--erro">{{ erro }}</p>
    <p v-if="acaoErro" class="aviso aviso--erro" role="alert">{{ acaoErro }}</p>
    <p v-if="carregando" class="agd__vazio">Carregando…</p>

    <p v-else-if="!doDia.length" class="agd__vazio">
      Nenhum serviço agendado por este painel neste dia.
    </p>

    <template v-else>
      <!-- ⚠️ O "não vistos" é POR PESSOA, como o selo: diz o que FALTA a quem
           está olhando, e não quantos a equipe deixou de ver. -->
      <p class="agd__dia-titulo">
        {{ doDia.length }} {{ doDia.length === 1 ? 'serviço' : 'serviços' }}
        <template v-if="naoVistos(doDia)">
          · {{ naoVistos(doDia) }} não {{ naoVistos(doDia) === 1 ? 'visto' : 'vistos' }}
        </template>
      </p>

      <ul class="agd__lista">
        <li v-for="a in doDia" :key="a.id">
          <article class="agd__cartao"
                   :class="{ 'agd__cartao--cancelado': a.estado === 'cancelado',
                             'agd__cartao--aberto': estaAberto(a),
                             'agd__cartao--novo': !a.visto_em && a.estado !== 'cancelado' }">
            <!-- 🚨 O CABEÇALHO INTEIRO É O BOTÃO DE ABRIR, e não um ícone de
                 12px no canto: é o alvo de toque de 44px que o padrão pede, e
                 em celular um alvo pequeno num cartão grande é o defeito mais
                 comum de lista que abre. -->
            <button type="button" class="agd__cartao-topo"
                    :aria-expanded="estaAberto(a) ? 'true' : 'false'"
                    @click="alternarCartao(a)">
              <span class="agd__cartao-hora">{{ hora(a.inicio) }}</span>
              <span class="agd__cartao-cliente">{{ a.cliente_nome }}</span>
              <span class="agd__estado" :class="`agd__estado--${a.estado}`">
                {{ ROTULO_ESTADO[a.estado] || a.estado }}
              </span>
              <!-- `NOVO` é a ausência de `visto_em` desta pessoa; `Visto` traz
                   a hora, que é a da PRIMEIRA vez (o servidor não reescreve). -->
              <span v-if="!a.visto_em && a.estado !== 'cancelado'"
                    class="agd__selo-novo">NOVO</span>
              <span v-else-if="a.visto_em" class="agd__selo-visto">
                Visto {{ hora(a.visto_em) }}
              </span>
              <i class="bi" :class="estaAberto(a) ? 'bi-chevron-up' : 'bi-chevron-down'"
                 aria-hidden="true"></i>
            </button>

            <p class="agd__cartao-resumo">
              {{ a.tecnico_nome || 'sem técnico' }} · OS {{ ordens(a) }} ·
              {{ placas(a) }}
            </p>

            <small v-if="a.estado === 'cancelado' && a.motivo_cancelamento"
                   class="agd__motivo">{{ a.motivo_cancelamento }}</small>
            <!-- 🚨 TELA QUE MENTE É DEFEITO (`M12`). O aviso de "não foi
                 ao Harmonit" existia só na caixa, logo depois de agendar, e
                 vivia um instante: dali em diante o erro ficava só na linha
                 do banco e esta tela mostrava um compromisso que parecia
                 inteiro. Medido em 18/11: 6 dos 10 ativos estavam assim, e
                 nada na tela dizia.
                 ⚠️ NÃO É ERRO DO COMPROMISSO: o dono é o MoviZap (decisão 7
                 dele) e ele vale aqui. É por isso que o selo fica ao LADO do
                 estado, e não no lugar dele. -->
            <small v-if="a.estado !== 'cancelado' && !a.harmonit_agendamento_id
                         && a.harmonit_erro"
                   class="agd__sem-harmonit" :title="a.harmonit_erro">
              Não foi para a OS no Harmonit
            </small>

            <!-- ⚠️ "Marcar como visto" existe NO CARTÃO FECHADO, 🔵 porque ele
                 pediu os dois caminhos: dar ciência sem precisar abrir, e a
                 marca automática ao abrir. -->
            <button v-if="!a.visto_em && a.estado !== 'cancelado'"
                    class="botao botao--fantasma agd__visto-botao" type="button"
                    :disabled="marcandoVisto === a.id"
                    @click="marcarVisto(a)">
              <i class="bi bi-check2" aria-hidden="true"></i> Marcar como visto
            </button>

            <div v-if="estaAberto(a)" class="agd__cartao-corpo">
              <!-- 🔵 *"ao abrir já confirma e avisa que confirmou também"*. O
                   aviso é desta visita: recarregar a tela não o repete, porque
                   ele é sobre o gesto, não sobre o compromisso. -->
              <p v-if="avisadosAgora.has(a.id)" class="agd__aviso-visto">
                <i class="bi bi-check2-circle" aria-hidden="true"></i>
                Marquei como visto agora, porque você abriu este compromisso.
                <button class="botao botao--fantasma" type="button"
                        :disabled="marcandoVisto === a.id"
                        @click="desmarcarVisto(a)">Desfazer</button>
              </p>

              <dl class="agd__ficha">
                <dt>Técnico</dt><dd>{{ a.tecnico_nome || '—' }}</dd>
                <dt>OS</dt><dd>{{ ordens(a) }}</dd>
                <dt>Placa(s)</dt><dd>{{ placas(a) }}</dd>
                <dt>Endereço</dt><dd>{{ a.endereco || '—' }}</dd>
                <dt>Acompanha</dt>
                <dd>
                  {{ a.responsavel_cliente || '—' }}
                  <!-- ⚠️ Vazio aqui tem um motivo, e a tela diz qual em vez de
                       deixar o operador achar que alguém esqueceu. -->
                  <span v-if="!a.responsavel_cliente && a.estado === 'aguardando'"
                        class="agd__ficha-nota">
                    (ainda não confirmado pelo cliente)
                  </span>
                </dd>
                <dt>Orçamento</dt><dd>{{ a.orcamento_numero || '—' }}</dd>
              </dl>

              <div class="agd__acoes">
                <button v-if="a.estado !== 'cancelado'" class="botao botao--fantasma"
                        type="button" @click="pedirReagendar(a)">Reagendar</button>
                <button v-if="a.estado !== 'cancelado'" class="botao botao--fantasma"
                        type="button" @click="pedirCancelar(a)">Cancelar</button>
                <button v-if="a.estado !== 'cancelado'" class="botao botao--fantasma"
                        type="button" @click="reenviarConfirmacao(a)">Reenviar confirmação</button>
                <button v-if="a.conversa_id" class="botao botao--fantasma"
                        type="button" @click="abrirConversa(a)">Abrir conversa</button>
                <!-- 🚨 ÂNCORA, NUNCA `window.open` (bloqueador de pop-up come
                     `window.open` sem aviso). E só para quem tem a `PNL_1.1`
                     concedida na `CFG_15.1`: compromisso SEM OS também não
                     desenha, porque não há card para onde ir. -->
                <a v-if="podeVerOQuadro && ordensDoCartao(a)"
                   class="botao botao--contorno"
                   :href="linkDoCard(a)" target="_blank" rel="noopener noreferrer">
                  Ir para o card
                  <i class="bi bi-box-arrow-up-right" aria-hidden="true"></i>
                </a>
              </div>

              <!-- 🚨 O REENVIO ABRE AQUI DENTRO, e isto é o conserto de uma
                   distância: até 26/11 ele nascia no PÉ DA TABELA, longe da
                   linha clicada, e em dia cheio a pessoa clicava e não via
                   nada acontecer.
                   🚨 NÃO ENVIA NADA (decisão 6 dele): mostra para copiar e
                   oferece abrir a conversa com o texto no compositor. -->
              <div v-if="reenvio && reenvio.agendamento.id === a.id" class="agd__reenvio">
                <header class="agd__reenvio-topo">
                  <strong>Confirmação de {{ reenvio.agendamento.cliente_nome }}</strong>
                  <button class="botao botao--fantasma" type="button" @click="reenvio = null">
                    Fechar
                  </button>
                </header>

                <p class="aviso aviso--info agd__reenvio-aviso">
                  Isto <b>não envia nada</b>: quem envia é você. Copie o texto, ou abra a
                  conversa com ele já no compositor.
                </p>
                <p v-if="reenvio.quantos > 1" class="agd__reenvio-nota">
                  Mesma data e hora: {{ reenvio.quantos }} compromissos entraram numa
                  mensagem só, com as placas e as OS somadas ({{ reenvio.ordens.join(', ') }}).
                </p>
                <!-- ⚠️ Compromisso ainda aguardando não tem responsável: o campo sai
                     vazio, e a tela diz por quê. -->
                <p v-if="reenvio.semResponsavel" class="aviso aviso--atencao agd__reenvio-nota">
                  Este compromisso ainda não foi confirmado pelo cliente, então ninguém
                  disse quem acompanha o técnico — o campo sai vazio. Quem preenche é a
                  aba <b>Confirmar</b>, na conversa do cliente.
                </p>

                <div class="agd__reenvio-textos">
                  <article>
                    <h3 class="agd__reenvio-rotulo">Para o cliente</h3>
                    <pre class="agd__reenvio-pre">{{ reenvio.doCliente }}</pre>
                    <div class="agd__acoes">
                      <button class="botao botao--fantasma" type="button"
                              @click="copiar('cliente', reenvio.doCliente)">
                        {{ copiado === 'cliente' ? 'Copiado' : 'Copiar' }}
                      </button>
                      <button v-if="reenvio.agendamento.conversa_id" class="botao botao--contorno"
                              type="button"
                              @click="abrirConversaComTexto(reenvio.agendamento, reenvio.doCliente)">
                        Abrir conversa com este texto
                      </button>
                    </div>
                  </article>
                  <article>
                    <h3 class="agd__reenvio-rotulo">Para o técnico</h3>
                    <pre class="agd__reenvio-pre">{{ reenvio.doTecnico }}</pre>
                    <div class="agd__acoes">
                      <button class="botao botao--fantasma" type="button"
                              @click="copiar('tecnico', reenvio.doTecnico)">
                        {{ copiado === 'tecnico' ? 'Copiado' : 'Copiar' }}
                      </button>
                      <button v-if="reenvio.agendamento.conversa_id" class="botao botao--contorno"
                              type="button"
                              @click="abrirConversaComTexto(reenvio.agendamento, reenvio.doTecnico)">
                        Abrir conversa com este texto
                      </button>
                    </div>
                  </article>
                </div>
                <!-- A conversa de ORIGEM é a do técnico (decisão dele de 07/10: em
                     conversa de técnico o `cliente_id` do contato é nulo). Dizer isso
                     evita o operador achar que "abrir conversa" leva ao cliente. -->
                <p class="agd__reenvio-nota">
                  “Abrir conversa” leva à conversa de onde este agendamento saiu — a do
                  técnico. A do cliente abre-se pela Caixa.
                </p>
              </div>
            </div>
          </article>
        </li>
      </ul>
    </template>
  </section>

    <!-- Os dois diálogos que substituíram os `window.prompt` (26/10). As
         classes são as `.modal` globais: casca nova para isto seria um
         segundo padrão de modal no mesmo projeto. -->
    <div v-if="acao" class="modal" @click.self="fecharAcao">
      <div class="modal__caixa" role="dialog" aria-modal="true"
           :aria-label="acao.tipo === 'cancelar' ? 'Cancelar agendamento'
                                                 : 'Reagendar'">
        <template v-if="acao.tipo === 'cancelar'">
          <p class="modal__titulo">Cancelar o agendamento?</p>
          <p class="modal__texto">
            {{ acao.agendamento.cliente_nome }} —
            {{ dataBr(acao.agendamento.inicio) }} às {{ hora(acao.agendamento.inicio) }}
          </p>
          <label class="campo">
            <span class="campo__rotulo">Por quê? (fica registrado)</span>
            <textarea v-model="motivoDigitado" class="campo__entrada" rows="3"
                      placeholder="O cliente pediu para remarcar, técnico..."></textarea>
            <!-- O motivo é obrigatório, e a tela DIZ isso em vez de só
                 desabilitar o botão e deixar a pessoa adivinhar. -->
            <span class="campo__ajuda">
              Sem motivo não dá para cancelar: ele fica no histórico do
              compromisso.
            </span>
          </label>
        </template>

        <template v-else-if="acao.tipo === 'rascunho'">
          <p class="modal__titulo">Substituir o texto do compositor?</p>
          <p class="modal__texto">
            A conversa de {{ acao.agendamento.cliente_nome }} já tem texto não
            enviado. Substituir pelo da confirmação apaga o que está lá.
          </p>
          <!-- 🚨 MOSTRA O QUE SERIA PERDIDO. O `window.confirm` daqui até
               26/10 perguntava sem mostrar nada, e quem decidia decidia às
               cegas sobre o texto de outra pessoa. -->
          <pre class="agd__rascunho">{{ acao.havia.slice(0, 400) }}</pre>
        </template>

        <template v-else>
          <p class="modal__titulo">Reagendar</p>
          <p class="modal__texto">
            {{ acao.agendamento.cliente_nome }} — hoje em
            {{ dataBr(acao.agendamento.inicio) }} às {{ hora(acao.agendamento.inicio) }}
          </p>
          <label class="campo">
            <span class="campo__rotulo">Nova data e hora</span>
            <input v-model="quandoDigitado" class="campo__entrada"
                   type="datetime-local" />
            <span class="campo__ajuda">
              No celular isto abre o seletor do próprio aparelho.
            </span>
          </label>
        </template>

        <p v-if="acaoErro" class="aviso aviso--erro" role="alert">
          <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
          <span>{{ acaoErro }}</span>
        </p>

        <div class="modal__acoes">
          <button class="botao botao--contorno" type="button"
                  :disabled="salvandoAcao" @click="fecharAcao">
            Voltar
          </button>
          <button
            :class="['botao', acao.tipo === 'reagendar' ? 'botao--primario' : 'botao--perigo']"
            type="button"
            :disabled="salvandoAcao || !podeConfirmarAcao"
            @click="confirmarAcao"
          >
            <span v-if="salvandoAcao" class="girando"></span>
            {{ acao.tipo === 'cancelar' ? 'Cancelar o agendamento'
               : acao.tipo === 'rascunho' ? 'Substituir e abrir'
               : 'Reagendar' }}
          </button>
        </div>
      </div>
    </div>
</template>

<style scoped>
.agd { display: flex; flex-direction: column; gap: var(--e-3); min-height: 0; }
.agd__navegacao { display: flex; gap: var(--e-2); flex-wrap: wrap; }

.agd__carrossel { display: flex; gap: var(--e-2); overflow-x: auto; padding-bottom: var(--e-1); }
.agd__dia {
  position: relative;
  flex: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  min-width: 68px;
  padding: var(--e-2);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
  background: var(--superficie-2);
  color: inherit;
  cursor: pointer;
}
.agd__dia--hoje { border-color: var(--acento); }
.agd__dia--ativo { background: var(--acento); color: #fff; border-color: var(--acento); }
.agd__dia-semana, .agd__dia-mes { font-size: var(--txt-xs); text-transform: uppercase; }
.agd__dia-numero { font-size: var(--txt-lg); font-weight: var(--peso-forte); }
.agd__dia-selo {
  position: absolute;
  top: 4px;
  right: 6px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 999px;
  background: var(--acento);
  color: #fff;
  font-size: 10px;
  line-height: 16px;
}
.agd__dia--ativo .agd__dia-selo { background: rgba(255, 255, 255, .35); }

/* ---- A LISTA DE CARTÕES (26/11) ---------------------------------------- */
.agd__dia-titulo {
  margin: 0;
  color: var(--texto-fraco);
  font-size: var(--txt-sm);
  text-transform: uppercase;
  letter-spacing: .02em;
}
.agd__lista { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--e-2); }
.agd__cartao {
  display: flex;
  flex-direction: column;
  gap: var(--e-1);
  padding: var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-left: 3px solid var(--borda);
  border-radius: var(--r-md);
  background: var(--superficie-2);
}
/* ⚠️ A borda da esquerda é o que distingue de longe sem contar casa por casa:
   acento para o que esta pessoa ainda não viu. */
.agd__cartao--novo { border-left-color: var(--acento); }
.agd__cartao--aberto { background: var(--superficie); }
.agd__cartao--cancelado { opacity: .65; }
/* 🚨 44px de alvo de toque: é tela de celular, e o padrão visual é explícito
   em que "16px e 44px não são estética". */
.agd__cartao-topo {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  flex-wrap: wrap;
  min-height: 44px;
  padding: 0;
  border: 0;
  background: none;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.agd__cartao-hora { font-size: var(--txt-lg); font-weight: var(--peso-forte); }
.agd__cartao-cliente { flex: 1 1 auto; font-weight: var(--peso-forte); }
.agd__cartao-resumo { margin: 0; color: var(--texto-fraco); font-size: var(--txt-sm); }
.agd__cartao-corpo {
  display: flex;
  flex-direction: column;
  gap: var(--e-2);
  margin-top: var(--e-2);
  padding-top: var(--e-2);
  border-top: var(--borda-fina) solid var(--borda);
}
/* O detalhe em duas colunas: rótulo estreito, valor quebrando à vontade. */
.agd__ficha {
  display: grid;
  grid-template-columns: minmax(84px, auto) 1fr;
  gap: var(--e-1) var(--e-3);
  margin: 0;
  font-size: var(--txt-sm);
}
.agd__ficha dt { color: var(--texto-fraco); }
.agd__ficha dd { margin: 0; overflow-wrap: anywhere; }
.agd__ficha-nota { color: var(--texto-fraco); }

/* Os dois selos. ⚠️ Classe própria no padrão `agd__`, e NUNCA `.pilula`:
   `.pilula` é `scoped` por componente e não existe em `estilo/*.css` -- o selo
   nasceria sem estilo nenhum e nenhuma trava pegaria, porque o jsdom não faz
   layout. */
.agd__selo-novo {
  padding: 2px var(--e-2);
  border-radius: 999px;
  background: var(--acento);
  color: #fff;
  font-size: var(--txt-xs);
  font-weight: var(--peso-forte);
  letter-spacing: .04em;
}
.agd__selo-visto { color: var(--texto-fraco); font-size: var(--txt-xs); }
.agd__visto-botao { align-self: flex-start; }
.agd__aviso-visto {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  flex-wrap: wrap;
  margin: 0;
  color: var(--ok);
  font-size: var(--txt-sm);
}

/* O mês ao lado (ponta 3) */
.agd__mes {
  display: flex;
  flex-direction: column;
  gap: var(--e-2);
  align-self: flex-start;
  padding: var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
  background: var(--superficie-2);
}
/* 🚨 26/10: o CSS da grade foi para `CalendarioMes.vue`.
   ⚠️ AS DUAS CÓPIAS DIVERGIAM EM QUATRO MEDIDAS, todas sem razão: coluna de
   36px aqui contra 34px no modal, altura 32px contra 30px, `gap` de 4px contra
   3px, e fundo `--superficie` contra `--superficie-2`. Nenhuma delas chegava
   ao `--altura-toque: 44px` do padrão. É o melhor retrato do que a cópia
   custa: ninguém escolheu ser diferente -- ficou diferente. */
/* O trecho do rascunho que seria perdido: monoespaçado e com teto de altura,
   porque pode ser texto longo e o modal não é um leitor. */
.agd__rascunho {
  max-height: 30vh;
  overflow: auto;
  margin: 0 0 var(--e-4);
  padding: var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-sm);
  background: var(--superficie-2);
  font-size: var(--txt-sm);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.agd__mes-nota { margin: 0; max-width: 34ch; color: var(--texto-fraco); font-size: var(--txt-xs); }

/* Reenviar confirmação (ponta 2) */
.agd__reenvio {
  display: flex;
  flex-direction: column;
  gap: var(--e-2);
  padding: var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
  background: var(--superficie-2);
}
.agd__reenvio-topo { display: flex; align-items: center; justify-content: space-between; gap: var(--e-2); }
.agd__reenvio-aviso, .agd__reenvio-nota { margin: 0; }
.agd__reenvio-nota { color: var(--texto-fraco); font-size: var(--txt-sm); }
.agd__reenvio-textos { display: flex; gap: var(--e-3); flex-wrap: wrap; }
.agd__reenvio-textos > article { flex: 1 1 320px; display: flex; flex-direction: column; gap: var(--e-2); }
.agd__reenvio-rotulo { margin: 0; font-size: var(--txt-sm); }
.agd__reenvio-pre {
  margin: 0;
  padding: var(--e-2);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-sm);
  background: var(--superficie);
  white-space: pre-wrap;
  word-break: break-word;
  font-size: var(--txt-sm);
}
.agd__vazio { color: var(--texto-fraco); font-size: var(--txt-sm); }
.agd__acoes { display: flex; gap: var(--e-1); flex-wrap: wrap; }
.agd__motivo { color: var(--texto-fraco); }
.agd__estado { font-size: var(--txt-xs); font-weight: var(--peso-forte); }
.agd__estado--confirmado { color: var(--ok); }
.agd__estado--aguardando { color: var(--aviso); }
.agd__estado--cancelado { color: var(--erro); }
.agd__sem-harmonit {
  color: var(--aviso);
  font-size: var(--txt-xs);
  font-weight: var(--peso-forte);
  cursor: help;
}
</style>
