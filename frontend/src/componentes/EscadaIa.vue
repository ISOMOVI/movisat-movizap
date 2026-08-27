<script setup>
/* ============================================================================
   A escada da IA — os quatro interruptores num lugar só.
   ----------------------------------------------------------------------------
   🚨 POR QUE ISTO EXISTE. Em 26/08 o usuário disse: *"não tem botão nenhum
   ali, nem por canal, nem por prompt e nem por tipo"*. Os três botões
   existiam, em TRÊS TELAS DIFERENTES, e eu medi no journal que ele estava com
   o bundle certo -- não era cache. O defeito era o painel esconder o que não
   pode fazer:

     CFG_1.1  o "Ligar IA" era o QUARTO botão de contorno de uma fileira cinza
     CFG_5.1  botão sempre `:disabled`, sem dizer o que destrava
     CFG_2.1  a sala de ensaio SUMIA inteira (`v-if`) quando faltava prompt --
              a tela escondia justamente o caminho que levaria ao prompt

   🚨 A REGRA DESTA TELA, E ELA VALE PARA TODO DEGRAU: **nada some**. Degrau
   travado fica cinza, com o motivo escrito e o link para o degrau que o
   destrava. Um botão que desaparece não ensina nada; um botão cinza que diz
   "precisa de prompt publicado" ensina.

   🚨 SÃO QUATRO TRAVAS SEPARADAS DE PROPÓSITO, e a ordem é a ordem de uso.
   Ligar o tipo (3) não põe a IA no ar, e ligar o canal (4) sozinho também
   não. `docs/04`, sequência de ativação.
   ============================================================================ */
import { computed, onMounted, ref } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'

const emit = defineEmits(['ir-para'])

const prompt = ref(null)
const automacao = ref(null)
const canais = ref([])
const carregando = ref(true)
const erro = ref('')
const recado = ref('')
const ocupado = ref(false)

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    const [p, a, c] = await Promise.all([
      api.get('/api/ia/prompt'),
      api.get('/api/automacao'),
      api.get('/api/canais'),
    ])
    prompt.value = p
    automacao.value = a
    canais.value = c
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao ler o estado da IA.'
  } finally {
    carregando.value = false
  }
}

/* 🚨 SÓ O CANAL DE ATENDIMENTO. O informativo é disparo, não conversa, e a
   rota recusa -- a tela não oferece o que o backend nega. */
const canalDeAtendimento = computed(
  () => canais.value.find((c) => c.tipo === 'atendimento' && c.ativo) || null,
)

const temPrompt = computed(() => Boolean(prompt.value?.versao_ativa))
const motorPronto = computed(() => Boolean(prompt.value?.motor_existe))
const motivoDoMotor = computed(() => prompt.value?.motor?.motivo || '')

const tiposLigados = computed(
  () => (automacao.value?.tipos || []).filter((t) => t.ia_ligada),
)
const totalTipos = computed(() => (automacao.value?.tipos || []).length)
const pessoasAlcancadas = computed(
  () => tiposLigados.value.reduce((soma, t) => soma + (t.contatos || 0), 0),
)

const noAr = computed(() => Boolean(canalDeAtendimento.value?.ia_ligada))

/* ⚠️ DESLIGAR NUNCA TRAVA. É exatamente quando o motor está ruim que alguém
   quer desligar -- a regra vem do backend (`canais.definir_ia`) e a tela não
   pode contradizê-la. */
const travaDoCanal = computed(() => {
  if (noAr.value) return ''
  if (!canalDeAtendimento.value) return 'nenhum canal de atendimento ativo'
  if (!motorPronto.value) return motivoDoMotor.value || 'o motor não está disponível'
  if (!tiposLigados.value.length) {
    return 'nenhum tipo de contato ligado — ligar aqui não faria a IA responder ninguém'
  }
  return ''
})

/* Os quatro degraus, montados como DADO e não como marcação repetida: é o que
   garante que todos apareçam sempre, inclusive os travados. */
