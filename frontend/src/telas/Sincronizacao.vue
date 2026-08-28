<script setup>
/* ============================================================================
   CFG_3.1 — Sincronização do Harmonit
   ----------------------------------------------------------------------------
   Três perguntas diferentes, e a tela não pode misturá-las:

     o que eu TENHO      quantos clientes, contatos e telefones estão no banco
     quando foi a última leitura, o que ela mudou
     o Harmonit está DE PÉ   o disjuntor, que é outra coisa

   🚨 "1.050 clientes" não diz nada sobre o Harmonit estar respondendo. É
   assim que se descobre tarde demais que a base parou de atualizar há uma
   semana -- o número na tela continua bonito enquanto a fonte está morta.

   ⚠️ O sync completo leva ~5 s e a requisição fica esperando. É deliberado:
   devolver "iniciei" e obrigar a pessoa a ficar recarregando para saber se
   deu certo é pior que esperar cinco segundos olhando um botão girando.
   ============================================================================ */
import { ref, computed, onMounted } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'

const dados = ref(null)
const carregando = ref(true)
const erro = ref('')
const sincronizando = ref(false)
const resultado = ref(null)
const aviso = ref('')

const totais = computed(() => dados.value?.totais || {})
const harmonit = computed(() => dados.value?.harmonit || {})
const ultima = computed(() => dados.value?.ultima || null)
const historico = computed(() => dados.value?.historico || [])

/** A base cadastral só é confiável se alguém leu recentemente. */
const idadeDaBase = computed(() => {
  const quando = ultima.value?.terminado_em || ultima.value?.iniciado_em
  if (!quando) return null
  return Math.floor((Date.now() - new Date(quando)) / 3600000)
})

/** O cron roda a cada 12 h. Passou de 24 h, alguma coisa está errada. */
const baseVelha = computed(() => idadeDaBase.value !== null && idadeDaBase.value >= 24)

async function carregar(silencioso = false) {
  if (!silencioso) carregando.value = true
  try {
    dados.value = await api.get('/api/sync')
    erro.value = ''
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao ler o estado da sincronização.'
  } finally {
    carregando.value = false
  }
}

async function sincronizarAgora() {
  sincronizando.value = true
  aviso.value = ''
  resultado.value = null
  try {
    resultado.value = await api.post('/api/sync/agora')
    await carregar(true)
  } catch (e) {
    if (e instanceof ErroDeApi && e.status === 409) {
      aviso.value = 'Já existe uma sincronização em andamento. Espere ela terminar.'
    } else {
      aviso.value = e instanceof ErroDeApi ? e.message : 'A sincronização falhou.'
    }
  } finally {
    sincronizando.value = false
  }
}

function quando(iso) {
  return iso ? new Date(iso).toLocaleString('pt-BR') : '—'
}

function duracao(execucao) {
  if (!execucao?.terminado_em) return '—'
  const seg = (new Date(execucao.terminado_em) - new Date(execucao.iniciado_em)) / 1000
  return `${seg.toFixed(1)} s`
}

function numero(n) {
  return (n ?? 0).toLocaleString('pt-BR')
}

