<script setup>
/* ============================================================================
   CAD_2.1 — Atendentes.
   ----------------------------------------------------------------------------
   🚨 A PAUSA DO ALMOÇO É O INTERVALO ENTRE DUAS FAIXAS DO MESMO DIA.
   08:00–12:00 e 13:00–18:00 são duas linhas, e o almoço é o buraco entre elas.
   Não existe campo "pausa", e é por isso que cada dia aceita várias faixas.

   ⚠️ A jornada NÃO bloqueia transferência. Ela existe para a fila AVISAR que
   a pessoa está fora do horário — bloquear faria o atendente fechar a conversa
   para se livrar dela, e aí o cliente some do radar de vez.

   🔵 REPAGINADA EM 24/09, com as regras dele sobre os campos:
     · *"o campo de e-mail, deve aparecer somente para admin e owner"* -- esta
       tela só abre para os dois, então aqui ele sempre aparece;
     · *"o 'Login' pode ser oculto a todos menos owner, pois usamos o auth
       google para logar"* -- conta nova criada pelo admin nasce com o login
       igual ao e-mail, porque o banco exige login;
     · *"o botão editar dos atendentes deve abrir um modal"* -- ModalEdicao.

   🚨 "SEM SENHA" NÃO QUER DIZER "NÃO ENTRA" (medido em 24/09). A entrada pelo
   Google casa pelo e-mail (`google_auth.py`), sem senha nenhuma. A tela avisava
   *"N conta(s) sem senha"* e dizia que conta sem senha não entra -- verdade
   antes do Google, mentira depois. Agora mostra COMO cada um entra.
   ============================================================================ */
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'

import { api, ErroDeApi } from '../api/cliente.js'
import { sessao } from '../estado/sessao.js'
import { corDaInicial, iniciais } from '../util/avatar.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'
import ModalEdicao from '../componentes/ModalEdicao.vue'

const DIAS = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado']
const DIAS_CURTOS = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']
const ESTADOS = [
  { valor: 'disponivel', rotulo: 'Disponível' },
  { valor: 'ausente', rotulo: 'Em pausa' },
  { valor: 'nao_perturbe', rotulo: 'Não perturbe' },
  { valor: 'offline', rotulo: 'Fora do expediente' },
]
/* ⚠️ Os rótulos são os MESMOS da Minha conta: o mesmo estado com dois nomes
   faria o owner e a pessoa conversarem sobre coisas diferentes. */
const ROTULO_PERFIL = {
  owner: 'Owner', admin: 'Admin', atendimento: 'Atendimento', cadastro: 'Cadastro',
}

/* 🚨 QUEM BARRA É O BACKEND (`_so_owner_mexe_no_owner`, `_so_owner_da_admin`).
   Aqui só não se OFERECE o que voltaria 403. `owner` não se oferece a ninguém:
   não se promove ninguém a owner, e o seletor que mostrava a opção só dava
   erro ao salvar. */
const souOwner = computed(() => Boolean(sessao.usuario?.owner))
const perfisOferecidos = computed(() =>
  souOwner.value ? ['admin', 'atendimento', 'cadastro'] : ['atendimento', 'cadastro'],
)

const atendentes = ref([])
const carregando = ref(true)
const erro = ref('')
const recado = ref('')
const incluirInativos = ref(false)

/* ---- o interruptor da jornada (25/08) ------------------------------------
   Decisão do usuário: *"pode colocar interruptor na configuração do owner de
   usar jornada ou não, daí pode montar ela mas deixando desligado"*. O
   interruptor mora em Configurações › Geral; aqui se lê o estado. */
const jornadaAtiva = ref(false)

async function carregarJornadaAtiva() {
  try {
    jornadaAtiva.value = (await api.get('/api/config/jornada')).jornada_ativa
  } catch { jornadaAtiva.value = false }
}

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    atendentes.value = await api.get(`/api/atendentes?incluir_inativos=${incluirInativos.value}`)
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao ler os atendentes.'
  } finally {
    carregando.value = false
  }
}

onMounted(() => { carregar(); carregarJornadaAtiva() })

/* ---- o resumo do topo ----------------------------------------------------
   Os números que se pergunta sobre uma equipe antes de olhar linha a linha. */
const ativos = computed(() => atendentes.value.filter((a) => a.ativo))
const resumo = computed(() => ({
  ativos: ativos.value.length,
  emAberto: ativos.value.reduce((s, a) => s + (a.em_aberto || 0), 0),
  concluidas: ativos.value.reduce((s, a) => s + (a.concluidas_semana || 0), 0),
  semAcesso: ativos.value.filter((a) => !a.email && !a.tem_senha).length,
}))

/* Como a pessoa entra: pelo Google (tem e-mail), por senha, ou não entra. */
function acessoDe(a) {
  if (a.email) return { rotulo: 'Google', classe: 'chip--ok', icone: 'bi-google' }
  if (a.tem_senha) return { rotulo: 'senha', classe: '', icone: 'bi-key' }
  return { rotulo: 'não entra', classe: 'chip--erro', icone: 'bi-slash-circle' }
}

/* Total de horas por semana: é o número que RH olha, e ninguém soma faixas de
   cabeça. */
function horasSemana(a) {
  const minutos = (a.jornada || []).reduce((total, f) => {
    const [hi, mi] = f.inicio.split(':').map(Number)
    const [hf, mf] = f.fim.split(':').map(Number)
    return total + (hf * 60 + mf) - (hi * 60 + mi)
  }, 0)
  return (minutos / 60).toFixed(1).replace('.', ',')
}

function diasDaJornada(a) {
  const dias = [...new Set((a.jornada || []).map((f) => f.dia_semana))].sort()
  return dias.map((d) => DIAS_CURTOS[d]).join(' · ')
}

/* ---- ativo / inativo (25/09) ----------------------------------------------
   🔵 *"vamos ligar isso a um status de inativo e ativo no perfil do
   atendente, um interruptor, inativo não loga a conta permanece lá"*. Tomou o
   lugar do "Desligar", que apagava senha e times e não tinha volta.

   🚨 NÃO EXISTE APAGAR. `conversa`, `transferencia` e `mensagem` apontam para
   o atendente. Inativar tira o acesso; as conversas abertas vão para quem a
   pessoa escolher, obrigatório, como no afastamento. */
const inativando = ref(null)
const inativarPara = ref(null)
const erroInativar = ref('')
const trocandoAtivo = ref(false)

