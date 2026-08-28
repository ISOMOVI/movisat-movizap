<script setup>
/* ============================================================================
   CFG_2.1 — IA, prompt.
   ----------------------------------------------------------------------------
   🚨 ESTA TELA NÃO LIGA A IA E NÃO FALA COM MODELO NENHUM. Ela guarda texto
   versionado. Quem decide se a IA responde é `canal.ia_ligada`, por canal, e
   os dois canais estão desligados — o cabeçalho mostra isso o tempo todo, de
   propósito: ter prompt publicado é fácil de confundir com "IA no ar".

   🚨 A CONVERSA GRAVA QUAL VERSÃO A ATENDEU. Sem isso, "a IA respondeu errado
   semana passada" é irrespondível: o texto já mudou e ninguém sabe o que ela
   estava lendo na hora.

   ⚠️ O doc pedia "rascunho testável antes de publicar", e até 25/08 isso era
   só ver o texto montado — testar de verdade exigia o modelo. Em 26/08 o motor
   entrou, e a SALA DE ENSAIO no fim desta tela é o passo 3 da sequência de
   ativação do `docs/04`: *validar o bot respondendo, em conversa de teste*.

   🚨 ENSAIAR NÃO É OPERAR. O ensaio roda o motor inteiro contra uma conversa
   de verdade — prompt, ferramentas, modelo — e NÃO envia, NÃO grava, NÃO
   transfere e NÃO liga nada. Ele mostra o que ela TERIA feito. Se ensaiar
   operasse, não seria ensaio.
   ============================================================================ */
import { ref, computed, onMounted } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'

const estado = ref(null)
const versoes = ref([])
const conteudo = ref('')
const montado = ref(null)
const carregando = ref(true)
const salvando = ref(false)
const erro = ref('')
const recado = ref('')
const vendo = ref(null)

const canaisComIa = computed(() => (estado.value?.canais || []).filter((c) => c.ia_ligada))

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    const [e, lista] = await Promise.all([
      api.get('/api/ia/prompt'),
      api.get('/api/ia/prompt/versoes'),
    ])
    estado.value = e
    versoes.value = lista

    if (e.versao_ativa) {
      const ativa = await api.get(`/api/ia/prompt/versoes/${e.versao_ativa.id}`)
      conteudo.value = ativa.conteudo
      vendo.value = ativa.versao
    } else {
      const sugestao = await api.get('/api/ia/prompt/sugestao')
      conteudo.value = sugestao.conteudo
      vendo.value = null
      recado.value = 'Nenhuma versão publicada ainda — este é o rascunho sugerido, com as 7 camadas.'
    }
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao ler o prompt.'
  } finally {
    carregando.value = false
  }
}

onMounted(carregar)

async function gravar(publicar) {
  salvando.value = true
  erro.value = ''
  recado.value = ''
  try {
    const nova = await api.post('/api/ia/prompt/versoes', {
      conteudo: conteudo.value,
      publicar,
    })
    recado.value = publicar
      ? `Versão ${nova.versao} gravada e publicada.`
      : `Versão ${nova.versao} gravada como rascunho — não está valendo.`
    montado.value = null
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui gravar.'
  } finally {
    salvando.value = false
  }
}

async function publicarVersao(id, numero) {
  salvando.value = true
  erro.value = ''
  recado.value = ''
  try {
    await api.post(`/api/ia/prompt/versoes/${id}/publicar`)
    recado.value = `Versão ${numero} passou a ser a ativa.`
    montado.value = null
    await carregar()
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui publicar.'
  } finally {
    salvando.value = false
  }
}

async function abrirVersao(id) {
  erro.value = ''
  try {
    const v = await api.get(`/api/ia/prompt/versoes/${id}`)
    conteudo.value = v.conteudo
    vendo.value = v.versao
    recado.value = `Mostrando a versão ${v.versao}. Gravar cria uma versão nova — nada é sobrescrito.`
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui abrir a versão.'
  }
}

async function preVisualizar() {
  erro.value = ''
  try {
    montado.value = await api.get('/api/ia/prompt/montado')
  } catch (e) {
    erro.value = e instanceof ErroDeApi
      ? `${e.message} Publique uma versão primeiro.`
      : 'Não consegui montar.'
  }
}

