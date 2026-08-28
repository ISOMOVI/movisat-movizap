<script setup>
/* ============================================================================
   ATD_5.1 — Histórico.
   ----------------------------------------------------------------------------
   As conversas encerradas, pesquisáveis. É o que responde "o que já falamos
   com esse cliente antes?" — pergunta que sem isto só se responde pedindo
   para a pessoa repetir tudo.

   ⚠️ A busca por telefone passa pelo normalizador: `18 99811-6168`,
   `(18) 9811-6168` e `5518998116168` acham a mesma conversa.

   🚨 O código é ATD_5.1, não ATD_2.x: 2 é a ficha do contato e 3/4 estão
   reservados (Informativos e E-mail). Código não se reaproveita — reusar
   faria log antigo mentir.
   ============================================================================ */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { api, ErroDeApi } from '../api/cliente.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'

const router = useRouter()
const itens = ref([])
const classificacoes = ref([])
const busca = ref('')
const classificacaoId = ref('')
const carregando = ref(true)
const erro = ref('')

async function carregar() {
  carregando.value = true
  try {
    const p = new URLSearchParams()
    if (busca.value.trim()) p.set('busca', busca.value.trim())
    if (classificacaoId.value) p.set('classificacao_id', classificacaoId.value)
    itens.value = await api.get(`/api/historico?${p.toString()}`)
    erro.value = ''
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao ler o histórico.'
  } finally {
    carregando.value = false
  }
}

onMounted(async () => {
  try {
    classificacoes.value = await api.get('/api/classificacoes')
  } catch {
    // filtro é conveniência: sem ele a tela ainda funciona
    classificacoes.value = []
  }
  await carregar()
})

function abrir(id) {
  router.push({ path: `/atendimento/${id}` })
}

function duracao(seg) {
  if (!seg) return '—'
  const min = Math.round(seg / 60)
  if (min < 60) return `${min} min`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h} h ${min % 60} min`
  return `${Math.floor(h / 24)} d`
}

function data(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

const totalMensagens = computed(
  () => itens.value.reduce((s, i) => s + Number(i.qtd_mensagens || 0), 0),
)
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Histórico</h1>
        <AjudaDaTela>
          Conversas encerradas. É o que responde "o que já falamos com essa
          pessoa antes?". A busca acha o telefone em qualquer grafia.
        </AjudaDaTela>
      </div>
      <div class="linha">
        <span class="chip">{{ itens.length }} conversas</span>
        <span class="chip">{{ totalMensagens }} mensagens</span>
      </div>
    </header>

    <section class="cartao tela__bloco">
      <div class="cartao__corpo linha linha--quebra">
        <label class="campo campo--busca">
          <span class="campo__rotulo">Buscar</span>
          <input
            v-model="busca"
            class="campo__entrada"
            type="search"
            placeholder="nome, cliente ou telefone"
            @keyup.enter="carregar"
          />
          <!-- 🚨 A FAIXA SAIU DAQUI EM 28/08, NA AUDITORIA. Ele disse que os
               textos fixos estavam *"pelo sistema todo"* e citou dois
               exemplos com "etc"; eu entreguei os dois exemplos e deixei
               ESTE -- mesma construção (`campo__ajuda` sob um campo de
               busca), mesmo lugar, outra tela. É o M11 furado uma rodada
               depois de eu escrevê-lo: exemplo não é escopo. -->
        </label>

        <label class="campo">
          <span class="campo__rotulo">Classificação</span>
          <select v-model="classificacaoId" class="campo__entrada" @change="carregar">
            <option value="">todas</option>
            <option v-for="c in classificacoes" :key="c.id" :value="c.id">{{ c.nome }}</option>
          </select>
        </label>

        <button class="botao botao--primario" type="button" @click="carregar">
          <i class="bi bi-search" aria-hidden="true"></i> Buscar
        </button>
      </div>
    </section>

    <p v-if="erro" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>{{ erro }}</span>
    </p>

    <p v-if="carregando" class="linha fraco">
      <span class="girando"></span> Lendo…
    </p>

    <div v-else-if="!itens.length" class="vazio">
      <i class="bi bi-clock-history vazio__icone" aria-hidden="true"></i>
      <p class="vazio__titulo">Nenhuma conversa encerrada</p>
      <p>Conversa entra aqui quando o atendimento é concluído.</p>
    </div>

    <section v-else class="cartao tela__bloco">
      <div class="tabela--rolavel">
        <table class="tabela">
          <thead>
            <tr>
              <th>Quem</th>
              <th>Classificação</th>
              <th>Encerrada</th>
              <th>Duração</th>
              <th>Msgs</th>
              <th>Quem atendeu</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in itens" :key="c.id">
              <td>
                <strong>{{ c.contato_nome || c.telefone_e164 }}</strong>
                <p v-if="c.cliente_nome" class="apagado pequeno">{{ c.cliente_nome }}</p>
              </td>
              <td>
                <span class="chip">{{ c.classificacao_nome || 'sem classificação' }}</span>
                <p v-if="c.classificacao_texto" class="apagado pequeno">
                  {{ c.classificacao_texto }}
                </p>
              </td>
              <td class="pequeno fraco">{{ data(c.resolvida_em) }}</td>
              <td class="mono pequeno">{{ duracao(c.segundos_total) }}</td>
              <td class="mono pequeno">{{ c.qtd_mensagens }}</td>
              <td class="pequeno fraco">
                <span v-if="c.resolvida_pela_ia" class="chip chip--acento">IA</span>
                <span v-else>{{ c.atendente_nome || '—' }}</span>
                <span v-if="c.qtd_transferencias" class="apagado">
                  · {{ c.qtd_transferencias }} transf.
                </span>
              </td>
              <td>
                <button class="botao botao--pequeno botao--contorno" type="button" @click="abrir(c.id)">
                  Ver
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.tela { max-width: 1150px; }

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

.linha--quebra { flex-wrap: wrap; gap: var(--e-3); align-items: flex-end; }
.campo--busca { min-width: 260px; flex: 1; }
</style>