/* A própria conta não tem interruptor: o backend recusa, e a tela não oferece. */
const editandoASiMesmo = computed(() =>
  Boolean(editando.value?.login) &&
  editando.value.login.toLowerCase() === (sessao.usuario?.login || '').toLowerCase())

function alternarAtivo() {
  const a = editando.value
  if (a.ativo) {
    inativando.value = a
    inativarPara.value = null
    erroInativar.value = ''
    return
  }
  gravarAtivo(a, true, null)
}

async function gravarAtivo(a, ativo, para) {
  trocandoAtivo.value = true
  erroInativar.value = ''
  try {
    const r = await api.put(`/api/atendentes/${a.id}/ativo`, { ativo, transferir_para: para })
    if (ativo) recado.value = `${a.nome} está ativo de novo e entra no painel.`
    else if (r.transferidas) recado.value = `${a.nome} ficou inativo. ${r.transferidas} conversa(s) transferida(s).`
    else recado.value = `${a.nome} ficou inativo.`
    inativando.value = null
    fechar()
    await carregar()
  } catch (e) {
    const texto = e instanceof ErroDeApi ? e.message : 'Não consegui mudar a situação.'
    if (inativando.value) erroInativar.value = texto
    else erroModal.value = texto
    await carregar()
  } finally {
    trocandoAtivo.value = false
  }
}

/* ---- o modal de edição --------------------------------------------------- */
const editando = ref(null)
const form = ref(vazio())
const jornada = ref([])
const novaSenha = ref('')
const erroModal = ref('')
const salvando = ref(false)
let retrato = ''

/* ⚠️ Cada faixa carrega um `uid` só para o :key do v-for. Sem chave estável, o
   Vue recicla o <input> pelo índice: remover a faixa do meio faz o horário da
   seguinte aparecer no lugar errado, e o usuário salva sem perceber. */
let proximoUid = 1
const comUid = (faixa) => ({ ...faixa, uid: proximoUid++ })

function vazio() {
  return {
    nome: '', login: '', email: '', perfil: 'atendimento',
    estado: 'disponivel', fuso: 'America/Sao_Paulo',
  }
}

/* O que conta como "mudou": o formulário, a jornada SEM o uid (que é só do
   v-for) e a senha nova. Comparado com o retrato tirado ao abrir. */
function estadoAtual() {
  return JSON.stringify({
    form: form.value,
    jornada: jornada.value.map(({ dia_semana, inicio, fim }) => ({ dia_semana, inicio, fim })),
    senha: novaSenha.value,
  })
}
const sujo = computed(() => editando.value !== null && estadoAtual() !== retrato)

function abrir(a) {
  editando.value = a
  form.value = a.id
    ? {
        nome: a.nome, login: a.login, email: a.email || '', perfil: a.perfil,
        estado: a.estado, fuso: a.fuso,
      }
    : vazio()
  jornada.value = (a.jornada || []).map((f) => comUid({
    dia_semana: f.dia_semana,
    inicio: (f.inicio || '').slice(0, 5),
    fim: (f.fim || '').slice(0, 5),
  }))
  novaSenha.value = ''
  erroModal.value = ''
  recado.value = ''
  retrato = estadoAtual()
}

function fechar() {
  editando.value = null
  erroModal.value = ''
}

/* A linha do owner: só o owner a abre, e o perfil dela não muda. */
const editandoOwner = computed(() => Boolean(editando.value?.owner))
/* Admin editando um admin: o perfil fica travado (só o owner muda). */
const perfilTravado = computed(() =>
  editandoOwner.value || (!souOwner.value && form.value.perfil === 'admin'))

function adicionarFaixa(dia) {
  jornada.value.push(comUid({ dia_semana: dia, inicio: '08:00', fim: '12:00' }))
}
function removerFaixa(faixa) {
  jornada.value = jornada.value.filter((f) => f !== faixa)
}
function faixasDe(dia) {
  return jornada.value.filter((f) => f.dia_semana === dia)
}

/* ---- duração e copiar (24/09) ----------------------------------------------
   🔵 Pedido dele: *"botões de ação rápida"* -- escolheu "copiar para os dias" e
   "mostrar a duração". */
function minutosDaFaixa(f) {
  const [hi, mi] = (f.inicio || '0:0').split(':').map(Number)
  const [hf, mf] = (f.fim || '0:0').split(':').map(Number)
  return Math.max(0, (hf * 60 + mf) - (hi * 60 + mi))
}
function horas(minutos) {
  const h = Math.floor(minutos / 60)
  const m = minutos % 60
  return m ? `${h}h${String(m).padStart(2, '0')}` : `${h}h`
}
const duracaoDoDia = (dia) => faixasDe(dia).reduce((s, f) => s + minutosDaFaixa(f), 0)
const duracaoDaSemana = computed(() => jornada.value.reduce((s, f) => s + minutosDaFaixa(f), 0))

const copiandoDe = ref(null)
const copiarPara = ref([])
const UTEIS = [1, 2, 3, 4, 5]
function abrirCopia(dia) {
  copiandoDe.value = dia
  // Dia útil copia para os outros dias úteis; fim de semana começa vazio.
  copiarPara.value = UTEIS.includes(dia) ? UTEIS.filter((d) => d !== dia) : []
}
function aplicarCopia() {
  const origem = faixasDe(copiandoDe.value)
  const destinos = copiarPara.value
  jornada.value = [
    ...jornada.value.filter((f) => !destinos.includes(f.dia_semana)),
    ...destinos.flatMap((d) => origem.map((f) => comUid({ dia_semana: d, inicio: f.inicio, fim: f.fim }))),
  ]
  copiandoDe.value = null
}

/* ---- afastamento (24/09) ---------------------------------------------------
   🔵 *"em caso de conversas em aberto, perguntar para qual usuario transferir
   elas 'abre modal de lista de usuarios', é obrigatório e dai executa"* --
   *"somente em caso de férias ou algo do tipo"*. */
const MOTIVOS_AFASTAMENTO = ['Férias', 'Licença', 'Atestado', 'Outro']
const afastando = ref(null)
const erroAfastamento = ref('')
const afastandoAgora = ref(false)

/* 🔵 25/09: *"um calendário já indica a saída e a volta, daí volta"*. A data
   é a do navegador, no formato do <input type="date"> (`sv-SE` dá AAAA-MM-DD
   no fuso local -- `toISOString` daria o dia em UTC, e às 21h já é amanhã). */
