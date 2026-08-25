<script setup>
/* ============================================================================
   CFG_5.1 — Automação por tipo de contato
   ----------------------------------------------------------------------------
   Pedido do usuário em 25/08: um interruptor por tipo de contato, para a
   mensagem que chega ser filtrada antes de gastar atendimento.

   🚨 ESTA TELA NÃO PROMETE IA. Medido em 25/08: `canal.ia_ligada` é lido em
   quatro lugares e nenhum age sobre ele -- não há motor no painel. O
   interruptor de IA aparece TRAVADO, com o motivo escrito. `docs/09`, item 4:
   configuração não afirma o que o código não faz. Botão que não faz nada é
   pior que botão ausente, porque alguém confia nele.

   ⚠️ Cada linha mostra QUANTOS contatos ela alcança. Sem esse número, ligar
   "Cliente" parece inofensivo e atinge 1.750 pessoas.
   ============================================================================ */
import { ref, onMounted } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'

const tipos = ref([])
const iaDisponivel = ref(false)
const iaMotivo = ref('')
const carregando = ref(true)
const erro = ref('')
const recado = ref('')
const salvando = ref('')

/* O rascunho do texto vive fora da lista: digitar não pode disparar gravação a
   cada tecla, e a lista é recarregada a cada gravação. */
const rascunho = ref({})

const NOME = {
  cliente: 'Cliente',
  fornecedor: 'Fornecedor',
  parceiro: 'Parceiro',
  tecnico: 'Técnico',
  lead: 'Lead',
  colaborador: 'Colaborador',
  teste: 'Teste',
  sem_identificacao: 'Sem identificação',
  sem_cadastro: 'Sem cadastro',
}

/* 🚨 "SEM CADASTRO" NÃO É UM TIPO DE CONTATO: é a ausência de contato. Fica na
   lista porque é o caso MAIS COMUM -- 64% das conversas em 25/08 -- e é onde
   uma mensagem automática mais ajuda ou mais atrapalha. */
const EXPLICA = {
  sem_cadastro: 'Quem escreve de um número que não está na base. É o caso mais '
    + 'comum: 64% das conversas.',
  sem_identificacao: 'O contato existe na base, mas ninguém marcou o que ele é.',
}

async function carregar() {
  carregando.value = true
  try {
    const r = await api.get('/api/automacao')
    tipos.value = r.tipos || []
    iaDisponivel.value = Boolean(r.ia_disponivel)
    iaMotivo.value = r.ia_motivo || ''
    for (const t of tipos.value) rascunho.value[t.relacao] = t.boas_vindas_texto || ''
    erro.value = ''
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui ler.'
  } finally {
    carregando.value = false
  }
}

async function gravar(tipo, campos) {
  salvando.value = tipo.relacao
  erro.value = ''
  recado.value = ''
  try {
    await api.put(`/api/automacao/${tipo.relacao}`, campos)
    /* 🚨 Relê em vez de confiar no 200: o que vale é o que o banco gravou. */
    await carregar()
    recado.value = `${NOME[tipo.relacao]}: gravado.`
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui gravar.'
    await carregar()
  } finally {
    salvando.value = ''
  }
}

function alternar(tipo) {
  gravar(tipo, {
    boas_vindas_ligado: !tipo.boas_vindas_ligado,
    boas_vindas_texto: rascunho.value[tipo.relacao] || null,
  })
}

function salvarTexto(tipo) {
  if ((rascunho.value[tipo.relacao] || '') === (tipo.boas_vindas_texto || '')) return
  gravar(tipo, { boas_vindas_texto: rascunho.value[tipo.relacao] || null })
}

onMounted(carregar)
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Automação por tipo</h1>
        <p class="fraco pequeno">
          O que roda sozinho quando chega mensagem. Nada aqui nasce ligado.
        </p>
      </div>
      <span class="chip chip--codigo chip--acento">CFG_5.1</span>
    </header>

    <!-- 🚨 O aviso de IA vem ANTES da lista, não escondido no fim: quem abre
         esta tela procurando IA precisa saber logo que ela não existe. -->
    <p v-if="!iaDisponivel" class="aviso aviso--atencao">
      <i class="bi bi-robot aviso__icone" aria-hidden="true"></i>
      <span>
        <strong>IA ainda não.</strong> {{ iaMotivo }}
        O interruptor aparece travado de propósito — botão que não faz nada é
        pior que botão nenhum, porque alguém confia nele.
      </span>
    </p>

    <p v-if="erro" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>{{ erro }}</span>
    </p>
    <p v-if="recado" class="aviso aviso--ok" role="status">
      <i class="bi bi-check-circle aviso__icone" aria-hidden="true"></i>
      <span>{{ recado }}</span>
    </p>

    <p v-if="carregando" class="linha fraco">
      <span class="girando"></span> Lendo…
    </p>

    <section v-for="t in tipos" v-else :key="t.relacao" class="cartao aut">
      <header class="cartao__cabecalho">
        <div>
          <strong>{{ NOME[t.relacao] || t.relacao }}</strong>
          <!-- ⚠️ O ALCANCE. Ligar "Cliente" hoje atinge 1.750 pessoas, e o
               número precisa estar à vista NA HORA de ligar. -->
          <p class="apagado pequeno">
            {{ t.contatos }} contato(s) com este tipo
            <span v-if="EXPLICA[t.relacao]"> · {{ EXPLICA[t.relacao] }}</span>
          </p>
        </div>
        <span v-if="t.boas_vindas_ligado" class="chip chip--ok">ligado</span>
        <span v-else class="chip">desligado</span>
      </header>

      <div class="cartao__corpo pilha">
        <label class="campo">
          <span class="campo__rotulo">Mensagem de boas-vindas</span>
          <textarea
            v-model="rascunho[t.relacao]"
            class="campo__entrada"
            rows="2"
            maxlength="4000"
            placeholder="Olá! Recebemos sua mensagem e já vamos atender."
            @blur="salvarTexto(t)"
          ></textarea>
          <span class="campo__ajuda">
            Enviada <strong>uma vez por conversa</strong>, quando a pessoa
            escreve. Nunca em grupo.
          </span>
        </label>

        <div class="linha linha--quebra">
          <button
            class="botao botao--pequeno"
            :class="t.boas_vindas_ligado ? 'botao--contorno' : 'botao--primario'"
            type="button"
            :disabled="salvando === t.relacao"
            @click="alternar(t)"
          >
            <span v-if="salvando === t.relacao" class="girando"></span>
            <i v-else class="bi" :class="t.boas_vindas_ligado
                 ? 'bi-toggle-on' : 'bi-toggle-off'" aria-hidden="true"></i>
            {{ t.boas_vindas_ligado ? 'Desligar boas-vindas' : 'Ligar boas-vindas' }}
          </button>

          <!-- Travado enquanto não há motor. O `title` diz por quê: interruptor
               cinza sem explicação vira chamado. -->
          <button
            class="botao botao--pequeno botao--fantasma"
            type="button"
            disabled
            :title="iaMotivo"
          >
            <i class="bi bi-robot" aria-hidden="true"></i>
            IA — indisponível
          </button>
        </div>
      </div>
    </section>

    <p class="apagado pequeno">
      A mensagem sai uma vez por conversa: a marca fica gravada na própria
      conversa, então reentrega de webhook não faz o cliente receber duas vezes.
    </p>
  </div>
</template>

<style scoped>
.aut { margin-bottom: var(--e-3); }
.aut .cartao__cabecalho { align-items: flex-start; }
</style>
