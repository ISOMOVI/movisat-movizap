<script setup>
/* ============================================================================
   Um recado em formato de conversa — o balão do painel da Operação.
   ----------------------------------------------------------------------------
   🔵 04/11: *"Card OBS anexos, texto, format conve -- exibir em modal"*.

   🚨 ESTE COMPONENTE NÃO FOI EXTRAÍDO DA `CaixaDeEntrada.vue`, e isso é uma
   escolha declarada. O plano previa extrair, mas o markup das bolhas vive
   dentro de uma tela de ~4 mil linhas que é a mais usada do sistema, com
   modificadores próprios (`balao--casa`, `balao--atual`, `balao--tocado`,
   `balao--realcado`, mídia, citada, áudio). Mexer nela para reaproveitar
   bolha de recado seria risco desproporcional ao ganho.

   ⚠️ O custo está dito: agora há **três** desenhos de bolha no projeto — o da
   Caixa, o do Chat interno e este. Unificá-los é frente própria, e o recado
   aqui é bem mais simples que os outros dois (não tem mídia inline, nem
   citação, nem áudio).

   ⚠️ O recado do SISTEMA (`[checklist] ...`, `[sistema] prioridade: ...`) é
   desenhado diferente: ele não foi escrito por uma pessoa, e mostrá-lo igual
   a um recado humano faria parecer que alguém digitou aquilo.
   ============================================================================ */
import { computed, ref } from 'vue'
import { pedirBlob } from '../api/cliente.js'

const props = defineProps({
  recado: { type: Object, required: true },
  quando: { type: Function, required: true },
  /* 🔵 11/11: apagar observação. `souOwner` decide se o botão
     "ver o que dizia" existe -- e **quem diz é o servidor**: para quem não é
     owner o `texto` já vem nulo, então o botão não teria o que revelar. */
  souOwner: { type: Boolean, default: false },
  podeApagar: { type: Boolean, default: false },
})

const emit = defineEmits(['apagar'])

/* `[checklist]` e `[sistema]` são os dois prefixos que o servidor usa. */
const doSistema = computed(
  () => /^\[(checklist|sistema)\]/.test(props.recado.texto || ''))

/* 🔵 11/11, dele: *"os marcados ficam com em verde e os não marcados ficam
   em vermelho"*.

   🚨 A CLASSE SAI DO PRÓPRIO ✓/✗, QUE CONTINUA NO TEXTO. Cor sozinha não é
   portador de informação -- quem não distingue verde de vermelho continua
   lendo o sinal, exatamente como a pílula do card usa âmbar E luminosidade
   diferente, e como o item feito do checklist é riscado E esmaecido.
   ⚠️ Só vale no recado do CHECKLIST: um recado de pessoa que comece com ✓ não
   é placar de etapa, e pintá-lo seria inventar significado. */
const linhas = computed(() => String(props.recado.texto || '').split('\n'))

const doChecklist = computed(
  () => /^\[checklist\]/.test(props.recado.texto || ''))

function classeDaLinha(linha) {
  if (!doChecklist.value) return null
  const t = String(linha || '').trimStart()
  if (t.startsWith('✓')) return 'recado__linha--feito'
  if (t.startsWith('✗')) return 'recado__linha--falta'
  return null
}

/* 🔵 11/11, pedido dele: *"Se excluírem, aparecerá como 'Observação excluida' e
   log's"* · *"somente owner pode visualizar o exlcuido, com botão, como no chat
   interno"* · e a autoria fica: *"é um dos objetivos, rastreabilidade"*. */
const apagada = computed(() => !!props.recado.apagada_em)

/* 🚨 O OWNER REVELA; OS OUTROS NÃO TÊM O QUE REVELAR. O `texto` vem nulo do
   servidor para quem não é owner, então a condição é dupla de propósito: nem a
   tela oferece o gesto, nem haveria conteúdo se oferecesse. */
const podeRevelar = computed(
  () => apagada.value && props.souOwner && !!props.recado.texto)

const original = ref(false)

