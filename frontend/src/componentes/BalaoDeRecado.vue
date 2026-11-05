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
})

/* `[checklist]` e `[sistema]` são os dois prefixos que o servidor usa. */
const doSistema = computed(
  () => /^\[(checklist|sistema)\]/.test(props.recado.texto || ''))

const linhas = computed(() => String(props.recado.texto || '').split('\n'))

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
  <li class="recado" :class="{ 'recado--sistema': doSistema }">
    <div class="recado__balao">
      <p v-for="(linha, i) in linhas" :key="i" class="recado__linha">{{ linha }}</p>

      <p v-if="erroDoAnexo" class="recado__erro" role="alert">{{ erroDoAnexo }}</p>

      <ul v-if="recado.anexos && recado.anexos.length" class="recado__anexos">
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
