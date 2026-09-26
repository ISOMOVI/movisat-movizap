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

   🔵 O NOME SE EDITA AQUI DESDE 24/09, decisão dele: *"Nome de exibição pode
   ser alterado por todos os tipos, se quiser"*. Login, e-mail e perfil
   continuam fora: e-mail é a chave do login Google, perfil é permissão.

   🔵 E NEM TODO CAMPO APARECE PARA TODOS (mesmo dia): *"o campo de e-mail,
   deve aparecer somente para admin e owner"* e *"o 'Login' pode ser oculto a
   todos menos owner, pois usamos o auth google para logar"*.
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

/* ---- o nome de exibição (24/09) ---- */
const nomeNovo = ref('')
const nomeMudou = computed(() =>
  perfil.value && nomeNovo.value.trim() && nomeNovo.value.trim() !== perfil.value.nome)
const veEmail = computed(() => ['owner', 'admin'].includes(perfil.value?.perfil))
const veLogin = computed(() => perfil.value?.perfil === 'owner')

async function salvarNome () {
  if (!nomeMudou.value || salvando.value) return
  salvando.value = true
  erro.value = ''
  recado.value = ''
  try {
    await api.put('/api/eu/nome', { nome: nomeNovo.value })
    await carregar()
    recado.value = `Seu nome agora aparece como "${perfil.value.nome}".`
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui trocar o seu nome.'
  } finally {
    salvando.value = false
  }
}

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
    ajuda: 'Encerrou o dia. Enquanto estiver assim, não recebe conversa transferida.' },
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
    nomeNovo.value = perfil.value.nome
    voltaNova.value = perfil.value.afastado_ate || perfil.value.afasta_ate || ''
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui carregar seus dados.'
  } finally {
    carregando.value = false
  }
}

async function alternarSempreOnline (evento) {
  salvando.value = true
  erro.value = ''
  recado.value = ''
  try {
    await api.put('/api/eu/sempre-online', { ligado: evento.target.checked })
    await carregar()
    recado.value = perfil.value.sempre_online
      ? '"Sempre online" ligado: dentro da sua jornada, a regra de tempo não muda o seu estado.'
      : '"Sempre online" desligado.'
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui mudar.'
    await carregar()
  } finally {
    salvando.value = false
  }
}

/* ---- afastamento (25/09) ----------------------------------------------------
   🔵 *"ela loga e vai na configuração dela e coloca o dia de ontem"*. Enquanto
   está afastada, os estados ficam travados (o backend também recusa); o
   caminho de volta é a data. Hoje ou antes encerra; um marcado, cancela. */
const afastado = computed(() => Boolean(perfil.value?.afastamento_motivo))
const marcado = computed(() => Boolean(perfil.value?.afasta_em))
const voltaNova = ref('')
const dataBR = (iso) => (iso ? new Date(iso + 'T12:00').toLocaleDateString('pt-BR') : '')

async function mudarVolta () {
  if (!voltaNova.value || salvando.value) return
  const eraAfastado = afastado.value
  salvando.value = true
  erro.value = ''
  recado.value = ''
  try {
    const r = await api.put('/api/eu/afastamento', { volta: voltaNova.value })
    await carregar()
    if (!r.encerrado) recado.value = `Volta mudada para ${dataBR(voltaNova.value)}.`
    else if (eraAfastado) recado.value = 'Afastamento encerrado: você está Disponível.'
    else recado.value = 'O afastamento marcado foi cancelado.'
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui mudar a data de volta.'
  } finally {
    salvando.value = false
  }
}

