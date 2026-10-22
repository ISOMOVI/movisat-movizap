<script setup>
/* ============================================================================
   A página pública do formulário — `forms.movisat.com.br/f/<slug>`
   ----------------------------------------------------------------------------
   🚨 ESTA PÁGINA NÃO É O PAINEL, e é um bundle à parte de propósito. O bundle
   do painel publica `sourcemap: true`: uma rota pública dentro dele faria
   qualquer anônimo baixar o painel inteiro com o código-fonte. A pergunta foi
   dele (*"qual a mais segura para os links que terão acesso externos"*).

   🚨 QUEM RECUSA É O SERVIDOR. O obrigatório, a opção de lista, o tipo do
   arquivo, o tempo mínimo e a conta de somar são conferidos lá -- aqui o que
   existe é a mensagem que a pessoa lê. No Bitrix era o contrário: toda a
   validação no navegador, e um POST cru criou registro em 22/10.

   ⚠️ A ISCA É INVISÍVEL PARA GENTE E VISÍVEL PARA ROBÔ: campo fora da tela,
   sem rótulo e com `tabindex="-1"`. Preenchido, o servidor descarta o envio
   em silêncio -- e responde o mesmo "recebemos" de sempre, porque robô que
   toma erro aprende a tentar de outro jeito.

   ⚠️ SEM `autocomplete="off"`: o cliente que preenche a ficha cadastral no
   celular merece o preenchimento do próprio navegador.
   ============================================================================ */
import { onMounted, reactive, ref } from 'vue'

import CamposDoFormulario from '../src/componentes/CamposDoFormulario.vue'

const slug = (window.location.pathname.split('/f/')[1] || '').split(/[?#/]/)[0]

const def = ref(null)
const valores = reactive({})
const anexos = reactive({})
const erro = ref('')
const naoExiste = ref(false)
const enviando = ref(false)
const pronto = ref(false)
const desafio = ref(null)
const resposta = ref('')

async function carregar() {
  try {
    const r = await fetch(`/api/publico/formulario/${encodeURIComponent(slug)}`)
    if (r.status === 404) { naoExiste.value = true; return }
    if (!r.ok) throw new Error('falha')
    def.value = await r.json()
    desafio.value = def.value.desafio
    document.title = def.value.titulo || 'Formulário'
  } catch {
    erro.value = 'Não consegui abrir o formulário agora. Tente de novo em instantes.'
  }
}

function guardarArquivo(nome, arquivos) {
  anexos[nome] = [...(arquivos || [])]
}

async function enviar() {
  erro.value = ''
  enviando.value = true
  try {
    const corpo = new FormData()
    corpo.append('valores', JSON.stringify(valores))
    corpo.append('abertura', def.value.abertura)
    corpo.append('isca', document.getElementById('isca')?.value || '')
    if (desafio.value) {
      corpo.append('desafio_token', desafio.value.token)
      corpo.append('desafio_resposta', resposta.value)
    }
    /* Os anexos vão em duas listas paralelas: multipart com nome de campo
       dinâmico não dá para declarar do outro lado. O servidor confere o par. */
    for (const [campo, arquivos] of Object.entries(anexos)) {
      for (const arquivo of arquivos) {
        corpo.append('campos', campo)
        corpo.append('arquivos', arquivo)
      }
    }
    const r = await fetch(`/api/publico/formulario/${encodeURIComponent(slug)}`,
                          { method: 'POST', body: corpo })
    const dados = await r.json().catch(() => ({}))
    if (!r.ok) {
      erro.value = dados.detail || 'Não consegui enviar. Confira os dados.'
      /* Conta errada ou expirada: pede outra, senão a pessoa fica presa na
         mesma pergunta. */
      if (desafio.value) {
        const nova = await fetch('/api/publico/desafio').then((x) => x.json())
        desafio.value = nova
        resposta.value = ''
      }
      return
    }
    pronto.value = true
  } catch {
    erro.value = 'Não consegui enviar agora. Tente de novo em instantes.'
  } finally {
    enviando.value = false
  }
}

onMounted(carregar)
</script>

<template>
  <main class="pagina">
    <div v-if="naoExiste" class="cartao">
      <h1 class="titulo">Formulário não encontrado</h1>
      <!-- 🚨 A MESMA FRASE para "não existe" e "está desligado": distinguir
           os dois contaria ao mundo quais formulários a casa tem. -->
      <p class="apoio">
        Confira o link. Se ele veio de alguém da Movisat, peça o endereço de novo.
      </p>
    </div>

    <div v-else-if="pronto" class="cartao">
      <h1 class="titulo">Recebemos sua solicitação</h1>
      <p class="apoio">Em breve entraremos em contato.</p>
    </div>

    <form v-else-if="def" class="cartao" @submit.prevent="enviar">
      <h1 class="titulo">{{ def.titulo }}</h1>
      <p v-if="def.descricao" class="apoio">{{ def.descricao }}</p>

      <CamposDoFormulario
        :campos="def.campos"
        :regras="def.regras"
        :valores="valores"
        :erro="erro"
        @arquivo="guardarArquivo"
      />

      <label v-if="desafio" class="campo-desafio">
        <span>{{ desafio.pergunta }}</span>
        <input v-model="resposta" class="entrada" inputmode="numeric" required />
      </label>

      <!-- a isca -->
      <input id="isca" class="isca" tabindex="-1" aria-hidden="true" autocomplete="off" />

      <button class="botao" type="submit" :disabled="enviando">
        {{ enviando ? 'Enviando…' : (def.botao || 'Enviar') }}
      </button>
    </form>

    <p v-else-if="erro" class="cartao apoio">{{ erro }}</p>
  </main>
</template>

<style scoped>
.pagina {
  min-height: 100vh;
  padding: var(--e-5) var(--e-4);
  background: var(--fundo);
  display: flex;
  justify-content: center;
  align-items: flex-start;
}
.cartao {
  width: 100%;
  max-width: 680px;
  display: flex;
  flex-direction: column;
  gap: var(--e-4);
  padding: var(--e-5);
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
}
.titulo { margin: 0; font-size: var(--txt-xl); color: var(--texto); }
.apoio { margin: 0; color: var(--texto-fraco); line-height: var(--entrelinha); }

.campo-desafio { display: flex; flex-direction: column; gap: var(--e-2); }
.entrada {
  min-height: var(--altura-toque);
  padding: var(--e-2) var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
  font-size: var(--txt-campo);
  background: var(--superficie);
  color: var(--texto);
}
.botao {
  min-height: var(--altura-toque);
  padding: var(--e-2) var(--e-5);
  border: 0;
  border-radius: var(--r-md);
  background: var(--acento);
  color: var(--acento-texto);
  font-size: var(--txt-md);
  font-weight: var(--peso-medio);
  cursor: pointer;
}
.botao:disabled { background: var(--borda-forte); cursor: progress; }

/* A isca sai da tela sem `display:none` -- robô ignora campo oculto por
   display, mas preenche o que existe no DOM. */
.isca { position: absolute; left: -9999px; width: 1px; height: 1px; opacity: 0; }
</style>
