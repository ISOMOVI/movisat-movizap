<script setup>
/* ============================================================================
   CFG_9.1 — Registro de telas.
   ----------------------------------------------------------------------------
   Única tela do esqueleto que já tem backend pronto (/api/telas/registro), e
   por isso a única implementada de verdade. É também a tela que prova o
   contrato: o que está aqui é o mesmo `telas.py` que decide navegação,
   permissão e auditoria — não uma cópia mantida à mão no frontend.

   Só o owner enxerga.
   ============================================================================ */
import { ref, computed, onMounted } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'
import { codigosPermitidos } from '../estado/sessao.js'

const registro = ref(null)
const erro = ref('')
const carregando = ref(true)

const NOME_DO_MODULO = {
  ATD: 'Atendimento',
  CAD: 'Cadastro',
  CFG: 'Configuração',
  REL: 'Relatórios',
}

onMounted(async () => {
  try {
    registro.value = await api.get('/api/telas/registro')
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao ler o registro.'
  } finally {
    carregando.value = false
  }
})

const telas = computed(() => registro.value?.telas || [])
const faseAtual = computed(() => registro.value?.fase_atual ?? null)

const grupos = computed(() => {
  const porModulo = new Map()
  for (const tela of telas.value) {
    const modulo = tela.codigo.split('_')[0]
    if (!porModulo.has(modulo)) porModulo.set(modulo, [])
    porModulo.get(modulo).push(tela)
  }
  return [...porModulo].map(([modulo, lista]) => ({
    modulo,
    nome: NOME_DO_MODULO[modulo] || modulo,
    telas: lista,
  }))
})

const ativas = computed(() =>
  telas.value.filter((t) => faseAtual.value !== null && t.fase <= faseAtual.value).length,
)
const reservadas = computed(() => telas.value.length - ativas.value)

function estaAtiva(tela) {
  return faseAtual.value !== null && tela.fase <= faseAtual.value
}
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Registro de telas</h1>
        <p class="fraco pequeno">
          Fonte única de navegação, permissão e auditoria. O código é imutável e
          nunca é reaproveitado — reusar faria log antigo mentir.
        </p>
      </div>
      <div v-if="registro" class="linha">
        <span class="chip chip--ok">{{ ativas }} ativas</span>
        <span class="chip">{{ reservadas }} reservadas</span>
        <span class="chip chip--acento">fase {{ faseAtual }}</span>
      </div>
    </header>

    <p v-if="carregando" class="linha fraco">
      <span class="girando"></span> Lendo o registro…
    </p>

    <p v-else-if="erro" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>{{ erro }}</span>
    </p>

    <template v-else>
      <section v-for="grupo in grupos" :key="grupo.modulo" class="cartao tela__bloco">
        <header class="cartao__cabecalho">
          <span>{{ grupo.nome }}</span>
          <span class="apagado mono">{{ grupo.modulo }}_</span>
        </header>
        <div class="tabela--rolavel">
          <table class="tabela">
            <thead>
              <tr>
                <th>Código</th>
                <th>Título</th>
                <th>Rota</th>
                <th>Permissão</th>
                <th>Situação</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="tela in grupo.telas" :key="tela.codigo" :class="{ 'linha--futura': !estaAtiva(tela) }">
                <td>
                  <span class="chip chip--codigo" :class="{ 'chip--acento': codigosPermitidos.has(tela.codigo) }">
                    {{ tela.codigo }}
                  </span>
                </td>
                <td>
                  <div class="linha">
                    <i class="bi" :class="tela.icone" aria-hidden="true"></i>
                    <span>{{ tela.titulo }}</span>
                  </div>
                  <p class="apagado pequeno">{{ tela.descricao }}</p>
                </td>
                <td class="mono pequeno fraco">{{ tela.rota }}</td>
                <td><span class="chip">{{ tela.permissao }}</span></td>
                <td>
                  <span v-if="estaAtiva(tela)" class="chip chip--ok">no ar</span>
                  <span v-else class="chip chip--aviso">reservada · fase {{ tela.fase }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="cartao tela__bloco">
        <header class="cartao__cabecalho"><span>Perfis e permissões</span></header>
        <div class="cartao__corpo pilha">
          <div v-for="(permissoes, perfil) in registro.perfis" :key="perfil" class="perfil">
            <span class="chip chip--acento perfil__nome">{{ perfil }}</span>
            <div class="linha perfil__lista">
              <span v-for="p in permissoes" :key="p" class="chip">{{ p }}</span>
            </div>
          </div>
          <p class="apagado pequeno">
            Conta nova nasce sem nenhuma permissão: falha fechado. O owner enxerga
            tudo independentemente do que estiver gravado.
          </p>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.tela { max-width: 1100px; }

.tela__cabecalho {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--e-4);
  flex-wrap: wrap;
  margin-bottom: var(--e-5);
}
.tela__cabecalho p { max-width: var(--largura-texto); margin-top: var(--e-1); }

.tela__bloco { margin-bottom: var(--e-5); overflow: hidden; }
.tela__bloco .tabela td:first-child { white-space: nowrap; }

.linha--futura td { opacity: .62; }

.perfil { display: flex; align-items: baseline; gap: var(--e-3); flex-wrap: wrap; }
.perfil__nome { min-width: 92px; justify-content: center; }
.perfil__lista { flex-wrap: wrap; }
</style>
