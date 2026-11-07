<script setup>
/* ============================================================================
   CFG_15.1 — a permissão dos painéis, por pessoa e por aba.
   ----------------------------------------------------------------------------
   🔵 06/11, pedido dele: *"em configuração, crie uma aba de permissão para os
   paineis, ali vou definir quem pode ver o que e por aba tbm, como notará que o
   pós venda ja possui abas"*.

   🚨 A COLUNA É A TELA, e a tela é quem carrega permissão no MoviZap. A aba de
   dentro (`PNL_1.3`) é uma coluna própria, aninhada na principal — é o *"por
   aba tbm"*, e é por isso que a grade traz `aba_titulo`: no registro as duas
   colunas do Pós-venda se chamam "Pós-venda", e o nome que as distingue mora no
   banco (`painel_aba.titulo`).

   🚨 GRAVA POR LINHA, COM BOTÃO, e não no clique da caixa. Marcar é dar acesso
   a dado de cliente; salvar no clique transforma um toque errado em concessão
   silenciosa. A linha alterada mostra o botão e o que vai mudar.

   ⚠️ A TELA REDESENHA DO QUE O SERVIDOR DEVOLVEU, nunca do que ela mandou: a
   rota responde com a grade relida. Confiar no próprio palpite é como `M12`
   começa.

   ⚠️ SEM PARÁGRAFO DIDÁTICO (decisão dele, 30/10: *"atrapalha o
   profissionalismo"*). O que a tela escreve é ESTADO: quem é owner, quem
   concedeu cada marca e quando, e quais linhas estão pendentes de gravar.
   ============================================================================ */
import { computed, onMounted, ref } from 'vue'

import { api } from '../api/cliente.js'

const telas = ref([])
const pessoas = ref([])
const carregando = ref(true)
const erro = ref('')
const salvando = ref(0)

/* O rascunho por pessoa: `Set` de códigos. 🚨 Separado do que veio do
   servidor, para a linha saber dizer se está pendente -- e para "desfazer"
   ser só reler. */
const rascunho = ref(new Map())

function semearRascunho() {
  const m = new Map()
  for (const p of pessoas.value) m.set(p.atendente_id, new Set(p.concedidas))
  rascunho.value = m
}

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    const r = await api.get('/api/config/permissao-paineis')
    telas.value = r.telas || []
    pessoas.value = r.pessoas || []
    semearRascunho()
  } catch (e) {
    erro.value = e?.message || 'Não deu para ler a permissão dos painéis.'
  } finally {
    carregando.value = false
  }
}

function marcada(pessoa, codigo) {
  return rascunho.value.get(pessoa.atendente_id)?.has(codigo) || false
}

function alternar(pessoa, codigo) {
  if (!pessoa.editavel) return
  const atual = rascunho.value.get(pessoa.atendente_id)
  if (!atual) return
  if (atual.has(codigo)) atual.delete(codigo)
  else atual.add(codigo)
  // `Map` não é reativo por mutação de valor: troca a referência.
  rascunho.value = new Map(rascunho.value)
}

/* A linha está pendente? Compara CONJUNTOS, não a ordem. */
function pendente(pessoa) {
  if (!pessoa.editavel) return false
  const r = rascunho.value.get(pessoa.atendente_id) || new Set()
  const gravado = new Set(pessoa.concedidas)
  if (r.size !== gravado.size) return true
  for (const c of r) if (!gravado.has(c)) return true
  return false
}

const pendentes = computed(() => pessoas.value.filter((p) => pendente(p)).length)

async function gravar(pessoa) {
  const codigos = [...(rascunho.value.get(pessoa.atendente_id) || [])]
  salvando.value = pessoa.atendente_id
  erro.value = ''
  try {
    const r = await api.put('/api/config/permissao-paineis', {
      atendente_id: pessoa.atendente_id,
      codigos,
    })
    telas.value = r.telas || []
    pessoas.value = r.pessoas || []
    semearRascunho()
  } catch (e) {
    erro.value = e?.message || 'Não deu para gravar.'
  } finally {
    salvando.value = 0
  }
}

function desfazer(pessoa) {
  rascunho.value.set(pessoa.atendente_id, new Set(pessoa.concedidas))
  rascunho.value = new Map(rascunho.value)
}

/* O rótulo da coluna: o título da ABA quando existe, senão o do registro.
   🚨 Sem isto, duas colunas do Pós-venda ficariam com o mesmo nome. */
function rotulo(tela) {
  return tela.aba_titulo || tela.titulo
}

/* A marca de quem concedeu, como ESTADO e não como explicação. */
function origem(pessoa, codigo) {
  const d = pessoa.detalhe?.[codigo]
  if (!d) return ''
  const quando = d.concedida_em ? new Date(d.concedida_em) : null
  const data = quando
    ? `${String(quando.getDate()).padStart(2, '0')}/${String(quando.getMonth() + 1).padStart(2, '0')}`
    : ''
  return d.concedida_por_nome ? `${d.concedida_por_nome} · ${data}` : data
}

