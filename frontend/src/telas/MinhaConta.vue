<script setup>
/* ============================================================================
   CFG_10.1 — Minha conta.
   ----------------------------------------------------------------------------
   🔵 Pedido dele em 17/09: *"central de perfil 'minha conta' para foto de
   usuario, dados de perfil, tipo de envio 'entrer ou clique'"*. O status é
   🟢 pedido do Rodrigo, trazido por ele em 15/09.

   🚨 O `atendente.estado` JÁ EXISTIA, desde a migração 001, com três valores
   -- e nunca chegou a tela nenhuma. Por isso ele lembrava do status e não o
   via: coluna viva no banco e morta no produto. A 044 acrescentou o quarto
   (`offline`) e esta tela é o produto que faltava em cima dela.

   🚨 O TIPO DE ENVIO É ESPELHO, NÃO CÓPIA. O mesmo interruptor mora na
   CFG_6.1 (Atalhos), porque lá ele responde "o que o teclado faz por mim".
   Aqui ele responde "como EU envio". São a mesma preferência
   (`enviar_com_enter`) e a mesma rota -- duas portas para o mesmo quarto,
   nunca dois quartos.

   ⚠️ O QUE NÃO SE EDITA AQUI, e de propósito: nome, login, e-mail e perfil.
   Todo mundo entra por Google com domínio travado, então o nome e o e-mail
   são de lá; e perfil é permissão, que é decisão do owner na tela de
   cadastro. Mostrar como leitura é melhor que esconder -- é a regra "nada
   some" (27/08): a pessoa vê o que vale para ela e por que não pode mudar.
   ============================================================================ */
import { ref, computed, onMounted } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'
import { sessao } from '../estado/sessao.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'

const carregando = ref(true)
const salvando = ref(false)
const erro = ref('')
const recado = ref('')
const perfil = ref(null)
/* Muda a cada troca de foto para o navegador não servir a antiga do cache:
   o caminho da imagem é o mesmo, só o conteúdo mudou. */
const versaoFoto = ref(Date.now())

/* 🚨 O RÓTULO É DA PESSOA, O VALOR É DO BANCO. `nao_perturbe` é o que o
   `CHECK` aceita; "Não perturbe" é o que se lê. Misturar os dois faria a tela
   mostrar nome de coluna para quem atende. */
const ESTADOS = [
  { valor: 'disponivel', rotulo: 'Disponível', cor: 'ok',
    ajuda: 'Recebendo conversa normalmente.' },
  { valor: 'ausente', rotulo: 'Em pausa', cor: 'aviso',
    ajuda: 'Almoço, reunião, café. Você volta hoje.' },
  { valor: 'nao_perturbe', rotulo: 'Não perturbe', cor: 'erro',
    ajuda: 'Está no painel, mas concentrado em outra coisa.' },
  { valor: 'offline', rotulo: 'Fora do expediente', cor: '',
    ajuda: 'Encerrou o dia. É escolha sua, não é deduzido de estar ou não com o painel aberto.' },
]

const estadoAtual = computed(
  () => ESTADOS.find((e) => e.valor === perfil.value?.estado) || null,
)

const iniciais = computed(() => {
  const nome = (perfil.value?.nome || sessao.nome || '').trim()
  if (!nome) return '?'
  const partes = nome.split(/\s+/)
  return ((partes[0]?.[0] || '') + (partes.length > 1 ? partes[partes.length - 1][0] : ''))
    .toUpperCase()
})

async function carregar () {
  carregando.value = true
  erro.value = ''
  try {
    perfil.value = await api.get('/api/eu/perfil')
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui carregar seus dados.'
  } finally {
    carregando.value = false
  }
}

async function definirEstado (valor) {
  if (salvando.value || perfil.value?.estado === valor) return
  salvando.value = true
  erro.value = ''
  recado.value = ''
  try {
    await api.put('/api/eu/estado', { estado: valor })
    /* 🚨 RELÊ EM VEZ DE CONFIAR NO 200 -- a prova é o estado, não o código de
       retorno. Vale para o painel inteiro e já custou caro em 12/08. */
    await carregar()
    recado.value = `Agora você está como "${estadoAtual.value?.rotulo || valor}".`
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui mudar o seu estado.'
  } finally {
    salvando.value = false
  }
}

async function alternarEnter (evento) {
  const ligado = evento.target.checked
  salvando.value = true
  erro.value = ''
  recado.value = ''
  try {
    await api.put('/api/eu/enviar-com-enter', { ligado })
    await carregar()
    recado.value = ligado
      ? 'Enter envia. Shift+Enter quebra a linha.'
      : 'Enter quebra a linha. O envio é pelo botão ou Ctrl+Enter.'
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui salvar a preferência.'
    await carregar()
  } finally {
    salvando.value = false
  }
}