async function definirEstado (valor) {
  if (salvando.value || afastado.value || perfil.value?.estado === valor) return
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
          <!-- 🚨 A FRASE MUDA COM A REGRA (24/09). Dizia "É você quem escolhe —
               não é deduzido", verdade até existir a regra de tempo. Com ela
               ligada, o sistema também muda o estado, e a tela tem de dizer. -->
          <p v-if="perfil.regra_de_tempo" class="apagado pequeno">
            Você escolhe, e o sistema também muda quando você fica sem atender
            (Configurações › Geral). O que o sistema mudou volta a
            <strong>Disponível</strong> na sua próxima ação; o que você escolheu fica.
          </p>
          <p v-else class="apagado pequeno">
            É você quem escolhe — não é deduzido de ter o painel aberto.
          </p>
          <p v-if="perfil.estado_automatico" class="aviso aviso--info pequeno">
            <i class="bi bi-clock-history aviso__icone" aria-hidden="true"></i>
            <span>Este estado foi posto pelo sistema, por tempo sem atender.</span>
          </p>
          <!-- 🔵 25/09: a frase dizia "Escolher um estado abaixo encerra o
               afastamento" -- deixou de ser verdade (M12). Agora a volta é
               pela data, e os estados ficam travados. -->
          <div v-if="afastado || marcado" class="aviso aviso--atencao pequeno conta__afastamento">
            <i class="bi bi-airplane aviso__icone" aria-hidden="true"></i>
            <div class="pilha">
              <span v-if="afastado">
                Você está afastado ({{ perfil.afastamento_motivo }})<template
                v-if="perfil.afastado_ate"> até {{ dataBR(perfil.afastado_ate) }}</template>
                e não recebe conversa. Os estados abaixo ficam travados até a volta.
              </span>
              <span v-else>
                Você tem um afastamento marcado ({{ perfil.afasta_motivo }}): sai em
                {{ dataBR(perfil.afasta_em) }} e volta em {{ dataBR(perfil.afasta_ate) }}.
              </span>
              <form class="conta__volta" @submit.prevent="mudarVolta">
                <label class="campo">
                  <span class="campo__rotulo">Dia da volta</span>
                  <input v-model="voltaNova" class="campo__entrada" type="date" />
                </label>
                <button class="botao botao--contorno" type="submit"
                        :disabled="!voltaNova || salvando">Mudar a volta</button>
              </form>
              <small class="apagado">
                {{ afastado
                  ? 'Para voltar agora, escolha hoje ou um dia anterior.'
                  : 'Escolher hoje ou um dia anterior cancela o afastamento marcado.' }}
              </small>
            </div>
          </div>
          <div class="conta__estados">
            <button
              v-for="e in ESTADOS"
              :key="e.valor"
              type="button"
              class="conta__estado"
              :class="{ 'conta__estado--ativo': perfil.estado === e.valor }"
              :disabled="salvando || afastado"
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

          <!-- 🔵 24/09: *"Para o owner, pode ter o status para marcar 'sempre
               online' - dentro da jornada que o owner tbm terá, mas será
               exclusivo dele"*. -->
          <label v-if="perfil.perfil === 'owner'" class="conta__sempre">
            <input type="checkbox" :checked="perfil.sempre_online" :disabled="salvando"
                   @change="alternarSempreOnline" />
            <span>
              <strong>Sempre online</strong>
              <small class="apagado">
                Dentro da sua jornada, a regra de tempo não muda o
                seu estado.
                <template v-if="!perfil.tem_jornada">
                  Você ainda não tem jornada: monte a sua em Atendentes.
                </template>
              </small>
            </span>
          </label>
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
            <!-- 🚨 Dizia "É a mesma preferência que aparece em Atalhos" -- e
                 desde 24/09 Atalhos é só do owner: para quem atende, a frase
                 apontava para uma tela que ele não abre. -->
            <template v-if="perfil.perfil === 'owner'">É a mesma preferência que aparece em Atalhos.</template>
          </p>
        </div>
      </section>

      <!-- ----------------------------------------------------------- dados -->
      <section class="cartao tela__bloco">
        <div class="cartao__corpo pilha">
          <h2 class="cartao__titulo">Seus dados</h2>
          <form class="conta__nome" @submit.prevent="salvarNome">
            <label class="campo">
              <span class="campo__rotulo">Nome de exibição</span>
              <input v-model="nomeNovo" class="campo__entrada" maxlength="200" autocomplete="name" />
              <span class="campo__ajuda">É o que o cliente e a equipe veem.</span>
            </label>
            <button class="botao botao--primario" type="submit" :disabled="!nomeMudou || salvando">
              Salvar nome
            </button>
          </form>
          <dl class="conta__dados">
            <div v-if="veLogin"><dt>Login</dt><dd>{{ perfil.login }}</dd></div>
            <div v-if="veEmail"><dt>E-mail</dt><dd>{{ perfil.email || '—' }}</dd></div>
            <div><dt>Perfil</dt><dd>{{ perfil.perfil }}</dd></div>
            <!-- 🔵 25/09: "Teto de conversas" saiu -- *"não deve haver máximo
                 de conversas"*, e o campo nunca foi lido por nada. -->
          </dl>
          <p class="apagado pequeno">
            O nome é seu para mudar. Os outros campos são alterados em Atendentes.
          </p>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.conta__nome { display: flex; flex-direction: column; align-items: flex-start; gap: var(--e-2); }
.conta__nome .campo { width: 100%; max-width: 420px; margin-bottom: 0; }
.conta__estados { display: grid; gap: var(--e-2); }
.conta__afastamento { align-items: flex-start; }
/* Travado tem de PARECER travado (visto na prévia de 25/09): desabilitado sem
   mudança visual convida ao clique que não faz nada. */
.conta__estado:disabled { opacity: .55; cursor: not-allowed; }
.conta__estado:disabled:hover { border-color: var(--borda); }
.conta__volta { display: flex; align-items: flex-end; flex-wrap: wrap; gap: var(--e-2); }
.conta__volta .campo { margin-bottom: 0; }
.conta__sempre { display: flex; align-items: flex-start; gap: var(--e-3); padding: var(--e-3); border: 1px dashed var(--borda-forte); border-radius: var(--r-md); cursor: pointer; }
.conta__sempre input { width: 18px; height: 18px; margin-top: 2px; accent-color: var(--acento); }
.conta__sempre span { display: flex; flex-direction: column; gap: 2px; }

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
