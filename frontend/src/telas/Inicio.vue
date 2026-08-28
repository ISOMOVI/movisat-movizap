<script setup>
/* ============================================================================
   INI_1.1 — Tela inicial
   ----------------------------------------------------------------------------
   É a primeira tela do registro, e por isso o destino de TODO login: a rota
   `/` manda para `sessao.telas[0].rota`. Vale igual para a entrada por senha
   e pela do Google.

   A tela em três faixas (25/08):
     A. O MEU DIA      — o que espera VOCÊ, e o que você já concluiu
     B. A OPERAÇÃO     — o que espera a equipe
     C. só owner       — canais, fila técnica, alcance do cadastro
        C'. quem não é owner recebe no lugar "Como você está configurado"

   🚨 A RÉGUA DESTA TELA: se o número está em zero e isso é bom, ele encolhe.
   O que cresce é o que espera alguém.

   ⚠️ O QUE MUDOU NA RÉGUA. Ela dizia "nenhum número de volume, isso é
   relatório". Continua verdade para VOLUME -- mensagens processadas não entra.
   Mas DESFECHO entra desde 25/08, por decisão do usuário: atendimento
   concluído é o outro lado do que está aberto, e é o que faz esta tela ser um
   mini-CRM de atendimento. Continua sem gráfico: número, período e rota.

   ⚠️ Cada número é clicável e leva para onde se resolve. Número que não leva
   a lugar nenhum é enfeite: quem olha não tem o que fazer com ele.
   ============================================================================ */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

import { api } from '../api/cliente.js'
import { sessao } from '../estado/sessao.js'

const router = useRouter()
const dados = ref(null)
const agenda = ref(null)
const erro = ref('')
let relogio = null

/* O período do cartão de desfecho. Fica no navegador porque é preferência de
   leitura, não configuração: quem olha "mês" hoje quer "mês" amanhã, e isso
   não vale uma coluna no banco. */
const PERIODOS = [
  { valor: 'hoje', rotulo: 'hoje' },
  { valor: 'semana', rotulo: '7 dias' },
  { valor: 'mes', rotulo: '30 dias' },
]
const periodo = ref(localStorage.getItem('movizap.inicio.periodo') || 'hoje')

function trocarPeriodo(valor) {
  periodo.value = valor
  localStorage.setItem('movizap.inicio.periodo', valor)
}

const saudacao = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return 'Bom dia'
  if (h < 18) return 'Boa tarde'
  return 'Boa noite'
})

const agora = computed(() =>
  new Date().toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }),
)

async function carregar() {
  try {
    dados.value = await api.get('/api/inicio')
    erro.value = ''
  } catch {
    erro.value = 'Não consegui ler o estado do painel.'
  }
  /* 🚨 A agenda é buscada à parte e NUNCA derruba a tela: é complemento. Se
     o Google estiver fora, ou a permissão não tiver sido concedida, a faixa
     some e conversas e canais continuam aparecendo. */
  try {
    agenda.value = await api.get('/api/agenda/hoje')
  } catch {
    agenda.value = null
  }
}

