<!--
  CFG_16.1 — DISPAROS OPERAÇÃO
  ============================================================================
  🔵 11/11, dele: *"Em configurações tela nova de 'Disparos Operação' -> Deixar o
  campo de menagens que são enviadas em cada etapa do fluxo com interruptor de
  'ligado e desligado'"* · *"nasce em branco e com interruptor desligado ainda,
  na tela de config exclusiva owner"* · *"por hora só whatsapp"* · *"por enquanto
  somente cliente deixe no painel de disparos uma nota que nenhuma vai ao
  tecnico"*.

  🚨 ESTA TELA GOVERNA A PRIMEIRA COISA DO PAINEL QUE FALA COM O CLIENTE
  SOZINHA. Com o interruptor ligado, mover um card para a etapa **envia** --
  sem mais nenhuma confirmação. É por isso que ela mostra o texto final de um
  exemplo: é a última conferência que existe antes de o cliente receber.

  ⚠️ O interruptor só liga com texto: o servidor recusa com frase, e o banco
  recusa de novo (CHECK da migração 102).
-->
<script setup>
import { computed, onMounted, ref } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'

const etapas = ref([])
const variaveis = ref([])
const canal = ref('whatsapp')
const vaiPara = ref('cliente')
const teto = ref(2000)

const carregando = ref(true)
const erro = ref('')
const salvando = ref(0)
const aberta = ref(null)

/* O rascunho por etapa: o texto só vai ao servidor no Salvar. ⚠️ Um `v-model`
   direto na lista gravaria a cada tecla, e aqui gravar é mexer no que o cliente
   vai receber. */
const rascunho = ref({})

const ligadas = computed(() => etapas.value.filter((e) => e.ativo).length)

/* 🚨 O EXEMPLO RESOLVIDO, e é o que faz desta tela uma conferência de verdade:
   ler `{{Nome}}` não diz nada sobre o que o cliente vê. Os valores são de
   exemplo e a tela diz isso. */
function exemplo(texto) {
  return String(texto || '')
    .replaceAll('{{Contato: Primeiro nome}}', 'João')
    .replaceAll('{{Nome}}', '17105')
    .replaceAll('{{Código de envio/acompanhamento transporte}}', 'AA123456789BR')
    .replace(/\{\{[^}]*\}\}/g, '')
    .trim()
}

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    const r = await api.get('/api/config/disparos-operacao')
    etapas.value = r.etapas || []
    variaveis.value = r.variaveis || []
    canal.value = r.canal || 'whatsapp'
    vaiPara.value = r.vai_para || 'cliente'
    teto.value = r.teto || 2000
    const novo = {}
    for (const e of etapas.value) novo[e.situacao_id] = e.texto || ''
    rascunho.value = novo
  } catch (e) {
    erro.value = e instanceof ErroDeApi
      ? e.message : 'Não consegui ler os disparos.'
  } finally {
    carregando.value = false
  }
}

function mudou(e) {
  return (rascunho.value[e.situacao_id] || '') !== (e.texto || '')
}

async function salvar(e, ativo) {
  if (salvando.value) return
  salvando.value = e.situacao_id
  erro.value = ''
  try {
    await api.put(`/api/config/disparos-operacao/${e.situacao_id}`,
                  { texto: rascunho.value[e.situacao_id] || null,
                    ativo: ativo === undefined ? e.ativo : ativo })
    await carregar()
  } catch (err) {
    erro.value = err instanceof ErroDeApi
      ? err.message : 'Não consegui salvar este disparo.'
  } finally {
    salvando.value = 0
  }
}

function inserir(e, chave) {
  rascunho.value[e.situacao_id] =
    `${rascunho.value[e.situacao_id] || ''}${chave}`
}

onMounted(carregar)
</script>

