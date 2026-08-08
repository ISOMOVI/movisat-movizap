<script setup>
/* ============================================================================
   ATD_3.1 — Informativos.
   ----------------------------------------------------------------------------
   🚨 É A ÚNICA TELA QUE ALCANÇA CLIENTE DE VERDADE EM LOTE. O canal é
   irreversível: mensagem enviada não volta. Por isso o desenho todo empurra
   para a cautela:

     - o disparo nasce RASCUNHO e não sai sozinho;
     - "Enviar 1 e conferir" fica ANTES do botão de enviar o lote;
     - ritmo e teto por hora aparecem como campos, não como promessa;
     - a cobertura mostra QUEM FICA DE FORA, e por quê.

   🚨 MEDIDO EM 07/08: dos 944 clientes ativos, só 369 são alcançáveis. E dos
   575 que ficam de fora, 483 é CADASTRO INCOMPLETO (só fixo ou sem telefone),
   não é o cliente que recusou WhatsApp. Disparar para 369 achando que falou
   com 944 é o erro que esta tela existe para não deixar acontecer.
   ============================================================================ */
import { ref, computed, onMounted } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'

const cobertura = ref(null)
const disparos = ref([])
const respostas = ref(null)
const aberto = ref(null)
const carregando = ref(true)
const erro = ref('')
const recado = ref('')
const ocupado = ref(false)

const form = ref({ titulo: '', corpo: '', intervalo_seg: 5, teto_por_hora: 200 })
const foneTeste = ref('')

async function carregar() {
  try {
    const [c, lista, r] = await Promise.all([
      api.get('/api/informativos/cobertura'),
      api.get('/api/informativos'),
      api.get('/api/informativos/respostas'),
    ])
    cobertura.value = c
    disparos.value = lista
    respostas.value = r
    erro.value = ''
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao ler os informativos.'
  } finally {
    carregando.value = false
  }
}

onMounted(carregar)

const foraPorCadastro = computed(() => cobertura.value?.fora_por_cadastro || 0)
const pct = (n) => (cobertura.value?.clientes_ativos
  ? Math.round((n * 100) / cobertura.value.clientes_ativos)
  : 0)

async function criar() {
  ocupado.value = true
  erro.value = ''
  recado.value = ''
  try {
    const novo = await api.post('/api/informativos', form.value)
    aberto.value = novo
    recado.value = `Rascunho criado com ${novo.total_destinos} destinos. `
                 + 'Nada foi enviado ainda.'
    form.value = { titulo: '', corpo: '', intervalo_seg: 5, teto_por_hora: 200 }
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui criar.'
  } finally {
    ocupado.value = false
  }
}

async function abrir(id) {
  try {
    aberto.value = await api.get(`/api/informativos/${id}`)
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui abrir.'
  }
}

async function testar() {
  ocupado.value = true
  erro.value = ''
  recado.value = ''
  try {
    const r = await api.post(`/api/informativos/${aberto.value.id}/teste`,
      { telefone: foneTeste.value || null })
    recado.value = r.avulso
      ? `Teste avulso enviado para ${r.telefone} — a fila não foi tocada.`
      : `Enviado para 1 destino (${r.telefone}). Confira antes de soltar o resto.`
    await abrir(aberto.value.id)
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'O teste falhou.'
  } finally {
    ocupado.value = false
  }
}

async function enviarLote() {
  ocupado.value = true
  erro.value = ''
  recado.value = ''
  try {
    const r = await api.post(`/api/informativos/${aberto.value.id}/enviar?quantos=20`)
    recado.value = r.motivo
      ? `Parou: ${r.motivo} (${r.ja_saiu_na_hora} já saíram nesta hora).`
      : `${r.enviados} enviados, ${r.falhas} falhas, ${r.restam} na fila.`
    await Promise.all([abrir(aberto.value.id), carregar()])
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha no envio.'
  } finally {
    ocupado.value = false
  }
}