function hora(iso, diaInteiro) {
  if (!iso) return ''
  if (diaInteiro) return 'dia todo'
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

/* "agora" é o compromisso que já começou e ainda não acabou pela próxima
   hora -- é o que a pessoa precisa ver primeiro ao abrir o painel. */
function acontecendo(e) {
  if (e.dia_inteiro || !e.quando) return false
  const d = new Date(e.quando)
  return d <= new Date() && new Date() - d < 3600000
}

function quando(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  const min = Math.round((Date.now() - d) / 60000)
  if (min < 60) return `há ${min} min`
  if (min < 1440) return `há ${Math.round(min / 60)} h`
  return `há ${Math.round(min / 1440)} d`
}

/* Segundos viram "4 min" ou "1 h 12". Média em segundos crus obriga quem lê a
   dividir de cabeça, e ninguém divide -- só ignora o número. */
function duracao(segundos) {
  if (segundos === null || segundos === undefined) return '—'
  if (segundos < 60) return `${segundos}s`
  if (segundos < 3600) return `${Math.round(segundos / 60)} min`
  const h = Math.floor(segundos / 3600)
  const m = Math.round((segundos % 3600) / 60)
  return m ? `${h} h ${m}` : `${h} h`
}

/* 0 = domingo, igual ao `dia_semana` do banco. */
const DIAS = ['domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado']
const hojeEh = computed(() => DIAS[new Date().getDay()])

const config = computed(() => dados.value?.configuracao || null)
const desfecho = computed(() => dados.value?.desfecho || null)

onMounted(() => {
  carregar()
  // 60s: a tela fica aberta o dia inteiro e precisa parecer viva, mas não é
  // a caixa de entrada -- lá o intervalo é de 5s porque o dado é a conversa.
  relogio = setInterval(carregar, 60000)
})
onUnmounted(() => clearInterval(relogio))
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1 class="tela__titulo">{{ saudacao }}, {{ sessao.usuario?.nome || '' }}</h1>
        <p class="apagado pequeno">{{ agora }}</p>
      </div>
      <button class="botao botao--pequeno botao--fantasma" type="button" @click="carregar">
        <i class="bi bi-arrow-clockwise" aria-hidden="true"></i> Atualizar
      </button>
    </header>

    <!-- 🚨 SEM VÍNCULO DE ATENDIMENTO, A TELA PARA AQUI. A conta entra no
         painel, mas não tem linha em `atendente` com e-mail -- e sem isso
         tudo que a pessoa escrever é gravado com autor NULL: ela responde o
         cliente e a conversa não sabe dizer quem respondeu. Até 12/08 isso
         acontecia calado, e o histórico ficava anônimo sem ninguém notar. -->
    <div v-if="sessao.usuario && !sessao.usuario.vinculoAtendimento" class="vazio">
      <i class="bi bi-person-slash vazio__icone" aria-hidden="true"></i>
      <p class="vazio__titulo">Não possui vínculo de atendimento</p>
      <p>Procure o administrador do sistema.</p>
      <p class="apagado pequeno">
        Sua conta entra no painel, mas não está ligada a um atendente com
        e-mail — então nada do que você escrever teria autor registrado.
      </p>
    </div>

    <template v-else>
      <p v-if="erro" class="aviso aviso--erro">{{ erro }}</p>
      <p v-else-if="!dados" class="apagado">carregando…</p>

      <template v-else>
      <!-- ═══ FAIXA A — o meu dia ═══════════════════════════════════════ -->
      <h2 class="inicio__faixa">O seu dia</h2>
      <section class="inicio__atencao">
        <button
          v-for="item in dados.meu_dia"
          :key="item.chave"
          class="inicio__card"
          :class="{ 'inicio__card--quieto': !item.valor }"
          type="button"
          @click="router.push(item.rota)"
        >
          <strong class="inicio__numero">{{ item.valor }}</strong>
          <span class="inicio__rotulo">{{ item.rotulo }}</span>
        </button>

        <!-- ⚠️ CARTÃO DE DESFECHO, NÃO DE VOLUME. O número é atendimento
             CONCLUÍDO: o outro lado do que está aberto, e o que a régua
             desta tela passou a aceitar em 25/08. -->
        <div v-if="desfecho" class="inicio__card inicio__card--desfecho">
          <strong class="inicio__numero inicio__numero--ok">
            {{ desfecho.minhas[periodo] }}
          </strong>
          <span class="inicio__rotulo">atendimentos concluídos por você</span>
          <span class="inicio__nota apagado">
            equipe: {{ desfecho.equipe[periodo] }}
            <template v-if="desfecho.segundos_ate_resposta.minha !== null">
              · sua 1ª resposta em {{ duracao(desfecho.segundos_ate_resposta.minha) }}
            </template>
          </span>
          <div class="inicio__periodos">
            <button
              v-for="p in PERIODOS"
              :key="p.valor"
              class="botao botao--pequeno"
              :class="periodo === p.valor ? 'botao--primario' : 'botao--fantasma'"
              type="button"
              @click="trocarPeriodo(p.valor)"
            >
              {{ p.rotulo }}
            </button>
          </div>
          <!-- 🚨 As conversas fechadas ANTES da migração 029 não sabem quem
               as concluiu. Contar como de ninguém é a verdade; omitir a
               diferença faria a pessoa achar que o número dela está errado. -->
          <span v-if="desfecho.sem_autor_hoje" class="inicio__nota">
            {{ desfecho.sem_autor_hoje }} concluído(s) hoje sem autor registrado
          </span>
        </div>
      </section>

      <!-- ═══ FAIXA B — a operação ══════════════════════════════════════ -->
      <h2 class="inicio__faixa">A operação</h2>
      <section class="inicio__atencao">
        <button
          v-for="item in dados.atencao"
          :key="item.chave"
          class="inicio__card"
          :class="{ 'inicio__card--quieto': !item.valor }"
          type="button"
          @click="router.push(item.rota)"
        >
          <strong class="inicio__numero">{{ item.valor }}</strong>
          <span class="inicio__rotulo">{{ item.rotulo }}</span>
          <span v-if="item.nota" class="inicio__nota">{{ item.nota }}</span>
        </button>
      </section>

      <!-- ── a agenda de hoje ────────────────────────────────────────── -->
      <section v-if="agenda && agenda.eventos.length" class="cartao inicio__bloco">
        <h2 class="inicio__titulo">Hoje</h2>
        <ul class="inicio__agenda">
          <li v-for="(e, i) in agenda.eventos" :key="i" class="linha pequeno">
            <span class="inicio__hora" :class="{ 'inicio__hora--agora': acontecendo(e) }">
              {{ acontecendo(e) ? 'agora' : hora(e.quando, e.dia_inteiro) }}
            </span>
            <strong>{{ e.titulo }}</strong>
            <span v-if="e.local" class="apagado">· {{ e.local }}</span>
            <a v-if="e.link" :href="e.link" target="_blank" rel="noopener" class="apagado">
              <i class="bi bi-camera-video" aria-hidden="true"></i>
            </a>
          </li>
        </ul>
      </section>

      <!-- ═══ FAIXA C' — como VOCÊ está configurado (quem não é owner) ═══
           🚨 EXISTE PORQUE NÃO HAVIA ONDE DESCOBRIR ISSO. Quem não é owner
           não abre CAD_2.1 nem CAD_2.2: não tinha como saber em que times
           está, que filas enxerga, nem por que uma tela não aparece. A
           conclusão natural era "o painel está quebrado". -->
      <section v-if="config" class="cartao inicio__bloco inicio__config">
        <h2 class="inicio__titulo">
          Como você está configurado
          <span class="chip chip--pequeno">só leitura</span>
        </h2>
        <dl class="inicio__dados">
          <dt>Perfil</dt>
          <dd>{{ config.perfil }}</dd>

          <dt>Seu estado</dt>
          <dd>{{ config.estado }}</dd>

          <dt>Jornada de {{ hojeEh }}</dt>
          <dd>
            <template v-if="config.jornada_hoje.length">
              <span v-for="(f, i) in config.jornada_hoje" :key="i" class="chip">
                {{ f.inicio.slice(0, 5) }}–{{ f.fim.slice(0, 5) }}
              </span>
              <span v-if="!config.dentro_do_horario" class="chip chip--aviso">
                fora do horário agora
              </span>
            </template>
            <!-- ⚠️ Sem jornada, a fila conta a pessoa como fora do expediente
                 sempre. Isso precisa aparecer, não ficar como espaço em branco. -->
            <span v-else class="chip chip--aviso">
              sem jornada — a fila te conta como fora do expediente
            </span>
          </dd>

          <dt>Times</dt>
          <dd>
            <span v-for="t in config.times" :key="t" class="chip">{{ t }}</span>
            <span v-if="!config.times.length" class="apagado pequeno">
              você não está em nenhum time
            </span>
          </dd>

          <dt>Filas que você vê</dt>
          <!-- 🚨 LISTA VAZIA AQUI SIGNIFICA O CONTRÁRIO DO QUE PARECE: sem
               linha de permissão, a pessoa vê a fila INTEIRA. É o padrão
               permissivo da migração 001. -->
          <dd>
            <span v-if="config.ve_a_fila_inteira" class="chip chip--ok">
              a fila inteira
            </span>
            <span v-for="f in config.filas" v-else :key="f" class="chip">{{ f }}</span>
          </dd>

          <dt>Recebe transferência</dt>
          <dd>{{ config.transferivel ? 'sim' : 'não' }}</dd>
        </dl>
        <p class="apagado pequeno">
          
        </p>
      </section>

      <!-- ═══ FAIXA C — só owner ════════════════════════════════════════
           🚨 A TRAVA É NO SERVIDOR. `dados.canais` só existe no JSON quando
           quem pede é owner -- o `v-if` daqui é a segunda camada, não a
           primeira. Esconder só na tela deixaria a rota respondendo. -->
      <template v-if="dados.owner">
        <section v-if="dados.canais" class="cartao inicio__bloco">
          <h2 class="inicio__titulo">
            Canais
            <span class="chip chip--pequeno chip--acento">owner</span>
          </h2>
          <ul class="inicio__canais">
            <li v-for="c in dados.canais" :key="c.id" class="linha pequeno">
              <span
                class="inicio__ponto"
                :class="c.estado === 'conectado' ? 'inicio__ponto--ok' : 'inicio__ponto--erro'"
                aria-hidden="true"
              ></span>
              <strong>{{ c.nome }}</strong>
              <span class="apagado">{{ c.estado || 'sem registro' }}</span>
              <span class="apagado">· {{ quando(c.desde) }}</span>
              <span v-if="c.ia_ligada" class="chip chip--acento">IA ligada</span>
            </li>
          </ul>
        </section>

        <!-- ── nada travado ────────────────────────────────────────────── -->
        <section
          v-if="dados.saude"
          class="cartao inicio__bloco"
          :class="{ 'inicio__bloco--alerta': dados.saude.pendentes || dados.saude.com_erro }"
        >
          <h2 class="inicio__titulo">
            {{ dados.saude.pendentes || dados.saude.com_erro ? 'Precisa de atenção' : 'Nada travado' }}
          </h2>
          <p class="pequeno">
            {{ dados.saude.pendentes }} evento(s) pendente(s) ·
            {{ dados.saude.com_erro }} com erro
            <span v-if="dados.saude.sync" class="apagado">
              · sync {{ quando(dados.saude.sync.iniciado_em) }},
              {{ dados.saude.sync.lidos }} clientes
            </span>
          </p>
          <p v-if="dados.alcance" class="apagado pequeno">
            {{ dados.alcance.clientes }} clientes ativos ·
            {{ dados.alcance.com_whatsapp }} números com WhatsApp ·
            {{ dados.alcance.com_email }} com e-mail
            <span v-if="dados.alcance.nao_verificados">
              · {{ dados.alcance.nao_verificados }} sem verificar
            </span>
          </p>
        </section>
      </template>
      </template>
    </template>
  </div>
</template>

<style scoped>
/* Título de faixa: separa "o seu dia" de "a operação" sem virar mais um
   cartão. Sem ele os dois grupos de número viram uma parede só. */
.inicio__faixa {
  font-size: var(--txt-sm);
  font-weight: var(--peso-forte);
  text-transform: uppercase;
  letter-spacing: .06em;
  color: var(--texto-apagado);
  margin: var(--e-4) 0 var(--e-2);
}
.inicio__faixa:first-of-type { margin-top: 0; }

.inicio__atencao {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--e-3);
  margin-bottom: var(--e-4);
}

