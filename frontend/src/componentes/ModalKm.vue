<script setup>
/* ============================================================================
   A calculadora de KM do técnico.
   ----------------------------------------------------------------------------
   🔵 Pedido dele (26/10): *"na parte de agendamento do tecnico: proponha no
   deslocamento uma calculadora km técnico que pode abrir outro modal para
   calcular, dai o endereço do tecnico sempre fica preenchido conforme o
   ultimo (...) E dali coloca os dados de endereço do cliente puxando do CEP,
   etc para o orlamento"*. E, sobre a distância: *"o km é o calculo a ser
   feito, é a informação a ser encontrada. Hoje é feita na mão via 'rotas' do
   google e dai esse KM é inserido manualmente"*.

   🚨 ELE FUNCIONA SEM O CÁLCULO, e isso é a parte que importa hoje. Enquanto
   não houver chave da API de rotas, `disponivel` vem `false` do backend: a
   tela **diz por quê** e o campo de km continua manual — que é como ele é
   preenchido desde 21/10. Botão que abre e falha é pior que botão que não
   existe.

   🚨 E A MEMÓRIA DA ORIGEM FUNCIONA DE QUALQUER JEITO: o backend grava o que
   foi digitado mesmo quando o cálculo não acontece. Então *"fica salvo para
   proximas"* já vale, sem chave nenhuma.

   ⚠️ O CEP é consultado **pelo backend** (`/api/cep/{cep}`), nunca pelo
   navegador, e tem três respostas distinguíveis — achou · não existe · não deu
   para consultar. "Não deu para consultar" NÃO é "CEP errado", e a tela diz
   qual dos dois foi: senão o operador apaga um CEP certo achando que errou.

   ⚠️ O que o CEP preenche é SUGESTÃO: os campos continuam editáveis, e o CEP
   **nunca** preenche o número.
   ============================================================================ */
import { ref, computed, onMounted } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'