const diaISO = (somar = 0) => {
  const d = new Date()
  d.setDate(d.getDate() + somar)
  return d.toLocaleDateString('sv-SE')
}
const afastamentoVazio = () => ({ motivo: 'Férias', outro: '', de: diaISO(0), ate: '', para: null })
const afastamento = ref(afastamentoVazio())
const saidaFutura = computed(() => afastamento.value.de > diaISO(0))

/* Quem pode receber. HOJE: ativo, recebe transferência, não está offline nem
   afastado -- a mesma régua do backend (`pode_receber`). MARCADO: basta estar
   ativo e receber transferência; offline agora não importa, o que vale é o
   dia da saída (e, se nesse dia não puder, as conversas vão para a fila). */
function recebedoresPara(pessoa, futuro = false) {
  return atendentes.value.filter((a) =>
    a.ativo && a.transferivel && a.id !== pessoa?.id &&
    (futuro || (a.estado !== 'offline' && !a.afastamento_motivo)))
}
const recebedores = computed(() => recebedoresPara(afastando.value, saidaFutura.value))
const recebedoresInativar = computed(() => recebedoresPara(inativando.value))

/* O substituto de um afastamento marcado, pelo nome. */
const nomeDe = (id) => atendentes.value.find((a) => a.id === id)?.nome || 'quem foi escolhido'

function abrirAfastamento() {
  afastando.value = editando.value
  afastamento.value = afastamentoVazio()
  erroAfastamento.value = ''
}

/* Marcado para o futuro, o substituto é sempre obrigatório: até a saída
   podem chegar conversas. Hoje, só se houver conversa aberta. */
const precisaSubstituto = computed(() =>
  Boolean(afastando.value) && (saidaFutura.value || afastando.value.em_aberto > 0))

async function confirmarAfastamento() {
  const a = afastando.value
  const motivo = afastamento.value.motivo === 'Outro'
    ? afastamento.value.outro.trim() : afastamento.value.motivo
  if (!motivo) { erroAfastamento.value = 'Diga o motivo.'; return }
  if (!afastamento.value.ate) { erroAfastamento.value = 'Escolha o dia da volta.'; return }
  if (afastamento.value.ate <= afastamento.value.de) {
    erroAfastamento.value = 'A volta tem de ser depois da saída.'
    return
  }
  if (precisaSubstituto.value && !afastamento.value.para) {
    erroAfastamento.value = saidaFutura.value
      ? 'Escolha quem vai receber as conversas no dia da saída.'
      : 'Escolha quem vai receber as conversas em aberto.'
    return
  }
  afastandoAgora.value = true
  erroAfastamento.value = ''
  try {
    const r = await api.post(`/api/atendentes/${a.id}/afastar`, {
      motivo, de: afastamento.value.de, ate: afastamento.value.ate,
      transferir_para: afastamento.value.para,
    })
    if (r.agendado) {
      recado.value = `Afastamento de ${a.nome} marcado: sai em ${dataCurta(afastamento.value.de)}, volta em ${dataCurta(afastamento.value.ate)}.`
    } else {
      recado.value = r.transferidas
        ? `${a.nome} afastado (${motivo}) até ${dataCurta(afastamento.value.ate)}. ${r.transferidas} conversa(s) transferida(s).`
        : `${a.nome} afastado (${motivo}) até ${dataCurta(afastamento.value.ate)}.`
    }
    afastando.value = null
    fechar()
    await carregar()
  } catch (e) {
    erroAfastamento.value = e instanceof ErroDeApi ? e.message : 'Não consegui afastar.'
    // ⚠️ Falha pela metade transfere parte das conversas: relê para o número
    // de "em aberto" não ficar mentindo (achado da auditoria de 24/09).
    await carregar()
    const atual = atendentes.value.find((x) => x.id === a.id)
    if (atual) afastando.value = atual
  } finally {
    afastandoAgora.value = false
  }
}

async function encerrarAfastamento() {
  const eraMarcado = !editando.value.afastamento_motivo
  try {
    await api.post(`/api/atendentes/${editando.value.id}/retornar`, {})
    recado.value = eraMarcado
      ? `O afastamento marcado de ${editando.value.nome} foi cancelado.`
      : `${editando.value.nome} voltou do afastamento e está disponível.`
    fechar()
    await carregar()
  } catch (e) {
    erroModal.value = e instanceof ErroDeApi ? e.message : 'Não consegui encerrar o afastamento.'
  }
}

const dataCurta = (iso) => (iso ? new Date(iso + 'T12:00').toLocaleDateString('pt-BR') : '')
const ROTULO_ESTADO = Object.fromEntries(ESTADOS.map((e) => [e.valor, e.rotulo]))