.inicio__card {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--e-4);
  text-align: left;
  background: var(--superficie);
  border: var(--borda-fina) solid var(--acento-borda);
  border-radius: var(--r-lg);
  box-shadow: var(--sombra-1);
  cursor: pointer;
  font-family: var(--fonte);
  transition: box-shadow .15s, border-color .15s;
}
.inicio__card:hover { box-shadow: var(--sombra-2); border-color: var(--acento); }
.inicio__card:focus-visible { outline: none; box-shadow: var(--foco); }

/* 🚨 Zero que é boa notícia ENCOLHE. Sem isto, três zeros ocupam o mesmo
   espaço visual que o número que está pedindo trabalho. */
.inicio__card--quieto {
  border-color: var(--borda);
  box-shadow: none;
  opacity: .6;
}
.inicio__card--quieto .inicio__numero { color: var(--texto-apagado); }

/* O cartão de desfecho não é um botão: ele tem botões DENTRO (os períodos).
   Por isso não tem cursor de clique nem hover de cartão clicável. */
.inicio__card--desfecho {
  cursor: default;
  border-color: var(--ok-borda);
  grid-column: span 2;
}
.inicio__card--desfecho:hover { border-color: var(--ok-borda); box-shadow: var(--sombra-1); }

.inicio__periodos { display: flex; gap: var(--e-1); margin-top: var(--e-2); }