onMounted(carregar)
</script>

<template>
  <section class="perm">
    <h2 class="perm__titulo">Permissão dos painéis</h2>

    <p v-if="carregando" class="perm__nota">Lendo…</p>
    <p v-else-if="!telas.length" class="perm__nota">
      Nenhum painel no registro ainda.
    </p>

    <div v-else class="perm__rolo">
      <table class="perm__grade">
        <thead>
          <tr>
            <th class="perm__pessoa" scope="col">Pessoa</th>
            <th
              v-for="t in telas"
              :key="t.codigo"
              scope="col"
              class="perm__col"
              :class="{ 'perm__col--aba': t.aba_de }"
            >
              <span class="perm__col-nome">{{ rotulo(t) }}</span>
              <span class="perm__col-codigo">{{ t.codigo }}</span>
            </th>
            <th class="perm__acao" scope="col"><span class="perm__oculto">Gravar</span></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="p in pessoas"
            :key="p.atendente_id"
            :class="{ 'perm__linha--pendente': pendente(p) }"
          >
            <th class="perm__pessoa" scope="row">
              <span class="perm__nome">{{ p.nome }}</span>
              <span class="perm__perfil">{{ p.owner ? 'owner' : p.perfil }}</span>
            </th>
            <td v-for="t in telas" :key="t.codigo" class="perm__celula">
              <label class="perm__caixa">
                <input
                  type="checkbox"
                  :checked="marcada(p, t.codigo)"
                  :disabled="!p.editavel || salvando === p.atendente_id"
                  :aria-label="`${p.nome} — ${rotulo(t)}`"
                  @change="alternar(p, t.codigo)"
                />
                <span v-if="origem(p, t.codigo)" class="perm__origem">
                  {{ origem(p, t.codigo) }}
                </span>
              </label>
            </td>
            <td class="perm__acao">
              <template v-if="pendente(p)">
                <button
                  class="botao"
                  type="button"
                  :disabled="salvando === p.atendente_id"
                  @click="gravar(p)"
                >
                  {{ salvando === p.atendente_id ? 'Gravando…' : 'Gravar' }}
                </button>
                <button class="perm__desfazer" type="button" @click="desfazer(p)">
                  desfazer
                </button>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-if="erro" class="aviso aviso--erro">{{ erro }}</p>
    <p v-else-if="pendentes" class="aviso aviso--atencao">
      {{ pendentes === 1 ? '1 linha alterada e não gravada' : `${pendentes} linhas alteradas e não gravadas` }}.
    </p>
  </section>
</template>

<style scoped>
.perm { display: flex; flex-direction: column; gap: var(--e-3); }
.perm__titulo { margin: 0; font-size: var(--txt-lg); }
.perm__nota { margin: 0; color: var(--texto-fraco); font-size: var(--txt-sm); }
/* A grade cresce com os painéis: rola na horizontal em vez de encolher a
   coluna da pessoa, que é a que dá sentido à linha. */
.perm__rolo { overflow-x: auto; }
.perm__grade { border-collapse: collapse; font-size: var(--txt-sm); }
.perm__grade th,
.perm__grade td {
  border-bottom: 1px solid var(--borda);
  padding: var(--e-2);
  text-align: left;
  vertical-align: top;
}
.perm__pessoa { position: sticky; left: 0; background: var(--fundo); min-width: 180px; }
.perm__nome { display: block; font-weight: var(--peso-forte); }
.perm__perfil { display: block; color: var(--texto-fraco); font-size: var(--txt-xs); }
.perm__col { min-width: 132px; }
/* A aba de dentro entra recuada: a hierarquia é dado (`aba_de`), e aqui ela
   vira forma. */
.perm__col--aba { padding-left: var(--e-4); }
.perm__col-nome { display: block; }
.perm__col-codigo { display: block; color: var(--texto-fraco); font-size: var(--txt-xs); }
/* 44px de toque, padrão dos quatro painéis. */
.perm__caixa {
  display: flex;
  flex-direction: column;
  gap: var(--e-1);
  min-height: 44px;
  cursor: pointer;
}
.perm__caixa input { width: 20px; height: 20px; }
.perm__origem { color: var(--texto-fraco); font-size: var(--txt-xs); }
/* `--aviso-suave` é o token que existe (conferido no `tokens.css`): inventar
   nome de token é o defeito que a 5ª conferência do CSS publicado caça. */
.perm__linha--pendente { background: var(--aviso-suave); }
.perm__linha--pendente .perm__pessoa { background: var(--aviso-suave); }
.perm__acao { white-space: nowrap; }
.perm__desfazer {
  background: none;
  border: 0;
  padding: var(--e-1);
  color: var(--texto-fraco);
  font-size: var(--txt-xs);
  cursor: pointer;
  text-decoration: underline;
}
.perm__oculto {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}
</style>
