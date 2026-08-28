<script setup>
/* ============================================================================
   ATD_1.3 — Fila.
   ----------------------------------------------------------------------------
   Não é a caixa de entrada filtrada: a caixa mostra o que é SEU, a fila mostra
   o que não é de NINGUÉM — responsabilidade coletiva.

   🚨 O BALDE "SEM TRIAGEM" VEM PRIMEIRO. Quem atribui time é a triagem, e a
   triagem é a IA, que está desligada. Se esta tela só agrupasse por time, ela
   apareceria vazia enquanto gente real espera. Enquanto a IA não existe, a
   triagem é manual: abrir, ler e transferir para o time certo.

   ⚠️ Ordenado por ESPERA, não por chegada — quem esperou mais aparece antes.
   ============================================================================ */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

import { api, ErroDeApi } from '../api/cliente.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'

const router = useRouter()
const grupos = ref([])
const carregando = ref(true)
const erro = ref('')
const recado = ref('')
let timer = null

async function carregar({ silencioso = false } = {}) {
  if (!silencioso) carregando.value = true
  try {
    grupos.value = await api.get('/api/fila')
    erro.value = ''
  } catch (e) {
    if (!silencioso) erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao ler a fila.'
  } finally {
    carregando.value = false
  }
}

onMounted(async () => {
  await carregar()
  timer = setInterval(() => carregar({ silencioso: true }), 10000)
})
onUnmounted(() => clearInterval(timer))

async function assumir(id) {
  try {
    await api.post(`/api/conversas/${id}/assumir`)
    recado.value = 'Conversa assumida — ela saiu da fila e está na sua caixa.'
    await carregar({ silencioso: true })
  } catch (e) {
    // 🚨 409 é o caso projetado: outra pessoa clicou primeiro.
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui assumir.'
    await carregar({ silencioso: true })
  }
}

function abrir(id) {
  router.push({ path: `/atendimento/${id}` })
}

const totalEsperando = computed(
  () => grupos.value.reduce((soma, g) => soma + g.esperando, 0),
)

const semTriagem = computed(() => grupos.value.find((g) => g.sem_triagem))

function espera(seg) {
  if (!seg) return '—'
  const min = Math.round(seg / 60)
  if (min < 60) return `${min} min`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h} h ${min % 60} min`
  return `${Math.floor(h / 24)} d`
}

function quem(c) {
  return c.contato_nome || c.telefone_e164
}
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Fila</h1>
        <AjudaDaTela>Conversas sem dono. A caixa de entrada mostra o que é seu; aqui é o que não é de ninguém.</AjudaDaTela>
      </div>
      <span class="chip" :class="totalEsperando ? 'chip--aviso' : 'chip--ok'">
        {{ totalEsperando }} esperando
      </span>
    </header>

    <p v-if="semTriagem && semTriagem.esperando" class="aviso aviso--atencao" role="status">
      <i class="bi bi-signpost-split aviso__icone" aria-hidden="true"></i>
      <!-- 🚨 CORTADO NO FATO (28/08). O número é estado e fica; o resto —
           quem atribui o time, que a IA está desligada, o que muda quando ela
           entrar — era aula sobre o desenho. Foi o exemplo com que ele
           nomeou o padrão: *"elas ajudaram nas etapas de lógica, mas agora em
           teste sujam a tela"*. -->
      <span>
        <strong>{{ semTriagem.esperando }} conversa(s) sem triagem.</strong>
      </span>
    </p>

    <p v-if="erro" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>{{ erro }}</span>
    </p>
    <p v-if="recado" class="aviso aviso--ok" role="status">
      <i class="bi bi-check-circle aviso__icone" aria-hidden="true"></i>
      <span>{{ recado }}</span>
    </p>

    <p v-if="carregando" class="linha fraco">
      <span class="girando"></span> Lendo a fila…
    </p>

    <template v-else>
      <section
        v-for="g in grupos"
        :key="g.time_id ?? 'sem-triagem'"
        class="cartao tela__bloco"
        :class="{ 'cartao--destaque': g.sem_triagem && g.esperando }"
      >
        <header class="cartao__cabecalho">
          <span>
            <i v-if="g.sem_triagem" class="bi bi-signpost-split" aria-hidden="true"></i>
            {{ g.sem_triagem ? 'Sem triagem' : g.time_nome }}
          </span>
          <div class="linha">
            <span class="chip" :class="g.esperando ? 'chip--aviso' : ''">
              {{ g.esperando }} esperando
            </span>
            <span v-if="g.esperando" class="apagado pequeno">
              mais antiga: {{ espera(g.espera_maior_seg) }}
            </span>
          </div>
        </header>

        <div v-if="!g.esperando" class="cartao__corpo">
          <p class="fraco pequeno">Ninguém esperando.</p>
        </div>

        <div v-else class="tabela--rolavel">
          <table class="tabela">
            <thead>
              <tr>
                <th>Quem</th>
                <th>Esperando</th>
                <th>Estado</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in g.conversas" :key="c.id">
                <td>
                  <strong>{{ quem(c) }}</strong>
                  <p v-if="!c.contato_nome" class="pequeno">
                    <span class="chip chip--aviso">não identificado</span>
                  </p>
                </td>
                <td class="mono">{{ espera(c.espera_seg) }}</td>
                <td><span class="chip">{{ c.estado }}</span></td>
                <td>
                  <div class="linha">
                    <button class="botao botao--pequeno botao--contorno" type="button" @click="abrir(c.id)">
                      Abrir
                    </button>
                    <button class="botao botao--pequeno botao--primario" type="button" @click="assumir(c.id)">
                      Assumir
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <!-- ⚠️ O rodapé explicava a garantia de concorrência do "Assumir". É
         verdade, é importante, e não é da tela: quem assume não decide nada
         com essa informação. Vive no `docs/06`, ATD_1.3. -->
  </div>
</template>

<style scoped>
.tela { max-width: 1000px; }

.tela__cabecalho {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--e-4);
  flex-wrap: wrap;
  margin-bottom: var(--e-5);
}
.tela__cabecalho p { max-width: var(--largura-texto); margin-top: var(--e-1); }

.tela__bloco { margin-bottom: var(--e-4); overflow: hidden; }

.cartao--destaque { outline: 2px solid rgba(255, 193, 7, .55); }
</style>