async function salvar() {
  salvando.value = true
  erroModal.value = ''
  try {
    const email = form.value.email.trim() || null
    /* 🚨 O BANCO EXIGE LOGIN, E O ADMIN NÃO VÊ O CAMPO. Conta nova criada por
       ele nasce com o login igual ao e-mail -- e por isso, para ele, o e-mail
       é obrigatório na criação. Na edição o login vai como estava. */
    let login = form.value.login.trim()
    if (!souOwner.value && !editando.value.id) {
      if (!email) {
        erroModal.value = 'Informe o e-mail: é por ele que a pessoa entra.'
        return
      }
      login = email
    }
    const corpo = { ...form.value, login, email }
    const alvo = editando.value.id
      ? await api.put(`/api/atendentes/${editando.value.id}`, corpo)
      : await api.post('/api/atendentes', corpo)

    await api.put(`/api/atendentes/${alvo.id}/jornada`, {
      faixas: jornada.value.map(({ dia_semana, inicio, fim }) => ({ dia_semana, inicio, fim })),
    })

    if (novaSenha.value) {
      await api.post(`/api/atendentes/${alvo.id}/senha`, { senha: novaSenha.value })
    }
    recado.value = editando.value.id ? `${alvo.nome}: alterações salvas.` : `${alvo.nome} criado.`
    fechar()
    await carregar()
  } catch (e) {
    erroModal.value = e instanceof ErroDeApi ? e.message : 'Não consegui salvar.'
  } finally {
    salvando.value = false
  }
}
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Atendentes</h1>
        <AjudaDaTela>Quem atende, em quais times e em que horário. Os times de cada um se definem em Times.</AjudaDaTela>
      </div>
      <div class="cabecalho__acoes">
        <label class="linha pequeno fraco">
          <input v-model="incluirInativos" type="checkbox" @change="carregar" />
          mostrar inativos
        </label>
        <!-- ⚠️ Para o admin é chip, não link: Configurações › Geral é do
             owner, e o link o levaria a uma tela que ele não abre. -->
        <component
          :is="souOwner ? RouterLink : 'span'"
          class="chip"
          :class="jornadaAtiva ? 'chip--ok' : ''"
          :to="souOwner ? '/config/geral' : undefined"
          :title="jornadaAtiva
            ? 'A fila avisa quem está fora do horário — muda-se em Configurações › Geral'
            : 'A escala fica gravada e não afeta a fila — liga-se em Configurações › Geral'"
        >
          <i class="bi" :class="jornadaAtiva ? 'bi-toggle-on' : 'bi-toggle-off'"
             aria-hidden="true"></i>
          Jornada {{ jornadaAtiva ? 'ligada' : 'desligada' }}
        </component>
        <button class="botao botao--primario" type="button" @click="abrir({})">
          <i class="bi bi-person-plus" aria-hidden="true"></i> Novo atendente
        </button>
      </div>
    </header>

    <!-- O resumo: quantos são, quanto carregam agora, quanto fecharam. -->
    <section v-if="!carregando && atendentes.length" class="resumo" aria-label="Resumo da equipe">
      <div class="resumo__item">
        <span class="resumo__numero">{{ resumo.ativos }}</span>
        <span class="resumo__rotulo">ativos</span>
      </div>
      <div class="resumo__item">
        <span class="resumo__numero">{{ resumo.emAberto }}</span>
        <span class="resumo__rotulo">conversas em aberto</span>
      </div>
      <div class="resumo__item">
        <span class="resumo__numero">{{ resumo.concluidas }}</span>
        <span class="resumo__rotulo">concluídas em 7 dias</span>
      </div>
      <div class="resumo__item" :class="{ 'resumo__item--erro': resumo.semAcesso }">
        <span class="resumo__numero">{{ resumo.semAcesso }}</span>
        <span class="resumo__rotulo">sem como entrar</span>
      </div>
    </section>

    <p v-if="recado" class="aviso aviso--ok" role="status">
      <i class="bi bi-check2-circle aviso__icone" aria-hidden="true"></i>
      <span>{{ recado }}</span>
    </p>

    <p v-if="erro" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>{{ erro }}</span>
    </p>

    <p v-if="carregando" class="linha fraco">
      <span class="girando"></span> Lendo os atendentes…
    </p>

    <div v-else-if="!atendentes.length" class="vazio">
      <i class="bi bi-people vazio__icone" aria-hidden="true"></i>
      <p class="vazio__titulo">Nenhum atendente</p>
      <p>Crie o primeiro em "Novo atendente".</p>
    </div>

    <section v-else class="cartao lista">
      <div class="tabela--rolavel">
        <table class="tabela">
          <thead>
            <tr>
              <th>Atendente</th>
              <th>Perfil</th>
              <th>Times</th>
              <th>Jornada</th>
              <th class="rh__num">Conversas</th>
              <th>Entra por</th>
              <th><span class="so-leitor">Ações</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in atendentes" :key="a.id" :class="{ 'linha--inativa': !a.ativo }">
              <td>
                <div class="pessoa">
                  <span class="avatar" :style="{ background: corDaInicial(a.nome) }" aria-hidden="true">
                    <img v-if="a.tem_foto" :src="`/api/atendentes/${a.id}/foto`" alt="" />
                    <template v-else>{{ iniciais(a.nome) }}</template>
                  </span>
                  <div class="pessoa__texto">
                    <strong class="pessoa__nome">{{ a.nome }}</strong>
                    <span v-if="a.email" class="pessoa__linha">{{ a.email }}</span>
                    <span v-if="souOwner" class="pessoa__linha mono">{{ a.login }}</span>
                    <span class="pessoa__estado">
                      <span class="estado" :class="`estado--${a.estado}`">{{ ROTULO_ESTADO[a.estado] }}</span>
                      <span v-if="a.estado_automatico" class="apagado pequeno">· pelo sistema</span>
                    </span>
                    <span v-if="a.afastamento_motivo" class="chip chip--pequeno chip--aviso">
                      <i class="bi bi-airplane" aria-hidden="true"></i>
                      {{ a.afastamento_motivo }}<template v-if="a.afastado_ate"> até {{ dataCurta(a.afastado_ate) }}</template>
                    </span>
                    <span v-else-if="a.afasta_em" class="chip chip--pequeno">
                      <i class="bi bi-calendar-event" aria-hidden="true"></i>
                      {{ a.afasta_motivo }} de {{ dataCurta(a.afasta_em) }} a {{ dataCurta(a.afasta_ate) }}
                    </span>
                    <span v-if="!a.ativo" class="chip chip--pequeno">inativo</span>
                  </div>
                </div>
              </td>
              <td><span class="chip perfil" :class="`perfil--${a.perfil}`">{{ ROTULO_PERFIL[a.perfil] || a.perfil }}</span></td>
              <td>
                <div class="chips">
                  <span v-for="t in a.times" :key="t.id" class="chip chip--pequeno">{{ t.nome }}</span>
                  <span v-if="!a.times.length" class="apagado pequeno">nenhum</span>
                </div>
              </td>
              <td class="pequeno jornada">
                <!-- 🚨 "FORA DO HORÁRIO" E "SEM JORNADA" SÃO COISAS
                     DIFERENTES. Sem a distinção, quem nunca cadastrou escala
                     aparece como se estivesse fora do expediente. -->
                <template v-if="a.tem_jornada">
                  <span class="fraco">{{ diasDaJornada(a) }}</span>
                  <br />
                  <span class="apagado">{{ horasSemana(a) }} h/semana</span>
                  <span v-if="jornadaAtiva && !a.no_horario"
                        class="chip chip--aviso chip--pequeno">fora do horário</span>
                </template>
                <span v-else class="apagado">sem jornada</span>
              </td>
              <!-- Os dois números que fazem esta tela ser de RH, numa coluna só
                   desde 24/09: em duas, a tabela passava da largura e empurrava
                   a coluna de ações para fora da tela (visto na prévia). -->
              <td class="rh__num conversas">
                <strong>{{ a.em_aberto }}</strong> <span class="apagado">abertas</span>
                <br />
                <span class="apagado pequeno">{{ a.concluidas_semana }} concluídas em 7 dias</span>
              </td>
              <td>
                <span class="chip chip--pequeno" :class="acessoDe(a).classe">
                  <i class="bi" :class="acessoDe(a).icone" aria-hidden="true"></i>
                  {{ acessoDe(a).rotulo }}
                </span>
              </td>
              <td>
                <div class="acoes">
                  <button v-if="souOwner || !a.owner"
                          class="botao botao--pequeno botao--contorno" type="button" @click="abrir(a)">
                    <i class="bi bi-pencil" aria-hidden="true"></i> Editar
                  </button>
                  <!-- 🔵 25/09: o "Desligar" daqui virou o interruptor
                       Ativo/Inativo, dentro do Editar -- decisão dele. -->
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <p class="rodape apagado pequeno">
      Atendente não é apagado: inativo, fica sem acesso, e o histórico continua com o nome dele.
      <template v-if="!jornadaAtiva">
        A jornada está <strong>desligada</strong>: liga-se em Configurações › Geral.
      </template>
    </p>

    <!-- ---------------------------------------------------------- edição -->
    <ModalEdicao
      v-if="editando"
      :titulo="editando.id ? editando.nome : 'Novo atendente'"
      :subtitulo="editando.id ? (ROTULO_PERFIL[editando.perfil] || editando.perfil) : 'A conta entra pelo Google com o e-mail informado'"
      :sujo="sujo"
      :salvando="salvando"
      @salvar="salvar"
      @fechar="fechar"
    >
      <template #icone>
        <span class="avatar avatar--grande" :style="{ background: corDaInicial(form.nome || '?') }" aria-hidden="true">
          <img v-if="editando.tem_foto" :src="`/api/atendentes/${editando.id}/foto`" alt="" />
          <template v-else>{{ iniciais(form.nome || '?') }}</template>
        </span>
      </template>

      <section class="secao">
        <h2 class="secao__titulo">Identificação</h2>
        <div class="grade">
          <label class="campo">
            <span class="campo__rotulo">Nome de exibição</span>
            <input v-model="form.nome" class="campo__entrada" maxlength="200" />
            <span class="campo__ajuda">É o que o cliente e a equipe veem.</span>
          </label>

          <label class="campo">
            <span class="campo__rotulo">E-mail</span>
            <input v-model="form.email" class="campo__entrada" type="email" maxlength="200"
                   autocapitalize="off" :disabled="editandoOwner && !souOwner" />
            <span class="campo__ajuda">É por ele que a pessoa entra, pelo Google.</span>
          </label>

          <label v-if="souOwner" class="campo">
            <span class="campo__rotulo">Login</span>
            <input v-model="form.login" class="campo__entrada mono" maxlength="60" autocapitalize="off" />
            <span class="campo__ajuda">Só você vê. A entrada é pelo e-mail.</span>
          </label>

          <label class="campo">
            <span class="campo__rotulo">Perfil</span>
            <select v-model="form.perfil" class="campo__entrada" :disabled="perfilTravado">
              <option v-if="perfilTravado" :value="form.perfil">{{ ROTULO_PERFIL[form.perfil] }}</option>
              <template v-else>
                <option v-for="p in perfisOferecidos" :key="p" :value="p">{{ ROTULO_PERFIL[p] }}</option>
              </template>
            </select>
            <span class="campo__ajuda">
              <template v-if="editandoOwner || perfilTravado">Este perfil não pode ser alterado.</template>
              <template v-else>Define as telas que a pessoa vê.</template>
            </span>
          </label>

          <label class="campo">
            <span class="campo__rotulo">Estado</span>
            <select v-model="form.estado" class="campo__entrada">
              <option v-for="e in ESTADOS" :key="e.valor" :value="e.valor">{{ e.rotulo }}</option>
            </select>
            <span class="campo__ajuda">A própria pessoa também muda, na Minha conta.</span>
          </label>
          <!-- 🚨 O TETO DE CONVERSAS SAIU DA TELA (25/08): a coluna era gravada
               e LIDA POR NADA. Volta quando houver distribuição que o use. -->
        </div>
      </section>

      <!-- 🔵 25/09: *"um status de inativo e ativo no perfil do atendente, um
           interruptor"*. É ação na hora, como o Afastar: não espera o Salvar.
           Inativar abre a confirmação (e quem recebe as conversas); reativar
           é direto. A própria conta não tem interruptor. -->
      <section v-if="editando.id && !editandoASiMesmo" class="secao">
        <h2 class="secao__titulo">Acesso</h2>
        <label class="interruptor situacao">
          <input type="checkbox" role="switch" :checked="editando.ativo"
                 :disabled="sujo || trocandoAtivo" @click.prevent="alternarAtivo" />
          <span>
            <strong>{{ editando.ativo ? 'Ativo' : 'Inativo' }}</strong>
            <small class="apagado">
              {{ editando.ativo
                ? 'Entra no painel e pode receber conversa.'
                : 'Não entra no painel. A conta, os times e o histórico ficam; religar devolve o acesso.' }}
            </small>
          </span>
        </label>
        <span v-if="sujo" class="campo__ajuda">Salve ou cancele as alterações antes de mudar o acesso.</span>
      </section>

      <!-- 🔵 SÓ LEITURA DESDE 24/09, decisão dele: *"no cadastro do
           atendentes pode ter os times dos quais são vinculados, mas só
           visualizar"*. Quem grava é a CAD_2.2. -->
      <section v-if="editando.id" class="secao">
        <h2 class="secao__titulo">Times</h2>
        <div class="chips">
          <span v-for="t in editando.times" :key="t.id" class="chip">{{ t.nome }}</span>
          <span v-if="!editando.times.length" class="apagado pequeno">Não está em nenhum time.</span>
        </div>
        <p class="campo__ajuda">
          Quem entra em cada time se define em <RouterLink to="/cadastro/times">Times</RouterLink>.
        </p>
      </section>

      <section class="secao">
        <h2 class="secao__titulo secao__titulo--linha">
          Jornada
          <span class="secao__total">{{ horas(duracaoDaSemana) }} por semana</span>
        </h2>
        <p class="campo__ajuda secao__ajuda">
          O almoço é o <strong>intervalo entre duas faixas do mesmo dia</strong>:
          08:00–12:00 e 13:00–18:00.
        </p>
        <div class="dias">
          <div v-for="(nome, dia) in DIAS" :key="dia" class="dia">
            <span class="dia__nome">{{ nome }}</span>
            <div class="dia__faixas">
              <div v-for="faixa in faixasDe(dia)" :key="faixa.uid" class="faixa">
                <input v-model="faixa.inicio" class="campo__entrada campo--hora" type="time"
                       :aria-label="`Início, ${nome}`" />
                <span class="apagado">até</span>
                <input v-model="faixa.fim" class="campo__entrada campo--hora" type="time"
                       :aria-label="`Fim, ${nome}`" />
                <button class="botao botao--icone botao--pequeno botao--fantasma" type="button"
                        :aria-label="`Remover faixa de ${nome}`" @click="removerFaixa(faixa)">
                  <i class="bi bi-x-lg" aria-hidden="true"></i>
                </button>
              </div>
              <div class="dia__acoes">
                <button class="botao botao--pequeno botao--fantasma" type="button"
                        @click="adicionarFaixa(dia)">
                  <i class="bi bi-plus-lg" aria-hidden="true"></i> faixa
                </button>
                <button v-if="faixasDe(dia).length" class="botao botao--pequeno botao--fantasma"
                        type="button" @click="abrirCopia(dia)">
                  <i class="bi bi-copy" aria-hidden="true"></i> Copiar para outros dias
                </button>
              </div>
              <div v-if="copiandoDe === dia" class="copia">
                <span class="pequeno fraco">Copiar {{ nome }} para:</span>
                <div class="copia__dias">
                  <template v-for="(outro, d) in DIAS" :key="d">
                    <label v-if="d !== dia" class="copia__dia"
                           :class="{ 'copia__dia--marcado': copiarPara.includes(d) }">
                      <input v-model="copiarPara" type="checkbox" :value="d" />
                      {{ DIAS_CURTOS[d] }}
                    </label>
                  </template>
                </div>
                <div class="linha">
                  <button class="botao botao--pequeno botao--primario" type="button"
                          :disabled="!copiarPara.length" @click="aplicarCopia">Copiar</button>
                  <button class="botao botao--pequeno botao--fantasma" type="button"
                          @click="copiandoDe = null">Cancelar</button>
                </div>
                <span class="campo__ajuda">O horário dos dias marcados é substituído.</span>
              </div>
            </div>
            <span class="dia__duracao" :class="{ apagado: !duracaoDoDia(dia) }">
              {{ duracaoDoDia(dia) ? horas(duracaoDoDia(dia)) : 'folga' }}
            </span>
          </div>
        </div>
      </section>

      <section v-if="editando.id && editando.ativo" class="secao">
        <h2 class="secao__titulo">Afastamento</h2>
        <template v-if="editando.afastamento_motivo">
          <p class="aviso aviso--atencao pequeno">
            <i class="bi bi-airplane aviso__icone" aria-hidden="true"></i>
            <span>
              Afastado: <strong>{{ editando.afastamento_motivo }}</strong><template
              v-if="editando.afastado_ate">, volta em {{ dataCurta(editando.afastado_ate) }}</template>.
              Não recebe conversa. Na volta, o afastamento termina sozinho.
            </span>
          </p>
          <button class="botao botao--contorno" type="button" @click="encerrarAfastamento">
            Encerrar afastamento agora
          </button>
        </template>
        <template v-else-if="editando.afasta_em">
          <p class="aviso aviso--info pequeno">
            <i class="bi bi-calendar-event aviso__icone" aria-hidden="true"></i>
            <span>
              Marcado: <strong>{{ editando.afasta_motivo }}</strong>, sai em
              {{ dataCurta(editando.afasta_em) }} e volta em {{ dataCurta(editando.afasta_ate) }}.
              Na saída, as conversas abertas vão para {{ nomeDe(editando.afasta_substituto_id) }}.
            </span>
          </p>
          <button class="botao botao--contorno" type="button" @click="encerrarAfastamento">
            Cancelar afastamento marcado
          </button>
        </template>
        <template v-else>
          <p class="campo__ajuda secao__ajuda">
            Férias, licença, atestado. Na saída a pessoa fica offline e não recebe
            conversa; as abertas vão para quem você escolher. Na volta, termina sozinho.
          </p>
          <button class="botao botao--contorno" type="button" :disabled="sujo"
                  @click="abrirAfastamento">
            <i class="bi bi-airplane" aria-hidden="true"></i> Afastar
          </button>
          <span v-if="sujo" class="campo__ajuda">Salve ou cancele as alterações antes de afastar.</span>
        </template>
      </section>

      <section class="secao">
        <h2 class="secao__titulo">Senha</h2>
        <label class="campo campo--estreito">
          <span class="campo__rotulo">
            {{ editando.tem_senha ? 'Trocar a senha' : 'Definir uma senha' }}
          </span>
          <input v-model="novaSenha" class="campo__entrada" type="password"
                 autocomplete="new-password" minlength="10" maxlength="256"
                 placeholder="deixe em branco para não mexer" />
          <span class="campo__ajuda">
            Opcional: quem tem e-mail entra pelo Google. Pelo menos 10 caracteres.
          </span>
        </label>
      </section>

      <p v-if="erroModal" class="aviso aviso--erro" role="alert">
        <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
        <span>{{ erroModal }}</span>
      </p>
    </ModalEdicao>

    <div v-if="afastando" class="modal afastar" @click.self="afastando = null">
      <div class="modal__caixa afastar__caixa" role="dialog" aria-modal="true"
           :aria-label="`Afastar ${afastando.nome}`">
        <p class="modal__titulo">Afastar {{ afastando.nome }}</p>
        <p class="modal__texto pequeno">
          Na saída, fica offline e não recebe conversa. Na volta, o afastamento termina sozinho.
        </p>

        <div class="grade">
          <label class="campo">
            <span class="campo__rotulo">Motivo</span>
            <select v-model="afastamento.motivo" class="campo__entrada">
              <option v-for="m in MOTIVOS_AFASTAMENTO" :key="m" :value="m">{{ m }}</option>
            </select>
          </label>
          <label v-if="afastamento.motivo === 'Outro'" class="campo">
            <span class="campo__rotulo">Qual?</span>
            <input v-model="afastamento.outro" class="campo__entrada" maxlength="60" />
          </label>
        </div>
        <!-- 🔵 25/09: *"um calendário já indica a saída e a volta"*. -->
        <div class="grade">
          <label class="campo">
            <span class="campo__rotulo">Saída</span>
            <input v-model="afastamento.de" class="campo__entrada" type="date" :min="diaISO(0)" />
          </label>
          <label class="campo">
            <span class="campo__rotulo">Volta <span class="obrigatorio">*</span></span>
            <input v-model="afastamento.ate" class="campo__entrada" type="date"
                   :min="afastamento.de" />
          </label>
        </div>

        <fieldset v-if="precisaSubstituto" class="bloco">
          <legend class="campo__rotulo">
            <template v-if="saidaFutura">Quem recebe as conversas abertas no dia da saída</template>
            <template v-else>Quem recebe as {{ afastando.em_aberto }} conversa(s) em aberto</template>
            <span class="obrigatorio">*</span>
          </legend>
          <div class="recebedores">
            <label v-for="r in recebedores" :key="r.id" class="recebedor"
                   :class="{ 'recebedor--marcado': afastamento.para === r.id }">
              <input v-model="afastamento.para" type="radio" name="recebedor" :value="r.id" />
              <span class="avatar avatar--pequeno" :style="{ background: corDaInicial(r.nome) }"
                    aria-hidden="true">{{ iniciais(r.nome) }}</span>
              <span class="recebedor__nome">{{ r.nome }}</span>
              <span class="estado" :class="`estado--${r.estado}`">{{ ROTULO_ESTADO[r.estado] }}</span>
            </label>
            <p v-if="!recebedores.length" class="aviso aviso--erro pequeno">
              Ninguém disponível para receber agora (todos offline ou afastados).
            </p>
          </div>
          <p v-if="saidaFutura" class="campo__ajuda">
            Se no dia essa pessoa estiver offline, as conversas vão para a fila.
          </p>
        </fieldset>
        <p v-else class="aviso aviso--info pequeno">
          <i class="bi bi-check2-circle aviso__icone" aria-hidden="true"></i>
          <span>Sem conversas em aberto: nada a transferir.</span>
        </p>

        <p v-if="erroAfastamento" class="aviso aviso--erro" role="alert">{{ erroAfastamento }}</p>

        <div class="modal__acoes">
          <button class="botao botao--contorno" type="button" @click="afastando = null">Cancelar</button>
          <button class="botao botao--primario" type="button"
                  :disabled="afastandoAgora || !afastamento.ate || (precisaSubstituto && !afastamento.para)"
                  @click="confirmarAfastamento">
            <template v-if="saidaFutura">Marcar afastamento</template>
            <template v-else>{{ afastando.em_aberto ? `Afastar e transferir ${afastando.em_aberto}` : 'Afastar' }}</template>
          </button>
        </div>
      </div>
    </div>

    <!-- 🔵 25/09: inativar confirma e pede quem recebe as conversas abertas. -->
    <div v-if="inativando" class="modal afastar" @click.self="inativando = null">
      <div class="modal__caixa afastar__caixa" role="dialog" aria-modal="true"
           :aria-label="`Inativar ${inativando.nome}`">
        <p class="modal__titulo">Inativar {{ inativando.nome }}?</p>
        <p class="modal__texto">
          A pessoa <strong>não entra mais no painel</strong>, e a sessão aberta cai.
          A conta, os times e o histórico ficam: religar devolve o acesso.
        </p>

        <fieldset v-if="inativando.em_aberto" class="bloco">
          <legend class="campo__rotulo">
            Quem recebe as {{ inativando.em_aberto }} conversa(s) em aberto <span class="obrigatorio">*</span>
          </legend>
          <div class="recebedores">
            <label v-for="r in recebedoresInativar" :key="r.id" class="recebedor"
                   :class="{ 'recebedor--marcado': inativarPara === r.id }">
              <input v-model="inativarPara" type="radio" name="recebedor-inativar" :value="r.id" />
              <span class="avatar avatar--pequeno" :style="{ background: corDaInicial(r.nome) }"
                    aria-hidden="true">{{ iniciais(r.nome) }}</span>
              <span class="recebedor__nome">{{ r.nome }}</span>
              <span class="estado" :class="`estado--${r.estado}`">{{ ROTULO_ESTADO[r.estado] }}</span>
            </label>
            <p v-if="!recebedoresInativar.length" class="aviso aviso--erro pequeno">
              Ninguém disponível para receber agora (todos offline ou afastados).
            </p>
          </div>
        </fieldset>

        <p v-if="erroInativar" class="aviso aviso--erro" role="alert">{{ erroInativar }}</p>

        <div class="modal__acoes">
          <button class="botao botao--contorno" type="button" @click="inativando = null">Cancelar</button>
          <button class="botao botao--perigo" type="button"
                  :disabled="trocandoAtivo || (inativando.em_aberto > 0 && !inativarPara)"
                  @click="gravarAtivo(inativando, false, inativarPara)">
            {{ inativando.em_aberto ? `Inativar e transferir ${inativando.em_aberto}` : 'Inativar' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tela { max-width: 1180px; }

.tela__cabecalho {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--e-4);
  flex-wrap: wrap;
  margin-bottom: var(--e-5);
}
.tela__cabecalho p { max-width: var(--largura-texto); margin-top: var(--e-1); }
.cabecalho__acoes { display: flex; align-items: center; gap: var(--e-3); flex-wrap: wrap; }

/* ---- resumo ---- */
.resumo {
  display: grid;
  /* 130px: no celular cabem dois por linha, em vez de quatro cartões
     empilhados ocupando a tela inteira antes da lista. */
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: var(--e-3);
  margin-bottom: var(--e-5);
}
.resumo__item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--e-3) var(--e-4);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-lg);
  background: var(--superficie);
  box-shadow: var(--sombra-1);
}
.resumo__numero {
  font-size: var(--txt-2xl);
  font-weight: var(--peso-forte);
  line-height: 1.1;
  color: var(--texto);
  font-variant-numeric: tabular-nums;
}
.resumo__rotulo { font-size: var(--txt-sm); color: var(--texto-apagado); }
.resumo__item--erro { border-color: var(--erro-borda); background: var(--erro-suave); }
.resumo__item--erro .resumo__numero { color: var(--erro); }