async function subirFoto (evento) {
  const arquivo = evento.target.files && evento.target.files[0]
  evento.target.value = ''            // deixa reenviar o mesmo arquivo
  if (!arquivo) return
  erro.value = ''
  recado.value = ''
  const corpo = new FormData()
  corpo.append('arquivo', arquivo)
  try {
    /* `fetch` direto para o navegador montar o `boundary` -- mesmo caminho da
       imagem de assinatura no E-mail. */
    const r = await fetch('/api/eu/foto', {
      method: 'POST',
      headers: { Authorization: `Bearer ${localStorage.getItem('movizap.token')}` },
      body: corpo,
    })
    if (!r.ok) {
      /* O backend recusa COM MOTIVO (não é imagem, passa de 2 MB, conta sem
         linha em `atendente`): "não consegui" perderia o porquê. */
      const detalhe = await r.json().catch(() => ({}))
      throw new ErroDeApi(detalhe.detail || 'O servidor recusou a imagem.', r.status, '')
    }
    await carregar()
    versaoFoto.value = Date.now()
    recado.value = 'Foto salva.'
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui subir a foto.'
  }
}

async function tirarFoto () {
  erro.value = ''
  recado.value = ''
  try {
    await api.del('/api/eu/foto')
    await carregar()
    versaoFoto.value = Date.now()
    recado.value = 'Foto removida. Voltou para as suas iniciais.'
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui remover a foto.'
  }
}

onMounted(carregar)
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Minha conta</h1>
        <AjudaDaTela>
          O que está aqui vale só para você. Nome, e-mail e perfil vêm do
          login pelo Google e da sua ficha de atendente — quem muda perfil é
          o responsável pelo painel, porque perfil é permissão.
        </AjudaDaTela>
      </div>
      <span v-if="estadoAtual" class="chip" :class="estadoAtual.cor ? 'chip--' + estadoAtual.cor : ''">
        {{ estadoAtual.rotulo }}
      </span>
    </header>

    <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>
    <p v-if="recado" class="aviso aviso--ok" role="status">{{ recado }}</p>
    <p v-if="carregando" class="apagado">Carregando…</p>

    <template v-if="!carregando && perfil">
      <!-- ---------------------------------------------------------- estado -->
      <section class="cartao tela__bloco">
        <div class="cartao__corpo pilha">
          <h2 class="cartao__titulo">Como você está</h2>
          <p class="apagado pequeno">
            É você quem escolhe — não é deduzido de ter o painel aberto.
          </p>
          <div class="conta__estados">
            <button
              v-for="e in ESTADOS"
              :key="e.valor"
              type="button"
              class="conta__estado"
              :class="{ 'conta__estado--ativo': perfil.estado === e.valor }"
              :disabled="salvando"
              :aria-pressed="perfil.estado === e.valor"
              @click="definirEstado(e.valor)"
            >
              <span class="conta__bolinha" :class="'conta__bolinha--' + e.valor"
                    aria-hidden="true"></span>
              <span class="conta__estado-texto">
                <strong>{{ e.rotulo }}</strong>
                <small class="apagado">{{ e.ajuda }}</small>
              </span>
            </button>
          </div>
        </div>
      </section>

      <!-- ------------------------------------------------------------ foto -->
      <section class="cartao tela__bloco">
        <div class="cartao__corpo pilha">
          <h2 class="cartao__titulo">Sua foto</h2>
          <div class="conta__foto-linha">
            <img
              v-if="perfil.tem_foto"
              class="conta__foto"
              :src="`/api/atendentes/${perfil.id}/foto?v=${versaoFoto}`"
              :alt="`Foto de ${perfil.nome}`"
            />
            <span v-else class="conta__foto conta__foto--iniciais" aria-hidden="true">
              {{ iniciais }}
            </span>
            <div class="pilha">
              <label class="botao botao--contorno conta__subir">
                <i class="bi bi-upload" aria-hidden="true"></i>
                {{ perfil.tem_foto ? 'Trocar foto' : 'Escolher foto' }}
                <input type="file" accept="image/*" hidden @change="subirFoto" />
              </label>
              <button v-if="perfil.tem_foto" type="button"
                      class="botao botao--contorno" @click="tirarFoto">
                <i class="bi bi-trash" aria-hidden="true"></i> Remover
              </button>
              <p class="apagado pequeno">PNG ou JPG, até 2 MB.</p>
            </div>
          </div>
        </div>
      </section>

      <!-- --------------------------------------------------- tipo de envio -->
      <section class="cartao tela__bloco">
        <div class="cartao__corpo pilha">
          <h2 class="cartao__titulo">Como você envia</h2>
          <label class="interruptor">
            <input type="checkbox" :checked="perfil.enviar_com_enter"
                   :disabled="salvando" @change="alternarEnter" />
            <span><strong>Enter envia a mensagem</strong></span>
          </label>
          <p class="apagado pequeno">
            {{ perfil.enviar_com_enter
              ? 'Shift+Enter quebra a linha.'
              : 'Enter quebra a linha; o envio é pelo botão ou Ctrl+Enter.' }}
            É a mesma preferência que aparece em Atalhos.
          </p>
        </div>
      </section>

      <!-- ----------------------------------------------------------- dados -->
      <section class="cartao tela__bloco">
        <div class="cartao__corpo pilha">
          <h2 class="cartao__titulo">Seus dados</h2>
          <dl class="conta__dados">
            <div><dt>Nome</dt><dd>{{ perfil.nome }}</dd></div>
            <div><dt>Login</dt><dd>{{ perfil.login }}</dd></div>
            <div><dt>E-mail</dt><dd>{{ perfil.email || '—' }}</dd></div>
            <div><dt>Perfil</dt><dd>{{ perfil.perfil }}</dd></div>
            <div>
              <dt>Teto de conversas</dt>
              <dd>{{ perfil.max_conversas ?? 'sem teto' }}</dd>
            </div>
          </dl>
          <p class="apagado pequeno">
            Estes campos são da sua ficha de atendente. Quem os altera é o
            responsável pelo painel, em Cadastros › Atendentes.
          </p>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.conta__estados { display: grid; gap: var(--e-2); }

