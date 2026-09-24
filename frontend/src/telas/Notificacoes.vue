<script setup>
/* ============================================================================
   CFG_11.1 — Notificações (24/09)
   ----------------------------------------------------------------------------
   🔵 *"o sistema de notificações ficara em configuração, cada um poderá
   ajustar o seu tom, volume - com minimo de 1 (1 até 5), pisca aba
   obrigatoriamente e coloque oopções de som, mas a opção da notificação estar
   ativada por usuario ou não, só aparece ao Owner"*.

   ⚠️ Cada escolha grava na hora e toca de amostra: quem escolhe um som quer
   ouvi-lo, e um botão "Salvar" separado seria um passo a mais para esquecer.
   ============================================================================ */
import { ref, computed, onMounted } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'
import { sessao } from '../estado/sessao.js'
import { notificacoes } from '../estado/notificacoes.js'
import { TONS, tocar, somBloqueado } from '../util/som.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'

const souOwner = computed(() => Boolean(sessao.usuario?.owner))
const minha = ref(null)
const equipe = ref([])
const erro = ref('')
const recado = ref('')
const salvando = ref(false)

async function carregar() {
  erro.value = ''
  try {
    minha.value = await api.get('/api/eu/notificacoes')
    if (souOwner.value) equipe.value = await api.get('/api/notificacoes/equipe')
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui ler as notificações.'
  }
}

onMounted(carregar)

async function gravar(tom, volume) {
  salvando.value = true
  erro.value = ''
  recado.value = ''
  try {
    const r = await api.put('/api/eu/notificacao', { tom, volume })
    minha.value = { ...minha.value, tom: r.tom, volume: r.volume }
    notificacoes.tom = r.tom
    notificacoes.volume = r.volume
    await tocar(r.tom, r.volume)
    recado.value = 'Salvo.'
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui salvar.'
  } finally {
    salvando.value = false
  }
}

async function alternarPessoa(p) {
  erro.value = ''
  try {
    const r = await api.put(`/api/atendentes/${p.id}/notificacao`, { ativa: !p.notificacao_ativa })
    p.notificacao_ativa = r.notificacao_ativa
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui mudar.'
  }
}
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Notificações</h1>
        <AjudaDaTela>
          O som e o aviso na aba quando chega mensagem numa conversa sua.
        </AjudaDaTela>
      </div>
    </header>

    <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>
    <p v-if="recado" class="aviso aviso--ok" role="status">{{ recado }}</p>

    <template v-if="minha">
      <p v-if="!minha.ativa" class="aviso aviso--atencao" role="status">
        <i class="bi bi-bell-slash aviso__icone" aria-hidden="true"></i>
        <span>As suas notificações estão <strong>desligadas pelo owner</strong>: nada toca
        nem pisca. O número nas abas continua aparecendo.</span>
      </p>

      <section class="cartao tela__bloco">
        <div class="cartao__corpo pilha">
          <h2 class="cartao__titulo">Quando avisa</h2>
          <ul class="regras">
            <li>Só nas conversas em que <strong>você é o dono</strong>.</li>
            <li>Toca quando uma conversa sua recebe mensagem e estava lida.</li>
            <li>Com até <strong>4</strong> conversas não lidas, cada uma toca. Passou disso,
              fica só o número, e só uma conversa <strong>nova</strong> para você toca, uma vez.</li>
          </ul>
          <label class="fixo">
            <input type="checkbox" checked disabled />
            <span>
              <strong>A aba do navegador pisca</strong>
              <small class="apagado">quando o painel está em segundo plano e há conversa sua não lida. Sempre ligado.</small>
            </span>
          </label>
        </div>
      </section>

      <section class="cartao tela__bloco">
        <div class="cartao__corpo pilha">
          <h2 class="cartao__titulo">Seu som</h2>
          <div class="tons" role="radiogroup" aria-label="Tom">
            <button v-for="t in TONS" :key="t.valor" type="button" class="tom"
                    :class="{ 'tom--ativo': minha.tom === t.valor }"
                    :aria-pressed="minha.tom === t.valor" :disabled="salvando"
                    @click="gravar(t.valor, minha.volume)">
              <i class="bi" :class="minha.tom === t.valor ? 'bi-record-circle-fill' : 'bi-circle'"
                 aria-hidden="true"></i>
              <span>
                <strong>{{ t.rotulo }}</strong>
                <small class="apagado">{{ t.ajuda }}</small>
              </span>
            </button>
          </div>

          <div class="volume">
            <span class="campo__rotulo">Volume</span>
            <div class="volume__niveis" role="radiogroup" aria-label="Volume">
              <button v-for="n in 5" :key="n" type="button" class="nivel"
                      :class="{ 'nivel--ativo': minha.volume === n }"
                      :aria-pressed="minha.volume === n" :disabled="salvando"
                      @click="gravar(minha.tom, n)">{{ n }}</button>
            </div>
            <span class="campo__ajuda">De 1 a 5. Não há mudo: quem não deve ouvir, o owner desliga.</span>
          </div>

          <div class="linha">
            <button class="botao botao--contorno" type="button" @click="tocar(minha.tom, minha.volume)">
              <i class="bi bi-play-circle" aria-hidden="true"></i> Testar
            </button>
            <span v-if="somBloqueado" class="pequeno apagado">
              O navegador só toca depois de um clique na página — clique em Testar de novo.
            </span>
          </div>
        </div>
      </section>

      <!-- 🔵 "só aparece ao Owner". A rota também recusa quem não é. -->
      <section v-if="souOwner" class="cartao tela__bloco">
        <div class="cartao__corpo pilha">
          <h2 class="cartao__titulo">Quem recebe notificação <span class="chip chip--pequeno">só o owner vê</span></h2>
          <p class="apagado pequeno">Desligada, a pessoa não ouve som nem vê a aba piscar. O número nas abas continua.</p>
          <ul class="equipe">
            <li v-for="p in equipe" :key="p.id" class="equipe__pessoa">
              <span>{{ p.nome }} <small class="apagado">{{ p.perfil }}</small></span>
              <label class="interruptor">
                <input type="checkbox" :checked="p.notificacao_ativa" @change="alternarPessoa(p)" />
                <span>{{ p.notificacao_ativa ? 'Ligada' : 'Desligada' }}</span>
              </label>
            </li>
          </ul>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.tela { max-width: 820px; }