.aviso { margin-bottom: var(--e-4); }

/* ---- lista ---- */
.lista { overflow: hidden; margin-bottom: var(--e-4); }
.lista .tabela td { vertical-align: middle; }

.pessoa { display: flex; align-items: center; gap: var(--e-3); min-width: 200px; }
.pessoa__texto { display: flex; flex-direction: column; min-width: 0; }
.pessoa__nome { color: var(--texto); }
.pessoa__linha { font-size: var(--txt-sm); color: var(--texto-apagado); overflow-wrap: anywhere; }

.avatar {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: var(--r-full);
  overflow: hidden;
  color: #fff;
  font-size: var(--txt-sm);
  font-weight: var(--peso-forte);
  box-shadow: 0 0 0 2px var(--superficie), 0 0 0 3px var(--borda);
}
.avatar img { width: 100%; height: 100%; object-fit: cover; }
.avatar--grande { width: 44px; height: 44px; font-size: var(--txt-md); }

.chips { display: flex; flex-wrap: wrap; gap: var(--e-1); max-width: 190px; }

.perfil { font-weight: var(--peso-medio); }
.perfil--owner { background: var(--acento-suave); border-color: var(--acento-borda); color: var(--acento); }
.perfil--admin { background: var(--info-suave); border-color: var(--info-borda); color: var(--info); }