/* Alvo grande de propósito: 44px é o piso do padrão dos quatro painéis, e
   trocar de estado é coisa que se faz de celular, a caminho do almoço. */
.conta__estado {
  display: flex;
  align-items: center;
  gap: var(--e-3);
  min-height: 44px;
  padding: var(--e-2) var(--e-3);
  border: 1px solid var(--borda);
  border-radius: var(--r-md);
  background: var(--superficie);
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.conta__estado:hover { border-color: var(--acento); }
.conta__estado--ativo {
  border-color: var(--acento);
  box-shadow: inset 0 0 0 1px var(--acento);
}
.conta__estado-texto { display: flex; flex-direction: column; }
.conta__estado-texto small { font-size: var(--txt-sm); }

/* 🚨 DEFINIDAS AQUI PORQUE NÃO SÃO GLOBAIS. `.interruptor` mora no escopo da
   CFG_6.1 e `.cartao__titulo` não existe em CSS nenhum -- conferido antes de
   usar, que é a lição do `var(--raio, 12px)` que nunca existiu e caía no
   valor de emergência em silêncio. */
.interruptor { display: flex; align-items: center; gap: var(--e-3); cursor: pointer; }
.interruptor input { width: 18px; height: 18px; accent-color: var(--acento); }

.cartao__titulo { margin: 0; font-size: var(--txt-lg); }

.conta__bolinha {
  width: 12px; height: 12px; border-radius: 50%;
  flex: 0 0 auto;
  border: 1px solid rgba(0, 0, 0, .15);
}
.conta__bolinha--disponivel   { background: var(--ok); }
.conta__bolinha--ausente      { background: var(--aviso); }
.conta__bolinha--nao_perturbe { background: var(--erro); }
.conta__bolinha--offline      { background: var(--texto-apagado); }

.conta__foto-linha { display: flex; align-items: flex-start; gap: var(--e-3); }
.conta__foto {
  width: 96px; height: 96px;
  border-radius: 50%;
  object-fit: cover;
  flex: 0 0 auto;
  border: 1px solid var(--borda);
}
.conta__foto--iniciais {
  display: grid;
  place-items: center;
  background: var(--acento);
  color: var(--acento-texto);
  font-size: 2rem;
  font-weight: var(--peso-forte);
}
/* O input de arquivo fica escondido dentro do label: o botão do navegador não
   se veste, e ter dois controles para a mesma ação confunde. */
.conta__subir { cursor: pointer; }

.conta__dados { display: grid; gap: var(--e-2); margin: 0; }
.conta__dados > div { display: flex; gap: var(--e-2); flex-wrap: wrap; }
.conta__dados dt { color: var(--texto-apagado); min-width: 10rem; }
.conta__dados dd { margin: 0; }
</style>