function quando(iso) {
  return iso ? new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : '—'
}
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Informativos</h1>
        <p class="fraco pequeno">
          Disparo pelo canal informativo. Sem resposta de cliente — quem
          responde cai no contador lá embaixo.
        </p>
      </div>
    </header>

    <p class="aviso aviso--atencao">
      <i class="bi bi-exclamation-triangle aviso__icone" aria-hidden="true"></i>
      <span>
        <strong>O canal é irreversível.</strong> Mensagem enviada não volta.
        O disparo nasce como rascunho e só sai quando você mandar — e vale
        enviar 1 e conferir antes de soltar o resto.
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

    <!-- ------------------------------------------------------- COBERTURA -->
    <section v-if="cobertura" class="cartao tela__bloco">
      <header class="cartao__cabecalho">
        <span>Quem este canal alcança</span>
        <span class="chip chip--acento">
          {{ cobertura.alcancaveis }} de {{ cobertura.clientes_ativos }}
          ({{ pct(cobertura.alcancaveis) }}%)
        </span>
      </header>
      <div class="cartao__corpo">
        <table class="tabela">
          <tbody>
            <tr>
              <td><strong>Alcançáveis por WhatsApp</strong></td>
              <td class="mono">{{ cobertura.alcancaveis }}</td>
              <td class="fraco pequeno">{{ cobertura.telefones_alvo }} números distintos</td>
            </tr>
            <tr>
              <td>Têm celular, nenhum com WhatsApp</td>
              <td class="mono">{{ cobertura.sem_whatsapp_com_celular }}</td>
              <td class="fraco pequeno">de fato não usam</td>
            </tr>
            <tr class="linha--cadastro">
              <td>Só têm telefone fixo</td>
              <td class="mono">{{ cobertura.so_telefone_fixo }}</td>
              <td class="fraco pequeno">cadastro incompleto</td>
            </tr>
            <tr class="linha--cadastro">
              <td>Nenhum telefone cadastrado</td>
              <td class="mono">{{ cobertura.sem_telefone }}</td>
              <td class="fraco pequeno">cadastro incompleto</td>
            </tr>
          </tbody>
        </table>
        <p class="aviso aviso--info" style="margin-top:12px">
          <i class="bi bi-info-circle aviso__icone" aria-hidden="true"></i>
          <span>
            🚨 <strong>{{ foraPorCadastro }} clientes ({{ pct(foraPorCadastro) }}%)
            ficam de fora por cadastro incompleto</strong>, não por recusarem
            WhatsApp. Corrigir o telefone no Harmonit aumenta o alcance mais que
            qualquer coisa que eu faça aqui.
          </span>
        </p>
      </div>
    </section>

    <!-- ----------------------------------------------------- NOVO DISPARO -->
    <section class="cartao tela__bloco">
      <header class="cartao__cabecalho"><span>Novo informativo</span></header>
      <div class="cartao__corpo pilha">
        <label class="campo">
          <span class="campo__rotulo">Título (só para você identificar)</span>
          <input v-model="form.titulo" class="campo__entrada" maxlength="200" />
        </label>
        <label class="campo">
          <span class="campo__rotulo">Mensagem</span>
          <textarea v-model="form.corpo" class="campo__entrada" rows="5" maxlength="4000"></textarea>
          <span class="campo__ajuda">{{ form.corpo.length }} / 4000 caracteres.</span>
        </label>
        <div class="grade">
          <label class="campo">
            <span class="campo__rotulo">Intervalo entre envios (s)</span>
            <input v-model.number="form.intervalo_seg" class="campo__entrada" type="number" min="1" max="300" />
          </label>
          <label class="campo">
            <span class="campo__rotulo">Teto por hora</span>
            <input v-model.number="form.teto_por_hora" class="campo__entrada" type="number" min="1" max="2000" />
            <span class="campo__ajuda">Rajada é o que derruba número.</span>
          </label>
        </div>
        <button class="botao botao--primario" type="button" :disabled="ocupado || !form.titulo || !form.corpo" @click="criar">
          Criar rascunho (não envia)
        </button>
      </div>
    </section>

    <!-- ---------------------------------------------------- DISPARO ABERTO -->
    <section v-if="aberto" class="cartao tela__bloco">
      <header class="cartao__cabecalho">
        <span>{{ aberto.titulo }}</span>
        <span class="chip" :class="aberto.estado === 'concluido' ? 'chip--ok' : 'chip--aviso'">
          {{ aberto.estado }}
        </span>
      </header>
      <div class="cartao__corpo pilha">
        <p class="mono pequeno fraco">{{ aberto.total_destinos }} destinos · criado {{ quando(aberto.criado_em) }}</p>
        <div class="linha linha--quebra">
          <span v-for="d in aberto.destinos" :key="d.estado" class="chip">
            {{ d.n }} {{ d.estado }}
          </span>
        </div>

        <label class="campo">
          <span class="campo__rotulo">Enviar 1 para conferir</span>
          <input v-model="foneTeste" class="campo__entrada" placeholder="telefone avulso (em branco = o 1º da fila)" />
          <span class="campo__ajuda">
            Telefone avulso não toca a fila. Em branco, manda para o primeiro
            destino real e o marca como enviado.
          </span>
        </label>

        <div class="linha linha--quebra">
          <button class="botao botao--contorno" type="button" :disabled="ocupado" @click="testar">
            <i class="bi bi-send-check" aria-hidden="true"></i> Enviar 1 e conferir
          </button>
          <button class="botao botao--perigo" type="button" :disabled="ocupado" @click="enviarLote">
            <span v-if="ocupado" class="girando"></span>
            Enviar próximos 20
          </button>
        </div>
        <p class="apagado pequeno">
          A confirmação de que chegou é o <strong>estado de entrega</strong> que
          volta pelo webhook — não o retorno do envio, que sai sempre como
          "pendente".
        </p>
      </div>
    </section>

    <!-- ---------------------------------------------------------- HISTÓRICO -->
    <section v-if="disparos.length" class="cartao tela__bloco">
      <header class="cartao__cabecalho"><span>Disparos</span></header>
      <div class="tabela--rolavel">
        <table class="tabela">
          <thead>
            <tr><th>Título</th><th>Estado</th><th>Total</th><th>Entregues</th><th>Pendentes</th><th>Falhas</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="d in disparos" :key="d.id">
              <td><strong>{{ d.titulo }}</strong><p class="apagado pequeno">{{ quando(d.criado_em) }}</p></td>
              <td><span class="chip">{{ d.estado }}</span></td>
              <td class="mono">{{ d.total }}</td>
              <td class="mono">{{ d.entregues }}</td>
              <td class="mono">{{ d.pendentes }}</td>
              <td class="mono">{{ d.falharam }}</td>
              <td>
                <button class="botao botao--pequeno botao--contorno" type="button" @click="abrir(d.id)">Abrir</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ---------------------------------------------------------- RESPOSTAS -->
    <section v-if="respostas" class="cartao tela__bloco">
      <header class="cartao__cabecalho">
        <span>Respostas recebidas neste canal</span>
        <span class="chip" :class="respostas.total ? 'chip--aviso' : ''">{{ respostas.total }}</span>
      </header>
      <div class="cartao__corpo">
        <p class="fraco pequeno">
          O informativo é só de envio — estas mensagens <strong>não viram
          conversa</strong>. Aparecem aqui para não ficarem invisíveis: gente
          responde boleto.
        </p>
        <div v-if="respostas.ultimas.length" class="tabela--rolavel">
          <table class="tabela">
            <tbody>
              <tr v-for="r in respostas.ultimas" :key="r.id">
                <td class="mono pequeno">{{ r.telefone || '—' }}</td>
                <td>{{ r.texto || '(sem texto)' }}</td>
                <td class="fraco pequeno">{{ quando(r.recebido_em) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.tela { max-width: 1000px; }

.tela__cabecalho { margin-bottom: var(--e-4); }
.tela__cabecalho p { max-width: var(--largura-texto); margin-top: var(--e-1); }

.tela__bloco { margin-bottom: var(--e-4); overflow: hidden; }

.grade { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: var(--e-3); }
.linha--quebra { flex-wrap: wrap; gap: var(--e-3); }
.linha--cadastro td:first-child { padding-left: var(--e-3); }

textarea.campo__entrada { resize: vertical; }
</style>
