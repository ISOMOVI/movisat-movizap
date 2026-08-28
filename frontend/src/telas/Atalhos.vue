<script setup>
/* ============================================================================
   CFG_6.1 — Atalhos de teclado.
   ----------------------------------------------------------------------------
   Pedido dele em 28/08: *"crie nas configurações tela de atalhos e interruptor
   desligado para eles e permita edição por lá também"*.

   🚨 A TELA NASCEU DE UMA PERGUNTA QUE DERRUBOU UM RECURSO MEU. Ele perguntou
   *"quem pediu esses atalhos? ou eles já são nativos do WhatsApp?"* -- e a
   resposta honesta era: ninguém pediu, e não são. `j`/`k` vêm do Gmail (e antes,
   do `vi`), e eu os levei para a Caixa de entrada, que é a tela que ELE
   escolheu entre cinco mockups para parecer o WhatsApp.

   ⚠️ E um deles agia sem perguntar: `a` assumia a conversa na hora, com 380
   conversas sem dono e nove pessoas testando ao mesmo tempo.

   🚨 NASCEM DESLIGADOS. Ausência de preferência = desligado, no banco e aqui.
   Quem nunca abriu esta tela não tem atalho nenhum -- e isso é o recurso, não
   uma limitação.

   🚨 O CATÁLOGO VEM DO BACKEND. A tela não sabe quais atalhos existem: ela
   desenha o que `/api/eu/atalhos` devolver. Escrever a lista aqui criaria duas
   verdades, e a que o operador vê seria a errada.
   ============================================================================ */
import { computed, ref, onMounted } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'

const carregando = ref(true)
const salvando = ref(false)
const erro = ref('')
const recado = ref('')

const ligados = ref(false)
const teclas = ref({})
const catalogo = ref([])
const capturando = ref('')

/* Agrupado por tela, na ordem em que o backend mandou: a pessoa procura pela
   tela em que está, não pelo nome interno da ação. */
const porTela = computed(() => {
  const grupos = []
  for (const item of catalogo.value) {
    let g = grupos.find((x) => x.tela === item.tela)
    if (!g) { g = { tela: item.tela, itens: [] }; grupos.push(g) }
    g.itens.push(item)
  }
  return grupos
})

const perigosos = computed(
  () => catalogo.value.filter((a) => a.perigo).length,
)

async function carregar() {
  carregando.value = true
  try {
    const r = await api.get('/api/eu/atalhos')
    ligados.value = r.ligados
    teclas.value = { ...r.teclas }
    catalogo.value = r.catalogo || []
    erro.value = ''
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui ler os atalhos.'
  } finally {
    carregando.value = false
  }
}

async function alternar() {
  salvando.value = true
  recado.value = ''
  const antes = ligados.value
  try {
    const r = await api.put('/api/eu/atalhos/ligados', { ligados: !antes })
    ligados.value = r.ligados
    recado.value = r.ligados
      ? 'Atalhos ligados para a sua conta.'
      : 'Atalhos desligados. Nenhuma tecla age nas telas.'
  } catch (e) {
    ligados.value = antes
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui salvar.'
  } finally {
    salvando.value = false
  }
}

/* ⚠️ CAPTURA A TECLA, não pede para digitar num campo. Campo de texto aceitaria
   "Enter" escrito por extenso, espaço, duas letras -- e o backend recusaria
   depois. Aqui a pessoa aperta a tecla que quer usar, que é o gesto real. */
function capturar(acao) {
  capturando.value = capturando.value === acao ? '' : acao
  recado.value = ''
}

async function aoApertar(evento, acao) {
  if (capturando.value !== acao) return
  evento.preventDefault()
  if (evento.key === 'Escape') { capturando.value = ''; return }
  const novas = { ...teclas.value, [acao]: evento.key }
  capturando.value = ''
  salvando.value = true
  erro.value = ''
  try {
    const r = await api.put('/api/eu/atalhos/teclas', { teclas: novas })
    teclas.value = { ...r.teclas }
    recado.value = 'Tecla trocada.'
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui salvar.'
  } finally {
    salvando.value = false
  }
}

