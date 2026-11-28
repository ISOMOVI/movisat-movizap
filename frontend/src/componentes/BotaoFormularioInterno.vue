<script setup>
/* ============================================================================
   O botão "Solicitar" do compositor do chat interno (27/11)
   ----------------------------------------------------------------------------
   🔵 Ele, 27/11: *"sera somente interno, talvez um botao de acao no chat
   interno? para forms internos igual no chat com clientes"*.

   🚨 **O QUE JÁ EXISTIA NÃO ERA ISTO.** O tipo `formulario` das mensagens
   rápidas é validado como URL (*"O formulário é um link: comece com
   https://"*) e só cola um endereço no campo de texto -- não abre formulário
   nenhum dentro do MoviZap. Este componente é a "lógica a montar" que ele
   mesmo previu.

   🚨 **COMPONENTE NOVO, E NÃO UMA MUDANÇA NO `BotaoFormulario.vue`.** Aquele
   depende de `conversaId` e das rotas de conversa (`ATD_1.2`); o chat interno
   não tem conversa, tem sala. Mexer nele mudaria a Caixa de entrada.

   🚨 **ESTE BOTÃO NÃO MANDA MENSAGEM NENHUMA** -- a regra está escrita por
   extenso no `BotaoFormulario.vue` da Caixa e vale igual aqui. Depois do
   envio ele emite `inserir`, e **quem manda é a pessoa**.

   ⚠️ O menu segue o molde do `BotaoMensagensRapidas`: busca no topo, teclado
   (setas, Enter, Esc), lista buscada do servidor **ao abrir** -- quem acabou
   de ligar um formulário o vê sem recarregar a tela.
   ============================================================================ */
import { computed, nextTick, onUnmounted, reactive, ref } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'
import CamposDoFormulario from './CamposDoFormulario.vue'

const emit = defineEmits(['inserir'])

const aberto = ref(false)
const carregando = ref(false)
const erro = ref('')
const lista = ref([])
const busca = ref('')
const aqui = ref(0)
const raiz = ref(null)
const campoBusca = ref(null)

/* O modal */
const escolhido = ref(null)        // a definição, como a rota a devolve
const valores = reactive({})
const anexos = reactive({})
const erroDoEnvio = ref('')
const enviando = ref(false)
const feito = ref(null)            // { card_id, painel, titulo }

const itens = computed(() => {
  const termo = busca.value.trim().toLowerCase()
  if (!termo) return lista.value
  return lista.value.filter((f) => (f.titulo || '').toLowerCase().includes(termo)
    || (f.setor || '').toLowerCase().includes(termo))
})

/* 🚨 O SOLICITANTE É O ÚNICO CAMPO TRAVADO, e por nome, não por posição: a
   definição pode ganhar campo e a ordem mudar. */
const travados = computed(
  () => (escolhido.value?.campos || [])
    .filter((c) => c.nome === 'CONTACT_NAME')
    .map((c) => c.nome))

async function abrir() {
  if (aberto.value) { fechar(); return }
  aberto.value = true
  carregando.value = true
  erro.value = ''
  busca.value = ''
  aqui.value = 0
  document.addEventListener('mousedown', foraDoMenu)
  try {
    lista.value = await api.get('/api/interno/formularios')
  } catch (e) {
    erro.value = e instanceof ErroDeApi
      ? e.message
      : 'Não consegui ler os formulários internos.'
  } finally {
    carregando.value = false
    nextTick(() => campoBusca.value?.focus())
  }
}

function fechar() {
  aberto.value = false
  document.removeEventListener('mousedown', foraDoMenu)
}
function foraDoMenu(evento) {
  if (raiz.value && !raiz.value.contains(evento.target)) fechar()
}
onUnmounted(() => document.removeEventListener('mousedown', foraDoMenu))

async function escolher(f) {
  fechar()
  erro.value = ''
  erroDoEnvio.value = ''
  feito.value = null
  for (const k of Object.keys(valores)) delete valores[k]
  for (const k of Object.keys(anexos)) delete anexos[k]
  try {
    const d = await api.get(`/api/interno/formulario/${encodeURIComponent(f.slug)}`)
    escolhido.value = d
    /* ⚠️ A rota manda o nome já preenchido para a tela MOSTRAR quem pede.
       🚨 Mas ela injeta o nome da sessão OUTRA VEZ no envio, antes do
       `validar` -- este valor é conveniência, nunca a fonte. */
    if (d.solicitante) valores.CONTACT_NAME = d.solicitante
  } catch (e) {
    erro.value = e instanceof ErroDeApi
      ? e.message
      : 'Não consegui abrir este formulário.'
  }
}

function fecharModal() {
  escolhido.value = null
  erroDoEnvio.value = ''
  feito.value = null
}

function guardarArquivo(nome, arquivos) {
  anexos[nome] = [...(arquivos || [])]
}

/* 🚨 NÃO passa pelo `api.post`, que serializa JSON. Anexo vai por `FormData`,
   e aí o navegador monta o `Content-Type` com o boundary sozinho -- definir o
   cabeçalho na mão quebra o upload EM SILÊNCIO, com o servidor recebendo corpo
   vazio. É o mesmo cuidado do `subirArquivo` do `ChatInterno`. */