function tamanho(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/* 🚨 O ANEXO VEM POR `fetch` E VIRA `blob:`, nunca por `href`. Ver o
   comentario no `template`. */
const baixando = ref(null)
const erroDoAnexo = ref('')

async function baixar(anexo) {
  baixando.value = anexo.id
  erroDoAnexo.value = ''
  let url = null
  try {
    const blob = await pedirBlob(`/api/paineis/operacao/anexo/${anexo.id}`)
    url = URL.createObjectURL(blob)
    /* ⚠️ `download` com o nome ORIGINAL: sem ele o navegador salvaria o
       arquivo com o nome do `blob:`, que e um UUID. */
    const l = document.createElement('a')
    l.href = url
    l.download = anexo.nome_original || 'anexo'
    l.rel = 'noopener'
    document.body.appendChild(l)
    l.click()
    l.remove()
  } catch (e) {
    /* 🚨 A FALHA E DITA. Antes o 401 era silencioso: o clique abria uma aba
       com a mensagem de erro da API, ou nada. */
    erroDoAnexo.value = e?.message || 'Nao consegui baixar o anexo.'
  } finally {
    baixando.value = null
    /* ⚠️ Solta o `blob:` depois do clique -- cada download reservaria memoria
       para sempre. O atraso existe porque revogar antes do navegador comecar a
       baixar cancela o download. */
    if (url) setTimeout(() => URL.revokeObjectURL(url), 10000)
  }
}
</script>

<template>
  <li class="recado"
      :class="{ 'recado--sistema': doSistema, 'recado--apagada': apagada }">
    <div class="recado__balao">
      <!-- O recado APAGADO: a frase no lugar do conteúdo. -->
      <p v-if="apagada && !original" class="recado__apagada">
        <i class="bi bi-slash-circle" aria-hidden="true"></i>
        Observação excluída
        <button v-if="podeRevelar" type="button" class="recado__revelar"
                @click="original = true">ver o que dizia</button>
      </p>

      <template v-else>
        <p v-if="apagada" class="recado__apagada">
          excluída ·
          <button type="button" class="recado__revelar"
                  @click="original = false">esconder</button>
        </p>
        <p v-for="(linha, i) in linhas" :key="i"
           class="recado__linha" :class="classeDaLinha(linha)">{{ linha }}</p>
      </template>

      <p v-if="erroDoAnexo" class="recado__erro" role="alert">{{ erroDoAnexo }}</p>

      <ul v-if="!apagada && recado.anexos && recado.anexos.length"
          class="recado__anexos">
        <li v-for="a in recado.anexos" :key="a.id">
          <!-- ⚠️ O ID, nunca o caminho de disco. E abre em outra aba: baixar
               nao pode tirar quem opera do painel.
               🚨 MAS NAO POR `<a href>`, e isto era um defeito: a rota e
               protegida por `Bearer` sem nenhum outro caminho, e **navegacao de
               link nao manda cabecalho `Authorization`** -- todo clique era
               **401**. O arquivo subia e nunca voltava.
               ⚠️ Ninguem notou porque `os_observacao_arquivo` tinha ZERO linhas:
               o furo estava no caminho de volta, que nunca foi percorrido.
               🔵 O conserto reusa a `pedirBlob` do `api/cliente.js`, que existe
               desde 27/08 pelo MESMO motivo -- o `<img src>` da midia tambem
               voltava 401, *"e o atendente veria um icone quebrado sem
               explicacao"*. -->
          <button type="button" class="recado__anexo" :disabled="baixando === a.id"
                  @click="baixar(a)">
            <i class="bi bi-paperclip" aria-hidden="true"></i>
            {{ a.nome_original }}
          </button>
          <span class="apagado pequeno">{{ tamanho(a.bytes) }}</span>
        </li>
      </ul>
    </div>

    <p class="recado__pe apagado pequeno">
      <span v-if="doSistema">registrado pelo sistema</span>
      <span v-else>{{ recado.quem || 'sem autor' }}</span>
      <span>· {{ quando(recado.em) }}</span>

      <!-- 🔵 A AUTORIA DO APAGAR FICA VISÍVEL PARA TODOS, e é o objetivo que
           ele nomeou: *"deve ter disponivel exibição da autoria sim, é um dos
           objetivos, rastreabilidade"*. O que some é o conteúdo, não o rastro:
           quem escreveu, quando, quem apagou e quando continuam na tela. -->
      <span v-if="apagada" class="recado__marca">
        · excluída por {{ recado.apagada_por_nome || 'sem autor' }}
        em {{ quando(recado.apagada_em) }}
      </span>

      <!-- 🚨 QUALQUER PESSOA COM O PAINEL APAGA, decisão dele (11/11), e SEM
           janela de tempo -- diferente do chat interno, onde só o autor apaga e
           só por 48 h. ⚠️ Não aparece no recado do SISTEMA: aquele texto é o
           log (checklist, prioridade, rastreio), e apagar log é apagar a
           prova. -->
      <button v-if="!apagada && !doSistema && podeApagar" type="button"
              class="recado__revelar" title="Excluir esta observação"
              @click="emit('apagar', recado)">excluir</button>
    </p>
  </li>
</template>

<style scoped>
.recado { list-style: none; margin: 0 0 var(--e-3); }

/* 🚨 ESTE BALAO TINHA ESCAPADO DO SISTEMA, e era a causa do *"sem
   tabulacao"* que ele viu: usava `var(--fundo-2)` e `var(--raio)` -- e
   **nenhum dos dois existe**. Os dois caiam no valor de emergencia, entao o
   balao nao tinha superficie de verdade nem raio de verdade: uma lavagem de
   cinza sobre o fundo, sem borda e sem forma.
   ⚠️ E e EXATAMENTE o defeito que o `tokens.css` ja documenta sobre o balao
   da Caixa, em 27/08: *"ate 27/08 ele usava `var(--raio, 12px)` -- token que
   nao existe, entao caia no valor de emergencia"*. Eu repeti num componente
   novo o erro que a casa tinha escrito.
   🔵 Os tokens certos existem desde 27/08 e sao destes: `--conversa-balao`,
   `--conversa-raio` e `--conversa-bico`. */
.recado__balao {
  background: var(--conversa-balao);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--conversa-raio);
  box-shadow: var(--sombra-1);
  padding: var(--e-2) var(--e-3);
  /* ⚠️ O recado pode ter linha longa (o checklist tem). Quebrar é melhor que
     rolar na horizontal dentro do modal. */
  overflow-wrap: anywhere;
}