const props = defineProps({
  /* A conversa. 🚨 De quem é a origem é o SERVIDOR que descobre, por ela: com
     o id do contato vindo do navegador, qualquer um com a tela sobrescreveria
     a origem de outro técnico trocando um número. */
  conversaId: { type: Number, default: null },
  /* O destino, já preenchido pelo passo do endereço do agendamento. */
  destinoInicial: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['fechar', 'usar'])

/* Os mesmos sete campos e limites do endereço do agendamento (migração 073):
   duas réguas para o mesmo endereço é uma delas mentindo. */
const LIMITES = { cep: 8, logradouro: 80, numero: 10, bairro: 60, cidade: 50,
                  uf: 2, complemento: 40 }

function vazio() {
  return { cep: '', logradouro: '', numero: '', bairro: '', cidade: '', uf: '',
           complemento: '' }
}

const origem = ref(vazio())
const destino = ref({ ...vazio(), ...props.destinoInicial })
const idaEVolta = ref(true)

const disponivel = ref(false)
const memoriaDe = ref('')
const calculando = ref(false)
const erro = ref('')
const aviso = ref('')
const resultado = ref(null)      // { km_ida, km, do_cache, consultado_em }
const kmManual = ref('')
const cepEstado = ref('')        // '' | curto | nao-existe | caiu

const temMinimo = computed(() =>
  !!origem.value.logradouro.trim() && !!origem.value.cidade.trim()
  && !!destino.value.logradouro.trim() && !!destino.value.cidade.trim())

/* O número que vai para a linha do orçamento: o calculado, ou o digitado. */
const kmFinal = computed(() => {
  if (resultado.value && resultado.value.km != null) return resultado.value.km
  const n = Number(String(kmManual.value).replace(',', '.'))
  return Number.isFinite(n) && n > 0 ? n : null
})

onMounted(async () => {
  try {
    const p = props.conversaId ? `?conversa_id=${props.conversaId}` : ''
    const r = await api.get(`/api/rotas/origem${p}`)
    disponivel.value = !!r.disponivel
    if (r.origem) {
      origem.value = { ...vazio(), ...r.origem }
      memoriaDe.value = r.origem.atualizado_em || ''
    }
  } catch {
    /* A memória é conveniência, não pré-requisito: sem ela a pessoa digita. */
    disponivel.value = false
  }
})

async function buscarCep(qual) {
  const alvo = qual === 'origem' ? origem : destino
  const digitos = (alvo.value.cep || '').replace(/\D/g, '')
  cepEstado.value = ''
  if (digitos.length !== 8) {
    if (digitos.length) cepEstado.value = 'curto'
    return
  }
  try {
    const r = await api.get(`/api/cep/${digitos}`)
    if (!r.achado) {
      cepEstado.value = 'nao-existe'
      return
    }
    /* ⚠️ Só preenche o que veio, e NUNCA o número: ele não está no CEP. */
    for (const campo of ['logradouro', 'bairro', 'cidade', 'uf']) {
      if (r[campo]) alvo.value[campo] = String(r[campo]).slice(0, LIMITES[campo])
    }
  } catch {
    cepEstado.value = 'caiu'
  }
}

async function calcular() {
  calculando.value = true
  erro.value = ''
  aviso.value = ''
  resultado.value = null
  try {
    const r = await api.post('/api/rotas/km', {
      conversa_id: props.conversaId || null,
      origem: origem.value,
      destino: destino.value,
      ida_e_volta: idaEVolta.value,
    })
    if (r.km == null) {
      /* Respondeu e não achou rota: é diferente de "não deu para perguntar",
         e a tela não pode chamar os dois da mesma coisa. */
      aviso.value = r.motivo || 'não achei uma rota entre estes dois endereços'
      return
    }
    resultado.value = r
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não deu para calcular agora.'
  } finally {
    calculando.value = false
  }
}

function usar() {
  if (kmFinal.value == null) return
  /* Devolve o km E a origem: quem grava o compromisso precisa dos dois (o
     retrato da migração 077). */
  emit('usar', { km: kmFinal.value, origem: { ...origem.value },
                 ida_e_volta: idaEVolta.value })
}

/* ---- O CAMINHO SEM API (🔵 ideia dele, 26/10) ------------------------------
   *"talvez botões que abrem no browser da pessoa e a rota pronta e pegue o
   KM"*.

   🚨 ESTE É O CAMINHO PRINCIPAL, não o reserva: custa zero, não precisa de
   chave, e o km sai da MESMA fonte que ele já confere à mão -- então não há
   divergência entre o que o sistema diz e o que o Google diz. O que o link
   resolve é o trabalho: chegar lá com os dois endereços já preenchidos.

   ⚠️ É um `<a target="_blank">`, não `window.open`: bloqueador de pop-up come
   `window.open` sem aviso, e aí o clique não faria nada e pareceria defeito.
   Com âncora, o meio-clique e o "copiar link" também funcionam. */
function comoTexto(e) {
  const primeiro = [e.logradouro, e.numero].filter(Boolean).join(', ')
  const local = [e.cidade, e.uf].filter(Boolean).join(' - ')
  return [primeiro, e.bairro, local, e.cep, 'Brasil']
    .map((p) => (p || '').trim()).filter(Boolean).join(', ')
}

/* 🚨 "TEM TEXTO" NÃO É "TEM ENDEREÇO". `comoTexto` anexa "Brasil" sempre, então
   com os campos em branco ela devolve `"Brasil"` -- e o link nascia válido,
   abrindo uma rota de um país para ele mesmo. A régua é CONTEÚDO ÚTIL: rua ou
   cidade. Achado pelo teste, não pela leitura. */
function temEndereco(e) {
  return !!(e.logradouro || '').trim() || !!(e.cidade || '').trim()
}

const linkDaRota = computed(() => {
  if (!temEndereco(origem.value) || !temEndereco(destino.value)) return ''
  const p = new URLSearchParams({ api: '1',
                                  origin: comoTexto(origem.value),
                                  destination: comoTexto(destino.value),
                                  travelmode: 'driving' })
  return `https://www.google.com/maps/dir/?${p.toString()}`
})

/* ⚠️ Dá para abrir com o endereço PELA METADE (sem número, sem bairro): o
   Google completa o que consegue, e ver a rota aproximada já ajuda. O que não
   dá é abrir sem rua nem cidade em um dos lados. */
const podeAbrirRota = computed(() => !!linkDaRota.value)

function quando(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
}
</script>

<template>
  <!-- A casca é a `.modal` global, com o `--z-modal` arrumado no bloco B —
       é o que faz este modal aparecer POR CIMA do de agendar. -->
  <div class="modal km" @click.self="emit('fechar')">
    <div class="modal__caixa km__caixa" role="dialog" aria-modal="true"
         aria-label="Calcular KM do técnico">
      <p class="modal__titulo">KM do deslocamento</p>

      <!-- 🚨 A TELA DIZ SE O CÁLCULO EXISTE, antes de qualquer botão. -->
      <p v-if="!disponivel" class="aviso aviso--info">
        <i class="bi bi-info-circle aviso__icone" aria-hidden="true"></i>
        <span>
          Abra a rota no Google com os dois endereços já preenchidos, veja o km
          e traga para o campo abaixo. O endereço de origem <b>fica
          guardado</b> para a próxima vez.
        </span>
      </p>

      <section class="km__bloco">
        <header class="km__cabecalho">
          <strong>Origem — de onde o técnico sai</strong>
          <span v-if="memoriaDe" class="chip chip--pequeno">
            guardado em {{ quando(memoriaDe) }}
          </span>
        </header>
        <div class="km__campos">
          <label class="campo campo--cep">
            <span class="campo__rotulo">CEP</span>
            <input v-model="origem.cep" class="campo__entrada" inputmode="numeric"
                   :maxlength="LIMITES.cep" @blur="buscarCep('origem')" />
          </label>
          <label class="campo km__rua">
            <span class="campo__rotulo">Rua</span>
            <input v-model="origem.logradouro" class="campo__entrada"
                   :maxlength="LIMITES.logradouro" />
          </label>
          <label class="campo campo--curto">
            <span class="campo__rotulo">Nº</span>
            <input v-model="origem.numero" class="campo__entrada"
                   :maxlength="LIMITES.numero" />
          </label>
          <label class="campo">
            <span class="campo__rotulo">Bairro</span>
            <input v-model="origem.bairro" class="campo__entrada"
                   :maxlength="LIMITES.bairro" />
          </label>
          <label class="campo">
            <span class="campo__rotulo">Cidade</span>
            <input v-model="origem.cidade" class="campo__entrada"
                   :maxlength="LIMITES.cidade" />
          </label>
          <label class="campo campo--curto">
            <span class="campo__rotulo">UF</span>
            <input v-model="origem.uf" class="campo__entrada"
                   :maxlength="LIMITES.uf" />
          </label>
        </div>
      </section>

      <section class="km__bloco">
        <header class="km__cabecalho">
          <strong>Destino — onde o serviço acontece</strong>
        </header>
        <div class="km__campos">
          <label class="campo campo--cep">
            <span class="campo__rotulo">CEP</span>
            <input v-model="destino.cep" class="campo__entrada" inputmode="numeric"
                   :maxlength="LIMITES.cep" @blur="buscarCep('destino')" />
          </label>
          <label class="campo km__rua">
            <span class="campo__rotulo">Rua</span>
            <input v-model="destino.logradouro" class="campo__entrada"
                   :maxlength="LIMITES.logradouro" />
          </label>
          <label class="campo campo--curto">
            <span class="campo__rotulo">Nº</span>
            <input v-model="destino.numero" class="campo__entrada"
                   :maxlength="LIMITES.numero" />
          </label>
          <label class="campo">
            <span class="campo__rotulo">Bairro</span>
            <input v-model="destino.bairro" class="campo__entrada"
                   :maxlength="LIMITES.bairro" />
          </label>
          <label class="campo">
            <span class="campo__rotulo">Cidade</span>
            <input v-model="destino.cidade" class="campo__entrada"
                   :maxlength="LIMITES.cidade" />
          </label>
          <label class="campo campo--curto">
            <span class="campo__rotulo">UF</span>
            <input v-model="destino.uf" class="campo__entrada"
                   :maxlength="LIMITES.uf" />
          </label>
        </div>
      </section>

      <!-- Os três estados do CEP, separados de propósito. -->
      <p v-if="cepEstado === 'curto'" class="aviso aviso--atencao">
        <span>O CEP tem 8 dígitos.</span>
      </p>
      <p v-else-if="cepEstado === 'nao-existe'" class="aviso aviso--atencao">
        <span>Este CEP não existe na base dos Correios. Confira, ou preencha à mão.</span>
      </p>
      <p v-else-if="cepEstado === 'caiu'" class="aviso aviso--erro">
        <span>
          Não deu para consultar o CEP agora — isto <b>não</b> quer dizer que
          ele está errado. Preencha à mão, ou tente de novo.
        </span>
      </p>

      <label class="campo campo--caixa km__volta">
        <input v-model="idaEVolta" type="checkbox" />
        <span class="campo__rotulo">ida e volta (o técnico volta)</span>
      </label>

      <div class="km__acoes">
        <!-- 🔵 O caminho sem API, e o PRIMEIRO da fila: custa zero e o número
             vem da mesma fonte que ele já confere. -->
        <a v-if="podeAbrirRota" class="botao botao--primario" :href="linkDaRota"
           target="_blank" rel="noopener noreferrer">
          <i class="bi bi-map" aria-hidden="true"></i> Ver a rota no Google
        </a>
        <span v-else class="apagado pequeno">
          preencha os endereços para abrir a rota
        </span>

        <!-- O cálculo automático, quando houver chave. ⚠️ Fica DEPOIS do link:
             o link é o que funciona sempre. -->
        <button v-if="disponivel" class="botao botao--contorno" type="button"
                :disabled="calculando || !temMinimo" @click="calcular">
          <span v-if="calculando" class="girando"></span>
          <i v-else class="bi bi-signpost-2" aria-hidden="true"></i>
          {{ calculando ? 'calculando…' : 'Calcular aqui' }}
        </button>
        <span v-if="disponivel && !temMinimo" class="apagado pequeno">
          precisa de rua e cidade nos dois
        </span>
      </div>

      <p v-if="aviso" class="aviso aviso--atencao">
        <span>{{ aviso }} — confira os endereços, ou digite o km abaixo.</span>
      </p>
      <p v-if="erro" class="aviso aviso--erro" role="alert">
        <span>{{ erro }}</span>
      </p>

      <!-- 🚨 AS DUAS CONTAS À VISTA: ninguém cobra errado por distração. -->
      <p v-if="resultado" class="aviso aviso--ok">
        <i class="bi bi-check-circle aviso__icone" aria-hidden="true"></i>
        <span>
          Ida <b>{{ resultado.km_ida }} km</b> ·
          total a cobrar <b>{{ resultado.km }} km</b>
          <template v-if="idaEVolta"> (ida e volta)</template>
          <span v-if="resultado.do_cache" class="apagado pequeno">
            — número já consultado em {{ quando(resultado.consultado_em) }}
          </span>
        </span>
      </p>

      <label class="campo km__manual">
        <span class="campo__rotulo">
          KM a cobrar{{ resultado ? ' (dá para corrigir)' : '' }}
        </span>
        <input :value="kmFinal != null ? kmFinal : kmManual"
               class="campo__entrada" inputmode="decimal" placeholder="0,0"
               @input="kmManual = $event.target.value; resultado = null" />
        <span class="campo__ajuda">
          Vai para a linha <b>KM DESLOCAMENTO</b> do orçamento. O valor em reais
          é calculado no servidor, pelo preço unitário da linha.
          <template v-if="idaEVolta">
            ⚠️ O Google mostra o km <b>de ida</b>: para ida e volta, dobre.
          </template>
        </span>
      </label>

      <div class="modal__acoes">
        <button class="botao botao--contorno" type="button" @click="emit('fechar')">
          Voltar
        </button>
        <button class="botao botao--primario" type="button"
                :disabled="kmFinal == null" @click="usar">
          Usar {{ kmFinal != null ? kmFinal + ' km' : 'o km' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* A caixa é maior que a `.modal__caixa` padrão: são dois endereços. */
.km__caixa { max-width: 680px; }

.km__bloco { margin-bottom: var(--e-4); }
.km__cabecalho {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  flex-wrap: wrap;
  margin-bottom: var(--e-2);
}
.km__campos {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: var(--e-2);
}
.km__rua { grid-column: span 2; }
.campo--cep { max-width: 140px; }
.campo--curto { max-width: 90px; }
.campo--caixa { flex-direction: row; align-items: center; gap: var(--e-2); }

.km__volta { margin-bottom: var(--e-3); }
.km__acoes {
  display: flex;
  align-items: center;
  gap: var(--e-3);
  flex-wrap: wrap;
  margin-bottom: var(--e-3);
}
.km__manual { margin-top: var(--e-3); }

@media (max-width: 640px) {
  .km__rua { grid-column: span 1; }
}
</style>