<template>
  <section class="disparos">
    <header class="disparos__topo">
      <h2>Disparos Operação</h2>
      <!-- 🚨 ESTADO, NÃO PARÁGRAFO (ele já tirou texto explicativo 3 vezes). -->
      <p class="nota pequeno">
        <strong>{{ ligadas }} de {{ etapas.length }}</strong> etapas ligadas ·
        canal {{ canal }} · vai para o {{ vaiPara }}
      </p>
      <!-- 🔵 A NOTA QUE ELE PEDIU, literal no sentido: *"deixe no painel de
           disparos uma nota que nenhuma vai ao tecnico"*. -->
      <p class="aviso aviso--atencao">
        Nenhuma destas mensagens vai ao técnico.
      </p>
    </header>

    <p v-if="carregando" class="nota pequeno">lendo…</p>
    <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>

    <ul v-if="!carregando" class="etapas">
      <li v-for="e in etapas" :key="e.situacao_id" class="etapa">
        <button type="button" class="etapa__porta"
                :aria-expanded="aberta === e.situacao_id"
                @click="aberta = aberta === e.situacao_id ? null : e.situacao_id">
          <strong>{{ e.nome }}</strong>
          <!-- ⚠️ "Ligado"/"Desligado" por extenso, e não só cor: cor sozinha
               não é portador, e aqui a diferença é "fala com o cliente" ou
               "não fala". -->
          <span class="pilula"
                :class="e.ativo ? 'pilula--alerta' : 'pilula--neutra'">
            {{ e.ativo ? 'Ligado' : 'Desligado' }}
          </span>
        </button>

        <div v-if="aberta === e.situacao_id" class="etapa__corpo">
          <textarea v-model="rascunho[e.situacao_id]" rows="4"
                    class="campo__entrada" :maxlength="teto"
                    :aria-label="`Mensagem da etapa ${e.nome}`"
                    placeholder="Sem mensagem nesta etapa"></textarea>

          <div class="etapa__variaveis">
            <button v-for="v in variaveis" :key="v.chave" type="button"
                    class="botao botao--pequeno botao--fantasma"
                    :title="v.o_que_e" @click="inserir(e, v.chave)">
              {{ v.chave }}
            </button>
          </div>

          <!-- 🚨 O QUE O CLIENTE VAI LER, com valores de exemplo. É a última
               conferência antes de ligar o interruptor. -->
          <p v-if="rascunho[e.situacao_id]" class="etapa__exemplo">
            <span class="apagado pequeno">o cliente lê</span><br />
            {{ exemplo(rascunho[e.situacao_id]) }}
          </p>

          <div class="etapa__acoes">
            <button class="botao" type="button"
                    :disabled="!mudou(e) || salvando === e.situacao_id"
                    @click="salvar(e)">Salvar texto</button>

            <button class="botao botao--contorno" type="button"
                    :disabled="salvando === e.situacao_id
                               || (!e.ativo && !String(rascunho[e.situacao_id] || '').trim())"
                    @click="salvar(e, !e.ativo)">
              {{ e.ativo ? 'Desligar' : 'Ligar' }}
            </button>

            <span v-if="e.atualizado_por_nome" class="apagado pequeno">
              por {{ e.atualizado_por_nome }}
            </span>
          </div>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.disparos { display: flex; flex-direction: column; gap: var(--e-4); }
.disparos__topo h2 { margin: 0 0 var(--e-1); font-size: var(--txt-lg); }
.disparos__topo .nota { margin: 0 0 var(--e-2); }

.etapas { list-style: none; margin: 0; padding: 0;
          display: flex; flex-direction: column; gap: var(--e-2); }
.etapa { border: 1px solid var(--borda); border-radius: var(--r-md);
         background: var(--superficie); overflow: hidden; }

.etapa__porta {
  width: 100%; display: flex; align-items: center; justify-content: space-between;
  gap: var(--e-3); padding: var(--e-3) var(--e-4);
  min-height: var(--altura-toque);
  background: none; border: 0; font: inherit; color: inherit;
  cursor: pointer; text-align: left;
}
.etapa__porta:hover { background: var(--superficie-2); }

.etapa__corpo { padding: 0 var(--e-4) var(--e-4);
                display: flex; flex-direction: column; gap: var(--e-3); }

/* ⚠️ `wrap` nos dois grupos: em tela de celular os botões não cabem numa
   linha, e sem isto saem da tela. */
.etapa__variaveis { display: flex; gap: var(--e-2); flex-wrap: wrap; }
.etapa__acoes { display: flex; gap: var(--e-2); flex-wrap: wrap;
                align-items: center; }

.etapa__exemplo {
  margin: 0; padding: var(--e-3);
  border-left: 3px solid var(--acento, #1B75BB);
  background: var(--superficie-2);
  white-space: pre-wrap;
}

/* 🚨 A `.pilula` É SCOPED POR COMPONENTE nesta casa -- ela não existe em
   `estilo/*.css`. O `PainelOperacao` e o `PainelAba` definem cada um a sua, e
   tela nova que usa a classe sem declarar fica com o selo SEM ESTILO: não
   quebra, não avisa, só fica feio. ⚠️ Nenhuma trava de tela pega isso, porque
   o jsdom não faz layout.
   ⚠️ Os valores são os do `PainelAba`, para os selos da casa parecerem os
   mesmos selos. */
.pilula {
  display: inline-flex; align-items: center; gap: var(--e-1);
  align-self: flex-start;
  padding: 1px var(--e-2); border-radius: var(--r-full);
  background: var(--superficie-2); color: var(--texto-fraco);
  font-size: var(--txt-xs); font-weight: var(--peso-forte);
}
/* ⚠️ Os dois que alertam diferem em LUMINOSIDADE, não só em matiz -- âmbar e
   verde, nunca vermelho e verde. É a régua do card. */
.pilula--alerta {
  color: var(--aviso-texto); background: var(--aviso-suave);
}
.pilula--pronto {
  color: var(--ok-texto); background: var(--ok-suave);
}
.pilula--neutra {
  color: var(--texto-fraco); background: var(--superficie-2);
}
</style>