onMounted(carregar)
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Sincronização</h1>
        <AjudaDaTela>Leitura do Harmonit a cada 12 h (05:45 e 17:45) e sob demanda. O MoviZap só lê — cadastro criado aqui nunca sobe para lá.</AjudaDaTela>
      </div>
      <span class="chip chip--codigo chip--acento">CFG_3.1</span>
    </header>

    <p v-if="aviso" class="aviso aviso--atencao tela__aviso" role="status">
      <i class="bi bi-exclamation-triangle aviso__icone" aria-hidden="true"></i>
      <span>{{ aviso }}</span>
    </p>

    <p v-if="carregando" class="linha fraco">
      <span class="girando"></span> Consultando…
    </p>

    <p v-else-if="erro" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>{{ erro }}</span>
    </p>

    <template v-else>
      <!-- ---------------------------------------------------- o que eu tenho -->
      <section class="cartao">
        <header class="cartao__cabecalho">
          <span class="linha">
            <i class="bi bi-people" aria-hidden="true"></i>
            O que está no banco
          </span>
          <span class="chip" :class="baseVelha ? 'chip--aviso' : 'chip--ok'">
            {{ idadeDaBase === null ? 'nunca sincronizado'
               : idadeDaBase < 1 ? 'lido há menos de 1 h'
               : `lido há ${idadeDaBase} h` }}
          </span>
        </header>

        <div class="cartao__corpo">
          <p v-if="baseVelha" class="aviso aviso--atencao">
            <i class="bi bi-clock-history aviso__icone" aria-hidden="true"></i>
            <span>
              A última leitura passou de 24 h. Os números abaixo descrevem o
              Harmonit de ontem.
            </span>
          </p>

          <dl class="sync__numeros">
            <div>
              <dt>Clientes</dt>
              <dd class="sync__grande">{{ numero(totais.clientes) }}</dd>
              <dd class="pequeno fraco">{{ numero(totais.clientes_ativos) }} ativos</dd>
            </div>
            <div>
              <dt>Contatos</dt>
              <dd class="sync__grande">{{ numero(totais.contatos) }}</dd>
              <dd class="pequeno fraco">um por cliente</dd>
            </div>
            <div>
              <dt>Telefones</dt>
              <dd class="sync__grande">{{ numero(totais.telefones) }}</dd>
              <dd class="pequeno fraco">em E.164, com o bruto guardado</dd>
            </div>
            <div>
              <dt>Cadastro nosso</dt>
              <dd class="sync__grande">{{ numero(totais.clientes_nossos) }}</dd>
              <dd class="pequeno fraco">o sync nunca encosta</dd>
            </div>
          </dl>

          <p class="aviso aviso--info">
            <i class="bi bi-whatsapp aviso__icone" aria-hidden="true"></i>
            <span>
              <strong>{{ numero(totais.nao_verificados) }}</strong> telefones
              ainda não foram verificados no WhatsApp, e
              <strong>{{ numero(totais.com_whatsapp) }}</strong> foram.
              <br /><span class="pequeno">
                Quem verifica é o Evolution, e ele precisa de um canal
                conectado.
              </span>
            </span>
          </p>
        </div>
      </section>

      <!-- ----------------------------------------------------- a fonte -->
      <section class="cartao">
        <header class="cartao__cabecalho">
          <span class="linha">
            <i class="bi bi-hdd-network" aria-hidden="true"></i>
            A API do Harmonit
          </span>
          <span class="chip" :class="harmonit.aberto ? 'chip--erro' : 'chip--ok'">
            {{ harmonit.aberto ? 'fora do ar' : 'respondendo' }}
          </span>
        </header>

        <div class="cartao__corpo">
          <p v-if="harmonit.aberto" class="aviso aviso--erro">
            <i class="bi bi-plug aviso__icone" aria-hidden="true"></i>
            <span>
              O disjuntor está aberto por mais
              {{ harmonit.segundos_restantes }} s, depois de
              {{ harmonit.falhas_seguidas }} falhas seguidas de autenticação.
              <br /><span class="pequeno">
                Último erro: {{ harmonit.ultimo_erro || '—' }}. 
              </span>
            </span>
          </p>
          <p v-else class="fraco pequeno">
            Nenhuma falha de autenticação acumulada.
          </p>

          <button
            class="botao botao--primario"
            :disabled="sincronizando || harmonit.aberto"
            @click="sincronizarAgora"
          >
            <span v-if="sincronizando" class="girando" aria-hidden="true"></span>
            <i v-else class="bi bi-arrow-repeat" aria-hidden="true"></i>
            {{ sincronizando ? 'Sincronizando… (leva ~5 s)' : 'Sincronizar agora' }}
          </button>
        </div>
      </section>

      <!-- ------------------------------------------- resultado da última ação -->
      <section v-if="resultado" class="cartao">
        <header class="cartao__cabecalho">
          <span class="linha">
            <i class="bi bi-check2-circle" aria-hidden="true"></i>
            Terminou em {{ resultado.duracao_seg }} s
          </span>
        </header>
        <div class="cartao__corpo">
          <p v-if="resultado.erro" class="aviso aviso--erro">
            <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
            <span>{{ resultado.erro }}</span>
          </p>
          <p class="linha sync__resumo">
            <span class="chip">{{ numero(resultado.lidos) }} lidos</span>
            <span class="chip chip--ok">{{ numero(resultado.criados) }} criados</span>
            <span class="chip">{{ numero(resultado.atualizados) }} atualizados</span>
            <span class="chip chip--aviso">{{ numero(resultado.inativados) }} inativados</span>
          </p>
        </div>
      </section>

      <!-- ------------------------------------------------------- histórico -->
      <section class="cartao">
        <header class="cartao__cabecalho">
          <span class="linha">
            <i class="bi bi-clock-history" aria-hidden="true"></i>
            Execuções
          </span>
        </header>

        <div class="cartao__corpo">
          <div v-if="!historico.length" class="vazio">
            <i class="bi bi-inbox vazio__icone" aria-hidden="true"></i>
            <p class="vazio__titulo">Nenhuma execução ainda</p>
          </div>

          <div v-else class="tabela--rolavel">
            <table class="tabela">
              <thead>
                <tr>
                  <th>Quando</th>
                  <th>Origem</th>
                  <th class="sync__num">Lidos</th>
                  <th class="sync__num">Criados</th>
                  <th class="sync__num">Atualiz.</th>
                  <th class="sync__num" title="Quantos PASSARAM a inativo nesta execução, não quantos estão inativos">
                    Inativados
                  </th>
                  <th class="sync__num" title="Campos de telefone em branco na origem. Não é erro — é o normal da base">
                    Vazios
                  </th>
                  <th class="sync__num" title="Telefone preenchido que a normalização recusou, como DDD 00">
                    Erros
                  </th>
                  <th class="sync__num">Duração</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="e in historico" :key="e.id">
                  <td class="mono pequeno">{{ quando(e.iniciado_em) }}</td>
                  <td>
                    <span class="chip" :class="e.origem === 'cron' ? '' : 'chip--acento'">
                      {{ e.origem }}
                    </span>
                  </td>
                  <td class="sync__num mono">{{ numero(e.lidos) }}</td>
                  <td class="sync__num mono">{{ numero(e.criados) }}</td>
                  <td class="sync__num mono">{{ numero(e.atualizados) }}</td>
                  <td class="sync__num mono">{{ numero(e.inativados) }}</td>
                  <td class="sync__num mono fraco">{{ numero(e.vazios) }}</td>
                  <td class="sync__num mono" :class="{ 'sync__erro': e.erros }">
                    {{ numero(e.erros) }}
                  </td>
                  <td class="sync__num mono pequeno">{{ duracao(e) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p class="fraco pequeno sync__legenda">
            <strong>Vazios</strong> são campos de telefone em branco no
            Harmonit — 1.857 dos 3.150 numa base saudável. <strong>Erros</strong> são telefones que não deu para normalizar. <strong>Inativados</strong> conta quem passou a inativo nesta execução.
          </p>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.sync__numeros {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
  gap: var(--e-4);
  margin: 0 0 var(--e-4);
}

.sync__numeros dt {
  font-size: var(--txt-xs);
  color: var(--texto-fraco);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.sync__numeros dd {
  margin: 0;
}

.sync__grande {
  font-size: var(--txt-2xl);
  font-weight: var(--peso-forte);
  line-height: var(--entrelinha-apertada);
  font-variant-numeric: tabular-nums;
}

.sync__num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.sync__erro {
  color: var(--erro);
  font-weight: var(--peso-medio);
}

.sync__resumo {
  flex-wrap: wrap;
  gap: var(--e-2);
}

.sync__legenda {
  margin-top: var(--e-4);
  max-width: var(--largura-texto);
}
</style>