/* 🚨 O recado do sistema é visivelmente outro: barra na lateral E a frase
   "registrado pelo sistema" no pé. Cor sozinha não é portador. */
/* 🚨 VERDE E VERMELHO COM O SINAL DO LADO -- ver o comentário do
   `classeDaLinha`. ⚠️ Os tokens da casa, nunca cor crua: cor crua aqui
   ficaria errada no tema escuro. */
/* O balão apagado: itálico e sublinhado pontilhado, molde exato do
   `.balao__apagada` do chat interno -- os dois estados têm de parecer o mesmo
   estado, porque são. */
.recado__apagada {
  margin: 0; font-style: italic; color: var(--texto-apagado);
  display: flex; align-items: center; gap: 4px; flex-wrap: wrap;
}
.recado__revelar {
  background: none; border: 0; padding: 0; font: inherit; color: inherit;
  cursor: pointer; text-decoration: underline dotted; text-underline-offset: 2px;
}
.recado__revelar:hover { text-decoration: underline; }
.recado__marca { color: var(--texto-apagado); }

.recado__linha--feito { color: var(--ok-texto, #15803D); }
.recado__linha--falta { color: var(--erro, #B91C1C); }

.recado--sistema .recado__balao {
  border-left: 3px solid var(--acento, #1B75BB);
  background: transparent;
}

.recado__linha { margin: 0; }
.recado__linha:empty { height: .5em; }

.recado__anexos {
  list-style: none;
  margin: var(--e-2) 0 0;
  padding: 0;
  display: grid;
  gap: var(--e-1);
}
.recado__anexos li { display: flex; align-items: center; gap: var(--e-2); }

/* 🚨 VIROU `<button>` e TEM DE PARECER O LINK QUE ERA: o gesto nao mudou para
   quem opera -- clicar no nome do arquivo baixa. O que mudou e que agora
   funciona (o `<a href>` levava 401, porque navegacao de link nao manda
   `Authorization`).
   ⚠️ `font: inherit` e o que impede o botao de herdar o visual de botao do
   tema; `text-align: left` e para nome comprido nao centralizar. */
.recado__anexo {
  display: inline-flex; align-items: center; gap: var(--e-1);
  min-height: var(--altura-toque);
  padding: 0;
  border: 0; background: none;
  font: inherit; text-align: left;
  color: var(--acento); text-decoration: underline;
  cursor: pointer;
}
.recado__anexo:hover:not(:disabled) { color: var(--acento-hover); }
/* ⚠️ Enquanto baixa, o botao diz que esta ocupado -- dois cliques seriam duas
   idas ao servidor pelo mesmo arquivo. */
.recado__anexo:disabled { color: var(--texto-fraco); cursor: progress; text-decoration: none; }

/* 🚨 A FALHA DO ANEXO E DITA. Antes o 401 era silencioso: o clique abria uma
   aba com a mensagem crua da API, ou nada. */
.recado__erro {
  margin: var(--e-1) 0 0;
  font-size: var(--txt-sm);
  color: var(--erro);
}

.recado__pe { margin: var(--e-1) 0 0; display: flex; gap: var(--e-1); }
</style>