.rh__num { text-align: right; font-variant-numeric: tabular-nums; }
.conversas { white-space: nowrap; }

.acoes { display: flex; gap: var(--e-2); justify-content: flex-end; flex-wrap: nowrap; }
.jornada { min-width: 96px; }

.linha--inativa td { opacity: .55; }

.rodape { margin: 0; }

/* ---- modal ---- */
.secao { padding-bottom: var(--e-5); margin-bottom: var(--e-5); border-bottom: var(--borda-fina) solid var(--borda); }
.secao:last-of-type { border-bottom: 0; margin-bottom: 0; padding-bottom: 0; }
.secao__titulo {
  margin: 0 0 var(--e-3);
  font-size: var(--txt-sm);
  font-weight: var(--peso-forte);
  letter-spacing: .04em;
  text-transform: uppercase;
  color: var(--texto-fraco);
}
.secao__ajuda { margin: 0 0 var(--e-3); }

.grade {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  column-gap: var(--e-4);
}
.campo--estreito { max-width: 360px; margin-bottom: 0; }

.dias {
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
  overflow: hidden;
}
/* Grade, não flex: no celular o nome e a duração vão para cima e as faixas
   ganham a largura toda. Espremidas entre os dois, cada campo de hora ia
   para uma linha (visto na prévia de 24/09). */