function quando(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

/* ── A sala de ensaio ───────────────────────────────────────────────────── */

const ensaio = ref({ conversaId: '', texto: '', rodando: false, r: null, erro: '' })

async function ensaiar() {
  const id = Number(ensaio.value.conversaId)
  if (!id) { ensaio.value.erro = 'Informe o número da conversa.'; return }
  ensaio.value.rodando = true
  ensaio.value.erro = ''
  ensaio.value.r = null
  try {
    ensaio.value.r = await api.post('/api/ia/ensaio', {
      conversa_id: id,
      texto: ensaio.value.texto || null,
    })
  } catch (e) {
    /* 🚨 O motivo vem com NOME — "grupo", "humano assumiu", "motor sem chave".
       "Nada aconteceu" mandaria alguém procurar defeito onde há regra. */
    ensaio.value.erro = e instanceof ErroDeApi ? e.message : 'Falha no ensaio.'
  } finally {
    ensaio.value.rodando = false
  }
}
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>IA — prompt</h1>
        <AjudaDaTela>O texto que a IA vai ler, versionado. Cada conversa grava qual versão a atendeu.</AjudaDaTela>
      </div>
      <span v-if="estado?.versao_ativa" class="chip chip--ok">
        versão {{ estado.versao_ativa.versao }} ativa
      </span>
      <span v-else class="chip chip--aviso">nenhuma versão publicada</span>
    </header>

    <p v-if="estado && !canaisComIa.length" class="aviso aviso--info">
      <i class="bi bi-robot aviso__icone" aria-hidden="true"></i>
      <span>
        <strong>A IA está desligada em todos os canais</strong>
        ({{ estado.canais.map((c) => c.nome).join(', ') }}).
        <template v-if="estado.motor_existe">
          O motor está pronto ({{ estado.motor?.modelo }}) — dá para
          <strong>ensaiar</strong> aqui embaixo sem enviar nada a ninguém.
        </template>
        <template v-else>
          O motor está indisponível: {{ estado.motor?.motivo }}
        </template>
        Publicar aqui <strong>não põe a IA no ar</strong> — o interruptor é por canal, na CFG_1.1.
      </span>
    </p>
    <p v-else-if="canaisComIa.length" class="aviso aviso--atencao" role="status">
      <i class="bi bi-broadcast aviso__icone" aria-hidden="true"></i>
      <span>
        <strong>IA LIGADA em:</strong>
        {{ canaisComIa.map((c) => c.nome).join(', ') }}. Publicar aqui muda o que
        ela responde a clientes reais, na hora.
      </span>
    </p>

    <p v-if="recado" class="aviso aviso--ok" role="status">
      <i class="bi bi-check-circle aviso__icone" aria-hidden="true"></i>
      <span>{{ recado }}</span>
    </p>

    <p v-if="erro" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>{{ erro }}</span>
    </p>

    <p v-if="carregando" class="linha fraco">
      <span class="girando"></span> Lendo o prompt…
    </p>

    <template v-else>
      <!-- ⚠️ A ÂNCORA EXISTE PARA A ESCADA (27/08). O passo 1 dela leva aqui,
           e a escada mora nesta mesma aba: sem um lugar para rolar até, o
           botão trocava a URL e nada acontecia na tela — que é o mesmo defeito
           de "botão que não faz nada" que a escada existe para acabar. -->
      <section id="prompt-editor" class="cartao tela__bloco">
        <header class="cartao__cabecalho">
          <span>Editor</span>
          <span v-if="vendo" class="apagado pequeno mono">vendo a versão {{ vendo }}</span>
          <span v-else class="apagado pequeno">rascunho sugerido</span>
        </header>
        <div class="cartao__corpo pilha">
          <label class="campo">
            <span class="so-leitor">Conteúdo do prompt</span>
            <textarea
              v-model="conteudo"
              class="campo__entrada editor mono"
              rows="22"
              spellcheck="false"
            ></textarea>
            <span class="campo__ajuda">
              {{ conteudo.length }} caracteres. As descrições dos times entram sozinhas — não copie para dentro do texto.
            </span>
          </label>

          <div class="linha linha--quebra">
            <button class="botao botao--primario" type="button" :disabled="salvando" @click="gravar(true)">
              <span v-if="salvando" class="girando"></span> Gravar e publicar
            </button>
            <button class="botao botao--contorno" type="button" :disabled="salvando" @click="gravar(false)">
              Gravar como rascunho
            </button>
            <button class="botao botao--fantasma" type="button" @click="preVisualizar">
              <i class="bi bi-eye" aria-hidden="true"></i> Pré-visualizar montado
            </button>
          </div>
        </div>
      </section>

      <section v-if="montado" class="cartao tela__bloco">
        <header class="cartao__cabecalho">
          <span>Como a IA receberia — versão {{ montado.versao }}</span>
          <button class="botao botao--pequeno botao--fantasma" type="button" @click="montado = null">
            fechar
          </button>
        </header>
        <div class="cartao__corpo">
          <pre class="montado mono">{{ montado.texto }}</pre>
        </div>
      </section>

      <section class="cartao tela__bloco">
        <header class="cartao__cabecalho">
          <span>Histórico</span>
          <span class="apagado pequeno">{{ versoes.length }} versão(ões)</span>
        </header>

        <div v-if="!versoes.length" class="cartao__corpo">
          <p class="fraco pequeno">
            Nenhuma versão gravada ainda. A primeira que você publicar vira a
            ativa.
          </p>
        </div>

        <div v-else class="tabela--rolavel">
          <table class="tabela">
            <thead>
              <tr>
                <th>Versão</th>
                <th>Quando</th>
                <th>Autor</th>
                <th>Tamanho</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="v in versoes" :key="v.id">
                <td>
                  <span class="chip" :class="{ 'chip--ok': v.ativo }">v{{ v.versao }}</span>
                  <span v-if="v.ativo" class="pequeno fraco"> ativa</span>
                </td>
                <td class="pequeno fraco">{{ quando(v.criado_em) }}</td>
                <td class="pequeno fraco">{{ v.autor_nome || '—' }}</td>
                <td class="pequeno mono fraco">{{ v.tamanho }}</td>
                <td>
                  <div class="linha">
                    <button class="botao botao--pequeno botao--fantasma" type="button" @click="abrirVersao(v.id)">
                      Abrir
                    </button>
                    <button
                      v-if="!v.ativo"
                      class="botao botao--pequeno botao--contorno"
                      type="button"
                      :disabled="salvando"
                      @click="publicarVersao(v.id, v.versao)"
                    >
                      Voltar para esta
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <!-- ════════════════════════════════════════════════════════════════════
         SALA DE ENSAIO — o passo 3 da sequência de ativação do docs/04.
         🚨 Não envia, não grava, não transfere. Mostra o que ela TERIA feito.
         ════════════════════════════════════════════════════════════════════ -->
    <section v-if="estado?.motor_existe" id="sala-de-ensaio" class="cartao">
      <header class="cartao__cabecalho">
        <div>
          <strong>Sala de ensaio</strong>
          <p class="apagado pequeno">
            Roda a IA de verdade contra uma conversa de verdade —
            <strong>sem enviar nada para o cliente</strong>, sem gravar e sem
            transferir. 
          </p>
        </div>
        <span class="chip chip--acento">{{ estado.motor?.modelo }}</span>
      </header>

      <div class="cartao__corpo pilha">
        <div class="linha linha--quebra">
          <label class="campo">
            <span class="campo__rotulo">Número da conversa</span>
            <input v-model="ensaio.conversaId" class="campo__entrada mono"
                   type="number" inputmode="numeric" placeholder="16224" />
            <span class="campo__ajuda">
              O número que aparece na barra de endereço ao abrir a conversa.
            </span>
          </label>
        </div>

        <label class="campo">
          <span class="campo__rotulo">Pergunta a fazer (opcional)</span>
          <textarea v-model="ensaio.texto" class="campo__entrada" rows="2"
                    maxlength="4000"
                    placeholder="Vazio = ensaia contra a última coisa que o cliente escreveu."></textarea>
        </label>

        <div class="linha">
          <button class="botao botao--primario" type="button"
                  :disabled="ensaio.rodando" @click="ensaiar()">
            <span v-if="ensaio.rodando" class="girando"></span>
            <i v-else class="bi bi-play-circle" aria-hidden="true"></i>
            Ensaiar
          </button>
        </div>

        <p v-if="ensaio.erro" class="aviso aviso--atencao" role="alert">
          <i class="bi bi-info-circle aviso__icone" aria-hidden="true"></i>
          <span>{{ ensaio.erro }}</span>
        </p>

        <div v-if="ensaio.r" class="pilha">
          <p class="ensaio__fala">{{ ensaio.r.texto }}</p>
          <p class="apagado pequeno">
            Ferramentas:
            <strong>{{ (ensaio.r.ferramentas || []).join(' → ') || 'nenhuma' }}</strong>
            · {{ ensaio.r.tokens }} tokens · {{ ensaio.r.provedor }}
          </p>
          <!-- ⚠️ A AÇÃO É O QUE MAIS IMPORTA VER, e é o que não aconteceu.
               Sem mostrar isto, um ensaio que transferiria pareceria um
               ensaio que só respondeu. -->
          <p v-for="(a, i) in (ensaio.r.acoes || [])" :key="i"
             class="aviso aviso--info">
            <i class="bi bi-arrow-right-circle aviso__icone" aria-hidden="true"></i>
            <span v-if="a.acao === 'transferir'">
              <strong>Teria transferido para {{ a.time }}</strong>, com a nota
              interna: “{{ a.resumo }}”
            </span>
            <span v-else>
              <strong>Teria encerrado</strong> a conversa: “{{ a.motivo }}”
            </span>
          </p>
        </div>
      </div>
    </section>

    <p class="apagado pequeno">
      Nenhuma versão é sobrescrita ou apagada: gravar sempre cria a próxima, e
      voltar atrás é republicar a antiga.
    </p>
  </div>
</template>

<style scoped>
.tela { max-width: 1000px; }

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

.linha--quebra { flex-wrap: wrap; gap: var(--e-3); }

.editor {
  min-height: 22rem;
  resize: vertical;
  line-height: 1.55;
  font-size: 0.9rem;
}

.montado {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.85rem;
  line-height: 1.55;
  margin: 0;
  max-height: 30rem;
  overflow: auto;
}

/* O balão do ensaio tem cara de mensagem de WhatsApp de propósito: é assim
   que o texto vai chegar, e ler num parágrafo comum esconde o comprimento. */
.ensaio__fala {
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--fundo-2, rgba(127, 127, 127, 0.1));
  border-radius: var(--r-2, 0.75rem);
  border-top-left-radius: 0.25rem;
  padding: var(--e-3, 0.75rem) var(--e-4, 1rem);
  margin: 0;
  max-width: 34rem;
  line-height: 1.5;
}
</style>