const degraus = computed(() => [
  {
    n: 1,
    titulo: 'Prompt publicado',
    feito: temPrompt.value,
    estado: temPrompt.value
      ? `versão ${prompt.value.versao_ativa.versao}, por ${prompt.value.versao_ativa.autor_nome || '—'}`
      : 'nenhuma versão publicada',
    trava: '',
    acao: temPrompt.value ? 'Ver e editar' : 'Escrever o prompt',
    aba: 'CFG_2.1',
    ancora: 'prompt-editor',
  },
  {
    n: 2,
    titulo: 'Ensaio',
    feito: false,
    estado: motorPronto.value
      ? 'cole uma conversa real e veja o que ela responderia'
      : 'indisponível',
    // 🚨 O MOTIVO VEM DO MOTOR, não daqui. A tela não decide se pode: ela
    // desenha o que o backend respondeu, com o porquê junto.
    trava: motorPronto.value ? '' : (motivoDoMotor.value || 'o motor não está disponível'),
    acao: 'Abrir a sala de ensaio',
    aba: 'CFG_2.1',
    ancora: 'sala-de-ensaio',
  },
  {
    n: 3,
    titulo: 'Tipos de contato',
    feito: tiposLigados.value.length > 0,
    estado: `${tiposLigados.value.length} de ${totalTipos.value} ligados`
      + (pessoasAlcancadas.value ? ` — alcança ${pessoasAlcancadas.value} pessoas` : ''),
    trava: motorPronto.value ? '' : (motivoDoMotor.value || 'o motor não está disponível'),
    acao: 'Escolher os tipos',
    aba: 'CFG_5.1',
  },
  {
    n: 4,
    titulo: 'Canal de atendimento',
    feito: noAr.value,
    estado: canalDeAtendimento.value
      ? (noAr.value ? 'a IA está no ar neste canal' : 'a IA está desligada')
      : 'nenhum canal de atendimento ativo',
    trava: travaDoCanal.value,
    acao: noAr.value ? 'Desligar a IA' : 'Ligar a IA',
    aba: null,
  },
])

/* 🚨 TROCAR DE ABA NÃO BASTA QUANDO A ABA JÁ É ESTA. Achado conferindo depois
   de entregar: os passos 1 e 2 apontam para a CFG_2.1, e a escada MORA na
   CFG_2.1 -- clicar trocava a URL e não acontecia nada na tela. É o defeito
   que a Automacao.vue já tinha escrito em comentário: "botão que não faz nada
   é pior que botão ausente, porque alguém confia nele".

   ⚠️ A rolagem espera o próximo quadro: quando a aba MUDA, o alvo ainda não
   está no DOM no instante do clique. */
