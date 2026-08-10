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

.inicio__canais { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--e-1); }
.inicio__ponto { width: 9px; height: 9px; border-radius: var(--r-full); flex: none; }
.inicio__ponto--ok { background: var(--ok); }
.inicio__ponto--erro { background: var(--erro); }
</style>
