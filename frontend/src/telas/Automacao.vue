<script setup>
/* ============================================================================
   CFG_5.1 — Automação por tipo de contato
   ----------------------------------------------------------------------------
   Pedido do usuário em 25/08: um interruptor por tipo de contato, para a
   mensagem que chega ser filtrada antes de gastar atendimento.

   🚨 ESTA TELA NÃO PROMETE O QUE O CÓDIGO NÃO FAZ, NOS DOIS SENTIDOS. Até
   25/08 o interruptor de IA aparecia TRAVADO porque não havia motor. Em 26/08
   o motor entrou (`movizap/ia.py`) e o interruptor destravou -- mas quem
   decide é a rota, não esta tela: `ia_disponivel` vem do próprio motor e volta
   a `false`, com o motivo, se faltar chave ou versão de prompt publicada.
   `docs/09`, item 4. Botão que não faz nada é pior que botão ausente, porque
   alguém confia nele.

   🚨 LIGAR AQUI NÃO PÕE A IA NO AR. São duas travas separadas de propósito:
   este interruptor é o FILTRO por tipo de contato; quem coloca no ar é
   `canal.ia_ligada`, na CFG_1.1. O aviso abaixo diz isso na tela, porque
   ninguém vai ler este comentário.

   ⚠️ Cada linha mostra QUANTOS contatos ela alcança. Sem esse número, ligar
   "Cliente" parece inofensivo e atinge 1.750 pessoas.
   ============================================================================ */
import { ref, onMounted } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'

const tipos = ref([])
const iaDisponivel = ref(false)
const iaMotivo = ref('')
const iaModelo = ref('')
/* Quantos canais estão com a IA no ar. Sem isso, ligar um tipo aqui parece
   colocar a IA para responder — e não coloca. */
const canaisComIa = ref(0)
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
    iaModelo.value = r.ia_modelo || ''
    for (const t of tipos.value) rascunho.value[t.relacao] = t.boas_vindas_texto || ''
    /* ⚠️ De outra rota, de propósito: o estado do canal é da CFG_1.1, e
       duplicar o campo em `/api/automacao` faria duas verdades sobre a mesma
       coisa. Falha aqui não pode derrubar a tela: sem o número, o aviso some,
       e a tela continua servindo. */
    try {
      const canais = await api.get('/api/canais')
      canaisComIa.value = (canais || []).filter((c) => c.ia_ligada).length
    } catch { canaisComIa.value = 0 }
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

function alternarIa(tipo) {
  gravar(tipo, { ia_ligada: !tipo.ia_ligada })
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
        <AjudaDaTela>O que roda sozinho quando chega mensagem. Nada aqui nasce ligado.</AjudaDaTela>
      </div>
      <span class="chip chip--codigo chip--acento">CFG_5.1</span>
    </header>

    <!-- 🚨 O aviso de IA vem ANTES da lista, não escondido no fim: quem abre
         esta tela procurando IA precisa saber logo em que pé ela está. -->
    <p v-if="!iaDisponivel" class="aviso aviso--atencao">
      <i class="bi bi-robot aviso__icone" aria-hidden="true"></i>
      <span>
        <strong>IA indisponível.</strong> {{ iaMotivo }}
        O interruptor aparece travado de propósito — botão que não faz nada é
        pior que botão nenhum, porque alguém confia nele.
      </span>
    </p>

    <!-- 🚨 LIGAR AQUI NÃO PÕE A IA NO AR, e a tela tem de dizer isso. Sem esta
         linha, alguém liga "Cliente" aqui, sai da tela achando que a IA está
         atendendo, e nada acontece — o pior tipo de silêncio. -->
    <p v-else-if="canaisComIa === 0" class="aviso aviso--atencao">
      <i class="bi bi-robot aviso__icone" aria-hidden="true"></i>
      <span>
        <strong>O motor está pronto ({{ iaModelo }}), mas nenhum canal está
        com a IA ligada.</strong>
        Ligar um tipo aqui é só o <em>filtro</em>: quem coloca a IA para
        responder é o interruptor do canal, na CFG_1.1 — e ela só atende o
        que chegar <strong>depois</strong> desse momento.
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
        <div class="linha">
          <span v-if="t.boas_vindas_ligado" class="chip chip--ok">boas-vindas</span>
          <span v-if="t.ia_ligada" class="chip chip--acento">IA</span>
          <span v-if="!t.boas_vindas_ligado && !t.ia_ligada" class="chip">desligado</span>
        </div>
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

          <!-- Travado só quando o motor não está disponível. O `title` diz por
               quê: interruptor cinza sem explicação vira chamado. -->
          <button
            class="botao botao--pequeno"
            :class="t.ia_ligada ? 'botao--contorno'
                    : (iaDisponivel ? 'botao--primario' : 'botao--fantasma')"
            type="button"
            :disabled="!iaDisponivel || salvando === t.relacao"
            :title="iaDisponivel
              ? 'A IA responde a quem tem este tipo — se o canal também estiver ligado.'
              : iaMotivo"
            @click="alternarIa(t)"
          >
            <i class="bi bi-robot" aria-hidden="true"></i>
            <template v-if="!iaDisponivel">IA — indisponível</template>
            <template v-else>{{ t.ia_ligada ? 'Desligar IA' : 'Ligar IA' }}</template>
          </button>
        </div>

        <!-- ⚠️ O ALCANCE DA IA É O MESMO NÚMERO, e o aviso só aparece na hora
             de ligar: ligar "Cliente" põe a IA para conversar com 1.750
             pessoas. -->
        <p v-if="iaDisponivel && !t.ia_ligada && t.contatos > 100"
           class="apagado pequeno">
          Ligar a IA aqui a coloca para conversar com <strong>{{ t.contatos }}</strong>
          pessoa(s), assim que elas escreverem.
        </p>
      </div>
    </section>

    <p class="apagado pequeno">
      A mensagem sai uma vez por conversa: a marca fica gravada na própria
      conversa, então reentrega de webhook não faz o cliente receber duas vezes.
      A IA usa a mesma ideia, com a própria marca — ela nunca responde duas
      vezes à mesma pergunta, e nunca responde ao que chegou antes de ser ligada.
    </p>
  </div>
</template>

<style scoped>
.aut { margin-bottom: var(--e-3); }
.aut .cartao__cabecalho { align-items: flex-start; }
</style>