.tela__cabecalho { margin-bottom: var(--e-5); }
.tela__bloco { margin-bottom: var(--e-4); }
.aviso { margin-bottom: var(--e-4); }
.cartao__titulo { display: flex; align-items: center; gap: var(--e-2); margin: 0; font-size: var(--txt-lg); }

.regras { margin: 0; padding-left: 1.2em; color: var(--texto-fraco); line-height: var(--entrelinha); }

.fixo { display: flex; align-items: flex-start; gap: var(--e-3); padding: var(--e-3);
        border: 1px dashed var(--borda-forte); border-radius: var(--r-md); }
.fixo input { width: 18px; height: 18px; margin-top: 2px; accent-color: var(--acento); }
.fixo span { display: flex; flex-direction: column; gap: 2px; }

.tons { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 180px), 1fr)); gap: var(--e-2); }
.tom {
  display: flex; align-items: flex-start; gap: var(--e-2); min-height: var(--altura-toque);
  padding: var(--e-3); border: var(--borda-fina) solid var(--borda); border-radius: var(--r-md);
  background: var(--superficie); color: inherit; font: inherit; text-align: left; cursor: pointer;
}
.tom:hover { border-color: var(--borda-forte); background: var(--superficie-2); }
.tom--ativo { border-color: var(--acento); background: var(--acento-suave); }
.tom .bi { color: var(--acento); margin-top: 2px; }
.tom span { display: flex; flex-direction: column; gap: 2px; }

.volume { display: flex; flex-direction: column; gap: var(--e-2); }
.volume__niveis { display: flex; gap: var(--e-2); }
.nivel {
  width: var(--altura-toque); height: var(--altura-toque);
  border: var(--borda-fina) solid var(--borda); border-radius: var(--r-md);
  background: var(--superficie); font: inherit; font-weight: var(--peso-forte); cursor: pointer;
}
.nivel--ativo { border-color: var(--acento); background: var(--acento); color: var(--acento-texto); }

.equipe { list-style: none; margin: 0; padding: 0; border: var(--borda-fina) solid var(--borda); border-radius: var(--r-md); }
.equipe__pessoa { display: flex; justify-content: space-between; align-items: center; gap: var(--e-3);
                  padding: var(--e-2) var(--e-3); }
.equipe__pessoa + .equipe__pessoa { border-top: var(--borda-fina) solid var(--borda); }
.interruptor { display: flex; align-items: center; gap: var(--e-2); cursor: pointer; }
.interruptor input { width: 18px; height: 18px; accent-color: var(--acento); }
</style>