.dia {
  display: grid;
  grid-template-columns: 84px minmax(0, 1fr) auto;
  align-items: start;
  column-gap: var(--e-3);
  row-gap: var(--e-2);
  padding: var(--e-2) var(--e-3);
}
@media (max-width: 640px) {
  .dia { grid-template-columns: minmax(0, 1fr) auto; }
  .dia__faixas { grid-column: 1 / -1; grid-row: 2; }
  .dia__duracao { grid-column: 2; grid-row: 1; }
  .dia .faixa { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr) auto; }
  .dia .campo--hora { min-width: 0; width: 100%; padding-left: var(--e-2); padding-right: var(--e-2); }
}
.dia + .dia { border-top: var(--borda-fina) solid var(--borda); }
.dia:nth-child(even) { background: var(--superficie-2); }
.dia__nome { padding-top: 8px; font-weight: var(--peso-medio); }
.dia__faixas { display: flex; flex-direction: column; gap: var(--e-2); flex: 1; min-width: 0; }
.dia__mais { align-self: flex-start; }
.faixa { display: flex; align-items: center; gap: var(--e-2); flex-wrap: wrap; }
.campo--hora { width: auto; min-width: 7.5rem; }

.secao__titulo--linha { display: flex; justify-content: space-between; align-items: baseline; }
.secao__total { font-weight: var(--peso-normal); letter-spacing: 0; text-transform: none; color: var(--texto-apagado); }
.dia__acoes { display: flex; flex-wrap: wrap; gap: var(--e-1); }
.dia__duracao { flex: none; min-width: 3.5rem; padding-top: 8px; text-align: right; font-variant-numeric: tabular-nums; font-weight: var(--peso-medio); }
.copia {
  display: flex; flex-direction: column; gap: var(--e-2);
  padding: var(--e-3); border: var(--borda-fina) solid var(--acento-borda);
  border-radius: var(--r-md); background: var(--acento-suave);
}
.copia__dias { display: flex; flex-wrap: wrap; gap: var(--e-1); }
.copia__dia {
  display: inline-flex; align-items: center; gap: 4px; padding: 4px var(--e-2);
  border: var(--borda-fina) solid var(--borda); border-radius: var(--r-full);
  background: var(--superficie); font-size: var(--txt-sm); cursor: pointer;
}
.copia__dia--marcado { border-color: var(--acento); color: var(--acento); }
.copia__dia input { accent-color: var(--acento); }