async function enviar() {
  if (enviando.value || !escolhido.value) return
  enviando.value = true
  erroDoEnvio.value = ''
  try {
    const corpo = new FormData()
    corpo.append('valores', JSON.stringify(valores))
    /* Os anexos vão em duas listas paralelas: multipart com nome de campo
       dinâmico não dá para declarar do outro lado. O servidor confere o par. */
    for (const [campo, arquivos] of Object.entries(anexos)) {
      for (const arquivo of arquivos) {
        corpo.append('campos', campo)
        corpo.append('arquivos', arquivo)
      }
    }
    const r = await fetch(
      `/api/interno/formulario/${encodeURIComponent(escolhido.value.slug)}`,
      {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('movizap.token')}` },
        body: corpo,
      })
    const dados = await r.json().catch(() => ({}))
    if (!r.ok) {
      /* 🚨 O ERRO FICA NA TELA e o modal NÃO fecha: quem preencheu não perde o
         que escreveu, e a frase que o servidor devolve é a que a pessoa lê. */
      erroDoEnvio.value = dados.detail || 'Não consegui enviar. Confira os dados.'
      return
    }
    feito.value = {
      card_id: dados.card_id,
      painel: dados.painel,
      titulo: escolhido.value.titulo,
    }
    /* 🚨 A LINHA VAI PARA O CAMPO, não para a sala. */
    emit('inserir', `Abri uma ${escolhido.value.titulo}`
      + (dados.card_id ? ` (card ${dados.card_id})` : '') + '.')
  } catch {
    erroDoEnvio.value = 'Sem resposta do servidor. Verifique a conexão.'
  } finally {
    enviando.value = false
  }
}

function teclado(evento) {
  if (evento.key === 'Escape') { evento.preventDefault(); fechar(); return }
  if (!itens.value.length) return
  if (evento.key === 'ArrowDown') {
    evento.preventDefault(); aqui.value = (aqui.value + 1) % itens.value.length
  }
  if (evento.key === 'ArrowUp') {
    evento.preventDefault()
    aqui.value = (aqui.value - 1 + itens.value.length) % itens.value.length
  }
  if (evento.key === 'Enter') { evento.preventDefault(); escolher(itens.value[aqui.value]) }
}

/* O nome do painel por extenso, para a tela não dizer o slug cru. ⚠️ Fallback
   no próprio slug: painel novo que eu não previ aqui aparece como ele é, e
   nunca em branco. */
const PAINEIS = {
  compras: 'Compras', financeiro: 'Financeiro', contratual: 'Contratual',
  pos_venda: 'Pós-venda', operacao: 'Operação',
}
const painelPorExtenso = computed(
  () => PAINEIS[feito.value?.painel] || feito.value?.painel || '')
</script>

<template>
  <span ref="raiz" class="bfi">
    <!-- 🚨 BOTÃO COM RÓTULO, não só ícone. `title` não é rótulo: o balão do
         navegador demora cerca de um segundo e não existe em toque. Foi esse o
         erro de 25/08 que escondeu o "Criar grupo" desta mesma tela. -->
    <button class="botao botao--contorno" type="button"
            :aria-expanded="aberto" aria-haspopup="dialog"
            @click="abrir">
      <i class="bi bi-clipboard-plus" aria-hidden="true"></i>
      Solicitar
    </button>

    <div v-if="aberto" class="bfi__menu" role="dialog"
         aria-label="Formulários internos" @keydown="teclado">
      <p class="bfi__titulo">Formulários internos</p>
      <input ref="campoBusca" v-model="busca" class="campo__entrada bfi__busca"
             type="search" placeholder="Procurar pelo nome"
             aria-label="Procurar formulário interno" @input="aqui = 0" />

      <p v-if="carregando" class="linha pequeno fraco">
        <span class="girando"></span> Lendo…
      </p>
      <p v-else-if="erro" class="aviso aviso--erro pequeno">{{ erro }}</p>
      <ul v-else-if="itens.length" class="bfi__lista" role="listbox">
        <li v-for="(f, i) in itens" :key="f.slug">
          <button type="button" class="bfi__item"
                  :class="{ 'bfi__item--aqui': i === aqui }"
                  :aria-selected="i === aqui"
                  @mouseenter="aqui = i" @click="escolher(f)">
            <strong>{{ f.titulo }}</strong>
            <small class="apagado">{{ f.setor }}</small>
          </button>
        </li>
      </ul>
      <!-- ⚠️ O VAZIO É DITO, e com os dois motivos separados: formulário
           interno desligado é o caso de hoje, e menu em branco pareceria
           defeito da tela. -->
      <p v-else class="bfi__vazio pequeno apagado">
        {{ busca
          ? 'Nada com esse nome.'
          : 'Nenhum formulário interno ligado ainda.' }}
      </p>
    </div>

    <!-- O modal usa as classes GLOBAIS de `estilo/componentes.css`
         (`.modal`, `.modal__caixa`, `.modal__titulo`, `.modal__texto`,
         `.modal__acoes`), como o de editar mensagem do próprio ChatInterno.
         🚨 O `.modal__caixa` global impõe 420px, e formulário não cabe nisso:
         o teto próprio está declarado abaixo, porque teto não se vence por
         especificidade. -->
    <div v-if="escolhido" class="modal" @click.self="fecharModal">
      <div class="modal__caixa bfi__caixa" role="dialog" aria-modal="true"
           :aria-label="escolhido.titulo">
        <p class="modal__titulo">{{ escolhido.titulo }}</p>
        <p v-if="escolhido.descricao" class="modal__texto pequeno">
          {{ escolhido.descricao }}</p>

        <template v-if="!feito">
          <CamposDoFormulario
            :campos="escolhido.campos"
            :regras="escolhido.regras"
            :valores="valores"
            :travados="travados"
            :formato="escolhido.formato"
            :busca-cliente="escolhido.busca_cliente"
            @arquivo="guardarArquivo" />

          <p v-if="erroDoEnvio" class="aviso aviso--erro pequeno">
            {{ erroDoEnvio }}</p>

          <div class="modal__acoes">
            <button class="botao botao--contorno" type="button"
                    @click="fecharModal">Cancelar</button>
            <button class="botao botao--primario bfi__enviar" type="button"
                    :disabled="enviando" @click="enviar">
              <span v-if="enviando" class="girando"></span>
              {{ enviando ? 'Enviando…' : (escolhido.botao || 'Enviar') }}
            </button>
          </div>
        </template>

        <!-- 🚨 DIZ QUAL CARD NASCEU E EM QUE PAINEL. Sem isto a pessoa envia e
             não tem como saber se a sugestão chegou a algum lugar. -->
        <template v-else>
          <p class="bfi__feito">
            <i class="bi bi-check-circle" aria-hidden="true"></i>
            Enviado.
            <template v-if="feito.card_id">
              Nasceu o card {{ feito.card_id }}<template v-if="painelPorExtenso">
              no painel {{ painelPorExtenso }}</template>.
            </template>
            <template v-else>
              A solicitação foi gravada.
            </template>
          </p>
          <p class="modal__texto pequeno">
            A linha foi para o campo de escrever — mande se quiser avisar a sala.
          </p>
          <div class="modal__acoes">
            <button class="botao botao--primario" type="button"
                    @click="fecharModal">Fechar</button>
          </div>
        </template>
      </div>
    </div>
  </span>
</template>

<style scoped>
.bfi { position: relative; display: inline-flex; align-items: center; }

.bfi__menu {
  position: absolute;
  bottom: calc(100% + var(--e-2));
  left: 0;
  z-index: var(--z-flutuante);
  width: min(360px, calc(100vw - 2 * var(--e-4)));
  display: flex;
  flex-direction: column;
  gap: var(--e-2);
  padding: var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-lg);
  background: var(--superficie);
  box-shadow: var(--sombra-2);
}
/* No celular o menu passava da borda direita -- o botão não fica no canto
   esquerdo da tela. Vira folha fixa, igual à do BotaoMensagensRapidas. */
@media (max-width: 640px) {
  .bfi__menu {
    position: fixed;
    left: var(--e-4);
    right: var(--e-4);
    bottom: calc(var(--altura-barra) + var(--e-4));
    width: auto;
    max-height: 70vh;
    overflow-y: auto;
  }
}
.bfi__titulo { margin: 0; font-weight: var(--peso-forte); }
.bfi__busca { margin: 0; }
.bfi__lista {
  list-style: none; margin: 0; padding: 0;
  max-height: 260px; overflow-y: auto;
}
.bfi__item {
  display: flex; flex-direction: column; align-items: flex-start; gap: 2px;
  width: 100%; padding: var(--e-2); border: 0; border-radius: var(--r-md);
  background: transparent; color: inherit; font: inherit;
  text-align: left; cursor: pointer;
}
.bfi__item--aqui { background: var(--acento-suave); }
.bfi__vazio { margin: 0; }

/* 🚨 O TETO PRÓPRIO DO MODAL. O `.modal__caixa` global impõe `max-width:
   420px`, e um formulário com área de texto não cabe nisso. Teto não se vence
   por especificidade: declara-se outro. */
.bfi__caixa {
  max-width: min(560px, calc(100vw - 2 * var(--e-4)));
  max-height: calc(100vh - 2 * var(--e-5));
  overflow-y: auto;
}
/* 🚨 O ROTULO TROCA AO CLICAR -- de *\"Enviar sugestao\"* para
   *\"Enviando...\"*, que e mais curto. Sem piso de largura o botao ENCOLHE
   debaixo do dedo no instante do clique, e o que estava sob o cursor sai de
   baixo dele. ⚠️ `ch` e nao `px`: a medida acompanha a fonte. */
.bfi__enviar { min-width: 14ch; }
.bfi__feito { margin: 0; color: var(--ok); }
</style>