async function restaurar() {
  salvando.value = true
  erro.value = ''
  try {
    const r = await api.put('/api/eu/atalhos/teclas', { teclas: {} })
    teclas.value = { ...r.teclas }
    recado.value = 'Teclas de volta ao padrão.'
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui restaurar.'
  } finally {
    salvando.value = false
  }
}

onMounted(carregar)
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Atalhos de teclado</h1>
        <AjudaDaTela>
          As teclas valem só para a sua conta e só quando o interruptor está
          ligado. Nenhuma tecla funciona dentro de campo de texto.
        </AjudaDaTela>
      </div>
      <span class="chip" :class="ligados ? 'chip--ok' : ''">
        {{ ligados ? 'ligados' : 'desligados' }}
      </span>
    </header>

    <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>
    <p v-if="recado" class="aviso aviso--ok" role="status">{{ recado }}</p>

    <section class="cartao tela__bloco">
      <div class="cartao__corpo pilha">
        <label class="interruptor">
          <input type="checkbox" :checked="ligados" :disabled="salvando"
                 @change="alternar" />
          <span><strong>Usar atalhos de teclado</strong></span>
        </label>
        <p class="apagado pequeno">
          Nascem desligados. Ligar vale só para você.
        </p>
        <!-- ⚠️ O AVISO VEM ANTES DE LIGAR, não depois de a pessoa descobrir
             apertando. O backend marca quais ações mudam estado sem perguntar. -->
        <p v-if="!ligados && perigosos" class="aviso aviso--atencao">
          <i class="bi bi-exclamation-triangle aviso__icone" aria-hidden="true"></i>
          <span>
            {{ perigosos }} destes atalhos <strong>agem sem perguntar</strong>.
            Estão marcados na lista abaixo.
          </span>
        </p>
      </div>
    </section>

    <p v-if="carregando" class="linha fraco"><span class="girando"></span> Lendo…</p>

    <section v-for="g in porTela" :key="g.tela" class="cartao tela__bloco">
      <header class="cartao__cabecalho">{{ g.tela }}</header>
      <div class="cartao__corpo">
        <ul class="atalhos">
          <li v-for="a in g.itens" :key="a.acao" class="atalho">
            <div class="atalho__texto">
              <span>{{ a.descricao }}</span>
              <span v-if="a.aviso" class="apagado pequeno">{{ a.aviso }}</span>
            </div>
            <span v-if="a.perigo" class="chip chip--aviso">age direto</span>
            <!-- A tecla é um botão: clicar arma a captura, e a próxima tecla
                 apertada vira o atalho. -->
            <button
              class="botao botao--pequeno botao--contorno atalho__tecla"
              type="button"
              :disabled="salvando"
              :title="capturando === a.acao
                ? 'Aperte a tecla que quer usar — Esc cancela'
                : 'Clique e aperte a tecla que quer usar'"
              @click="capturar(a.acao)"
              @keydown="aoApertar($event, a.acao)"
            >
              {{ capturando === a.acao ? 'aperte a tecla…' : teclas[a.acao] }}
            </button>
          </li>
        </ul>
      </div>
    </section>

    <div v-if="!carregando" class="linha">
      <button class="botao botao--pequeno botao--fantasma" type="button"
              :disabled="salvando" @click="restaurar">
        <i class="bi bi-arrow-counterclockwise" aria-hidden="true"></i>
        Voltar ao padrão
      </button>
    </div>
  </div>
</template>

<style scoped>
.interruptor { display: flex; align-items: center; gap: var(--e-3); cursor: pointer; }
.interruptor input { width: 18px; height: 18px; accent-color: var(--acento); }

.atalhos { list-style: none; margin: 0; padding: 0; }
.atalho {
  display: flex;
  align-items: center;
  gap: var(--e-3);
  padding: var(--e-2) 0;
}
.atalho + .atalho { border-top: var(--borda-fina) solid var(--borda); }
.atalho__texto { display: flex; flex-direction: column; flex: 1 1 auto; min-width: 0; }

/* A tecla tem largura fixa: a coluna alinha e a lista fica lida de cima a
   baixo, não em zigue-zague. */
.atalho__tecla {
  min-width: 7.5rem;
  justify-content: center;
  font-family: var(--fonte-mono, monospace);
}
</style>