/* Estado: bolinha + palavra. Cor sozinha não diz nada a quem não a distingue. */
.pessoa__estado { display: inline-flex; align-items: center; flex-wrap: wrap; column-gap: 4px; }
.pessoa__estado > span { white-space: nowrap; }
.estado { white-space: nowrap; display: inline-flex; align-items: center; gap: 5px; font-size: var(--txt-sm); color: var(--texto-fraco); }
.estado::before { content: ''; width: 8px; height: 8px; border-radius: 50%; background: var(--texto-apagado); }
.estado--disponivel::before { background: var(--ok); }
.estado--ausente::before { background: var(--aviso); }
.estado--nao_perturbe::before { background: var(--erro); }

/* O interruptor Ativo/Inativo (25/09): mesmo desenho do da Geral. */
.interruptor { display: flex; align-items: flex-start; gap: var(--e-3); cursor: pointer; }
.interruptor input { width: 18px; height: 18px; margin-top: 3px; accent-color: var(--acento); flex: none; }
.interruptor span { display: flex; flex-direction: column; }
.interruptor small { font-size: var(--txt-sm); }

.afastar { z-index: calc(var(--z-modal) + 1); }
.afastar__caixa { max-width: 520px; }
.bloco { border: 0; padding: 0; margin: 0 0 var(--e-3); }
.obrigatorio { color: var(--erro); }
.recebedores { display: flex; flex-direction: column; gap: var(--e-2); max-height: 260px; overflow-y: auto; }
.recebedor {
  display: flex; align-items: center; gap: var(--e-2); min-height: var(--altura-toque);
  padding: var(--e-2) var(--e-3); border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md); cursor: pointer;
}
.recebedor:hover { background: var(--superficie-2); }
.recebedor--marcado { border-color: var(--acento-borda); background: var(--acento-suave); }
.recebedor input { accent-color: var(--acento); }
.recebedor__nome { flex: 1; }
.avatar--pequeno { width: 26px; height: 26px; font-size: var(--txt-xs); box-shadow: none; }
</style>
