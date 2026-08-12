<script setup>
/* ============================================================================
   INI_1.1 — Tela inicial
   ----------------------------------------------------------------------------
   É a primeira tela do registro, e por isso o destino de TODO login: a rota
   `/` manda para `sessao.telas[0].rota`. Vale igual para a entrada por senha
   e pela do Google.

   🚨 A RÉGUA DESTA TELA: se o número está em zero e isso é bom, ele encolhe.
   O que cresce é o que espera alguém. Não há gráfico nem total de mensagens
   -- isso é relatório, e relatório tem código próprio (REL_1.1).

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
         acontecia calado, e o histórico ficava anônimo sem ninguém notar.
         Deixar trabalhar e explicar depois é pior do que barrar agora. -->
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
      <!-- ── o que espera alguém ─────────────────────────────────────── -->
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

      <!-- ── os canais estão de pé? ──────────────────────────────────── -->
      <section class="cartao inicio__bloco">
        <h2 class="inicio__titulo">Canais</h2>
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
        <p class="apagado pequeno">
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
  </div>
</template>

<style scoped>
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

.inicio__numero { font-size: var(--txt-2xl); line-height: 1.1; color: var(--acento); }
.inicio__rotulo { font-size: var(--txt-md); color: var(--texto); }
.inicio__nota { font-size: var(--txt-sm); color: var(--aviso); }

.inicio__bloco { padding: var(--e-4); margin-bottom: var(--e-3); }
.inicio__bloco--alerta { border-color: var(--aviso-borda); background: var(--aviso-suave); }
.inicio__titulo { font-size: var(--txt-md); margin: 0 0 var(--e-2); }

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