.inicio__numero { font-size: var(--txt-2xl); line-height: 1.1; color: var(--acento); }
.inicio__numero--ok { color: var(--ok); }
.inicio__rotulo { font-size: var(--txt-md); color: var(--texto); }
.inicio__nota { font-size: var(--txt-sm); color: var(--aviso); }

.inicio__bloco { padding: var(--e-4); margin-bottom: var(--e-3); }
.inicio__bloco--alerta { border-color: var(--aviso-borda); background: var(--aviso-suave); }
.inicio__titulo { font-size: var(--txt-md); margin: 0 0 var(--e-2); }

.inicio__config { background: var(--superficie-2); }
.inicio__dados {
  display: grid;
  grid-template-columns: minmax(130px, auto) 1fr;
  gap: var(--e-1) var(--e-3);
  margin: 0 0 var(--e-2);
  font-size: var(--txt-sm);
}
.inicio__dados dt { color: var(--texto-fraco); }
.inicio__dados dd { margin: 0; display: flex; flex-wrap: wrap; gap: var(--e-1); align-items: center; }

.inicio__agenda { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--e-1); }
.inicio__hora {
  min-width: 54px; flex: none;
  font-variant-numeric: tabular-nums;
  color: var(--texto-fraco);
}
.inicio__hora--agora {
  color: var(--acento);
  font-weight: 700;
}

.inicio__canais { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--e-1); }
.inicio__ponto { width: 9px; height: 9px; border-radius: var(--r-full); flex: none; }
.inicio__ponto--ok { background: var(--ok); }
.inicio__ponto--erro { background: var(--erro); }
</style>