function agir(degrau) {
  if (!degrau.aba) {
    alternarCanal()
    return
  }
  emit('ir-para', degrau.aba)
  if (!degrau.ancora) return
  requestAnimationFrame(() => {
    const alvo = document.getElementById(degrau.ancora)
    if (alvo) alvo.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

async function alternarCanal() {
  const canal = canalDeAtendimento.value
  if (!canal) return
  const ligando = !canal.ia_ligada
  const aviso = ligando
    ? `A IA vai responder sozinha no canal "${canal.nome}".\n\n`
      + 'Ela só atende o que chegar A PARTIR DE AGORA: conversa parada não é '
      + 'respondida.\n\nConfirma?'
    : `Desligar a IA no canal "${canal.nome}"?\n\n`
      + 'As conversas que ela estava atendendo ficam onde estão, esperando gente.'
  if (!window.confirm(aviso)) return

  ocupado.value = true
  recado.value = ''
  try {
    await api.put(`/api/canais/${canal.id}/ia`, { ligada: ligando })
    recado.value = ligando
      ? 'IA ligada. Ela atende o que chegar a partir de agora.'
      : 'IA desligada.'
    await carregar()
  } catch (e) {
    recado.value = e instanceof ErroDeApi ? e.message : 'Falha ao mudar a IA.'
  } finally {
    ocupado.value = false
  }
}

onMounted(carregar)
defineExpose({ carregar })
</script>

<template>
  <section class="escada">
    <header class="escada__topo">
      <div>
        <h2 class="escada__titulo">
          <i class="bi bi-robot" aria-hidden="true"></i>
          A IA, em quatro passos
        </h2>
        <p class="fraco pequeno escada__subtitulo">
          Na ordem em que se usa. Passo travado continua aqui, cinza, dizendo o
          que falta — nenhum deles some.
        </p>
      </div>
      <span class="chip" :class="noAr ? 'chip--acento' : ''">
        {{ noAr ? 'IA no ar' : 'IA desligada' }}
      </span>
    </header>

    <p v-if="carregando" class="linha fraco escada__carregando">
      <span class="girando"></span> Lendo o estado da IA…
    </p>

    <p v-else-if="erro" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>{{ erro }}</span>
    </p>

    <template v-else>
      <p v-if="recado" class="aviso aviso--ok" role="status">
        <i class="bi bi-check-circle aviso__icone" aria-hidden="true"></i>
        <span>{{ recado }}</span>
      </p>

      <ol class="escada__lista">
        <li v-for="d in degraus" :key="d.n"
            class="degrau"
            :class="{ 'degrau--feito': d.feito, 'degrau--travado': Boolean(d.trava) }">
          <span class="degrau__numero" aria-hidden="true">
            <i v-if="d.feito" class="bi bi-check-lg"></i>
            <template v-else>{{ d.n }}</template>
          </span>

          <div class="degrau__corpo">
            <p class="degrau__titulo">{{ d.titulo }}</p>
            <p class="degrau__estado pequeno">{{ d.estado }}</p>
            <!-- 🚨 O MOTIVO É A PARTE QUE FALTAVA. Botão cinza sem explicação
                 é o mesmo que botão ausente: ninguém descobre o que fazer. -->
            <p v-if="d.trava" class="degrau__trava pequeno">
              <i class="bi bi-lock" aria-hidden="true"></i> {{ d.trava }}
            </p>
          </div>

          <button class="botao degrau__acao"
                  :class="d.n === 4 && !d.trava
                    ? (noAr ? 'botao--perigo' : 'botao--primario')
                    : 'botao--contorno'"
                  type="button"
                  :disabled="Boolean(d.trava) || ocupado"
                  :title="d.trava || d.acao"
                  @click="agir(d)">
            {{ d.acao }}
          </button>
        </li>
      </ol>

      <p class="escada__nota pequeno fraco">
        <i class="bi bi-info-circle" aria-hidden="true"></i>
        O passo 3 e o passo 4 são travas separadas: ligar um sem o outro não
        põe a IA para responder ninguém.
      </p>
    </template>
  </section>
</template>

<style scoped>
.escada {
  padding: var(--e-5);
  margin-bottom: var(--e-5);
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
}

.escada__topo {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--e-4);
  margin-bottom: var(--e-4);
}
.escada__titulo {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  margin: 0;
  font-size: var(--txt-lg);
  font-weight: var(--peso-forte);
}
.escada__subtitulo { margin: var(--e-1) 0 0; }
.escada__carregando { padding: var(--e-3) 0; }

.escada__lista {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--e-2);
}

.degrau {
  display: flex;
  align-items: center;
  gap: var(--e-3);
  padding: var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-sm);
  background: var(--fundo);
}
/* ⚠️ O degrau travado fica APAGADO, nunca escondido: é a regra desta tela. */
.degrau--travado { opacity: .72; }
.degrau--feito { border-color: var(--ok); }

.degrau__numero {
  flex: none;
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border-radius: var(--r-full);
  background: var(--superficie-2);
  color: var(--texto-fraco);
  font-size: var(--txt-sm);
  font-weight: var(--peso-forte);
}
.degrau--feito .degrau__numero { background: var(--ok); color: #fff; }

.degrau__corpo { flex: 1 1 auto; min-width: 0; }
.degrau__titulo { margin: 0; font-weight: var(--peso-medio); }
.degrau__estado { margin: 2px 0 0; color: var(--texto-fraco); }
.degrau__trava { margin: 2px 0 0; color: var(--aviso); }

.degrau__acao { flex: none; }

.escada__nota {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  margin: var(--e-4) 0 0;
}

@media (max-width: 720px) {
  .degrau { flex-wrap: wrap; }
  .degrau__acao { width: 100%; }
}
</style>
