<script setup>
/* ============================================================================
   CFG_4.1 — Classificações.
   ----------------------------------------------------------------------------
   🚨 ISTO É O MOTIVO DO FECHAMENTO DA CONVERSA, não o papel do contato. As
   duas coisas têm nome parecido e confundi-las estraga o analytics:

     etiqueta de papel (CAD_1.2) = o que a PESSOA é.   Dura para sempre.
     classificação    (aqui)     = o que a CONVERSA foi. Vale uma conversa.

   ⚠️ "Outro" tem comentário obrigatório de propósito. Sem isso vira o
   vale-tudo onde metade das conversas acaba, e o analytics morre junto.
   ============================================================================ */
import { ref, onMounted } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'

const itens = ref([])
const carregando = ref(true)
const erro = ref('')
const salvando = ref(false)
const incluirInativas = ref(false)

const editando = ref(null)
const form = ref({ nome: '', exige_comentario: false, ativo: true, ordem: 0 })

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    itens.value = await api.get(`/api/classificacoes?incluir_inativas=${incluirInativas.value}`)
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao ler as classificações.'
  } finally {
    carregando.value = false
  }
}

onMounted(carregar)

function abrirNova() {
  editando.value = {}
  form.value = { nome: '', exige_comentario: false, ativo: true, ordem: 0 }
  erro.value = ''
}

function abrirEdicao(item) {
  editando.value = item
  form.value = { ...item }
  erro.value = ''
}

function fechar() {
  editando.value = null
  erro.value = ''
}

async function salvar() {
  salvando.value = true
  erro.value = ''
  try {
    if (editando.value?.id) await api.put(`/api/classificacoes/${editando.value.id}`, form.value)
    else await api.post('/api/classificacoes', form.value)
    fechar()
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui salvar.'
  } finally {
    salvando.value = false
  }
}
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Classificações</h1>
        <p class="fraco pequeno">
          O motivo com que o atendente <strong>encerra</strong> a conversa. É o
          que responde depois "no que gastamos atendimento".
        </p>
      </div>
      <div class="linha">
        <label class="linha pequeno fraco">
          <input v-model="incluirInativas" type="checkbox" @change="carregar" />
          mostrar inativas
        </label>
        <button class="botao botao--primario" type="button" @click="abrirNova">
          <i class="bi bi-plus-lg" aria-hidden="true"></i> Nova
        </button>
      </div>
    </header>

    <p class="aviso aviso--info">
      <i class="bi bi-info-circle aviso__icone" aria-hidden="true"></i>
      <span>
        Não confundir com a <strong>etiqueta de papel</strong> do contato
        (CAD_1.2): aquela descreve a pessoa e dura para sempre; esta descreve
        uma conversa e vale só para ela.
      </span>
    </p>

    <p v-if="erro && !editando" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>{{ erro }}</span>
    </p>

    <section v-if="editando" class="cartao tela__bloco">
      <header class="cartao__cabecalho">
        <span>{{ editando.id ? `Editando ${editando.nome}` : 'Nova classificação' }}</span>
      </header>
      <div class="cartao__corpo pilha">
        <label class="campo">
          <span class="campo__rotulo">Nome</span>
          <input v-model="form.nome" class="campo__entrada" maxlength="80" />
        </label>

        <label class="campo">
          <span class="campo__rotulo">Ordem</span>
          <input v-model.number="form.ordem" class="campo__entrada" type="number" />
          <span class="campo__ajuda">Menor aparece primeiro. 99 é o fim da lista.</span>
        </label>

        <label class="linha">
          <input v-model="form.exige_comentario" type="checkbox" />
          <span>Exige comentário do atendente</span>
        </label>

        <label v-if="editando.id" class="linha">
          <input v-model="form.ativo" type="checkbox" />
          <span>Ativa</span>
        </label>

        <p v-if="erro" class="aviso aviso--erro" role="alert">
          <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
          <span>{{ erro }}</span>
        </p>

        <div class="linha">
          <button class="botao botao--primario" type="button" :disabled="salvando" @click="salvar">
            <span v-if="salvando" class="girando"></span>
            {{ salvando ? 'Salvando…' : 'Salvar' }}
          </button>
          <button class="botao botao--fantasma" type="button" @click="fechar">Cancelar</button>
        </div>
      </div>
    </section>

    <p v-if="carregando" class="linha fraco">
      <span class="girando"></span> Lendo…
    </p>

    <div v-else-if="!itens.length" class="vazio">
      <i class="bi bi-tags vazio__icone" aria-hidden="true"></i>
      <p class="vazio__titulo">Nenhuma classificação</p>
      <p>Sem nenhuma ativa, o atendente não consegue encerrar conversa.</p>
    </div>

    <section v-else class="cartao tela__bloco">
      <div class="tabela--rolavel">
        <table class="tabela">
          <thead>
            <tr>
              <th>Ordem</th>
              <th>Nome</th>
              <th>Comentário</th>
              <th>Situação</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in itens" :key="c.id" :class="{ 'linha--inativa': !c.ativo }">
              <td class="mono fraco">{{ c.ordem }}</td>
              <td><strong>{{ c.nome }}</strong></td>
              <td>
                <span v-if="c.exige_comentario" class="chip chip--acento">obrigatório</span>
                <span v-else class="fraco pequeno">—</span>
              </td>
              <td>
                <span v-if="c.ativo" class="chip chip--ok">ativa</span>
                <span v-else class="chip">inativa</span>
              </td>
              <td>
                <button class="botao botao--pequeno botao--contorno" type="button" @click="abrirEdicao(c)">
                  Editar
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <p class="apagado pequeno">
      A última classificação ativa não pode ser desativada: classificar é
      obrigatório para fechar conversa, e sem nenhuma ninguém encerraria nada.
    </p>
  </div>
</template>

<style scoped>
.tela { max-width: 900px; }

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

.linha--inativa td { opacity: .6; }
</style>
